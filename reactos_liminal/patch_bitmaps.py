# The `afterglow.toolbar-bitmaps` patcher: replace cells of the Explorer toolbar strips in a copy of browseui.dll with Afterglow's icons.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""browseui.dll keeps the toolbar images as four RT_BITMAP strips (24 px and 16 px cells, normal and hot), 32 bits per pixel with
straight alpha, loaded as image lists whose cell is as wide as the strip is tall. A cell is replaced in place, so each strip keeps
its id, size and depth and nothing in the file moves; a bitmap that differs in size or depth from the one the table expects is
refused. The 16 px cells are Afterglow's 16 px frames; the 24 px cells are made by halving its 48 px frames (a premultiplied 2 x 2
average in integer arithmetic, so the result does not depend on a library version), because Afterglow does not render 24 px. The
hot strips get the same cells as the normal ones. The result is checked against `pins/icon-families.json` and stays in the work
directory, never in git.
"""

import json
import struct
from pathlib import Path

from .fetch import sha256_file
from .icon_map import load_map, require_icon, toolbar_cells
from .log import log
from .mtools import FatImage
from .patch_base import PatchedFile, PatchError, note_patched
from .patch_icons import icon_set_digest, require_pin, settle_result, verified_icons
from .pe_resources import RT_BITMAP, PeError, PeFile, read_ico

STRIPS_FILE = Path(__file__).resolve().parent / "bitmap_strips.json"
PINS_FILE = Path(__file__).resolve().parent.parent / "pins" / "icon-families.json"
FAMILY = "toolbar-bitmaps"
HEADER_SIZE = 40


def load_strips() -> dict:
	return json.loads(STRIPS_FILE.read_text())


def frame_rows(ico_bytes: bytes, size: int) -> list[bytes]:
	"""The pixel rows (bottom row first, BGRA) of the `size` px frame of an .ico."""
	for width, height, bit_count, image in read_ico(ico_bytes):
		if width == height == size:
			if bit_count != 32:
				raise PatchError(f"the {size} px frame is {bit_count}-bit, expected 32")
			pixels = image[HEADER_SIZE : HEADER_SIZE + size * size * 4]
			return [pixels[row * size * 4 : (row + 1) * size * 4] for row in range(size)]
	raise PatchError(f"the icon has no {size} px frame")


def halve(rows: list[bytes]) -> list[bytes]:
	"""Half the size: each pixel is the alpha-weighted average of a 2 x 2 block, in integers."""
	size = len(rows) // 2
	out = []
	for row in range(size):
		line = bytearray()
		for column in range(size):
			block = [rows[2 * row + dy][(2 * column + dx) * 4 : (2 * column + dx) * 4 + 4] for dy in (0, 1) for dx in (0, 1)]
			alpha_total = sum(pixel[3] for pixel in block)
			if alpha_total == 0:
				line += bytes(4)
				continue
			for channel in range(3):
				weighted = sum(pixel[channel] * pixel[3] for pixel in block)
				line.append((2 * weighted + alpha_total) // (2 * alpha_total))
			line.append((alpha_total + 2) // 4)
		out.append(bytes(line))
	return out


def cell_rows(ico_bytes: bytes, cell: int) -> list[bytes]:
	if cell == 24:
		return halve(frame_rows(ico_bytes, 48))
	return frame_rows(ico_bytes, cell)


def patch_strips(stock: bytes, strips: list[dict], cells: list[dict], icons: dict[str, bytes]) -> tuple[bytes, list[str]]:
	"""Write the cells into every strip. `icons` maps an Afterglow id to its .ico bytes."""
	try:
		pe = PeFile(stock)
		bitmaps = pe.data_entries(RT_BITMAP)
		report = []
		for strip in strips:
			if strip["id"] not in bitmaps:
				raise PatchError(f"the file has no bitmap {strip['id']}")
			entry = bitmaps[strip["id"]][0]
			start, size = pe.entry_location(entry)
			header = pe.data[start : start + HEADER_SIZE]
			header_size, width, height, planes, bit_count, compression = struct.unpack_from("<IiiHHI", header, 0)
			cell = strip["cell"]
			if (header_size, width, height, planes, bit_count, compression) != (40, cell * strip["count"], cell, 1, 32, 0):
				raise PatchError(
					f"bitmap {strip['id']} is {width}x{height} at {bit_count} bits; expected {cell * strip['count']}x{cell} at 32 "
					"(a bitmap is replaced only by one of the same size and depth)"
				)
			if size != HEADER_SIZE + width * height * 4:
				raise PatchError(f"bitmap {strip['id']} has {size} bytes, expected {HEADER_SIZE + width * height * 4}")
			pixels = bytearray(pe.data[start + HEADER_SIZE : start + size])
			stride = width * 4
			for item in cells:
				if not 0 <= item["index"] < strip["count"]:
					raise PatchError(f"cell {item['index']} is outside bitmap {strip['id']}")
				rows = cell_rows(icons[item["afterglow"]], cell)
				for row, line in enumerate(rows):
					offset = row * stride + item["index"] * cell * 4
					pixels[offset : offset + cell * 4] = line
			pe.overwrite_entry(entry, bytes(pe.data[start : start + HEADER_SIZE]) + bytes(pixels))
			report.append(f"bitmap {strip['id']}: {len(cells)} cells of {cell} px")
		pe.update_checksum()
		return pe.to_bytes(), report
	except PeError as error:
		raise PatchError(f"the file cannot be patched: {error}") from error


def strip_cells(entries: dict[str, dict], file_spec: dict) -> list[dict]:
	"""The cells to replace in one file, as `[{"index", "afterglow"}]`: every cell Afterglow's map verifies for the module, plus the
	file's own `cells` rows for cells the map does not name. Where the map names a cell it decides."""
	strip_ids = [strip["id"] for strip in file_spec["strips"]]
	named = toolbar_cells(entries, file_spec["path"].rsplit("/", 1)[-1], strip_ids)
	cells = {index: icon_id for index, icon_id in named.items()}
	for item in file_spec.get("cells", []):
		if item["index"] not in cells:
			require_icon(entries, item["afterglow"], f"toolbar cell {item['index']}")
			cells[item["index"]] = item["afterglow"]
	return [{"index": index, "afterglow": icon_id} for index, icon_id in sorted(cells.items())]


