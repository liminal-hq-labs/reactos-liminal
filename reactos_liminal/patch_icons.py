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

Art comes from Afterglow: its `desktop/icons/render.py` renders the .ico files from the vector masters (the hand-tuned 16 px frames
come with them) and each .ico is checked against Afterglow's own SHA256SUMS. Its map.json says which groups to replace
(`icon_map.py`); this repository's table adds only the stock file's sum and the few groups the map does not name. The patched DLL is
checked against the sum pinned in `pins/shell32-icons.json`, keyed by a digest of the icon files used, so a changed icon set cannot go
through without `rl pin` recording its result. The result is ReactOS code (LGPL-2.1) and stays in the work directory, never in git.
"""

import hashlib
import json
import subprocess
from pathlib import Path

from .fetch import sha256_file
from .icon_map import load_map, module_groups, require_icon
from .icon_survey import load_table
from .log import log
from .mtools import FatImage
from .patch_base import PatchedFile, PatchError, active_recorder
from .pe_resources import RT_GROUP_ICON, RT_ICON, GroupFrame, PeError, PeFile, build_group, parse_group, read_ico

SHELL32 = "ReactOS/system32/shell32.dll"
SECTION_NAME = b".agico"
SECTION_FLAGS = 0x40000040  # initialized data, readable
PINS_FILE = Path(__file__).resolve().parent.parent / "pins" / "shell32-icons.json"
SIZES = (48, 32, 16)  # the sizes ReactOS asks for; never 24
FIT_PREFERENCE = (32, 16, 48)  # the sizes a fitted group adds when it has an id to spare, in order


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


def verified_icons(source_tree: Path, scratch: Path, icon_ids: set[str]) -> tuple[dict[str, bytes], dict[str, str]]:
	"""Render Afterglow's icon set (once per build) and return the .ico bytes of the named icons by id, and their sums by file name.
	Each file is checked against the sum Afterglow records, so a renderer or toolchain that differs is caught here."""
	render_dir = scratch / "icons"
	render_icons(source_tree, render_dir)
	recorded = _afterglow_sums(source_tree)
	icons: dict[str, bytes] = {}
	sums: dict[str, str] = {}
	for icon_id in sorted(icon_ids):
		name = f"ico/{icon_id}.ico"
		path = render_dir / name
		if not path.is_file():
			raise PatchError(f"Afterglow's render.py did not write {name}")
		sha = sha256_file(path)
		if sha != recorded.get(name):
			raise PatchError(f"{name} renders as {sha}, Afterglow records {recorded.get(name)}; the renderer or its tools differ")
		icons[icon_id] = path.read_bytes()
		sums[name] = sha
	return icons, sums


def settle_result(section: str, digest: str, name: str, result: str, expected: str | None, pins_file: str) -> None:
	"""Check a patched file against its pinned result, or, under `rl pin`, record it as the new pin."""
	recorder = active_recorder()
	if recorder is not None:
		recorder.record(section, digest, name, result)
	elif result != expected:
		raise PatchError(f"patched {name} is {result}, expected {expected} (icon set {digest} in {pins_file})")


def require_pin(digest: str, expected: object, what: str, pins_file: str) -> None:
	"""An icon set with no pinned result is refused, unless `rl pin` is collecting pins."""
	if expected is None and active_recorder() is None:
		raise PatchError(f"{what}: no pinned result for icon set {digest}; run `./rl pin` to record it in {pins_file}")


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


def fitted_sizes(stock_frames: list[GroupFrame]) -> list[int]:
	"""The sizes to write into a group with fewer frame ids than SIZES: the sizes the stock group holds (the dialog or code that loads
	it asks for those), then, while the group owns an id to spare, the sizes it lacks, nearest below first (32, 16, then 48). Frames
	of a size the stock group holds twice (a 32 px 8-bit and 32-bit pair) share one new frame, which frees the other's id for that."""
	held = {frame.width for frame in stock_frames if frame.width in SIZES}
	sizes = [size for size in SIZES if size in held]
	for extra in FIT_PREFERENCE:
		if len(sizes) < len(stock_frames) and extra not in sizes:
			sizes.append(extra)
	return sorted(sizes, reverse=True)


