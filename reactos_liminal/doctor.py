# `rl doctor`: check that the tools the pipeline calls are installed.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
	name: str  # the executable looked up on PATH
	purpose: str
	required: bool = True
	version_args: tuple[str, ...] = ("--version",)
	alternative: str | None = None  # another executable that does the same job


TOOLS = (
	Tool("qemu-system-i386", "runs the install and the build VM", version_args=("--version",)),
	Tool("qemu-img", "creates and converts disk images"),
	Tool("mcopy", "mtools: reads and writes files on the FAT32 disk image", version_args=("--version",)),
	Tool("mdel", "mtools: trims files from the disk image"),
	Tool("xorriso", "reads the install ISO and builds the settings CD", alternative="7z"),
	Tool("7z", "reads ISO files where xorriso is not installed", required=False, version_args=()),
	Tool("zstd", "compresses the v86 disk parts and state"),
	Tool("bash", "runs the helper scripts"),
	Tool("llvm-rc", "builds the Afterglow visual style", required=False),
	Tool("lld-link", "builds the Afterglow visual style", required=False),
	Tool("rsvg-convert", "renders Afterglow's vector art", required=False),
)


def _version(tool: Tool, path: str) -> str:
	if not tool.version_args:
		return ""
	try:
		done = subprocess.run([path, *tool.version_args], capture_output=True, text=True, timeout=10, check=False)
	except (OSError, subprocess.TimeoutExpired):
		return ""
	text = (done.stdout or done.stderr).strip()
	return text.splitlines()[0][:80] if text else ""


def check() -> tuple[list[str], bool]:
	"""The report lines and whether every required tool is present."""
	lines: list[str] = []
	ok = True
	python_ok = sys.version_info >= (3, 12)
	lines.append(f"{'ok     ' if python_ok else 'MISSING'} python3 {sys.version.split()[0]} (3.12 or newer)")
	ok &= python_ok
	found = {tool.name: shutil.which(tool.name) for tool in TOOLS}
	for tool in TOOLS:
		path = found[tool.name]
		if path:
			version = _version(tool, path)
			lines.append(f"ok      {tool.name}: {tool.purpose}" + (f"  [{version}]" if version else ""))
			continue
		covered = tool.alternative is not None and found.get(tool.alternative)
		if tool.required and not covered:
			ok = False
			lines.append(f"MISSING {tool.name}: {tool.purpose}")
		else:
			lines.append(
				f"absent  {tool.name}: {tool.purpose} ({'optional' if not tool.required else 'covered by ' + str(tool.alternative)})"
			)
	for module, purpose in (
		("numpy", "Afterglow's style and pointer generators"),
		("PIL", "Afterglow's pointer generator"),
	):
		try:
			__import__(module)
			lines.append(f"ok      python {module}: {purpose}")
		except ImportError:
			lines.append(f"absent  python {module}: {purpose} (optional)")
	kvm = "/dev/kvm"
	if os.access(kvm, os.W_OK):
		lines.append(f"ok      {kvm}: hardware acceleration for the install and the build VM")
	else:
		lines.append(f"absent  {kvm}: QEMU falls back to software emulation, about ten times slower")
	return lines, bool(ok)
