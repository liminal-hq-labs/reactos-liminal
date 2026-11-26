# Tests for the pointer patcher on a tiny FAT disk and a fake Afterglow tree whose patch tool writes known bytes.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib

import pytest

from reactos_liminal.patchers import PatchError, run_patchers

PATCHED = b"patched-user32"


@pytest.fixture
def setup(fat, tmp_path):
	original = tmp_path / "user32.dll"
	original.write_bytes(b"original-user32")
	fat.make_directory("ReactOS")
	fat.make_directory("ReactOS/system32")
	fat.copy_in(original, "ReactOS/system32/user32.dll")
	tree = tmp_path / "tree"
	(tree / "desktop" / "pointers").mkdir(parents=True)
	(tree / "desktop" / "pointers" / "patch-user32.py").write_text(
		'import sys\nassert open(sys.argv[1], "rb").read() == b"original-user32", "not the stock file"\n'
		f"open(sys.argv[3], 'wb').write({PATCHED!r})\n"
	)
	files = tmp_path / "files"
	(files / "cursors").mkdir(parents=True)
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	return fat, tree, files, scratch


def write_sum(tree, sha):
	(tree / "desktop" / "pointers" / "SHA256SUMS.user32").write_text(f"{sha}  user32-afterglow.dll\n")


def test_the_patched_copy_is_returned_when_the_sum_matches(setup):
	fat, tree, files, scratch = setup
	write_sum(tree, hashlib.sha256(PATCHED).hexdigest())
	patched = run_patchers(["afterglow.pointers"], fat, tree, files, scratch)
	assert [item.image_path for item in patched] == ["ReactOS/system32/user32.dll"]
	assert patched[0].local_file.read_bytes() == PATCHED


def test_a_wrong_sum_is_refused_and_leaves_no_file(setup):
	fat, tree, files, scratch = setup
	write_sum(tree, "0" * 64)
	with pytest.raises(PatchError, match="expected"):
		run_patchers(["afterglow.pointers"], fat, tree, files, scratch)
	assert not (scratch / "user32-afterglow.dll").exists()


def test_a_changed_stock_file_is_refused_by_the_tool(setup, tmp_path):
	"""A one-byte-changed user32.dll: Afterglow's own tool refuses it, and so does the patcher."""
	fat, tree, files, scratch = setup
	write_sum(tree, hashlib.sha256(PATCHED).hexdigest())
	changed = tmp_path / "changed.dll"
	changed.write_bytes(b"original-user33")
	fat.copy_in(changed, "ReactOS/system32/user32.dll")
	with pytest.raises(PatchError, match="not the stock file"):
		run_patchers(["afterglow.pointers"], fat, tree, files, scratch)


def test_missing_cursors_are_reported(setup):
	fat, tree, files, scratch = setup
	(files / "cursors").rmdir()
	write_sum(tree, "0" * 64)
	with pytest.raises(PatchError, match="cursors"):
		run_patchers(["afterglow.pointers"], fat, tree, files, scratch)


def test_the_golden_disk_is_only_read(setup):
	fat, tree, files, scratch = setup
	write_sum(tree, hashlib.sha256(PATCHED).hexdigest())
	before = hashlib.sha256(fat.image.read_bytes()).hexdigest()
	run_patchers(["afterglow.pointers"], fat, tree, files, scratch)
	assert hashlib.sha256(fat.image.read_bytes()).hexdigest() == before


def test_a_patcher_without_afterglow_files_is_refused(fat, tmp_path):
	with pytest.raises(PatchError, match="needs the Afterglow files"):
		run_patchers(["afterglow.pointers"], fat, None, None, tmp_path)


def test_no_patchers_means_no_work(fat, tmp_path):
	assert run_patchers([], fat, None, None, tmp_path) == []
