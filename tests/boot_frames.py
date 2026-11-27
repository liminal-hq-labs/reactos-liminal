# Pixel checks on QEMU screendump frames, for the boot guard: the boot menu, the kernel boot logo and the logon banner. Pure functions
# over (width, height, RGB bytes), so the checks themselves are tested without a QEMU.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import struct

Frame = tuple[int, int, bytes]

LOGO_ORIGIN = (113, 23)  # where the kernel centres the 414 x 366 logo on 640 x 480
GOLD = (168, 87, 0)  # VGA text colour 6 ("Brown") as QEMU's screendump shows it: the selection bar in FreeLoader's minimal menu


def shown_colour(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
	"""The colour a capture of the boot screen shows for a palette entry: the VGA DAC keeps the top six bits of each channel, and a
	capture expands them to eight, setting the two low bits when the six-bit value is odd."""
	return tuple((value >> 2 << 2) | (3 if (value >> 2) & 1 else 0) for value in rgb)


def pixel(frame: Frame, x: int, y: int) -> tuple[int, int, int]:
	width, _height, data = frame
	offset = (y * width + x) * 3
	return data[offset], data[offset + 1], data[offset + 2]


STOCK_BLUE = (58, 110, 165)  # ReactOS's built-in desktop colour (COLOR_BACKGROUND in win32k.sys)


def stock_blue_share(frame: Frame) -> float:
	"""The share of the frame's pixels that are ReactOS's stock desktop blue, within a few levels of each channel."""
	_width, _height, data = frame
	near = 0
	for offset in range(0, len(data), 3):
		if all(abs(data[offset + channel] - STOCK_BLUE[channel]) <= 6 for channel in range(3)):
			near += 1
	return near / (len(data) // 3)


def menu_looks_minimal_gold_on_black(frame: Frame) -> tuple[bool, str]:
	"""The boot menu: a mostly black screen with a selection bar in text colour 6 (gold)."""
	width, height, data = frame
	pixels = width * height
	black = sum(1 for offset in range(0, len(data), 3) if data[offset : offset + 3] == b"\0\0\0")
	gold = sum(1 for offset in range(0, len(data), 3) if tuple(data[offset : offset + 3]) == GOLD)
	ok = black > 0.85 * pixels and gold > 0.004 * pixels
	return ok, f"{black / pixels:.1%} black, {gold / pixels:.2%} gold"


def read_bmp4(bmp: bytes) -> tuple[int, int, list[list[int]], list[tuple[int, int, int]]]:
	"""Width, height, rows of palette indices (top row first) and the palette of an uncompressed 4-bit .bmp."""
	pixel_offset = struct.unpack_from("<I", bmp, 10)[0]
	_size, width, height, _planes, bits, compression, _image, _x, _y, used, _important = struct.unpack_from("<IiiHHIIiiII", bmp, 14)
	if bits != 4 or compression != 0:
		raise ValueError("expected an uncompressed 4-bit bitmap")
	palette = [(bmp[54 + 4 * i + 2], bmp[54 + 4 * i + 1], bmp[54 + 4 * i]) for i in range(used or 16)]
	stride = (width * 4 + 31) // 32 * 4
	rows = []
	for row in range(height):
		start = pixel_offset + (height - 1 - row) * stride
		line = bmp[start : start + stride]
		rows.append([(line[x // 2] >> 4) if x % 2 == 0 else (line[x // 2] & 15) for x in range(width)])
	return width, height, rows, palette


def logo_differences(frame: Frame, bmp4: bytes, skip: tuple[int, int, int, int], origin: tuple[int, int] = LOGO_ORIGIN) -> tuple[int, int]:
	"""How many pixels of the 640 x 480 boot frame differ from the logo drawn through the DAC, and how many were compared. `skip` is the
	progress bar's box in logo coordinates (x, y, width, height), which the kernel draws over."""
	width, height, rows, palette = read_bmp4(bmp4)
	shown = [shown_colour(rgb) for rgb in palette]
	left, top = origin
	box_x, box_y, box_w, box_h = skip
	different = compared = 0
	for y in range(height):
		for x in range(width):
			if box_x <= x < box_x + box_w and box_y <= y < box_y + box_h:
				continue
			compared += 1
			if pixel(frame, left + x, top + y) != shown[rows[y][x]]:
				different += 1
	return different, compared


def read_bmp24_rows(bmp: bytes) -> tuple[int, int, list[bytes]]:
	"""Width, height and the RGB bytes of each row (top row first) of an uncompressed 24-bit .bmp."""
	pixel_offset = struct.unpack_from("<I", bmp, 10)[0]
	_size, width, height, _planes, bits, compression = struct.unpack_from("<IiiHHI", bmp, 14)
	if bits != 24 or compression != 0:
		raise ValueError("expected an uncompressed 24-bit bitmap")
	stride = (width * 3 + 3) // 4 * 4
	rows = []
	for row in range(height):
		start = pixel_offset + (height - 1 - row) * stride
		line = bmp[start : start + width * 3]
		rows.append(b"".join(line[x + 2 : x + 3] + line[x + 1 : x + 2] + line[x : x + 1] for x in range(0, len(line), 3)))
	return width, height, rows


def find_banner(frame: Frame, bmp24: bytes) -> tuple[tuple[int, int] | None, int]:
	"""Find a 24-bit bitmap in a frame by its top row, and count the pixels of it that differ. (None, -1) when the row is not there."""
	frame_width, frame_height, data = frame
	width, height, rows = read_bmp24_rows(bmp24)
	row_bytes = frame_width * 3
	for y in range(frame_height - height + 1):
		line = data[y * row_bytes : (y + 1) * row_bytes]
		x = line.find(rows[0])
		while x != -1 and x % 3:
			x = line.find(rows[0], x + 1)
		if x == -1:
			continue
		left = x // 3
		different = 0
		for offset in range(height):
			start = ((y + offset) * frame_width + left) * 3
			if data[start : start + width * 3] != rows[offset]:
				different += sum(
					1 for index in range(0, width * 3, 3) if data[start + index : start + index + 3] != rows[offset][index : index + 3]
				)
		return (left, y), different
	return None, -1
