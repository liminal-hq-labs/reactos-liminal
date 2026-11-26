# `rl image`: turn the golden disk into the finished disk image, offline and in a build VM, with no hand step.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# The order is fixed and is the same for every recipe:
#
#   1. copy       the golden disk is copied (sparse) and never written
#   2. patchers   each patcher takes a stock file from the golden disk and yields a patched copy, which is written to the image
#   3. trim       the recipe's trim profile removes files; it never removes a patched file or a licence file
#   4. files      the recipe's own files, the Afterglow style and pointer files, and the shortcuts
#   5. settings   the build VM applies the registry settings and the page file, then shuts down
#
# Patchers run before the trim so that each one is checked against the stock file, and so that the trim cannot remove what a patcher
# wrote. A recipe cannot change this order.
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import settings as settings_module
from .afterglow import fetch_afterglow, prepare_afterglow
from .install import golden_path
from .lnk import make_lnk
from .log import log
from .mtools import FatImage
from .patchers import run_patchers
from .paths import ensure
from .recipe import Recipe
from .trim import LICENCE_PATHS, TrimReport, apply_profile, build_profile, check_profile
from .vm import PrivateVm

PIPELINE = ("copy", "patchers", "trim", "files", "settings")
DESKTOP = "Documents and Settings/Administrator/Desktop"


class ImageError(Exception):
	"""The image could not be built."""


@dataclass
class ImagePlan:
	golden: Path
	out: Path
	steps: list[str] = field(default_factory=list)

	def describe(self) -> str:
		lines = [f"golden disk: {self.golden}", f"image: {self.out}", "steps, in this order:"]
		lines += [f"  {number}. {step}" for number, step in enumerate(self.steps, 1)]
		return "\n".join(lines)


def plan_image(recipe: Recipe, work: Path, golden: Path | None = None, out: Path | None = None, with_settings: bool = True) -> ImagePlan:
	"""The plan, with nothing downloaded, written or run."""
	golden = golden or golden_path(recipe, work)
	out = out or work / "images" / f"{recipe.name}.img"
	patchers = recipe.section("patchers", "list")
	profile = build_profile(recipe.section("trim", "profile"), recipe.section("trim", "extra"))
	check_profile(profile, [])  # a list that reaches a licence file stops the plan, before anything runs
	plan = ImagePlan(golden, out)
	plan.steps.append("copy the golden disk (sparse); the golden disk is only read")
	plan.steps.append(
		"patchers: " + (", ".join(patchers) if patchers else "none") + " (each checked against the stock file; run before the trim)"
	)
	plan.steps.append(
		f"trim profile {profile.name!r}: {len(profile.entries)} entries; refuses a patched file or a licence file "
		f"({', '.join(LICENCE_PATHS)})"
	)
	for name, count in profile.sources[1:]:
		plan.steps.append(f"  extra trim list {name}: {count} entries, applied after the profile and checked the same way")
	extras = [f"{len(recipe.data['files'])} files", f"{len(recipe.data['shortcuts'])} shortcuts"]
	extras.append("the Afterglow style and pointers")
	extras.append(f"{len(recipe.section('settings', 'remove_desktop_shortcuts'))} stock desktop shortcuts removed")
	plan.steps.append("files: " + ", ".join(extras))
	if with_settings:
		names = list(settings_module.settings_files(recipe))
		plan.steps.append(
			f"settings: build VM applies {', '.join(names)} and the page file {recipe.section('settings', 'page_file')!r}, then shuts down"
		)
	else:
		plan.steps.append("settings: skipped (--no-settings)")
	return plan


def _copy_sparse(source: Path, destination: Path) -> None:
	destination.unlink(missing_ok=True)
	done = subprocess.run(
		["cp", "--sparse=always", "--reflink=auto", str(source), str(destination)], capture_output=True, text=True, check=False
	)
	if done.returncode != 0:
		raise ImageError(f"cannot copy the golden disk: {done.stderr.strip()}")
	destination.chmod(0o644)


