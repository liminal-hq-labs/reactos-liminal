# Tests for `rl pin`: the pin rewrite, the ref lookup, the pin files and the command, with the fetch, the builds and the patchers faked.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import json
import subprocess

import pytest

from reactos_liminal import patch_base
from reactos_liminal import pin as pin_module
from reactos_liminal.cli import build_parser, main
from reactos_liminal.pin import PinError, resolve_ref, set_pins
from reactos_liminal.recipe import load

OLD = "a" * 40
NEW = "b" * 40
SHA = "c" * 64
NEWSHA = "d" * 64

RECIPE = f"""# header
[recipe]
name = "test"

[inputs.reactos_iso]
name = "x.iso"
url = "file:///x.zip"
zip_sha256 = "{SHA}"
sha256 = "{SHA}"

# the pin
[inputs.afterglow]
repo = "x/y"
commit = "{OLD}"
tar_sha256 = "{SHA}"
msstyles_sha256 = "{SHA}"
apply_reg = "desktop/install/afterglow-original.reg"

[patchers]
list = ["afterglow.icons"]
"""


def test_set_pins_changes_only_the_named_lines_in_the_afterglow_table():
	text = RECIPE + '\n[other]\ncommit = "keep"\n'
	changed = set_pins(text, {"commit": NEW, "tar_sha256": NEWSHA})
	assert f'commit = "{NEW}"' in changed and f'tar_sha256 = "{NEWSHA}"' in changed
	assert 'commit = "keep"' in changed and f'sha256 = "{SHA}"' in changed  # the other table and the ISO pin are untouched
	assert changed.replace(NEW, OLD).replace(NEWSHA, SHA) == text


def test_set_pins_removes_a_key_given_none_and_refuses_a_missing_one():
	with_note = RECIPE.replace(f'commit = "{OLD}"\n', f'commit = "{OLD}"\npre_merge = "a branch"\n')
	assert "pre_merge" not in set_pins(with_note, {"pre_merge": None})
	assert set_pins(RECIPE, {"pre_merge": None}) == RECIPE
	with pytest.raises(PinError, match="no `wallpaper_sha256` line"):
		set_pins(RECIPE, {"wallpaper_sha256": SHA})
	with pytest.raises(PinError, match="not in the recipe"):
		set_pins("[recipe]\n", {"commit": NEW})


def test_a_commit_is_used_as_given_without_asking_github(monkeypatch):
	monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("no lookup expected"))
	assert resolve_ref("x/y", NEW) == NEW


def fake_ls_remote(monkeypatch, lines, code=0):
	def run(argv, **kwargs):
		assert argv[:2] == ["git", "ls-remote"]
		return subprocess.CompletedProcess(argv, code, stdout=lines, stderr="boom")

	monkeypatch.setattr(subprocess, "run", run)


def test_a_tag_resolves_to_the_commit_an_annotated_tag_points_at(monkeypatch):
	fake_ls_remote(monkeypatch, f"{OLD}\trefs/tags/v1\n{NEW}\trefs/tags/v1^{{}}\n")
	assert resolve_ref("x/y", "v1") == NEW


def test_a_branch_resolves_to_its_tip(monkeypatch):
	fake_ls_remote(monkeypatch, f"{NEW}\trefs/heads/feat/icons\n")
	assert resolve_ref("x/y", "feat/icons") == NEW


def test_an_unknown_ref_and_a_failed_lookup_are_errors(monkeypatch):
	fake_ls_remote(monkeypatch, "")
	with pytest.raises(PinError, match="no tag, branch or commit"):
		resolve_ref("x/y", "nope")
	fake_ls_remote(monkeypatch, "", code=128)
	with pytest.raises(PinError, match="cannot look up"):
		resolve_ref("x/y", "nope")


@pytest.fixture
def faked(tmp_path, monkeypatch):
	"""`pin_afterglow` with the network, the builds and the patchers faked: the recipe and the pin files are real files in tmp_path."""
	recipe_path = tmp_path / "recipe.toml"
	recipe_path.write_text(RECIPE)
	shell32_pins = tmp_path / "shell32-icons.json"
	shell32_pins.write_text(json.dumps({"stock_sha256": SHA, "results": {"old": "old"}}))
	family_pins = tmp_path / "icon-families.json"
	family_pins.write_text(json.dumps({"families": {"cpl-icons": {"old": {"f": "old"}}, "other": {"keep": {"f": "keep"}}}}))
	monkeypatch.setattr(pin_module, "SHELL32_PINS_FILE", shell32_pins)
	monkeypatch.setattr(pin_module, "FAMILY_PINS_FILE", family_pins)
	wallpaper_pins = tmp_path / "afterglow-wallpapers.json"
	wallpaper_pins.write_text(json.dumps({"commit": "0" * 40, "scenes": {"dusk-dark-smooth": "old"}}))
	monkeypatch.setattr(pin_module, "WALLPAPER_PINS_FILE", wallpaper_pins)
	monkeypatch.setattr(pin_module, "discover_scenes", lambda tree: ["dusk-dark-smooth", "dusk-light-smooth"])
	monkeypatch.setattr(
		pin_module, "render_set", lambda recipe, tree, scratch, names, measured: measured.update({name: NEWSHA for name in names})
	)
	golden = tmp_path / "golden.img"
	golden.write_bytes(b"x")
	tree = tmp_path / "tree"
	tree.mkdir()
	(tree / ".verified").write_text(NEWSHA + "\n")
	seen = {}

	def fetch(recipe, work, tarball, trust):
		seen["commit"] = recipe.section("inputs", "afterglow")["commit"]
		assert trust
		return tree

	def prepare(recipe, work, source_tree, measured):
		measured["msstyles_sha256"] = NEWSHA

	def patchers(names, disk, source_tree, files, scratch):
		recorder = patch_base.active_recorder()
		seen.setdefault("runs", []).append((list(names), recorder is not None))
		if recorder is not None:
			recorder.record("shell32", "digest", "ReactOS/system32/shell32.dll", "new-shell32")
			recorder.record("cpl-icons", "digest", "f", "new-cpl")
		return []

	monkeypatch.setattr(pin_module, "fetch_afterglow", fetch)
	monkeypatch.setattr(pin_module, "prepare_afterglow", prepare)
	monkeypatch.setattr(pin_module, "run_patchers", patchers)
	monkeypatch.setattr(pin_module, "FatImage", lambda path: path)
	return recipe_path, golden, seen, shell32_pins, family_pins, wallpaper_pins


