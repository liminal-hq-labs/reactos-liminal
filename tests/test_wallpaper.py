# Tests for the wallpaper step: the recipe keys, the path on the disk and the render check, with a fake Afterglow renderer.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import json
import shutil

import pytest

from reactos_liminal import wallpaper
from reactos_liminal.image import _replace_stock_wallpapers, _write_wallpaper, _write_wallpaper_set
from reactos_liminal.licences import ChangeRecord
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
	path.write_text(text.replace("C:\\\\ReactOS\\\\Web\\\\Wallpaper\\\\Afterglow Dusk (dark, smooth).bmp", "/ReactOS/x.bmp"))
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
	recipe.data["settings"]["wallpaper"] = "C:\\ReactOS\\afterglow-wallpaper.bmp"
	recipe.data["wallpapers"] = {"scenes": [], "replace_stock": False}
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


def test_a_recipe_supplies_its_own_wallpaper_from_a_file_entry(base_recipe_path, tmp_path):
	"""A downstream recipe puts its own BMP at `settings.wallpaper` with [[files]]; the plan says the scene is not rendered."""
	from reactos_liminal.image import _wallpaper_file_entry, plan_image

	(tmp_path / "emblem.bmp").write_bytes(b"BM-emblem")
	child = tmp_path / "child.toml"
	child.write_text(
		'[recipe]\nname = "child"\nextends = "rl:recipes/afterglow.toml"\n\n'
		'[[files]]\nsource = "emblem.bmp"\ndestination = "ReactOS/Web/Wallpaper/Afterglow Dusk (dark, smooth).bmp"\n'
	)
	recipe = load(child)
	entry = _wallpaper_file_entry(recipe)
	assert entry is not None and entry["source"] == str(tmp_path / "emblem.bmp")
	assert wallpaper.wanted(recipe) == "dusk-dark-smooth"  # the pin is inherited, and still measured by `rl lock`
	plan = plan_image(recipe, tmp_path / "work", golden=tmp_path / "golden.img", out=tmp_path / "out.img")
	text = "\n".join(plan.steps)
	assert "comes from [[files]]" in text and "rendered from its SVG master" not in text
	assert _wallpaper_file_entry(load(base_recipe_path)) is None


# The set of wallpapers in the folder Display Properties lists

SCENES = [f"{palette}-{mode}-{style}" for palette in ("aurora", "dusk") for mode in ("dark", "light") for style in ("smooth", "stepped")]


def fake_set_tree(tmp_path, names):
	"""An Afterglow tree whose renderer writes, for the scene named by `--only`, a bitmap of that scene's name."""
	tree = tmp_path / "set-tree"
	(tree / "scripts").mkdir(parents=True)
	(tree / "assets" / "wallpapers").mkdir(parents=True)
	for name in names:
		(tree / "assets" / "wallpapers" / f"afterglow-{name}.svg").write_text("<svg/>")
	(tree / "scripts" / "render-wallpapers.mjs").write_text(
		"import { mkdirSync, writeFileSync } from 'node:fs';\n"
		"const argument = (flag) => process.argv[process.argv.indexOf(flag) + 1];\n"
		"mkdirSync(`${argument('--out')}/bmp`, { recursive: true });\n"
		"writeFileSync(`${argument('--out')}/bmp/${argument('--only')}-1024x768.bmp`, `BM-${argument('--only')}`);\n"
	)
	return tree


def bitmap_of(scene):
	return f"BM-afterglow-{scene}".encode()


@pytest.fixture
def pinned_set(base_recipe_path, monkeypatch, tmp_path):
	"""The base recipe with a pins file for two palettes, whose BMPs the fake renderer writes."""
	recipe = load(base_recipe_path)
	pins = tmp_path / "afterglow-wallpapers.json"
	pins.write_text(
		json.dumps(
			{
				"commit": recipe.section("inputs", "afterglow")["commit"],
				"scenes": {scene: hashlib.sha256(bitmap_of(scene)).hexdigest() for scene in SCENES},
			}
		)
	)
	monkeypatch.setattr(wallpaper, "PINS_FILE", pins)
	monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)
	return recipe, pins


