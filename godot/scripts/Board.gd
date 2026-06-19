extends Node2D

# Board geometry ported from main.py's load_pixel_board()/board_to_screen():
# the source art is a 142x142 image whose playable 8x8 grid starts at pixel
# (7, 20) with 16x12px tiles (slightly wider than tall, giving the board its
# tabletop look). We scale the whole image by SQUARE_W/16 so the grid lines
# up exactly under squares we draw highlights/pieces into.
const TILE_W_PX := 16
const TILE_H_PX := 12
const GRID_X_PX := 7
const GRID_Y_PX := 20
const SOURCE_SIZE := 142

const SQUARE_W := 64
const SQUARE_H := 48  # SQUARE_W * TILE_H_PX / TILE_W_PX, kept as a literal for const-folding
const BOARD_W := SQUARE_W * 8
const BOARD_H := SQUARE_H * 8

const SELECT_COLOR := Color8(80, 170, 255, 150)
const LEGAL_MOVE_COLOR := Color8(60, 220, 110, 170)
const CAPTURE_COLOR := Color8(230, 70, 70, 170)
const CHECK_COLOR := Color8(240, 60, 60, 90)
const FIRE_COLOR := Color8(255, 110, 40, 130)
const PENDING_HINT_COLOR := Color8(255, 215, 90, 90)

var engine: GameEngine
var selected = null
var legal_moves: Array = []
var piece_textures := {}
var board_texture: Texture2D

var dragging := false
var drag_piece := ""
var drag_from = null
var drag_mouse_pos := Vector2.ZERO

signal status_changed(text: String)
signal move_made()

func _ready():
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	engine = GameEngine.new()
	board_texture = load("res://assets/board_persp_05.png")
	_load_piece_textures()
	queue_redraw()
	status_changed.emit(engine.status_message)

func _load_piece_textures():
	var letter_to_name = {"p": "Pawn", "r": "Rook", "n": "Knight", "b": "Bishop", "q": "Queen", "k": "King"}
	for letter in letter_to_name:
		var name = letter_to_name[letter]
		piece_textures[letter.to_upper()] = load("res://assets/pieces/wood/W_%s.png" % name)
		piece_textures[letter] = load("res://assets/pieces/classic/B_%s.png" % name)

func _scale() -> float:
	return SQUARE_W / float(TILE_W_PX)

func _square_rect(row: int, col: int) -> Rect2:
	return Rect2(col * SQUARE_W, row * SQUARE_H, SQUARE_W, SQUARE_H)

func _draw():
	var scale = _scale()
	var grid_ox = GRID_X_PX * scale
	var grid_oy = GRID_Y_PX * scale
	var img_size = SOURCE_SIZE * scale
	draw_texture_rect(board_texture, Rect2(-grid_ox, -grid_oy, img_size, img_size), false)

	var chess = engine.chess

	if engine.pending_card != "":
		for r in range(8):
			for c in range(8):
				draw_rect(_square_rect(r, c), PENDING_HINT_COLOR)

	for sq in engine.fire_tiles:
		draw_rect(_square_rect(sq.x, sq.y), FIRE_COLOR)

	if not engine.game_over:
		var king_pos = chess.find_king(chess.turn)
		if king_pos != null and chess.is_in_check(chess.turn):
			draw_rect(_square_rect(king_pos.x, king_pos.y), CHECK_COLOR)

	if selected != null:
		draw_rect(_square_rect(selected.x, selected.y), SELECT_COLOR)
		for m in legal_moves:
			var is_capture = chess.board[m.x][m.y] != ""
			var color = CAPTURE_COLOR if is_capture else LEGAL_MOVE_COLOR
			var r = _square_rect(m.x, m.y)
			draw_circle(r.get_center(), SQUARE_W * 0.16, color)

	for row in range(8):
		for col in range(8):
			var piece = chess.board[row][col]
			if piece == "":
				continue
			if dragging and drag_from == Vector2i(row, col):
				continue
			_draw_piece(piece, row, col)

	if dragging:
		var dest_h = SQUARE_W * 2.0
		var dest = Rect2(drag_mouse_pos.x - SQUARE_W / 2.0, drag_mouse_pos.y - dest_h * 0.65, SQUARE_W, dest_h)
		draw_texture_rect(piece_textures.get(drag_piece), dest, false)

func _draw_piece(piece: String, row: int, col: int):
	var tex: Texture2D = piece_textures.get(piece)
	if tex == null:
		return
	# Sprites are 16x32 (1x2 tiles) and stand with their base on the square's
	# floor, overlapping the square above - same convention as main.py.
	var dest_h = SQUARE_W * 2.0
	var sq = _square_rect(row, col)
	var dest = Rect2(sq.position.x, sq.position.y + sq.size.y - dest_h, SQUARE_W, dest_h)
	draw_texture_rect(tex, dest, false)

func _square_from_pos(pos: Vector2):
	var col = int(pos.x / SQUARE_W)
	var row = int(pos.y / SQUARE_H)
	if row < 0 or row > 7 or col < 0 or col > 7:
		return null
	return Vector2i(row, col)

func _unhandled_input(event):
	if engine.game_over:
		return

	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
		if engine.pending_card != "":
			engine.cancel_pending_card()
			status_changed.emit(engine.status_message)
			queue_redraw()
		return

	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		var sq = _square_from_pos(get_local_mouse_position())
		if event.pressed:
			if sq == null:
				return

			if engine.pending_card != "":
				engine.play_card_target(sq.x, sq.y)
				move_made.emit()
				status_changed.emit(engine.status_message)
				queue_redraw()
				return

			if engine.active_card == "gambit":
				engine.click_square(sq.x, sq.y)
				move_made.emit()
				status_changed.emit(engine.status_message)
				queue_redraw()
				return

			var piece = engine.chess.board[sq.x][sq.y]
			if piece != "" and engine.chess.piece_color(piece) == engine.chess.turn:
				dragging = true
				drag_piece = piece
				drag_from = sq
				drag_mouse_pos = get_local_mouse_position()
				selected = sq
				legal_moves = engine.get_current_legal_moves(sq.x, sq.y)
				queue_redraw()
		else:
			if dragging:
				_try_drop(sq)
				dragging = false
				queue_redraw()

	elif event is InputEventMouseMotion and dragging:
		drag_mouse_pos = get_local_mouse_position()
		queue_redraw()

func _try_drop(to_sq):
	dragging = false
	if to_sq == null or drag_from == null:
		selected = null
		legal_moves = []
		return

	if engine.try_move(drag_from, to_sq):
		move_made.emit()
		status_changed.emit(engine.status_message)

	selected = null
	legal_moves = []
	drag_from = null
