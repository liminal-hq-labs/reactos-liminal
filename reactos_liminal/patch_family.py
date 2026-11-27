# The icon patchers for files other than shell32.dll: `afterglow.cpl-icons`, `afterglow.program-icons`, `afterglow.dialog-icons` and
# `afterglow.map-icons`.
#
# The applets, the programs and file-type libraries, the message-box icons of user32.dll (patched on top of the copy `afterglow.pointers`
# leaves) and every other module the map names (the games, the accessories, the remaining applets). Each file is taken from the golden
# disk, guarded by the SHA-256 of the stock 0.4.16 file in `icon_families.json`, has the groups Afterglow's icon map verifies replaced,
# and is checked against `pins/icon-families.json`.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import json
from pathlib import Path

from .fetch import sha256_file
from .icon_dll import build_icon_dll
from .icon_map import ColourEdit, MapResource, load_colours, load_map, module_resources, require_icon
from .log import log
from .mtools import FatImage
from .patch_base import PatchedFile, PatchError, is_trimmed, latest_patched, note_created, note_patched, note_skipped
from .patch_icons import icon_set_digest, patch_icon_groups, require_pin, settle_result, stock_group_problem, verified_icons
from .pe_resources import PeError, PeFile

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


def family_resources(entries: dict[str, dict], file_spec: dict) -> dict[int, MapResource]:
	"""The groups to replace in one file, as `{group: MapResource}`: every group Afterglow's map verifies for the module, plus the
	file's own `groups` rows for groups the map does not name (verified in this repository from the source and the stock file, so
	their evidence is `table`). Where the map names a group it decides."""
	groups = module_resources(entries, module_name(file_spec))
	for row in file_spec.get("groups", []):
		if row["group"] in groups:
			continue
		require_icon(entries, row["afterglow"], f"{file_spec['path']} group {row['group']}")
		groups[row["group"]] = MapResource(row["afterglow"], ("table",))
	return groups


def family_groups(entries: dict[str, dict], file_spec: dict) -> dict[int, str]:
	"""`family_resources` as `{group: Afterglow icon id}`."""
	return {group: resource.icon_id for group, resource in family_resources(entries, file_spec).items()}


def usable_groups(stock: bytes, module: str, image_path: str, resources: dict[int, MapResource]) -> dict[int, str]:
	"""The groups of `resources` to write into a file, as `{group: icon id}`. A group verified in the stock binary (by Afterglow or by
	this repository's table) is trusted, and a missing one is an error in the patch. A group the map verified from the ReactOS source
	alone is checked against the stock file here: when it is missing, or is not an icon group the patcher can fill, it is left alone,
	logged, and listed in the coverage report."""
	usable: dict[int, str] = {}
	for group, resource in sorted(resources.items()):
		problem = None if resource.seen_in_binary else stock_group_problem(stock, group)
		if problem is None:
			usable[group] = resource.icon_id
			if not resource.seen_in_binary:
				log(
					"patch",
					f"   {image_path}: group {group} ({resource.icon_id}) is verified from the source only; the stock file holds it",
				)
		else:
			log("patch", f"   {image_path}: group {group} ({resource.icon_id}) is left alone: {problem}")
			note_skipped(module, group, f"verified from the source only, and {problem}")
	return usable


def input_copy(file_spec: dict, scratch: Path) -> Path | None:
	"""The file a family patches in place of the stock one when an earlier patcher of this build already wrote its path
	(`user32.dll` from `afterglow.pointers`, `agexplorer.exe` from `afterglow.start`, `agmsgina.dll` from `afterglow.logon`): the
	newest such copy, so no earlier patcher's work is lost. The stock file (`stock_path`, by default the file's own path) is still
	checked against its hash. None when no earlier patcher wrote the path."""
	return latest_patched(scratch, file_spec["path"])


def write_colours(data: bytes, edits: list[ColourEdit], image_path: str) -> bytes:
	"""Write each colour edit over the bytes the map says the stock code holds there, and refuse when they are not those bytes. The
	file is the stock file (its SHA-256 is checked by the caller), so a refusal means the map and the binary disagree."""
	patched = bytearray(data)
	for edit in edits:
		end = edit.offset + len(edit.stock)
		found = bytes(patched[edit.offset : end])
		if found != edit.stock:
			raise PatchError(
				f"{image_path} holds {found.hex(' ')} at {edit.offset:#x}, not the {edit.stock.hex(' ')} Afterglow's map records for "
				f"the {edit.colour_id} colour ({edit.instruction}); the offset was checked against the stock file only"
			)
		patched[edit.offset : end] = edit.afterglow
	return bytes(patched)


def new_file_bytes(image_path: str, golden: FatImage, groups: dict[int, str], icons_by_id: dict[str, bytes]) -> bytes:
	"""The bytes of a file the stock disk does not have and the family creates: a resource-only DLL with the icon groups the map names for
	it. Refuses when the stock disk has a file of that name, because the patch was written for a ReactOS that ships none."""
	if golden.exists(image_path):
		raise PatchError(f"{image_path} is on the stock disk; the patch creates it and was written for a ReactOS that ships none")
	if not groups:
		raise PatchError(f"Afterglow's map names no icon group for {image_path}")
	try:
		return build_icon_dll({group: icons_by_id[icon_id] for group, icon_id in groups.items()})
	except PeError as error:
		raise PatchError(f"{image_path} cannot be written: {error}") from error


