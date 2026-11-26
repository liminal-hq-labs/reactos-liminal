# The build manifest: the SHA-256 and size of every output, the pinned inputs and the time each stage took. And the Markdown job
# summary made from it.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import json
import os
import time
from pathlib import Path

from .fetch import sha256_file
from .install import render_unattend
from .recipe import Recipe

PARTS_FOLDER = "parts"


class ManifestError(Exception):
	"""Output that cannot be listed."""


def parse_pairs(text: str) -> dict[str, str]:
	"""A `name=value,name=value` list as a dict; a part without `=` is an error."""
	pairs: dict[str, str] = {}
	for part in filter(None, (piece.strip() for piece in text.split(","))):
		name, separator, value = part.partition("=")
		if not separator:
			raise ManifestError(f"expected NAME=VALUE, got {part!r}")
		pairs[name] = value
	return pairs


def list_outputs(dist: Path, manifest_name: str) -> tuple[dict[str, dict], dict | None]:
	"""Every file under `dist` with its size and SHA-256, the parts folder summed as one entry (its own manifest.json is listed)."""
	files: dict[str, dict] = {}
	parts: dict | None = None
	for path in sorted(dist.rglob("*")):
		if not path.is_file():
			continue
		relative = path.relative_to(dist).as_posix()
		if relative == manifest_name:
			continue
		if relative.startswith(PARTS_FOLDER + "/") and path.name != "manifest.json":
			parts = parts or {"files": 0, "bytes": 0}
			parts["files"] += 1
			parts["bytes"] += path.stat().st_size
			continue
		files[relative] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
	if parts:
		chunk = "one zstd file per chunk"
		parts["note"] = f"{chunk}; the raw image's SHA-256 and the chunk list are in parts/manifest.json"
	return files, parts


def build_manifest(
	recipe: Recipe,
	dist: Path,
	manifest_name: str = "build-manifest.json",
	timings: dict[str, str] | None = None,
	hashes: dict[str, str] | None = None,
	v86_version: str = "",
	extra: dict[str, str] | None = None,
	peak_disk_mb: int = 0,
	built: str | None = None,
) -> dict:
	"""The manifest document. `built` is a UTC timestamp; it defaults to `$SOURCE_DATE_EPOCH` if set, else now."""
	if built is None:
		epoch = int(os.environ["SOURCE_DATE_EPOCH"]) if "SOURCE_DATE_EPOCH" in os.environ else time.time()
		built = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))
	iso = recipe.section("inputs", "reactos_iso")
	pinned = {
		"recipe": recipe.name,
		"reactos": "0.4.16 (tag 0.4.16-release), official i386 install CD",
		"reactos_iso_zip_sha256": iso["zip_sha256"],
		"reactos_iso_sha256": iso["sha256"],
		"unattend_inf_sha256": hashlib.sha256(render_unattend(recipe).encode()).hexdigest(),
		"trim_profile": recipe.section("trim", "profile"),
		"patchers": recipe.section("patchers", "list"),
		"chunk_size": recipe.chunk_size,
		"v86": v86_version,
		"inputs": hashes or {},
		"extra": extra or {},
	}
	if "afterglow" in recipe.data["inputs"]:
		afterglow = recipe.section("inputs", "afterglow")
		pinned["afterglow"] = {"repo": afterglow["repo"], "commit": afterglow["commit"], "msstyles_sha256": afterglow["msstyles_sha256"]}
	outputs, parts = list_outputs(dist, manifest_name)
	return {
		"built": built,
		"pinned": pinned,
		"timings_seconds": {name: int(value) for name, value in (timings or {}).items()},
		"peak_work_disk_mb": peak_disk_mb,
		"outputs": outputs,
		"parts": parts,
	}


def write_manifest(document: dict, path: Path) -> None:
	path.write_text(json.dumps(document, indent="\t") + "\n")


def _megabytes(byte_count: int) -> str:
	return f"{byte_count / 1e6:.1f} MB"


def job_summary(manifest: dict) -> str:
	"""A Markdown job summary: sizes, stage timings, pinned inputs, and the source and licence material that publishing would need."""
	pin = manifest["pinned"]
	out = ["## ReactOS image", "", "### Outputs", "", "| Output | Size | SHA-256 |", "|---|---:|---|"]
	for name, entry in sorted(manifest["outputs"].items()):
		out.append(f"| `{name}` | {_megabytes(entry['bytes'])} | `{entry['sha256'][:16]}…` |")
	if manifest.get("parts"):
		parts = manifest["parts"]
		out.append(
			f"| `parts/` ({parts['files']} files, with `manifest.json`) | {_megabytes(parts['bytes'])} | see `parts/manifest.json` |"
		)
	out += ["", "### Stage timings", "", "| Stage | Seconds |", "|---|---:|"]
	out += [f"| {name} | {seconds} |" for name, seconds in manifest["timings_seconds"].items()]
	out += ["", f"Peak work-directory use: {manifest['peak_work_disk_mb']} MB allocated.", "", "### Pinned inputs", ""]
	out += [
		f"- **Recipe:** `{pin['recipe']}`; trim profile `{pin['trim_profile']}`; patchers: {', '.join(pin['patchers']) or 'none'}",
		f"- **ReactOS:** {pin['reactos']}; zip SHA-256 `{pin['reactos_iso_zip_sha256']}`, ISO SHA-256 `{pin['reactos_iso_sha256']}`",
		f"- **Answers file:** `unattend.inf` SHA-256 `{pin['unattend_inf_sha256']}`",
		f"- **Part size:** {pin['chunk_size']} bytes",
		f"- **v86:** {pin['v86'] or 'not recorded'}",
	]
	if "afterglow" in pin:
		out.append(f"- **Afterglow:** `{pin['afterglow']['repo']}` at `{pin['afterglow']['commit']}`")
	out += [f"- **{name}:** `{value[:16]}…`" for name, value in pin["inputs"].items()]
	out += [f"- **{name}:** `{value}`" for name, value in pin["extra"].items()]
	out += [
		"",
		"### Before this is published anywhere",
		"",
		"The artifact is a ReactOS disk image. ReactOS is GPL-2.0-or-later, with LGPL-2.1-or-later for the Wine-derived DLLs and other free licences for bundled parts, so publishing the image means publishing, or offering in writing, the corresponding source and the licence texts. It stays a workflow artifact (7 days) until that is settled. The material to publish with it:",
		"",
		"- **ReactOS 0.4.16 source:** tag `0.4.16-release` (commit `822e8647792a2c43f033e3e00ed273d59f163c7b`) of <https://github.com/reactos/reactos>, as an archive beside the image, with `COPYING`, `COPYING.LIB` and the licence files under `media/fonts/doc/`.",
		"- **WineVDM (otvdm):** the build in `Program Files\\otvdm` (GPL-2.0): its exact release, source archive and licence from <https://github.com/otya128/winevdm>.",
		"- **v86:** the emulator is BSD-2-Clause; `bios/seabios.bin` and `bios/vgabios.bin` are SeaBIOS and SeaVGABIOS 1.16.2 (LGPL-3.0), so offer that source.",
		"- **What we changed:** the trim profile, the registry files, the answers file, the patched files and anything the recipe adds.",
		"- **Fonts:** the image carries ReactOS's metric-compatible clones, not Microsoft's fonts; check a font inventory before publishing.",
	]
	return "\n".join(out)
