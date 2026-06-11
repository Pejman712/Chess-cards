def get_bishock_destroyed_squares(game, row, col):
    """
    Bishock:
    Select one of your bishops.
    It destroys every non-king piece on all four diagonals.
    Kings are not destroyed.
    The bishop also destroys itself.
    """

    piece = game.board[row][col]

    if piece is None:
        return []

    if piece.lower() != "b":
        return []

    destroyed = []

    directions = [
        (-1, -1),
        (-1, 1),
        (1, -1),
        (1, 1),
    ]

    for dr, dc in directions:
        current_row = row + dr
        current_col = col + dc

        while game.in_bounds(current_row, current_col):
            target_piece = game.board[current_row][current_col]

            if target_piece is not None:
                if target_piece.lower() != "k":
                    destroyed.append((current_row, current_col))

            current_row += dr
            current_col += dc

    destroyed.append((row, col))

    return destroyed