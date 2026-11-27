# Trim profiles: named lists of files and folders to remove from the installed disk, a recipe's own extra lists after them, and the
# guard that keeps a trim from ever removing a file a patcher wrote or a licence file.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
from dataclasses import dataclass, field
from pathlib import Path

from .mtools import FatImage
from .paths import REPO

PROFILES_DIR = REPO / "profiles"

# The licence texts and notices the disk must keep, as paths under the FAT32 root. `LICENSES` is a folder: everything in it is kept.
# The release steps write the first three; the last is the licence of WineVDM, which the trim keeps. Gecko's licence goes with Gecko,
# which the `base` profile removes.
LICENCE_PATHS = (
	"LICENSES",
	"NOTICE.txt",
	"CHANGES.txt",
	"Program Files/otvdm/LICENSE",
)


class TrimError(Exception):
	"""A profile or extra list that cannot be read, or one that would remove a protected file."""


@dataclass(frozen=True)
class TrimEntry:
	kind: str  # "f" a file, "d" a folder and everything in it
	path: str
	source: str = field(default="", compare=False)  # the list that holds the entry, for messages; empty for the named profile


@dataclass
class Profile:
	name: str
	entries: list[TrimEntry] = field(default_factory=list)
	sources: list[tuple[str, int]] = field(default_factory=list)  # each list applied, in order, with its entry count


@dataclass
class TrimReport:
	removed: list[TrimEntry] = field(default_factory=list)
	missing: list[TrimEntry] = field(default_factory=list)
	bytes_freed: int = 0
	sources: list[tuple[str, int]] = field(default_factory=list)


def _normal(path: str) -> str:
	"""A path under the FAT32 root in the form used for comparison: forward slashes, no edges, lower case (FAT ignores case)."""
	return path.replace("\\", "/").strip("/").lower()


def parse_profile(name: str, text: str, source: bool = False) -> Profile:
	entries = []
	for number, raw in enumerate(text.splitlines(), 1):
		line = raw.strip()
		if not line or line.startswith("#"):
			continue
		kind, _, path = line.partition(" ")
		if kind not in ("f", "d") or not path.strip():
			raise TrimError(f"profile {name}, line {number}: expected 'f PATH' or 'd PATH', got {raw!r}")
		if ".." in path.replace("\\", "/").split("/") or path.startswith(("/", "\\")):
			raise TrimError(f"profile {name}, line {number}: unsafe path {path!r}")
		entries.append(TrimEntry(kind, path.strip(), name if source else ""))
	return Profile(name, entries, [(name, len(entries))])


def profile_names() -> list[str]:
	return sorted(path.stem for path in PROFILES_DIR.glob("*.txt"))


def load_profile(name: str, directory: Path | None = None) -> Profile:
	path = (directory or PROFILES_DIR) / f"{name}.txt"
	try:
		return parse_profile(name, path.read_text(encoding="utf-8"))
	except FileNotFoundError:
		raise TrimError(f"no trim profile named {name!r}; known: {', '.join(profile_names())}") from None


def load_extra(paths: list[str]) -> list[Profile]:
	"""Read the recipe's `trim.extra` files, in order. A missing or malformed file is an error that names the key and the entry."""
	lists = []
	for index, name in enumerate(paths):
		key = f"trim.extra[{index}]"
		try:
			text = Path(name).read_text(encoding="utf-8")
		except FileNotFoundError:
			raise TrimError(f"{key}: no such trim list: {name}") from None
		except (OSError, UnicodeDecodeError) as error:
			raise TrimError(f"{key}: cannot read {name}: {error}") from None
		try:
			lists.append(parse_profile(name, text, source=True))
		except TrimError as error:
			raise TrimError(f"{key}: {error}") from None
	return lists


def build_profile(name: str, extra_paths: list[str] = ()) -> Profile:
	"""The named profile followed by each extra list, in order. An entry an earlier list already removes is not repeated."""
	profile = load_profile(name)
	seen = {(entry.kind, _normal(entry.path)) for entry in profile.entries}
	for extra in load_extra(list(extra_paths)):
		fresh = [entry for entry in extra.entries if (entry.kind, _normal(entry.path)) not in seen]
		seen.update((entry.kind, _normal(entry.path)) for entry in fresh)
		profile.entries += fresh
		profile.sources.append((extra.name, len(fresh)))
	return profile


def protection_conflicts(entry: TrimEntry, patched_paths: set[str] | list[str] = ()) -> str | None:
	"""Why this entry may not run, or None. An entry conflicts when it removes a patched file or a licence path, a folder that holds one,
	or a file inside a protected licence folder."""
	target = _normal(entry.path)
	protected = {_normal(path): "a patched file" for path in patched_paths}
	protected.update({_normal(path): "a licence file" for path in LICENCE_PATHS})
	for path, what in protected.items():
		same = target == path
		holds = entry.kind == "d" and path.startswith(target + "/")
		inside = path in {_normal(p) for p in LICENCE_PATHS} and target.startswith(path + "/")
		if same or holds or inside:
			return f"{entry.path} would remove {what} ({path})"
	return None


def removes(profile: Profile, path: str) -> bool:
	"""True when the profile removes the file at `path`: a `f` entry for it, or a `d` entry for a folder that holds it."""
	target = _normal(path)
	for entry in profile.entries:
		name = _normal(entry.path)
		if target == name or (entry.kind == "d" and target.startswith(name + "/")):
			return True
	return False


def check_profile(profile: Profile, patched_paths: set[str] | list[str] = ()) -> None:
	"""Refuse a profile that reaches a protected file, before anything is removed."""
	for entry in profile.entries:
		problem = protection_conflicts(entry, patched_paths)
		if problem:
			where = f"trim list {entry.source}" if entry.source else f"profile {profile.name}"
			raise TrimError(f"{where}: {problem}")


def apply_profile(disk: FatImage, profile: Profile, patched_paths: set[str] | list[str] = ()) -> TrimReport:
	"""Remove the profile's entries from the disk (a working copy; never the golden disk). The protection check runs first, and
	afterwards every patched file is confirmed to be still there."""
	check_profile(profile, patched_paths)
	report = TrimReport(sources=list(profile.sources))
	free_before = disk.free_bytes()
	for entry in profile.entries:
		removed = disk.delete_tree(entry.path) if entry.kind == "d" else disk.delete_file(entry.path)
		(report.removed if removed else report.missing).append(entry)
	report.bytes_freed = disk.free_bytes() - free_before
	for path in patched_paths:
		if not disk.exists(path):
			raise TrimError(f"the trim removed a patched file: {path}")
	return report
