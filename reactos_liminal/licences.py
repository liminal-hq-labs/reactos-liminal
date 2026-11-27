# Licence and attribution files for the image: `LICENSES/`, `NOTICE.txt` and `CHANGES.txt`, written into the disk by `rl image`, and the
# human-readable licences page made by `rl licences`. All of it is generated from the recipe and from the run.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# The official ReactOS ISO carries no licence texts (only `readme.txt` and a wallpaper credits file), so the texts held in `licences/`
# are the well-known SPDX ones, each with its source and SHA-256 in `licences/README.md`. The Apache-2.0 and MIT texts are this
# repository's own licence files, which cover Afterglow's art and these tools.
from dataclasses import dataclass, field
from pathlib import Path

from .fetch import sha256_file
from .mtools import FatImage
from .paths import REPO
from .recipe import Recipe, is_reg_path
from .trim import TrimReport

PRODUCT = "Afterglow for ReactOS — unofficial remaster by Liminal HQ Labs"
PROJECT_URL = "https://github.com/liminal-hq-labs/reactos-liminal"
ISSUES_URL = PROJECT_URL + "/issues"
REACTOS_SOURCE_URL = "https://github.com/reactos/reactos"
REACTOS_TAG = "0.4.16-release"
REACTOS_COMMIT = "822e8647792a2c43f033e3e00ed273d59f163c7b"
WINEVDM_URL = "https://github.com/otya128/winevdm"
AFTERGLOW_URL = "https://github.com/liminal-hq/afterglow-themes"
SAVERS_URL = "https://github.com/liminal-hq-labs/afterglow-savers"

LICENCES_DIR = REPO / "licences"
IMAGE_LICENCE_FOLDER = "LICENSES"
IMAGE_NOTICE = "NOTICE.txt"
IMAGE_CHANGES = "CHANGES.txt"


class LicenceError(Exception):
	"""A licence text that is missing or does not match its recorded SHA-256."""


@dataclass(frozen=True)
class LicenceText:
	spdx: str
	title: str
	source: Path
	image_name: str  # the file name inside `LICENSES/` on the image
	sha256: str | None  # the recorded sum of a text held in `licences/`; the repository's own licence files are not pinned here
	provenance: str


TEXTS = (
	LicenceText(
		"GPL-2.0-only",
		"GNU General Public License, version 2",
		LICENCES_DIR / "GPL-2.0-only.txt",
		"GPL-2.0.txt",
		"aaf135472f81c5b4a0dca9367e5bb5e9750032b5bebe5442b36e4c0a47430df3",
		"SPDX licence list data, text/GPL-2.0-only.txt (the FSF's text)",
	),
	LicenceText(
		"LGPL-2.1-only",
		"GNU Lesser General Public License, version 2.1",
		LICENCES_DIR / "LGPL-2.1-only.txt",
		"LGPL-2.1.txt",
		"5749785c8bdefafcb5d798270ed0a967036fe2ca63dcedade1627565dfef81d2",
		"SPDX licence list data, text/LGPL-2.1-only.txt (the FSF's text)",
	),
	LicenceText(
		"Apache-2.0",
		"Apache License, version 2.0",
		REPO / "LICENSE-APACHE",
		"Apache-2.0.txt",
		None,
		"this repository's LICENSE-APACHE",
	),
	LicenceText("MIT", "MIT licence", REPO / "LICENSE-MIT", "MIT.txt", None, "this repository's LICENSE-MIT"),
)


@dataclass(frozen=True)
class Component:
	name: str
	licence: str
	text: str  # the file in `LICENSES/` that holds the text, or a note where this build does not carry one
	where: str  # where the component is on the image
	trimmed_by_base: bool = False  # a trim profile (`base`) removes it, so the notice names it only for an untrimmed image
	replaced_wallpapers: bool = False  # a recipe with `wallpapers.replace_stock` removes it too, and its credits files go with it
	needs_build: str = ""  # the `[builds]` name a recipe must declare for the component to be on its image


