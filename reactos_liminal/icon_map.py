# Afterglow's icon map: which ReactOS resource each of its icons replaces, as `desktop/icons/map.json` verifies it.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The icon patchers take their list of groups and toolbar cells from this map, not from a table of their own. An entry's `resource`
names a module and an icon group (or, for the Explorer toolbar, the bitmap strips and a cell index), and its `also` list names more
resources that take the same icon. A resource is null unless Afterglow verified it against ReactOS 0.4.16, so nothing here guesses.
A new icon set is therefore a new Afterglow pin and nothing else: the patchers read the new map and the new sums.

The repository's own tables (`shell32_icons.json`, `icon_families.json`, `bitmap_strips.json`) keep what the map cannot say: the stock
file's SHA-256 that guards each patch, the frames a group holds, and the few groups the map does not name that are replaced anyway
(each with its icon and why)."""

import json
from pathlib import Path

from .patch_base import PatchError


def load_map(source_tree: Path) -> dict[str, dict]:
	"""Afterglow's icon map as `{icon id: entry}`."""
	map_file = source_tree / "desktop" / "icons" / "map.json"
	if not map_file.is_file():
		raise PatchError(f"{map_file} is missing; the pinned Afterglow commit has no icon map")
	return {entry["id"]: entry for entry in json.loads(map_file.read_text())["icons"]}


def _resources(entry: dict) -> list[dict]:
	found = [entry["resource"]] if entry.get("resource") else []
	return found + list(entry.get("also") or [])


def module_groups(entries: dict[str, dict], module: str) -> dict[int, str]:
	"""The verified icon groups of one module as `{group id: Afterglow icon id}`. Two icons for one group is an error in the map."""
	groups: dict[int, str] = {}
	for icon_id, entry in entries.items():
		for resource in _resources(entry):
			if resource.get("module") != module or "group" not in resource:
				continue
			group = resource["group"]
			if groups.get(group, icon_id) != icon_id:
				raise PatchError(f"Afterglow's map.json gives {module} group {group} to both {groups[group]!r} and {icon_id!r}")
			groups[group] = icon_id
	return groups


def toolbar_cells(entries: dict[str, dict], module: str, strip_ids: list[int]) -> dict[int, str]:
	"""The verified toolbar cells of one module as `{cell index: Afterglow icon id}`, for entries whose bitmaps are exactly the
	strips the patcher knows. A map that names other bitmaps than the table holds is refused rather than half applied."""
	cells: dict[int, str] = {}
	for icon_id, entry in entries.items():
		for resource in _resources(entry):
			if resource.get("module") != module or "cell" not in resource:
				continue
			if sorted(resource.get("bitmaps", [])) != sorted(strip_ids):
				raise PatchError(
					f"Afterglow's map.json puts {icon_id!r} in bitmaps {resource.get('bitmaps')} of {module}; the table has {strip_ids}"
				)
			cell = resource["cell"]
			if cells.get(cell, icon_id) != icon_id:
				raise PatchError(f"Afterglow's map.json gives {module} cell {cell} to both {cells[cell]!r} and {icon_id!r}")
			cells[cell] = icon_id
	return cells


def require_icon(entries: dict[str, dict], icon_id: str, where: str) -> None:
	"""An icon this repository names itself must exist in the map."""
	if icon_id not in entries:
		raise PatchError(f"Afterglow's map.json has no icon {icon_id!r} ({where})")


def load_bitmaps(source_tree: Path) -> list[dict]:
	"""The `bitmaps` list of Afterglow's map: each dialog bitmap with its module, resource id, stock size and depth, the art file that
	renders it (`bitmap`, in the folder of `file`) and what shows it."""
	map_file = source_tree / "desktop" / "icons" / "map.json"
	if not map_file.is_file():
		raise PatchError(f"{map_file} is missing; the pinned Afterglow commit has no icon map")
	found = json.loads(map_file.read_text()).get("bitmaps")
	if not found:
		raise PatchError(f"{map_file} has no `bitmaps` list; the pinned Afterglow commit predates the dialog art")
	return found
