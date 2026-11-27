# Tests for the PPM to PNG conversion of monitor screenshots.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import struct
import zlib

import pytest

from reactos_liminal.ppm import ppm_to_png, read_ppm


def decode_png(data):
	assert data.startswith(b"\x89PNG\r\n\x1a\n")
	position, header, pixel_data = 8, None, b""
	while position < len(data):
		length, kind = struct.unpack(">I4s", data[position : position + 8])
		payload = data[position + 8 : position + 8 + length]
		assert zlib.crc32(kind + payload) & 0xFFFFFFFF == struct.unpack(">I", data[position + 8 + length : position + 12 + length])[0]
		if kind == b"IHDR":
			header = struct.unpack(">IIBBBBB", payload)
		elif kind == b"IDAT":
			pixel_data += payload
		position += 12 + length
	return header, zlib.decompress(pixel_data)


def test_a_small_picture_round_trips(tmp_path):
	pixels = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 9, 8, 7])
	source = tmp_path / "s.ppm"
	source.write_bytes(b"P6\n# a comment\n2 2\n255\n" + pixels)
	target = tmp_path / "s.png"
	ppm_to_png(source, target)
	header, raw = decode_png(target.read_bytes())
	assert header[:2] == (2, 2) and header[2:5] == (8, 2, 0)
	assert raw == b"\x00" + pixels[:6] + b"\x00" + pixels[6:]


def test_bad_input_is_refused():
	with pytest.raises(ValueError):
		read_ppm(b"P5\n1 1\n255\n\x00")
	with pytest.raises(ValueError, match="truncated"):
		read_ppm(b"P6\n2 2\n255\n\x00\x00")
