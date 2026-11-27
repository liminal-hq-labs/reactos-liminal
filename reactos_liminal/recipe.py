# The recipe: a TOML file that names every input with its pin, the install answers, the trim profile, the patchers and the outputs.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# A recipe chooses and parameterizes steps; it cannot add a new kind of write. `extends` layers one recipe on another: tables merge
# key by key, and any other value (a list, a string) in the extending recipe replaces the one it extends. Three lists are the exception.
# `trim.extra`: each recipe's own list, resolved against that recipe's folder, is added after the lists of the recipes it extends. The
# entries of `settings.reg_files` that end in `.reg` work the same way: paths beside the recipe that lists them, kept after the named files.
# `[[files]]`: entries merge by destination (an extending recipe's entry replaces the extended recipe's entry for the same destination in
# place, and its other entries follow), and each file source is made absolute against the recipe that wrote it.
import copy
import os
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

# The ISO writer a recipe pins, as `NAME VERSION`: cdrkit's `genisoimage`, which Ubuntu's apt ships and CI uses. cdrtools' `mkisofs`
# writes a disc that boots the same but is not byte for byte the same, so a build with another writer is reported. The epoch is the
# time stamped on every file and volume descriptor (2025-08-29), so a disc is reproducible; `$SOURCE_DATE_EPOCH` overrides it.
ISO_WRITER_PIN = "genisoimage 1.1.11"
ISO_EPOCH = 1756425600

PATCHERS = (
	"afterglow.pointers",
	"afterglow.start",
	"afterglow.logon",
	"afterglow.icons",
	"afterglow.cpl-icons",
	"afterglow.program-icons",
	"afterglow.dialog-icons",
	"afterglow.toolbar-bitmaps",
	"afterglow.dialog-bitmaps",
	"afterglow.boot",
)
REG_FILES = (
	"display",
	"quiet",
	"watermark-off",
	"mouse-linear",
	"hide-desktop-icons",
	"afterglow-logon",
	"regional-canada",
	"pointer-defaults",
)
TRIM_PROFILES = ("none", "base")


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


REG_HEADER = "Windows Registry Editor Version 5.00"


def is_reg_path(entry: Any) -> bool:
	"""An entry of `settings.reg_files` that names a file beside a recipe instead of one of the built-in names."""
	return isinstance(entry, str) and entry.endswith(".reg")


def _reg_files(value: Any, key: str) -> list[str]:
	"""Built-in names, then `.reg` paths (made absolute against the recipe that lists them before this runs). A path must be a registry
	file that exists and starts with the registry header; the built-in names are checked as for any name list."""
	named = [item for item in value if not is_reg_path(item)] if isinstance(value, list) else value
	_name_list(REG_FILES)(named, key)
	paths = [item for item in value if is_reg_path(item)]
	if len(set(paths)) != len(paths):
		raise RecipeError(f"{key}: duplicate entries")
	for item in paths:
		path = Path(item)
		if not path.is_file():
			raise RecipeError(f"{key}: {path.name} is not a file beside the recipe that lists it ({path})")
		try:
			first = path.read_text(encoding="utf-8-sig").splitlines()[:1]
		except (OSError, UnicodeDecodeError) as error:
			raise RecipeError(f"{key}: cannot read {path}: {error}") from None
		if first != [REG_HEADER]:
			raise RecipeError(f"{key}: {path.name} must start with the line {REG_HEADER!r}")
	return [*named, *paths]


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


def _writer(value: Any, key: str) -> str:
	if not isinstance(value, str) or not re.fullmatch(r"(mkisofs|genisoimage) \S+", value):
		raise RecipeError(f"{key}: expected the ISO writer as 'NAME VERSION', such as 'genisoimage 1.1.11'")
	return value


def _volume(value: Any, key: str) -> str:
	if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_ ]{1,32}", value):
		raise RecipeError(f"{key}: expected a volume label of up to 32 letters, digits, spaces or underscores")
	return value


def _locale(value: Any, key: str) -> str:
	if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{4}", value):
		raise RecipeError(f'{key}: expected a four-digit hexadecimal locale id such as "0409"')
	return value.upper()


def _scene(value: Any, key: str) -> str:
	if not isinstance(value, str) or not re.fullmatch(r"[a-z]+-(dark|light)-(smooth|stepped)", value):
		raise RecipeError(f'{key}: expected an Afterglow wallpaper such as "dusk-dark-smooth" (palette, mode, style)')
	return value


def _guest_path(value: Any, key: str) -> str:
	if not isinstance(value, str) or not re.fullmatch(r"[Cc]:\\[^\\/:*?\"<>|]+(\\[^\\/:*?\"<>|]+)*", value):
		raise RecipeError(f"{key}: expected a path on drive C: with backslashes, such as C:\\ReactOS\\afterglow.bmp")
	return value


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


