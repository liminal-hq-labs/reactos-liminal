# Tests for the cpl and program icon patchers and the toolbar bitmap patcher, on synthetic PE files and a fake Afterglow tree.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import json
import struct

import pytest
from pe_fixtures import group_of, ico, make_dll, stock_dll

from reactos_liminal import patch_bitmaps, patch_family, patch_icons
from reactos_liminal.patchers import PatchError, run_patchers
from reactos_liminal.pe_resources import RT_BITMAP, PeFile

CPL = "ReactOS/system32/test.cpl"
BROWSEUI = "ReactOS/system32/browseui.dll"
CELL = 16
COUNT = 6


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
			"map_kind": "applet",
			"files": [{"path": CPL, "stock_sha256": hashlib.sha256(cpl_bytes).hexdigest(), "groups": [{"group": 4, "afterglow": "mouse"}]}],
		}
	}
	monkeypatch.setattr(patch_family, "load_families", lambda: families)
	strips = {
		"files": [
			{
				"path": BROWSEUI,
				"stock_sha256": hashlib.sha256(browseui_bytes).hexdigest(),
				"strips": [{"id": 214, "cell": 16, "count": COUNT}, {"id": 216, "cell": 16, "count": COUNT}],
				"cells": [{"index": 2, "afterglow": "mouse"}],
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
	(icons_dir / "map.json").write_text(json.dumps({"icons": [{"id": "mouse", "kind": "applet", "group": "Control Panel applets"}]}))
	digest = patch_icons.icon_set_digest({"ico/mouse.ico": icon_sum})
	cpl_result = hashlib.sha256(patch_icons.patch_icon_groups(cpl_bytes, {4: icon})[0]).hexdigest()
	bitmap_result = hashlib.sha256(
		patch_bitmaps.patch_strips(browseui_bytes, strips["files"][0]["strips"], strips["files"][0]["cells"], {"mouse": icon})[0]
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


def test_a_map_that_calls_the_icon_something_else_is_refused(setup, tmp_path):
	fat, tree, scratch, _c, _b, icons_dir, _p = setup
	(icons_dir / "map.json").write_text(json.dumps({"icons": [{"id": "mouse", "kind": "drive"}]}))
	with pytest.raises(PatchError, match="expected 'applet'"):
		run_patchers(["afterglow.cpl-icons"], fat, tree, tmp_path, scratch)


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
	assert json.loads(families)["families"].keys() == {"cpl-icons", "program-icons"}
	spec = patch_bitmaps.load_strips()["files"][0]
	assert {strip["cell"] for strip in spec["strips"]} == {16, 24}
	assert all(0 <= cell["index"] < 47 for cell in spec["cells"])
	pins = json.loads(patch_family.PINS_FILE.read_text())["families"]
	assert set(pins) == {"cpl-icons", "program-icons", "toolbar-bitmaps"}
