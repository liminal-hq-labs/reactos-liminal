# Tests for the shell link writer. The sums are of the files Quill's make-lnk.py wrote for the same arguments, so a link made here is
# byte for byte the link the demo disk carried.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import struct

import pytest

from reactos_liminal.lnk import LinkError, make_lnk, read_lnk


def test_a_full_link_matches_the_original_writer():
	data = make_lnk("C:\\Quill\\QUILL32.EXE", "C:\\Quill\\DEMO.QLD", "C:\\Quill", "Quill, 32-bit build", 1, "C:\\Quill\\QUILLDESK.ICO")
	assert hashlib.sha256(data).hexdigest() == "ee929c8e9b0e01bd762141807df84e2d80152f887532ab28d6b44c086020a50a"


def test_a_bare_link_matches_the_original_writer():
	assert (
		hashlib.sha256(make_lnk("C:\\A.EXE", show_command=3)).hexdigest()
		== "01c3d8744c9af888a8717c21dd36731ced8a2301151667ff9373fcb55762d14c"
	)


def test_header_and_strings():
	data = make_lnk("C:\\A.EXE", "ARGS", "C:\\", "Desc", 7, "C:\\I.ICO", icon_index=2)
	assert struct.unpack("<I", data[:4])[0] == 0x4C
	flags = struct.unpack("<I", data[20:24])[0]
	assert flags & 0x2 and flags & 0x4 and flags & 0x10 and flags & 0x20 and flags & 0x40
	assert struct.unpack("<i", data[56:60])[0] == 2  # icon index
	assert struct.unpack("<I", data[60:64])[0] == 7  # show command
	assert b"\x04\x00Desc" in data and b"\x04\x00ARGS" in data and b"\x08\x00C:\\I.ICO" in data
	assert data.endswith(b"\x00\x00\x00\x00")


def test_the_text_fields_of_a_link_read_back():
	data = make_lnk("C:\\ReactOS\\system32\\calc.exe", "/x", "C:\\ReactOS", "Calculator", 1, "C:\\I.ICO", icon_index=2)
	link = read_lnk(data)
	assert (link.target, link.arguments, link.working_dir, link.description) == (
		"C:\\ReactOS\\system32\\calc.exe",
		"/x",
		"C:\\ReactOS",
		"Calculator",
	)
	assert (link.icon, link.icon_index) == ("C:\\I.ICO", 2)


def test_a_link_with_an_item_id_list_is_read_past_it():
	plain = make_lnk("C:\\A.EXE", description="Desc")
	id_list = struct.pack("<H", 22) + b"\x14\x00" + bytes(18) + struct.pack("<H", 0)  # one 20-byte item and the terminator
	flags = struct.unpack("<I", plain[20:24])[0] | 0x1
	data = plain[:20] + struct.pack("<I", flags) + plain[24:0x4C] + id_list + plain[0x4C:]
	link = read_lnk(data)
	assert link.target == "C:\\A.EXE" and link.description == "Desc"


def test_a_link_with_no_local_path_has_an_empty_target():
	data = bytearray(make_lnk("C:\\A.EXE"))
	data[20:24] = struct.pack("<I", struct.unpack("<I", data[20:24])[0] & ~0x2)  # no LinkInfo
	assert read_lnk(bytes(data[:0x4C]) + struct.pack("<H", 0)).target == ""


def test_unicode_strings_are_read():
	text = "Install"
	body = struct.pack("<H", len(text)) + text.encode("utf-16-le")
	header = bytearray(make_lnk("C:\\A.EXE")[:0x4C])
	header[20:24] = struct.pack("<I", 0x4 | 0x80)  # name, unicode
	assert read_lnk(bytes(header) + body).description == "Install"


@pytest.mark.parametrize("data", [b"", b"short", bytes(200), make_lnk("C:\\A.EXE")[:30], make_lnk("C:\\A.EXE")[:90]])
def test_bytes_that_are_not_a_link_are_refused_not_crashed_on(data):
	with pytest.raises(LinkError):
		read_lnk(data)