# Patchers that build on the copy another patcher writes of the same file, as (earlier, later) pairs: when both are listed, `earlier`
# must come first, or the later write would replace the earlier from the stock file and lose its work. The pointers copy of
# user32.dll, the Start copy of explorer.exe and the logon copy of msgina.dll are made from the stock files; the icon patchers and the
# dialog bitmaps then take the newest copy of each path they patch.
PATCHER_ORDER = (
	("afterglow.pointers", "afterglow.dialog-icons"),
	("afterglow.start", "afterglow.program-icons"),
	("afterglow.logon", "afterglow.program-icons"),
	("afterglow.icons", "afterglow.dialog-bitmaps"),
	("afterglow.program-icons", "afterglow.dialog-bitmaps"),
	("afterglow.start", "afterglow.dialog-bitmaps"),
	("afterglow.logon", "afterglow.dialog-bitmaps"),
)


def _patcher_list(value: Any, key: str) -> list[str]:
	"""The patcher names, in order. `afterglow.dialog-icons` patches the user32.dll that `afterglow.pointers` writes, so it needs that
	patcher listed before it; the other way round, the pointers copy would replace the icons. The other pairs in PATCHER_ORDER need
	only the order, and only when both are listed."""
	names = _name_list(PATCHERS)(value, key)
	if "afterglow.dialog-icons" in names and "afterglow.pointers" not in names:
		raise RecipeError(f"{key}: afterglow.dialog-icons builds on the user32.dll of afterglow.pointers, which must be listed before it")
	for earlier, later in PATCHER_ORDER:
		if earlier in names and later in names and names.index(earlier) > names.index(later):
			raise RecipeError(f"{key}: {later} builds on the file {earlier} writes, so {earlier} must be listed before it")
	return names


def _str_list(value: Any, key: str) -> list[str]:
	return _name_list(None)(value, key)


def _recipe_name(value: Any, key: str) -> str:
	if not isinstance(value, str) or not NAME.match(value):
		raise RecipeError(f"{key}: expected a lowercase name of letters, digits and hyphens")
	return value


def _choice_int(*options: int):
	def check(value: Any, key: str) -> int:
		if isinstance(value, bool) or value not in options:
			raise RecipeError(f"{key}: expected one of {', '.join(str(option) for option in options)}")
		return value

	return check


def _chunk(value: Any, key: str) -> int:
	byte_count = parse_size(value, key)
	if byte_count < MIN_CHUNK_SIZE or byte_count & (byte_count - 1):
		raise RecipeError(f"{key}: expected a power of two of at least 64 KiB; got {byte_count}")
	return byte_count


def _table_list(spec: dict):
	"""A list of tables (`[[name]]` in TOML), each validated against `spec`."""

	def check(value: Any, key: str) -> list[dict]:
		if not isinstance(value, list):
			raise RecipeError(f"{key}: expected a list of tables")
		return [_validate(item, spec, f"{key}[{index}]") for index, item in enumerate(value)]

	return check


_REQ = object()

