# Tests for the trim profiles and the guard that keeps a trim from removing a patched file or a licence file.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import pytest

from reactos_liminal import trim
from reactos_liminal.image import ImageError, plan_image, trim_image
from reactos_liminal.recipe import load
from reactos_liminal.trim import (
	LICENCE_PATHS,
	TrimEntry,
	TrimError,
	apply_profile,
	build_profile,
	check_profile,
	load_profile,
	parse_profile,
	profile_names,
	protection_conflicts,
)

NIC_DRIVERS = [f"f ReactOS/system32/drivers/{name}.sys" for name in ("e1000", "rtl8139", "pcnet", "dc21x4", "nvnet", "netkvm")]


def lines(profile):
	return [f"{entry.kind} {entry.path}" for entry in profile.entries]


def test_the_built_in_profiles_are_none_and_base():
	assert profile_names() == ["base", "none"]


def test_none_removes_nothing():
	assert load_profile("none").entries == []


def test_base_is_a_complete_list_that_keeps_the_network_stack():
	entries = lines(load_profile("base"))
	assert len(entries) == 128
	assert not any("tcpip" in line.lower() or "afd" in line.lower() or "tdi" in line.lower() for line in entries)
	assert not any(driver in entries for driver in NIC_DRIVERS)


@pytest.mark.parametrize("name", ["none", "base"])
def test_shipped_profiles_never_reach_a_protected_path(name):
	check_profile(load_profile(name))
	check_profile(load_profile(name), ["ReactOS/system32/user32.dll", "ReactOS/system32/agmsgina.dll"])


def test_parse_rules():
	profile = parse_profile("x", "# comment\n\nf a/b.txt\nd c d\n")
	assert profile.entries == [TrimEntry("f", "a/b.txt"), TrimEntry("d", "c d")]
	for bad in ("x a/b", "f", "f ../etc", "d /abs"):
		with pytest.raises(TrimError):
			parse_profile("x", bad)


def test_unknown_profile_is_named():
	with pytest.raises(TrimError, match="known: base, none"):
		load_profile("tiny")


@pytest.mark.parametrize(
	"entry",
	[
		TrimEntry("f", "ReactOS/system32/user32.dll"),
		TrimEntry("f", "reactos/SYSTEM32/User32.DLL"),  # FAT ignores case
		TrimEntry("d", "ReactOS/system32"),  # holds the patched file
		TrimEntry("d", "ReactOS"),
	],
)
def test_a_patched_file_is_protected(entry):
	assert "patched file" in protection_conflicts(entry, ["ReactOS/system32/user32.dll"])


@pytest.mark.parametrize(
	"entry",
	[
		TrimEntry("f", "NOTICE.txt"),
		TrimEntry("f", "CHANGES.txt"),
		TrimEntry("d", "LICENSES"),
		TrimEntry("f", "LICENSES/GPL-2.0.txt"),
		TrimEntry("d", "Program Files/otvdm"),
		TrimEntry("f", "Program Files/otvdm/LICENSE"),
	],
)
def test_licence_files_are_protected(entry):
	assert "licence file" in protection_conflicts(entry)


def test_unrelated_paths_pass():
	assert protection_conflicts(TrimEntry("f", "ReactOS/system32/sol.exe"), ["ReactOS/system32/user32.dll"]) is None
	assert protection_conflicts(TrimEntry("d", "ReactOS/system32/gecko")) is None  # Gecko's licence goes with Gecko
	assert set(LICENCE_PATHS) >= {"LICENSES", "NOTICE.txt", "CHANGES.txt"}


def test_a_profile_that_reaches_a_patched_file_is_refused_before_any_removal(fat, tmp_path):
	source = tmp_path / "f.bin"
	source.write_bytes(b"x" * 1000)
	fat.make_directory("ReactOS")
	fat.copy_in(source, "ReactOS/a.bin")
	fat.copy_in(source, "ReactOS/user32.dll")
	profile = parse_profile("p", "f ReactOS/a.bin\nf ReactOS/user32.dll\n")
	with pytest.raises(TrimError, match="patched file"):
		apply_profile(fat, profile, ["ReactOS/user32.dll"])
	assert fat.exists("ReactOS/a.bin")  # nothing was removed, not even the entry before the bad one


