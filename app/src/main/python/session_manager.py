import threading
import pwncat
import time
from collections import deque
import logging
import re
from queue import Queue, Empty

# --- Globals ---
listeners = {}
sessions = {}
next_listener_id = 0
next_session_id = 0
sessions_lock = threading.Lock()
log = logging.getLogger("pwncat")

# --------------------------------------------------------------------
# Helper function to parse 'ls -lA --time-style=long-iso' output
def parse_ls_output(output: str):
    items = []
    # Regex to capture permissions, links, owner, group, size, date, time, and name
    # drwxr-xr-x 2 root root 4096 2023-10-27 09:41 mydir
    # -rw-r--r-- 1 user user  123 2023-10-27 09:42 file.txt
    # lrw-r--r-- 1 user user   20 2023-10-27 09:43 symlink -> target
    ls_pattern = re.compile(
        r"^(?P<type>[d\-l])(?P<perms>.{9})\s+"  # type and permissions
        r"(?P<links>\d+)\s+"  # number of links
        r"(?P<owner>\S+)\s+"  # owner
        r"(?P<group>\S+)\s+"  # group
        r"(?P<size>\d+)\s+"  # size
        r"(?P<date>\d{4}-\d{2}-\d{2})\s+"  # date
        r"(?P<time>\d{2}:\d{2})\s+"  # time
        r"(?P<name>.+)"  # name
    )

    for line in output.strip().splitlines():
        match = ls_pattern.match(line.strip())
        if match:
            details = match.groupdict()
            is_dir = details['type'] == 'd'
            # Handle symlinks in the name
            name_part = details['name']
            if ' -> ' in name_part:
                name = name_part.split(' -> ')[0]
            else:
                name = name_part

            items.append({
                "name": name,
                "path": name,  # Path will be corrected in the list_files function
                "is_dir": is_dir
            })
    return items

class PwncatSession:
    """Represents an active session, managing IO and subprocess interaction."""

    def __init__(self, session_id, client_address):
        self.id = session_id
        self.platform = "linux"  # Assume linux for now for ls command
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
                # End of utility command output
                output_buffer += decoded_data.split(self.utility_marker)[0]
                self.utility_result = output_buffer
                output_buffer = ""
            elif self.utility_marker is not None:
                # Accumulating utility command output
                output_buffer += decoded_data
            else:
                # Normal interactive terminal output
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
                # Utility commands have priority
                command = self.utility_queue.get_nowait()
                self.proc.consumer(command)
            except Empty:
                # No utility commands, check for interactive
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

        # Wait for the result
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
    """
    A custom IO module that acts as a factory for PwncatSession objects.
    """
    def __init__(self, ssig):
        super(SessionIO, self).__init__(ssig)
        self.active_session = None

    def producer(self, *args, **kwargs):
        yield from ()

    def consumer(self, data):
        global next_session_id
        with sessions_lock:
            if self.active_session is None:
                session_id = next_session_id
                client_address_info = self.net_instance.net._Net__active
                addr_str = f"{client_address_info['remote_addr']}:{client_address_info['remote_port']}"
                log.info(f"New connection from {addr_str}, creating session {session_id}")
                self.active_session = PwncatSession(session_id, addr_str)
                sessions[session_id] = self.active_session
                next_session_id += 1

        self.active_session.send_interactive_command(data)

    def interrupt(self):
        if self.active_session:
            self.active_session.ssig.raise_terminate()

def initialize_manager():
    p_log = logging.getLogger("pwncat")
    p_log.setLevel(logging.CRITICAL)

def create_listener(uri: str):
    global next_listener_id
    try:
        proto, _, host_port = uri.partition("://")
        host, _, port_str = host_port.rpartition(":")
        port = int(port_str)

        is_udp = proto.lower() == "udp"
        ssig = pwncat.InterruptHandler(keep_open=True, no_shutdown=False)
        enc = pwncat.StringEncoder()
        sock_opts = pwncat.DsIONetworkSock(pwncat.RECV_BUFSIZE, pwncat.LISTEN_BACKLOG,
                                           pwncat.TIMEOUT_RECV_SOCKET,
                                           pwncat.TIMEOUT_RECV_SOCKET_RETRY, False, False, False,
                                           None, None, is_udp, False, "", None, "")
        srv_opts = pwncat.DsIONetworkSrv(True, -1, 1.0, [])
        cli_opts = pwncat.DsIONetworkCli(-1, 1.0, [])
        net = pwncat.IONetwork(ssig, enc, host, [port], "server", srv_opts, cli_opts, sock_opts)

        session_io = SessionIO(ssig)
        session_io.net_instance = net

        run = pwncat.Runner(ssig, False, pwncat.PSEStore(ssig, [net]))
        run.add_action("NET_TO_SESSION_IO",
                       pwncat.DsRunnerAction(pwncat.DsCallableProducer(net.producer),
                                             session_io.consumer, [net.interrupt], [], False, None))

        listener_id = next_listener_id
        thread = threading.Thread(target=run.run, daemon=True, name=f"Listener-{listener_id}")
        thread.start()

        listeners[listener_id] = {"id": listener_id, "uri": uri, "thread": thread, "ssig": ssig}
        next_listener_id += 1
        return {"id": listener_id, "uri": uri}
    except Exception as e:
        log.error(f"Create Listener Error: {e}")
        return {"error": str(e)}

def get_listeners():
    return [{"id": l["id"], "uri": l["uri"]} for l in listeners.values()]

def remove_listener(listener_id: int):
    if listener_id in listeners:
        listeners[listener_id]["ssig"].raise_terminate()
        del listeners[listener_id]

def get_sessions():
    with sessions_lock:
        dead_sessions = [sid for sid, s in sessions.items() if s.proc.proc.poll() is not None]
        for sid in dead_sessions:
            log.info(f"Cleaning up dead session {sid}")
            del sessions[sid]
        return [{"id": s.id, "platform": s.platform} for s in sessions.values()]

def start_interactive_session(session_id: int, callback):
    with sessions_lock:
        if session_id in sessions:
            session = sessions[session_id]
            session.terminal_listener = callback
            log.info(f"Attaching terminal listener to session {session_id}")
            for item in list(session.terminal_buffer):
                callback.onOutput(pwncat.StringEncoder.decode(item))
        else:
            if callback: callback.onClose()

def send_to_terminal(session_id: int, command: str):
    with sessions_lock:
        if session_id in sessions:
            sessions[session_id].send_interactive_command(pwncat.StringEncoder.encode(command))


def list_files(session_id: int, path: str):
    with sessions_lock:
        if session_id in sessions:
            session = sessions[session_id]
            command = f"ls -lA --time-style=long-iso \"{path}\""
            output = session.execute_utility_command(command)
            if output:
                parsed_items = parse_ls_output(output)
                for item in parsed_items:
                    if path == "/":
                        item['path'] = f"/{item['name']}"
                    else:
                        item['path'] = f"{path.rstrip('/')}/{item['name']}"
                return parsed_items
            return []
    return []


def read_file(session_id: int, path: str):
    with sessions_lock:
        if session_id in sessions:
            session = sessions[session_id]
            command = f"cat \"{path}\""
            content = session.execute_utility_command(command)
            if content is not None:
                return {"content": content}
            else:
                return {"error": f"Failed to read file: {path}"}
    return {"error": "Session not found"}


# --- Stubs for future implementation ---
def download_file(session_id: int, remote_path: str, local_path: str): return {
    "error": "Not implemented"}
def run_exploit(session_id: int, exploit_id: str): return {"error": "Not implemented"}
def start_persistent_enumeration(session_id: int, listener): pass