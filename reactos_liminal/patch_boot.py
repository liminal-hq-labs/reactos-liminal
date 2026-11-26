# The boot patcher: the Afterglow logo in a copy of the kernel, installed as `agntoskr.exe`, and a FreeLoader menu that starts it.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# The kernel draws its boot screen from RT_BITMAP 5, a 190 x 224, 16-colour RLE4 logo in a 16,504-byte slot. The Afterglow logo is
# 414 x 366 (the most the "safe to turn off" screen can hold is 415 x 366), 16 colours and RLE4 as well, and shorter than the slot, so
# it is written over the slot and the resource's size field is lowered. Its 16 palette entries are the palette of the whole boot
# screen, and the VGA DAC keeps only the top six bits of each channel, so the screen shows each colour truncated (`value >> 2`), not
# as designed; Afterglow's palette notes record what a capture shows. The stock `ntoskrnl.exe` stays on the disk, and FreeLoader's
# `Kernel=agntoskr.exe` entry picks the copy. The input must be exactly the 0.4.16 kernel and the result must match the pinned sum.
#
# The boot menu is `freeldr.ini` on the installed disk: the stock text in, a minimal menu out (RL-13, RL-13.1). The install CD's own
# menu is edited by `isopatch` and is not this file.
import hashlib
from pathlib import Path

from .fetch import sha256_file
from .log import log
from .mtools import FatImage
from .patch_base import PatchedFile, PatchError, render_art
from .pe_resource import PeError, PeFile, dib_from_bmp, dib_info, replace_bitmap

KERNEL_PATH = "ReactOS/system32/ntoskrnl.exe"
PATCHED_KERNEL_PATH = "ReactOS/system32/agntoskr.exe"
MENU_PATH = "freeldr.ini"
# The ReactOS 0.4.16 kernel, the one file this patcher accepts.
KERNEL_SHA256 = ("832cedd75a1e3bcb7209d8f09b37e694cdd40117c084bc262b2d013d528138ff",)
KERNEL_RESULT_SHA256 = "67493c463046bcc4352f19a22b1c126d213e1195c4dfa68d4b52fca1c23fa7a0"
LOGO_ID = 5
STOCK_LOGO = (190, 224, 4, 2, 16504)  # width, height, bits per pixel, compression (RLE4), DIB bytes
LOGO_SHAPE = (414, 366, 4, 2)
MAX_LOGO = (415, 366)  # the shutdown screen draws the logo unclipped at (225, 114) on 640 x 480
LOGO_BMP = "afterglow-logo-rle4.bmp"

# The freeldr.ini an unattended install of this release leaves on the disk, after `install` put back its default entry and delay.
MENU_STOCK_SHA256 = ("60d6f98163599a82982f769c93348f55333b466700c57e4e8d3c8b5b66daaba5",)
MENU_RESULT_SHA256 = "ff8e138bcc90f5f23f081ad4ed622ff25bdd51cf5b650189304f5a8e1c07094e"
MENU_TIMEOUT = 10
# Named as ReactOS names its own entries ("ReactOS", "ReactOS (Debug)"); the stock "ReactOS" entry is the fallback.
ENTRY_NAME = "ReactOS (Afterglow)"
# Design 1: FreeLoader's minimal menu, a gold selection bar on black. FreeLoader's own names for the colours are the 16 text colours;
# Brown is the dark yellow the text mode shows as gold.
DISPLAY = (
	"MinimalUI=Yes",
	"SelectedColor=Brown",
	"SelectedTextColor=Black",
	f"TimeText=Starting {ENTRY_NAME} in %d s",
)


