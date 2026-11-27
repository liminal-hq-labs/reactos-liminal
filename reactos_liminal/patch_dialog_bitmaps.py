# The `afterglow.dialog-bitmaps` patcher: the About banner, the Shut Down and Log Off dialogs' backgrounds, marks and button strips.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""shell32.dll draws the About box banner (131) and the line under it (138) and the Log Off dialog (500 to 502); msgina.dll draws the
Shut Down dialog (20002 to 20004), which the Start menu loads from `msgina.dll` by name and Winlogon loads from the GINA the
registry names (`agmsgina.dll`, RL-27). Each is a 24-bit RT_BITMAP written in place over the stock one, which has the same size and
depth, so nothing in the file moves and the PE checksum is recomputed. The list (module, id, size, depth, which Afterglow art) is the
`bitmaps` list of Afterglow's map.json; this repository holds only the files, each guarded by the stock file's SHA-256, and a
bitmap whose stock size or depth differs from what the map says is refused.

The patch builds on the newest copy an earlier patcher made of the same path (shell32.dll from `afterglow.icons`, `agmsgina.dll` from
`afterglow.logon` and the icon patchers), so the icons are kept. Its result is checked against `pins/icon-families.json`, keyed by a
digest of the art used and of those earlier copies, and stays in the work directory, never in git (ReactOS code).
"""

import json
from pathlib import Path

from . import pe_resources
from .fetch import sha256_file
from .icon_map import load_bitmaps
from .log import log
from .mtools import FatImage
from .patch_base import PatchedFile, PatchError, is_trimmed, latest_patched, render_art
from .patch_bitmaps import PINS_FILE
from .patch_family import module_name
from .patch_icons import icon_set_digest, require_pin, settle_result
from .pe_resource import PeError, PeFile, dib_from_bmp, dib_info, replace_bitmap

SPEC_FILE = Path(__file__).resolve().parent / "dialog_bitmaps.json"
FAMILY = "dialog-bitmaps"
SECTION_NAME = b".agbmp"
SECTION_FLAGS = 0x40000040  # initialized data, readable


def load_spec() -> dict:
	return json.loads(SPEC_FILE.read_text())


def art_folder_of(source_tree: Path, file: str) -> str:
	"""The folder of `file` in the Afterglow source, or the nearest one above it with a `render.py`."""
	folder = file.rsplit("/", 1)[0]
	while "/" in folder and not (source_tree / folder / "render.py").is_file():
		folder = folder.rsplit("/", 1)[0]
	return folder if (source_tree / folder / "render.py").is_file() else file.rsplit("/", 1)[0]


def render_bitmaps(source_tree: Path, scratch: Path, resources: list[dict]) -> dict[str, tuple[bytes, str]]:
	"""Render the art the resources name, one Afterglow art folder at a time (the folder of each entry's `file`, or the nearest folder
	above it that holds a `render.py`: the card faces sit in `desktop/cards/faces`, drawn by `desktop/cards/render.py`), and return
	`{bitmap file name: (BMP bytes, SHA-256)}`. Each file is checked against the sums Afterglow records for its folder."""
	by_folder: dict[str, list[str]] = {}
	for resource in resources:
		names = by_folder.setdefault(art_folder_of(source_tree, resource["file"]), [])
		if resource["bitmap"] not in names:
			names.append(resource["bitmap"])
	rendered: dict[str, tuple[bytes, str]] = {}
	for folder, names in sorted(by_folder.items()):
		made = render_art(source_tree / folder, scratch / "dialog-art" / folder.replace("/", "_"), names)
		for name, path in made.items():
			rendered[name] = (path.read_bytes(), sha256_file(path))
	return rendered


def write_bitmaps(stock: bytes, resources: list[dict], rendered: dict[str, tuple[bytes, str]]) -> tuple[bytes, list[str]]:
	"""Write each resource's art over the same bitmap of a PE file. Refuses a bitmap whose stock size or depth, or whose new size, is not
	the one the map records. Art of the stock depth goes over the old DIB where it is. Art at another depth (the 24-bit card backs over
	the 8-bit stock ones, which have no room for it) goes in a new section with the resource's entry pointed at it, as the icon patchers
	do; the width and height still match, so the program that loads it draws it the same way."""
	data = stock
	report = []
	grown: list[tuple[int, bytes]] = []
	try:
		for resource in resources:
			width, height = resource["size"]
			dib = dib_from_bmp(rendered[resource["bitmap"]][0])
			info = dib_info(dib)
			if (info.width, info.height, info.compression) != (width, height, 0) or info.bits_per_pixel not in (resource["bits"], 24):
				depths = " or ".join(f"{bits}-bit" for bits in sorted({resource["bits"], 24}))
				raise PatchError(f"{resource['bitmap']} is not a {width} x {height}, {depths} bitmap")
			slot = PeFile(data).bitmap(resource["resource"])
			old = dib_info(data[slot.data_offset : slot.data_offset + slot.size])
			if (old.width, old.height, old.bits_per_pixel, old.compression) != (width, height, resource["bits"], 0):
				raise PatchError(
					f"bitmap {resource['resource']} ({resource['name']}) is {old.width} x {old.height} at {old.bits_per_pixel} bits "
					f"in the file; the map says {width} x {height} at {resource['bits']}"
				)
			if info.bits_per_pixel == resource["bits"]:
				data = replace_bitmap(data, resource["resource"], dib, same_size=True)
				report.append(f"bitmap {resource['resource']} ({resource['name']}): {resource['bitmap']}")
			else:
				grown.append((resource["resource"], dib))
				report.append(
					f"bitmap {resource['resource']} ({resource['name']}): {resource['bitmap']}, {info.bits_per_pixel}-bit over the "
					f"stock {old.bits_per_pixel}-bit one, in a new section"
				)
		if grown:
			data = _write_grown(data, grown)
	except (PeError, pe_resources.PeError) as error:
		raise PatchError(f"the file cannot be patched: {error}") from error
	return data, report


def _write_grown(data: bytes, grown: list[tuple[int, bytes]]) -> bytes:
	"""Put the DIBs in one new section and point each bitmap's resource entry at its bytes."""
	pe = pe_resources.PeFile(data)
	entries = pe.data_entries(pe_resources.RT_BITMAP)
	content = bytearray()
	edits = []
	for resource_id, dib in grown:
		if len(entries.get(resource_id, [])) != 1:
			raise pe_resources.PeError(f"bitmap {resource_id} is not in the file in exactly one language")
		content += bytes(-len(content) % 4)
		edits.append((entries[resource_id][0], len(content), len(dib)))
		content += dib
	new_rva = pe.append_section(SECTION_NAME, bytes(content), SECTION_FLAGS)
	for entry, offset, size in edits:
		pe.point_entry_at(entry, new_rva + offset, size)
	pe.update_checksum()
	return pe.to_bytes()