def test_pin_moves_the_pin_measures_the_hashes_and_rewrites_the_pin_files(faked, tmp_path):
	recipe_path, golden, seen, shell32_pins, family_pins, wallpaper_pins = faked
	changes = pin_module.pin_afterglow(recipe_path, tmp_path / "work", ref=NEW, pre_merge="a branch", golden=golden)
	text = recipe_path.read_text()
	assert f'commit = "{NEW}"' in text and f'tar_sha256 = "{NEWSHA}"' in text and f'msstyles_sha256 = "{NEWSHA}"' in text
	assert 'pre_merge = "a branch"' in text
	assert load(recipe_path).section("inputs", "afterglow")["pre_merge"] == "a branch"
	assert seen["commit"] == NEW
	assert json.loads(shell32_pins.read_text())["results"] == {"digest": "new-shell32"}  # the old icon set's result is replaced
	families = json.loads(family_pins.read_text())["families"]
	assert families["cpl-icons"] == {"digest": {"f": "new-cpl"}} and families["other"] == {"keep": {"f": "keep"}}
	assert [line.split(":")[0] for line in changes] == [
		"commit",
		"tar_sha256",
		"msstyles_sha256",
		"pre_merge",
		"shell32-icons.json",
		"icon-families.json",
		"afterglow-wallpapers.json",
	]
	assert json.loads(wallpaper_pins.read_text()) == {"commit": NEW, "scenes": {"dusk-dark-smooth": NEWSHA, "dusk-light-smooth": NEWSHA}}
	# The icon patchers ran recording; then the recipe's own list ran once more, checking.
	assert seen["runs"] == [(list(pin_module.ICON_PATCHERS), True), (["afterglow.icons"], False)]


def test_pin_without_a_ref_keeps_the_commit_and_the_note(faked, tmp_path):
	recipe_path, golden, seen, *_ = faked
	pin_module.pin_afterglow(recipe_path, tmp_path / "work", golden=golden)
	assert seen["commit"] == OLD and f'commit = "{OLD}"' in recipe_path.read_text()


def test_a_later_bump_without_a_note_drops_it(faked, tmp_path):
	recipe_path, golden, *_ = faked
	pin_module.pin_afterglow(recipe_path, tmp_path / "work", ref=NEW, pre_merge="a branch", golden=golden)
	pin_module.pin_afterglow(recipe_path, tmp_path / "work", ref=OLD, golden=golden)
	assert "pre_merge" not in recipe_path.read_text()


def test_check_lists_what_is_stale_and_writes_nothing(faked, tmp_path):
	recipe_path, golden, _seen, shell32_pins, family_pins, wallpaper_pins = faked
	before = (recipe_path.read_text(), shell32_pins.read_text(), family_pins.read_text(), wallpaper_pins.read_text())
	changes = pin_module.pin_afterglow(recipe_path, tmp_path / "work", ref=NEW, golden=golden, check=True)
	assert any(line.startswith("commit:") for line in changes) and any(line.startswith("afterglow-wallpapers.json:") for line in changes)
	assert (recipe_path.read_text(), shell32_pins.read_text(), family_pins.read_text(), wallpaper_pins.read_text()) == before


def test_pin_needs_the_golden_disk(faked, tmp_path):
	recipe_path, *_ = faked
	with pytest.raises(PinError, match="rl install"):
		pin_module.pin_afterglow(recipe_path, tmp_path / "work", golden=tmp_path / "missing.img")


def test_the_pin_command_is_registered_and_pre_merge_needs_a_ref(capsys, tmp_path):
	args = build_parser().parse_args(["pin", "r.toml", "--afterglow", "v1", "--check"])
	assert args.afterglow == "v1" and args.check
	assert main(["pin", str(tmp_path / "r.toml"), "--pre-merge", "x"]) == 2
	assert "--pre-merge goes with --afterglow" in capsys.readouterr().err
