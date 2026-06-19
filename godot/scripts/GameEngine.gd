extends RefCounted
class_name GameEngine

# Wraps ChessState with the Ether economy, the deck/hand/discard system, and
# all 24 card effects (ported from GameState in main.py).

const WHITE = ChessState.WHITE
const BLACK = ChessState.BLACK

const HAND_START = 5
const MAX_DISCARDS = 5
const MAX_HISTORY = 12

const ABILITY_CARDS = ["pawntastic", "queentum", "windknight", "inzone"]

const TARGET_CARDS = [
	"pawntastic", "bishock", "rookdemon", "windknight", "queentum", "longlivetheking",
	"armageddon", "thedramatic", "inzone", "gambit", "gravitystorm",
]
const INSTANT_CARDS = [
	"switchero", "prophecy", "capitalism", "plague", "solo", "absoluteprotection",
	"timetraveler", "extrablood", "chrisma", "nope", "communism", "propaganda",
	"ifeelsafe", "iguess",
]

const CARD_NAMES = [
	"pawntastic", "bishock", "rookdemon", "windknight", "queentum", "longlivetheking",
	"switchero", "prophecy", "armageddon", "thedramatic", "capitalism", "plague",
	"solo", "absoluteprotection", "timetraveler", "extrablood", "chrisma", "inzone",
	"nope", "communism", "gambit", "propaganda", "ifeelsafe", "iguess", "gravitystorm",
]

const CARD_COSTS = {
	"pawntastic": 1, "windknight": 3, "bishock": 3, "rookdemon": 5, "queentum": 9, "longlivetheking": 12,
	"switchero": 20, "prophecy": 40, "armageddon": 30, "thedramatic": 20, "capitalism": 100,
	"plague": 60, "solo": 20, "absoluteprotection": 20, "timetraveler": 20, "extrablood": 15,
	"chrisma": 15, "inzone": 30, "nope": 15, "communism": 20, "gambit": 10, "propaganda": 30,
	"ifeelsafe": 15, "iguess": 40, "gravitystorm": 30,
}

const PIECE_VALUES = ChessState.PIECE_VALUES

var chess: ChessState

var ether := {WHITE: 0, BLACK: 0}
var deck := {WHITE: [], BLACK: []}
var hand := {WHITE: [], BLACK: []}
var discard := {WHITE: [], BLACK: []}
var discards_used := {WHITE: 0, BLACK: 0}

var moves_made_this_turn := 0
var ability_used_this_turn := false

var active_card := ""
var active_card_owner := ""
var selected = null  # Vector2i or null
var legal_moves_for_selected: Array = []
var pending_card := ""  # card picked from hand, awaiting a board-square target

var windknight_square = null
var windknight_moves_remaining := 0
var inzone_square = null
var inzone_captures := 0

var fire_tiles := {}          # Vector2i -> int ttl
var rookdemon_rooks := {}     # Vector2i -> int charges remaining
var dramatic_pieces := {}     # Vector2i -> true
var plague_active := {}       # color -> true
var absolute_protection_active := {}
var extra_blood_active := {}
var propaganda_active := {}
var ifeelsafe_active := {}
var bonus_turns := {WHITE: 0, BLACK: 0}

var card_undo := {WHITE: null, BLACK: null}
var history: Array = []

var game_over := false
var winner_message := ""
var status_message := ""

func _init():
	chess = ChessState.new()
	deal_starting_hands()
	status_message = chess.status_message

# -----------------------------
# Deck / hand / discard
# -----------------------------
func deal_starting_hands():
	for color in [WHITE, BLACK]:
		deck[color] = CARD_NAMES.duplicate()
		deck[color].shuffle()
		hand[color] = []
		discard[color] = []
		draw_cards(color, HAND_START)

func draw_cards(color: String, n: int):
	for _i in range(n):
		if deck[color].is_empty():
			deck[color] = discard[color]
			discard[color] = []
			deck[color].shuffle()
		if deck[color].is_empty():
			break
		hand[color].append(deck[color].pop_back())

func spend_card(card_name: String) -> bool:
	var color = chess.turn
	if not hand[color].has(card_name):
		status_message = "%s is not in your hand." % card_name
		return false

	var cost = CARD_COSTS.get(card_name, 0)
	if ether[color] < cost:
		status_message = "Not enough Ether for %s. Need %d, have %d." % [card_name, cost, ether[color]]
		return false

	save_history()
	card_undo[color] = _dup_snapshot(history[-1])
	ether[color] -= cost
	hand[color].erase(card_name)
	discard[color].append(card_name)
	return true

func discard_card(card_name: String) -> bool:
	var color = chess.turn
	if not hand[color].has(card_name):
		status_message = "%s is not in your hand." % card_name
		return false
	if discards_used[color] >= MAX_DISCARDS:
		status_message = "No discards left (limit %d)." % MAX_DISCARDS
		return false

	hand[color].erase(card_name)
	discard[color].append(card_name)
	discards_used[color] += 1
	draw_cards(color, 1)

	var left = MAX_DISCARDS - discards_used[color]
	status_message = "Discarded %s. %d discard(s) left." % [card_name, left]
	return true

# -----------------------------
# Turn flow
# -----------------------------
func moves_allowed() -> int:
	return 1 + bonus_turns.get(chess.turn, 0)

func can_end_turn() -> bool:
	if game_over:
		return false
	if active_card in ABILITY_CARDS:
		return false
	if moves_made_this_turn >= 1 or ability_used_this_turn:
		return true
	return not chess.has_any_legal_moves(chess.turn)

func end_turn() -> bool:
	if not can_end_turn():
		status_message = "Move a piece before ending your turn."
		return false

	var mover = chess.turn
	award_check_bonus_for_player(mover)
	decay_fire_tiles()
	active_card = ""
	active_card_owner = ""
	_advance_turn()
	selected = null
	legal_moves_for_selected = []
	start_turn_effects()
	_sync_status()
	return true