def run_family(family_name: str, golden: FatImage, source_tree: Path, scratch: Path) -> list[PatchedFile]:
	family = load_families()[family_name]
	pins = load_pins()["families"].get(family_name, {})
	entries = load_map(source_tree)
	resources = {file_spec["path"]: family_resources(entries, file_spec) for file_spec in family["files"]}
	icon_ids = {resource.icon_id for found in resources.values() for resource in found.values()}
	icons_by_id, icon_sums = verified_icons(source_tree, scratch, icon_ids)
	colours = {file_spec["path"]: load_colours(source_tree, module_name(file_spec)) for file_spec in family["files"]}
	for image_path, edits in colours.items():  # a changed colour in the map is a new icon set, so a new pin
		for edit in edits:
			icon_sums[f"colour/{image_path}/{edit.offset:#x}"] = edit.afterglow.hex()
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
		module = module_name(file_spec)
		if is_trimmed(image_path):
			log("patch", f"   {family_name}: {image_path} is removed by the trim, so it is left alone")
			continue
		if file_spec.get("new_file"):
			patched_bytes = new_file_bytes(
				image_path, golden, {group: res.icon_id for group, res in resources[image_path].items()}, icons_by_id
			)
			flat = image_path.replace("/", "_")
			patched = scratch / f"{family_name}-{flat}.patched"
			patched.write_bytes(patched_bytes)
			result = sha256_file(patched)
			try:
				settle_result(family_name, digest, image_path, result, (expected_by_file or {}).get(image_path), PINS_FILE.name)
			except PatchError:
				patched.unlink(missing_ok=True)
				raise
			note_created(image_path)
			for group, resource in resources[image_path].items():
				note_patched(module, group, resource.icon_id, image_path)
			log("patch", f"   {family_name}: {image_path} created, {len(resources[image_path])} groups ({result})")
			results.append(PatchedFile(image_path, patched))
			continue
		if not golden.exists(stock_path):
			log("patch", f"   {family_name}: {stock_path} is not on the stock disk, so it is left alone")
			for group in resources[image_path]:
				note_skipped(module, group, f"{stock_path} is not on the stock disk")
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
		wanted = usable_groups(stock_file.read_bytes(), module, image_path, resources[image_path])
		if not wanted and not colours[image_path]:
			log("patch", f"   {family_name}: {image_path} has no group to replace, so it is left alone")
			continue
		icons = {group: icons_by_id[icon_id] for group, icon_id in wanted.items()}
		try:
			base = write_colours((inputs[image_path] or stock_file).read_bytes(), colours[image_path], image_path)
			if wanted:
				patched_bytes, report = patch_icon_groups(base, icons)
			else:
				report = []
				pe = PeFile(base)
				pe.update_checksum()
				patched_bytes = pe.to_bytes()
		except (PatchError, PeError) as error:
			raise PatchError(f"{image_path}: {error}") from error
		patched = scratch / f"{family_name}-{flat}.patched"
		patched.write_bytes(patched_bytes)
		result = sha256_file(patched)
		try:
			settle_result(family_name, digest, image_path, result, (expected_by_file or {}).get(image_path), PINS_FILE.name)
		except PatchError:
			patched.unlink(missing_ok=True)
			raise
		for group, icon_id in wanted.items():
			note_patched(module, group, icon_id, image_path)
		for line in report:
			if "fitted" in line:
				log("patch", f"   {image_path}: {line}")
		for edit in colours[image_path]:
			log(
				"patch",
				f"   {image_path}: the {edit.colour_id} colour at {edit.offset:#x}: {edit.stock.hex(' ')} -> {edit.afterglow.hex(' ')}",
			)
		log("patch", f"   {family_name}: {image_path} patched, {len(report)} groups, {len(colours[image_path])} colours ({result})")
		results.append(PatchedFile(image_path, patched))
	return results


def cpl_icons(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch the Control Panel applets' icon groups with the Afterglow applet icons."""
	return run_family("cpl-icons", golden, source_tree, scratch)


def program_icons(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch the icons of the desktop and Start menu programs and of the file types that take theirs from a program or library."""
	return run_family("program-icons", golden, source_tree, scratch)


def map_icons(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch the icons of every other module the map names: the games, the accessories, the applets and programs the other families do
	not list. A module the active trim removes is left alone, so the list is the same for the full and the compact image."""
	return run_family("map-icons", golden, source_tree, scratch)


def dialog_icons(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch the message-box icons (the warning, question, error and information icons, and the default program icon) of user32.dll,
	on top of the copy `afterglow.pointers` made."""
	return run_family("dialog-icons", golden, source_tree, scratch)