FILE_SPEC = {"source": (_str, _REQ), "destination": (_str, _REQ)}
SHORTCUT_SPEC = {
	"name": (_str, _REQ),
	"target": (_str, _REQ),
	"arguments": (_str, ""),
	"working_dir": (_str, ""),
	"description": (_str, ""),
	"icon": (_str, ""),
	"icon_index": (_int(0, 1000), 0),
	"show": (_choice_int(1, 3, 7), 1),
}

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
			"wallpaper": (_scene, None),
			"wallpaper_sha256": (_sha256, None),
			"pre_merge": (_str, None),
		},
	},
	"builds": {
		"afterfetch": {
			"source": (_str, _REQ),
			"sha256": (_sha256, _REQ),
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
	"iso": {
		"writer": (_writer, ISO_WRITER_PIN),
		"volume": (_volume, "ReactOS"),
		"epoch": (_int(0, 4_102_444_800), ISO_EPOCH),
	},
	"settings": {
		"display_width": (_int(640, 4096), 1024),
		"display_height": (_int(480, 4096), 768),
		"page_file": (_page_file, "64 64"),
		"icon_size": (_int(16, 256), 32),
		"wallpaper": (_guest_path, None),
		"wallpaper_style": (_choice("stretch", "centre", "tile"), "stretch"),
		"reg_files": (_reg_files, ["display", "quiet", "watermark-off"]),
		"remove_desktop_shortcuts": (_str_list, []),
	},
	"trim": {
		"profile": (_choice(*TRIM_PROFILES), "none"),
		"extra": (_str_list, []),
	},
	"patchers": {
		"list": (_patcher_list, []),
	},
	"files": (_table_list(FILE_SPEC), []),
	"shortcuts": (_table_list(SHORTCUT_SPEC), []),
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


def _own_extra(raw: dict, path: Path) -> list | None:
	"""The recipe's own `trim.extra` with each string made absolute against this recipe's folder, or None when it sets none. A value
	that is not a list of strings is left as it is for the validator to name."""
	table = raw.get("trim")
	if not isinstance(table, dict) or not isinstance(table.get("extra"), list):
		return None
	return [str(path.parent / item) if isinstance(item, str) and item else item for item in table["extra"]]


def _own_reg_files(raw: dict, path: Path) -> list | None:
	"""The recipe's own `settings.reg_files` with each `.reg` path made absolute against this recipe's folder, or None when it sets
	none."""
	table = raw.get("settings")
	if not isinstance(table, dict) or not isinstance(table.get("reg_files"), list):
		return None
	return [str(path.parent / item) if is_reg_path(item) else item for item in table["reg_files"]]


BUILT_PREFIX = "built:"


def _file_key(entry: Any) -> str | None:
	"""The destination as the disk sees it (case-insensitive, one separator, no leading slash), or None when the entry is malformed."""
	destination = entry.get("destination") if isinstance(entry, dict) else None
	if not isinstance(destination, str):
		return None
	return destination.replace("\\", "/").strip("/").lower()


def _own_files(raw: dict, path: Path) -> list | None:
	"""The recipe's own `[[files]]` with each plain source made absolute against this recipe's folder (a `built:` source is a name,
	not a path), or None when it lists none. A malformed entry is left for the validator to name."""
	entries = raw.get("files")
	if not isinstance(entries, list):
		return None
	resolved = []
	for entry in entries:
		source = entry.get("source") if isinstance(entry, dict) else None
		if isinstance(source, str) and source and not source.startswith(BUILT_PREFIX):
			entry = {**entry, "source": os.path.normpath(path.parent / source)}
		resolved.append(entry)
	return resolved


def merge_files(inherited: list, own: list) -> list:
	"""`inherited` with each `own` entry replacing the inherited entry for the same destination in place; the rest of `own` follows."""
	merged = list(inherited)
	positions = {_file_key(entry): index for index, entry in enumerate(merged) if _file_key(entry) is not None}
	for entry in own:
		key = _file_key(entry)
		if key is not None and key in positions:
			merged[positions[key]] = entry
		else:
			if key is not None:
				positions[key] = len(merged)
			merged.append(entry)
	return merged


def _resolve(path: Path, seen: tuple[Path, ...]) -> tuple[dict, list[Path]]:
	path = path.resolve()
	if path in seen:
		raise RecipeError(f"{path}: extends itself through {' -> '.join(str(p) for p in seen)}")
	raw = _read(path)
	chain = [path]
	own_extra = _own_extra(raw, path)
	own_reg_files = _own_reg_files(raw, path)
	own_files = _own_files(raw, path)
	parent = raw.get("recipe", {}).get("extends") if isinstance(raw.get("recipe"), dict) else None
	if parent:
		if not isinstance(parent, str):
			raise RecipeError(f"{path}: recipe.extends: expected a string")
		# `rl:` names a recipe inside this repository; any other value is a path beside the extending recipe.
		ppath = REPO / parent[3:] if parent.startswith("rl:") else path.parent / parent
		base, base_chain = _resolve(ppath, (*seen, path))
		inherited = base.get("trim", {}).get("extra") if isinstance(base.get("trim"), dict) else None
		inherited_regs = base.get("settings", {}).get("reg_files") if isinstance(base.get("settings"), dict) else None
		inherited_files = base.get("files") if isinstance(base.get("files"), list) else []
		raw = _merge(base, raw)
		chain = chain + base_chain
		if own_extra is not None:
			raw["trim"]["extra"] = [*(inherited if isinstance(inherited, list) else []), *own_extra]
		if own_reg_files is not None:
			# The named files are the extending recipe's when it lists any; the paths of both recipes follow them, base first.
			inherited_list = inherited_regs if isinstance(inherited_regs, list) else []
			inherited_paths = [item for item in inherited_list if is_reg_path(item)]
			own_named = [item for item in own_reg_files if not is_reg_path(item)]
			named = own_named if own_named else [item for item in inherited_list if not is_reg_path(item)]
			own_paths = [item for item in own_reg_files if is_reg_path(item)]
			raw["settings"]["reg_files"] = [*named, *inherited_paths, *own_paths]
		if own_files is not None:
			raw["files"] = merge_files(inherited_files, own_files)
	else:
		if own_extra is not None:
			raw["trim"]["extra"] = own_extra
		if own_reg_files is not None:
			raw["settings"]["reg_files"] = own_reg_files
		if own_files is not None:
			raw["files"] = own_files
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
	pin = data.get("inputs", {}).get("afterglow", {})
	if ("wallpaper" in pin) != ("wallpaper_sha256" in pin):
		raise RecipeError("inputs.afterglow: wallpaper and wallpaper_sha256 go together")
	if "wallpaper" in pin and "wallpaper" not in data["settings"]:
		raise RecipeError("settings.wallpaper: required when inputs.afterglow.wallpaper names a scene (the path the BMP is written to)")
	for entry in data["files"]:
		if entry["source"].startswith(BUILT_PREFIX) and entry["source"][len(BUILT_PREFIX) :] not in data.get("builds", {}):
			raise RecipeError(f"files: {entry['source']} names a build that no [builds] table declares")
	if "reactos_iso" not in data.get("inputs", {}):
		raise RecipeError("inputs.reactos_iso: required (the pinned ISO)")
	return Recipe(data=data, chain=chain)
