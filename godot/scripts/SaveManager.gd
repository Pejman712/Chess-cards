extends RefCounted
class_name SaveManager

# Settings + save-game persistence, ported from main.py's save_config/
# load_config/save_game/load_game. Godot's user:// is the equivalent of
# main.py writing config.json/savegame.pkl next to the script.

const CONFIG_PATH = "user://config.json"
const SAVE_PATH = "user://savegame.dat"

const DEFAULT_CONFIG = {
	"music_muted": false,
	"white_skin_index": 2,
	"black_skin_index": 1,
	"board_index": 0,
	"difficulty": "Medium",
	"human_color": "white",
	"disabled_cards": [],
}

static func save_config(settings: Dictionary):
	var data = DEFAULT_CONFIG.duplicate()
	for key in settings:
		data[key] = settings[key]
	var f = FileAccess.open(CONFIG_PATH, FileAccess.WRITE)
	if f == null:
		return
	f.store_string(JSON.stringify(data, "  "))
	f.close()

static func load_config() -> Dictionary:
	if not FileAccess.file_exists(CONFIG_PATH):
		return DEFAULT_CONFIG.duplicate()
	var f = FileAccess.open(CONFIG_PATH, FileAccess.READ)
	if f == null:
		return DEFAULT_CONFIG.duplicate()
	var text = f.get_as_text()
	f.close()

	var parsed = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		return DEFAULT_CONFIG.duplicate()

	var data = DEFAULT_CONFIG.duplicate()
	for key in parsed:
		data[key] = parsed[key]
	return data

static func has_save() -> bool:
	return FileAccess.file_exists(SAVE_PATH)

# Mirrors main.py: auto-saved during local (pvp/pvc) play, not mid-game-over.
static func save_game(engine: GameEngine, mode: String, human_color: String):
	if mode != "pvp" and mode != "pvc":
		return
	if engine.game_over:
		return

	var payload = {
		"mode": mode,
		"human_color": human_color,
		"state": NetSync.serialize(engine),
	}
	var f = FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f == null:
		return
	f.store_var(payload)
	f.close()

static func delete_save():
	if FileAccess.file_exists(SAVE_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SAVE_PATH))

# Returns {"mode": String, "human_color": String, "state": Dictionary} or
# null if there is no save / it can't be read.
static func load_game():
	if not has_save():
		return null
	var f = FileAccess.open(SAVE_PATH, FileAccess.READ)
	if f == null:
		return null
	var payload = f.get_var()
	f.close()
	if typeof(payload) != TYPE_DICTIONARY or not payload.has("state"):
		return null
	return payload