func award_check_bonus_for_player(color: String) -> bool:
	var enemy = chess.enemy_color(color)
	if chess.is_in_check(enemy):
		ether[color] += 5
		return true
	return false

func _advance_turn():
	if ifeelsafe_active.has(chess.turn):
		var bonus = 3 * pieces_around_king(chess.turn)
		if bonus > 0:
			ether[chess.turn] += bonus

	chess.turn = chess.enemy_color(chess.turn)
	moves_made_this_turn = 0
	ability_used_this_turn = false

func start_turn_effects():
	var deficit = HAND_START - hand[chess.turn].size()
	if deficit > 0:
		draw_cards(chess.turn, deficit)

	if absolute_protection_active.has(chess.turn):
		absolute_protection_active.erase(chess.turn)

	if plague_active.has(chess.turn):
		var enemy = chess.enemy_color(chess.turn)
		var targets = []
		for r in range(8):
			for c in range(8):
				var piece = chess.board[r][c]
				if piece == "" or chess.piece_color(piece) != enemy:
					continue
				if piece.to_lower() == "k":
					continue
				if absolute_protection_active.has(enemy):
					continue
				targets.append(Vector2i(r, c))
		if not targets.is_empty():
			var sq = targets[randi() % targets.size()]
			var killed = chess.board[sq.x][sq.y]
			chess.board[sq.x][sq.y] = ""
			rookdemon_rooks.erase(sq)
			dramatic_pieces.erase(sq)
			if windknight_square == sq:
				windknight_square = null
				windknight_moves_remaining = 0
			status_message = "Plague killed %s's %s." % [enemy, killed.to_upper()]

	if propaganda_active.has(chess.turn) and randf() < 0.5:
		var enemy = chess.enemy_color(chess.turn)
		var targets = []
		for r in range(8):
			for c in range(8):
				var piece = chess.board[r][c]
				if piece != "" and chess.piece_color(piece) == enemy and piece.to_lower() != "k":
					targets.append(Vector2i(r, c))
		if not targets.is_empty():
			var sq = targets[randi() % targets.size()]
			var piece = chess.board[sq.x][sq.y]
			chess.board[sq.x][sq.y] = piece.to_upper() if chess.turn == WHITE else piece.to_lower()
			rookdemon_rooks.erase(sq)
			dramatic_pieces.erase(sq)
			status_message = "Propaganda converted %s's %s." % [enemy, piece.to_upper()]

func _sync_status():
	if chess.game_over and not game_over:
		game_over = true
		winner_message = chess.winner_message
	status_message = chess.status_message if not game_over else winner_message

func player_has_only_king(color: String) -> bool:
	var count = 0
	for r in range(8):
		for c in range(8):
			var piece = chess.board[r][c]
			if piece != "" and chess.piece_color(piece) == color:
				count += 1
				if piece.to_lower() != "k":
					return false
	return count == 1

func current_player_wins(reason: String):
	var winner = chess.turn
	game_over = true
	active_card = ""
	active_card_owner = ""
	selected = null
	legal_moves_for_selected = []
	winner_message = "%s wins by %s." % [winner.capitalize(), reason]
	status_message = winner_message

func find_checking_pieces(color: String) -> Array:
	var king = chess.find_king(color)
	if king == null:
		return []
	var enemy = chess.enemy_color(color)
	var attackers = []
	for r in range(8):
		for c in range(8):
			var piece = chess.board[r][c]
			if piece != "" and chess.piece_color(piece) == enemy:
				for m in chess.get_pseudo_legal_moves(r, c, false):
					if m == king:
						attackers.append(Vector2i(r, c))
						break
	return attackers

# -----------------------------
# Fire helpers
# -----------------------------
func add_fire_tiles(squares: Array):
	for sq in squares:
		var piece = chess.board[sq.x][sq.y]
		if piece != "" and piece.to_lower() == "k":
			continue
		fire_tiles[sq] = 4

func decay_fire_tiles():
	var expired = []
	for sq in fire_tiles.keys():
		fire_tiles[sq] -= 1
		if fire_tiles[sq] <= 0:
			expired.append(sq)
	for sq in expired:
		fire_tiles.erase(sq)

func apply_fire_damage_at(row: int, col: int):
	var sq = Vector2i(row, col)
	if not fire_tiles.has(sq):
		return
	var piece = chess.board[row][col]
	if piece == "" or piece.to_lower() == "k":
		return
	chess.board[row][col] = ""

# -----------------------------
# History / snapshots (Nope, TimeTraveler)
# -----------------------------
func _dup_board() -> Array:
	var b = []
	for row in chess.board:
		b.append(row.duplicate())
	return b

func _make_snapshot() -> Dictionary:
	return {
		"board": _dup_board(),
		"fire_tiles": fire_tiles.duplicate(true),
		"rookdemon_rooks": rookdemon_rooks.duplicate(true),
		"dramatic_pieces": dramatic_pieces.duplicate(true),
		"plague_active": plague_active.duplicate(true),
		"absolute_protection_active": absolute_protection_active.duplicate(true),
		"extra_blood_active": extra_blood_active.duplicate(true),
		"propaganda_active": propaganda_active.duplicate(true),
		"ifeelsafe_active": ifeelsafe_active.duplicate(true),
		"bonus_turns": bonus_turns.duplicate(true),
		"deck": {WHITE: deck[WHITE].duplicate(), BLACK: deck[BLACK].duplicate()},
		"hand": {WHITE: hand[WHITE].duplicate(), BLACK: hand[BLACK].duplicate()},
		"discard": {WHITE: discard[WHITE].duplicate(), BLACK: discard[BLACK].duplicate()},
		"discards_used": discards_used.duplicate(true),
		"ether": ether.duplicate(true),
		"turn": chess.turn,
		"white_king_moved": chess.white_king_moved,
		"black_king_moved": chess.black_king_moved,
		"white_left_rook_moved": chess.white_left_rook_moved,
		"white_right_rook_moved": chess.white_right_rook_moved,
		"black_left_rook_moved": chess.black_left_rook_moved,
		"black_right_rook_moved": chess.black_right_rook_moved,
		"en_passant_target": chess.en_passant_target,
	}