COMPONENTS = (
	Component(
		"ReactOS kernel, drivers and most of user mode",
		"GPL-2.0-or-later, with the ReactOS runtime linking exception stated in the source's COPYING",
		"GPL-2.0.txt",
		"the whole system",
	),
	Component(
		"Wine-derived DLLs (parts of user32, uxtheme, comctl32, shell32 and others)",
		"LGPL-2.1-or-later",
		"LGPL-2.1.txt",
		"ReactOS\\system32",
	),
	Component(
		"Third-party code listed in ReactOS's `media/doc/3rd Party Files.txt` (zlib, libpng, FreeType, mbed TLS, ACPICA and others)",
		"their own licences, including GPL-3.0-or-later, GPL-2.0, Apache-2.0, MIT and BSD-style licences",
		"named in the ReactOS source tree; texts are in the corresponding source",
		"ReactOS\\system32",
	),
	Component("WineVDM (otvdm)", "GPL-2.0", "Program Files\\otvdm\\LICENSE", "Program Files\\otvdm"),
	Component(
		"Fonts (Liberation, Croscore, DejaVu-derived, ReactOS clones and others in `media/fonts/`)",
		"OFL-1.1, GPL with the font exception and others, per the ReactOS source's `media/fonts/doc/`",
		"named in the ReactOS source tree; texts are in the corresponding source",
		"ReactOS\\Fonts",
	),
	Component(
		"Wallpapers shipped with ReactOS",
		"CC-BY-NC-3.0 (Backwoods, Borealis, Deep Sea; Angelus is NC-SA), CC0-1.0, CC-BY-SA-4.0, CC-BY-1.0 and CC-BY-4.0, as each wallpaper's credits file says",
		"credits files beside the wallpapers",
		"ReactOS\\Web\\Wallpaper",
		trimmed_by_base=True,
		replaced_wallpapers=True,
	),
	Component(
		"Wine Gecko (the browser engine)",
		"MPL-2.0 and the licences inside it",
		"shipped with Gecko",
		"ReactOS\\system32\\gecko",
		trimmed_by_base=True,
	),
	Component(
		"Afterglow desktop theme (style, pointers, wallpapers)",
		"Apache-2.0 OR MIT",
		"Apache-2.0.txt and MIT.txt",
		"ReactOS\\Resources\\Themes\\Afterglow; the wallpapers in ReactOS\\Web\\Wallpaper or ReactOS\\afterglow-wallpaper.bmp",
	),
	Component(
		"Afterglow screensavers (Maze, Cracktro, Twilight, Ink and Collection), built from source at a pinned commit",
		"Apache-2.0 OR MIT",
		"Apache-2.0.txt and MIT.txt",
		"ReactOS\\system32 (AGMAZE.SCR, AGCRACK.SCR, AGTWILIT.SCR, AGINK.SCR and AGCOLLCT.SCR)",
		needs_build="afterglow-savers",
	),
	Component(
		"ReactOS Liminal's own settings, shortcuts and scripts",
		"Apache-2.0 OR MIT",
		"Apache-2.0.txt and MIT.txt",
		"the settings and desktop",
	),
)


def licence_texts() -> dict[str, bytes]:
	"""The text of every licence this build carries, by its name inside `LICENSES/`. A text held in `licences/` is checked against its
	recorded sum, so a changed file stops the build."""
	found: dict[str, bytes] = {}
	for text in TEXTS:
		if not text.source.is_file():
			raise LicenceError(f"licence text missing: {text.source}")
		if text.sha256 and sha256_file(text.source) != text.sha256:
			raise LicenceError(f"{text.source} does not match its recorded SHA-256 {text.sha256}")
		found[text.image_name] = text.source.read_bytes()
	return found


def to_ascii(text: str) -> str:
	"""Text for a file on the disk. ReactOS's Notepad reads the ANSI code page, so the typographic marks used in the docs become plain
	ones, and anything else that is not ASCII is an error rather than a garbled character."""
	for mark, plain in (("—", "-"), ("–", "-"), ("’", "'"), ("“", '"'), ("”", '"'), ("™", "(TM)"), ("…", "...")):
		text = text.replace(mark, plain)
	try:
		text.encode("ascii")
	except UnicodeEncodeError as error:
		raise LicenceError(f"text for the disk has a character that is not ASCII: {text[error.start : error.end]!r}") from None
	return text


def _crlf(text: str) -> bytes:
	return to_ascii(text).replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii")


