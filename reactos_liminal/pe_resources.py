# A small reader and writer for the parts of a 32-bit PE file the icon patcher needs: the section table, the resource directory, icon
# groups, a new appended section and the checksum. Standard library only.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import struct
from dataclasses import dataclass

RT_BITMAP = 2
RT_ICON = 3
RT_GROUP_ICON = 14
DIRECTORY_RESOURCE = 2  # index of the resource table in the data directory
HIGH_BIT = 0x80000000


class PeError(Exception):
	"""A file that is not the PE layout this code was written for."""


def align_up(value: int, alignment: int) -> int:
	return (value + alignment - 1) // alignment * alignment


@dataclass(frozen=True)
class Section:
	name: str
	virtual_size: int
	virtual_address: int
	raw_size: int
	raw_offset: int

	@property
	def extent(self) -> int:
		return max(self.virtual_size, self.raw_size)


@dataclass(frozen=True)
class GroupFrame:
	"""One entry of an RT_GROUP_ICON directory."""

	width: int  # 0 means 256
	height: int
	colours: int
	planes: int
	bit_count: int
	size: int
	icon_id: int


class PeFile:
	"""A PE32 image held in memory. `data_entry_offset` values are file offsets of an IMAGE_RESOURCE_DATA_ENTRY."""

	def __init__(self, data: bytes):
		self.data = bytearray(data)
		if self.data[:2] != b"MZ":
			raise PeError("not a PE file (no MZ header)")
		self.pe_offset = struct.unpack_from("<I", self.data, 0x3C)[0]
		if self.data[self.pe_offset : self.pe_offset + 4] != b"PE\0\0":
			raise PeError("not a PE file (no PE signature)")
		self.section_count = struct.unpack_from("<H", self.data, self.pe_offset + 6)[0]
		optional_size = struct.unpack_from("<H", self.data, self.pe_offset + 20)[0]
		self.optional = self.pe_offset + 24
		if struct.unpack_from("<H", self.data, self.optional)[0] != 0x10B:
			raise PeError("not a PE32 file")
		self.section_alignment, self.file_alignment = struct.unpack_from("<II", self.data, self.optional + 32)
		self.headers_size = struct.unpack_from("<I", self.data, self.optional + 60)[0]
		self.section_table = self.optional + optional_size
		self.sections = [self._read_section(index) for index in range(self.section_count)]
		self._resource_rva, self._resource_size = struct.unpack_from("<II", self.data, self.optional + 96 + 8 * DIRECTORY_RESOURCE)
		if not self._resource_rva:
			raise PeError("the file has no resource directory")
		self._resource_raw = self.rva_to_offset(self._resource_rva)

	def _read_section(self, index: int) -> Section:
		name, virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
			"<8sIIII", self.data, self.section_table + 40 * index
		)
		return Section(name.rstrip(b"\0").decode("ascii", "replace"), virtual_size, virtual_address, raw_size, raw_offset)

	def rva_to_offset(self, rva: int) -> int:
		for section in self.sections:
			if section.virtual_address <= rva < section.virtual_address + section.extent:
				return section.raw_offset + (rva - section.virtual_address)
		raise PeError(f"RVA {rva:#x} is in no section")

	# --- the resource directory -------------------------------------------------------------------------------------------------

	def _entries(self, directory_offset: int):
		"""The (name or id, target) pairs of one resource directory; `directory_offset` is relative to the resource table."""
		named, ids = struct.unpack_from("<HH", self.data, self._resource_raw + directory_offset + 12)
		for index in range(named + ids):
			yield struct.unpack_from("<II", self.data, self._resource_raw + directory_offset + 16 + 8 * index)

	def _name(self, name_offset: int) -> str:
		"""The string a named resource entry points at (a length in characters, then UTF-16LE), as the compiler wrote it."""
		start = self._resource_raw + name_offset
		length = struct.unpack_from("<H", self.data, start)[0]
		return bytes(self.data[start + 2 : start + 2 + 2 * length]).decode("utf-16-le")

	def data_entries(self, resource_type: int) -> dict[int | str, list[int]]:
		"""Resource id (or name, for a resource the module names by string) -> file offsets of its data entries, one per language, for
		one resource type."""
		found: dict[int | str, list[int]] = {}
		for type_id, type_target in self._entries(0):
			if type_id != resource_type or not type_target & HIGH_BIT:
				continue
			for resource_id, id_target in self._entries(type_target & ~HIGH_BIT):
				if not id_target & HIGH_BIT:
					continue
				key = self._name(resource_id & ~HIGH_BIT) if resource_id & HIGH_BIT else resource_id
				for _language, language_target in self._entries(id_target & ~HIGH_BIT):
					if language_target & HIGH_BIT:
						raise PeError(f"resource {resource_type}/{key} has a directory where a language entry should be")
					found.setdefault(key, []).append(self._resource_raw + language_target)
		return found

	def entry_data(self, data_entry_offset: int) -> bytes:
		rva, size = struct.unpack_from("<II", self.data, data_entry_offset)
		start = self.rva_to_offset(rva)
		return bytes(self.data[start : start + size])

	def entry_location(self, data_entry_offset: int) -> tuple[int, int]:
		"""The file offset and size of the bytes a data entry points at."""
		rva, size = struct.unpack_from("<II", self.data, data_entry_offset)
		return self.rva_to_offset(rva), size

	def overwrite_entry(self, data_entry_offset: int, content: bytes) -> None:
		"""Replace a resource's bytes where they are; the new bytes must be exactly as long as the old."""
		start, size = self.entry_location(data_entry_offset)
		if len(content) != size:
			raise PeError(f"the new resource is {len(content)} bytes, the old one {size}")
		self.data[start : start + size] = content

	def point_entry_at(self, data_entry_offset: int, rva: int, size: int) -> None:
		struct.pack_into("<II", self.data, data_entry_offset, rva, size)

	# --- writing ----------------------------------------------------------------------------------------------------------------

	def append_section(self, name: bytes, content: bytes, characteristics: int) -> int:
		"""Add a section after the last one and return its RVA. Refuses when the header has no room for another section header."""
		if self.section_table + 40 * (self.section_count + 1) > self.headers_size:
			raise PeError("the file has no room for another section header")
		first_raw = min(section.raw_offset for section in self.sections if section.raw_size)
		if self.section_table + 40 * (self.section_count + 1) > first_raw:
			raise PeError("the file has no room for another section header before its first section")
		last = self.sections[-1]
		new_rva = align_up(last.virtual_address + last.extent, self.section_alignment)
		new_raw = align_up(len(self.data), self.file_alignment)
		raw_size = align_up(len(content), self.file_alignment)
		self.data += bytes(new_raw - len(self.data))
		self.data += content + bytes(raw_size - len(content))
		header = struct.pack("<8sIIIIIIHHI", name, len(content), new_rva, raw_size, new_raw, 0, 0, 0, 0, characteristics)
		start = self.section_table + 40 * self.section_count
		self.data[start : start + 40] = header
		self.section_count += 1
		struct.pack_into("<H", self.data, self.pe_offset + 6, self.section_count)
		struct.pack_into("<I", self.data, self.optional + 56, align_up(new_rva + len(content), self.section_alignment))
		self.sections.append(self._read_section(self.section_count - 1))
		return new_rva

	def update_checksum(self) -> None:
		struct.pack_into("<I", self.data, self.optional + 64, 0)
		length = len(self.data) - (len(self.data) & 1)
		total = sum(struct.unpack_from(f"<{length // 2}H", self.data, 0))  # Python ints do not overflow, so fold the carry at the end
		if len(self.data) & 1:
			total += self.data[-1]
		total = (total & 0xFFFF) + (total >> 16)
		total = (total & 0xFFFF) + (total >> 16)
		struct.pack_into("<I", self.data, self.optional + 64, (total & 0xFFFF) + len(self.data))

	def to_bytes(self) -> bytes:
		return bytes(self.data)