func _dup_snapshot(snap: Dictionary) -> Dictionary:
	return snap.duplicate(true)

func save_history():
	history.append(_make_snapshot())
	if history.size() > MAX_HISTORY:
		history.pop_front()

func restore_snapshot(snap: Dictionary, positions_only: bool = false, keep_turn: bool = false, keep_ether: bool = false):
	chess.board = []
	for row in snap["board"]:
		chess.board.append(row.duplicate())
	rookdemon_rooks = snap["rookdemon_rooks"].duplicate(true)
	dramatic_pieces = snap["dramatic_pieces"].duplicate(true)
	chess.white_king_moved = snap["white_king_moved"]
	chess.black_king_moved = snap["black_king_moved"]
	chess.white_left_rook_moved = snap["white_left_rook_moved"]
	chess.white_right_rook_moved = snap["white_right_rook_moved"]
	chess.black_left_rook_moved = snap["black_left_rook_moved"]
	chess.black_right_rook_moved = snap["black_right_rook_moved"]
	chess.en_passant_target = snap["en_passant_target"]

	if not positions_only:
		fire_tiles = snap["fire_tiles"].duplicate(true)
		plague_active = snap["plague_active"].duplicate(true)
		absolute_protection_active = snap["absolute_protection_active"].duplicate(true)
		extra_blood_active = snap["extra_blood_active"].duplicate(true)
		propaganda_active = snap["propaganda_active"].duplicate(true)
		ifeelsafe_active = snap["ifeelsafe_active"].duplicate(true)
		bonus_turns = snap["bonus_turns"].duplicate(true)
		deck = {WHITE: snap["deck"][WHITE].duplicate(), BLACK: snap["deck"][BLACK].duplicate()}
		hand = {WHITE: snap["hand"][WHITE].duplicate(), BLACK: snap["hand"][BLACK].duplicate()}
		discard = {WHITE: snap["discard"][WHITE].duplicate(), BLACK: snap["discard"][BLACK].duplicate()}
		discards_used = snap["discards_used"].duplicate(true)
		if not keep_ether:
			ether = snap["ether"].duplicate(true)
		if not keep_turn:
			chess.turn = snap["turn"]

	selected = null
	legal_moves_for_selected = []
	active_card = ""
	active_card_owner = ""
	windknight_square = null
	windknight_moves_remaining = 0
	inzone_square = null
	inzone_captures = 0

# -----------------------------
# Card finishing helpers
# -----------------------------
func finish_card(message: String):
	status_message = message.replace("{player}", chess.turn.capitalize())
	active_card = ""
	active_card_owner = ""
	pending_card = ""
	selected = null
	legal_moves_for_selected = []

func finish_ability_move():
	active_card = ""
	active_card_owner = ""
	windknight_square = null
	windknight_moves_remaining = 0
	inzone_square = null
	inzone_captures = 0
	selected = null
	legal_moves_for_selected = []
	ability_used_this_turn = true
	status_message = "%s used an ability." % chess.turn.capitalize()

func finish_chess_move():
	moves_made_this_turn += 1
	active_card = ""
	active_card_owner = ""
	windknight_square = null
	windknight_moves_remaining = 0
	inzone_square = null
	inzone_captures = 0
	selected = null
	legal_moves_for_selected = []
	status_message = "%s moved." % chess.turn.capitalize()

func _finish_move():
	if active_card in ABILITY_CARDS:
		finish_ability_move()
	else:
		finish_chess_move()

