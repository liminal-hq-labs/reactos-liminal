# The Afterglow desktop theme: fetch the pinned source, check it, and build the files the disk needs from it. Nothing of Afterglow is
# committed here; the source is pinned by commit and by the SHA-256 of the tar GitHub serves for it.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import gzip
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

from .fetch import FetchError, sha256_file
from .log import log
from .paths import ensure
from .recipe import Recipe

POINTER_FILES = 16  # 14 .cur and 2 .ani


def source_url(recipe: Recipe) -> str:
	pin = recipe.section("inputs", "afterglow")
	return f"https://codeload.github.com/{pin['repo']}/tar.gz/{pin['commit']}"


def _check_members(archive: tarfile.TarFile) -> None:
	for member in archive.getmembers():
		parts = member.name.split("/")
		if member.name.startswith("/") or ".." in parts:
			raise FetchError(f"the Afterglow archive has an unsafe path: {member.name!r}")
		if member.issym() or member.islnk() or member.isdev():
			raise FetchError(f"the Afterglow archive holds a link or device: {member.name!r}")


def fetch_afterglow(recipe: Recipe, work: Path, tarball: Path | None = None, trust: bool = False) -> Path:
	"""The pinned Afterglow source tree in the work directory. `tarball` is a local .tar.gz used instead of the download; the same hash
	check applies. A tree that is already extracted and checked is reused. `trust` is for `rl pin` alone: it accepts whatever tar
	the commit gives (the new sum is read back with `tree_tar_sha256`) instead of requiring the pinned one."""
	pin = recipe.section("inputs", "afterglow")
	cache = ensure(work, "afterglow")
	destination = cache / pin["commit"]
	marker = destination / ".verified"
	if marker.is_file() and (trust or marker.read_text().strip() == pin["tar_sha256"]):
		log("afterglow", f"{destination} (already fetched and checked)")
		return destination
	scratch = cache / ".fetch"
	shutil.rmtree(scratch, ignore_errors=True)
	scratch.mkdir()
	try:
		compressed = scratch / "source.tar.gz"
		if tarball is not None:
			shutil.copyfile(tarball, compressed)
		else:
			# GitHub may recompress an archive, so the pin is the sum of the uncompressed tar; download unchecked, then check that.
			download_unchecked(source_url(recipe), compressed)
		raw = scratch / "source.tar"
		with gzip.open(compressed, "rb") as source, open(raw, "wb") as target:
			shutil.copyfileobj(source, target, 1 << 20)
		actual = sha256_file(raw)
		if not trust and actual != pin["tar_sha256"]:
			raise FetchError(f"Afterglow tar SHA-256 is {actual}, expected {pin['tar_sha256']}; the download was discarded")
		extracted = scratch / "tree"
		extracted.mkdir()
		with tarfile.open(raw) as archive:
			_check_members(archive)
			archive.extractall(extracted, filter="data")
		top = [path for path in extracted.iterdir() if path.is_dir()]
		if len(top) != 1 or not (top[0] / "desktop" / "style" / "build.sh").is_file():
			raise FetchError("the Afterglow archive has no desktop/style/build.sh")
		shutil.rmtree(destination, ignore_errors=True)
		top[0].replace(destination)
		# The checked tar stays beside the tree so `rl verify` can check the pin again without downloading.
		raw.replace(cache / f"{pin['commit']}.tar")
		marker.write_text(actual + "\n")
	finally:
		shutil.rmtree(scratch, ignore_errors=True)
	return destination


def tree_tar_sha256(source_tree: Path) -> str:
	"""The SHA-256 of the tar a fetched tree came from, as `fetch_afterglow` recorded it."""
	return (source_tree / ".verified").read_text().strip()


def download_unchecked(url: str, destination: Path) -> None:
	log("afterglow", f"downloading {url}")
	with urllib.request.urlopen(url, timeout=120) as response, open(destination, "wb") as target:
		shutil.copyfileobj(response, target, 1 << 20)


def _run(argv: list[str], what: str) -> None:
	done = subprocess.run(argv, capture_output=True, text=True, check=False)
	if done.returncode != 0:
		raise FetchError(f"{what} failed: {(done.stderr or done.stdout).strip()[-500:]}")


def prepare_afterglow(recipe: Recipe, work: Path, source_tree: Path, measured: dict[str, str] | None = None) -> Path:
	"""Build the files the disk takes from the Afterglow source into `work/afterglow-files`: `afterglow.msstyles` (checked against the
	pin), `afterglow.reg` (selects the style and scheme), `cursors/` (the 16 pointer files) and `pointers.reg`. Needs llvm-rc, lld-link
	and python3 with numpy and Pillow, as Afterglow's own scripts do. With `measured` (for `rl pin`), the style's sum is stored there
	as `msstyles_sha256` instead of being checked."""
	pin = recipe.section("inputs", "afterglow")
	output = work / "afterglow-files"
	shutil.rmtree(output, ignore_errors=True)
	output.mkdir(parents=True)
	style_dir = output / ".style"
	_run(["bash", str(source_tree / "desktop" / "style" / "build.sh"), str(style_dir)], "the Afterglow style build")
	built = style_dir / "afterglow.msstyles"
	actual = sha256_file(built)
	if measured is not None:
		measured["msstyles_sha256"] = actual
	elif actual != pin["msstyles_sha256"]:
		raise FetchError(f"afterglow.msstyles is {actual}, expected {pin['msstyles_sha256']}; the toolchain or the source differs")
	built.replace(output / "afterglow.msstyles")
	shutil.rmtree(style_dir)
	shutil.copyfile(source_tree / pin["apply_reg"], output / "afterglow.reg")
	cursors = output / "cursors"
	cursors.mkdir()
	_run(["python3", "-I", str(source_tree / "desktop" / "pointers" / "gen-cursors.py"), str(cursors)], "the pointer build")
	count = len([path for path in cursors.iterdir() if path.is_file()])
	if count != POINTER_FILES:
		raise FetchError(f"the pointer build wrote {count} files, expected {POINTER_FILES}")
	shutil.copyfile(source_tree / "desktop" / "pointers" / "afterglow-pointers.reg", output / "pointers.reg")
	log("afterglow", f"wrote afterglow.msstyles, afterglow.reg, pointers.reg and {count} pointer files to {output}")
	return output
