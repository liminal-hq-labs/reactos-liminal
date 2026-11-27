# Tests for the cpl and program icon patchers and the toolbar bitmap patcher, on synthetic PE files and a fake Afterglow tree.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import json
import struct

import pytest
from pe_fixtures import group_of, ico, make_dll, stock_dll

from reactos_liminal import patch_base, patch_bitmaps, patch_dialog_bitmaps, patch_family, patch_icons
from reactos_liminal.patchers import PatchError, run_patchers
from reactos_liminal.pe_resources import RT_BITMAP, PeFile

CPL = "ReactOS/system32/test.cpl"
BROWSEUI = "ReactOS/system32/browseui.dll"
CELL = 16
COUNT = 6
# Afterglow's map entry for the one icon the fixtures use: an applet group in the .cpl, and cell 2 of the toolbar strips.
MOUSE = {
	"id": "mouse",
	"kind": "applet",
	"resource": {"module": "test.cpl", "group": 4},
	"also": [{"module": "browseui.dll", "bitmaps": [214, 216], "cell": 2}],
}


def strip_bitmap(fill: int) -> bytes:
	"""A 32-bit strip of COUNT square cells of CELL px, every pixel one value."""
	pixels = bytes([fill, fill, fill, 255]) * CELL * CELL * COUNT
	return struct.pack("<IiiHHIIiiII", 40, CELL * COUNT, CELL, 1, 32, 0, len(pixels), 0, 0, 0, 0) + pixels


@pytest.fixture
def setup(fat, tmp_path, monkeypatch):
	cpl_bytes = stock_dll()
	browseui_bytes = make_dll({}, {}, bitmaps={214: strip_bitmap(1), 216: strip_bitmap(1)})
	fat.make_directory("ReactOS")
	fat.make_directory("ReactOS/system32")
	for name, content in (("test.cpl", cpl_bytes), ("browseui.dll", browseui_bytes)):
		local = tmp_path / name
		local.write_bytes(content)
		fat.copy_in(local, f"ReactOS/system32/{name}")
	families = {
		"cpl-icons": {
			"files": [{"path": CPL, "stock_sha256": hashlib.sha256(cpl_bytes).hexdigest()}],
		}
	}
	monkeypatch.setattr(patch_family, "load_families", lambda: families)
	strips = {
		"files": [
			{
				"path": BROWSEUI,
				"stock_sha256": hashlib.sha256(browseui_bytes).hexdigest(),
				"strips": [{"id": 214, "cell": 16, "count": COUNT}, {"id": 216, "cell": 16, "count": COUNT}],
			}
		]
	}
	monkeypatch.setattr(patch_bitmaps, "load_strips", lambda: strips)
	tree = tmp_path / "tree"
	icons_dir = tree / "desktop" / "icons"
	icons_dir.mkdir(parents=True)
	icon = ico(0x40)
	(icons_dir / "render.py").write_text(
		"import os, sys\nos.makedirs(os.path.join(sys.argv[1], 'ico'))\n"
		f"open(os.path.join(sys.argv[1], 'ico', 'mouse.ico'), 'wb').write({icon!r})\n"
	)
	icon_sum = hashlib.sha256(icon).hexdigest()
	(icons_dir / "SHA256SUMS").write_text(f"{icon_sum}  ico/mouse.ico\n")
	(icons_dir / "map.json").write_text(json.dumps({"icons": [MOUSE]}))
	digest = patch_icons.icon_set_digest({"ico/mouse.ico": icon_sum})
	cpl_result = hashlib.sha256(patch_icons.patch_icon_groups(cpl_bytes, {4: icon})[0]).hexdigest()
	bitmap_result = hashlib.sha256(
		patch_bitmaps.patch_strips(browseui_bytes, strips["files"][0]["strips"], [{"index": 2, "afterglow": "mouse"}], {"mouse": icon})[0]
	).hexdigest()
	pins = {"families": {"cpl-icons": {digest: {CPL: cpl_result}}, "toolbar-bitmaps": {digest: {BROWSEUI: bitmap_result}}}}
	monkeypatch.setattr(patch_family, "load_pins", lambda: pins)
	monkeypatch.setattr(patch_bitmaps, "PINS_FILE", tmp_path / "pins.json")
	(tmp_path / "pins.json").write_text(json.dumps(pins))
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	return fat, tree, scratch, cpl_bytes, browseui_bytes, icons_dir, pins


