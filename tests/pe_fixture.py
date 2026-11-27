# A tiny PE32 file with bitmap resources, for the patcher tests: no ReactOS file is ever needed.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import struct

RAW_START = 0x200
SECTION_RVA = 0x1000


def make_dib(width: int, height: int, bits: int, compression: int = 0, pixels: bytes = b"", colours: int = 0, fill: int = 0) -> bytes:
	"""A DIB (a bitmap resource body). With no `pixels` it holds zero-filled uncompressed rows of the right length."""
	if not pixels:
		pixels = bytes([fill]) * ((width * bits + 31) // 32 * 4 * height)
	header = struct.pack("<IiiHHIIiiII", 40, width, height, 1, bits, compression, len(pixels), 0, 0, colours, 0)
	return header + b"\0" * (4 * colours) + pixels


def bmp_file(dib: bytes) -> bytes:
	"""A .bmp: the DIB behind a 14-byte file header."""
	return b"BM" + struct.pack("<IHHI", 14 + len(dib), 0, 0, 14 + 40) + dib


def make_pe(bitmaps: dict[int, bytes], slack: dict[int, int] | None = None, languages: dict[int, int] | None = None) -> bytes:
	"""A PE32 image whose .rsrc holds `bitmaps` ({resource id: DIB}), each followed by `slack[id]` spare bytes before the next
	resource. `languages[id]` = n puts the resource in n languages."""
	slack = slack or {}
	languages = languages or {}
	ids = sorted(bitmaps)
	root_size = 16 + 8
	type_dir = root_size
	type_size = 16 + 8 * len(ids)
	lang_dirs = type_dir + type_size
	cursor = lang_dirs
	lang_dir_at = {}
	for resource_id in ids:
		lang_dir_at[resource_id] = cursor
		cursor += 16 + 8 * languages.get(resource_id, 1)
	entries_at = {}
	for resource_id in ids:
		entries_at[resource_id] = cursor
		cursor += 16 * languages.get(resource_id, 1)
	blobs = bytearray()
	blob_at = {}
	for resource_id in ids:
		cursor_blob = cursor + len(blobs)
		blob_at[resource_id] = cursor_blob
		blobs += bitmaps[resource_id] + b"\0" * slack.get(resource_id, 0)
		blobs += b"\0" * (-len(blobs) % 4)
	rsrc = bytearray(cursor)
	struct.pack_into("<IIHHHH", rsrc, 0, 0, 0, 0, 0, 0, 1)
	struct.pack_into("<II", rsrc, 16, 2, 0x80000000 | type_dir)
	struct.pack_into("<IIHHHH", rsrc, type_dir, 0, 0, 0, 0, 0, len(ids))
	for index, resource_id in enumerate(ids):
		struct.pack_into("<II", rsrc, type_dir + 16 + 8 * index, resource_id, 0x80000000 | lang_dir_at[resource_id])
		count = languages.get(resource_id, 1)
		struct.pack_into("<IIHHHH", rsrc, lang_dir_at[resource_id], 0, 0, 0, 0, 0, count)
		for lang in range(count):
			struct.pack_into("<II", rsrc, lang_dir_at[resource_id] + 16 + 8 * lang, 0x409 + lang, entries_at[resource_id] + 16 * lang)
			struct.pack_into(
				"<IIII", rsrc, entries_at[resource_id] + 16 * lang, SECTION_RVA + blob_at[resource_id], len(bitmaps[resource_id]), 0, 0
			)
	rsrc += blobs
	raw_size = len(rsrc) + (-len(rsrc) % 0x200)
	rsrc += b"\0" * (raw_size - len(rsrc))
	dos = bytearray(0x40)
	dos[:2] = b"MZ"
	struct.pack_into("<I", dos, 0x3C, 0x40)
	coff = struct.pack("<HHIIIHH", 0x14C, 1, 0, 0, 0, 224, 0x2102)
	optional = bytearray(224)
	struct.pack_into("<H", optional, 0, 0x10B)
	struct.pack_into("<I", optional, 92, 16)
	struct.pack_into("<II", optional, 96 + 16, SECTION_RVA, len(rsrc))
	section = b".rsrc\0\0\0" + struct.pack("<IIIIIIHHI", len(rsrc), SECTION_RVA, raw_size, RAW_START, 0, 0, 0, 0, 0x40000040)
	header = bytes(dos) + b"PE\0\0" + coff + bytes(optional) + section
	return header + b"\0" * (RAW_START - len(header)) + bytes(rsrc)
