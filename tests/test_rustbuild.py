# Tests for programs built from source: the recipe's `[builds]` table, `built:` files, the pin check and the lock, with a fake build script.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib

import pytest

from reactos_liminal.recipe import RecipeError, load
from reactos_liminal.rustbuild import BuildError, build_program, build_programs, declaring_file, used_builds

BASE = """[recipe]
name = "base"

[inputs.reactos_iso]
name = "x.iso"
url = "file:///x.zip"
zip_sha256 = "{sum}"
sha256 = "{sum}"

[builds.afterfetch]
source = "tool"
sha256 = "{pin}"

[[files]]
source = "built:afterfetch"
destination = "ReactOS/system32/afterfetch.exe"
"""

OUTPUT = b"MZ fake program"
SCRIPT = '#!/usr/bin/env bash\nmkdir -p "$1"\nprintf "MZ fake program" > "$1/afterfetch.exe"\n'


def make_recipe(directory, pin=None):
	tool = directory / "tool"
	tool.mkdir()
	(tool / "build.sh").write_text(SCRIPT)
	pin = pin or hashlib.sha256(OUTPUT).hexdigest()
	path = directory / "base.toml"
	path.write_text(BASE.format(sum="a" * 64, pin=pin))
	return path


def test_a_build_is_run_and_checked_against_its_pin(tmp_path):
	recipe = load(make_recipe(tmp_path))
	assert used_builds(recipe) == ["afterfetch"]
	built = build_programs(recipe, tmp_path / "work")
	assert built["afterfetch"].read_bytes() == OUTPUT


def test_a_different_output_is_refused(tmp_path):
	recipe = load(make_recipe(tmp_path, pin="b" * 64))
	with pytest.raises(BuildError, match="expected " + "b" * 64):
		build_program(recipe, tmp_path / "work", "afterfetch")


def test_lock_measures_instead_of_checking(tmp_path):
	recipe = load(make_recipe(tmp_path, pin="b" * 64))
	measured = {}
	build_program(recipe, tmp_path / "work", "afterfetch", measured)
	assert measured == {"sha256": hashlib.sha256(OUTPUT).hexdigest()}


def test_a_failing_build_reports_its_output(tmp_path):
	recipe = load(make_recipe(tmp_path))
	(tmp_path / "tool" / "build.sh").write_text("#!/usr/bin/env bash\necho no linker >&2\nexit 3\n")
	with pytest.raises(BuildError, match="no linker"):
		build_program(recipe, tmp_path / "work", "afterfetch")


def test_a_consumer_recipe_finds_the_base_recipes_source(tmp_path):
	make_recipe(tmp_path)
	child_folder = tmp_path / "child"
	child_folder.mkdir()
	(child_folder / "child.toml").write_text('[recipe]\nname = "child"\nextends = "../base.toml"\n')
	recipe = load(child_folder / "child.toml")
	assert declaring_file(recipe, "afterfetch") == tmp_path / "base.toml"
	assert build_programs(recipe, tmp_path / "work")["afterfetch"].is_file()


def test_a_built_file_needs_a_declared_build(tmp_path):
	path = tmp_path / "r.toml"
	path.write_text(
		BASE.format(sum="a" * 64, pin="b" * 64).replace('[builds.afterfetch]\nsource = "tool"\nsha256 = "' + "b" * 64 + '"\n', "")
	)
	with pytest.raises(RecipeError, match="built:afterfetch"):
		load(path)


def test_the_base_recipe_builds_afterfetch_from_this_repository(base_recipe_path):
	recipe = load(base_recipe_path)
	assert recipe.section("builds", "afterfetch")["source"] == "../tools/afterfetch"
	destinations = {entry["destination"]: entry["source"] for entry in recipe.data["files"]}
	assert destinations["ReactOS/system32/afterfetch.exe"] == "built:afterfetch"
	assert destinations["ReactOS/system32/afterfetch.cmd"].endswith("afterfetch.cmd")
