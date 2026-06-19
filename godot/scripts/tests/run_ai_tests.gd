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
	test_stockfish_loads()
	test_fen_roundtrip()
	test_ai_plays_a_full_opening()
	test_fallback_prefers_captures()
	print("---")
	print("%d/%d checks passed" % [checks - failures, checks])
	quit(1 if failures > 0 else 0)

func test_stockfish_loads():
	var ai = GameAI.new("Easy")
	check("stockfish binary loads and reports available", ai.has_engine())
	ai.quit()

func test_fen_roundtrip():
	var g = GameEngine.new()
	var fen = StockfishEngine.board_to_fen(g)
	check("starting position FEN matches", fen.begins_with("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"))

func test_ai_plays_a_full_opening():
	var g = GameEngine.new()
	var ai = GameAI.new("Easy")
	check("engine available for opening test", ai.has_engine())

	# White (human) plays e4, then the AI (black) should reply with a legal move.
	var ok = g.try_move(Vector2i(6, 4), Vector2i(4, 4))
	check("human e2-e4 accepted", ok)
	g.end_turn()
	check("turn passed to black (AI)", g.chess.turn == GameEngine.BLACK)

	ai.apply_ai_turn(g, GameEngine.BLACK, GameEngine.WHITE)
	check("AI made a move and handed the turn back", g.chess.turn == GameEngine.WHITE)
	check("game is not over after one exchange", not g.game_over)

	ai.quit()

func test_fallback_prefers_captures():
	var g = GameEngine.new()
	for r in range(8):
		for c in range(8):
			g.chess.board[r][c] = ""
	g.chess.board[4][4] = "R"   # white rook
	g.chess.board[4][6] = "p"   # capturable black pawn
	g.chess.board[0][0] = "K"
	g.chess.board[7][7] = "k"
	g.chess.turn = GameEngine.WHITE

	var move = GameAI.fallback_move(g, GameEngine.WHITE, GameEngine.BLACK)
	check("fallback AI found a move", move != null)
	check("fallback AI chooses the capture over a quiet move", move[1] == Vector2i(4, 6))
