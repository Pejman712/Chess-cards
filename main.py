import pygame
import sys
import copy
import math
import os
import random

from cards.pawntastic import get_pawntastic_moves
from cards.bishock import get_bishock_destroyed_squares
from cards.rookdemon import get_rookdemon_path
from cards.windknight import is_valid_windknight_target
from cards.queentum import get_queentum_moves
from cards.longlivetheking import choose_random_escape_corner, get_empty_escape_corners, get_surrounding_empty_squares

pygame.init()

# Audio is optional: a machine without a sound device (or a headless test
# run) should still launch the game, just silently.
try:
    pygame.mixer.init()
    _audio_ok = True
except pygame.error:
    _audio_ok = False


def start_music():
    if not _audio_ok:
        return
    try:
        pygame.mixer.music.load(os.path.join("assets", "music.mp3"))
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play(-1)  # loop forever
    except pygame.error:
        pass


# -----------------------------
# Window / board settings
# -----------------------------
ROWS = 8
COLS = 8

# Fullscreen. Press ESC to quit.
# Set CHESS_WINDOW=1280x800 to run windowed instead (useful for testing).
if os.environ.get("CHESS_WINDOW"):
    win_w, win_h = (int(v) for v in os.environ["CHESS_WINDOW"].lower().split("x"))
    display = pygame.display.set_mode((win_w, win_h))
else:
    display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
pygame.display.set_caption("Chess Power-Up Cards")
SCREEN_WIDTH, SCREEN_HEIGHT = display.get_size()

# The whole game is drawn to this offscreen surface, then blitted to the real
# window each frame - optionally with a shake offset (see the main loop).
screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
clock = pygame.time.Clock()

# Layout (top to bottom): info bar at the very top, the board in the middle,
# and the player's hand fanned in an arc across the bottom.
SIDE_MARGIN = 16
BOARD_MARGIN = 6  # tight vertical gap so the board can take more space
PANEL_PAD = 12
HEADER_H = 30
CARD_GAP = 10
INFO_HEIGHT = 92  # taller bar to fit the larger fonts
CARD_ASPECT = 230 / 183  # card art aspect (height / width)

# The board only reserves HAND_RESERVE at the bottom for the hand. The actual
# cards are larger than that and are anchored to the screen bottom, so they
# fan up and overlap the board's lower edge a little.
HAND_RESERVE = int(SCREEN_HEIGHT * 0.225)
TRAY_HEIGHT = HAND_RESERVE
TRAY_Y = SCREEN_HEIGHT - HAND_RESERVE

