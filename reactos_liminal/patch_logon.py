# The logon banner patcher: Afterglow's banner and bar in a copy of `msgina.dll`, installed as `agmsgina.dll` and selected by one
# registry value, so the stock `msgina.dll` stays on the disk and the off switch is deleting that value.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# ReactOS 0.4.16's winlogon reads `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\GinaDLL` and loads that file as the
# GINA, so a separately named patched copy works (the decision is RL-21). msgina draws every logon box with two 24-bit bitmaps,
# IDI_ROSLOGO (20000, 413 x 72) and IDI_BAR (20001, 413 x 5). The Afterglow BMPs are the same size and depth, so each is written over
# its resource in place and the PE checksum is recomputed. The input must be exactly the 0.4.16 msgina.dll; the result is checked
# against the sum pinned here. The patched file is ReactOS code (GPL) and stays in the work directory.
from pathlib import Path

from .fetch import sha256_file
from .log import log
from .mtools import FatImage
from .patch_base import PatchedFile, PatchError, render_art
from .pe_resource import PeError, PeFile, dib_from_bmp, dib_info, replace_bitmap

STOCK_PATH = "ReactOS/system32/msgina.dll"
PATCHED_PATH = "ReactOS/system32/agmsgina.dll"
# The ReactOS 0.4.16 msgina.dll, the one file this patcher accepts.
STOCK_SHA256 = ("95863449bd6af48e256708624ccc9b96ee91c931c4ac8eeb59b174c475dfca77",)
# The result for the Afterglow banner and bar the recipe pins. A different commit with different art gives a different sum, and the
# pin is bumped with it.
RESULT_SHA256 = "74e9017d83b7a1216a5cd30f9b2330b9f64fa0891e65ad2ea18bd133d9aa6bbd"
# Afterglow's render, the resource it replaces, and the size and depth that resource has.
BITMAPS = (
	("afterglow-banner.bmp", 20000, (413, 72, 24)),
	("afterglow-bar.bmp", 20001, (413, 5, 24)),
)


def afterglow_logon(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch a copy of the guest's msgina.dll with the Afterglow banner and bar; refuse any other msgina.dll."""
	rendered = render_art(source_tree / "desktop" / "logon", scratch / "logon-art", [name for name, _id, _shape in BITMAPS])
	stock = scratch / "msgina.dll"
	golden.copy_out(STOCK_PATH, stock)
	actual = sha256_file(stock)
	if actual not in STOCK_SHA256:
		raise PatchError(f"refused: the guest's msgina.dll is {actual}, not the ReactOS 0.4.16 file this patcher was written for")
	data = stock.read_bytes()
	try:
		for name, resource_id, shape in BITMAPS:
			dib = dib_from_bmp(rendered[name].read_bytes())
			info = dib_info(dib)
			if (info.width, info.height, info.bits_per_pixel, info.compression) != (*shape, 0):
				raise PatchError(f"{name} is not a {shape[0]} x {shape[1]}, {shape[2]}-bit bitmap")
			slot = PeFile(data).bitmap(resource_id)
			old = dib_info(data[slot.data_offset : slot.data_offset + slot.size])
			if (old.width, old.height, old.bits_per_pixel) != shape:
				raise PatchError(f"msgina.dll resource {resource_id} is not the {shape[0]} x {shape[1]} bitmap it was written for")
			data = replace_bitmap(data, resource_id, dib, same_size=True)
	except PeError as error:
		raise PatchError(f"msgina.dll: {error}") from error
	patched = scratch / "agmsgina.dll"
	patched.write_bytes(data)
	result = sha256_file(patched)
	if result != RESULT_SHA256:
		patched.unlink(missing_ok=True)
		raise PatchError(f"patched msgina.dll is {result}, expected {RESULT_SHA256}")
	log("patch", f"   afterglow.logon: msgina.dll patched as agmsgina.dll ({result})")
	return [PatchedFile(PATCHED_PATH, patched)]
