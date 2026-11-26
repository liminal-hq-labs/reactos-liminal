# What every patcher shares: the error it raises and the file it returns. They live here, not in patchers.py, so a patcher module can
# import them without importing the registry that imports the patcher.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from .fetch import sha256_file


class PatchError(Exception):
	"""A patcher refused its input or produced a file that does not match its pin."""


@dataclass(frozen=True)
class PatchedFile:
	image_path: str  # where the file goes on the disk, under the FAT32 root
	local_file: Path  # the patched copy in the work directory
	attributes: str = (
		""  # mattrib flags to put back after the write, such as "+h +s" for freeldr.ini; empty leaves them as the copy made them
	)


@dataclass
class PinRecorder:
	"""What `rl pin` collects while the icon patchers run: each patcher's result for the icon set it was given, instead of a check
	against a pin. `results[section][icon set digest][file]` is the SHA-256 of the patched file."""

	results: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)

	def record(self, section: str, digest: str, name: str, result: str) -> None:
		self.results.setdefault(section, {}).setdefault(digest, {})[name] = result


_recorder: PinRecorder | None = None


@contextmanager
def recording():
	"""Run patchers in lock mode: they record their results in the returned recorder and do not require a pin."""
	global _recorder
	previous, _recorder = _recorder, PinRecorder()
	try:
		yield _recorder
	finally:
		_recorder = previous


def active_recorder() -> PinRecorder | None:
	return _recorder


def read_sums(path: Path) -> dict[str, str]:
	"""The `sha256sum`-format file at `path` as `{name: hash}`."""
	try:
		lines = path.read_text(encoding="utf-8").splitlines()
	except OSError as error:
		raise PatchError(f"cannot read {path}: {error}") from error
	sums: dict[str, str] = {}
	for line in lines:
		fields = line.split()
		if len(fields) == 2:
			sums[fields[1].lstrip("*")] = fields[0]
	return sums


def render_art(art_folder: Path, destination: Path, expected_files: list[str]) -> dict[str, Path]:
	"""Run Afterglow's own `render.py` for one art folder (it holds `render.py` and `SHA256SUMS`) into `destination`, and check each
	file named in `expected_files` against the sum Afterglow records for it. Returns `{name: path}`."""
	tool = art_folder / "render.py"
	if not tool.is_file():
		raise PatchError(f"{tool} is missing; the pinned Afterglow source has no such art")
	destination.mkdir(parents=True, exist_ok=True)
	done = subprocess.run(["python3", "-I", str(tool), str(destination)], capture_output=True, text=True, check=False)
	if done.returncode != 0:
		raise PatchError(f"{tool.parent.name}/render.py failed: {(done.stderr or done.stdout).strip()[-400:]}")
	recorded = read_sums(art_folder / "SHA256SUMS")
	rendered: dict[str, Path] = {}
	for name in expected_files:
		path = destination / name
		if name not in recorded:
			raise PatchError(f"{art_folder.name}/SHA256SUMS has no sum for {name}")
		if not path.is_file():
			raise PatchError(f"{tool.parent.name}/render.py wrote no {name}")
		actual = sha256_file(path)
		if actual != recorded[name]:
			raise PatchError(f"{name} renders as {actual}, Afterglow records {recorded[name]}; the renderer or its fonts differ")
		rendered[name] = path
	return rendered
