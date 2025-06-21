# Module `pwncat`

pwncat.

## Functions

#### `get_args()`

Retrieve command line arguments.

---

#### `get_version()`

Return version information.

---

#### `main()`

Run the program.

## Classes

### `ArgValidator`

Validate command line arguments.

**Static methods**

* `get_port_list_from_string(value)`: Returns a list of ports from an comma, range or increment.
* `is_valid_port(value)`: Returns True if a given value is a valid port.
* `is_valid_port_list(value)`: Returns True if a given value is a valid port list by comma or range.
* `type_color(value)`: Check argument for valid –color value.
* `type_crlf(value)`: Check argument for valid –crlf value.
* `type_file_content(value)`: Check argument for valid file content (file must exist and be
  readable).
* `type_info(value)`: Check argument for valid –info value.
* `type_local(value)`: Check argument for valid -L/–local value.
* `type_port(value)`: Check argument for valid port.
* `type_port_list(value)`: Check argument for valid port list separated by comma or range number.
* `type_remote(value)`: Check argument for valid -R/–remote value.
* `type_self_inject(value)`: Check argument for valid –self-inject value.
* `type_tos(value)`: Check argument for valid –tos value.

---

### `CNC(network)`

Command and Control base class.

* **Subclasses**: `CNCAutoDeploy`
* **Instance variables**:
    * `remote_py3`: Is remote version Python3? Else it is Python2.
    * `remote_python`: Discovered absolute Python remote path.
* **Methods**:
    * `create_remote_tmpfile()`: OS-independent remote tempfile creation.
    * `flush_receive()`: Try to reveive everything which is currently being sent from remote.
    * `print_info(message=None, newline=True, erase=False)`: Print a message to the local screen to
      inform the user.
    * `print_raw(message, newline)`: Print a message to the local screen without color/prefix.
    * `remote_command(command, output)`: Run remote command with correct linefeeds and receive
      response lines.
    * `remote_file_exists(remote_path)`: Ensure given remote path exists as a file on remote end.
    * `send(data)`: Send data through a connected (TCP) or unconnected (UDP) socket.
    * `send_recv(data, strip_suffix=True, strip_echo=False)`: Send data through a connected (TCP) or
      unconnected (UDP) socket and receive all replies.
    * `upload(lpath, rpath)`: OS-independent upload of a local file to a remote path.

---

### `CNCAutoDeploy(network, cmd, host, ports)`

Command&Control pwncat auto deployment class.

* **Ancestors**: `CNC`
* **Inherited members**:
    * `CNC`: `create_remote_tmpfile`, `flush_receive`, `print_info`, `print_raw`, `remote_command`,
      `remote_file_exists`, `remote_py3`, `remote_python`, `send`, `send_recv`, `upload`

---

### `CNCPythonNotFound(*args, **kwargs)`

CNC Exception handler.

* **Ancestors**: `builtins.BaseException`

---

### `ColoredLogFormatter(color, loglevel)`

Custom log formatter which adds different details and color support.

* **Ancestors**: `logging.Formatter`
* **Class variables**:
    * `COLORS`
    * `COLOR_DEF`
    * `COLOR_RST`
* **Methods**:
    * `format(record)`: Apply custom formatting to log message.

---

### `DsCallableProducer(function, *args, **kwargs)`

A type-safe data structure for Callable functions.

* **Instance variables**:
    * `args`: `*args`: optional *args for the callable function.
    * `function`: `IO.producer`: Callable funtcion function.
    * `kwargs`: `**kargs`: optional *kwargs for the callable function.

---

### `DsIOCommand(enc, executable, bufsize)`

A type-safe data structure for IOCommand options.

* **Instance variables**:
    * `bufsize`: `int`: `subprocess.Popen` bufsize.
    * `enc`: `StringEncoder`: Instance of StringEncoder.
    * `executable`: `srt`: Name or path of executable to run (e.g.: `/bin/bash`).

---

### `DsIONetworkCli(reconn, reconn_wait, reconn_robin)`

A type-safe data structure for IONetwork client options.

* **Instance variables**:
    * `reconn`: `int`: If connection fails, retry endless (if negative) or x many times.
    * `reconn_robin`: `[int]`: List of alternating re-connection ports.
    * `reconn_wait`: `float`: Wait time between re-connections in seconds.

---

### `DsIONetworkSock(...)`

A type-safe data structure for IONetwork socket options.

* **Ancestors**: `DsSock`
* **Instance variables**:
    * `recv_timeout_retry`: `int`: How many times to retry receiving if stop signal was raised.
