# Hash-checked downloads: every input is verified against its pinned SHA-256 before it is used, and nothing is kept on a mismatch.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path

from .log import log
from .paths import ensure
from .recipe import Recipe


class FetchError(Exception):
	"""A download or an input that does not match its pin."""


def sha256_file(path: str | Path) -> str:
	digest = hashlib.sha256()
	with open(path, "rb") as source:
		for block in iter(lambda: source.read(1 << 20), b""):
			digest.update(block)
	return digest.hexdigest()


def has_hash(path: Path, expected_sha256: str) -> bool:
	return path.is_file() and sha256_file(path) == expected_sha256


def download(url: str, destination: Path, expected_sha256: str) -> Path:
	"""Download `url` to `destination`, keeping it only when its SHA-256 matches. `file://` URLs work, for tests and local mirrors."""
	if has_hash(destination, expected_sha256):
		return destination
	partial = destination.with_name(destination.name + ".part")
	destination.parent.mkdir(parents=True, exist_ok=True)
	log("fetch", f"downloading {url}")
	try:
		with urllib.request.urlopen(url, timeout=60) as response, open(partial, "wb") as target:
			shutil.copyfileobj(response, target, 1 << 20)
		actual = sha256_file(partial)
		if actual != expected_sha256:
			raise FetchError(f"{url}: SHA-256 is {actual}, expected {expected_sha256}; the download was discarded")
		partial.replace(destination)
	finally:
		partial.unlink(missing_ok=True)
	return destination


def extract_member(archive: Path, member_name: str, destination: Path) -> None:
	"""Write one named file out of a zip. The name must be a plain file name: no folder, no `..`."""
	if "/" in member_name or "\\" in member_name or member_name in ("", ".", ".."):
		raise FetchError(f"unsafe archive member name: {member_name!r}")
	partial = destination.with_name(destination.name + ".part")
	try:
		with zipfile.ZipFile(archive) as bundle:
			if member_name not in bundle.namelist():
				raise FetchError(f"{archive.name} has no {member_name}")
			with bundle.open(member_name) as source, open(partial, "wb") as target:
				shutil.copyfileobj(source, target, 1 << 20)
		partial.replace(destination)
	finally:
		partial.unlink(missing_ok=True)


def fetch_iso(recipe: Recipe, work: Path, iso: Path | None = None) -> Path:
	"""The pinned install ISO. A given `iso` or one already in the work directory is used when its hash matches; otherwise the zip is
	downloaded, checked, and the ISO is taken out of it and checked too."""
	pin = recipe.section("inputs", "reactos_iso")
	if iso is not None:
		if not has_hash(iso, pin["sha256"]):
			raise FetchError(f"{iso}: not the pinned ISO (expected SHA-256 {pin['sha256']})")
		return iso
	downloads = ensure(work, "dl")
	cached = downloads / pin["name"]
	if has_hash(cached, pin["sha256"]):
		log("fetch", f"ISO already in {cached}")
		return cached
	archive = downloads / (pin["name"] + ".zip")
	download(pin["url"], archive, pin["zip_sha256"])
	extract_member(archive, pin["name"], cached)
	archive.unlink()
	if not has_hash(cached, pin["sha256"]):
		cached.unlink()
		raise FetchError(f"{pin['name']} in the zip is not the pinned ISO; it was discarded")
	return cached
