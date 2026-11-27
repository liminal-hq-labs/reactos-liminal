# Tests for the logon patcher on a synthetic msgina.dll and a fake Afterglow tree whose renderer writes known bitmaps.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib

import pytest
from pe_fixture import bmp_file, make_dib, make_pe

from reactos_liminal import patch_logon
from reactos_liminal.patch_base import PatchError
from reactos_liminal.patchers import run_patchers
from reactos_liminal.pe_resource import PeFile, dib_from_bmp, replace_bitmap

STOCK_BANNER = make_dib(413, 72, 24, fill=0x10)
STOCK_BAR = make_dib(413, 5, 24, fill=0x20)
NEW_BANNER = bmp_file(make_dib(413, 72, 24, fill=0xA1))
NEW_BAR = bmp_file(make_dib(413, 5, 24, fill=0xB2))


def sha(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


@pytest.fixture
def setup(fat, tmp_path, monkeypatch):
	stock = make_pe({20000: STOCK_BANNER, 20001: STOCK_BAR, 20002: make_dib(48, 40, 24)})
	stock_file = tmp_path / "msgina.dll"
	stock_file.write_bytes(stock)
	fat.make_directory("ReactOS")
	fat.make_directory("ReactOS/system32")
	fat.copy_in(stock_file, "ReactOS/system32/msgina.dll")
	expected = replace_bitmap(replace_bitmap(stock, 20000, dib_from_bmp(NEW_BANNER), True), 20001, dib_from_bmp(NEW_BAR), True)
	monkeypatch.setattr(patch_logon, "STOCK_SHA256", (sha(stock),))
	monkeypatch.setattr(patch_logon, "RESULT_SHA256", sha(expected))
	tree = tmp_path / "tree"
	art = tree / "desktop" / "logon"
	art.mkdir(parents=True)
	(art / "banner.bmp").write_bytes(NEW_BANNER)
	(art / "bar.bmp").write_bytes(NEW_BAR)
	(art / "render.py").write_text(
		"import shutil, sys\n"
		f"shutil.copy({str(art / 'banner.bmp')!r}, sys.argv[1] + '/afterglow-banner.bmp')\n"
		f"shutil.copy({str(art / 'bar.bmp')!r}, sys.argv[1] + '/afterglow-bar.bmp')\n"
	)
	write_sums(art, NEW_BANNER, NEW_BAR)
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	return fat, tree, scratch, expected, stock


def write_sums(art, banner, bar):
	(art / "SHA256SUMS").write_text(f"{sha(banner)}  afterglow-banner.bmp\n{sha(bar)}  afterglow-bar.bmp\n")


def test_the_patched_copy_is_written_as_agmsgina_with_the_afterglow_bitmaps(setup, tmp_path):
	fat, tree, scratch, expected, _stock = setup
	patched = run_patchers(["afterglow.logon"], fat, tree, tmp_path, scratch)
	assert [item.image_path for item in patched] == ["ReactOS/system32/agmsgina.dll"]
	assert patched[0].local_file.read_bytes() == expected
	pe = PeFile(expected)
	slot = pe.bitmap(20000)
	assert expected[slot.data_offset : slot.data_offset + slot.size] == dib_from_bmp(NEW_BANNER)


def test_the_stock_msgina_and_the_golden_disk_are_not_touched(setup, tmp_path):
	fat, tree, scratch, _expected, _stock = setup
	before = sha(fat.image.read_bytes())
	run_patchers(["afterglow.logon"], fat, tree, tmp_path, scratch)
	assert sha(fat.image.read_bytes()) == before


def test_a_changed_stock_file_is_refused(setup, tmp_path):
	fat, tree, scratch, _expected, stock = setup
	changed = tmp_path / "changed.dll"
	changed.write_bytes(stock[:-1] + bytes([stock[-1] ^ 1]))
	fat.copy_in(changed, "ReactOS/system32/msgina.dll")
	with pytest.raises(PatchError, match="refused"):
		run_patchers(["afterglow.logon"], fat, tree, tmp_path, scratch)
	assert not (scratch / "agmsgina.dll").exists()


def test_any_file_but_the_real_msgina_is_refused_by_the_built_in_guard(fat, setup, tmp_path, monkeypatch):
	_fat, tree, scratch, _expected, stock = setup
	monkeypatch.undo()
	with pytest.raises(PatchError, match="refused"):
		run_patchers(["afterglow.logon"], fat, tree, tmp_path, scratch)


def test_a_result_that_misses_its_pin_is_refused_and_leaves_no_file(setup, tmp_path, monkeypatch):
	fat, tree, scratch, _expected, _stock = setup
	monkeypatch.setattr(patch_logon, "RESULT_SHA256", "0" * 64)
	with pytest.raises(PatchError, match="expected"):
		run_patchers(["afterglow.logon"], fat, tree, tmp_path, scratch)
	assert not (scratch / "agmsgina.dll").exists()


def test_art_that_does_not_match_afterglows_sums_is_refused(setup, tmp_path):
	fat, tree, scratch, _expected, _stock = setup
	(tree / "desktop" / "logon" / "SHA256SUMS").write_text("0" * 64 + "  afterglow-banner.bmp\n" + "0" * 64 + "  afterglow-bar.bmp\n")
	with pytest.raises(PatchError, match="Afterglow records"):
		run_patchers(["afterglow.logon"], fat, tree, tmp_path, scratch)


def test_a_banner_of_the_wrong_size_is_refused(setup, tmp_path):
	fat, tree, scratch, _expected, _stock = setup
	art = tree / "desktop" / "logon"
	wrong = bmp_file(make_dib(412, 72, 24))
	(art / "banner.bmp").write_bytes(wrong)
	write_sums(art, wrong, NEW_BAR)
	with pytest.raises(PatchError, match="413 x 72"):
		run_patchers(["afterglow.logon"], fat, tree, tmp_path, scratch)


def test_a_msgina_whose_bitmap_has_another_shape_is_refused(setup, tmp_path, monkeypatch):
	fat, tree, scratch, _expected, _stock = setup
	odd = make_pe({20000: make_dib(100, 72, 24), 20001: STOCK_BAR})
	odd_file = tmp_path / "odd.dll"
	odd_file.write_bytes(odd)
	fat.copy_in(odd_file, "ReactOS/system32/msgina.dll")
	monkeypatch.setattr(patch_logon, "STOCK_SHA256", (sha(odd),))
	with pytest.raises(PatchError, match="resource 20000"):
		run_patchers(["afterglow.logon"], fat, tree, tmp_path, scratch)
