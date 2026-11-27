# SHA-256 sums in the `sha256sum` format: write them for a folder of outputs, and check a file of them.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
from dataclasses import dataclass
from pathlib import Path

from .fetch import sha256_file


class SumsError(Exception):
	"""A sums file that cannot be read."""


@dataclass(frozen=True)
class CheckResult:
	checked: int
	failed: list[str]
	missing: list[str]

	@property
	def ok(self) -> bool:
		return not self.failed and not self.missing


def list_files(paths: list[Path]) -> list[Path]:
	"""The files named, with each folder replaced by the files under it, sorted by path."""
	files: list[Path] = []
	for path in paths:
		if path.is_dir():
			files += [child for child in path.rglob("*") if child.is_file()]
		elif path.is_file():
			files.append(path)
		else:
			raise SumsError(f"{path}: no such file or folder")
	return sorted(files)


def sums_text(paths: list[Path], base: Path | None = None) -> str:
	"""`sha256sum`-format lines (`HASH  NAME`, binary mode off). Names are relative to `base` when given."""
	lines = []
	for path in list_files(paths):
		name = path.relative_to(base) if base else path
		lines.append(f"{sha256_file(path)}  {name.as_posix()}")
	return "\n".join(lines) + ("\n" if lines else "")


def check_sums(sums_file: Path, base: Path | None = None) -> CheckResult:
	"""Check every line of a sums file. Names are relative to `base`, else to the sums file's folder."""
	root = base or sums_file.parent
	checked = 0
	failed: list[str] = []
	missing: list[str] = []
	for number, line in enumerate(sums_file.read_text().splitlines(), 1):
		if not line.strip():
			continue
		expected, separator, name = line.partition("  ")
		if not separator or len(expected) != 64:
			raise SumsError(f"{sums_file}, line {number}: not a sha256sum line")
		target = root / name.lstrip("*")
		if not target.is_file():
			missing.append(name)
			continue
		checked += 1
		if sha256_file(target) != expected:
			failed.append(name)
	return CheckResult(checked, failed, missing)
