import asyncio
import os
import pty
import tempfile
from pwncat.manager import Manager
from typing import List

manager = Manager()


# --- Session Management ---

def get_sessions() -> List[dict]:
    return [
        {
            "id": session.id,
            "platform": session.platform,
            "protocol": session.protocol,
            "address": str(session.client),
        }
        for session in manager.sessions.values()
    ]


def get_session(session_id: int):
    return manager.sessions.get(session_id)


def remove_session(session_id: int):
    session = get_session(session_id)
    if session:
        session.close()
        return True
    return False


# --- Listener Management ---

def get_listeners() -> List[dict]:
    return [
        {"id": listener.id, "protocol": listener.protocol, "address": str(listener.server)}
        for listener in manager.listeners.values()
    ]


def create_listener(protocol: str, host: str, port: int):
    # This might need more robust error handling
    listener = manager.listen(protocol=protocol, address=(host, port))
    return {"id": listener.id, "protocol": listener.protocol, "address": str(listener.server)}


def remove_listener(listener_id: int):
    listener = manager.listeners.get(listener_id)
    if listener:
        listener.stop()
        return True
    return False


# --- Filesystem Operations ---
async def list_files(session_id: int, path: str):
    session = get_session(session_id)
    if not session:
        return None
    try:
        return await asyncio.to_thread(session.platform.fs.listdir, path)
    except (FileNotFoundError, PermissionError) as e:
        raise e


async def read_file(session_id: int, path: str):
    session = get_session(session_id)
    if not session:
        return None
    try:
        with session.platform.fs.open(path, "r") as f:
            # Limit read size to prevent OOM on large files
            return f.read(1024 * 1024), f.name
    except (FileNotFoundError, PermissionError) as e:
        raise e


async def download_file(session_id: int, path: str):
    session = get_session(session_id)
    if not session:
        return None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        session.platform.fs.download(path, tmp_path)
        return tmp_path
    except Exception as e:
        # Clean up in case of error
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise e


async def upload_file(session_id: int, destination_path: str, file_content: bytes):
    session = get_session(session_id)
    if not session:
        return None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        session.platform.fs.upload(tmp_path, destination_path)
        return {"path": destination_path}
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# --- Process Operations ---
def list_processes(session_id: int):
    session = get_session(session_id)
    if session:
        return session.platform.ps()
    return None


# --- Network Operations ---
def get_network_info(session_id: int):
    session = get_session(session_id)
    if session:
        return session.platform.ifconfig()
    return None


# --- Privilege Escalation ---
def get_privesc_findings(session_id: int):
    session = get_session(session_id)
    if session:
        # Assuming facts are stored/cached in the session object somehow
        return session.facts.get("privesc", [])
    return None


def run_privesc_scan(session_id: int):
    session = get_session(session_id)
    if session:
        # This will block, consider running in a thread
        return session.platform.find_suid()
    return None

# ... other functions would go here