def test_a_scene_is_named_for_people_and_written_beside_the_picker_s_folder():
	assert wallpaper.friendly_name("dusk-dark-smooth") == "Afterglow Dusk (dark, smooth)"
	assert wallpaper.friendly_name("graphite-light-stepped") == "Afterglow Graphite (light, stepped)"
	assert wallpaper.set_destination("dusk-dark-smooth") == "ReactOS/Web/Wallpaper/Afterglow Dusk (dark, smooth).bmp"


def test_the_base_recipe_offers_every_pinned_afterglow_scene_by_name_order(base_recipe_path):
	recipe = load(base_recipe_path)
	names = wallpaper.scenes(recipe)
	assert len(names) == 20 and set(names) == set(json.loads(wallpaper.PINS_FILE.read_text())["scenes"])
	assert [wallpaper.friendly_name(name) for name in names] == sorted(wallpaper.friendly_name(name) for name in names)
	assert names[0] == "aurora-dark-smooth" and "dusk-light-stepped" in names
	assert wallpaper.wanted(recipe) in names  # the desktop wallpaper is one of the set


def test_the_default_wallpaper_is_the_set_s_own_dusk_file(base_recipe_path):
	recipe = load(base_recipe_path)
	assert wallpaper.image_path(recipe.section("settings", "wallpaper")) == wallpaper.set_destination(wallpaper.wanted(recipe))
	assert recipe.section("wallpapers", "replace_stock") is True


def test_the_pins_file_is_for_the_pinned_commit_and_agrees_with_the_recipe(base_recipe_path):
	recipe = load(base_recipe_path)
	pins = json.loads(wallpaper.PINS_FILE.read_text())
	assert pins["commit"] == recipe.section("inputs", "afterglow")["commit"]
	assert pins["scenes"][wallpaper.wanted(recipe)] == recipe.section("inputs", "afterglow")["wallpaper_sha256"]
	assert all(len(digest) == 64 for digest in pins["scenes"].values())


def test_the_compact_recipe_turns_the_set_and_the_replacement_off_and_keeps_its_own_file(compact_recipe_path):
	recipe = load(compact_recipe_path)
	assert recipe.section("wallpapers") == {"scenes": [], "replace_stock": False}
	assert wallpaper.scenes(recipe) == []
	assert recipe.section("settings", "wallpaper") == "C:\\ReactOS\\afterglow-wallpaper.bmp"
	assert wallpaper.wanted(recipe) == "dusk-dark-smooth"  # its one wallpaper is still the pinned scene
	assert recipe.section("trim", "profile") == "base"


def test_a_child_changes_the_set_by_setting_the_key_again(tmp_path):
	"""Tables merge key by key and a list or string replaces the inherited value, so a child narrows the set or empties it."""
	one = tmp_path / "one.toml"
	one.write_text('[recipe]\nname = "one"\nextends = "rl:recipes/afterglow.toml"\n\n[wallpapers]\nscenes = ["dusk-light-smooth"]\n')
	recipe = load(one)
	assert wallpaper.scenes(recipe) == ["dusk-light-smooth"] and recipe.section("wallpapers", "replace_stock") is True
	none = tmp_path / "none.toml"
	none.write_text('[recipe]\nname = "none"\nextends = "rl:recipes/afterglow.toml"\n\n[wallpapers]\nscenes = []\nreplace_stock = false\n')
	assert wallpaper.scenes(load(none)) == [] and load(none).section("wallpapers", "replace_stock") is False