# -----------------------------
# The core move (chess move, piece-power continuation, or card-driven move)
# -----------------------------
func make_move(from_sq: Vector2i, to_sq: Vector2i) -> bool:
	if game_over:
		return false

	var piece = chess.board[from_sq.x][from_sq.y]
	if piece == "":
		return false

	var captured_piece_before = chess.board[to_sq.x][to_sq.y]
	if captured_piece_before != "" and captured_piece_before.to_lower() == "k":
		status_message = "The king cannot be captured."
		return false

	save_history()

	var color = chess.piece_color(piece)
	var piece_type = piece.to_lower()

	var captured_square_was_dramatic = captured_piece_before != "" and dramatic_pieces.has(to_sq)
	var target_is_absolute_protected = captured_piece_before != "" and absolute_protection_active.has(chess.piece_color(captured_piece_before))

	if target_is_absolute_protected:
		if piece_type == "k":
			return false
		chess.board[from_sq.x][from_sq.y] = ""
		rookdemon_rooks.erase(from_sq)
		dramatic_pieces.erase(from_sq)
		decay_fire_tiles()
		active_card = ""
		active_card_owner = ""
		_advance_turn()
		selected = null
		legal_moves_for_selected = []
		status_message = "AbsoluteProtection triggered: the attacker was destroyed."
		start_turn_effects()
		return true

	var was_windknight_move = active_card == "windknight" and windknight_square == from_sq and piece_type == "n"
	var was_inzone_move = active_card == "inzone" and inzone_square == from_sq

	var move_distance = chess.get_move_distance(piece, from_sq, to_sq)

	var ep_capture_sq = null
	if piece_type == "p" and chess.en_passant_target != null and chess.en_passant_target == to_sq and captured_piece_before == "":
		ep_capture_sq = Vector2i(from_sq.x, to_sq.y)
		if dramatic_pieces.has(ep_capture_sq):
			captured_square_was_dramatic = true
			dramatic_pieces.erase(ep_capture_sq)

	var moving_piece_was_dramatic = dramatic_pieces.has(from_sq)
	dramatic_pieces.erase(from_sq)

	var rook_fire_path = []
	var rook_has_charge = piece_type == "r" and rookdemon_rooks.has(from_sq)
	var rook_remaining_after = -1
	if rook_has_charge:
		rook_fire_path = CardHelpers.rookdemon_path(from_sq, to_sq)
		rook_remaining_after = rookdemon_rooks[from_sq] - 1

	var is_castle = piece_type == "k" and abs(to_sq.y - from_sq.y) == 2

	var result = chess.make_move(from_sq, to_sq)
	var capture_ether = chess.get_piece_value(result.get("captured", ""))

	if rook_has_charge:
		rookdemon_rooks.erase(from_sq)
		add_fire_tiles(rook_fire_path)
		if rook_remaining_after > 0:
			rookdemon_rooks[to_sq] = rook_remaining_after

	if is_castle:
		var row = from_sq.x
		if to_sq.y == 6 and rookdemon_rooks.has(Vector2i(row, 7)):
			rookdemon_rooks[Vector2i(row, 5)] = rookdemon_rooks[Vector2i(row, 7)]
			rookdemon_rooks.erase(Vector2i(row, 7))
		elif to_sq.y == 2 and rookdemon_rooks.has(Vector2i(row, 0)):
			rookdemon_rooks[Vector2i(row, 3)] = rookdemon_rooks[Vector2i(row, 0)]
			rookdemon_rooks.erase(Vector2i(row, 0))

	if captured_piece_before != "" or ep_capture_sq != null:
		dramatic_pieces.erase(to_sq)
		rookdemon_rooks.erase(to_sq)
		if windknight_square == to_sq:
			windknight_square = null
			windknight_moves_remaining = 0

	if moving_piece_was_dramatic and chess.board[to_sq.x][to_sq.y] != "":
		dramatic_pieces[to_sq] = true

	if capture_ether > 0 and extra_blood_active.has(color):
		capture_ether *= 2

	var total_gained = move_distance + capture_ether
	if total_gained > 0:
		ether[color] += total_gained
		status_message = "%s gained %d Ether (%d move + %d capture)." % [color.capitalize(), total_gained, move_distance, capture_ether]
	else:
		status_message = chess.status_message

	apply_fire_damage_at(to_sq.x, to_sq.y)

	var moved_piece_survived = chess.board[to_sq.x][to_sq.y] != ""

	if captured_square_was_dramatic and moved_piece_survived:
		if chess.board[to_sq.x][to_sq.y].to_lower() != "k":
			chess.board[to_sq.x][to_sq.y] = ""
			rookdemon_rooks.erase(to_sq)
			dramatic_pieces.erase(to_sq)
			moved_piece_survived = false
			status_message = "TheDramatic triggered: the capturing piece was destroyed."

	if not moved_piece_survived:
		rookdemon_rooks.erase(to_sq)
		if windknight_square == to_sq:
			windknight_square = null
			windknight_moves_remaining = 0

	if was_inzone_move:
		if moved_piece_survived and capture_ether > 0:
			inzone_captures += 1
			inzone_square = to_sq
			selected = to_sq
			legal_moves_for_selected = chess.get_capture_moves_only(to_sq.x, to_sq.y)
			var check_on_board = chess.is_in_check(WHITE) or chess.is_in_check(BLACK)
			if not legal_moves_for_selected.is_empty() and inzone_captures < 5 and not check_on_board:
				status_message = "InZone: keep capturing with the same piece."
				return true

		if moved_piece_survived:
			chess.board[to_sq.x][to_sq.y] = ""
			rookdemon_rooks.erase(to_sq)
			dramatic_pieces.erase(to_sq)

		_finish_move()
		return true

	if was_windknight_move and moved_piece_survived:
		windknight_moves_remaining -= 1
		if windknight_moves_remaining > 0:
			windknight_square = to_sq
			selected = to_sq
			legal_moves_for_selected = chess.get_legal_moves(to_sq.x, to_sq.y)
			if not legal_moves_for_selected.is_empty():
				status_message = "Windknight: move the same knight one more time."
				return true
		_finish_move()
		return true

	_finish_move()
	_sync_status()
	return true

# Entry point used by the UI for a drag/drop board move. Honors active-card
# move restrictions (Pawntastic/Queentum override legal moves; Windknight/
# InZone restrict to the active piece) the same way main.py's select_square
# gates make_move calls.
func try_move(from_sq: Vector2i, to_sq: Vector2i) -> bool:
	if game_over:
		return false

	if active_card == "windknight" or active_card == "inzone":
		if selected != from_sq or not legal_moves_for_selected.has(to_sq):
			return false
		return make_move(from_sq, to_sq)

	if active_card == "gambit":
		return false  # gambit uses click_square, not drag

	if active_card == "" and moves_made_this_turn >= moves_allowed():
		status_message = "No moves left this turn. Press END TURN."
		return false

	var legal = get_current_legal_moves(from_sq.x, from_sq.y)
	if not legal.has(to_sq):
		return false

	return make_move(from_sq, to_sq)

# What a click/drag-pickup on this square should highlight right now,
# accounting for an active card's custom move set.
func get_current_legal_moves(row: int, col: int) -> Array:
	if active_card == "pawntastic" and selected == Vector2i(row, col):
		return chess.legal_filter(row, col, CardHelpers.pawntastic_moves(chess, row, col))
	if active_card == "queentum" and selected == Vector2i(row, col):
		return chess.legal_filter(row, col, CardHelpers.queentum_moves(chess, row, col))
	return chess.get_legal_moves(row, col)

# -----------------------------
# Card dispatch
# -----------------------------
func play_card(card_name: String) -> bool:
	if game_over:
		return false
	if card_name in TARGET_CARDS:
		pending_card = card_name
		return true
	return _activate_instant(card_name)

func play_card_target(row: int, col: int) -> bool:
	if pending_card == "":
		return false
	var card_name = pending_card
	var ok = _activate_target(card_name, row, col)
	return ok

func cancel_pending_card():
	pending_card = ""

