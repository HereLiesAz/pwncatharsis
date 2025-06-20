import threading
import time
from pwncat.manager import Manager

# This is the global pwncat manager instance
manager = Manager()

def initialize_manager():
    """Initializes the pwncat manager's database."""
    if not manager.db_path.exists():
        manager.initialize()


def get_session(session_id: int):
    """Retrieves a session by its ID."""
    return manager.sessions.get(session_id, None)


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

        while not session.raw_pty.closed:
            # Enumerate Loot
            try:
                current_loot = list(session.find_loot())
                for item in current_loot:
                    # Use a unique tuple to identify the loot item
                    item_key = (item.type, item.source, item.content)
                    if item_key not in known_loot:
                        known_loot.add(item_key)
                        listener.onNewLoot({
                            "type": item.type,
                            "source": item.source,
                            "content": item.content
                        })
            except Exception as e:
                print(f"Loot enumeration failed: {e}")

            # Enumerate Privesc
            try:
                current_privesc = list(session.enumerate_privesc())
                for item in current_privesc:
                    # Use the exploit title as a unique identifier
                    if item.title not in known_privesc:
                        known_privesc.add(item.title)
                        listener.onNewPrivescFinding({
                            "name": item.title,
                            "description": item.description,
                            "exploit_id": item.exploit
                        })
            except Exception as e:
                print(f"Privesc enumeration failed: {e}")

            # Wait before the next enumeration cycle
            time.sleep(15)

    # Run the enumeration in a background thread
    thread = threading.Thread(target=enumeration_loop, daemon=True)
    thread.start()


# --- Other functions (create_listener, get_listeners, list_files, etc.) remain the same ---
def create_listener(uri: str):
    """Creates a new listener and returns its ID and URI."""
    try:
        listener = manager.listen(uri)
        return {"id": listener.id, "uri": str(listener.server.getsockname())}
    except Exception as e:
        return {"error": str(e)}

def get_listeners():
    """Returns a list of active listeners."""
    return [
        {"id": listener.id, "uri": str(listener.server.getsockname())}
        for listener in manager.listeners.values()
    ]

def remove_listener(listener_id: int):
    """Removes a listener by its ID."""
    listener = manager.listeners.get(listener_id)
    if listener:
        listener.stop()

def get_sessions():
    """Returns a list of active sessions."""
    return [
        {
            "id": session.id,
            "platform": session.platform,
        }
        for session in manager.sessions.values()
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
            while not session.raw_pty.closed:
                try:
                    data = session.raw_pty.read(4096, timeout=1)
                    if data:
                        callback.onOutput(data.decode('utf-8', 'ignore'))
                except EOFError:
                    break
        finally:
            callback.onClose()

    if session.raw_pty is None:
        session.run(" ")

    thread = threading.Thread(target=reader_thread, daemon=True)
    thread.start()

def send_to_terminal(session_id: int, command: str):
    session = get_session(session_id)
    if session and session.raw_pty:
        session.raw_pty.write(command.encode('utf-8'))

def list_files(session_id: int, path: str):
    session = get_session(session_id)
    if not session:
        return []
    try:
        results = []
        for file in session.platform.fs.listdir(path):
            results.append({
                "name": file.name,
                "path": file.path,
                "is_dir": file.is_dir
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
        session.platform.fs.download(remote_path, local_path)
        return {"path": local_path}
    except Exception as e:
        return {"error": str(e)}
