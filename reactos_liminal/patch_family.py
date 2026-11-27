# The icon patchers for files other than shell32.dll: `afterglow.cpl-icons`, `afterglow.program-icons` and `afterglow.dialog-icons`.
#
# The applets, the programs and file-type libraries, and the message-box icons of user32.dll (patched on top of the copy
# `afterglow.pointers` leaves). Each file is taken from the golden disk, guarded by the SHA-256 of the stock 0.4.16 file in
# `icon_families.json`, has the groups Afterglow's icon map verifies replaced, and is checked against `pins/icon-families.json`.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import json
from pathlib import Path

from .fetch import sha256_file
from .icon_map import load_map, module_groups, require_icon
from .log import log
from .mtools import FatImage
from .patch_base import PatchedFile, PatchError, is_trimmed, latest_patched
from .patch_icons import icon_set_digest, patch_icon_groups, require_pin, settle_result, verified_icons

FAMILIES_FILE = Path(__file__).resolve().parent / "icon_families.json"
PINS_FILE = Path(__file__).resolve().parent.parent / "pins" / "icon-families.json"


def load_families() -> dict:
	return json.loads(FAMILIES_FILE.read_text())["families"]


def load_pins() -> dict:
	return json.loads(PINS_FILE.read_text())


def module_name(file_spec: dict) -> str:
	"""The module name Afterglow's map uses for a file: the file's own name, unless the file is a copy that carries another module's
	resources (`agexplorer.exe` is `explorer.exe`, `agmsgina.dll` is `msgina.dll`) and says so in `module`."""
	return file_spec.get("module") or file_spec["path"].rsplit("/", 1)[-1]


def family_groups(entries: dict[str, dict], file_spec: dict) -> dict[int, str]:
	"""The groups to replace in one file, as `{group: Afterglow icon id}`: every group Afterglow's map verifies for the module, plus the
	file's own `groups` rows for groups the map does not name. Where the map names a group it decides."""
	groups = module_groups(entries, module_name(file_spec))
	for row in file_spec.get("groups", []):
		if row["group"] in groups:
			continue
		require_icon(entries, row["afterglow"], f"{file_spec['path']} group {row['group']}")
		groups[row["group"]] = row["afterglow"]
	return groups


def input_copy(file_spec: dict, scratch: Path) -> Path | None:
	"""The file a family patches in place of the stock one when an earlier patcher of this build already wrote its path
	(`user32.dll` from `afterglow.pointers`, `agexplorer.exe` from `afterglow.start`, `agmsgina.dll` from `afterglow.logon`): the
	newest such copy, so no earlier patcher's work is lost. The stock file (`stock_path`, by default the file's own path) is still
	checked against its hash. None when no earlier patcher wrote the path."""
	return latest_patched(scratch, file_spec["path"])


def run_family(family_name: str, golden: FatImage, source_tree: Path, scratch: Path) -> list[PatchedFile]:
	family = load_families()[family_name]
	pins = load_pins()["families"].get(family_name, {})
	entries = load_map(source_tree)
	wanted = {file_spec["path"]: family_groups(entries, file_spec) for file_spec in family["files"]}
	icons_by_id, icon_sums = verified_icons(source_tree, scratch, {icon_id for groups in wanted.values() for icon_id in groups.values()})
	inputs = {file_spec["path"]: input_copy(file_spec, scratch) for file_spec in family["files"]}
	for image_path, earlier in inputs.items():
		if earlier is not None:  # a file built on another patcher's result is pinned against that result too
			icon_sums[f"base/{image_path}"] = sha256_file(earlier)
	digest = icon_set_digest(icon_sums)
	expected_by_file = pins.get(digest)
	require_pin(digest, expected_by_file, family_name, PINS_FILE.name)
	results = []
	for file_spec in family["files"]:
		image_path = file_spec["path"]
		stock_path = file_spec.get("stock_path", image_path)
		if is_trimmed(image_path):
			log("patch", f"   {family_name}: {image_path} is removed by the trim, so it is left alone")
			continue
		if inputs[image_path] is None and file_spec.get("stock_path"):
			log("patch", f"   {family_name}: {image_path} is not written by an earlier patcher in this recipe, so it is left alone")
			continue
		flat = image_path.replace("/", "_")  # two files can share a name (the notepad.exe in ReactOS and in system32)
		stock_file = scratch / f"{family_name}-{flat}"
		golden.copy_out(stock_path, stock_file)
		actual = sha256_file(stock_file)
		if actual != file_spec["stock_sha256"]:
			raise PatchError(
				f"{stock_path} is not the stock file of ReactOS 0.4.16 i386 (SHA-256 {actual}, expected {file_spec['stock_sha256']}); "
				"its group and frame ids were checked against that one file only"
			)
		icons = {group: icons_by_id[icon_id] for group, icon_id in wanted[image_path].items()}
		try:
			patched_bytes, report = patch_icon_groups((inputs[image_path] or stock_file).read_bytes(), icons)
		except PatchError as error:
			raise PatchError(f"{image_path}: {error}") from error
		patched = scratch / f"{family_name}-{flat}.patched"
		patched.write_bytes(patched_bytes)
		result = sha256_file(patched)
		try:
			settle_result(family_name, digest, image_path, result, (expected_by_file or {}).get(image_path), PINS_FILE.name)
		except PatchError:
			patched.unlink(missing_ok=True)
			raise
		for line in report:
			if "fitted" in line:
				log("patch", f"   {image_path}: {line}")
		log("patch", f"   {family_name}: {image_path} patched, {len(report)} groups ({result})")
		results.append(PatchedFile(image_path, patched))
	return results


def cpl_icons(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch the Control Panel applets' icon groups with the Afterglow applet icons."""
	return run_family("cpl-icons", golden, source_tree, scratch)


def program_icons(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch the icons of the desktop and Start menu programs and of the file types that take theirs from a program or library."""
	return run_family("program-icons", golden, source_tree, scratch)


def dialog_icons(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch the message-box icons (the warning, question, error and information icons, and the default program icon) of user32.dll,
	on top of the copy `afterglow.pointers` made."""
	return run_family("dialog-icons", golden, source_tree, scratch)
