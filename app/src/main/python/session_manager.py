import threading
from pwncat.manager import Manager

# This is the global pwncat manager instance
manager = Manager()


def initialize_manager():
    """Initializes the pwncat manager's database."""
    if not manager.db_path.exists():
        manager.initialize()


def create_listener(uri: str):
    """Creates a new listener and returns its ID and URI."""
    try:
        listener = manager.listen(uri)
        return {"id": listener.id, "uri": str(listener.server.getsockname())}
    except Exception as e:
        # It's good practice to return error details
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


def get_session(session_id: int):
    """Retrieves a session by its ID."""
    return manager.sessions.get(session_id, None)


def start_interactive_session(session_id: int, callback):
    """
    Starts an interactive pty for a session and streams output
    to the provided Kotlin callback.
    """
    session = get_session(session_id)
    if not session:
        return

    def reader_thread():
        """Reads from the session's PTY and sends data to the callback."""
        try:
            while not session.raw_pty.closed:
                try:
                    data = session.raw_pty.read(4096, timeout=1)
                    if data:
                        # Call the onOutput method on the Kotlin callback object
                        callback.onOutput(data.decode('utf-8', 'ignore'))
                except EOFError:
                    break
        finally:
            # Notify the client that the session has closed
            callback.onClose()

    # The PTY might not exist until a command is run, ensure it's there.
    if session.raw_pty is None:
        session.run(" ")  # Run a dummy command to initialize PTY

    # Run the reader in a background thread so it doesn't block
    thread = threading.Thread(target=reader_thread, daemon=True)
    thread.start()


def send_to_terminal(session_id: int, command: str):
    """Sends an input string to the session's PTY."""
    session = get_session(session_id)
    if session and session.raw_pty:
        session.raw_pty.write(command.encode('utf-8'))


# Add other direct-callable functions here for filesystem, privesc, etc.
# For example:
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
    except Exception:
        return []  # Return empty on error
