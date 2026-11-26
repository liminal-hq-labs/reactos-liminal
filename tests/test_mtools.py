# Tests for the FAT32 helper, on a tiny FAT image made in the test.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import os
import shutil

import pytest

from reactos_liminal.mtools import MtoolsError

pytestmark = pytest.mark.skipif(shutil.which("mformat") is None, reason="needs mtools")


def test_copy_read_and_delete(fat, tmp_path):
	source = tmp_path / "a.txt"
	source.write_bytes(b"hello")
	fat.make_directory("ReactOS")
	fat.make_directory("ReactOS")  # again: fine
	fat.make_directory("ReactOS/sub")
	fat.copy_in(source, "ReactOS/sub/a.txt")
	assert fat.exists("ReactOS/sub/a.txt") and not fat.exists("ReactOS/nope.txt")
	assert fat.read("ReactOS/sub/a.txt") == b"hello"
	out = tmp_path / "out.txt"
	fat.copy_out("ReactOS/sub/a.txt", out)
	assert out.read_bytes() == b"hello"
	assert fat.delete_file("ReactOS/sub/a.txt") and not fat.delete_file("ReactOS/sub/a.txt")
	assert fat.delete_tree("ReactOS") and not fat.exists("ReactOS")


def test_free_space_grows_when_a_tree_is_deleted(fat, tmp_path):
	source = tmp_path / "big.bin"
	source.write_bytes(os.urandom(200_000))
	fat.make_directory("d")
	fat.copy_in(source, "d/big.bin")
	before = fat.free_bytes()
	fat.delete_tree("d")
	assert fat.free_bytes() >= before + 200_000


def test_a_failing_command_raises(fat):
	with pytest.raises(MtoolsError, match="mtype"):
		fat.read("missing.txt")
