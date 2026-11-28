#!/usr/bin/env python3
# Make guest/reg/ac97-preinstall.reg from registry exports of the image before and after the demo machine's first boot.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# The first export is of the image as the install left it (booted in QEMU); the second is of the same image after a cold boot in the
# machine that will run it (v86 with its AC'97 card), once ReactOS's plug and play has installed every device that machine has and the
# build had not.
#
# Usage: make-ac97-reg.py BEFORE.reg AFTER.reg OUT.reg [--software BEFORE_SW.reg AFTER_SW.reg]
# Each input is `regedit /e FILE HKEY_LOCAL_MACHINE\SYSTEM\ControlSet001` (UTF-16 text); the software pair is the same for
# `HKEY_LOCAL_MACHINE\SOFTWARE`, where the audio stack registers its COM classes and the `wave1` entry of Drivers32 that winmm
# reads. The output holds what the second boot added or changed, and nothing the running system writes by itself: resource lists
# (LogConf, Control under Enum), the device interface keys (Control\DeviceClasses, except the `Device Parameters` the INF writes),
# the service counter, the environment. What is left is each device's Enum entry and driver class entry, the services, tags and
# group orders that go with them, and the audio stack's category names and classes.
import argparse
import re
import sys
from pathlib import Path

PREFIX = "HKEY_LOCAL_MACHINE\\SYSTEM\\ControlSet001\\"
OUT_PREFIX = "HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\"
# Keys (and everything under them) that plug and play or the kernel writes at every start, from the machine it runs on.
RUNTIME_TREES = ("Control\\Session Manager\\Environment", "Control\\ServiceCurrent")
# The device interfaces are registered again at every start, but the INF gives each its `Device Parameters` (CLSID and friendly name), once.
INTERFACE_TREE = "control\\deviceclasses"
INTERFACE_KEPT = "device parameters"
# Values that are the machine's resources or live state; they are rewritten at each start.
RUNTIME_VALUES = ("BootConfig", "BasicConfigVector", "AllocConfig", "FilteredConfigVector", "OverrideConfigVector")


def parse(path: Path) -> dict[str, dict[str, str]]:
	"""`{key: {value name: the value's text, continuation lines included}}` from a regedit export."""
	text = path.read_bytes().decode("utf-16").replace("\r", "")
	keys: dict[str, dict[str, str]] = {}
	current = None
	lines = text.split("\n")
	index = 0
	while index < len(lines):
		line = lines[index]
		if line.startswith("["):
			current = line[1:-1]
			keys.setdefault(current, {})
		elif current is not None and (line.startswith('"') or line.startswith("@")):
			whole = line
			while whole.endswith("\\") and index + 1 < len(lines):
				index += 1
				whole += "\n" + lines[index]
			name = re.match(r'^("(?:[^"\\]|\\.)*"|@)=', whole).group(1)
			keys[current][name] = whole
		index += 1
	return keys


SOFTWARE_PREFIX = "HKEY_LOCAL_MACHINE\\SOFTWARE\\"
# What the software hive gets at every logon or start, or what the install leaves to run once: not part of the device.
SOFTWARE_RUNTIME_TREES = ("Microsoft\\Windows\\CurrentVersion\\Explorer\\SessionInfo",)
SOFTWARE_RUNTIME_VALUES = (
	("Microsoft\\Windows\\CurrentVersion\\RunOnce", None),
	("Microsoft\\Windows NT\\CurrentVersion\\ProfileList", None),
)


def is_software_runtime(relative: str) -> bool:
	lowered = relative.lower()
	return any(lowered == tree.lower() or lowered.startswith(tree.lower() + "\\") for tree in SOFTWARE_RUNTIME_TREES)


def software_value_skipped(relative: str) -> bool:
	lowered = relative.lower()
	return any(lowered == key.lower() or lowered.startswith(key.lower() + "\\") for key, _ in SOFTWARE_RUNTIME_VALUES)


def is_runtime(relative: str) -> bool:
	"""A key whose content the system makes again at every start."""
	parts = relative.lower().split("\\")
	if "logconf" in parts:
		return True
	if parts[0] == "enum" and parts[-1] == "control":  # ActiveService and the like
		return True
	if relative.lower().startswith(INTERFACE_TREE):
		return parts[-1] != INTERFACE_KEPT
	return any(relative.lower() == tree.lower() or relative.lower().startswith(tree.lower() + "\\") for tree in RUNTIME_TREES)


def section(before: dict, after: dict, prefix: str, out_prefix: str, runtime, skipped_values=lambda relative: False) -> list[str]:
	"""The keys of `after` that are new, or whose values changed, as .reg lines; `runtime(relative)` drops a key and everything it holds,
	`skipped_values(relative)` keeps a key but not its changed values."""
	out: list[str] = []
	for key, values in after.items():
		if not key.startswith(prefix):
			continue
		relative = key[len(prefix) :]
		if runtime(relative):
			continue
		is_new = key not in before
		kept = {
			name: text
			for name, text in values.items()
			if (is_new or (before[key].get(name) != text and not skipped_values(relative))) and name.strip('"') not in RUNTIME_VALUES
		}
		if not is_new and not kept:
			continue
		out.append(f"[{out_prefix}{relative}]")
		out += kept.values()
		out.append("")
	return out


def build(before: dict, after: dict, software: tuple[dict, dict] | None = None) -> str:
	out = [
		"Windows Registry Editor Version 5.00",
		"",
		"; The machine's devices and the AC'97 sound card driver, installed ahead of time. ReactOS's plug and play installs each device it",
		"; finds that the image's first boot (in QEMU) did not know: the Quill demo's emulator (v86) has other disk, video, network, bus",
		"; and sound hardware, and the AC'97 driver among it. That takes tens of seconds after the desktop appears, and the browser",
		"; machine's disk is not kept, so it was repeated at every cold boot and every Reset. These are the keys that boot added or",
		"; changed, with nothing the system rewrites at each start. Made by tools/ac97/make-ac97-reg.py; see docs/ac97-preinstall.md.",
		";",
		"; (c) Copyright 2026 Liminal HQ, Scott Morris",
		"; SPDX-License-Identifier: Apache-2.0 OR MIT",
		"",
	]
	out += section(before, after, PREFIX, OUT_PREFIX, is_runtime)
	if software is not None:
		out += section(*software, SOFTWARE_PREFIX, SOFTWARE_PREFIX, is_software_runtime, software_value_skipped)
	return "\n".join(out)


def main() -> int:
	parser = argparse.ArgumentParser(description="Make ac97-preinstall.reg from a before and an after registry export.")
	parser.add_argument("before", type=Path)
	parser.add_argument("after", type=Path)
	parser.add_argument("out", type=Path)
	parser.add_argument("--software", nargs=2, type=Path, metavar=("BEFORE_SW", "AFTER_SW"))
	args = parser.parse_args()
	software = (parse(args.software[0]), parse(args.software[1])) if args.software else None
	args.out.write_text(build(parse(args.before), parse(args.after), software), encoding="utf-8", newline="\n")
	return 0


if __name__ == "__main__":
	sys.exit(main())
