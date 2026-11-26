# Tests for the boot patcher: the kernel logo on a synthetic kernel, and the FreeLoader menu on a synthetic freeldr.ini.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib

import pytest
from pe_fixture import bmp_file, make_dib, make_pe

from reactos_liminal import patch_boot
from reactos_liminal.patch_base import PatchError
from reactos_liminal.patch_boot import afterglow_menu
from reactos_liminal.patchers import run_patchers
from reactos_liminal.pe_resource import PeFile, dib_from_bmp, dib_info, replace_bitmap

STOCK_LOGO = make_dib(190, 224, 4, 2, pixels=b"\x01\x00" * 8200, colours=16)
NEW_LOGO = bmp_file(make_dib(414, 366, 4, 2, pixels=b"\x05\x11" * 600, colours=16))
STOCK_MENU = (
	b"[FREELOADER]\r\nTimeOut=3\r\nDefaultOS=ReactOS\r\n\r\n"
	b"[Display]\r\nTitleText=ReactOS Boot Manager\r\nMinimalUI=Yes\r\n\r\n"
	b'[Operating Systems]\r\nReactOS="ReactOS"\r\nReactOS_Debug="ReactOS (Debug)"\r\n\r\n'
	b"[ReactOS]\r\nBootType=Windows2003\r\nSystemPath=multi(0)disk(0)rdisk(0)partition(1)\\ReactOS\r\nOptions=/FASTDETECT\r\n\r\n"
	b"[ReactOS_Debug]\r\nBootType=Windows2003\r\nSystemPath=multi(0)disk(0)rdisk(0)partition(1)\\ReactOS\r\nOptions=/DEBUG\r\n"
)


