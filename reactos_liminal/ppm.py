# Turn the PPM that QEMU's `screendump` writes into a PNG, with the standard library only.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import struct
import zlib
from pathlib import Path


def _chunk(kind: bytes, payload: bytes) -> bytes:
	checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
	return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def read_ppm(data: bytes) -> tuple[int, int, bytes]:
	"""Width, height and RGB bytes of a binary (P6) PPM with 8-bit samples."""
	fields: list[bytes] = []
	position = 0
	while len(fields) < 4:
		while data[position : position + 1].isspace():
			position += 1
		if data[position : position + 1] == b"#":
			position = data.index(b"\n", position) + 1
			continue
		start = position
		while not data[position : position + 1].isspace():
			position += 1
		fields.append(data[start:position])
	position += 1  # the single whitespace byte after the maximum value
	if fields[0] != b"P6" or int(fields[3]) != 255:
		raise ValueError("not an 8-bit binary PPM")
	width, height = int(fields[1]), int(fields[2])
	pixels = data[position : position + width * height * 3]
	if len(pixels) != width * height * 3:
		raise ValueError("the PPM is truncated")
	return width, height, pixels


def ppm_to_png(source: Path, destination: Path) -> None:
	width, height, pixels = read_ppm(source.read_bytes())
	row_bytes = width * 3
	raw = b"".join(b"\x00" + pixels[row * row_bytes : (row + 1) * row_bytes] for row in range(height))
	header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
	png = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 6)) + _chunk(b"IEND", b"")
	destination.write_bytes(png)
