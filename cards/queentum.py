def get_queentum_moves(game, row, col):
    """
    Queentum:
    The selected queen can teleport to any square on the board.

    Allowed targets:
    - any empty square
    - any enemy non-king piece square, capturing that piece

    Not allowed:
    - friendly occupied squares
    - enemy king square
    - a destination that leaves your own king in check
      this last rule is checked by main.py through get_legal_moves()
    """
    piece = game.board[row][col]

    if piece is None:
        return []

    if piece.lower() != "q":
        return []

    color = game.piece_color(piece)
    moves = []

    for target_row in range(8):
        for target_col in range(8):
            if (target_row, target_col) == (row, col):
                continue

            target_piece = game.board[target_row][target_col]

            if target_piece is None:
                moves.append((target_row, target_col))
                continue

            target_color = game.piece_color(target_piece)

            if target_color != color and target_piece.lower() != "k":
                moves.append((target_row, target_col))

    return moves