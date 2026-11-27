# The icon patchers for files other than shell32.dll: `afterglow.cpl-icons` (the Control Panel applets) and `afterglow.program-icons`
# (the programs ReactOS puts on the desktop and Start menu, and the file types whose icon comes from a program or library).
#
# Each file is taken from the golden disk, guarded by the SHA-256 of the stock 0.4.16 file, and has the groups listed in
# `icon_families.json` replaced by Afterglow's icons the way `patch_icons` does it. The result of each file is checked against
# `pins/icon-families.json`, keyed by the family and a digest of the icons used. Patched files stay in the work directory, never in git.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import json
from pathlib import Path

from .fetch import sha256_file
from .log import log
from .mtools import FatImage
from .patch_icons import _afterglow_sums, icon_set_digest, patch_icon_groups, render_icons
from .patchers import PatchedFile, PatchError

FAMILIES_FILE = Path(__file__).resolve().parent / "icon_families.json"
PINS_FILE = Path(__file__).resolve().parent.parent / "pins" / "icon-families.json"


def load_families() -> dict:
	return json.loads(FAMILIES_FILE.read_text())["families"]


def load_pins() -> dict:
	return json.loads(PINS_FILE.read_text())


def check_family_map(source_tree: Path, family: dict, family_name: str) -> None:
	"""Every Afterglow icon the family uses must be in Afterglow's map.json, and for the Control Panel applets be an applet there."""
	map_file = source_tree / "desktop" / "icons" / "map.json"
	if not map_file.is_file():
		raise PatchError(f"{map_file} is missing; the pinned Afterglow commit has no icon map")
	entries = {entry["id"]: entry for entry in json.loads(map_file.read_text())["icons"]}
	for file_spec in family["files"]:
		for row in file_spec["groups"]:
			entry = entries.get(row["afterglow"])
			if entry is None:
				raise PatchError(
					f"{family_name}: Afterglow's map.json has no icon {row['afterglow']!r} ({file_spec['path']} group {row['group']})"
				)
			if family["map_kind"] and entry.get("kind") != family["map_kind"]:
				raise PatchError(
					f"{family_name}: Afterglow's map.json lists {row['afterglow']!r} as {entry.get('kind')!r}, "
					f"expected {family['map_kind']!r}"
				)


def run_family(family_name: str, golden: FatImage, source_tree: Path, scratch: Path) -> list[PatchedFile]:
	family = load_families()[family_name]
	pins = load_pins()["families"].get(family_name, {})
	check_family_map(source_tree, family, family_name)
	render_dir = scratch / "icons"
	render_icons(source_tree, render_dir)
	afterglow_sums = _afterglow_sums(source_tree)
	icon_sums: dict[str, str] = {}
	for file_spec in family["files"]:
		for row in file_spec["groups"]:
			name = f"ico/{row['afterglow']}.ico"
			path = render_dir / name
			if not path.is_file():
				raise PatchError(f"Afterglow's render.py did not write {name}")
			sha = sha256_file(path)
			if sha != afterglow_sums.get(name):
				raise PatchError(f"{name} renders as {sha}, Afterglow records {afterglow_sums.get(name)}; the renderer or its tools differ")
			icon_sums[name] = sha
	digest = icon_set_digest(icon_sums)
	expected_by_file = pins.get(digest)
	if expected_by_file is None:
		raise PatchError(
			f"{family_name}: no pinned result for icon set {digest}; patch, check the results and add them to {PINS_FILE.name}"
		)
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
		icons = {row["group"]: (render_dir / "ico" / f"{row['afterglow']}.ico").read_bytes() for row in file_spec["groups"]}
		try:
			patched_bytes, report = patch_icon_groups(stock_file.read_bytes(), icons)
		except PatchError as error:
			raise PatchError(f"{image_path}: {error}") from error
		patched = scratch / f"{family_name}-{base}.patched"
		patched.write_bytes(patched_bytes)
		result = sha256_file(patched)
		if result != expected_by_file.get(image_path):
			patched.unlink(missing_ok=True)
			raise PatchError(f"patched {image_path} is {result}, expected {expected_by_file.get(image_path)}")
		log("patch", f"   {family_name}: {image_path} patched, {len(report)} groups ({result})")
		results.append(PatchedFile(image_path, patched))
	return results


def cpl_icons(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch the Control Panel applets' icon groups with the Afterglow applet icons."""
	return run_family("cpl-icons", golden, source_tree, scratch)


def program_icons(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch the icons of the desktop and Start menu programs and of the file types that take theirs from a program or library."""
	return run_family("program-icons", golden, source_tree, scratch)
