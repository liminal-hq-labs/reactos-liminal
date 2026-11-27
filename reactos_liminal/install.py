# `rl install`: install ReactOS onto a blank raw disk with no hand step, and keep the result as the golden disk the rest of the
# pipeline starts from.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# How: the official install CD is copied and gets the recipe's answers written over \I386\UNATTEND.INF (the download itself is not
# touched). Setup reads them, takes the partitioning, format, boot loader, language and computer answers from them, and asks nothing.
# QEMU runs three times on one raw disk, each run ended by the guest itself (-no-reboot turns a guest restart into an exit): text-mode
# setup (copies files, writes the boot loader), the graphical second stage, and the first boot to the desktop, where a GuiRunOnce line
# writes "ci: desktop" to the serial port and powers the guest off. Screenshots from QEMU's monitor are kept every minute.
#
# The disk must be RAW. On a qcow2 disk setup fails with "Setup failed to install the FAT32 bootcode on the system partition".
import hashlib
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import isopatch
from .fetch import fetch_iso, has_hash
from .isobuild import IsoBuildError, remove_tree, write_iso, writer_identity
from .isotree import apply_install, apply_menu, pinned_writer, source_epoch, stock_tree
from .log import log
from .mtools import FatImage, MtoolsError
from .paths import REPO, ensure
from .recipe import Recipe
from .vm import PrivateVm, VmError, VmSpec, default_accel

UNATTEND_TEMPLATE = REPO / "guest" / "unattend.inf.in"
# The files whose contents shape the golden disk, besides the recipe's answers and the ISO's hash.
SHAPING_FILES = (
	UNATTEND_TEMPLATE,
	Path(__file__).resolve(),
	Path(isopatch.__file__).resolve(),
	Path(__file__).resolve().parent / "isobuild.py",
	Path(__file__).resolve().parent / "isotree.py",
	Path(__file__).resolve().parent / "vm.py",
	Path(__file__).resolve().parent / "mtools.py",
)

# The installer's own kernel starts with the kernel debugger on COM1 in this (debug) release and breaks into it on the first
# exception, which hangs the run when nothing is attached (it did, one run in three). Start it without the debugger.
DEBUG_FLAGS = "/DEBUG /KDSERIAL /DEBUGPORT=COM1 /FIRSTCHANCE"
NO_DEBUG_FLAG = "/NODEBUG"

STAGES = (
	("text", "d", "boot the CD: text-mode setup partitions, formats, copies files, writes the boot loader, then restarts"),
	("gui", "c", "boot the new disk: the graphical part of setup registers components, then restarts"),
	("desktop", "c", "first boot to the desktop: GuiRunOnce reports on the serial port and powers the guest off"),
)


class InstallError(Exception):
	"""The unattended install did not finish."""


def render_unattend(recipe: Recipe) -> str:
	"""The answers file for the recipe's `install` table."""
	install = recipe.section("install")
	values = {
		"LOCALE": install["locale"],
		"OWNER_NAME": install["owner_name"],
		"COMPUTER_NAME": install["computer_name"],
		"TIME_ZONE_INDEX": str(install["time_zone_index"]),
		"DEFAULT_THEMES_OFF": "yes" if install["classic_shell"] else "no",
	}
	text = UNATTEND_TEMPLATE.read_text(encoding="utf-8")
	for name, value in values.items():
		if any(character in value for character in '"\r\n'):
			raise InstallError(f"install answer {name} must not contain a quote or a line break: {value!r}")
		text = text.replace(f"@{name}@", value)
	return text


def fix_installed_freeldr(text: bytes) -> bytes:
	"""An unattended install of this release writes a boot menu that starts the kernel debugger on COM1 with no menu delay. This puts
	back the entry and delay an interactive install writes, so the guest boots normally and COM1 is free for the desktop report."""
	lines = text.replace(b"\r", b"").split(b"\n")
	fixed = []
	for line in lines:
		if line.startswith(b"DefaultOS="):
			line = b"DefaultOS=ReactOS"
		elif line.startswith(b"TimeOut="):
			line = b"TimeOut=3"
		fixed.append(line)
	if fixed and fixed[-1] == b"":
		fixed.pop()
	return b"".join(line + b"\r\n" for line in fixed)


def iso_builder(recipe: Recipe, in_place_iso: bool = False) -> str:
	"""Who made the install CD: the in-place patcher, or the rebuild with the ISO writer that is installed (its name and version)."""
	if in_place_iso:
		return "in-place"
	return "rebuild " + writer_identity(recipe.section("iso")["writer"])