def source_offer_lines() -> list[str]:
	return [
		"ReactOS 0.4.16 is released under the GNU General Public License, and this system contains ReactOS's code. The complete corresponding source is",
		f"the ReactOS 0.4.16 source (tag {REACTOS_TAG}, commit {REACTOS_COMMIT}) at {REACTOS_SOURCE_URL}, together with the source of WineVDM",
		f"({WINEVDM_URL}) and of ReactOS Liminal (the recipe, the tools and the patches) at {PROJECT_URL}. Each release of this remaster attaches",
		"an archive of that source, with its SHA-256, to the release it belongs to.",
		"",
		f"If you received this system without that archive, ask for a copy at {ISSUES_URL}. The offer is valid for three years from the date",
		"you received this system, and for as long as ReactOS Liminal keeps the release available.",
	]


def _absent(recipe: Recipe, component: Component) -> bool:
	"""True when the component needs a build the recipe does not declare, so it is not on the image and no document names it."""
	return bool(component.needs_build) and component.needs_build not in recipe.data.get("builds", {})


def _removed(recipe: Recipe, component: Component) -> bool:
	"""True when the recipe takes the component off the image: the compact trim removes it, or `wallpapers.replace_stock` replaces
	ReactOS's wallpapers with Afterglow's."""
	trimmed = recipe.section("trim", "profile") != "none" and component.trimmed_by_base
	replaced = recipe.section("wallpapers", "replace_stock") and component.replaced_wallpapers
	return trimmed or replaced


def _removal_note(recipe: Recipe, component: Component) -> str:
	if recipe.section("trim", "profile") != "none" and component.trimmed_by_base:
		return f" (removed by the `{recipe.section('trim', 'profile')}` trim profile)"
	return " (replaced by Afterglow's wallpapers)"


def notice_text(recipe: Recipe) -> bytes:
	"""`NOTICE.txt` for the disk: what this is, that it is unofficial, the source offer, where the licences are, and the credits."""
	iso = recipe.section("inputs", "reactos_iso")
	lines = [
		PRODUCT,
		"",
		"This is an unofficial remaster of ReactOS 0.4.16, made by Liminal HQ Labs. It is not made, endorsed or supported by the ReactOS",
		"Project. ReactOS is a trademark of the ReactOS Project. Report problems with this remaster to Liminal HQ Labs, not to ReactOS.",
		"",
		"What it is: the official ReactOS 0.4.16 install CD (the sum of its ISO is " + iso["sha256"] + "),",
		"installed unattended, dressed with the Afterglow desktop theme and set up by the recipe '" + recipe.name + "'.",
		f"{IMAGE_CHANGES} lists what was changed.",
		"",
		"Licences",
		"--------",
		f"ReactOS and its parts keep their own licences. The texts are in the {IMAGE_LICENCE_FOLDER} folder on this disk:",
	]
	lines += [f"  {IMAGE_LICENCE_FOLDER}\\{text.image_name}  {text.title}" for text in TEXTS]
	lines += ["", "Components and their licences:"]
	for component in COMPONENTS:
		if not _removed(recipe, component) and not _absent(recipe, component):
			lines.append(f"  - {component.name}: {component.licence}")
	lines += ["", "Source code", "-----------", *source_offer_lines(), ""]
	lines += [
		"Credits",
		"-------",
		"ReactOS is the work of the ReactOS Team and its contributors; its CREDITS file in the source lists them.",
		"Much of its user mode comes from the Wine project and its contributors.",
		f"WineVDM (otvdm) is by otya128 and its contributors ({WINEVDM_URL}).",
		f"The Afterglow desktop theme is by Liminal HQ ({AFTERGLOW_URL}).",
		*([f"The Afterglow screensavers are by Liminal HQ ({SAVERS_URL})."] if "afterglow-savers" in recipe.data.get("builds", {}) else []),
		f"This remaster is built with ReactOS Liminal ({PROJECT_URL}).",
	]
	return _crlf("\n".join(lines) + "\n")


@dataclass(frozen=True)
class PatchChange:
	patcher: str
	image_path: str
	before_sha256: str
	after_sha256: str


