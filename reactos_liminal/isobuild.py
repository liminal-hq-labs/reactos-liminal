# Build a ReactOS install disc from a file tree, the way ReactOS builds its own: ISO 9660:1999 names, no Rock Ridge, no Joliet, the
# no-emulation El Torito entry for `loader/isoboot.bin` and the isohybrid boot record from `loader/isombr.bin`.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Why this exact recipe. FreeLoader reads only the Primary Volume Descriptor's directory tree. It compares each name with `_stricmp`
# after cutting at `;`, but it does not remove the trailing dot that ISO 9660 levels 1 to 3 add to a name with no extension, so a
# writer's default `SYSTEM.;1` is never `system` and the live entry stops with "Could not load SYSTEM.ALT hive". ReactOS's own disc is
# written by cdrtools `mkisofs -iso-level 4`, which stores names exactly as given (case kept, no version, no forced dot, up to 207
# characters). FreeLoader also copies a name into a 32-byte buffer with no bounds check, so a name of 32 characters or more in a folder
# it searches overflows its stack. `-boot-info-table` is never used: it overwrites boot code in `isoboot.bin`. Details and evidence are
# in `docs/iso.md`.
#
# Two builds of the same tree with the same writer are byte for byte the same: every file time is the epoch, the volume descriptors'
# dates are the epoch, cdrtools' "MKI" sector (the build time and command line) is blanked, and the hybrid boot record has a fixed
# disk id. The two writers (cdrtools and cdrkit's genisoimage) give different bytes from each other, so the recipe pins one.
import functools
import os
import re
import shutil
import struct
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

SECTOR = 2048
DEFAULT_VOLUME = "ReactOS"
PUBLISHER = "ReactOS Project"
BOOT_IMAGE = "loader/isoboot.bin"
HYBRID_CODE = "loader/isombr.bin"
BOOT_CATALOG = "boot.catalog"
# The boot sector's own files first on the disc, as ReactOS's build orders them.
SORT_FILES = ((BOOT_CATALOG, 4), (BOOT_IMAGE, 3), ("loader/isobtrt.bin", 2))
HYBRID_HEADS = 64
HYBRID_SECTORS = 32
HYBRID_PARTITION_TYPE = 0x96
HYBRID_DISK_ID = 0x4C49_4847  # fixed, so the output is reproducible; isohybrid picks a random one

# FreeLoader copies a name into `CHAR Name[32]`, so a name of this many characters or more overflows it.
FREELOADER_NAME_LIMIT = 32
# The folders FreeLoader reads while it boots Setup and the live environment. Names in other folders (the profiles, the side-by-side
# assemblies in `reactos/winsxs`) are never copied into that buffer.
FREELOADER_FOLDERS = (
	"",
	"loader",
	"i386",
	"i386/system32",
	"i386/system32/config",
	"i386/system32/drivers",
	"reactos",
	"reactos/system32",
	"reactos/system32/config",
	"reactos/system32/drivers",
)
# The files FreeLoader and Setup open by name; each must be found under FreeLoader's own comparison.
BOOT_PATH = (
	"loader/freeldr.sys",
	"freeldr.ini",
	"i386/txtsetup.sif",
	"i386/unattend.inf",
	"i386/reactos.cab",
	"reactos/system32/config/system",
	"reactos/system32/ntoskrnl.exe",
	"reactos/system32/drivers/cdfs.sys",
)

WRITER_NAMES = ("mkisofs", "genisoimage")


class IsoBuildError(Exception):
	"""A disc that cannot be written safely, or a writer that is not there."""


@dataclass(frozen=True)
class Writer:
	"""The ISO writer program: cdrtools `mkisofs` (version 2 or 3) or cdrkit `genisoimage` (1.1.x, also installed as `mkisofs`)."""

	path: str
	name: str
	version: str

	@property
	def identity(self) -> str:
		return f"{self.name} {self.version}"

	@property
	def cdrtools(self) -> bool:
		"""cdrtools has `-duplicates-once` and `-eltorito-boot`; cdrkit has `-b` and `-c`."""
		return self.name == "mkisofs"


