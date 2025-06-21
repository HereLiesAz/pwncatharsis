import base64
import logging
from session import parse_ls_output

log = logging.getLogger("pwncat")

def list_files(session_id: int, path: str, sessions: dict, lock):
    with lock:
        if session_id in sessions:
            session = sessions[session_id]
            command = f"ls -lA --time-style=long-iso \"{path}\""
            output = session.execute_utility_command(command)
            if output:
                parsed_items = parse_ls_output(output)
                for item in parsed_items:
                    item[
                        'path'] = f"{path.rstrip('/')}/{item['name']}" if path != "/" else f"/{item['name']}"
                return parsed_items
            return []
    return []

def read_file(session_id: int, path: str, sessions: dict, lock):
    with lock:
        if session_id in sessions:
            session = sessions[session_id]
            command = f"cat \"{path}\""
            content = session.execute_utility_command(command)
            if content is not None:
                content_lines = content.strip().splitlines()
                if content_lines and command in content_lines[0]:
                    content_lines = content_lines[1:]
                return {"content": "\n".join(content_lines)}
            else:
                return {"error": f"Failed to read file: {path}"}
    return {"error": "Session not found"}


def download_file(session_id: int, remote_path: str, local_path: str, sessions: dict, lock):
    with lock:
        if session_id not in sessions:
            return {"error": "Session not found"}
        session = sessions[session_id]

    # Base64 encode the remote file to ensure safe transport.
    # The `|| echo ...` part provides a clear failure signal.
    command = f"base64 \"{remote_path}\" 2>/dev/null || echo PWNCAT_DOWNLOAD_FAILED"
    b64_content = session.execute_utility_command(command)

    if b64_content is None or "PWNCAT_DOWNLOAD_FAILED" in b64_content:
        log.error(f"Failed to read or base64 encode remote file: {remote_path}")
        return {"error": f"Failed to read or base64 encode remote file: {remote_path}"}

    try:
        # The output might have newlines depending on the base64 utility, remove them.
        b64_content_clean = "".join(b64_content.strip().splitlines())
        decoded_bytes = base64.b64decode(b64_content_clean)

        # Write the decoded bytes to the local file path provided by the client.
        with open(local_path, "wb") as f:
            f.write(decoded_bytes)

        log.info(f"Successfully downloaded {remote_path} to {local_path}")
        return {"path": local_path}
    except Exception as e:
        log.error(f"Failed to decode or write file {local_path}: {e}")
        return {"error": f"Failed to decode or write file: {e}"}
