# Read a Windows registry hive file (regf): the keys, their subkeys and their values. Read only, standard library only; enough for the
# audit to list what a hive launches, not a general registry library.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import struct
from dataclasses import dataclass

REG_SZ = 1
REG_EXPAND_SZ = 2
REG_MULTI_SZ = 7
HIVE_BINS_START = 0x1000  # offsets in a hive are relative to the first hive bin, after the 4 KiB base block
INLINE_DATA = 0x80000000  # set in a value's data length when the data is held in the offset field itself


class HiveError(ValueError):
	"""Bytes that are not a hive this reader understands."""


@dataclass(frozen=True)
class RegistryValue:
	name: str
	kind: int
	data: bytes

	def text(self) -> str:
		"""The value as text: a string for REG_SZ and REG_EXPAND_SZ, the first string of a REG_MULTI_SZ; empty for any other type."""
		if self.kind not in (REG_SZ, REG_EXPAND_SZ, REG_MULTI_SZ):
			return ""
		decoded = self.data.decode("utf-16-le", errors="replace")
		return decoded.split("\0", 1)[0]


class Hive:
	"""A hive held in memory. `open_key` takes a backslash path from the root and returns a key or None."""

	def __init__(self, data: bytes):
		if len(data) < HIVE_BINS_START + 0x20 or data[:4] != b"regf":
			raise HiveError("not a registry hive")
		self.data = data
		(self.root_offset,) = struct.unpack_from("<I", data, 0x24)

	def _cell(self, offset: int) -> bytes:
		start = HIVE_BINS_START + offset
		try:
			(size,) = struct.unpack_from("<i", self.data, start)
		except struct.error as error:
			raise HiveError(f"cell {offset:#x} is outside the hive") from error
		length = abs(size)
		return self.data[start + 4 : start + length]

	def root(self) -> "Key":
		return Key(self, self.root_offset)

	def open_key(self, path: str) -> "Key | None":
		key = self.root()
		for part in [piece for piece in path.split("\\") if piece]:
			key = key.subkey(part)
			if key is None:
				return None
		return key


class Key:
	def __init__(self, hive: Hive, offset: int):
		self.hive = hive
		cell = hive._cell(offset)
		if cell[:2] != b"nk":
			raise HiveError(f"cell {offset:#x} is not a key")
		(flags,) = struct.unpack_from("<H", cell, 2)
		(self._subkey_count,) = struct.unpack_from("<I", cell, 0x14)
		(self._subkey_list,) = struct.unpack_from("<I", cell, 0x1C)
		(self._value_count,) = struct.unpack_from("<I", cell, 0x24)
		(self._value_list,) = struct.unpack_from("<I", cell, 0x28)
		(name_length,) = struct.unpack_from("<H", cell, 0x48)
		raw_name = cell[0x4C : 0x4C + name_length]
		self.name = raw_name.decode("latin-1" if flags & 0x20 else "utf-16-le", errors="replace")

	def _subkey_offsets(self, list_offset: int) -> list[int]:
		cell = self.hive._cell(list_offset)
		kind = cell[:2]
		(count,) = struct.unpack_from("<H", cell, 2)
		if kind in (b"lf", b"lh"):
			return [struct.unpack_from("<I", cell, 4 + 8 * index)[0] for index in range(count)]
		if kind == b"li":
			return [struct.unpack_from("<I", cell, 4 + 4 * index)[0] for index in range(count)]
		if kind == b"ri":
			offsets = []
			for index in range(count):
				offsets += self._subkey_offsets(struct.unpack_from("<I", cell, 4 + 4 * index)[0])
			return offsets
		raise HiveError(f"unknown subkey list {kind!r}")

	def subkeys(self) -> list["Key"]:
		if not self._subkey_count or self._subkey_list == 0xFFFFFFFF:
			return []
		return [Key(self.hive, offset) for offset in self._subkey_offsets(self._subkey_list)]

	def subkey(self, name: str) -> "Key | None":
		wanted = name.lower()
		for key in self.subkeys():
			if key.name.lower() == wanted:
				return key
		return None

	def values(self) -> list[RegistryValue]:
		if not self._value_count or self._value_list == 0xFFFFFFFF:
			return []
		cell = self.hive._cell(self._value_list)
		found = []
		for index in range(self._value_count):
			(offset,) = struct.unpack_from("<I", cell, 4 * index)
			found.append(self._value(offset))
		return found

	def _value(self, offset: int) -> RegistryValue:
		cell = self.hive._cell(offset)
		if cell[:2] != b"vk":
			raise HiveError(f"cell {offset:#x} is not a value")
		(name_length,) = struct.unpack_from("<H", cell, 2)
		(length_field,) = struct.unpack_from("<I", cell, 4)
		(data_offset,) = struct.unpack_from("<I", cell, 8)
		(kind,) = struct.unpack_from("<I", cell, 12)
		(flags,) = struct.unpack_from("<H", cell, 16)
		raw_name = cell[0x14 : 0x14 + name_length]
		name = raw_name.decode("latin-1" if flags & 1 else "utf-16-le", errors="replace")
		length = length_field & ~INLINE_DATA
		if length_field & INLINE_DATA:
			data = struct.pack("<I", data_offset)[:length]
		elif length > 0x3FD8:
			data = b""  # big data (a block list) is not read: none of the values the audit looks at is that large
		else:
			data = self.hive._cell(data_offset)[:length]
		return RegistryValue(name, kind, data)

	def value(self, name: str) -> RegistryValue | None:
		wanted = name.lower()
		for value in self.values():
			if value.name.lower() == wanted:
				return value
		return None
