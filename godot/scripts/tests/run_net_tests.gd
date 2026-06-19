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

func wait_until(timeout_ms: int, pred: Callable) -> bool:
	var start = Time.get_ticks_msec()
	while Time.get_ticks_msec() - start < timeout_ms:
		if pred.call():
			return true
		OS.delay_msec(20)
	return false

func _init():
	test_loopback_handshake_and_sync()
	print("---")
	print("%d/%d checks passed" % [checks - failures, checks])
	quit(1 if failures > 0 else 0)

func test_loopback_handshake_and_sync():
	var host_engine = GameEngine.new()
	var client_engine = GameEngine.new()

	var host_session = OnlineSession.new()
	host_session.start_host(host_engine)

	var client_session = OnlineSession.new()
	client_session.start_join(client_engine, "127.0.0.1")

	var host_ready = wait_until(8000, func(): return host_session.lobby_update())
	check("host completes the handshake and deals", host_ready)

	var client_ready = wait_until(8000, func(): return client_session.lobby_update())
	check("client receives the opening state", client_ready)

	check("client's hand matches the host's dealt hand", client_engine.hand[GameEngine.WHITE] == host_engine.hand[GameEngine.WHITE])
	check("client's turn matches host's turn", client_engine.chess.turn == host_engine.chess.turn)

	# Host (White) makes a move and ends the turn; that should push state to the client.
	host_engine.try_move(Vector2i(6, 4), Vector2i(4, 4))
	host_session._prev_turn = host_engine.chess.turn
	host_engine.end_turn()
	host_session.push_if_handover()

	var synced = wait_until(4000, func():
		client_session.receive()
		return client_engine.chess.turn == GameEngine.BLACK
	)
	check("client received the host's move after turn handover", synced)
	check("client sees the moved pawn", client_engine.chess.board[4][4] == "P")

	host_session.leave()
	client_session.leave()
