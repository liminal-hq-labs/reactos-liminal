# Tests for the dialog bitmap patcher on synthetic PE files, a fake Afterglow tree and a tiny FAT disk (no ReactOS file is used).
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import json
import struct

import pytest
from pe_fixtures import make_dll

from reactos_liminal import patch_base, patch_bitmaps, patch_dialog_bitmaps, patch_icons
from reactos_liminal.patchers import PatchError, run_patchers
from reactos_liminal.pe_resource import PeFile, pe_checksum

SHELL = "ReactOS/system32/shell32.dll"
GINA = "ReactOS/system32/msgina.dll"
GINA_COPY = "ReactOS/system32/agmsgina.dll"
WIDTH, HEIGHT = 6, 3


def dib24(fill: int, width: int = WIDTH, height: int = HEIGHT) -> bytes:
	"""A 24-bit bottom-up DIB of one colour, rows padded to four bytes, as a stock dialog bitmap is."""
	stride = (width * 3 + 3) // 4 * 4
	pixels = bytes([fill]) * stride * height
	return struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, len(pixels), 0, 0, 0, 0) + pixels


def bmp24(fill: int, width: int = WIDTH, height: int = HEIGHT) -> bytes:
	"""The .bmp file of that DIB: the same bytes behind a 14-byte file header."""
	body = dib24(fill, width, height)
	return b"BM" + struct.pack("<IHHI", 14 + len(body), 0, 0, 14 + 40) + body


# Afterglow's map entries for the fixtures: one bitmap in shell32.dll and two in msgina.dll, from two art folders.
RESOURCES = [
	{
		"id": "banner",
		"file": "desktop/dialogs/banner.svg",
		"bitmap": "banner.bmp",
		"module": "shell32.dll",
		"resource": 131,
		"name": "IDB_BANNER",
		"size": [WIDTH, HEIGHT],
		"bits": 24,
	},
	{
		"id": "background",
		"file": "desktop/dialogs/background.svg",
		"bitmap": "background.bmp",
		"module": "msgina.dll",
		"resource": 20003,
		"name": "IDI_BACKGROUND",
		"size": [WIDTH, HEIGHT],
		"bits": 24,
	},
	{
		"id": "bar",
		"file": "desktop/logon/bar.svg",
		"bitmap": "bar.bmp",
		"module": "msgina.dll",
		"resource": 20007,
		"name": "IDI_BAR",
		"size": [WIDTH, HEIGHT],
		"bits": 24,
	},
]
ART = {"desktop/dialogs": {"banner.bmp": bmp24(0x11), "background.bmp": bmp24(0x22)}, "desktop/logon": {"bar.bmp": bmp24(0x33)}}


def write_tree(tree, resources=RESOURCES, art=ART):
	"""A fake Afterglow tree: a map with `bitmaps`, and an art folder per entry whose render.py writes known bytes."""
	icons = tree / "desktop" / "icons"
	icons.mkdir(parents=True, exist_ok=True)
	(icons / "map.json").write_text(json.dumps({"icons": [], "bitmaps": resources}))
	for folder, files in art.items():
		directory = tree / folder
		directory.mkdir(parents=True, exist_ok=True)
		writes = "".join(f"open(os.path.join(sys.argv[1], {name!r}), 'wb').write({data!r})\n" for name, data in files.items())
		(directory / "render.py").write_text(f"import os, sys\nos.makedirs(sys.argv[1], exist_ok=True)\n{writes}")
		(directory / "SHA256SUMS").write_text("".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in files.items()))