def test_apply_removes_files_and_folders_and_reports_what_is_missing(fat, tmp_path):
	source = tmp_path / "f.bin"
	source.write_bytes(b"x" * 100_000)
	fat.make_directory("d")
	fat.make_directory("d/sub")
	fat.copy_in(source, "d/sub/one.bin")
	fat.copy_in(source, "two.bin")
	fat.copy_in(source, "keep.bin")
	profile = parse_profile("p", "d d\nf two.bin\nf not-there.bin\n")
	report = apply_profile(fat, profile)
	assert [entry.path for entry in report.removed] == ["d", "two.bin"]
	assert [entry.path for entry in report.missing] == ["not-there.bin"]
	assert report.bytes_freed >= 200_000
	assert fat.exists("keep.bin") and not fat.exists("d") and not fat.exists("two.bin")


def test_a_trim_never_touches_a_golden_disk(tmp_path, base_recipe_path):
	golden = tmp_path / "work" / "golden" / "x.img"
	golden.parent.mkdir(parents=True)
	golden.write_bytes(b"")
	with pytest.raises(ImageError, match="golden"):
		trim_image(load(base_recipe_path), tmp_path / "work", golden)


def test_the_profiles_directory_is_in_the_repository():
	assert trim.PROFILES_DIR.is_dir()


def write_recipe(directory, name, trim_table, extends=None):
	"""A recipe file in `directory` that extends the Afterglow recipe (or `extends`) and sets the `[trim]` table."""
	parent = extends or '"rl:recipes/afterglow.toml"'
	path = directory / name
	path.write_text(f'[recipe]\nname = "{path.stem}"\nextends = {parent}\n\n[trim]\n{trim_table}\n')
	return path


def test_extra_is_applied_after_the_profile(tmp_path):
	(tmp_path / "mine.txt").write_text("# mine\nf ReactOS/system32/drivers/e1000.sys\nf ReactOS/system32/sol.exe\n")
	profile = build_profile("base", [str(tmp_path / "mine.txt")])
	base = load_profile("base")
	assert lines(profile)[: len(base.entries)] == lines(base)
	# sol.exe is already in base, so only the driver is new
	assert lines(profile)[len(base.entries)] == "f ReactOS/system32/drivers/e1000.sys"
	assert [name for name, _ in profile.sources][:2] == ["base", str(tmp_path / "mine.txt")]
	assert [count for _, count in profile.sources][:2] == [len(base.entries), 1]


def test_extra_removes_files_on_the_disk_and_is_in_the_report(fat, tmp_path):
	source = tmp_path / "f.bin"
	source.write_bytes(b"x" * 10_000)
	fat.copy_in(source, "one.bin")
	fat.copy_in(source, "two.bin")
	(tmp_path / "mine.txt").write_text("f two.bin\n")
	profile = build_profile("none", [str(tmp_path / "mine.txt")])
	report = apply_profile(fat, profile)
	assert [entry.path for entry in report.removed] == ["two.bin"]
	assert report.sources == [("none", 0), (str(tmp_path / "mine.txt"), 1)]
	assert fat.exists("one.bin") and not fat.exists("two.bin")


@pytest.mark.parametrize("line", ["f NOTICE.txt", "d LICENSES", "d Program Files/otvdm", "f ReactOS/system32/user32.dll"])
def test_extra_that_reaches_a_protected_file_is_refused_before_anything_is_removed(fat, tmp_path, line):
	source = tmp_path / "f.bin"
	source.write_bytes(b"x" * 1000)
	fat.copy_in(source, "first.bin")
	extra = tmp_path / "bad.txt"
	extra.write_text(f"f first.bin\n{line}\n")
	profile = build_profile("none", [str(extra)])
	with pytest.raises(TrimError, match="bad.txt"):
		apply_profile(fat, profile, ["ReactOS/system32/user32.dll"])
	assert fat.exists("first.bin")


def test_a_missing_extra_file_names_the_key(tmp_path):
	(tmp_path / "here.txt").write_text("f x\n")
	with pytest.raises(TrimError, match=r"trim\.extra\[1\]: no such trim list"):
		build_profile("base", [str(tmp_path / "here.txt"), str(tmp_path / "gone.txt")])


def test_a_malformed_extra_file_names_the_key_and_line(tmp_path):
	extra = tmp_path / "bad.txt"
	extra.write_text("f fine.txt\nrm nope\n")
	with pytest.raises(TrimError, match=r"trim\.extra\[0\].*line 2"):
		build_profile("none", [str(extra)])
	extra.write_text("d ../outside\n")
	with pytest.raises(TrimError, match=r"trim\.extra\[0\].*unsafe path"):
		build_profile("none", [str(extra)])


