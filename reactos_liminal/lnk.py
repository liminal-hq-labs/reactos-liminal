# Write a minimal Windows shell link (.lnk), and read the text fields of one: a local target path, optional arguments, working folder,
# description and icon.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# The link carries no ID list, only LinkInfo with the local base path, which the Wine-derived shell32 in ReactOS reads. `icon` names an
# .ico (or any file with icons) and `icon_index` the index inside it, instead of the target's own icon.
import struct
from dataclasses import dataclass

HAS_ID_LIST = 0x1
HAS_LINK_INFO = 0x2
HAS_NAME = 0x4
HAS_RELATIVE_PATH = 0x8
HAS_WORKING_DIR = 0x10
HAS_ARGUMENTS = 0x20
HAS_ICON_LOCATION = 0x40
IS_UNICODE = 0x80
LINK_CLSID = bytes.fromhex("0114020000000000C000000000000046")  # 00021401-0000-0000-C000-000000000046


def _counted_string(text: str) -> bytes:
	"""StringData is UTF-16 when the IsUnicode flag is set; this link is ANSI."""
	encoded = text.encode("ascii")
	return struct.pack("<H", len(encoded)) + encoded


def make_lnk(
	target: str,
	arguments: str = "",
	working_dir: str = "",
	description: str = "",
	show_command: int = 1,
	icon: str = "",
	icon_index: int = 0,
) -> bytes:
	flags = HAS_LINK_INFO | HAS_ICON_LOCATION  # the icon comes from the target itself when no ID list supplies one
	if description:
		flags |= HAS_NAME
	if working_dir:
		flags |= HAS_WORKING_DIR
	if arguments:
		flags |= HAS_ARGUMENTS

	header = struct.pack("<I", 0x4C) + LINK_CLSID
	header += struct.pack("<IIQQQ", flags, 0x20, 0, 0, 0)  # attributes (archive), three FILETIMEs
	header += struct.pack("<IiIHHII", 0, icon_index, show_command, 0, 0, 0, 0)  # size, icon index, show command, hotkey, reserved

	base_path = target.encode("ascii") + b"\0"
	volume_label = b"\0"
	volume_id = struct.pack("<IIII", 16 + len(volume_label), 3, 0, 16) + volume_label  # DRIVE_FIXED, no serial
	info_header_length = 28
	volume_offset = info_header_length
	base_offset = volume_offset + len(volume_id)
	suffix_offset = base_offset + len(base_path)
	link_info = struct.pack("<IIIIIII", suffix_offset + 1, info_header_length, 1, volume_offset, base_offset, 0, suffix_offset)
	link_info += volume_id + base_path + b"\0"
	link_info = struct.pack("<I", len(link_info)) + link_info[4:]

	body = header + link_info
	if description:
		body += _counted_string(description)
	if working_dir:
		body += _counted_string(working_dir)
	if arguments:
		body += _counted_string(arguments)
	body += _counted_string(icon or target)
	return body + struct.pack("<I", 0)  # terminal block


@dataclass(frozen=True)
class LinkContents:
	"""What a shell link points at, as far as the link says it in text. `target` is empty for a link that holds only an item ID list
	(a virtual folder such as My Computer), which has no path to check."""

	target: str = ""
	arguments: str = ""
	working_dir: str = ""
	icon: str = ""
	icon_index: int = 0
	description: str = ""


class LinkError(ValueError):
	"""Bytes that are not a shell link this reader understands."""


def _read_string_data(data: bytes, position: int, unicode: bool) -> tuple[str, int]:
	(count,) = struct.unpack_from("<H", data, position)
	position += 2
	if unicode:
		return data[position : position + 2 * count].decode("utf-16-le", errors="replace").rstrip("\0"), position + 2 * count
	return data[position : position + count].decode("latin-1").rstrip("\0"), position + count


def read_lnk(data: bytes) -> LinkContents:
	"""Read the text fields of a shell link: the local base path of its LinkInfo (as ReactOS's shell and `make_lnk` write it) and the
	StringData after it. The item ID list is skipped, not decoded."""
	try:
		if len(data) < 0x4C or struct.unpack_from("<I", data, 0)[0] != 0x4C or data[4:20] != LINK_CLSID:
			raise LinkError("not a shell link")
		(flags,) = struct.unpack_from("<I", data, 20)
		(icon_index,) = struct.unpack_from("<i", data, 56)
		position = 0x4C
		if flags & HAS_ID_LIST:
			(size,) = struct.unpack_from("<H", data, position)
			position += 2 + size
		target = ""
		if flags & HAS_LINK_INFO:
			(info_size,) = struct.unpack_from("<I", data, position)
			(info_flags,) = struct.unpack_from("<I", data, position + 8)
			(base_offset,) = struct.unpack_from("<I", data, position + 16)
			if info_flags & 1 and base_offset:
				start = position + base_offset
				target = data[start : data.index(b"\0", start)].decode("latin-1")
			position += info_size
		unicode = bool(flags & IS_UNICODE)
		fields = {}
		for flag, name in (
			(HAS_NAME, "description"),
			(HAS_RELATIVE_PATH, "relative"),
			(HAS_WORKING_DIR, "working_dir"),
			(HAS_ARGUMENTS, "arguments"),
			(HAS_ICON_LOCATION, "icon"),
		):
			if flags & flag:
				fields[name], position = _read_string_data(data, position, unicode)
	except (struct.error, ValueError) as error:
		raise LinkError(f"unreadable shell link: {error}") from error
	return LinkContents(
		target=target,
		arguments=fields.get("arguments", ""),
		working_dir=fields.get("working_dir", ""),
		icon=fields.get("icon", ""),
		icon_index=icon_index,
		description=fields.get("description", ""),
	)
