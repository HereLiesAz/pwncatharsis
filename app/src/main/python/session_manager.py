import threading
import pwncat

# --- Globals to manage the state that was previously in a 'Manager' ---
listeners = {}
threads = {}
next_listener_id = 0


# --------------------------------------------------------------------

def initialize_manager():
    """
    This function is no longer strictly necessary but is kept for API consistency
    with the Kotlin PwncatRepository.
    """
    pass

def create_listener(uri: str):
    """
    Creates and starts a new pwncat listener in a background thread.
    """
    global next_listener_id
    try:
        # 1. Parse the URI
        proto, _, host_port = uri.partition("://")
        host, _, port_str = host_port.rpartition(":")
        port = int(port_str)

        if proto.lower() not in ["tcp", "udp"]:
            return {"error": f"Unsupported protocol: {proto}"}

        # 2. Set up pwncat options using the classes from pwncat.py
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

        # 3. Create the main IONetwork object
        net = pwncat.IONetwork(ssig, enc, host, [port], "server", srv_opts, cli_opts, sock_opts)

        # 4. Create a dummy IO module for the runner
        mod = pwncat.IOStdinStdout(ssig,
                                   pwncat.DsIOStdinStdout(enc, pwncat.TIMEOUT_READ_STDIN, False))

        # 5. Configure the Runner to handle the connection
        run = pwncat.Runner(ssig, False, pwncat.PSEStore(ssig, [net]))
        run.add_action(
            "RECV",
            pwncat.DsRunnerAction(
                pwncat.DsCallableProducer(net.producer),
                mod.consumer,
                [net.interrupt], [], False, None
            ),
        )
        run.add_action(
            "STDIN",
            pwncat.DsRunnerAction(
                pwncat.DsCallableProducer(mod.producer),
                net.consumer,
                [mod.interrupt], [], False, None
            ),
        )

        # 6. Run the listener in a background thread so it doesn't block
        listener_id = next_listener_id
        thread = threading.Thread(target=run.run, daemon=True)
        thread.start()

        # 7. Store the listener state
        listeners[listener_id] = {"id": listener_id, "uri": uri, "thread": thread, "ssig": ssig}
        next_listener_id += 1

        return {"id": listener_id, "uri": uri}

    except Exception as e:
        return {"error": str(e)}

def get_listeners():
    """Returns a list of active listeners."""
    return [{"id": l["id"], "uri": l["uri"]} for l in listeners.values()]

def remove_listener(listener_id: int):
    """Stops a listener thread."""
    if listener_id in listeners:
        listeners[listener_id]["ssig"].raise_terminate()
        del listeners[listener_id]
    return


# --- Functions below this line require a similar rewrite once a session is established ---
def get_sessions(): return []
def start_interactive_session(session_id: int, callback):
    if callback: callback.onClose()


def send_to_terminal(session_id: int, command: str): pass


def list_files(session_id: int, path: str): return []


def read_file(session_id: int, path: str): return {"error": "Not implemented"}


def download_file(session_id: int, remote_path: str, local_path: str): return {
    "error": "Not implemented"}
