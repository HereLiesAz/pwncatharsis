import re


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
            items.append({
                "name": name,
                "path": name,
                "is_dir": details['type'] == 'd'
            })
    return items


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
                return {"content": content}
            else:
                return {"error": f"Failed to read file: {path}"}
    return {"error": "Session not found"}
