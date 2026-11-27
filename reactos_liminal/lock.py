# The lock file and `rl verify`: a record of every input a recipe resolves to, with its SHA-256, and a re-check of every pin against
# what is in the work directory and against that record.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# The lock holds only what the recipe resolves to, so it is the same on every machine: no time, no path outside the repository and no
# hash of something a build makes. Editing a pin without running `rl lock` is drift, and so is a cached download that no longer
# matches its pin.
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .fetch import sha256_file
from .install import golden_key, golden_path, render_unattend
from .recipe import Recipe, is_reg_path
from .trim import PROFILES_DIR

LOCK_SCHEMA = 1
REQUIRABLE = ("iso-zip", "iso", "afterglow-tar", "msstyles")


class LockError(Exception):
	"""A lock file that cannot be read, or an input that is not what the recipe pins."""


@dataclass(frozen=True)
class Check:
	name: str
	status: str  # "ok", "drift" (a hash or lock entry that differs) or "absent" (nothing to check yet)
	detail: str

	def line(self) -> str:
		return f"{self.status:<6} {self.name}: {self.detail}"


def lock_path(recipe: Recipe) -> Path:
	"""The lock file beside the recipe that was loaded: `afterglow.toml` is locked by `afterglow.lock.json`."""
	top = recipe.chain[0]
	return top.with_name(top.stem + ".lock.json")


def _relative(path: Path, base: Path) -> str:
	return Path(os.path.relpath(path, base)).as_posix()


def _text_sum(text: str) -> str:
	return hashlib.sha256(text.encode()).hexdigest()


def build_lock(recipe: Recipe) -> dict:
	"""The lock document: the pinned inputs as the recipe resolves them, plus the sums of the local files that shape a build."""
	base = recipe.chain[0].parent
	inputs: dict = {"reactos_iso": dict(recipe.section("inputs", "reactos_iso"))}
	if "afterglow" in recipe.data["inputs"]:
		inputs["afterglow"] = dict(recipe.section("inputs", "afterglow"))
	profile_name = recipe.section("trim", "profile")
	trim_lists: dict[str, str] = {}
	profile_file = PROFILES_DIR / f"{profile_name}.txt"
	if profile_file.is_file():
		trim_lists[f"profile:{profile_name}"] = sha256_file(profile_file)
	for extra in recipe.section("trim", "extra"):
		trim_lists[f"extra:{extra}"] = sha256_file(base / extra)
	reg_files = {
		f"reg:{os.path.relpath(entry, base).replace(os.sep, '/')}": sha256_file(Path(entry))
		for entry in recipe.section("settings", "reg_files")
		if is_reg_path(entry)
	}
	files = {entry["source"]: sha256_file(base / entry["source"]) for entry in recipe.data["files"] if (base / entry["source"]).is_file()}
	return {
		"schema": LOCK_SCHEMA,
		"recipe": recipe.name,
		"inputs": inputs,
		"answers_sha256": _text_sum(render_unattend(recipe)),
		"trim_lists": trim_lists,
		"files": files,
		**({"reg_files": reg_files} if reg_files else {}),
	}


def write_lock(recipe: Recipe, path: Path | None = None) -> Path:
	path = path or lock_path(recipe)
	path.write_text(json.dumps(build_lock(recipe), indent="\t") + "\n")
	return path


def _differences(expected: object, actual: object, where: str = "") -> list[str]:
	"""Every key at which two lock documents differ, named by its dotted path."""
	if isinstance(expected, dict) and isinstance(actual, dict):
		found: list[str] = []
		for key in sorted(set(expected) | set(actual)):
			child = f"{where}.{key}" if where else str(key)
			if key not in actual:
				found.append(f"{child} is in the recipe but not in the lock")
			elif key not in expected:
				found.append(f"{child} is in the lock but not in the recipe")
			else:
				found += _differences(expected[key], actual[key], child)
		return found
	if expected != actual:
		return [f"{where}: the recipe says {expected!r}, the lock says {actual!r}"]
	return []


def check_lock(recipe: Recipe, path: Path | None = None) -> list[Check]:
	"""Compare the lock file with what the recipe resolves to now."""
	path = path or lock_path(recipe)
	if not path.is_file():
		return [Check("lock", "drift", f"{path.name} does not exist; run `rl lock` to write it")]
	try:
		recorded = json.loads(path.read_text())
	except json.JSONDecodeError as error:
		return [Check("lock", "drift", f"{path.name} is not valid JSON ({error}); run `rl lock` to write it again")]
	if recorded.get("schema") != LOCK_SCHEMA:
		return [Check("lock", "drift", f"{path.name} has schema {recorded.get('schema')!r}, expected {LOCK_SCHEMA}; run `rl lock`")]
	differences = _differences(build_lock(recipe), recorded)
	if differences:
		return [Check("lock", "drift", f"{path.name}: {difference}; run `rl lock` if the change is meant") for difference in differences]
	return [Check("lock", "ok", f"{path.name} matches the recipe")]


def _check_file(name: str, path: Path, expected: str) -> Check:
	if not path.is_file():
		return Check(name, "absent", f"{path} is not there yet")
	actual = sha256_file(path)
	if actual != expected:
		return Check(name, "drift", f"{path} is {actual}, the pin is {expected}")
	return Check(name, "ok", f"{path.name} is {expected}")


def verify(recipe: Recipe, work: Path, lock_file: Path | None = None, check_lock_file: bool = True) -> list[Check]:
	"""Re-check every input pin against the files in the work directory, then the lock file against the recipe. A file that is not
	there yet is `absent`, not drift: a build has not fetched it. Nothing is downloaded and nothing is written."""
	checks: list[Check] = []
	iso = recipe.section("inputs", "reactos_iso")
	downloads = work / "dl"
	checks.append(_check_file("iso-zip", downloads / (iso["name"] + ".zip"), iso["zip_sha256"]))
	checks.append(_check_file("iso", downloads / iso["name"], iso["sha256"]))
	if "afterglow" in recipe.data["inputs"]:
		afterglow = recipe.section("inputs", "afterglow")
		checks.append(_check_file("afterglow-tar", work / "afterglow" / f"{afterglow['commit']}.tar", afterglow["tar_sha256"]))
		checks.append(_check_file("msstyles", work / "afterglow-files" / "afterglow.msstyles", afterglow["msstyles_sha256"]))
	if check_lock_file:
		checks += check_lock(recipe, lock_file)
	return checks


def failures(checks: list[Check], require: tuple[str, ...] = ()) -> list[Check]:
	"""The checks that fail a run: every drift, and any `absent` input the caller requires."""
	return [check for check in checks if check.status == "drift" or (check.status == "absent" and check.name in require)]


def cache_keys(recipe: Recipe, work: Path) -> dict[str, str]:
	"""The facts a CI cache is keyed on and stored at, as `name=value` pairs: the ISO's SHA-256 and path, the Afterglow commit, tar sum and
	folder, and the golden disk's key and path. A cache restores into the same paths, and `rl fetch` and `rl verify` check what it
	restored against the pins."""
	iso = recipe.section("inputs", "reactos_iso")
	keys = {
		"iso_sha256": iso["sha256"],
		"iso_path": str(work / "dl" / iso["name"]),
		"golden_key": golden_key(recipe),
		"golden_path": str(golden_path(recipe, work)),
	}
	if "afterglow" in recipe.data["inputs"]:
		afterglow = recipe.section("inputs", "afterglow")
		keys["afterglow_commit"] = afterglow["commit"]
		keys["afterglow_tar_sha256"] = afterglow["tar_sha256"]
		keys["afterglow_path"] = str(work / "afterglow")
	return keys