def _write_payload(recipe: Recipe, disk: FatImage, afterglow_files: Path | None, scratch: Path) -> None:
	base = recipe.chain[0].parent
	for entry in recipe.data["files"]:
		source = (base / entry["source"]).resolve()
		if not source.is_file():
			raise ImageError(f"files: {source} is not a file")
		parent = entry["destination"].rsplit("/", 1)[0] if "/" in entry["destination"] else ""
		if parent:
			_make_path(disk, parent)
		disk.copy_in(source, entry["destination"])
	if afterglow_files is not None:
		themes = "ReactOS/Resources/Themes/Afterglow"
		_make_path(disk, themes)
		disk.copy_in(afterglow_files / "afterglow.msstyles", f"{themes}/afterglow.msstyles")
		cursors = afterglow_files / "cursors"
		if cursors.is_dir():
			_make_path(disk, "ReactOS/Cursors/Afterglow")
			for path in sorted(cursors.iterdir()):
				disk.copy_in(path, f"ReactOS/Cursors/Afterglow/{path.name}")
	for name in recipe.section("settings", "remove_desktop_shortcuts"):
		disk.delete_file(f"{DESKTOP}/{name}.lnk")
	for shortcut in recipe.data["shortcuts"]:
		link = scratch / "link.lnk"
		link.write_bytes(
			make_lnk(
				shortcut["target"],
				shortcut["arguments"],
				shortcut["working_dir"],
				shortcut["description"],
				shortcut["show"],
				shortcut["icon"],
				shortcut["icon_index"],
			)
		)
		disk.copy_in(link, f"{DESKTOP}/{shortcut['name']}.lnk")


def _make_path(disk: FatImage, path: str) -> None:
	built = ""
	for part in path.split("/"):
		built = f"{built}/{part}" if built else part
		disk.make_directory(built)


def build_image(
	recipe: Recipe,
	work: Path,
	golden: Path | None = None,
	out: Path | None = None,
	with_settings: bool = True,
	afterglow_tarball: Path | None = None,
	accel: str | None = None,
) -> Path:
	"""Build the image and return its path. The golden disk is never written."""
	golden = golden or golden_path(recipe, work)
	if not golden.is_file():
		raise ImageError(f"no golden disk at {golden}; run `rl install` first")
	out = out or work / "images" / f"{recipe.name}.img"
	if out.resolve() == golden.resolve():
		raise ImageError("the output must not be the golden disk")
	# Cheap checks first: the trim profile must not reach a licence file.
	profile = build_profile(recipe.section("trim", "profile"), recipe.section("trim", "extra"))
	check_profile(profile, [])
	out.parent.mkdir(parents=True, exist_ok=True)
	patcher_names = recipe.section("patchers", "list")

	source_tree = afterglow_files = None
	scratch_root = ensure(work, "scratch")
	if "afterglow" in recipe.data["inputs"]:
		source_tree = fetch_afterglow(recipe, work, afterglow_tarball)
		afterglow_files = prepare_afterglow(recipe, work, source_tree)

	with tempfile.TemporaryDirectory(dir=scratch_root) as scratch_name:
		scratch = Path(scratch_name)
		log("image", "1. copy the golden disk")
		_copy_sparse(golden, out)
		disk = FatImage(out)

		log("image", f"2. patchers: {', '.join(patcher_names) or 'none'}")
		patched = run_patchers(patcher_names, FatImage(golden), source_tree, afterglow_files, scratch)
		for item in patched:
			disk.copy_in(item.local_file, item.image_path)
		patched_paths = [item.image_path for item in patched]

		log("image", f"3. trim profile {profile.name}")
		report: TrimReport = apply_profile(disk, profile, patched_paths)
		for name, count in report.sources[1:]:
			log("image", f"   extra trim list {name}: {count} entries")
		log("image", f"   removed {len(report.removed)}, missing {len(report.missing)}, freed {report.bytes_freed // (1024 * 1024)} MiB")

		log("image", "4. files and shortcuts")
		_write_payload(recipe, disk, afterglow_files, scratch)

		if with_settings:
			log("image", "5. settings in the build VM")
			tree = scratch / "cd"
			settings_module.write_settings_cd_tree(recipe, tree, afterglow_files)
			iso = scratch / "setup.iso"
			settings_module.make_settings_iso(tree, iso)
			vm = PrivateVm(ensure(work, "build-vm"))
			spec = settings_module.build_vm_spec(out, iso, accel)
			try:
				settings_module.apply_in_guest(vm, spec)
			except settings_module.SettingsError as error:
				raise ImageError(str(error)) from error
	log("image", f"done: {out} ({disk.free_bytes() // (1024 * 1024)} MiB free inside)")
	return out


def trim_image(
	recipe: Recipe, work: Path, image: Path, profile_name: str | None = None, patched_paths: list[str] | None = None
) -> TrimReport:
	"""Trim a working copy of a disk in place. Refuses a disk in the work directory's golden folder."""
	if (work / "golden") in image.resolve().parents:
		raise ImageError("refusing to trim a golden disk; trim a copy (rl image makes one)")
	profile = build_profile(profile_name or recipe.section("trim", "profile"), recipe.section("trim", "extra"))
	return apply_profile(FatImage(image), profile, patched_paths or [])
