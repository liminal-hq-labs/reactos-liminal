# The `afterglow.icons` patcher: replace the icon groups of a copy of ReactOS 0.4.16's shell32.dll with the Afterglow icon set.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""ReactOS draws every folder, drive, desktop item and the Recycle Bin from shell32.dll's own RT_GROUP_ICON resources, and the
Explorer registry hooks (`Shell Icons`, DefaultIcon) only reach some of them, so the DLL itself is patched. The new frames go into
one new section appended to the file; each replaced group's directory entry and its frames' data entries are pointed at the new
bytes. The resource directory itself never grows (nothing moves, so no other RVA changes): a group takes over frame ids the stock
group already owns, and a group that would need more frames than the stock one has ids for is refused. The stock frames stay in
`.rsrc`, unreferenced.

Art comes from Afterglow: its `desktop/icons/render.py` renders the .ico files from the vector masters (the scripted renders; the
hand-drawn 16 px redraws do not exist yet), each .ico is checked against Afterglow's own SHA256SUMS, and its map.json is checked
against this repository's table. The patched DLL is checked against the sum pinned in `pins/shell32-icons.json`, keyed by a digest
of the icon files used, so a changed icon set cannot go through without a new pin. The result is ReactOS code (LGPL-2.1) and stays
in the work directory, never in git.
"""

import hashlib
import json
import subprocess
from pathlib import Path

from .fetch import sha256_file
from .icon_survey import load_table
from .log import log
from .mtools import FatImage
from .patchers import PatchedFile, PatchError
from .pe_resources import RT_GROUP_ICON, RT_ICON, GroupFrame, PeError, PeFile, build_group, parse_group, read_ico

SHELL32 = "ReactOS/system32/shell32.dll"
SECTION_NAME = b".agico"
SECTION_FLAGS = 0x40000040  # initialized data, readable
PINS_FILE = Path(__file__).resolve().parent.parent / "pins" / "shell32-icons.json"
SIZES = (48, 32, 16)  # the sizes ReactOS asks for; never 24


def load_pins() -> dict:
	return json.loads(PINS_FILE.read_text())


def icon_set_digest(icon_sums: dict[str, str]) -> str:
	"""A digest of the .ico files the patcher uses: the SHA-256 of `name sha256` lines, sorted by name."""
	text = "".join(f"{name} {icon_sums[name]}\n" for name in sorted(icon_sums))
	return hashlib.sha256(text.encode()).hexdigest()


def _afterglow_sums(source_tree: Path) -> dict[str, str]:
	sums_file = source_tree / "desktop" / "icons" / "SHA256SUMS"
	if not sums_file.is_file():
		raise PatchError(f"{sums_file} is missing; the pinned Afterglow commit has no icon set")
	sums = {}
	for line in sums_file.read_text().splitlines():
		parts = line.split()
		if len(parts) == 2:
			sums[parts[1]] = parts[0]
	return sums


def _check_map(source_tree: Path, rows: list[dict]) -> None:
	"""Afterglow's map.json may name a group for an icon; where it does it must be the group in this repository's table."""
	map_file = source_tree / "desktop" / "icons" / "map.json"
	if not map_file.is_file():
		raise PatchError(f"{map_file} is missing; the pinned Afterglow commit has no icon map")
	entries = {entry["id"]: entry for entry in json.loads(map_file.read_text())["icons"]}
	for row in rows:
		entry = entries.get(row["afterglow"])
		if entry is None:
			raise PatchError(f"Afterglow's map.json has no icon {row['afterglow']!r} (shell32 group {row['group']})")
		resource = entry.get("resource")
		if resource is None:
			if row["tier"] == "core":
				raise PatchError(f"Afterglow's map.json no longer names a group for {row['afterglow']!r}; the table expects {row['group']}")
			continue
		if resource.get("module") != "shell32.dll" or resource.get("group") != row["group"]:
			raise PatchError(
				f"Afterglow's map.json puts {row['afterglow']!r} at {resource.get('module')} group {resource.get('group')}; "
				f"the table has shell32.dll group {row['group']}"
			)


def render_icons(source_tree: Path, destination: Path) -> None:
	"""Render Afterglow's icon set into `destination` once; a later patcher in the same build reuses it."""
	if (destination / "ico").is_dir():
		return
	tool = source_tree / "desktop" / "icons" / "render.py"
	if not tool.is_file():
		raise PatchError(f"{tool} is missing; the pinned Afterglow commit has no icon renderer")
	done = subprocess.run(["python3", "-I", str(tool), str(destination)], capture_output=True, text=True, check=False)
	if done.returncode != 0:
		raise PatchError(f"Afterglow's render.py failed: {(done.stderr or done.stdout).strip()[-400:]}")


