import pkg_resources
import sys

# This is a temporary diagnostic script.
# It will print all installed Python packages to the Android log (Logcat).
# This allows us to verify what Chaquopy has successfully installed.

try:
    installed_packages = {pkg.key for pkg in pkg_resources.working_set}
    print("--- CHAQUOPY INSTALLED PACKAGES START ---")
    print(sorted(installed_packages))
    print("--- CHAQUOPY INSTALLED PACKAGES END ---")
    print(f"Python version: {sys.version}")

except Exception as e:
    print(f"Failed to list packages: {e}")


def initialize_manager():
    """Diagnostic stub."""
    print("DIAGNOSTIC: initialize_manager called")
    pass

# All other functions are disabled to prevent crashes.
def get_session(session_id: int): return None
def create_listener(uri: str): return {}
def get_listeners(): return []
def remove_listener(listener_id: int): pass
def get_sessions(): return []
def start_interactive_session(session_id: int, callback): pass