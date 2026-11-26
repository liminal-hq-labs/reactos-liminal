# Tests for the shell link writer. The sums are of the files Quill's make-lnk.py wrote for the same arguments, so a link made here is
# byte for byte the link the demo disk carried.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import struct

from reactos_liminal.lnk import make_lnk


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
