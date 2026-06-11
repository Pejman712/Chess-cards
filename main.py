import pygame
import sys
import copy
import os

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
BOARD_SIZE = 640
ROWS = 8
COLS = 8
SQUARE_SIZE = BOARD_SIZE // ROWS

SIDEBAR_WIDTH = 220
INFO_HEIGHT = 80

WIDTH = BOARD_SIZE + SIDEBAR_WIDTH
HEIGHT = BOARD_SIZE + INFO_HEIGHT

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Chess Power-Up Cards")
clock = pygame.time.Clock()

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

font = pygame.font.SysFont("dejavusans", 44)
small_font = pygame.font.SysFont("dejavusans", 21)
tiny_font = pygame.font.SysFont("dejavusans", 16)

# -----------------------------
# Card images
# -----------------------------
CARD_WIDTH = 100
CARD_HEIGHT = 112

PAWNTASTIC_IMAGE_PATH = os.path.join("cards", "pawntastic.png")
BISHOCK_IMAGE_PATH = os.path.join("cards", "bishock.png")
ROOKDEMON_IMAGE_PATH = os.path.join("cards", "rookdemon.png")
WINDKNIGHT_IMAGE_PATH = os.path.join("cards", "windknight.png")
QUEENTUM_IMAGE_PATH = os.path.join("cards", "queentum.png")
LONGLIVETHEKING_IMAGE_PATH = os.path.join("cards", "longlivetheking.png")


def load_card_image(path):
    try:
        image = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(image, (CARD_WIDTH, CARD_HEIGHT))
    except pygame.error:
        return None


pawntastic_image = load_card_image(PAWNTASTIC_IMAGE_PATH)
bishock_image = load_card_image(BISHOCK_IMAGE_PATH)
rookdemon_image = load_card_image(ROOKDEMON_IMAGE_PATH)
windknight_image = load_card_image(WINDKNIGHT_IMAGE_PATH)
queentum_image = load_card_image(QUEENTUM_IMAGE_PATH)
longlivetheking_image = load_card_image(LONGLIVETHEKING_IMAGE_PATH)

# -----------------------------
# Piece symbols
# Uppercase = White
# Lowercase = Black
# -----------------------------
PIECE_SYMBOLS = {
    "P": "♙", "R": "♖", "N": "♘", "B": "♗", "Q": "♕", "K": "♔",
    "p": "♟", "r": "♜", "n": "♞", "b": "♝", "q": "♛", "k": "♚",
}