def test_the_cpl_patcher_replaces_the_group_and_matches_its_pin(setup, tmp_path):
	fat, tree, scratch, *_ = setup
	patched = run_patchers(["afterglow.cpl-icons"], fat, tree, tmp_path, scratch)
	assert [item.image_path for item in patched] == [CPL]
	frames = group_of(PeFile(patched[0].local_file.read_bytes()), 4)
	assert [(frame.width, frame.bit_count) for frame in frames] == [(48, 32), (32, 32), (16, 32)]


def test_a_changed_cpl_is_refused(setup, tmp_path):
	fat, tree, scratch, cpl_bytes, *_ = setup
	changed = tmp_path / "changed.cpl"
	changed.write_bytes(cpl_bytes[:-1] + b"\x01")
	fat.copy_in(changed, "ReactOS/system32/test.cpl")
	with pytest.raises(PatchError, match="not the stock file"):
		run_patchers(["afterglow.cpl-icons"], fat, tree, tmp_path, scratch)


def test_the_group_to_replace_is_the_one_the_map_names(setup, tmp_path):
	"""Move the icon to group 30 in the map and group 30 is the one the patcher tries, with no change to the repository's tables."""
	fat, tree, scratch, _c, _b, icons_dir, _p = setup
	moved = {**MOUSE, "resource": {"module": "test.cpl", "group": 30}}
	(icons_dir / "map.json").write_text(json.dumps({"icons": [moved]}))
	with patch_base.recording():
		patched = run_patchers(["afterglow.cpl-icons"], fat, tree, tmp_path, scratch)
	frames = group_of(PeFile(patched[0].local_file.read_bytes()), 30)
	assert [frame.width for frame in frames] == [32, 16]  # a two-frame group is fitted, not refused


def test_a_file_with_no_group_in_the_map_is_checked_and_its_groups_stay_as_they_were(setup, tmp_path):
	fat, tree, scratch, cpl_bytes, _b, icons_dir, _p = setup
	(icons_dir / "map.json").write_text(json.dumps({"icons": [{"id": "mouse", "kind": "applet"}]}))
	with patch_base.recording():
		patched = run_patchers(["afterglow.cpl-icons"], fat, tree, tmp_path, scratch)
	assert group_of(PeFile(patched[0].local_file.read_bytes()), 4) == group_of(PeFile(cpl_bytes), 4)


def dialog_family(monkeypatch, cpl_bytes):
	"""Make the test applet stand in for user32.dll: a family whose file an earlier patcher has already written."""
	families = {
		"dialog-icons": {
			"files": [{"path": CPL, "stock_sha256": hashlib.sha256(cpl_bytes).hexdigest()}],
		}
	}
	monkeypatch.setattr(patch_family, "load_families", lambda: families)


def earlier_copy(scratch, content):
	"""A copy of the test applet as an earlier patcher of the same build leaves it."""
	local = scratch / "earlier.cpl"
	local.write_bytes(content)
	patch_base.remember_patched(scratch, patch_base.PatchedFile(CPL, local))


def test_a_family_built_on_another_patchers_copy_patches_that_copy_and_pins_against_it(setup, tmp_path, monkeypatch):
	fat, tree, scratch, cpl_bytes, *_ = setup
	dialog_family(monkeypatch, cpl_bytes)
	base = cpl_bytes[:-1] + b"\x01"  # the earlier patcher's copy: still the stock file's layout, not its bytes
	earlier_copy(scratch, base)
	with patch_base.recording() as recorder:
		patched = run_patchers(["afterglow.dialog-icons"], fat, tree, tmp_path, scratch)
	assert patched[0].local_file.read_bytes() == patch_icons.patch_icon_groups(base, {4: ico(0x40)})[0]
	assert patched[0].local_file.read_bytes() != patch_icons.patch_icon_groups(cpl_bytes, {4: ico(0x40)})[0]
	(digest,) = recorder.results["dialog-icons"]
	icon_only = patch_icons.icon_set_digest({"ico/mouse.ico": hashlib.sha256(ico(0x40)).hexdigest()})
	assert digest != icon_only  # the pin is keyed by the earlier copy as well as the icons


