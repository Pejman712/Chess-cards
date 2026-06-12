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

# -----------------------------
# Window / board settings
# -----------------------------
ROWS = 8
COLS = 8

# Fullscreen. Press ESC to quit.
# Set CHESS_WINDOW=1280x800 to run windowed instead (useful for testing).
if os.environ.get("CHESS_WINDOW"):
    win_w, win_h = (int(v) for v in os.environ["CHESS_WINDOW"].lower().split("x"))
    screen = pygame.display.set_mode((win_w, win_h))
else:
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
pygame.display.set_caption("Chess Power-Up Cards")
SCREEN_WIDTH, SCREEN_HEIGHT = screen.get_size()
clock = pygame.time.Clock()

# Layout:
# piece power cards on the left, general/game cards on the right, board
# centered, status bar at the bottom. Cards are shown at the art's native
# resolution, so each panel wraps into as many columns as needed for the
# rows that fit on screen.
INFO_HEIGHT = 110
SIDE_MARGIN = 16
PANEL_PAD = 12
HEADER_H = 40
CARD_GAP = 10
CARD_TOP = HEADER_H + 16
CARD_WIDTH = 183  # native size of the card art; never resized
CARD_HEIGHT = 230
CARD_ASPECT = CARD_HEIGHT / CARD_WIDTH

