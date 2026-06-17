def get_pawntastic_moves(game, row, col):
    """
    Pawntastic:
    The selected pawn may move 1 to 4 squares forward.
    It cannot capture.
    It cannot jump over pieces.
    Every square on the path must be empty.
    """
    piece = game.board[row][col]

    if piece is None:
        return []

    if piece.lower() != "p":
        return []

    color = game.piece_color(piece)
    direction = -1 if color == "white" else 1

    moves = []

    for distance in range(1, 5):
        target_row = row + direction * distance
        target_col = col

        if not game.in_bounds(target_row, target_col):
            break

        if not game.is_empty(target_row, target_col):
            break

        moves.append((target_row, target_col))

    return moves
