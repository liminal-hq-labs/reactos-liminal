# `rl pin`: move the Afterglow pin and refresh every hash that depends on it.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Afterglow is a pinned input, and a good deal of what the pipeline checks follows from the pin: the sum of the source tar, of the
built visual style and of the wallpaper (in the recipe), and the sum each icon patcher's result must have (in `pins/`). The icon
patchers read the icon list from Afterglow's `map.json`, so a new icon set needs no code change: bump the pin, run `rl pin`.

    rl pin RECIPE                       measure the pin the recipe already names and rewrite any hash that is stale
    rl pin RECIPE --afterglow REF       first move the pin to REF: a commit, a tag or a branch of the recipe's repository
    rl pin RECIPE --check               change nothing; exit 1 if any hash is stale

The new sums are measured, not trusted: the source is fetched at the commit, the style and the wallpaper are built, and the icon
patchers run against the golden disk in a recording mode that keeps each result instead of comparing it. The finished pins are then
checked by running every patcher the recipe lists, so a stale constant in the logon, Start or boot patcher (art Afterglow changed)
is reported here, not at the end of a long image build.
"""

import json
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path

from .afterglow import fetch_afterglow, prepare_afterglow, tree_tar_sha256
from .install import golden_path
from .log import log
from .mtools import FatImage
from .patch_base import PatchError, recording
from .patch_bitmaps import PINS_FILE as FAMILY_PINS_FILE
from .patch_icons import PINS_FILE as SHELL32_PINS_FILE
from .patchers import run_patchers
from .paths import ensure
from .recipe import Recipe, load
from .rustbuild import build_program, declaring_file
from .wallpaper import render_wallpaper, wanted

ICON_PATCHERS = ("afterglow.icons", "afterglow.cpl-icons", "afterglow.program-icons", "afterglow.toolbar-bitmaps")
SECTION = "[inputs.afterglow]"
HEX40 = re.compile(r"^[0-9a-f]{40}$")


class PinError(Exception):
	"""The pin could not be moved or its hashes could not be measured."""


def resolve_ref(repo: str, ref: str) -> str:
	"""The commit a ref names in `repo` on GitHub: a 40-digit commit as given, otherwise a tag (annotated tags are peeled), a branch or
	`HEAD`, found with `git ls-remote`."""
	if HEX40.match(ref):
		return ref
	done = subprocess.run(
		["git", "ls-remote", f"https://github.com/{repo}.git", ref, f"{ref}^{{}}", f"refs/heads/{ref}", f"refs/tags/{ref}^{{}}"],
		capture_output=True,
		text=True,
		check=False,
	)
	if done.returncode != 0:
		raise PinError(f"cannot look up {ref!r} in {repo}: {done.stderr.strip()[-300:]}")
	found: dict[str, str] = {}
	for line in done.stdout.splitlines():
		commit, name = line.split("\t")
		found[name] = commit
	for name in (f"refs/tags/{ref}^{{}}", f"{ref}^{{}}", f"refs/heads/{ref}", f"refs/tags/{ref}", ref):
		if name in found:
			return found[name]
	raise PinError(f"{repo} has no tag, branch or commit {ref!r}")


def pin_file(recipe: Recipe) -> Path:
	"""The recipe file in the chain that declares `inputs.afterglow`, the nearest one: that is where the pin lives."""
	for path in recipe.chain:
		if "afterglow" in tomllib.loads(path.read_text()).get("inputs", {}):
			return path
	raise PinError("no recipe in the chain has an [inputs.afterglow] table")


def set_pins(text: str, values: dict[str, str | None], section: str = SECTION) -> str:
	"""`text` with the keys of the `section` table (`[inputs.afterglow]` by default)
	set to `values`. A key that has a value must already be in the table (so a
	comment above it stays with it); a value of None removes the key. Nothing else in the file is touched."""
	lines = text.split("\n")
	try:
		start = lines.index(section)
	except ValueError as error:
		raise PinError(f"{section} is not in the recipe file") from error
	end = next((index for index in range(start + 1, len(lines)) if lines[index].startswith("[")), len(lines))
	for key, value in values.items():
		pattern = re.compile(rf'^{re.escape(key)}\s*=\s*".*"\s*$')
		found = [index for index in range(start + 1, end) if pattern.match(lines[index])]
		if not found:
			if value is None:
				continue
			raise PinError(f"{section} has no `{key}` line to update")
		if value is None:
			del lines[found[0]]
			end -= 1
		else:
			lines[found[0]] = f'{key} = "{value}"'
	return "\n".join(lines)


def write_json(path: Path, document: dict) -> None:
	path.write_text(json.dumps(document, indent="\t", ensure_ascii=False) + "\n")


def merged_icon_pins(recorded: dict[str, dict[str, dict[str, str]]]) -> tuple[dict, dict]:
	"""The shell32 pin file and the families pin file with the recorded results in place of the old ones. A section that was recorded
	keeps only its new icon set (a pin for an icon set that is no longer in use is dead weight); a section that was not recorded is
	left alone."""
	shell32 = json.loads(SHELL32_PINS_FILE.read_text())
	families = json.loads(FAMILY_PINS_FILE.read_text())
	if "shell32" in recorded:
		shell32["results"] = {digest: files["ReactOS/system32/shell32.dll"] for digest, files in recorded["shell32"].items()}
	for name, by_digest in recorded.items():
		if name != "shell32":
			families["families"][name] = by_digest
	return shell32, families


def pin_afterglow(
	recipe_path: str | Path,
	work: Path,
	ref: str | None = None,
	pre_merge: str | None = None,
	golden: Path | None = None,
	tarball: Path | None = None,
	check: bool = False,
) -> list[str]:
	"""Move the pin to `ref` if given, measure every hash that follows from it and rewrite the stale ones. Returns a line for each
	change; with `check` nothing is written and the lines say what would change. `pre_merge` records a note beside a pin that is on an
	unmerged branch (None removes the note, which is right once the pin is a merged commit or a tag)."""
	recipe = load(recipe_path)
	pin = recipe.section("inputs", "afterglow")
	commit = resolve_ref(pin["repo"], ref) if ref else pin["commit"]
	if ref:
		log("pin", f"{ref} is {commit}")
	trial = load(recipe_path)
	trial.data["inputs"]["afterglow"]["commit"] = commit
	golden = golden or golden_path(recipe, work)
	if not golden.is_file():
		raise PinError(f"no golden disk at {golden}; run `rl install` first (the icon results are measured against its stock files)")

	measured: dict[str, str] = {"commit": commit}
	tree = fetch_afterglow(trial, work, tarball, trust=True)
	measured["tar_sha256"] = tree_tar_sha256(tree)
	prepare_afterglow(trial, work, tree, measured)
	if wanted(trial):
		with tempfile.TemporaryDirectory(dir=ensure(work, "scratch")) as scratch_name:
			render_wallpaper(trial, tree, Path(scratch_name), measured)

	with recording() as recorder, tempfile.TemporaryDirectory(dir=ensure(work, "scratch")) as scratch_name:
		run_patchers(list(ICON_PATCHERS), FatImage(golden), tree, work / "afterglow-files", Path(scratch_name))
	shell32_pins, family_pins = merged_icon_pins(recorder.results)

	changes = [f"{key}: {pin.get(key)} -> {value}" for key, value in measured.items() if pin.get(key) != value]
	built_sums: dict[str, str] = {}
	for name, table in recipe.data.get("builds", {}).items():
		sums: dict[str, str] = {}
		build_program(recipe, work, name, sums)
		built_sums[name] = sums["sha256"]
		if table["sha256"] != sums["sha256"]:
			changes.append(f"builds.{name}.sha256: {table['sha256']} -> {sums['sha256']}")
	wanted_note = pre_merge if ref else pin.get("pre_merge")
	if wanted_note != pin.get("pre_merge"):
		changes.append(f"pre_merge: {pin.get('pre_merge')} -> {wanted_note}")
	for path, document in ((SHELL32_PINS_FILE, shell32_pins), (FAMILY_PINS_FILE, family_pins)):
		if json.loads(path.read_text()) != document:
			changes.append(f"{path.name}: icon results refreshed")
	if check:
		return changes

	file = pin_file(recipe)
	values: dict[str, str | None] = dict(measured)
	if "pre_merge" in pin or wanted_note:
		values["pre_merge"] = wanted_note
	text = file.read_text()
	if wanted_note and "pre_merge" not in pin:
		text = text.replace(f'commit = "{pin["commit"]}"\n', f'commit = "{pin["commit"]}"\npre_merge = "{wanted_note}"\n', 1)
	file.write_text(set_pins(text, values))
	for name, digest in built_sums.items():
		build_file = declaring_file(recipe, name)
		build_file.write_text(set_pins(build_file.read_text(), {"sha256": digest}, f"[builds.{name}]"))
	write_json(SHELL32_PINS_FILE, shell32_pins)
	write_json(FAMILY_PINS_FILE, family_pins)

	# The finished pins, end to end: every patcher the recipe lists, with nothing recorded this time.
	verified = load(recipe_path)
	with tempfile.TemporaryDirectory(dir=ensure(work, "scratch")) as scratch_name:
		try:
			run_patchers(verified.section("patchers", "list"), FatImage(golden), tree, work / "afterglow-files", Path(scratch_name))
		except PatchError as error:
			raise PinError(
				f"the pin and the icon results are updated, but a patcher still refuses: {error}. A patcher that pins its own result in "
				"code (logon, Start, boot) needs that constant moved by hand for the new art."
			) from error
	return changes
