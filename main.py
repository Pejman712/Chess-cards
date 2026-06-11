import pygame
import sys
import copy
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
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
pygame.display.set_caption("Chess Power-Up Cards")
SCREEN_WIDTH, SCREEN_HEIGHT = screen.get_size()
clock = pygame.time.Clock()

# Side-card layout:
# piece power cards on the left, general/game cards on the right.
INFO_HEIGHT = 112
SIDE_MARGIN = 14

LEFT_PANEL_WIDTH = max(220, min(300, SCREEN_WIDTH // 6))
RIGHT_PANEL_WIDTH = max(430, min(560, SCREEN_WIDTH // 3))

BOARD_AREA_WIDTH = SCREEN_WIDTH - LEFT_PANEL_WIDTH - RIGHT_PANEL_WIDTH - SIDE_MARGIN * 2
BOARD_AREA_HEIGHT = SCREEN_HEIGHT - INFO_HEIGHT - SIDE_MARGIN * 2

BOARD_SIZE = min(BOARD_AREA_WIDTH, BOARD_AREA_HEIGHT)
SQUARE_SIZE = BOARD_SIZE // ROWS
BOARD_SIZE = SQUARE_SIZE * ROWS

BOARD_X = LEFT_PANEL_WIDTH + SIDE_MARGIN + max(0, (BOARD_AREA_WIDTH - BOARD_SIZE) // 2)
BOARD_Y = SIDE_MARGIN + max(0, (BOARD_AREA_HEIGHT - BOARD_SIZE) // 2)

LEFT_PANEL_X = 0
RIGHT_PANEL_X = SCREEN_WIDTH - RIGHT_PANEL_WIDTH
INFO_Y = SCREEN_HEIGHT - INFO_HEIGHT

WIDTH = SCREEN_WIDTH
HEIGHT = SCREEN_HEIGHT

# -----------------------------
# Colors
# -----------------------------
LIGHT_SQUARE = (240, 217, 181)
DARK_SQUARE = (181, 136, 99)
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
TABLE_BG = (39, 24, 14)
TABLE_BG_2 = (65, 39, 21)
WOOD_FRAME = (105, 62, 28)
WOOD_FRAME_DARK = (35, 20, 10)
WOOD_FRAME_LIGHT = (182, 125, 58)
PANEL_BG = (24, 19, 15)
PANEL_EDGE = (151, 105, 52)
GOLD = (225, 190, 104)
PARCHMENT = (224, 202, 157)
CARD_SHELF_BG = (18, 15, 13)

# Short effect animations.
animations = []

font = pygame.font.SysFont("dejavusans", int(SQUARE_SIZE * 0.82))
small_font = pygame.font.SysFont("dejavusans", 21)
tiny_font = pygame.font.SysFont("dejavusans", max(16, int(SQUARE_SIZE * 0.20)))

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
    "meterstrike",
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
    "meterstrike",
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

CARD_GAP = max(8, SCREEN_HEIGHT // 95)
MAX_ROWS = max(len(PIECE_POWER_CARDS), (len(GENERAL_CARDS) + 1) // 2)
AVAILABLE_CARD_HEIGHT = max(360, SCREEN_HEIGHT - INFO_HEIGHT - SIDE_MARGIN * 4)
MAX_CARD_HEIGHT_FROM_ROWS = (AVAILABLE_CARD_HEIGHT - CARD_GAP * (MAX_ROWS - 1)) // MAX_ROWS
MAX_CARD_WIDTH_FROM_HEIGHT = int(MAX_CARD_HEIGHT_FROM_ROWS / 1.32)

# Very large card art. Cards intentionally overlap.
# The side panels are only anchor zones; the cards may extend over the board.
CARD_WIDTH = max(300, min(390, SCREEN_WIDTH // 5))
CARD_HEIGHT = int(CARD_WIDTH * 1.32)

# Separate spacing from actual card size so cards can overlap heavily.
LEFT_CARD_STEP = max(86, min(125, (SCREEN_HEIGHT - INFO_HEIGHT - SIDE_MARGIN * 4) // max(1, len(PIECE_POWER_CARDS))))
RIGHT_CARD_STEP = max(
    42,
    (SCREEN_HEIGHT - INFO_HEIGHT - SIDE_MARGIN * 2 - CARD_HEIGHT) // max(1, (len(GENERAL_CARDS) - 1))
)
RIGHT_CARD_COLUMN_STEP = 0
CARD_TOP = SIDE_MARGIN + 46


def load_card_image(path):
    try:
        image = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(image, (CARD_WIDTH, CARD_HEIGHT))
    except pygame.error:
        return None


# -----------------------------
# Piece symbols
# Uppercase = White
# Lowercase = Black
# -----------------------------
PIECE_SYMBOLS = {
    # Use filled glyphs for both sides. Color distinguishes white vs black.
    "P": "♟", "R": "♜", "N": "♞", "B": "♝", "Q": "♛", "K": "♚",
    "p": "♟", "r": "♜", "n": "♞", "b": "♝", "q": "♛", "k": "♚",
}

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
    "meterstrike": 30,
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
    "meterstrike",
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
    return (x + SQUARE_SIZE // 2, y + SQUARE_SIZE // 2)


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


def draw_background():
    screen.fill(TABLE_BG)

    # Dark wood table with alternating bands.
    band_h = max(24, SCREEN_HEIGHT // 26)
    for y in range(0, SCREEN_HEIGHT, band_h):
        color = TABLE_BG if (y // band_h) % 2 == 0 else TABLE_BG_2
        pygame.draw.rect(screen, color, pygame.Rect(0, y, SCREEN_WIDTH, band_h))

    # Center glow behind the board.
    glow = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    pygame.draw.circle(
        glow,
        (220, 170, 80, 28),
        (SCREEN_WIDTH // 2, BOARD_Y + BOARD_SIZE // 2),
        max(BOARD_SIZE // 2, 320),
    )
    screen.blit(glow, (0, 0))

    # Board shadow.
    shadow_rect = pygame.Rect(BOARD_X - 20, BOARD_Y + 14, BOARD_SIZE + 40, BOARD_SIZE + 44)
    shadow_surface = pygame.Surface((shadow_rect.width, shadow_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(shadow_surface, (0, 0, 0, 115), shadow_surface.get_rect(), border_radius=22)
    screen.blit(shadow_surface, shadow_rect)


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
                    rect = pygame.Rect(0, 0, SQUARE_SIZE, SQUARE_SIZE)
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

            banner_w = min(780, SCREEN_WIDTH - 120)
            banner_h = 88
            banner = pygame.Rect(0, 0, banner_w, banner_h)
            banner.center = (SCREEN_WIDTH // 2, max(85, BOARD_Y + BOARD_SIZE // 2))

            pygame.draw.rect(surface, (20, 14, 8, alpha), banner, border_radius=16)
            pygame.draw.rect(surface, (*GOLD, alpha), banner, 3, border_radius=16)

            text_surface = small_font.render(anim["text"], True, color)
            text_surface.set_alpha(alpha)
            rect = text_surface.get_rect(center=banner.center)
            surface.blit(text_surface, rect)
            screen.blit(surface, (0, 0))

        anim["frames"] -= 1
        if anim["frames"] <= 0:
            finished.append(anim)

    for anim in finished:
        animations.remove(anim)



class GameState:
    def __init__(self):
        self.board = initial_board()
        self.turn = WHITE
        self.selected = None
        self.legal_moves_for_selected = []

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
        self.turn = self.enemy_color(self.turn)
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
            self.fire_tiles[(row, col)] = 2

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
        self.turn = self.enemy_color(self.turn)
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
        self.turn = self.enemy_color(self.turn)
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
        self.turn = self.enemy_color(self.turn)
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

    def activate_meterstrike_on_square(self, row, col):
        if self.game_over:
            return

        if not self.pay_for_game_card("meterstrike"):
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
        add_animation("blast", squares=fire_squares, text="METEOR", color=(255, 95, 35), frames=38)

        self.consume_turn_after_game_card(
            f"{{player}} played Meterstrike. Destroyed {destroyed_count} piece(s) and created fire."
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
        self.turn = self.enemy_color(self.turn)
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
                self.turn = self.enemy_color(self.turn)
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
                self.turn = self.enemy_color(self.turn)
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
                self.turn = self.enemy_color(self.turn)
                self.selected = None
                self.legal_moves_for_selected = []
                self.start_turn_effects()
                self.update_status()
                return

            self.award_check_bonus_for_player(color)
            self.decay_fire_tiles()
            self.active_card = None
            self.active_card_owner = None
            self.turn = self.enemy_color(self.turn)
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
drag_offset_x = 0
drag_offset_y = 0


def is_board_flipped():
    return game.turn == BLACK


def board_to_screen(row, col):
    if is_board_flipped():
        display_row = 7 - row
        display_col = 7 - col
    else:
        display_row = row
        display_col = col

    x = BOARD_X + display_col * SQUARE_SIZE
    y = BOARD_Y + display_row * SQUARE_SIZE
    return x, y


def get_card_rects():
    rects = {}

    # Left side: piece power cards, one large vertical column.
    left_x = LEFT_PANEL_X + 10

    for index, card_name in enumerate(PIECE_POWER_CARDS):
        y = CARD_TOP + index * LEFT_CARD_STEP
        rects[card_name] = pygame.Rect(left_x, y, CARD_WIDTH, CARD_HEIGHT)

    # Right side: general/game cards, one large overlapping column.
    # The column spans the full vertical space; cards overlap by design.
    right_start_x = SCREEN_WIDTH - CARD_WIDTH - 14

    for index, card_name in enumerate(GENERAL_CARDS):
        x = right_start_x
        y = CARD_TOP + index * RIGHT_CARD_STEP
        rects[card_name] = pygame.Rect(x, y, CARD_WIDTH, CARD_HEIGHT)

    return rects


# -----------------------------
# Drawing
# -----------------------------
def draw_board():
    # Classic wooden frame.
    outer = pygame.Rect(BOARD_X - 18, BOARD_Y - 18, BOARD_SIZE + 36, BOARD_SIZE + 36)
    middle = pygame.Rect(BOARD_X - 10, BOARD_Y - 10, BOARD_SIZE + 20, BOARD_SIZE + 20)
    pygame.draw.rect(screen, WOOD_FRAME_DARK, outer, border_radius=16)
    pygame.draw.rect(screen, WOOD_FRAME, middle, border_radius=12)
    pygame.draw.rect(screen, WOOD_FRAME_LIGHT, middle, 4, border_radius=12)
    pygame.draw.rect(screen, GOLD, pygame.Rect(BOARD_X - 3, BOARD_Y - 3, BOARD_SIZE + 6, BOARD_SIZE + 6), 2)

    for row in range(ROWS):
        for col in range(COLS):
            color = LIGHT_SQUARE if (row + col) % 2 == 0 else DARK_SQUARE
            x, y = board_to_screen(row, col)
            rect = pygame.Rect(x, y, SQUARE_SIZE, SQUARE_SIZE)
            pygame.draw.rect(screen, color, rect)

            # Subtle inner shading for a more classic board look.
            shade = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
            shade.fill((255, 255, 255, 16) if (row + col) % 2 == 0 else (0, 0, 0, 18))
            screen.blit(shade, rect)

    # Coordinates around the board.
    files = "abcdefgh"
    ranks = "87654321"

    for display_col in range(8):
        if is_board_flipped():
            label = files[7 - display_col]
        else:
            label = files[display_col]

        text = tiny_font.render(label, True, PARCHMENT)
        x = BOARD_X + display_col * SQUARE_SIZE + SQUARE_SIZE // 2 - text.get_width() // 2
        screen.blit(text, (x, BOARD_Y + BOARD_SIZE + 2))

    for display_row in range(8):
        if is_board_flipped():
            label = ranks[7 - display_row]
        else:
            label = ranks[display_row]

        text = tiny_font.render(label, True, PARCHMENT)
        y = BOARD_Y + display_row * SQUARE_SIZE + SQUARE_SIZE // 2 - text.get_height() // 2
        screen.blit(text, (BOARD_X - 15, y))

    if game.is_in_check(game.turn):
        king_pos = game.find_king(game.turn)

        if king_pos is not None:
            kr, kc = king_pos
            x, y = board_to_screen(kr, kc)
            rect = pygame.Rect(x, y, SQUARE_SIZE, SQUARE_SIZE)
            check_surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
            check_surface.fill((220, 35, 35, 135))
            screen.blit(check_surface, rect)

    if game.selected is not None:
        row, col = game.selected
        x, y = board_to_screen(row, col)
        rect = pygame.Rect(x, y, SQUARE_SIZE, SQUARE_SIZE)
        pygame.draw.rect(screen, SELECT_COLOR, rect, max(4, SQUARE_SIZE // 18))

    for move in game.legal_moves_for_selected:
        row, col = move
        x, y = board_to_screen(row, col)
        center = (x + SQUARE_SIZE // 2, y + SQUARE_SIZE // 2)

        if game.board[row][col] is None:
            pygame.draw.circle(screen, LEGAL_MOVE_COLOR, center, max(7, SQUARE_SIZE // 7))
            pygame.draw.circle(screen, (20, 90, 30), center, max(8, SQUARE_SIZE // 7), 2)
        else:
            pygame.draw.circle(screen, CAPTURE_COLOR, center, max(11, SQUARE_SIZE // 5), 4)


def draw_fire_tiles():
    for (row, col), turns_remaining in game.fire_tiles.items():
        x, y = board_to_screen(row, col)
        rect = pygame.Rect(x, y, SQUARE_SIZE, SQUARE_SIZE)

        fire_surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
        fire_surface.fill((255, 80, 0, 90))
        screen.blit(fire_surface, rect)

        cx, cy = rect.center
        for i in range(3):
            radius = int(SQUARE_SIZE * (0.18 + i * 0.08))
            pygame.draw.circle(screen, (255, 160 - i * 30, 30), (cx, cy - i * 4), radius, 2)

        flame_text = tiny_font.render("FIRE", True, (255, 240, 200))
        flame_rect = flame_text.get_rect(center=rect.center)
        screen.blit(flame_text, flame_rect)

        turns_text = tiny_font.render(str(turns_remaining), True, (255, 240, 200))
        screen.blit(turns_text, (rect.x + 5, rect.y + 5))


def draw_pieces():
    for row in range(ROWS):
        for col in range(COLS):
            piece = game.board[row][col]

            if piece is None:
                continue

            x, y = board_to_screen(row, col)
            symbol = PIECE_SYMBOLS[piece]
            piece_color = (245, 245, 245) if piece.isupper() else (25, 25, 25)
            outline_color = (25, 25, 25) if piece.isupper() else (245, 245, 245)

            text_surface = font.render(symbol, True, piece_color)
            text_rect = text_surface.get_rect(center=(x + SQUARE_SIZE // 2, y + SQUARE_SIZE // 2))

            # Strong outline so filled pieces remain visible on both square colors.
            for ox, oy in [
                (-2, 0), (2, 0), (0, -2), (0, 2),
                (-2, -2), (-2, 2), (2, -2), (2, 2),
            ]:
                outline = font.render(symbol, True, outline_color)
                screen.blit(outline, text_rect.move(ox, oy))
            screen.blit(text_surface, text_rect)

            if (row, col) in game.rookdemon_rooks:
                remaining = game.rookdemon_rooks[(row, col)]
                badge = tiny_font.render(f"D{remaining}", True, (255, 80, 20))
                screen.blit(badge, (x + 5, y + SQUARE_SIZE - 22))

            if (row, col) == game.windknight_square:
                badge = tiny_font.render(f"W{game.windknight_moves_remaining}", True, (70, 220, 255))
                screen.blit(badge, (x + SQUARE_SIZE - 28, y + SQUARE_SIZE - 22))

            if (row, col) in game.dramatic_pieces:
                badge = tiny_font.render("D!", True, (255, 230, 60))
                screen.blit(badge, (x + SQUARE_SIZE - 28, y + 4))

            if (row, col) == game.inzone_square:
                badge = tiny_font.render("Z!", True, (255, 70, 70))
                screen.blit(badge, (x + 5, y + 4))


def draw_single_card(rect, owner, card_name):
    used = card_name in game.used_cards[owner] if card_name in ABILITY_CARDS else False

    labels = {
        "pawntastic": ("Pawntastic", (40, 90, 40), ["Pawn", "1-4 forward"]),
        "bishock": ("Bishock", (80, 40, 100), ["Bishop", "shock"]),
        "rookdemon": ("Rookdemon", (120, 40, 20), ["Rook", "fire trail"]),
        "windknight": ("Windknight", (30, 90, 85), ["Knight", "moves twice"]),
        "queentum": ("Queentum", (70, 35, 105), ["Queen", "teleports"]),
        "longlivetheking": ("LongLive", (105, 80, 25), ["King", "escapes"]),
        "switchero": ("Switchero", (40, 65, 130), ["Swap", "ownership"]),
        "prophecy": ("Prophecy", (120, 95, 30), ["Your pawns", "to queens"]),
        "meterstrike": ("Meterstrike", (120, 45, 35), ["3x3 blast", "+ fire"]),
        "thedramatic": ("TheDramatic", (95, 45, 95), ["Marked piece", "revenge"]),
        "capitalism": ("Capitalism", (45, 130, 65), ["Pay 100", "win"]),
        "plague": ("Plague", (65, 110, 45), ["Start turn", "enemy dies"]),
        "solo": ("Solo", (45, 45, 45), ["Only king", "wins"]),
        "absoluteprotection": ("AbsProtect", (35, 95, 140), ["One turn", "shield"]),
        "timetraveler": ("TimeTraveler", (40, 80, 140), ["Back", "3 turns"]),
        "extrablood": ("ExtraBlood", (120, 25, 25), ["Passive", "2x capture"]),
        "chrisma": ("Chrisma", (135, 45, 115), ["Charm", "near king"]),
        "inzone": ("InZone", (150, 40, 35), ["Capture", "streak"]),
    }

    fallback_name, fallback_color, desc_lines = labels.get(card_name, (card_name, (70, 70, 70), []))
    image = card_images.get(owner, {}).get(card_name)

    if image is not None:
        card_surface = image.copy()
    else:
        card_surface = pygame.Surface((CARD_WIDTH, CARD_HEIGHT), pygame.SRCALPHA)
        card_surface.fill((*fallback_color, 255))

        # Dramatic fallback picture: radial rings and symbolic center.
        pygame.draw.rect(card_surface, WOOD_FRAME_DARK, card_surface.get_rect(), border_radius=10)
        inner = pygame.Rect(4, 4, CARD_WIDTH - 8, CARD_HEIGHT - 8)
        pygame.draw.rect(card_surface, fallback_color, inner, border_radius=8)
        pygame.draw.rect(card_surface, GOLD, inner, 2, border_radius=8)

        symbol_map = {
            "switchero": "⇄",
            "prophecy": "♛",
            "meterstrike": "✦",
            "thedramatic": "☠",
            "capitalism": "$",
            "plague": "☣",
            "solo": "♚",
            "absoluteprotection": "♜",
        }
        symbol = symbol_map.get(card_name, "✦")

        for radius in [CARD_WIDTH // 4, CARD_WIDTH // 3]:
            pygame.draw.circle(card_surface, (*GOLD, 120), (CARD_WIDTH // 2, CARD_HEIGHT // 2), radius, 2)

        big = small_font.render(symbol, True, TEXT_COLOR)
        big_rect = big.get_rect(center=(CARD_WIDTH // 2, CARD_HEIGHT // 2 - 4))
        card_surface.blit(big, big_rect)

        label = tiny_font.render(fallback_name, True, TEXT_COLOR)
        label_rect = label.get_rect(center=(CARD_WIDTH // 2, max(14, CARD_HEIGHT // 6)))
        card_surface.blit(label, label_rect)

        y = CARD_HEIGHT - 42
        for line in desc_lines[:2]:
            text = tiny_font.render(line, True, TEXT_COLOR)
            text_rect = text.get_rect(center=(CARD_WIDTH // 2, y))
            card_surface.blit(text, text_rect)
            y += 16

    cost = CARD_COSTS.get(card_name, 0)

    if used:
        overlay = pygame.Surface((CARD_WIDTH, CARD_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 165))
        card_surface.blit(overlay, (0, 0))

        buy_surface = tiny_font.render(f"BUY: {cost} ETHER", True, TEXT_COLOR)
        buy_rect = buy_surface.get_rect(center=(CARD_WIDTH // 2, CARD_HEIGHT // 2 + 20))
        card_surface.blit(buy_surface, buy_rect)

    screen.blit(card_surface, rect)

    border_color = CARD_DISABLED if used else CARD_BORDER
    pygame.draw.rect(screen, border_color, rect, 3, border_radius=10)

    if used:
        used_surface = tiny_font.render("USED", True, TEXT_COLOR)
        used_rect = used_surface.get_rect(center=rect.center)
        screen.blit(used_surface, used_rect)


def draw_game_over_overlay():
    if game.winner_message is None:
        return

    overlay = pygame.Surface((BOARD_SIZE, BOARD_SIZE), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 105))
    screen.blit(overlay, (BOARD_X, BOARD_Y))

    box_w = min(BOARD_SIZE - 80, 620)
    box_h = 110
    box = pygame.Rect(0, 0, box_w, box_h)
    box.center = (BOARD_X + BOARD_SIZE // 2, BOARD_Y + BOARD_SIZE // 2)

    pygame.draw.rect(screen, WOOD_FRAME_DARK, box, border_radius=16)
    pygame.draw.rect(screen, GOLD, box, 4, border_radius=16)

    title = small_font.render("GAME OVER", True, GOLD)
    title_rect = title.get_rect(center=(box.centerx, box.y + 32))
    screen.blit(title, title_rect)

    result = small_font.render(game.winner_message, True, TEXT_COLOR)
    result_rect = result.get_rect(center=(box.centerx, box.y + 72))
    screen.blit(result, result_rect)


def draw_sidebar():
    # Left panel: piece power cards.
    left_rect = pygame.Rect(0, 0, LEFT_PANEL_WIDTH, SCREEN_HEIGHT)
    right_rect = pygame.Rect(RIGHT_PANEL_X, 0, RIGHT_PANEL_WIDTH, SCREEN_HEIGHT)

    pygame.draw.rect(screen, CARD_SHELF_BG, left_rect)
    pygame.draw.rect(screen, CARD_SHELF_BG, right_rect)

    pygame.draw.line(screen, PANEL_EDGE, (LEFT_PANEL_WIDTH - 1, 0), (LEFT_PANEL_WIDTH - 1, SCREEN_HEIGHT), 4)
    pygame.draw.line(screen, PANEL_EDGE, (RIGHT_PANEL_X, 0), (RIGHT_PANEL_X, SCREEN_HEIGHT), 4)

    # Header plaques.
    left_header = pygame.Rect(10, 8, LEFT_PANEL_WIDTH - 20, 34)
    right_header = pygame.Rect(RIGHT_PANEL_X + 10, 8, RIGHT_PANEL_WIDTH - 20, 34)

    for plaque, title in [
        (left_header, "Piece Powers"),
        (right_header, "General Cards"),
    ]:
        pygame.draw.rect(screen, WOOD_FRAME_DARK, plaque, border_radius=8)
        pygame.draw.rect(screen, WOOD_FRAME, plaque, 2, border_radius=8)
        title_surface = tiny_font.render(title, True, PARCHMENT)
        title_rect = title_surface.get_rect(center=plaque.center)
        screen.blit(title_surface, title_rect)

    # Player / Ether mini panels.
    turn_box = pygame.Rect(10, SCREEN_HEIGHT - INFO_HEIGHT + 6, LEFT_PANEL_WIDTH - 20, INFO_HEIGHT - 12)
    pygame.draw.rect(screen, WOOD_FRAME_DARK, turn_box, border_radius=8)
    pygame.draw.rect(screen, GOLD, turn_box, 2, border_radius=8)

    turn_text = tiny_font.render(f"{game.turn.capitalize()} turn", True, PARCHMENT)
    ether_text_1 = tiny_font.render(f"W Ether: {game.ether[WHITE]}", True, TEXT_COLOR)
    ether_text_2 = tiny_font.render(f"B Ether: {game.ether[BLACK]}", True, TEXT_COLOR)
    screen.blit(turn_text, (turn_box.x + 8, turn_box.y + 4))
    screen.blit(ether_text_1, (turn_box.x + 8, turn_box.y + 22))
    screen.blit(ether_text_2, (turn_box.x + 8, turn_box.y + 40))

    if is_board_flipped():
        view_text = "Black view"
    else:
        view_text = "White view"

    view_surface = tiny_font.render(view_text, True, MUTED_TEXT)
    screen.blit(view_surface, (RIGHT_PANEL_X + 14, SCREEN_HEIGHT - INFO_HEIGHT + 10))

    status_flags = []
    if game.plague_active:
        status_flags.append("Plague")
    if game.absolute_protection_active:
        status_flags.append("Protection")
    if game.extra_blood_active:
        status_flags.append("ExtraBlood")

    if status_flags:
        flags = tiny_font.render(" | ".join(status_flags), True, GOLD)
        screen.blit(flags, (RIGHT_PANEL_X + 14, SCREEN_HEIGHT - INFO_HEIGHT + 32))

    card_rects = get_card_rects()
    mouse_pos = pygame.mouse.get_pos()

    hovered = None

    for card_name, rect in card_rects.items():
        if dragging_card == card_name:
            continue

        if rect.collidepoint(mouse_pos):
            hovered = card_name
            continue

        draw_single_card(rect, game.turn, card_name)

    # Draw hovered card last and enlarged so overlapped cards are readable.
    if hovered is not None and hovered != dragging_card:
        rect = card_rects[hovered].inflate(44, 44)
        pygame.draw.rect(screen, (255, 220, 110), rect.inflate(12, 12), 4, border_radius=16)
        draw_single_card(rect, game.turn, hovered)


def draw_dragging_card():
    if dragging_card is None:
        return

    mouse_x, mouse_y = pygame.mouse.get_pos()

    rect = pygame.Rect(
        mouse_x - drag_offset_x,
        mouse_y - drag_offset_y,
        CARD_WIDTH + 34,
        CARD_HEIGHT + 34
    )

    draw_single_card(rect, game.turn, dragging_card)


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
        card_text = "Left: piece powers. Right: general cards. Click instant cards or drag targeted cards."

    bar = pygame.Rect(LEFT_PANEL_WIDTH, INFO_Y, SCREEN_WIDTH - LEFT_PANEL_WIDTH - RIGHT_PANEL_WIDTH, INFO_HEIGHT)
    pygame.draw.rect(screen, PANEL_BG, bar)
    pygame.draw.line(screen, PANEL_EDGE, (bar.x, bar.y), (bar.right, bar.y), 4)

    # Winner/result line is always prominent at game end.
    if game.winner_message is not None:
        result_surface = small_font.render(f"GAME OVER: {game.winner_message}", True, GOLD)
        result_rect = result_surface.get_rect(center=(bar.centerx, bar.y + 20))
        screen.blit(result_surface, result_rect)
        first_line_y = bar.y + 46
    else:
        turn_surface = small_font.render(f"{game.turn.capitalize()} to act", True, GOLD)
        screen.blit(turn_surface, (bar.x + 14, bar.y + 10))
        first_line_y = bar.y + 38

    status_surface = tiny_font.render(game.status_message, True, TEXT_COLOR)
    help_surface = tiny_font.render(card_text, True, MUTED_TEXT)

    ether_text = f"Ether: White {game.ether[WHITE]} | Black {game.ether[BLACK]}"
    ether_surface = tiny_font.render(ether_text, True, GOLD)

    rules_text = "Money: +1 Ether per tile moved | capture = piece value | check = +5 Ether | click USED ability to refill"
    rules_surface = tiny_font.render(rules_text, True, PARCHMENT)

    active_flags = []
    if game.plague_active:
        active_flags.append("Plague")
    if game.absolute_protection_active:
        active_flags.append("AbsoluteProtection")
    if game.extra_blood_active:
        active_flags.append("ExtraBlood")
    if game.active_card:
        active_flags.append(f"Active card: {game.active_card}")

    flags_text = "Active effects: " + (", ".join(active_flags) if active_flags else "none")
    flags_surface = tiny_font.render(flags_text, True, MUTED_TEXT)

    x = bar.x + 14
    screen.blit(status_surface, (x, first_line_y))
    screen.blit(help_surface, (x, first_line_y + 22))
    screen.blit(rules_surface, (x, first_line_y + 44))
    screen.blit(flags_surface, (x, first_line_y + 66))

    screen.blit(ether_surface, (bar.right - ether_surface.get_width() - 14, first_line_y))



def get_square_from_mouse(pos):
    x, y = pos

    if x < BOARD_X or x >= BOARD_X + BOARD_SIZE:
        return None

    if y < BOARD_Y or y >= BOARD_Y + BOARD_SIZE:
        return None

    display_row = (y - BOARD_Y) // SQUARE_SIZE
    display_col = (x - BOARD_X) // SQUARE_SIZE

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
                    drag_offset_x = mouse_pos[0] - card_rects[clicked_card].x
                    drag_offset_y = mouse_pos[1] - card_rects[clicked_card].y

            else:
                square = get_square_from_mouse(mouse_pos)

                if square is not None:
                    row, col = square
                    game.select_square(row, col)

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

                    elif dragging_card == "meterstrike":
                        game.activate_meterstrike_on_square(row, col)

                    elif dragging_card == "thedramatic":
                        game.activate_thedramatic_on_square(row, col)

                    elif dragging_card == "inzone":
                        game.activate_inzone_on_square(row, col)

                else:
                    game.status_message = "Drop the card on a valid piece."

                dragging_card = None

    draw_background()
    draw_board()
    draw_fire_tiles()
    draw_pieces()
    draw_animations()
    draw_game_over_overlay()
    draw_sidebar()
    draw_dragging_card()
    draw_info_panel()

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
