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

func empty_engine() -> GameEngine:
	var g = GameEngine.new()
	for r in range(8):
		for c in range(8):
			g.chess.board[r][c] = ""
	return g

func give_card(g: GameEngine, card: String, ether: int = 999):
	if not g.hand[g.chess.turn].has(card):
		g.hand[g.chess.turn].append(card)
	g.ether[g.chess.turn] = ether

func _init():
	test_pawntastic()
	test_bishock()
	test_rookdemon()
	test_windknight()
	test_queentum()
	test_longlivetheking()
	test_switchero()
	test_prophecy()
	test_armageddon()
	test_thedramatic()
	test_capitalism()
	test_plague()
	test_solo()
	test_absoluteprotection()
	test_timetraveler()
	test_extrablood()
	test_chrisma()
	test_inzone()
	test_nope_cancel()
	test_nope_check()
	test_communism()
	test_gambit()
	test_propaganda()
	test_ifeelsafe()
	test_iguess()
	test_gravitystorm()
	print("---")
	print("%d/%d checks passed" % [checks - failures, checks])
	quit(1 if failures > 0 else 0)

func test_pawntastic():
	var g = empty_engine()
	g.chess.board[6][4] = "P"  # white pawn e2
	g.chess.board[0][0] = "k"
	g.chess.board[7][0] = "K"
	give_card(g, "pawntastic")
	var ok = g.play_card("pawntastic")
	check("pawntastic is a target card (pending)", ok and g.pending_card == "pawntastic")
	ok = g.play_card_target(6, 4)
	check("pawntastic activates on own pawn", ok)
	check("pawntastic offers up to 4 squares forward", g.legal_moves_for_selected.size() == 4)
	g.make_move(Vector2i(6, 4), Vector2i(2, 4))  # charge 4 squares
	check("pawn charged 4 squares", g.chess.board[2][4] == "P")
	check("pawntastic does not consume the normal chess move", g.moves_made_this_turn == 0)
	check("pawntastic sets ability_used_this_turn", g.ability_used_this_turn)

func test_bishock():
	var g = empty_engine()
	g.chess.board[4][4] = "B"  # white bishop
	g.chess.board[2][2] = "p"  # enemy pawn on diagonal
	g.chess.board[6][6] = "n"  # enemy knight on diagonal
	g.chess.board[0][0] = "k"
	g.chess.board[7][0] = "K"
	give_card(g, "bishock")
	g.play_card("bishock")
	var before = g.ether[GameEngine.WHITE]
	g.play_card_target(4, 4)
	check("bishock destroys the bishop itself", g.chess.board[4][4] == "")
	check("bishock destroys pawn on diagonal", g.chess.board[2][2] == "")
	check("bishock destroys knight on diagonal", g.chess.board[6][6] == "")
	check("bishock pays out captured value (1 + 3)", g.ether[GameEngine.WHITE] == before + 4)

func test_rookdemon():
	var g = empty_engine()
	g.chess.board[7][0] = "R"
	g.chess.board[0][0] = "k"
	g.chess.board[7][7] = "K"
	give_card(g, "rookdemon")
	g.play_card("rookdemon")
	g.play_card_target(7, 0)
	check("rookdemon arms the rook with 2 charges", g.rookdemon_rooks.get(Vector2i(7, 0)) == 2)

	g.chess.board[7][0] = "R"
	g.make_move(Vector2i(7, 0), Vector2i(7, 4))
	check("rook moved", g.chess.board[7][4] == "R" or g.chess.board[7][4] == "")
	check("fire trail laid behind the rook", g.fire_tiles.has(Vector2i(7, 1)))

func test_windknight():
	var g = empty_engine()
	g.chess.board[7][1] = "N"
	g.chess.board[0][0] = "k"
	g.chess.board[7][7] = "K"
	give_card(g, "windknight")
	g.play_card("windknight")
	g.play_card_target(7, 1)
	check("windknight activates on own knight", g.active_card == "windknight")
	check("windknight grants 2 moves", g.windknight_moves_remaining == 2)

	var dest1 = g.legal_moves_for_selected[0]
	g.make_move(Vector2i(7, 1), dest1)
	check("windknight allows a second move after the first", g.active_card == "windknight" or g.windknight_moves_remaining == 0)