func _activate_instant(card_name: String) -> bool:
	match card_name:
		"switchero": return activate_switchero()
		"prophecy": return activate_prophecy()
		"capitalism": return activate_capitalism()
		"plague": return activate_plague()
		"solo": return activate_solo()
		"absoluteprotection": return activate_absoluteprotection()
		"timetraveler": return activate_timetraveler()
		"extrablood": return activate_extrablood()
		"chrisma": return activate_chrisma()
		"nope": return activate_nope()
		"communism": return activate_communism()
		"propaganda": return activate_propaganda()
		"ifeelsafe": return activate_ifeelsafe()
		"iguess": return activate_iguess()
	return false

func _activate_target(card_name: String, row: int, col: int) -> bool:
	match card_name:
		"pawntastic": return activate_pawntastic_on_square(row, col)
		"bishock": return activate_bishock_on_square(row, col)
		"rookdemon": return activate_rookdemon_on_square(row, col)
		"windknight": return activate_windknight_on_square(row, col)
		"queentum": return activate_queentum_on_square(row, col)
		"longlivetheking": return activate_longlivetheking_on_square(row, col)
		"armageddon": return activate_armageddon_on_square(row, col)
		"thedramatic": return activate_thedramatic_on_square(row, col)
		"inzone": return activate_inzone_on_square(row, col)
		"gambit": return activate_gambit_on_square(row, col)
		"gravitystorm": return activate_gravitystorm_on_square(row, col)
	return false

# -----------------------------
# Piece-power cards
# -----------------------------
func activate_pawntastic_on_square(row: int, col: int) -> bool:
	if game_over:
		return false
	var piece = chess.board[row][col]
	if piece == "" or chess.piece_color(piece) != chess.turn:
		status_message = "Drop Pawntastic on one of your pawns."
		return false
	if piece.to_lower() != "p":
		status_message = "Pawntastic only works on pawns."
		return false

	var moves = chess.legal_filter(row, col, CardHelpers.pawntastic_moves(chess, row, col))
	if moves.is_empty():
		status_message = "That pawn has no Pawntastic moves."
		return false

	if not spend_card("pawntastic"):
		return false

	active_card = "pawntastic"
	active_card_owner = chess.turn
	selected = Vector2i(row, col)
	legal_moves_for_selected = moves
	pending_card = ""
	status_message = "%s used Pawntastic. Choose the pawn's move." % chess.turn.capitalize()
	return true

func activate_bishock_on_square(row: int, col: int) -> bool:
	if game_over:
		return false
	var piece = chess.board[row][col]
	if piece == "" or chess.piece_color(piece) != chess.turn:
		status_message = "Drop Bishock on one of your bishops."
		return false
	if piece.to_lower() != "b":
		status_message = "Bishock only works on bishops."
		return false

	var destroyed = CardHelpers.bishock_destroyed_squares(chess, row, col)
	if destroyed.is_empty():
		status_message = "Bishock found nothing to destroy."
		return false

	if not spend_card("bishock"):
		return false

	var ether_gained = 0
	for sq in destroyed:
		var target_piece = chess.board[sq.x][sq.y]
		if target_piece != "" and target_piece.to_lower() == "k":
			continue
		if target_piece != "":
			ether_gained += chess.get_piece_value(target_piece)
		chess.board[sq.x][sq.y] = ""
		fire_tiles.erase(sq)
		rookdemon_rooks.erase(sq)
		if windknight_square == sq:
			windknight_square = null
			windknight_moves_remaining = 0

	ether[chess.turn] += ether_gained
	finish_card("{player} used Bishock and gained %d Ether." % ether_gained)
	return true

func activate_rookdemon_on_square(row: int, col: int) -> bool:
	if game_over:
		return false
	var piece = chess.board[row][col]
	if piece == "" or chess.piece_color(piece) != chess.turn:
		status_message = "Drop Rookdemon on one of your rooks."
		return false
	if piece.to_lower() != "r":
		status_message = "Rookdemon only works on rooks."
		return false

	if not spend_card("rookdemon"):
		return false

	rookdemon_rooks[Vector2i(row, col)] = 2
	finish_card("{player} empowered a rook with Rookdemon.")
	return true

func activate_windknight_on_square(row: int, col: int) -> bool:
	if game_over:
		return false
	if not CardHelpers.is_valid_windknight_target(chess, row, col, chess.turn):
		status_message = "Drop Windknight on one of your knights."
		return false

	var moves = chess.get_legal_moves(row, col)
	if moves.is_empty():
		status_message = "That knight has no legal Windknight move."
		return false

	if not spend_card("windknight"):
		return false

	active_card = "windknight"
	active_card_owner = chess.turn
	windknight_square = Vector2i(row, col)
	windknight_moves_remaining = 2
	selected = Vector2i(row, col)
	legal_moves_for_selected = moves
	pending_card = ""
	status_message = "%s used Windknight. Move the knight twice." % chess.turn.capitalize()
	return true

func activate_queentum_on_square(row: int, col: int) -> bool:
	if game_over:
		return false
	var piece = chess.board[row][col]
	if piece == "" or chess.piece_color(piece) != chess.turn:
		status_message = "Drop Queentum on one of your queens."
		return false
	if piece.to_lower() != "q":
		status_message = "Queentum only works on queens."
		return false

	var moves = chess.legal_filter(row, col, CardHelpers.queentum_moves(chess, row, col))
	if moves.is_empty():
		status_message = "That queen has no legal Queentum teleport."
		return false

	if not spend_card("queentum"):
		return false

	active_card = "queentum"
	active_card_owner = chess.turn
	selected = Vector2i(row, col)
	legal_moves_for_selected = moves
	pending_card = ""
	status_message = "%s used Queentum. Choose any legal teleport square." % chess.turn.capitalize()
	return true

func can_use_longlivetheking(color: String = "") -> bool:
	if color == "":
		color = chess.turn
	if not hand[color].has("longlivetheking"):
		return false
	if ether[color] < CARD_COSTS.get("longlivetheking", 0):
		return false
	if CardHelpers.get_empty_escape_corners(chess).is_empty():
		return false
	var king_pos = chess.find_king(color)
	if king_pos == null:
		return false
	return not safe_escape_corners(king_pos.x, king_pos.y, color).is_empty()

