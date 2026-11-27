# Tests for the recipe loader and validator.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import pytest

from reactos_liminal.recipe import DEFAULT_CHUNK_SIZE, RecipeError, load, parse_size

MINIMAL = """
[recipe]
name = "child"
extends = "base.toml"
"""


def write(directory, name, text):
	path = directory / name
	path.write_text(text)
	return path


def test_base_recipe_loads_with_pinned_inputs(base_recipe_path):
	recipe = load(base_recipe_path)
	assert recipe.name == "afterglow"
	iso = recipe.section("inputs", "reactos_iso")
	assert iso["name"] == "ReactOS-0.4.16-i386.iso"
	assert len(iso["sha256"]) == 64 and len(iso["zip_sha256"]) == 64
	assert recipe.section("inputs", "afterglow")["commit"] == "78fa9d57805a993eaa8162b17a154e73bcd8c319"
	assert recipe.section("patchers", "list") == [
		"afterglow.pointers",
		"afterglow.start",
		"afterglow.icons",
		"afterglow.cpl-icons",
		"afterglow.program-icons",
		"afterglow.toolbar-bitmaps",
		"afterglow.logon",
		"afterglow.boot",
	]
	assert recipe.section("trim", "profile") == "base"


def test_chunk_size_defaults_to_eight_mebibytes(base_recipe_path, tmp_path):
	assert load(base_recipe_path).chunk_size == 8 * 1024 * 1024 == DEFAULT_CHUNK_SIZE
	text = base_recipe_path.read_text().replace('chunk_size = "8MiB"\n', "")
	path = write(tmp_path, "nochunk.toml", text)
	assert load(path).chunk_size == DEFAULT_CHUNK_SIZE


def test_chunk_size_is_a_recipe_parameter(base_recipe_path, tmp_path):
	text = base_recipe_path.read_text().replace('"8MiB"', '"1MiB"')
	assert load(write(tmp_path, "small.toml", text)).chunk_size == 1 << 20


@pytest.mark.parametrize("bad", ['"3MiB"', "1000", '"4KiB"', "true", '"lots"'])
def test_bad_chunk_sizes_are_refused(base_recipe_path, tmp_path, bad):
	text = base_recipe_path.read_text().replace('"8MiB"', bad)
	with pytest.raises(RecipeError, match="chunk_size"):
		load(write(tmp_path, "bad.toml", text))


def test_parse_size_units():
	assert parse_size("8MiB", "k") == 8 << 20
	assert parse_size(" 2 GiB", "k") == 2 << 30
	assert parse_size(512, "k") == 512


def test_unknown_key_names_its_path(base_recipe_path, tmp_path):
	text = base_recipe_path.read_text() + "\n[install_typo]\nx = 1\n"
	with pytest.raises(RecipeError, match="install_typo: unknown key"):
		load(write(tmp_path, "typo.toml", text))


def test_missing_pin_is_named(base_recipe_path, tmp_path):
	text = base_recipe_path.read_text().replace('sha256 = "6f15', 'sha256x = "6f15')
	with pytest.raises(RecipeError, match="sha256x: unknown key|sha256: required"):
		load(write(tmp_path, "nopin.toml", text))


def test_malformed_hash_is_refused(base_recipe_path, tmp_path):
	text = base_recipe_path.read_text().replace("6f15ca6e", "6F15CA6E")
	with pytest.raises(RecipeError, match="inputs.reactos_iso.sha256"):
		load(write(tmp_path, "upper.toml", text))


def test_unknown_trim_profile_and_patcher_are_refused(base_recipe_path, tmp_path):
	text = base_recipe_path.read_text().replace('profile = "base"', 'profile = "tiny"')
	with pytest.raises(RecipeError, match="trim.profile"):
		load(write(tmp_path, "trim.toml", text))
	text = base_recipe_path.read_text().replace(
		'list = [\n\t"afterglow.pointers",\n\t"afterglow.start",\n\t"afterglow.icons",\n\t"afterglow.cpl-icons",\n\t"afterglow.program-icons",\n\t"afterglow.toolbar-bitmaps",\n\t"afterglow.logon",\n\t"afterglow.boot",\n]',
		'list = ["made.up"]',
	)
	with pytest.raises(RecipeError, match="patchers.list"):
		load(write(tmp_path, "patch.toml", text))


def test_a_recipe_without_the_iso_pin_is_refused(tmp_path):
	with pytest.raises(RecipeError, match="reactos_iso"):
		load(write(tmp_path, "empty.toml", '[recipe]\nname = "x"\n'))


def test_a_recipe_without_a_name_is_refused(tmp_path):
	with pytest.raises(RecipeError, match="recipe"):
		load(write(tmp_path, "anon.toml", "[install]\nlocale = '0409'\n"))


def test_extends_merges_tables_key_by_key(base_recipe_path, tmp_path):
	write(tmp_path, "base.toml", base_recipe_path.read_text())
	child = write(
		tmp_path,
		"child.toml",
		MINIMAL + '\n[install]\ncomputer_name = "QUILLDEMO"\n\n[trim]\nprofile = "none"\n\n[patchers]\nlist = ["afterglow.pointers"]\n',
	)
	recipe = load(child)
	assert recipe.name == "child"
	assert recipe.section("install", "computer_name") == "QUILLDEMO"
	assert recipe.section("install", "owner_name") == "ReactOS user"
	assert recipe.section("trim", "profile") == "none"
	assert "afterglow.pointers" in recipe.section("patchers", "list")
	assert recipe.section("inputs", "reactos_iso")["name"] == "ReactOS-0.4.16-i386.iso"
	assert [path.name for path in recipe.chain] == ["child.toml", "base.toml"]


