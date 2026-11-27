# Shared fixtures: a small recipe that points at a synthetic ISO inside a zip, so no ReactOS file is ever needed.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reactos_liminal.mtools import PARTITION_OFFSET, FatImage  # noqa: E402
from reactos_liminal.recipe import load  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
ISO_NAME = "TEST.iso"
ISO_BYTES = b"not a real ISO, just bytes\n" * 100


def sha256_bytes(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


@pytest.fixture(scope="session", autouse=True)
def _probed_iso_writers():
	"""Look for the ISO writers once, before a test forbids starting processes: the golden disk's key names the writer."""
	from reactos_liminal.isobuild import writers_on_path

	writers_on_path()


@pytest.fixture
def base_recipe_path() -> Path:
	return REPO / "recipes" / "afterglow.toml"


@pytest.fixture
def compact_recipe_path() -> Path:
	return REPO / "recipes" / "afterglow-compact.toml"


@pytest.fixture
def fake_iso_recipe(tmp_path):
	"""A recipe whose ISO pin matches a synthetic zip served from a file:// URL. Returns (recipe, zip_path, iso_bytes)."""
	archive = tmp_path / "source" / "iso.zip"
	archive.parent.mkdir()
	with zipfile.ZipFile(archive, "w") as bundle:
		bundle.writestr(ISO_NAME, ISO_BYTES)
	recipe_path = tmp_path / "recipe.toml"
	recipe_path.write_text(
		f"""
[recipe]
name = "test"
[inputs.reactos_iso]
name = "{ISO_NAME}"
url = "{archive.as_uri()}"
zip_sha256 = "{sha256_bytes(archive.read_bytes())}"
sha256 = "{sha256_bytes(ISO_BYTES)}"
"""
	)
	return load(recipe_path), archive, ISO_BYTES


def make_fat_image(path, megabytes=8):
	"""A raw disk image with one small FAT partition at 1 MiB, made with mformat. Skips the test when mtools is missing."""
	import shutil

	if shutil.which("mformat") is None:
		pytest.skip("needs mtools")
	with open(path, "wb") as blank:
		blank.truncate(PARTITION_OFFSET + megabytes * 1024 * 1024)
	spec = f"{path}@@{PARTITION_OFFSET}"
	env = dict(os.environ, MTOOLS_SKIP_CHECK="1")
	subprocess.run(
		["mformat", "-i", spec, "-F", "-T", str(megabytes * 2048), "-h", "1", "-s", "1", "::"], check=True, capture_output=True, env=env
	)
	return FatImage(path)


@pytest.fixture
def fat(tmp_path):
	return make_fat_image(tmp_path / "disk.img")
