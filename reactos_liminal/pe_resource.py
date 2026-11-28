# Read a 32-bit PE file's bitmap resources and replace one in place, with the standard library only.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# A bitmap resource (RT_BITMAP, type 2) is a DIB: a BITMAPINFOHEADER, the colour table, then the pixels, without the 14-byte file
# header. Replacing one here never moves any other byte: the new DIB is written over the old one's slot, the resource's size field is
# updated when it changes, and the PE checksum is recomputed. The patchers (patch_logon.py, patch_boot.py) hold the guards.
import struct
from dataclasses import dataclass

RT_BITMAP = 2
FILE_HEADER = 14  # the BITMAPFILEHEADER a .bmp carries and a resource does not


class PeError(Exception):
	"""The file is not a PE32 image this module can read, or the resource is not there."""


@dataclass(frozen=True)
class DibInfo:
	width: int
	height: int
	bits_per_pixel: int
	compression: int
	header_size: int
	colours_used: int


@dataclass(frozen=True)
class Slot:
	"""Where a bitmap resource sits in the file."""

	entry_offset: int  # the resource data entry (RVA, size, code page, reserved)
	data_offset: int  # the first byte of the DIB in the file
	size: int  # the DIB's size as the entry records it
	room: int  # bytes from the DIB's start to the next resource's start, or to the end of the section's raw data


def u16(data: bytes | bytearray, offset: int) -> int:
	return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes | bytearray, offset: int) -> int:
	return struct.unpack_from("<I", data, offset)[0]


def dib_info(dib: bytes | bytearray) -> DibInfo:
	header_size, width, height, _planes, bits, compression, _image_size, _xppm, _yppm, used, _important = struct.unpack_from(
		"<IiiHHIIiiII", dib, 0
	)
	return DibInfo(width, height, bits, compression, header_size, used)


def dib_from_bmp(bmp: bytes) -> bytes:
	"""The resource form of a .bmp file: everything after the 14-byte file header."""
	if bmp[:2] != b"BM":
		raise PeError("the bitmap is not a .bmp file")
	return bmp[FILE_HEADER:]


def pe_checksum(data: bytes | bytearray, checksum_offset: int) -> int:
	"""The checksum the PE header records: the 16-bit words summed with end-around carry, the checksum field itself left out, plus the
	file length."""
	padded = bytes(data) + (b"\0" if len(data) % 2 else b"")
	total = 0
	for offset in range(0, len(padded), 2):
		if offset in (checksum_offset, checksum_offset + 2):
			continue
		total += u16(padded, offset)
		total = (total & 0xFFFF) + (total >> 16)
	total = (total & 0xFFFF) + (total >> 16)
	return (total + len(data)) & 0xFFFFFFFF


class PeFile:
	"""A parsed PE32 image over `data`. Parsing never writes."""

	def __init__(self, data: bytes | bytearray):
		self.data = data
		pe_offset = u32(data, 0x3C) if len(data) > 0x40 else 0
		if data[pe_offset : pe_offset + 4] != b"PE\0\0":
			raise PeError("not a PE file")
		coff = pe_offset + 4
		section_count = u16(data, coff + 2)
		optional_size = u16(data, coff + 16)
		self.optional = coff + 20
		if u16(data, self.optional) != 0x10B:
			raise PeError("not a PE32 image")
		self.checksum_offset = self.optional + 64
		if u32(data, self.optional + 92) < 3:
			raise PeError("the image has no resource directory")
		self.resource_rva = u32(data, self.optional + 96 + 2 * 8)
		self.sections: list[tuple[int, int, int, int]] = []  # virtual address, virtual size, raw offset, raw size
		position = self.optional + optional_size
		for _ in range(section_count):
			virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", data, position + 8)
			self.sections.append((virtual_address, virtual_size, raw_offset, raw_size))
			position += 40

	def file_offset(self, rva: int) -> int:
		for virtual_address, virtual_size, raw_offset, raw_size in self.sections:
			if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
				if rva - virtual_address >= raw_size:
					raise PeError(f"RVA {rva:#x} is past the raw data of its section")
				return raw_offset + (rva - virtual_address)
		raise PeError(f"RVA {rva:#x} is in no section")

	def _entries(self, directory: int):
		named, ids = u16(self.data, directory + 12), u16(self.data, directory + 14)
		for index in range(named + ids):
			entry = directory + 16 + 8 * index
			yield u32(self.data, entry), u32(self.data, entry + 4)

	def _data_entries(self, base: int, directory: int):
		for _name, target in self._entries(directory):
			if target & 0x80000000:
				yield from self._data_entries(base, base + (target & 0x7FFFFFFF))
			else:
				yield base + target

	def bitmap(self, resource_id: int) -> Slot:
		"""The slot of bitmap `resource_id`. A bitmap in more than one language is refused: it has no single slot to replace."""
		base = self.file_offset(self.resource_rva)
		for type_id, type_target in self._entries(base):
			if type_id != RT_BITMAP or not type_target & 0x80000000:
				continue
			for item_id, item_target in self._entries(base + (type_target & 0x7FFFFFFF)):
				if item_id != resource_id or not item_target & 0x80000000:
					continue
				languages = list(self._entries(base + (item_target & 0x7FFFFFFF)))
				if len(languages) != 1 or languages[0][1] & 0x80000000:
					raise PeError(f"bitmap {resource_id} is in {len(languages)} languages, not one")
				entry = base + languages[0][1]
				rva, size = u32(self.data, entry), u32(self.data, entry + 4)
				starts = [u32(self.data, other) for other in self._data_entries(base, base)]
				section_end = rva + size
				for virtual_address, virtual_size, _raw_offset, raw_size in self.sections:
					if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
						section_end = virtual_address + raw_size
				following = min([start for start in starts if start > rva] + [section_end])
				return Slot(entry, self.file_offset(rva), size, following - rva)
		raise PeError(f"bitmap {resource_id} is not in the file")


