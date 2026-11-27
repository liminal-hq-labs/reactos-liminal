# Tests for the cold-boot colours patcher on a synthetic win32k.sys: a PE with the stock colour table appended.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib

import pytest
from pe_fixture import make_dib, make_pe

from reactos_liminal import patch_colours
from reactos_liminal.patch_base import PatchError
from reactos_liminal.patch_colours import STOCK_TABLE, VALUE_NAMES, afterglow_colours, patch_win32k
from reactos_liminal.patchers import run_patchers
from reactos_liminal.pe_resource import PeFile, pe_checksum

STYLE_REG = """Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\ThemeManager]
"ColorName"="Dusk"

[HKEY_CURRENT_USER\\Control Panel\\Colors]
"ActiveTitle"="31 37 84"
"TitleText"="255 255 255"

; generated
[HKEY_CURRENT_USER\\Control Panel\\Colors]
"Background"="9 14 42"
"Hilight"="66 57 108"

[HKEY_CURRENT_USER\\Console]
"ColorTable00"=dword:0030120a
"""
COLOURS = {"ActiveTitle": (31, 37, 84), "TitleText": (255, 255, 255), "Background": (9, 14, 42), "Hilight": (66, 57, 108)}


def sha(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


def table(overrides: dict[str, tuple[int, int, int]] | None = None) -> bytes:
	entries = list(STOCK_TABLE)
	for name, rgb in (overrides or {}).items():
		entries[VALUE_NAMES.index(name)] = rgb
	return b"".join(bytes(entry) + b"\0" for entry in entries)


def win32k(with_table: bytes | None = None, copies: int = 1) -> bytes:
	base = bytearray(make_pe({1: make_dib(4, 4, 24)}))
	for _ in range(copies):
		base += b"\xcc" * 7 + (with_table if with_table is not None else table())
	return bytes(base)


@pytest.fixture
def setup(fat, tmp_path, monkeypatch):
	stock = win32k()
	stock_file = tmp_path / "win32k.sys"
	stock_file.write_bytes(stock)
	fat.make_directory("ReactOS")
	fat.make_directory("ReactOS/system32")
	fat.copy_in(stock_file, "ReactOS/system32/win32k.sys")
	expected = patch_win32k_with(stock, monkeypatch)
	monkeypatch.setattr(patch_colours, "RESULT_SHA256", sha(expected))
	tree = tmp_path / "tree"
	tree.mkdir()
	files = tmp_path / "files"
	files.mkdir()
	(files / "afterglow.reg").write_text(STYLE_REG)
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	return fat, tree, files, scratch, stock, expected


def patch_win32k_with(stock: bytes, monkeypatch) -> bytes:
	monkeypatch.setattr(patch_colours, "STOCK_SHA256", (sha(stock),))
	return patch_win32k(stock, COLOURS)


def test_the_reg_file_colours_are_read_from_the_current_users_colours_sections_only():
	assert afterglow_colours(STYLE_REG) == COLOURS


def test_the_stock_table_has_one_name_per_entry():
	assert len(STOCK_TABLE) == len(VALUE_NAMES) == 31
	assert VALUE_NAMES.index("Background") == 1 and STOCK_TABLE[1] == (58, 110, 165)


def test_only_the_named_entries_change_and_the_checksum_is_right(setup, tmp_path):
	fat, tree, files, scratch, stock, expected = setup
	patched = run_patchers(["afterglow.colours"], fat, tree, files, scratch)
	assert [item.image_path for item in patched] == ["ReactOS/system32/win32k.sys"]
	data = patched[0].local_file.read_bytes()
	assert data == expected and len(data) == len(stock)
	assert table(COLOURS) in data and table() not in data
	pe = PeFile(data)
	assert int.from_bytes(data[pe.checksum_offset : pe.checksum_offset + 4], "little") == pe_checksum(data, pe.checksum_offset)


def test_the_golden_disk_is_not_touched(setup):
	fat, tree, files, scratch, _stock, _expected = setup
	before = sha(fat.image.read_bytes())
	run_patchers(["afterglow.colours"], fat, tree, files, scratch)
	assert sha(fat.image.read_bytes()) == before


def test_another_win32k_is_refused(setup, tmp_path):
	fat, tree, files, scratch, stock, _expected = setup
	changed = tmp_path / "changed.sys"
	changed.write_bytes(stock + b"\0")
	fat.copy_in(changed, "ReactOS/system32/win32k.sys")
	with pytest.raises(PatchError, match="refused"):
		run_patchers(["afterglow.colours"], fat, tree, files, scratch)


def test_a_table_that_is_missing_or_repeated_is_refused(monkeypatch):
	for stock in (win32k(with_table=b"\0" * 124), win32k(copies=2)):
		monkeypatch.setattr(patch_colours, "STOCK_SHA256", (sha(stock),))
		with pytest.raises(PatchError, match="not once"):
			patch_win32k(stock, COLOURS)


def test_a_style_file_without_a_desktop_colour_is_refused(monkeypatch):
	stock = win32k()
	monkeypatch.setattr(patch_colours, "STOCK_SHA256", (sha(stock),))
	with pytest.raises(PatchError, match="Background"):
		patch_win32k(stock, {"ActiveTitle": (1, 2, 3)})


def test_a_result_that_does_not_match_the_pin_is_refused(setup, monkeypatch):
	fat, tree, files, scratch, _stock, _expected = setup
	monkeypatch.setattr(patch_colours, "RESULT_SHA256", "0" * 64)
	with pytest.raises(PatchError, match="expected"):
		run_patchers(["afterglow.colours"], fat, tree, files, scratch)
	assert not (scratch / "win32k-afterglow.sys").exists()