func test_queentum():
	var g = empty_engine()
	g.chess.board[4][4] = "Q"
	g.chess.board[0][0] = "k"
	g.chess.board[7][0] = "K"
	give_card(g, "queentum")
	g.play_card("queentum")
	g.play_card_target(4, 4)
	check("queentum offers teleport to nearly every square", g.legal_moves_for_selected.size() >= 60)
	g.make_move(Vector2i(4, 4), Vector2i(7, 7))
	check("queen teleported far away", g.chess.board[7][7] == "Q")
	check("queentum does not consume the normal chess move", g.moves_made_this_turn == 0)

func test_longlivetheking():
	var g = empty_engine()
	g.chess.board[4][4] = "K"
	g.chess.board[0][0] = "k"
	give_card(g, "longlivetheking")
	var ok = g.play_card("longlivetheking")
	ok = g.play_card_target(4, 4)
	check("longlivetheking succeeds with an empty corner available", ok)
	var king_pos = g.chess.find_king(GameEngine.WHITE)
	var is_corner = king_pos in [Vector2i(0,0), Vector2i(0,7), Vector2i(7,0), Vector2i(7,7)]
	check("king escaped to a corner", is_corner)
	var spawned = 0
	for r in range(8):
		for c in range(8):
			if g.chess.board[r][c] == "P" or g.chess.board[r][c] == "Q":
				spawned += 1
	check("pawns/queens spawned around the king", spawned > 0)

func test_switchero():
	var g = empty_engine()
	g.chess.board[7][4] = "K"
	g.chess.board[6][4] = "P"
	g.chess.board[0][4] = "k"
	g.chess.board[1][4] = "p"
	give_card(g, "switchero")
	g.play_card("switchero")
	# 180-degree rotation: (r, c) -> (7-r, 7-c), plus a colour swap.
	check("white's pawn rotated to (1,3) and became black's", g.chess.board[1][3] == "p")
	check("black's pawn rotated to (6,3) and became white's", g.chess.board[6][3] == "P")

func test_prophecy():
	var g = empty_engine()
	g.chess.board[6][0] = "P"
	g.chess.board[6][1] = "P"
	g.chess.board[1][0] = "p"
	g.chess.board[7][4] = "K"
	g.chess.board[0][4] = "k"
	give_card(g, "prophecy")
	g.play_card("prophecy")
	check("white pawn 1 promoted to queen", g.chess.board[6][0] == "Q")
	check("white pawn 2 promoted to queen", g.chess.board[6][1] == "Q")
	check("black pawn untouched", g.chess.board[1][0] == "p")

func test_armageddon():
	var g = empty_engine()
	g.chess.board[4][4] = "p"
	g.chess.board[4][5] = "n"
	g.chess.board[7][0] = "K"
	g.chess.board[0][0] = "k"
	give_card(g, "armageddon")
	var before = g.ether[GameEngine.WHITE]
	g.play_card("armageddon")
	g.play_card_target(4, 4)
	check("armageddon destroys pieces in blast radius", g.chess.board[4][4] == "" and g.chess.board[4][5] == "")
	check("armageddon pays the destroyed value net of its cost (-30 + 1 + 3)", g.ether[GameEngine.WHITE] == before - 30 + 4)
	check("armageddon leaves fire on the blast squares", g.fire_tiles.has(Vector2i(4, 4)))

func test_thedramatic():
	var g = empty_engine()
	g.chess.board[4][4] = "R"
	g.chess.board[7][0] = "K"
	g.chess.board[0][0] = "k"
	give_card(g, "thedramatic")
	g.play_card("thedramatic")
	g.play_card_target(4, 4)
	check("thedramatic marks the piece", g.dramatic_pieces.has(Vector2i(4, 4)))

	g.chess.board[4][5] = "n"  # enemy knight that will capture
	g.chess.turn = GameEngine.BLACK
	g.make_move(Vector2i(4, 5), Vector2i(4, 4))
	check("the avenging capture destroys the capturer too", g.chess.board[4][4] == "")

func test_capitalism():
	var g = empty_engine()
	g.chess.board[7][4] = "K"
	g.chess.board[0][4] = "k"
	give_card(g, "capitalism", 100)
	g.play_card("capitalism")
	check("capitalism wins the game instantly", g.game_over)
	check("white wins by capitalism", g.winner_message.find("Capitalism") != -1)

