# Tests for the pinned Afterglow fetch and prepare steps, on a local tarball and a fake source tree (no network).
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import gzip
import hashlib
import io
import tarfile

import pytest

from reactos_liminal.afterglow import fetch_afterglow, prepare_afterglow, source_url
from reactos_liminal.fetch import FetchError
from reactos_liminal.recipe import load

STYLE_BUILD = b'#!/bin/bash\nmkdir -p "$1"\nprintf "style" > "$1/afterglow.msstyles"\n'
CURSOR_BUILD = b'import sys, pathlib\nfor number in range(16):\n\tpathlib.Path(sys.argv[1], f"p{number}.cur").write_bytes(b"cur")\n'


def make_tar(members, extra=None):
	"""A gzip'd tar of {name: bytes} under one top folder, as GitHub serves a commit. Returns (gz bytes, sha256 of the tar)."""
	raw = io.BytesIO()
	with tarfile.open(fileobj=raw, mode="w") as archive:
		for name, data in members.items():
			info = tarfile.TarInfo("top-abc/" + name)
			info.size = len(data)
			archive.addfile(info, io.BytesIO(data))
		for info, data in extra or []:
			archive.addfile(info, io.BytesIO(data) if data is not None else None)
	tar = raw.getvalue()
	return gzip.compress(tar, mtime=0), hashlib.sha256(tar).hexdigest()


FILES = {
	"desktop/style/build.sh": STYLE_BUILD,
	"desktop/install/afterglow-original.reg": b"REGEDIT4 style\n",
	"desktop/pointers/gen-cursors.py": CURSOR_BUILD,
	"desktop/pointers/afterglow-pointers.reg": b"REGEDIT4 pointers\n",
}


@pytest.fixture
def pinned(fake_iso_recipe):
	"""The test recipe with an Afterglow input pinned to FILES. Returns (recipe, tarball bytes)."""
	recipe, _, _ = fake_iso_recipe
	gz, tar_sha = make_tar(FILES)
	recipe.data["inputs"]["afterglow"] = {
		"repo": "x/y",
		"commit": "a" * 40,
		"tar_sha256": tar_sha,
		"msstyles_sha256": hashlib.sha256(b"style").hexdigest(),
		"apply_reg": "desktop/install/afterglow-original.reg",
	}
	return recipe, gz


def write(tmp_path, data):
	path = tmp_path / "src.tar.gz"
	path.write_bytes(data)
	return path


def test_the_url_names_the_commit(pinned):
	assert source_url(pinned[0]) == "https://codeload.github.com/x/y/tar.gz/" + "a" * 40


def test_a_good_tarball_is_extracted_and_remembered(pinned, tmp_path):
	recipe, gz = pinned
	tree = fetch_afterglow(recipe, tmp_path / "work", write(tmp_path, gz))
	assert tree == tmp_path / "work" / "afterglow" / ("a" * 40)
	assert (tree / "desktop" / "style" / "build.sh").is_file()
	assert fetch_afterglow(recipe, tmp_path / "work") == tree  # reused: no tarball and no network needed


def test_a_changed_tarball_is_refused_and_leaves_nothing(pinned, tmp_path):
	recipe, _ = pinned
	other, _ = make_tar({**FILES, "extra": b"x"})
	with pytest.raises(FetchError, match="expected"):
		fetch_afterglow(recipe, tmp_path / "work", write(tmp_path, other))
	assert not (tmp_path / "work" / "afterglow" / ("a" * 40)).exists()


def test_recompressing_does_not_matter_because_the_pin_is_of_the_tar(pinned, tmp_path):
	recipe, gz = pinned
	recompressed = gzip.compress(gzip.decompress(gz), 1, mtime=12345)
	assert fetch_afterglow(recipe, tmp_path / "work", write(tmp_path, recompressed)).is_dir()


@pytest.mark.parametrize("bad_name", ["top-abc/../evil", "/abs"])
def test_an_unsafe_member_is_refused(pinned, tmp_path, bad_name):
	recipe, _ = pinned
	info = tarfile.TarInfo(bad_name)
	info.size = 1
	gz, tar_sha = make_tar(FILES, [(info, b"x")])
	recipe.data["inputs"]["afterglow"]["tar_sha256"] = tar_sha
	with pytest.raises(FetchError, match="unsafe"):
		fetch_afterglow(recipe, tmp_path / "work", write(tmp_path, gz))


def test_a_link_member_is_refused(pinned, tmp_path):
	recipe, _ = pinned
	info = tarfile.TarInfo("top-abc/link")
	info.type = tarfile.SYMTYPE
	info.linkname = "/etc/passwd"
	gz, tar_sha = make_tar(FILES, [(info, None)])
	recipe.data["inputs"]["afterglow"]["tar_sha256"] = tar_sha
	with pytest.raises(FetchError, match="link"):
		fetch_afterglow(recipe, tmp_path / "work", write(tmp_path, gz))


def test_an_archive_without_the_style_build_is_refused(pinned, tmp_path):
	recipe, _ = pinned
	gz, tar_sha = make_tar({"README.md": b"hi"})
	recipe.data["inputs"]["afterglow"]["tar_sha256"] = tar_sha
	with pytest.raises(FetchError, match="build.sh"):
		fetch_afterglow(recipe, tmp_path / "work", write(tmp_path, gz))


def test_prepare_builds_the_files_and_checks_the_style_hash(pinned, tmp_path):
	recipe, gz = pinned
	work = tmp_path / "work"
	tree = fetch_afterglow(recipe, work, write(tmp_path, gz))
	output = prepare_afterglow(recipe, work, tree)
	assert (output / "afterglow.msstyles").read_bytes() == b"style"
	assert (output / "afterglow.reg").read_bytes() == b"REGEDIT4 style\n"
	assert (output / "pointers.reg").read_bytes() == b"REGEDIT4 pointers\n"
	assert len(list((output / "cursors").iterdir())) == 16


def test_prepare_refuses_a_style_that_differs_from_the_pin(pinned, tmp_path):
	recipe, gz = pinned
	work = tmp_path / "work"
	tree = fetch_afterglow(recipe, work, write(tmp_path, gz))
	recipe.data["inputs"]["afterglow"]["msstyles_sha256"] = "0" * 64
	with pytest.raises(FetchError, match="toolchain or the source differs"):
		prepare_afterglow(recipe, work, tree)


def test_the_base_recipe_pins_load():
	from tests.conftest import REPO

	pin = load(REPO / "recipes" / "afterglow.toml").section("inputs", "afterglow")
	assert pin["repo"] == "liminal-hq/afterglow-themes" and len(pin["commit"]) == 40
