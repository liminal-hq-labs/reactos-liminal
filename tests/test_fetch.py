# Tests for the hash-checked downloads, run on file:// URLs and a synthetic zip.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import zipfile

import pytest

from reactos_liminal.fetch import FetchError, download, extract_member, fetch_iso, sha256_file


def test_iso_is_downloaded_checked_and_extracted(fake_iso_recipe, tmp_path):
	recipe, archive, iso_bytes = fake_iso_recipe
	work = tmp_path / "work"
	iso = fetch_iso(recipe, work)
	assert iso == work / "dl" / "TEST.iso"
	assert iso.read_bytes() == iso_bytes
	assert not (work / "dl" / "TEST.iso.zip").exists()
	assert not list((work / "dl").glob("*.part"))


def test_a_cached_iso_is_reused_without_downloading(fake_iso_recipe, tmp_path):
	recipe, archive, _ = fake_iso_recipe
	work = tmp_path / "work"
	fetch_iso(recipe, work)
	archive.unlink()
	assert fetch_iso(recipe, work).is_file()


def test_own_iso_is_checked_against_the_pin(fake_iso_recipe, tmp_path):
	recipe, _, iso_bytes = fake_iso_recipe
	good = tmp_path / "mine.iso"
	good.write_bytes(iso_bytes)
	assert fetch_iso(recipe, tmp_path / "work", good) == good
	bad = tmp_path / "other.iso"
	bad.write_bytes(iso_bytes + b"x")
	with pytest.raises(FetchError, match="not the pinned ISO"):
		fetch_iso(recipe, tmp_path / "work", bad)


def test_a_download_with_the_wrong_hash_is_discarded(tmp_path):
	source = tmp_path / "source.bin"
	source.write_bytes(b"payload")
	destination = tmp_path / "out" / "file.bin"
	with pytest.raises(FetchError, match="expected"):
		download(source.as_uri(), destination, "0" * 64)
	assert not destination.exists()
	assert not list((tmp_path / "out").glob("*.part"))


def test_a_tampered_zip_is_refused_before_extraction(fake_iso_recipe, tmp_path):
	recipe, archive, _ = fake_iso_recipe
	with zipfile.ZipFile(archive, "w") as bundle:
		bundle.writestr("TEST.iso", b"different")
	with pytest.raises(FetchError, match="SHA-256 is"):
		fetch_iso(recipe, tmp_path / "work")
	assert not (tmp_path / "work" / "dl" / "TEST.iso").exists()


def test_a_zip_holding_the_wrong_iso_is_discarded(fake_iso_recipe, tmp_path, monkeypatch):
	recipe, archive, _ = fake_iso_recipe
	recipe.data["inputs"]["reactos_iso"]["sha256"] = "1" * 64
	with pytest.raises(FetchError, match="not the pinned ISO"):
		fetch_iso(recipe, tmp_path / "work")
	assert not (tmp_path / "work" / "dl" / "TEST.iso").exists()


@pytest.mark.parametrize("name", ["../evil", "a/b", "", "..", "a\\b"])
def test_unsafe_member_names_are_refused(tmp_path, name):
	archive = tmp_path / "a.zip"
	with zipfile.ZipFile(archive, "w") as bundle:
		bundle.writestr("ok.txt", b"x")
	with pytest.raises(FetchError, match="unsafe"):
		extract_member(archive, name, tmp_path / "out")


def test_sha256_file(tmp_path):
	path = tmp_path / "f"
	path.write_bytes(b"abc")
	assert sha256_file(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
