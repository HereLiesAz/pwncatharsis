import logging
import re
import threading
import time
from collections import deque
from queue import Queue, Empty

import pwncat

log = logging.getLogger("pwncat")


class PwncatSession:
    """Represents an active session, managing IO and subprocess interaction."""

    def __init__(self, session_id, client_address):
        self.id = session_id
        self.platform = "linux"
        self.client_address = client_address
        self.terminal_buffer = deque(maxlen=2048)
        self.terminal_listener = None

        self.command_queue = deque()
        self.utility_queue = Queue()
        self.utility_result = None
        self.utility_marker = None

        self.ssig = pwncat.InterruptHandler(keep_open=True, no_shutdown=False)
        enc = pwncat.StringEncoder()
        self.proc = pwncat.IOCommand(self.ssig, pwncat.DsIOCommand(enc, "/bin/sh", -1))

        threading.Thread(target=self.proc_to_session_loop, daemon=True).start()
        threading.Thread(target=self.session_to_proc_loop, daemon=True).start()
        log.info(f"Session {self.id}: Initialized for {client_address}")

    def proc_to_session_loop(self):
        """Pumps data from the subprocess's stdout to the correct destination."""
        output_buffer = ""
        for data in self.proc.producer():
            decoded_data = pwncat.StringEncoder.decode(data)
            if self.utility_marker and self.utility_marker in decoded_data:
                output_buffer += decoded_data.split(self.utility_marker)[0]
                self.utility_result = output_buffer
                output_buffer = ""
            elif self.utility_marker is not None:
                output_buffer += decoded_data
            else:
                if self.terminal_listener:
                    try:
                        self.terminal_listener.onOutput(decoded_data)
                    except Exception as e:
                        log.error(f"Session {self.id}: Error in terminal_listener.onOutput: {e}")
                self.terminal_buffer.append(data)

    def session_to_proc_loop(self):
        """Prioritizes utility commands, then interactive commands."""
        while not self.ssig.has_terminate():
            try:
                command = self.utility_queue.get_nowait()
                self.proc.consumer(command)
            except Empty:
                if self.command_queue:
                    command = self.command_queue.popleft()
                    self.proc.consumer(command)
                else:
                    time.sleep(0.05)

    def execute_utility_command(self, command: str) -> str:
        """Executes a command and captures its output, separate from the main terminal."""
        marker = f"END_MARKER_{int(time.time())}"
        full_command = f"{command}; echo {marker}\n"

        self.utility_marker = marker
        self.utility_result = None

        self.utility_queue.put(pwncat.StringEncoder.encode(full_command))

        start_time = time.time()
        while self.utility_result is None and not self.ssig.has_terminate():
            if time.time() - start_time > 5:  # 5 second timeout
                log.error(f"Session {self.id}: Timeout waiting for utility command: {command}")
                self.utility_marker = None
                return None

            time.sleep(0.1)

        result = self.utility_result
        self.utility_marker = None
        self.utility_result = None

        return result

    def send_interactive_command(self, command_bytes: bytes):
        """Add a command to the interactive queue."""
        self.command_queue.append(command_bytes)


class SessionIO(pwncat.IO):
    """A custom IO module that acts as a factory for PwncatSession objects."""

    def __init__(self, ssig, sessions_dict_ref, sessions_lock_ref):
        super(SessionIO, self).__init__(ssig)
        self.active_session = None
        self.sessions = sessions_dict_ref
        self.sessions_lock = sessions_lock_ref
        self.next_session_id = 0

    def producer(self, *args, **kwargs):
        yield from ()

    def consumer(self, data):
        with self.sessions_lock:
            if self.active_session is None:
                session_id = self.next_session_id
                client_address_info = self.net_instance.net._Net__active
                addr_str = f"{client_address_info['remote_addr']}:{client_address_info['remote_port']}"
                log.info(f"New connection from {addr_str}, creating session {session_id}")
                self.active_session = PwncatSession(session_id, addr_str)
                self.sessions[session_id] = self.active_session
                self.next_session_id += 1  # This should be managed globally

        self.active_session.send_interactive_command(data)

    def interrupt(self):
        if self.active_session:
            self.active_session.ssig.raise_terminate()
