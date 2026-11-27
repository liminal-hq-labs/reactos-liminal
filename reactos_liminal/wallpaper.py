# The Afterglow wallpapers: render a scene from its SVG master with Afterglow's own script, check the BMP against its pin and name where
# it goes on the disk. One scene is the desktop wallpaper (`inputs.afterglow.wallpaper`); the recipe's `[wallpapers]` table can also put
# a set of scenes in the folder Display Properties lists, and replace ReactOS's own wallpapers there.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Afterglow draws every wallpaper as an SVG master (`assets/wallpapers/afterglow-<palette>-<mode>-<style>.svg`) and renders the 24-bit
# 1024 x 768 BMP ReactOS wants with `scripts/render-wallpapers.mjs`: the centre 4:3 crop of the canvas, scaled, with a light seeded
# dither on the smooth ones. The same masters give the same bytes, so the pins hold the BMPs' SHA-256: the desktop wallpaper's in the
# recipe, the set's in `pins/afterglow-wallpapers.json`. The recipe's `settings.wallpaper` is the path inside the guest; the BMP is
# written to that path, and the settings step selects it.
#
# Display Properties lists the files of the Windows folder and of `WallPaperDir` (`%SystemRoot%\Web\Wallpaper`) that GDI+ can open, and
# a wallpaper's name in the list is its file name without the extension, so the set's files are named for people: "Afterglow Dusk
# (dark, smooth).bmp". The list is in directory order, and the set is written in name order into a folder with no other image in it.
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .fetch import sha256_file
from .log import log
from .paths import REPO
from .recipe import Recipe
from .trim import PROFILES_DIR, Profile, parse_profile

SCENE = re.compile(r"^[a-z]+-(dark|light)-(smooth|stepped)$")
RENDER_OUT = "dist/rl-wallpaper"  # under the Afterglow tree; the renderer takes a path relative to the tree
BMP_SIZE = (1024, 768)
FOLDER = "ReactOS/Web/Wallpaper"  # `WallPaperDir`: the folder Display Properties lists from
PINS_FILE = REPO / "pins" / "afterglow-wallpapers.json"
STOCK_LIST = PROFILES_DIR / "wallpapers" / "stock.txt"
RENDER_WORKERS = 4


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


def _render_scene(scene: str, source_tree: Path, scratch: Path) -> tuple[Path, str]:
	"""Render one scene with Afterglow's script to a BMP in `scratch`; returns the file and its SHA-256. Needs node, rsvg-convert and
	ImageMagick 7. Each scene renders into its own folder under the tree, so scenes can render side by side."""
	script = source_tree / "scripts" / "render-wallpapers.mjs"
	name = f"afterglow-{scene}"
	if not (source_tree / "assets" / "wallpapers" / f"{name}.svg").is_file():
		raise WallpaperError(f"the Afterglow source has no wallpaper {name}.svg")
	for tool in ("node", "rsvg-convert", "magick"):
		if shutil.which(tool) is None:
			raise WallpaperError(f"rendering the wallpaper needs {tool} on the PATH")
	out_dir = f"{RENDER_OUT}-{scene}"
	shutil.rmtree(source_tree / out_dir, ignore_errors=True)
	done = subprocess.run(
		["node", str(script), "--out", out_dir, "--only", name], cwd=source_tree, capture_output=True, text=True, check=False
	)
	rendered = source_tree / out_dir / "bmp" / f"{name}-{BMP_SIZE[0]}x{BMP_SIZE[1]}.bmp"
	if done.returncode != 0 or not rendered.is_file():
		raise WallpaperError(f"render-wallpapers.mjs failed: {(done.stderr or done.stdout).strip()[-400:]}")
	actual = sha256_file(rendered)
	destination = scratch / f"{name}.bmp"
	shutil.copyfile(rendered, destination)
	shutil.rmtree(source_tree / out_dir, ignore_errors=True)
	return destination, actual