def parse_group(data: bytes) -> list[GroupFrame]:
	"""The frames of an RT_GROUP_ICON resource (GRPICONDIR followed by 14-byte entries)."""
	if len(data) < 6:
		raise PeError("an icon group is shorter than its header")
	reserved, kind, count = struct.unpack_from("<HHH", data, 0)
	if reserved != 0 or kind != 1 or len(data) != 6 + 14 * count:
		raise PeError("an icon group is malformed")
	frames = []
	for index in range(count):
		width, height, colours, _reserved, planes, bit_count, size, icon_id = struct.unpack_from("<BBBBHHIH", data, 6 + 14 * index)
		frames.append(GroupFrame(width or 256, height or 256, colours, planes, bit_count, size, icon_id))
	return frames


def build_group(frames: list[GroupFrame]) -> bytes:
	out = struct.pack("<HHH", 0, 1, len(frames))
	for frame in frames:
		out += struct.pack(
			"<BBBBHHIH",
			0 if frame.width >= 256 else frame.width,
			0 if frame.height >= 256 else frame.height,
			frame.colours,
			0,
			frame.planes,
			frame.bit_count,
			frame.size,
			frame.icon_id,
		)
	return out


def read_ico(data: bytes) -> list[tuple[int, int, int, bytes]]:
	"""The frames of an .ico file as (width, height, bit count, DIB bytes), in file order. Only DIB frames are accepted, because the
	resource loaders of older Windows and ReactOS read those."""
	reserved, kind, count = struct.unpack_from("<HHH", data, 0)
	if reserved != 0 or kind != 1 or count == 0:
		raise PeError("not an .ico file")
	frames = []
	for index in range(count):
		width, height, _colours, _reserved, _planes, bit_count, size, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * index)
		image = data[offset : offset + size]
		if len(image) != size or image[:4] != struct.pack("<I", 40):
			raise PeError("an .ico frame is not an uncompressed DIB")
		frames.append((width or 256, height or 256, bit_count, image))
	return frames
