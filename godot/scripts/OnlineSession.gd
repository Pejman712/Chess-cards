extends RefCounted
class_name OnlineSession

# Glue between NetLink/NetSync and a GameEngine, ported from main.py's
# net_lobby_update/net_receive/net_push_if_handover. Host plays White and
# deals the opening hands; the client receives that as its first state sync.

var net: NetLink = null
var engine: GameEngine = null
var local_color := ""
var dealt := false
var _prev_turn := ""
var _prev_over := false

func start_host(eng: GameEngine) -> NetLink:
	engine = eng
	local_color = GameEngine.WHITE
	net = NetLink.new()
	net.host()
	return net

func start_join(eng: GameEngine, host_ip: String = "") -> NetLink:
	engine = eng
	local_color = GameEngine.BLACK
	net = NetLink.new()
	net.join(host_ip)
	return net

# Call every frame while waiting in the lobby. Returns true once both sides
# have a synced opening position and gameplay should begin.
func lobby_update() -> bool:
	if net == null or net.error != "":
		return false

	if net.role == "host":
		if net.connected and not dealt:
			_reset_sync()
			net.send(NetSync.serialize(engine))
			dealt = true
			return true
		return false
	else:
		if net.connected:
			var payload = net.poll()
			if payload != null:
				NetSync.apply(engine, payload)
				_reset_sync()
				return true
		return false

func _reset_sync():
	_prev_turn = engine.chess.turn
	_prev_over = engine.game_over

# Call every frame during play: drains any state the peer sent.
func receive():
	if net == null:
		return
	var payload = net.poll()
	while payload != null:
		NetSync.apply(engine, payload)
		_prev_turn = engine.chess.turn
		_prev_over = engine.game_over
		payload = net.poll()

# Call after local input is processed: sends our state if we just handed
# the turn over (or the game just ended).
func push_if_handover():
	if net == null or not net.connected:
		return
	var ended_turn = _prev_turn == local_color and engine.chess.turn != local_color
	var ended_game = engine.game_over and not _prev_over
	if ended_turn or ended_game:
		net.send(NetSync.serialize(engine))
	_prev_turn = engine.chess.turn
	_prev_over = engine.game_over

func leave():
	if net != null:
		net.close()
	net = null
