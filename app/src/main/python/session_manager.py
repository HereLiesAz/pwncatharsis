import logging
import threading
from session import SessionIO, PwncatSession

import pwncat
from files import list_files as list_files_impl, read_file as read_file_impl

# --- Globals ---
listeners = {}
sessions = {}
next_listener_id = 0
sessions_lock = threading.Lock()
log = logging.getLogger("pwncat")

# --------------------------------------------------------------------

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

        session_io = SessionIO(ssig, sessions, sessions_lock)
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
    return list_files_impl(session_id, path, sessions, sessions_lock)

def read_file(session_id: int, path: str):
    return read_file_impl(session_id, path, sessions, sessions_lock)

# --- Stubs for future implementation ---
def download_file(session_id: int, remote_path: str, local_path: str): return {
    "error": "Not implemented"}
def run_exploit(session_id: int, exploit_id: str): return {"error": "Not implemented"}
def start_persistent_enumeration(session_id: int, listener): pass