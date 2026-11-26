# Synthetic PE files for the icon and bitmap patcher tests: a small DLL with icon groups, icons and bitmaps laid out like ReactOS's.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import struct

from reactos_liminal.pe_resources import RT_BITMAP, RT_GROUP_ICON, RT_ICON, GroupFrame, PeFile, build_group, parse_group

FILE_ALIGNMENT = 512
SECTION_ALIGNMENT = 4096


def dib(size: int, fill: int) -> bytes:
	"""A 32-bit icon frame (a BITMAPINFOHEADER of twice the height, BGRA rows, a zero AND mask) of one colour."""
	pixels = bytes([fill, fill, fill, 255]) * size * size
	mask = bytes(((size + 31) // 32 * 4) * size)
	return struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, len(pixels) + len(mask), 0, 0, 0, 0) + pixels + mask


def ico(fill: int, sizes=(16, 32, 48), bit_count=32) -> bytes:
	frames = [dib(size, fill) for size in sizes]
	out = struct.pack("<HHH", 0, 1, len(frames))
	offset = 6 + 16 * len(frames)
	for size, frame in zip(sizes, frames, strict=True):
		out += struct.pack("<BBBBHHII", size, size, 0, 0, 1, bit_count, len(frame), offset)
		offset += len(frame)
	return out + b"".join(frames)


def resource_tree(
	groups: dict[int, list[tuple[int, int, int]]], frames: dict[int, bytes], base_rva: int, bitmaps: dict[int, bytes]
) -> bytes:
	"""A resource section: RT_ICON frames and RT_GROUP_ICON groups. `groups` maps a group id to (icon id, size, bits) tuples."""
	type_ids = [RT_BITMAP, RT_ICON, RT_GROUP_ICON]
	resources = {RT_BITMAP: sorted(bitmaps), RT_ICON: sorted(frames), RT_GROUP_ICON: sorted(groups)}
	# Directory sizes: root; one id directory per type; one language directory per resource; one data entry per resource.
	root_size = 16 + 8 * len(type_ids)
	offset = root_size
	type_offsets = {}
	for type_id in type_ids:
		type_offsets[type_id] = offset
		offset += 16 + 8 * len(resources[type_id])
	language_offsets = {}
	for type_id in type_ids:
		for resource_id in resources[type_id]:
			language_offsets[(type_id, resource_id)] = offset
			offset += 16 + 8
	data_entry_offsets = {}
	for key in language_offsets:
		data_entry_offsets[key] = offset
		offset += 16
	payload_start = offset
	payloads = {}
	blob = bytearray()
	for type_id in type_ids:
		for resource_id in resources[type_id]:
			data = (
				bitmaps[resource_id]
				if type_id == RT_BITMAP
				else frames[resource_id]
				if type_id == RT_ICON
				else build_group(
					[GroupFrame(size, size, 0, 1, bits, len(frames[icon_id]), icon_id) for icon_id, size, bits in groups[resource_id]]
				)
			)
			payloads[(type_id, resource_id)] = (payload_start + len(blob), len(data))
			blob += data + bytes(-len(data) % 4)
	out = bytearray()
	out += struct.pack("<IIHHHH", 0, 0, 0, 0, 0, len(type_ids))
	for type_id in type_ids:
		out += struct.pack("<II", type_id, 0x80000000 | type_offsets[type_id])
	for type_id in type_ids:
		out += struct.pack("<IIHHHH", 0, 0, 0, 0, 0, len(resources[type_id]))
		for resource_id in resources[type_id]:
			out += struct.pack("<II", resource_id, 0x80000000 | language_offsets[(type_id, resource_id)])
	for key in language_offsets:
		out += struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 1)
		out += struct.pack("<II", 0x409, data_entry_offsets[key])
	for key in language_offsets:
		position, size = payloads[key]
		out += struct.pack("<IIII", base_rva + position, size, 0, 0)
	assert len(out) == payload_start
	return bytes(out + blob)


def make_dll(groups, frames, extra_sections=0, header_room=True, bitmaps=None) -> bytes:
	"""A PE32 with .text, .rsrc and a trailing section, laid out like shell32.dll (the resources are not last)."""
	rsrc_rva = 0x2000
	rsrc = resource_tree(groups, frames, rsrc_rva, bitmaps or {})
	section_count = 3 + extra_sections
	headers_size = 0x400 if header_room else FILE_ALIGNMENT
	optional_size = 224
	pe_offset = 0x80
	table = pe_offset + 24 + optional_size
	text = b"\xc3" + bytes(FILE_ALIGNMENT - 1)
	rsrc_raw = rsrc + bytes(-len(rsrc) % FILE_ALIGNMENT)
	tail = b"tail" + bytes(FILE_ALIGNMENT - 4)
	rsrc_virtual = (len(rsrc) + SECTION_ALIGNMENT - 1) // SECTION_ALIGNMENT * SECTION_ALIGNMENT
	tail_rva = rsrc_rva + rsrc_virtual
	image = bytearray(headers_size)
	image[0:2] = b"MZ"
	struct.pack_into("<I", image, 0x3C, pe_offset)
	image[pe_offset : pe_offset + 4] = b"PE\0\0"
	struct.pack_into("<HHIIIHH", image, pe_offset + 4, 0x14C, section_count, 0, 0, 0, optional_size, 0x2102)
	optional = pe_offset + 24
	struct.pack_into("<H", image, optional, 0x10B)
	struct.pack_into("<II", image, optional + 32, SECTION_ALIGNMENT, FILE_ALIGNMENT)
	struct.pack_into("<I", image, optional + 56, tail_rva + SECTION_ALIGNMENT)
	struct.pack_into("<I", image, optional + 60, headers_size)
	struct.pack_into("<I", image, optional + 92, 16)
	struct.pack_into("<II", image, optional + 96 + 16, rsrc_rva, len(rsrc))
	raw = headers_size
	sections = [(b".text", len(text), 0x1000, len(text), raw, text)]
	raw += len(text)
	sections.append((b".rsrc", len(rsrc), rsrc_rva, len(rsrc_raw), raw, rsrc_raw))
	raw += len(rsrc_raw)
	sections.append((b".tail", 4, tail_rva, len(tail), raw, tail))
	for index in range(extra_sections):
		sections.append((b".x%d" % index, 4, tail_rva + SECTION_ALIGNMENT * (index + 1), 0, 0, b""))
	for index, (name, virtual_size, virtual_address, raw_size, raw_offset, _content) in enumerate(sections):
		struct.pack_into(
			"<8sIIIIIIHHI", image, table + 40 * index, name, virtual_size, virtual_address, raw_size, raw_offset, 0, 0, 0, 0, 0x40000040
		)
	return bytes(image) + b"".join(section[5] for section in sections)


def stock_dll(**options) -> bytes:
	frames = {1: dib(48, 1), 2: dib(32, 2), 3: dib(16, 3), 4: dib(48, 4), 5: dib(32, 5), 6: dib(16, 6), 7: dib(32, 7), 8: dib(16, 8)}
	groups = {
		4: [(1, 48, 8), (2, 32, 8), (3, 16, 8), (4, 48, 32), (5, 32, 32), (6, 16, 32)],
		30: [(7, 32, 32), (8, 16, 32)],  # like the stock shortcut arrow: no 48 px frame, and only two ids
	}
	return make_dll(groups, frames, **options)


def group_of(pe: PeFile, group_id: int) -> list[GroupFrame]:
	return parse_group(pe.entry_data(pe.data_entries(RT_GROUP_ICON)[group_id][0]))
