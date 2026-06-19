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
	SaveManager.delete_save()
	test_config_roundtrip()
	test_save_load_roundtrip()
	test_no_save_after_game_over()
	test_delete_save()
	print("---")
	print("%d/%d checks passed" % [checks - failures, checks])
	quit(1 if failures > 0 else 0)

func test_config_roundtrip():
	var settings = {
		"music_muted": true,
		"white_skin_index": 5,
		"difficulty": "Hard",
		"human_color": "black",
		"disabled_cards": ["capitalism", "solo"],
	}
	SaveManager.save_config(settings)
	var loaded = SaveManager.load_config()
	check("music_muted persisted", loaded["music_muted"] == true)
	check("white_skin_index persisted", loaded["white_skin_index"] == 5)
	check("difficulty persisted", loaded["difficulty"] == "Hard")
	check("human_color persisted", loaded["human_color"] == "black")
	check("disabled_cards persisted", loaded["disabled_cards"] == ["capitalism", "solo"])
	check("unset fields keep their default (board_index)", loaded["board_index"] == 0)

func test_save_load_roundtrip():
	var g = GameEngine.new()
	g.try_move(Vector2i(6, 4), Vector2i(4, 4))
	g.end_turn()
	g.ether[GameEngine.WHITE] = 42
	g.fire_tiles[Vector2i(3, 3)] = 2

	check("no save exists yet", not SaveManager.has_save())
	SaveManager.save_game(g, "pvc", GameEngine.BLACK)
	check("save file now exists", SaveManager.has_save())

	var payload = SaveManager.load_game()
	check("load returns a payload", payload != null)
	check("mode round-trips", payload["mode"] == "pvc")
	check("human_color round-trips", payload["human_color"] == "black")

	var g2 = GameEngine.new()
	NetSync.apply(g2, payload["state"])
	check("board position round-trips", g2.chess.board[4][4] == "P")
	check("turn round-trips", g2.chess.turn == g.chess.turn)
	check("ether round-trips", g2.ether[GameEngine.WHITE] == 42)
	check("fire tiles round-trip", g2.fire_tiles.get(Vector2i(3, 3)) == 2)

func test_no_save_after_game_over():
	SaveManager.delete_save()
	var g = GameEngine.new()
	g.game_over = true
	SaveManager.save_game(g, "pvp", GameEngine.WHITE)
	check("a finished game is not auto-saved", not SaveManager.has_save())

func test_delete_save():
	var g = GameEngine.new()
	SaveManager.save_game(g, "pvp", GameEngine.WHITE)
	check("save exists before delete", SaveManager.has_save())
	SaveManager.delete_save()
	check("save is gone after delete", not SaveManager.has_save())