* **Inherited members**:
    * `DsSock`: `backlog`, `bufsize`, `info`, `ip_tos`, `ipv4`, `ipv6`, `nodns`, `recv_timeout`,
      `src_addr`, `src_port`, `udp`, `udp_sconnect`, `udp_sconnect_word`

---

### `DsIONetworkSrv(keep_open, rebind, rebind_wait, rebind_robin)`

A type-safe data structure for IONetwork server options.

* **Instance variables**:
    * `keep_open`: `bool`: Accept new clients if one has disconnected.
    * `rebind`: `int`: If binding fails, retry endless (if negative) or x many times.
    * `rebind_robin`: `[int]`: List of alternating rebind ports.
    * `rebind_wait`: `float`: Wait time between rebinds in seconds.

---

### `DsIOStdinStdout(encoder, input_timeout, send_on_eof)`

A type-safe data structure for IOStdinStdout options.

* **Instance variables**:
    * `enc`: `StringEncoder`: String encoder instance.
    * `input_timeout`: `float`: Input timeout in seconds for non-blocking read or `None` for
      blocking.
    * `send_on_eof`: `float`: Determines if we buffer STDIN until EOF before sending.

---

### `DsRunnerAction(...)`

A type-safe data structure for Action functions for the Runner class.

* **Instance variables**:
    * `code`: `ast.AST`: custom Python code which provides a `transform(data, pse) -> str` function.
    * `consumer`: `IO.consumer`: Data consumer function.
    * `daemon_thread`: `bool`: Determines if the action will be started in a daemon thread.
    * `interrupts`: `[List[Callable[[], None]]]`: List of interrupt functions for the
      producer/consumer.
    * `producer`: `DsCallableProducer`: Data producer function struct with args and kwargs.
    * `transformers`: `[Transform.transformer]`: List of transformer functions applied before
      consumer.

---

### `DsRunnerRepeater(...)`

A type-safe data structure for repeated functions for the Runner class.

* **Instance variables**:
    * `action`: `Callable[…, None]`: function to be run periodically.
    * `args`: `*args`: optional *args for the action function.
    * `kwargs`: `**kargs`: optional *kwargs for the action function.
    * `pause`: `int`: pause in seconds between repeated action calls.
    * `repeat`: `int`: how many times to repeat the action function.
    * `ssig`: `InterruptHandler`: InterruptHandler instance.

---

### `DsRunnerTimer(...)`

A type-safe data structure for Timer functions for the Runner class.

* **Instance variables**:
    * `action`: `Callable[…, None]`: function to be run periodically.
    * `args`: `*args`: optional *args for the action function.
    * `intvl`: `int`: interval at which to run the action function..
    * `kwargs`: `**kargs`: optional *kwargs for the action function.
    * `ssig`: `InterruptHandler`: InterruptHandler instance.

---

### `DsSock(...)`

A type-safe data structure for DsSock options.

* **Subclasses**: `DsIONetworkSock`
* **Instance variables**:
    * `backlog`: `int`: Listen backlog.
    * `bufsize`: `int`: Receive buffer size.
    * `info`: `str`: Determines what info to display about the socket connection.
    * `ip_tos`: `str`: Determines what IP_TOS (Type of Service) value to set for the socket.
    * `ipv4`: `bool`: Only use IPv4 instead of both, IPv4 and IPv6.
    * `ipv6`: `bool`: Only use IPv6 instead of both, IPv4 and IPv6.
    * `nodns`: `bool`: Determines if we resolve hostnames or not.
    * `recv_timeout`: `float` or `None`: Receive timeout to change blocking socket to time-out
      based.
    * `src_addr`: `bool`: Custom source address for connect mode.
    * `src_port`: `bool`: Custom source port for connect mode.
    * `udp`: `bool`: Determines if we use TCP or UDP.
    * `udp_sconnect`: `bool`: Determines if we use stateful connect for UDP.
    * `udp_sconnect_word`: `str`: What string to send when emulating a stateful UDP connect.

---

### `DsTransformLinefeed(crlf)`

A type-safe data structure for DsTransformLinefeed options.

* **Instance variables**:
    * `crlf`: `bool`: Converts line endings to LF, CRLF or CR and noop on `None`.

---

### `DsTransformSafeword(ssig, safeword)`

A type-safe data structure for DsTransformSafeword options.

* **Instance variables**:
    * `safeword`: `str`: The safeword to shutdown the instance upon receiving.
    * `ssig`: `InterruptHandler`: InterruptHandler instance to trigger a shutdown signal.

---

### `IO(ssig)`

Abstract class to for pwncat I/O modules.

