# Tests for `rl iso`: the official disc rebuilt from its tree with the Afterglow menu text and the image's notices, checked on a small
# synthetic disc that stands in for the official one.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib

import pytest
from iso_fixtures import FILES, LONG_NAME, have_writer, make_tree, stock_sums

from reactos_liminal import isotree
from reactos_liminal.fetch import FetchError
from reactos_liminal.iso import IsoError, build_iso
from reactos_liminal.isobuild import detect_writer, freeldr_lookup, read_primary_tree, write_iso
from reactos_liminal.licences import ChangeRecord, write_licence_files
from reactos_liminal.mtools import FatImage
from reactos_liminal.recipe import load

pytestmark = pytest.mark.skipif(not have_writer(), reason="needs xorriso and an ISO writer (mkisofs or genisoimage)")


@pytest.fixture
def setup(tmp_path, fat, monkeypatch):
	"""A small official disc, a recipe pinned to it, and an image that holds the licence files. Returns (recipe, work, image, iso)."""
	monkeypatch.setattr(isotree, "STOCK_SUMS", stock_sums())
	tree = make_tree(tmp_path / "official")
	iso = tmp_path / "work" / "dl" / "TEST.iso"
	write_iso(tree, iso, tmp_path / "official-scratch", detect_writer(), 1756425600)
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


def test_the_remaster_is_rebuilt_with_the_menu_the_notices_and_every_name_exact(setup, tmp_path):
	recipe, work, image, iso = setup
	out = tmp_path / "out" / "remaster.iso"
	before = iso.read_bytes()
	assert build_iso(recipe, work, image, out) == out
	assert iso.read_bytes() == before  # the official ISO is only read
	names = read_primary_tree(out)
	for path in ("NOTICE.txt", "CHANGES.txt", "LICENSES/GPL-2.0.txt", "LICENSES/LGPL-2.1.txt"):
		assert path in names, path
	# Names FreeLoader and the live environment need are as the official disc has them.
	assert freeldr_lookup(out, "reactos/system32/config/system") is not None
	assert "Profiles/Default User/ntuser.dat" in names
	assert f"reactos/winsxs/{LONG_NAME}" in names


def test_the_remaster_menu_names_afterglow_and_the_answers_are_not_on_it(setup, tmp_path):
	recipe, work, image, iso = setup
	out = tmp_path / "out.iso"
	build_iso(recipe, work, image, out)
	menu = freeldr_lookup(out, "freeldr.ini")
	data = out.read_bytes()[menu.extent * 2048 : menu.extent * 2048 + menu.size].decode()
	assert "ReactOS (Afterglow) Live Environment (Graphics Mode)" in data
	assert "DefaultOS=LiveImg" in data and "DefaultOS=Setup" not in data
	answers = freeldr_lookup(out, "i386/unattend.inf")
	assert out.read_bytes()[answers.extent * 2048 : answers.extent * 2048 + answers.size] == FILES["i386/unattend.inf"]
	text = freeldr_lookup(out, "i386/txtsetup.sif")
	assert b"/NODEBUG" not in out.read_bytes()[text.extent * 2048 : text.extent * 2048 + text.size]


def test_the_remaster_is_reproducible(setup, tmp_path, monkeypatch):
	recipe, work, image, iso = setup
	monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
	build_iso(recipe, work, image, tmp_path / "one.iso")
	build_iso(recipe, work, image, tmp_path / "two.iso")
	assert (tmp_path / "one.iso").read_bytes() == (tmp_path / "two.iso").read_bytes()
	monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
	build_iso(recipe, work, image, tmp_path / "three.iso")
	assert (tmp_path / "three.iso").read_bytes() != (tmp_path / "one.iso").read_bytes()


def test_no_tree_is_left_behind(setup, tmp_path):
	recipe, work, image, iso = setup
	build_iso(recipe, work, image, tmp_path / "out.iso")
	assert list((work / "scratch").iterdir()) == []


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
