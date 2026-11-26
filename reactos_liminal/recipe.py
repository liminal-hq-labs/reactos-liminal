# The recipe: a TOML file that names every input with its pin, the install answers, the trim profile, the patchers and the outputs.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# A recipe chooses and parameterizes steps; it cannot add a new kind of write. `extends` layers one recipe on another: tables merge
# key by key, and any other value (a list, a string) in the extending recipe replaces the one it extends.
import copy
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import REPO

HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
NAME = re.compile(r"^[a-z][a-z0-9-]*$")

# The default size of one v86 disk part. v86 fetches a part per read, so a larger part means fewer requests and a better
# compression ratio at the cost of more bytes per cold read; the Quill demo measured 1 MiB, and 8 MiB is the starting point for the
# next measurement. A recipe sets it with `outputs.parts.chunk_size`.
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024
MIN_CHUNK_SIZE = 64 * 1024

PATCHERS = ("afterglow.pointers",)
TRIM_PROFILES = ("none", "demo", "base")


class RecipeError(Exception):
	"""A recipe that cannot be read or does not validate. The message names the key."""


def parse_size(value: Any, key: str) -> int:
	"""A byte count: an integer, or a string such as "8MiB", "512KiB", "4GiB"."""
	if isinstance(value, bool):
		raise RecipeError(f"{key}: expected a size, not a boolean")
	if isinstance(value, int):
		return value
	if isinstance(value, str):
		match = re.fullmatch(r"(\d+)\s*(B|KiB|MiB|GiB)?", value.strip())
		if match:
			units = {"B": 1, "KiB": 1 << 10, "MiB": 1 << 20, "GiB": 1 << 30, None: 1}
			return int(match.group(1)) * units[match.group(2)]
	raise RecipeError(f'{key}: expected a size such as 8388608 or "8MiB", got {value!r}')


def _sha256(value: Any, key: str) -> str:
	if not isinstance(value, str) or not HEX64.match(value):
		raise RecipeError(f"{key}: expected 64 lowercase hex digits (a SHA-256)")
	return value


def _commit(value: Any, key: str) -> str:
	if not isinstance(value, str) or not HEX40.match(value):
		raise RecipeError(f"{key}: expected a full 40-digit lowercase commit")
	return value


def _str(value: Any, key: str) -> str:
	if not isinstance(value, str) or not value:
		raise RecipeError(f"{key}: expected a non-empty string")
	return value


def _bool(value: Any, key: str) -> bool:
	if not isinstance(value, bool):
		raise RecipeError(f"{key}: expected true or false")
	return value


def _int(lowest: int, highest: int):
	def check(value: Any, key: str) -> int:
		if isinstance(value, bool) or not isinstance(value, int) or not lowest <= value <= highest:
			raise RecipeError(f"{key}: expected an integer from {lowest} to {highest}")
		return value

	return check


def _choice(*options: str):
	def check(value: Any, key: str) -> str:
		if value not in options:
			raise RecipeError(f"{key}: expected one of {', '.join(options)}; got {value!r}")
		return value

	return check


def _locale(value: Any, key: str) -> str:
	if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{4}", value):
		raise RecipeError(f'{key}: expected a four-digit hexadecimal locale id such as "0409"')
	return value.upper()


def _page_file(value: Any, key: str) -> str:
	if not isinstance(value, str) or not re.fullmatch(r"\d+ \d+", value):
		raise RecipeError(f'{key}: expected "INITIAL MAXIMUM" in megabytes, such as "64 64"')
	return value


def _name_list(allowed: tuple[str, ...] | None):
	def check(value: Any, key: str) -> list[str]:
		if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
			raise RecipeError(f"{key}: expected a list of strings")
		if allowed is not None:
			for item in value:
				if item not in allowed:
					raise RecipeError(f"{key}: unknown entry {item!r}; known: {', '.join(allowed)}")
		if len(set(value)) != len(value):
			raise RecipeError(f"{key}: duplicate entries")
		return value

	return check


def _str_list(value: Any, key: str) -> list[str]:
	return _name_list(None)(value, key)


def _recipe_name(value: Any, key: str) -> str:
	if not isinstance(value, str) or not NAME.match(value):
		raise RecipeError(f"{key}: expected a lowercase name of letters, digits and hyphens")
	return value


def _chunk(value: Any, key: str) -> int:
	byte_count = parse_size(value, key)
	if byte_count < MIN_CHUNK_SIZE or byte_count & (byte_count - 1):
		raise RecipeError(f"{key}: expected a power of two of at least 64 KiB; got {byte_count}")
	return byte_count


_REQ = object()