@dataclass
class ChangeRecord:
	"""What a run changed, for `CHANGES.txt`: each patched file with its sums, and the trim's report."""

	patched: list[PatchChange] = field(default_factory=list)
	trim: TrimReport | None = None
	trim_profile: str = ""
	settings_applied: bool = False
	written_files: list[str] = field(default_factory=list)  # paths on the image written by the files step
	stock_wallpapers_removed: list[str] = field(default_factory=list)  # ReactOS's wallpapers a `wallpapers.replace_stock` recipe removed


def changes_text(recipe: Recipe, record: ChangeRecord) -> bytes:
	"""`CHANGES.txt` for the disk: what differs from the official ReactOS 0.4.16 install, from the recipe and from the run."""
	install = recipe.section("install")
	settings = recipe.section("settings")
	lines = [
		"CHANGES.txt - what was changed from the official ReactOS 0.4.16",
		"",
		f"Recipe: {recipe.name}. ReactOS Liminal builds this system from the official install CD; nothing else is added to ReactOS's own files.",
		"",
		"1. Install",
		"----------",
		"The install is unattended. The answers file sets:",
		f"  locale {install['locale']}, time zone index {install['time_zone_index']}, computer name {install['computer_name']}, "
		f"owner name {install['owner_name']}, classic shell {'on' if install['classic_shell'] else 'off'}.",
		"The boot menu file freeldr.ini on the installed disk is set to start ReactOS by default with a three second delay.",
		"",
		"2. Patched files (same size, in place)",
		"--------------------------------------",
	]
	if record.patched:
		for change in record.patched:
			lines += [
				f"  {change.image_path}",
				f"    patcher: {change.patcher}",
				f"    before: {change.before_sha256}",
				f"    after:  {change.after_sha256}",
			]
	else:
		lines.append("  none")
	lines += ["", "3. Removed files (the trim)", "---------------------------", f"Profile: {record.trim_profile or 'none'}."]
	if record.trim is not None:
		for name, count in record.trim.sources[1:]:
			lines.append(f"Extra list {name}: {count} entries.")
		lines.append(f"Removed {len(record.trim.removed)} entries; {len(record.trim.missing)} were not on the disk.")
		for entry in record.trim.removed:
			lines.append(f"  {'folder' if entry.kind == 'd' else 'file  '} {entry.path}")
	else:
		lines.append("No trim was run.")
	if recipe.section("wallpapers", "replace_stock"):
		lines.append(
			f"ReactOS's own wallpapers, with their credits files, were replaced by Afterglow's: {len(record.stock_wallpapers_removed)} files "
			"removed from ReactOS\\Web\\Wallpaper."
		)
		lines += [f"  file   {path}" for path in record.stock_wallpapers_removed]
	lines += ["", "4. Added files", "--------------"]
	added = [*record.written_files]
	if added:
		lines += [f"  {path}" for path in added]
	else:
		lines.append("  none")
	lines += ["  LICENSES, NOTICE.txt and CHANGES.txt (this file)"]
	removed_shortcuts = settings["remove_desktop_shortcuts"]
	if removed_shortcuts:
		lines += ["", "Desktop shortcuts removed: " + ", ".join(removed_shortcuts) + "."]
	lines += ["", "5. Settings applied", "-------------------"]
	if record.settings_applied:
		lines += [
			f"  display mode {settings['display_width']} x {settings['display_height']}, page file {settings['page_file']} MB, "
			f"desktop icon size {settings['icon_size']}.",
			"  registry files: " + ", ".join(Path(name).name if is_reg_path(name) else name for name in settings["reg_files"]) + ".",
		]
		if settings.get("wallpaper"):
			lines.append(f"  wallpaper {settings['wallpaper']}.")
	else:
		lines.append("  not applied in this build.")
	return _crlf("\n".join(lines) + "\n")


def write_licence_files(disk: FatImage, recipe: Recipe, record: ChangeRecord, scratch: Path) -> list[str]:
	"""Write `LICENSES/`, `NOTICE.txt` and `CHANGES.txt` to the image. Returns the paths written, under the FAT32 root."""
	written: list[str] = []
	disk.make_directory(IMAGE_LICENCE_FOLDER)
	for name, data in sorted(licence_texts().items()):
		local = scratch / "licence.txt"
		local.write_bytes(data if b"\r\n" in data else data.replace(b"\n", b"\r\n"))
		disk.copy_in(local, f"{IMAGE_LICENCE_FOLDER}/{name}")
		written.append(f"{IMAGE_LICENCE_FOLDER}/{name}")
	for name, data in ((IMAGE_NOTICE, notice_text(recipe)), (IMAGE_CHANGES, changes_text(recipe, record))):
		local = scratch / "notice.txt"
		local.write_bytes(data)
		disk.copy_in(local, name)
		written.append(name)
	return written