func _apply_longlivetheking(board: Array, from_square: Vector2i, to_square: Vector2i, color: String) -> int:
	var pawn_piece = "P" if color == WHITE else "p"
	var queen_piece = "Q" if color == WHITE else "q"
	var promotion_row = 0 if color == WHITE else 7

	var king_piece = board[from_square.x][from_square.y]
	board[to_square.x][to_square.y] = king_piece
	board[from_square.x][from_square.y] = ""

	var spawned = 0
	for dr in [-1, 0, 1]:
		for dc in [-1, 0, 1]:
			if dr == 0 and dc == 0:
				continue
			var nr = to_square.x + dr
			var nc = to_square.y + dc
			if chess.in_bounds(nr, nc) and board[nr][nc] == "":
				board[nr][nc] = queen_piece if nr == promotion_row else pawn_piece
				spawned += 1
	return spawned

func safe_escape_corners(king_row: int, king_col: int, color: String) -> Array:
	var safe = []
	for corner in CardHelpers.get_empty_escape_corners(chess):
		var test_board = []
		for row in chess.board:
			test_board.append(row.duplicate())
		_apply_longlivetheking(test_board, Vector2i(king_row, king_col), corner, color)

		var probe = chess.clone()
		probe.board = test_board
		if not probe.is_in_check(color):
			safe.append(corner)
	return safe

func activate_longlivetheking_on_square(row: int, col: int) -> bool:
	if game_over:
		if not can_use_longlivetheking(chess.turn):
			return false
		game_over = false

	var piece = chess.board[row][col]
	if piece == "" or chess.piece_color(piece) != chess.turn:
		status_message = "Drop LongLiveTheKing on your king."
		return false
	if piece.to_lower() != "k":
		status_message = "LongLiveTheKing only works on kings."
		return false

	if CardHelpers.get_empty_escape_corners(chess).is_empty():
		status_message = "LongLiveTheKing failed: no empty corner exists."
		return false

	var safe_corners = safe_escape_corners(row, col, chess.turn)
	if safe_corners.is_empty():
		status_message = "LongLiveTheKing failed: every corner would leave the king in check."
		return false

	var escape_corner = safe_corners[randi() % safe_corners.size()]

	if not spend_card("longlivetheking"):
		return false

	if chess.turn == WHITE:
		chess.white_king_moved = true
	else:
		chess.black_king_moved = true

	var spawned = _apply_longlivetheking(chess.board, Vector2i(row, col), escape_corner, chess.turn)
	finish_card("{player} escaped to a safe corner and spawned %d pawn(s)." % spawned)
	return true

# -----------------------------
# Game cards
# -----------------------------
func activate_switchero() -> bool:
	if game_over:
		return false
	if not spend_card("switchero"):
		return false

	var rot = func(sq: Vector2i): return Vector2i(7 - sq.x, 7 - sq.y)

	var new_board = []
	for _r in range(8):
		new_board.append(["", "", "", "", "", "", "", ""])

	for row in range(8):
		for col in range(8):
			var piece = chess.board[row][col]
			if piece != "":
				var n = rot.call(Vector2i(row, col))
				new_board[n.x][n.y] = piece.to_lower() if piece == piece.to_upper() else piece.to_upper()
	chess.board = new_board

	var new_rookdemon = {}
	for sq in rookdemon_rooks:
		new_rookdemon[rot.call(sq)] = rookdemon_rooks[sq]
	rookdemon_rooks = new_rookdemon

	var new_fire = {}
	for sq in fire_tiles:
		new_fire[rot.call(sq)] = fire_tiles[sq]
	fire_tiles = new_fire

	var new_dramatic = {}
	for sq in dramatic_pieces:
		new_dramatic[rot.call(sq)] = true
	dramatic_pieces = new_dramatic

	if windknight_square != null:
		windknight_square = rot.call(windknight_square)
	if inzone_square != null:
		inzone_square = rot.call(inzone_square)

	for col in range(8):
		if chess.board[0][col] == "P":
			chess.board[0][col] = "Q"
		if chess.board[7][col] == "p":
			chess.board[7][col] = "q"

	chess.white_king_moved = true
	chess.black_king_moved = true
	chess.white_left_rook_moved = true
	chess.white_right_rook_moved = true
	chess.black_left_rook_moved = true
	chess.black_right_rook_moved = true
	chess.en_passant_target = null

	finish_card("{player} seized the enemy army with Switchero.")
	return true

func activate_prophecy() -> bool:
	if game_over:
		return false
	if not spend_card("prophecy"):
		return false

	var changed = 0
	var pawn_piece = "P" if chess.turn == WHITE else "p"
	var queen_piece = "Q" if chess.turn == WHITE else "q"

	for row in range(8):
		for col in range(8):
			if chess.board[row][col] == pawn_piece:
				chess.board[row][col] = queen_piece
				changed += 1

	finish_card("{player} played The Prophecy. %d own pawn(s) became queen(s)." % changed)
	return true

func activate_armageddon_on_square(row: int, col: int) -> bool:
	if game_over:
		return false
	if not spend_card("armageddon"):
		return false

	var destroyed_value = 0
	var destroyed_count = 0
	var fire_squares = []

	for dr in [-1, 0, 1]:
		for dc in [-1, 0, 1]:
			var nr = row + dr
			var nc = col + dc
			if not chess.in_bounds(nr, nc):
				continue
			var target_piece = chess.board[nr][nc]
			if target_piece != "" and target_piece.to_lower() == "k":
				continue
			if target_piece != "":
				destroyed_value += chess.get_piece_value(target_piece)
				destroyed_count += 1
				chess.board[nr][nc] = ""
				rookdemon_rooks.erase(Vector2i(nr, nc))
				dramatic_pieces.erase(Vector2i(nr, nc))
				if windknight_square == Vector2i(nr, nc):
					windknight_square = null
					windknight_moves_remaining = 0
			fire_squares.append(Vector2i(nr, nc))

	ether[chess.turn] += destroyed_value
	add_fire_tiles(fire_squares)
	finish_card("{player} played Armageddon. Destroyed %d piece(s) and created fire." % destroyed_count)
	return true