* **Ancestors**: `abc.ABC`
* **Subclasses**: `IOCommand`, `IONetwork`, `IONetworkScanner`, `IOStdinStdout`
* **Instance variables**:
    * `log`: `TraceLogger`: Logger instance.
    * `ssig`: `InterruptHandler`: InterruptHandler instance.
* **Methods**:
    * `consumer(data)`: Define a consumer callback which will apply an action on the producer
      output.
    * `interrupt()`: Define an interrupt function which will stop the producer.
    * `producer(*args, **kwargs)`: Implement a generator function which constantly yields data.

---

### `IOCommand(ssig, opts)`

Implement command execution functionality.

* **Ancestors**: `IO`, `abc.ABC`
* **Methods**:
    * `consumer(data)`: Send data received to stdin (command input).
    * `interrupt()`: Stop function that can be called externally to close this instance.
    * `producer(*args, **kwargs)`: Constantly ask for input.
* **Inherited members**:
    * `IO`: `log`, `ssig`

---

### `IONetwork(...)`

Pwncat implementation based on custom Socket library.

* **Ancestors**: `IO`, `abc.ABC`
* **Instance variables**:
    * `net`: Returns instance of Net.
* **Methods**:
    * `consumer(data)`: Send data to a socket.
    * `interrupt()`: Stop function that can be called externally to close this instance.
    * `producer(*args, **kwargs)`: Network receive generator which hooks into the receive function
      and adds features.
* **Inherited members**:
    * `IO`: `log`, `ssig`

---

### `IONetworkScanner(...)`

Pwncat Scanner implementation based on custom Socket library.

* **Ancestors**: `IO`, `abc.ABC`
* **Class variables**:
    * `BANNER_PAYLOADS`
    * `BANNER_REG`
    * `BANNER_REG_COMP`
* **Methods**:
    * `consumer(data)`: Print received data to stdout.
    * `interrupt()`: Stop function that can be called externally to close this instance.
    * `producer(*args, **kwargs)`: Port scanner yielding open/closed string for given port.
* **Inherited members**:
    * `IO`: `log`, `ssig`

---

### `IOStdinStdout(ssig, opts)`

Implement basic stdin/stdout I/O module.

* **Ancestors**: `IO`, `abc.ABC`
* **Methods**:
    * `consumer(data)`: Print received data to stdout.
    * `interrupt()`: Stop function that can be called externally to close this instance.
    * `producer(*args, **kwargs)`: Constantly ask for user input.
* **Inherited members**:
    * `IO`: `log`, `ssig`

---

### `InterruptHandler(keep_open, no_shutdown)`

Pwncat interrupt handler.

* **Methods**:
    * `has_command_quit()`: `bool`: Switch to be checked if the command should be closed.
    * `has_sock_quit()`: `bool`: Switch to be checked if the socket connection should be closed.
    * `has_sock_send_eof()`: `bool`: Switch to be checked if the socket connection should be closed
      for sending.
    * `has_stdin_quit()`: `bool`: Switch to be checked if the STDIN should be closed.
    * `has_terminate()`: `bool`: Switch to be checked if pwncat should be terminated.
    * `raise_command_eof()`: Signal the application that Command has received EOF.
    * `raise_command_quit()`: Signal the application that Command should be quit.
    * `raise_sock_eof()`: Signal the application that Socket has received EOF.
    * `raise_sock_quit()`: Signal the application that Socket should be quit.
    * `raise_sock_send_eof()`: Signal the application that Socket should be closed for sending.
    * `raise_stdin_eof()`: Signal the application that STDIN has received EOF.
    * `raise_stdin_quit()`: Signal the application that STDIN should be quit.
    * `raise_terminate()`: Signal the application that Socket should be quit.

---

### `Net(encoder, ssig, options)`

Provides an abstracted server client socket for TCP and UDP.

* **Methods**:
    * `close_bind_sock()`: Close the bind socket used by the server to accept clients.
    * `close_conn_sock()`: Close the communication socket used for send and receive.
    * `re_accept_client()`: Re-accept new clients, if connection is somehow closed or accept did not
      work.
    * `receive()`: Receive and return data from the connected (TCP) or unconnected (UDP) socket.
    * `run_client(host, port)`: Run and create a TCP or UDP client and connect to a remote peer.
    * `run_server(host, port)`: Run and create a TCP or UDP listening server and wait for a client
      to connect.
    * `send(data)`: Send data through a connected (TCP) or unconnected (UDP) socket.
    * `send_eof()`: Close the active socket for sending. The remote part will get an EOF.

---

### `PSEStore(ssig, net)`

Pwncats Scripting Engine store to persist and exchange data for send/recv scripts.