@pytest.mark.parametrize(
	"line, message",
	[
		('scenes = "some"', "all"),
		('scenes = ["dusk"]', "wallpaper"),
		('scenes = ["dusk-dark-smooth", "dusk-dark-smooth"]', "duplicate"),
		("scenes = [1]", "list"),
		('replace_stock = "yes"', "true or false"),
		("extra = 1", "unknown key"),
	],
)
def test_the_wallpapers_table_is_validated(tmp_path, line, message):
	path = tmp_path / "bad.toml"
	path.write_text(f'[recipe]\nname = "bad"\nextends = "rl:recipes/afterglow.toml"\n\n[wallpapers]\n{line}\n')
	with pytest.raises(RecipeError, match=message):
		load(path)


def test_scenes_need_an_afterglow_source(fake_iso_recipe, tmp_path):
	recipe, _, _ = fake_iso_recipe
	text = recipe.chain[0].read_text() + '\n[wallpapers]\nscenes = ["dusk-dark-smooth"]\n'
	path = tmp_path / "no-afterglow.toml"
	path.write_text(text)
	with pytest.raises(RecipeError, match="needs an"):
		load(path)


def test_the_stock_list_is_the_wallpaper_folder_s_files_the_compact_trim_also_removes():
	stock = wallpaper.stock_list()
	paths = {entry.path for entry in stock.entries}
	assert paths and all(entry.kind == "f" and entry.path.startswith(wallpaper.FOLDER + "/") for entry in stock.entries)
	trim_lines = {
		line[2:] for line in (wallpaper.PROFILES_DIR / "base.txt").read_text().splitlines() if line.startswith("f " + wallpaper.FOLDER)
	}
	assert paths == trim_lines
	assert "ReactOS/Web/Wallpaper/Nebula.bmp" in paths and "ReactOS/Web/Wallpaper/README.txt" in paths


@needs_node
def test_a_set_is_rendered_and_checked_against_the_pins_file(pinned_set, tmp_path):
	recipe, _ = pinned_set
	recipe.data["wallpapers"]["scenes"] = "all"
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	files = wallpaper.render_set(recipe, fake_set_tree(tmp_path, SCENES), scratch)
	assert sorted(files) == sorted(SCENES)
	assert files["dusk-light-smooth"].read_bytes() == bitmap_of("dusk-light-smooth")


@needs_node
def test_a_set_scene_that_differs_from_its_pin_is_refused(pinned_set, tmp_path):
	recipe, pins = pinned_set
	document = json.loads(pins.read_text())
	document["scenes"]["dusk-dark-smooth"] = "0" * 64
	pins.write_text(json.dumps(document))
	recipe.data["wallpapers"]["scenes"] = ["dusk-dark-smooth"]
	with pytest.raises(WallpaperError, match="expected"):
		wallpaper.render_set(recipe, fake_set_tree(tmp_path, SCENES), tmp_path)


def test_pins_for_another_afterglow_commit_are_refused(pinned_set, tmp_path):
	recipe, pins = pinned_set
	document = json.loads(pins.read_text())
	document["commit"] = "0" * 40
	pins.write_text(json.dumps(document))
	with pytest.raises(WallpaperError, match="run `rl pin`"):
		wallpaper.render_set(recipe, fake_set_tree(tmp_path, SCENES), tmp_path, ["dusk-dark-smooth"])


def test_a_scene_with_no_pin_is_refused(pinned_set, tmp_path):
	recipe, _ = pinned_set
	with pytest.raises(WallpaperError, match="no sum for"):
		wallpaper.render_set(recipe, fake_set_tree(tmp_path, SCENES), tmp_path, ["ember-dark-smooth"])


@needs_node
def test_rl_pin_measures_every_scene_the_source_draws(pinned_set, tmp_path):
	recipe, _ = pinned_set
	tree = fake_set_tree(tmp_path, SCENES)
	(tree / "assets" / "wallpapers" / "afterglow-notes.svg").write_text("<svg/>")  # not a scene name
	assert wallpaper.discover_scenes(tree) == SCENES
	measured = {}
	wallpaper.render_set(recipe, tree, tmp_path, wallpaper.discover_scenes(tree), measured)
	assert measured == {scene: hashlib.sha256(bitmap_of(scene)).hexdigest() for scene in SCENES}