def test_extra_paths_resolve_relative_to_the_recipe(tmp_path):
	folder = tmp_path / "downstream" / "recipes"
	folder.mkdir(parents=True)
	(folder / "mine.txt").write_text("f a.bin\n")
	recipe = load(write_recipe(folder, "mine.toml", 'extra = ["mine.txt"]'))
	assert recipe.section("trim", "extra") == [str(folder / "mine.txt")]
	assert recipe.section("trim", "profile") == "none"  # from the extended recipe
	# the plan finds the file wherever the process runs
	plan = plan_image(recipe, tmp_path / "work")
	assert any("extra trim list" in step and "mine.txt" in step and "1 entries" in step for step in plan.steps)


def test_a_missing_extra_stops_the_plan_and_names_the_key(tmp_path):
	recipe = load(write_recipe(tmp_path, "mine.toml", 'extra = ["nowhere.txt"]'))
	with pytest.raises(TrimError, match=r"trim\.extra\[0\]"):
		plan_image(recipe, tmp_path / "work")


def test_an_extra_that_is_not_a_list_of_strings_is_a_recipe_error(tmp_path):
	from reactos_liminal.recipe import RecipeError

	with pytest.raises(RecipeError, match=r"trim\.extra"):
		load(write_recipe(tmp_path, "mine.toml", "extra = 3"))


def test_an_extending_recipe_adds_its_own_extra_after_the_one_it_extends(tmp_path):
	parent_folder = tmp_path / "parent"
	child_folder = tmp_path / "child"
	parent_folder.mkdir()
	child_folder.mkdir()
	(parent_folder / "one.txt").write_text("f one.bin\n")
	(child_folder / "two.txt").write_text("f two.bin\n")
	parent = write_recipe(parent_folder, "parent.toml", 'extra = ["one.txt"]')
	child = write_recipe(child_folder, "child.toml", 'extra = ["two.txt"]', extends=f'"{parent}"')
	recipe = load(child)
	assert recipe.section("trim", "extra") == [str(parent_folder / "one.txt"), str(child_folder / "two.txt")]
	profile = build_profile("none", recipe.section("trim", "extra"))
	assert lines(profile) == ["f one.bin", "f two.bin"]
	# a child that sets no extra keeps its parent's
	quiet = write_recipe(child_folder, "quiet.toml", 'profile = "base"', extends=f'"{parent}"')
	assert load(quiet).section("trim", "extra") == [str(parent_folder / "one.txt")]


def test_trim_image_applies_the_recipes_extra_with_a_built_in_profile(tmp_path, fat):
	source = tmp_path / "f.bin"
	source.write_bytes(b"x" * 1000)
	fat.copy_in(source, "gone.bin")
	(tmp_path / "mine.txt").write_text("f gone.bin\n")
	recipe = load(write_recipe(tmp_path, "mine.toml", 'extra = ["mine.txt"]'))
	report = trim_image(recipe, tmp_path / "work", fat.image, "none")
	assert [entry.path for entry in report.removed] == ["gone.bin"]


@pytest.mark.parametrize(
	"path, removed",
	[
		("ReactOS/system32/mmc.exe", True),  # a file entry
		("reactos/system32/MMC.EXE", True),  # FAT ignores case
		("ReactOS/system32/gecko/wine_gecko.cab", True),  # inside a folder entry
		("ReactOS/system32/taskmgr.exe", False),
	],
)
def test_removes_says_whether_a_profile_reaches_a_path(path, removed):
	"""The patchers use this to leave alone a file the trim will remove, so the trim's protection rule is never tripped."""
	profile = trim.build_profile("base", [])
	assert trim.removes(profile, path) is removed


def test_no_file_the_patchers_write_is_one_the_base_profile_removes():
	"""Every path in the families (but `map-icons`, whose trimmed files a patcher leaves alone), the toolbar strips and the dialog bitmaps stays in the compact image, so the compact patch list
	is the full one and the pins are the same."""
	from reactos_liminal import patch_bitmaps, patch_dialog_bitmaps, patch_family

	paths = [
		file_spec["path"] for name, family in patch_family.load_families().items() if name != "map-icons" for file_spec in family["files"]
	]
	paths += [file_spec["path"] for file_spec in patch_bitmaps.load_strips()["files"]]
	paths += [file_spec["path"] for file_spec in patch_dialog_bitmaps.load_spec()["files"]]
	profile = trim.build_profile("base", [])
	assert [path for path in paths if trim.removes(profile, path)] == []


def test_the_stock_shortcut_list_is_well_formed():
	shortcuts = trim.load_shortcuts()
	assert len(shortcuts) >= 38
	for link, target in shortcuts.items():
		assert link.endswith(".lnk") and not target.startswith("/") and ".." not in link.split("/")
	assert shortcuts["Start Menu/Programs/Accessories/Calculator.lnk"] == "ReactOS/system32/calc.exe"


