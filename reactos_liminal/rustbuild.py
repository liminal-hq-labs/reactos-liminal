# Programs built from source at image time: `[builds.NAME]` in a recipe names a Rust project in this repository, and `rl image` builds
# it with its own pinned toolchain and writes the result wherever a `[[files]]` entry says `source = "built:NAME"`.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The build is a script in the project (`build.sh OUT_DIR`) that leaves `OUT_DIR/NAME.exe`. The script is reproducible (the same source
and toolchain give the same bytes), so the recipe pins the SHA-256 of the output, as it pins every other input; `rl lock` measures it."""

import os
import subprocess
import tomllib
from pathlib import Path

from .fetch import FetchError, sha256_file
from .log import log
from .paths import ensure
from .recipe import Recipe

BUILT_PREFIX = "built:"


class BuildError(FetchError):
	"""A program could not be built, or its output is not the pinned one."""


def used_builds(recipe: Recipe) -> list[str]:
	"""The build names the recipe's `[[files]]` use, in the order of the recipe's builds table."""
	wanted = {entry["source"][len(BUILT_PREFIX) :] for entry in recipe.data["files"] if entry["source"].startswith(BUILT_PREFIX)}
	return [name for name in recipe.data.get("builds", {}) if name in wanted]


def declaring_file(recipe: Recipe, name: str) -> Path:
	"""The nearest recipe file in the chain that declares `[builds.NAME]`: the build's `source` is relative to its folder, and `rl lock`
	rewrites its pin there."""
	for path in recipe.chain:
		if name in tomllib.loads(path.read_text()).get("builds", {}):
			return path
	raise BuildError(f"no recipe in the chain declares [builds.{name}]")


def build_program(recipe: Recipe, work: Path, name: str, measured: dict[str, str] | None = None) -> Path:
	"""Build `name` into the work directory and return the executable. The output must be the pinned SHA-256; with `measured` (for
	`rl lock`) its sum is stored there as `sha256` instead."""
	table = recipe.section("builds", name)
	source = (declaring_file(recipe, name).parent / table["source"]).resolve()
	script = source / "build.sh"
	if not script.is_file():
		raise BuildError(f"builds.{name}: {script} is not a file")
	folder = ensure(work, "builds", name)
	output = folder / "dist"
	environment = {**os.environ, "CARGO_TARGET_DIR": str(folder / "target"), "CARGO_BUILD_JOBS": os.environ.get("CARGO_BUILD_JOBS", "4")}
	log("build", f"{name}: {script} (the project's pinned toolchain; needs rustup, rust-src and lld, see `rl doctor`)")
	done = subprocess.run(["bash", str(script), str(output)], capture_output=True, text=True, check=False, env=environment, cwd=source)
	built = output / f"{name}.exe"
	if done.returncode != 0 or not built.is_file():
		raise BuildError(f"builds.{name}: the build failed: {(done.stderr or done.stdout).strip()[-800:]}")
	actual = sha256_file(built)
	if measured is not None:
		measured["sha256"] = actual
	elif actual != table["sha256"]:
		raise BuildError(f"builds.{name}: {built.name} is {actual}, expected {table['sha256']}; the toolchain or the source differs")
	log("build", f"{name}: {built.stat().st_size} bytes, sha256 {actual}")
	return built


def build_programs(recipe: Recipe, work: Path) -> dict[str, Path]:
	"""Every build the recipe's files use, as {name: executable}."""
	return {name: build_program(recipe, work, name) for name in used_builds(recipe)}
