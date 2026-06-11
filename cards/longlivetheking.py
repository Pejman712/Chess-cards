# cards/longlivetheking.py

import random


def get_empty_escape_corners(game):
    corners = [(0, 0), (0, 7), (7, 0), (7, 7)]
    return [corner for corner in corners if game.board[corner[0]][corner[1]] is None]


def choose_random_escape_corner(game):
    empty_corners = get_empty_escape_corners(game)

    if not empty_corners:
        return None

    return random.choice(empty_corners)


def get_surrounding_empty_squares(game, row, col):
    squares = []

    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue

            nr = row + dr
            nc = col + dc

            if game.in_bounds(nr, nc) and game.board[nr][nc] is None:
                squares.append((nr, nc))

    return squares