def parse_writer_version(text: str) -> tuple[str, str] | None:
	"""The writer's name and version from its `-version` output. cdrkit is `genisoimage` 1.1.x, but the `mkisofs` link it installs
	reports itself as `mkisofs 2.01`; only cdrtools reports 3.x, so anything older is cdrkit and is named `genisoimage`."""
	found = re.match(r"\s*(mkisofs|genisoimage)\s+(\S+)", text)
	if not found:
		return None
	name, version = found.groups()
	if not version.startswith("3."):
		name = "genisoimage"
	return name, version


def writers_on_path() -> list[Writer]:
	"""Every ISO writer on the path, `mkisofs` first, without repeats of the same program. Probed once per `PATH`, so asking for the
	golden disk's key (which names the writer) starts nothing after the first time."""
	return list(_probe(os.environ.get("PATH", "")))


@functools.cache
def _probe(search_path: str) -> tuple[Writer, ...]:
	found: list[Writer] = []
	seen: set[str] = set()
	for name in WRITER_NAMES:
		found_path = shutil.which(name)
		if not found_path:
			continue
		# Run the program the link names: Debian's `mkisofs` is a link to `genisoimage`, and Arch's `genisoimage` to `mkisofs`.
		path = os.path.realpath(found_path)
		if path in seen:
			continue
		seen.add(path)
		try:
			done = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=20, check=False)
		except (OSError, subprocess.TimeoutExpired):
			continue
		parsed = parse_writer_version(done.stdout + done.stderr)
		if parsed:
			found.append(Writer(path, *parsed))
	return tuple(found)


def detect_writer(pin: str | None = None) -> Writer:
	"""The writer to use: the one that matches `pin` ("genisoimage 1.1.11") when it is installed, else the first on the path."""
	candidates = writers_on_path()
	if not candidates:
		raise IsoBuildError("no ISO writer is installed: install cdrtools (mkisofs) or cdrkit (genisoimage)")
	for candidate in candidates:
		if pin and candidate.identity == pin:
			return candidate
	return candidates[0]


def writer_identity(pin: str | None = None) -> str:
	"""The writer's `name version`, or `none` when no writer is installed (a plan can still be printed)."""
	try:
		return detect_writer(pin).identity
	except IsoBuildError:
		return "none"


def writer_command(writer: Writer, tree: Path, out: Path, sort_file: Path, volume: str = DEFAULT_VOLUME) -> list[str]:
	"""The writer's command line, with ReactOS's own flags (`boot/boot_images.cmake`): level 4 names, the boot catalog hidden, a 4-sector
	no-emulation boot image, no Rock Ridge, no Joliet and no boot info table."""
	command = [writer.path, "-quiet", "-o", str(out), "-iso-level", "4", "-publisher", PUBLISHER, "-preparer", PUBLISHER]
	command += ["-volid", volume, "-volset", volume]
	if writer.cdrtools:
		command += ["-eltorito-platform", "x86", "-eltorito-boot", BOOT_IMAGE]
	else:
		command += ["-b", BOOT_IMAGE, "-c", BOOT_CATALOG]
	command += ["-no-emul-boot", "-boot-load-size", "4", "-hide", BOOT_CATALOG, "-sort", str(sort_file)]
	if writer.cdrtools:
		command.append("-duplicates-once")
	command += ["-no-cache-inodes", str(tree)]
	return command


def sort_file_text(tree: Path) -> str:
	return "".join(f"{tree}/{name} {weight}\n" for name, weight in SORT_FILES)


def extract_tree(iso: Path, tree: Path) -> None:
	"""Read-only extraction of a disc into `tree` (which must not exist), writable afterwards. Empty folders are kept."""
	if shutil.which("xorriso") is None:
		raise IsoBuildError("xorriso is not installed; it extracts the official disc")
	if tree.exists():
		raise IsoBuildError(f"{tree} already exists")
	done = subprocess.run(
		["xorriso", "-osirrox", "on", "-indev", str(iso), "-extract", "/", str(tree)], capture_output=True, text=True, check=False
	)
	if done.returncode != 0 or not tree.is_dir():
		raise IsoBuildError(f"xorriso could not extract {iso}: {(done.stderr or done.stdout).strip()[-300:]}")
	make_writable(tree)


