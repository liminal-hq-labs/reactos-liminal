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
#   4. files      ReactOS's stock wallpapers when the recipe replaces them, then the recipe's own files, the Afterglow wallpapers, style and
#                 pointer files, and the shortcuts
#   5. licences   `LICENSES/`, `NOTICE.txt` and `CHANGES.txt`, made from the recipe and from what steps 2 to 4 did
#   6. settings   the build VM applies the registry settings and the page file, then shuts down
#
# Patchers run before the trim so that each one is checked against the stock file, and so that the trim cannot remove what a patcher
# wrote. A recipe cannot change this order.
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import settings as settings_module
from .afterglow import fetch_afterglow, prepare_afterglow
from .audit import audit_image
from .fetch import sha256_file
from .install import golden_path
from .licences import TEXTS, ChangeRecord, PatchChange, write_licence_files
from .lnk import make_lnk
from .log import log
from .mtools import FatImage
from .patch_base import skipping
from .patchers import run_patchers
from .paths import ensure
from .recipe import Recipe
from .rustbuild import BUILT_PREFIX, build_programs, used_builds
from .trim import LICENCE_PATHS, SHORTCUTS_SOURCE, TrimReport, apply_profile, build_profile, check_profile, removes
from .vm import PrivateVm
from .wallpaper import FOLDER as wallpaper_folder_path
from .wallpaper import WallpaperError, image_path, render_set, render_wallpaper, scenes, set_destination, stock_list, wanted

PIPELINE = ("copy", "patchers", "trim", "files", "licences", "settings")
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
		f"trim profile {profile.name!r}: {profile.sources[0][1]} entries; refuses a patched file or a licence file "
		f"({', '.join(LICENCE_PATHS)})"
	)
	for name, count in profile.sources[1:]:
		if name == SHORTCUTS_SOURCE:
			plan.steps.append(f"  shortcuts of the programs removed ({name}): {count} entries, in every user's profile")
		else:
			plan.steps.append(f"  extra trim list {name}: {count} entries, applied after the profile and checked the same way")
	if used_builds(recipe):
		plan.steps.insert(
			0, "build: " + ", ".join(used_builds(recipe)) + " from source (pinned toolchain; output checked against its SHA-256)"
		)
	extras = [f"{len(recipe.data['files'])} files", f"{len(recipe.data['shortcuts'])} shortcuts"]
	extras.append("the Afterglow style and pointers")
	if wanted(recipe) and _wallpaper_file_entry(recipe):
		extras.append(f"the wallpaper {recipe.section('settings', 'wallpaper')} comes from [[files]] (no scene rendered)")
	elif wanted(recipe):
		extras.append(f"the {wanted(recipe)} wallpaper rendered from its SVG master to {recipe.section('settings', 'wallpaper')}")
	if recipe.section("wallpapers", "replace_stock"):
		extras.append(f"ReactOS's {len(stock_list().entries)} stock wallpaper files removed first")
	if scenes(recipe):
		extras.append(f"{len(scenes(recipe))} Afterglow wallpapers rendered into the wallpaper folder ({wallpaper_folder_path})")
	extras.append(f"{len(recipe.section('settings', 'remove_desktop_shortcuts'))} stock desktop shortcuts removed")
	plan.steps.append("files: " + ", ".join(extras))
	plan.steps.append(
		f"licences: {', '.join(text.image_name for text in TEXTS)} in LICENSES, then NOTICE.txt and CHANGES.txt (the list of patched files "
		"with their sums, the trim and the settings)"
	)
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


def _wallpaper_file_entry(recipe: Recipe) -> dict | None:
	"""The `[[files]]` entry that writes `settings.wallpaper`, if the recipe has one."""
	if "wallpaper" not in recipe.section("settings"):
		return None
	target = image_path(recipe.section("settings", "wallpaper")).lower()
	for entry in recipe.data["files"]:
		if entry["destination"].replace("\\", "/").strip("/").lower() == target:
			return entry
	return None


