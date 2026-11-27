# `rl iso`: write the remastered install ISO from the official install CD and the finished image.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# The disc is rebuilt from a file tree, as ReactOS builds its own (`isobuild.py`): the official disc is extracted, the menu text is
# changed, the licence texts, the notice and the list of changes that `rl image` wrote into the disk are added (taken from the image so
# the disc and the disk always agree), and the tree is written with the recipe's pinned ISO writer. The unattended answers are never on
# this disc: they are the install CD's (`install.py`), and a tree that carries them is refused.
import tempfile
from pathlib import Path

from .fetch import FetchError, has_hash
from .isobuild import IsoBuildError, remove_tree, write_iso
from .isotree import apply_menu, check_no_answers, pinned_writer, source_epoch, stock_tree
from .licences import IMAGE_CHANGES, IMAGE_LICENCE_FOLDER, IMAGE_NOTICE
from .log import log
from .mtools import FatImage
from .paths import ensure
from .recipe import Recipe

DISC_FOLDER = IMAGE_LICENCE_FOLDER


class IsoError(IsoBuildError):
	"""The remastered ISO could not be written."""


def disc_tree(image: Path, destination: Path) -> list[str]:
	"""Copy the licence folder, `NOTICE.txt` and `CHANGES.txt` out of the image into a folder tree for the new session. Returns the names
	on the disc. A missing file means `rl image` has not written them, and a remaster without the notices is not published."""
	disk = FatImage(image)
	names: list[str] = []
	for name in (IMAGE_NOTICE, IMAGE_CHANGES):
		if not disk.exists(name):
			raise IsoError(f"{name} is not in the image {image}; run `rl image` first")
		disk.copy_out(name, destination / name)
		names.append(name)
	folder = destination / DISC_FOLDER
	folder.mkdir(parents=True, exist_ok=True)
	listing = disk.run("mdir", "-b", f"::/{DISC_FOLDER}", check=False)
	if listing.returncode != 0:
		raise IsoError(f"{DISC_FOLDER} is not in the image {image}; run `rl image` first")
	for line in listing.stdout.decode(errors="replace").splitlines():
		file_name = line.strip().rsplit("/", 1)[-1]
		if file_name and file_name not in (".", ".."):
			disk.copy_out(f"{DISC_FOLDER}/{file_name}", folder / file_name)
			names.append(f"{DISC_FOLDER}/{file_name}")
	if len(names) < 3:
		raise IsoError(f"{DISC_FOLDER} in the image {image} holds no licence texts")
	return names


def build_iso(recipe: Recipe, work: Path, image: Path, out: Path, official_iso: Path | None = None) -> Path:
	"""Rebuild the official ISO with the Afterglow menu text and the notices from `image`. The official ISO is only read, and the result
	is never the official ISO's own path."""
	pin = recipe.section("inputs", "reactos_iso")
	official = official_iso or work / "dl" / pin["name"]
	if not has_hash(official, pin["sha256"]):
		raise FetchError(f"{official} is not the pinned ISO (expected SHA-256 {pin['sha256']}); run `rl fetch` first")
	if out.resolve() == official.resolve():
		raise IsoError("the output must not be the official ISO")
	writer = pinned_writer(recipe)
	scratch_root = ensure(work, "scratch")
	with tempfile.TemporaryDirectory(dir=scratch_root) as scratch_name:
		scratch = Path(scratch_name)
		tree = scratch / "tree"
		try:
			stock_tree(official, tree)
			apply_menu(tree)
			names = disc_tree(image, tree)
			log("iso", f"menu text set; added {', '.join(names)}")
			check_no_answers(tree)
			write_iso(tree, out, scratch, writer, source_epoch(recipe), recipe.section("iso")["volume"])
		finally:
			remove_tree(tree)
	log("iso", f"wrote {out} with {writer.identity}")
	return out
