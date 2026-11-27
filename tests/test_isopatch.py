# Tests for the in-place ISO edits, on synthetic files and a small ISO made with xorriso.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import shutil
import subprocess

import pytest

from reactos_liminal import isopatch
from reactos_liminal.isopatch import SECTOR, IsoPatchError

FREELDR = b"[FREELOADER]\r\nDefaultOS=LiveCD\r\nTimeOut=3\r\n\r\n[Setup]\r\n"


def test_text_file_is_padded_to_the_old_size():
	old = b"x" * 200
	new = isopatch.replace_text_file(old, b"[Unattend]\r\nA = 1")
	assert len(new) == 200
	assert new.startswith(b"[Unattend]\nA = 1\n;")
	assert new.endswith(b" ")


def test_text_file_that_does_not_fit_is_refused():
	with pytest.raises(IsoPatchError, match="holds"):
		isopatch.replace_text_file(b"x" * 10, b"y" * 20)


def test_default_os_keeps_the_size_with_blank_lines():
	new = isopatch.set_default_os(FREELDR, "Boot")
	assert len(new) == len(FREELDR)
	assert b"DefaultOS=Boot\r\n" in new
	assert b"DefaultOS=Boot\r\n\r\nTimeOut" in new  # the saved bytes became a blank line


def test_default_os_with_a_longer_name_is_refused():
	with pytest.raises(IsoPatchError, match="cannot keep the size"):
		isopatch.set_default_os(FREELDR, "AVeryLongEntryName")


def test_substitute_pads_with_spaces_and_wants_one_match():
	old = b"a /DEBUG /KDSERIAL b"
	assert isopatch.substitute(old, "/DEBUG /KDSERIAL", "/NODEBUG") == b"a /NODEBUG" + b" " * 8 + b" b"
	with pytest.raises(IsoPatchError):
		isopatch.substitute(old + old, "/DEBUG /KDSERIAL", "/NODEBUG")
	with pytest.raises(IsoPatchError):
		isopatch.substitute(old, "/DEBUG", "/MUCH-LONGER-THAN-THE-OLD-TEXT")


@pytest.mark.skipif(shutil.which("xorriso") is None, reason="needs xorriso")
def test_in_place_edit_changes_only_that_file(tmp_path):
	tree = tmp_path / "tree"
	(tree / "i386").mkdir(parents=True)
	(tree / "i386" / "unattend.inf").write_bytes(b"old answers\n" * 50)
	(tree / "other.txt").write_bytes(b"untouched\n" * 300)
	iso = tmp_path / "t.iso"
	subprocess.run(["xorriso", "-as", "mkisofs", "-quiet", "-o", str(iso), str(tree)], check=True, capture_output=True)
	before = iso.read_bytes()
	lba, size = isopatch.find_file(iso, "/i386/unattend.inf")
	assert size == 600
	isopatch.patch_in_place(iso, lba, size, lambda old: isopatch.replace_text_file(old, b"new answers"))
	after = iso.read_bytes()
	assert len(after) == len(before)
	assert after[lba * SECTOR : lba * SECTOR + 12] == b"new answers\n"
	changed = [index for index in range(0, len(before), SECTOR) if before[index : index + SECTOR] != after[index : index + SECTOR]]
	assert changed == [lba * SECTOR, (lba + 1) * SECTOR] or changed == [lba * SECTOR]
	with pytest.raises(IsoPatchError, match="not on"):
		isopatch.find_file(iso, "/missing")


def test_an_edit_that_changes_the_length_is_refused(tmp_path):
	image = tmp_path / "x.iso"
	image.write_bytes(bytes(SECTOR * 3))
	with pytest.raises(IsoPatchError, match="changed the size"):
		isopatch.patch_in_place(image, 1, 10, lambda old: old + b"x")
