# Write a resource-only DLL that holds icon groups: the `imageres.dll` Explorer's Show Desktop button asks for.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""ReactOS 0.4.16 ships no `imageres.dll`, but the taskbar's Show Desktop button loads icon 110 from it before it falls back to
`shell32.dll`'s Desktop folder icon, and nothing else loads the file. A resource-only `imageres.dll` with that one group therefore
gives the button its own icon and touches nothing else; deleting the file restores the stock behaviour.

The file is a PE32 DLL with no code, no imports and no entry point: the headers, one `.rsrc` section holding an RT_ICON frame per .ico
frame and an RT_GROUP_ICON per group, and the PE checksum. Everything in it is fixed by its inputs (no time stamp), so the same icons
always give the same bytes and the result can be pinned. The resource language is neutral.
"""

import struct

from .pe_resources import RT_GROUP_ICON, RT_ICON, GroupFrame, PeError, PeFile, align_up, build_group, read_ico

SECTION_ALIGNMENT = 0x1000
FILE_ALIGNMENT = 0x200
IMAGE_BASE = 0x10000000
DOS_STUB = 0x40  # the PE signature sits right after a 64-byte DOS header
OPTIONAL_SIZE = 224
SECTION_FLAGS = 0x40000040  # initialized data, readable
HIGH_BIT = 0x80000000
LANGUAGE_NEUTRAL = 0


def _directory(entries: list[tuple[int, int]]) -> bytes:
	"""A resource directory of numeric ids: its 16-byte header and one 8-byte entry per (id, target) pair, ids ascending."""
	out = struct.pack("<IIHHHH", 0, 0, 0, 0, 0, len(entries))
	for entry_id, target in sorted(entries):
		out += struct.pack("<II", entry_id, target)
	return out


def build_icon_dll(groups: dict[int, bytes]) -> bytes:
	"""A resource-only DLL holding one icon group per entry of `groups` (group id -> .ico bytes). Every frame must be a 32-bit DIB. Icon
	frame ids are numbered from 1 in group order, so they cannot clash."""
	if not groups:
		raise PeError("a resource-only DLL needs at least one icon group")
	frames: list[tuple[int, bytes]] = []  # (icon id, DIB)
	group_data: dict[int, bytes] = {}
	for group_id in sorted(groups):
		listed = []
		for width, height, bit_count, image in read_ico(groups[group_id]):
			if bit_count != 32:
				raise PeError(f"the icon for group {group_id} has a {bit_count}-bit {width}x{height} frame, expected 32")
			frames.append((len(frames) + 1, image))
			listed.append(GroupFrame(width, height, 0, 1, 32, len(image), len(frames)))
		group_data[group_id] = build_group(listed)
	# Resource table layout: root, the two type directories, one language directory per resource, the data entries, then the data.
	icon_ids = [icon_id for icon_id, _image in frames]
	resources = [(RT_ICON, icon_id) for icon_id in icon_ids] + [(RT_GROUP_ICON, group_id) for group_id in sorted(groups)]
	root_size = 16 + 8 * 2
	type_sizes = {RT_ICON: 16 + 8 * len(icon_ids), RT_GROUP_ICON: 16 + 8 * len(groups)}
	language_size = 16 + 8
	icon_directory = root_size
	group_directory = icon_directory + type_sizes[RT_ICON]
	first_language = group_directory + type_sizes[RT_GROUP_ICON]
	first_entry = first_language + language_size * len(resources)
	entry_offsets = {resource: first_entry + 16 * index for index, resource in enumerate(resources)}
	data_start = first_entry + 16 * len(resources)
	payloads = {(RT_ICON, icon_id): image for icon_id, image in frames} | {
		(RT_GROUP_ICON, group_id): group_data[group_id] for group_id in groups
	}
	section_rva = SECTION_ALIGNMENT
	table = bytearray()
	table += _directory([(RT_ICON, HIGH_BIT | icon_directory), (RT_GROUP_ICON, HIGH_BIT | group_directory)])
	for resource_type in (RT_ICON, RT_GROUP_ICON):
		table += _directory(
			[
				(item_id, HIGH_BIT | (first_language + language_size * index))
				for index, (kind, item_id) in enumerate(resources)
				if kind == resource_type
			]
		)
	for resource in resources:
		table += _directory([(LANGUAGE_NEUTRAL, entry_offsets[resource])])
	data = bytearray()
	entries = bytearray()
	for resource in resources:
		data += bytes(align_up(len(data), 4) - len(data))
		entries += struct.pack("<IIII", section_rva + data_start + len(data), len(payloads[resource]), 0, 0)
		data += payloads[resource]
	assert len(table) == first_entry
	section = bytes(table) + bytes(entries) + bytes(data)
	raw_size = align_up(len(section), FILE_ALIGNMENT)
	size_of_image = align_up(section_rva + len(section), SECTION_ALIGNMENT)
	headers = bytearray(FILE_ALIGNMENT)
	headers[0:2] = b"MZ"
	struct.pack_into("<I", headers, 0x3C, DOS_STUB)
	struct.pack_into("<4sHHIIIHH", headers, DOS_STUB, b"PE\0\0", 0x14C, 1, 0, 0, 0, OPTIONAL_SIZE, 0x2102)
	optional = DOS_STUB + 24
	struct.pack_into("<HBBIIIIII", headers, optional, 0x10B, 2, 0, 0, raw_size, 0, 0, section_rva, section_rva)
	struct.pack_into(
		"<IIIHHHHHHIIIIHHIIIIII",
		headers,
		optional + 28,
		IMAGE_BASE,
		SECTION_ALIGNMENT,
		FILE_ALIGNMENT,
		4,
		0,
		0,
		0,
		4,
		0,
		0,
		size_of_image,
		FILE_ALIGNMENT,
		0,
		2,
		0,
		0x100000,
		0x1000,
		0x100000,
		0x1000,
		0,
		16,
	)
	struct.pack_into("<II", headers, optional + 96 + 8 * 2, section_rva, len(section))
	struct.pack_into(
		"<8sIIIIIIHHI",
		headers,
		optional + OPTIONAL_SIZE,
		b".rsrc",
		len(section),
		section_rva,
		raw_size,
		FILE_ALIGNMENT,
		0,
		0,
		0,
		0,
		SECTION_FLAGS,
	)
	pe = PeFile(bytes(headers) + section + bytes(raw_size - len(section)))
	pe.update_checksum()
	return pe.to_bytes()
