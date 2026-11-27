# Tests for the boot guard's pixel checks, on synthetic frames.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import struct

import boot_frames as frames


def blank(width, height, colour=(0, 0, 0)):
	return width, height, bytes(colour) * (width * height)


def test_stock_blue_is_found_only_where_the_stock_colour_is():
	assert frames.stock_blue_share(blank(4, 4, (58, 110, 165))) == 1.0
	assert frames.stock_blue_share(blank(4, 4, (61, 108, 170))) == 1.0
	assert frames.stock_blue_share(blank(4, 4, (9, 14, 42))) == 0.0
	half = put(blank(2, 1, (9, 14, 42)), 0, 0, (58, 110, 165))
	assert frames.stock_blue_share(half) == 0.5


def put(frame, x, y, colour):
	width, height, data = frame
	data = bytearray(data)
	offset = (y * width + x) * 3
	data[offset : offset + 3] = bytes(colour)
	return width, height, bytes(data)


def bmp4(width, height, indices, palette):
	stride = (width * 4 + 31) // 32 * 4
	body = bytearray()
	for row in reversed(range(height)):
		line = bytearray(stride)
		for x in range(width):
			line[x // 2] |= indices[row][x] << (4 if x % 2 == 0 else 0)
		body += line
	table = b"".join(bytes((b, g, r, 0)) for r, g, b in palette)
	info = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 4, 0, len(body), 0, 0, 16, 0)
	return b"BM" + struct.pack("<IHHI", 54 + len(table) + len(body), 0, 0, 54 + len(table)) + info + table + bytes(body)


def bmp24(width, height, colours):
	stride = (width * 3 + 3) // 4 * 4
	body = bytearray()
	for row in reversed(range(height)):
		line = b"".join(bytes((b, g, r)) for r, g, b in colours[row]) + b"\0" * (stride - width * 3)
		body += line
	info = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, len(body), 0, 0, 0, 0)
	return b"BM" + struct.pack("<IHHI", 54 + len(body), 0, 0, 54) + info + bytes(body)


def test_the_dac_shows_the_top_six_bits_with_the_low_bits_set_for_odd_values():
	assert frames.shown_colour((0x09, 0x0E, 0x2A)) == (0x08, 0x0F, 0x28)
	assert frames.shown_colour((0xFF, 0xAA, 0x40)) == (0xFF, 0xA8, 0x40)
	assert frames.shown_colour((0x52, 0x3D, 0x6C)) == (0x50, 0x3F, 0x6F)


def test_a_black_screen_with_a_gold_bar_is_the_minimal_menu():
	frame = blank(720, 400)
	for x in range(100, 400):
		for y in range(100, 116):
			frame = put(frame, x, y, frames.GOLD)
	ok, _detail = frames.menu_looks_minimal_gold_on_black(frame)
	assert ok


def test_a_blue_menu_with_no_gold_is_not():
	ok, _detail = frames.menu_looks_minimal_gold_on_black(blank(720, 400, (0, 0, 170)))
	assert not ok


def test_the_logo_check_counts_differences_and_skips_the_progress_box():
	palette = [(i * 16, i * 8, 255 - i) for i in range(16)]
	indices = [[(x + y) % 16 for x in range(8)] for y in range(4)]
	image = bmp4(8, 4, indices, palette)
	assert frames.read_bmp4(image)[2] == indices
	frame = blank(40, 30)
	shown = [frames.shown_colour(rgb) for rgb in palette]
	for y in range(4):
		for x in range(8):
			frame = put(frame, 5 + x, 6 + y, shown[indices[y][x]])
	assert frames.logo_differences(frame, image, (0, 0, 0, 0), origin=(5, 6)) == (0, 32)
	frame = put(frame, 5 + 2, 6 + 1, (1, 2, 3))
	assert frames.logo_differences(frame, image, (0, 0, 0, 0), origin=(5, 6)) == (1, 32)
	assert frames.logo_differences(frame, image, (2, 1, 1, 1), origin=(5, 6)) == (0, 31)


def test_the_banner_is_found_by_its_first_row_and_compared():
	colours = [[(x * 10, y * 20, 7) for x in range(6)] for y in range(3)]
	image = bmp24(6, 3, colours)
	frame = blank(30, 20, (9, 9, 9))
	for y in range(3):
		for x in range(6):
			frame = put(frame, 11 + x, 4 + y, colours[y][x])
	assert frames.find_banner(frame, image) == ((11, 4), 0)
	frame = put(frame, 12, 5, (200, 200, 200))
	assert frames.find_banner(frame, image) == ((11, 4), 1)
	assert frames.find_banner(blank(30, 20), image) == (None, -1)