def replace_bitmap(data: bytes, resource_id: int, dib: bytes, same_size: bool) -> bytes:
	"""A copy of `data` with bitmap `resource_id` replaced by `dib`, which is written over the old DIB. With `same_size` the new DIB
	must be exactly as long as the old one. Otherwise it may be shorter or equal; the rest of the slot is zeroed and the resource's
	size field is lowered. The PE checksum is recomputed. Nothing else changes."""
	pe = PeFile(data)
	slot = pe.bitmap(resource_id)
	if same_size and len(dib) != slot.size:
		raise PeError(f"bitmap {resource_id}: the new DIB is {len(dib)} bytes and the slot is {slot.size}")
	if len(dib) > slot.size:
		raise PeError(f"bitmap {resource_id}: the new DIB is {len(dib)} bytes and the slot holds {slot.size}")
	patched = bytearray(data)
	patched[slot.data_offset : slot.data_offset + slot.size] = dib + b"\0" * (slot.size - len(dib))
	struct.pack_into("<I", patched, slot.entry_offset + 4, len(dib))
	struct.pack_into("<I", patched, pe.checksum_offset, pe_checksum(patched, pe.checksum_offset))
	return bytes(patched)


KEY = (255, 0, 255)


def _palette(dib: bytes | bytearray, info: DibInfo) -> tuple[int, int]:
	"""Where a palette DIB's colour table starts and how many entries it has."""
	return info.header_size, info.colours_used or (1 << info.bits_per_pixel)


def _pixel_offsets(dib: bytes | bytearray, info: DibInfo):
	"""The offset of each pixel of a 24 or 32-bit DIB (rows padded to four bytes)."""
	step = info.bits_per_pixel // 8
	stride = (info.width * step + 3) & ~3
	for row in range(abs(info.height)):
		start = info.header_size + row * stride
		for column in range(info.width):
			yield start + column * step


def has_exact_key(dib: bytes | bytearray) -> bool:
	"""True when the bitmap uses magenta, exactly 255, 0, 255, as its transparent colour: a colour table that holds it (up to 8 bits), or
	a 24 or 32-bit bitmap with a pixel of it. ReactOS's `GdiTransparentBlt` callers key on that value only."""
	info = dib_info(dib)
	if info.bits_per_pixel <= 8:
		start, count = _palette(dib, info)
		return any(tuple(dib[start + 4 * index + 2 : start + 4 * index - 1 : -1]) == KEY for index in range(count))
	if info.bits_per_pixel in (24, 32):
		return any((dib[offset + 2], dib[offset + 1], dib[offset]) == KEY for offset in _pixel_offsets(dib, info))
	return False


def snap_key(dib: bytes | bytearray) -> tuple[bytes, int]:
	"""The bitmap with every colour near magenta (red and blue at least 200, green at most 80) set to exactly 255, 0, 255, and how many
	pixels or palette entries changed. Art that is drawn on a magenta key and then resampled or quantised ends up at 254, 0, 255 and
	with a few pinker edge pixels; the key is then not transparent. Nothing else in such art is that close to magenta."""
	data = bytearray(dib)
	info = dib_info(data)
	changed = 0

	def near(red: int, green: int, blue: int) -> bool:
		return red >= 200 and blue >= 200 and green <= 80 and (red, green, blue) != KEY

	if info.bits_per_pixel <= 8:
		start, count = _palette(data, info)
		for index in range(count):
			base = start + 4 * index
			if near(data[base + 2], data[base + 1], data[base]):
				data[base + 2], data[base + 1], data[base] = KEY
				changed += 1
	elif info.bits_per_pixel in (24, 32):
		for offset in _pixel_offsets(data, info):
			if near(data[offset + 2], data[offset + 1], data[offset]):
				data[offset + 2], data[offset + 1], data[offset] = KEY
				changed += 1
	return bytes(data), changed