def afterglow_menu(stock: bytes) -> bytes:
	"""The Afterglow freeldr.ini made from the stock one: the Afterglow entry first and the default, the stock entry kept as the
	fallback under its own name, every other entry and section unchanged."""
	text = stock.decode("ascii").replace("\r\n", "\n")
	lines = text.split("\n")
	out: list[str] = []
	section = ""
	for line in lines:
		if line.startswith("["):
			if section == "Display":
				out += list(DISPLAY) + [""]
			section = line.strip("[]")
			if section == "Display":
				out.append(line)
				continue  # the stock keys are replaced as a block when the section ends
			if section == "ReactOS":
				out += [
					"[Afterglow]",
					"BootType=Windows2003",
					"SystemPath=multi(0)disk(0)rdisk(0)partition(1)\\ReactOS",
					"Options=/FASTDETECT",
					"Kernel=agntoskr.exe",
					"",
				]
		if section == "Display" and not line.startswith("["):
			continue
		if section == "FREELOADER" and line.startswith("TimeOut="):
			line = f"TimeOut={MENU_TIMEOUT}"
		elif section == "FREELOADER" and line.startswith("DefaultOS="):
			line = "DefaultOS=Afterglow"
		elif section == "Operating Systems" and line.startswith("ReactOS="):
			out.append(f'Afterglow="{ENTRY_NAME}"')
		out.append(line)
	result = "\n".join(out)
	for needle in ("[Afterglow]", "DefaultOS=Afterglow", f'Afterglow="{ENTRY_NAME}"', 'ReactOS="ReactOS"', "MinimalUI=Yes"):
		if needle not in result:
			raise PatchError(f"freeldr.ini: the stock file has no place for {needle!r}")
	return result.replace("\n", "\r\n").encode("ascii")


def _patch_kernel(golden: FatImage, source_tree: Path, scratch: Path) -> PatchedFile:
	rendered = render_art(source_tree / "desktop" / "boot", scratch / "boot-art", [LOGO_BMP])
	stock = scratch / "ntoskrnl.exe"
	golden.copy_out(KERNEL_PATH, stock)
	actual = sha256_file(stock)
	if actual not in KERNEL_SHA256:
		raise PatchError(f"refused: the guest's ntoskrnl.exe is {actual}, not the ReactOS 0.4.16 kernel this patcher was written for")
	data = stock.read_bytes()
	dib = dib_from_bmp(rendered[LOGO_BMP].read_bytes())
	info = dib_info(dib)
	if (info.width, info.height, info.bits_per_pixel, info.compression) != LOGO_SHAPE or info.colours_used not in (0, 16):
		raise PatchError(f"{LOGO_BMP} is not a {LOGO_SHAPE[0]} x {LOGO_SHAPE[1]} RLE4 bitmap with 16 colours")
	if info.width > MAX_LOGO[0] or info.height > MAX_LOGO[1]:
		raise PatchError(f"the logo is larger than {MAX_LOGO[0]} x {MAX_LOGO[1]}")
	try:
		slot = PeFile(data).bitmap(LOGO_ID)
		old = dib_info(data[slot.data_offset : slot.data_offset + slot.size])
		if (old.width, old.height, old.bits_per_pixel, old.compression, slot.size) != STOCK_LOGO:
			raise PatchError("refused: bitmap 5 is not the stock 190 x 224 RLE4 logo")
		data = replace_bitmap(data, LOGO_ID, dib, same_size=False)
	except PeError as error:
		raise PatchError(f"ntoskrnl.exe: {error}") from error
	patched = scratch / "agntoskr.exe"
	patched.write_bytes(data)
	result = sha256_file(patched)
	if result != KERNEL_RESULT_SHA256:
		patched.unlink(missing_ok=True)
		raise PatchError(f"patched ntoskrnl.exe is {result}, expected {KERNEL_RESULT_SHA256}")
	log("patch", f"   afterglow.boot: ntoskrnl.exe patched as agntoskr.exe ({result})")
	return PatchedFile(PATCHED_KERNEL_PATH, patched)


def _patch_menu(golden: FatImage, scratch: Path) -> PatchedFile:
	stock = golden.read(MENU_PATH)
	actual = hashlib.sha256(stock).hexdigest()
	if actual not in MENU_STOCK_SHA256:
		raise PatchError(f"refused: the guest's freeldr.ini is {actual}, not the file an unattended 0.4.16 install leaves")
	patched = scratch / "freeldr.ini"
	patched.write_bytes(afterglow_menu(stock))
	result = sha256_file(patched)
	if result != MENU_RESULT_SHA256:
		patched.unlink(missing_ok=True)
		raise PatchError(f"patched freeldr.ini is {result}, expected {MENU_RESULT_SHA256}")
	log("patch", f"   afterglow.boot: freeldr.ini has the {ENTRY_NAME!r} entry ({result})")
	return PatchedFile(MENU_PATH, patched, attributes="+h +s")


def afterglow_boot(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""The kernel with the Afterglow logo as agntoskr.exe, and the boot menu that starts it with the stock entry kept as the fallback."""
	return [_patch_kernel(golden, source_tree, scratch), _patch_menu(golden, scratch)]
