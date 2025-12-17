import random

W, H = 10, 20
HIDDEN = 2

TETROS = {
    "I": [
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        [(2, 0), (2, 1), (2, 2), (2, 3)],
        [(0, 2), (1, 2), (2, 2), (3, 2)],
        [(1, 0), (1, 1), (1, 2), (1, 3)],
    ],
    "O": [[(1, 1), (2, 1), (1, 2), (2, 2)]] * 4,
    "T": [
        [(1, 1), (0, 2), (1, 2), (2, 2)],
        [(1, 1), (1, 2), (2, 2), (1, 3)],
        [(0, 2), (1, 2), (2, 2), (1, 3)],
        [(1, 1), (0, 2), (1, 2), (1, 3)],
    ],
    "S": [
        [(1, 1), (2, 1), (0, 2), (1, 2)],
        [(1, 1), (1, 2), (2, 2), (2, 3)],
        [(1, 2), (2, 2), (0, 3), (1, 3)],
        [(0, 1), (0, 2), (1, 2), (1, 3)],
    ],
    "Z": [
        [(0, 1), (1, 1), (1, 2), (2, 2)],
        [(2, 1), (1, 2), (2, 2), (1, 3)],
        [(0, 2), (1, 2), (1, 3), (2, 3)],
        [(1, 1), (0, 2), (1, 2), (0, 3)],
    ],
    "J": [
        [(0, 1), (0, 2), (1, 2), (2, 2)],
        [(1, 1), (2, 1), (1, 2), (1, 3)],
        [(0, 2), (1, 2), (2, 2), (2, 3)],
        [(1, 1), (1, 2), (0, 3), (1, 3)],
    ],
    "L": [
        [(2, 1), (0, 2), (1, 2), (2, 2)],
        [(1, 1), (1, 2), (1, 3), (2, 3)],
        [(0, 2), (1, 2), (2, 2), (0, 3)],
        [(0, 1), (1, 1), (1, 2), (1, 3)],
    ],
}

COLORS = {
    "I": (0, 240, 240),
    "O": (240, 240, 0),
    "T": (160, 0, 240),
    "S": (0, 240, 0),
    "Z": (240, 0, 0),
    "J": (0, 0, 240),
    "L": (240, 160, 0),
    "G": (90, 90, 90),
}

def new_bag():
    bag = list(TETROS.keys())
    random.shuffle(bag)
    return bag

def empty_board():
    return [[None for _ in range(W)] for _ in range(H + HIDDEN)]

def can_place(board, piece, rot, px, py):
    for (x, y) in TETROS[piece][rot]:
        gx, gy = px + x, py + y
        if gx < 0 or gx >= W or gy < 0 or gy >= (H + HIDDEN):
            return False
        if board[gy][gx] is not None:
            return False
    return True

def lock_piece(board, piece, rot, px, py):
    for (x, y) in TETROS[piece][rot]:
        board[py + y][px + x] = piece

def clear_lines(board):
    cleared = 0
    y = HIDDEN
    while y < (H + HIDDEN):
        if all(board[y][x] is not None for x in range(W)):
            del board[y]
            board.insert(0, [None] * W)
            cleared += 1
        else:
            y += 1
    return cleared

def add_garbage(board, n):
    for _ in range(n):
        hole = random.randrange(W)
        row = ["G"] * W
        row[hole] = None
        board.pop(0)
        board.append(row)

def board_to_string(board):
    out = []
    for y in range(HIDDEN, H + HIDDEN):
        for x in range(W):
            c = board[y][x]
            out.append("." if c is None else c)
    return "".join(out)

def string_to_board(s):
    b = empty_board()
    if not s or len(s) < W * H:
        return b
    i = 0
    for y in range(HIDDEN, H + HIDDEN):
        for x in range(W):
            ch = s[i]
            i += 1
            b[y][x] = None if ch == "." else ch
    return b