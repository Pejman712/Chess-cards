extends RefCounted
class_name NetLink

# LAN networking for online play, ported from netplay.py: a UDP beacon so a
# client can find the host without typing an IP, plus a TCP link carrying
# full Variant payloads (Godot's StreamPeer.put_var/get_var already do the
# length-prefixed framing main.py hand-rolled with struct.pack).
#
# Host-authoritative, turn-based: whichever side just handed over the turn
# (or ended the game) sends its whole game state; the peer replaces its
# local state wholesale. See NetSync for what travels in that payload.

const DISCOVERY_PORT = 50777
const GAME_PORT = 50778
const MAGIC = "CHESSCARDS1:"

var role := ""          # "host" | "client"
var connected := false
var error := ""
var local_ip := ""

var _inbox: Array = []
var _mutex := Mutex.new()
var _stop := false
var _beacon_stop := false
var _tcp: StreamPeerTCP = null
var _thread: Thread = null
var _beacon_thread: Thread = null

func _init():
	local_ip = _get_local_ip()

func _get_local_ip() -> String:
	for ip in IP.get_local_addresses():
		if ip != "127.0.0.1" and not ip.begins_with("::") and ip.find(":") == -1:
			return ip
	return "127.0.0.1"

# ---------------------------------------------------------------- hosting
func host():
	role = "host"
	_thread = Thread.new()
	_thread.start(_host_thread)
	_beacon_thread = Thread.new()
	_beacon_thread.start(_beacon_loop)

func _beacon_loop():
	var udp = PacketPeerUDP.new()
	udp.set_broadcast_enabled(true)
	var msg = (MAGIC + local_ip).to_utf8_buffer()
	while not _beacon_stop and not connected:
		udp.set_dest_address("255.255.255.255", DISCOVERY_PORT)
		udp.put_packet(msg)
		OS.delay_msec(500)
	udp.close()

func _host_thread():
	var server = TCPServer.new()
	var err = server.listen(GAME_PORT)
	if err != OK:
		error = "listen failed (%d)" % err
		return
	while not _stop:
		if server.is_connection_available():
			_tcp = server.take_connection()
			_beacon_stop = true
			connected = true
			break
		OS.delay_msec(100)
	server.stop()
	if _tcp != null:
		_recv_loop()

# ---------------------------------------------------------------- joining
func join(host_ip: String = ""):
	role = "client"
	_thread = Thread.new()
	_thread.start(_join_thread.bind(host_ip))

func _discover(timeout_sec: float = 8.0) -> String:
	var udp = PacketPeerUDP.new()
	var err = udp.bind(DISCOVERY_PORT)
	if err != OK:
		error = "discovery bind failed (%d)" % err
		return ""

	var deadline = Time.get_ticks_msec() + int(timeout_sec * 1000)
	while Time.get_ticks_msec() < deadline and not _stop:
		if udp.get_available_packet_count() > 0:
			var data = udp.get_packet()
			var s = data.get_string_from_utf8()
			if s.begins_with(MAGIC):
				udp.close()
				return s.substr(MAGIC.length())
		OS.delay_msec(50)
	udp.close()
	return ""

func _join_thread(host_ip: String):
	var ip = host_ip
	if ip == "":
		ip = _discover()
	if ip == "":
		if error == "":
			error = "No host found on the network."
		return

	var tcp = StreamPeerTCP.new()
	var err = tcp.connect_to_host(ip, GAME_PORT)
	if err != OK:
		error = "connect failed (%d)" % err
		return

	var deadline = Time.get_ticks_msec() + 5000
	while Time.get_ticks_msec() < deadline:
		tcp.poll()
		var status = tcp.get_status()
		if status == StreamPeerTCP.STATUS_CONNECTED:
			break
		if status == StreamPeerTCP.STATUS_ERROR:
			error = "connection error"
			return
		OS.delay_msec(20)

	if tcp.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		error = "connect timeout"
		return

	_tcp = tcp
	connected = true
	_recv_loop()

# ------------------------------------------------------------- framed I/O
func send(payload: Dictionary):
	if _tcp == null:
		return
	_tcp.put_var(payload)

func _recv_loop():
	while not _stop:
		_tcp.poll()
		var status = _tcp.get_status()
		if status != StreamPeerTCP.STATUS_CONNECTED:
			error = "peer disconnected"
			connected = false
			return
		if _tcp.get_available_bytes() > 0:
			var data = _tcp.get_var()
			_mutex.lock()
			_inbox.append(data)
			_mutex.unlock()
		else:
			OS.delay_msec(20)

func poll():
	_mutex.lock()
	var result = null
	if not _inbox.is_empty():
		result = _inbox.pop_front()
	_mutex.unlock()
	return result

func close():
	_stop = true
	_beacon_stop = true
	if _tcp != null:
		_tcp.disconnect_from_host()
	if _thread != null and _thread.is_started():
		_thread.wait_to_finish()
	if _beacon_thread != null and _beacon_thread.is_started():
		_beacon_thread.wait_to_finish()
