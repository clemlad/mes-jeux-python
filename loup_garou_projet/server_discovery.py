import json
import socket
import threading
import time

DISCOVERY_PORT = 37020
GAME_PORT = 5555
DISCOVERY_INTERVAL = 1.0
SERVER_TIMEOUT = 3.5
ANNOUNCE_TYPE = "werewolf_server_announce"


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


class ServerBroadcaster:
    def __init__(self, server_name, host_ip=None, game_port=GAME_PORT):
        self.server_name = server_name
        self.host_ip = host_ip or get_local_ip()
        self.game_port = game_port
        self.running = False
        self.thread = None
        self.player_count = 1
        self.max_players = 12

    def set_player_count(self, count):
        self.player_count = count

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        payload = {
            "type": ANNOUNCE_TYPE,
            "name": self.server_name,
            "host": self.host_ip,
            "port": self.game_port,
            "players": self.player_count,
            "max_players": self.max_players,
        }
        try:
            while self.running:
                payload["players"] = self.player_count
                data = json.dumps(payload).encode("utf-8")
                sock.sendto(data, ("255.255.255.255", DISCOVERY_PORT))
                time.sleep(DISCOVERY_INTERVAL)
        finally:
            sock.close()


class ServerDiscovery:
    def __init__(self):
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.found_servers = {}

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _listen(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", DISCOVERY_PORT))
        sock.settimeout(1.0)
        try:
            while self.running:
                try:
                    data, addr = sock.recvfrom(4096)
                except socket.timeout:
                    self._cleanup()
                    continue
                except OSError:
                    break

                try:
                    msg = json.loads(data.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                if msg.get("type") != ANNOUNCE_TYPE:
                    continue

                host = msg.get("host") or addr[0]
                port = msg.get("port", GAME_PORT)
                key = (host, port)
                with self.lock:
                    self.found_servers[key] = {
                        "name": msg.get("name", "Serveur"),
                        "host": host,
                        "port": port,
                        "players": msg.get("players", 0),
                        "max_players": msg.get("max_players", 12),
                        "last_seen": time.time(),
                    }
                self._cleanup()
        finally:
            sock.close()

    def _cleanup(self):
        now = time.time()
        with self.lock:
            expired = [
                key for key, info in self.found_servers.items()
                if now - info["last_seen"] > SERVER_TIMEOUT
            ]
            for key in expired:
                del self.found_servers[key]

    def get_servers(self):
        with self.lock:
            servers = list(self.found_servers.values())
        servers.sort(key=lambda s: (s["name"].lower(), s["host"], s["port"]))
        return servers
