import time
import pygame

MAX_PLAYERS = 8
DEFAULT_PORT = 5000

def fit_text(font: pygame.font.Font, text: str, max_w: int) -> str:
    if font.size(text)[0] <= max_w:
        return text
    if max_w <= font.size("…")[0]:
        return "…"
    t = text
    while t and font.size(t + "…")[0] > max_w:
        t = t[:-1]
    return t + "…"

class TextInput:
    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, label: str, max_len: int = 16):
        self.rect = rect
        self.font = font
        self.label = label
        self.max_len = max_len
        self.text = ""
        self.active = False

    def handle_event(self, e: pygame.event.Event):
        if e.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(e.pos)
        if e.type == pygame.KEYDOWN and self.active:
            if e.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                pass
            else:
                if len(self.text) < self.max_len and e.unicode and e.unicode.isprintable():
                    self.text += e.unicode

    def draw(self, surf):
        pygame.draw.rect(surf, (30, 30, 36), self.rect, border_radius=8)
        pygame.draw.rect(surf, (120, 120, 140) if self.active else (70, 70, 86), self.rect, 2, border_radius=8)
        lab = self.font.render(self.label, True, (210, 210, 220))
        surf.blit(lab, (self.rect.x, self.rect.y - 26))
        txt = self.font.render(self.text if self.text else "", True, (240, 240, 250))
        surf.blit(txt, (self.rect.x + 10, self.rect.y + (self.rect.height - txt.get_height()) // 2))
        if self.active and (time.time() * 2) % 2 < 1:
            cx = self.rect.x + 10 + txt.get_width() + 2
            cy = self.rect.y + (self.rect.height - txt.get_height()) // 2
            pygame.draw.rect(surf, (240, 240, 250), pygame.Rect(cx, cy, 2, txt.get_height()))

class Button:
    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, text: str):
        self.rect = rect
        self.font = font
        self.text = text

    def is_clicked(self, e: pygame.event.Event) -> bool:
        return e.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(e.pos)

    def draw(self, surf, enabled=True):
        bg = (50, 50, 60) if enabled else (28, 28, 34)
        br = (160, 160, 190) if enabled else (70, 70, 86)
        pygame.draw.rect(surf, bg, self.rect, border_radius=10)
        pygame.draw.rect(surf, br, self.rect, 2, border_radius=10)
        t = self.font.render(self.text, True, (240, 240, 250) if enabled else (150, 150, 160))
        surf.blit(t, (self.rect.centerx - t.get_width() // 2, self.rect.centery - t.get_height() // 2))

def main_menu_screen() -> str:
    pygame.display.set_caption("LAN Tetris")
    screen = pygame.display.set_mode((1000, 600))
    clock = pygame.time.Clock()
    big = pygame.font.SysFont("consolas", 44)
    font = pygame.font.SysFont("consolas", 20)
    btn_y_offset = 80

    host_btn = Button(pygame.Rect(60, 200 + btn_y_offset, 240, 70), font, "HOST")
    join_btn = Button(pygame.Rect(60, 290 + btn_y_offset, 240, 70), font, "JOIN")
    quit_btn = Button(pygame.Rect(60, 380 + btn_y_offset, 240, 70), font, "QUIT")

    while True:
        clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return
                raise SystemExit
            if host_btn.is_clicked(e):
                return "host"
            if join_btn.is_clicked(e):
                return "join"
            if quit_btn.is_clicked(e):
                pygame.quit()
                raise SystemExit
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_h:
                    return "host"
                if e.key == pygame.K_j:
                    return "join"
                if e.key == pygame.K_ESCAPE:
                    pygame.quit()
                    raise SystemExit

        screen.fill((12, 12, 16))
        screen.blit(big.render("LAN TETRIS", True, (240, 240, 250)), (60, 80))
        screen.blit(font.render("H: Host  |  J: Join  |  ESC: Quit", True, (160, 160, 175)), (60, 140))
        screen.blit(font.render("Controls (in-game):", True, (160, 160, 175)), (60, 165))
        screen.blit(font.render("Z=CCW, X/Up=CW | C=Hold | Space=HardDrop | Down=SoftDrop", True, (160, 160, 175)), (60, 190))
        host_btn.draw(screen, True)
        join_btn.draw(screen, True)
        quit_btn.draw(screen, True)
        pygame.display.flip()

def host_lobby_screen(server, local_ip: str, port: int, start_delay_s: float) -> tuple[str, float]:
    screen = pygame.display.set_mode((1000, 650))
    pygame.display.set_caption("Tetris Lobby (Host)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 20)
    big = pygame.font.SysFont("consolas", 34)
    input_y_offset = 60
    nick_input = TextInput(pygame.Rect(60, 270 + input_y_offset, 420, 52),font,"Nickname (Host)",16)
    nick_input.active = True

    start_btn = Button(pygame.Rect(60, 460, 220, 56), font, "START (Enter)")
    back_btn = Button(pygame.Rect(300, 460, 140, 56), font, "BACK")

    info_lines = [
        f"Your IP: {local_ip}",
        f"Port: {port}",
        "Give your IP to friends.",
        "They choose JOIN and enter your IP.",
        "After START: no new joins.",
    ]

    while True:
        clock.tick(60)
        with server._lock:
            roster = dict(server.names)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                server.stop()
                pygame.quit()
                raise SystemExit

            nick_input.handle_event(e)

            if back_btn.is_clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                server.stop()
                return "", 0.0

            if start_btn.is_clicked(e) or (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER)):
                name = nick_input.text.strip()[:16] or "Host"
                server.names[1] = name

                server.initial_player_count = len(server.names)

                start_at = time.time() + start_delay_s
                server.schedule_start(start_at)
                return name, start_at

        screen.fill((12, 12, 16))
        screen.blit(big.render("LOBBY (HOST)", True, (240, 240, 250)), (60, 60))

        y = 120
        for line in info_lines:
            screen.blit(font.render(line, True, (200, 200, 210)), (60, y))
            y += 28

        nick_input.draw(screen)
        start_btn.draw(screen, True)
        back_btn.draw(screen, True)

        pygame.draw.rect(screen, (18, 18, 22), pygame.Rect(560, 100, 380, 500), border_radius=10)
        pygame.draw.rect(screen, (70, 70, 86), pygame.Rect(560, 100, 380, 500), 2, border_radius=10)
        screen.blit(font.render("Connected players:", True, (220, 220, 230)), (575, 115))

        y2 = 155
        line_h = 30
        max_w = 380 - 30
        for pid in sorted(roster.keys())[:MAX_PLAYERS]:
            nm = fit_text(font, str(roster[pid]), max_w - 50)
            screen.blit(font.render(f"{pid}: {nm}", True, (200, 200, 210)), (575, y2))
            y2 += line_h

        pygame.display.flip()

def join_connect_screen() -> tuple[str, int, str]:
    screen = pygame.display.set_mode((1000, 650))
    pygame.display.set_caption("Join (Enter IP)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 20)
    big = pygame.font.SysFont("consolas", 34)

    ip_input = TextInput(pygame.Rect(60, 200, 420, 52), font, "Host IP", 32)
    ip_input.active = True
    port_input = TextInput(pygame.Rect(60, 290, 200, 52), font, "Port", 5)
    port_input.text = str(DEFAULT_PORT)
    nick_input = TextInput(pygame.Rect(60, 380, 420, 52), font, "Nickname", 16)

    connect_btn = Button(pygame.Rect(520, 200, 220, 56), font, "CONNECT")
    back_btn = Button(pygame.Rect(520, 270, 220, 56), font, "BACK")
    err = ""

    while True:
        clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            ip_input.handle_event(e)
            port_input.handle_event(e)
            nick_input.handle_event(e)

            if back_btn.is_clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                return "", 0, ""

            if connect_btn.is_clicked(e) or (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER)):
                ip = ip_input.text.strip()
                if not ip:
                    err = "IP bos olamaz."
                    continue
                try:
                    port = int(port_input.text.strip() or DEFAULT_PORT)
                    if not (1 <= port <= 65535):
                        raise ValueError
                except Exception:
                    err = "Port gecersiz."
                    continue
                nick = nick_input.text.strip()[:16] or "Player"
                return ip, port, nick

        screen.fill((12, 12, 16))
        screen.blit(big.render("JOIN", True, (240, 240, 250)), (60, 70))
        screen.blit(font.render("Host IP gir ve CONNECT.", True, (160, 160, 175)), (60, 130))

        ip_input.draw(screen)
        port_input.draw(screen)
        nick_input.draw(screen)

        connect_btn.draw(screen, True)
        back_btn.draw(screen, True)

        if err:
            screen.blit(font.render(err, True, (240, 120, 120)), (60, 570))
        pygame.display.flip()

def client_lobby_screen(peer, host_ip: str, port: int, nickname: str) -> tuple[float, int]:
    screen = pygame.display.set_mode((1000, 650))
    pygame.display.set_caption("Tetris Lobby (Client)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 20)
    big = pygame.font.SysFont("consolas", 34)

    my_id = None
    roster = {1: "Host"}
    started_at = None
    sent_hello = False

    t0 = time.time()
    while time.time() - t0 < 3.0 and my_id is None:
        while peer.inbox:
            msg = peer.inbox.popleft()
            if msg.get("t") == "welcome":
                my_id = int(msg.get("id"))
                roster = {int(k): v for k, v in msg.get("roster", {}).items()}
                break
        time.sleep(0.01)
    if my_id is None:
        my_id = 2

    ready_btn = Button(pygame.Rect(60, 520, 220, 56), font, "READY")
    back_btn = Button(pygame.Rect(300, 520, 140, 56), font, "BACK")

    while True:
        clock.tick(60)

        while peer.inbox:
            msg = peer.inbox.popleft()
            t = msg.get("t")
            if t == "roster":
                r = msg.get("roster", {})
                roster = {int(k): v for k, v in r.items()}
            elif t == "join":
                pid = int(msg.get("id"))
                nm = str(msg.get("name", f"Player{pid}"))
                roster[pid] = nm
            elif t == "start":
                started_at = float(msg.get("at", time.time()))

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                peer.close()
                pygame.quit()
                raise SystemExit

            if back_btn.is_clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                peer.close()
                return 0.0, my_id

            if ready_btn.is_clicked(e) or (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER)):
                if not sent_hello:
                    peer.send({"t": "hello", "name": nickname})
                    sent_hello = True

        if started_at is not None:
            if not sent_hello:
                peer.send({"t": "hello", "name": nickname})
            return started_at, my_id

        screen.fill((12, 12, 16))
        screen.blit(big.render("LOBBY (CLIENT)", True, (240, 240, 250)), (60, 60))
        screen.blit(font.render(f"Connected to: {host_ip}:{port}   (your id: {my_id})", True, (200, 200, 210)), (60, 120))
        screen.blit(font.render(f"Your nickname: {nickname}", True, (200, 200, 210)), (60, 150))
        screen.blit(font.render("Press READY, wait for host START.", True, (160, 160, 175)), (60, 190))

        ready_btn.draw(screen, True)
        back_btn.draw(screen, True)

        pygame.draw.rect(screen, (18, 18, 22), pygame.Rect(560, 100, 380, 510), border_radius=10)
        pygame.draw.rect(screen, (70, 70, 86), pygame.Rect(560, 100, 380, 510), 2, border_radius=10)
        screen.blit(font.render("Connected players:", True, (220, 220, 230)), (575, 115))

        y2 = 155
        line_h = 30
        max_w = 380 - 30
        for pid in sorted(roster.keys())[:MAX_PLAYERS]:
            nm = str(roster[pid]) + (" (YOU)" if pid == my_id else "")
            nm = fit_text(font, nm, max_w - 50)
            screen.blit(font.render(f"{pid}: {nm}", True, (200, 200, 210)), (575, y2))
            y2 += line_h

        pygame.display.flip()

def countdown_screen(start_at: float, title: str = "Game starting"):
    screen = pygame.display.get_surface()
    clock = pygame.time.Clock()
    big = pygame.font.SysFont("consolas", 44)
    font = pygame.font.SysFont("consolas", 20)

    while True:
        clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
        left = start_at - time.time()
        if left <= 0:
            return
        screen.fill((12, 12, 16))
        screen.blit(big.render(title, True, (240, 240, 250)), (60, 60))
        screen.blit(big.render(f"{left:0.2f}s", True, (240, 240, 250)), (60, 120))
        screen.blit(font.render("Everyone will start together.", True, (160, 160, 175)), (60, 200))
        pygame.display.flip()

def show_ranking_screen(end_packet: dict, my_id: int):
    screen = pygame.display.get_surface()
    clock = pygame.time.Clock()
    big = pygame.font.SysFont("consolas", 44)
    font = pygame.font.SysFont("consolas", 22)
    small = pygame.font.SysFont("consolas", 18)

    winner = end_packet.get("winner")
    ranking = end_packet.get("ranking", [])
    roster = end_packet.get("roster", {})

    def name_of(pid):
        return str(roster.get(pid, f"Player{pid}"))

    while True:
        clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                return

        screen.fill((12, 12, 16))
        screen.blit(big.render("GAME OVER", True, (240, 240, 250)), (60, 50))

        if winner is not None:
            screen.blit(font.render(f"WINNER: {winner} - {name_of(winner)}", True, (200, 255, 200)), (60, 120))
        else:
            screen.blit(font.render("Winner yok (tek kisi bitti).", True, (200, 200, 210)), (60, 120))

        screen.blit(font.render("RANKING:", True, (220, 220, 230)), (60, 170))
        y = 210
        for i, pid in enumerate(ranking, start=1):
            you = " (YOU)" if pid == my_id else ""
            screen.blit(small.render(f"{i}. {pid} - {name_of(pid)}{you}", True, (200, 200, 210)), (60, y))
            y += 26

        screen.blit(small.render("ESC / Enter / Space: CIKIS", True, (150, 150, 170)),
                    (60, screen.get_height() - 60))
        pygame.display.flip()


# ---------------------------
# IN-GAME HUD / LAYOUT
# ---------------------------

def compute_game_layout(w: int, h: int) -> dict:
    """
    Paint mock'undaki gibi:
    [sol oyuncular] [MAIN BOARD] [NEXT+HOLD] [RANK PANEL]
    """
    pad = 16
    gap = 14

    # Genişlik oranları (mock'a yakın)
    left_w = int(w * 0.18)
    main_w = int(w * 0.44)
    mid_w  = int(w * 0.18)   # next+hold
    rank_w = w - (pad*2 + gap*3 + left_w + main_w + mid_w)

    x_left = pad
    x_main = x_left + left_w + gap
    x_mid  = x_main + main_w + gap
    x_rank = x_mid + mid_w + gap

    y_top = pad
    full_h = h - pad*2

    # OUTER PANELS
    left_rect = pygame.Rect(x_left, y_top, left_w, full_h)
    main_rect = pygame.Rect(x_main, y_top, main_w, full_h)
    mid_rect  = pygame.Rect(x_mid,  y_top, mid_w,  full_h)
    rank_rect = pygame.Rect(x_rank, y_top, rank_w, full_h)

    # LEFT PANEL -> 2 kolon (solda 3 büyük, sağda 4 küçük)
    inner_pad = 10
    col_gap = 10

    colA_w = int((left_w - inner_pad*2 - col_gap) * 0.52)  # sol-en dış (oyuncu6/7/8)
    colB_w = (left_w - inner_pad*2 - col_gap) - colA_w     # sol-iç (oyuncu2/3/4/5)

    colA_x = left_rect.x + inner_pad
    colB_x = colA_x + colA_w + col_gap
    col_y  = left_rect.y + inner_pad
    col_h  = left_rect.height - inner_pad*2

    # 3 büyük kutu (eşit paylaştır)
    a_gap = 10
    a_box_h = (col_h - a_gap*2) // 3
    left_big = [
        pygame.Rect(colA_x, col_y + (a_box_h + a_gap)*0, colA_w, a_box_h),
        pygame.Rect(colA_x, col_y + (a_box_h + a_gap)*1, colA_w, a_box_h),
        pygame.Rect(colA_x, col_y + (a_box_h + a_gap)*2, colA_w, a_box_h),
    ]

    # 4 küçük kutu
    b_gap = 10
    b_box_h = (col_h - b_gap*3) // 4
    left_small = [
        pygame.Rect(colB_x, col_y + (b_box_h + b_gap)*0, colB_w, b_box_h),
        pygame.Rect(colB_x, col_y + (b_box_h + b_gap)*1, colB_w, b_box_h),
        pygame.Rect(colB_x, col_y + (b_box_h + b_gap)*2, colB_w, b_box_h),
        pygame.Rect(colB_x, col_y + (b_box_h + b_gap)*3, colB_w, b_box_h),
    ]

    # MID PANEL -> üst NEXT listesi, alt HOLD
    mid_pad = 10
    next_h = int(mid_rect.height * 0.72)
    hold_h = mid_rect.height - next_h - mid_pad
    next_rect = pygame.Rect(mid_rect.x + mid_pad, mid_rect.y + mid_pad, mid_rect.width - mid_pad*2, next_h - mid_pad)
    hold_rect = pygame.Rect(mid_rect.x + mid_pad, next_rect.bottom + mid_pad, mid_rect.width - mid_pad*2, hold_h - mid_pad)

    return {
        "left_rect": left_rect,
        "main_rect": main_rect,
        "mid_rect": mid_rect,
        "rank_rect": rank_rect,
        "left_big": left_big,       # 3 adet
        "left_small": left_small,   # 4 adet
        "next_rect": next_rect,
        "hold_rect": hold_rect,
    }


def draw_panel(surf, rect: pygame.Rect, title: str, font: pygame.font.Font,
               border=(220, 40, 40), fill=(10, 10, 14), title_color=(220, 40, 40)):
    pygame.draw.rect(surf, fill, rect, border_radius=10)
    pygame.draw.rect(surf, border, rect, 3, border_radius=10)
    if title:
        t = font.render(title, True, title_color)
        surf.blit(t, (rect.x + 12, rect.y + 10))


def in_game_draw_hud(
    surf: pygame.Surface,
    layout: dict,
    font: pygame.font.Font,
    my_name: str,
    roster: dict,
    ranking_list: list,
    # aşağıdakiler şimdilik placeholder; senin game state'ine bağlayacağız
):
    """
    Sadece HUD'ı çizer. Board/next/hold renderını senin game çizim fonksiyonlarınla birleştireceğiz.
    """
    # BACKGROUND
    surf.fill((12, 12, 16))

    # OUTER PANELS
    draw_panel(surf, layout["left_rect"], "", font)
    draw_panel(surf, layout["main_rect"], "", font)
    draw_panel(surf, layout["mid_rect"], "", font)
    draw_panel(surf, layout["rank_rect"], "oyuncu siralamasi", font)

    # MAIN LABEL (mocktaki yazı gibi)
    center_label = font.render("bloklarin dustugu kisim", True, (220, 40, 40))
    mr = layout["main_rect"]
    surf.blit(center_label, (mr.centerx - center_label.get_width()//2, mr.centery - center_label.get_height()//2))

    # LEFT MINI BOARDS (placeholder)
    # big: oyuncu6/7/8  small: oyuncu2/3/4/5 gibi düşün
    for i, r in enumerate(layout["left_big"], start=6):
        draw_panel(surf, r, f"oyuncu{i}", font)
    for i, r in enumerate(layout["left_small"], start=2):
        draw_panel(surf, r, f"oyuncu{i}", font)

    # NEXT + HOLD
    draw_panel(surf, layout["next_rect"], "sonrasinda gelecek olan\nblocklarin listesi", font)
    draw_panel(surf, layout["hold_rect"], "hold", font)

    # RANKING LIST (placeholder yazdırma)
    rr = layout["rank_rect"]
    y = rr.y + 54
    line_h = 26
    max_w = rr.width - 24

    # Eğer ranking_list boşsa, roster'a göre bas
    if ranking_list:
        ids = ranking_list
    else:
        ids = sorted([int(k) for k in roster.keys()])[:MAX_PLAYERS]

    for idx, pid in enumerate(ids, start=1):
        nm = str(roster.get(pid, f"Player{pid}"))
        txt = f"{idx}. {pid} - {nm}"
        txt = fit_text(font, txt, max_w)
        surf.blit(font.render(txt, True, (200, 200, 210)), (rr.x + 12, y))
        y += line_h

    # Üst sağa kendi adını (istersen)
    if my_name:
        label = font.render(f"{my_name}", True, (120, 120, 130))
        surf.blit(label, (rr.x + rr.width - label.get_width() - 12, rr.y + 12))
