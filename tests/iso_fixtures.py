# A small synthetic stand-in for the official install disc's file tree, with the files the ISO code looks at. No ReactOS file is used.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import shutil
from pathlib import Path

from reactos_liminal import isotree
from reactos_liminal.isobuild import detect_writer

FREELDR = (
	"[FREELOADER]\r\nDefaultOS=LiveImg\r\nTimeOut=3\r\n\r\n[Display]\r\nTitleText=ReactOS Boot Media\r\nMinimalUI=Yes\r\n\r\n"
	'[Operating Systems]\r\nSetup="ReactOS Setup (Text Mode)"\r\nLiveImg="ReactOS Live Environment (Graphics Mode)"\r\n'
	'LiveImg_RamDisk="ReactOS Live Environment - RamDisk"\r\n'
)
TXTSETUP = (
	'[Cabinets]\r\nCabinet = reactos.cab\r\n\r\n[SetupData]\r\nSetupDebugOptions = "/DEBUG /KDSERIAL /DEBUGPORT=COM1 /FIRSTCHANCE"\r\n'
)
UNATTEND = "[Unattend]\r\nUnattendSetupEnabled = no\r\n"
LONG_NAME = "x86_microsoft.windows.common-controls_6595b64144ccf1df_5.82.2600.2982_none_deadbeef"

FILES = {
	"loader/isoboot.bin": b"\x90" * 2048,
	"loader/isobtrt.bin": b"\x91" * 2048,
	"loader/isombr.bin": b"\xeb" * 440,
	"loader/freeldr.sys": b"freeldr" * 300,
	"freeldr.ini": FREELDR.encode(),
	"i386/txtsetup.sif": TXTSETUP.encode(),
	"i386/unattend.inf": UNATTEND.encode(),
	"i386/reactos.cab": b"MSCF" + b"cabinet" * 400,
	"reactos/system32/config/system": b"hive" * 100,
	"reactos/system32/ntoskrnl.exe": b"MZ" * 300,
	"reactos/system32/drivers/cdfs.sys": b"MZ" * 100,
	f"reactos/winsxs/{LONG_NAME}/a.dll": b"MZ",
	"Profiles/Default User/ntuser.dat": b"profile",
}


def make_tree(root: Path) -> Path:
	"""Write the synthetic tree under `root/tree` (with an empty folder, as `Profiles` is on the real disc) and return it."""
	tree = root / "tree"
	for name, data in FILES.items():
		path = tree / name
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_bytes(data)
	(tree / "Profiles" / "Empty").mkdir()
	return tree


def stock_sums() -> dict[str, str]:
	"""The sums of the synthetic files the edits guard, to stand in for the real disc's."""
	return {name: hashlib.sha256(FILES[name]).hexdigest() for name in isotree.STOCK_SUMS}


def have_writer() -> bool:
	try:
		detect_writer()
	except Exception:
		return False
	return shutil.which("xorriso") is not None