WHITE = "white"
BLACK = "black"


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

        # Windknight state:
        # The selected knight must move twice before the turn changes.
        self.windknight_square = None
        self.windknight_moves_remaining = 0

        # Fire / Rookdemon system
        self.fire_tiles = {}
        self.rookdemon_rooks = {}

        # Castling rights
        self.white_king_moved = False
        self.black_king_moved = False
        self.white_left_rook_moved = False
        self.white_right_rook_moved = False
        self.black_left_rook_moved = False
        self.black_right_rook_moved = False

        self.en_passant_target = None

        self.game_over = False
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

        for destroy_row, destroy_col in destroyed_squares:
            target_piece = self.board[destroy_row][destroy_col]

            if target_piece is not None and target_piece.lower() == "k":
                continue

            self.board[destroy_row][destroy_col] = None
            self.fire_tiles.pop((destroy_row, destroy_col), None)
            self.rookdemon_rooks.pop((destroy_row, destroy_col), None)

            if self.windknight_square == (destroy_row, destroy_col):
                self.windknight_square = None
                self.windknight_moves_remaining = 0

        self.used_cards[self.turn].add("bishock")

        self.active_card = None
        self.active_card_owner = None
        self.selected = None
        self.legal_moves_for_selected = []

        self.decay_fire_tiles()
        self.turn = self.enemy_color(self.turn)
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

        self.rookdemon_rooks[(row, col)] = 2
        self.used_cards[self.turn].add("rookdemon")

        self.selected = None
        self.legal_moves_for_selected = []
        self.active_card = None
        self.active_card_owner = None

        self.status_message = f"{self.turn.capitalize()} empowered a rook with Rookdemon."
        self.decay_fire_tiles()
        self.turn = self.enemy_color(self.turn)
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
        self.decay_fire_tiles()
        escaped_player = self.turn
        self.turn = self.enemy_color(self.turn)
        self.status_message = (
            f"{escaped_player.capitalize()} escaped to a random corner "
            f"and spawned {spawned} pawn(s)."
        )
        self.update_status()

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

        color = self.piece_color(piece)
        piece_type = piece.lower()

        was_windknight_move = (
            self.active_card == "windknight"
            and self.windknight_square == original_from_square
            and piece_type == "n"
        )

        if captured_piece is not None:
            self.update_castling_rights_for_capture(to_row, to_col, captured_piece)

        if piece_type == "p" and self.en_passant_target == (to_row, to_col) and captured_piece is None:
            capture_row = from_row
            capture_col = to_col
            self.board[capture_row][capture_col] = None
            self.rookdemon_rooks.pop((capture_row, capture_col), None)

            if self.windknight_square == (capture_row, capture_col):
                self.windknight_square = None
                self.windknight_moves_remaining = 0

        self.board[to_row][to_col] = piece
        self.board[from_row][from_col] = None

        if captured_piece is not None:
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

            self.apply_fire_damage_at(to_row, to_col)

            moved_piece_survived = self.board[to_row][to_col] is not None

            if not moved_piece_survived:
                self.rookdemon_rooks.pop((to_row, to_col), None)

                if self.windknight_square == (to_row, to_col):
                    self.windknight_square = None
                    self.windknight_moves_remaining = 0

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
                self.update_status()
                return

            self.decay_fire_tiles()
            self.active_card = None
            self.active_card_owner = None
            self.turn = self.enemy_color(self.turn)
            self.selected = None
            self.legal_moves_for_selected = []
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
                    self.status_message = f"Checkmate. {winner} wins."
                    self.game_over = True
            else:
                self.status_message = f"{self.turn.capitalize()} is in check"
        else:
            if not self.has_any_legal_moves(self.turn):
                self.status_message = "Stalemate. Draw."
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


def get_card_rects():
    x = BOARD_SIZE + 60

    return {
        "pawntastic": pygame.Rect(x, 28, CARD_WIDTH, CARD_HEIGHT),
        "bishock": pygame.Rect(x, 130, CARD_WIDTH, CARD_HEIGHT),
        "rookdemon": pygame.Rect(x, 232, CARD_WIDTH, CARD_HEIGHT),
        "windknight": pygame.Rect(x, 334, CARD_WIDTH, CARD_HEIGHT),
        "queentum": pygame.Rect(x, 436, CARD_WIDTH, CARD_HEIGHT),
        "longlivetheking": pygame.Rect(x, 538, CARD_WIDTH, CARD_HEIGHT),
    }


# -----------------------------
# Drawing
# -----------------------------
def draw_board():
    for row in range(ROWS):
        for col in range(COLS):
            color = LIGHT_SQUARE if (row + col) % 2 == 0 else DARK_SQUARE

            rect = pygame.Rect(
                col * SQUARE_SIZE,
                row * SQUARE_SIZE,
                SQUARE_SIZE,
                SQUARE_SIZE
            )

            pygame.draw.rect(screen, color, rect)

    if game.is_in_check(game.turn):
        king_pos = game.find_king(game.turn)

        if king_pos is not None:
            kr, kc = king_pos
            rect = pygame.Rect(
                kc * SQUARE_SIZE,
                kr * SQUARE_SIZE,
                SQUARE_SIZE,
                SQUARE_SIZE
            )
            pygame.draw.rect(screen, CHECK_COLOR, rect)

    if game.selected is not None:
        row, col = game.selected
        rect = pygame.Rect(
            col * SQUARE_SIZE,
            row * SQUARE_SIZE,
            SQUARE_SIZE,
            SQUARE_SIZE
        )
        pygame.draw.rect(screen, SELECT_COLOR, rect, 5)

    for move in game.legal_moves_for_selected:
        row, col = move
        center = (
            col * SQUARE_SIZE + SQUARE_SIZE // 2,
            row * SQUARE_SIZE + SQUARE_SIZE // 2
        )

        if game.board[row][col] is None:
            pygame.draw.circle(screen, LEGAL_MOVE_COLOR, center, 12)
        else:
            pygame.draw.circle(screen, CAPTURE_COLOR, center, 16, 4)