def make_writable(tree: Path) -> None:
	for path in [tree, *tree.rglob("*")]:
		if not path.is_symlink():
			path.chmod(path.stat().st_mode | 0o200 | (0o100 if path.is_dir() else 0))


def remove_tree(tree: Path) -> None:
	"""Delete a tree extracted from a disc, whose folders may be read-only."""
	if tree.exists():
		make_writable(tree)
		shutil.rmtree(tree)


def fix_times(tree: Path, epoch: int) -> None:
	for path in [tree, *tree.rglob("*")]:
		os.utime(path, (epoch, epoch), follow_symlinks=False)


def tree_paths(tree: Path) -> list[str]:
	"""Every file and folder under the tree as a `/` path relative to it, sorted."""
	return sorted(path.relative_to(tree).as_posix() for path in tree.rglob("*"))


def freeldr_name(raw: bytes) -> str:
	"""A name as FreeLoader sees it: the record's bytes up to `;`, with nothing else removed (the trailing dot stays)."""
	return raw.split(b";", 1)[0].decode("latin-1")


def check_tree_names(tree: Path) -> None:
	"""Refuse a tree with a name FreeLoader would overflow its buffer on: 32 characters or more in a folder it searches."""
	problems = []
	for folder in FREELOADER_FOLDERS:
		directory = tree / folder if folder else tree
		if not directory.is_dir():
			continue
		for entry in sorted(directory.iterdir()):
			if len(entry.name.encode("latin-1", "replace")) >= FREELOADER_NAME_LIMIT:
				problems.append(f"{(folder + '/' if folder else '') + entry.name} ({len(entry.name)} characters)")
	if problems:
		raise IsoBuildError(
			f"FreeLoader copies names into a {FREELOADER_NAME_LIMIT}-byte buffer; these names in a folder it searches are too long: "
			+ ", ".join(problems)
		)


@dataclass(frozen=True)
class Record:
	raw: bytes
	extent: int
	size: int
	is_folder: bool