def toolbar_bitmaps(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch the Explorer toolbar strips in a copy of browseui.dll."""
	spec = load_strips()
	pins = json.loads(PINS_FILE.read_text())["families"].get(FAMILY, {})
	entries = load_map(source_tree)
	results = []
	for file_spec in spec["files"]:
		cells = strip_cells(entries, file_spec)
		icons, icon_sums = verified_icons(source_tree, scratch, {item["afterglow"] for item in cells})
		digest = icon_set_digest(icon_sums)
		expected = (pins.get(digest) or {}).get(file_spec["path"])
		require_pin(digest, expected, FAMILY, PINS_FILE.name)
		stock_file = scratch / "browseui.dll"
		golden.copy_out(file_spec["path"], stock_file)
		actual = sha256_file(stock_file)
		if actual != file_spec["stock_sha256"]:
			raise PatchError(
				f"{file_spec['path']} is not the stock browseui.dll of ReactOS 0.4.16 i386 (SHA-256 {actual}, expected "
				f"{file_spec['stock_sha256']}); the bitmap ids and cell indexes were checked against that one file only"
			)
		patched_bytes, report = patch_strips(stock_file.read_bytes(), file_spec["strips"], cells, icons)
		patched = scratch / "browseui-afterglow.dll"
		patched.write_bytes(patched_bytes)
		result = sha256_file(patched)
		try:
			settle_result(FAMILY, digest, file_spec["path"], result, expected, PINS_FILE.name)
		except PatchError:
			patched.unlink(missing_ok=True)
			raise
		for item in cells:
			note_patched(file_spec["path"].rsplit("/", 1)[-1], item["index"], item["afterglow"], file_spec["path"], "cell")
		for line in report:
			log("patch", f"   {line}")
		log("patch", f"   {FAMILY}: {file_spec['path']} patched, {len(cells)} cells ({result})")
		results.append(PatchedFile(file_spec["path"], patched))
	return results
