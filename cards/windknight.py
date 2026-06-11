def is_valid_windknight_target(game, row, col):
    """
    Windknight:
    Must be dropped on one of the current player's knights.
    The selected knight then moves twice in a row.
    """
    piece = game.board[row][col]

    if piece is None:
        return False

    if game.piece_color(piece) != game.turn:
        return False

    return piece.lower() == "n"