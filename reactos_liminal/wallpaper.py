# The Afterglow wallpaper: render one scene from its SVG master with Afterglow's own script, check the BMP against the recipe's pin and
# name where it goes on the disk.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Afterglow draws every wallpaper as an SVG master (`assets/wallpapers/afterglow-<palette>-<mode>-<style>.svg`) and renders the 24-bit
# 1024 x 768 BMP ReactOS wants with `scripts/render-wallpapers.mjs`: the centre 4:3 crop of the canvas, scaled, with a light seeded
# dither on the smooth ones. The same masters give the same bytes, so the recipe pins the BMP's SHA-256. The recipe's
# `settings.wallpaper` is the path inside the guest; the BMP is written to that path, and the settings step selects it.
import re
import shutil
import subprocess
from pathlib import Path

from .fetch import sha256_file
from .log import log
from .recipe import Recipe

SCENE = re.compile(r"^[a-z]+-(dark|light)-(smooth|stepped)$")
RENDER_OUT = "dist/rl-wallpaper"  # under the Afterglow tree; the renderer takes a path relative to the tree
BMP_SIZE = (1024, 768)


class WallpaperError(Exception):
	"""The wallpaper could not be rendered, or does not match its pin."""


def wanted(recipe: Recipe) -> str | None:
	"""The scene the recipe asks for, such as "dusk-dark-smooth", or None."""
	return recipe.section("inputs").get("afterglow", {}).get("wallpaper")


def image_path(guest_path: str) -> str:
	"""Where a guest path such as C:\\ReactOS\\afterglow.bmp is on the FAT32 disk: ReactOS/afterglow.bmp."""
	match = re.fullmatch(r"[Cc]:\\(.+)", guest_path)
	if not match:
		raise WallpaperError(f"settings.wallpaper: expected a path on drive C:, such as C:\\ReactOS\\afterglow.bmp; got {guest_path!r}")
	return match.group(1).replace("\\", "/")


def render_wallpaper(recipe: Recipe, source_tree: Path, scratch: Path) -> Path:
	"""Render the recipe's scene to a BMP in `scratch` and check it against `inputs.afterglow.wallpaper_sha256`. Needs node,
	rsvg-convert and ImageMagick 7."""
	scene = wanted(recipe)
	if scene is None:
		raise WallpaperError("the recipe names no inputs.afterglow.wallpaper")
	pin = recipe.section("inputs", "afterglow")["wallpaper_sha256"]
	script = source_tree / "scripts" / "render-wallpapers.mjs"
	name = f"afterglow-{scene}"
	if not (source_tree / "assets" / "wallpapers" / f"{name}.svg").is_file():
		raise WallpaperError(f"the Afterglow source has no wallpaper {name}.svg")
	for tool in ("node", "rsvg-convert", "magick"):
		if shutil.which(tool) is None:
			raise WallpaperError(f"rendering the wallpaper needs {tool} on the PATH")
	shutil.rmtree(source_tree / RENDER_OUT, ignore_errors=True)
	done = subprocess.run(
		["node", str(script), "--out", RENDER_OUT, "--only", name], cwd=source_tree, capture_output=True, text=True, check=False
	)
	rendered = source_tree / RENDER_OUT / "bmp" / f"{name}-{BMP_SIZE[0]}x{BMP_SIZE[1]}.bmp"
	if done.returncode != 0 or not rendered.is_file():
		raise WallpaperError(f"render-wallpapers.mjs failed: {(done.stderr or done.stdout).strip()[-400:]}")
	actual = sha256_file(rendered)
	if actual != pin:
		raise WallpaperError(f"{rendered.name} is {actual}, expected {pin}; the renderer or its tools differ from the pin")
	destination = scratch / f"{name}.bmp"
	shutil.copyfile(rendered, destination)
	shutil.rmtree(source_tree / RENDER_OUT, ignore_errors=True)
	log("wallpaper", f"{name} rendered from its SVG master ({actual})")
	return destination
