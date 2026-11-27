# The `afterglow.start` patcher: the Afterglow Start button orb and Start menu banner in a copy of ReactOS's explorer.exe.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# explorer.exe holds the Start button image as bitmap 143 (25 x 20, 32 bit, straight alpha) and the strip down the left of the Start
# menu as bitmap 158 (21 x 233, 24 bit). The patcher replaces both in place with DIBs of the same size and format, fixes the PE checksum
# and writes the result as `agexplorer.exe` beside the stock file, which stays untouched. A registry value, `Winlogon\Shell`, selects the
# copy (the `shell-agexplorer` settings file), so the off switch is one value. The art is Afterglow's: `desktop/start/render.py` draws
# the two DIBs from vector masters and Afterglow records their SHA-256.
#
# It is ReactOS code (LGPL-2.1) and stays in the work directory, never in git.
import hashlib
import struct
import subprocess
from pathlib import Path

from .fetch import sha256_file
from .log import log
from .mtools import FatImage
from .patch_base import PatchedFile, PatchError

STOCK_PATH = "ReactOS/explorer.exe"
PATCHED_PATH = "ReactOS/agexplorer.exe"
STOCK_SIZE = 1841664
STOCK_SHA256 = "4e54225b041fe93ce0b252c6fda3c6c3cdae6203ba6a2d1e5b77873cd86488f7"
# The sum of the patched file for the art Afterglow pins at the commit the recipe names; a different render is refused.
PATCHED_SHA256 = "0e5ae3a18c64aa92b77a6811fec241d193047991dd7af5221ff06c43806ae859"
RT_BITMAP = 2
# resource id: (width, height, bits per pixel, resource size in the file, DIB file name)
SLOTS = {143: (25, 20, 32, 2040, "start-orb.dib"), 158: (21, 233, 24, 14954, "start-banner.dib")}


def _u16(data, offset: int) -> int:
	return struct.unpack_from("<H", data, offset)[0]


def _u32(data, offset: int) -> int:
	return struct.unpack_from("<I", data, offset)[0]


class PortableExecutable:
	"""Just enough of a PE32 image to find a bitmap resource and the checksum field."""

	def __init__(self, data: bytes):
		self.data = data
		header = _u32(data, 0x3C)
		if data[header : header + 4] != b"PE\0\0":
			raise PatchError("explorer.exe is not a PE file")
		coff = header + 4
		section_count = _u16(data, coff + 2)
		optional_size = _u16(data, coff + 16)
		optional = coff + 20
		if _u16(data, optional) != 0x10B:
			raise PatchError("explorer.exe is not PE32")
		self.checksum_offset = optional + 64
		self.resource_rva = _u32(data, optional + 96 + 2 * 8)
		self.sections = []
		cursor = optional + optional_size
		for _ in range(section_count):
			virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", data, cursor + 8)
			self.sections.append((virtual_address, max(virtual_size, raw_size), raw_size, raw_offset))
			cursor += 40

	def file_offset(self, rva: int) -> int:
		for virtual_address, span, raw_size, raw_offset in self.sections:
			if virtual_address <= rva < virtual_address + span:
				if rva - virtual_address >= raw_size:
					raise PatchError(f"RVA {rva:#x} is past the raw data of its section")
				return raw_offset + rva - virtual_address
		raise PatchError(f"RVA {rva:#x} is in no section")

	def _entries(self, offset: int):
		named, ids = _u16(self.data, offset + 12), _u16(self.data, offset + 14)
		for index in range(named + ids):
			entry = offset + 16 + 8 * index
			yield _u32(self.data, entry), _u32(self.data, entry + 4)

	def bitmap(self, resource_id: int) -> tuple[int, int]:
		"""The file offset and size of a bitmap resource, which must have exactly one language."""
		base = self.file_offset(self.resource_rva)
		for type_id, type_sub in self._entries(base):
			if type_id != RT_BITMAP or not type_sub & 0x80000000:
				continue
			for name_id, name_sub in self._entries(base + (type_sub & 0x7FFFFFFF)):
				if name_id != resource_id or not name_sub & 0x80000000:
					continue
				languages = list(self._entries(base + (name_sub & 0x7FFFFFFF)))
				if len(languages) != 1 or languages[0][1] & 0x80000000:
					raise PatchError(f"bitmap {resource_id} has an unexpected language layout")
				entry = base + languages[0][1]
				return self.file_offset(_u32(self.data, entry)), _u32(self.data, entry + 4)
		raise PatchError(f"bitmap {resource_id} is not in explorer.exe")


