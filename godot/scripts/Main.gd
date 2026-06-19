extends Control

@onready var board: Node2D = $Board
@onready var hand_panel: Node2D = $HandPanel
@onready var status_label: Label = $StatusLabel
@onready var white_ether_label: Label = $WhiteEtherChip
@onready var black_ether_label: Label = $BlackEtherChip
@onready var turn_label: Label = $TurnLabel
@onready var end_turn_button: Button = $EndTurnButton
@onready var vs_ai_button: CheckButton = $VsAiButton
@onready var save_button: Button = $SaveButton
@onready var load_button: Button = $LoadButton
@onready var hint_label: Label = $HintLabel

const HUMAN_COLOR = GameEngine.WHITE
const AI_COLOR = GameEngine.BLACK

var ai: GameAI = null
var vs_ai := false

func _ready():
	hand_panel.engine = board.engine

	board.status_changed.connect(_on_update)
	board.move_made.connect(_on_update)
	hand_panel.card_played.connect(_on_update)
	hand_panel.card_discarded.connect(_on_update)
	end_turn_button.pressed.connect(_on_end_turn)
	vs_ai_button.toggled.connect(_on_vs_ai_toggled)
	save_button.pressed.connect(_on_save)
	load_button.pressed.connect(_on_load)
	_refresh_all()

func _on_vs_ai_toggled(pressed: bool):
	vs_ai = pressed
	if vs_ai and ai == null:
		ai = GameAI.new("Easy")
	_maybe_run_ai_turn()

func _on_update(_text: String = ""):
	_refresh_all()
	_maybe_run_ai_turn()

func _maybe_run_ai_turn():
	var engine: GameEngine = board.engine
	if not vs_ai or ai == null or engine.game_over:
		return
	if engine.chess.turn != AI_COLOR:
		return
	ai.apply_ai_turn(engine, AI_COLOR, HUMAN_COLOR)
	board.selected = null
	board.legal_moves = []
	board.queue_redraw()
	hand_panel.queue_redraw()
	_refresh_all()

func _refresh_all():
	var engine: GameEngine = board.engine
	status_label.text = engine.status_message
	white_ether_label.text = "White: %d" % engine.ether[GameEngine.WHITE]
	black_ether_label.text = "Black: %d" % engine.ether[GameEngine.BLACK]
	turn_label.text = "%s's Turn" % engine.chess.turn.capitalize()

	if engine.pending_card != "":
		hint_label.text = "Click a board square to target %s (right-click to cancel)" % engine.pending_card
	elif engine.active_card == "gambit":
		hint_label.text = "Gambit active: click your pieces to sacrifice, or click elsewhere to stop"
	else:
		hint_label.text = "Left-click a card to play it - right-click to discard"

	hand_panel.queue_redraw()

func _on_end_turn():
	var engine: GameEngine = board.engine
	if vs_ai and engine.chess.turn == AI_COLOR:
		return
	engine.end_turn()
	board.selected = null
	board.legal_moves = []
	board.queue_redraw()
	_refresh_all()
	_maybe_run_ai_turn()

func _on_save():
	var engine: GameEngine = board.engine
	var mode = "pvc" if vs_ai else "pvp"
	SaveManager.save_game(engine, mode, HUMAN_COLOR)
	status_label.text = "Game saved."

func _on_load():
	var payload = SaveManager.load_game()
	if payload == null:
		status_label.text = "No save found."
		return
	NetSync.apply(board.engine, payload["state"])
	vs_ai = payload["mode"] == "pvc"
	vs_ai_button.set_pressed_no_signal(vs_ai)
	if vs_ai and ai == null:
		ai = GameAI.new("Easy")
	board.queue_redraw()
	_refresh_all()
