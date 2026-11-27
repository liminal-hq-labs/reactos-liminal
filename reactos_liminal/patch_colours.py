# The cold-boot colours patcher: Afterglow's desktop colours in the system colour table of `win32k.sys`, so the screen is never
# ReactOS's blue between the display mode being set and the first user logging on.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# `win32k.sys` starts with a built-in table of the 31 system colours (`SysColors[]` in `win32ss/gdi/ntgdi/stockobj.c`, 0.4.16),
# COLOR_BACKGROUND being ReactOS's blue, RGB(58, 110, 165). Nothing reads the registry's `Control Panel\Colors` until `userinit.exe`
# runs for the signed-in user (`SetUserSysColors`), so the desktop the logon dialogs, "Welcome" and "Applying your personal settings"
# are drawn on is that built-in table whatever `HKU\.DEFAULT` holds, and so is the first frame after the mode is set. The registry
# route does not reach it; this table does. The patcher writes the values the Afterglow style file sets under `Control Panel\Colors`
# over the same entries, in place at the same size, and recomputes the PE checksum. smss loads `win32k.sys` by a fixed name (it only
# looks for the `Kmode` value), so the patched file replaces the stock one on the image; the golden disk keeps the original.
# The input must be exactly the 0.4.16 file, the table must occur once in it, and the result must match the pinned sum.
import hashlib
import re
from pathlib import Path

from .fetch import sha256_file
from .log import log
from .mtools import FatImage
from .patch_base import PatchedFile, PatchError
from .pe_resource import PeError, PeFile, pe_checksum

PATH = "ReactOS/system32/win32k.sys"
# The ReactOS 0.4.16 win32k.sys, the one file this patcher accepts.
STOCK_SHA256 = ("5bac622de90b6748506f9a529732579ecb447a273be2b7599503a9f7a7c46833",)
# The result for the Afterglow colours the recipe pins. A different commit with different colours gives a different sum.
RESULT_SHA256 = "fbbc43ab018abf047c72b8a579537c4d3595cab74620a2d5a03d214e77d943eb"
# The stock table, in COLORREF (R, G, B, 0) order, and the registry value that names each entry (userinit's `g_RegColorNames`).
STOCK_TABLE = (
	(212, 208, 200), (58, 110, 165), (10, 36, 106), (128, 128, 128), (212, 208, 200), (255, 255, 255), (0, 0, 0), (0, 0, 0),
	(0, 0, 0), (255, 255, 255), (212, 208, 200), (212, 208, 200), (128, 128, 128), (10, 36, 106), (255, 255, 255), (212, 208, 200),
	(128, 128, 128), (128, 128, 128), (0, 0, 0), (212, 208, 200), (255, 255, 255), (64, 64, 64), (212, 208, 200), (0, 0, 0),
	(255, 255, 225), (181, 181, 181), (0, 0, 128), (166, 202, 240), (192, 192, 192), (49, 106, 197), (236, 233, 216),
)  # fmt: skip
VALUE_NAMES = (
	"Scrollbar", "Background", "ActiveTitle", "InactiveTitle", "Menu", "Window", "WindowFrame", "MenuText", "WindowText", "TitleText",
	"ActiveBorder", "InactiveBorder", "AppWorkSpace", "Hilight", "HilightText", "ButtonFace", "ButtonShadow", "GrayText", "ButtonText",
	"InactiveTitleText", "ButtonHilight", "ButtonDkShadow", "ButtonLight", "InfoText", "InfoWindow", "ButtonAlternateFace",
	"HotTrackingColor", "GradientActiveTitle", "GradientInactiveTitle", "MenuHilight", "MenuBar",
)  # fmt: skip
COLOURS_KEY = "[hkey_current_user\\control panel\\colors]"
VALUE_LINE = re.compile(r'^"([^"]+)"="(\d{1,3}) (\d{1,3}) (\d{1,3})"\s*$')


def afterglow_colours(style_reg: str) -> dict[str, tuple[int, int, int]]:
	"""The `Control Panel\\Colors` values the Afterglow style file sets for the current user, by value name."""
	colours: dict[str, tuple[int, int, int]] = {}
	inside = False
	for line in style_reg.splitlines():
		stripped = line.strip()
		if stripped.startswith("["):
			inside = stripped.lower() == COLOURS_KEY
			continue
		match = VALUE_LINE.match(stripped) if inside else None
		if match and match.group(1) in VALUE_NAMES:
			red, green, blue = (int(match.group(index)) for index in (2, 3, 4))
			if max(red, green, blue) > 255:
				raise PatchError(f"the colour {match.group(1)} is out of range")
			colours[match.group(1)] = (red, green, blue)
	return colours


def patch_win32k(stock: bytes, colours: dict[str, tuple[int, int, int]]) -> bytes:
	"""A copy of the stock win32k.sys with each named colour written over its entry of the system colour table."""
	if hashlib.sha256(stock).hexdigest() not in STOCK_SHA256:
		raise PatchError("refused: the guest's win32k.sys is not the ReactOS 0.4.16 file this patcher was written for")
	if "Background" not in colours:
		raise PatchError("the Afterglow style file sets no desktop (Background) colour")
	pattern = b"".join(bytes(entry) + b"\0" for entry in STOCK_TABLE)
	if stock.count(pattern) != 1:
		raise PatchError(f"the system colour table occurs {stock.count(pattern)} times in win32k.sys, not once; refused")
	start = stock.index(pattern)
	data = bytearray(stock)
	for name, rgb in colours.items():
		position = start + 4 * VALUE_NAMES.index(name)
		data[position : position + 4] = bytes(rgb) + b"\0"
	try:
		checksum_offset = PeFile(data).checksum_offset
	except PeError as error:
		raise PatchError(f"win32k.sys: {error}") from error
	data[checksum_offset : checksum_offset + 4] = pe_checksum(data, checksum_offset).to_bytes(4, "little")
	return bytes(data)


def afterglow_colours_patch(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch a copy of the guest's win32k.sys with the Afterglow desktop colours; refuse any other win32k.sys."""
	style = files / "afterglow.reg"
	if not style.is_file():
		raise PatchError(f"{style} is missing; prepare the Afterglow files first")
	colours = afterglow_colours(style.read_text(encoding="utf-8", errors="replace"))
	stock = scratch / "win32k.sys"
	golden.copy_out(PATH, stock)
	patched = scratch / "win32k-afterglow.sys"
	patched.write_bytes(patch_win32k(stock.read_bytes(), colours))
	result = sha256_file(patched)
	if result != RESULT_SHA256:
		patched.unlink(missing_ok=True)
		raise PatchError(f"patched win32k.sys is {result}, expected {RESULT_SHA256}")
	log("patch", f"   afterglow.colours: win32k.sys patched ({result})")
	return [PatchedFile(PATH, patched)]
