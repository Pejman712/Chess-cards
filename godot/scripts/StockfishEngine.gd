extends RefCounted
class_name StockfishEngine

# Thin UCI wrapper around engine/stockfish_bin (or $STOCKFISH_PATH), ported
# from main.py's ensure_engine()/_think()/_board_to_fen(). Runs synchronously
# from the caller's point of view; GameAI is responsible for keeping this off
# the frame that needs to stay responsive (see GameAI._think_async via Thread).

const DIFFICULTY_SETTINGS = {
	"Easy": {"time_ms": 50, "elo": 1320},
	"Medium": {"time_ms": 100, "elo": 1700},
	"Hard": {"time_ms": 250, "elo": null},
}

var stdio: FileAccess = null
var available := false

func _init():
	var env_path = OS.get_environment("STOCKFISH_PATH")
	var path = env_path if env_path != "" else ProjectSettings.globalize_path("res://engine/stockfish_bin")

	if not FileAccess.file_exists(path):
		available = false
		return

	var result = OS.execute_with_pipe(path, [], false)
	stdio = result.get("stdio")
	if stdio == null:
		available = false
		return

	_send("uci")
	if not _wait_for("uciok", 2000):
		available = false
		stdio = null
		return

	_send("isready")
	_wait_for("readyok", 2000)
	available = true

func configure(difficulty: String):
	if not available:
		return
	var cfg = DIFFICULTY_SETTINGS.get(difficulty, DIFFICULTY_SETTINGS["Medium"])
	if cfg["elo"] == null:
		_send("setoption name UCI_LimitStrength value false")
	else:
		_send("setoption name UCI_LimitStrength value true")
		_send("setoption name UCI_Elo value %d" % cfg["elo"])

# Returns a UCI move string like "e2e4" or "e7e8q", or "" if no move found.
func best_move_for_fen(fen: String, difficulty: String) -> String:
	if not available:
		return ""

	var cfg = DIFFICULTY_SETTINGS.get(difficulty, DIFFICULTY_SETTINGS["Medium"])
	_send("position fen %s" % fen)
	_send("go movetime %d" % cfg["time_ms"])

	var deadline_ms = cfg["time_ms"] + 2000
	var start = Time.get_ticks_msec()
	while Time.get_ticks_msec() - start < deadline_ms:
		var line = stdio.get_line()
		if line.begins_with("bestmove"):
			var parts = line.split(" ")
			if parts.size() >= 2 and parts[1] != "(none)":
				return parts[1]
			return ""
		if line == "":
			OS.delay_msec(5)
	return ""

func quit():
	if stdio != null:
		_send("quit")
		stdio = null
	available = false

func _send(cmd: String):
	stdio.store_string(cmd + "\n")
	stdio.flush()

func _wait_for(token: String, timeout_ms: int) -> bool:
	var start = Time.get_ticks_msec()
	while Time.get_ticks_msec() - start < timeout_ms:
		var line = stdio.get_line()
		if line.begins_with(token):
			return true
		if line == "":
			OS.delay_msec(5)
	return false

# -----------------------------
# FEN <-> board conversion (ported from _board_to_fen / _uci_to_coords)
# -----------------------------
static func board_to_fen(engine: GameEngine) -> String:
	var chess = engine.chess
	var ranks = []
	for r in range(8):
		var run = 0
		var s = ""
		for c in range(8):
			var p = chess.board[r][c]
			if p == "":
				run += 1
			else:
				if run > 0:
					s += str(run)
					run = 0
				s += p
		if run > 0:
			s += str(run)
		ranks.append(s)
	var placement = "/".join(ranks)
	var active = "w" if chess.turn == ChessState.WHITE else "b"

	var rights = ""
	if not chess.white_king_moved:
		if not chess.white_right_rook_moved:
			rights += "K"
		if not chess.white_left_rook_moved:
			rights += "Q"
	if not chess.black_king_moved:
		if not chess.black_right_rook_moved:
			rights += "k"
		if not chess.black_left_rook_moved:
			rights += "q"
	if rights == "":
		rights = "-"

	var ep = "-"
	if chess.en_passant_target != null:
		var er = chess.en_passant_target.x
		var ec = chess.en_passant_target.y
		if er >= 0 and er < 8 and ec >= 0 and ec < 8:
			ep = "abcdefgh"[ec] + str(8 - er)

	return "%s %s %s %s 0 1" % [placement, active, rights, ep]

# uci move strings are e.g. "e2e4" or "e7e8q" (promotion suffix ignored -
# ChessState always auto-promotes pawns to queen, matching main.py).
static func uci_to_squares(move: String):
	if move.length() < 4:
		return null
	var from_file = move[0]
	var from_rank = move[1]
	var to_file = move[2]
	var to_rank = move[3]

	var files = "abcdefgh"
	var from_col = files.find(from_file)
	var from_row = 8 - int(from_rank)
	var to_col = files.find(to_file)
	var to_row = 8 - int(to_rank)

	if from_col < 0 or to_col < 0:
		return null

	return [Vector2i(from_row, from_col), Vector2i(to_row, to_col)]