def draw_fire_tiles():
    for (row, col), turns_remaining in game.fire_tiles.items():
        rect = pygame.Rect(
            col * SQUARE_SIZE,
            row * SQUARE_SIZE,
            SQUARE_SIZE,
            SQUARE_SIZE
        )

        fire_surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
        fire_surface.fill((255, 80, 0, 115))
        screen.blit(fire_surface, rect)

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

            symbol = PIECE_SYMBOLS[piece]
            text_surface = font.render(symbol, True, (20, 20, 20))
            text_rect = text_surface.get_rect(
                center=(
                    col * SQUARE_SIZE + SQUARE_SIZE // 2,
                    row * SQUARE_SIZE + SQUARE_SIZE // 2
                )
            )
            screen.blit(text_surface, text_rect)

            if (row, col) in game.rookdemon_rooks:
                remaining = game.rookdemon_rooks[(row, col)]
                badge = tiny_font.render(f"D{remaining}", True, (255, 80, 20))
                screen.blit(
                    badge,
                    (
                        col * SQUARE_SIZE + 5,
                        row * SQUARE_SIZE + SQUARE_SIZE - 22
                    )
                )

            if (row, col) == game.windknight_square:
                badge = tiny_font.render(f"W{game.windknight_moves_remaining}", True, (70, 220, 255))
                screen.blit(
                    badge,
                    (
                        col * SQUARE_SIZE + SQUARE_SIZE - 28,
                        row * SQUARE_SIZE + SQUARE_SIZE - 22
                    )
                )


