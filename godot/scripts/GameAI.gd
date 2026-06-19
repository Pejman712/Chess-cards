extends RefCounted
class_name GameAI

# Computer opponent for Player-vs-Computer mode (ported from main.py's
# ai_update()/_apply_ai_move()/_fallback_move()). Cards stay human-only -
# the AI only ever plays plain chess moves.

var stockfish: StockfishEngine = null
var difficulty := "Medium"

func _init(diff: String = "Medium"):
	difficulty = diff
	var sf = StockfishEngine.new()
	if sf.available:
		sf.configure(difficulty)
		stockfish = sf

func has_engine() -> bool:
	return stockfish != null and stockfish.available

func quit():
	if stockfish != null:
		stockfish.quit()

# Greedy fallback: best capture available, else a random legal move.
static func fallback_move(engine: GameEngine, ai_color: String, human_color: String):
	var moves = []
	var chess = engine.chess
	for r in range(8):
		for c in range(8):
			var piece = chess.board[r][c]
			if piece != "" and chess.piece_color(piece) == ai_color:
				for m in chess.get_legal_moves(r, c):
					moves.append([Vector2i(r, c), m])

	if moves.is_empty():
		return null

	moves.shuffle()

	var capture_value = func(move):
		var to = move[1]
		var target = chess.board[to.x][to.y]
		if target != "" and chess.piece_color(target) == human_color:
			return chess.get_piece_value(target)
		return 0

	moves.sort_custom(func(a, b): return capture_value.call(a) > capture_value.call(b))
	return moves[0]

# Asks Stockfish for a move (blocking on the calling thread - callers running
# this on the main thread should wrap it in a Thread to stay responsive).
func best_move(engine: GameEngine, ai_color: String, human_color: String):
	if has_engine():
		var fen = StockfishEngine.board_to_fen(engine)
		var uci = stockfish.best_move_for_fen(fen, difficulty)
		if uci != "":
			var squares = StockfishEngine.uci_to_squares(uci)
			if squares != null:
				return squares
	return fallback_move(engine, ai_color, human_color)

# Applies the computer's full turn: pick a move, play it, end the turn.
# Falls back to a greedy move if the engine's suggestion isn't legal in the
# current (possibly card-altered) position.
func apply_ai_turn(engine: GameEngine, ai_color: String, human_color: String):
	if engine.game_over or engine.chess.turn != ai_color:
		return

	var move = best_move(engine, ai_color, human_color)
	if move == null:
		engine.end_turn()
		return

	var ok = engine.try_move(move[0], move[1])
	if not ok:
		var fb = fallback_move(engine, ai_color, human_color)
		if fb != null:
			engine.try_move(fb[0], fb[1])

	if engine.chess.turn == ai_color and not engine.game_over:
		engine.end_turn()