def pe_checksum(data: bytes, checksum_offset: int) -> int:
	"""The PE checksum: 16-bit words summed with carry, the checksum field itself skipped, plus the file length."""
	total = 0
	padded = data + (b"\0" if len(data) % 2 else b"")
	for offset in range(0, len(padded), 2):
		if offset in (checksum_offset, checksum_offset + 2):
			continue
		total += _u16(padded, offset)
		total = (total & 0xFFFF) + (total >> 16)
	total = (total & 0xFFFF) + (total >> 16)
	return (total + len(data)) & 0xFFFFFFFF


def dib_header(dib: bytes) -> tuple[int, int, int, int, int]:
	"""(header size, width, height, bits per pixel, compression) of a DIB."""
	header_size, width, height, _planes, bits, compression = struct.unpack_from("<IiiHHI", dib, 0)
	return header_size, width, height, bits, compression


def patch_explorer(stock: bytes, dibs: dict[int, bytes]) -> bytes:
	"""A copy of the stock explorer.exe with each bitmap replaced by the DIB for its id. Refuses any other file, and any DIB that is
	not the exact size and format of the resource it replaces."""
	if len(stock) != STOCK_SIZE or _sha256(stock) != STOCK_SHA256:
		raise PatchError(f"explorer.exe is not the stock ReactOS 0.4.16 file ({len(stock)} bytes, SHA-256 {_sha256(stock)}); refused")
	image = PortableExecutable(stock)
	data = bytearray(stock)
	for resource_id, (width, height, bits, size, _name) in SLOTS.items():
		offset, current = image.bitmap(resource_id)
		if current != size or dib_header(stock[offset : offset + current]) != (40, width, height, bits, 0):
			raise PatchError(f"bitmap {resource_id} is not the stock {width} x {height}, {bits} bit image; refused")
		dib = dibs[resource_id]
		if len(dib) != size or dib_header(dib) != (40, width, height, bits, 0):
			raise PatchError(
				f"the art for bitmap {resource_id} must be a {size} byte {width} x {height}, {bits} bit DIB with no compression"
			)
		data[offset : offset + size] = dib
	struct.pack_into("<I", data, image.checksum_offset, pe_checksum(bytes(data), image.checksum_offset))
	return bytes(data)


def _sha256(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


def _render_art(source_tree: Path, scratch: Path) -> dict[int, bytes]:
	"""Render the DIBs with Afterglow's own script and check each against the sum Afterglow records."""
	tool = source_tree / "desktop" / "start" / "render.py"
	sums_file = source_tree / "desktop" / "start" / "SHA256SUMS"
	if not tool.is_file() or not sums_file.is_file():
		raise PatchError(f"{source_tree} has no desktop/start; the Afterglow pin is older than the Start orb masters")
	art = scratch / "start-art"
	done = subprocess.run(["python3", "-I", str(tool), str(art)], capture_output=True, text=True, check=False)
	if done.returncode != 0:
		raise PatchError(f"desktop/start/render.py failed: {(done.stderr or done.stdout).strip()[-400:]}")
	recorded = {}
	for line in sums_file.read_text().splitlines():
		parts = line.split()
		if len(parts) == 2:
			recorded[parts[1]] = parts[0]
	dibs = {}
	for resource_id, (_w, _h, _b, _size, name) in SLOTS.items():
		path = art / name
		actual = sha256_file(path)
		if actual != recorded.get(name):
			raise PatchError(f"{name} is {actual}, Afterglow records {recorded.get(name)}")
		dibs[resource_id] = path.read_bytes()
	return dibs


def afterglow_start(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Write `agexplorer.exe`: the stock explorer.exe with the Afterglow Start orb and menu banner. Checked against the stock hash
	first and against the pinned sum of the result last."""
	stock = scratch / "explorer.exe"
	golden.copy_out(STOCK_PATH, stock)
	dibs = _render_art(source_tree, scratch)
	patched_bytes = patch_explorer(stock.read_bytes(), dibs)
	actual = _sha256(patched_bytes)
	if actual != PATCHED_SHA256:
		raise PatchError(f"patched explorer.exe is {actual}, expected {PATCHED_SHA256}")
	patched = scratch / "agexplorer.exe"
	patched.write_bytes(patched_bytes)
	log("patch", f"   afterglow.start: agexplorer.exe written ({actual})")
	return [PatchedFile(PATCHED_PATH, patched)]
