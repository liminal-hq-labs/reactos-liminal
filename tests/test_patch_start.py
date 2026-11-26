# Tests for the Start orb and banner patcher on a synthetic explorer.exe: a tiny PE with the two bitmap resources, the stock size and
# hash replaced by the synthetic file's own so the guard can be tested without a ReactOS file.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import struct

import pytest

from reactos_liminal import patch_start
from reactos_liminal.patch_start import PortableExecutable, pe_checksum
from reactos_liminal.patchers import PatchError, run_patchers

ORB_SLOT = patch_start.SLOTS[143]
BANNER_SLOT = patch_start.SLOTS[158]


def dib(width, height, bits, size, fill):
	header = struct.pack("<IiiHHIIiiII", 40, width, height, 1, bits, 0, size - 40, 0, 0, 0, 0)
	return header + bytes([fill]) * (size - 40)


STOCK_ORB = dib(*ORB_SLOT[:3], ORB_SLOT[3], 0x11)
STOCK_BANNER = dib(*BANNER_SLOT[:3], BANNER_SLOT[3], 0x22)
NEW_ORB = dib(*ORB_SLOT[:3], ORB_SLOT[3], 0xAA)
NEW_BANNER = dib(*BANNER_SLOT[:3], BANNER_SLOT[3], 0xBB)


def make_explorer(orb=STOCK_ORB, banner=STOCK_BANNER) -> bytes:
	"""A PE32 with one .rsrc section holding RT_BITMAP 143 and 158, one language each."""
	section_rva, section_raw = 0x1000, 0x200
	# resource tree: root -> type 2 -> ids 143 and 158 -> one language each -> data entries
	root = 0
	type_dir = 24
	name_143, name_158 = 24 + 16 + 16, 24 + 16 + 16 + 24
	entry_143, entry_158 = name_158 + 24, name_158 + 24 + 16
	data_start = entry_158 + 16
	tree = bytearray(data_start)

	def directory(offset, entries):
		struct.pack_into("<IIHHHH", tree, offset, 0, 0, 0, 0, 0, len(entries))
		for index, (identifier, target) in enumerate(entries):
			struct.pack_into("<II", tree, offset + 16 + 8 * index, identifier, target)

	directory(root, [(2, 0x80000000 | type_dir)])
	directory(type_dir, [(143, 0x80000000 | name_143), (158, 0x80000000 | name_158)])
	directory(name_143, [(0x409, entry_143)])
	directory(name_158, [(0x409, entry_158)])
	orb_at = data_start
	banner_at = orb_at + len(orb)
	struct.pack_into("<IIII", tree, entry_143, section_rva + orb_at, len(orb), 0, 0)
	struct.pack_into("<IIII", tree, entry_158, section_rva + banner_at, len(banner), 0, 0)
	section = bytes(tree) + orb + banner
	header = bytearray(0x200)
	header[0:2] = b"MZ"
	struct.pack_into("<I", header, 0x3C, 0x40)
	header[0x40:0x44] = b"PE\0\0"
	struct.pack_into("<HHIIIHH", header, 0x44, 0x14C, 1, 0, 0, 0, 0xE0, 0x102)
	optional = 0x58
	struct.pack_into("<H", header, optional, 0x10B)
	struct.pack_into("<I", header, optional + 92, 16)
	struct.pack_into("<II", header, optional + 96 + 2 * 8, section_rva, len(section))
	section_header = optional + 0xE0
	header[section_header : section_header + 8] = b".rsrc\0\0\0"
	struct.pack_into("<IIII", header, section_header + 8, len(section), section_rva, len(section), section_raw)
	return bytes(header) + section


@pytest.fixture
def explorer(tmp_path, fat, monkeypatch):
	stock = make_explorer()
	monkeypatch.setattr(patch_start, "STOCK_SIZE", len(stock))
	monkeypatch.setattr(patch_start, "STOCK_SHA256", hashlib.sha256(stock).hexdigest())
	source = tmp_path / "explorer.exe"
	source.write_bytes(stock)
	fat.make_directory("ReactOS")
	fat.copy_in(source, "ReactOS/explorer.exe")
	return stock


def write_art(tmp_path, orb=NEW_ORB, banner=NEW_BANNER):
	"""A fake Afterglow tree whose render.py writes known DIBs, and the SHA256SUMS that records them."""
	tree = tmp_path / "tree"
	start = tree / "desktop" / "start"
	start.mkdir(parents=True)
	(start / "render.py").write_text(
		"import sys, pathlib\n"
		"out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)\n"
		f"(out / 'start-orb.dib').write_bytes({orb!r})\n(out / 'start-banner.dib').write_bytes({banner!r})\n"
	)
	(start / "SHA256SUMS").write_text(
		f"{hashlib.sha256(banner).hexdigest()}  start-banner.dib\n{hashlib.sha256(orb).hexdigest()}  start-orb.dib\n"
	)
	return tree


