# Pure data describing the cards: names, groupings, costs, targeting rules,
# and display info. No pygame/runtime dependency - safe to import anywhere.

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
    "earthquake",
    "mirrormatch",
    "insurance",
    "shuffleup",
    "possession",
    "hotpotato",
    "pandorashand",
    "hydra",
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
    "earthquake",
    "mirrormatch",
    "insurance",
    "shuffleup",
    "possession",
    "hotpotato",
    "pandorashand",
    "hydra",
]

# Tray order: piece-power cards first, then game cards.
ALL_TRAY_CARDS = PIECE_POWER_CARDS + GENERAL_CARDS

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
    "earthquake", "mirrormatch", "insurance", "shuffleup", "possession",
    "hotpotato", "pandorashand", "hydra",
}

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
    "earthquake": 30,
    "mirrormatch": 20,
    "insurance": 15,
    "shuffleup": 35,
    "possession": 25,
    "hotpotato": 15,
    "pandorashand": 15,
    "hydra": 25,
}

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
    "earthquake": ("Earthquake", (110, 80, 40), "Every piece slides one rank toward its own back row; collisions kill the piece in front."),
    "mirrormatch": ("Mirror Match", (90, 100, 160), "Copy the last card the opponent played, for free."),
    "insurance": ("Insurance", (40, 120, 140), "Passive: the first piece you lose each turn pays double its value."),
    "shuffleup": ("Shuffle Up", (150, 90, 170), "Pick up every non-king piece and redeal them randomly."),
    "possession": ("Possession", (140, 30, 150), "Take full control of the opponent's next turn."),
    "hotpotato": ("Hot Potato", (200, 100, 20), "A random enemy piece becomes a bomb; it explodes in 2 turns."),
    "pandorashand": ("Pandora's Hand", (130, 100, 60), "Discard your hand, draw that many random cards, and play one for free."),
    "hydra": ("Hydra", (40, 130, 80), "Passive: when one of your pieces dies this turn, two pawns spawn where it fell."),
}