def test_a_malformed_shortcut_list_names_its_line(tmp_path):
	path = tmp_path / "shortcuts.txt"
	path.write_text("# comment\nA.lnk => x.exe\nB.lnk x.exe\n")
	with pytest.raises(TrimError, match=r"shortcuts.txt, line 3"):
		trim.load_shortcuts(path)


def test_removing_a_program_removes_its_shortcut_in_every_profile_and_an_emptied_folder():
	profile = parse_profile("p", "f ReactOS/system32/calc.exe\nf ReactOS/system32/sol.exe\nf ReactOS/system32/winmine.exe\n")
	shortcuts = {
		"Start Menu/Programs/Accessories/Calculator.lnk": "ReactOS/system32/calc.exe",
		"Start Menu/Programs/Accessories/Notepad.lnk": "ReactOS/system32/notepad.exe",
		"Start Menu/Programs/Games/Solitaire.lnk": "ReactOS/system32/sol.exe",
		"Start Menu/Programs/Games/WineMine.lnk": "ReactOS/system32/winmine.exe",
	}
	found = lines_of(trim.shortcut_entries(profile, shortcuts))
	for owner in trim.PROFILE_FOLDERS:
		assert f"f Documents and Settings/{owner}/Start Menu/Programs/Accessories/Calculator.lnk" in found
		assert f"d Documents and Settings/{owner}/Start Menu/Programs/Games" in found  # every link in the folder goes, so the folder does
	assert not any("Notepad" in line for line in found) and not any("Games/Solitaire" in line for line in found)


def lines_of(entries):
	return [f"{entry.kind} {entry.path}" for entry in entries]


def test_a_shortcut_the_profile_already_removes_is_not_repeated():
	profile = parse_profile("p", "f ReactOS/system32/calc.exe\nf Documents and Settings/Administrator/Start Menu/Programs/Calculator.lnk\n")
	shortcuts = {"Start Menu/Programs/Calculator.lnk": "ReactOS/system32/calc.exe"}
	found = lines_of(trim.shortcut_entries(profile, shortcuts))
	assert "f Documents and Settings/Administrator/Start Menu/Programs/Calculator.lnk" not in found and len(found) == 3


def test_the_profile_none_removes_no_shortcut_and_the_base_profile_removes_those_of_its_programs():
	assert trim.build_profile("none").entries == []
	base = lines_of(trim.build_profile("base").entries)
	for owner in ("Default User", "NetworkService"):
		assert f"f Documents and Settings/{owner}/Start Menu/Programs/Accessories/Calculator.lnk" in base
		assert f"d Documents and Settings/{owner}/Start Menu/Programs/Games" in base
	# a program the compact image keeps keeps its shortcut
	assert not any("Notepad.lnk" in line or "Task Manager.lnk" in line for line in base)
	assert trim.build_profile("base").sources[-1][0] == "shortcuts/stock.txt"


def test_an_extra_list_that_removes_a_program_removes_its_shortcut_too(tmp_path):
	extra = tmp_path / "extra.txt"
	extra.write_text("f ReactOS/system32/notepad.exe\n")
	profile = build_profile("base", [str(extra)])
	assert "f Documents and Settings/Administrator/Start Menu/Programs/Accessories/Notepad.lnk" in lines_of(profile.entries)


def test_a_user_without_a_listed_shortcut_is_not_reported_as_missing(fat, tmp_path):
	source = tmp_path / "f.bin"
	source.write_bytes(b"x")
	for folder in ("Documents and Settings", "Documents and Settings/Default User", "Documents and Settings/Default User/Start Menu"):
		fat.make_directory(folder)
	fat.make_directory("Documents and Settings/Default User/Start Menu/Programs")
	fat.copy_in(source, "Documents and Settings/Default User/Start Menu/Programs/Calculator.lnk")
	profile = parse_profile("p", "f ReactOS/system32/calc.exe\nf ReactOS/system32/stale.exe\n")
	profile.entries += trim.shortcut_entries(profile, {"Start Menu/Programs/Calculator.lnk": "ReactOS/system32/calc.exe"})
	report = apply_profile(fat, profile)
	assert not fat.exists("Documents and Settings/Default User/Start Menu/Programs/Calculator.lnk")
	assert [entry.path for entry in report.missing] == ["ReactOS/system32/calc.exe", "ReactOS/system32/stale.exe"]
