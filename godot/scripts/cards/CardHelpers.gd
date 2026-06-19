extends RefCounted
class_name CardHelpers

# Pure move/target calculators ported from cards/*.py. None of these touch
# Ether, hands, or game state beyond reading the board - GameEngine applies
# the actual effects.

static func pawntastic_moves(chess: ChessState, row: int, col: int) -> Array:
	var piece = chess.board[row][col]
	if piece == "" or piece.to_lower() != "p":
		return []

	var color = chess.piece_color(piece)
	var direction = -1 if color == ChessState.WHITE else 1
	var moves = []

	for distance in range(1, 5):
		var target_row = row + direction * distance
		var target_col = col
		if not chess.in_bounds(target_row, target_col):
			break
		if not chess.is_empty(target_row, target_col):
			break
		moves.append(Vector2i(target_row, target_col))

	return moves

static func bishock_destroyed_squares(chess: ChessState, row: int, col: int) -> Array:
	var piece = chess.board[row][col]
	if piece == "" or piece.to_lower() != "b":
		return []

	var destroyed = []
	var directions = [Vector2i(-1,-1), Vector2i(-1,1), Vector2i(1,-1), Vector2i(1,1)]

	for d in directions:
		var cr = row + d.x
		var cc = col + d.y
		while chess.in_bounds(cr, cc):
			var target_piece = chess.board[cr][cc]
			if target_piece != "" and target_piece.to_lower() != "k":
				destroyed.append(Vector2i(cr, cc))
			cr += d.x
			cc += d.y

	destroyed.append(Vector2i(row, col))
	return destroyed

static func rookdemon_path(from_square: Vector2i, to_square: Vector2i) -> Array:
	var path = []
	if from_square.x == to_square.x:
		var step = 1 if to_square.y > from_square.y else -1
		var c = from_square.y + step
		while c != to_square.y + step:
			path.append(Vector2i(from_square.x, c))
			c += step
	elif from_square.y == to_square.y:
		var step = 1 if to_square.x > from_square.x else -1
		var r = from_square.x + step
		while r != to_square.x + step:
			path.append(Vector2i(r, from_square.y))
			r += step
	return path

static func is_valid_windknight_target(chess: ChessState, row: int, col: int, turn: String) -> bool:
	var piece = chess.board[row][col]
	if piece == "":
		return false
	if chess.piece_color(piece) != turn:
		return false
	return piece.to_lower() == "n"

static func queentum_moves(chess: ChessState, row: int, col: int) -> Array:
	var piece = chess.board[row][col]
	if piece == "" or piece.to_lower() != "q":
		return []

	var color = chess.piece_color(piece)
	var moves = []

	for tr in range(8):
		for tc in range(8):
			if tr == row and tc == col:
				continue
			var target_piece = chess.board[tr][tc]
			if target_piece == "":
				moves.append(Vector2i(tr, tc))
				continue
			var target_color = chess.piece_color(target_piece)
			if target_color != color and target_piece.to_lower() != "k":
				moves.append(Vector2i(tr, tc))

	return moves

const ESCAPE_CORNERS = [Vector2i(0,0), Vector2i(0,7), Vector2i(7,0), Vector2i(7,7)]

static func get_empty_escape_corners(chess: ChessState) -> Array:
	var result = []
	for corner in ESCAPE_CORNERS:
		if chess.board[corner.x][corner.y] == "":
			result.append(corner)
	return result

static func get_surrounding_empty_squares(chess: ChessState, row: int, col: int) -> Array:
	var squares = []
	for dr in [-1, 0, 1]:
		for dc in [-1, 0, 1]:
			if dr == 0 and dc == 0:
				continue
			var nr = row + dr
			var nc = col + dc
			if chess.in_bounds(nr, nc) and chess.board[nr][nc] == "":
				squares.append(Vector2i(nr, nc))
	return squares
