# Patchers: each takes a stock file from the golden disk, checks it is the one file it was written for, and yields a patched copy and
# the path it goes to on the image. Patchers run before the trim, so each is checked against the stock file and the trim can never
# remove what a patcher wrote.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .fetch import sha256_file
from .log import log
from .mtools import FatImage


class PatchError(Exception):
	"""A patcher refused its input or produced a file that does not match its pin."""


@dataclass(frozen=True)
class PatchedFile:
	image_path: str  # where the file goes on the disk, under the FAT32 root
	local_file: Path  # the patched copy in the work directory


def _afterglow_pointers(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Make the Afterglow pointers the system pointers: patch a copy of the guest's user32.dll with Afterglow's own tool, which refuses
	any other user32.dll, and check the result against the sum Afterglow records. ReactOS ignores pointer schemes and loads the system
	pointers from user32.dll, so the patched copy replaces it on the image. It is ReactOS code (LGPL-2.1) and stays in the work
	directory, never in git."""
	cursors = files / "cursors"
	if not cursors.is_dir():
		raise PatchError(f"{cursors} is missing; prepare the Afterglow files first")
	stock = scratch / "user32.dll"
	patched = scratch / "user32-afterglow.dll"
	golden.copy_out("ReactOS/system32/user32.dll", stock)
	tool = source_tree / "desktop" / "pointers" / "patch-user32.py"
	done = subprocess.run(["python3", "-I", str(tool), str(stock), str(cursors), str(patched)], capture_output=True, text=True, check=False)
	if done.returncode != 0:
		raise PatchError(f"patch-user32.py refused the guest's user32.dll: {(done.stderr or done.stdout).strip()[-400:]}")
	expected = (source_tree / "desktop" / "pointers" / "SHA256SUMS.user32").read_text().split()[0]
	actual = sha256_file(patched)
	if actual != expected:
		patched.unlink(missing_ok=True)
		raise PatchError(f"patched user32.dll is {actual}, expected {expected}")
	log("patch", f"   afterglow.pointers: user32.dll patched ({actual})")
	return [PatchedFile("ReactOS/system32/user32.dll", patched)]


def _afterglow_start(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	from .patch_start import afterglow_start  # imported here: the module imports this one for PatchError and PatchedFile

	return afterglow_start(golden, source_tree, files, scratch)


PATCHERS = {"afterglow.pointers": _afterglow_pointers, "afterglow.start": _afterglow_start}


def run_patchers(names: list[str], golden: FatImage, source_tree: Path | None, files: Path | None, scratch: Path) -> list[PatchedFile]:
	"""Run the named patchers against the golden disk, which is only read. Returns the patched copies to write."""
	results: list[PatchedFile] = []
	for name in names:
		if source_tree is None or files is None:
			raise PatchError(f"patcher {name} needs the Afterglow files")
		results += PATCHERS[name](golden, source_tree, files, scratch)
	return results
