# Tests for the Go button bitmaps the toolbar patcher writes, and the coverage rows for map `bitmaps` entries, on synthetic PE files.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import json
import struct

import pytest
from pe_fixture import bmp_file, make_dib, make_pe
from pe_fixtures import ico, make_dll

from reactos_liminal import coverage, patch_base, patch_bitmaps, patch_icons
from reactos_liminal.patchers import PatchError, run_patchers
from reactos_liminal.pe_resources import RT_BITMAP, PeFile

BROWSEUI = "ReactOS/system32/browseui.dll"
CELL = 16
COUNT = 6
SIDE = 20
GO_ENTRIES = [
	{
		"id": "go",
		"file": "desktop/icons/svg/24/go.svg",
		"bitmap": "go.bmp",
		"module": "browseui.dll",
		"resource": resource,
		"name": name,
		"size": [SIDE, SIDE],
		"bits": 32,
		"evidence": ["source", "binary"],
	}
	for resource, name in ((230, "IDB_SHELL_GO"), (231, "IDB_SHELL_GO_HOT"))
]
MOUSE = {"id": "mouse", "kind": "toolbar", "resource": {"module": "browseui.dll", "bitmaps": [214, 216], "cell": 2, "evidence": ["source"]}}
GO = {"id": "go", "kind": "bitmap", "resource": None}


def strip(fill: int) -> bytes:
	pixels = bytes([fill, fill, fill, 255]) * CELL * CELL * COUNT
	return struct.pack("<IiiHHIIiiII", 40, CELL * COUNT, CELL, 1, 32, 0, len(pixels), 0, 0, 0, 0) + pixels


def go_dib(fill: int, side: int = SIDE, bits: int = 32) -> bytes:
	return make_dib(side, side, bits, fill=fill)


def browseui(overrides: dict[int, bytes] | None = None) -> bytes:
	bitmaps = {214: strip(1), 216: strip(1), 230: go_dib(0), 231: go_dib(0)}
	bitmaps.update(overrides or {})
	return make_dll({}, {}, bitmaps=bitmaps)


def resource_bytes(data: bytes, resource_id: int) -> bytes:
	pe = PeFile(data)
	return pe.entry_data(pe.data_entries(RT_BITMAP)[resource_id][0])


def test_the_go_bitmaps_are_written_in_place_and_keep_their_length():
	stock = browseui()
	art = {"go.bmp": bmp_file(go_dib(0x55))}
	patched, report = patch_bitmaps.write_resource_bitmaps(stock, GO_ENTRIES, art)
	assert len(patched) == len(stock) and len(report) == 2
	for resource_id in (230, 231):
		assert resource_bytes(patched, resource_id) == go_dib(0x55)
		assert len(resource_bytes(patched, resource_id)) == 1640
	assert resource_bytes(patched, 214) == resource_bytes(stock, 214)


@pytest.mark.parametrize(
	"stock_bitmap, message",
	[(make_dib(21, 20, 32), "21x20 at 32 bits"), (make_dib(20, 20, 24), "at 24 bits")],
)
def test_a_stock_bitmap_of_another_size_or_depth_is_refused(stock_bitmap, message):
	stock = browseui({230: stock_bitmap})
	with pytest.raises(PatchError, match=message):
		patch_bitmaps.write_resource_bitmaps(stock, GO_ENTRIES, {"go.bmp": bmp_file(go_dib(1))})


@pytest.mark.parametrize("art", [bmp_file(go_dib(1, side=24)), bmp_file(go_dib(1, bits=24))])
def test_art_of_another_size_or_depth_is_refused(art):
	with pytest.raises(PatchError, match="is not a 20 x 20, 32-bit"):
		patch_bitmaps.write_resource_bitmaps(browseui(), GO_ENTRIES, {"go.bmp": art})


def test_a_missing_bitmap_is_refused():
	stock = make_pe({230: go_dib(0)})
	with pytest.raises(PatchError, match="231"):
		patch_bitmaps.write_resource_bitmaps(stock, GO_ENTRIES, {"go.bmp": bmp_file(go_dib(1))})


@pytest.fixture
def setup(fat, tmp_path, monkeypatch):
	stock = browseui()
	fat.make_directory("ReactOS")
	fat.make_directory("ReactOS/system32")
	local = tmp_path / "browseui.dll"
	local.write_bytes(stock)
	fat.copy_in(local, BROWSEUI)
	strips = {
		"files": [
			{
				"path": BROWSEUI,
				"stock_sha256": hashlib.sha256(stock).hexdigest(),
				"strips": [{"id": 214, "cell": 16, "count": COUNT}, {"id": 216, "cell": 16, "count": COUNT}],
			}
		]
	}
	monkeypatch.setattr(patch_bitmaps, "load_strips", lambda: strips)
	tree = tmp_path / "tree"
	icons_dir = tree / "desktop" / "icons"
	icons_dir.mkdir(parents=True)
	icon = ico(0x40)
	art = bmp_file(go_dib(0x77))
	(icons_dir / "render.py").write_text(
		"import os, sys\nos.makedirs(os.path.join(sys.argv[1], 'ico'))\nos.makedirs(os.path.join(sys.argv[1], 'bmp'))\n"
		f"open(os.path.join(sys.argv[1], 'ico', 'mouse.ico'), 'wb').write({icon!r})\n"
		f"open(os.path.join(sys.argv[1], 'bmp', 'go.bmp'), 'wb').write({art!r})\n"
	)
	(icons_dir / "SHA256SUMS").write_text(
		f"{hashlib.sha256(icon).hexdigest()}  ico/mouse.ico\n{hashlib.sha256(art).hexdigest()}  bmp/go.bmp\n"
	)
	write_map(tree, [MOUSE, GO], GO_ENTRIES)
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	return fat, tree, scratch, stock