def draw_single_card(rect, owner, card_name):
    used = card_name in game.used_cards[owner]

    if card_name == "pawntastic":
        image = pawntastic_image
        fallback_name = "Pawntastic"
        fallback_color = (40, 90, 40)
        desc_lines = ["Pawn moves", "1-4 forward"]

    elif card_name == "bishock":
        image = bishock_image
        fallback_name = "Bishock"
        fallback_color = (80, 40, 100)
        desc_lines = ["Destroy", "diagonals"]

    elif card_name == "rookdemon":
        image = rookdemon_image
        fallback_name = "Rookdemon"
        fallback_color = (120, 40, 20)
        desc_lines = ["Rook leaves", "fire trail"]

    elif card_name == "windknight":
        image = windknight_image
        fallback_name = "Windknight"
        fallback_color = (30, 90, 85)
        desc_lines = ["Knight moves", "twice"]

    elif card_name == "queentum":
        image = queentum_image
        fallback_name = "Queentum"
        fallback_color = (70, 35, 105)
        desc_lines = ["Queen", "teleports"]

    elif card_name == "longlivetheking":
        image = longlivetheking_image
        fallback_name = "LongLive"
        fallback_color = (105, 80, 25)
        desc_lines = ["King escapes", "to corner"]

    else:
        image = None
        fallback_name = card_name
        fallback_color = (70, 70, 70)
        desc_lines = []

    if image is not None:
        card_surface = image.copy()
    else:
        card_surface = pygame.Surface((CARD_WIDTH, CARD_HEIGHT))
        card_surface.fill(fallback_color)

        label = tiny_font.render(fallback_name, True, TEXT_COLOR)
        label_rect = label.get_rect(center=(CARD_WIDTH // 2, 32))
        card_surface.blit(label, label_rect)

        y = 70
        for line in desc_lines:
            text = tiny_font.render(line, True, TEXT_COLOR)
            text_rect = text.get_rect(center=(CARD_WIDTH // 2, y))
            card_surface.blit(text, text_rect)
            y += 22

    if used:
        overlay = pygame.Surface((CARD_WIDTH, CARD_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        card_surface.blit(overlay, (0, 0))

    screen.blit(card_surface, rect)

    border_color = CARD_DISABLED if used else CARD_BORDER
    pygame.draw.rect(screen, border_color, rect, 3, border_radius=10)

    if used:
        used_surface = small_font.render("USED", True, TEXT_COLOR)
        used_rect = used_surface.get_rect(center=rect.center)
        screen.blit(used_surface, used_rect)


def draw_sidebar():
    sidebar_rect = pygame.Rect(BOARD_SIZE, 0, SIDEBAR_WIDTH, BOARD_SIZE)
    pygame.draw.rect(screen, SIDEBAR_BG, sidebar_rect)

    title = small_font.render("Power Cards", True, TEXT_COLOR)
    screen.blit(title, (BOARD_SIZE + 45, 12))

    player_text = f"{game.turn.capitalize()}'s Cards"
    player_surface = tiny_font.render(player_text, True, TEXT_COLOR)
    screen.blit(player_surface, (BOARD_SIZE + 55, 31))

    card_rects = get_card_rects()

    for card_name, rect in card_rects.items():
        if dragging_card == card_name:
            continue

        draw_single_card(rect, game.turn, card_name)


def draw_dragging_card():
    if dragging_card is None:
        return

    mouse_x, mouse_y = pygame.mouse.get_pos()

    rect = pygame.Rect(
        mouse_x - drag_offset_x,
        mouse_y - drag_offset_y,
        CARD_WIDTH,
        CARD_HEIGHT
    )

    draw_single_card(rect, game.turn, dragging_card)


def draw_info_panel():
    rect = pygame.Rect(0, BOARD_SIZE, WIDTH, INFO_HEIGHT)
    pygame.draw.rect(screen, INFO_BG, rect)

    status_surface = small_font.render(game.status_message, True, TEXT_COLOR)
    screen.blit(status_surface, (20, BOARD_SIZE + 12))

    if game.active_card == "pawntastic":
        card_text = "Pawntastic active: click a highlighted destination."
    elif game.active_card == "windknight":
        card_text = "Windknight active: move the selected knight twice."
    elif game.active_card == "queentum":
        card_text = "Queentum active: click any legal teleport destination."
    else:
        card_text = "Drag a card onto a valid piece. Press R to reset."

    help_surface = small_font.render(card_text, True, TEXT_COLOR)
    screen.blit(help_surface, (20, BOARD_SIZE + 45))


def get_square_from_mouse(pos):
    x, y = pos

    if x >= BOARD_SIZE:
        return None

    if y >= BOARD_SIZE:
        return None

    row = y // SQUARE_SIZE
    col = x // SQUARE_SIZE

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
            if event.key == pygame.K_r:
                game = GameState()
                dragging_card = None

        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos
            card_rects = get_card_rects()

            clicked_card = None

            for card_name, rect in card_rects.items():
                if rect.collidepoint(mouse_pos):
                    clicked_card = card_name
                    break

            if clicked_card is not None:
                if clicked_card in game.used_cards[game.turn]:
                    game.status_message = f"{game.turn.capitalize()} has already used {clicked_card.capitalize()}."

                elif game.active_card is not None:
                    game.status_message = "Finish the active card move first."

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

                else:
                    game.status_message = "Drop the card on a valid piece."

                dragging_card = None

    screen.fill((0, 0, 0))
    draw_board()
    draw_fire_tiles()
    draw_pieces()
    draw_sidebar()
    draw_dragging_card()
    draw_info_panel()

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()