def golden_key(recipe: Recipe, in_place_iso: bool = False) -> str:
	"""Hash of everything that shapes the golden disk: the ISO's hash, the rendered answers, the memory and disk size, how and with what
	the install CD is made, and the code and template that run the install. The cached disk is reused only while this stays the same."""
	digest = hashlib.sha256()
	digest.update(recipe.section("inputs", "reactos_iso")["sha256"].encode())
	digest.update(f"iso-builder={iso_builder(recipe, in_place_iso)}".encode())
	digest.update(render_unattend(recipe).encode())
	install = recipe.section("install")
	digest.update(f"memory={install['memory_mb']};disk={install['disk_size_mb']}".encode())
	for path in SHAPING_FILES:
		digest.update(hashlib.sha256(path.read_bytes()).digest())
	return digest.hexdigest()


@dataclass
class InstallPlan:
	"""What `rl install` would do. Built without touching anything, so a dry run can print it."""

	key: str
	golden: Path
	cached: bool
	iso_source: str
	accel: str
	steps: list[str] = field(default_factory=list)
	commands: dict[str, list[str]] = field(default_factory=dict)

	def describe(self) -> str:
		lines = [
			f"golden disk: {self.golden}",
			f"input hash: {self.key}",
			f"cache: {'hit, nothing to do' if self.cached else 'miss, the install runs'}",
			f"install CD: {self.iso_source}",
			f"acceleration: {self.accel}",
			"steps:",
		]
		lines += [f"  {number}. {step}" for number, step in enumerate(self.steps, 1)]
		for name, command in self.commands.items():
			lines.append(f"QEMU, stage {name}:")
			lines.append("  " + " ".join(command))
		return "\n".join(lines)


def golden_path(recipe: Recipe, work: Path, in_place_iso: bool = False) -> Path:
	return work / "golden" / f"{recipe.name}-{golden_key(recipe, in_place_iso)[:16]}.img"


def plan_install(recipe: Recipe, work: Path, iso: Path | None = None, accel: str | None = None, in_place_iso: bool = False) -> InstallPlan:
	"""The plan, with no download, no file written and no process started."""
	pin = recipe.section("inputs", "reactos_iso")
	key = golden_key(recipe, in_place_iso)
	golden = golden_path(recipe, work, in_place_iso)
	accel = accel or default_accel()
	if iso is not None:
		iso_source = f"{iso} (checked against the pin)"
	elif has_hash(work / "dl" / pin["name"], pin["sha256"]):
		iso_source = f"{work / 'dl' / pin['name']} (already downloaded)"
	else:
		iso_source = f"download {pin['url']} and check both hashes"
	install = recipe.section("install")
	install_dir = work / "install"
	vm = PrivateVm(install_dir)
	derived = install_dir / "install.iso"
	plan = InstallPlan(key=key, golden=golden, cached=golden.is_file(), iso_source=iso_source, accel=accel)
	edits = (
		f"write the answers ({install['locale']}, {install['computer_name']}, {install['owner_name']}) over /i386/unattend.inf, make "
		f"Setup the default entry of /freeldr.ini, and start Setup without the kernel debugger in /i386/txtsetup.sif"
	)
	if in_place_iso:
		derive = f"derive the install CD at {derived} by editing a copy of the official ISO in place at the same sizes: {edits}"
	else:
		derive = (
			f"derive the install CD at {derived}: extract the official ISO, set the Afterglow menu text, {edits}, then write the "
			f"disc with {iso_builder(recipe)} (ISO 9660:1999 names, hybrid boot record)"
		)
	plan.steps = [
		derive,
		f"create a blank {install['disk_size_mb']} MiB raw disk (sparse)",
	]
	for name, order, what in STAGES:
		plan.steps.append(f"stage {name}: {what}")
		if name == "text":
			plan.steps.append(
				"put back DefaultOS=ReactOS and TimeOut=3 in the installed freeldr.ini (the unattended install writes a debugger entry)"
			)
		spec = VmSpec(
			disk=Path(f"{golden}.part"),
			cdrom=derived,
			boot_order=order,
			memory_mb=install["memory_mb"],
			accel=accel,
		)
		plan.commands[name] = vm.command(spec)
	plan.steps.append("check explorer.exe is on the disk and the desktop stage reported, then keep the disk and record the input hash")
	return plan


def _stage_timeout(accel: str, override: int | None) -> int:
	if override:
		return override
	return 1800 if accel == "kvm" else 7200


def _run_stage(vm: PrivateVm, spec: VmSpec, name: str, shots: Path, timeout: int) -> None:
	for stale in shots.glob("*.png"):
		stale.unlink()
	shots.mkdir(parents=True, exist_ok=True)
	pid = vm.start(spec)
	started = last_shot = time.monotonic()
	count = 0
	log("install", f"{name}: started (pid {pid}, {spec.accel}, boot {spec.boot_order})")
	while vm.running():
		time.sleep(5)
		now = time.monotonic()
		if now - last_shot >= 60:
			last_shot = now
			count += 1
			vm.screenshot(shots / f"{count:03d}.png")
		if now - started > timeout:
			vm.screenshot(shots / "timeout.png")
			vm.stop()
			raise InstallError(f"stage {name} timed out after {timeout}s; see {shots}")
	log("install", f"{name}: guest ended after {int(time.monotonic() - started)}s")