def read_records(image, extent: int, length: int) -> list[Record]:
	"""The directory records of one folder, skipping `.` and `..`."""
	image.seek(extent * SECTOR)
	data = image.read(length)
	records = []
	offset = 0
	while offset < len(data):
		record_length = data[offset]
		if record_length == 0:
			offset = (offset // SECTOR + 1) * SECTOR
			continue
		record = data[offset : offset + record_length]
		name = record[33 : 33 + record[32]]
		if name not in (b"\x00", b"\x01"):
			start, size = struct.unpack_from("<I", record, 2)[0], struct.unpack_from("<I", record, 10)[0]
			records.append(Record(name, start, size, bool(record[25] & 2)))
		offset += record_length
	return records


def read_primary_tree(iso: Path) -> dict[str, Record]:
	"""Every path in the Primary Volume Descriptor's tree (the only tree FreeLoader reads), keyed by the raw names joined with `/`."""
	paths: dict[str, Record] = {}
	with open(iso, "rb") as image:
		image.seek(16 * SECTOR)
		descriptor = image.read(SECTOR)
		if descriptor[1:6] != b"CD001" or descriptor[0] != 1:
			raise IsoBuildError(f"{iso} has no primary volume descriptor at sector 16")
		root = (struct.unpack_from("<I", descriptor, 158)[0], struct.unpack_from("<I", descriptor, 166)[0])
		stack = [("", root)]
		while stack:
			prefix, (extent, length) = stack.pop()
			for record in read_records(image, extent, length):
				path = prefix + record.raw.decode("latin-1")
				paths[path] = record
				if record.is_folder:
					stack.append((path + "/", (record.extent, record.size)))
	return paths


def freeldr_lookup(iso: Path, path: str) -> Record | None:
	"""Find a file the way FreeLoader does: each name cut at `;` and compared without case, nothing else removed."""
	with open(iso, "rb") as image:
		image.seek(16 * SECTOR)
		descriptor = image.read(SECTOR)
		extent, length = struct.unpack_from("<I", descriptor, 158)[0], struct.unpack_from("<I", descriptor, 166)[0]
		found = None
		for part in path.split("/"):
			matches = [r for r in read_records(image, extent, length) if freeldr_name(r.raw).lower() == part.lower()]
			if not matches:
				return None
			found = matches[0]
			extent, length = found.extent, found.size
		return found


def boot_entry(iso: Path) -> tuple[int, int, int, int]:
	"""The El Torito default entry: (boot media type, load size in sectors, image LBA, platform id)."""
	with open(iso, "rb") as image:
		image.seek(17 * SECTOR)
		record = image.read(SECTOR)
		if record[7:30] != b"EL TORITO SPECIFICATION":
			raise IsoBuildError("no El Torito boot record at sector 17")
		catalog = struct.unpack_from("<I", record, 71)[0]
		image.seek(catalog * SECTOR)
		block = image.read(64)
	platform = block[1]
	media = block[32 + 1]
	load_size = struct.unpack_from("<H", block, 32 + 6)[0]
	lba = struct.unpack_from("<I", block, 32 + 8)[0]
	return media, load_size, lba, platform


def check_iso(iso: Path, tree: Path, hybrid: bool = True) -> None:
	"""Refuse a disc that FreeLoader could not read: every path in the tree must be in the primary tree under exactly its own name (no
	upper-casing, no `;1`, no trailing dot, no cut or changed name), every file FreeLoader opens must be found by its own comparison, and
	the boot entry and the hybrid boot record must be what ReactOS's own disc has."""
	on_disc = read_primary_tree(iso)
	wanted = tree_paths(tree)
	hidden = {BOOT_CATALOG}
	missing = [path for path in wanted if path not in on_disc]
	extra = [path for path in on_disc if path not in set(wanted) and path not in hidden]
	if missing or extra:
		lines = [f"the disc's names differ from the tree ({len(missing)} missing, {len(extra)} extra)"]
		for path in missing[:5]:
			lines.append(f"  in the tree, not on the disc under that name: {path}")
		for path in extra[:5]:
			lines.append(f"  on the disc, not in the tree: {path}")
		raise IsoBuildError("\n".join(lines))
	for path in BOOT_PATH:
		if (tree / path).exists() and freeldr_lookup(iso, path) is None:
			raise IsoBuildError(f"FreeLoader would not find {path} on the disc")
	media, load_size, lba, _platform = boot_entry(iso)
	if media != 0 or load_size != 4:
		raise IsoBuildError(f"the boot entry must be no-emulation with a load size of 4 sectors (it is media {media}, load {load_size})")
	boot = freeldr_lookup(iso, BOOT_IMAGE)
	if boot is None or boot.extent != lba:
		raise IsoBuildError(f"the boot entry does not point at /{BOOT_IMAGE}")
	if hybrid:
		with open(iso, "rb") as image:
			mbr = image.read(512)
		if mbr[510:512] != b"\x55\xaa" or struct.unpack_from("<I", mbr, 432)[0] != lba * 4 or mbr[446 + 4] != HYBRID_PARTITION_TYPE:
			raise IsoBuildError("the hybrid boot record is missing or does not point at the boot image")


def iso_date(epoch: int) -> bytes:
	"""The 17-byte volume descriptor date for `epoch`, in UTC."""
	return time.strftime("%Y%m%d%H%M%S", time.gmtime(epoch)).encode() + b"00" + b"\x00"


def fix_descriptor_dates(iso: Path, epoch: int) -> None:
	"""Set the creation, modification and effective dates of every volume descriptor to `epoch`, and blank cdrtools' "MKI" sector (the
	build time and the paths it was run with), which nothing reads and which would make every build differ."""
	stamp = iso_date(epoch)
	with open(iso, "r+b") as image:
		for sector in range(16, 64):
			image.seek(sector * SECTOR)
			descriptor = image.read(7)
			if descriptor[1:6] != b"CD001":
				break
			if descriptor[0] == 255:
				image.seek((sector + 1) * SECTOR)
				if image.read(4) == b"MKI ":
					image.seek((sector + 1) * SECTOR)
					image.write(bytes(SECTOR))
				break
			if descriptor[0] in (1, 2):
				for offset in (813, 830, 864):
					image.seek(sector * SECTOR + offset)
					image.write(stamp)


def make_hybrid(iso: Path, mbr_code: Path) -> None:
	"""What ReactOS's `isohybrid -b isombr.bin -t 0x96` does, with a fixed disk id: the boot record's code, the boot image's LBA in
	512-byte sectors at offset 432 (`isombr` reads it there), one active partition of type 0x96 over the whole image, and the image
	padded to a whole cylinder of 64 heads by 32 sectors."""
	code = mbr_code.read_bytes()[:432]
	cylinder = HYBRID_HEADS * HYBRID_SECTORS * 512
	size = iso.stat().st_size
	padding = (cylinder - size % cylinder) % cylinder
	cylinders = (size + padding) // cylinder
	last_cylinder = min(cylinders, 1024)
	_media, _load, boot_lba, _platform = boot_entry(iso)
	entry = bytes(
		[
			0x80,
			0,
			1,
			0,
			HYBRID_PARTITION_TYPE,
			HYBRID_HEADS - 1,
			HYBRID_SECTORS + (((last_cylinder - 1) & 0x300) >> 2),
			(last_cylinder - 1) & 0xFF,
		]
	) + struct.pack("<II", 0, cylinders * HYBRID_HEADS * HYBRID_SECTORS)
	record = code + struct.pack("<III", boot_lba * 4, 0, HYBRID_DISK_ID) + b"\0\0" + entry + bytes(48) + b"\x55\xaa"
	if len(record) != 512:
		raise IsoBuildError(f"{mbr_code} is shorter than the 432 bytes of boot code the hybrid record needs")
	with open(iso, "r+b") as image:
		image.write(record)
		if padding:
			image.seek(size + padding - 1)
			image.write(b"\0")


def write_iso(tree: Path, out: Path, scratch: Path, writer: Writer, epoch: int, volume: str = DEFAULT_VOLUME, hybrid: bool = True) -> Path:
	"""Write the tree as a disc at `out`. It is written beside `out`, checked against the tree, and only then moved into place, so a
	disc FreeLoader could not read is never left behind."""
	check_tree_names(tree)
	if not (tree / BOOT_IMAGE).is_file():
		raise IsoBuildError(f"the tree has no /{BOOT_IMAGE}")
	if hybrid and not (tree / HYBRID_CODE).is_file():
		raise IsoBuildError(f"the tree has no /{HYBRID_CODE}")
	fix_times(tree, epoch)
	scratch.mkdir(parents=True, exist_ok=True)
	sort_file = scratch / "bootfiles.sort"
	sort_file.write_text(sort_file_text(tree))
	out.parent.mkdir(parents=True, exist_ok=True)
	partial = out.with_name(out.name + ".part")
	partial.unlink(missing_ok=True)
	done = subprocess.run(
		writer_command(writer, tree, partial, sort_file, volume),
		env=dict(os.environ, TZ="UTC"),
		capture_output=True,
		text=True,
		check=False,
	)
	if done.returncode != 0:
		partial.unlink(missing_ok=True)
		raise IsoBuildError(f"{writer.identity} failed: {(done.stderr or done.stdout).strip()[-500:]}")
	try:
		fix_descriptor_dates(partial, epoch)
		if hybrid:
			make_hybrid(partial, tree / HYBRID_CODE)
		check_iso(partial, tree, hybrid)
	except IsoBuildError:
		partial.unlink(missing_ok=True)
		raise
	partial.replace(out)
	return out