@pytest.fixture
def setup(fat, tmp_path, monkeypatch):
	shell_bytes = make_dll({}, {}, bitmaps={131: dib24(1), 138: dib24(2)})
	gina_bytes = make_dll({}, {}, bitmaps={20003: dib24(3), 20007: dib24(4), 20009: dib24(5)})
	fat.make_directory("ReactOS")
	fat.make_directory("ReactOS/system32")
	for path, content in ((SHELL, shell_bytes), (GINA, gina_bytes)):
		local = tmp_path / path.rsplit("/", 1)[1]
		local.write_bytes(content)
		fat.copy_in(local, path)
	spec = {
		"files": [
			{"path": SHELL, "stock_sha256": hashlib.sha256(shell_bytes).hexdigest()},
			{"path": GINA, "stock_sha256": hashlib.sha256(gina_bytes).hexdigest()},
			{"path": GINA_COPY, "module": "msgina.dll", "stock_path": GINA, "stock_sha256": hashlib.sha256(gina_bytes).hexdigest()},
		]
	}
	monkeypatch.setattr(patch_dialog_bitmaps, "load_spec", lambda: spec)
	tree = tmp_path / "tree"
	write_tree(tree)
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	pins_file = tmp_path / "pins.json"
	monkeypatch.setattr(patch_dialog_bitmaps, "PINS_FILE", pins_file)
	pins_file.write_text(json.dumps({"families": {}}))
	return fat, tree, scratch, shell_bytes, gina_bytes, spec


def run(setup, tmp_path):
	fat, tree, scratch, *_ = setup
	with patch_base.recording() as recorder:
		patched = run_patchers(["afterglow.dialog-bitmaps"], fat, tree, tmp_path, scratch)
	return patched, recorder


def bitmap_of(data: bytes, resource_id: int) -> bytes:
	slot = PeFile(data).bitmap(resource_id)
	return data[slot.data_offset : slot.data_offset + slot.size]


def test_each_bitmap_is_written_in_place_as_a_dib_and_the_file_keeps_its_size(setup, tmp_path):
	_fat, _tree, _scratch, shell_bytes, gina_bytes, _spec = setup
	patched, _recorder = run(setup, tmp_path)
	assert [item.image_path for item in patched] == [SHELL, GINA]  # agmsgina.dll is left alone: no earlier patcher wrote it
	shell, gina = (item.local_file.read_bytes() for item in patched)
	assert len(shell) == len(shell_bytes) and len(gina) == len(gina_bytes)
	assert bitmap_of(shell, 131) == dib24(0x11)  # the DIB, without the .bmp file header
	assert bitmap_of(shell, 138) == dib24(2)  # not in the map's list for this module, so unchanged
	assert bitmap_of(gina, 20003) == dib24(0x22) and bitmap_of(gina, 20007) == dib24(0x33) and bitmap_of(gina, 20009) == dib24(5)


def test_only_the_bitmap_bytes_and_the_checksum_change(setup, tmp_path):
	_fat, _tree, _scratch, shell_bytes, *_ = setup
	patched, _recorder = run(setup, tmp_path)
	new = patched[0].local_file.read_bytes()
	slot = PeFile(shell_bytes).bitmap(131)
	differing = {offset for offset in range(len(new)) if new[offset] != shell_bytes[offset]}
	checksum_at = PeFile(new).checksum_offset
	assert all(slot.data_offset <= offset < slot.data_offset + slot.size or checksum_at <= offset < checksum_at + 4 for offset in differing)
	assert struct.unpack_from("<I", new, checksum_at)[0] == pe_checksum(new, checksum_at)


def test_the_bitmap_ids_come_from_the_map_not_from_this_repository(setup, tmp_path):
	_fat, tree, *_ = setup
	moved = [{**RESOURCES[1], "resource": 20009}]
	write_tree(tree, RESOURCES[:1] + moved)
	patched, _recorder = run(setup, tmp_path)
	gina = patched[1].local_file.read_bytes()
	assert bitmap_of(gina, 20009) == dib24(0x22) and bitmap_of(gina, 20003) == dib24(3)


def test_a_bitmap_whose_stock_size_is_not_the_one_the_map_records_is_refused(setup, tmp_path):
	_fat, tree, *_ = setup
	wrong = [{**RESOURCES[0], "size": [WIDTH + 1, HEIGHT]}]
	write_tree(tree, wrong, {"desktop/dialogs": {"banner.bmp": bmp24(0x11, WIDTH + 1, HEIGHT)}})
	with pytest.raises(PatchError, match="the map says"):
		run(setup, tmp_path)


def test_art_of_another_size_or_depth_than_the_map_records_is_refused(setup, tmp_path):
	_fat, tree, *_ = setup
	write_tree(tree, art={**ART, "desktop/dialogs": {"banner.bmp": bmp24(0x11, WIDTH + 1, HEIGHT), "background.bmp": bmp24(0x22)}})
	with pytest.raises(PatchError, match="is not a 6 x 3, 24-bit bitmap"):
		run(setup, tmp_path)