def patch_icon_groups(stock: bytes, icons: dict[int, bytes]) -> tuple[bytes, list[str]]:
	"""Replace the icon groups in a PE file (shell32.dll, a .cpl, a program). `icons` maps a group id to the bytes of its .ico file.
	Returns the new file and a line per group. A group with three or more frame ids of its own gets the three sizes 48, 32 and 16. A
	group with fewer (one or two frames, such as a 32 px applet icon) is fitted: it keeps the sizes the stock group holds, and takes
	a spare id for the next size down when it has one; no resource is added, so the directory never grows. Raises PatchError when a
	group is missing, owns no frame id, or the icon has a frame that is not 32-bit."""
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
			new: dict[int, bytes] = {}
			for width, height, bit_count, image in read_ico(icons[group_id]):
				if width != height or width not in SIZES or bit_count != 32 or width in new:
					raise PatchError(
						f"the icon for group {group_id} has a {width}x{height} {bit_count}-bit frame; expected 48, 32 and 16 px, 32-bit"
					)
				new[width] = image
			if not stock_frames:
				raise PatchError(f"group {group_id} has no frame ids of its own to write")
			fitted = len(available) < len(SIZES)
			sizes = fitted_sizes(stock_frames) if fitted else SIZES
			if any(size not in new for size in sizes):
				raise PatchError(f"the icon for group {group_id} lacks one of the sizes {', '.join(str(size) for size in sizes)}")
			# Give each new frame a stock frame id of the same size and depth where there is one, then any other unused id.
			unused = list(stock_frames)
			frames_out: list[GroupFrame] = []
			for size in sizes:
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
			mode = f", fitted to {'+'.join(str(size) for size in sizes)} px" if fitted else ""
			ids = [frame.icon_id for frame in frames_out]
			report.append(f"group {group_id}: {len(stock_frames)} stock frames -> {len(frames_out)} (ids {ids}){mode}")
		new_rva = pe.append_section(SECTION_NAME, bytes(content), SECTION_FLAGS)
		for entries, offset, size in edits:
			for entry in entries:
				pe.point_entry_at(entry, new_rva + offset, size)
		pe.update_checksum()
		return pe.to_bytes(), report
	except PeError as error:
		raise PatchError(f"the file cannot be patched: {error}") from error


def shell32_groups(entries: dict[str, dict], table: dict) -> dict[int, str]:
	"""The shell32.dll groups to replace, as `{group: Afterglow icon id}`: every group Afterglow's map verifies, plus the rows of the
	table that name an icon for a group the map does not (a theme-compatibility alias, say). Where the map names a group it decides."""
	groups = module_groups(entries, "shell32.dll")
	for row in table["groups"]:
		icon_id = row.get("afterglow")
		if icon_id is None or row["group"] in groups:
			continue
		require_icon(entries, icon_id, f"shell32 group {row['group']}")
		groups[row["group"]] = icon_id
	return groups


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
	groups = shell32_groups(load_map(source_tree), table)
	icons_by_id, icon_sums = verified_icons(source_tree, scratch, set(groups.values()))
	digest = icon_set_digest(icon_sums)
	expected = pins["results"].get(digest)
	require_pin(digest, expected, "shell32.dll", PINS_FILE.name)
	patched_bytes, report = patch_icon_groups(stock_file.read_bytes(), {group: icons_by_id[icon_id] for group, icon_id in groups.items()})
	patched = scratch / "shell32-afterglow.dll"
	patched.write_bytes(patched_bytes)
	result = sha256_file(patched)
	try:
		settle_result("shell32", digest, SHELL32, result, expected, PINS_FILE.name)
	except PatchError:
		patched.unlink(missing_ok=True)
		raise
	for line in report:
		log("patch", f"   {line}")
	log("patch", f"   afterglow.icons: shell32.dll patched, {len(groups)} groups ({result})")
	return [PatchedFile(SHELL32, patched)]