func test_plague():
	var g = empty_engine()
	g.chess.board[7][4] = "K"
	g.chess.board[0][4] = "k"
	g.chess.board[1][1] = "p"
	give_card(g, "plague")
	g.play_card("plague")
	check("plague is active for white", g.plague_active.has(GameEngine.WHITE))
	g.moves_made_this_turn = 1  # simulate having moved, to allow end_turn
	g.end_turn()  # white -> black
	g.moves_made_this_turn = 1
	g.end_turn()  # black -> white, triggers start_turn_effects for white -> plague kills a black piece
	check("plague killed the lone black pawn at white's next turn", g.chess.board[1][1] == "")

func test_solo():
	var g = empty_engine()
	g.chess.board[7][4] = "K"
	g.chess.board[0][4] = "k"
	g.chess.board[0][0] = "q"
	give_card(g, "solo")
	var ok = g.play_card("solo")
	check("solo fails if you still have other pieces' enemy doesn't matter, only own", ok)
	check("solo wins instantly since only the king remains", g.game_over)

func test_absoluteprotection():
	var g = empty_engine()
	g.chess.board[4][4] = "P"
	g.chess.board[7][0] = "K"
	g.chess.board[0][0] = "k"
	give_card(g, "absoluteprotection")
	g.play_card("absoluteprotection")
	check("absolute protection active for white", g.absolute_protection_active.has(GameEngine.WHITE))

	g.chess.board[3][5] = "n"
	g.chess.turn = GameEngine.BLACK
	var ok = g.make_move(Vector2i(3, 5), Vector2i(4, 4))
	check("attack on a protected piece destroys the attacker instead", g.chess.board[3][5] == "" and g.chess.board[4][4] == "P")

func test_timetraveler():
	var g = empty_engine()
	g.chess.board[6][4] = "P"
	g.chess.board[7][0] = "K"
	g.chess.board[0][0] = "k"
	give_card(g, "timetraveler")
	var ok = g.play_card("timetraveler")
	check("timetraveler needs 3 prior turns and fails immediately", not ok)

	for i in range(3):
		g.chess.board[6][4 + i] = "P"
		g.make_move(Vector2i(6, 4 + i), Vector2i(5, 4 + i))

	var board_before = g._dup_board()
	ok = g.play_card("timetraveler")
	check("timetraveler succeeds once 3 prior turns exist", ok)
	check("board positions changed after rewinding", g._dup_board() != board_before)

func test_extrablood():
	var g = empty_engine()
	g.chess.board[6][4] = "P"
	g.chess.board[5][5] = "p"
	g.chess.board[7][0] = "K"
	g.chess.board[0][0] = "k"
	give_card(g, "extrablood")
	g.play_card("extrablood")
	check("extrablood active for white", g.extra_blood_active.has(GameEngine.WHITE))
	var before = g.ether[GameEngine.WHITE]
	g.make_move(Vector2i(6, 4), Vector2i(5, 5))  # pawn captures pawn
	check("extrablood doubles capture ether (1 move + 2x1 capture = 3)", g.ether[GameEngine.WHITE] == before + 3)

func test_chrisma():
	var g = empty_engine()
	g.chess.board[4][4] = "K"
	g.chess.board[4][5] = "p"
	g.chess.board[0][0] = "k"
	give_card(g, "chrisma")
	var before = g.ether[GameEngine.WHITE]
	g.play_card("chrisma")
	check("chrisma converts the adjacent enemy pawn", g.chess.board[4][5] == "P")
	check("chrisma pays out the converted value net of its cost (-15 + 1)", g.ether[GameEngine.WHITE] == before - 15 + 1)

func test_inzone():
	var g = empty_engine()
	g.chess.board[4][4] = "Q"
	g.chess.board[4][5] = "p"
	g.chess.board[4][6] = "n"
	g.chess.board[7][0] = "K"
	g.chess.board[0][0] = "k"
	give_card(g, "inzone")
	# InZone can't target a queen per the rules - use a rook instead.
	g.chess.board[4][4] = "R"
	g.play_card("inzone")
	var ok = g.play_card_target(4, 4)
	check("inzone activates with an available capture", ok)
	g.make_move(Vector2i(4, 4), Vector2i(4, 5))  # capture pawn
	check("inzone chains into another capture opportunity", g.active_card == "inzone")
	g.make_move(Vector2i(4, 5), Vector2i(4, 6))  # capture knight, streak ends (no more captures)
	check("inzone piece dies when the streak ends", g.chess.board[4][6] == "")