def test_a_patchers_result_is_the_next_patchers_input(setup, tmp_path, monkeypatch):
	"""run_patchers notes each result, so two patchers on one file build on each other and nothing is lost."""
	fat, tree, scratch, cpl_bytes, *_ = setup
	spec = {"path": CPL, "stock_sha256": hashlib.sha256(cpl_bytes).hexdigest()}
	monkeypatch.setattr(patch_family, "load_families", lambda: {"cpl-icons": {"files": [spec]}, "dialog-icons": {"files": [spec]}})
	first = run_patchers(["afterglow.cpl-icons"], fat, tree, tmp_path, scratch)
	assert patch_base.latest_patched(scratch, CPL) == first[0].local_file
	with patch_base.recording() as recorder:
		second = run_patchers(["afterglow.dialog-icons"], fat, tree, tmp_path, scratch)
	assert second[0].local_file.read_bytes() == patch_icons.patch_icon_groups(first[0].local_file.read_bytes(), {4: ico(0x40)})[0]
	assert "dialog-icons" in recorder.results


def test_a_copy_of_a_stock_file_is_left_alone_when_no_earlier_patcher_wrote_it(setup, tmp_path, monkeypatch):
	"""`agexplorer.exe` and `agmsgina.dll` exist only when `afterglow.start` and `afterglow.logon` wrote them."""
	fat, tree, scratch, cpl_bytes, *_ = setup
	copy = "ReactOS/system32/ag.cpl"
	spec = {"path": copy, "module": "test.cpl", "stock_path": CPL, "stock_sha256": hashlib.sha256(cpl_bytes).hexdigest()}
	monkeypatch.setattr(patch_family, "load_families", lambda: {"cpl-icons": {"files": [spec]}})
	with patch_base.recording():
		assert run_patchers(["afterglow.cpl-icons"], fat, tree, tmp_path, scratch) == []
		local = scratch / "ag.cpl"
		local.write_bytes(cpl_bytes)
		patch_base.remember_patched(scratch, patch_base.PatchedFile(copy, local))
		patched = run_patchers(["afterglow.cpl-icons"], fat, tree, tmp_path, scratch)
	assert [item.image_path for item in patched] == [copy]
	assert group_of(PeFile(patched[0].local_file.read_bytes()), 4)[0].icon_id == 4


def test_a_copy_still_checks_the_stock_file_it_is_made_from(setup, tmp_path, monkeypatch):
	fat, tree, scratch, cpl_bytes, *_ = setup
	spec = {"path": "ReactOS/system32/ag.cpl", "stock_path": CPL, "module": "test.cpl", "stock_sha256": "0" * 64}
	monkeypatch.setattr(patch_family, "load_families", lambda: {"cpl-icons": {"files": [spec]}})
	local = scratch / "ag.cpl"
	local.write_bytes(cpl_bytes)
	patch_base.remember_patched(scratch, patch_base.PatchedFile(spec["path"], local))
	with pytest.raises(PatchError, match="not the stock file"), patch_base.recording():
		run_patchers(["afterglow.cpl-icons"], fat, tree, tmp_path, scratch)


def test_a_file_the_trim_removes_is_left_alone_and_the_pin_does_not_change(setup, tmp_path):
	"""The patch list is the same for the full and the compact image: a file the trim removes is skipped, and the pin, keyed by the
	icons and the earlier copies, is the one the full image uses."""
	fat, tree, scratch, *_ = setup
	with patch_base.skipping(lambda path: path == CPL):
		assert run_patchers(["afterglow.cpl-icons"], fat, tree, tmp_path, scratch) == []
	assert not list(scratch.glob("*.patched"))
	with patch_base.skipping(lambda path: False):
		patched = run_patchers(["afterglow.cpl-icons"], fat, tree, tmp_path, scratch)  # the pin is checked, and is the same
	assert [item.image_path for item in patched] == [CPL]


