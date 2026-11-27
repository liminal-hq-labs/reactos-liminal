# The icon coverage report: for each resource Afterglow's map names, whether an icon patcher replaced it, left it alone (and why) or
# could not verify it.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""`rl pin` runs every icon patcher with nothing trimmed and keeps what each did with each resource (`PinRecorder.patched` and
`.skipped`). This module sets that against the map: every resource the map lists is exactly one row, with one of three statuses.

- **patched**: a patcher wrote the Afterglow icon into the file (or files) named.
- **skipped**: a patcher looked at the resource and left it alone, with the reason (a group missing from the stock file, a file that is
  not on the disk).
- **unverified**: no patcher took it: the map has no verified resource for the icon, or the module is on the disk but this repository
  holds no stock SHA-256 for it, so nothing may be written to it.

A resource the repository's own tables add (a group the map does not name) is listed after the map's rows with its evidence `table`.
The compact column says whether the `base` trim keeps the patched file; a patcher leaves a removed file alone, so the full and the
compact image have one patch list. The report is written to `docs/icon-coverage.md` by `rl pin` and checked by `rl pin --check`."""

from dataclasses import dataclass
from pathlib import Path

from .icon_map import map_resources
from .patch_base import PinRecorder
from .paths import REPO
from .trim import Profile, removes

REPORT_FILE = REPO / "docs" / "icon-coverage.md"
PATCHED, SKIPPED, UNVERIFIED = "patched", "skipped", "unverified"
BITMAP_MODULES = {"browseui.dll"}  # modules whose resources are toolbar cells, not icon groups


# Why an icon the map leaves unmapped stays unpatched, from reading ReactOS 0.4.16's source and its stock files for something that shows
# the art. The icons are drawn for the Afterglow set, but no resource of the image is that thing, and none is invented for them.
UNMAPPED_REASONS = {
	"cd-disc": (
		"no resource shows a disc; the nearest, setupapi.dll 51, is the Device Manager's DVD/CD-ROM drives class icon "
		"(hivesys.inf `Icon` -51), a drive"
	),
	"clock": "the taskbar clock is text drawn by Explorer, not an icon; Date and Time's own icon is `datetime`",
	"floppy-disk": (
		"no resource shows a disk; setupapi.dll 50 is named by no device class, and shell32.dll 7, the floppy drive, is `floppy`"
	),
	"monitor": (
		"the Monitor device class names no icon in hivesys.inf, and the monitor in Display Properties (desk.cpl 1001) is a "
		"160 x 120 bitmap, not an icon"
	),
	"ram-module": (
		"no resource shows memory; the Ramdisk class takes setupapi.dll 5, the network card icon, and setupapi.dll 159 is named by no class"
	),
	"readme": "a shortcut's icon, not a resource: the Read Me shortcut names no icon, so it shows the .txt file type's",
	"showdesk": "the first Show Desktop design; the button asks for imageres.dll 110, which `showdesktop` takes",
	"trynet": (
		"the tray network icons are netshell.dll 105 to 109, which the `lan` icons take (`lan`, `lanoff`, `lanrec`, `lantrans`, "
		"`lanboth`); no resource is left for this one"
	),
	"usb-key": (
		"no resource shows a USB drive; setupapi.dll 20 is the Universal Serial Bus controllers class, and no class names "
		"setupapi.dll 21 (a removable drive)"
	),
}


@dataclass(frozen=True)
class Row:
	icon_id: str
	module: str
	target: str  # "group 100", "cell 5" or "-" when the map names no resource
	evidence: str
	status: str
	files: tuple[str, ...]
	detail: str  # why, for a skipped or unverified row


def _key(resource: dict) -> tuple[str, str, int] | None:
	kind = "cell" if "cell" in resource else "group" if "group" in resource else None
	if kind is None:
		return None
	return (resource["module"].lower(), kind, resource[kind])


def build_rows(entries: dict[str, dict], recorder: PinRecorder, listed_modules: set[str], image_files: dict[str, list[str]]) -> list[Row]:
	"""One row per resource of the map, in map order, then one per patched resource the map does not name. `listed_modules` are the
	lower-case module names the families give a stock hash for; `image_files` maps a lower-case file name to its paths on the disk."""
	rows: list[Row] = []
	seen: set[tuple[str, str, int]] = set()
	by_icon: dict[str, list[dict]] = {icon_id: [] for icon_id in entries}
	for icon_id, resource in map_resources(entries):
		by_icon[icon_id].append(resource)
	for icon_id, resources in by_icon.items():
		if not resources:
			detail = UNMAPPED_REASONS.get(icon_id, "the map names no verified ReactOS resource for this icon")
			rows.append(Row(icon_id, "-", "-", "-", UNVERIFIED, (), detail))
			continue
		for resource in resources:
			key = _key(resource)
			if key is None:
				rows.append(Row(icon_id, resource.get("module", "-"), "-", "-", UNVERIFIED, (), "the map names no group or cell"))
				continue
			seen.add(key)
			module, kind, number = key
			evidence = "+".join(resource.get("evidence") or []) or "-"
			target = f"{kind} {number}"
			if key in recorder.patched and recorder.patched[key][0] == icon_id:
				if any(path in recorder.created for path in recorder.patched[key][1]):
					note = "a new file: the stock disk has none, so the patcher creates it with this group"
				else:
					note = "" if "binary" in evidence else "the map has source evidence only; the patcher checked the stock binary"
				rows.append(Row(icon_id, module, target, evidence, PATCHED, tuple(recorder.patched[key][1]), note))
			elif key in recorder.skipped:
				rows.append(Row(icon_id, module, target, evidence, SKIPPED, (), "; ".join(recorder.skipped[key])))
			elif module not in listed_modules and module not in BITMAP_MODULES and module != "shell32.dll":
				where = ", ".join(image_files.get(module, [])) or "not on the disk"
				rows.append(
					Row(icon_id, module, target, evidence, UNVERIFIED, (), f"no stock SHA-256 is recorded for the module ({where})")
				)
			else:
				rows.append(Row(icon_id, module, target, evidence, UNVERIFIED, (), "no patcher took this resource"))
	for key, (icon_id, paths) in sorted(recorder.patched.items()):
		if key not in seen:
			module, kind, number = key
			rows = [row for row in rows if not (row.icon_id == icon_id and row.target == "-")]  # the table gives the icon its resource
			note = "the map has no resource for this icon; this repository's table names it (verified from the source and the stock file)"
			rows.append(Row(icon_id, module, f"{kind} {number}", "table", PATCHED, tuple(paths), note))
	return rows


def counts(rows: list[Row]) -> dict[str, int]:
	return {status: sum(1 for row in rows if row.status == status) for status in (PATCHED, SKIPPED, UNVERIFIED)}


def render(rows: list[Row], compact: Profile) -> str:
	"""The report as markdown. `compact` is the trim profile of the compact image."""
	total = counts(rows)
	icons = {row.icon_id for row in rows}
	unmapped = sorted({row.icon_id for row in rows if row.target == "-"})
	lines = [
		"# Icon coverage",
		"",
		"Every resource Afterglow's `map.json` names, and what the icon patchers did with it. Generated by `rl pin` from the pinned map "
		"and the golden disk; `rl pin --check` fails when it is stale. See [icon-survey.md](icon-survey.md) for the method.",
		"",
		f"- **Resources:** {len(rows)} rows for {len(icons)} icons: {total[PATCHED]} patched, {total[SKIPPED]} skipped, "
		f"{total[UNVERIFIED]} unverified.",
		f"- **Icons with no ReactOS resource in the map:** {', '.join(f'`{icon}`' for icon in unmapped) or 'none'}.",
		"- **Compact:** the `base` trim removes the file, so the compact image leaves it alone and the full image carries the icon.",
		"",
		"| Icon | Module | Resource | Evidence | Status | Files | Compact | Note |",
		"|---|---|---|---|---|---|---|---|",
	]
	for row in rows:
		files = "<br>".join(f"`{path}`" for path in row.files) or "-"
		if row.files:
			removed = [path for path in row.files if removes(compact, path)]
			compact_text = "removed by trim" if removed else "kept"
		else:
			compact_text = "-"
		module = f"`{row.module}`" if row.module != "-" else "-"
		lines.append(
			f"| `{row.icon_id}` | {module} | {row.target} | {row.evidence} | {row.status} | {files} | {compact_text} | {row.detail} |"
		)
	return "\n".join(lines) + "\n"


def image_files_by_name(paths: list[str], modules: set[str]) -> dict[str, list[str]]:
	"""The paths on the disk of the files named in `modules`, by lower-case file name."""
	found: dict[str, list[str]] = {}
	for path in sorted(paths):
		name = path.rsplit("/", 1)[-1].lower()
		if name in modules:
			found.setdefault(name, []).append(path)
	return found


def report_is_current(text: str, path: Path = REPORT_FILE) -> bool:
	return path.is_file() and path.read_text() == text
