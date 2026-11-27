# A registry hive writer for tests: the keys and values of a small tree, laid out as regf cells, so the reader is tested on bytes made
# here and not on a ReactOS file.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import struct

REG_SZ = 1
REG_EXPAND_SZ = 2
REG_DWORD = 4


def sz(text: str) -> tuple[int, bytes]:
	return REG_SZ, (text + "\0").encode("utf-16-le")


def expand(text: str) -> tuple[int, bytes]:
	return REG_EXPAND_SZ, (text + "\0").encode("utf-16-le")


class _Cells:
	def __init__(self):
		self.data = bytearray(b"hbin" + bytes(28))

	def add(self, body: bytes) -> int:
		offset = len(self.data)
		size = (4 + len(body) + 7) & ~7
		self.data += struct.pack("<i", -size) + body + bytes(size - 4 - len(body))
		return offset


def _key(cells: _Cells, name: str, values: dict, children: dict, parent: int) -> int:
	value_offsets = []
	for value_name, (kind, data) in values.items():
		encoded = value_name.encode("ascii")
		if len(data) <= 4:
			length_field, data_offset = len(data) | 0x80000000, struct.unpack("<I", data.ljust(4, b"\0"))[0]
		else:
			length_field, data_offset = len(data), cells.add(data)
		body = b"vk" + struct.pack("<HIIIH", len(encoded), length_field, data_offset, kind, 1) + bytes(2) + encoded
		value_offsets.append(cells.add(body))
	value_list = cells.add(b"".join(struct.pack("<I", offset) for offset in value_offsets)) if value_offsets else 0xFFFFFFFF
	child_offsets = [_key(cells, child_name, *child, parent=0) for child_name, child in children.items()]
	subkey_list = 0xFFFFFFFF
	if child_offsets:
		entries = b"".join(struct.pack("<II", offset, 0) for offset in child_offsets)
		subkey_list = cells.add(b"lf" + struct.pack("<H", len(child_offsets)) + entries)
	encoded = name.encode("ascii")
	body = bytearray(0x4C + len(encoded))
	body[0:2] = b"nk"
	struct.pack_into("<H", body, 2, 0x20)
	struct.pack_into("<I", body, 0x10, parent)
	struct.pack_into("<II", body, 0x14, len(child_offsets), 0)
	struct.pack_into("<I", body, 0x1C, subkey_list)
	struct.pack_into("<I", body, 0x24, len(value_offsets))
	struct.pack_into("<I", body, 0x28, value_list)
	struct.pack_into("<H", body, 0x48, len(encoded))
	body[0x4C:] = encoded
	return cells.add(bytes(body))


def key(values: dict | None = None, children: dict | None = None) -> tuple[dict, dict]:
	"""A key's values (`name: sz(...)`) and its subkeys (`name: key(...)`)."""
	return values or {}, children or {}


def build_hive(tree: dict) -> bytes:
	"""A hive whose root holds the keys of `tree`, a mapping of names to `key(...)` pairs."""
	cells = _Cells()
	root = _key(cells, "ROOT", {}, tree, parent=0xFFFFFFFF)
	cells.data[8:12] = struct.pack("<I", len(cells.data))
	base = bytearray(0x1000)
	base[0:4] = b"regf"
	struct.pack_into("<I", base, 0x24, root)
	return bytes(base) + bytes(cells.data)