def test_the_dialog_icons_are_user32_and_take_their_groups_from_the_map():
	"""The family names only the file and its stock sum: the message-box groups come from the map."""
	(file_spec,) = patch_family.load_families()["dialog-icons"]["files"]
	assert file_spec["path"] == "ReactOS/system32/user32.dll" and "base" not in file_spec
	assert "groups" not in file_spec
	entries = {
		name: {"id": name, "resource": {"module": "user32.dll", "group": group}}
		for name, group in (("warning", 101), ("question", 102), ("error", 103), ("info", 104))
	}
	assert patch_family.family_groups(entries, file_spec) == {101: "warning", 102: "question", 103: "error", 104: "info"}


def test_the_group_table_adds_only_groups_the_map_does_not_name(monkeypatch):
	entries = {"mouse": MOUSE, "keys": {"id": "keys"}}
	spec = {"path": CPL, "groups": [{"group": 4, "afterglow": "keys"}, {"group": 7, "afterglow": "keys"}]}
	assert patch_family.family_groups(entries, spec) == {4: "mouse", 7: "keys"}  # the map decides group 4; the table adds group 7
	with pytest.raises(PatchError, match="no icon 'gone'"):
		patch_family.family_groups(entries, {"path": CPL, "groups": [{"group": 9, "afterglow": "gone"}]})


def test_a_map_that_puts_toolbar_icons_in_other_bitmaps_is_refused(setup, tmp_path):
	fat, tree, scratch, _c, _b, icons_dir, _p = setup
	other = {**MOUSE, "also": [{"module": "browseui.dll", "bitmaps": [214, 215], "cell": 2}]}
	(icons_dir / "map.json").write_text(json.dumps({"icons": [other]}))
	with pytest.raises(PatchError, match="the table has"):
		run_patchers(["afterglow.toolbar-bitmaps"], fat, tree, tmp_path, scratch)


def test_two_icons_for_one_group_is_an_error_in_the_map():
	twin = {"id": "twin", "resource": {"module": "test.cpl", "group": 4}}
	with pytest.raises(PatchError, match="both"):
		patch_family.family_groups({"mouse": MOUSE, "twin": twin}, {"path": CPL})


def test_an_unpinned_icon_set_is_refused(setup, tmp_path, monkeypatch):
	fat, tree, scratch, *_ = setup
	monkeypatch.setattr(patch_family, "load_pins", lambda: {"families": {}})
	with pytest.raises(PatchError, match="no pinned result"):
		run_patchers(["afterglow.cpl-icons"], fat, tree, tmp_path, scratch)


def test_a_wrong_pinned_result_is_refused_and_leaves_no_file(setup, tmp_path, monkeypatch):
	fat, tree, scratch, *_rest, pins = setup
	digest = next(iter(pins["families"]["cpl-icons"]))
	monkeypatch.setattr(patch_family, "load_pins", lambda: {"families": {"cpl-icons": {digest: {CPL: "0" * 64}}}})
	with pytest.raises(PatchError, match="expected"):
		run_patchers(["afterglow.cpl-icons"], fat, tree, tmp_path, scratch)
	assert not list(scratch.glob("*.patched"))