def render_wallpaper(recipe: Recipe, source_tree: Path, scratch: Path, measured: dict[str, str] | None = None) -> Path:
	"""Render the recipe's scene to a BMP in `scratch` and check it against `inputs.afterglow.wallpaper_sha256`. With `measured` (for
	`rl pin`), the sum is stored there as `wallpaper_sha256` instead of being checked."""
	scene = wanted(recipe)
	if scene is None:
		raise WallpaperError("the recipe names no inputs.afterglow.wallpaper")
	pin = recipe.section("inputs", "afterglow").get("wallpaper_sha256")
	destination, actual = _render_scene(scene, source_tree, scratch)
	if measured is not None:
		measured["wallpaper_sha256"] = actual
	elif actual != pin:
		destination.unlink()
		raise WallpaperError(f"{destination.name} is {actual}, expected {pin}; the renderer or its tools differ from the pin")
	log("wallpaper", f"afterglow-{scene} rendered from its SVG master ({actual})")
	return destination


# The set: every scene in the folder Display Properties lists


def load_pins() -> dict:
	"""`pins/afterglow-wallpapers.json`: the Afterglow commit the sums are for and each scene's BMP sum."""
	try:
		return json.loads(PINS_FILE.read_text())
	except FileNotFoundError:
		raise WallpaperError(f"{PINS_FILE} is missing; `rl pin` writes it") from None


def scenes(recipe: Recipe) -> list[str]:
	"""The scenes the recipe's `[wallpapers]` table puts in the picker's folder, in name order: every pinned scene for "all", or the
	list. Empty when the recipe sets none."""
	chosen = recipe.section("wallpapers", "scenes")
	if chosen == "all":
		return sorted(load_pins()["scenes"], key=friendly_name)
	return sorted(chosen, key=friendly_name)


def friendly_name(scene: str) -> str:
	"""The name a person sees in Display Properties: "Afterglow Dusk (dark, smooth)" for `dusk-dark-smooth`."""
	palette, mode, style = scene.split("-")
	return f"Afterglow {palette.capitalize()} ({mode}, {style})"


def set_destination(scene: str) -> str:
	"""Where a scene of the set is on the FAT32 disk."""
	return f"{FOLDER}/{friendly_name(scene)}.bmp"


def stock_list() -> Profile:
	"""The files ReactOS ships in the wallpaper folder, which `wallpapers.replace_stock` removes, as trim entries."""
	try:
		return parse_profile("wallpapers/stock", STOCK_LIST.read_text(encoding="utf-8"))
	except FileNotFoundError:
		raise WallpaperError(f"{STOCK_LIST} is missing") from None


def render_set(
	recipe: Recipe, source_tree: Path, scratch: Path, names: list[str] | None = None, measured: dict[str, str] | None = None
) -> dict[str, Path]:
	"""Render the scenes (the recipe's, or `names`) into `scratch` and check each BMP against `pins/afterglow-wallpapers.json`; with
	`measured` (for `rl pin`), the sums are stored there by scene instead. Returns each scene's file."""
	names = scenes(recipe) if names is None else names
	if not names:
		return {}
	pins = None
	if measured is None:
		pins = load_pins()
		commit = recipe.section("inputs", "afterglow")["commit"]
		if pins["commit"] != commit:
			raise WallpaperError(f"{PINS_FILE.name} is for Afterglow {pins['commit']}, the recipe pins {commit}; run `rl pin`")
		missing = [name for name in names if name not in pins["scenes"]]
		if missing:
			raise WallpaperError(f"{PINS_FILE.name} has no sum for {', '.join(missing)}")
	with ThreadPoolExecutor(max_workers=RENDER_WORKERS) as pool:
		rendered = list(pool.map(lambda name: _render_scene(name, source_tree, scratch), names))
	files: dict[str, Path] = {}
	for name, (file, actual) in zip(names, rendered, strict=True):
		if measured is not None:
			measured[name] = actual
		elif actual != pins["scenes"][name]:
			raise WallpaperError(f"{file.name} is {actual}, expected {pins['scenes'][name]}; the renderer or its tools differ from the pin")
		files[name] = file
	log("wallpaper", f"{len(files)} scenes rendered from their SVG masters")
	return files


def discover_scenes(source_tree: Path) -> list[str]:
	"""Every scene the Afterglow source draws, from the SVG masters in `assets/wallpapers/`."""
	folder = source_tree / "assets" / "wallpapers"
	found = [path.stem.removeprefix("afterglow-") for path in sorted(folder.glob("afterglow-*.svg"))]
	return [scene for scene in found if SCENE.match(scene)]
