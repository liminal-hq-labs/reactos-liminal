# The `rl` command line.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import argparse
import json
import sys
from pathlib import Path

from . import __version__, doctor
from .afterglow import fetch_afterglow
from .fetch import FetchError, fetch_iso
from .image import ImageError, build_image, plan_image, trim_image
from .install import InstallError, plan_install, run_install
from .patchers import PatchError
from .paths import WorkDirError, resolve_work
from .recipe import RecipeError, load
from .settings import SettingsError
from .trim import TrimError, profile_names
from .vm import VmError

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
	if "afterglow" in recipe.data["inputs"]:
		print(fetch_afterglow(recipe, work, Path(args.afterglow_tarball) if args.afterglow_tarball else None))
	return 0


def _cmd_install(args: argparse.Namespace) -> int:
	recipe = load(args.recipe)
	work = resolve_work(args.work)
	iso = Path(args.iso) if args.iso else None
	if args.dry_run:
		print(plan_install(recipe, work, iso, args.accel).describe())
		return 0
	golden = run_install(
		recipe, work, iso, force=args.force, keep_disk_on_failure=args.keep_disk, accel=args.accel, stage_timeout=args.stage_timeout
	)
	print(golden)
	return 0


def _cmd_image(args: argparse.Namespace) -> int:
	recipe = load(args.recipe)
	work = resolve_work(args.work)
	golden = Path(args.golden) if args.golden else None
	out = Path(args.out) if args.out else None
	if args.dry_run:
		print(plan_image(recipe, work, golden, out, with_settings=not args.no_settings).describe())
		return 0
	tarball = Path(args.afterglow_tarball) if args.afterglow_tarball else None
	image = build_image(recipe, work, golden, out, with_settings=not args.no_settings, afterglow_tarball=tarball, accel=args.accel)
	print(image)
	return 0


def _cmd_trim(args: argparse.Namespace) -> int:
	recipe = load(args.recipe)
	work = resolve_work(args.work)
	report = trim_image(recipe, work, Path(args.image), args.profile)
	print(f"removed {len(report.removed)}, missing {len(report.missing)}, freed {report.bytes_freed} bytes")
	for entry in report.missing:
		print(f"missing: {entry.kind} {entry.path}", file=sys.stderr)
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
	sub.add_argument(
		"--afterglow-tarball", metavar="FILE", help="use a local .tar.gz of the pinned Afterglow commit (checked against the pin)"
	)
	_add_work(sub)
	sub.set_defaults(func=_cmd_fetch)

	sub = commands.add_parser("install", help="install ReactOS unattended in a private QEMU and keep the golden disk")
	sub.add_argument("recipe", help="recipe TOML file")
	sub.add_argument("--iso", metavar="FILE", help="use your own copy of the official ISO (checked against the pin)")
	sub.add_argument("--dry-run", action="store_true", help="print the plan and the QEMU commands without running anything")
	sub.add_argument("--force", action="store_true", help="install again even when the golden disk for these inputs exists")
	sub.add_argument("--keep-disk", action="store_true", help="leave the partial disk in the work directory after a failure")
	sub.add_argument("--accel", choices=("kvm", "tcg,thread=multi"), help="QEMU acceleration (default: kvm when /dev/kvm is writable)")
	sub.add_argument("--stage-timeout", type=int, metavar="SECONDS", help="limit for each of the three runs (default 1800 with KVM)")
	_add_work(sub)
	sub.set_defaults(func=_cmd_install)

	sub = commands.add_parser("image", help="turn the golden disk into the finished image: patchers, trim, files, settings")
	sub.add_argument("recipe", help="recipe TOML file")
	sub.add_argument("--golden", metavar="FILE", help="the golden disk (default: the one `rl install` made for this recipe)")
	sub.add_argument("--out", metavar="FILE", help="the image to write (default: WORK/images/NAME.img)")
	sub.add_argument("--dry-run", action="store_true", help="print the plan and run nothing")
	sub.add_argument("--no-settings", action="store_true", help="skip the build VM run that applies the registry settings")
	sub.add_argument("--afterglow-tarball", metavar="FILE", help="use a local .tar.gz of the pinned Afterglow commit")
	sub.add_argument("--accel", choices=("kvm", "tcg,thread=multi"), help="QEMU acceleration for the build VM")
	_add_work(sub)
	sub.set_defaults(func=_cmd_image)

	sub = commands.add_parser("trim", help=f"trim a working copy of a disk with a profile ({', '.join(profile_names())})")
	sub.add_argument("recipe", help="recipe TOML file (supplies the default profile)")
	sub.add_argument("image", help="the disk image to trim in place; never a golden disk")
	sub.add_argument("--profile", help="profile name, instead of the recipe's")
	_add_work(sub)
	sub.set_defaults(func=_cmd_trim)
	return parser


def main(argv: list[str] | None = None) -> int:
	args = build_parser().parse_args(argv)
	try:
		return args.func(args)
	except (RecipeError, FetchError, WorkDirError, InstallError, VmError, ImageError, SettingsError, TrimError, PatchError) as error:
		print(f"rl: {error}", file=sys.stderr)
		return 2
