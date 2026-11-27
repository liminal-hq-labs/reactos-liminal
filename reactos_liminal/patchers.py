# Patchers: each takes a stock file from the golden disk, checks it is the one file it was written for, and yields a patched copy and
# the path it goes to on the image. Patchers run before the trim, so each is checked against the stock file and the trim can never
# remove what a patcher wrote.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import subprocess
from pathlib import Path

from .fetch import sha256_file
from .log import log
from .mtools import FatImage
from .patch_base import PatchedFile, PatchError, remember_patched  # noqa: F401  (re-exported: cli and the tests import them from here)
from .patch_bitmaps import toolbar_bitmaps
from .patch_boot import afterglow_boot
from .patch_dialog_bitmaps import dialog_bitmaps
from .patch_family import cpl_icons, dialog_icons, map_icons, program_icons
from .patch_icons import afterglow_icons
from .patch_logon import afterglow_logon
from .patch_start import afterglow_start


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


PATCHERS = {
	"afterglow.pointers": _afterglow_pointers,
	"afterglow.start": afterglow_start,
	"afterglow.icons": afterglow_icons,
	"afterglow.cpl-icons": cpl_icons,
	"afterglow.program-icons": program_icons,
	"afterglow.dialog-icons": dialog_icons,
	"afterglow.map-icons": map_icons,
	"afterglow.toolbar-bitmaps": toolbar_bitmaps,
	"afterglow.dialog-bitmaps": dialog_bitmaps,
	"afterglow.logon": afterglow_logon,
	"afterglow.boot": afterglow_boot,
}


def run_patchers(names: list[str], golden: FatImage, source_tree: Path | None, files: Path | None, scratch: Path) -> list[PatchedFile]:
	"""Run the named patchers against the golden disk, which is only read. Returns the patched copies to write."""
	results: list[PatchedFile] = []
	for name in names:
		if source_tree is None or files is None:
			raise PatchError(f"patcher {name} needs the Afterglow files")
		made = PATCHERS[name](golden, source_tree, files, scratch)
		for item in made:
			remember_patched(scratch, item)
		results += made
	return results
