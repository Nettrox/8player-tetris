import socket
import threading
import time
import json
from collections import deque

ATTACKS_ENABLED = True

class NetPeer:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.alive = True
        self.inbox = deque()
        self._send_lock = threading.Lock()
        threading.Thread(target=self._rx_loop, daemon=True).start()

    def send(self, obj: dict):
        if not self.alive:
            return
        data = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
        with self._send_lock:
            try:
                self.sock.sendall(data)
            except Exception:
                self.alive = False

    def _rx_loop(self):
        buf = b""
        try:
            while self.alive:
                chunk = self.sock.recv(4096)
                if not chunk:
                    self.alive = False
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self.inbox.append(json.loads(line.decode("utf-8")))
                    except Exception:
                        pass
        except Exception:
            self.alive = False

    def close(self):
        self.alive = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


def get_local_ip() -> str:
    ip = "127.0.0.1"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        try:
            s.close()
        except Exception:
            pass
    return ip


def join_connect(ip: str, port: int, timeout_s: float = 3.0) -> NetPeer:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout_s)
    s.connect((ip, port))
    s.settimeout(None)
    peer = NetPeer(s)

    # late-join reject check
    t0 = time.time()
    while time.time() - t0 < 1.0:
        if peer.inbox:
            msg = peer.inbox.popleft()
            if msg.get("t") == "reject":
                reason = msg.get("reason", "unknown")
                peer.close()
                raise ConnectionError(f"Rejected by host: {reason}")
            else:
                peer.inbox.appendleft(msg)
                break
        time.sleep(0.01)

    return peer


class HostServer:
    def __init__(self, bind_ip: str, port: int, max_clients: int = 7):
        self.bind_ip = bind_ip
        self.port = port
        self.max_clients = max_clients

        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((bind_ip, port))
        self._srv.listen(8)
        self._srv.settimeout(0.5)

        self.running = True
        self._lock = threading.Lock()
        self.peers: dict[int, NetPeer] = {}
        self.names: dict[int, str] = {1: "Host"}
        self.next_id = 2

        self.last_board: dict[int, str] = {}
        self.last_alive: dict[int, bool] = {}
        self.started_at: float | None = None

        self.end_sent = False
        self.death_order: list[int] = []
        self.dead_seen: set[int] = set()
        self.last_end_msg: dict | None = None

        self.initial_player_count = 1

        threading.Thread(target=self._accept_loop, daemon=True).start()

    def stop(self):
        self.running = False
        try:
            self._srv.close()
        except Exception:
            pass
        with self._lock:
            for p in list(self.peers.values()):
                p.close()
            self.peers.clear()

    def _broadcast(self, msg: dict, exclude: int | None = None):
        with self._lock:
            items = list(self.peers.items())
        for pid, peer in items:
            if exclude is not None and pid == exclude:
                continue
            if peer.alive:
                peer.send(msg)

    def _accept_loop(self):
        while self.running:
            try:
                conn, _addr = self._srv.accept()
            except socket.timeout:
                continue
            except Exception:
                break

            if self.started_at is not None:
                try:
                    conn.sendall(b'{"t":"reject","reason":"game_started"}\n')
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
                continue

            with self._lock:
                if len(self.peers) >= self.max_clients:
                    try:
                        conn.sendall(b'{"t":"reject","reason":"room_full"}\n')
                    except Exception:
                        pass
                    try:
                        conn.close()
                    except Exception:
                        pass
                    continue

                pid = self.next_id
                self.next_id += 1
                peer = NetPeer(conn)
                self.peers[pid] = peer
                self.names[pid] = f"Player{pid}"
                self.last_alive[pid] = True

            roster = {str(k): v for k, v in self.names.items()}
            peer.send({"t": "welcome", "id": pid, "roster": roster})
            self._broadcast({"t": "join", "id": pid, "name": self.names[pid]}, exclude=None)

    def schedule_start(self, at: float):
        self.started_at = at
        self._broadcast({"t": "start", "at": at}, exclude=None)

    def poll_and_route(self, host_name: str, host_board_s: str, host_alive: bool) -> int:
        atk_to_host = 0
        self.names[1] = host_name

        # broadcast host board to everyone
        self._broadcast({"t": "board", "id": 1, "s": host_board_s, "alive": host_alive}, exclude=None)

        with self._lock:
            items = list(self.peers.items())

        for pid, peer in items:
            if not peer.alive:
                continue

            while peer.inbox:
                msg = peer.inbox.popleft()
                t = msg.get("t")

                if t == "hello":
                    nm = str(msg.get("name", f"Player{pid}"))[:16]
                    self.names[pid] = nm
                    roster = {str(k): v for k, v in self.names.items()}
                    self._broadcast({"t": "roster", "roster": roster}, exclude=None)

                elif t == "board":
                    s = msg.get("s", "")
                    alive = bool(msg.get("alive", True))
                    self.last_board[pid] = s
                    self.last_alive[pid] = alive
                    if alive is False and pid not in self.dead_seen:
                        self.dead_seen.add(pid)
                        self.death_order.append(pid)
                    self._broadcast({"t": "board", "id": pid, "s": s, "alive": alive}, exclude=pid)

                elif t == "atk" and ATTACKS_ENABLED:
                    n = int(msg.get("n", 0))
                    if n > 0:
                        atk_to_host += n
                        self._broadcast({"t": "atk", "n": n}, exclude=pid)

                elif t == "dead":
                    self.last_alive[pid] = False
                    if pid not in self.dead_seen:
                        self.dead_seen.add(pid)
                        self.death_order.append(pid)
                    self._broadcast({"t": "dead", "id": pid}, exclude=pid)

        # game over check (host decides)
        if not self.end_sent:
            alive_ids = []
            if host_alive:
                alive_ids.append(1)
            with self._lock:
                for pid, a in self.last_alive.items():
                    if a:
                        alive_ids.append(pid)

            should_end = False
            winner = None

            if self.initial_player_count >= 2:
                if len(alive_ids) == 1:
                    should_end = True
                    winner = alive_ids[0]
            else:
                if len(alive_ids) == 0:
                    should_end = True
                    winner = None

            if should_end:
                ranking = []
                if winner is not None:
                    ranking.append(winner)
                for pid in reversed(self.death_order):
                    if pid != winner and pid not in ranking:
                        ranking.append(pid)

                roster = {str(k): v for k, v in self.names.items()}
                end_msg = {"t": "end", "winner": winner, "ranking": ranking, "roster": roster}
                self.last_end_msg = end_msg
                self.end_sent = True
                self._broadcast(end_msg, exclude=None)

        return atk_to_host