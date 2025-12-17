import time
import pygame

from net import HostServer, join_connect, get_local_ip
import ui
from game import common_game_loop
from tetris_core import string_to_board

MAX_PLAYERS = 8
DEFAULT_PORT = 5000
START_DELAY_SECONDS = 2.0

def run_client(peer, nickname: str, my_id: int):
    roster = {1: "Host"}
    opp_boards = {}
    alive_map = {}
    end_packet = {"active": False, "winner": None, "ranking": [], "roster": {}}

    def drain_messages() -> int:
        atks_for_me = 0
        while peer.inbox:
            msg = peer.inbox.popleft()
            t = msg.get("t")

            if t == "roster":
                r = msg.get("roster", {})
                roster.clear()
                roster.update({int(k): v for k, v in r.items()})

            elif t == "join":
                pid = int(msg.get("id"))
                nm = str(msg.get("name", f"Player{pid}"))
                roster[pid] = nm

            elif t == "board":
                pid = int(msg.get("id"))
                s = msg.get("s", "")
                opp_boards[pid] = string_to_board(s)
                alive_map[pid] = bool(msg.get("alive", True))

            elif t == "dead":
                pid = int(msg.get("id"))
                alive_map[pid] = False

            elif t == "atk":
                n = int(msg.get("n", 0))
                if n > 0:
                    atks_for_me += n

            elif t == "end":
                end_packet["active"] = True
                end_packet["winner"] = msg.get("winner")
                end_packet["ranking"] = msg.get("ranking", [])
                end_packet["roster"] = {int(k): v for k, v in msg.get("roster", {}).items()}

        return atks_for_me

    def poll_net(_s, _a):
        return drain_messages()

    def send_board(s, alive):
        peer.send({"t": "board", "s": s, "alive": alive})

    def send_atk(n):
        peer.send({"t": "atk", "n": n})

    def send_dead():
        peer.send({"t": "dead"})

    common_game_loop(
        nickname=nickname,
        my_id=my_id,
        poll_net=poll_net,
        send_board=send_board,
        send_atk=send_atk,
        send_dead=send_dead,
        get_roster=lambda: roster,
        get_opp_boards=lambda: opp_boards,
        get_alive_map=lambda: alive_map,
        on_exit=lambda: peer.close(),
        host_server=None,
        end_packet=end_packet,
    )

def run_host(server: HostServer, nickname: str):
    my_id = 1
    roster = {1: nickname}
    opp_boards = {}
    alive_map = {}
    end_packet = {"active": False, "winner": None, "ranking": [], "roster": {}}

    def poll_net(board_s, alive):
        atks = server.poll_and_route(nickname, board_s, alive)

        roster.clear()
        with server._lock:
            for pid, nm in server.names.items():
                roster[pid] = nm

        opp_boards.clear()
        alive_map.clear()
        with server._lock:
            for pid, s in server.last_board.items():
                opp_boards[pid] = string_to_board(s)
            for pid, a in server.last_alive.items():
                alive_map[pid] = bool(a)

        if server.last_end_msg is not None and not end_packet["active"]:
            msg = server.last_end_msg
            end_packet["active"] = True
            end_packet["winner"] = msg.get("winner")
            end_packet["ranking"] = msg.get("ranking", [])
            end_packet["roster"] = {int(k): v for k, v in msg.get("roster", {}).items()}

        return atks

    def send_atk(n):
        server._broadcast({"t": "atk", "n": n}, exclude=None)

    def send_dead():
        server._broadcast({"t": "dead", "id": 1}, exclude=None)

    common_game_loop(
        nickname=nickname,
        my_id=my_id,
        poll_net=poll_net,
        send_board=lambda s, alive: None,
        send_atk=send_atk,
        send_dead=send_dead,
        get_roster=lambda: roster,
        get_opp_boards=lambda: opp_boards,
        get_alive_map=lambda: alive_map,
        on_exit=lambda: server.stop(),
        host_server=server,
        end_packet=end_packet,
    )

def main():
    pygame.init()
    pygame.display.set_mode((1000, 600))

    while True:
        mode = ui.main_menu_screen()

        if mode == "host":
            local_ip = get_local_ip()
            port = DEFAULT_PORT
            server = HostServer("0.0.0.0", port, max_clients=MAX_PLAYERS - 1)

            host_nick, start_at = ui.host_lobby_screen(server, local_ip, port, START_DELAY_SECONDS)
            if not host_nick:
                continue

            ui.countdown_screen(start_at, "Game starting")
            try:
                run_host(server, host_nick)
            finally:
                try:
                    server.stop()
                except Exception:
                    pass

        elif mode == "join":
            host_ip, port, nick = ui.join_connect_screen()
            if not host_ip:
                continue

            try:
                peer = join_connect(host_ip, port, timeout_s=3.0)
            except Exception:
                # basit fail ekranı
                scr = pygame.display.set_mode((900, 300))
                scr.fill((12, 12, 16))
                f = pygame.font.SysFont("consolas", 18)
                scr.blit(f.render("CONNECT FAILED", True, (240, 120, 120)), (30, 40))
                scr.blit(f.render(f"{host_ip}:{port}", True, (200, 200, 210)), (30, 80))
                pygame.display.flip()
                time.sleep(2)
                continue

            try:
                start_at, my_id = ui.client_lobby_screen(peer, host_ip, port, nick)
                if start_at <= 0:
                    continue
                peer.send({"t": "hello", "name": nick})
                ui.countdown_screen(start_at, "Game starting")
                run_client(peer, nick, my_id)
            finally:
                try:
                    peer.close()
                except Exception:
                    pass

if __name__ == "__main__":
    main()