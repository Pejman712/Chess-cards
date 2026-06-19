extends Node2D

# Fanned hand of card art at the bottom of the screen, replacing main.py's
# tray of draggable cards with a simpler click-to-play / right-click-to-
# discard interaction (full drag-and-drop card art is future polish).

const CARD_W := 110
const CARD_H := 138  # matches the card art's 183:230 aspect ratio
const CARD_SPACING := 56
const ARC_LIFT := 22
const HOVER_LIFT := 14

var engine: GameEngine
var card_textures := {}  # "name_color" -> Texture2D
var hover_index := -1

signal card_played()
signal card_discarded()

func _ready():
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	for card_name in GameEngine.CARD_NAMES:
		card_textures["%s_white" % card_name] = _try_load("res://cards/%s_white.png" % card_name)
		card_textures["%s_black" % card_name] = _try_load("res://cards/%s_black.png" % card_name)

func _try_load(path: String) -> Texture2D:
	if ResourceLoader.exists(path):
		return load(path)
	return null

func _hand() -> Array:
	if engine == null:
		return []
	return engine.hand[engine.chess.turn]

func _card_rect(index: int) -> Rect2:
	var hand = _hand()
	var n = hand.size()
	var center = (n - 1) / 2.0
	var t = index - center
	var max_t = max(center, 0.5)
	var lift = ARC_LIFT * (1.0 - pow(t / max_t, 2)) if n > 1 else ARC_LIFT
	var x = t * CARD_SPACING - CARD_W / 2.0
	var y = -lift - (HOVER_LIFT if index == hover_index else 0.0)
	return Rect2(x, y, CARD_W, CARD_H)

func _draw():
	if engine == null:
		return
	var hand = _hand()
	var color_suffix = "white" if engine.chess.turn == GameEngine.WHITE else "black"

	for i in range(hand.size()):
		var card_name = hand[i]
		var rect = _card_rect(i)
		var tex: Texture2D = card_textures.get("%s_%s" % [card_name, color_suffix])
		var cost = GameEngine.CARD_COSTS.get(card_name, 0)
		var affordable = engine.ether[engine.chess.turn] >= cost

		if tex != null:
			draw_texture_rect(tex, rect, false, Color(1, 1, 1, 1) if affordable else Color(0.55, 0.55, 0.55, 1))
		else:
			draw_rect(rect, Color(0.3, 0.3, 0.3))
			draw_string(ThemeDB.fallback_font, rect.position + Vector2(6, 20), card_name, HORIZONTAL_ALIGNMENT_LEFT, rect.size.x - 12, 12)

		if i == hover_index:
			draw_rect(rect, Color(1, 1, 0.6, 0.25))

		draw_string(ThemeDB.fallback_font, rect.position + Vector2(4, rect.size.y - 6), str(cost), HORIZONTAL_ALIGNMENT_LEFT, 40, 16, Color(1, 0.9, 0.4))

func _index_at(pos: Vector2) -> int:
	var hand = _hand()
	# Topmost-drawn card (last index) should win when fans overlap.
	for i in range(hand.size() - 1, -1, -1):
		if _card_rect(i).has_point(pos):
			return i
	return -1

func _unhandled_input(event):
	if event is InputEventMouseMotion:
		var new_hover = _index_at(get_local_mouse_position())
		if new_hover != hover_index:
			hover_index = new_hover
			queue_redraw()

	if event is InputEventMouseButton and event.pressed:
		var idx = _index_at(get_local_mouse_position())
		if idx == -1:
			return
		var card_name = _hand()[idx]

		if event.button_index == MOUSE_BUTTON_LEFT:
			engine.play_card(card_name)
			card_played.emit()
			queue_redraw()
		elif event.button_index == MOUSE_BUTTON_RIGHT:
			engine.discard_card(card_name)
			card_discarded.emit()
			queue_redraw()