def test_art_that_does_not_match_afterglows_sums_is_refused(setup, tmp_path):
	_fat, tree, *_ = setup
	(tree / "desktop" / "dialogs" / "SHA256SUMS").write_text(f"{'0' * 64}  banner.bmp\n{'0' * 64}  background.bmp\n")
	with pytest.raises(PatchError, match="Afterglow records"):
		run(setup, tmp_path)


@pytest.mark.parametrize("path", [SHELL, GINA])
def test_a_changed_stock_file_is_refused(setup, tmp_path, path):
	fat, *_ = setup
	changed = tmp_path / "changed.dll"
	changed.write_bytes(make_dll({}, {}, bitmaps={131: dib24(9), 138: dib24(2), 20003: dib24(3), 20007: dib24(4), 20009: dib24(5)}))
	fat.copy_in(changed, path)
	with pytest.raises(PatchError, match="not the stock file"):
		run(setup, tmp_path)


def test_the_map_must_list_the_bitmaps(setup, tmp_path):
	_fat, tree, *_ = setup
	(tree / "desktop" / "icons" / "map.json").write_text(json.dumps({"icons": []}))
	with pytest.raises(PatchError, match="no `bitmaps` list"):
		run(setup, tmp_path)


def test_a_copy_is_patched_when_an_earlier_patcher_wrote_it_and_keeps_that_patchers_work(setup, tmp_path):
	_fat, _tree, scratch, _shell, gina_bytes, _spec = setup
	earlier = scratch / "earlier.dll"
	earlier_bytes = bytearray(gina_bytes)
	earlier_bytes[-1] ^= 0xFF  # a byte outside the bitmaps, as an icon patcher's section would be
	earlier.write_bytes(bytes(earlier_bytes))
	patch_base.remember_patched(scratch, patch_base.PatchedFile(GINA_COPY, earlier))
	patched, recorder = run(setup, tmp_path)
	copy = next(item for item in patched if item.image_path == GINA_COPY).local_file.read_bytes()
	assert copy[-1] == earlier_bytes[-1] and bitmap_of(copy, 20003) == dib24(0x22)
	(digest,) = recorder.results["dialog-bitmaps"]
	assert set(recorder.results["dialog-bitmaps"][digest]) == {SHELL, GINA, GINA_COPY}


def test_a_file_the_trim_removes_is_left_alone(setup, tmp_path):
	fat, tree, scratch, *_ = setup
	with patch_base.recording(), patch_base.skipping(lambda path: path == GINA):
		patched = run_patchers(["afterglow.dialog-bitmaps"], fat, tree, tmp_path, scratch)
	assert [item.image_path for item in patched] == [SHELL]


def test_the_result_is_checked_against_its_pin_and_an_unpinned_set_is_refused(setup, tmp_path):
	fat, tree, *_ = setup
	_patched, recorder = run(setup, tmp_path)
	((digest, results),) = recorder.results["dialog-bitmaps"].items()
	pins = {"families": {"dialog-bitmaps": {digest: results}}}

	def run_again(name):
		scratch = tmp_path / name  # a fresh build: the earlier run's copies are not this one's inputs
		scratch.mkdir()
		return run_patchers(["afterglow.dialog-bitmaps"], fat, tree, tmp_path, scratch)

	patch_dialog_bitmaps.PINS_FILE.write_text(json.dumps(pins))
	assert len(run_again("pinned")) == 2
	pins["families"]["dialog-bitmaps"][digest][SHELL] = "0" * 64
	patch_dialog_bitmaps.PINS_FILE.write_text(json.dumps(pins))
	with pytest.raises(PatchError, match="expected"):
		run_again("wrong")
	patch_dialog_bitmaps.PINS_FILE.write_text(json.dumps({"families": {}}))
	with pytest.raises(PatchError, match="no pinned result"):
		run_again("unpinned")


def test_the_shipped_table_names_files_and_hashes_only():
	spec = patch_dialog_bitmaps.load_spec()
	assert [item["path"] for item in spec["files"]] == [SHELL, GINA, GINA_COPY, "ReactOS/system32/cards.dll"]
	assert all(set(item) <= {"path", "module", "stock_path", "stock_sha256"} for item in spec["files"])  # no resource ids here
	assert patch_dialog_bitmaps.FAMILY in json.loads(patch_bitmaps.PINS_FILE.read_text())["families"]
	assert patch_icons.PINS_FILE.name == "shell32-icons.json"


