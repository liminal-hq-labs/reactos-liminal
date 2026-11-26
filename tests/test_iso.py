# Tests for `rl iso`: the official ISO with a session appended, checked on a tiny synthetic ISO built with xorriso.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import shutil
import subprocess

import pytest

from reactos_liminal.fetch import FetchError
from reactos_liminal.iso import IsoError, build_iso
from reactos_liminal.isopatch import find_file
from reactos_liminal.licences import ChangeRecord, write_licence_files
from reactos_liminal.mtools import FatImage
from reactos_liminal.recipe import load

pytestmark = pytest.mark.skipif(shutil.which("xorriso") is None, reason="needs xorriso")


@pytest.fixture
def setup(tmp_path, fat):
	"""A small official ISO, a recipe pinned to it, and an image that holds the licence files. Returns (recipe, work, image, iso)."""
	source = tmp_path / "source"
	(source / "i386").mkdir(parents=True)
	(source / "i386" / "FIRST.TXT").write_bytes(b"first session\n" * 500)
	(source / "readme.txt").write_text("official\n")
	(source / "loader").mkdir()
	(source / "loader" / "isoboot.bin").write_bytes(b"\x90" * 2048)
	iso = tmp_path / "work" / "dl" / "TEST.iso"
	iso.parent.mkdir(parents=True)
	subprocess.run(
		["xorriso", "-as", "mkisofs", "-V", "REACTOS", "-b", "loader/isoboot.bin", "-no-emul-boot", "-o", str(iso), str(source)],
		check=True,
		capture_output=True,
	)
	digest = hashlib.sha256(iso.read_bytes()).hexdigest()
	recipe_path = tmp_path / "recipe.toml"
	recipe_path.write_text(
		f'[recipe]\nname = "test"\n[inputs.reactos_iso]\nname = "TEST.iso"\nurl = "file:///nowhere"\nzip_sha256 = "{"0" * 64}"\nsha256 = "{digest}"\n'
	)
	recipe = load(recipe_path)
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	write_licence_files(fat, recipe, ChangeRecord(), scratch)
	return recipe, tmp_path / "work", fat.image, iso


def test_the_remaster_keeps_the_first_session_and_adds_the_notices(setup, tmp_path):
	recipe, work, image, iso = setup
	out = tmp_path / "out" / "remaster.iso"
	before = iso.read_bytes()
	lba_before = find_file(iso, "/i386/FIRST.TXT")
	assert build_iso(recipe, work, image, out) == out
	assert iso.read_bytes() == before  # the official ISO is only read
	# The system area (the boot record) and the first session's file data are byte for byte where they were, so the boot loader's view of
	# the disc is unchanged; only the volume descriptors move on to describe the second session.
	after = out.read_bytes()
	assert after[:32768] == before[:32768]
	assert find_file(out, "/i386/FIRST.TXT") == lba_before
	start, size = lba_before
	assert after[start * 2048 : start * 2048 + size] == before[start * 2048 : start * 2048 + size] == b"first session\n" * 500
	boot = subprocess.run(["xorriso", "-indev", str(out), "-report_el_torito", "plain"], capture_output=True, text=True, check=True).stdout
	assert "/loader/isoboot.bin" in boot  # the boot entry survives the new session
	listing = subprocess.run(["xorriso", "-indev", str(out), "-find", "/", "-type", "f"], capture_output=True, text=True, check=True).stdout
	for name in ("/NOTICE.txt", "/CHANGES.txt", "/LICENSES/GPL-2.0.txt", "/LICENSES/LGPL-2.1.txt", "/readme.txt"):
		assert name in listing, name


def test_a_wrong_iso_is_refused(setup, tmp_path):
	recipe, work, image, iso = setup
	other = tmp_path / "other.iso"
	other.write_bytes(b"x")
	with pytest.raises(FetchError, match="pinned ISO"):
		build_iso(recipe, work, image, tmp_path / "o.iso", other)


def test_the_output_may_not_be_the_official_iso(setup):
	recipe, work, image, iso = setup
	with pytest.raises(IsoError, match="official"):
		build_iso(recipe, work, image, iso)


def test_an_image_without_the_notices_is_refused(setup, tmp_path):
	recipe, work, image, iso = setup
	bare = tmp_path / "bare.img"
	from tests.conftest import make_fat_image

	make_fat_image(bare)
	with pytest.raises(IsoError, match="rl image"):
		build_iso(recipe, work, bare, tmp_path / "o.iso")
	assert FatImage(image).exists("NOTICE.txt")