def dialog_bitmaps(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Write the dialog bitmaps into shell32.dll, msgina.dll and agmsgina.dll."""
	spec = load_spec()
	pins = json.loads(PINS_FILE.read_text())["families"].get(FAMILY, {})
	resources = load_bitmaps(source_tree)
	rendered = render_bitmaps(source_tree, scratch, resources)
	sums = {f"bitmap/{name}": sha for name, (_bytes, sha) in rendered.items()}
	inputs = {file_spec["path"]: latest_patched(scratch, file_spec["path"]) for file_spec in spec["files"]}
	for image_path, earlier in inputs.items():
		if earlier is not None:
			sums[f"base/{image_path}"] = sha256_file(earlier)
	digest = icon_set_digest(sums)
	expected_by_file = pins.get(digest)
	require_pin(digest, expected_by_file, FAMILY, PINS_FILE.name)
	results = []
	for file_spec in spec["files"]:
		image_path = file_spec["path"]
		stock_path = file_spec.get("stock_path", image_path)
		mine = [resource for resource in resources if resource["module"] == module_name(file_spec)]
		if not mine:
			continue
		if is_trimmed(image_path):
			log("patch", f"   {FAMILY}: {image_path} is removed by the trim, so it is left alone")
			continue
		if inputs[image_path] is None and file_spec.get("stock_path"):
			log("patch", f"   {FAMILY}: {image_path} is not written by an earlier patcher in this recipe, so it is left alone")
			continue
		flat = image_path.replace("/", "_")
		stock_file = scratch / f"{FAMILY}-{flat}"
		golden.copy_out(stock_path, stock_file)
		actual = sha256_file(stock_file)
		if actual != file_spec["stock_sha256"]:
			raise PatchError(
				f"{stock_path} is not the stock file of ReactOS 0.4.16 i386 (SHA-256 {actual}, expected {file_spec['stock_sha256']}); "
				"its bitmap ids were checked against that one file only"
			)
		try:
			patched_bytes, report = write_bitmaps((inputs[image_path] or stock_file).read_bytes(), mine, rendered)
		except PatchError as error:
			raise PatchError(f"{image_path}: {error}") from error
		patched = scratch / f"{FAMILY}-{flat}.patched"
		patched.write_bytes(patched_bytes)
		result = sha256_file(patched)
		try:
			settle_result(FAMILY, digest, image_path, result, (expected_by_file or {}).get(image_path), PINS_FILE.name)
		except PatchError:
			patched.unlink(missing_ok=True)
			raise
		for line in report:
			log("patch", f"   {image_path}: {line}")
		log("patch", f"   {FAMILY}: {image_path} patched, {len(report)} bitmaps ({result})")
		results.append(PatchedFile(image_path, patched))
	return results
