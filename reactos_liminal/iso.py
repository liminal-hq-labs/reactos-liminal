# `rl iso`: write the remastered install ISO from the official install CD and the finished image.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# The remaster is the official ISO with a second session appended: nothing already on the disc moves, so the boot record, every file
# and the boot loader's view of the registry hive are byte for byte as shipped (a rebuilt image broke the boot loader, see
# `isopatch.py`). The session adds the licence texts, the notice and the list of changes that `rl image` wrote into the disk, taken
# from the image so the disc and the disk always agree. Setup's own art and the extra cabinet are the next additions to this step.
import shutil
import subprocess
import tempfile
from pathlib import Path

from .fetch import FetchError, has_hash
from .licences import IMAGE_CHANGES, IMAGE_LICENCE_FOLDER, IMAGE_NOTICE
from .log import log
from .mtools import FatImage
from .paths import ensure
from .recipe import Recipe

# The volume keeps the official label. Names go on the disc in upper case with the ISO 9660 rules, and the Joliet names keep their case.
DISC_FOLDER = IMAGE_LICENCE_FOLDER
COMPLIANCE = "iso_9660_level=3:lowercase:omit_version:no_force_dots:deep_paths:long_paths"


class IsoError(Exception):
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
	"""Copy the official ISO to `out` and append a session with the notices from `image`. The official ISO is only read, and the result
	is never the official ISO's own path."""
	pin = recipe.section("inputs", "reactos_iso")
	official = official_iso or work / "dl" / pin["name"]
	if not has_hash(official, pin["sha256"]):
		raise FetchError(f"{official} is not the pinned ISO (expected SHA-256 {pin['sha256']}); run `rl fetch` first")
	if out.resolve() == official.resolve():
		raise IsoError("the output must not be the official ISO")
	if shutil.which("xorriso") is None:
		raise IsoError("xorriso is not installed")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.unlink(missing_ok=True)
	copied = subprocess.run(
		["cp", "--sparse=always", "--reflink=auto", str(official), str(out)], capture_output=True, text=True, check=False
	)
	if copied.returncode != 0:
		raise IsoError(f"cannot copy the official ISO: {copied.stderr.strip()}")
	out.chmod(0o644)
	with tempfile.TemporaryDirectory(dir=ensure(work, "scratch")) as scratch_name:
		tree = Path(scratch_name) / "session"
		tree.mkdir()
		names = disc_tree(image, tree)
		log("iso", f"appending a session with {', '.join(names)}")
		# `-dev` opens the copy for appending, so the first session stays where it is; `-boot_image any keep` carries the El Torito boot
		# entry over, which xorriso otherwise drops from the new session.
		done = subprocess.run(
			[
				"xorriso",
				*["-dev", str(out)],
				*["-boot_image", "any", "keep"],
				# The official disc stores lower-case names with no version suffix, and the boot loader opens them by those names (as
				# `system`, not `SYSTEM.;1`), so the new session must write names the same way.
				*["-compliance", COMPLIANCE],
				*["-map", str(tree), "/", "-commit"],
			],
			capture_output=True,
			text=True,
			check=False,
		)
	if done.returncode != 0:
		out.unlink(missing_ok=True)
		raise IsoError(f"xorriso failed: {(done.stderr or done.stdout).strip()[-500:]}")
	log("iso", f"wrote {out}")
	return out
