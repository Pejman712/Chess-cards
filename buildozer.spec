[app]

title = Chess Power-Up Cards
package.name = chesscards
package.domain = org.chesscards

source.dir = .
source.main = main.py
source.include_exts = py,png,gif,ttf,mp3,ogg,txt,json
source.exclude_dirs = godot,.venv,__pycache__,.git,tests

version = 1.5

icon.filename = %(source.dir)s/icon.png

# Cards/pieces/board/fonts/music - everything main.py loads at runtime.
# python-for-android bundles whatever matches source.include_exts under
# source.dir, so assets/ and cards/ are picked up automatically.
#
# pygame uses our local recipe override (android-recipes/pygame, see
# p4a.local_recipes below) instead of p4a's bundled one: that local recipe
# builds pygame 2.6.1 instead of the bundled recipe's hardcoded 2.1.0
# (2.1.0's pre-Cythonized _sdl2/sdl2.c references CPython's old
# longintrepr.h and fails to compile against any host Python p4a can build
# now), and passes pygame's "-enable-arm-neon" setup.py flag, without which
# pygame links "successfully" but crashes at runtime on real ARM devices/
# the ARM emulator with a missing-symbol dlopen error (see the recipe's
# docstring for the full explanation). cython here installs it into p4a's
# isolated build-time hostpython, not into the APK - it's not a runtime
# dependency of the app itself.
requirements = python3,pygame,cython,chess
p4a.local_recipes = android-recipes

orientation = all
fullscreen = 1

# INTERNET/ACCESS_*: needed for the LAN "online" mode (netplay.py).
# Everything else (PvP, PvC) is fully offline.
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE

android.api = 33
android.minapi = 21
android.archs = arm64-v8a

# Pin python-for-android to its last release that defaults hostpython3/
# python3 to Python 3.11 (v2026.05.09 jumped straight to 3.14, with no
# release in between). The pygame recipe is still pinned to pygame 2.1.0
# (2021), whose C sources reference CPython's old longintrepr.h - removed
# in 3.12+ - so building against 3.14 fails with a fatal compile error.
# 3.11 is the last host Python pygame 2.1.0 can actually compile against.
p4a.branch = v2024.01.21

# Stockfish (engine/stockfish_bin) is a desktop x86 binary and is gitignored -
# it never ships in the APK. ensure_engine() in main.py already falls back
# to the built-in basic AI when no engine binary is found, so PvC still
# works, just without Stockfish's strength.

[buildozer]
log_level = 2
warn_on_root = 1