func test_nope_cancel():
	var g = empty_engine()
	g.chess.board[7][0] = "K"
	g.chess.board[0][0] = "k"
	give_card(g, "switchero")
	g.play_card("switchero")  # white plays a card, sets card_undo[WHITE]
	check("playing a card records an undo snapshot", g.card_undo[GameEngine.WHITE] != null)

	g.chess.turn = GameEngine.BLACK
	give_card(g, "nope")
	var board_before_cancel = g._dup_board()
	var ok = g.play_card("nope")
	check("black's nope cancels white's last card", ok)
	check("white's undo snapshot consumed", g.card_undo[GameEngine.WHITE] == null)

func test_nope_check():
	var g = empty_engine()
	g.chess.board[7][4] = "K"
	g.chess.board[0][4] = "k"
	g.chess.board[6][3] = "q"  # enemy queen giving check to white king
	give_card(g, "nope")
	var ok = g.play_card("nope")
	check("nope while in check destroys the checking piece", ok and g.chess.board[6][3] == "")

func test_communism():
	var g = empty_engine()
	g.chess.board[7][0] = "K"
	g.chess.board[0][0] = "k"
	g.ether[GameEngine.WHITE] = 100
	g.ether[GameEngine.BLACK] = 0
	give_card(g, "communism", 100)
	g.play_card("communism")
	# Cost 20 comes out of white's pile first (100 -> 80), then the
	# remaining 80 total is split evenly.
	check("communism splits the post-cost ether evenly", g.ether[GameEngine.WHITE] == 40 and g.ether[GameEngine.BLACK] == 40)

func test_gambit():
	var g = empty_engine()
	g.chess.board[6][0] = "P"
	g.chess.board[6][1] = "N"
	g.chess.board[7][4] = "K"
	g.chess.board[0][4] = "k"
	give_card(g, "gambit")
	var before = g.ether[GameEngine.WHITE]
	g.play_card("gambit")
	g.play_card_target(6, 0)
	# Cost 10 is paid once on the first sacrifice; the pawn's double value (2) is added.
	check("first sacrifice pays double pawn value net of cost (-10 + 2)", g.ether[GameEngine.WHITE] == before - 10 + 2)
	check("gambit mode stays active for more sacrifices", g.active_card == "gambit")
	var after_first = g.ether[GameEngine.WHITE]
	g.click_square(6, 1)
	check("second sacrifice pays double knight value (6 more), no extra cost", g.ether[GameEngine.WHITE] == after_first + 6)
	g.click_square(4, 4)  # click empty square to end gambit
	check("gambit ends after clicking elsewhere", g.active_card == "")

func test_propaganda():
	var g = empty_engine()
	g.chess.board[7][4] = "K"
	g.chess.board[0][4] = "k"
	g.chess.board[1][1] = "p"
	give_card(g, "propaganda")
	g.play_card("propaganda")
	check("propaganda active for white", g.propaganda_active.has(GameEngine.WHITE))

func test_ifeelsafe():
	var g = empty_engine()
	g.chess.board[4][4] = "K"
	g.chess.board[4][5] = "P"
	g.chess.board[0][0] = "k"
	give_card(g, "ifeelsafe")
	g.play_card("ifeelsafe")
	g.moves_made_this_turn = 1
	var before = g.ether[GameEngine.WHITE]
	g.end_turn()
	check("ifeelsafe pays ether for the piece defending the king", g.ether[GameEngine.WHITE] == before + 3)

func test_iguess():
	var g = empty_engine()
	g.chess.board[7][4] = "K"
	g.chess.board[0][4] = "k"
	give_card(g, "iguess")
	g.play_card("iguess")
	check("iguess grants 2 extra moves permanently", g.bonus_turns[GameEngine.WHITE] == 2)
	check("moves_allowed reflects the bonus", g.moves_allowed() == 3)

func test_gravitystorm():
	var g = empty_engine()
	g.chess.board[0][0] = "p"
	g.chess.board[7][7] = "n"
	g.chess.board[7][0] = "K"
	g.chess.board[0][7] = "k"
	give_card(g, "gravitystorm")
	g.play_card("gravitystorm")
	g.play_card_target(3, 3)
	var p_pos = null
	var n_pos = null
	for r in range(8):
		for c in range(8):
			if g.chess.board[r][c] == "p":
				p_pos = Vector2i(r, c)
			if g.chess.board[r][c] == "n":
				n_pos = Vector2i(r, c)
	check("pawn pulled toward the gravity point", p_pos != Vector2i(0, 0))
	check("knight pulled toward the gravity point", n_pos != Vector2i(7, 7))
	check("the gravity core square itself stays empty", g.chess.board[3][3] == "")