func activate_gravitystorm_on_square(row: int, col: int) -> bool:
	if game_over:
		return false
	var core_piece = chess.board[row][col]
	if core_piece != "" and core_piece.to_lower() == "k":
		status_message = "Gravity Storm cannot be aimed at a king."
		return false

	if not spend_card("gravitystorm"):
		return false

	var target = Vector2i(row, col)
	var crushed = 0

	if core_piece != "":
		chess.board[row][col] = ""
		rookdemon_rooks.erase(target)
		dramatic_pieces.erase(target)
		if windknight_square == target:
			windknight_square = null
			windknight_moves_remaining = 0
		if inzone_square == target:
			inzone_square = null
		crushed = 1

	var movers = []
	for r in range(8):
		for c in range(8):
			if chess.board[r][c] != "":
				movers.append(Vector2i(r, c))
	movers.sort_custom(func(a, b):
		return (a.x - row) ** 2 + (a.y - col) ** 2 < (b.x - row) ** 2 + (b.y - col) ** 2
	)

	var moved = 0
	for from_sq in movers:
		var piece = chess.board[from_sq.x][from_sq.y]
		var cr = from_sq.x
		var cc = from_sq.y
		while true:
			var dr = signi(row - cr)
			var dc = signi(col - cc)
			var nr = cr + dr
			var nc = cc + dc
			if nr == target.x and nc == target.y:
				break
			if not chess.in_bounds(nr, nc) or chess.board[nr][nc] != "":
				break
			cr = nr
			cc = nc

		if cr == from_sq.x and cc == from_sq.y:
			continue

		var to_sq = Vector2i(cr, cc)
		chess.board[to_sq.x][to_sq.y] = piece
		chess.board[from_sq.x][from_sq.y] = ""
		if rookdemon_rooks.has(from_sq):
			rookdemon_rooks[to_sq] = rookdemon_rooks[from_sq]
			rookdemon_rooks.erase(from_sq)
		if dramatic_pieces.has(from_sq):
			dramatic_pieces.erase(from_sq)
			dramatic_pieces[to_sq] = true
		if windknight_square == from_sq:
			windknight_square = to_sq
		if inzone_square == from_sq:
			inzone_square = to_sq
		moved += 1

	var note = "%d piece(s) pulled inward" % moved
	if crushed:
		note += " and 1 crushed on the core"
	finish_card("{player} unleashed Gravity Storm. %s." % note)
	return true

func activate_thedramatic_on_square(row: int, col: int) -> bool:
	if game_over:
		return false
	if not spend_card("thedramatic"):
		return false

	var piece = chess.board[row][col]
	if piece == "":
		ether[chess.turn] += CARD_COSTS["thedramatic"]
		status_message = "Drop TheDramatic on one of your pieces."
		return false
	if chess.piece_color(piece) != chess.turn:
		ether[chess.turn] += CARD_COSTS["thedramatic"]
		status_message = "You can only use TheDramatic on your own piece."
		return false
	if piece.to_lower() == "k":
		ether[chess.turn] += CARD_COSTS["thedramatic"]
		status_message = "TheDramatic cannot be used on kings."
		return false

	dramatic_pieces[Vector2i(row, col)] = true
	finish_card("{player} played TheDramatic. The marked piece will avenge itself if captured.")
	return true

func activate_capitalism() -> bool:
	if game_over:
		return false
	if not spend_card("capitalism"):
		return false
	current_player_wins("Capitalism")
	return true

func activate_plague() -> bool:
	if game_over:
		return false
	if not spend_card("plague"):
		return false
	plague_active[chess.turn] = true
	finish_card("{player} unleashed Plague. At the start of their turns, one enemy piece dies.")
	return true

func activate_solo() -> bool:
	if game_over:
		return false
	if not player_has_only_king(chess.turn):
		status_message = "Solo only works if you have only your king left."
		return false
	if not spend_card("solo"):
		return false
	current_player_wins("Solo")
	return true

func activate_absoluteprotection() -> bool:
	if game_over:
		return false
	if not spend_card("absoluteprotection"):
		return false
	absolute_protection_active[chess.turn] = true
	finish_card("{player} activated AbsoluteProtection for one opponent turn.")
	return true

func activate_timetraveler() -> bool:
	if game_over:
		return false
	if history.size() < 3:
		status_message = "TimeTraveler needs at least 3 previous turns."
		return false
	if not spend_card("timetraveler"):
		return false

	var snapshot = _dup_snapshot(history[history.size() - 4])
	restore_snapshot(snapshot, true)
	history = history.slice(0, history.size() - 4)
	finish_card("{player} rewound the pieces 3 turns. Ether and powers are kept.")
	return true

func activate_extrablood() -> bool:
	if game_over:
		return false
	if extra_blood_active.has(chess.turn):
		status_message = "ExtraBlood is already active for you."
		return false
	if not spend_card("extrablood"):
		return false
	extra_blood_active[chess.turn] = true
	finish_card("{player} activated ExtraBlood. Capture Ether is now doubled.")
	return true

func activate_chrisma() -> bool:
	if game_over:
		return false
	var king_pos = chess.find_king(chess.turn)
	if king_pos == null:
		status_message = "Chrisma failed: no king found."
		return false
	if not spend_card("chrisma"):
		return false

	var converted = 0
	var gained = 0
	for dr in [-1, 0, 1]:
		for dc in [-1, 0, 1]:
			if dr == 0 and dc == 0:
				continue
			var nr = king_pos.x + dr
			var nc = king_pos.y + dc
			if not chess.in_bounds(nr, nc):
				continue
			var piece = chess.board[nr][nc]
			if piece == "" or chess.piece_color(piece) == chess.turn or piece.to_lower() == "k":
				continue
			gained += chess.get_piece_value(piece)
			chess.board[nr][nc] = piece.to_upper() if chess.turn == WHITE else piece.to_lower()
			converted += 1

	ether[chess.turn] += gained
	finish_card("{player} used Chrisma. Converted %d piece(s) and gained %d Ether." % [converted, gained])
	return true

