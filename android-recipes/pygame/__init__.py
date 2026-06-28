# Local override of python-for-android's bundled "pygame" recipe.
#
# Identical to the upstream recipe (kivy/python-for-android, pinned tag
# v2024.01.21) except for two changes:
#
#   1. version bumped to 2.6.1 (matching requirements.txt / the desktop
#      build), instead of the recipe's hardcoded 2.1.0 - whose bundled,
#      pre-Cythonized _sdl2/sdl2.c has a stale "#include longintrepr.h"
#      that fails to compile against any host Python p4a can build now.
#
#   2. setup_extra_args = ['-enable-arm-neon'] added.
#
#      Without it, pygame crashes at *runtime* on real ARM devices/ARM
#      emulator images with:
#          ImportError: dlopen failed: cannot locate symbol
#          "alphablit_alpha_sse2_argb_surf_alpha" referenced by
#          ".../pygame/surface.so"
#
#      pygame's simd_blitters_sse2.c guards those blitter functions with
#      `#if (defined(__SSE2__) || defined(PG_ENABLE_ARM_NEON))`. On an ARM
#      cross-build neither macro is defined by default - the NDK clang
#      target doesn't define __SSE2__ (correctly, ARM has no SSE2), and
#      PG_ENABLE_ARM_NEON is only defined when pygame's own setup.py sees
#      the `-enable-arm-neon` CLI flag (pygame's setup.py decides this
#      itself; it does NOT detect the target architecture automatically -
#      cross-compiling from an x86_64 host gives it no reliable way to).
#      So the functions are silently skipped entirely, surface.c's blitter
#      dispatch table still references them unconditionally, and the
#      result links "successfully" but the symbol is missing at runtime.
#      `-enable-arm-neon` makes pygame's setup.py define PG_ENABLE_ARM_NEON
#      and add -mfpu=neon to CFLAGS, which is the documented, correct way
#      to build pygame for ARM.

from os.path import join

from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from pythonforandroid.toolchain import current_directory


class Pygame2Recipe(CompiledComponentsPythonRecipe):
    """
    Recipe to build apps based on SDL2-based pygame.

    .. warning:: Some pygame functionality is still untested, and some
        dependencies like freetype, postmidi and libjpeg are currently
        not part of the build. It's usable, but not complete.
    """

    version = '2.6.1'
    url = 'https://github.com/pygame/pygame/archive/{version}.tar.gz'

    site_packages_name = 'pygame'
    name = 'pygame'

    depends = ['sdl2', 'sdl2_image', 'sdl2_mixer', 'sdl2_ttf', 'setuptools', 'jpeg', 'png']
    call_hostpython_via_targetpython = False  # Due to setuptools
    install_in_hostpython = False

    # See the module docstring above - this is the actual fix.
    # Default empty; set per-arch in build_arch so x86_64 builds are unaffected.
    setup_extra_args = []

    def build_arch(self, arch):
        # -enable-arm-neon is required on ARM targets (see module docstring) but
        # must NOT be passed for x86_64 — it pulls in sse2neon.h which conflicts
        # with the real SSE2 headers on x86_64 and fails to compile.
        if arch.arch in ('arm64-v8a', 'armeabi-v7a'):
            self.setup_extra_args = ['-enable-arm-neon']
        else:
            self.setup_extra_args = []
        super().build_arch(arch)

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        with current_directory(self.get_build_dir(arch.arch)):
            setup_template = open(join("buildconfig", "Setup.Android.SDL2.in")).read()
            env = self.get_recipe_env(arch)
            env['ANDROID_ROOT'] = join(self.ctx.ndk.sysroot, 'usr')

            png = self.get_recipe('png', self.ctx)
            png_lib_dir = join(png.get_build_dir(arch.arch), '.libs')
            png_inc_dir = png.get_build_dir(arch)

            jpeg = self.get_recipe('jpeg', self.ctx)
            jpeg_inc_dir = jpeg_lib_dir = jpeg.get_build_dir(arch.arch)

            sdl_mixer_includes = ""
            sdl2_mixer_recipe = self.get_recipe('sdl2_mixer', self.ctx)
            for include_dir in sdl2_mixer_recipe.get_include_dirs(arch):
                sdl_mixer_includes += f"-I{include_dir} "

            sdl2_image_includes = ""
            sdl2_image_recipe = self.get_recipe('sdl2_image', self.ctx)
            for include_dir in sdl2_image_recipe.get_include_dirs(arch):
                sdl2_image_includes += f"-I{include_dir} "

            setup_file = setup_template.format(
                sdl_includes=(
                    " -I" + join(self.ctx.bootstrap.build_dir, 'jni', 'SDL', 'include') +
                    " -L" + join(self.ctx.bootstrap.build_dir, "libs", str(arch)) +
                    " -L" + png_lib_dir + " -L" + jpeg_lib_dir + " -L" + arch.ndk_lib_dir_versioned),
                sdl_ttf_includes="-I"+join(self.ctx.bootstrap.build_dir, 'jni', 'SDL2_ttf'),
                sdl_image_includes=sdl2_image_includes,
                sdl_mixer_includes=sdl_mixer_includes,
                jpeg_includes="-I"+jpeg_inc_dir,
                png_includes="-I"+png_inc_dir,
                freetype_includes=""
            )
            # simd_blitters_sse2.c and simd_blitters_avx2.c define the SIMD
            # blitter symbols that surface.c references (alphablit_alpha_*,
            # pg_has_avx2, etc.).  The upstream Setup.Android.SDL2.in template
            # omits them, so the symbols land as NOTYPE UND in surface.so and
            # dlopen fails at runtime.  Adding them here compiles the functions
            # directly into the surface extension:
            #   arm64 — simd_blitters.h auto-defines PG_ENABLE_ARM_NEON via
            #           __aarch64__, sse2neon.h maps SSE2→NEON intrinsics.
            #   x86_64 — -msse2 in CFLAGS defines __SSE2__, real SSE2 used.
            #   avx2 — pg_has_avx2()/stubs always compiled; AVX2 intrinsic
            #           paths only activate when __AVX2__ is also defined.
            setup_file = setup_file.replace(
                "surface src_c/surface.c src_c/alphablit.c src_c/surface_fill.c",
                "surface src_c/surface.c src_c/alphablit.c src_c/surface_fill.c"
                " src_c/simd_blitters_sse2.c src_c/simd_blitters_avx2.c"
            )
            open("Setup", "w").write(setup_file)

    def get_recipe_env(self, arch):
        env = super().get_recipe_env(arch)
        env['USE_SDL2'] = '1'
        env["PYGAME_CROSS_COMPILE"] = "TRUE"
        env["PYGAME_ANDROID"] = "TRUE"
        # On x86_64 the NDK clang doesn't auto-define __SSE2__ in cross-compile
        # mode, so the pygame SIMD blitter (simd_blitters_sse2.c) is compiled
        # out while surface.c's dispatch table still references it — same
        # missing-symbol crash as ARM without -enable-arm-neon.  Adding -msse2
        # makes clang define __SSE2__ and compiles the blitter in.
        if arch.arch == 'x86_64':
            env['CFLAGS'] = env.get('CFLAGS', '') + ' -msse2'
        return env


recipe = Pygame2Recipe()