def _write_wallpaper(recipe: Recipe, disk: FatImage, source_tree: Path | None, scratch: Path) -> None:
	"""Render the recipe's Afterglow wallpaper and write it to `settings.wallpaper`, unless a `[[files]]` entry writes that path (the
	recipe's own file wins, and nothing is rendered)."""
	if wanted(recipe) is None or source_tree is None:
		return
	target = image_path(recipe.section("settings", "wallpaper"))
	if _wallpaper_file_entry(recipe):
		log("image", f"   wallpaper: [[files]] already writes {target}, so the Afterglow scene is not rendered")
		return
	try:
		bitmap = render_wallpaper(recipe, source_tree, scratch)
	except WallpaperError as error:
		raise ImageError(str(error)) from error
	if "/" in target:
		_make_path(disk, target.rsplit("/", 1)[0])
	disk.copy_in(bitmap, target)


def _replace_stock_wallpapers(recipe: Recipe, disk: FatImage, patched_paths: list[str], record: ChangeRecord) -> None:
	"""Remove ReactOS's own wallpapers (`profiles/wallpapers/stock.txt`) when the recipe says `wallpapers.replace_stock`, so the list
	in Display Properties holds only what the recipe puts there. The same guard as the trim applies: a patched file or a licence file is
	never removed. A file that is not there (a trim has removed it) is skipped."""
	if not recipe.section("wallpapers", "replace_stock"):
		return
	stock = stock_list()
	check_profile(stock, patched_paths)
	for entry in stock.entries:
		if disk.delete_tree(entry.path) if entry.kind == "d" else disk.delete_file(entry.path):
			record.stock_wallpapers_removed.append(entry.path)
	log("image", f"   replaced stock wallpapers: removed {len(record.stock_wallpapers_removed)} of {len(stock.entries)} files")


def _write_wallpaper_set(recipe: Recipe, disk: FatImage, source_tree: Path | None, scratch: Path) -> None:
	"""Render the recipe's `wallpapers.scenes` and write them, in name order, to the folder Display Properties lists. The scene that is
	the desktop wallpaper is already written (to `settings.wallpaper`), and a `[[files]]` entry for a scene's path replaces the scene."""
	names = scenes(recipe)
	if not names or source_tree is None:
		return
	taken = {entry["destination"].replace("\\", "/").strip("/").lower() for entry in recipe.data["files"]}
	if "wallpaper" in recipe.section("settings"):
		taken.add(image_path(recipe.section("settings", "wallpaper")).lower())
	todo = [name for name in names if set_destination(name).lower() not in taken]
	try:
		bitmaps = render_set(recipe, source_tree, scratch, todo)
	except WallpaperError as error:
		raise ImageError(str(error)) from error
	_make_path(disk, wallpaper_folder_path)
	for name in todo:
		disk.copy_in(bitmaps[name], set_destination(name))


def _write_payload(
	recipe: Recipe,
	disk: FatImage,
	afterglow_files: Path | None,
	scratch: Path,
	source_tree: Path | None = None,
	built: dict[str, Path] | None = None,
) -> None:
	base = recipe.chain[0].parent
	_write_wallpaper(recipe, disk, source_tree, scratch)
	_write_wallpaper_set(recipe, disk, source_tree, scratch)
	for entry in recipe.data["files"]:
		if entry["source"].startswith(BUILT_PREFIX):
			source = (built or {})[entry["source"][len(BUILT_PREFIX) :]]
		else:
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


