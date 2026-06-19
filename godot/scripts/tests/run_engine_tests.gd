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

func sq(file: String, rank: int) -> Vector2i:
	var col = "abcdefgh".find(file)
	var row = 8 - rank
	return Vector2i(row, col)

func _init():
	test_hand_dealt()
	test_move_ether()
	test_capture_ether()
	test_check_bonus()
	test_end_turn_requires_move()
	test_card_spend_cost()
	test_discard_limit()
	test_hand_refill_on_turn_start()
	print("---")
	print("%d/%d checks passed" % [checks - failures, checks])
	quit(1 if failures > 0 else 0)

func test_hand_dealt():
	var g = GameEngine.new()
	check("white starts with 5 cards", g.hand[GameEngine.WHITE].size() == 5)
	check("black starts with 5 cards", g.hand[GameEngine.BLACK].size() == 5)
	check("white starts with 0 ether", g.ether[GameEngine.WHITE] == 0)

func test_move_ether():
	var g = GameEngine.new()
	var ok = g.try_move(sq("e", 2), sq("e", 4))
	check("e2-e4 is accepted", ok)
	check("white gains 2 ether for a 2-square pawn move", g.ether[GameEngine.WHITE] == 2)

func test_capture_ether():
	var g = GameEngine.new()
	g.try_move(sq("e", 2), sq("e", 4))
	g.end_turn()
	g.try_move(sq("d", 7), sq("d", 5))
	g.end_turn()
	g.try_move(sq("e", 4), sq("d", 5))  # pawn captures pawn, 1 square diagonal
	check("capturing a pawn grants 1 (move) + 1 (value) ether", g.ether[GameEngine.WHITE] == 2 + 1 + 1)

func test_check_bonus():
	var g = GameEngine.new()
	for r in range(8):
		for c in range(8):
			g.chess.board[r][c] = ""
	g.chess.board[0][0] = "k"
	g.chess.board[7][7] = "K"
	g.chess.board[1][7] = "R"  # white rook can deliver check along rank 1 / col a
	g.chess.turn = GameEngine.WHITE
	var ok = g.try_move(Vector2i(1, 7), Vector2i(1, 0))  # rook to a7, checking black king on a8
	check("rook move to deliver check succeeds", ok)
	check("black king is in check", g.chess.is_in_check(GameEngine.BLACK))
	var before = g.ether[GameEngine.WHITE]
	g.end_turn()
	check("check bonus of +5 awarded on end_turn", g.ether[GameEngine.WHITE] == before + 5)

func test_end_turn_requires_move():
	var g = GameEngine.new()
	var ended = g.end_turn()
	check("end_turn fails before any move is made", not ended)
	g.try_move(sq("e", 2), sq("e", 4))
	ended = g.end_turn()
	check("end_turn succeeds after a move", ended)
	check("turn passes to black", g.chess.turn == GameEngine.BLACK)

func test_card_spend_cost():
	var g = GameEngine.new()
	g.hand[GameEngine.WHITE] = ["pawntastic"]
	g.ether[GameEngine.WHITE] = 0
	var ok = g.spend_card("pawntastic")
	check("cannot afford pawntastic with 0 ether", not ok)
	g.ether[GameEngine.WHITE] = 1
	ok = g.spend_card("pawntastic")
	check("can afford pawntastic with 1 ether", ok)
	check("ether deducted", g.ether[GameEngine.WHITE] == 0)
	check("card moved to discard", g.discard[GameEngine.WHITE].has("pawntastic"))
	check("card removed from hand", not g.hand[GameEngine.WHITE].has("pawntastic"))

func test_discard_limit():
	var g = GameEngine.new()
	g.discards_used[GameEngine.WHITE] = GameEngine.MAX_DISCARDS
	var card = g.hand[GameEngine.WHITE][0]
	var ok = g.discard_card(card)
	check("discard fails once the per-game limit is reached", not ok)

func test_hand_refill_on_turn_start():
	var g = GameEngine.new()
	var card = g.hand[GameEngine.WHITE][0]
	g.ether[GameEngine.WHITE] = 100
	g.spend_card(card)
	check("hand has 4 cards after spending one", g.hand[GameEngine.WHITE].size() == 4)
	g.try_move(sq("e", 2), sq("e", 4))
	g.end_turn()
	g.try_move(sq("e", 7), sq("e", 5))
	g.end_turn()
	check("white's hand refilled to 5 on their next turn start", g.hand[GameEngine.WHITE].size() == 5)
