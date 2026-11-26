# Shared fixtures: a small recipe that points at a synthetic ISO inside a zip, so no ReactOS file is ever needed.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reactos_liminal.recipe import load  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
ISO_NAME = "TEST.iso"
ISO_BYTES = b"not a real ISO, just bytes\n" * 100


def sha256_bytes(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


@pytest.fixture
def base_recipe_path() -> Path:
	return REPO / "recipes" / "afterglow.toml"


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