def dib8(fill: int, width: int = WIDTH, height: int = HEIGHT) -> bytes:
	"""An 8-bit bottom-up DIB with a 256-entry colour table, as the stock card backs are."""
	stride = (width + 3) // 4 * 4
	pixels = bytes([fill]) * stride * height
	return struct.pack("<IiiHHIIiiII", 40, width, height, 1, 8, 0, len(pixels), 0, 0, 256, 0) + bytes(1024) + pixels


CARD_RESOURCES = [
	{
		"id": "card-back",
		"file": "desktop/cards/card-back.svg",
		"bitmap": "card-back.bmp",
		"module": "cards.dll",
		"resource": 54,
		"name": "Background_1",
		"size": [WIDTH, HEIGHT],
		"bits": 8,
	}
]


@pytest.fixture
def cards(fat, tmp_path, monkeypatch):
	stock = make_dll({}, {}, bitmaps={53: dib8(1), 54: dib8(2), 55: dib8(3)})
	fat.make_directory("ReactOS")
	fat.make_directory("ReactOS/system32")
	local = tmp_path / "cards.dll"
	local.write_bytes(stock)
	fat.copy_in(local, "ReactOS/system32/cards.dll")
	path = "ReactOS/system32/cards.dll"
	spec = {"files": [{"path": path, "stock_sha256": hashlib.sha256(stock).hexdigest()}]}
	monkeypatch.setattr(patch_dialog_bitmaps, "load_spec", lambda: spec)
	tree = tmp_path / "tree"
	write_tree(tree, CARD_RESOURCES, {"desktop/cards": {"card-back.bmp": bmp24(0x44)}})
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	pins_file = tmp_path / "pins.json"
	monkeypatch.setattr(patch_dialog_bitmaps, "PINS_FILE", pins_file)
	pins_file.write_text(json.dumps({"families": {}}))
	return fat, tree, scratch, stock, path


def test_art_at_another_depth_goes_in_a_new_section_and_only_its_entry_moves(cards, tmp_path):
	fat, tree, scratch, stock, path = cards
	with patch_base.recording():
		patched = run_patchers(["afterglow.dialog-bitmaps"], fat, tree, tmp_path, scratch)
	assert [item.image_path for item in patched] == [path]
	new = patched[0].local_file.read_bytes()
	assert bitmap_of(new, 54) == dib24(0x44)  # 24-bit now, same width and height
	assert bitmap_of(new, 53) == dib8(1) and bitmap_of(new, 55) == dib8(3)  # the other backs are untouched
	assert b".agbmp" in new[:0x400]  # the new section's header
	assert new.startswith(stock[:0x80])  # the DOS header and stub did not move
	assert struct.unpack_from("<I", new, PeFile(new).checksum_offset)[0] == pe_checksum(new, PeFile(new).checksum_offset)


def test_art_of_a_size_the_map_does_not_name_is_refused(cards, tmp_path, monkeypatch):
	fat, tree, scratch, _stock, _path = cards
	write_tree(tree, CARD_RESOURCES, {"desktop/cards": {"card-back.bmp": bmp24(0x44, WIDTH + 4, HEIGHT)}})
	with patch_base.recording(), pytest.raises(PatchError, match="is not a 6 x 3, 8-bit or 24-bit bitmap"):
		run_patchers(["afterglow.dialog-bitmaps"], fat, tree, tmp_path, scratch)


def test_a_stock_bitmap_of_another_depth_than_the_map_says_is_refused(cards, tmp_path):
	fat, tree, scratch, _stock, _path = cards
	resources = [{**CARD_RESOURCES[0], "bits": 24}]
	write_tree(tree, resources, {"desktop/cards": {"card-back.bmp": bmp24(0x44)}})
	with patch_base.recording(), pytest.raises(PatchError, match="is 6 x 3 at 8 bits in the file"):
		run_patchers(["afterglow.dialog-bitmaps"], fat, tree, tmp_path, scratch)
