# Programs built from source at image time: `[builds.NAME]` in a recipe is a Rust project in this repository (one `NAME.exe`), or a project
# at a pinned commit of another repository (several outputs, such as the Afterglow savers' `.scr` files).
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""A build is a script (`build.sh OUT_DIR`) that leaves its outputs in `OUT_DIR`. The script is reproducible (the same source and
toolchain give the same bytes), so the recipe pins the SHA-256 of each output, as it pins every other input; `rl lock` and `rl pin`
measure them.

A project in this repository (`source`, `sha256`) leaves `OUT_DIR/NAME.exe`, and `built:NAME` names it. A project at a pinned commit of
another repository (`repo`, `commit`, `tar_sha256`, an optional `script`, and an `outputs` table of file name to SHA-256) is fetched as
the source tar GitHub serves for that commit, checked like the Afterglow tar, extracted once per commit, and built there; `built:NAME/FILE`
names one output. An output the script writes that the recipe does not list is ignored."""

import gzip
import os
import shutil
import subprocess
import tarfile
import tomllib
from pathlib import Path

from .afterglow import download_unchecked
from .fetch import FetchError, sha256_file
from .log import log
from .paths import ensure
from .recipe import BUILT_PREFIX, Recipe, is_remote_build, split_built


class BuildError(FetchError):
	"""A program could not be built, or its output is not the pinned one."""


def used_builds(recipe: Recipe) -> list[str]:
	"""The build names the recipe's `[[files]]` use, in the order of the recipe's builds table."""
	wanted = {split_built(entry["source"])[0] for entry in recipe.data["files"] if entry["source"].startswith(BUILT_PREFIX)}
	return [name for name in recipe.data.get("builds", {}) if name in wanted]


def remote_builds(recipe: Recipe) -> list[str]:
	"""Every build from another repository the recipe declares (used or not: `rl fetch`, `rl lock` and `rl pin` cover them all)."""
	return [name for name, table in recipe.data.get("builds", {}).items() if is_remote_build(table)]


def declaring_file(recipe: Recipe, name: str, key: str | None = None, output: str | None = None) -> Path:
	"""The nearest recipe file in the chain that declares `[builds.NAME]`: the build's `source` is relative to its folder, and `rl lock`
	rewrites its pin there. With `key` the nearest file that sets that key (`commit`), and with `output` the nearest file that declares
	that output, so a consumer recipe's extra output is pinned in the consumer's file."""
	for path in recipe.chain:
		table = tomllib.loads(path.read_text()).get("builds", {}).get(name)
		if table is None:
			continue
		if key is not None and key not in table:
			continue
		if output is not None and output not in table.get("outputs", {}):
			continue
		return path
	raise BuildError(f"no recipe in the chain declares [builds.{name}]" + (f" {output or key}" if (output or key) else ""))


def tar_path(recipe: Recipe, work: Path, name: str) -> Path:
	"""Where the checked, uncompressed source tar of a remote build is kept, so `rl verify` can check the pin without downloading."""
	return work / "builds" / name / f"{recipe.section('builds', name)['commit']}.tar"


def source_url(recipe: Recipe, name: str) -> str:
	table = recipe.section("builds", name)
	return f"https://codeload.github.com/{table['repo']}/tar.gz/{table['commit']}"


def _check_members(archive: tarfile.TarFile, name: str) -> None:
	"""Refuse a member outside the tree, an absolute path, a device, and a link that leaves the tree. A relative link inside the tree is
	allowed (the savers' `platforms/win32/crates` is one)."""
	for member in archive.getmembers():
		parts = member.name.split("/")
		if member.name.startswith("/") or ".." in parts:
			raise BuildError(f"builds.{name}: the source archive has an unsafe path: {member.name!r}")
		if member.isdev() or member.isfifo():
			raise BuildError(f"builds.{name}: the source archive holds a device: {member.name!r}")
		if member.issym() or member.islnk():
			target = member.linkname
			base = parts[:-1] if member.issym() else []
			resolved = os.path.normpath("/".join([*base, target])) if member.issym() else os.path.normpath(target)
			if target.startswith("/") or resolved.startswith("..") or resolved.startswith("/"):
				raise BuildError(f"builds.{name}: the source archive has a link that leaves the tree: {member.name!r} -> {target!r}")


def fetch_build_source(recipe: Recipe, work: Path, name: str, tarball: Path | None = None, trust: bool = False) -> Path:
	"""The pinned source tree of a remote build, extracted once per commit under `WORK/builds/NAME/src-<commit>`. `tarball` is a local
	.tar.gz used instead of the download; the same hash check applies. `trust` is for `rl pin` alone: it accepts whatever tar the commit
	gives (the new sum is read back with `tree_tar_sha256`)."""
	table = recipe.section("builds", name)
	folder = ensure(work, "builds", name)
	destination = folder / f"src-{table['commit']}"
	marker = destination / ".verified"
	if marker.is_file() and (trust or marker.read_text().strip() == table["tar_sha256"]):
		log("build", f"{name}: {destination} (already fetched and checked)")
		return destination
	scratch = folder / ".fetch"
	shutil.rmtree(scratch, ignore_errors=True)
	scratch.mkdir()
	try:
		compressed = scratch / "source.tar.gz"
		if tarball is not None:
			shutil.copyfile(tarball, compressed)
		else:
			# GitHub may recompress an archive, so the pin is the sum of the uncompressed tar.
			download_unchecked(source_url(recipe, name), compressed)
		raw = scratch / "source.tar"
		with gzip.open(compressed, "rb") as source, open(raw, "wb") as target:
			shutil.copyfileobj(source, target, 1 << 20)
		actual = sha256_file(raw)
		if not trust and actual != table["tar_sha256"]:
			raise BuildError(f"builds.{name}: the source tar is {actual}, expected {table['tar_sha256']}; the download was discarded")
		extracted = scratch / "tree"
		extracted.mkdir()
		with tarfile.open(raw) as archive:
			_check_members(archive, name)
			try:
				archive.extractall(extracted, filter="data")
			except tarfile.TarError as error:
				raise BuildError(f"builds.{name}: the source archive is refused: {error}") from error
		top = [path for path in extracted.iterdir() if path.is_dir()]
		if len(top) != 1:
			raise BuildError(f"builds.{name}: the source archive does not hold one project folder")
		if not (top[0] / table["script"]).is_file():
			raise BuildError(f"builds.{name}: the source archive has no {table['script']}")
		shutil.rmtree(destination, ignore_errors=True)
		top[0].replace(destination)
		raw.replace(tar_path(recipe, work, name))
		marker.write_text(actual + "\n")
	finally:
		shutil.rmtree(scratch, ignore_errors=True)
	return destination


def tree_tar_sha256(tree: Path) -> str:
	"""The SHA-256 of the tar a fetched tree came from, as `fetch_build_source` recorded it."""
	return (tree / ".verified").read_text().strip()


def _run_script(script: Path, output: Path, folder: Path, cwd: Path, name: str) -> None:
	environment = {**os.environ, "CARGO_TARGET_DIR": str(folder / "target"), "CARGO_BUILD_JOBS": os.environ.get("CARGO_BUILD_JOBS", "4")}
	log("build", f"{name}: {script.name} (the project's pinned toolchain; needs rustup, rust-src and lld, see `rl doctor`)")
	shutil.rmtree(output, ignore_errors=True)
	done = subprocess.run(["bash", str(script), str(output)], capture_output=True, text=True, check=False, env=environment, cwd=cwd)
	if done.returncode != 0:
		raise BuildError(f"builds.{name}: the build failed: {(done.stderr or done.stdout).strip()[-800:]}")


def _build_remote(recipe: Recipe, work: Path, name: str, measured: dict | None, tarball: Path | None) -> Path:
	table = recipe.section("builds", name)
	tree = fetch_build_source(recipe, work, name, tarball, trust=measured is not None)
	folder = ensure(work, "builds", name)
	output = folder / "dist"
	_run_script(tree / table["script"], output, folder, tree, name)
	sums: dict[str, str] = {}
	for file_name, expected in table["outputs"].items():
		built = output / file_name
		if not built.is_file():
			raise BuildError(f"builds.{name}: the build did not write {file_name}")
		sums[file_name] = sha256_file(built)
		if measured is None and sums[file_name] != expected:
			raise BuildError(f"builds.{name}: {file_name} is {sums[file_name]}, expected {expected}; the toolchain or the source differs")
		log("build", f"{name}: {file_name} {built.stat().st_size} bytes, sha256 {sums[file_name]}")
	if measured is not None:
		measured["tar_sha256"] = tree_tar_sha256(tree)
		measured["outputs"] = sums
	return output


def build_program(recipe: Recipe, work: Path, name: str, measured: dict | None = None, tarball: Path | None = None) -> Path:
	"""Build `name` into the work directory. A project in this repository returns its executable; a build from another repository
	returns the folder of its outputs. Every output must be the pinned SHA-256; with `measured` (for `rl lock` and `rl pin`) the sums are
	stored there instead (`sha256`, or `tar_sha256` and `outputs`)."""
	table = recipe.section("builds", name)
	if is_remote_build(table):
		return _build_remote(recipe, work, name, measured, tarball)
	source = (declaring_file(recipe, name).parent / table["source"]).resolve()
	script = source / "build.sh"
	if not script.is_file():
		raise BuildError(f"builds.{name}: {script} is not a file")
	folder = ensure(work, "builds", name)
	output = folder / "dist"
	_run_script(script, output, folder, source, name)
	built = output / f"{name}.exe"
	if not built.is_file():
		raise BuildError(f"builds.{name}: the build did not write {built.name}")
	actual = sha256_file(built)
	if measured is not None:
		measured["sha256"] = actual
	elif actual != table["sha256"]:
		raise BuildError(f"builds.{name}: {built.name} is {actual}, expected {table['sha256']}; the toolchain or the source differs")
	log("build", f"{name}: {built.stat().st_size} bytes, sha256 {actual}")
	return built


def build_programs(recipe: Recipe, work: Path) -> dict[str, Path]:
	"""Every build the recipe's files use, as {name: executable, or the folder of the outputs of a build from another repository}."""
	return {name: build_program(recipe, work, name) for name in used_builds(recipe)}


def built_file(built: dict[str, Path], source: str) -> Path:
	"""The file a `built:NAME` or `built:NAME/FILE` source names, given the result of `build_programs`."""
	name, output = split_built(source)
	return built[name] / output if output else built[name]