def licences_page(recipe: Recipe) -> str:
	"""The licences page as Markdown, for the docs and the release. It says what each component is licensed under and where the texts,
	the source and the list of changes are, so it carries no run-specific sums; `CHANGES.txt` on the image has those."""
	iso = recipe.section("inputs", "reactos_iso")
	out = [
		"# Licences",
		"",
		f"{PRODUCT} is an unofficial remaster of ReactOS 0.4.16. It is not made, endorsed or supported by the ReactOS Project, and ReactOS is a trademark of the ReactOS Project. This page is generated by `rl licences`; the image carries the same facts in `NOTICE.txt`, `CHANGES.txt` and the `LICENSES` folder.",
		"",
		"## What the image is",
		"",
		f"- **Base:** the official ReactOS 0.4.16 install CD, `{iso['name']}`, SHA-256 `{iso['sha256']}`.",
		f"- **Recipe:** `{recipe.name}`, with trim profile `{recipe.section('trim', 'profile')}` and patchers {', '.join(f'`{name}`' for name in recipe.section('patchers', 'list')) or 'none'}.",
	]
	if "afterglow" in recipe.data["inputs"]:
		afterglow = recipe.section("inputs", "afterglow")
		out.append(f"- **Afterglow:** [`{afterglow['repo']}`](https://github.com/{afterglow['repo']}) at commit `{afterglow['commit']}`.")
	for name, table in recipe.data.get("builds", {}).items():
		if "repo" in table:
			out.append(
				f"- **{name}:** [`{table['repo']}`](https://github.com/{table['repo']}) at commit `{table['commit']}`, built from source."
			)
	out += ["", "## Components and licences", "", "| Component | Licence | Text | Where |", "|---|---|---|---|"]
	for component in COMPONENTS:
		if _absent(recipe, component):
			continue
		where = component.where + (_removal_note(recipe, component) if _removed(recipe, component) else "")
		out.append(f"| {component.name} | {component.licence} | {component.text} | {where} |")
	out += [
		"",
		f"Component licences are taken from ReactOS's own documentation and are confirmed file by file against the 0.4.16 source before each release; the licence checklist in [SPEC.md]({PROJECT_URL}/blob/main/SPEC.md#licence-checklist) records that step.",
		"",
		"## Licence texts",
		"",
		f"The `{IMAGE_LICENCE_FOLDER}` folder on the image holds these texts. The official ISO carries none, so they come from the SPDX licence list and this repository ([provenance]({PROJECT_URL}/blob/main/licences/README.md)).",
		"",
		"| File | Licence | SPDX |",
		"|---|---|---|",
	]
	out += [f"| `{text.image_name}` | {text.title} | `{text.spdx}` |" for text in TEXTS]
	out += [
		"",
		"## Source code",
		"",
		f"- **ReactOS 0.4.16:** tag `{REACTOS_TAG}` (commit `{REACTOS_COMMIT}`) of <{REACTOS_SOURCE_URL}>.",
		f"- **WineVDM (otvdm):** <{WINEVDM_URL}>, the release installed on the image.",
		f"- **ReactOS Liminal:** the recipe, the tools and the patches at <{PROJECT_URL}>, at the release's tag.",
		"- **Release archive:** each release attaches a corresponding-source archive with its SHA-256.",
		f"- **Written offer:** if you received the system without that archive, ask at <{ISSUES_URL}>; the offer is valid for three years from receipt and for as long as the release stays available.",
		"",
		"## What was changed",
		"",
		"`CHANGES.txt` on the image lists every patched file with its SHA-256 before and after, the trim profile and every removed path, the files added and the settings applied. The release's `build-manifest.json` records the same inputs and every output's hash.",
		"",
	]
	return "\n".join(out)