def derive_install_cd(recipe: Recipe, iso_path: Path, derived: Path, install_dir: Path, in_place_iso: bool = False) -> None:
	"""Write the install CD: the official disc with the answers, Setup as the default entry and Setup's debugger off. By default the disc
	is rebuilt from a file tree with ReactOS's own recipe (`isobuild.py`). `in_place_iso` is the earlier method, kept for one release as a
	fallback: it overwrites three files of a copy at their own sizes."""
	derived.unlink(missing_ok=True)
	answers = render_unattend(recipe).encode()
	if in_place_iso:
		shutil.copyfile(iso_path, derived)
		derived.chmod(0o644)
		try:
			lba, size = isopatch.find_file(iso_path, "/i386/unattend.inf")
			isopatch.patch_in_place(derived, lba, size, lambda old: isopatch.replace_text_file(old, answers))
			# The disc boots the live environment by default; make the text-mode setup the default entry.
			lba, size = isopatch.find_file(iso_path, "/freeldr.ini")
			isopatch.patch_in_place(derived, lba, size, lambda old: isopatch.set_default_os(old, "Setup"))
			lba, size = isopatch.find_file(iso_path, "/i386/txtsetup.sif")
			isopatch.patch_in_place(derived, lba, size, lambda old: isopatch.substitute(old, DEBUG_FLAGS, NO_DEBUG_FLAG))
		except isopatch.IsoPatchError as error:
			raise InstallError(str(error)) from error
		return
	tree = install_dir / "tree"
	try:
		remove_tree(tree)
		stock_tree(iso_path, tree)
		apply_menu(tree)
		apply_install(tree, answers)
		write_iso(tree, derived, install_dir / "iso-scratch", pinned_writer(recipe), source_epoch(recipe), recipe.section("iso")["volume"])
	except IsoBuildError as error:
		raise InstallError(str(error)) from error
	finally:
		remove_tree(tree)
	derived.chmod(0o644)


def run_install(
	recipe: Recipe,
	work: Path,
	iso: Path | None = None,
	force: bool = False,
	keep_disk_on_failure: bool = False,
	accel: str | None = None,
	stage_timeout: int | None = None,
	in_place_iso: bool = False,
) -> Path:
	"""Install ReactOS 0.4.16 unattended onto a blank disk and return the golden disk's path. A disk for the same input hash is
	reused unless `force`."""
	golden = golden_path(recipe, work, in_place_iso)
	if golden.is_file() and not force:
		log("install", f"golden disk is current ({golden}); nothing to do")
		return golden
	accel = accel or default_accel()
	timeout = _stage_timeout(accel, stage_timeout)
	iso_path = fetch_iso(recipe, work, iso)
	install = recipe.section("install")
	install_dir = ensure(work, "install")
	ensure(work, "golden")
	derived = install_dir / "install.iso"
	derive_install_cd(recipe, iso_path, derived, install_dir, in_place_iso)
	log("install", f"derived CD written ({iso_builder(recipe, in_place_iso)}): answers replaced, Setup is the default boot entry")

	disk = Path(f"{golden}.part")
	disk.unlink(missing_ok=True)
	with open(disk, "wb") as blank:
		blank.truncate(install["disk_size_mb"] * 1024 * 1024)
	vm = PrivateVm(install_dir)
	finished = False
	try:
		fat = FatImage(disk)
		for name, order, _what in STAGES:
			spec = VmSpec(disk=disk, cdrom=derived, boot_order=order, memory_mb=install["memory_mb"], accel=accel)
			_run_stage(vm, spec, name, install_dir / "shots" / name, timeout)
			if name == "text":
				if not fat.exists("ReactOS/system32"):
					raise InstallError(f"text-mode setup left no ReactOS folder; see {install_dir / 'shots' / 'text'}")
				fixed = fix_installed_freeldr(fat.read("freeldr.ini"))
				staged = install_dir / "freeldr.ini"
				staged.write_bytes(fixed)
				fat.set_attributes("freeldr.ini", "-r -h -s")
				fat.copy_in(staged, "freeldr.ini")
				fat.set_attributes("freeldr.ini", "+h +s")
		if b"ci: desktop" not in vm.serial_path.read_bytes():
			raise InstallError(f"the desktop stage did not report; see {install_dir / 'shots' / 'desktop'}")
		if not fat.exists("ReactOS/explorer.exe"):
			raise InstallError("explorer.exe is missing from the installed disk")
		disk.replace(golden)
		finished = True
	except (VmError, MtoolsError) as error:
		raise InstallError(str(error)) from error
	finally:
		vm.stop()
		derived.unlink(missing_ok=True)
		if not finished and not keep_disk_on_failure:
			disk.unlink(missing_ok=True)
	allocated_mb = os.stat(golden).st_blocks * 512 // (1024 * 1024)
	log("install", f"golden disk: {golden} ({allocated_mb} MB allocated); input hash {golden_key(recipe)}")
	return golden