* **Instance variables**:
    * `log`: `Logging.logger`: Instance of Logging.logger class.
    * `messages`: `Dict[str, List[bytes]]`: Stores sent and received messages by its thread name.
    * `net`: `IONetwork`: List of active IONetwork instances (client or server).
    * `ssig`: `InterruptHandler`: Instance of InterruptHandler class.
    * `store`: `Any`: Custom data store to be used in PSE scripts to persist your data between
      calls.

---

### `Runner(ssig, fast_quit, pse)`

Runner class that takes care about putting everything into threads.

* **Methods**:
    * `add_action(name, action)`: Add a function to the producer/consumer thread pool runner.
    * `add_repeater(name, repeater)`: Add a function to the repeater thread pool runner.
    * `add_timer(name, timer)`: Add a function to the timer thread pool runner.
    * `run()`: Run threaded pwncat I/O modules.

---

### `Sock()`

Thread-safe singleton Socket wrapper to emulate a module within the same file.

* **Ancestors**: `pwncat.SingletonMeta`
* **Static methods**:
    * `is_ipv4_address(host)`: Check if a given str is a valid IPv4 address.
    * `is_ipv6_address(host)`: Check if a given str is a valid IPv6 address.
* **Methods**:
    * `accept(sockets, has_quit, select_timeout=0.01)`: Accept a single connection from given list
      of sockets.
    * `bind(sock, addr, port)`: Bind the socket to an address.
    * `close(sock, name)`: Shuts down and closes a socket.
    * `connect(...)`: Connect to a remote socket at given address and port.
    * `create_socket(family, sock_type, reuse_addr, ip_tos_name=None)`: Create TCP or UDP socket.
    * `get_family_name(family)`: Returns human readable name of given address family as str.
    * `get_iptos_by_name(name)`: Get IP Type of Service hexadecimal value by name.
    * `get_sock_opts(sock, opts)`: Debug logs configured socket options.
    * `get_type_name(sock_type)`: Returns human readable name of given socket type as str.
    * `gethostbyname(host, family, resolvedns)`: Translate hostname into a IP address for a given
      address family.
    * `listen(sock, backlog)`: Listen for connections made to the socket.
    * `shutdown_recv(sock, name)`: Shuts down a socket for receiving data (only allow to send data).
    * `shutdown_send(sock, name)`: Shuts down a socket for sending data (only allow to receive
      data).

---

### `StringEncoder`

Takes care about Python 2/3 string encoding/decoding.

* **Class variables**:
    * `CODECS`
* **Static methods**:
    * `decode(data)`: Convert bytes into a string type for Python3.
    * `encode(data)`: Convert string into a byte type for Python3.
    * `rstrip(data, search=None)`: Implementation of rstring which works on bytes or strings.

---

### `TraceLogger(name, level=0)`

Extend Python's default logger class with TRACE level logging.

* **Ancestors**: `logging.Logger`, `logging.Filterer`
* **Class variables**:
    * `LEVEL_NAME`
    * `LEVEL_NUM`
* **Methods**:
    * `trace(msg, *args, **kwargs)`: Set custom log level for TRACE.

---

### `Transform()`

Abstract class to for pwncat I/O transformers.

* **Ancestors**: `abc.ABC`
* **Subclasses**: `TransformHttpPack`, `TransformHttpUnpack`, `TransformLinefeed`,
  `TransformSafeword`
* **Instance variables**:
    * `log`: `TraceLogger`: Logger instance.
* **Methods**:
    * `transform(data)`: Implement a transformer function which transforms a string..

---

### `TransformHttpPack(opts)`

Implement a transformation to pack data into HTTP packets.

* **Ancestors**: `Transform`, `abc.ABC`
* **Methods**:
    * `transform(data)`: Wrap data into a HTTP packet.
* **Inherited members**:
    * `Transform`: `log`

---

### `TransformHttpUnpack(opts)`

Implement a transformation to unpack data from HTTP packets.

* **Ancestors**: `Transform`, `abc.ABC`
* **Methods**:
    * `transform(data)`: Unwrap data from a HTTP packet.
* **Inherited members**:
    * `Transform`: `log`

---

### `TransformLinefeed(opts)`

Implement basic linefeed replacement.

* **Ancestors**: `Transform`, `abc.ABC`
* **Methods**:
    * `transform(data)`: Transform linefeeds to CRLF, LF or CR if requested.
* **Inherited members**:
    * `Transform`: `log`

---

### `TransformSafeword(opts)`

Implement a trigger to emergency shutdown upon receival of a specific safeword.

* **Ancestors**: `Transform`, `abc.ABC`
* **Methods**:
    * `transform(data)`: Raise a stop signal upon receiving the safeword.
* **Inherited members**:
    * `Transform`: `log`