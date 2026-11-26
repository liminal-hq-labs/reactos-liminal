# The `rl` command line.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import argparse
import json
import sys
from pathlib import Path

from . import __version__, doctor
from .fetch import FetchError, fetch_iso
from .paths import WorkDirError, resolve_work
from .recipe import RecipeError, load

DESCRIPTION = """Build Afterglow-dressed ReactOS disk images from a recipe. Unofficial: not made, endorsed or supported by the ReactOS
project. Large files go in the work directory (--work, $RL_WORK, default ~/.cache/reactos-liminal), never inside the repository."""


def _add_work(parser: argparse.ArgumentParser) -> None:
	parser.add_argument(
		"--work",
		metavar="DIR",
		help="work directory, outside the repository (default: $RL_WORK or ~/.cache/reactos-liminal)",
	)


def _cmd_doctor(_args: argparse.Namespace) -> int:
	lines, ok = doctor.check()
	print("\n".join(lines))
	if not ok:
		print("\nrl doctor: required tools are missing", file=sys.stderr)
	return 0 if ok else 1


def _cmd_explain(args: argparse.Namespace) -> int:
	recipe = load(args.recipe)
	document = {"files": [str(path) for path in recipe.chain], "recipe": recipe.data}
	print(json.dumps(document, indent="\t"))
	return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
	recipe = load(args.recipe)
	work = resolve_work(args.work)
	iso = fetch_iso(recipe, work, Path(args.iso) if args.iso else None)
	print(iso)
	return 0


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(prog="rl", description=DESCRIPTION)
	parser.add_argument("--version", action="version", version=f"rl {__version__}")
	commands = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

	sub = commands.add_parser("doctor", help="check that the tools the pipeline needs are installed")
	sub.set_defaults(func=_cmd_doctor)

	sub = commands.add_parser("explain", help="print the resolved, validated recipe after `extends`")
	sub.add_argument("recipe", help="recipe TOML file")
	sub.set_defaults(func=_cmd_explain)

	sub = commands.add_parser("fetch", help="download and check every pinned input, nothing else")
	sub.add_argument("recipe", help="recipe TOML file")
	sub.add_argument("--iso", metavar="FILE", help="use your own copy of the official ISO (checked against the pin)")
	_add_work(sub)
	sub.set_defaults(func=_cmd_fetch)
	return parser


def main(argv: list[str] | None = None) -> int:
	args = build_parser().parse_args(argv)
	try:
		return args.func(args)
	except (RecipeError, FetchError, WorkDirError) as error:
		print(f"rl: {error}", file=sys.stderr)
		return 2