CARD_ROWS_FIT = max(
    1, (SCREEN_HEIGHT - CARD_TOP - SIDE_MARGIN + CARD_GAP) // (CARD_HEIGHT + CARD_GAP)
)
LEFT_CARD_COLS = -(-6 // CARD_ROWS_FIT)  # 6 piece power cards
RIGHT_CARD_COLS = -(-12 // CARD_ROWS_FIT)  # 12 game cards

LEFT_PANEL_WIDTH = LEFT_CARD_COLS * CARD_WIDTH + PANEL_PAD * (LEFT_CARD_COLS + 1)
RIGHT_PANEL_WIDTH = RIGHT_CARD_COLS * CARD_WIDTH + PANEL_PAD * (RIGHT_CARD_COLS + 1)

BOARD_AREA_WIDTH = SCREEN_WIDTH - LEFT_PANEL_WIDTH - RIGHT_PANEL_WIDTH - SIDE_MARGIN * 2
BOARD_AREA_HEIGHT = SCREEN_HEIGHT - INFO_HEIGHT - SIDE_MARGIN * 2

# The perspective board has 16x12px squares, so on screen a square is 4
# wide to 3 tall. The vertical budget per square width: 8 rows * 0.75,
# plus 1.25 headroom for sprites poking above the top rank, plus ~0.56
# for the board's bottom frame and 3D lip.
SQUARE_W = min(BOARD_AREA_WIDTH // COLS, int(BOARD_AREA_HEIGHT / 7.81))
SQUARE_W -= SQUARE_W % 4
SQUARE_H = SQUARE_W * 3 // 4
SQUARE_SIZE = SQUARE_W  # piece sprites and effect sizes scale off the square width

BOARD_W = SQUARE_W * COLS
BOARD_H = SQUARE_H * ROWS
PIECE_HEADROOM = SQUARE_W * 2 - SQUARE_H

BOARD_X = LEFT_PANEL_WIDTH + SIDE_MARGIN + max(0, (BOARD_AREA_WIDTH - BOARD_W) // 2)
BOARD_Y = SIDE_MARGIN + PIECE_HEADROOM + max(
    0, (BOARD_AREA_HEIGHT - PIECE_HEADROOM - BOARD_H) // 2
)

LEFT_PANEL_X = 0
RIGHT_PANEL_X = SCREEN_WIDTH - RIGHT_PANEL_WIDTH
INFO_Y = SCREEN_HEIGHT - INFO_HEIGHT

WIDTH = SCREEN_WIDTH
HEIGHT = SCREEN_HEIGHT

# -----------------------------
# Colors
# -----------------------------
# Sampled from the pixel-art board asset so highlights stay in tune with it.
LIGHT_SQUARE = (226, 213, 161)
DARK_SQUARE = (120, 79, 72)
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


title_font = load_font(32, 24, bold=True)
small_font = load_font(16, 17)
tiny_font = load_font(16, 14)
badge_font = load_font(16, 13, bold=True)

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
BOARD_IMAGE_FILE = "board_persp_05.png"

# Source geometry of the perspective board image: 16x12px squares, with the
# playing area's top-left square starting at pixel (7, 20). The frame around
# it carries baked-in coordinate labels (left and bottom) and a 3D lip below.
BOARD_TILE_W_PX = 16
BOARD_TILE_H_PX = 12
BOARD_GRID_X_PX = 7
BOARD_GRID_Y_PX = 20


def load_pixel_board():
    image = pygame.image.load(os.path.join(ASSET_DIR, BOARD_IMAGE_FILE)).convert_alpha()

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
    return scaled, round(BOARD_GRID_X_PX * scale), round(BOARD_GRID_Y_PX * scale)


BOARD_IMAGE, BOARD_IMAGE_OX, BOARD_IMAGE_OY = load_pixel_board()

# Animated background: a looping GIF decoded once at startup. Frames are
# stored at half screen resolution to keep memory reasonable and upscaled
# when drawn; a dark tint baked into each frame keeps the play area readable.
BACKGROUND_GIF = os.path.join(ASSET_DIR, "background.gif")
BACKGROUND_DIM = 120  # 0 = full brightness, 255 = black


def load_background_frames():
    try:
        from PIL import Image, ImageSequence
    except ImportError:
        return [], 40

    try:
        gif = Image.open(BACKGROUND_GIF)
    except OSError:
        return [], 40

    frame_ms = max(20, gif.info.get("duration", 40))
    half_size = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    tint = pygame.Surface(half_size)
    tint.set_alpha(BACKGROUND_DIM)

    frames = []
    for frame in ImageSequence.Iterator(gif):
        rgb = frame.convert("RGB")
        surface = pygame.image.frombuffer(rgb.tobytes(), rgb.size, "RGB").convert()
        surface = pygame.transform.scale(surface, half_size)
        surface.blit(tint, (0, 0))
        frames.append(surface)

    return frames, frame_ms


BACKGROUND_FRAMES, BACKGROUND_FRAME_MS = load_background_frames()

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
PIECE_SPRITE_FILES = {
    "P": "W_Pawn.png", "R": "W_Rook.png", "N": "W_Knight.png",
    "B": "W_Bishop.png", "Q": "W_Queen.png", "K": "W_King.png",
    "p": "B_Pawn.png", "r": "B_Rook.png", "n": "B_Knight.png",
    "b": "B_Bishop.png", "q": "B_Queen.png", "k": "B_King.png",
}

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
]

def load_card_image(path):
    try:
        return pygame.image.load(path).convert_alpha()
    except pygame.error:
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
# Clicking a USED card in the bottom row buys/refills that ability.
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
    "inzone": ("InZone", (150, 40, 35), "Chain captures with one piece; it dies after."),
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


# The upscaled frame is cached: the GIF runs at ~25fps while the game loop
# runs faster, so most ticks reuse the previous scale.
_background_cache = {"index": None, "surface": None}


def draw_background():
    if not BACKGROUND_FRAMES:
        screen.fill((0, 0, 0))
        return

    index = (pygame.time.get_ticks() // BACKGROUND_FRAME_MS) % len(BACKGROUND_FRAMES)

    if _background_cache["index"] != index:
        _background_cache["index"] = index
        _background_cache["surface"] = pygame.transform.scale(
            BACKGROUND_FRAMES[index], (SCREEN_WIDTH, SCREEN_HEIGHT)
        )

    screen.blit(_background_cache["surface"], (0, 0))


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
                t = progress / fall_part
                fall_frames = METEOR_FRAMES[:METEOR_FALL_COUNT]
                frame = fall_frames[min(len(fall_frames) - 1, int(t * len(fall_frames)))]
                start_y = impact[1] - BOARD_H
                pos_y = round(start_y + (impact[1] - start_y) * t * t)
                screen.blit(frame, frame.get_rect(midbottom=(impact[0], pos_y)))
            else:
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

        # Card system
        self.active_card = None
        self.active_card_owner = None
        self.used_cards = {
            WHITE: set(),
            BLACK: set(),
        }

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

    def clone(self):
        return copy.deepcopy(self)

    def piece_color(self, piece):
        if piece is None:
            return None
        return WHITE if piece.isupper() else BLACK

    def enemy_color(self, color):
        return BLACK if color == WHITE else WHITE

    def pass_turn(self):
        # In cheat mode the turn is frozen so one player can act repeatedly.
        if self.cheat_mode:
            return
        self.turn = self.enemy_color(self.turn)

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

    def refill_card(self, card_name):
        if card_name not in self.used_cards[self.turn]:
            self.status_message = f"{card_name.capitalize()} is not used yet."
            return

        cost = CARD_COSTS.get(card_name, 0)

        if self.ether[self.turn] < cost:
            self.status_message = (
                f"Not enough Ether to refill {card_name.capitalize()}. "
                f"Need {cost}, have {self.ether[self.turn]}."
            )
            return

        self.ether[self.turn] -= cost
        self.used_cards[self.turn].remove(card_name)
        self.status_message = (
            f"{self.turn.capitalize()} refilled {card_name.capitalize()} "
            f"for {cost} Ether."
        )

    def can_pay_for_card(self, card_name):
        return self.ether[self.turn] >= CARD_COSTS.get(card_name, 0)

    def pay_for_game_card(self, card_name):
        cost = CARD_COSTS.get(card_name, 0)

        if self.ether[self.turn] < cost:
            self.status_message = (
                f"Not enough Ether for {card_name.capitalize()}. "
                f"Need {cost}, have {self.ether[self.turn]}."
            )
            return False

        self.save_history()
        self.ether[self.turn] -= cost
        return True

    def consume_turn_after_game_card(self, message):
        add_animation("banner", text=message.replace("{player}", self.turn.capitalize()), color=GOLD, frames=42)
        self.active_card = None
        self.active_card_owner = None
        self.selected = None
        self.legal_moves_for_selected = []
        self.windknight_square = None
        self.windknight_moves_remaining = 0
        self.decay_fire_tiles()

        played_by = self.turn
        self.award_check_bonus_for_player(played_by)
        self.pass_turn()
        self.status_message = message.replace("{player}", played_by.capitalize())
        self.start_turn_effects()
        self.update_status()

        # Preserve the game-card message unless the new player is in check/checkmate.
        if not self.is_in_check(self.turn) and not self.game_over:
            self.status_message = message.replace("{player}", played_by.capitalize())

    def start_turn_effects(self):
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
            "used_cards": copy.deepcopy(self.used_cards),
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

    def restore_snapshot(self, snapshot):
        self.board = copy.deepcopy(snapshot["board"])
        self.fire_tiles = copy.deepcopy(snapshot["fire_tiles"])
        self.rookdemon_rooks = copy.deepcopy(snapshot["rookdemon_rooks"])
        self.dramatic_pieces = copy.deepcopy(snapshot["dramatic_pieces"])
        self.plague_active = copy.deepcopy(snapshot["plague_active"])
        self.absolute_protection_active = copy.deepcopy(snapshot["absolute_protection_active"])
        self.extra_blood_active = copy.deepcopy(snapshot["extra_blood_active"])
        self.used_cards = copy.deepcopy(snapshot["used_cards"])
        self.ether = copy.deepcopy(snapshot["ether"])
        self.turn = snapshot["turn"]
        self.white_king_moved = snapshot["white_king_moved"]
        self.black_king_moved = snapshot["black_king_moved"]
        self.white_left_rook_moved = snapshot["white_left_rook_moved"]
        self.white_right_rook_moved = snapshot["white_right_rook_moved"]
        self.black_left_rook_moved = snapshot["black_left_rook_moved"]
        self.black_right_rook_moved = snapshot["black_right_rook_moved"]
        self.en_passant_target = snapshot["en_passant_target"]

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

        if "pawntastic" in self.used_cards[self.turn]:
            self.status_message = f"{self.turn.capitalize()} has already used Pawntastic."
            return

        piece = self.board[row][col]

        if piece is None:
            self.status_message = "Drop Pawntastic on one of your pawns."
            return

        if self.piece_color(piece) != self.turn:
            self.status_message = "You can only use Pawntastic on your own pawn."
            return

        if piece.lower() != "p":
            self.status_message = "Pawntastic only works on pawns."
            return

        self.active_card = "pawntastic"
        self.active_card_owner = self.turn
        self.selected = (row, col)
        self.legal_moves_for_selected = self.get_legal_moves(row, col)

        if not self.legal_moves_for_selected:
            self.active_card = None
            self.active_card_owner = None
            self.selected = None
            self.status_message = "That pawn has no Pawntastic moves."
            return

        add_animation("magic", squares=[(row, col)], text="PAWN", color=(120, 255, 130), frames=26)
        self.status_message = f"{self.turn.capitalize()} used Pawntastic. Choose the pawn's move."

    def activate_bishock_on_square(self, row, col):
        if self.game_over:
            return

        if "bishock" in self.used_cards[self.turn]:
            self.status_message = f"{self.turn.capitalize()} has already used Bishock."
            return

        piece = self.board[row][col]

        if piece is None:
            self.status_message = "Drop Bishock on one of your bishops."
            return

        if self.piece_color(piece) != self.turn:
            self.status_message = "You can only use Bishock on your own bishop."
            return

        if piece.lower() != "b":
            self.status_message = "Bishock only works on bishops."
            return

        destroyed_squares = get_bishock_destroyed_squares(self, row, col)

        if not destroyed_squares:
            self.status_message = "Bishock found nothing to destroy."
            return

        self.save_history()

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

        self.used_cards[self.turn].add("bishock")

        self.active_card = None
        self.active_card_owner = None
        self.selected = None
        self.legal_moves_for_selected = []

        self.decay_fire_tiles()
        self.pass_turn()
        self.start_turn_effects()
        self.update_status()

    def activate_rookdemon_on_square(self, row, col):
        if self.game_over:
            return

        if "rookdemon" in self.used_cards[self.turn]:
            self.status_message = f"{self.turn.capitalize()} has already used Rookdemon."
            return

        piece = self.board[row][col]

        if piece is None:
            self.status_message = "Drop Rookdemon on one of your rooks."
            return

        if self.piece_color(piece) != self.turn:
            self.status_message = "You can only use Rookdemon on your own rook."
            return

        if piece.lower() != "r":
            self.status_message = "Rookdemon only works on rooks."
            return

        self.save_history()
        self.rookdemon_rooks[(row, col)] = 2
        self.used_cards[self.turn].add("rookdemon")
        add_animation("magic", squares=[(row, col)], text="FIRE", color=(255, 90, 35), frames=36)

        self.selected = None
        self.legal_moves_for_selected = []
        self.active_card = None
        self.active_card_owner = None

        self.status_message = f"{self.turn.capitalize()} empowered a rook with Rookdemon."
        self.award_check_bonus_for_player(self.turn)
        self.decay_fire_tiles()
        self.pass_turn()
        self.start_turn_effects()
        self.update_status()

    def activate_windknight_on_square(self, row, col):
        if self.game_over:
            return

        if "windknight" in self.used_cards[self.turn]:
            self.status_message = f"{self.turn.capitalize()} has already used Windknight."
            return

        if not is_valid_windknight_target(self, row, col):
            self.status_message = "Drop Windknight on one of your knights."
            return

        self.active_card = "windknight"
        self.active_card_owner = self.turn
        self.windknight_square = (row, col)
        self.windknight_moves_remaining = 2
        self.used_cards[self.turn].add("windknight")

        self.selected = (row, col)
        self.legal_moves_for_selected = self.get_legal_moves(row, col)

        if not self.legal_moves_for_selected:
            self.active_card = None
            self.active_card_owner = None
            self.windknight_square = None
            self.windknight_moves_remaining = 0
            self.used_cards[self.turn].discard("windknight")
            self.selected = None
            self.status_message = "That knight has no legal Windknight move."
            return

        add_animation("magic", squares=[(row, col)], text="WIND", color=(90, 220, 255), frames=32)
        self.status_message = f"{self.turn.capitalize()} used Windknight. Move the knight twice."


    def activate_queentum_on_square(self, row, col):
        if self.game_over:
            return

        if "queentum" in self.used_cards[self.turn]:
            self.status_message = f"{self.turn.capitalize()} has already used Queentum."
            return

        piece = self.board[row][col]

        if piece is None:
            self.status_message = "Drop Queentum on one of your queens."
            return

        if self.piece_color(piece) != self.turn:
            self.status_message = "You can only use Queentum on your own queen."
            return

        if piece.lower() != "q":
            self.status_message = "Queentum only works on queens."
            return

        self.active_card = "queentum"
        self.active_card_owner = self.turn
        self.selected = (row, col)
        self.legal_moves_for_selected = self.get_legal_moves(row, col)

        if not self.legal_moves_for_selected:
            self.active_card = None
            self.active_card_owner = None
            self.selected = None
            self.status_message = "That queen has no legal Queentum teleport."
            return

        add_animation("magic", squares=[(row, col)], text="QUANTUM", color=(200, 120, 255), frames=32)
        self.status_message = f"{self.turn.capitalize()} used Queentum. Choose any legal teleport square."


    def can_use_longlivetheking(self, color=None):
        if color is None:
            color = self.turn

        if "longlivetheking" in self.used_cards[color]:
            return False

        if not get_empty_escape_corners(self):
            return False

        king_pos = self.find_king(color)
        return king_pos is not None

    def activate_longlivetheking_on_square(self, row, col):
        if self.game_over:
            # Allow this card as a last escape if update_status reached a
            # checkmate-like state but the card is still available.
            if not self.can_use_longlivetheking(self.turn):
                return
            self.game_over = False

        if "longlivetheking" in self.used_cards[self.turn]:
            self.status_message = f"{self.turn.capitalize()} has already used LongLiveTheKing."
            return

        piece = self.board[row][col]

        if piece is None:
            self.status_message = "Drop LongLiveTheKing on your king."
            return

        if self.piece_color(piece) != self.turn:
            self.status_message = "You can only use LongLiveTheKing on your own king."
            return

        if piece.lower() != "k":
            self.status_message = "LongLiveTheKing only works on kings."
            return

        escape_corner = choose_random_escape_corner(self)

        if escape_corner is None:
            self.status_message = "LongLiveTheKing failed: no empty corner exists."
            return

        from_row, from_col = row, col
        to_row, to_col = escape_corner
        king_piece = self.board[from_row][from_col]

        self.save_history()
        add_animation("move_line", squares=[(from_row, from_col), (to_row, to_col)], color=(255, 235, 140), frames=40)

        # Move king to the random empty corner.
        self.board[to_row][to_col] = king_piece
        self.board[from_row][from_col] = None

        # Moving the king disables castling.
        if self.turn == WHITE:
            self.white_king_moved = True
            pawn_piece = "P"
            queen_piece = "Q"
            promotion_row = 0
        else:
            self.black_king_moved = True
            pawn_piece = "p"
            queen_piece = "q"
            promotion_row = 7

        # Spawn pawns around the destination on every empty neighboring square.
        spawned = 0
        for pawn_row, pawn_col in get_surrounding_empty_squares(self, to_row, to_col):
            if pawn_row == promotion_row:
                self.board[pawn_row][pawn_col] = queen_piece
            else:
                self.board[pawn_row][pawn_col] = pawn_piece
            spawned += 1

        self.used_cards[self.turn].add("longlivetheking")

        self.active_card = None
        self.active_card_owner = None
        self.selected = None
        self.legal_moves_for_selected = []
        self.windknight_square = None
        self.windknight_moves_remaining = 0

        # The escape consumes the turn.
        self.award_check_bonus_for_player(self.turn)
        self.decay_fire_tiles()
        escaped_player = self.turn
        self.pass_turn()
        self.status_message = (
            f"{escaped_player.capitalize()} escaped to a random corner "
            f"and spawned {spawned} pawn(s)."
        )
        self.start_turn_effects()
        self.update_status()


    # -----------------------------
    # Game card activation
    # -----------------------------
    def activate_switchero(self):
        if self.game_over:
            return

        if not self.pay_for_game_card("switchero"):
            return

        swapped = {
            "P": "p", "R": "r", "N": "n", "B": "b", "Q": "q", "K": "k",
            "p": "P", "r": "R", "n": "N", "b": "B", "q": "Q", "k": "K",
        }

        affected = []

        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]
                if piece is not None:
                    self.board[row][col] = swapped[piece]
                    affected.append((row, col))

        add_animation("magic", squares=affected, text="SWAP", color=(90, 170, 255), frames=45)

        (
            self.white_king_moved,
            self.black_king_moved,
        ) = (
            self.black_king_moved,
            self.white_king_moved,
        )

        (
            self.white_left_rook_moved,
            self.black_left_rook_moved,
        ) = (
            self.black_left_rook_moved,
            self.white_left_rook_moved,
        )

        (
            self.white_right_rook_moved,
            self.black_right_rook_moved,
        ) = (
            self.black_right_rook_moved,
            self.white_right_rook_moved,
        )

        self.consume_turn_after_game_card("{player} played Switchero. All piece ownership switched.")

    def activate_prophecy(self):
        if self.game_over:
            return

        if not self.pay_for_game_card("prophecy"):
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

        self.consume_turn_after_game_card(
            f"{{player}} played The Prophecy. {changed} own pawn(s) became queen(s)."
        )

    def activate_armageddon_on_square(self, row, col):
        if self.game_over:
            return

        if not self.pay_for_game_card("armageddon"):
            return

        destroyed_value = 0
        destroyed_count = 0
        fire_squares = []

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
                    self.board[nr][nc] = None
                    self.rookdemon_rooks.pop((nr, nc), None)
                    self.dramatic_pieces.discard((nr, nc))

                    if self.windknight_square == (nr, nc):
                        self.windknight_square = None
                        self.windknight_moves_remaining = 0

                fire_squares.append((nr, nc))

        self.add_ether(self.turn, destroyed_value)
        self.add_fire_tiles(fire_squares)

        if METEOR_FRAMES:
            add_animation("meteor_sprite", frames=96, extra={"square": (row, col)})
        else:
            add_animation("blast", squares=fire_squares, text="METEOR", color=(255, 95, 35), frames=38)

        self.consume_turn_after_game_card(
            f"{{player}} played Armageddon. Destroyed {destroyed_count} piece(s) and created fire."
        )

    def activate_thedramatic_on_square(self, row, col):
        if self.game_over:
            return

        if not self.pay_for_game_card("thedramatic"):
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

        self.consume_turn_after_game_card(
            "{player} played TheDramatic. The marked piece will avenge itself if captured."
        )


    def activate_capitalism(self):
        if self.game_over:
            return

        if not self.pay_for_game_card("capitalism"):
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

        if not self.pay_for_game_card("plague"):
            return

        self.plague_active.add(self.turn)

        self.consume_turn_after_game_card(
            "{player} unleashed Plague. At the start of their turns, one enemy piece dies."
        )

    def activate_solo(self):
        if self.game_over:
            return

        if not self.player_has_only_king(self.turn):
            self.status_message = "Solo only works if you have only your king left."
            return

        if not self.pay_for_game_card("solo"):
            return

        king = self.find_king(self.turn)
        if king is not None:
            add_animation("magic", squares=[king], text="SOLO", color=(255, 230, 120), frames=55)

        self.current_player_wins("Solo")

    def activate_absoluteprotection(self):
        if self.game_over:
            return

        if not self.pay_for_game_card("absoluteprotection"):
            return

        self.absolute_protection_active.add(self.turn)
        protected_squares = []
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p is not None and self.piece_color(p) == self.turn:
                    protected_squares.append((r, c))
        add_animation("shield", squares=protected_squares, text="SHIELD", color=(90, 210, 255), frames=40)

        self.consume_turn_after_game_card(
            "{player} activated AbsoluteProtection for one opponent turn."
        )


    def activate_timetraveler(self):
        if self.game_over:
            return

        if len(self.history) < 3:
            self.status_message = "TimeTraveler needs at least 3 previous turns."
            return

        if not self.pay_for_game_card("timetraveler"):
            return

        # pay_for_game_card saved the current state, so go back to the
        # third state before this payment snapshot.
        if len(self.history) < 4:
            self.ether[self.turn] += CARD_COSTS["timetraveler"]
            self.status_message = "TimeTraveler needs more history."
            return

        snapshot = copy.deepcopy(self.history[-4])
        self.restore_snapshot(snapshot)
        self.history = self.history[:-4]
        add_animation("magic", squares=[(r, c) for r in range(8) for c in range(8)], text="TIME", color=(120, 190, 255), frames=55)
        self.status_message = "TimeTraveler restored the board from 3 turns ago."
        self.decay_fire_tiles()
        self.pass_turn()
        self.start_turn_effects()
        self.update_status()

    def activate_extrablood(self):
        if self.game_over:
            return

        if self.turn in self.extra_blood_active:
            self.status_message = "ExtraBlood is already active for you."
            return

        if not self.pay_for_game_card("extrablood"):
            return

        self.extra_blood_active.add(self.turn)
        add_animation("banner", text=f"{self.turn.capitalize()} activated ExtraBlood", color=(220, 30, 30), frames=50)
        self.consume_turn_after_game_card("{player} activated ExtraBlood. Capture Ether is now doubled.")

    def activate_chrisma(self):
        if self.game_over:
            return

        king_pos = self.find_king(self.turn)

        if king_pos is None:
            self.status_message = "Chrisma failed: no king found."
            return

        if not self.pay_for_game_card("chrisma"):
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
        self.consume_turn_after_game_card(
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

        capture_moves = self.get_capture_moves_only(row, col)

        if not capture_moves:
            self.status_message = "That piece has no captures for InZone."
            return

        if not self.pay_for_game_card("inzone"):
            return

        self.active_card = "inzone"
        self.active_card_owner = self.turn
        self.inzone_square = (row, col)
        self.inzone_captures = 0
        self.selected = (row, col)
        self.legal_moves_for_selected = capture_moves
        add_animation("magic", squares=[(row, col)], text="ZONE", color=(255, 70, 70), frames=42)
        self.status_message = "InZone active: capture repeatedly with this piece. It dies when the streak ends."

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
    def make_move(self, from_square, to_square, test_mode=False):
        from_row, from_col = from_square
        to_row, to_col = to_square

        original_from_square = (from_row, from_col)
        original_to_square = (to_row, to_col)

        piece = self.board[from_row][from_col]
        captured_piece = self.board[to_row][to_col]

        if piece is None:
            return

        if not test_mode:
            self.save_history()

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
            if self.active_card == "pawntastic":
                self.used_cards[color].add("pawntastic")

            if self.active_card == "queentum":
                self.used_cards[color].add("queentum")

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

                    if self.legal_moves_for_selected:
                        self.status_message = "InZone: keep capturing with the same piece."
                        return

                # Streak ends: the InZone piece dies.
                if moved_piece_survived:
                    self.board[to_row][to_col] = None
                    self.rookdemon_rooks.pop((to_row, to_col), None)
                    self.dramatic_pieces.discard((to_row, to_col))
                    add_animation("burst", squares=[(to_row, to_col)], text="BURNOUT", color=(255, 60, 60), frames=38)

                self.active_card = None
                self.active_card_owner = None
                self.inzone_square = None
                self.inzone_captures = 0
                self.award_check_bonus_for_player(color)
                self.decay_fire_tiles()
                self.pass_turn()
                self.selected = None
                self.legal_moves_for_selected = []
                self.start_turn_effects()
                self.update_status()
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

                self.active_card = None
                self.active_card_owner = None
                self.windknight_square = None
                self.windknight_moves_remaining = 0
                self.decay_fire_tiles()
                self.pass_turn()
                self.selected = None
                self.legal_moves_for_selected = []
                self.start_turn_effects()
                self.update_status()
                return

            self.award_check_bonus_for_player(color)
            self.decay_fire_tiles()
            self.active_card = None
            self.active_card_owner = None
            self.pass_turn()
            self.selected = None
            self.legal_moves_for_selected = []
            self.start_turn_effects()
            self.update_status()

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

        if self.selected is not None:
            if (row, col) in self.legal_moves_for_selected:
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


def is_board_flipped():
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
    rects = {}

    # Cards fill each panel column by column at their native size.
    for index, card_name in enumerate(PIECE_POWER_CARDS):
        grid_col = index // CARD_ROWS_FIT
        grid_row = index % CARD_ROWS_FIT
        x = LEFT_PANEL_X + PANEL_PAD + grid_col * (CARD_WIDTH + PANEL_PAD)
        y = CARD_TOP + grid_row * (CARD_HEIGHT + CARD_GAP)
        rects[card_name] = pygame.Rect(x, y, CARD_WIDTH, CARD_HEIGHT)

    for index, card_name in enumerate(GENERAL_CARDS):
        grid_col = index // CARD_ROWS_FIT
        grid_row = index % CARD_ROWS_FIT
        x = RIGHT_PANEL_X + PANEL_PAD + grid_col * (CARD_WIDTH + PANEL_PAD)
        y = CARD_TOP + grid_row * (CARD_HEIGHT + CARD_GAP)
        rects[card_name] = pygame.Rect(x, y, CARD_WIDTH, CARD_HEIGHT)

    return rects


# -----------------------------
# Drawing
# -----------------------------
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
        center = (x + SQUARE_W // 2, y + SQUARE_H // 2)

        if game.board[row][col] is None:
            pygame.draw.circle(screen, LEGAL_MOVE_COLOR, center, max(7, SQUARE_SIZE // 7))
            pygame.draw.circle(screen, (20, 90, 30), center, max(8, SQUARE_SIZE // 7), 2)
        else:
            pygame.draw.circle(screen, CAPTURE_COLOR, center, max(11, SQUARE_SIZE // 5), 4)


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


def get_piece_surface(piece, lifted=False):
    key = (piece, lifted)

    if key not in _piece_cache:
        sprite = pygame.image.load(os.path.join(ASSET_DIR, PIECE_SPRITE_FILES[piece])).convert_alpha()
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


def draw_single_card(rect, owner, card_name):
    used = card_name in game.used_cards[owner] if card_name in ABILITY_CARDS else False
    display_name, _, _ = CARD_INFO.get(card_name, (card_name, (70, 70, 70), ""))
    affordable = game.ether[game.turn] >= CARD_COSTS.get(card_name, 0)

    rect = rect.move(0, get_card_bob(card_name))
    screen.blit(get_card_face(owner, card_name, rect.size, used, affordable), rect)

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
    used = card_name in game.used_cards[owner] if card_name in ABILITY_CARDS else False

    # The preview shows the card at native size (never resized); it exists
    # for the description box underneath.
    preview_h = CARD_HEIGHT
    preview_w = CARD_WIDTH
    info_h = 92
    pad = 10
    total_h = preview_h + info_h + pad * 3

    # Show the preview next to the panel the card lives in, over the table.
    if card_rect.centerx < SCREEN_WIDTH // 2:
        panel_x = LEFT_PANEL_WIDTH + 16
    else:
        panel_x = RIGHT_PANEL_X - preview_w - pad * 2 - 16

    panel_y = min(
        max(SIDE_MARGIN, card_rect.centery - total_h // 2),
        SCREEN_HEIGHT - INFO_HEIGHT - total_h - 8,
    )

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


def draw_sidebar():
    # The cards sit directly on the animated background - no panel fill.
    # Header plaques.
    left_header = pygame.Rect(8, 10, LEFT_PANEL_WIDTH - 16, HEADER_H - 12)
    right_header = pygame.Rect(RIGHT_PANEL_X + 8, 10, RIGHT_PANEL_WIDTH - 16, HEADER_H - 12)

    for plaque, title in [
        (left_header, "PIECE POWERS"),
        (right_header, "POWER CARDS"),
    ]:
        pygame.draw.rect(screen, WOOD_FRAME_DARK, plaque, border_radius=8)
        pygame.draw.rect(screen, WOOD_FRAME, plaque, 2, border_radius=8)
        title_x = plaque.centerx - badge_font.size(title)[0] // 2
        title_y = plaque.centery - badge_font.get_height() // 2
        draw_wavy_text(badge_font, title, PARCHMENT, (title_x, title_y), amp=2)

    card_rects = get_card_rects()
    mouse_pos = pygame.mouse.get_pos()
    hovered = None

    for card_name, rect in card_rects.items():
        if dragging_card == card_name:
            continue

        draw_single_card(rect, game.turn, card_name)

        if rect.collidepoint(mouse_pos):
            hovered = card_name

    # Highlight the hovered card and show a large readable preview beside
    # the panel.
    if hovered is not None and dragging_card is None:
        outline = card_rects[hovered].move(0, get_card_bob(hovered)).inflate(6, 6)
        pygame.draw.rect(screen, (255, 220, 110), outline, 3, border_radius=10)
        draw_card_preview(game.turn, hovered, card_rects[hovered])


def draw_dragging_card():
    if dragging_card is None:
        return

    mouse_x, mouse_y = pygame.mouse.get_pos()

    rect = pygame.Rect(0, 0, CARD_WIDTH, CARD_HEIGHT)
    rect.center = (mouse_x, mouse_y)

    draw_single_card(rect, game.turn, dragging_card)


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
    chip = pygame.Rect(topleft[0], topleft[1], 168, 26)
    pygame.draw.rect(screen, WOOD_FRAME_DARK, chip, border_radius=13)
    pygame.draw.rect(screen, GOLD if is_active else (80, 70, 55), chip, 2, border_radius=13)

    pygame.draw.circle(screen, color, (chip.x + 14, chip.centery), 7)
    pygame.draw.circle(screen, (90, 80, 60), (chip.x + 14, chip.centery), 7, 1)

    text = f"{label}  {amount} Ether"
    text_color = TEXT_COLOR if is_active else MUTED_TEXT
    draw_shadow_text(tiny_font, text, text_color, (chip.x + 27, chip.centery - tiny_font.get_height() // 2), offset=1)


def draw_info_panel():
    if game.active_card == "pawntastic":
        card_text = "Pawntastic active: click a highlighted destination."
    elif game.active_card == "windknight":
        card_text = "Windknight active: move the selected knight twice."
    elif game.active_card == "queentum":
        card_text = "Queentum active: click any legal teleport destination."
    elif game.active_card == "inzone":
        card_text = "InZone active: keep capturing with the selected piece."
    else:
        card_text = "Drag a card onto the board to use it. Click instant cards. Click a USED card to refill it."

    bar = pygame.Rect(LEFT_PANEL_WIDTH, INFO_Y, SCREEN_WIDTH - LEFT_PANEL_WIDTH - RIGHT_PANEL_WIDTH, INFO_HEIGHT)
    pygame.draw.rect(screen, PANEL_BG, bar)
    pygame.draw.line(screen, PANEL_EDGE, (bar.x, bar.y), (bar.right, bar.y), 3)

    chips_w = 190
    text_w = bar.width - chips_w - 28

    if game.winner_message is not None:
        headline = f"GAME OVER - {game.winner_message}"
    else:
        headline = f"{game.turn.capitalize()} to move"

    x = bar.x + 16
    draw_wavy_text(title_font, clip_text(title_font, headline, text_w), GOLD, (x, bar.y + 8), amp=2, offset=3)

    if game.cheat_mode:
        draw_badge("CHEAT MODE   C: off   T: pass turn", GOLD, (bar.x + 16, bar.y - 26))

    active_flags = []
    if game.plague_active:
        active_flags.append("Plague")
    if game.absolute_protection_active:
        active_flags.append("AbsoluteProtection")
    if game.extra_blood_active:
        active_flags.append("ExtraBlood")

    if active_flags:
        third_line = ("Active effects: " + ", ".join(active_flags), GOLD)
    else:
        third_line = (
            "+1 Ether per square moved  -  captures pay piece value  -  check pays +5  -  R restarts",
            MUTED_TEXT,
        )

    lines = [
        (card_text, MUTED_TEXT),
        third_line,
    ]

    # Don't repeat the headline ("White to move") as the status line.
    if game.status_message and game.status_message != headline:
        lines.insert(0, (game.status_message, TEXT_COLOR))

    y = bar.y + 40
    for text, color in lines:
        draw_shadow_text(tiny_font, clip_text(tiny_font, text, text_w), color, (x, y))
        y += 21

    # Ether totals on the right; the side to move is highlighted.
    chips_x = bar.right - chips_w
    draw_ether_chip("White", game.ether[WHITE], (240, 240, 235), game.turn == WHITE, (chips_x, bar.y + 18))
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


# -----------------------------
# Main loop
# -----------------------------
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

            elif event.key == pygame.K_r:
                game = GameState()
                dragging_card = None
                dragging_piece = None

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

        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos
            card_rects = get_card_rects()

            clicked_card = None

            for card_name, rect in card_rects.items():
                if rect.collidepoint(mouse_pos):
                    clicked_card = card_name

            if clicked_card is not None:
                if clicked_card in ABILITY_CARDS and clicked_card in game.used_cards[game.turn]:
                    game.refill_card(clicked_card)

                elif game.active_card is not None:
                    game.status_message = "Finish the active card move first."

                elif clicked_card == "switchero":
                    game.activate_switchero()

                elif clicked_card == "prophecy":
                    game.activate_prophecy()

                elif clicked_card == "capitalism":
                    game.activate_capitalism()

                elif clicked_card == "plague":
                    game.activate_plague()

                elif clicked_card == "solo":
                    game.activate_solo()

                elif clicked_card == "absoluteprotection":
                    game.activate_absoluteprotection()

                elif clicked_card == "timetraveler":
                    game.activate_timetraveler()

                elif clicked_card == "extrablood":
                    game.activate_extrablood()

                elif clicked_card == "chrisma":
                    game.activate_chrisma()

                else:
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
                square = get_square_from_mouse(event.pos)

                if square is not None:
                    row, col = square

                    if dragging_card == "pawntastic":
                        game.activate_pawntastic_on_square(row, col)

                    elif dragging_card == "bishock":
                        game.activate_bishock_on_square(row, col)

                    elif dragging_card == "rookdemon":
                        game.activate_rookdemon_on_square(row, col)

                    elif dragging_card == "windknight":
                        game.activate_windknight_on_square(row, col)

                    elif dragging_card == "queentum":
                        game.activate_queentum_on_square(row, col)

                    elif dragging_card == "longlivetheking":
                        game.activate_longlivetheking_on_square(row, col)

                    elif dragging_card == "armageddon":
                        game.activate_armageddon_on_square(row, col)

                    elif dragging_card == "thedramatic":
                        game.activate_thedramatic_on_square(row, col)

                    elif dragging_card == "inzone":
                        game.activate_inzone_on_square(row, col)

                else:
                    game.status_message = "Drop the card on a valid piece."

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

    draw_background()
    draw_board()
    draw_fire_tiles()
    draw_pieces()
    draw_animations()
    draw_game_over_overlay()
    draw_sidebar()
    draw_dragging_card()
    draw_dragging_piece()
    draw_info_panel()

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
