# `rl doctor`: check that the tools the pipeline calls are installed.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .isobuild import writers_on_path
from .paths import REPO
from .recipe import ISO_WRITER_PIN


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
	Tool("xorriso", "reads the install ISO, extracts its tree and builds the settings CD"),
	Tool(
		"mkisofs",
		"writes the install CD and the remastered ISO (cdrtools; cdrkit installs it as a link to genisoimage)",
		alternative="genisoimage",
		version_args=("-version",),
	),
	Tool(
		"genisoimage",
		"writes the install CD and the remastered ISO (cdrkit, the writer the recipe pins)",
		required=False,
		version_args=("-version",),
	),
	Tool("gcab", "writes the extra Setup cabinet on the remastered ISO", required=False),
	Tool("cabextract", "checks the extra Setup cabinet", required=False),
	Tool("zstd", "compresses the v86 disk parts and state"),
	Tool("fallocate", "punches holes in the finished image so it is sparse", required=False),
	Tool("bash", "runs the helper scripts"),
	Tool("rustup", "installs the pinned Rust toolchain for the programs built from source (afterfetch.exe)", required=False),
	Tool("cargo", "builds the programs built from source (afterfetch.exe)", required=False),
	Tool("llvm-rc", "builds the Afterglow visual style", required=False),
	Tool("lld-link", "builds the Afterglow visual style", required=False),
	Tool("rsvg-convert", "renders Afterglow's vector art", required=False),
	Tool("node", "renders Afterglow's wallpapers", required=False),
	Tool("magick", "ImageMagick 7: crops, scales and writes Afterglow's wallpaper BMP", required=False),
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


def _iso_writer_lines() -> list[str]:
	"""Which ISO writers are installed against the one the recipe pins. A different writer makes a disc that boots the same but is not
	byte for byte the pinned build's."""
	writers = writers_on_path()
	if not writers:
		return []  # the tool lines above already report the missing writer
	if any(writer.identity == ISO_WRITER_PIN for writer in writers):
		return [f"ok      ISO writer {ISO_WRITER_PIN} matches the recipe's pin"]
	found = ", ".join(writer.identity for writer in writers)
	return [
		f"differs ISO writer {found}: the recipe pins {ISO_WRITER_PIN}; discs boot the same but their bytes differ from the pinned build"
	]


def _rust_line() -> str:
	"""Whether the toolchain `tools/afterfetch` pins is installed with `rust-src` (the build compiles `core` for a Pentium) and its own
	`rust-lld`. Checked in that project's folder, where `rust-toolchain.toml` selects the version."""
	folder = REPO / "tools" / "afterfetch"
	if shutil.which("rustc") is None:
		return (
			"absent  rust toolchain: builds afterfetch.exe (rustup fetches the pinned one: `rustup toolchain install` in tools/afterfetch)"
		)
	try:
		done = subprocess.run(["rustc", "--print", "sysroot"], capture_output=True, text=True, timeout=60, check=False, cwd=folder)
	except (OSError, subprocess.TimeoutExpired):
		return "absent  rust toolchain: could not run rustc in tools/afterfetch"
	sysroot = Path(done.stdout.strip())
	if done.returncode != 0 or not sysroot.is_dir():
		return "absent  rust toolchain: the pinned toolchain is not installed (run `rustup toolchain install` in tools/afterfetch)"
	missing = [name for name, path in (("rust-src", "lib/rustlib/src/rust/library"),) if not (sysroot / path).is_dir()]
	if not list(sysroot.glob("lib/rustlib/*/bin/rust-lld")):
		missing.append("rust-lld")
	if missing:
		return f"absent  rust toolchain {sysroot.name}: missing {', '.join(missing)} for afterfetch.exe (`rustup component add rust-src`)"
	return f"ok      rust toolchain {sysroot.name}: rust-src and rust-lld present for afterfetch.exe"


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
	lines += _iso_writer_lines()
	lines.append(_rust_line())
	kvm = "/dev/kvm"
	if os.access(kvm, os.W_OK):
		lines.append(f"ok      {kvm}: hardware acceleration for the install and the build VM")
	else:
		lines.append(f"absent  {kvm}: QEMU falls back to software emulation, about ten times slower")
	return lines, bool(ok)
