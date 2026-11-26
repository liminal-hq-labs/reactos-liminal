# The icon patchers for files other than shell32.dll: `afterglow.cpl-icons` (the Control Panel applets) and `afterglow.program-icons`
# (the programs ReactOS puts on the desktop and Start menu, and the file types whose icon comes from a program or library).
#
# Each file is taken from the golden disk, guarded by the SHA-256 of the stock 0.4.16 file listed in `icon_families.json`, and has the
# groups Afterglow's icon map verifies for it replaced by Afterglow's icons, the way `patch_icons` does it. The result of each file is
# checked against `pins/icon-families.json`, keyed by the family and a digest of the icons used. Patched files stay in the work
# directory, never in git.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import json
from pathlib import Path

from .fetch import sha256_file
from .icon_map import load_map, module_groups, require_icon
from .log import log
from .mtools import FatImage
from .patch_base import PatchedFile, PatchError
from .patch_icons import icon_set_digest, patch_icon_groups, require_pin, settle_result, verified_icons

FAMILIES_FILE = Path(__file__).resolve().parent / "icon_families.json"
PINS_FILE = Path(__file__).resolve().parent.parent / "pins" / "icon-families.json"


def load_families() -> dict:
	return json.loads(FAMILIES_FILE.read_text())["families"]


def load_pins() -> dict:
	return json.loads(PINS_FILE.read_text())


def family_groups(entries: dict[str, dict], file_spec: dict) -> dict[int, str]:
	"""The groups to replace in one file, as `{group: Afterglow icon id}`: every group Afterglow's map verifies for the module, plus the
	file's own `groups` rows for groups the map does not name. Where the map names a group it decides."""
	groups = module_groups(entries, file_spec["path"].rsplit("/", 1)[-1])
	for row in file_spec.get("groups", []):
		if row["group"] in groups:
			continue
		require_icon(entries, row["afterglow"], f"{file_spec['path']} group {row['group']}")
		groups[row["group"]] = row["afterglow"]
	return groups


def run_family(family_name: str, golden: FatImage, source_tree: Path, scratch: Path) -> list[PatchedFile]:
	family = load_families()[family_name]
	pins = load_pins()["families"].get(family_name, {})
	entries = load_map(source_tree)
	wanted = {file_spec["path"]: family_groups(entries, file_spec) for file_spec in family["files"]}
	icons_by_id, icon_sums = verified_icons(source_tree, scratch, {icon_id for groups in wanted.values() for icon_id in groups.values()})
	digest = icon_set_digest(icon_sums)
	expected_by_file = pins.get(digest)
	require_pin(digest, expected_by_file, family_name, PINS_FILE.name)
	results = []
	for file_spec in family["files"]:
		image_path = file_spec["path"]
		base = image_path.rsplit("/", 1)[-1]
		stock_file = scratch / f"{family_name}-{base}"
		golden.copy_out(image_path, stock_file)
		actual = sha256_file(stock_file)
		if actual != file_spec["stock_sha256"]:
			raise PatchError(
				f"{image_path} is not the stock file of ReactOS 0.4.16 i386 (SHA-256 {actual}, expected {file_spec['stock_sha256']}); "
				"its group and frame ids were checked against that one file only"
			)
		icons = {group: icons_by_id[icon_id] for group, icon_id in wanted[image_path].items()}
		try:
			patched_bytes, report = patch_icon_groups(stock_file.read_bytes(), icons)
		except PatchError as error:
			raise PatchError(f"{image_path}: {error}") from error
		patched = scratch / f"{family_name}-{base}.patched"
		patched.write_bytes(patched_bytes)
		result = sha256_file(patched)
		try:
			settle_result(family_name, digest, image_path, result, (expected_by_file or {}).get(image_path), PINS_FILE.name)
		except PatchError:
			patched.unlink(missing_ok=True)
			raise
		log("patch", f"   {family_name}: {image_path} patched, {len(report)} groups ({result})")
		results.append(PatchedFile(image_path, patched))
	return results


def cpl_icons(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch the Control Panel applets' icon groups with the Afterglow applet icons."""
	return run_family("cpl-icons", golden, source_tree, scratch)


def program_icons(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch the icons of the desktop and Start menu programs and of the file types that take theirs from a program or library."""
	return run_family("program-icons", golden, source_tree, scratch)