func activate_inzone_on_square(row: int, col: int) -> bool:
	if game_over:
		return false
	var piece = chess.board[row][col]
	if piece == "":
		status_message = "Drop InZone on one of your pieces."
		return false
	if chess.piece_color(piece) != chess.turn:
		status_message = "You can only use InZone on your own piece."
		return false
	if piece.to_lower() == "k":
		status_message = "InZone cannot be used on kings."
		return false
	if piece.to_lower() == "q":
		status_message = "InZone cannot be used on the queen."
		return false

	var capture_moves = chess.get_capture_moves_only(row, col)
	if capture_moves.is_empty():
		status_message = "That piece has no captures for InZone."
		return false

	if not spend_card("inzone"):
		return false

	active_card = "inzone"
	active_card_owner = chess.turn
	inzone_square = Vector2i(row, col)
	inzone_captures = 0
	selected = Vector2i(row, col)
	legal_moves_for_selected = capture_moves
	pending_card = ""
	status_message = "InZone active: capture repeatedly with this piece. It dies when the streak ends."
	return true

func activate_nope() -> bool:
	if game_over:
		return false
	var opp = chess.enemy_color(chess.turn)
	var in_check = chess.is_in_check(chess.turn)

	if card_undo.get(opp) == null and not in_check:
		status_message = "Nope has nothing to cancel."
		return false

	if not spend_card("nope"):
		return false

	var notes = []
	if in_check:
		var killed = 0
		for sq in find_checking_pieces(chess.turn):
			var piece = chess.board[sq.x][sq.y]
			if piece != "" and piece.to_lower() != "k":
				chess.board[sq.x][sq.y] = ""
				rookdemon_rooks.erase(sq)
				dramatic_pieces.erase(sq)
				killed += 1
		if killed > 0:
			notes.append("destroyed the checking piece")
	elif card_undo.get(opp) != null:
		restore_snapshot(card_undo[opp], false, true, true)
		card_undo[opp] = null
		notes.append("cancelled the opponent's last card")

	var summary = " and ".join(notes) if not notes.is_empty() else "fizzled"
	finish_card("{player} played Nope: %s." % summary)
	return true

func activate_communism() -> bool:
	if game_over:
		return false
	if not spend_card("communism"):
		return false

	var total = ether[WHITE] + ether[BLACK]
	var half = total / 2
	ether[chess.enemy_color(chess.turn)] = half
	ether[chess.turn] = total - half
	finish_card("{player} played Communism. Ether is now shared equally.")
	return true

func gambit_can_sacrifice(row: int, col: int) -> bool:
	var piece = chess.board[row][col]
	if piece == "":
		status_message = "Drop Gambit on one of your pieces."
		return false
	if chess.piece_color(piece) != chess.turn:
		status_message = "You can only sacrifice your own piece."
		return false
	if piece.to_lower() == "k":
		status_message = "Gambit cannot sacrifice the king."
		return false
	return true

func gambit_sacrifice(row: int, col: int):
	var piece = chess.board[row][col]
	var value = chess.get_piece_value(piece) * 2
	chess.board[row][col] = ""
	rookdemon_rooks.erase(Vector2i(row, col))
	dramatic_pieces.erase(Vector2i(row, col))
	if windknight_square == Vector2i(row, col):
		windknight_square = null
		windknight_moves_remaining = 0

	ether[chess.turn] += value
	status_message = "Gambit: +%d Ether. Click more pieces to sacrifice, or click elsewhere to finish." % value

func gambit_finish():
	active_card = ""
	active_card_owner = ""
	selected = null
	legal_moves_for_selected = []

func activate_gambit_on_square(row: int, col: int) -> bool:
	if game_over:
		return false
	if not gambit_can_sacrifice(row, col):
		return false
	if not spend_card("gambit"):
		return false

	active_card = "gambit"
	active_card_owner = chess.turn
	pending_card = ""
	gambit_sacrifice(row, col)
	return true

# Click while Gambit is active: sacrifice another own piece, or finish.
func click_square(row: int, col: int):
	if active_card == "gambit":
		var clicked_piece = chess.board[row][col]
		if clicked_piece != "" and chess.piece_color(clicked_piece) == chess.turn and clicked_piece.to_lower() != "k":
			gambit_sacrifice(row, col)
		else:
			gambit_finish()

func activate_propaganda() -> bool:
	if game_over:
		return false
	if propaganda_active.has(chess.turn):
		status_message = "Propaganda is already active for you."
		return false
	if not spend_card("propaganda"):
		return false
	propaganda_active[chess.turn] = true
	finish_card("{player} spread Propaganda. Each turn may convert an enemy piece.")
	return true

func activate_ifeelsafe() -> bool:
	if game_over:
		return false
	if ifeelsafe_active.has(chess.turn):
		status_message = "I Feel Safe is already active for you."
		return false
	if not spend_card("ifeelsafe"):
		return false
	ifeelsafe_active[chess.turn] = true
	finish_card("{player} feels safe. End of turn: +3 Ether per piece by the king.")
	return true

func activate_iguess() -> bool:
	if game_over:
		return false
	if not spend_card("iguess"):
		return false
	bonus_turns[chess.turn] += 2
	finish_card("{player} played I Guess. They now take 2 extra moves every turn.")
	return true

func pieces_around_king(color: String) -> int:
	var king = chess.find_king(color)
	if king == null:
		return 0
	var count = 0
	for dr in [-1, 0, 1]:
		for dc in [-1, 0, 1]:
			if dr == 0 and dc == 0:
				continue
			var nr = king.x + dr
			var nc = king.y + dc
			if chess.in_bounds(nr, nc) and chess.is_friend(nr, nc, color):
				count += 1
	return count
