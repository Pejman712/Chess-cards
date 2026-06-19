extends SceneTree

var failures := 0
var checks := 0

func check(label: String, cond: bool):
	checks += 1
	if not cond:
		failures += 1
		print("FAIL: ", label)
	else:
		print("ok:   ", label)

func _init():
	test_initial_moves()
	test_scholars_mate_checkmate()
	test_castling()
	test_en_passant()
	test_promotion()
	test_stalemate()
	print("---")
	print("%d/%d checks passed" % [checks - failures, checks])
	quit(1 if failures > 0 else 0)

func test_initial_moves():
	var s = ChessState.new()
	var pawn_moves = s.get_legal_moves(6, 4)  # e2
	check("e2 pawn has 2 legal moves at start", pawn_moves.size() == 2)
	var knight_moves = s.get_legal_moves(7, 1)  # Nb1
	check("Nb1 has 2 legal moves at start", knight_moves.size() == 2)
	check("white has legal moves", s.has_any_legal_moves(ChessState.WHITE))

func sq(file: String, rank: int) -> Vector2i:
	var col = "abcdefgh".find(file)
	var row = 8 - rank
	return Vector2i(row, col)

func test_scholars_mate_checkmate():
	# Fool's mate: fastest checkmate, 2 moves each.
	var s = ChessState.new()
	s.make_move(sq("f", 2), sq("f", 3)); s.turn = s.enemy_color(s.turn)
	s.make_move(sq("e", 7), sq("e", 5)); s.turn = s.enemy_color(s.turn)
	s.make_move(sq("g", 2), sq("g", 4)); s.turn = s.enemy_color(s.turn)
	s.make_move(sq("d", 8), sq("h", 4)); s.turn = s.enemy_color(s.turn)
	check("fool's mate ends the game", s.game_over)
	check("black wins fool's mate", s.winner_message.begins_with("Black"))

func test_castling():
	var s = ChessState.new()
	# Clear pieces between king and rook on white's kingside, and knight/bishop too.
	s.board[7][5] = ""
	s.board[7][6] = ""
	var moves = s.get_legal_moves(7, 4)  # king e1
	var can_castle = false
	for m in moves:
		if m == Vector2i(7, 6):
			can_castle = true
	check("white king can castle kingside when path is clear", can_castle)

	if can_castle:
		s.make_move(sq("e", 1), sq("g", 1))
		check("king moved to g1", s.board[7][6] == "K")
		check("rook moved to f1", s.board[7][5] == "R")
		check("h1 is now empty", s.board[7][7] == "")

func test_en_passant():
	var s = ChessState.new()
	s.make_move(sq("e", 2), sq("e", 4)); s.turn = s.enemy_color(s.turn)
	s.make_move(sq("a", 7), sq("a", 6)); s.turn = s.enemy_color(s.turn)
	s.make_move(sq("e", 4), sq("e", 5)); s.turn = s.enemy_color(s.turn)
	s.make_move(sq("d", 7), sq("d", 5)); s.turn = s.enemy_color(s.turn)
	# White pawn on e5 should be able to capture en passant on d6.
	var moves = s.get_legal_moves(3, 4)  # e5 = row 3, col 4
	var has_ep = false
	for m in moves:
		if m == sq("d", 6):
			has_ep = true
	check("en passant capture is a legal move", has_ep)
	if has_ep:
		s.make_move(sq("e", 5), sq("d", 6))
		check("en passant captured the d5 pawn", s.board[3][3] == "")
		check("pawn landed on d6", s.board[2][3] == "P")

func test_promotion():
	var s = ChessState.new()
	s.board = ChessState.initial_board()
	for r in range(8):
		for c in range(8):
			s.board[r][c] = ""
	s.board[1][0] = "P"  # white pawn one step from promoting on a8
	s.board[0][7] = "k"
	s.board[7][7] = "K"
	s.make_move(Vector2i(1, 0), Vector2i(0, 0))
	check("pawn promotes to queen", s.board[0][0] == "Q")

func test_stalemate():
	var s = ChessState.new()
	for r in range(8):
		for c in range(8):
			s.board[r][c] = ""
	# Classic stalemate: black king a8, white king c7, white queen b6. Black to move.
	s.board[0][0] = "k"
	s.board[1][2] = "K"
	s.board[2][1] = "Q"
	s.turn = ChessState.BLACK
	check("black has no legal moves (stalemate)", not s.has_any_legal_moves(ChessState.BLACK))
	check("black is not in check", not s.is_in_check(ChessState.BLACK))
