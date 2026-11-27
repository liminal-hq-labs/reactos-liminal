# Write a minimal Windows shell link (.lnk): a local target path, optional arguments, working folder and description.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# The link carries no ID list, only LinkInfo with the local base path, which the Wine-derived shell32 in ReactOS reads. `icon` names an
# .ico (or any file with icons) and `icon_index` the index inside it, instead of the target's own icon.
import struct

HAS_LINK_INFO = 0x2
HAS_NAME = 0x4
HAS_WORKING_DIR = 0x10
HAS_ARGUMENTS = 0x20
HAS_ICON_LOCATION = 0x40
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