CARD_HEIGHT = int(SCREEN_HEIGHT * 0.235)
CARD_WIDTH = int(CARD_HEIGHT / CARD_ASPECT)
TRAY_COLS = max(1, (SCREEN_WIDTH - 2 * SIDE_MARGIN) // (CARD_WIDTH + PANEL_PAD))
ARC_LIFT = int(CARD_HEIGHT * 0.10)  # how high the middle of the fan rises
ACTION_BTN_W = 210  # End Turn / Discard buttons flanking the hand

# Info bar pinned to the very top; the board fills the space between them.
INFO_Y = 0
BOARD_AREA_WIDTH = SCREEN_WIDTH - 2 * SIDE_MARGIN
BOARD_AREA_TOP = INFO_HEIGHT + BOARD_MARGIN
BOARD_AREA_HEIGHT = (TRAY_Y - BOARD_MARGIN) - BOARD_AREA_TOP

# The perspective board has 16x12px squares (4 wide : 3 tall on screen). The
# vertical budget per square width is 8 rows * 0.75 = 6, plus 1.25 headroom for
# the back-rank sprites. The board's bottom lip is allowed to tuck behind the
# hand cards, so it is not reserved here.
# BOARD_SCALE shrinks the board below the space it could fill, leaving more
# room around it (which the dimmed backdrop and larger hand cards fill).
BOARD_SCALE = 0.84
SQUARE_W = min(BOARD_AREA_WIDTH // COLS, int(BOARD_AREA_HEIGHT / 7.25))
SQUARE_W = int(SQUARE_W * BOARD_SCALE)
SQUARE_W -= SQUARE_W % 4
SQUARE_H = SQUARE_W * 3 // 4
SQUARE_SIZE = SQUARE_W  # piece sprites and effect sizes scale off the square width

BOARD_W = SQUARE_W * COLS
BOARD_H = SQUARE_H * ROWS
PIECE_HEADROOM = SQUARE_W * 2 - SQUARE_H

BOARD_X = SIDE_MARGIN + max(0, (BOARD_AREA_WIDTH - BOARD_W) // 2)
# BOARD_LIFT raises the board above its centered position (bigger = higher).
BOARD_LIFT = 80
BOARD_Y = BOARD_AREA_TOP + PIECE_HEADROOM + max(
    0, (BOARD_AREA_HEIGHT - PIECE_HEADROOM - BOARD_H) // 2
) - BOARD_LIFT

WIDTH = SCREEN_WIDTH
HEIGHT = SCREEN_HEIGHT

# -----------------------------
# Colors
# -----------------------------
# LIGHT_SQUARE / DARK_SQUARE are sampled from the active board image at load
# time (see load_pixel_board) so coordinate labels stay readable on any palette.
SELECT_COLOR = (80, 170, 255)
LEGAL_MOVE_COLOR = (60, 180, 90)
CAPTURE_COLOR = (220, 80, 80)
CHECK_COLOR = (240, 60, 60)

INFO_BG = (35, 35, 35)
SIDEBAR_BG = (25, 30, 25)
TEXT_COLOR = (240, 240, 240)
MUTED_TEXT = (150, 150, 150)
CARD_BORDER = (210, 180, 90)
CARD_DISABLED = (70, 70, 70)

# Classic table / board styling
WOOD_FRAME = (105, 62, 28)
WOOD_FRAME_DARK = (35, 20, 10)
WOOD_FRAME_LIGHT = (182, 125, 58)
PANEL_BG = (24, 19, 15)
PANEL_EDGE = (151, 105, 52)
GOLD = (225, 190, 104)
PARCHMENT = (224, 202, 157)

# Short effect animations.
animations = []

# UI font: m6x11 by Daniel Linssen (managore.itch.io/m6x11), the typeface
# Balatro uses. It is designed on a 16pt pixel grid - render it at multiples
# of 16 with antialiasing forced off so the pixels stay square and crisp.
FONT_PATH = os.path.join("assets", "fonts", "m6x11.ttf")


class PixelFont(pygame.font.Font):
    def render(self, text, antialias=True, color=(255, 255, 255), background=None):
        return super().render(text, False, color, background)


def load_font(size, fallback_size, bold=False):
    try:
        return PixelFont(FONT_PATH, size)
    except (OSError, FileNotFoundError, pygame.error):
        return pygame.font.SysFont("dejavusans", fallback_size, bold=bold)


title_font = load_font(48, 32, bold=True)
small_font = load_font(24, 22, bold=True)
tiny_font = load_font(20, 18)
badge_font = load_font(20, 16, bold=True)
menu_title_font = load_font(96, 64, bold=True)
menu_font = load_font(32, 26, bold=True)
home_title_font = load_font(160, 120, bold=True)  # big CHESSBYTE logo
menu_option_font = load_font(40, 30, bold=True)   # START / CATALOG / ...
subtitle_font = load_font(26, 20, bold=True)      # DEAL . DEPLOY . CHECKMATE
hint_font = load_font(22, 18, bold=True)          # footer controls hint
action_font = load_font(32, 24, bold=True)        # END TURN / DISCARD buttons

TEXT_SHADOW_COLOR = (24, 13, 8)


def draw_shadow_text(font_obj, text, color, pos, offset=2):
    screen.blit(font_obj.render(text, True, TEXT_SHADOW_COLOR), (pos[0] + offset, pos[1] + offset))
    screen.blit(font_obj.render(text, True, color), pos)


# Single characters re-render every frame for the wave, so cache them.
_glyph_cache = {}


def get_glyph(font_obj, ch, color):
    key = (id(font_obj), ch, color)

    if key not in _glyph_cache:
        _glyph_cache[key] = font_obj.render(ch, True, color)

    return _glyph_cache[key]


def draw_wavy_text(font_obj, text, color, pos, amp=2, offset=2, target=None, phase=0.0):
    # Balatro-style label: every character bobs on its own phase. Offsets
    # snap to whole pixels so the pixel grid stays intact.
    if target is None:
        target = screen

    ticks = pygame.time.get_ticks()
    x, y = pos

    for i, ch in enumerate(text):
        dy = round(math.sin(ticks * 0.006 + i * 0.55 + phase) * amp)
        target.blit(get_glyph(font_obj, ch, TEXT_SHADOW_COLOR), (x + offset, y + dy + offset))
        glyph = get_glyph(font_obj, ch, color)
        target.blit(glyph, (x, y + dy))
        x += glyph.get_width()

# -----------------------------
# Pixel-art board and pieces
# Assets: "pixel chess" by Dani Maccari (https://dani-maccari.itch.io/)
# -----------------------------
ASSET_DIR = "assets"

# Board color options, cycled in-game with the B key. All share the same
# perspective geometry, so only the palette changes between them.
BOARD_FILES = [
    "board_persp_05.png",  # warm brown (default)
    "board_persp_01.png",  # slate blue
    "board_persp_02.png",  # pale green
    "board_persp_03.png",  # steel
    "board_persp_04.png",  # navy
]
current_board_index = 0

# Source geometry of the perspective board image: 16x12px squares, with the
# playing area's top-left square starting at pixel (7, 20). The frame around
# it carries baked-in coordinate labels (left and bottom) and a 3D lip below.
BOARD_TILE_W_PX = 16
BOARD_TILE_H_PX = 12
BOARD_GRID_X_PX = 7
BOARD_GRID_Y_PX = 20


def load_pixel_board(filename):
    image = pygame.image.load(os.path.join(ASSET_DIR, filename)).convert_alpha()

    # Sample a light and a dark square so the drawn coordinate labels stay
    # readable on whatever palette this board uses.
    light = tuple(image.get_at((BOARD_GRID_X_PX + 8, BOARD_GRID_Y_PX + 6)))[:3]
    dark = tuple(image.get_at((BOARD_GRID_X_PX + 24, BOARD_GRID_Y_PX + 6)))[:3]

    # Paint over the baked-in coordinate labels on the frame: the game draws
    # its own coordinates so they stay correct when the board flips for Black.
    frame_color = image.get_at((image.get_width() // 2, BOARD_GRID_Y_PX - 3))
    grid_h_px = BOARD_TILE_H_PX * ROWS
    grid_w_px = BOARD_TILE_W_PX * COLS
    pygame.draw.rect(
        image,
        frame_color,
        pygame.Rect(0, BOARD_GRID_Y_PX, BOARD_GRID_X_PX - 1, grid_h_px),
    )
    pygame.draw.rect(
        image,
        frame_color,
        pygame.Rect(BOARD_GRID_X_PX, BOARD_GRID_Y_PX + grid_h_px + 1, grid_w_px, 5),
    )

    # 16x12 source squares scale to SQUARE_W x SQUARE_H with the same factor
    # on both axes. Nearest-neighbour scaling keeps the pixel art crisp.
    scale = SQUARE_W / BOARD_TILE_W_PX
    size = round(image.get_width() * scale)
    scaled = pygame.transform.scale(image, (size, size))
    return scaled, round(BOARD_GRID_X_PX * scale), round(BOARD_GRID_Y_PX * scale), light, dark


BOARD_IMAGE, BOARD_IMAGE_OX, BOARD_IMAGE_OY, LIGHT_SQUARE, DARK_SQUARE = load_pixel_board(
    BOARD_FILES[current_board_index]
)

# Animated background: a looping GIF decoded once at startup. Frames are
# stored at half screen resolution to keep memory reasonable and upscaled
# when drawn; a dark tint baked into each frame keeps the play area readable.
BACKGROUND_FILE = os.path.join(ASSET_DIR, "background.png")
BACKGROUND_DIM = 110  # 0 = full brightness, 255 = black


def load_background_image():
    try:
        image = pygame.image.load(BACKGROUND_FILE).convert()
    except (pygame.error, FileNotFoundError):
        return None
    image = pygame.transform.scale(image, (SCREEN_WIDTH, SCREEN_HEIGHT))
    # Darken so the board and cards stay readable on top.
    tint = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    tint.set_alpha(BACKGROUND_DIM)
    image.blit(tint, (0, 0))
    return image


BACKGROUND_IMAGE = load_background_image()

# Armageddon sprite animation, sliced from assets/meteor_strike.png: the
# first METEOR_FALL_COUNT frames are the falling meteor, the rest play
# through once at the impact point (burst, explosion, smoke, ash).
METEOR_FALL_COUNT = 4


def load_meteor_frames():
    frames = []

    for i in range(32):
        path = os.path.join(ASSET_DIR, f"meteor_{i}.png")
        if not os.path.exists(path):
            break
        frames.append(pygame.image.load(path).convert_alpha())

    if len(frames) <= METEOR_FALL_COUNT:
        return []

    # One shared scale, sized so the biggest explosion frame spans the 3x3
    # blast area; the falling piece stays proportionally smaller.
    scale = SQUARE_W * 3.4 / max(frame.get_width() for frame in frames)
    return [
        pygame.transform.scale(
            frame,
            (max(1, round(frame.get_width() * scale)), max(1, round(frame.get_height() * scale))),
        )
        for frame in frames
    ]


METEOR_FRAMES = load_meteor_frames()


# Fire tile sprites: a looping campfire cycle (grow, peak, ember, smoke).
def load_fire_frames():
    frames = []

    for i in range(32):
        path = os.path.join(ASSET_DIR, f"fire_{i}.png")
        if not os.path.exists(path):
            break
        frames.append(pygame.image.load(path).convert_alpha())

    if not frames:
        return []

    # Shared scale, sized so the biggest flame nearly fills a square width.
    scale = SQUARE_W * 0.95 / max(frame.get_width() for frame in frames)
    return [
        pygame.transform.scale(
            frame,
            (max(1, round(frame.get_width() * scale)), max(1, round(frame.get_height() * scale))),
        )
        for frame in frames
    ]


FIRE_FRAMES = load_fire_frames()

# 16x32 sprites: a piece stands on its square and overlaps the square above.
PIECE_NAMES = {
    "p": "Pawn", "r": "Rook", "n": "Knight", "b": "Bishop", "q": "Queen", "k": "King",
}

# Piece color/style options. White and Black each pick a skin independently
# (cycle with 1 and 2 in-game). A skin is drawn either from an art folder
# ("asset") or by recoloring the crisp light sprite with a multiply tint
# ("tint"), which keeps dark outlines dark and transparent pixels clear.
PIECE_SKINS = [
    {"name": "Ivory", "spec": ("asset", "classic", "W")},
    {"name": "Onyx", "spec": ("asset", "classic", "B")},
    {"name": "Wood", "spec": ("asset", "wood", "W")},
    {"name": "Dark Wood", "spec": ("asset", "wood", "B")},
    {"name": "Sky", "spec": ("tint", (150, 205, 255))},
    {"name": "Blue", "spec": ("tint", (70, 120, 225))},
    {"name": "Mint", "spec": ("tint", (170, 230, 150))},
    {"name": "Green", "spec": ("tint", (55, 150, 70))},
    {"name": "Lavender", "spec": ("tint", (210, 180, 255))},
    {"name": "Purple", "spec": ("tint", (130, 70, 190))},
    {"name": "Rose", "spec": ("tint", (255, 165, 155))},
    {"name": "Red", "spec": ("tint", (200, 55, 55))},
    {"name": "Gold", "spec": ("tint", (230, 185, 70))},
]
white_skin_index = 2  # Wood
black_skin_index = 1  # Onyx

# -----------------------------
# Card images
# -----------------------------
CARD_NAMES = [
    "pawntastic",
    "bishock",
    "rookdemon",
    "windknight",
    "queentum",
    "longlivetheking",

    # Game cards: bought with Ether and played directly.
    "switchero",
    "prophecy",
    "armageddon",
    "thedramatic",
    "capitalism",
    "plague",
    "solo",
    "absoluteprotection",
    "timetraveler",
    "extrablood",
    "chrisma",
    "inzone",
    "nope",
    "communism",
    "gambit",
    "propaganda",
    "ifeelsafe",
    "iguess",
    "gravitystorm",
]

PIECE_POWER_CARDS = [
    "pawntastic",
    "bishock",
    "rookdemon",
    "windknight",
    "queentum",
    "longlivetheking",
]

GENERAL_CARDS = [
    "switchero",
    "prophecy",
    "armageddon",
    "thedramatic",
    "capitalism",
    "plague",
    "solo",
    "absoluteprotection",
    "timetraveler",
    "extrablood",
    "chrisma",
    "inzone",
    "nope",
    "communism",
    "gambit",
    "propaganda",
    "ifeelsafe",
    "iguess",
    "gravitystorm",
]

# Tray order: piece-power cards first, then game cards.
ALL_TRAY_CARDS = PIECE_POWER_CARDS + GENERAL_CARDS

# Which cards are allowed into a new game's decks. Toggled per-card in the
# Catalog screen (ticked = in the game). Starts with every card enabled.
enabled_cards = set(ALL_TRAY_CARDS)

# Which of your pieces a draggable card may be played on. A piece letter means
# only that type; "any" means any of your pieces; "non_king" means any but the
# king. Used to highlight valid targets while a card is being dragged.
CARD_TARGET_TYPE = {
    "pawntastic": "p",
    "bishock": "b",
    "rookdemon": "r",
    "windknight": "n",
    "queentum": "q",
    "longlivetheking": "k",
    "thedramatic": "any",
    "inzone": "inzone",  # any of your pieces except king and queen
    "gambit": "non_king",
}

# "Target" cards are dragged onto one of your pieces; "instant" cards take
# effect as soon as they are played. Every card can also be dragged onto the
# Discard button to throw it away. Each card's activation method is named
# activate_<name>_on_square (target) or activate_<name> (instant).
TARGET_CARDS = {
    "pawntastic", "bishock", "rookdemon", "windknight", "queentum",
    "longlivetheking", "armageddon", "thedramatic", "inzone", "gambit",
    "gravitystorm",
}
INSTANT_CARDS = {
    "switchero", "prophecy", "capitalism", "plague", "solo", "absoluteprotection",
    "timetraveler", "extrablood", "chrisma", "nope", "communism", "propaganda",
    "ifeelsafe", "iguess",
}

def load_card_image(path):
    try:
        return pygame.image.load(path).convert_alpha()
    except (pygame.error, FileNotFoundError):
        return None


# Card art is loaded at full resolution and scaled on demand (cards in the
# panels, the hover preview and the dragged card all use different sizes).
_scaled_card_cache = {}


def get_scaled_card_image(owner, card_name, width, height):
    key = (owner, card_name, width, height)

    if key not in _scaled_card_cache:
        image = card_images.get(owner, {}).get(card_name)

        if image is None:
            _scaled_card_cache[key] = None
        elif (width, height) == image.get_size():
            # Cards are displayed at the art's native size - no resampling.
            _scaled_card_cache[key] = image
        else:
            _scaled_card_cache[key] = pygame.transform.smoothscale(image, (width, height))

    return _scaled_card_cache[key]


# Board encoding: Uppercase = White, Lowercase = Black.
WHITE = "white"
BLACK = "black"

# -----------------------------
# Economy / shop
# -----------------------------
# Ether is the in-game currency.
# Players gain:
# - 1 Ether per tile moved
# - captured piece value in Ether
#
# Cards are played from hand for Ether; they never recharge (deck system).
PIECE_VALUES = {
    "p": 1,
    "n": 3,
    "b": 3,
    "r": 5,
    "q": 9,
    "k": 12,
}

CARD_COSTS = {
    "pawntastic": PIECE_VALUES["p"],
    "windknight": PIECE_VALUES["n"],
    "bishock": PIECE_VALUES["b"],
    "rookdemon": PIECE_VALUES["r"],
    "queentum": PIECE_VALUES["q"],
    "longlivetheking": PIECE_VALUES["k"],

    # Game cards
    "switchero": 20,
    "prophecy": 40,
    "armageddon": 30,
    "thedramatic": 20,
    "capitalism": 100,
    "plague": 60,
    "solo": 20,
    "absoluteprotection": 20,
    "timetraveler": 20,
    "extrablood": 15,
    "chrisma": 15,
    "inzone": 30,
    "nope": 15,
    "communism": 20,
    "gambit": 10,
    "propaganda": 30,
    "ifeelsafe": 15,
    "iguess": 40,
    "gravitystorm": 30,
}

ABILITY_CARDS = {
    "pawntastic",
    "bishock",
    "rookdemon",
    "windknight",
    "queentum",
    "longlivetheking",
}

GAME_CARDS = {
    "switchero",
    "prophecy",
    "armageddon",
    "thedramatic",
    "capitalism",
    "plague",
    "solo",
    "absoluteprotection",
    "timetraveler",
    "extrablood",
    "chrisma",
    "inzone",
    "nope",
    "communism",
    "gambit",
    "propaganda",
    "ifeelsafe",
    "iguess",
    "gravitystorm",
}

card_images = {
    WHITE: {},
    BLACK: {},
}

for card_name in CARD_NAMES:
    card_images[WHITE][card_name] = load_card_image(os.path.join("cards", f"{card_name}_white.png"))
    card_images[BLACK][card_name] = load_card_image(os.path.join("cards", f"{card_name}_black.png"))

# Display name, fallback art color, one-line description (hover preview).
CARD_INFO = {
    "pawntastic": ("Pawntastic", (40, 90, 40), "A pawn may charge 1-4 squares forward."),
    "bishock": ("Bishock", (80, 40, 100), "A bishop zaps every piece on its diagonals."),
    "rookdemon": ("Rookdemon", (120, 40, 20), "A rook leaves a burning trail for 2 moves."),
    "windknight": ("Windknight", (30, 90, 85), "A knight moves twice in one turn."),
    "queentum": ("Queentum", (70, 35, 105), "The queen teleports to any legal square."),
    "longlivetheking": ("LongLiveTheKing", (105, 80, 25), "The king escapes to a corner and spawns pawns."),
    "switchero": ("Switchero", (40, 65, 130), "Swap ownership of every piece on the board."),
    "prophecy": ("The Prophecy", (120, 95, 30), "All of your pawns become queens."),
    "armageddon": ("Armageddon", (120, 45, 35), "3x3 blast destroys pieces and leaves fire."),
    "thedramatic": ("TheDramatic", (95, 45, 95), "The marked piece kills whatever captures it."),
    "capitalism": ("Capitalism", (45, 130, 65), "Pay 100 Ether: instant win."),
    "plague": ("Plague", (65, 110, 45), "One random enemy piece dies each of your turns."),
    "solo": ("Solo", (45, 45, 45), "Win instantly if only your king remains."),
    "absoluteprotection": ("AbsProtection", (35, 95, 140), "Your pieces cannot be captured for one turn."),
    "timetraveler": ("TimeTraveler", (40, 80, 140), "Rewind the board 3 turns."),
    "extrablood": ("ExtraBlood", (120, 25, 25), "Passive: capture Ether is doubled."),
    "chrisma": ("Chrisma", (135, 45, 115), "Convert enemy pieces around your king."),
    "inzone": ("InZone", (150, 40, 35), "Chain up to 5 captures; the piece dies after."),
    "nope": ("Nope", (60, 60, 110), "Cancel the opponent's last card; kills the checker if you are in check."),
    "communism": ("Communism", (150, 30, 30), "Split all Ether evenly between both players."),
    "gambit": ("Gambit", (110, 80, 30), "Sacrifice as many of your pieces as you want for double value each."),
    "propaganda": ("Propaganda", (120, 60, 130), "Each of your turns: 50% to convert an enemy piece."),
    "ifeelsafe": ("I Feel Safe", (40, 110, 120), "Passive: end of turn, +3 Ether per piece by your king."),
    "iguess": ("I Guess", (90, 90, 100), "Permanently take 2 extra moves each turn."),
    "gravitystorm": ("Gravity Storm", (50, 40, 80), "Every piece falls toward the chosen point until it hits a piece or wall."),
}


def initial_board():
    return [
        ["r", "n", "b", "q", "k", "b", "n", "r"],
        ["p", "p", "p", "p", "p", "p", "p", "p"],
        [None, None, None, None, None, None, None, None],
        [None, None, None, None, None, None, None, None],
        [None, None, None, None, None, None, None, None],
        [None, None, None, None, None, None, None, None],
        ["P", "P", "P", "P", "P", "P", "P", "P"],
        ["R", "N", "B", "Q", "K", "B", "N", "R"],
    ]



def board_center(row, col):
    x, y = board_to_screen(row, col)
    return (x + SQUARE_W // 2, y + SQUARE_H // 2)


def add_animation(kind, squares=None, text="", color=(255, 220, 120), frames=30, extra=None):
    if squares is None:
        squares = []

    animations.append({
        "kind": kind,
        "squares": list(squares),
        "text": text,
        "color": color,
        "frames": frames,
        "max_frames": frames,
        "extra": extra or {},
    })


# --- Card draw / discard flight animations (screen-space) -------------------
def _deck_pile_pos():
    b = get_action_buttons()["end_turn"]
    return (b.centerx, b.top - 4)


def _discard_pile_pos():
    b = get_action_buttons()["discard"]
    return (b.centerx, b.top - 4)


def _hand_center_pos():
    return (SCREEN_WIDTH // 2, TRAY_Y + TRAY_HEIGHT // 2)


def spawn_draw_fly(target, index, card_name):
    # A face-down card flies from the deck pile into its hand slot, staggered.
    add_animation("card_fly", frames=16, extra={
        "from": _deck_pile_pos(), "to": target,
        "owner": None, "card": None, "reveal": card_name, "delay": index * 4,
    })


def cards_in_flight():
    # Names of cards still flying in from the deck (hidden in the hand until they land).
    return {a["extra"].get("reveal") for a in animations
            if a["kind"] == "card_fly" and a["extra"].get("reveal")}


def animate_initial_hand():
    # Fly the already-dealt starting hand in from the deck, one card per slot.
    rects = get_card_rects()
    for i, card in enumerate(game.hand[view_color()]):
        r = rects.get(card)
        target = r.center if r is not None else _hand_center_pos()
        spawn_draw_fly(target, i, card)


def spawn_discard_fly(from_center, owner, card_name):
    # The played/discarded card flies from its hand slot to the discard pile.
    add_animation("card_fly", frames=15, extra={
        "from": from_center, "to": _discard_pile_pos(),
        "owner": owner, "card": card_name, "delay": 0,
    })


# A handful of faint card images drift across the background with random
# position, velocity, rotation and spin.
FLOATING_CARD_COUNT = 30
FLOATING_CARD_ALPHA = 200
_floating_cards = []
_last_float_ticks = [0]


def init_floating_cards():
    card_w = int(SCREEN_HEIGHT * 0.13)
    card_h = int(card_w * CARD_ASPECT)
    names = [c for c in ALL_TRAY_CARDS if card_images[WHITE].get(c) is not None]
    if not names:
        return

    # Spread starting positions over a grid so the cards stay evenly distributed
    # rather than clustering; each sits at its cell center with a little jitter.
    cols = max(1, math.ceil(math.sqrt(FLOATING_CARD_COUNT * SCREEN_WIDTH / SCREEN_HEIGHT)))
    rows = max(1, math.ceil(FLOATING_CARD_COUNT / cols))
    cell_w = SCREEN_WIDTH / cols
    cell_h = SCREEN_HEIGHT / rows

    for i in range(FLOATING_CARD_COUNT):
        name = random.choice(names)
        owner = random.choice((WHITE, BLACK))
        base = pygame.transform.smoothscale(card_images[owner][name], (card_w, card_h)).convert_alpha()
        # Bake the faint alpha in so rotation keeps it subtle.
        base.fill((255, 255, 255, FLOATING_CARD_ALPHA), special_flags=pygame.BLEND_RGBA_MULT)

        col = i % cols
        row = i // cols
        cx = (col + 0.5) * cell_w + random.uniform(-cell_w * 0.3, cell_w * 0.3)
        cy = (row + 0.5) * cell_h + random.uniform(-cell_h * 0.3, cell_h * 0.3)

        _floating_cards.append({
            "base": base,
            "x": cx,
            "y": cy,
            "vx": random.uniform(-22, 22),
            "vy": random.uniform(-22, 22),
            "angle": random.uniform(0, 360),
            "spin": random.uniform(-18, 18),
            "_ra": None,   # angle of the cached rotated surface
            "_rs": None,   # cached rotated surface
        })


# Snap rotation to a fine step and cache the rotated frame. The step is small
# enough that the spin looks continuous, but it still avoids a re-rotate on
# frames where the angle barely moved (and for nearly-still cards).
FLOAT_ANGLE_STEP = 0.5


def draw_floating_cards():
    if not _floating_cards:
        init_floating_cards()

    now = pygame.time.get_ticks()
    if _last_float_ticks[0]:
        dt = max(0.0, min(0.05, (now - _last_float_ticks[0]) / 1000.0))
    else:
        dt = 1 / 60
    _last_float_ticks[0] = now

    margin = int(SCREEN_HEIGHT * 0.18)
    for card in _floating_cards:
        card["x"] += card["vx"] * dt
        card["y"] += card["vy"] * dt
        card["angle"] = (card["angle"] + card["spin"] * dt) % 360

        # Wrap around the screen edges (with a margin so they drift off fully).
        if card["x"] < -margin:
            card["x"] = SCREEN_WIDTH + margin
        elif card["x"] > SCREEN_WIDTH + margin:
            card["x"] = -margin
        if card["y"] < -margin:
            card["y"] = SCREEN_HEIGHT + margin
        elif card["y"] > SCREEN_HEIGHT + margin:
            card["y"] = -margin

        # Rotate with antialiasing (rotozoom), but only when the snapped angle
        # actually changes - the cached frame is reused on the frames between.
        bucket = round(card["angle"] / FLOAT_ANGLE_STEP) * FLOAT_ANGLE_STEP
        if card["_rs"] is None or bucket != card["_ra"]:
            card["_ra"] = bucket
            card["_rs"] = pygame.transform.rotozoom(card["base"], bucket, 1.0)
        rotated = card["_rs"]
        screen.blit(rotated, rotated.get_rect(center=(round(card["x"]), round(card["y"]))))


BG_DIM = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
BG_DIM.fill((0, 0, 0, 120))  # gameplay backdrop dim; board/pieces/cards draw on top


def draw_background():
    if BACKGROUND_IMAGE is not None:
        screen.blit(BACKGROUND_IMAGE, (0, 0))
    else:
        screen.fill((0, 0, 0))

    draw_floating_cards()
    # Darken the backdrop so the board and hand (drawn afterwards) stand out.
    screen.blit(BG_DIM, (0, 0))


def draw_animations():
    finished = []

    for anim in animations:
        progress = 1 - (anim["frames"] / anim["max_frames"])
        alpha = max(0, int(240 * (1 - progress)))
        color = anim["color"]

        if anim["kind"] == "move_line" and len(anim["squares"]) >= 2:
            start = board_center(*anim["squares"][0])
            end = board_center(*anim["squares"][1])
            surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            width = max(4, SQUARE_SIZE // 13)
            pygame.draw.line(surface, (*color, alpha), start, end, width)

            # Travelling orb on the movement path.
            ox = int(start[0] + (end[0] - start[0]) * progress)
            oy = int(start[1] + (end[1] - start[1]) * progress)
            pygame.draw.circle(surface, (*color, alpha), (ox, oy), max(6, SQUARE_SIZE // 9))
            pygame.draw.circle(surface, (255, 255, 255, alpha), (ox, oy), max(3, SQUARE_SIZE // 18))
            screen.blit(surface, (0, 0))

        elif anim["kind"] in ["burst", "blast", "shield", "magic", "meteor", "coin", "poison"]:
            surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

            for row, col in anim["squares"]:
                cx, cy = board_center(row, col)
                radius = int(SQUARE_SIZE * (0.22 + progress * 0.95))
                width = max(2, int(8 * (1 - progress)))
                pygame.draw.circle(surface, (*color, alpha), (cx, cy), radius, width)

                if anim["kind"] in ["blast", "meteor"]:
                    rect = pygame.Rect(0, 0, SQUARE_W, SQUARE_H)
                    rect.center = (cx, cy)
                    pygame.draw.rect(surface, (*color, max(38, alpha // 3)), rect)

                    # Impact rays.
                    for i in range(8):
                        angle = (math.pi * 2 * i / 8) + progress
                        x2 = cx + int(math.cos(angle) * radius * 1.2)
                        y2 = cy + int(math.sin(angle) * radius * 1.2)
                        pygame.draw.line(surface, (*color, alpha), (cx, cy), (x2, y2), 2)

                elif anim["kind"] == "shield":
                    shield_rect = pygame.Rect(0, 0, int(SQUARE_SIZE * 0.72), int(SQUARE_SIZE * 0.72))
                    shield_rect.center = (cx, cy)
                    pygame.draw.rect(surface, (90, 210, 255, max(55, alpha // 3)), shield_rect, 3, border_radius=8)
                    pygame.draw.circle(surface, (90, 210, 255, max(35, alpha // 4)), (cx, cy), int(SQUARE_SIZE * 0.47), 2)

                elif anim["kind"] == "coin":
                    coin_y = cy - int(progress * 36)
                    pygame.draw.circle(surface, (255, 220, 90, alpha), (cx, coin_y), max(7, SQUARE_SIZE // 10))
                    pygame.draw.circle(surface, (80, 45, 5, alpha), (cx, coin_y), max(7, SQUARE_SIZE // 10), 2)

                elif anim["kind"] == "poison":
                    for i in range(5):
                        px = cx + int(math.sin(progress * 8 + i) * SQUARE_SIZE * 0.25)
                        py = cy - int(progress * SQUARE_SIZE * 0.5) + i * 8
                        pygame.draw.circle(surface, (120, 230, 80, max(30, alpha)), (px, py), max(3, SQUARE_SIZE // 18))

                if anim["text"]:
                    txt = tiny_font.render(anim["text"], True, (*color,))
                    txt.set_alpha(alpha)
                    txt_rect = txt.get_rect(center=(cx, cy - int(progress * 38)))
                    surface.blit(txt, txt_rect)

            screen.blit(surface, (0, 0))

        elif anim["kind"] == "banner":
            surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay_alpha = max(0, int(125 * (1 - progress)))
            surface.fill((0, 0, 0, overlay_alpha))

            text_surface = small_font.render(anim["text"], True, color)
            banner_w = min(max(text_surface.get_width() + 70, 360), SCREEN_WIDTH - 120)
            banner_h = 70
            banner = pygame.Rect(0, 0, banner_w, banner_h)
            banner.center = (SCREEN_WIDTH // 2, max(85, BOARD_Y + BOARD_H // 2))

            pygame.draw.rect(surface, (20, 14, 8, alpha), banner, border_radius=16)
            pygame.draw.rect(surface, (*GOLD, alpha), banner, 3, border_radius=16)
            text_surface.set_alpha(alpha)
            rect = text_surface.get_rect(center=banner.center)
            surface.blit(text_surface, rect)
            screen.blit(surface, (0, 0))

        elif anim["kind"] == "piece_drop":
            # A carried piece flying back to its square (snapback).
            extra = anim["extra"]
            row, col = extra["square"]
            x, y = board_to_screen(row, col)
            target = (x + SQUARE_W // 2, y + SQUARE_H - SQUARE_H // 12)
            start = extra["from_pos"]

            t = progress * progress  # accelerate toward the square, like gravity
            pos = (
                int(start[0] + (target[0] - start[0]) * t),
                int(start[1] + (target[1] - start[1]) * t),
            )

            piece_surface = get_piece_surface(extra["piece"], lifted=True)
            rect = piece_surface.get_rect(midbottom=pos)
            screen.blit(piece_surface, rect)

        elif anim["kind"] == "meteor_sprite" and METEOR_FRAMES:
            row, col = anim["extra"]["square"]
            x, y = board_to_screen(row, col)
            # The strike covers a 3x3 area; everything anchors to its bottom.
            impact = (x + SQUARE_W // 2, y + SQUARE_H // 2 + round(SQUARE_H * 1.5))

            fall_part = 0.4
            if progress < fall_part:
                # The doomed pieces are still standing while the meteor falls;
                # they vanish under the explosion the instant it lands.
                for pr, pc, piece in sorted(anim["extra"].get("destroyed_pieces", [])):
                    px, py = board_to_screen(pr, pc)
                    ghost = get_piece_surface(piece)
                    screen.blit(ghost, ghost.get_rect(
                        midbottom=(px + SQUARE_W // 2, py + SQUARE_H - SQUARE_H // 12)
                    ))

                t = progress / fall_part
                fall_frames = METEOR_FRAMES[:METEOR_FALL_COUNT]
                frame = fall_frames[min(len(fall_frames) - 1, int(t * len(fall_frames)))]
                start_y = impact[1] - BOARD_H
                pos_y = round(start_y + (impact[1] - start_y) * t * t)
                screen.blit(frame, frame.get_rect(midbottom=(impact[0], pos_y)))
            else:
                # The moment the meteor lands: lay down the fire tiles so the
                # burning starts after the strike, not before it.
                if not anim["extra"].get("fire_started"):
                    game.add_fire_tiles(anim["extra"].get("fire_squares", []))
                    anim["extra"]["fire_started"] = True

                impact_frames = METEOR_FRAMES[METEOR_FALL_COUNT:]
                t = (progress - fall_part) / (1 - fall_part)
                index = min(len(impact_frames) - 1, int(t * len(impact_frames)))
                frame = impact_frames[index]

                # Fade the final embers frame out.
                if index == len(impact_frames) - 1:
                    sub = t * len(impact_frames) - index
                    frame.set_alpha(round(255 * (1 - sub)))

                screen.blit(frame, frame.get_rect(midbottom=impact))
                frame.set_alpha(255)

        elif anim["kind"] == "piece_land":
            # Impact squash: widest and flattest right after touching down.
            extra = anim["extra"]
            row, col = extra["square"]
            x, y = board_to_screen(row, col)

            squash = 1 - progress
            piece_surface = get_piece_surface(extra["piece"])
            w = round(piece_surface.get_width() * (1 + 0.18 * squash))
            h = round(piece_surface.get_height() * (1 - 0.22 * squash))
            squashed = pygame.transform.scale(piece_surface, (w, h))
            rect = squashed.get_rect(midbottom=(x + SQUARE_W // 2, y + SQUARE_H - SQUARE_H // 12))
            screen.blit(squashed, rect)

        elif anim["kind"] == "teleport":
            extra = anim["extra"]
            piece = extra["piece"]
            fr, fc = extra["from"]
            tr, tc = extra["to"]
            fx, fy = board_to_screen(fr, fc)
            tx, ty = board_to_screen(tr, tc)
            inner = (200, 120, 255)
            outer = (150, 220, 255)

            def beam(cx, top, amount):
                # A vertical pillar of light, brightest at full amount.
                if amount <= 0:
                    return
                w = max(4, int(SQUARE_W * 0.5 * amount))
                pillar = pygame.Surface((w, SQUARE_H * 2), pygame.SRCALPHA)
                pillar.fill((*outer, int(120 * amount)))
                screen.blit(pillar, pillar.get_rect(midtop=(cx, top - SQUARE_H)))

            def rings(cx, cy, radius, alpha):
                for k, color in enumerate((inner, outer)):
                    rad = radius - k * max(3, SQUARE_W // 16)
                    if rad > 1:
                        ring = pygame.Surface((rad * 2 + 4, rad * 2 + 4), pygame.SRCALPHA)
                        pygame.draw.circle(ring, (*color, alpha), (rad + 2, rad + 2), rad, max(2, SQUARE_W // 24))
                        screen.blit(ring, ring.get_rect(center=(cx, cy)))

            # Phase 1 (dematerialize at origin): queen shrinks into a beam.
            if progress < 0.55:
                t = progress / 0.55
                fcx = fx + SQUARE_W // 2
                ghost = get_piece_surface(piece)
                gw = max(1, round(ghost.get_width() * (1 - 0.6 * t)))
                gh = max(1, round(ghost.get_height() * (1 - 0.2 * t)))
                ghost = pygame.transform.scale(ghost, (gw, gh))
                ghost.set_alpha(int(255 * (1 - t)))
                screen.blit(ghost, ghost.get_rect(midbottom=(fcx, fy + SQUARE_H - SQUARE_H // 12)))
                beam(fcx, fy, 1 - t)
                rings(fcx, fy + SQUARE_H // 2, int(SQUARE_W * (0.55 - 0.45 * t)), int(220 * (1 - t)))

            # Phase 2 (materialize at destination): beam forms into the queen.
            if progress > 0.4:
                t = (progress - 0.4) / 0.6
                tcx = tx + SQUARE_W // 2
                beam(tcx, ty, 1 - t)
                queen = get_piece_surface(piece)
                qh = max(1, round(queen.get_height() * (0.4 + 0.6 * t)))
                grown = pygame.transform.scale(queen, (queen.get_width(), qh))
                grown.set_alpha(int(255 * t))
                screen.blit(grown, grown.get_rect(midbottom=(tcx, ty + SQUARE_H - SQUARE_H // 12)))
                rings(tcx, ty + SQUARE_H // 2, int(SQUARE_W * 0.55 * (1 - t)), int(220 * t))

        elif anim["kind"] == "slide":
            # A piece gliding from its old square to its new one (Gravity Storm).
            ex = anim["extra"]
            fr, fc = ex["from"]
            tr, tc = ex["to"]
            fx, fy = board_to_screen(fr, fc)
            tx, ty = board_to_screen(tr, tc)
            surf = get_piece_surface(ex["piece"])

            if ex.get("delay", 0) > 0:
                # Waiting its turn: sit still at the starting square. (Its real
                # board square is hidden, so it must be drawn here meanwhile.)
                ex["delay"] -= 1
                rect = surf.get_rect(midbottom=(fx + SQUARE_W // 2, fy + SQUARE_H - SQUARE_H // 12))
                screen.blit(surf, rect)
                continue

            ease = 1 - (1 - progress) ** 2  # ease-out toward the centre
            cx = fx + (tx - fx) * ease
            cy = fy + (ty - fy) * ease
            rect = surf.get_rect(midbottom=(cx + SQUARE_W // 2, cy + SQUARE_H - SQUARE_H // 12))
            screen.blit(surf, rect)

        elif anim["kind"] == "card_fly":
            ex = anim["extra"]
            if ex.get("delay", 0) > 0:
                ex["delay"] -= 1
                continue  # held until its stagger delay elapses

            t = 1 - anim["frames"] / anim["max_frames"]
            te = 1 - (1 - t) ** 2  # ease-out toward the target
            fx, fy = ex["from"]
            tx, ty = ex["to"]
            cx = int(fx + (tx - fx) * te)
            cy = int(fy + (ty - fy) * te)

            w = max(40, int(CARD_WIDTH * 0.5))
            h = max(56, int(CARD_HEIGHT * 0.5))

            # Fade in at the start. Discards fade out as they reach the pile;
            # draws stay opaque so they "become" the card landing in the hand.
            is_draw = ex.get("card") is None
            if t < 0.2:
                a = t / 0.2
            elif (not is_draw) and t > 0.7:
                a = max(0.0, (1 - t) / 0.3)
            else:
                a = 1.0
            alpha = int(255 * a)

            if ex.get("card"):
                face = get_card_face(ex["owner"], ex["card"], (w, h), False, True).copy()
                face.set_alpha(alpha)
                screen.blit(face, face.get_rect(center=(cx, cy)))
            else:
                back = pygame.Surface((w, h), pygame.SRCALPHA)
                pygame.draw.rect(back, (28, 24, 40, alpha), back.get_rect(), border_radius=6)
                pygame.draw.rect(back, (*GOLD, alpha), back.get_rect(), 2, border_radius=6)
                pygame.draw.circle(back, (*GOLD, alpha), (w // 2, h // 2), w // 5, 2)
                screen.blit(back, back.get_rect(center=(cx, cy)))

        anim["frames"] -= 1
        if anim["frames"] <= 0:
            finished.append(anim)

    for anim in finished:
        animations.remove(anim)

        # Drag-and-drop chain: snapback flight -> impact squash -> dust ring.
        if anim["kind"] == "piece_drop":
            add_animation("piece_land", frames=8, extra=anim["extra"])
        elif anim["kind"] == "piece_land":
            add_animation("burst", squares=[anim["extra"]["square"]], color=(225, 205, 150), frames=14)



class GameState:
    def __init__(self):
        self.board = initial_board()
        self.turn = WHITE
        self.selected = None
        self.legal_moves_for_selected = []

        # Cheat mode (toggle with C): unlimited Ether for both players and
        # the turn never passes automatically; T passes it manually.
        self.cheat_mode = False

        # Card system (Slay-the-Spire style): each player has a deck, a hand,
        # and a discard pile. Cards are played from hand for Ether and never
        # recharge - they go to the discard pile. Players draw only by
        # discarding (drawing that many back on their next turn).
        self.active_card = None
        self.active_card_owner = None
        self.deck = {WHITE: [], BLACK: []}
        self.hand = {WHITE: [], BLACK: []}
        self.discard = {WHITE: [], BLACK: []}
        self.pending_draw = {WHITE: 0, BLACK: 0}
        self.discard_marks = set()  # cards in the current hand marked to discard

        # Each player may discard at most MAX_DISCARDS cards across the whole
        # game. Discarding is done by dragging a card onto the Discard button.
        self.discards_used = {WHITE: 0, BLACK: 0}

        # Running game log shown on the right: chess moves and cards played.
        # Each entry is (color, kind, text) where kind is "move" or "card".
        self.move_log = []

        # Economy
        self.ether = {
            WHITE: 0,
            BLACK: 0,
        }

        # Windknight state:
        # The selected knight must move twice before the turn changes.
        self.windknight_square = None
        self.windknight_moves_remaining = 0

        # Fire / Rookdemon system
        self.fire_tiles = {}
        self.rookdemon_rooks = {}

        # TheDramatic system:
        # If a marked piece is captured, the capturing piece dies too.
        self.dramatic_pieces = set()

        # Plague system:
        # If a color is active here, at the start of that player's turn,
        # one random enemy non-king piece dies.
        self.plague_active = set()

        # AbsoluteProtection system:
        # If a color is active here, its pieces cannot be captured for
        # the opponent's next turn. The attacking piece dies instead.
        self.absolute_protection_active = set()

        # ExtraBlood passive:
        # Captures by these players give double capture Ether.
        self.extra_blood_active = set()

        # InZone system:
        # A selected piece may keep capturing. When the streak ends, it dies.
        self.inzone_square = None
        self.inzone_captures = 0

        # Propaganda: at the start of each of these players' turns there is a
        # 50% chance to convert one enemy non-king piece.
        self.propaganda_active = set()

        # I Feel Safe: at the end of these players' turns, gain 3 Ether per
        # friendly piece adjacent to their king.
        self.ifeelsafe_active = set()

        # I Guess: permanent extra moves per turn (added to the 1 base move).
        self.bonus_turns = {WHITE: 0, BLACK: 0}
        self.pending_extra_moves = {WHITE: 0, BLACK: 0}

        # A turn ends only when the player makes their chess move(s) AND presses
        # End Turn. moves_made_this_turn tracks how many chess moves were made.
        self.moves_made_this_turn = 0

        # Piece-power abilities (Pawntastic, Queentum, Windknight, InZone) do not
        # use up the player's normal chess move. This records that the player did
        # act this turn, so they may End Turn even if they only used an ability.
        self.ability_used_this_turn = False

        # Nope: snapshot of the state just before each player's last game card,
        # so the opponent can cancel it.
        self.card_undo = {WHITE: None, BLACK: None}

        # Guards start-of-turn effects so they fire once per real turn (not on
        # each extra move within an "I Guess" multi-move turn).
        self._effects_applied_for = None

        # TimeTraveler system:
        # Save board/piece states before real turn actions.
        self.history = []

        # Castling rights
        self.white_king_moved = False
        self.black_king_moved = False
        self.white_left_rook_moved = False
        self.white_right_rook_moved = False
        self.black_left_rook_moved = False
        self.black_right_rook_moved = False

        self.en_passant_target = None

        self.game_over = False
        self.winner_message = None
        self.status_message = "White to move"

        self.deal_starting_hands()

    # -----------------------------
    # Deck / hand / discard
    # -----------------------------
    HAND_START = 5
    MAX_DISCARDS = 5  # per player, for the whole game

    # Cards whose move is a piece "ability" and so does not consume the
    # player's normal chess move for the turn.
    ABILITY_CARDS = ("pawntastic", "queentum", "windknight", "inzone")

    def deal_starting_hands(self):
        # Only the cards ticked in the Catalog are dealt into the decks.
        active = [c for c in ALL_TRAY_CARDS if c in enabled_cards]
        for color in (WHITE, BLACK):
            self.deck[color] = list(active)
            random.shuffle(self.deck[color])
            self.hand[color] = []
            self.discard[color] = []
            self.pending_draw[color] = 0
            self.draw_cards(color, self.HAND_START)

    def draw_cards(self, color, n):
        # Only animate draws for the live game and the player whose turn it is.
        live = globals().get("game") is self and color == self.turn
        drawn_cards = []
        for _ in range(n):
            if not self.deck[color]:
                # Reshuffle the discard pile into the deck.
                self.deck[color] = self.discard[color]
                self.discard[color] = []
                random.shuffle(self.deck[color])
            if not self.deck[color]:
                break  # no cards anywhere
            card = self.deck[color].pop()
            self.hand[color].append(card)
            drawn_cards.append(card)

        # Fly each new card from the deck pile to its final slot in the hand.
        if live and drawn_cards:
            rects = get_card_rects()
            for i, card in enumerate(drawn_cards):
                r = rects.get(card)
                target = r.center if r is not None else _hand_center_pos()
                spawn_draw_fly(target, i, card)

    def spend_card(self, card_name):
        display = CARD_INFO.get(card_name, (card_name,))[0]

        if card_name not in self.hand[self.turn]:
            self.status_message = f"{display} is not in your hand."
            return False

        cost = CARD_COSTS.get(card_name, 0)
        if self.ether[self.turn] < cost:
            self.status_message = f"Not enough Ether for {display}. Need {cost}, have {self.ether[self.turn]}."
            return False

        self.save_history()
        self.card_undo[self.turn] = copy.deepcopy(self.history[-1])
        self.ether[self.turn] -= cost

        # Capture the card's hand position to animate it flying to the pile.
        from_center = None
        if globals().get("game") is self:
            r = get_card_rects().get(card_name)
            if r is not None:
                from_center = r.center

        self.hand[self.turn].remove(card_name)
        self.discard[self.turn].append(card_name)
        self.discard_marks.discard(card_name)
        self.log_event(self.turn, "card", display)
        if from_center is not None:
            spawn_discard_fly(from_center, self.turn, card_name)
        return True

    def discard_card(self, card_name):
        # Drag a card onto the Discard button to throw it away and draw a
        # replacement. Each player is limited to MAX_DISCARDS for the game.
        if self.game_over:
            return False

        display = CARD_INFO.get(card_name, (card_name,))[0]

        if card_name not in self.hand[self.turn]:
            self.status_message = f"{display} is not in your hand."
            return False

        if self.discards_used[self.turn] >= self.MAX_DISCARDS:
            self.status_message = f"No discards left (limit {self.MAX_DISCARDS})."
            return False

        # Capture the card's hand position to animate it flying to the pile.
        from_center = None
        if globals().get("game") is self:
            r = get_card_rects().get(card_name)
            if r is not None:
                from_center = r.center

        self.hand[self.turn].remove(card_name)
        self.discard[self.turn].append(card_name)
        self.discard_marks.discard(card_name)
        self.discards_used[self.turn] += 1

        if from_center is not None:
            spawn_discard_fly(from_center, self.turn, card_name)

        # Draw a replacement so the hand stays full.
        self.draw_cards(self.turn, 1)

        left = self.MAX_DISCARDS - self.discards_used[self.turn]
        self.status_message = f"Discarded {display}. {left} discard(s) left."
        return True

    def finish_card(self, message):
        # A free card effect resolves without ending the turn.
        msg = message.replace("{player}", self.turn.capitalize())
        add_animation("banner", text=msg, color=GOLD, frames=42)
        self.active_card = None
        self.active_card_owner = None
        self.selected = None
        self.legal_moves_for_selected = []
        self.update_status()
        if not self.is_in_check(self.turn) and not self.game_over:
            self.status_message = msg

    def end_turn(self):
        if self.game_over:
            return

        # A special card move in progress must be finished first.
        if self.active_card in ("pawntastic", "queentum", "windknight", "inzone"):
            self.status_message = "Finish the active card move first."
            return

        # The player must act before the turn can pass: either make a chess move
        # or use a piece ability (abilities do not consume the chess move).
        if (
            self.moves_made_this_turn < 1
            and not self.ability_used_this_turn
            and self.has_any_legal_moves(self.turn)
        ):
            self.status_message = "Move a piece before ending your turn."
            return

        self.discard_marks = set()
        self.award_check_bonus_for_player(self.turn)
        self.decay_fire_tiles()
        self.active_card = None
        self.active_card_owner = None
        self.pass_turn()
        self.selected = None
        self.legal_moves_for_selected = []
        self.start_turn_effects()
        self.update_status()

    def clone(self):
        return copy.deepcopy(self)

    def piece_color(self, piece):
        if piece is None:
            return None
        return WHITE if piece.isupper() else BLACK

    def enemy_color(self, color):
        return BLACK if color == WHITE else WHITE

    def pieces_around_king(self, color):
        king = self.find_king(color)
        if king is None:
            return 0
        kr, kc = king
        count = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = kr + dr, kc + dc
                if self.in_bounds(nr, nc) and self.is_friend(nr, nc, color):
                    count += 1
        return count

    def moves_allowed(self):
        # 1 base chess move per turn, plus any granted by "I Guess".
        return 1 + self.bonus_turns.get(self.turn, 0)

    def finish_chess_move(self):
        # A chess move is made but the turn does NOT pass - the player must
        # press End Turn to hand over (after they have moved).
        self.moves_made_this_turn += 1
        self.active_card = None
        self.active_card_owner = None
        self.windknight_square = None
        self.windknight_moves_remaining = 0
        self.inzone_square = None
        self.inzone_captures = 0
        self.selected = None
        self.legal_moves_for_selected = []

        if self.moves_made_this_turn < self.moves_allowed():
            self.status_message = f"{self.turn.capitalize()} may move again, or press END TURN."
        else:
            self.status_message = f"{self.turn.capitalize()} moved. Press END TURN."

    def finish_ability_move(self):
        # A piece ability (Pawntastic / Queentum / Windknight / InZone) resolves
        # WITHOUT consuming the player's normal chess move, so moves_made is left
        # untouched and the player may still move a piece this turn.
        self.active_card = None
        self.active_card_owner = None
        self.windknight_square = None
        self.windknight_moves_remaining = 0
        self.inzone_square = None
        self.inzone_captures = 0
        self.selected = None
        self.legal_moves_for_selected = []
        self.ability_used_this_turn = True

        if self.moves_made_this_turn < self.moves_allowed():
            self.status_message = f"{self.turn.capitalize()} used an ability. You may still move a piece, or press END TURN."
        else:
            self.status_message = f"{self.turn.capitalize()} used an ability. Press END TURN."

    def _finish_move(self):
        # Abilities do not use up the chess move; ordinary card/plain moves do.
        if self.active_card in self.ABILITY_CARDS:
            self.finish_ability_move()
        else:
            self.finish_chess_move()

    def pass_turn(self):
        # In cheat mode the turn is frozen so one player can act repeatedly.
        if self.cheat_mode:
            return

        # "I Feel Safe": end-of-turn Ether for a fortified king.
        if self.turn in self.ifeelsafe_active:
            bonus = 3 * self.pieces_around_king(self.turn)
            if bonus > 0:
                self.add_ether(self.turn, bonus)
                king = self.find_king(self.turn)
                if king is not None:
                    add_animation("coin", squares=[king], text=f"+{bonus}", color=(120, 230, 255), frames=32)

        self.turn = self.enemy_color(self.turn)
        self.moves_made_this_turn = 0
        self.ability_used_this_turn = False

    def in_bounds(self, row, col):
        return 0 <= row < 8 and 0 <= col < 8

    def is_empty(self, row, col):
        return self.board[row][col] is None

    def is_enemy(self, row, col, color):
        piece = self.board[row][col]
        return piece is not None and self.piece_color(piece) != color

    def is_friend(self, row, col, color):
        piece = self.board[row][col]
        return piece is not None and self.piece_color(piece) == color

    # -----------------------------
    # Economy / shop helpers
    # -----------------------------
    def get_piece_value(self, piece):
        if piece is None:
            return 0
        return PIECE_VALUES.get(piece.lower(), 0)

    def get_move_distance(self, piece, from_square, to_square):
        from_row, from_col = from_square
        to_row, to_col = to_square

        dr = abs(to_row - from_row)
        dc = abs(to_col - from_col)

        if piece is None:
            return 0

        # Knights move in an L shape: count the 3 grid steps.
        if piece.lower() == "n":
            return dr + dc

        # Sliding pieces, pawns, king movement, castling, and teleporting
        # use the largest board-axis distance.
        return max(dr, dc)

    def add_ether(self, color, amount):
        if amount <= 0:
            return
        self.ether[color] += amount

    def start_turn_effects(self):
        # Run once per real turn, not on each extra "I Guess" move.
        if self._effects_applied_for == self.turn:
            return
        self._effects_applied_for = self.turn

        # Refill the hand back up to the starting size each turn, replacing any
        # cards played or discarded, so the player always begins with a full hand.
        self.pending_draw[self.turn] = 0
        deficit = self.HAND_START - len(self.hand[self.turn])
        if deficit > 0:
            self.draw_cards(self.turn, deficit)

        # AbsoluteProtection expires when the protected player gets the turn back.
        if self.turn in self.absolute_protection_active:
            self.absolute_protection_active.remove(self.turn)

        # Plague triggers at the start of the plagued player's turns.
        if self.turn in self.plague_active:
            enemy = self.enemy_color(self.turn)
            possible_targets = []

            for row in range(8):
                for col in range(8):
                    piece = self.board[row][col]

                    if piece is None:
                        continue

                    if self.piece_color(piece) != enemy:
                        continue

                    if piece.lower() == "k":
                        continue

                    # Absolute protection blocks plague death.
                    if enemy in self.absolute_protection_active:
                        continue

                    possible_targets.append((row, col))

            if possible_targets:
                row, col = random.choice(possible_targets)
                killed_piece = self.board[row][col]
                self.board[row][col] = None
                self.rookdemon_rooks.pop((row, col), None)
                self.dramatic_pieces.discard((row, col))

                if self.windknight_square == (row, col):
                    self.windknight_square = None
                    self.windknight_moves_remaining = 0

                self.status_message = (
                    f"Plague killed {enemy}'s {killed_piece.upper()}."
                )
                add_animation("poison", squares=[(row, col)], text="PLAGUE", color=(125, 220, 80), frames=42)

        # Propaganda: 50% chance to convert one enemy non-king piece.
        if self.turn in self.propaganda_active and random.random() < 0.5:
            enemy = self.enemy_color(self.turn)
            targets = [
                (r, c)
                for r in range(8)
                for c in range(8)
                if self.board[r][c] is not None
                and self.piece_color(self.board[r][c]) == enemy
                and self.board[r][c].lower() != "k"
            ]
            if targets:
                row, col = random.choice(targets)
                piece = self.board[row][col]
                self.board[row][col] = piece.upper() if self.turn == WHITE else piece.lower()
                self.rookdemon_rooks.pop((row, col), None)
                self.dramatic_pieces.discard((row, col))
                self.status_message = f"Propaganda converted {enemy}'s {piece.upper()}."
                add_animation("magic", squares=[(row, col)], text="PROPAGANDA", color=(210, 130, 255), frames=42)

    def is_absolute_protected_square(self, row, col):
        piece = self.board[row][col]

        if piece is None:
            return False

        return self.piece_color(piece) in self.absolute_protection_active

    def player_has_only_king(self, color):
        count = 0

        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]

                if piece is not None and self.piece_color(piece) == color:
                    count += 1

                    if piece.lower() != "k":
                        return False

        return count == 1

    def current_player_wins(self, reason):
        winner = self.turn
        self.game_over = True
        self.active_card = None
        self.active_card_owner = None
        self.selected = None
        self.legal_moves_for_selected = []
        self.winner_message = f"{winner.capitalize()} wins by {reason}."
        self.status_message = self.winner_message
        add_animation("banner", text=self.status_message, color=GOLD, frames=80)

    def save_history(self):
        snapshot = {
            "board": copy.deepcopy(self.board),
            "fire_tiles": copy.deepcopy(self.fire_tiles),
            "rookdemon_rooks": copy.deepcopy(self.rookdemon_rooks),
            "dramatic_pieces": copy.deepcopy(self.dramatic_pieces),
            "plague_active": copy.deepcopy(self.plague_active),
            "absolute_protection_active": copy.deepcopy(self.absolute_protection_active),
            "extra_blood_active": copy.deepcopy(self.extra_blood_active),
            "propaganda_active": copy.deepcopy(self.propaganda_active),
            "ifeelsafe_active": copy.deepcopy(self.ifeelsafe_active),
            "bonus_turns": copy.deepcopy(self.bonus_turns),
            "deck": copy.deepcopy(self.deck),
            "hand": copy.deepcopy(self.hand),
            "discard": copy.deepcopy(self.discard),
            "discards_used": copy.deepcopy(self.discards_used),
            "pending_draw": copy.deepcopy(self.pending_draw),
            "ether": copy.deepcopy(self.ether),
            "turn": self.turn,
            "white_king_moved": self.white_king_moved,
            "black_king_moved": self.black_king_moved,
            "white_left_rook_moved": self.white_left_rook_moved,
            "white_right_rook_moved": self.white_right_rook_moved,
            "black_left_rook_moved": self.black_left_rook_moved,
            "black_right_rook_moved": self.black_right_rook_moved,
            "en_passant_target": self.en_passant_target,
        }

        self.history.append(snapshot)

        if len(self.history) > 12:
            self.history.pop(0)

    def restore_snapshot(self, snapshot, positions_only=False, keep_turn=False, keep_ether=False):
        # Piece positions and the state needed to keep play legal.
        self.board = copy.deepcopy(snapshot["board"])
        self.rookdemon_rooks = copy.deepcopy(snapshot["rookdemon_rooks"])
        self.dramatic_pieces = copy.deepcopy(snapshot["dramatic_pieces"])
        self.white_king_moved = snapshot["white_king_moved"]
        self.black_king_moved = snapshot["black_king_moved"]
        self.white_left_rook_moved = snapshot["white_left_rook_moved"]
        self.white_right_rook_moved = snapshot["white_right_rook_moved"]
        self.black_left_rook_moved = snapshot["black_left_rook_moved"]
        self.black_right_rook_moved = snapshot["black_right_rook_moved"]
        self.en_passant_target = snapshot["en_passant_target"]

        # positions_only (TimeTraveler): leave Ether, powers and fire as-is so
        # only the pieces rewind; everything else stays active.
        if not positions_only:
            self.fire_tiles = copy.deepcopy(snapshot["fire_tiles"])
            self.plague_active = copy.deepcopy(snapshot["plague_active"])
            self.absolute_protection_active = copy.deepcopy(snapshot["absolute_protection_active"])
            self.extra_blood_active = copy.deepcopy(snapshot["extra_blood_active"])
            self.propaganda_active = copy.deepcopy(snapshot["propaganda_active"])
            self.ifeelsafe_active = copy.deepcopy(snapshot["ifeelsafe_active"])
            self.bonus_turns = copy.deepcopy(snapshot["bonus_turns"])
            self.deck = copy.deepcopy(snapshot["deck"])
            self.hand = copy.deepcopy(snapshot["hand"])
            self.discard = copy.deepcopy(snapshot["discard"])
            self.discards_used = copy.deepcopy(snapshot.get("discards_used", self.discards_used))
            self.pending_draw = copy.deepcopy(snapshot["pending_draw"])
            if not keep_ether:
                self.ether = copy.deepcopy(snapshot["ether"])
            if not keep_turn:
                self.turn = snapshot["turn"]

        self.selected = None
        self.legal_moves_for_selected = []
        self.active_card = None
        self.active_card_owner = None
        self.windknight_square = None
        self.windknight_moves_remaining = 0
        self.inzone_square = None
        self.inzone_captures = 0

    def award_check_bonus_for_player(self, color):
        enemy = self.enemy_color(color)

        if self.is_in_check(enemy):
            self.add_ether(color, 5)
            add_animation("coin", squares=[self.find_king(enemy)] if self.find_king(enemy) else [], text="+5 CHECK", color=(255, 220, 90), frames=38)
            return True

        return False

    def get_capture_moves_only(self, row, col):
        piece = self.board[row][col]

        if piece is None:
            return []

        legal_moves = self.get_legal_moves(row, col)
        capture_moves = []

        for target_row, target_col in legal_moves:
            target_piece = self.board[target_row][target_col]

            if target_piece is not None and self.piece_color(target_piece) != self.piece_color(piece):
                capture_moves.append((target_row, target_col))
                continue

            # En passant also counts as a capture.
            if piece.lower() == "p" and self.en_passant_target == (target_row, target_col):
                capture_moves.append((target_row, target_col))

        return capture_moves

    # -----------------------------
    # Fire helpers
    # -----------------------------
    def add_fire_tiles(self, squares):
        for row, col in squares:
            piece = self.board[row][col]
            if piece is not None and piece.lower() == "k":
                continue
            # Decays once per ply, so 4 = two full turns of burning.
            self.fire_tiles[(row, col)] = 4

    def decay_fire_tiles(self):
        expired = []

        for square in list(self.fire_tiles.keys()):
            self.fire_tiles[square] -= 1
            if self.fire_tiles[square] <= 0:
                expired.append(square)

        for square in expired:
            del self.fire_tiles[square]

    def apply_fire_damage_at(self, row, col):
        if (row, col) not in self.fire_tiles:
            return

        piece = self.board[row][col]
        if piece is None:
            return

        if piece.lower() == "k":
            return

        self.board[row][col] = None

    # -----------------------------
    # Card activation
    # -----------------------------
    def activate_pawntastic_on_square(self, row, col):
        if self.game_over:
            return

        piece = self.board[row][col]

        if piece is None or self.piece_color(piece) != self.turn:
            self.status_message = "Drop Pawntastic on one of your pawns."
            return

        if piece.lower() != "p":
            self.status_message = "Pawntastic only works on pawns."
            return

        moves = self.get_legal_moves(row, col)
        if not moves:
            self.status_message = "That pawn has no Pawntastic moves."
            return

        if not self.spend_card("pawntastic"):
            return

        self.active_card = "pawntastic"
        self.active_card_owner = self.turn
        self.selected = (row, col)
        self.legal_moves_for_selected = moves

        add_animation("magic", squares=[(row, col)], text="PAWN", color=(120, 255, 130), frames=26)
        self.status_message = f"{self.turn.capitalize()} used Pawntastic. Choose the pawn's move."

    def activate_bishock_on_square(self, row, col):
        if self.game_over:
            return

        piece = self.board[row][col]

        if piece is None or self.piece_color(piece) != self.turn:
            self.status_message = "Drop Bishock on one of your bishops."
            return

        if piece.lower() != "b":
            self.status_message = "Bishock only works on bishops."
            return

        destroyed_squares = get_bishock_destroyed_squares(self, row, col)

        if not destroyed_squares:
            self.status_message = "Bishock found nothing to destroy."
            return

        if not self.spend_card("bishock"):
            return

        ether_gained = 0

        for destroy_row, destroy_col in destroyed_squares:
            target_piece = self.board[destroy_row][destroy_col]

            if target_piece is not None and target_piece.lower() == "k":
                continue

            if target_piece is not None:
                ether_gained += self.get_piece_value(target_piece)

            self.board[destroy_row][destroy_col] = None
            self.fire_tiles.pop((destroy_row, destroy_col), None)
            self.rookdemon_rooks.pop((destroy_row, destroy_col), None)

            if self.windknight_square == (destroy_row, destroy_col):
                self.windknight_square = None
                self.windknight_moves_remaining = 0

        self.add_ether(self.turn, ether_gained)
        add_animation("blast", squares=destroyed_squares, text="ZAP", color=(170, 85, 255), frames=36)
        self.finish_card(f"{{player}} used Bishock and gained {ether_gained} Ether.")

    def activate_rookdemon_on_square(self, row, col):
        if self.game_over:
            return

        piece = self.board[row][col]

        if piece is None or self.piece_color(piece) != self.turn:
            self.status_message = "Drop Rookdemon on one of your rooks."
            return

        if piece.lower() != "r":
            self.status_message = "Rookdemon only works on rooks."
            return

        if not self.spend_card("rookdemon"):
            return

        self.rookdemon_rooks[(row, col)] = 2
        add_animation("magic", squares=[(row, col)], text="FIRE", color=(255, 90, 35), frames=36)
        self.finish_card("{player} empowered a rook with Rookdemon.")

    def activate_windknight_on_square(self, row, col):
        if self.game_over:
            return

        if not is_valid_windknight_target(self, row, col):
            self.status_message = "Drop Windknight on one of your knights."
            return

        moves = self.get_legal_moves(row, col)
        if not moves:
            self.status_message = "That knight has no legal Windknight move."
            return

        if not self.spend_card("windknight"):
            return

        self.active_card = "windknight"
        self.active_card_owner = self.turn
        self.windknight_square = (row, col)
        self.windknight_moves_remaining = 2
        self.selected = (row, col)
        self.legal_moves_for_selected = moves

        add_animation("magic", squares=[(row, col)], text="WIND", color=(90, 220, 255), frames=32)
        self.status_message = f"{self.turn.capitalize()} used Windknight. Move the knight twice."


    def activate_queentum_on_square(self, row, col):
        if self.game_over:
            return

        piece = self.board[row][col]

        if piece is None or self.piece_color(piece) != self.turn:
            self.status_message = "Drop Queentum on one of your queens."
            return

        if piece.lower() != "q":
            self.status_message = "Queentum only works on queens."
            return

        moves = self.get_legal_moves(row, col)
        if not moves:
            self.status_message = "That queen has no legal Queentum teleport."
            return

        if not self.spend_card("queentum"):
            return

        self.active_card = "queentum"
        self.active_card_owner = self.turn
        self.selected = (row, col)
        self.legal_moves_for_selected = moves

        add_animation("magic", squares=[(row, col)], text="QUANTUM", color=(200, 120, 255), frames=32)
        self.status_message = f"{self.turn.capitalize()} used Queentum. Choose any legal teleport square."


    def can_use_longlivetheking(self, color=None):
        if color is None:
            color = self.turn

        # Must hold the card and be able to pay for it.
        if "longlivetheking" not in self.hand[color]:
            return False

        if self.ether[color] < CARD_COSTS.get("longlivetheking", 0):
            return False

        if not get_empty_escape_corners(self):
            return False

        king_pos = self.find_king(color)
        if king_pos is None:
            return False

        return bool(self.safe_escape_corners(king_pos[0], king_pos[1], color))

    def _apply_longlivetheking(self, board, from_square, to_square, color):
        # Mutate `board` in place: move the king to the corner and spawn pawns
        # (promoting on the back rank) on every empty neighbouring square.
        # Returns the number of pawns spawned.
        from_row, from_col = from_square
        to_row, to_col = to_square

        if color == WHITE:
            pawn_piece, queen_piece, promotion_row = "P", "Q", 0
        else:
            pawn_piece, queen_piece, promotion_row = "p", "q", 7

        king_piece = board[from_row][from_col]
        board[to_row][to_col] = king_piece
        board[from_row][from_col] = None

        spawned = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = to_row + dr, to_col + dc
                if self.in_bounds(nr, nc) and board[nr][nc] is None:
                    board[nr][nc] = queen_piece if nr == promotion_row else pawn_piece
                    spawned += 1

        return spawned

    def safe_escape_corners(self, king_row, king_col, color):
        # Corners the king may flee to where it is NOT in check after arriving
        # (counting the pawns it spawns, which can block incoming attacks).
        safe = []
        for corner in get_empty_escape_corners(self):
            test_board = copy.deepcopy(self.board)
            self._apply_longlivetheking(test_board, (king_row, king_col), corner, color)

            probe = self.clone()
            probe.board = test_board
            if not probe.is_in_check(color):
                safe.append(corner)

        return safe

    def activate_longlivetheking_on_square(self, row, col):
        if self.game_over:
            # Allow this card as a last escape if update_status reached a
            # checkmate-like state but the card is still available.
            if not self.can_use_longlivetheking(self.turn):
                return
            self.game_over = False

        piece = self.board[row][col]

        if piece is None or self.piece_color(piece) != self.turn:
            self.status_message = "Drop LongLiveTheKing on your king."
            return

        if piece.lower() != "k":
            self.status_message = "LongLiveTheKing only works on kings."
            return

        if not get_empty_escape_corners(self):
            self.status_message = "LongLiveTheKing failed: no empty corner exists."
            return

        # Only flee to a corner where the king is NOT in check after arriving.
        safe_corners = self.safe_escape_corners(row, col, self.turn)
        if not safe_corners:
            self.status_message = "LongLiveTheKing failed: every corner would leave the king in check."
            return

        escape_corner = random.choice(safe_corners)

        if not self.spend_card("longlivetheking"):
            return

        from_row, from_col = row, col
        to_row, to_col = escape_corner

        add_animation("move_line", squares=[(from_row, from_col), (to_row, to_col)], color=(255, 235, 140), frames=40)

        # Moving the king disables castling.
        if self.turn == WHITE:
            self.white_king_moved = True
        else:
            self.black_king_moved = True

        # Move the king to the safe corner and spawn the pawns around it.
        spawned = self._apply_longlivetheking(self.board, (from_row, from_col), (to_row, to_col), self.turn)

        self.finish_card(
            f"{{player}} escaped to a safe corner and spawned {spawned} pawn(s)."
        )


    # -----------------------------
    # Game card activation
    # -----------------------------
    def activate_switchero(self):
        if self.game_over:
            return

        if not self.spend_card("switchero"):
            return

        # You take over your opponent's army: after the card you own all of
        # THEIR pieces in THEIR positions, but in YOUR colour and seen from YOUR
        # side, and they inherit your old army the same way. Concretely this is a
        # 180-degree rotation of the board (so the enemy formation arrives on
        # your side, oriented to your view) combined with a colour swap (so the
        # pieces that land on your side become yours). A piece at (r, c) becomes
        # the recoloured enemy piece from (7-r, 7-c).
        def rot(square):
            return (7 - square[0], 7 - square[1])

        new_board = [[None] * 8 for _ in range(8)]
        affected = []
        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]
                if piece is not None:
                    nr, nc = rot((row, col))
                    new_board[nr][nc] = piece.swapcase()  # rotate, then change owner
                    affected.append((nr, nc))
        self.board = new_board

        # The position-keyed effects travel with the pieces (the rook/piece on a
        # rotated square is still the same square's effect, just a new owner).
        self.rookdemon_rooks = {rot(sq): v for sq, v in self.rookdemon_rooks.items()}
        self.fire_tiles = {rot(sq): v for sq, v in self.fire_tiles.items()}
        self.dramatic_pieces = {rot(sq) for sq in self.dramatic_pieces}
        if self.windknight_square is not None:
            self.windknight_square = rot(self.windknight_square)
        if self.inzone_square is not None:
            self.inzone_square = rot(self.inzone_square)

        # Promote any pawn that landed on its promotion rank.
        for col in range(8):
            if self.board[0][col] == "P":
                self.board[0][col] = "Q"
            if self.board[7][col] == "p":
                self.board[7][col] = "q"

        # Kings and rooks have all relocated and changed owner, so castling is no
        # longer available and any en passant window is void.
        self.white_king_moved = True
        self.black_king_moved = True
        self.white_left_rook_moved = True
        self.white_right_rook_moved = True
        self.black_left_rook_moved = True
        self.black_right_rook_moved = True
        self.en_passant_target = None

        add_animation("magic", squares=affected or [(0, 0)], text="SWAP", color=(90, 170, 255), frames=45)

        self.finish_card("{player} seized the enemy army with Switchero.")

    def activate_prophecy(self):
        if self.game_over:
            return

        if not self.spend_card("prophecy"):
            return

        changed = 0
        changed_squares = []

        pawn_piece = "P" if self.turn == WHITE else "p"
        queen_piece = "Q" if self.turn == WHITE else "q"

        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]

                if piece == pawn_piece:
                    self.board[row][col] = queen_piece
                    changed += 1
                    changed_squares.append((row, col))

        if changed_squares:
            add_animation("magic", squares=changed_squares, text="QUEEN", color=(255, 215, 80), frames=42)

        self.finish_card(
            f"{{player}} played The Prophecy. {changed} own pawn(s) became queen(s)."
        )

    def activate_armageddon_on_square(self, row, col):
        if self.game_over:
            return

        if not self.spend_card("armageddon"):
            return

        destroyed_value = 0
        destroyed_count = 0
        fire_squares = []
        destroyed_pieces = []

        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                nr = row + dr
                nc = col + dc

                if not self.in_bounds(nr, nc):
                    continue

                target_piece = self.board[nr][nc]

                # Never delete kings.
                if target_piece is not None and target_piece.lower() == "k":
                    continue

                if target_piece is not None:
                    destroyed_value += self.get_piece_value(target_piece)
                    destroyed_count += 1
                    # Removed from the board now (so game logic stays correct),
                    # but remembered so the animation can keep showing them
                    # standing until the meteor actually lands on them.
                    destroyed_pieces.append((nr, nc, target_piece))
                    self.board[nr][nc] = None
                    self.rookdemon_rooks.pop((nr, nc), None)
                    self.dramatic_pieces.discard((nr, nc))

                    if self.windknight_square == (nr, nc):
                        self.windknight_square = None
                        self.windknight_moves_remaining = 0

                fire_squares.append((nr, nc))

        self.add_ether(self.turn, destroyed_value)

        if METEOR_FRAMES:
            # Fire is laid down only when the meteor hits (see meteor_sprite),
            # so the strike plays out over clean squares first.
            add_animation("meteor_sprite", frames=96, extra={
                "square": (row, col),
                "fire_squares": fire_squares,
                "destroyed_pieces": destroyed_pieces,
            })
        else:
            self.add_fire_tiles(fire_squares)
            add_animation("blast", squares=fire_squares, text="METEOR", color=(255, 95, 35), frames=38)

        self.finish_card(
            f"{{player}} played Armageddon. Destroyed {destroyed_count} piece(s) and created fire."
        )

    def activate_gravitystorm_on_square(self, row, col):
        if self.game_over:
            return

        target = (row, col)
        core_piece = self.board[row][col]

        # The gravity core may not be aimed at a king - the king is never
        # crushed, so the card simply cannot be played there.
        if core_piece is not None and core_piece.lower() == "k":
            self.status_message = "Gravity Storm cannot be aimed at a king."
            return

        if not self.spend_card("gravitystorm"):
            return

        crushed = 0
        # The chosen point becomes an empty, impassable core. Any piece sitting
        # on it is crushed as the core forms, and nothing else ever settles
        # there - every other piece is packed into a tight circle around it.
        if core_piece is not None:
            self.board[row][col] = None
            self.rookdemon_rooks.pop((row, col), None)
            self.dramatic_pieces.discard((row, col))
            if self.windknight_square == (row, col):
                self.windknight_square = None
                self.windknight_moves_remaining = 0
            if self.inzone_square == (row, col):
                self.inzone_square = None
            add_animation("burst", squares=[(row, col)], text="CRUSH", color=(150, 120, 230), frames=30)
            crushed = 1

        # Collect every remaining piece, the ones nearest the core first.
        movers = []
        for r in range(ROWS):
            for c in range(COLS):
                piece = self.board[r][c]
                if piece is not None:
                    movers.append((r, c, piece))
        movers.sort(key=lambda m: (m[0] - row) ** 2 + (m[1] - col) ** 2)

        # Real gravity: each piece, closest first, slides toward the point one
        # king-step at a time (diagonally when it can, straight when aligned)
        # and stops the instant the next square is the empty core, the wall, or
        # a piece that already settled. The piece in front stops nearest the
        # point and whatever is behind it stacks up outside - so the pieces that
        # START closest (the pawns) end up innermost and the back rank piles up
        # around them. Each piece only travels along its own line toward the
        # point, so it always keeps the side it came from.
        moved = 0
        for fr, fc, piece in movers:
            cr, cc = fr, fc
            while True:
                dr = (row > cr) - (row < cr)
                dc = (col > cc) - (col < cc)
                nr, nc = cr + dr, cc + dc
                if (nr, nc) == target:
                    break
                if not self.in_bounds(nr, nc) or self.board[nr][nc] is not None:
                    break
                cr, cc = nr, nc

            if (cr, cc) == (fr, fc):
                continue

            # Move the piece and carry its per-square state along with it.
            self.board[cr][cc] = piece
            self.board[fr][fc] = None
            if (fr, fc) in self.rookdemon_rooks:
                self.rookdemon_rooks[(cr, cc)] = self.rookdemon_rooks.pop((fr, fc))
            if (fr, fc) in self.dramatic_pieces:
                self.dramatic_pieces.discard((fr, fc))
                self.dramatic_pieces.add((cr, cc))
            if self.windknight_square == (fr, fc):
                self.windknight_square = (cr, cc)
            if self.inzone_square == (fr, fc):
                self.inzone_square = (cr, cc)

            # A gentle slide from where the piece started to its new spot,
            # staggered so the pieces closest to the point fall first and the
            # outer ones follow a beat later (an inward ripple).
            stagger = max(abs(fr - row), abs(fc - col)) * 5
            add_animation("slide", frames=48, extra={
                "piece": piece,
                "from": (fr, fc),
                "to": (cr, cc),
                "delay": stagger,
            })
            moved += 1

        add_animation("burst", squares=[target], text="GRAVITY", color=(150, 120, 230), frames=42)
        note = f"{moved} piece(s) pulled inward"
        if crushed:
            note += " and 1 crushed on the core"
        self.finish_card(f"{{player}} unleashed Gravity Storm. {note}.")

    def activate_thedramatic_on_square(self, row, col):
        if self.game_over:
            return

        if not self.spend_card("thedramatic"):
            return

        piece = self.board[row][col]

        if piece is None:
            self.ether[self.turn] += CARD_COSTS["thedramatic"]
            self.status_message = "Drop TheDramatic on one of your pieces."
            return

        if self.piece_color(piece) != self.turn:
            self.ether[self.turn] += CARD_COSTS["thedramatic"]
            self.status_message = "You can only use TheDramatic on your own piece."
            return

        if piece.lower() == "k":
            self.ether[self.turn] += CARD_COSTS["thedramatic"]
            self.status_message = "TheDramatic cannot be used on kings."
            return

        self.dramatic_pieces.add((row, col))
        add_animation("magic", squares=[(row, col)], text="D!", color=(255, 230, 70), frames=38)

        self.finish_card(
            "{player} played TheDramatic. The marked piece will avenge itself if captured."
        )


    def activate_capitalism(self):
        if self.game_over:
            return

        if not self.spend_card("capitalism"):
            return

        my_squares = []
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p is not None and self.piece_color(p) == self.turn:
                    my_squares.append((r, c))

        add_animation("coin", squares=my_squares, text="ETHER", color=(255, 220, 90), frames=55)
        self.current_player_wins("Capitalism")

    def activate_plague(self):
        if self.game_over:
            return

        if not self.spend_card("plague"):
            return

        self.plague_active.add(self.turn)

        self.finish_card(
            "{player} unleashed Plague. At the start of their turns, one enemy piece dies."
        )

    def activate_solo(self):
        if self.game_over:
            return

        if not self.player_has_only_king(self.turn):
            self.status_message = "Solo only works if you have only your king left."
            return

        if not self.spend_card("solo"):
            return

        king = self.find_king(self.turn)
        if king is not None:
            add_animation("magic", squares=[king], text="SOLO", color=(255, 230, 120), frames=55)

        self.current_player_wins("Solo")

    def activate_absoluteprotection(self):
        if self.game_over:
            return

        if not self.spend_card("absoluteprotection"):
            return

        self.absolute_protection_active.add(self.turn)
        protected_squares = []
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p is not None and self.piece_color(p) == self.turn:
                    protected_squares.append((r, c))
        add_animation("shield", squares=protected_squares, text="SHIELD", color=(90, 210, 255), frames=40)

        self.finish_card(
            "{player} activated AbsoluteProtection for one opponent turn."
        )


    def activate_timetraveler(self):
        if self.game_over:
            return

        # Needs 3 prior snapshots; spend_card adds one more, so require 3 now.
        if len(self.history) < 3:
            self.status_message = "TimeTraveler needs at least 3 previous turns."
            return

        if not self.spend_card("timetraveler"):
            return

        snapshot = copy.deepcopy(self.history[-4])
        # Only the piece positions rewind - Ether, cards and every active power
        # are kept as they are now.
        self.restore_snapshot(snapshot, positions_only=True)
        self.history = self.history[:-4]
        add_animation("magic", squares=[(r, c) for r in range(8) for c in range(8)], text="TIME", color=(120, 190, 255), frames=55)
        self.finish_card("{player} rewound the pieces 3 turns. Ether and powers are kept.")

    def activate_extrablood(self):
        if self.game_over:
            return

        if self.turn in self.extra_blood_active:
            self.status_message = "ExtraBlood is already active for you."
            return

        if not self.spend_card("extrablood"):
            return

        self.extra_blood_active.add(self.turn)
        add_animation("banner", text=f"{self.turn.capitalize()} activated ExtraBlood", color=(220, 30, 30), frames=50)
        self.finish_card("{player} activated ExtraBlood. Capture Ether is now doubled.")

    def activate_chrisma(self):
        if self.game_over:
            return

        king_pos = self.find_king(self.turn)

        if king_pos is None:
            self.status_message = "Chrisma failed: no king found."
            return

        if not self.spend_card("chrisma"):
            return

        kr, kc = king_pos
        converted = 0
        gained = 0
        affected = []

        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                nr = kr + dr
                nc = kc + dc

                if dr == 0 and dc == 0:
                    continue

                if not self.in_bounds(nr, nc):
                    continue

                piece = self.board[nr][nc]

                if piece is None:
                    continue

                if self.piece_color(piece) == self.turn:
                    continue

                if piece.lower() == "k":
                    continue

                gained += self.get_piece_value(piece)
                self.board[nr][nc] = piece.upper() if self.turn == WHITE else piece.lower()
                converted += 1
                affected.append((nr, nc))

        self.add_ether(self.turn, gained)
        add_animation("magic", squares=affected or [king_pos], text="CHARM", color=(255, 120, 220), frames=48)
        self.finish_card(
            f"{{player}} used Chrisma. Converted {converted} piece(s) and gained {gained} Ether."
        )

    def activate_inzone_on_square(self, row, col):
        if self.game_over:
            return

        piece = self.board[row][col]

        if piece is None:
            self.status_message = "Drop InZone on one of your pieces."
            return

        if self.piece_color(piece) != self.turn:
            self.status_message = "You can only use InZone on your own piece."
            return

        if piece.lower() == "k":
            self.status_message = "InZone cannot be used on kings."
            return

        if piece.lower() == "q":
            self.status_message = "InZone cannot be used on the queen."
            return

        capture_moves = self.get_capture_moves_only(row, col)

        if not capture_moves:
            self.status_message = "That piece has no captures for InZone."
            return

        if not self.spend_card("inzone"):
            return

        self.active_card = "inzone"
        self.active_card_owner = self.turn
        self.inzone_square = (row, col)
        self.inzone_captures = 0
        self.selected = (row, col)
        self.legal_moves_for_selected = capture_moves
        add_animation("magic", squares=[(row, col)], text="ZONE", color=(255, 70, 70), frames=42)
        self.status_message = "InZone active: capture repeatedly with this piece. It dies when the streak ends."

    def find_checking_pieces(self, color):
        king = self.find_king(color)
        if king is None:
            return []
        enemy = self.enemy_color(color)
        attackers = []
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece is not None and self.piece_color(piece) == enemy:
                    if king in self.get_pseudo_legal_moves(r, c, include_castling=False):
                        attackers.append((r, c))
        return attackers

    def activate_nope(self):
        if self.game_over:
            return

        opp = self.enemy_color(self.turn)
        in_check = self.is_in_check(self.turn)

        if self.card_undo.get(opp) is None and not in_check:
            self.status_message = "Nope has nothing to cancel."
            return

        if not self.spend_card("nope"):
            return

        notes = []

        if in_check:
            # In check, killing the piece giving check takes priority: it
            # removes the threat directly, whereas reverting the opponent's
            # card might not clear the check (it can come from a normal move).
            killed = 0
            for r, c in self.find_checking_pieces(self.turn):
                piece = self.board[r][c]
                if piece is not None and piece.lower() != "k":
                    self.board[r][c] = None
                    self.rookdemon_rooks.pop((r, c), None)
                    self.dramatic_pieces.discard((r, c))
                    add_animation("burst", squares=[(r, c)], text="NOPE", color=(120, 160, 255), frames=36)
                    killed += 1
            if killed:
                notes.append("destroyed the checking piece")
        elif self.card_undo.get(opp) is not None:
            # Cancel the opponent's last card (it may have been played a turn or
            # two ago) by reverting to the state just before it. This last card
            # may itself be a Nope, so Nope can cancel a Nope. The current turn
            # and Ether totals are left as they are now.
            self.restore_snapshot(self.card_undo[opp], keep_turn=True, keep_ether=True)
            self.card_undo[opp] = None
            notes.append("cancelled the opponent's last card")

        summary = " and ".join(notes) if notes else "fizzled"
        self.finish_card(f"{{player}} played Nope: {summary}.")

    def activate_communism(self):
        if self.game_over:
            return

        if not self.spend_card("communism"):
            return

        total = self.ether[WHITE] + self.ether[BLACK]
        half = total // 2
        # Any odd Ether goes to the player who played the card.
        self.ether[self.enemy_color(self.turn)] = half
        self.ether[self.turn] = total - half
        add_animation("banner", text="COMMUNISM", color=(220, 60, 60), frames=44)
        self.finish_card("{player} played Communism. Ether is now shared equally.")

    def activate_gambit_on_square(self, row, col):
        # The first sacrifice pays for the card and arms Gambit; while it stays
        # active the player can keep clicking their own pieces to sacrifice as
        # many as they want (see select_square / gambit_sacrifice).
        if self.game_over:
            return

        if not self.gambit_can_sacrifice(row, col):
            return

        if not self.spend_card("gambit"):
            return

        self.active_card = "gambit"
        self.active_card_owner = self.turn
        self.gambit_sacrifice(row, col)

    def gambit_can_sacrifice(self, row, col):
        piece = self.board[row][col]

        if piece is None:
            self.status_message = "Drop Gambit on one of your pieces."
            return False

        if self.piece_color(piece) != self.turn:
            self.status_message = "You can only sacrifice your own piece."
            return False

        if piece.lower() == "k":
            self.status_message = "Gambit cannot sacrifice the king."
            return False

        return True

    def gambit_sacrifice(self, row, col):
        piece = self.board[row][col]
        value = self.get_piece_value(piece) * 2
        self.board[row][col] = None
        self.rookdemon_rooks.pop((row, col), None)
        self.dramatic_pieces.discard((row, col))
        if self.windknight_square == (row, col):
            self.windknight_square = None
            self.windknight_moves_remaining = 0

        self.add_ether(self.turn, value)
        add_animation("burst", squares=[(row, col)], text="GAMBIT", color=(200, 150, 60), frames=34)
        add_animation("coin", squares=[(row, col)], text=f"+{value}", color=(255, 220, 90), frames=40)
        self.status_message = (
            f"Gambit: +{value} Ether. Click more pieces to sacrifice, "
            "or click elsewhere to finish."
        )

    def gambit_finish(self):
        # Leave Gambit mode; the player keeps the turn to make their move.
        self.active_card = None
        self.active_card_owner = None
        self.selected = None
        self.legal_moves_for_selected = []
        self.update_status()

    def activate_propaganda(self):
        if self.game_over:
            return

        if self.turn in self.propaganda_active:
            self.status_message = "Propaganda is already active for you."
            return

        if not self.spend_card("propaganda"):
            return

        self.propaganda_active.add(self.turn)
        add_animation("banner", text="PROPAGANDA", color=(210, 130, 255), frames=46)
        self.finish_card("{player} spread Propaganda. Each turn may convert an enemy piece.")

    def activate_ifeelsafe(self):
        if self.game_over:
            return

        if self.turn in self.ifeelsafe_active:
            self.status_message = "I Feel Safe is already active for you."
            return

        if not self.spend_card("ifeelsafe"):
            return

        self.ifeelsafe_active.add(self.turn)
        add_animation("banner", text="I FEEL SAFE", color=(90, 210, 255), frames=46)
        self.finish_card(
            "{player} feels safe. End of turn: +3 Ether per piece by the king."
        )

    def activate_iguess(self):
        if self.game_over:
            return

        if not self.spend_card("iguess"):
            return

        self.bonus_turns[self.turn] += 2
        add_animation("banner", text="I GUESS  +2 MOVES", color=(150, 220, 150), frames=50)
        self.finish_card(
            "{player} played I Guess. They now take 2 extra moves every turn."
        )

    # -----------------------------
    # Move generation
    # -----------------------------
    def get_pseudo_legal_moves(self, row, col, include_castling=True):
        piece = self.board[row][col]
        if piece is None:
            return []

        color = self.piece_color(piece)
        piece_type = piece.lower()
        moves = []

        if piece_type == "p":
            moves.extend(self.get_pawn_moves(row, col, color))

        elif piece_type == "r":
            moves.extend(self.get_sliding_moves(row, col, color, [
                (-1, 0), (1, 0), (0, -1), (0, 1)
            ]))

        elif piece_type == "b":
            moves.extend(self.get_sliding_moves(row, col, color, [
                (-1, -1), (-1, 1), (1, -1), (1, 1)
            ]))

        elif piece_type == "q":
            moves.extend(self.get_sliding_moves(row, col, color, [
                (-1, 0), (1, 0), (0, -1), (0, 1),
                (-1, -1), (-1, 1), (1, -1), (1, 1)
            ]))

        elif piece_type == "n":
            knight_steps = [
                (-2, -1), (-2, 1),
                (-1, -2), (-1, 2),
                (1, -2), (1, 2),
                (2, -1), (2, 1),
            ]

            for dr, dc in knight_steps:
                nr, nc = row + dr, col + dc
                if self.in_bounds(nr, nc) and not self.is_friend(nr, nc, color):
                    moves.append((nr, nc))

        elif piece_type == "k":
            king_steps = [
                (-1, -1), (-1, 0), (-1, 1),
                (0, -1),           (0, 1),
                (1, -1),  (1, 0),  (1, 1),
            ]

            for dr, dc in king_steps:
                nr, nc = row + dr, col + dc
                if self.in_bounds(nr, nc) and not self.is_friend(nr, nc, color):
                    moves.append((nr, nc))

            if include_castling:
                moves.extend(self.get_castling_moves(color))

        return moves

    def get_pawn_moves(self, row, col, color):
        moves = []
        direction = -1 if color == WHITE else 1
        start_row = 6 if color == WHITE else 1

        one_row = row + direction

        if self.in_bounds(one_row, col) and self.is_empty(one_row, col):
            moves.append((one_row, col))

            two_row = row + 2 * direction

            if row == start_row and self.in_bounds(two_row, col) and self.is_empty(two_row, col):
                moves.append((two_row, col))

        for dc in [-1, 1]:
            nr, nc = row + direction, col + dc

            if self.in_bounds(nr, nc) and self.is_enemy(nr, nc, color):
                moves.append((nr, nc))

        if self.en_passant_target is not None:
            ep_row, ep_col = self.en_passant_target

            if ep_row == row + direction and abs(ep_col - col) == 1:
                moves.append((ep_row, ep_col))

        return moves

    def get_sliding_moves(self, row, col, color, directions):
        moves = []

        for dr, dc in directions:
            nr, nc = row + dr, col + dc

            while self.in_bounds(nr, nc):
                if self.is_empty(nr, nc):
                    moves.append((nr, nc))

                elif self.is_enemy(nr, nc, color):
                    moves.append((nr, nc))
                    break

                else:
                    break

                nr += dr
                nc += dc

        return moves

    def get_castling_moves(self, color):
        moves = []

        if color == WHITE:
            row = 7
            king_moved = self.white_king_moved
            left_rook_moved = self.white_left_rook_moved
            right_rook_moved = self.white_right_rook_moved
            king_piece = "K"
        else:
            row = 0
            king_moved = self.black_king_moved
            left_rook_moved = self.black_left_rook_moved
            right_rook_moved = self.black_right_rook_moved
            king_piece = "k"

        if self.board[row][4] != king_piece:
            return moves

        if king_moved:
            return moves

        if self.is_in_check(color):
            return moves

        enemy = self.enemy_color(color)

        if not right_rook_moved:
            if self.board[row][7] is not None and self.board[row][7].lower() == "r":
                if self.is_empty(row, 5) and self.is_empty(row, 6):
                    if not self.is_square_attacked(row, 5, enemy) and not self.is_square_attacked(row, 6, enemy):
                        moves.append((row, 6))

        if not left_rook_moved:
            if self.board[row][0] is not None and self.board[row][0].lower() == "r":
                if self.is_empty(row, 1) and self.is_empty(row, 2) and self.is_empty(row, 3):
                    if not self.is_square_attacked(row, 3, enemy) and not self.is_square_attacked(row, 2, enemy):
                        moves.append((row, 2))

        return moves

    def get_legal_moves(self, row, col):
        piece = self.board[row][col]

        if piece is None:
            return []

        color = self.piece_color(piece)

        if self.active_card == "pawntastic":
            pseudo_moves = get_pawntastic_moves(self, row, col)
        elif self.active_card == "queentum":
            pseudo_moves = get_queentum_moves(self, row, col)
        else:
            pseudo_moves = self.get_pseudo_legal_moves(row, col)

        legal_moves = []

        for move in pseudo_moves:
            # A king can never be captured, so capturing one is never a legal move.
            target_piece = self.board[move[0]][move[1]]
            if target_piece is not None and target_piece.lower() == "k":
                continue

            if piece.lower() == "k" and move in self.fire_tiles:
                continue

            if piece.lower() == "k" and self.is_absolute_protected_square(move[0], move[1]):
                continue

            test_state = self.clone()
            test_state.make_move((row, col), move, test_mode=True)

            if not test_state.is_in_check(color):
                legal_moves.append(move)

        return legal_moves

    # -----------------------------
    # Check / attacks
    # -----------------------------
    def find_king(self, color):
        target = "K" if color == WHITE else "k"

        for row in range(8):
            for col in range(8):
                if self.board[row][col] == target:
                    return row, col

        return None

    def is_in_check(self, color):
        king_pos = self.find_king(color)

        if king_pos is None:
            return False

        enemy = self.enemy_color(color)
        return self.is_square_attacked(king_pos[0], king_pos[1], enemy)

    def is_square_attacked(self, row, col, by_color):
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]

                if piece is None:
                    continue

                if self.piece_color(piece) != by_color:
                    continue

                piece_type = piece.lower()

                if piece_type == "p":
                    direction = -1 if by_color == WHITE else 1

                    for dc in [-1, 1]:
                        if (r + direction, c + dc) == (row, col):
                            return True

                elif piece_type == "k":
                    if abs(r - row) <= 1 and abs(c - col) <= 1:
                        return True

                else:
                    moves = self.get_pseudo_legal_moves(r, c, include_castling=False)

                    if (row, col) in moves:
                        return True

        return False

    def has_any_legal_moves(self, color):
        saved_active_card = self.active_card
        saved_active_card_owner = self.active_card_owner
        saved_windknight_square = self.windknight_square
        saved_windknight_moves_remaining = self.windknight_moves_remaining

        self.active_card = None
        self.active_card_owner = None
        self.windknight_square = None
        self.windknight_moves_remaining = 0

        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]

                if piece is not None and self.piece_color(piece) == color:
                    if self.get_legal_moves(row, col):
                        self.active_card = saved_active_card
                        self.active_card_owner = saved_active_card_owner
                        self.windknight_square = saved_windknight_square
                        self.windknight_moves_remaining = saved_windknight_moves_remaining
                        return True

        self.active_card = saved_active_card
        self.active_card_owner = saved_active_card_owner
        self.windknight_square = saved_windknight_square
        self.windknight_moves_remaining = saved_windknight_moves_remaining
        return False

    # -----------------------------
    # Making moves
    # -----------------------------
    def log_event(self, color, kind, text):
        self.move_log.append((color, kind, text))
        if len(self.move_log) > 200:
            del self.move_log[:-200]

    @staticmethod
    def square_name(row, col):
        return f"{'abcdefgh'[col]}{8 - row}"

    def move_notation(self, piece, from_square, to_square, captured_piece):
        letter = piece.upper()  # P, N, B, R, Q, K (piece-type only)
        sep = "x" if captured_piece is not None else "-"
        return f"{letter} {self.square_name(*from_square)}{sep}{self.square_name(*to_square)}"

    def make_move(self, from_square, to_square, test_mode=False):
        from_row, from_col = from_square
        to_row, to_col = to_square

        original_from_square = (from_row, from_col)
        original_to_square = (to_row, to_col)

        piece = self.board[from_row][from_col]
        captured_piece = self.board[to_row][to_col]

        if piece is None:
            return

        # Under no circumstances can a king be captured - by a normal move, a
        # piece ability, or any other mechanic that routes through make_move.
        if captured_piece is not None and captured_piece.lower() == "k":
            if not test_mode:
                self.status_message = "The king cannot be captured."
            return

        if not test_mode:
            self.save_history()
            # Note: a normal move does NOT clear card_undo. Nope cancels the
            # opponent's *last card*, which stays cancellable across the moves
            # and turns played after it, until the opponent plays another card.
            self.log_event(self.piece_color(piece), "move",
                           self.move_notation(piece, original_from_square,
                                              original_to_square, captured_piece))

        color = self.piece_color(piece)
        piece_type = piece.lower()
        move_distance = self.get_move_distance(piece, original_from_square, original_to_square)
        capture_ether = self.get_piece_value(captured_piece)
        captured_square_was_dramatic = (
            captured_piece is not None
            and (to_row, to_col) in self.dramatic_pieces
        )
        target_is_absolute_protected = (
            captured_piece is not None
            and self.piece_color(captured_piece) in self.absolute_protection_active
        )

        # AbsoluteProtection: protected piece survives, attacker dies.
        if target_is_absolute_protected:
            if piece_type == "k":
                return

            self.board[from_row][from_col] = None
            self.rookdemon_rooks.pop((from_row, from_col), None)
            self.dramatic_pieces.discard((from_row, from_col))

            if not test_mode:
                self.decay_fire_tiles()
                self.active_card = None
                self.active_card_owner = None
                self.pass_turn()
                self.selected = None
                self.legal_moves_for_selected = []
                self.status_message = "AbsoluteProtection triggered: the attacker was destroyed."
                add_animation("shield", squares=[(to_row, to_col), (from_row, from_col)], text="BLOCK", color=(90, 210, 255), frames=34)
                self.start_turn_effects()
                self.update_status()

            return

        was_windknight_move = (
            self.active_card == "windknight"
            and self.windknight_square == original_from_square
            and piece_type == "n"
        )

        was_inzone_move = (
            self.active_card == "inzone"
            and self.inzone_square == original_from_square
        )

        if captured_piece is not None:
            self.update_castling_rights_for_capture(to_row, to_col, captured_piece)

        if piece_type == "p" and self.en_passant_target == (to_row, to_col) and captured_piece is None:
            capture_row = from_row
            capture_col = to_col
            en_passant_piece = self.board[capture_row][capture_col]
            capture_ether += self.get_piece_value(en_passant_piece)

            if (capture_row, capture_col) in self.dramatic_pieces:
                captured_square_was_dramatic = True
                self.dramatic_pieces.discard((capture_row, capture_col))

            self.board[capture_row][capture_col] = None
            self.rookdemon_rooks.pop((capture_row, capture_col), None)

            if self.windknight_square == (capture_row, capture_col):
                self.windknight_square = None
                self.windknight_moves_remaining = 0

        moving_piece_was_dramatic = (from_row, from_col) in self.dramatic_pieces
        self.dramatic_pieces.discard((from_row, from_col))

        self.board[to_row][to_col] = piece
        self.board[from_row][from_col] = None

        if captured_piece is not None:
            self.dramatic_pieces.discard((to_row, to_col))
            self.rookdemon_rooks.pop((to_row, to_col), None)

            if self.windknight_square == (to_row, to_col):
                self.windknight_square = None
                self.windknight_moves_remaining = 0

        if piece_type == "r" and original_from_square in self.rookdemon_rooks:
            fire_path = get_rookdemon_path(original_from_square, original_to_square)
            self.add_fire_tiles(fire_path)

            remaining = self.rookdemon_rooks[original_from_square] - 1
            del self.rookdemon_rooks[original_from_square]

            if remaining > 0:
                self.rookdemon_rooks[original_to_square] = remaining

        if piece_type == "k" and abs(to_col - from_col) == 2:
            if to_col == 6:
                rook_piece = self.board[to_row][7]
                self.board[to_row][5] = rook_piece
                self.board[to_row][7] = None

                if (to_row, 7) in self.rookdemon_rooks:
                    self.rookdemon_rooks[(to_row, 5)] = self.rookdemon_rooks[(to_row, 7)]
                    del self.rookdemon_rooks[(to_row, 7)]

            elif to_col == 2:
                rook_piece = self.board[to_row][0]
                self.board[to_row][3] = rook_piece
                self.board[to_row][0] = None

                if (to_row, 0) in self.rookdemon_rooks:
                    self.rookdemon_rooks[(to_row, 3)] = self.rookdemon_rooks[(to_row, 0)]
                    del self.rookdemon_rooks[(to_row, 0)]

        if piece_type == "p":
            if color == WHITE and to_row == 0:
                self.board[to_row][to_col] = "Q"
            elif color == BLACK and to_row == 7:
                self.board[to_row][to_col] = "q"

        if moving_piece_was_dramatic and self.board[to_row][to_col] is not None:
            self.dramatic_pieces.add((to_row, to_col))

        self.update_castling_rights_for_move(from_row, from_col, piece)

        self.en_passant_target = None

        if piece_type == "p" and abs(to_row - from_row) == 2:
            middle_row = (from_row + to_row) // 2
            self.en_passant_target = (middle_row, from_col)

        if not test_mode:
            if self.active_card == "queentum":
                add_animation("teleport", frames=34, extra={
                    "from": original_from_square,
                    "to": original_to_square,
                    "piece": piece,
                })

            if capture_ether > 0 and color in self.extra_blood_active:
                capture_ether *= 2

            move_ether = move_distance
            total_ether_gained = move_ether + capture_ether
            self.add_ether(color, total_ether_gained)

            if total_ether_gained > 0:
                add_animation("coin", squares=[original_to_square], text=f"+{total_ether_gained}", color=(255, 220, 90), frames=32)

            if total_ether_gained > 0:
                self.status_message = (
                    f"{color.capitalize()} gained {total_ether_gained} Ether "
                    f"({move_ether} move + {capture_ether} capture)."
                )

            add_animation("move_line", squares=[original_from_square, original_to_square], color=(255, 230, 130), frames=18)

            if captured_piece is not None or capture_ether > 0:
                add_animation("burst", squares=[original_to_square], text="HIT", color=(255, 70, 70), frames=28)

            self.apply_fire_damage_at(to_row, to_col)

            moved_piece_survived = self.board[to_row][to_col] is not None

            if captured_square_was_dramatic and moved_piece_survived:
                # The captured piece avenges itself.
                if self.board[to_row][to_col].lower() != "k":
                    self.board[to_row][to_col] = None
                    self.rookdemon_rooks.pop((to_row, to_col), None)
                    self.dramatic_pieces.discard((to_row, to_col))
                    moved_piece_survived = False
                    self.status_message = "TheDramatic triggered: the capturing piece was destroyed."

            if not moved_piece_survived:
                self.rookdemon_rooks.pop((to_row, to_col), None)

                if self.windknight_square == (to_row, to_col):
                    self.windknight_square = None
                    self.windknight_moves_remaining = 0

            if was_inzone_move:
                if moved_piece_survived and capture_ether > 0:
                    self.inzone_captures += 1
                    self.inzone_square = (to_row, to_col)
                    self.selected = (to_row, to_col)
                    self.legal_moves_for_selected = self.get_capture_moves_only(to_row, to_col)

                    # The streak ends at 5 captures, or immediately if a king
                    # is now in check (either side).
                    check_on_board = self.is_in_check(WHITE) or self.is_in_check(BLACK)

                    if self.legal_moves_for_selected and self.inzone_captures < 5 and not check_on_board:
                        self.status_message = "InZone: keep capturing with the same piece."
                        return

                # Streak ends: the InZone piece dies.
                if moved_piece_survived:
                    self.board[to_row][to_col] = None
                    self.rookdemon_rooks.pop((to_row, to_col), None)
                    self.dramatic_pieces.discard((to_row, to_col))
                    add_animation("burst", squares=[(to_row, to_col)], text="BURNOUT", color=(255, 60, 60), frames=38)

                self._finish_move()
                return

            if was_windknight_move and moved_piece_survived:
                self.windknight_moves_remaining -= 1

                if self.windknight_moves_remaining > 0:
                    self.windknight_square = (to_row, to_col)
                    self.selected = (to_row, to_col)
                    self.legal_moves_for_selected = self.get_legal_moves(to_row, to_col)

                    if self.legal_moves_for_selected:
                        self.status_message = "Windknight: move the same knight one more time."
                        return

                self._finish_move()
                return

            self._finish_move()

    def update_castling_rights_for_move(self, from_row, from_col, piece):
        piece_type = piece.lower()
        color = self.piece_color(piece)

        if piece_type == "k":
            if color == WHITE:
                self.white_king_moved = True
            else:
                self.black_king_moved = True

        elif piece_type == "r":
            if color == WHITE:
                if from_row == 7 and from_col == 0:
                    self.white_left_rook_moved = True
                elif from_row == 7 and from_col == 7:
                    self.white_right_rook_moved = True
            else:
                if from_row == 0 and from_col == 0:
                    self.black_left_rook_moved = True
                elif from_row == 0 and from_col == 7:
                    self.black_right_rook_moved = True

    def update_castling_rights_for_capture(self, row, col, captured_piece):
        if captured_piece.lower() != "r":
            return

        color = self.piece_color(captured_piece)

        if color == WHITE:
            if row == 7 and col == 0:
                self.white_left_rook_moved = True
            elif row == 7 and col == 7:
                self.white_right_rook_moved = True
        else:
            if row == 0 and col == 0:
                self.black_left_rook_moved = True
            elif row == 0 and col == 7:
                self.black_right_rook_moved = True

    def update_status(self):
        if self.is_in_check(self.turn):
            if not self.has_any_legal_moves(self.turn):
                if self.can_use_longlivetheking(self.turn):
                    self.status_message = (
                        f"{self.turn.capitalize()} is checkmated, "
                        "but LongLiveTheKing can still be used."
                    )
                    self.game_over = False
                else:
                    winner = "Black" if self.turn == WHITE else "White"
                    self.winner_message = f"{winner} wins by checkmate."
                    self.status_message = self.winner_message
                    self.game_over = True
            else:
                self.status_message = f"{self.turn.capitalize()} is in check"
        else:
            if not self.has_any_legal_moves(self.turn):
                self.winner_message = "Draw by stalemate."
                self.status_message = self.winner_message
                self.game_over = True
            else:
                self.status_message = f"{self.turn.capitalize()} to move"

    def select_square(self, row, col):
        if self.game_over:
            return

        clicked_piece = self.board[row][col]

        if self.active_card == "windknight":
            if self.selected is not None and (row, col) in self.legal_moves_for_selected:
                self.make_move(self.selected, (row, col))
                return

            self.status_message = "Windknight is active. Move the selected knight."
            return

        if self.active_card == "inzone":
            if self.selected is not None and (row, col) in self.legal_moves_for_selected:
                self.make_move(self.selected, (row, col))
                return

            self.status_message = "InZone is active. Capture with the selected piece."
            return

        if self.active_card == "gambit":
            # Click your own (non-king) pieces to sacrifice more of them; a click
            # anywhere else ends Gambit and returns to normal play.
            if clicked_piece is not None and self.piece_color(clicked_piece) == self.turn and clicked_piece.lower() != "k":
                self.gambit_sacrifice(row, col)
            else:
                self.gambit_finish()
            return

        if self.selected is not None:
            if (row, col) in self.legal_moves_for_selected:
                # A plain chess move is limited to the moves allowed this turn.
                if self.active_card is None and self.moves_made_this_turn >= self.moves_allowed():
                    self.status_message = "No moves left this turn. Press END TURN."
                    return
                self.make_move(self.selected, (row, col))
                return

        if clicked_piece is not None and self.piece_color(clicked_piece) == self.turn:
            if self.active_card == "pawntastic" and clicked_piece.lower() != "p":
                self.selected = None
                self.legal_moves_for_selected = []
                self.status_message = "Pawntastic only works on pawns."
                return

            if self.active_card == "queentum" and clicked_piece.lower() != "q":
                self.selected = None
                self.legal_moves_for_selected = []
                self.status_message = "Queentum only works on queens."
                return

            self.selected = (row, col)
            self.legal_moves_for_selected = self.get_legal_moves(row, col)
        else:
            self.selected = None
            self.legal_moves_for_selected = []


game = GameState()

# -----------------------------
# Dragging state
# -----------------------------
dragging_card = None
dragging_piece = None  # (row, col) of the piece being dragged, or None
dragging_lift_ticks = 0  # when the current drag started, for the lift ease
dragging_lift_from = (0, 0)  # screen point the piece was lifted from


def view_color():
    # Whose hand / ether / deck the local player should SEE in the tray. In
    # hot-seat this is the side to move; vs Computer the human's chosen colour;
    # online it is the local player's own colour (so you never see the
    # opponent's hand, and your tray stays put when it's their turn).
    if game_mode == "pvc":
        return human_color
    if game_mode == "online" and net_local_color is not None:
        return net_local_color
    return game.turn


def is_board_flipped():
    # Keep the local player's own side at the bottom of the screen.
    if game_mode == "pvc":
        return human_color == BLACK
    if game_mode == "online" and net_local_color is not None:
        return net_local_color == BLACK
    return game.turn == BLACK


def board_to_screen(row, col):
    if is_board_flipped():
        display_row = 7 - row
        display_col = 7 - col
    else:
        display_row = row
        display_col = col

    x = BOARD_X + display_col * SQUARE_W
    y = BOARD_Y + display_row * SQUARE_H
    return x, y


def get_card_rects():
    # The current player's hand, fanned in a shallow arc and centered between
    # the side buttons. Cards overlap only if the hand is unusually large.
    rects = {}
    hand = game.hand[view_color()]
    n = len(hand)
    if n == 0:
        return rects

    avail = SCREEN_WIDTH - 2 * (SIDE_MARGIN + ACTION_BTN_W + PANEL_PAD)
    spacing = CARD_WIDTH + PANEL_PAD
    if n > 1 and n * spacing > avail:
        spacing = max(CARD_WIDTH // 3, (avail - CARD_WIDTH) // (n - 1))

    total = CARD_WIDTH + (n - 1) * spacing
    start_x = (SCREEN_WIDTH - total) // 2
    # Cards hang from the bottom of the screen and the middle ones rise highest.
    bottom = SCREEN_HEIGHT - CARD_GAP
    center = (n - 1) / 2
    max_off = max(1.0, center)

    for index, card_name in enumerate(hand):
        off = index - center
        x = start_x + index * spacing
        lift = ARC_LIFT * (1 - (off / max_off) ** 2)  # middle rises highest
        y = int(bottom - lift - CARD_HEIGHT)
        rects[card_name] = pygame.Rect(x, y, CARD_WIDTH, CARD_HEIGHT)

    return rects


# -----------------------------
# Drawing
# -----------------------------
def draw_corner_brackets(rect, color, thickness=3):
    # An L-shaped bracket in each corner, leaving the middle of every edge
    # empty - frames the square without filling it.
    inset = max(3, SQUARE_W // 14)
    arm = max(6, SQUARE_W // 4)
    inner = rect.inflate(-inset * 2, -inset * 2)

    for (corner, hx, vy) in (
        (inner.topleft, 1, 1),
        (inner.topright, -1, 1),
        (inner.bottomleft, 1, -1),
        (inner.bottomright, -1, -1),
    ):
        cx, cy = corner
        pygame.draw.line(screen, color, corner, (cx + hx * arm, cy), thickness)
        pygame.draw.line(screen, color, corner, (cx, cy + vy * arm), thickness)


def get_card_target_squares(card_name):
    target = CARD_TARGET_TYPE.get(card_name)

    if target is None:
        return []

    squares = []
    for r in range(ROWS):
        for c in range(COLS):
            piece = game.board[r][c]
            if piece is None or game.piece_color(piece) != game.turn:
                continue
            kind = piece.lower()
            if (
                target == "any"
                or (target == "non_king" and kind != "k")
                or (target == "inzone" and kind not in ("k", "q"))
                or kind == target
            ):
                squares.append((r, c))

    return squares


def draw_card_target_hints():
    # While a piece-targeting card is held - or Gambit is active and waiting for
    # more sacrifices - show which of your pieces it can target: pulsing amber
    # corner brackets that blink on and off.
    card = dragging_card if dragging_card is not None else (
        "gambit" if game.active_card == "gambit" else None
    )
    if card is None:
        return

    squares = get_card_target_squares(card)
    if not squares:
        return

    # Blink the outline on and off (no fill).
    if pygame.time.get_ticks() % 700 >= 350:
        return

    color = (70, 230, 90)
    for r, c in squares:
        x, y = board_to_screen(r, c)
        rect = pygame.Rect(x, y, SQUARE_W, SQUARE_H)
        draw_corner_brackets(rect, color, thickness=max(3, SQUARE_W // 22))


def draw_board():
    # Pixel-art board with its own frame baked into the image.
    screen.blit(BOARD_IMAGE, (BOARD_X - BOARD_IMAGE_OX, BOARD_Y - BOARD_IMAGE_OY))

    # Coordinates inside the edge squares, tinted with the opposite
    # square color so they never collide with the frame.
    files = "abcdefgh"
    ranks = "87654321"

    for display_col in range(8):
        if is_board_flipped():
            label = files[7 - display_col]
        else:
            label = files[display_col]

        color = DARK_SQUARE if (7 + display_col) % 2 == 0 else LIGHT_SQUARE
        text = tiny_font.render(label, True, color)
        x = BOARD_X + display_col * SQUARE_W + SQUARE_W - text.get_width() - 4
        y = BOARD_Y + BOARD_H - text.get_height() - 2
        screen.blit(text, (x, y))

    for display_row in range(8):
        if is_board_flipped():
            label = ranks[7 - display_row]
        else:
            label = ranks[display_row]

        color = DARK_SQUARE if display_row % 2 == 0 else LIGHT_SQUARE
        text = tiny_font.render(label, True, color)
        screen.blit(text, (BOARD_X + 4, BOARD_Y + display_row * SQUARE_H + 3))

    if game.is_in_check(game.turn):
        king_pos = game.find_king(game.turn)

        if king_pos is not None:
            kr, kc = king_pos
            x, y = board_to_screen(kr, kc)
            rect = pygame.Rect(x, y, SQUARE_W, SQUARE_H)
            check_surface = pygame.Surface((SQUARE_W, SQUARE_H), pygame.SRCALPHA)
            check_surface.fill((220, 35, 35, 135))
            screen.blit(check_surface, rect)

    if game.selected is not None:
        row, col = game.selected
        x, y = board_to_screen(row, col)
        rect = pygame.Rect(x, y, SQUARE_W, SQUARE_H)
        pygame.draw.rect(screen, SELECT_COLOR, rect, max(4, SQUARE_SIZE // 18))

    for move in game.legal_moves_for_selected:
        row, col = move
        x, y = board_to_screen(row, col)
        rect = pygame.Rect(x, y, SQUARE_W, SQUARE_H)

        if game.board[row][col] is None:
            draw_corner_brackets(rect, LEGAL_MOVE_COLOR, thickness=max(3, SQUARE_W // 22))
        else:
            draw_corner_brackets(rect, CAPTURE_COLOR, thickness=max(4, SQUARE_W // 16))


def draw_badge(text, color, topleft):
    label = badge_font.render(text, True, color)
    pad = 3
    bg = pygame.Surface((label.get_width() + pad * 2, label.get_height() + pad * 2), pygame.SRCALPHA)
    pygame.draw.rect(bg, (15, 12, 10, 215), bg.get_rect(), border_radius=6)
    screen.blit(bg, topleft)
    screen.blit(label, (topleft[0] + pad, topleft[1] + pad))


def draw_fire_tiles():
    ticks = pygame.time.get_ticks()

    for (row, col), turns_remaining in game.fire_tiles.items():
        x, y = board_to_screen(row, col)
        rect = pygame.Rect(x, y, SQUARE_W, SQUARE_H)

        # Subtle tint so the dangerous square reads even between flames.
        fire_surface = pygame.Surface((SQUARE_W, SQUARE_H), pygame.SRCALPHA)
        fire_surface.fill((255, 80, 0, 55))
        screen.blit(fire_surface, rect)

        if FIRE_FRAMES:
            # Looping campfire; per-tile phase so fires don't burn in sync.
            index = (ticks // 90 + row * 3 + col * 5) % len(FIRE_FRAMES)
            frame = FIRE_FRAMES[index]
            screen.blit(frame, frame.get_rect(midbottom=(rect.centerx, rect.bottom - SQUARE_H // 12)))
        else:
            cx, cy = rect.center
            for i in range(3):
                radius = int(SQUARE_H * (0.18 + i * 0.08))
                pygame.draw.circle(screen, (255, 160 - i * 30, 30), (cx, cy - i * 4), radius, 2)

        draw_badge(f"{turns_remaining}", (255, 230, 180), (rect.x + 4, rect.y + 4))


_piece_cache = {}
_piece_shadow = None


def get_piece_shadow():
    global _piece_shadow

    if _piece_shadow is None:
        size = (int(SQUARE_W * 0.62), max(6, int(SQUARE_H * 0.30)))
        _piece_shadow = pygame.Surface(size, pygame.SRCALPHA)
        # Two ellipses give the shadow a softer edge; per-blit set_alpha
        # scales the whole thing.
        pygame.draw.ellipse(_piece_shadow, (0, 0, 0, 150), _piece_shadow.get_rect())
        inner = _piece_shadow.get_rect().inflate(-size[0] // 4, -size[1] // 4)
        pygame.draw.ellipse(_piece_shadow, (0, 0, 0, 255), inner)

    return _piece_shadow


def _load_themed_sprite(spec, piece):
    name = PIECE_NAMES[piece.lower()]

    if spec[0] == "asset":
        _, folder, prefix = spec
        return pygame.image.load(
            os.path.join(ASSET_DIR, "pieces", folder, f"{prefix}_{name}.png")
        ).convert_alpha()

    # Tint: recolor the classic light sprite by multiplying with the color.
    # Multiply leaves the dark outline dark and transparent pixels untouched.
    base = pygame.image.load(
        os.path.join(ASSET_DIR, "pieces", "classic", f"W_{name}.png")
    ).convert_alpha()
    tint = pygame.Surface(base.get_size(), pygame.SRCALPHA)
    tint.fill((*spec[1], 255))
    base.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    return base


def get_piece_surface(piece, lifted=False):
    skin_index = white_skin_index if piece.isupper() else black_skin_index
    key = (skin_index, piece, lifted)

    if key not in _piece_cache:
        spec = PIECE_SKINS[skin_index]["spec"]
        sprite = _load_themed_sprite(spec, piece)
        # Nearest-neighbour scaling keeps the pixel art crisp. A picked-up
        # piece is drawn slightly larger so it reads as closer to the camera.
        scale = 1.12 if lifted else 1.0
        size = (round(SQUARE_SIZE * scale), round(SQUARE_SIZE * 2 * scale))
        _piece_cache[key] = pygame.transform.scale(sprite, size)

    return _piece_cache[key]


def draw_pieces():
    # Sprites are two squares tall, so draw upper screen rows first and let
    # pieces on lower rows overlap them.
    # Squares whose piece is currently rendered by a drop/land animation.
    animated_squares = {
        anim["extra"]["square"]
        for anim in animations
        if anim["kind"] in ("piece_drop", "piece_land")
    }
    # The teleporting queen is drawn by the teleport animation until it lands.
    animated_squares |= {anim["extra"]["to"] for anim in animations if anim["kind"] == "teleport"}
    # Gravity Storm pieces are drawn by their slide animation until they arrive.
    animated_squares |= {anim["extra"]["to"] for anim in animations if anim["kind"] == "slide"}

    occupied = []
    for row in range(ROWS):
        for col in range(COLS):
            piece = game.board[row][col]

            if piece is None:
                continue

            # The dragged piece is drawn at the mouse position instead.
            if (row, col) == dragging_piece:
                continue

            if (row, col) in animated_squares:
                continue

            x, y = board_to_screen(row, col)
            occupied.append((y, x, row, col, piece))

    ticks = pygame.time.get_ticks()

    render_list = []
    for y, x, row, col, piece in sorted(occupied):
        # Gentle idle bob (lift only, so pieces never sink into the board).
        # Per-square phase keeps the pieces from moving in lockstep.
        phase = (row * 3 + col * 5) * 0.6
        lift = (math.sin(ticks / 350.0 + phase) + 1) / 2
        bob = round(lift * max(2, SQUARE_SIZE // 20))
        render_list.append((y, x, row, col, piece, bob))

    # Ground shadows first, in their own pass, so a shadow never draws on
    # top of a neighbouring piece. The shadow fades as the piece bobs up.
    shadow = get_piece_shadow()
    for y, x, row, col, piece, bob in render_list:
        shadow.set_alpha(115 - bob * 9)
        screen.blit(shadow, shadow.get_rect(center=(x + SQUARE_W // 2, y + SQUARE_H - SQUARE_H // 10)))

    for y, x, row, col, piece, bob in render_list:
        piece_surface = get_piece_surface(piece)
        piece_rect = piece_surface.get_rect(
            midbottom=(x + SQUARE_W // 2, y + SQUARE_H - SQUARE_H // 12 - bob)
        )
        screen.blit(piece_surface, piece_rect)

        if (row, col) in game.rookdemon_rooks:
            remaining = game.rookdemon_rooks[(row, col)]
            draw_badge(f"D{remaining}", (255, 110, 40), (x + 4, y + SQUARE_H - 23))

        if (row, col) == game.windknight_square:
            draw_badge(f"W{game.windknight_moves_remaining}", (90, 220, 255), (x + SQUARE_W - 30, y + SQUARE_H - 23))

        if (row, col) in game.dramatic_pieces:
            draw_badge("D!", (255, 230, 60), (x + SQUARE_W - 28, y + 4))

        if (row, col) == game.inzone_square:
            draw_badge("Z!", (255, 90, 90), (x + 4, y + 4))


# Everything on a card face is static except the wavy name, so the face is
# composed once per (owner, card, state) and reused; the name is drawn on
# top each frame.
_card_face_cache = {}


def get_card_face(owner, card_name, size, used, affordable):
    key = (owner, card_name, size, used, affordable)

    if key in _card_face_cache:
        return _card_face_cache[key]

    width, height = size
    _, fallback_color, _ = CARD_INFO.get(card_name, (card_name, (70, 70, 70), ""))
    cost = CARD_COSTS.get(card_name, 0)

    image = get_scaled_card_image(owner, card_name, width, height)
    card_surface = pygame.Surface(size, pygame.SRCALPHA)

    if image is not None:
        card_surface.blit(image, (0, 0))
    else:
        # Fallback art: colored plate with a gold ring.
        pygame.draw.rect(card_surface, WOOD_FRAME_DARK, card_surface.get_rect(), border_radius=8)
        inner = pygame.Rect(3, 3, width - 6, height - 6)
        pygame.draw.rect(card_surface, fallback_color, inner, border_radius=6)
        pygame.draw.circle(card_surface, (*GOLD, 120), (width // 2, height // 2), width // 3, 2)

    # Name strip along the bottom so every card is identifiable at a glance.
    strip_h = max(18, height // 8)
    strip = pygame.Surface((width, strip_h), pygame.SRCALPHA)
    strip.fill((12, 9, 6, 205))
    card_surface.blit(strip, (0, height - strip_h))

    # Cost chip in the top-right corner; gold when affordable, gray when not.
    chip_text = badge_font.render(str(cost), True, (25, 18, 8))
    chip_w = chip_text.get_width() + 10
    chip_h = chip_text.get_height() + 4
    chip = pygame.Rect(width - chip_w - 4, 4, chip_w, chip_h)
    pygame.draw.rect(card_surface, GOLD if affordable else (130, 125, 110), chip, border_radius=8)
    card_surface.blit(chip_text, chip_text.get_rect(center=chip.center))

    if used:
        overlay = pygame.Surface(size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        card_surface.blit(overlay, (0, 0))

        used_surface = badge_font.render("USED", True, TEXT_COLOR)
        card_surface.blit(used_surface, used_surface.get_rect(center=(width // 2, height // 2 - 10)))

        buy_surface = badge_font.render(f"Refill: {cost}", True, GOLD if affordable else MUTED_TEXT)
        card_surface.blit(buy_surface, buy_surface.get_rect(center=(width // 2, height // 2 + 10)))

    _card_face_cache[key] = card_surface
    return card_surface


def get_card_bob(card_name):
    # Idle float for the whole card; the name's wave rides on top of it.
    phase = sum(map(ord, card_name)) % 10
    return round(math.sin(pygame.time.get_ticks() * 0.002 + phase) * 3)


# How high a card rises and how strongly it dims when not hovered. The eased
# per-card hover amount (0 resting, 1 hovered) lives in _card_hover_anim and is
# advanced each frame in draw_sidebar.
CARD_HOVER_LIFT = int(CARD_HEIGHT * 0.09)
CARD_REST_DIM = 45  # alpha of the shade laid over a fully-rested card
_card_hover_anim = {}


def draw_single_card(rect, owner, card_name, hover=1.0, lift=0):
    # Cards in hand are always playable (no "used" state in the deck system).
    used = False
    display_name, accent, _ = CARD_INFO.get(card_name, (card_name, (70, 70, 70), ""))
    affordable = game.ether[view_color()] >= CARD_COSTS.get(card_name, 0)

    rect = rect.move(0, get_card_bob(card_name) - lift)

    # A halo in the card's general color sits behind it, faint at rest and
    # blooming as the card lifts on hover. Lighten the accent so it reads as a
    # glow rather than a dark plate.
    glow_color = tuple(min(255, c + 100) for c in accent)
    base = max(2, int(CARD_WIDTH * 0.03))
    for i in range(3):
        spread = base + round(base * 0.6 * hover) + i * base
        alpha = int((90 + 165 * hover) * (1 - i / 3))
        halo = pygame.Surface((rect.width + spread * 2, rect.height + spread * 2), pygame.SRCALPHA)
        pygame.draw.rect(halo, (*glow_color, min(255, alpha)), halo.get_rect(), border_radius=16)
        screen.blit(halo, (rect.x - spread, rect.y - spread))

    screen.blit(get_card_face(owner, card_name, rect.size, used, affordable), rect)

    # Dim and red-mark cards selected for discard.
    if card_name in game.discard_marks:
        mark = pygame.Surface(rect.size, pygame.SRCALPHA)
        mark.fill((180, 30, 30, 90))
        screen.blit(mark, rect)
        pygame.draw.rect(screen, (240, 80, 80), rect, 3, border_radius=8)

    strip_h = max(18, rect.height // 8)
    name_text = clip_text(badge_font, display_name, rect.width - 6)
    name_x = rect.x + (rect.width - badge_font.size(name_text)[0]) // 2
    name_y = rect.y + rect.height - strip_h // 2 - badge_font.get_height() // 2
    draw_wavy_text(
        badge_font,
        name_text,
        PARCHMENT,
        (name_x, name_y),
        amp=1,
        offset=1,
        phase=sum(map(ord, card_name)) % 10,
    )

    border_color = CARD_DISABLED if used else CARD_BORDER
    pygame.draw.rect(screen, border_color, rect, 2, border_radius=8)

    # Rested cards sit a little dim; they brighten as the cursor lands on them.
    dim = round(CARD_REST_DIM * (1 - hover))
    if dim > 0:
        shade = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(shade, (0, 0, 0, dim), shade.get_rect(), border_radius=8)
        screen.blit(shade, rect)


def rematch_available():
    # A rematch button is offered for local games, and for the online host (the
    # joiner just receives the host's fresh position automatically).
    if game.winner_message is None:
        return False
    if game_mode == "online":
        return net is not None and net.connected and net_local_color == WHITE
    return True


def get_rematch_button():
    box_w = min(BOARD_W - 80, 620)
    box = pygame.Rect(0, 0, box_w, 110)
    box.center = (BOARD_X + BOARD_W // 2, BOARD_Y + BOARD_H // 2)
    btn = pygame.Rect(0, 0, 220, 48)
    btn.center = (box.centerx, box.bottom + 40)
    return btn


def do_rematch():
    global _last_saved_turn
    if game_mode == "online":
        if net is not None and net.connected and net_local_color == WHITE:
            start_new_game()
            net_reset_sync()
            net.send(net_serialize_state())
        return
    delete_save()
    _last_saved_turn = None
    if game_mode == "pvc":
        ai_reset()
        configure_engine()
    start_new_game()


def draw_game_over_overlay():
    if game.winner_message is None:
        return

    overlay = pygame.Surface((BOARD_W, BOARD_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 105))
    screen.blit(overlay, (BOARD_X, BOARD_Y))

    box_w = min(BOARD_W - 80, 620)
    box_h = 110
    box = pygame.Rect(0, 0, box_w, box_h)
    box.center = (BOARD_X + BOARD_W // 2, BOARD_Y + BOARD_H // 2)

    pygame.draw.rect(screen, WOOD_FRAME_DARK, box, border_radius=16)
    pygame.draw.rect(screen, GOLD, box, 4, border_radius=16)

    title = title_font.render("GAME OVER", True, GOLD)
    title_rect = title.get_rect(center=(box.centerx, box.y + 34))
    screen.blit(title, title_rect)

    result = render_clipped(small_font, game.winner_message, TEXT_COLOR, box.width - 40)
    result_rect = result.get_rect(center=(box.centerx, box.y + 74))
    screen.blit(result, result_rect)

    if rematch_available():
        btn = get_rematch_button()
        hot = btn.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(screen, (90, 200, 120) if hot else WOOD_FRAME_DARK, btn, border_radius=10)
        pygame.draw.rect(screen, (120, 230, 150), btn, 3, border_radius=10)
        lbl = small_font.render("REMATCH", True, (235, 255, 240))
        screen.blit(lbl, lbl.get_rect(center=btn.center))
    elif game_mode == "online":
        wait = small_font.render("Waiting for host to start a rematch...", True, TEXT_COLOR)
        screen.blit(wait, wait.get_rect(center=(box.centerx, box.bottom + 36)))


def draw_wait_banner():
    # A small status pill when the player can't act: computer thinking, or the
    # opponent's turn online.
    msg = None
    if game.game_over:
        return
    if game_mode == "pvc" and game.turn == ai_color():
        msg = "COMPUTER IS THINKING..."
    elif game_mode == "online" and net is not None and net.connected and game.turn != net_local_color:
        msg = "OPPONENT'S TURN..."
    if msg is None:
        return
    surf = small_font.render(msg, True, (245, 235, 180))
    pad = 14
    box = surf.get_rect()
    box.inflate_ip(pad * 2, pad)
    box.center = (BOARD_X + BOARD_W // 2, BOARD_Y + 26)
    bg = pygame.Surface(box.size, pygame.SRCALPHA)
    pygame.draw.rect(bg, (0, 0, 0, 150), bg.get_rect(), border_radius=10)
    screen.blit(bg, box)
    pygame.draw.rect(screen, (180, 160, 90), box, 1, border_radius=10)
    screen.blit(surf, surf.get_rect(center=box.center))


def wrap_text(text, font_obj, max_width):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        candidate = (current + " " + word).strip()
        if font_obj.size(candidate)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def draw_card_preview(owner, card_name, card_rect):
    display_name, _, description = CARD_INFO.get(card_name, (card_name, (70, 70, 70), ""))
    cost = CARD_COSTS.get(card_name, 0)
    used = False

    # A large preview, floated above the hovered card in the tray.
    preview_w = 200
    preview_h = int(preview_w * CARD_ASPECT)
    info_h = 92
    pad = 10
    total_h = preview_h + info_h + pad * 3

    # Centered over the card, clamped to the screen, sitting above the tray.
    panel_x = min(max(SIDE_MARGIN, card_rect.centerx - (preview_w + pad * 2) // 2),
                  SCREEN_WIDTH - preview_w - pad * 2 - SIDE_MARGIN)
    panel_y = max(SIDE_MARGIN, TRAY_Y - total_h - 8)

    panel = pygame.Rect(panel_x, panel_y, preview_w + pad * 2, total_h)
    shadow = pygame.Surface((panel.width + 16, panel.height + 16), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 130), shadow.get_rect(), border_radius=14)
    screen.blit(shadow, (panel.x - 4, panel.y + 2))

    pygame.draw.rect(screen, (24, 18, 12), panel, border_radius=12)
    pygame.draw.rect(screen, GOLD, panel, 2, border_radius=12)

    art_rect = pygame.Rect(panel.x + pad, panel.y + pad, preview_w, preview_h)
    image = get_scaled_card_image(owner, card_name, preview_w, preview_h)

    if image is not None:
        screen.blit(image, art_rect)
    else:
        pygame.draw.rect(screen, CARD_INFO.get(card_name, (None, (70, 70, 70), None))[1], art_rect, border_radius=8)
    pygame.draw.rect(screen, CARD_BORDER, art_rect, 2, border_radius=8)

    text_x = panel.x + pad
    text_y = art_rect.bottom + pad

    name_surface = small_font.render(display_name, True, PARCHMENT)
    screen.blit(name_surface, (text_x, text_y))

    cost_label = f"Refill: {cost} Ether" if used else f"Cost: {cost} Ether"
    cost_surface = tiny_font.render(cost_label, True, GOLD)
    screen.blit(cost_surface, (text_x, text_y + 24))

    line_y = text_y + 44
    for line in wrap_text(description, tiny_font, preview_w)[:2]:
        line_surface = tiny_font.render(line, True, TEXT_COLOR)
        screen.blit(line_surface, (text_x, line_y))
        line_y += 18


def get_action_buttons():
    # Discard on the left of the hand, End Turn on the right.
    bw, bh = ACTION_BTN_W, 84
    cy = TRAY_Y + TRAY_HEIGHT // 2
    discard = pygame.Rect(SIDE_MARGIN, cy - bh // 2, bw, bh)
    end_turn = pygame.Rect(SCREEN_WIDTH - SIDE_MARGIN - bw, cy - bh // 2, bw, bh)
    return {"discard": discard, "end_turn": end_turn}


def draw_sidebar():
    # The hand sits directly on the game background - no tray panel behind it,
    # and the cards are large enough to overlap the board's lower edge.

    # Discard (left) and End Turn (right) buttons, with status counts below.
    discards_left = game.MAX_DISCARDS - game.discards_used[view_color()]
    buttons = get_action_buttons()
    mouse_pos = pygame.mouse.get_pos()
    dragging_to_discard = (
        dragging_card is not None
        and buttons["discard"].collidepoint(mouse_pos)
    )
    meta = {
        "discard": ("DISCARD",
                    (235, 45, 45) if dragging_to_discard else (200, 70, 70),
                    f"{discards_left} left"),
        "end_turn": ("END TURN", (90, 200, 120), f"Deck {len(game.deck[view_color()])}"),
    }
    for key, brect in buttons.items():
        label, color, sub = meta[key]
        hot = brect.collidepoint(mouse_pos)
        fill = pygame.Surface(brect.size, pygame.SRCALPHA)
        fill.fill((*color, 75 if hot else 38))
        screen.blit(fill, brect)
        pygame.draw.rect(screen, color, brect, 3 if hot else 2, border_radius=10)
        lx = brect.centerx - action_font.size(label)[0] // 2
        draw_shadow_text(action_font, label, color, (lx, brect.centery - action_font.get_height() // 2), offset=2)
        sx = brect.centerx - tiny_font.size(sub)[0] // 2
        draw_shadow_text(tiny_font, sub, MUTED_TEXT, (sx, brect.bottom + 4), offset=1)

    card_rects = get_card_rects()
    mouse_pos = pygame.mouse.get_pos()
    flight = cards_in_flight()  # cards still flying in from the deck stay hidden

    # The card under the cursor (topmost wins, since later cards draw on top).
    hovered = None
    if dragging_card is None:
        for card_name, rect in card_rects.items():
            if card_name not in flight and rect.collidepoint(mouse_pos):
                hovered = card_name

    # Ease each card's hover amount toward its target so the lift and glow
    # animate in and out instead of snapping. Drop stale entries.
    for card_name in [c for c in _card_hover_anim if c not in card_rects]:
        del _card_hover_anim[card_name]
    for card_name in card_rects:
        target = 1.0 if card_name == hovered else 0.0
        cur = _card_hover_anim.get(card_name, 0.0)
        cur += (target - cur) * 0.25
        _card_hover_anim[card_name] = target if abs(cur - target) < 0.01 else cur

    # Resting cards first; the hovered card is redrawn lifted on top.
    for card_name, rect in card_rects.items():
        if dragging_card == card_name or card_name in flight or card_name == hovered:
            continue
        h = _card_hover_anim.get(card_name, 0.0)
        draw_single_card(rect, view_color(), card_name, hover=h, lift=round(CARD_HOVER_LIFT * h))

    # Redraw the hovered card on top (cards can overlap), outline it, and float
    # a large readable preview above it.
    if hovered is not None and dragging_card is None:
        h = _card_hover_anim.get(hovered, 1.0)
        lift = round(CARD_HOVER_LIFT * h)
        draw_single_card(card_rects[hovered], view_color(), hovered, hover=h, lift=lift)
        outline = card_rects[hovered].move(0, get_card_bob(hovered) - lift).inflate(6, 6)
        pygame.draw.rect(screen, (255, 220, 110), outline, 3, border_radius=10)
        draw_card_preview(view_color(), hovered, card_rects[hovered])


def draw_dragging_card():
    if dragging_card is None:
        return

    mouse_x, mouse_y = pygame.mouse.get_pos()

    rect = pygame.Rect(0, 0, CARD_WIDTH, CARD_HEIGHT)
    rect.center = (mouse_x, mouse_y)

    draw_single_card(rect, view_color(), dragging_card)


def draw_dragging_piece():
    if dragging_piece is None:
        return

    row, col = dragging_piece
    piece = game.board[row][col]

    if piece is None:
        return

    mouse_pos = pygame.mouse.get_pos()

    # Shortly after pickup the piece eases from its square to the cursor
    # instead of teleporting.
    t = min(1.0, (pygame.time.get_ticks() - dragging_lift_ticks) / 130.0)
    t = 1 - (1 - t) ** 2
    target = (mouse_pos[0], mouse_pos[1] + SQUARE_H // 2)
    base_x = int(dragging_lift_from[0] + (target[0] - dragging_lift_from[0]) * t)
    base_y = int(dragging_lift_from[1] + (target[1] - dragging_lift_from[1]) * t)

    # Outline the square under the cursor when it is a legal drop target.
    hover = get_square_from_mouse(mouse_pos)
    if hover is not None and hover in game.legal_moves_for_selected:
        x, y = board_to_screen(*hover)
        pygame.draw.rect(screen, SELECT_COLOR, pygame.Rect(x, y, SQUARE_W, SQUARE_H), 3)

    # Soft shadow on the board, with the piece floating above it.
    shadow = get_piece_shadow()
    shadow.set_alpha(80)
    screen.blit(shadow, shadow.get_rect(center=(base_x, base_y)))

    piece_surface = get_piece_surface(piece, lifted=True)
    rect = piece_surface.get_rect(midbottom=(base_x, base_y - max(3, SQUARE_H // 10)))
    screen.blit(piece_surface, rect)


def clip_text(font_obj, text, max_width):
    if font_obj.size(text)[0] <= max_width:
        return text

    while text and font_obj.size(text + "...")[0] > max_width:
        text = text[:-1]

    return text + "..."


def render_clipped(font_obj, text, color, max_width):
    return font_obj.render(clip_text(font_obj, text, max_width), True, color)


def draw_ether_chip(label, amount, color, is_active, topleft):
    chip = pygame.Rect(topleft[0], topleft[1], 224, 32)
    pygame.draw.rect(screen, WOOD_FRAME_DARK, chip, border_radius=16)
    pygame.draw.rect(screen, GOLD if is_active else (80, 70, 55), chip, 2, border_radius=16)

    pygame.draw.circle(screen, color, (chip.x + 18, chip.centery), 9)
    pygame.draw.circle(screen, (90, 80, 60), (chip.x + 18, chip.centery), 9, 1)

    text = f"{label}  {amount} Ether"
    text_color = TEXT_COLOR if is_active else MUTED_TEXT
    draw_shadow_text(tiny_font, text, text_color, (chip.x + 34, chip.centery - tiny_font.get_height() // 2), offset=1)


def draw_move_log():
    # Running log on the right of the board: chess moves and cards played.
    btns = get_action_buttons()
    # Narrow panel hugging the right edge, aligned above the End Turn button.
    right = SCREEN_WIDTH - SIDE_MARGIN
    #left = max(BOARD_X + BOARD_W + 50, btns["end_turn"].left)
    left = 1600
    top = INFO_HEIGHT + 14
    bottom = btns["end_turn"].top - 14
    if right - left < 120 or bottom - top < 90:
        return  # not enough room beside the board

    panel = pygame.Rect(left, top, right - left, bottom - top)
    surf = pygame.Surface(panel.size, pygame.SRCALPHA)
    surf.fill((10, 10, 16, 185))
    screen.blit(surf, panel)
    pygame.draw.rect(screen, (78, 78, 98), panel, 2, border_radius=8)

    draw_shadow_text(small_font, "GAME LOG", GOLD, (panel.x + 14, panel.y + 10), offset=1)
    sep_y = panel.y + 14 + small_font.get_height()
    pygame.draw.line(screen, (78, 78, 98), (panel.x + 12, sep_y), (panel.right - 12, sep_y), 1)

    line_h = tiny_font.get_height() + 6
    text_x = panel.x + 30
    max_w = panel.right - 12 - text_x
    list_top = sep_y + 8
    capacity = max(1, (panel.bottom - 10 - list_top) // line_h)
    entries = game.move_log[-capacity:]  # newest entries, oldest first

    y = list_top
    for color, kind, text in entries:
        swatch = pygame.Rect(panel.x + 12, y + 3, 12, 12)
        if color == WHITE:
            pygame.draw.rect(screen, (235, 235, 245), swatch, border_radius=3)
        else:
            pygame.draw.rect(screen, (40, 40, 50), swatch, border_radius=3)
            pygame.draw.rect(screen, (120, 120, 140), swatch, 1, border_radius=3)
        text_color = GOLD if kind == "card" else (224, 224, 236)
        draw_shadow_text(tiny_font, clip_text(tiny_font, text, max_w), text_color, (text_x, y), offset=1)
        y += line_h


def draw_info_panel():
    if game.active_card == "pawntastic":
        card_text = "Pawntastic active: click a highlighted destination."
    elif game.active_card == "windknight":
        card_text = "Windknight active: move the selected knight twice."
    elif game.active_card == "queentum":
        card_text = "Queentum active: click any legal teleport destination."
    elif game.active_card == "inzone":
        card_text = "InZone active: keep capturing with the selected piece."
    elif game.active_card == "gambit":
        card_text = "Gambit active: click your pieces to sacrifice them, or click elsewhere to finish."
    else:
        card_text = "Drag cards onto your pieces to play them, or onto DISCARD to redraw. Move a piece, then press END TURN."

    bar = pygame.Rect(0, INFO_Y, SCREEN_WIDTH, INFO_HEIGHT)
    pygame.draw.rect(screen, PANEL_BG, bar)
    pygame.draw.line(screen, PANEL_EDGE, (bar.x, bar.y), (bar.right, bar.y), 3)

    chips_w = 250
    text_w = bar.width - chips_w - 44

    if game.winner_message is not None:
        headline = f"GAME OVER - {game.winner_message}"
    else:
        headline = f"{game.turn.capitalize()} to move"

    x = bar.x + 16
    draw_wavy_text(title_font, clip_text(title_font, headline, text_w), GOLD, (x, bar.y + 8), amp=2, offset=3)

    if game.cheat_mode:
        draw_badge("CHEAT MODE   C: off   T: pass turn", GOLD, (bar.x + 16, bar.bottom + 6))

    active_flags = []
    if game.plague_active:
        active_flags.append("Plague")
    if game.absolute_protection_active:
        active_flags.append("AbsoluteProtection")
    if game.extra_blood_active:
        active_flags.append("ExtraBlood")

    # One status line that fits the thin bar: prefer the latest message, else
    # the active-card hint, else any running effects.
    if game.status_message and game.status_message != headline:
        status_line, status_color = game.status_message, TEXT_COLOR
    elif active_flags:
        status_line, status_color = "Active effects: " + ", ".join(active_flags), GOLD
    else:
        status_line, status_color = card_text, MUTED_TEXT

    draw_shadow_text(tiny_font, clip_text(tiny_font, status_line, text_w), status_color, (x, bar.y + 60))

    # Ether totals on the right; the side to move is highlighted.
    chips_x = bar.right - chips_w
    draw_ether_chip("White", game.ether[WHITE], (240, 240, 235), game.turn == WHITE, (chips_x, bar.y + 14))
    draw_ether_chip("Black", game.ether[BLACK], (30, 28, 26), game.turn == BLACK, (chips_x, bar.y + 52))



def get_square_from_mouse(pos):
    x, y = pos

    if x < BOARD_X or x >= BOARD_X + BOARD_W:
        return None

    if y < BOARD_Y or y >= BOARD_Y + BOARD_H:
        return None

    display_row = (y - BOARD_Y) // SQUARE_H
    display_col = (x - BOARD_X) // SQUARE_W

    if is_board_flipped():
        row = 7 - display_row
        col = 7 - display_col
    else:
        row = display_row
        col = display_col

    return row, col


# =====================================================================
# Start screen and menus (Balatro-style m6x11 UI)
# =====================================================================
MENU_BG1 = (16, 12, 28)
MENU_BG2 = (22, 16, 36)
MENU_CYAN = (95, 232, 220)
MENU_PINK = (242, 96, 176)
MENU_WHITE = (236, 240, 248)
MENU_MUTED = (122, 112, 154)
MENU_GREEN = (96, 230, 136)
MENU_GOLD = (240, 188, 40)        # CHESSBYTE "BYTE" + selected button
MENU_GOLD_DARK = (40, 30, 6)      # text on top of the gold button
MENU_RED = (224, 104, 92)         # EXIT label

app_state = "menu"  # "menu" | "modeselect" | "lobby" | "playing" | "catalog" | "settings"
menu_selected = 0
modeselect_selected = 0
game_mode = "pvp"  # "pvp" (hot-seat) | "pvc" (vs computer) | "online" (LAN)
human_color = WHITE  # in PvC, the side the human plays (computer takes the other)
difficulty = "Medium"  # "Easy" | "Medium" | "Hard"

# LAN play (host-authoritative full-state sync). All None until a game is hosted
# or joined; see the "Online play" block near the main loop.
net = None             # netplay.NetLink while online, else None
net_local_color = None  # WHITE for the host, BLACK for the joiner
net_join_text = ""      # host address the joiner types (blank = auto-find)
_net_prev_turn = None   # for detecting "I just ended my turn" -> push state
_net_prev_over = False
_online_dealt = False   # host: has it dealt + sent the opening position yet
_last_saved_turn = None  # auto-save the local game whenever the turn changes

# Smooth fade-to-black transition between screens. progress runs 0 -> 1; the
# screen switches at the half-way point (fully black), so it fades out then in.
TRANSITION_STEP = 0.6
_transition = {"active": False, "progress": 0.0, "target": None, "switched": False, "on_switch": None}


def request_transition(target, on_switch=None):
    if _transition["active"] or target == app_state:
        return
    _transition.update(active=True, progress=0.0, target=target, switched=False, on_switch=on_switch)


def update_transition():
    global app_state
    if not _transition["active"]:
        return
    _transition["progress"] += TRANSITION_STEP
    if _transition["progress"] >= 0.5 and not _transition["switched"]:
        if _transition["on_switch"]:
            _transition["on_switch"]()
        app_state = _transition["target"]
        _transition["switched"] = True
    if _transition["progress"] >= 1.0:
        _transition["active"] = False


def draw_transition_overlay():
    if not _transition["active"]:
        return
    alpha = int(255 * (1 - abs(_transition["progress"] - 0.5) * 2))
    if alpha <= 0:
        return
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    overlay.fill((0, 0, 0))
    overlay.set_alpha(alpha)
    screen.blit(overlay, (0, 0))


def start_new_game():
    global game, dragging_card, dragging_piece
    game = GameState()
    dragging_card = None
    dragging_piece = None
    animate_initial_hand()

MENU_ITEMS = [
    {"label": "START", "action": "start", "icon": "pawn", "key": "enter", "accent": MENU_GOLD},
    {"label": "CATALOG", "action": "catalog", "icon": "spade", "key": "C", "accent": MENU_WHITE},
    {"label": "SETTINGS", "action": "settings", "icon": "gear", "key": "S", "accent": MENU_WHITE},
    {"label": "EXIT", "action": "exit", "icon": "x", "key": "Q", "accent": MENU_RED},
]


def current_menu_items():
    # CONTINUE appears only when a saved game exists (just below START).
    items = list(MENU_ITEMS)
    if has_save():
        items.insert(1, {"label": "CONTINUE", "action": "continue",
                         "icon": "heart", "key": "enter", "accent": MENU_GREEN})
    return items


def draw_menu_background():
    # Same galaxy background and drifting cards as the gameplay screen, so the
    # menus and the game share one look.
    if BACKGROUND_IMAGE is not None:
        screen.blit(BACKGROUND_IMAGE, (0, 0))
    else:
        screen.fill(MENU_BG1)
    draw_floating_cards()


def draw_icon(kind, cx, cy, s, color):
    r = max(2, s // 5)
    if kind == "pawn":
        pygame.draw.circle(screen, color, (cx, cy - s // 3), r)
        pygame.draw.polygon(screen, color, [
            (cx - s // 3, cy + s // 3), (cx + s // 3, cy + s // 3),
            (cx + r, cy - s // 8), (cx - r, cy - s // 8)])
        pygame.draw.rect(screen, color, (cx - s // 3 - 2, cy + s // 3, 2 * (s // 3) + 4, max(2, s // 7)))
    elif kind == "club":
        pygame.draw.circle(screen, color, (cx, cy - r), r)
        pygame.draw.circle(screen, color, (cx - r, cy + r // 2), r)
        pygame.draw.circle(screen, color, (cx + r, cy + r // 2), r)
        pygame.draw.rect(screen, color, (cx - r // 3, cy, max(2, 2 * r // 3), r + s // 5))
    elif kind == "heart":
        pygame.draw.circle(screen, color, (cx - r, cy - r // 2), r)
        pygame.draw.circle(screen, color, (cx + r, cy - r // 2), r)
        pygame.draw.polygon(screen, color, [
            (cx - 2 * r, cy - r // 3), (cx + 2 * r, cy - r // 3), (cx, cy + s // 2)])
    elif kind == "spade":
        pygame.draw.polygon(screen, color, [
            (cx, cy - s // 2), (cx - 2 * r, cy + r // 2), (cx + 2 * r, cy + r // 2)])
        pygame.draw.circle(screen, color, (cx - r, cy + r // 2), r)
        pygame.draw.circle(screen, color, (cx + r, cy + r // 2), r)
        pygame.draw.rect(screen, color, (cx - r // 3, cy + r // 2, max(2, 2 * r // 3), r))
    elif kind == "gear":
        pygame.draw.circle(screen, color, (cx, cy), s // 2, 3)
        pygame.draw.circle(screen, color, (cx, cy), max(2, s // 5))
        for i in range(8):
            a = i * math.pi / 4
            pygame.draw.line(screen, color,
                (cx + int(math.cos(a) * s // 2), cy + int(math.sin(a) * s // 2)),
                (cx + int(math.cos(a) * (s // 2 + s // 5)), cy + int(math.sin(a) * (s // 2 + s // 5))), 3)
    elif kind == "x":
        h = s // 2
        pygame.draw.line(screen, color, (cx - h, cy - h), (cx + h, cy + h), 4)
        pygame.draw.line(screen, color, (cx - h, cy + h), (cx + h, cy - h), 4)


def draw_neon_card(cx, cy, color, suit):
    w, h = 88, 120
    glow = pygame.Surface((w + 20, h + 20), pygame.SRCALPHA)
    pygame.draw.rect(glow, (*color, 55), glow.get_rect(), border_radius=14)
    screen.blit(glow, glow.get_rect(center=(cx, cy)))
    rect = pygame.Rect(0, 0, w, h)
    rect.center = (cx, cy)
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (*MENU_BG1, 230), panel.get_rect(), border_radius=10)
    screen.blit(panel, rect)
    pygame.draw.rect(screen, color, rect, 2, border_radius=10)
    draw_icon(suit, cx, cy, 30, color)


def draw_enter_arrow(cx, cy, color):
    pygame.draw.line(screen, color, (cx + 6, cy - 5), (cx + 6, cy + 2), 2)
    pygame.draw.line(screen, color, (cx + 6, cy + 2), (cx - 4, cy + 2), 2)
    pygame.draw.polygon(screen, color, [(cx - 4, cy - 2), (cx - 4, cy + 6), (cx - 9, cy + 2)])


def draw_key_badge(center, text, color):
    rect = pygame.Rect(0, 0, 30, 26)
    rect.center = center
    pygame.draw.rect(screen, MENU_BG2, rect, border_radius=6)
    pygame.draw.rect(screen, color, rect, 1, border_radius=6)
    if text == "enter":
        draw_enter_arrow(rect.centerx, rect.centery, color)
    else:
        label = badge_font.render(text, True, color)
        screen.blit(label, label.get_rect(center=rect.center))


def draw_glow_title(text, color, center):
    halo = menu_title_font.render(text, True, color)
    rect = halo.get_rect(center=center)
    for ox, oy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
        ghost = halo.copy()
        ghost.set_alpha(60)
        screen.blit(ghost, (rect.x + ox, rect.y + oy))
    return rect


def get_menu_rects():
    bw = int(min(560, SCREEN_WIDTH * 0.46))
    bh = max(58, int(SCREEN_HEIGHT * 0.094))
    gap = max(10, int(SCREEN_HEIGHT * 0.018))
    top = int(SCREEN_HEIGHT * 0.46)
    x = (SCREEN_WIDTH - bw) // 2
    return [pygame.Rect(x, top + i * (bh + gap), bw, bh) for i in range(len(current_menu_items()))]


def draw_back_hint():
    draw_shadow_text(small_font, "ESC  BACK", MENU_MUTED, (40, SCREEN_HEIGHT - 44))


def spaced_word_width(font_obj, text, spacing):
    return sum(font_obj.size(ch)[0] for ch in text) + spacing * (len(text) - 1)


def draw_spaced_word(font_obj, text, color, x, y, spacing):
    # Render letter-spaced text starting at x; returns the width used.
    start = x
    for ch in text:
        g = font_obj.render(ch, True, color)
        screen.blit(g, (x, y))
        x += g.get_width() + spacing
    return x - spacing - start


def draw_tagline(font_obj, words, color, center_x, y, letter_spacing=5, sep_gap=30):
    # Letter-spaced words separated by small diamond markers (the pixel font has
    # no middle-dot glyph, so the separators are drawn by hand).
    widths = [spaced_word_width(font_obj, w, letter_spacing) for w in words]
    total = sum(widths) + sep_gap * (len(words) - 1)
    x = center_x - total // 2
    cy = y + font_obj.get_height() // 2
    for i, w in enumerate(words):
        draw_spaced_word(font_obj, w, color, x, y, letter_spacing)
        x += widths[i]
        if i < len(words) - 1:
            dcx = x + sep_gap // 2
            pygame.draw.polygon(screen, color, [
                (dcx, cy - 4), (dcx + 4, cy), (dcx, cy + 4), (dcx - 4, cy)])
            x += sep_gap


def draw_start_screen():
    draw_menu_background()

    # Title: CHESS (white) + BYTE (gold), with a soft outline so it reads on the
    # busy galaxy background.
    chess = home_title_font.render("CHESS", True, MENU_WHITE)
    byte = home_title_font.render("BYTE", True, MENU_GOLD)
    total_w = chess.get_width() + byte.get_width()
    tx = (SCREEN_WIDTH - total_w) // 2
    ty = int(SCREEN_HEIGHT * 0.04)
    outline = home_title_font.render("CHESSBYTE", True, (0, 0, 0))
    for ox, oy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-3, -3), (3, 3), (3, -3), (-3, 3)):
        ghost = outline.copy()
        ghost.set_alpha(150)
        screen.blit(ghost, (tx + ox, ty + oy))
    screen.blit(chess, (tx, ty))
    screen.blit(byte, (tx + chess.get_width(), ty))

    # Subtitle: spaced caps tagline under the logo.
    sy = ty + chess.get_height() - 6
    #draw_tagline(subtitle_font, ["DEAL", "DEPLOY", "CHECKMATE"],
    #             MENU_WHITE, SCREEN_WIDTH // 2, sy)

    # Menu buttons: flat rounded bars with a left-aligned label. The selected
    # one is a filled gold bar with dark text and a glow; the rest are dark glass.
    for i, (item, rect) in enumerate(zip(current_menu_items(), get_menu_rects())):
        selected = i == menu_selected
        accent = item["accent"]

        if selected:
            # Outer glow halo behind the gold bar.
            glow = pygame.Surface((rect.w + 24, rect.h + 24), pygame.SRCALPHA)
            pygame.draw.rect(glow, (*accent, 70), glow.get_rect(), border_radius=12)
            screen.blit(glow, (rect.x - 12, rect.y - 12))
            pygame.draw.rect(screen, accent, rect, border_radius=8)
            pygame.draw.rect(screen, (255, 232, 150), rect, 3, border_radius=8)
            text_color = MENU_GOLD_DARK
        else:
            panel = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            pygame.draw.rect(panel, (10, 10, 14, 175), panel.get_rect(), border_radius=8)
            screen.blit(panel, rect)
            pygame.draw.rect(screen, (70, 70, 86), rect, 2, border_radius=8)
            text_color = accent if accent == MENU_RED else (228, 228, 238)

        label = item["label"]
        lx = rect.x + 28
        ly = rect.centery - menu_option_font.get_height() // 2
        if selected:
            draw_shadow_text(menu_option_font, label, text_color, (lx, ly), offset=0)
        else:
            draw_shadow_text(menu_option_font, label, text_color, (lx, ly), offset=2)

    # Footer: version on the left, controls hint on the right.
    draw_shadow_text(small_font, "v0.8.1", GOLD, (40, SCREEN_HEIGHT - 40))

    # Controls hint "[^v] SELECT  .  [enter] CONFIRM" with hand-drawn arrows
    # (the pixel font has no arrow/dot glyphs).
    sel = hint_font.render("SELECT", True, MENU_WHITE)
    conf = hint_font.render("CONFIRM", True, MENU_WHITE)
    arrows_w, gap1, dot_w, gap2, enter_w = 26, 8, 22, 8, 22
    total = arrows_w + gap1 + sel.get_width() + dot_w + enter_w + gap2 + conf.get_width()
    x = SCREEN_WIDTH - total - 40
    cy = SCREEN_HEIGHT - 40 + hint_font.get_height() // 2

    # Up + down arrows, side by side.
    pygame.draw.polygon(screen, MENU_WHITE, [(x + 5, cy - 7), (x + 1, cy), (x + 9, cy)])
    pygame.draw.rect(screen, MENU_WHITE, (x + 4, cy, 3, 7))
    pygame.draw.polygon(screen, MENU_WHITE, [(x + 19, cy + 7), (x + 15, cy), (x + 23, cy)])
    pygame.draw.rect(screen, MENU_WHITE, (x + 18, cy - 7, 3, 7))
    x += arrows_w + gap1
    screen.blit(sel, (x, SCREEN_HEIGHT - 40))
    x += sel.get_width()
    # Diamond separator.
    pygame.draw.polygon(screen, MENU_MUTED, [
        (x + dot_w // 2, cy - 4), (x + dot_w // 2 + 4, cy),
        (x + dot_w // 2, cy + 4), (x + dot_w // 2 - 4, cy)])
    x += dot_w
    # Enter / return arrow.
    draw_enter_arrow(x + 11, cy, MENU_WHITE)
    x += enter_w + gap2
    screen.blit(conf, (x, SCREEN_HEIGHT - 40))


CATALOG_COL_W = int(SCREEN_WIDTH * 0.42)


def get_catalog_rects():
    # Shared by the catalog's draw and click handling so the checkbox/row
    # hit-boxes always line up with what is on screen.
    cards = PIECE_POWER_CARDS + GENERAL_CARDS
    x0 = (SCREEN_WIDTH - CATALOG_COL_W * 2 - 50) // 2
    y0 = int(SCREEN_HEIGHT * 0.24)
    rows = (len(cards) + 1) // 2
    line_h = int((SCREEN_HEIGHT * 0.62) / rows)
    box = max(18, int(line_h * 0.30))

    out = []
    for i, name in enumerate(cards):
        x = x0 + (i % 2) * (CATALOG_COL_W + 50)
        y = y0 + (i // 2) * line_h
        check = pygame.Rect(x, y, box, box)
        row = pygame.Rect(x, y - 2, CATALOG_COL_W, line_h - 4)
        out.append((name, check, row))
    return out


def draw_catalog_screen():
    draw_menu_background()
    screen.blit(menu_title_font.render("CATALOG", True, MENU_PINK),
                draw_glow_title("CATALOG", MENU_PINK, (SCREEN_WIDTH // 2, int(SCREEN_HEIGHT * 0.12))))

    # A soft panel behind the list so the cards read against the busy galaxy.
    rects = get_catalog_rects()
    bounds = rects[0][2].unionall([r for _, _, r in rects])
    panel_rect = bounds.inflate(48, 48)
    panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, (*MENU_BG1, 205), panel.get_rect(), border_radius=16)
    screen.blit(panel, panel_rect)
    pygame.draw.rect(screen, MENU_PINK, panel_rect, 2, border_radius=16)

    mx, my = pygame.mouse.get_pos()
    for name, check, row in rects:
        disp, _, desc = CARD_INFO.get(name, (name, (0, 0, 0), ""))
        cost = CARD_COSTS.get(name, 0)
        on = name in enabled_cards
        hover = row.collidepoint(mx, my)

        # Checkbox: a box that holds a tick when the card is in the game.
        border = MENU_GREEN if on else (MENU_WHITE if hover else MENU_MUTED)
        pygame.draw.rect(screen, border, check, 2, border_radius=4)
        if on:
            pygame.draw.lines(screen, MENU_GREEN, False, [
                (check.left + check.w * 0.20, check.top + check.h * 0.52),
                (check.left + check.w * 0.42, check.top + check.h * 0.74),
                (check.left + check.w * 0.80, check.top + check.h * 0.26),
            ], 3)

        tx = check.right + 12
        title_color = MENU_CYAN if on else MENU_MUTED
        draw_shadow_text(small_font, f"{disp}  ({cost})", title_color, (tx, check.top - 2))
        draw_shadow_text(tiny_font, clip_text(tiny_font, desc, CATALOG_COL_W - (tx - row.left) - 10),
                         MENU_MUTED, (tx, check.top + 20))

    enabled_n = sum(1 for c in (PIECE_POWER_CARDS + GENERAL_CARDS) if c in enabled_cards)
    draw_shadow_text(small_font,
                     f"CLICK A CARD TO TICK IT IN / OUT  -  {enabled_n} IN THE GAME",
                     MENU_WHITE, (SCREEN_WIDTH // 2 - int(SCREEN_WIDTH * 0.18),
                                  int(SCREEN_HEIGHT * 0.88)))

    draw_back_hint()


def draw_settings_screen():
    draw_menu_background()
    screen.blit(menu_title_font.render("SETTINGS", True, MENU_CYAN),
                draw_glow_title("SETTINGS", MENU_CYAN, (SCREEN_WIDTH // 2, int(SCREEN_HEIGHT * 0.12))))

    x = int(SCREEN_WIDTH * 0.30)
    y = int(SCREEN_HEIGHT * 0.30)
    rows = [
        ("MUSIC", "Off" if music_muted else "On", "M"),
        ("WHITE PIECES", PIECE_SKINS[white_skin_index]["name"], "1"),
        ("BLACK PIECES", PIECE_SKINS[black_skin_index]["name"], "2"),
        ("BOARD", f"#{current_board_index + 1}", "B"),
        ("DIFFICULTY (vs CPU)", difficulty, "D"),
        ("PLAY AS (vs CPU)", "White" if human_color == WHITE else "Black", "P"),
    ]
    for label, value, key in rows:
        draw_shadow_text(menu_font, label, MENU_WHITE, (x, y))
        draw_shadow_text(menu_font, value, MENU_CYAN, (x + int(SCREEN_WIDTH * 0.22), y))
        draw_key_badge((x + int(SCREEN_WIDTH * 0.40), y + menu_font.get_height() // 2), key, MENU_MUTED)
        y += 48

    y += 24
    for line in ["IN-GAME KEYS", "R restart    C cheat    T pass turn (cheat)", "ESC return to this menu"]:
        draw_shadow_text(small_font, line, MENU_MUTED, (x, y))
        y += 28

    draw_back_hint()


def menu_activate(action):
    global running
    if action == "start":
        request_transition("modeselect")
    elif action == "continue":
        if load_game():
            request_transition("playing")
    elif action == "catalog":
        request_transition("catalog")
    elif action == "settings":
        request_transition("settings")
    elif action == "exit":
        running = False


def handle_menu_events(events):
    global menu_selected, running
    items = current_menu_items()
    rects = get_menu_rects()
    mx, my = pygame.mouse.get_pos()
    for i, r in enumerate(rects):
        if r.collidepoint(mx, my):
            menu_selected = i
    menu_selected %= len(items)

    for event in events:
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                menu_selected = (menu_selected - 1) % len(items)
            elif event.key == pygame.K_DOWN:
                menu_selected = (menu_selected + 1) % len(items)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                menu_activate(items[menu_selected]["action"])
            elif event.key == pygame.K_c:
                menu_activate("catalog")
            elif event.key == pygame.K_s:
                menu_activate("settings")
            elif event.key in (pygame.K_q, pygame.K_ESCAPE):
                menu_activate("exit")
        elif event.type == pygame.MOUSEBUTTONDOWN:
            for i, r in enumerate(rects):
                if r.collidepoint(event.pos):
                    menu_activate(items[i]["action"])


def handle_catalog_events(events):
    global running
    for event in events:
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            request_transition("menu")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Click a card row to tick it in or out of the game.
            for name, check, row in get_catalog_rects():
                if row.collidepoint(event.pos):
                    if name in enabled_cards:
                        enabled_cards.discard(name)
                    else:
                        enabled_cards.add(name)
                    save_config()
                    break


def handle_settings_events(events):
    global running, music_muted, white_skin_index, black_skin_index
    global current_board_index, BOARD_IMAGE, BOARD_IMAGE_OX, BOARD_IMAGE_OY, LIGHT_SQUARE, DARK_SQUARE
    global difficulty, human_color
    for event in events:
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                request_transition("menu")
                continue
            elif event.key == pygame.K_m and _audio_ok:
                music_muted = not music_muted
                pygame.mixer.music.set_volume(0.0 if music_muted else 0.5)
            elif event.key == pygame.K_1:
                white_skin_index = (white_skin_index + 1) % len(PIECE_SKINS)
            elif event.key == pygame.K_2:
                black_skin_index = (black_skin_index + 1) % len(PIECE_SKINS)
            elif event.key == pygame.K_b:
                current_board_index = (current_board_index + 1) % len(BOARD_FILES)
                BOARD_IMAGE, BOARD_IMAGE_OX, BOARD_IMAGE_OY, LIGHT_SQUARE, DARK_SQUARE = (
                    load_pixel_board(BOARD_FILES[current_board_index])
                )
            elif event.key == pygame.K_d:
                order = list(DIFFICULTY_SETTINGS.keys())
                difficulty = order[(order.index(difficulty) + 1) % len(order)]
                configure_engine()
            elif event.key == pygame.K_p:
                human_color = BLACK if human_color == WHITE else WHITE
            else:
                continue
            save_config()  # persist whatever just changed


# -----------------------------
# Mode select (Player vs Player / Player vs Computer)
# -----------------------------
MODE_ITEMS = [
    {"label": "PLAYER VS COMPUTER", "mode": "pvc",
     "sub": "You play White vs Stockfish (regular chess). You can still play cards."},
    {"label": "PLAYER VS PLAYER", "mode": "pvp",
     "sub": "Two players, hot-seat on the same screen."},
    {"label": "HOST GAME (LAN)", "mode": "host",
     "sub": "You play White. Your friend on the same Wi-Fi joins you."},
    {"label": "JOIN GAME (LAN)", "mode": "join",
     "sub": "You play Black. Finds a hosted game on your network automatically."},
]


def get_modeselect_rects():
    # Lay the buttons out to always fit on screen, however many modes there are:
    # the area between the title and the back hint is split into equal slots and
    # each button (plus its little description) sits in one slot.
    n = len(MODE_ITEMS)
    bw = int(min(720, SCREEN_WIDTH * 0.58))
    top = int(SCREEN_HEIGHT * 0.28)
    bottom = int(SCREEN_HEIGHT * 0.88)
    slot = (bottom - top) // max(1, n)
    bh = min(int(SCREEN_HEIGHT * 0.095), int(slot * 0.58))
    x = (SCREEN_WIDTH - bw) // 2
    return [pygame.Rect(x, top + i * slot, bw, bh) for i in range(n)]


def draw_modeselect_screen():
    draw_menu_background()
    screen.blit(menu_title_font.render("CHOOSE MODE", True, MENU_GOLD),
                draw_glow_title("CHOOSE MODE", MENU_GOLD, (SCREEN_WIDTH // 2, int(SCREEN_HEIGHT * 0.16))))

    mx, my = pygame.mouse.get_pos()
    for i, (item, rect) in enumerate(zip(MODE_ITEMS, get_modeselect_rects())):
        selected = i == modeselect_selected or rect.collidepoint(mx, my)
        pygame.draw.rect(screen, MENU_GOLD if selected else MENU_BG2, rect, border_radius=12)
        pygame.draw.rect(screen, MENU_WHITE if selected else MENU_MUTED, rect, 2, border_radius=12)
        tcol = MENU_GOLD_DARK if selected else (228, 228, 238)
        label = menu_option_font.render(item["label"], True, tcol)
        screen.blit(label, label.get_rect(center=rect.center))
        sub = tiny_font.render(clip_text(tiny_font, item["sub"], rect.width), True, MENU_MUTED)
        screen.blit(sub, sub.get_rect(midtop=(rect.centerx, rect.bottom + 6)))

    draw_back_hint()


def start_mode(mode):
    global game_mode, net, net_local_color, _online_dealt, _last_saved_turn
    ai_reset()
    _last_saved_turn = None  # force a fresh auto-save on the first frame

    if mode in ("host", "join"):
        global net_join_text
        _online_dealt = False
        game_mode = "online"
        if mode == "host":
            import netplay
            net = netplay.NetLink()
            net_local_color = WHITE
            net.host()
        else:
            # The joiner enters the host's address (or leaves it blank to
            # auto-find) in the lobby, so the link starts there, not here.
            net = None
            net_local_color = BLACK
            net_join_text = ""
        request_transition("lobby")
        return

    game_mode = mode
    net = None
    net_local_color = None
    if mode == "pvc":
        ensure_engine()
        configure_engine()  # apply the current difficulty to a reused engine
    request_transition("playing", on_switch=start_new_game)


def handle_modeselect_events(events):
    global running, modeselect_selected
    rects = get_modeselect_rects()
    mx, my = pygame.mouse.get_pos()
    for i, r in enumerate(rects):
        if r.collidepoint(mx, my):
            modeselect_selected = i

    for event in events:
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                request_transition("menu")
            elif event.key == pygame.K_UP:
                modeselect_selected = (modeselect_selected - 1) % len(MODE_ITEMS)
            elif event.key == pygame.K_DOWN:
                modeselect_selected = (modeselect_selected + 1) % len(MODE_ITEMS)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                start_mode(MODE_ITEMS[modeselect_selected]["mode"])
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in enumerate(rects):
                if r.collidepoint(event.pos):
                    start_mode(MODE_ITEMS[i]["mode"])


# -----------------------------
# Computer opponent (Stockfish - regular chess only; cards stay human-only)
# -----------------------------
import threading

_BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH") or os.path.join(
    _BASE_DIR, "engine", "stockfish_bin")

_ai = {
    "engine": None,    # chess.engine.SimpleEngine, or None to use the basic fallback
    "tried": False,    # have we attempted to open the engine yet
    "thinking": False,
    "result": None,    # ((fr,fc),(tr,tc)) | "fallback" | None
    "earliest": 0,     # ms: don't start thinking before this (let animations settle)
    "show_until": 0,   # ms: don't apply the move before this (so it isn't instant)
    "gen": 0,          # bumped on reset so a stale background result is ignored
}

# Per-difficulty think time and capped strength (Stockfish UCI_Elo). "Hard" runs
# at full strength.
DIFFICULTY_SETTINGS = {
    "Easy":   {"time": 0.05, "elo": 1320},
    "Medium": {"time": 0.10, "elo": 1700},
    "Hard":   {"time": 0.25, "elo": None},
}


def ai_color():
    # The colour the computer plays in PvC: the opposite of the human's.
    return BLACK if human_color == WHITE else WHITE


def configure_engine():
    eng = _ai["engine"]
    if eng is None:
        return
    cfg = DIFFICULTY_SETTINGS.get(difficulty, DIFFICULTY_SETTINGS["Medium"])
    try:
        if cfg["elo"] is None:
            eng.configure({"UCI_LimitStrength": False})
        else:
            eng.configure({"UCI_LimitStrength": True, "UCI_Elo": cfg["elo"]})
    except Exception as exc:
        print("engine configure failed:", exc)


def ensure_engine():
    if _ai["tried"]:
        return _ai["engine"]
    _ai["tried"] = True
    try:
        import chess.engine
        if os.path.exists(STOCKFISH_PATH):
            _ai["engine"] = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
            print("Stockfish loaded:", STOCKFISH_PATH)
        else:
            print("Stockfish binary not found at", STOCKFISH_PATH, "- using basic AI.")
    except Exception as exc:
        print("Stockfish unavailable, using basic AI:", exc)
        _ai["engine"] = None
    configure_engine()
    return _ai["engine"]


def ai_reset():
    _ai["gen"] += 1
    _ai["thinking"] = False
    _ai["result"] = None
    _ai["earliest"] = 0
    _ai["show_until"] = 0


def _board_to_fen(g):
    # The board already uses uppercase=White / lowercase=Black, which is exactly
    # FEN's convention, so piece letters map straight across. Row 0 is rank 8.
    ranks = []
    for r in range(ROWS):
        run, s = 0, ""
        for c in range(COLS):
            p = g.board[r][c]
            if p is None:
                run += 1
            else:
                if run:
                    s += str(run)
                    run = 0
                s += p
        if run:
            s += str(run)
        ranks.append(s)
    placement = "/".join(ranks)
    active = "w" if g.turn == WHITE else "b"

    rights = ""
    if not g.white_king_moved:
        if not g.white_right_rook_moved:
            rights += "K"
        if not g.white_left_rook_moved:
            rights += "Q"
    if not g.black_king_moved:
        if not g.black_right_rook_moved:
            rights += "k"
        if not g.black_left_rook_moved:
            rights += "q"
    rights = rights or "-"

    ep = "-"
    if g.en_passant_target is not None:
        er, ec = g.en_passant_target
        if 0 <= er < 8 and 0 <= ec < 8:
            ep = "abcdefgh"[ec] + str(8 - er)

    return f"{placement} {active} {rights} {ep} 0 1"


def _uci_to_coords(move):
    import chess
    frm = (7 - chess.square_rank(move.from_square), chess.square_file(move.from_square))
    to = (7 - chess.square_rank(move.to_square), chess.square_file(move.to_square))
    return (frm, to)


def _fallback_move(g):
    # Used when Stockfish is missing or the position isn't legal standard chess
    # (cards can create such positions). Greedy: grab the best capture, else any.
    me = ai_color()
    foe = human_color
    moves = []
    for r in range(ROWS):
        for c in range(COLS):
            p = g.board[r][c]
            if p is not None and g.piece_color(p) == me:
                for (tr, tc) in g.get_legal_moves(r, c):
                    moves.append(((r, c), (tr, tc)))
    if not moves:
        return None
    random.shuffle(moves)

    def capture_value(m):
        tr, tc = m[1]
        tp = g.board[tr][tc]
        return g.get_piece_value(tp) if (tp is not None and g.piece_color(tp) == foe) else 0

    moves.sort(key=capture_value, reverse=True)
    return moves[0]


def _think(fen, gen):
    result = None
    try:
        eng = _ai["engine"]
        if eng is not None:
            import chess
            import chess.engine
            board = chess.Board(fen)
            if board.is_valid():
                think_time = DIFFICULTY_SETTINGS.get(difficulty, DIFFICULTY_SETTINGS["Medium"])["time"]
                res = eng.play(board, chess.engine.Limit(time=think_time))
                if res.move is not None:
                    result = _uci_to_coords(res.move)
    except Exception as exc:
        print("AI think error:", exc)
        result = None
    if gen == _ai["gen"]:  # ignore if a new game/reset happened meanwhile
        _ai["result"] = result if result is not None else "fallback"
        _ai["thinking"] = False


def _apply_ai_move(move):
    if move == "fallback" or move is None:
        move = _fallback_move(game)
    if move is None:
        game.end_turn()  # no legal move - let the game resolve mate/stalemate
        return
    (fr, fc), (tr, tc) = move
    me = ai_color()
    before = game.moves_made_this_turn
    game.select_square(fr, fc)
    game.select_square(tr, tc)
    if game.moves_made_this_turn == before and game.turn == me:
        fb = _fallback_move(game)  # engine move wasn't legal in-game; try our own
        if fb:
            game.select_square(*fb[0])
            game.select_square(*fb[1])
    if game.turn == me and not game.game_over:
        game.end_turn()


def ai_update():
    # Drive the computer's colour with the engine in PvC. Non-blocking: the
    # search runs on a worker thread, applied on the main thread when ready.
    if game_mode != "pvc" or game.game_over or game.turn != ai_color() or game.active_card is not None:
        _ai["earliest"] = 0
        return

    # Wait for the human's move/card animation to finish before replying.
    if any(a["kind"] in ("meteor_sprite", "slide", "teleport", "piece_land", "piece_drop")
           for a in animations):
        return

    now = pygame.time.get_ticks()
    if not _ai["thinking"] and _ai["result"] is None:
        if _ai["earliest"] == 0:
            _ai["earliest"] = now + 300
            return
        if now >= _ai["earliest"]:
            _ai["thinking"] = True
            _ai["show_until"] = now + 250
            threading.Thread(target=_think, args=(_board_to_fen(game), _ai["gen"]),
                             daemon=True).start()
    elif _ai["result"] is not None and now >= _ai["show_until"]:
        move = _ai["result"]
        _ai["result"] = None
        _ai["thinking"] = False
        _ai["earliest"] = 0
        _apply_ai_move(move)


import atexit


@atexit.register
def _close_engine():
    try:
        if _ai["engine"] is not None:
            _ai["engine"].quit()
    except Exception:
        pass


# -----------------------------
# Online play (LAN, host-authoritative full-state sync)
# -----------------------------
import pickle


def net_serialize_state():
    # Only plain data lives in GameState.__dict__ (lists, dicts, sets, ints,
    # strings), so this pickles and replays cleanly on the other machine.
    return pickle.dumps({"type": "state", "dict": game.__dict__})


def net_apply_state(d):
    global dragging_card, dragging_piece
    game.__dict__.update(d)
    animations.clear()          # the peer's animations don't travel; drop stale ones
    dragging_card = None
    dragging_piece = None


def net_reset_sync():
    global _net_prev_turn, _net_prev_over
    _net_prev_turn = game.turn
    _net_prev_over = game.game_over


def net_leave():
    global net, net_local_color, game_mode, net_join_text
    if net is not None:
        net.close()
    net = None
    net_local_color = None
    net_join_text = ""
    game_mode = "pvp"


def net_lobby_update():
    # Runs each frame on the lobby screen: completes the handshake and, once both
    # sides are connected, the host deals + sends the opening position and both
    # transition into the game.
    global _online_dealt
    if net is None or net.error is not None:
        return
    if net.role == "host":
        if net.connected and not _online_dealt:
            start_new_game()
            net_reset_sync()
            net.send(net_serialize_state())
            _online_dealt = True
            request_transition("playing")
    else:  # client waits for the host's opening state
        if net.connected:
            payload = net.poll()
            if payload is not None:
                try:
                    msg = pickle.loads(payload)
                except Exception:
                    msg = None
                if msg and msg.get("type") == "state":
                    net_apply_state(msg["dict"])
                    net_reset_sync()
                    request_transition("playing")


def net_receive():
    # Drain incoming states at the start of a playing frame so input this frame
    # sees the latest position.
    global _net_prev_turn, _net_prev_over
    if game_mode != "online" or net is None:
        return
    payload = net.poll()
    while payload is not None:
        try:
            msg = pickle.loads(payload)
        except Exception:
            msg = None
        if msg and msg.get("type") == "state":
            net_apply_state(msg["dict"])
            _net_prev_turn = game.turn
            _net_prev_over = game.game_over
        payload = net.poll()


def net_push_if_handover():
    # After local input: if I just ended my turn (or the game), send the state.
    global _net_prev_turn, _net_prev_over
    if game_mode != "online" or net is None or not net.connected:
        return
    ended_turn = (_net_prev_turn == net_local_color and game.turn != net_local_color)
    ended_game = (game.game_over and not _net_prev_over)
    if ended_turn or ended_game:
        net.send(net_serialize_state())
    _net_prev_turn = game.turn
    _net_prev_over = game.game_over


def net_start_join():
    global net
    import netplay
    net = netplay.NetLink()
    net.join(host_ip=(net_join_text.strip() or None))


def draw_lobby_screen():
    draw_menu_background()
    screen.blit(menu_title_font.render("LAN GAME", True, MENU_CYAN),
                draw_glow_title("LAN GAME", MENU_CYAN, (SCREEN_WIDTH // 2, int(SCREEN_HEIGHT * 0.18))))

    # A soft panel behind the text so the address / status reads against the
    # busy galaxy background.
    panel_rect = pygame.Rect(0, 0, int(SCREEN_WIDTH * 0.52), int(SCREEN_HEIGHT * 0.46))
    panel_rect.center = (SCREEN_WIDTH // 2, int(SCREEN_HEIGHT * 0.55))
    panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, (*MENU_BG1, 210), panel.get_rect(), border_radius=16)
    screen.blit(panel, panel_rect)
    pygame.draw.rect(screen, MENU_CYAN, panel_rect, 2, border_radius=16)

    cx = SCREEN_WIDTH // 2
    y = int(SCREEN_HEIGHT * 0.38)

    def line(text, color, font=menu_font, dy=46):
        nonlocal y
        surf = font.render(text, True, color)
        screen.blit(surf, surf.get_rect(center=(cx, y)))
        y += dy

    if net_local_color == WHITE:
        # Host.
        line("Hosting as WHITE", MENU_GOLD)
        line(f"Your address:  {net.local_ip}" if net else "Your address: ...",
             MENU_WHITE, small_font, 38)
        if net is not None and net.connected:
            line("Friend connected - starting...", MENU_GREEN)
        else:
            line("Waiting for your friend to join...", MENU_CYAN)
            line("They choose JOIN GAME and type the address above.", MENU_MUTED, small_font)
    else:
        # Joiner.
        line("Joining as BLACK", MENU_PINK)
        if net is None or net.error is not None:
            if net is not None and net.error is not None:
                line(f"Couldn't connect: {net.error}", MENU_RED, small_font, 38)
            line("Type the host's address (shown on their screen):", MENU_WHITE, small_font, 40)
            box = pygame.Rect(0, 0, int(SCREEN_WIDTH * 0.32), 52)
            box.center = (cx, y + 6)
            pygame.draw.rect(screen, MENU_BG2, box, border_radius=8)
            pygame.draw.rect(screen, MENU_CYAN, box, 2, border_radius=8)
            caret = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
            txt = menu_font.render((net_join_text or "") + caret, True, MENU_WHITE)
            screen.blit(txt, txt.get_rect(midleft=(box.left + 12, box.centery)))
            y = box.bottom + 16
            line("ENTER to connect   (blank = auto-find on this Wi-Fi)", MENU_MUTED, small_font)
        elif net.connected:
            line("Connected - waiting for the first move...", MENU_GREEN)
        else:
            target = net_join_text.strip() or "the network"
            line(f"Connecting to {target}...", MENU_CYAN)

    draw_back_hint()


def handle_lobby_events(events):
    global running, net_join_text
    joiner_input = (net_local_color == BLACK and (net is None or net.error is not None))
    for event in events:
        if event.type == pygame.QUIT:
            net_leave()
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                net_leave()
                request_transition("menu")
            elif joiner_input:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    net_start_join()
                elif event.key == pygame.K_BACKSPACE:
                    net_join_text = net_join_text[:-1]
                elif event.unicode and event.unicode in "0123456789." and len(net_join_text) < 21:
                    net_join_text += event.unicode


# -----------------------------
# Saved settings + saved game (on disk)
# -----------------------------
import json

CONFIG_PATH = os.path.join(_BASE_DIR, "config.json")
SAVE_PATH = os.path.join(_BASE_DIR, "savegame.pkl")


def save_config():
    data = {
        "music_muted": music_muted,
        "white_skin_index": white_skin_index,
        "black_skin_index": black_skin_index,
        "board_index": current_board_index,
        "difficulty": difficulty,
        "human_color": human_color,
        # Store the *disabled* cards so cards added in future updates default on.
        "disabled_cards": [c for c in ALL_TRAY_CARDS if c not in enabled_cards],
    }
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        print("save_config failed:", exc)


def load_config():
    global music_muted, white_skin_index, black_skin_index, current_board_index
    global difficulty, human_color
    global BOARD_IMAGE, BOARD_IMAGE_OX, BOARD_IMAGE_OY, LIGHT_SQUARE, DARK_SQUARE
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
    except Exception:
        return  # no config yet, or unreadable - keep defaults

    music_muted = bool(data.get("music_muted", music_muted))
    white_skin_index = int(data.get("white_skin_index", white_skin_index)) % len(PIECE_SKINS)
    black_skin_index = int(data.get("black_skin_index", black_skin_index)) % len(PIECE_SKINS)
    if data.get("difficulty") in DIFFICULTY_SETTINGS:
        difficulty = data["difficulty"]
    if data.get("human_color") in (WHITE, BLACK):
        human_color = data["human_color"]

    disabled = set(data.get("disabled_cards", []))
    enabled_cards.clear()
    enabled_cards.update(c for c in ALL_TRAY_CARDS if c not in disabled)

    bi = int(data.get("board_index", current_board_index))
    if 0 <= bi < len(BOARD_FILES):
        current_board_index = bi
        BOARD_IMAGE, BOARD_IMAGE_OX, BOARD_IMAGE_OY, LIGHT_SQUARE, DARK_SQUARE = (
            load_pixel_board(BOARD_FILES[bi]))

    if music_muted and _audio_ok:
        pygame.mixer.music.set_volume(0.0)


def has_save():
    return os.path.exists(SAVE_PATH)


def save_game():
    # Auto-saved during local play so a game can be resumed from the menu.
    if game_mode not in ("pvp", "pvc") or game.game_over:
        return
    try:
        with open(SAVE_PATH, "wb") as f:
            pickle.dump({"mode": game_mode, "human_color": human_color,
                         "dict": game.__dict__}, f)
    except Exception as exc:
        print("save_game failed:", exc)


def delete_save():
    try:
        if os.path.exists(SAVE_PATH):
            os.remove(SAVE_PATH)
    except Exception:
        pass


def load_game():
    global game_mode, human_color, dragging_card, dragging_piece
    try:
        with open(SAVE_PATH, "rb") as f:
            data = pickle.load(f)
    except Exception as exc:
        print("load_game failed:", exc)
        return False
    game_mode = data.get("mode", "pvp")
    human_color = data.get("human_color", WHITE)
    game.__dict__.update(data["dict"])
    animations.clear()
    dragging_card = None
    dragging_piece = None
    ai_reset()
    if game_mode == "pvc":
        ensure_engine()
        configure_engine()
    return True


# -----------------------------
# Main loop
# -----------------------------
start_music()
music_muted = False
load_config()   # restore saved settings + catalog (overrides the defaults above)
running = True

while running:
    update_transition()
    # Input is ignored mid-fade so a screen can't be acted on while changing.
    blocked = _transition["active"]

    # Menu / catalog / settings run as their own self-contained frames.
    if app_state != "playing":
        events = pygame.event.get()
        if blocked:
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
        elif app_state == "menu":
            handle_menu_events(events)
        elif app_state == "modeselect":
            handle_modeselect_events(events)
        elif app_state == "lobby":
            handle_lobby_events(events)
        elif app_state == "catalog":
            handle_catalog_events(events)
        elif app_state == "settings":
            handle_settings_events(events)

        # The lobby advances the LAN handshake every frame (even mid-fade).
        if app_state == "lobby":
            net_lobby_update()

        if app_state == "menu":
            draw_start_screen()
        elif app_state == "modeselect":
            draw_modeselect_screen()
        elif app_state == "lobby":
            draw_lobby_screen()
        elif app_state == "catalog":
            draw_catalog_screen()
        elif app_state == "settings":
            draw_settings_screen()

        draw_transition_overlay()
        display.fill((0, 0, 0))
        display.blit(screen, (0, 0))
        pygame.display.flip()
        clock.tick(60)
        continue

    # Pull in any state the opponent sent before reading input this frame.
    net_receive()

    # Ignore human board/card input when it isn't this player's turn: the
    # computer's move in PvC, or the opponent's turn online. ESC still works.
    ai_to_move = (game_mode == "pvc" and game.turn == ai_color() and not game.game_over)
    online_not_my_turn = (
        game_mode == "online" and net is not None
        and (not net.connected or game.turn != net_local_color)
    )
    human_locked = ai_to_move or online_not_my_turn

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            continue
        if blocked:
            continue  # ignore input mid-fade (events still pumped)

        # The Rematch button stays clickable even when input is otherwise locked.
        if (event.type == pygame.MOUSEBUTTONDOWN and game.winner_message is not None
                and rematch_available() and get_rematch_button().collidepoint(event.pos)):
            do_rematch()
            continue

        if human_locked:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if game_mode == "online":
                    net_leave()
                elif game_mode in ("pvp", "pvc") and not game.game_over:
                    save_game()
                request_transition("menu")
            continue

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if game_mode == "online":
                    net_leave()
                elif game_mode in ("pvp", "pvc") and not game.game_over:
                    save_game()
                request_transition("menu")

            elif event.key == pygame.K_r and game_mode != "online":
                # Restart is local-only; disabled online (it would desync).
                game = GameState()
                dragging_card = None
                dragging_piece = None
                ai_reset()
                _last_saved_turn = None
                animate_initial_hand()

            elif event.key == pygame.K_m and _audio_ok:
                music_muted = not music_muted
                pygame.mixer.music.set_volume(0.0 if music_muted else 0.5)
                game.status_message = "Music muted." if music_muted else "Music on."

            elif event.key == pygame.K_1:
                white_skin_index = (white_skin_index + 1) % len(PIECE_SKINS)
                game.status_message = f"White pieces: {PIECE_SKINS[white_skin_index]['name']}"

            elif event.key == pygame.K_2:
                black_skin_index = (black_skin_index + 1) % len(PIECE_SKINS)
                game.status_message = f"Black pieces: {PIECE_SKINS[black_skin_index]['name']}"

            elif event.key == pygame.K_b:
                current_board_index = (current_board_index + 1) % len(BOARD_FILES)
                BOARD_IMAGE, BOARD_IMAGE_OX, BOARD_IMAGE_OY, LIGHT_SQUARE, DARK_SQUARE = (
                    load_pixel_board(BOARD_FILES[current_board_index])
                )
                game.status_message = f"Board color #{current_board_index + 1}"

            elif event.key == pygame.K_c:
                game.cheat_mode = not game.cheat_mode
                if game.cheat_mode:
                    game.status_message = "CHEAT MODE ON: unlimited Ether, turn frozen. T passes the turn, C turns it off."
                else:
                    game.status_message = "Cheat mode off."

            elif event.key == pygame.K_t and game.cheat_mode:
                game.turn = game.enemy_color(game.turn)
                game.selected = None
                game.legal_moves_for_selected = []
                game.start_turn_effects()
                game.update_status()

            elif event.key in (pygame.K_SPACE, pygame.K_e):
                game.end_turn()

        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos
            card_rects = get_card_rects()

            # End Turn / Discard buttons. Discarding is done by dragging a card
            # onto the Discard button, so a bare click just explains how.
            buttons = get_action_buttons()
            if buttons["end_turn"].collidepoint(mouse_pos):
                game.end_turn()
                continue
            if buttons["discard"].collidepoint(mouse_pos):
                left = game.MAX_DISCARDS - game.discards_used[game.turn]
                if left > 0:
                    game.status_message = f"Drag a card onto Discard to throw it away ({left} left)."
                else:
                    game.status_message = f"No discards left (limit {game.MAX_DISCARDS})."
                continue

            # Pick up a card. Every card can be dragged: onto one of your pieces
            # or the board to play it, or onto the Discard button to discard it.
            clicked_card = None
            for card_name, rect in card_rects.items():
                if rect.collidepoint(mouse_pos):
                    clicked_card = card_name

            if clicked_card is not None:
                dragging_card = clicked_card

            else:
                square = get_square_from_mouse(mouse_pos)

                if square is not None:
                    row, col = square
                    game.select_square(row, col)

                    # If the click selected this piece (rather than moving),
                    # pick it up so it follows the mouse until release.
                    if game.selected == (row, col):
                        dragging_piece = (row, col)
                        x, y = board_to_screen(row, col)
                        dragging_lift_from = (x + SQUARE_W // 2, y + SQUARE_H - SQUARE_H // 12)
                        dragging_lift_ticks = pygame.time.get_ticks()
                        add_animation("burst", squares=[(row, col)], color=(235, 215, 160), frames=14)

        elif event.type == pygame.MOUSEBUTTONUP:
            if dragging_card is not None:
                buttons = get_action_buttons()

                if game.active_card is not None:
                    game.status_message = "Finish the active card move first."

                elif buttons["discard"].collidepoint(event.pos):
                    # Dropped on the Discard button: throw the card away.
                    game.discard_card(dragging_card)

                elif dragging_card in INSTANT_CARDS:
                    # Instant cards take effect wherever they are released.
                    getattr(game, f"activate_{dragging_card}")()

                elif dragging_card in TARGET_CARDS:
                    square = get_square_from_mouse(event.pos)
                    if square is not None:
                        getattr(game, f"activate_{dragging_card}_on_square")(*square)
                    else:
                        game.status_message = "Drop the card on a valid piece, or on Discard."

                dragging_card = None

            elif dragging_piece is not None:
                square = get_square_from_mouse(event.pos)

                # Dropping on a legal square moves through the same path as
                # clicking it, so active-card rules still apply. Any other
                # drop snaps the piece back and keeps it selected.
                if (
                    square is not None
                    and square != dragging_piece
                    and game.selected == dragging_piece
                    and square in game.legal_moves_for_selected
                ):
                    game.select_square(*square)

                    # Impact squash where the piece settled (it may have been
                    # promoted, or died to a card effect - check the board).
                    landed = game.board[square[0]][square[1]]
                    if landed is not None:
                        add_animation("piece_land", frames=8, extra={"square": square, "piece": landed})

                else:
                    # Snapback: fly from the release point home to the square.
                    origin_piece = game.board[dragging_piece[0]][dragging_piece[1]]
                    if origin_piece is not None:
                        add_animation("piece_drop", frames=9, extra={
                            "square": dragging_piece,
                            "piece": origin_piece,
                            "from_pos": (event.pos[0], event.pos[1] + SQUARE_H // 2),
                        })

                dragging_piece = None

    # Cheat mode: keep both wallets topped up so everything is affordable.
    if game.cheat_mode:
        game.ether[WHITE] = 9999
        game.ether[BLACK] = 9999

    # Let the computer take Black's turn in PvC (no-op otherwise).
    ai_update()

    # Online: push the position when I hand over, and bail out if the link drops.
    net_push_if_handover()
    if game_mode == "online" and net is not None and net.error is not None and not game.game_over:
        game.status_message = "Connection lost. Returning to menu."
        net_leave()
        request_transition("menu")

    # Auto-save local games so CONTINUE can resume them; clear it when one ends.
    if game_mode in ("pvp", "pvc"):
        if game.game_over:
            delete_save()
        elif game.turn != _last_saved_turn:
            save_game()
            _last_saved_turn = game.turn

    draw_background()
    draw_board()
    draw_fire_tiles()
    draw_pieces()
    draw_card_target_hints()
    draw_animations()
    draw_game_over_overlay()
    draw_wait_banner()
    draw_move_log()
    draw_sidebar()
    draw_dragging_card()
    draw_dragging_piece()
    draw_info_panel()

    # Armageddon ambience: the sky darkens and the screen trembles as the
    # meteor falls, then a flash clears the dark and a hard jolt hits on impact.
    meteor = next((a for a in animations if a["kind"] == "meteor_sprite"), None)
    shake_amp = 0
    if meteor is not None:
        p = 1 - meteor["frames"] / meteor["max_frames"]
        if p < 0.4:  # falling: build the gloom and a low tremor
            veil = int(170 * (p / 0.4))
            shake_amp = 1 + int(4 * (p / 0.4))
        elif p < 0.5:  # impact: flash clears the dark, hardest shake
            veil = int(170 * (1 - (p - 0.4) / 0.1))
            shake_amp = int(16 * (1 - (p - 0.4) / 0.1))
        else:
            veil = 0
        if veil > 0:
            gloom = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            gloom.fill((0, 0, 0, veil))
            screen.blit(gloom, (0, 0))

    draw_transition_overlay()

    # Present the frame, offset by the shake (black shows at the bared edges).
    display.fill((0, 0, 0))
    if shake_amp > 0:
        display.blit(screen, (random.randint(-shake_amp, shake_amp), random.randint(-shake_amp, shake_amp)))
    else:
        display.blit(screen, (0, 0))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
