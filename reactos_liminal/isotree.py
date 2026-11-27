# The edits that turn the official install disc's file tree into Afterglow's discs: the menu text, the notices, an optional second
# cabinet, and (for the install CD only) the unattended answers.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Every text edit is guarded like a patcher: the stock file must be the exact one ReactOS 0.4.16 ships (an SHA-256 allow-list), and each
# line to change must occur exactly once. The published disc and the install CD share the menu text; they differ only in the three files
# the answers need (`i386/unattend.inf`, the default entry in `freeldr.ini` and the debugger flag in `i386/txtsetup.sif`). The answers
# partition and format disk 0, so they are never on the published disc, and `check_no_answers` refuses a tree that carries them.
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from .isobuild import IsoBuildError, Writer, detect_writer, extract_tree
from .log import log
from .recipe import Recipe

STOCK_SUMS = {
	"freeldr.ini": "e0d9aa807deca649dd8d84923195905cb2d40e95751eb57dd5d059bbcfba46a8",
	"i386/txtsetup.sif": "277d54ba502326e0fd8e799ae8bb2065364801211d9f61aaf68002fb9a13635c",
	"i386/unattend.inf": "e02b404161363deff28acdea94377bb9d71cc73ad6b91eff7e2bde3d2868cbaf",
}
FREELDR = "freeldr.ini"
TXTSETUP = "i386/txtsetup.sif"
UNATTEND = "i386/unattend.inf"

# Menu text. The installed disk's own entry ("ReactOS (Afterglow)") is the boot patcher's job; these are the disc's.
MENU_EDITS = (
	(b"TitleText=", b"TitleText=ReactOS (Afterglow) Boot Media"),
	(b'Setup="ReactOS Setup (Text Mode)"', b'Setup="ReactOS (Afterglow) Setup (Text Mode)"'),
	(b'LiveImg="ReactOS Live Environment (Graphics Mode)"', b'LiveImg="ReactOS (Afterglow) Live Environment (Graphics Mode)"'),
	(b'LiveImg_RamDisk="ReactOS Live Environment - RamDisk"', b'LiveImg_RamDisk="ReactOS (Afterglow) Live Environment - RamDisk"'),
)
DEBUG_FLAGS = b'SetupDebugOptions = "/DEBUG /KDSERIAL /DEBUGPORT=COM1 /FIRSTCHANCE"'
NO_DEBUG = b'SetupDebugOptions = "/NODEBUG"'
CABINET_NAME = "afterglow.cab"
CABINET_LIST = "afterglow.inf"


def source_epoch(recipe: Recipe) -> int:
	"""The time every file and descriptor on the disc carries: `$SOURCE_DATE_EPOCH`, else the recipe's `iso.epoch`."""
	return int(os.environ.get("SOURCE_DATE_EPOCH") or recipe.section("iso")["epoch"])


def pinned_writer(recipe: Recipe) -> Writer:
	"""The ISO writer to use, which is the recipe's pin when it is installed. Another writer works but gives different bytes, so it is
	reported."""
	pin = recipe.section("iso")["writer"]
	writer = detect_writer(pin)
	if writer.identity != pin:
		log("iso", f"warning: the recipe pins {pin} but {writer.identity} is installed; the disc will boot the same but its bytes differ")
	return writer


def sha256_of(path: Path) -> str:
	return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_line(text: bytes, start: bytes, new: bytes) -> bytes:
	"""Replace the one line that begins with `start` by `new`, keeping the line's ending."""
	lines = text.splitlines(keepends=True)
	hits = [index for index, line in enumerate(lines) if line.startswith(start)]
	if len(hits) != 1:
		raise IsoBuildError(f"expected one line starting {start.decode()!r}, found {len(hits)}")
	line = lines[hits[0]]
	ending = line[len(line.rstrip(b"\r\n")) :]
	lines[hits[0]] = new + ending
	return b"".join(lines)


def insert_after(text: bytes, line_start: bytes, new: bytes) -> bytes:
	"""Add the line `new` after the one line that begins with `line_start`, with the same line ending."""
	lines = text.splitlines(keepends=True)
	hits = [index for index, line in enumerate(lines) if line.startswith(line_start)]
	if len(hits) != 1:
		raise IsoBuildError(f"expected one line starting {line_start.decode()!r}, found {len(hits)}")
	line = lines[hits[0]]
	ending = line[len(line.rstrip(b"\r\n")) :]
	lines.insert(hits[0] + 1, new + ending)
	return b"".join(lines)


