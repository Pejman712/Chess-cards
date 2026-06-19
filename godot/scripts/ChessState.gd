extends RefCounted
class_name ChessState

# Board encoding matches main.py: uppercase = White, lowercase = Black.
# Empty squares are "".
const WHITE = "white"
const BLACK = "black"

const PIECE_VALUES = {"p": 1, "n": 3, "b": 3, "r": 5, "q": 9, "k": 12}

var board: Array = []  # 8x8 Array of String ("" for empty)
var turn: String = WHITE

var white_king_moved := false
var black_king_moved := false
var white_left_rook_moved := false
var white_right_rook_moved := false
var black_left_rook_moved := false
var black_right_rook_moved := false

var en_passant_target = null  # Vector2i or null

var game_over := false
var winner_message := ""
var status_message := "White to move"

func _init():
	board = initial_board()

static func initial_board() -> Array:
	var b = []
	b.append(["r", "n", "b", "q", "k", "b", "n", "r"])
	b.append(["p", "p", "p", "p", "p", "p", "p", "p"])
	for _i in range(4):
		b.append(["", "", "", "", "", "", "", ""])
	b.append(["P", "P", "P", "P", "P", "P", "P", "P"])
	b.append(["R", "N", "B", "Q", "K", "B", "N", "R"])
	return b

func clone() -> ChessState:
	var c = ChessState.new()
	c.board = []
	for row in board:
		c.board.append(row.duplicate())
	c.turn = turn
	c.white_king_moved = white_king_moved
	c.black_king_moved = black_king_moved
	c.white_left_rook_moved = white_left_rook_moved
	c.white_right_rook_moved = white_right_rook_moved
	c.black_left_rook_moved = black_left_rook_moved
	c.black_right_rook_moved = black_right_rook_moved
	c.en_passant_target = en_passant_target
	c.game_over = game_over
	c.winner_message = winner_message
	c.status_message = status_message
	return c

func piece_color(piece: String):
	if piece == "" or piece == null:
		return null
	return WHITE if piece == piece.to_upper() else BLACK

func enemy_color(color: String) -> String:
	return BLACK if color == WHITE else WHITE

func in_bounds(row: int, col: int) -> bool:
	return row >= 0 and row < 8 and col >= 0 and col < 8

func is_empty(row: int, col: int) -> bool:
	return board[row][col] == ""

func is_enemy(row: int, col: int, color: String) -> bool:
	var piece = board[row][col]
	return piece != "" and piece_color(piece) != color

func is_friend(row: int, col: int, color: String) -> bool:
	var piece = board[row][col]
	return piece != "" and piece_color(piece) == color

func get_piece_value(piece: String) -> int:
	if piece == "":
		return 0
	return PIECE_VALUES.get(piece.to_lower(), 0)

func get_move_distance(piece: String, from_square: Vector2i, to_square: Vector2i) -> int:
	if piece == "":
		return 0
	var dr = abs(to_square.x - from_square.x)
	var dc = abs(to_square.y - from_square.y)
	if piece.to_lower() == "n":
		return dr + dc
	return max(dr, dc)

# -----------------------------
# Pseudo-legal move generation
# -----------------------------
func get_pseudo_legal_moves(row: int, col: int, include_castling: bool = true) -> Array:
	var piece = board[row][col]
	if piece == "":
		return []

	var color = piece_color(piece)
	var piece_type = piece.to_lower()
	var moves = []

	if piece_type == "p":
		moves.append_array(get_pawn_moves(row, col, color))
	elif piece_type == "r":
		moves.append_array(get_sliding_moves(row, col, color, [Vector2i(-1,0),Vector2i(1,0),Vector2i(0,-1),Vector2i(0,1)]))
	elif piece_type == "b":
		moves.append_array(get_sliding_moves(row, col, color, [Vector2i(-1,-1),Vector2i(-1,1),Vector2i(1,-1),Vector2i(1,1)]))
	elif piece_type == "q":
		moves.append_array(get_sliding_moves(row, col, color, [
			Vector2i(-1,0),Vector2i(1,0),Vector2i(0,-1),Vector2i(0,1),
			Vector2i(-1,-1),Vector2i(-1,1),Vector2i(1,-1),Vector2i(1,1)
		]))
	elif piece_type == "n":
		var knight_steps = [
			Vector2i(-2,-1),Vector2i(-2,1),Vector2i(-1,-2),Vector2i(-1,2),
			Vector2i(1,-2),Vector2i(1,2),Vector2i(2,-1),Vector2i(2,1),
		]
		for step in knight_steps:
			var nr = row + step.x
			var nc = col + step.y
			if in_bounds(nr, nc) and not is_friend(nr, nc, color):
				moves.append(Vector2i(nr, nc))
	elif piece_type == "k":
		var king_steps = [
			Vector2i(-1,-1),Vector2i(-1,0),Vector2i(-1,1),
			Vector2i(0,-1),Vector2i(0,1),
			Vector2i(1,-1),Vector2i(1,0),Vector2i(1,1),
		]
		for step in king_steps:
			var nr = row + step.x
			var nc = col + step.y
			if in_bounds(nr, nc) and not is_friend(nr, nc, color):
				moves.append(Vector2i(nr, nc))
		if include_castling:
			moves.append_array(get_castling_moves(color))

	return moves