def pin_result(monkeypatch, explorer):
	patched = patch_start.patch_explorer(explorer, {143: NEW_ORB, 158: NEW_BANNER})
	monkeypatch.setattr(patch_start, "PATCHED_SHA256", hashlib.sha256(patched).hexdigest())
	return patched


def test_the_patched_copy_has_the_new_art_and_a_valid_checksum(tmp_path, fat, explorer, monkeypatch):
	expected = pin_result(monkeypatch, explorer)
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	patched = run_patchers(["afterglow.start"], fat, write_art(tmp_path), tmp_path, scratch)
	assert [item.image_path for item in patched] == ["ReactOS/agexplorer.exe"]
	data = patched[0].local_file.read_bytes()
	assert data == expected and len(data) == len(explorer)
	image = PortableExecutable(data)
	for resource_id, art in ((143, NEW_ORB), (158, NEW_BANNER)):
		offset, size = image.bitmap(resource_id)
		assert data[offset : offset + size] == art
	stored = struct.unpack_from("<I", data, image.checksum_offset)[0]
	assert stored == pe_checksum(data, image.checksum_offset)
	# only the two bitmaps and the checksum differ from the stock file
	changed = [index for index, (new, old) in enumerate(zip(data, explorer, strict=True)) if new != old]
	orb_offset, _ = image.bitmap(143)
	banner_offset, _ = image.bitmap(158)
	allowed = set(range(orb_offset, orb_offset + ORB_SLOT[3])) | set(range(banner_offset, banner_offset + BANNER_SLOT[3]))
	allowed |= set(range(image.checksum_offset, image.checksum_offset + 4))
	assert set(changed) <= allowed


def test_the_stock_file_on_the_disk_is_left_alone(tmp_path, fat, explorer, monkeypatch):
	pin_result(monkeypatch, explorer)
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	before = hashlib.sha256(fat.image.read_bytes()).hexdigest()
	run_patchers(["afterglow.start"], fat, write_art(tmp_path), tmp_path, scratch)
	assert hashlib.sha256(fat.image.read_bytes()).hexdigest() == before


def test_a_changed_stock_file_is_refused(tmp_path, fat, explorer, monkeypatch):
	pin_result(monkeypatch, explorer)
	changed = bytearray(explorer)
	changed[-1] ^= 1
	path = tmp_path / "changed.exe"
	path.write_bytes(bytes(changed))
	fat.copy_in(path, "ReactOS/explorer.exe")
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	with pytest.raises(PatchError, match="not the stock"):
		run_patchers(["afterglow.start"], fat, write_art(tmp_path), tmp_path, scratch)
	assert not (scratch / "agexplorer.exe").exists()


def test_art_that_afterglow_does_not_record_is_refused(tmp_path, fat, explorer, monkeypatch):
	pin_result(monkeypatch, explorer)
	tree = write_art(tmp_path)
	(tree / "desktop" / "start" / "SHA256SUMS").write_text("0" * 64 + "  start-orb.dib\n" + "0" * 64 + "  start-banner.dib\n")
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	with pytest.raises(PatchError, match="Afterglow records"):
		run_patchers(["afterglow.start"], fat, tree, tmp_path, scratch)


def test_art_of_the_wrong_size_is_refused(tmp_path, fat, explorer, monkeypatch):
	pin_result(monkeypatch, explorer)
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	tree = write_art(tmp_path, orb=dib(24, 20, 32, 40 + 24 * 20 * 4, 0xAA))
	with pytest.raises(PatchError, match="must be a"):
		run_patchers(["afterglow.start"], fat, tree, tmp_path, scratch)


def test_a_result_that_misses_its_pin_is_refused(tmp_path, fat, explorer, monkeypatch):
	pin_result(monkeypatch, explorer)
	monkeypatch.setattr(patch_start, "PATCHED_SHA256", "0" * 64)
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	with pytest.raises(PatchError, match="expected"):
		run_patchers(["afterglow.start"], fat, write_art(tmp_path), tmp_path, scratch)
	assert not (scratch / "agexplorer.exe").exists()


def test_a_tree_without_the_start_masters_is_refused(tmp_path, fat, explorer):
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	tree = tmp_path / "old"
	tree.mkdir()
	with pytest.raises(PatchError, match="older than the Start orb"):
		run_patchers(["afterglow.start"], fat, tree, tmp_path, scratch)
