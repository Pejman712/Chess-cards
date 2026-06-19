extends RefCounted
class_name NetSync

# Whole-state dump/restore for online play. Godot's StreamPeer Variant
# encoding handles Dictionary/Array/Vector2i/String/int/bool/null natively,
# so (unlike main.py's pickle-the-whole-__dict__ approach) we just need to
# list which GameEngine/ChessState fields matter - no custom (de)serializer
# per type is required.

static func serialize(engine: GameEngine) -> Dictionary:
	var chess = engine.chess
	return {
		"board": chess.board.duplicate(true),
		"turn": chess.turn,
		"white_king_moved": chess.white_king_moved,
		"black_king_moved": chess.black_king_moved,
		"white_left_rook_moved": chess.white_left_rook_moved,
		"white_right_rook_moved": chess.white_right_rook_moved,
		"black_left_rook_moved": chess.black_left_rook_moved,
		"black_right_rook_moved": chess.black_right_rook_moved,
		"en_passant_target": chess.en_passant_target,
		"game_over": chess.game_over,
		"winner_message": chess.winner_message,
		"status_message": chess.status_message,

		"ether": engine.ether.duplicate(true),
		"deck": {GameEngine.WHITE: engine.deck[GameEngine.WHITE].duplicate(), GameEngine.BLACK: engine.deck[GameEngine.BLACK].duplicate()},
		"hand": {GameEngine.WHITE: engine.hand[GameEngine.WHITE].duplicate(), GameEngine.BLACK: engine.hand[GameEngine.BLACK].duplicate()},
		"discard": {GameEngine.WHITE: engine.discard[GameEngine.WHITE].duplicate(), GameEngine.BLACK: engine.discard[GameEngine.BLACK].duplicate()},
		"discards_used": engine.discards_used.duplicate(true),
		"moves_made_this_turn": engine.moves_made_this_turn,
		"ability_used_this_turn": engine.ability_used_this_turn,

		"fire_tiles": engine.fire_tiles.duplicate(true),
		"rookdemon_rooks": engine.rookdemon_rooks.duplicate(true),
		"dramatic_pieces": engine.dramatic_pieces.duplicate(true),
		"plague_active": engine.plague_active.duplicate(true),
		"absolute_protection_active": engine.absolute_protection_active.duplicate(true),
		"extra_blood_active": engine.extra_blood_active.duplicate(true),
		"propaganda_active": engine.propaganda_active.duplicate(true),
		"ifeelsafe_active": engine.ifeelsafe_active.duplicate(true),
		"bonus_turns": engine.bonus_turns.duplicate(true),

		"card_undo": engine.card_undo.duplicate(true),
		"history": engine.history.duplicate(true),

		"game_over_engine": engine.game_over,
		"winner_message_engine": engine.winner_message,
		"status_message_engine": engine.status_message,
	}

static func apply(engine: GameEngine, d: Dictionary):
	var chess = engine.chess
	chess.board = d["board"].duplicate(true)
	chess.turn = d["turn"]
	chess.white_king_moved = d["white_king_moved"]
	chess.black_king_moved = d["black_king_moved"]
	chess.white_left_rook_moved = d["white_left_rook_moved"]
	chess.white_right_rook_moved = d["white_right_rook_moved"]
	chess.black_left_rook_moved = d["black_left_rook_moved"]
	chess.black_right_rook_moved = d["black_right_rook_moved"]
	chess.en_passant_target = d["en_passant_target"]
	chess.game_over = d["game_over"]
	chess.winner_message = d["winner_message"]
	chess.status_message = d["status_message"]

	engine.ether = d["ether"].duplicate(true)
	engine.deck = {GameEngine.WHITE: d["deck"][GameEngine.WHITE].duplicate(), GameEngine.BLACK: d["deck"][GameEngine.BLACK].duplicate()}
	engine.hand = {GameEngine.WHITE: d["hand"][GameEngine.WHITE].duplicate(), GameEngine.BLACK: d["hand"][GameEngine.BLACK].duplicate()}
	engine.discard = {GameEngine.WHITE: d["discard"][GameEngine.WHITE].duplicate(), GameEngine.BLACK: d["discard"][GameEngine.BLACK].duplicate()}
	engine.discards_used = d["discards_used"].duplicate(true)
	engine.moves_made_this_turn = d["moves_made_this_turn"]
	engine.ability_used_this_turn = d["ability_used_this_turn"]

	engine.fire_tiles = d["fire_tiles"].duplicate(true)
	engine.rookdemon_rooks = d["rookdemon_rooks"].duplicate(true)
	engine.dramatic_pieces = d["dramatic_pieces"].duplicate(true)
	engine.plague_active = d["plague_active"].duplicate(true)
	engine.absolute_protection_active = d["absolute_protection_active"].duplicate(true)
	engine.extra_blood_active = d["extra_blood_active"].duplicate(true)
	engine.propaganda_active = d["propaganda_active"].duplicate(true)
	engine.ifeelsafe_active = d["ifeelsafe_active"].duplicate(true)
	engine.bonus_turns = d["bonus_turns"].duplicate(true)

	engine.card_undo = d["card_undo"].duplicate(true)
	engine.history = d["history"].duplicate(true)

	engine.game_over = d["game_over_engine"]
	engine.winner_message = d["winner_message_engine"]
	engine.status_message = d["status_message_engine"]

	engine.active_card = ""
	engine.active_card_owner = ""
	engine.pending_card = ""
	engine.selected = null
	engine.legal_moves_for_selected = []
	engine.windknight_square = null
	engine.windknight_moves_remaining = 0
	engine.inzone_square = null
	engine.inzone_captures = 0
