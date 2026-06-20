# Settings (config.json) and save-game (savegame.pkl) persistence.
#
# Each function takes `app` - the running main module - and reads/writes its
# attributes directly (e.g. `app.game`, `app.human_color`) instead of
# importing main.py as a module. main.py is the entry script, so importing it
# by name would re-execute it as a second module (a real circular import);
# main.py instead passes itself in (see the wrappers near its persistence
# import) so there is still a single source of truth for this shared state.

import os
import json
import pickle

import pygame

from carddata import ALL_TRAY_CARDS

_BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
CONFIG_PATH = os.path.join(_BASE_DIR, "config.json")
SAVE_PATH = os.path.join(_BASE_DIR, "savegame.pkl")


def save_config(app):
    data = {
        "music_muted": app.music_muted,
        "white_skin_index": app.white_skin_index,
        "black_skin_index": app.black_skin_index,
        "board_index": app.current_board_index,
        "difficulty": app.difficulty,
        "human_color": app.human_color,
        # Store the *disabled* cards so cards added in future updates default on.
        "disabled_cards": [c for c in ALL_TRAY_CARDS if c not in app.enabled_cards],
    }
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        print("save_config failed:", exc)


def load_config(app):
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
    except Exception:
        return  # no config yet, or unreadable - keep defaults

    app.music_muted = bool(data.get("music_muted", app.music_muted))
    app.white_skin_index = int(data.get("white_skin_index", app.white_skin_index)) % len(app.PIECE_SKINS)
    app.black_skin_index = int(data.get("black_skin_index", app.black_skin_index)) % len(app.PIECE_SKINS)
    if data.get("difficulty") in app.DIFFICULTY_SETTINGS:
        app.difficulty = data["difficulty"]
    if data.get("human_color") in (app.WHITE, app.BLACK):
        app.human_color = data["human_color"]

    disabled = set(data.get("disabled_cards", []))
    app.enabled_cards.clear()
    app.enabled_cards.update(c for c in ALL_TRAY_CARDS if c not in disabled)

    bi = int(data.get("board_index", app.current_board_index))
    if 0 <= bi < len(app.BOARD_FILES):
        app.current_board_index = bi
        app.BOARD_IMAGE, app.BOARD_IMAGE_OX, app.BOARD_IMAGE_OY, app.LIGHT_SQUARE, app.DARK_SQUARE = (
            app.load_pixel_board(app.BOARD_FILES[bi]))

    if app.music_muted and app._audio_ok:
        pygame.mixer.music.set_volume(0.0)


def has_save(app):
    return os.path.exists(SAVE_PATH)


def save_game(app):
    # Auto-saved during local play so a game can be resumed from the menu.
    if app.game_mode not in ("pvp", "pvc") or app.game.game_over:
        return
    try:
        with open(SAVE_PATH, "wb") as f:
            pickle.dump({"mode": app.game_mode, "human_color": app.human_color,
                         "dict": app.game.__dict__}, f)
    except Exception as exc:
        print("save_game failed:", exc)


def delete_save(app):
    try:
        if os.path.exists(SAVE_PATH):
            os.remove(SAVE_PATH)
    except Exception:
        pass


def load_game(app):
    try:
        with open(SAVE_PATH, "rb") as f:
            data = pickle.load(f)
    except Exception as exc:
        print("load_game failed:", exc)
        return False
    app.game_mode = data.get("mode", "pvp")
    app.human_color = data.get("human_color", app.WHITE)
    app.game.__dict__.update(data["dict"])
    app.animations.clear()
    app.dragging_card = None
    app.dragging_piece = None
    app.ai_reset()
    if app.game_mode == "pvc":
        app.ensure_engine()
        app.configure_engine()
    return True
