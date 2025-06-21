import threading
import time
from collections import deque

import pwncat

# --- Globals ---
listeners = {}
sessions = {}
next_listener_id = 0
next_session_id = 0
sessions_lock = threading.Lock()


# --------------------------------------------------------------------

class PwncatSession:
    """Represents an active session, holding its state."""

    def __init__(self, session_id, transport_ssig):
        self.id = session_id
        self.platform = "unknown"  # This will be determined later
        self.terminal_buffer = deque(maxlen=1024)
        self.terminal_listener = None
        self.enumeration_listener = None

        # The underlying process for this session
        self.ssig = pwncat.InterruptHandler(keep_open=True, no_shutdown=False)
        self.proc = pwncat.IOCommand(self.ssig,
                                     pwncat.DsIOCommand(pwncat.StringEncoder(), "/bin/sh", -1))

        # The runner that connects the session's IO to the process
        self.runner = pwncat.Runner(self.ssig, False, pwncat.PSEStore(self.ssig, []))

        # This connects the session's producer (data from client) to the process's consumer (stdin)
        self.runner.add_action(
            f"SESSION_TO_PROC_{self.id}",
            pwncat.DsRunnerAction(
                pwncat.DsCallableProducer(self.producer),
                self.proc.consumer,
                [self.ssig.raise_terminate], [], True, None
            ),
        )
        # This connects the process's producer (stdout) to the session's consumer (send to client and buffer)
        self.runner.add_action(
            f"PROC_TO_SESSION_{self.id}",
            pwncat.DsRunnerAction(
                pwncat.DsCallableProducer(self.proc.producer),
                self.consumer,
                [self.proc.interrupt], [], True, None
            ),
        )

        self.thread = threading.Thread(target=self.runner.run, daemon=True)
        self.thread.start()

    def producer(self, *args, **kwargs):
        # This will be implemented to yield data received from the remote client
        pass

    def consumer(self, data):
        # This will be implemented to send data to the remote client
        # and also update the terminal buffer.
        self.terminal_buffer.append(data)
        if self.terminal_listener:
            self.terminal_listener.onOutput(pwncat.StringEncoder.decode(data))


class SessionIO(pwncat.IO):
    """
    A custom IO module that acts as a factory for PwncatSession objects.
    When a client connects, this class's consumer is called, which then
    spawns and registers a full PwncatSession.
    """

    def __init__(self, ssig):
        super(SessionIO, self).__init__(ssig)
        self.active_session = None

    def producer(self, *args, **kwargs):
        if self.active_session:
            yield from self.active_session.producer(*args, **kwargs)
        else:
            # Before a session is active, yield nothing.
            while not self.ssig.has_terminate() and self.active_session is None:
                time.sleep(0.1)

    def consumer(self, data):
        global next_session_id
        with sessions_lock:
            if self.active_session is None:
                session_id = next_session_id
                self.log.info(f"New connection detected, creating session {session_id}")
                self.active_session = PwncatSession(session_id, self.ssig)
                sessions[session_id] = self.active_session
                next_session_id += 1

        # Pass the first and all subsequent data to the active session's process
        self.active_session.proc.consumer(data)

    def interrupt(self):
        if self.active_session:
            self.active_session.ssig.raise_terminate()


def initialize_manager():
    pass


def create_listener(uri: str):
    global next_listener_id
    try:
        proto, _, host_port = uri.partition("://")
        host, _, port_str = host_port.rpartition(":")
        port = int(port_str)

        if proto.lower() not in ["tcp", "udp"]:
            return {"error": f"Unsupported protocol: {proto}"}

        is_udp = proto.lower() == "udp"
        ssig = pwncat.InterruptHandler(keep_open=True, no_shutdown=False)
        enc = pwncat.StringEncoder()

        sock_opts = pwncat.DsIONetworkSock(
            pwncat.RECV_BUFSIZE, pwncat.LISTEN_BACKLOG, pwncat.TIMEOUT_RECV_SOCKET,
            pwncat.TIMEOUT_RECV_SOCKET_RETRY, False, False, False, None, None,
            is_udp, False, "", None, ""
        )
        srv_opts = pwncat.DsIONetworkSrv(True, -1, 1.0, [])
        cli_opts = pwncat.DsIONetworkCli(-1, 1.0, [])

        net = pwncat.IONetwork(ssig, enc, host, [port], "server", srv_opts, cli_opts, sock_opts)

        # Use our custom SessionIO to handle incoming connections
        session_io = SessionIO(ssig)

        run = pwncat.Runner(ssig, False, pwncat.PSEStore(ssig, [net]))

        # From Network to our SessionIO
        run.add_action(
            "NET_TO_SESSION_IO",
            pwncat.DsRunnerAction(
                pwncat.DsCallableProducer(net.producer),
                session_io.consumer,
                [net.interrupt, session_io.interrupt], [], False, None
            ),
        )
        # From our SessionIO to Network
        run.add_action(
            "SESSION_IO_TO_NET",
            pwncat.DsRunnerAction(
                pwncat.DsCallableProducer(session_io.producer),
                net.consumer,
                [net.interrupt, session_io.interrupt], [], False, None
            ),
        )

        listener_id = next_listener_id
        thread = threading.Thread(target=run.run, daemon=True)
        thread.start()

        listeners[listener_id] = {"id": listener_id, "uri": uri, "thread": thread, "ssig": ssig}
        next_listener_id += 1

        return {"id": listener_id, "uri": uri}

    except Exception as e:
        return {"error": str(e)}


def get_listeners():
    return [{"id": l["id"], "uri": l["uri"]} for l in listeners.values()]


def remove_listener(listener_id: int):
    if listener_id in listeners:
        listeners[listener_id]["ssig"].raise_terminate()
        del listeners[listener_id]
    return


def get_sessions():
    with sessions_lock:
        return [
            {"id": s.id, "platform": s.platform}
            for s in sessions.values()
        ]


def start_interactive_session(session_id: int, callback):
    with sessions_lock:
        if session_id in sessions:
            session = sessions[session_id]
            session.terminal_listener = callback
            # Replay buffer
            for item in session.terminal_buffer:
                callback.onOutput(pwncat.StringEncoder.decode(item))
        else:
            if callback: callback.onClose()


def send_to_terminal(session_id: int, command: str):
    with sessions_lock:
        if session_id in sessions:
            sessions[session_id].proc.consumer(pwncat.StringEncoder.encode(command))


def list_files(session_id: int, path: str): return []


def read_file(session_id: int, path: str): return {"error": "Not implemented"}


def download_file(session_id: int, remote_path: str, local_path: str): return {
    "error": "Not implemented"}


def run_exploit(session_id: int, exploit_id: str): return {"error": "Not implemented"}


def start_persistent_enumeration(session_id: int, listener): pass