def patch_icon_groups(stock: bytes, icons: dict[int, bytes]) -> tuple[bytes, list[str]]:
	"""Replace the icon groups in a PE file (shell32.dll, a .cpl, a program). `icons` maps a group id to the bytes of its .ico file.
	Returns the new file and a line
	per group. Raises PatchError when a group is missing, has too few frame ids, or a frame is not 32-bit."""
	try:
		pe = PeFile(stock)
		groups = pe.data_entries(RT_GROUP_ICON)
		frames_by_id = pe.data_entries(RT_ICON)
		users: dict[int, set[int]] = {}  # frame id -> the groups that list it; a frame shared with another group cannot be reused
		for other_id, other_entries in groups.items():
			for frame in parse_group(pe.entry_data(other_entries[0])):
				users.setdefault(frame.icon_id, set()).add(other_id)
		content = bytearray()
		edits: list[tuple[list[int], int, int]] = []  # (data entries, offset in the new section, size)
		report = []
		for group_id in sorted(icons):
			if group_id not in groups:
				raise PatchError(f"the file has no icon group {group_id}")
			stock_frames = [frame for frame in parse_group(pe.entry_data(groups[group_id][0])) if users[frame.icon_id] == {group_id}]
			available = [frame.icon_id for frame in stock_frames]
			for icon_id in available:
				if icon_id not in frames_by_id:
					raise PatchError(f"group {group_id} names icon {icon_id}, which shell32.dll does not hold")
			new = {size: None for size in SIZES}
			for width, height, bit_count, image in read_ico(icons[group_id]):
				if width != height or width not in new or bit_count != 32 or new[width] is not None:
					raise PatchError(
						f"the icon for group {group_id} has a {width}x{height} {bit_count}-bit frame; expected 48, 32 and 16 px, 32-bit"
					)
				new[width] = image
			if any(image is None for image in new.values()):
				raise PatchError(f"the icon for group {group_id} lacks one of the sizes 48, 32 and 16")
			if len(available) < len(SIZES):
				raise PatchError(
					f"group {group_id} has {len(available)} frame ids of its own and needs {len(SIZES)}; "
					"the resource directory is not grown, so it is refused"
				)
			# Give each new frame a stock frame id of the same size and depth where there is one, then any other unused id.
			unused = list(stock_frames)
			frames_out: list[GroupFrame] = []
			for size in SIZES:
				pick = next((frame for frame in unused if frame.width == size and frame.bit_count == 32), None)
				pick = pick or next((frame for frame in unused if frame.width == size), None) or unused[0]
				unused.remove(pick)
				image = new[size]
				while len(content) % 4:
					content.append(0)
				edits.append((frames_by_id[pick.icon_id], len(content), len(image)))
				content += image
				frames_out.append(GroupFrame(size, size, 0, 1, 32, len(image), pick.icon_id))
			group_bytes = build_group(frames_out)
			while len(content) % 4:
				content.append(0)
			edits.append((groups[group_id], len(content), len(group_bytes)))
			content += group_bytes
			report.append(
				f"group {group_id}: {len(stock_frames)} stock frames -> {len(SIZES)} (ids {[frame.icon_id for frame in frames_out]})"
			)
		new_rva = pe.append_section(SECTION_NAME, bytes(content), SECTION_FLAGS)
		for entries, offset, size in edits:
			for entry in entries:
				pe.point_entry_at(entry, new_rva + offset, size)
		pe.update_checksum()
		return pe.to_bytes(), report
	except PeError as error:
		raise PatchError(f"the file cannot be patched: {error}") from error


def afterglow_icons(golden: FatImage, source_tree: Path, files: Path, scratch: Path) -> list[PatchedFile]:
	"""Patch a copy of the guest's shell32.dll so Explorer, the desktop, the folders and the Recycle Bin draw the Afterglow icons."""
	table = load_table()
	pins = load_pins()
	stock_file = scratch / "shell32.dll"
	golden.copy_out(SHELL32, stock_file)
	actual = sha256_file(stock_file)
	if actual != table["stock_sha256"]:
		raise PatchError(
			f"{SHELL32} is not the stock shell32.dll of ReactOS 0.4.16 i386 (SHA-256 {actual}, expected {table['stock_sha256']}); "
			"the group and frame ids were checked against that one file only"
		)
	rows = [row for row in table["groups"] if row["apply"]]
	_check_map(source_tree, rows)
	render_dir = scratch / "icons"
	render_icons(source_tree, render_dir)
	afterglow_sums = _afterglow_sums(source_tree)
	icon_sums = {}
	icons = {}
	for row in rows:
		name = f"ico/{row['afterglow']}.ico"
		path = render_dir / name
		if not path.is_file():
			raise PatchError(f"Afterglow's render.py did not write {name}")
		sha = sha256_file(path)
		if sha != afterglow_sums.get(name):
			raise PatchError(f"{name} renders as {sha}, Afterglow records {afterglow_sums.get(name)}; the renderer or its tools differ")
		icon_sums[name] = sha
		icons[row["group"]] = path.read_bytes()
	digest = icon_set_digest(icon_sums)
	expected = pins["results"].get(digest)
	if expected is None:
		raise PatchError(f"no pinned result for icon set {digest}; patch, check the result and add it to {PINS_FILE.name}")
	patched_bytes, report = patch_icon_groups(stock_file.read_bytes(), icons)
	patched = scratch / "shell32-afterglow.dll"
	patched.write_bytes(patched_bytes)
	result = sha256_file(patched)
	if result != expected:
		patched.unlink(missing_ok=True)
		raise PatchError(f"patched shell32.dll is {result}, expected {expected}")
	for line in report:
		log("patch", f"   {line}")
	log("patch", f"   afterglow.icons: shell32.dll patched, {len(rows)} groups ({result})")
	return [PatchedFile(SHELL32, patched)]