def write_map(tree, icons, bitmaps):
	(tree / "desktop" / "icons" / "map.json").write_text(json.dumps({"icons": icons, "bitmaps": bitmaps}))


def run_recording(fat, tree, tmp_path, scratch):
	with patch_base.recording() as recorder:
		patched = run_patchers(["afterglow.toolbar-bitmaps"], fat, tree, tmp_path, scratch)
	return patched[0].local_file.read_bytes(), recorder


def test_the_toolbar_patcher_writes_the_go_bitmaps_and_records_them(setup, tmp_path):
	fat, tree, scratch, stock = setup
	new, recorder = run_recording(fat, tree, tmp_path, scratch)
	assert len(new) == len(stock)
	for resource_id in (230, 231):
		assert resource_bytes(new, resource_id) == go_dib(0x77)
	assert recorder.patched[("browseui.dll", "bitmap", 230)] == ("go", [BROWSEUI])
	assert recorder.patched[("browseui.dll", "bitmap", 231)] == ("go", [BROWSEUI])


def test_the_strips_are_the_same_bytes_with_and_without_the_go_bitmaps(setup, tmp_path):
	fat, tree, scratch, stock = setup
	with_go, _recorder = run_recording(fat, tree, tmp_path, scratch)
	write_map(tree, [MOUSE, GO], [])
	without_go, _recorder = run_recording(fat, tree, tmp_path, scratch)
	assert resource_bytes(without_go, 230) == resource_bytes(stock, 230)
	for strip_id in (214, 216):
		assert resource_bytes(with_go, strip_id) == resource_bytes(without_go, strip_id)
		assert resource_bytes(with_go, strip_id) != resource_bytes(stock, strip_id)  # the cell itself did change


def test_a_one_byte_changed_browseui_is_refused_by_its_hash(setup, tmp_path):
	fat, tree, scratch, stock = setup
	changed = tmp_path / "changed.dll"
	changed.write_bytes(stock[:-1] + b"\x01")
	fat.copy_in(changed, BROWSEUI)
	with pytest.raises(PatchError, match="not the stock browseui.dll"):
		run_recording(fat, tree, tmp_path, scratch)


def test_art_that_differs_from_afterglows_sum_is_refused(setup, tmp_path):
	fat, tree, scratch, _stock = setup
	(tree / "desktop" / "icons" / "SHA256SUMS").write_text(f"{'0' * 64}  bmp/go.bmp\n")
	with pytest.raises(PatchError):
		patch_icons.verified_bitmaps(tree, scratch, {"go.bmp"})


def test_the_coverage_report_lists_a_bitmaps_entry_as_patched():
	entries = {"go": GO, "mouse": MOUSE}
	with patch_base.recording() as recorder:
		patch_base.note_patched("browseui.dll", 230, "go", BROWSEUI, "bitmap")
		patch_base.note_patched("browseui.dll", 231, "go", BROWSEUI, "bitmap")
		patch_base.note_patched("browseui.dll", 2, "mouse", BROWSEUI, "cell")
	rows = coverage.build_rows(entries, recorder, set(), {}, GO_ENTRIES)
	go_rows = [row for row in rows if row.icon_id == "go"]
	assert [(row.target, row.status) for row in go_rows] == [("bitmap 230", "patched"), ("bitmap 231", "patched")]
	assert coverage.counts(rows) == {"patched": 3, "skipped": 0, "unverified": 0}
	with patch_base.recording() as untouched:
		pass
	without = coverage.build_rows(entries, untouched, set(), {}, [])
	assert next(row for row in without if row.icon_id == "go").status == "unverified"


def test_the_bitmaps_table_marks_written_modules_patched_and_bitfields_strips_skipped():
	items = [
		{"id": "a", "module": "zipfldr.dll", "resource": 200, "size": [49, 49], "bits": 24},
		{"id": "b", "module": "comctl32.dll", "resource": 120, "size": [240, 16], "bits": 32},
		{"id": "go", "module": "browseui.dll", "resource": 230, "size": [20, 20], "bits": 32},
	]
	rows = coverage.bitmap_rows(items, {"zipfldr.dll": ["ReactOS/system32/zipfldr.dll"]})
	assert [(item["id"], status) for item, status, _note in rows] == [("a", "patched"), ("b", "skipped")]  # browseui.dll has its own rows
	assert "BI_BITFIELDS" in rows[1][2]