func get_pawn_moves(row: int, col: int, color: String) -> Array:
	var moves = []
	var direction = -1 if color == WHITE else 1
	var start_row = 6 if color == WHITE else 1

	var one_row = row + direction
	if in_bounds(one_row, col) and is_empty(one_row, col):
		moves.append(Vector2i(one_row, col))
		var two_row = row + 2 * direction
		if row == start_row and in_bounds(two_row, col) and is_empty(two_row, col):
			moves.append(Vector2i(two_row, col))

	for dc in [-1, 1]:
		var nr = row + direction
		var nc = col + dc
		if in_bounds(nr, nc) and is_enemy(nr, nc, color):
			moves.append(Vector2i(nr, nc))

	if en_passant_target != null:
		var ep: Vector2i = en_passant_target
		if ep.x == row + direction and abs(ep.y - col) == 1:
			moves.append(ep)

	return moves

func get_sliding_moves(row: int, col: int, color: String, directions: Array) -> Array:
	var moves = []
	for d in directions:
		var nr = row + d.x
		var nc = col + d.y
		while in_bounds(nr, nc):
			if is_empty(nr, nc):
				moves.append(Vector2i(nr, nc))
			elif is_enemy(nr, nc, color):
				moves.append(Vector2i(nr, nc))
				break
			else:
				break
			nr += d.x
			nc += d.y
	return moves

func get_castling_moves(color: String) -> Array:
	var moves = []
	var row: int
	var king_moved: bool
	var left_rook_moved: bool
	var right_rook_moved: bool
	var king_piece: String

	if color == WHITE:
		row = 7
		king_moved = white_king_moved
		left_rook_moved = white_left_rook_moved
		right_rook_moved = white_right_rook_moved
		king_piece = "K"
	else:
		row = 0
		king_moved = black_king_moved
		left_rook_moved = black_left_rook_moved
		right_rook_moved = black_right_rook_moved
		king_piece = "k"

	if board[row][4] != king_piece:
		return moves
	if king_moved:
		return moves
	if is_in_check(color):
		return moves

	var enemy = enemy_color(color)

	if not right_rook_moved:
		if board[row][7] != "" and board[row][7].to_lower() == "r":
			if is_empty(row, 5) and is_empty(row, 6):
				if not is_square_attacked(row, 5, enemy) and not is_square_attacked(row, 6, enemy):
					moves.append(Vector2i(row, 6))

	if not left_rook_moved:
		if board[row][0] != "" and board[row][0].to_lower() == "r":
			if is_empty(row, 1) and is_empty(row, 2) and is_empty(row, 3):
				if not is_square_attacked(row, 3, enemy) and not is_square_attacked(row, 2, enemy):
					moves.append(Vector2i(row, 2))

	return moves

func get_legal_moves(row: int, col: int) -> Array:
	return legal_filter(row, col, get_pseudo_legal_moves(row, col))

# Filters an arbitrary list of candidate destination squares the same way
# get_legal_moves does: no capturing a king, and the mover's own king must
# not end up in check. Used by cards (Pawntastic/Queentum) whose pseudo-move
# set differs from the piece's normal moves.
func legal_filter(row: int, col: int, pseudo_moves: Array) -> Array:
	var piece = board[row][col]
	if piece == "":
		return []

	var color = piece_color(piece)
	var legal_moves = []

	for move in pseudo_moves:
		var target_piece = board[move.x][move.y]
		if target_piece != "" and target_piece.to_lower() == "k":
			continue

		var test_state = clone()
		test_state.make_move(Vector2i(row, col), move, true)

		if not test_state.is_in_check(color):
			legal_moves.append(move)

	return legal_moves

func get_capture_moves_only(row: int, col: int) -> Array:
	var piece = board[row][col]
	if piece == "":
		return []

	var legal_moves = get_legal_moves(row, col)
	var capture_moves = []

	for m in legal_moves:
		var target_piece = board[m.x][m.y]
		if target_piece != "" and piece_color(target_piece) != piece_color(piece):
			capture_moves.append(m)
		elif piece.to_lower() == "p" and en_passant_target != null and en_passant_target == m:
			capture_moves.append(m)

	return capture_moves

# -----------------------------
# Check / attacks
# -----------------------------
func find_king(color: String):
	var target = "K" if color == WHITE else "k"
	for row in range(8):
		for col in range(8):
			if board[row][col] == target:
				return Vector2i(row, col)
	return null

func is_in_check(color: String) -> bool:
	var king_pos = find_king(color)
	if king_pos == null:
		return false
	var enemy = enemy_color(color)
	return is_square_attacked(king_pos.x, king_pos.y, enemy)

