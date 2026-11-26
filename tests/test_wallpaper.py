# Tests for the wallpaper step: the recipe keys, the path on the disk and the render check, with a fake Afterglow renderer.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import shutil

import pytest

from reactos_liminal import wallpaper
from reactos_liminal.image import _write_wallpaper
from reactos_liminal.recipe import RecipeError, load
from reactos_liminal.wallpaper import WallpaperError, image_path, render_wallpaper

BITMAP = b"BM-not-a-real-bitmap"


def test_the_guest_path_becomes_the_path_on_the_disk():
	assert image_path("C:\\ReactOS\\afterglow-wallpaper.bmp") == "ReactOS/afterglow-wallpaper.bmp"
	with pytest.raises(WallpaperError, match="drive C"):
		image_path("D:\\x.bmp")


def test_the_base_recipe_names_the_dusk_wallpaper(base_recipe_path):
	recipe = load(base_recipe_path)
	assert wallpaper.wanted(recipe) == "dusk-dark-smooth"
	assert recipe.section("settings", "wallpaper_style") == "stretch"


@pytest.mark.parametrize("scene", ["dusk", "Dusk-dark-smooth", "dusk-dim-smooth", "dusk-dark-smooth.svg"])
def test_a_scene_name_must_be_palette_mode_style(base_recipe_path, tmp_path, scene):
	path = tmp_path / "r.toml"
	path.write_text(base_recipe_path.read_text().replace('wallpaper = "dusk-dark-smooth"', f'wallpaper = "{scene}"'))
	with pytest.raises(RecipeError, match="wallpaper"):
		load(path)


def test_a_scene_needs_its_sum_and_a_guest_path(base_recipe_path, tmp_path):
	text = base_recipe_path.read_text()
	path = tmp_path / "no-sum.toml"
	path.write_text("\n".join(line for line in text.splitlines() if not line.startswith("wallpaper_sha256")))
	with pytest.raises(RecipeError, match="go together"):
		load(path)
	path = tmp_path / "no-path.toml"
	path.write_text("\n".join(line for line in text.splitlines() if not line.startswith('wallpaper = "C:')))
	with pytest.raises(RecipeError, match="settings.wallpaper"):
		load(path)
	path = tmp_path / "bad-path.toml"
	path.write_text(text.replace("C:\\\\ReactOS\\\\afterglow-wallpaper.bmp", "/ReactOS/x.bmp"))
	with pytest.raises(RecipeError, match="drive C"):
		load(path)


def fake_tree(tmp_path, bitmap=BITMAP):
	"""An Afterglow tree whose renderer is a node script that writes `bitmap` where the real one would."""
	tree = tmp_path / "tree"
	(tree / "scripts").mkdir(parents=True)
	(tree / "assets" / "wallpapers").mkdir(parents=True)
	(tree / "assets" / "wallpapers" / "afterglow-dusk-dark-smooth.svg").write_text("<svg/>")
	(tree / "scripts" / "render-wallpapers.mjs").write_text(
		"import { mkdirSync, writeFileSync } from 'node:fs';\n"
		"const out = process.argv[process.argv.indexOf('--out') + 1];\n"
		"mkdirSync(`${out}/bmp`, { recursive: true });\n"
		f"writeFileSync(`${{out}}/bmp/afterglow-dusk-dark-smooth-1024x768.bmp`, Buffer.from({list(bitmap)!r}));\n"
	)
	return tree


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@pytest.fixture
def pinned(base_recipe_path, monkeypatch):
	recipe = load(base_recipe_path)
	recipe.data["inputs"]["afterglow"]["wallpaper_sha256"] = hashlib.sha256(BITMAP).hexdigest()
	# the renderer's own tools are not needed by the fake one
	monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)
	return recipe


@needs_node
def test_a_render_that_matches_its_pin_is_returned(pinned, tmp_path):
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	bitmap = render_wallpaper(pinned, fake_tree(tmp_path), scratch)
	assert bitmap.name == "afterglow-dusk-dark-smooth.bmp" and bitmap.read_bytes() == BITMAP
	assert not (tmp_path / "tree" / wallpaper.RENDER_OUT).exists()


@needs_node
def test_a_render_that_differs_from_its_pin_is_refused(pinned, tmp_path):
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	with pytest.raises(WallpaperError, match="expected"):
		render_wallpaper(pinned, fake_tree(tmp_path, b"BM-another"), scratch)
	assert not list(scratch.iterdir())


def test_a_scene_the_source_does_not_have_is_refused(pinned, tmp_path):
	tree = fake_tree(tmp_path)
	(tree / "assets" / "wallpapers" / "afterglow-dusk-dark-smooth.svg").unlink()
	with pytest.raises(WallpaperError, match="no wallpaper"):
		render_wallpaper(pinned, tree, tmp_path)


@needs_node
def test_the_image_step_writes_the_bitmap_unless_a_file_entry_does(pinned, tmp_path, fat):
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	fat.make_directory("ReactOS")
	_write_wallpaper(pinned, fat, fake_tree(tmp_path), scratch)
	assert fat.read("ReactOS/afterglow-wallpaper.bmp") == BITMAP
	# a [[files]] entry for the same path wins, and the scene is not rendered (a render of other bytes would fail the pin)
	pinned.data["files"] = [{"source": "x.bmp", "destination": "ReactOS/Afterglow-Wallpaper.bmp"}]
	other = tmp_path / "other"
	other.mkdir()
	fat.delete_file("ReactOS/afterglow-wallpaper.bmp")
	_write_wallpaper(pinned, fat, fake_tree(other, b"BM-unused"), scratch)
	assert not fat.exists("ReactOS/afterglow-wallpaper.bmp")
