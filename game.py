import time
from collections import deque
import pygame
import ui


from tetris_core import (
    W, H, HIDDEN, TETROS, COLORS,
    new_bag, empty_board, can_place, lock_piece, clear_lines,
    add_garbage, board_to_string, string_to_board
)

ATTACKS_ENABLED = True

def common_game_loop(
    nickname: str,
    my_id: int,
    poll_net,
    send_board,
    send_atk,
    send_dead,
    get_roster,
    get_opp_boards,
    get_alive_map,
    on_exit,
    host_server,
    end_packet: dict,
):
    pygame.init()
    screen = pygame.display.set_mode((1600, 900), pygame.RESIZABLE)
    pygame.display.set_caption(f"Tetris (LAN) - {nickname}")
    clock = pygame.time.Clock()

    # Layout
    cell = 30
    opp_cell = 12
    margin = 16

    board_px_w = W * cell
    board_px_h = H * cell
    opp_board_w = W * opp_cell
    opp_board_h = H * opp_cell

    left_area_w = 2 * opp_board_w + 22
    players_box_h = 240

    left_ox = margin
    top_oy = margin + 90
    main_ox = left_ox + left_area_w + margin
    right_ox = main_ox + board_px_w + margin
    mini_start_y = top_oy + players_box_h + 10

    font = pygame.font.SysFont("consolas", 18)
    big = pygame.font.SysFont("consolas", 28)
    small = pygame.font.SysFont("consolas", 14)

    def recalc_fonts(scale: float):
        nonlocal font, big, small
        font = pygame.font.SysFont("consolas", max(14, int(18 * scale)))
        big = pygame.font.SysFont("consolas", max(18, int(28 * scale)))
        small = pygame.font.SysFont("consolas", max(12, int(14 * scale)))

    def recalc_layout(w, h):
        nonlocal cell, opp_cell, margin
        nonlocal board_px_w, board_px_h, opp_board_w, opp_board_h
        nonlocal left_area_w, players_box_h
        nonlocal left_ox, top_oy, main_ox, right_ox, mini_start_y

        margin = 16
        cell = 30
        opp_cell = 12

        header_h = 50
        gap_x = 22
        players_box_h = 240

        board_px_w = W * cell
        board_px_h = H * cell
        opp_board_w = W * opp_cell
        opp_board_h = H * opp_cell
        left_area_w = 2 * opp_board_w + gap_x

        right_panel_min = 360

        while True:
            need_w = margin * 4 + left_area_w + board_px_w + right_panel_min
            need_h = margin * 3 + header_h + players_box_h + board_px_h + 120
            if need_w <= w and need_h <= h:
                break

            if cell > 20:
                cell -= 1
                board_px_w = W * cell
                board_px_h = H * cell
            elif opp_cell > 8:
                opp_cell -= 1
                opp_board_w = W * opp_cell
                opp_board_h = H * opp_cell
                left_area_w = 2 * opp_board_w + gap_x
            else:
                break

        scale = cell / 30.0
        recalc_fonts(scale)

        left_ox = margin
        top_oy = margin + header_h + 14
        main_ox = left_ox + left_area_w + margin
        right_ox = main_ox + board_px_w + margin
        mini_start_y = top_oy + players_box_h + 10

    recalc_layout(*screen.get_size())

    # Game state
    board = empty_board()
    next_queue = deque(new_bag())

    def pop_next():
        if len(next_queue) < 7:
            for p in new_bag():
                next_queue.append(p)
        return next_queue.popleft()

    cur = pop_next()
    rot = 0
    px, py = 3, 0
    hold = None
    hold_used = False

    alive = True
    pending_garbage = 0

    gravity = 0.55
    grav_timer = 0.0
    soft_drop = False

    left_held = False
    right_held = False
    move_delay = 0.18
    move_repeat = 0.085
    move_timer = 0.0

    # ---- Lock system: lock_delay + 15 lock moves (no reset exploit) ----
    MAX_LOCK_RESETS = 15
    lock_moves_left = MAX_LOCK_RESETS
    touched_ground = False
    lock_delay = 0.65
    lock_timer = 0.0

    start_time = time.time()
    last_board_send = 0.0

    death_order: list[int] = []
    dead_seen: set[int] = set()

    def on_ground():
        return not can_place(board, cur, rot, px, py + 1)

    def reset_lock_state_new_piece():
        nonlocal lock_moves_left, touched_ground, lock_timer
        lock_moves_left = MAX_LOCK_RESETS
        touched_ground = False
        lock_timer = 0.0

    def use_lock_move():
        nonlocal lock_moves_left, lock_timer
        if lock_moves_left > 0:
            lock_moves_left -= 1
            lock_timer = 0.0

    def try_rotate(dir_):
        nonlocal rot, px, py
        newr = (rot + dir_) % 4
        kicks = [
            (0, 0),
            (-1, 0), (1, 0), (-2, 0), (2, 0),
            (0, -1), (-1, -1), (1, -1),
            (0, -2),
        ]
        for dx, dy in kicks:
            if can_place(board, cur, newr, px + dx, py + dy):
                rot = newr
                px += dx
                py += dy
                return True
        return False

    def do_hold():
        nonlocal cur, rot, px, py, hold, hold_used
        if hold_used:
            return
        hold_used = True
        if hold is None:
            hold = cur
            cur = pop_next()
        else:
            hold, cur = cur, hold
        rot = 0
        px, py = 3, 0
        reset_lock_state_new_piece()

    def apply_lock_and_spawn():
        nonlocal cur, rot, px, py, hold_used, alive, pending_garbage
        lock_piece(board, cur, rot, px, py)
        cleared = clear_lines(board)

        if ATTACKS_ENABLED:
            atk = 0
            if cleared == 2:
                atk = 1
            elif cleared == 3:
                atk = 2
            elif cleared >= 4:
                atk = 4
            if atk > 0:
                send_atk(atk)

        if ATTACKS_ENABLED and pending_garbage > 0:
            add_garbage(board, pending_garbage)
            pending_garbage = 0

        nxt = pop_next()
        if not can_place(board, nxt, 0, 3, 0):
            alive = False
            send_dead()
            return

        cur = nxt
        rot = 0
        px, py = 3, 0
        hold_used = False
        reset_lock_state_new_piece()

    def hard_drop():
        nonlocal py
        while can_place(board, cur, rot, px, py + 1):
            py += 1
        apply_lock_and_spawn()

    def draw_board(b, ox, oy, csize, ghost_piece=None):
        pygame.draw.rect(screen, (18, 18, 22), pygame.Rect(ox - 2, oy - 2, W * csize + 4, H * csize + 4))
        for yy in range(H):
            for xx in range(W):
                v = b[yy + HIDDEN][xx]
                if v is None:
                    pygame.draw.rect(
                        screen, (30, 30, 36),
                        pygame.Rect(ox + xx * csize, oy + yy * csize, csize - 1, csize - 1),
                        1
                    )
                else:
                    pygame.draw.rect(
                        screen, COLORS.get(v, (200, 200, 200)),
                        pygame.Rect(ox + xx * csize, oy + yy * csize, csize - 1, csize - 1)
                    )

        if ghost_piece:
            gp, gr, gpx, gpy = ghost_piece
            for (x, y) in TETROS[gp][gr]:
                vx, vy = gpx + x, gpy + y - HIDDEN
                if 0 <= vx < W and 0 <= vy < H:
                    pygame.draw.rect(
                        screen, (90, 90, 110),
                        pygame.Rect(ox + vx * csize, oy + vy * csize, csize - 1, csize - 1),
                        1
                    )

    def draw_mini_piece(piece, ox, oy, ms):
        if not piece:
            return
        color = COLORS.get(piece, (200, 200, 200))
        for (x, y) in TETROS[piece][0]:
            pygame.draw.rect(screen, color, pygame.Rect(ox + x * ms, oy + y * ms, ms - 1, ms - 1))

    def opp_ids_sorted():
        ob = get_opp_boards()
        return sorted([pid for pid in ob.keys() if pid != my_id])[:7]

    while True:
        dt = clock.tick(60) / 1000.0
        w, h = screen.get_size()

        my_board_s = board_to_string(board)
        gained = poll_net(my_board_s, alive)
        if ATTACKS_ENABLED and alive and gained:
            pending_garbage += int(gained)

        if end_packet.get("active"):
            from ui import show_ranking_screen
            show_ranking_screen(end_packet, my_id)
            on_exit()
            return  # pygame.quit() YOK! (menu tekrar açılacak)

        now = time.time()
        if host_server is None and (now - last_board_send) > 0.20:
            last_board_send = now
            send_board(my_board_s, alive)

        alive_map_now = get_alive_map()
        for pid, is_alive in alive_map_now.items():
            if is_alive is False and pid not in dead_seen:
                dead_seen.add(pid)
                death_order.append(pid)
        if alive is False and my_id not in dead_seen:
            dead_seen.add(my_id)
            death_order.append(my_id)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                on_exit()
                return

            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                recalc_layout(event.w, event.h)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    on_exit()
                    pygame.quit()
                    return

                if alive:
                    if event.key == pygame.K_LEFT:
                        left_held = True
                        right_held = False
                        move_timer = 0.0
                        grounded_before = on_ground()
                        if can_place(board, cur, rot, px - 1, py):
                            px -= 1
                            grounded_after = on_ground()
                            if touched_ground and (grounded_before or grounded_after):
                                use_lock_move()

                    elif event.key == pygame.K_RIGHT:
                        right_held = True
                        left_held = False
                        move_timer = 0.0
                        grounded_before = on_ground()
                        if can_place(board, cur, rot, px + 1, py):
                            px += 1
                            grounded_after = on_ground()
                            if touched_ground and (grounded_before or grounded_after):
                                use_lock_move()

                    elif event.key == pygame.K_z:
                        grounded_before = on_ground()
                        if try_rotate(-1):
                            grounded_after = on_ground()
                            if touched_ground and (grounded_before or grounded_after):
                                use_lock_move()

                    elif event.key == pygame.K_x or event.key == pygame.K_UP:
                        grounded_before = on_ground()
                        if try_rotate(+1):
                            grounded_after = on_ground()
                            if touched_ground and (grounded_before or grounded_after):
                                use_lock_move()

                    elif event.key == pygame.K_c:
                        do_hold()

                    elif event.key == pygame.K_SPACE:
                        hard_drop()

                    elif event.key == pygame.K_DOWN:
                        soft_drop = True

            if event.type == pygame.KEYUP:
                if event.key == pygame.K_DOWN:
                    soft_drop = False
                elif event.key == pygame.K_LEFT:
                    left_held = False
                elif event.key == pygame.K_RIGHT:
                    right_held = False

        if alive:
            if left_held or right_held:
                move_timer += dt
                if move_timer >= move_delay:
                    step = -1 if left_held else 1
                    grounded_before = on_ground()
                    if can_place(board, cur, rot, px + step, py):
                        px += step
                        grounded_after = on_ground()
                        if touched_ground and (grounded_before or grounded_after):
                            use_lock_move()
                    move_timer -= move_repeat
            else:
                move_timer = 0.0

        if alive:
            # gravity
            grav_timer += dt
            g = gravity * (0.12 if soft_drop else 1.0)
            if grav_timer >= g:
                grav_timer = 0.0
                if can_place(board, cur, rot, px, py + 1):
                    py += 1

            grounded = on_ground()

            # first touch starts timer + gives 15 moves
            if grounded and not touched_ground:
                touched_ground = True
                lock_moves_left = MAX_LOCK_RESETS
                lock_timer = 0.0

            # while grounded: timer runs, lock on time or on 0 moves
            if touched_ground and grounded:
                lock_timer += dt
                if lock_moves_left <= 0:
                    apply_lock_and_spawn()
                elif lock_timer >= lock_delay:
                    apply_lock_and_spawn()

            # if lifted (kicks etc): do NOT reset moves, only pause timer
            if touched_ground and not grounded:
                lock_timer = 0.0

            elapsed = time.time() - start_time
            gravity = max(0.12, 0.55 - elapsed * 0.002)

        # ghost
        gpy = py
        if alive:
            while can_place(board, cur, rot, px, gpy + 1):
                gpy += 1

        # ---- DRAW ----
        screen.fill((12, 12, 16))

        # Header (üst bar aynı kalsın)
        header_h = big.get_height() + 14
        header_rect = pygame.Rect(margin, margin, w - 2 * margin, header_h)
        pygame.draw.rect(screen, (18, 18, 22), header_rect, border_radius=10)
        pygame.draw.rect(screen, (70, 70, 86), header_rect, 2, border_radius=10)
        screen.blit(big.render(f"YOU: {nickname} (id {my_id})", True, (220, 220, 230)),
                    (header_rect.x + 12, header_rect.y + 6))

        roster = get_roster()
        opp_boards = get_opp_boards()
        alive_map = get_alive_map()

        # === YENİ LAYOUT: ui.compute_game_layout ===
        layout = ui.compute_game_layout(w, h)

        # Panel çerçeveleri
        ui.draw_panel(screen, layout["left_rect"], "", font, border=(220, 40, 40))
        ui.draw_panel(screen, layout["main_rect"], "", font, border=(220, 40, 40))
        ui.draw_panel(screen, layout["mid_rect"], "", font, border=(220, 40, 40))
        ui.draw_panel(screen, layout["rank_rect"], "oyuncu siralamasi", font, border=(220, 40, 40))

        # Next + Hold panelleri (mid içinde)
        ui.draw_panel(screen, layout["next_rect"], "NEXT", font, border=(220, 40, 40))
        ui.draw_panel(screen, layout["hold_rect"], "HOLD", font, border=(220, 40, 40))

        # === yardımcı: rect içine board sığdırma ===
        def fit_board_in_rect(rect: pygame.Rect, cols: int, rows: int, pad: int = 14):
            avail_w = max(10, rect.width - pad * 2)
            avail_h = max(10, rect.height - pad * 2)
            c = max(4, min(avail_w // cols, avail_h // rows))
            ox = rect.x + (rect.width - cols * c) // 2
            oy = rect.y + (rect.height - rows * c) // 2
            return c, ox, oy

        # === SOL PANEL: 7 mini board (3 büyük + 4 küçük) ===
        ids = opp_ids_sorted()  # max 7 kişi
        slots = layout["left_big"] + layout["left_small"]  # toplam 7 slot

        for i, r in enumerate(slots):
            if i >= len(ids):
                break
            pid = ids[i]
            nm = roster.get(pid, f"Player{pid}")
            st = "DEAD" if (alive_map.get(pid, True) is False) else "LIVE"

            head = f"{pid}:{nm} [{st}]"
            head = head if small.size(head)[0] <= (r.width - 18) else head[:18] + "…"
            screen.blit(small.render(head, True, (220, 220, 230)), (r.x + 10, r.y + 8))

            # board'u slot içine ortala
            c, ox, oy = fit_board_in_rect(r, W, H, pad=16)
            draw_board(opp_boards.get(pid, empty_board()), ox, oy, c, ghost_piece=None)

        # === ORTA (MAIN) PANEL: kendi board'un büyük çizimi ===
        main_rect = layout["main_rect"]
        cell2, main_ox2, main_oy2 = fit_board_in_rect(main_rect, W, H, pad=24)

        draw_board(board, main_ox2, main_oy2, cell2, ghost_piece=(cur, rot, px, gpy))
        if alive:
            for (x, y) in TETROS[cur][rot]:
                vx, vy = px + x, py + y - HIDDEN
                if 0 <= vx < W and 0 <= vy < H:
                    pygame.draw.rect(
                        screen, COLORS[cur],
                        pygame.Rect(main_ox2 + vx * cell2, main_oy2 + vy * cell2, cell2 - 1, cell2 - 1)
                    )

        # === MID PANEL: NEXT listesi + HOLD (kutular küçük kalacak) ===
        mini = max(6, int(10 * (cell2 / 30)))

        # NEXT (dikey liste)
        nxr = layout["next_rect"]
        screen.blit(font.render("NEXT:", True, (220, 220, 230)), (nxr.x + 10, nxr.y + 10))
        nq = list(next_queue)
        start_x = nxr.x + 14
        start_y = nxr.y + 40
        step_y = mini * 4 + 10
        max_show = max(3, (nxr.height - 50) // step_y)
        for i in range(min(8, max_show)):
            piece = nq[i] if i < len(nq) else None
            if piece:
                draw_mini_piece(piece, start_x, start_y + i * step_y, mini)

        # HOLD
        hdr = layout["hold_rect"]
        screen.blit(font.render("HOLD:", True, (220, 220, 230)), (hdr.x + 10, hdr.y + 10))
        if hold:
            draw_mini_piece(hold, hdr.x + 14, hdr.y + 40, mini)

        # === RANK PANEL: oyuncu listesi (senin eski players_box yerine) ===
        rr = layout["rank_rect"]
        y_list = rr.y + 54
        line_h = 22
        max_list_w = rr.width - 24
        for idx, pid in enumerate(sorted(roster.keys())[:8], start=1):
            nm = str(roster[pid])
            st = "ALIVE" if alive_map.get(pid, True) else "DEAD"
            if pid == my_id:
                st = "YOU" if alive else "YOU(DEAD)"
            txt = f"{idx}. {pid}: {nm} - {st}"
            if small.size(txt)[0] > max_list_w:
                txt = txt[: max(1, int(max_list_w / 8))] + "…"
            screen.blit(small.render(txt, True, (190, 190, 205)), (rr.x + 12, y_list))
            y_list += line_h

        # dead overlay
        if not alive:
            overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 140))
            screen.blit(overlay, (0, 0))
            msg1 = big.render("OLDUN!", True, (255, 200, 200))
            msg2 = font.render("Izliyorsun... (ESC ile cik)", True, (220, 220, 230))
            screen.blit(msg1, (main_ox2 + (W * cell2 - msg1.get_width()) // 2, main_oy2 + (H * cell2) // 2 - 30))
            screen.blit(msg2, (main_ox2 + (W * cell2 - msg2.get_width()) // 2, main_oy2 + (H * cell2) // 2 + 10))

        pygame.display.flip()