func is_square_attacked(row: int, col: int, by_color: String) -> bool:
	for r in range(8):
		for c in range(8):
			var piece = board[r][c]
			if piece == "":
				continue
			if piece_color(piece) != by_color:
				continue

			var piece_type = piece.to_lower()

			if piece_type == "p":
				var direction = -1 if by_color == WHITE else 1
				for dc in [-1, 1]:
					if r + direction == row and c + dc == col:
						return true
			elif piece_type == "k":
				if abs(r - row) <= 1 and abs(c - col) <= 1:
					return true
			else:
				var moves = get_pseudo_legal_moves(r, c, false)
				for m in moves:
					if m.x == row and m.y == col:
						return true

	return false

func has_any_legal_moves(color: String) -> bool:
	for row in range(8):
		for col in range(8):
			var piece = board[row][col]
			if piece != "" and piece_color(piece) == color:
				if get_legal_moves(row, col).size() > 0:
					return true
	return false

# -----------------------------
# Making moves
# -----------------------------
static func square_name(row: int, col: int) -> String:
	var files = "abcdefgh"
	return "%s%d" % [files[col], 8 - row]

func move_notation(piece: String, from_square: Vector2i, to_square: Vector2i, captured_piece: String) -> String:
	var letter = piece.to_upper()
	var sep = "x" if captured_piece != "" else "-"
	return "%s %s%s%s" % [letter, square_name(from_square.x, from_square.y), sep, square_name(to_square.x, to_square.y)]

# Returns a dict describing what happened, for animation/sound hooks:
# {captured: String, is_castle: bool, is_en_passant: bool, promoted: bool}
func make_move(from_square: Vector2i, to_square: Vector2i, test_mode: bool = false) -> Dictionary:
	var from_row = from_square.x
	var from_col = from_square.y
	var to_row = to_square.x
	var to_col = to_square.y

	var piece = board[from_row][from_col]
	var captured_piece = board[to_row][to_col]
	var result = {"captured": "", "is_castle": false, "is_en_passant": false, "promoted": false}

	if piece == "":
		return result

	var color = piece_color(piece)
	var piece_type = piece.to_lower()

	# En passant capture: pawn moves diagonally into an empty target square.
	var is_en_passant = false
	if piece_type == "p" and captured_piece == "" and from_col != to_col:
		is_en_passant = true
		var captured_row = from_row
		var captured_col = to_col
		captured_piece = board[captured_row][captured_col]
		board[captured_row][captured_col] = ""
		result["is_en_passant"] = true

	# Castling: king moves two columns; move the rook too.
	var is_castle = false
	if piece_type == "k" and abs(to_col - from_col) == 2:
		is_castle = true
		result["is_castle"] = true
		var row = from_row
		if to_col == 6:
			board[row][5] = board[row][7]
			board[row][7] = ""
		elif to_col == 2:
			board[row][3] = board[row][0]
			board[row][0] = ""

	board[to_row][to_col] = piece
	board[from_row][from_col] = ""

	# Pawn promotion: always to queen (matches main.py's simplified rule set).
	if piece_type == "p" and (to_row == 0 or to_row == 7):
		board[to_row][to_col] = "Q" if color == WHITE else "q"
		result["promoted"] = true

	result["captured"] = captured_piece if captured_piece != null else ""

	# Track castling rights.
	update_castling_rights_for_move(from_row, from_col, piece)
	update_castling_rights_for_capture(to_row, to_col, captured_piece)

	# Set up en passant target for the *next* move.
	en_passant_target = null
	if piece_type == "p" and abs(to_row - from_row) == 2:
		en_passant_target = Vector2i((from_row + to_row) / 2, from_col)

	if not test_mode:
		update_status()

	return result

func update_castling_rights_for_move(from_row: int, from_col: int, piece: String) -> void:
	if piece == "K":
		white_king_moved = true
	elif piece == "k":
		black_king_moved = true
	elif piece == "R":
		if from_row == 7 and from_col == 0:
			white_left_rook_moved = true
		elif from_row == 7 and from_col == 7:
			white_right_rook_moved = true
	elif piece == "r":
		if from_row == 0 and from_col == 0:
			black_left_rook_moved = true
		elif from_row == 0 and from_col == 7:
			black_right_rook_moved = true

func update_castling_rights_for_capture(row: int, col: int, captured_piece) -> void:
	if captured_piece == null or captured_piece == "":
		return
	if row == 7 and col == 0 and captured_piece == "R":
		white_left_rook_moved = true
	elif row == 7 and col == 7 and captured_piece == "R":
		white_right_rook_moved = true
	elif row == 0 and col == 0 and captured_piece == "r":
		black_left_rook_moved = true
	elif row == 0 and col == 7 and captured_piece == "r":
		black_right_rook_moved = true

func update_status() -> void:
	var enemy = enemy_color(turn)
	if is_in_check(enemy):
		if not has_any_legal_moves(enemy):
			game_over = true
			winner_message = "%s wins by checkmate." % turn.capitalize()
			status_message = winner_message
		else:
			status_message = "%s is in check." % enemy.capitalize()
	elif not has_any_legal_moves(enemy):
		game_over = true
		winner_message = "Draw by stalemate."
		status_message = winner_message
	else:
		status_message = "%s to move" % enemy.capitalize()