def _written_paths(recipe: Recipe, afterglow_files: Path | None) -> list[str]:
	"""The paths the files step added, for `CHANGES.txt`."""
	paths = [entry["destination"] for entry in recipe.data["files"]]
	if afterglow_files is not None:
		if wanted(recipe) and not _wallpaper_file_entry(recipe):
			paths.append(image_path(recipe.section("settings", "wallpaper")))
		paths += [set_destination(name) for name in scenes(recipe) if set_destination(name) not in paths]
	if afterglow_files is not None:
		paths.append("ReactOS/Resources/Themes/Afterglow/afterglow.msstyles")
		cursors = afterglow_files / "cursors"
		if cursors.is_dir():
			paths += [f"ReactOS/Cursors/Afterglow/{path.name}" for path in sorted(cursors.iterdir())]
	paths += [f"{DESKTOP}/{shortcut['name']}.lnk" for shortcut in recipe.data["shortcuts"]]
	return paths


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

	built = build_programs(recipe, work)
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
		record = ChangeRecord(trim_profile=profile.name, settings_applied=with_settings)
		golden_disk = FatImage(golden)
		patched = []
		# A patcher leaves alone a file this recipe's trim removes (the patch list does not change, so the pins do not), because a trim
		# that reaches a patched file is an error.
		for patcher_name in patcher_names:
			with skipping(lambda path: removes(profile, path)):
				made = run_patchers([patcher_name], golden_disk, source_tree, afterglow_files, scratch)
			for item in made:
				before = "(not on the stock disk)"
				if golden_disk.exists(item.image_path):
					stock = scratch / "stock.bin"
					golden_disk.copy_out(item.image_path, stock)
					before = sha256_file(stock)
					stock.unlink()
				record.patched.append(PatchChange(patcher_name, item.image_path, before, sha256_file(item.local_file)))
				patched.append(item)
		# Several patchers can write one path, each building on the last copy; only the final copy goes to the disk.
		final = {item.image_path.lower(): item for item in patched}
		patched = [item for item in patched if final[item.image_path.lower()] is item]
		for item in patched:
			if item.attributes:  # a hidden, system or read-only file (freeldr.ini) is unlocked for the write and locked again after
				disk.set_attributes(item.image_path, "-r -h -s")
			disk.copy_in(item.local_file, item.image_path)
			if item.attributes:
				disk.set_attributes(item.image_path, item.attributes)
		patched_paths = [item.image_path for item in patched]

		log("image", f"3. trim profile {profile.name}")
		report: TrimReport = apply_profile(disk, profile, patched_paths)
		record.trim = report
		for name, count in report.sources[1:]:
			what = "shortcuts of the programs removed" if name == SHORTCUTS_SOURCE else "extra trim list"
			log("image", f"   {what} {name}: {count} entries")
		log("image", f"   removed {len(report.removed)}, missing {len(report.missing)}, freed {report.bytes_freed // (1024 * 1024)} MiB")

		log("image", "4. files and shortcuts")
		_replace_stock_wallpapers(recipe, disk, patched_paths, record)
		_write_payload(recipe, disk, afterglow_files, scratch, source_tree, built)
		record.written_files = _written_paths(recipe, afterglow_files)

		log("image", "5. licences, notice and changes")
		write_licence_files(disk, recipe, record, scratch)

		if with_settings:
			log("image", "6. settings in the build VM")
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
	_log_audit(out)
	log("image", f"done: {out} ({disk.free_bytes() // (1024 * 1024)} MiB free inside)")
	return out


def _log_audit(image: Path) -> None:
	"""Say what the finished image launches that is not on its disk. Reported, not fatal: `rl audit` is the check that fails."""
	report = audit_image(FatImage(image))
	blocking = report.blocking()
	log(
		"image",
		f"audit: {len(report.findings)} entries checked, {len(report.dead)} dead, {len(blocking)} in a menu, at logon or in the applets",
	)
	for finding in blocking:
		log("image", f"   dead {finding.kind}: {finding.where} -> {finding.target}")


def trim_image(
	recipe: Recipe, work: Path, image: Path, profile_name: str | None = None, patched_paths: list[str] | None = None
) -> TrimReport:
	"""Trim a working copy of a disk in place. Refuses a disk in the work directory's golden folder."""
	if (work / "golden") in image.resolve().parents:
		raise ImageError("refusing to trim a golden disk; trim a copy (rl image makes one)")
	profile = build_profile(profile_name or recipe.section("trim", "profile"), recipe.section("trim", "extra"))
	return apply_profile(FatImage(image), profile, patched_paths or [])