def test_extends_cycle_is_refused(tmp_path):
	write(tmp_path, "a.toml", '[recipe]\nname = "a"\nextends = "b.toml"\n')
	write(tmp_path, "b.toml", '[recipe]\nname = "b"\nextends = "a.toml"\n')
	with pytest.raises(RecipeError, match="extends itself"):
		load(tmp_path / "a.toml")


def test_rl_prefix_names_a_recipe_in_the_repository(tmp_path):
	child = write(tmp_path, "child.toml", '[recipe]\nname = "child"\nextends = "rl:recipes/afterglow.toml"\n')
	assert load(child).section("inputs", "reactos_iso")["name"].endswith(".iso")


def test_missing_and_malformed_files_are_reported(tmp_path):
	with pytest.raises(RecipeError, match="no such recipe"):
		load(tmp_path / "nope.toml")
	with pytest.raises(RecipeError, match="bad.toml"):
		load(write(tmp_path, "bad.toml", "this is = = not toml"))


REG_TEXT = 'Windows Registry Editor Version 5.00\n\n[HKEY_CURRENT_USER\\Software\\Test]\n"Value"="one"\n'


def test_a_reg_path_is_resolved_beside_the_recipe_that_lists_it(base_recipe_path, tmp_path):
	child_folder = tmp_path / "child"
	child_folder.mkdir()
	write(child_folder, "extra.reg", REG_TEXT)
	child = write(
		child_folder, "child.toml", f'[recipe]\nname = "child"\nextends = "{base_recipe_path}"\n[settings]\nreg_files = ["extra.reg"]\n'
	)
	listed = load(child).section("settings", "reg_files")
	assert listed[:-1] == ["display", "quiet", "watermark-off", "afterglow-logon"]
	assert listed[-1] == str(child_folder / "extra.reg")


def test_the_named_files_come_first_and_each_recipe_adds_its_own_paths(base_recipe_path, tmp_path):
	write(tmp_path, "middle.reg", REG_TEXT)
	write(tmp_path, "top.reg", REG_TEXT)
	middle = write(
		tmp_path,
		"middle.toml",
		f'[recipe]\nname = "middle"\nextends = "{base_recipe_path}"\n[settings]\nreg_files = ["middle.reg", "display"]\n',
	)
	top = write(tmp_path, "top.toml", '[recipe]\nname = "top"\nextends = "middle.toml"\n[settings]\nreg_files = ["top.reg"]\n')
	assert load(middle).section("settings", "reg_files") == ["display", str(tmp_path / "middle.reg")]
	assert load(top).section("settings", "reg_files") == ["display", str(tmp_path / "middle.reg"), str(tmp_path / "top.reg")]


def test_a_missing_or_headerless_reg_file_is_refused(base_recipe_path, tmp_path):
	missing = write(
		tmp_path, "missing.toml", f'[recipe]\nname = "missing"\nextends = "{base_recipe_path}"\n[settings]\nreg_files = ["nope.reg"]\n'
	)
	with pytest.raises(RecipeError, match=r"settings.reg_files.*nope.reg is not a file"):
		load(missing)
	write(tmp_path, "bad.reg", "[HKEY_CURRENT_USER\\Software\\Test]\n")
	headerless = write(
		tmp_path, "headerless.toml", f'[recipe]\nname = "headerless"\nextends = "{base_recipe_path}"\n[settings]\nreg_files = ["bad.reg"]\n'
	)
	with pytest.raises(RecipeError, match="must start with the line"):
		load(headerless)


def test_a_duplicate_reg_path_is_refused(base_recipe_path, tmp_path):
	write(tmp_path, "extra.reg", REG_TEXT)
	twice = write(
		tmp_path,
		"twice.toml",
		f'[recipe]\nname = "twice"\nextends = "{base_recipe_path}"\n[settings]\nreg_files = ["extra.reg", "extra.reg"]\n',
	)
	with pytest.raises(RecipeError, match="duplicate"):
		load(twice)


def test_files_merge_by_destination_across_extends(base_recipe_path, tmp_path):
	base = load(base_recipe_path)
	assert len(base.data["files"]) == 2
	child_dir = tmp_path / "quill"
	child_dir.mkdir()
	write(child_dir, "mine.cmd", "@echo mine\n")
	child = write(
		child_dir,
		"child.toml",
		'[recipe]\nname = "child"\nextends = "rl:recipes/afterglow.toml"\n\n'
		'[[files]]\nsource = "mine.cmd"\ndestination = "ReactOS/System32/AFTERFETCH.cmd"\n\n'
		'[[files]]\nsource = "mine.cmd"\ndestination = "Quill/run.cmd"\n',
	)
	files = load(child).data["files"]
	assert [entry["destination"] for entry in files] == [
		"ReactOS/system32/afterfetch.exe",
		"ReactOS/System32/AFTERFETCH.cmd",
		"Quill/run.cmd",
	]
	assert files[0]["source"] == "built:afterfetch"
	assert files[1]["source"] == str(child_dir / "mine.cmd")


def test_inherited_file_sources_stay_relative_to_the_recipe_that_wrote_them(base_recipe_path, tmp_path):
	child = write(tmp_path, "child.toml", '[recipe]\nname = "child"\nextends = "rl:recipes/afterglow.toml"\n')
	files = {entry["destination"]: entry["source"] for entry in load(child).data["files"]}
	assert files["ReactOS/system32/afterfetch.cmd"] == str(base_recipe_path.parent.parent / "guest" / "cmd" / "afterfetch.cmd")
	assert files["ReactOS/system32/afterfetch.exe"] == "built:afterfetch"
