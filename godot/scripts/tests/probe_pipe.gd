extends SceneTree

func _init():
	var path = ProjectSettings.globalize_path("res://engine/stockfish_bin")
	print("path: ", path)
	var result = OS.execute_with_pipe(path, [], false)
	print("result keys: ", result.keys())
	var stdio: FileAccess = result.get("stdio")
	print("stdio: ", stdio)
	if stdio != null:
		stdio.store_string("uci\n")
		stdio.flush()
		var got_uciok = false
		for i in range(500):
			var line = stdio.get_line()
			if line != "":
				print("line: ", line)
			if line.begins_with("uciok"):
				got_uciok = true
				break
			OS.delay_msec(10)
		print("got uciok: ", got_uciok)

		stdio.store_string("isready\n")
		stdio.flush()
		for i in range(200):
			var line = stdio.get_line()
			if line != "":
				print("ready-line: ", line)
			if line.begins_with("readyok"):
				break
			OS.delay_msec(10)

		stdio.store_string("position startpos\ngo movetime 200\n")
		stdio.flush()
		for i in range(300):
			var line = stdio.get_line()
			if line != "":
				print("go-line: ", line)
			if line.begins_with("bestmove"):
				break
			OS.delay_msec(10)
	quit()
