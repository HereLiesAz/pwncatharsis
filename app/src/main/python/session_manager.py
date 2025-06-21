import threading
import time
from pwncat.manager import Manager

# This is the global pwncat manager instance
# NOTE: The API for `pwncat` (cytopia) is different from `pwncat-cs`.
# This `session_manager` has been rewritten to use the new API.
manager = Manager()

def initialize_manager():
    """Initializes the pwncat manager."""
    # The new `pwncat` does not require explicit database initialization
    # in the same way `pwncat-cs` did.
    pass

def get_session(session_id: int):
    """Retrieves a session by its ID."""
    try:
        return manager.sessions[session_id]
    except (IndexError, KeyError):
        return None

def start_persistent_enumeration(session_id: int, listener):
    """
    Runs enumeration modules in a loop and calls back to Kotlin
    with discovered items.
    """
    session = get_session(session_id)
    if not session:
        return

    def enumeration_loop():
        """The main loop for the background thread."""
        known_loot = set()
        known_privesc = set()

        while not session.is_alive():
            # NOTE: The `pwncat` API for loot and privesc is different.
            # This is a placeholder implementation and will need to be adapted
            # once we have a better understanding of the new API.
            try:
                # Placeholder for loot enumeration
                pass
            except Exception as e:
                print(f"Loot enumeration failed: {e}")

            try:
                # Placeholder for privesc enumeration
                pass
            except Exception as e:
                print(f"Privesc enumeration failed: {e}")

            time.sleep(15)

    thread = threading.Thread(target=enumeration_loop, daemon=True)
    thread.start()


def create_listener(uri: str):
    """Creates a new listener and returns its ID and URI."""
    try:
        listener = manager.create_listener(uri)
        return {"id": listener.id, "uri": str(listener.addr)}
    except Exception as e:
        return {"error": str(e)}

def get_listeners():
    """Returns a list of active listeners."""
    return [
        {"id": listener.id, "uri": str(listener.addr)}
        for listener in manager.listeners
    ]

def remove_listener(listener_id: int):
    """Removes a listener by its ID."""
    try:
        manager.remove_listener(manager.listeners[listener_id])
    except (IndexError, KeyError):
        pass

def get_sessions():
    """Returns a list of active sessions."""
    return [
        {
            "id": session.id,
            "platform": session.platform,
        }
        for session in manager.sessions
    ]

def start_interactive_session(session_id: int, callback):
    """
    Starts an interactive pty for a session and streams output
    to the provided Kotlin callback.
    """
    session = get_session(session_id)
    if not session:
        return

    def reader_thread():
        try:
            while session.is_alive():
                try:
                    data = session.recv(4096)
                    if data:
                        callback.onOutput(data.decode('utf-8', 'ignore'))
                except EOFError:
                    break
        finally:
            callback.onClose()

    thread = threading.Thread(target=reader_thread, daemon=True)
    thread.start()

def send_to_terminal(session_id: int, command: str):
    session = get_session(session_id)
    if session and session.is_alive():
        session.send(command.encode('utf-8'))

def list_files(session_id: int, path: str):
    session = get_session(session_id)
    if not session:
        return []
    try:
        # NOTE: The API for filesystem interaction is likely different.
        # This is a placeholder implementation.
        results = []
        for entry in session.platform.fs.listdir(path):
            results.append({
                "name": entry.name,
                "path": entry.path,
                "is_dir": entry.is_dir,
            })
        return results
    except Exception as e:
        print(f"Error listing files at {path}: {e}")
        return []


def read_file(session_id: int, path: str):
    session = get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    try:
        # NOTE: The API for filesystem interaction is likely different.
        # This is a placeholder implementation.
        with session.platform.fs.open(path, "r") as f:
            content = f.read(1024 * 1024)
            return {"content": content}
    except Exception as e:
        return {"error": str(e)}

def download_file(session_id: int, remote_path: str, local_path: str):
    session = get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    try:
        # NOTE: The API for filesystem interaction is likely different.
        # This is a placeholder implementation.
        session.platform.fs.download(remote_path, local_path)
        return {"path": local_path}
    except Exception as e:
        return {"error": str(e)}