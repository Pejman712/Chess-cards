def get_rookdemon_path(from_square, to_square):
    """
    Returns every square the rook travels through, including destination,
    excluding the starting square.
    Only works for straight rook movement.
    """
    from_row, from_col = from_square
    to_row, to_col = to_square

    path = []

    if from_row == to_row:
        step_col = 1 if to_col > from_col else -1

        for col in range(from_col + step_col, to_col + step_col, step_col):
            path.append((from_row, col))

    elif from_col == to_col:
        step_row = 1 if to_row > from_row else -1

        for row in range(from_row + step_row, to_row + step_row, step_row):
            path.append((row, from_col))

    return path