def sha(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


def test_the_stock_logo_fixture_is_the_size_of_the_real_slot():
	assert len(STOCK_LOGO) == 16504


@pytest.fixture
def setup(fat, tmp_path, monkeypatch):
	kernel = make_pe({5: STOCK_LOGO, 6: make_dib(8, 8, 4)})
	kernel_file = tmp_path / "ntoskrnl.exe"
	kernel_file.write_bytes(kernel)
	menu_file = tmp_path / "freeldr.ini"
	menu_file.write_bytes(STOCK_MENU)
	fat.make_directory("ReactOS")
	fat.make_directory("ReactOS/system32")
	fat.copy_in(kernel_file, "ReactOS/system32/ntoskrnl.exe")
	fat.copy_in(menu_file, "freeldr.ini")
	expected_kernel = replace_bitmap(kernel, 5, dib_from_bmp(NEW_LOGO), same_size=False)
	monkeypatch.setattr(patch_boot, "KERNEL_SHA256", (sha(kernel),))
	monkeypatch.setattr(patch_boot, "KERNEL_RESULT_SHA256", sha(expected_kernel))
	monkeypatch.setattr(patch_boot, "MENU_STOCK_SHA256", (sha(STOCK_MENU),))
	monkeypatch.setattr(patch_boot, "MENU_RESULT_SHA256", sha(afterglow_menu(STOCK_MENU)))
	tree = tmp_path / "tree"
	art = tree / "desktop" / "boot"
	art.mkdir(parents=True)
	(art / "logo.bmp").write_bytes(NEW_LOGO)
	(art / "render.py").write_text(
		f"import shutil, sys\nshutil.copy({str(art / 'logo.bmp')!r}, sys.argv[1] + '/afterglow-logo-rle4.bmp')\n"
	)
	(art / "SHA256SUMS").write_text(f"{sha(NEW_LOGO)}  afterglow-logo-rle4.bmp\n")
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	return fat, tree, scratch, kernel, expected_kernel


def test_the_kernel_copy_carries_the_new_logo_and_the_menu_starts_it(setup, tmp_path):
	fat, tree, scratch, kernel, expected = setup
	patched = run_patchers(["afterglow.boot"], fat, tree, tmp_path, scratch)
	assert [item.image_path for item in patched] == ["ReactOS/system32/agntoskr.exe", "freeldr.ini"]
	assert patched[0].local_file.read_bytes() == expected
	slot = PeFile(expected).bitmap(5)
	assert dib_info(expected[slot.data_offset :]).width == 414
	assert slot.size == len(dib_from_bmp(NEW_LOGO)) and slot.size < len(STOCK_LOGO)
	assert patched[1].attributes == "+h +s"
	assert b"Kernel=agntoskr.exe" in patched[1].local_file.read_bytes()
	assert len(expected) == len(kernel)


def test_the_golden_disk_is_only_read(setup, tmp_path):
	fat, tree, scratch, _kernel, _expected = setup
	before = sha(fat.image.read_bytes())
	run_patchers(["afterglow.boot"], fat, tree, tmp_path, scratch)
	assert sha(fat.image.read_bytes()) == before


def test_a_changed_kernel_is_refused(setup, tmp_path):
	fat, tree, scratch, kernel, _expected = setup
	changed = tmp_path / "changed.exe"
	changed.write_bytes(kernel[:-1] + bytes([kernel[-1] ^ 1]))
	fat.copy_in(changed, "ReactOS/system32/ntoskrnl.exe")
	with pytest.raises(PatchError, match="refused"):
		run_patchers(["afterglow.boot"], fat, tree, tmp_path, scratch)


def test_any_file_but_the_real_kernel_is_refused_by_the_built_in_guard(setup, tmp_path, monkeypatch):
	fat, tree, scratch, _kernel, _expected = setup
	monkeypatch.undo()
	with pytest.raises(PatchError, match="refused"):
		run_patchers(["afterglow.boot"], fat, tree, tmp_path, scratch)


def test_a_kernel_whose_logo_is_not_the_stock_one_is_refused(setup, tmp_path, monkeypatch):
	fat, tree, scratch, _kernel, _expected = setup
	odd = make_pe({5: make_dib(100, 100, 4, 2, pixels=b"\x01\x00" * 100, colours=16)})
	odd_file = tmp_path / "odd.exe"
	odd_file.write_bytes(odd)
	fat.copy_in(odd_file, "ReactOS/system32/ntoskrnl.exe")
	monkeypatch.setattr(patch_boot, "KERNEL_SHA256", (sha(odd),))
	with pytest.raises(PatchError, match="not the stock"):
		run_patchers(["afterglow.boot"], fat, tree, tmp_path, scratch)


def test_a_logo_that_does_not_fit_the_screen_or_the_slot_is_refused(setup, tmp_path):
	fat, tree, scratch, _kernel, _expected = setup
	art = tree / "desktop" / "boot"
	big = bmp_file(make_dib(414, 366, 4, 2, pixels=b"\x05\x11" * 9000, colours=16))
	(art / "logo.bmp").write_bytes(big)
	(art / "SHA256SUMS").write_text(f"{sha(big)}  afterglow-logo-rle4.bmp\n")
	with pytest.raises(PatchError, match="slot holds"):
		run_patchers(["afterglow.boot"], fat, tree, tmp_path, scratch)


def test_an_uncompressed_logo_is_refused(setup, tmp_path):
	fat, tree, scratch, _kernel, _expected = setup
	art = tree / "desktop" / "boot"
	plain = bmp_file(make_dib(414, 366, 4, 0, pixels=b"\0" * 10, colours=16))
	(art / "logo.bmp").write_bytes(plain)
	(art / "SHA256SUMS").write_text(f"{sha(plain)}  afterglow-logo-rle4.bmp\n")
	with pytest.raises(PatchError, match="RLE4"):
		run_patchers(["afterglow.boot"], fat, tree, tmp_path, scratch)


def test_a_changed_menu_is_refused(setup, tmp_path):
	fat, tree, scratch, _kernel, _expected = setup
	changed = tmp_path / "changed.ini"
	changed.write_bytes(STOCK_MENU.replace(b"TimeOut=3", b"TimeOut=4"))
	fat.set_attributes("freeldr.ini", "-r -h -s")
	fat.copy_in(changed, "freeldr.ini")
	with pytest.raises(PatchError, match="freeldr.ini"):
		run_patchers(["afterglow.boot"], fat, tree, tmp_path, scratch)


def test_a_result_that_misses_its_pin_is_refused(setup, tmp_path, monkeypatch):
	fat, tree, scratch, _kernel, _expected = setup
	monkeypatch.setattr(patch_boot, "KERNEL_RESULT_SHA256", "0" * 64)
	with pytest.raises(PatchError, match="expected"):
		run_patchers(["afterglow.boot"], fat, tree, tmp_path, scratch)
	assert not (scratch / "agntoskr.exe").exists()


def test_the_menu_makes_afterglow_the_default_and_keeps_the_stock_entry_as_the_fallback():
	text = afterglow_menu(STOCK_MENU).decode().split("\r\n")
	assert "DefaultOS=Afterglow" in text and "TimeOut=10" in text
	assert 'Afterglow="ReactOS (Afterglow)"' in text
	assert 'ReactOS="ReactOS"' in text
	assert text.index('Afterglow="ReactOS (Afterglow)"') < text.index('ReactOS="ReactOS"')
	assert "TitleText=ReactOS Boot Manager" not in text
	assert {"MinimalUI=Yes", "SelectedColor=Brown", "SelectedTextColor=Black"} <= set(text)
	afterglow = text.index("[Afterglow]")
	assert text[afterglow : afterglow + 5] == [
		"[Afterglow]",
		"BootType=Windows2003",
		"SystemPath=multi(0)disk(0)rdisk(0)partition(1)\\ReactOS",
		"Options=/FASTDETECT",
		"Kernel=agntoskr.exe",
	]


def test_the_stock_entry_and_the_other_entries_are_unchanged():
	text = afterglow_menu(STOCK_MENU).decode()
	stock_block = "[ReactOS]\r\nBootType=Windows2003\r\nSystemPath=multi(0)disk(0)rdisk(0)partition(1)\\ReactOS\r\nOptions=/FASTDETECT\r\n"
	assert stock_block in text and "Kernel=" not in text.split("[ReactOS]")[1].split("[")[0]
	assert (
		"[ReactOS_Debug]\r\nBootType=Windows2003\r\nSystemPath=multi(0)disk(0)rdisk(0)partition(1)\\ReactOS\r\nOptions=/DEBUG\r\n" in text
	)
	assert text.endswith("\r\n") and "\n" not in text.replace("\r\n", "")


def test_a_menu_with_no_stock_entry_is_refused():
	with pytest.raises(PatchError, match="no place"):
		afterglow_menu(b"[FREELOADER]\r\nTimeOut=3\r\nDefaultOS=ReactOS\r\n")