# section -> key -> (checker, default); a default of _REQ means the key is required when the section is present.
SCHEMA: dict[str, Any] = {
	"recipe": {
		"name": (_recipe_name, _REQ),
		"description": (_str, ""),
		"extends": (_str, None),
	},
	"inputs": {
		"reactos_iso": {
			"name": (_str, _REQ),
			"url": (_str, _REQ),
			"zip_sha256": (_sha256, _REQ),
			"sha256": (_sha256, _REQ),
		},
		"afterglow": {
			"repo": (_str, _REQ),
			"commit": (_commit, _REQ),
			"tar_sha256": (_sha256, _REQ),
			"msstyles_sha256": (_sha256, _REQ),
			"apply_reg": (_str, "desktop/install/afterglow-original.reg"),
		},
	},
	"install": {
		"locale": (_locale, "0409"),
		"time_zone_index": (_int(0, 999), 85),
		"computer_name": (_str, "REACTOS"),
		"owner_name": (_str, "ReactOS user"),
		"classic_shell": (_bool, True),
		"memory_mb": (_int(256, 4096), 768),
		"disk_size_mb": (_int(512, 65536), 4096),
	},
	"settings": {
		"display_width": (_int(640, 4096), 1024),
		"display_height": (_int(480, 4096), 768),
		"page_file": (_page_file, "64 64"),
		"icon_size": (_int(16, 256), 32),
		"wallpaper": (_str, None),
		"reg_files": (_str_list, ["display", "quiet", "watermark-off"]),
	},
	"trim": {
		"profile": (_choice(*TRIM_PROFILES), "none"),
	},
	"patchers": {
		"list": (_name_list(PATCHERS), []),
	},
	"outputs": {
		"disk": {
			"zero_free": (_bool, True),
		},
		"parts": {
			"chunk_size": (_chunk, DEFAULT_CHUNK_SIZE),
			"zstd_level": (_int(1, 22), 19),
		},
	},
}


def _has_required(spec: dict) -> bool:
	"""True when a section has a required key anywhere below it, so it cannot be defaulted from nothing."""
	for node in spec.values():
		if isinstance(node, tuple):
			if node[1] is _REQ:
				return True
		elif _has_required(node):
			return True
	return False


def _validate(table: Any, spec: dict, path: str) -> dict:
	if not isinstance(table, dict):
		raise RecipeError(f"{path}: expected a table")
	for key in table:
		if key not in spec:
			raise RecipeError(f"{path}.{key}: unknown key; known: {', '.join(spec)}")
	result: dict[str, Any] = {}
	for key, node in spec.items():
		here = f"{path}.{key}" if path else key
		if isinstance(node, tuple):
			checker, default = node
			if key in table:
				result[key] = checker(table[key], here)
			elif default is _REQ:
				raise RecipeError(f"{here}: required")
			elif default is not None:
				result[key] = copy.deepcopy(default)
		elif key in table:
			result[key] = _validate(table[key], node, here)
		elif not _has_required(node):
			result[key] = _validate({}, node, here)
	return result


def _merge(base: dict, overlay: dict) -> dict:
	merged = copy.deepcopy(base)
	for key, value in overlay.items():
		if isinstance(value, dict) and isinstance(merged.get(key), dict):
			merged[key] = _merge(merged[key], value)
		else:
			merged[key] = copy.deepcopy(value)
	return merged


def _read(path: Path) -> dict:
	try:
		with open(path, "rb") as recipe_file:
			return tomllib.load(recipe_file)
	except FileNotFoundError:
		raise RecipeError(f"{path}: no such recipe") from None
	except tomllib.TOMLDecodeError as error:
		raise RecipeError(f"{path}: {error}") from None


def _resolve(path: Path, seen: tuple[Path, ...]) -> tuple[dict, list[Path]]:
	path = path.resolve()
	if path in seen:
		raise RecipeError(f"{path}: extends itself through {' -> '.join(str(p) for p in seen)}")
	raw = _read(path)
	chain = [path]
	parent = raw.get("recipe", {}).get("extends") if isinstance(raw.get("recipe"), dict) else None
	if parent:
		if not isinstance(parent, str):
			raise RecipeError(f"{path}: recipe.extends: expected a string")
		# `rl:` names a recipe inside this repository; any other value is a path beside the extending recipe.
		ppath = REPO / parent[3:] if parent.startswith("rl:") else path.parent / parent
		base, base_chain = _resolve(ppath, (*seen, path))
		raw = _merge(base, raw)
		chain = chain + base_chain
	return raw, chain


@dataclass
class Recipe:
	"""A validated recipe. `data` is the resolved, defaulted tables; `chain` lists the files read, the recipe first."""

	data: dict
	chain: list[Path] = field(default_factory=list)

	@property
	def name(self) -> str:
		return self.data["recipe"]["name"]

	def section(self, *keys: str) -> dict:
		table = self.data
		for key in keys:
			table = table[key]
		return table

	@property
	def chunk_size(self) -> int:
		return self.data["outputs"]["parts"]["chunk_size"]


def load(path: str | Path) -> Recipe:
	"""Read, resolve `extends`, validate and default a recipe. Raises RecipeError with the key that is wrong."""
	raw, chain = _resolve(Path(path), ())
	if "recipe" not in raw:
		raise RecipeError("recipe: required (a [recipe] table with a name)")
	data = _validate(raw, SCHEMA, "")
	if "reactos_iso" not in data.get("inputs", {}):
		raise RecipeError("inputs.reactos_iso: required (the pinned ISO)")
	return Recipe(data=data, chain=chain)