@needs_node
def test_the_image_step_writes_the_set_in_name_order_and_skips_the_desktop_wallpaper_and_file_entries(pinned_set, tmp_path, fat):
	recipe, _ = pinned_set
	recipe.data["wallpapers"]["scenes"] = ["dusk-dark-smooth", "dusk-light-smooth", "aurora-dark-smooth"]
	recipe.data["settings"]["wallpaper"] = "C:\\ReactOS\\Web\\Wallpaper\\Afterglow Dusk (dark, smooth).bmp"
	recipe.data["files"] = [{"source": "x.bmp", "destination": "ReactOS/Web/Wallpaper/Afterglow Aurora (dark, smooth).bmp"}]
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	fat.make_directory("ReactOS")
	_write_wallpaper_set(recipe, fat, fake_set_tree(tmp_path, SCENES), scratch)
	folder = "ReactOS/Web/Wallpaper"
	assert fat.read(f"{folder}/Afterglow Dusk (light, smooth).bmp") == bitmap_of("dusk-light-smooth")
	assert not fat.exists(f"{folder}/Afterglow Dusk (dark, smooth).bmp")  # written with the desktop wallpaper, not here
	assert not fat.exists(f"{folder}/Afterglow Aurora (dark, smooth).bmp")  # a [[files]] entry supplies it


def test_a_recipe_without_a_set_writes_no_folder(pinned_set, tmp_path, fat):
	recipe, _ = pinned_set
	recipe.data["wallpapers"]["scenes"] = []
	_write_wallpaper_set(recipe, fat, tmp_path, tmp_path)
	assert not fat.exists("ReactOS/Web")


def test_the_stock_wallpapers_are_removed_only_when_the_recipe_replaces_them(base_recipe_path, fat):
	recipe = load(base_recipe_path)
	fat.make_directory("ReactOS")
	fat.make_directory("ReactOS/Web")
	fat.make_directory("ReactOS/Web/Wallpaper")
	for entry in wallpaper.stock_list().entries[:3]:
		fat.copy_in(base_recipe_path, entry.path)
	fat.copy_in(base_recipe_path, "ReactOS/Web/Wallpaper/Someone Elses.png")
	keep = ChangeRecord()
	recipe.data["wallpapers"]["replace_stock"] = False
	_replace_stock_wallpapers(recipe, fat, [], keep)
	assert keep.stock_wallpapers_removed == [] and fat.exists(wallpaper.stock_list().entries[0].path)
	recipe.data["wallpapers"]["replace_stock"] = True
	record = ChangeRecord()
	_replace_stock_wallpapers(recipe, fat, [], record)  # the ten files that are not on this disk are skipped
	assert len(record.stock_wallpapers_removed) == 3
	assert not fat.exists(wallpaper.stock_list().entries[0].path) and fat.exists("ReactOS/Web/Wallpaper/Someone Elses.png")


def test_the_stock_removal_never_removes_a_patched_file(base_recipe_path, fat):
	recipe = load(base_recipe_path)
	with pytest.raises(Exception, match="a patched file"):
		_replace_stock_wallpapers(recipe, fat, ["ReactOS/Web/Wallpaper/Nebula.bmp"], ChangeRecord())


def test_the_plan_names_the_set_and_the_stock_removal(base_recipe_path, compact_recipe_path, tmp_path):
	from reactos_liminal.image import plan_image

	full = "\n".join(plan_image(load(base_recipe_path), tmp_path / "work", golden=tmp_path / "g.img", out=tmp_path / "o.img").steps)
	assert "20 Afterglow wallpapers rendered into the wallpaper folder" in full and "13 stock wallpaper files removed first" in full
	compact = "\n".join(plan_image(load(compact_recipe_path), tmp_path / "work", golden=tmp_path / "g.img", out=tmp_path / "o.img").steps)
	assert "Afterglow wallpapers rendered" not in compact and "stock wallpaper files" not in compact