def test_the_bitmap_patcher_writes_cells_in_place_and_keeps_the_size(setup, tmp_path):
	fat, tree, scratch, _c, browseui_bytes, *_ = setup
	patched = run_patchers(["afterglow.toolbar-bitmaps"], fat, tree, tmp_path, scratch)
	new = patched[0].local_file.read_bytes()
	assert len(new) == len(browseui_bytes)
	before, after = PeFile(browseui_bytes), PeFile(new)
	for strip_id in (214, 216):
		old_bitmap = before.entry_data(before.data_entries(RT_BITMAP)[strip_id][0])
		new_bitmap = after.entry_data(after.data_entries(RT_BITMAP)[strip_id][0])
		assert len(old_bitmap) == len(new_bitmap) and old_bitmap[:40] == new_bitmap[:40]
		pixels = new_bitmap[40:]
		stride = CELL * COUNT * 4
		cell_start = 2 * CELL * 4
		assert pixels[cell_start : cell_start + 4] != old_bitmap[40 + cell_start : 40 + cell_start + 4]  # the cell changed
		assert pixels[:cell_start] == old_bitmap[40 : 40 + cell_start]  # the cells before it did not
		assert pixels[stride : stride + 4] == old_bitmap[40 + stride : 40 + stride + 4]  # nor did the next row's first cell


def test_a_bitmap_of_another_size_is_refused():
	wrong = make_dll({}, {}, bitmaps={214: strip_bitmap(1)})
	with pytest.raises(PatchError, match="same size and depth"):
		patch_bitmaps.patch_strips(
			wrong, [{"id": 214, "cell": 24, "count": COUNT}], [{"index": 0, "afterglow": "mouse"}], {"mouse": ico(1)}
		)


def test_a_missing_bitmap_is_refused():
	with pytest.raises(PatchError, match="no bitmap 99"):
		patch_bitmaps.patch_strips(make_dll({}, {}), [{"id": 99, "cell": 16, "count": COUNT}], [], {})


def test_a_changed_browseui_is_refused(setup, tmp_path):
	fat, tree, scratch, _c, browseui_bytes, *_ = setup
	changed = tmp_path / "changed.dll"
	changed.write_bytes(browseui_bytes[:-1] + b"\x01")
	fat.copy_in(changed, BROWSEUI)
	with pytest.raises(PatchError, match="not the stock browseui.dll"):
		run_patchers(["afterglow.toolbar-bitmaps"], fat, tree, tmp_path, scratch)


def test_halving_averages_by_alpha_and_keeps_transparent_pixels_clear():
	opaque = bytes([10, 20, 30, 255])
	clear = bytes(4)
	rows = [opaque * 2 + clear * 2, opaque * 2 + clear * 2, clear * 4, clear * 4]
	half = patch_bitmaps.halve(rows)
	assert half[0] == opaque + clear and half[1] == clear * 2


def test_the_cell_and_family_tables_are_consistent():
	families = patch_family.FAMILIES_FILE.read_text()
	assert json.loads(families)["families"].keys() == {"cpl-icons", "program-icons", "dialog-icons"}
	spec = patch_bitmaps.load_strips()["files"][0]
	assert {strip["cell"] for strip in spec["strips"]} == {16, 24}
	assert all(0 <= cell["index"] < 47 for cell in spec.get("cells", []))
	pins = json.loads(patch_family.PINS_FILE.read_text())["families"]
	assert set(pins) == {"cpl-icons", "program-icons", "dialog-icons", "toolbar-bitmaps", "dialog-bitmaps"}


def test_no_patched_file_is_one_the_base_trim_removes():
	"""The trim refuses to remove a patched file, so a family must not name a file the base profile deletes."""
	from reactos_liminal.trim import build_profile, check_profile

	paths = [file_spec["path"] for family in patch_family.load_families().values() for file_spec in family["files"]]
	paths += [file_spec["path"] for file_spec in patch_bitmaps.load_strips()["files"]]
	paths += [file_spec["path"] for file_spec in patch_dialog_bitmaps.load_spec()["files"]]
	check_profile(build_profile("base", []), paths)


def test_the_icons_the_map_does_not_name_yet_are_in_the_tables():
	"""The Internet Browser desktop item is shell32 group 512 and the Console applet is console.dll group 40; the map names neither."""
	shell32_rows = {row["group"]: row for row in patch_icons.load_table()["groups"]}
	assert shell32_rows[512]["afterglow"] == "browser"
	console = next(
		file_spec for file_spec in patch_family.load_families()["cpl-icons"]["files"] if file_spec["path"].endswith("/console.dll")
	)
	assert console["groups"] == [{"group": 40, "afterglow": "console"}]