def stock_tree(iso: Path, tree: Path) -> None:
	"""Extract the official disc and refuse it unless the three files that get edited are the exact ones ReactOS 0.4.16 ships."""
	extract_tree(iso, tree)
	for name, expected in STOCK_SUMS.items():
		path = tree / name
		if not path.is_file() or sha256_of(path) != expected:
			shutil.rmtree(tree, ignore_errors=True)
			raise IsoBuildError(f"{name} on the disc is not the file ReactOS 0.4.16 ships; the edits would not be safe")


def apply_menu(tree: Path) -> None:
	"""The Afterglow names in the boot menu. The default entry stays the live environment."""
	path = tree / FREELDR
	text = path.read_bytes()
	for start, new in MENU_EDITS:
		text = replace_line(text, start, new)
	path.write_bytes(text)


def apply_install(tree: Path, answers: bytes) -> None:
	"""Turn the tree into the install CD: the answers over `i386/unattend.inf`, Setup the default entry, and Setup started without the
	kernel debugger (its serial port hangs a run when nothing is attached to it)."""
	path = tree / FREELDR
	path.write_bytes(replace_line(path.read_bytes(), b"DefaultOS=", b"DefaultOS=Setup"))
	path = tree / TXTSETUP
	path.write_bytes(replace_line(path.read_bytes(), DEBUG_FLAGS, NO_DEBUG))
	(tree / UNATTEND).write_bytes(answers.replace(b"\r\n", b"\n"))


def check_no_answers(tree: Path) -> None:
	"""Refuse a tree that would put the unattended answers on a disc people receive: the answers file must be the stock one and Setup
	must not be the default entry."""
	if sha256_of(tree / UNATTEND) != STOCK_SUMS[UNATTEND]:
		raise IsoBuildError("i386/unattend.inf is not the stock file: the unattended answers format disk 0 and are not published")
	if any(line.strip() == b"DefaultOS=Setup" for line in (tree / FREELDR).read_bytes().splitlines()):
		raise IsoBuildError("freeldr.ini makes Setup the default entry: that is the install CD, not the published disc")


def build_cabinet(files: dict[str, bytes], epoch: int, scratch: Path) -> tuple[bytes, bytes]:
	"""A second cabinet and the `.inf` beside it that lists its files in directory 1. Setup reads each `[Cabinets]` line in order and the
	later cabinet's copy of a file wins, so the stock `reactos.cab` stays byte for byte as shipped. `gcab -z` writes MSZIP blocks that
	each inflate on their own, which is what Setup's decoder needs; file times are fixed so the cabinet is reproducible."""
	if shutil.which("gcab") is None:
		raise IsoBuildError("gcab is not installed; it writes the second cabinet")
	if not files:
		raise IsoBuildError("a cabinet needs at least one file")
	folder = scratch / "cabinet"
	folder.mkdir(parents=True, exist_ok=True)
	for name, data in files.items():
		(folder / name).write_bytes(data)
		os.utime(folder / name, (epoch, epoch))
	cabinet = scratch / CABINET_NAME
	cabinet.unlink(missing_ok=True)
	done = subprocess.run(["gcab", "-c", "-z", str(cabinet), *sorted(files)], cwd=folder, capture_output=True, text=True, check=False)
	if done.returncode != 0:
		raise IsoBuildError(f"gcab failed: {(done.stderr or done.stdout).strip()[-300:]}")
	listing = ["[Version]", 'Signature = "$Windows NT$"', "", "[Directories]", '1 = "\\"', "", "[SourceFiles]"]
	listing += [f"{name}=1" for name in sorted(files)]
	return cabinet.read_bytes(), ("\r\n".join(listing) + "\r\n").encode()


def add_cabinet(tree: Path, files: dict[str, bytes], epoch: int, scratch: Path) -> None:
	"""Add `files` to the disc as a second cabinet that Setup copies after `reactos.cab`."""
	cabinet, listing = build_cabinet(files, epoch, scratch)
	(tree / "i386" / CABINET_NAME).write_bytes(cabinet)
	(tree / "i386" / CABINET_LIST).write_bytes(listing)
	path = tree / TXTSETUP
	path.write_bytes(insert_after(path.read_bytes(), b"Cabinet = reactos.cab", f"Cabinet = {CABINET_NAME}".encode()))


def changed_files(first: Path, second: Path) -> list[str]:
	"""The paths whose bytes differ between two trees, or that only one holds, sorted."""
	names = {path.relative_to(first).as_posix() for path in first.rglob("*") if path.is_file()}
	names |= {path.relative_to(second).as_posix() for path in second.rglob("*") if path.is_file()}
	return sorted(
		name
		for name in names
		if not (first / name).is_file() or not (second / name).is_file() or (first / name).read_bytes() != (second / name).read_bytes()
	)
