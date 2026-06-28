# Building the Android APK

This packages the existing pygame game as-is via [Buildozer](https://github.com/kivy/buildozer)
+ python-for-android (p4a). No GUI rewrite needed - touch already maps to
mouse events in pygame, which is all this game's drag-and-drop needs (it
never uses multi-touch gestures).

## Prerequisites (Linux or WSL2 - Buildozer does not run on Windows directly)

```bash
sudo apt install -y python3-pip build-essential git python3-dev \
    libffi-dev libssl-dev unzip zip wget
pip install --upgrade pip
pip install "cython<3.0" "setuptools<71.0.0" buildozer
```

### Java: needs JDK 17, specifically

The current Android Gradle plugin (used by python-for-android's build step)
requires JDK 17 - JDK 11 fails the build. On **Ubuntu 20.04**, the default
repos only go up to `openjdk-11-jdk` (`openjdk-17-jdk` doesn't exist there),
and Adoptium's APT repo no longer lists `focal` either, so `apt install
openjdk-17-jdk` and the Adoptium-repo approach both fail here. The reliable
fix is Adoptium's binary API directly (no apt, no repo-version guessing):

```bash
cd /tmp
wget -O openjdk17.tar.gz "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse"
sudo mkdir -p /opt/jdk-17
sudo tar -xzf openjdk17.tar.gz -C /opt/jdk-17 --strip-components=1
echo 'export JAVA_HOME=/opt/jdk-17' >> ~/.bashrc
echo 'export PATH="$JAVA_HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
java -version   # should print 17.x
```

(On Ubuntu 22.04+, `sudo apt install -y openjdk-17-jdk` works fine and you
can skip this.)

The Cython/setuptools version pins matter - newer defaults are known to
break the python-for-android recipe build as of 2026. Android SDK/NDK are
downloaded automatically by Buildozer on first run (this takes a while).

### pygame needs a local recipe override, not just the stock one

`buildozer.spec` sets `p4a.local_recipes = android-recipes`, which points at
`android-recipes/pygame/` in this repo - a copy of p4a's bundled `pygame`
recipe (pinned tag `v2024.01.21`) with two changes, both load-bearing:

1. **Version bumped to 2.6.1** (matching `requirements.txt`) instead of the
   recipe's hardcoded 2.1.0. Without this, the build fails with
   `fatal error: 'longintrepr.h' file not found` while compiling pygame's
   `_sdl2` module - a stale, pre-Cythonized `_sdl2/sdl2.c` shipped inside
   the pygame 2.1.0 (2021) release itself, not a Python-version issue (it
   fails the same way even against an older, 3.11-default p4a release).
   Newer pygame releases regenerated that file with a current Cython and
   don't have the bug.

2. **`setup_extra_args = ['-enable-arm-neon']`** added. Without this, the
   build *succeeds* but the app crashes immediately on launch - on a real
   ARM phone, not just an emulator - with:
   ```
   ImportError: dlopen failed: cannot locate symbol
   "alphablit_alpha_sse2_argb_surf_alpha" referenced by ".../pygame/surface.so"
   ```
   pygame's SIMD blitter source guards those functions behind
   `#if (defined(__SSE2__) || defined(PG_ENABLE_ARM_NEON))`. Cross-compiling
   for ARM defines neither by default (correctly no `__SSE2__` on ARM;
   `PG_ENABLE_ARM_NEON` only gets defined if pygame's own `setup.py` sees an
   explicit `-enable-arm-neon` flag - it has no way to reliably detect the
   cross-compile target itself). So the functions are silently omitted, but
   `surface.c`'s blitter dispatch table still references them
   unconditionally - it links fine, and only blows up at `dlopen()` time.
   See the recipe file's docstring for the full explanation.

The `p4a.branch` pin to `v2024.01.21` (Python 3.11 default, NDK r25b) is
kept alongside this mainly because it's already a known-working
combination - not because it was the fix for either issue above.

## Build

```bash
cd Chess-cards
buildozer android debug
```

Output APK lands in `bin/chesscards-1.5-arm64-v8a_armeabi-v7a-debug.apk`.

To install + run on a connected device/emulator and stream logs:

```bash
buildozer android deploy run logcat
```

If you change `buildozer.spec` significantly (requirements, permissions),
run `buildozer android clean` first.

## What works out of the box

- PvP (hot-seat) and PvC (vs. the basic built-in AI) - fully offline.
- Online LAN mode - needs `INTERNET`/`ACCESS_NETWORK_STATE`/`ACCESS_WIFI_STATE`,
  already in `buildozer.spec`.
- Back gesture/button - mapped to the same handler as Esc everywhere
  (`pygame.K_AC_BACK`), so it exits screens the way Android users expect.
- Settings/save files now write to the app's actual private storage on
  Android (`persistence.py` checks `ANDROID_PRIVATE`, set by the p4a
  bootstrap) instead of the app's source directory.

## Known limitation: no Stockfish

`engine/stockfish_bin` is a desktop binary (gitignored, fetched per-machine -
see `requirements.txt`/`README.md`) and is never bundled into the APK; it's
also the wrong architecture and Android sandboxes subprocess execution
heavily regardless. `ensure_engine()` in `main.py` already falls back to the
basic built-in AI whenever no engine binary is found, so PvC mode still
works on Android - just without Stockfish's strength. Shipping a real
ARM-compiled Stockfish is possible but is a separate, nontrivial effort
(cross-compiling the engine + a sanctioned way to invoke a bundled native
binary from the app sandbox).

## Known limitation: layout is still desktop-shaped

This first pass only makes the app launch and be controllable on Android -
it does not redesign the UI for a phone screen. The board/tray layout is
tuned for a 16:9 desktop fullscreen; on a portrait phone it will look
cramped. Forcing `orientation = landscape` in `buildozer.spec` sidesteps the
worst of it for now. A proper phone layout is future work.
