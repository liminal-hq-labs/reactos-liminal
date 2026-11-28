# The `rl` command line.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import argparse
import json
import sys
import time
from pathlib import Path

from . import __version__, doctor
from . import sounds as sounds_module
from .afterglow import fetch_afterglow
from .audit import audit_image, expected_devices, expected_savers
from .fetch import FetchError, fetch_iso
from .hashing import SumsError, check_sums, sums_text
from .image import ImageError, build_image, plan_image, trim_image
from .install import InstallError, plan_install, run_install
from .iso import IsoError, build_iso
from .isobuild import IsoBuildError
from .licences import LicenceError, licences_page
from .lock import REQUIRABLE, LockError, cache_keys, failures, verify, write_lock
from .manifest import ManifestError, build_manifest, job_summary, parse_pairs, write_manifest
from .mtools import FatImage, MtoolsError
from .parts import PartsError, make_parts
from .patchers import PatchError
from .paths import WorkDirError, resolve_work
from .pin import PinError, pin_afterglow, pin_savers
from .recipe import RecipeError, load, parse_size
from .rustbuild import build_program, fetch_build_source, remote_builds
from .settings import SettingsError
from .trim import TrimError, profile_names
from .vm import VmError
from .zerofree import ZeroFreeError, dig_holes, zero_free_clusters

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
	for name in remote_builds(recipe):
		print(fetch_build_source(recipe, work, name))
	return 0


def _cmd_install(args: argparse.Namespace) -> int:
	recipe = load(args.recipe)
	work = resolve_work(args.work)
	iso = Path(args.iso) if args.iso else None
	if args.dry_run:
		print(plan_install(recipe, work, iso, args.accel, args.in_place_iso).describe())
		return 0
	golden = run_install(
		recipe,
		work,
		iso,
		force=args.force,
		keep_disk_on_failure=args.keep_disk,
		accel=args.accel,
		stage_timeout=args.stage_timeout,
		in_place_iso=args.in_place_iso,
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


def _cmd_iso(args: argparse.Namespace) -> int:
	recipe = load(args.recipe)
	work = resolve_work(args.work)
	image = Path(args.image) if args.image else work / "images" / f"{recipe.name}.img"
	out = Path(args.out) if args.out else work / "dist" / f"{recipe.name}-remaster.iso"
	print(build_iso(recipe, work, image, out, Path(args.iso) if args.iso else None))
	return 0


def _cmd_lock(args: argparse.Namespace) -> int:
	recipe = load(args.recipe)
	path = write_lock(recipe, Path(args.out) if args.out else None)
	print(path)
	return 0


def _cmd_verify(args: argparse.Namespace) -> int:
	recipe = load(args.recipe)
	work = resolve_work(args.work)
	required = tuple(name for entry in args.require or [] for name in entry.split(",") if name)
	unknown = [name for name in required if name not in REQUIRABLE]
	if unknown:
		raise LockError(f"--require: unknown input {', '.join(unknown)}; choose from {', '.join(REQUIRABLE)}")
	checks = verify(recipe, work, Path(args.lock) if args.lock else None, check_lock_file=not args.no_lock)
	for check in checks:
		print(check.line())
	failed = failures(checks, required)
	if failed:
		print(f"rl verify: {len(failed)} check(s) failed", file=sys.stderr)
		return 1
	print(f"rl verify: {len(checks)} checks, none failed")
	return 0


def _cmd_key(args: argparse.Namespace) -> int:
	for name, value in cache_keys(load(args.recipe), resolve_work(args.work)).items():
		print(f"{name}={value}")
	return 0


def _cmd_licences(args: argparse.Namespace) -> int:
	text = licences_page(load(args.recipe))
	if args.out:
		Path(args.out).write_text(text)
		print(args.out)
	else:
		print(text, end="")
	return 0


def _cmd_build(args: argparse.Namespace) -> int:
	recipe = load(args.recipe)
	if args.name not in recipe.data["builds"]:
		declared = ", ".join(recipe.data["builds"]) or "none"
		raise RecipeError(f"builds.{args.name}: the recipe declares no such build; it declares {declared}")
	result = build_program(recipe, resolve_work(args.work), args.name, tarball=Path(args.savers_tarball) if args.savers_tarball else None)
	print(result)
	return 0


def _cmd_pin(args: argparse.Namespace) -> int:
	if args.pre_merge and not args.afterglow:
		raise PinError("--pre-merge goes with --afterglow")
	if args.savers is not None:
		if args.afterglow:
			raise PinError("--savers and --afterglow pin different things; run them one at a time")
		changes = pin_savers(
			args.recipe,
			resolve_work(args.work),
			ref=args.savers or None,
			tarball=Path(args.savers_tarball) if args.savers_tarball else None,
			check=args.check,
		)
	else:
		changes = pin_afterglow(
			args.recipe,
			resolve_work(args.work),
			ref=args.afterglow,
			pre_merge=args.pre_merge,
			golden=Path(args.golden) if args.golden else None,
			tarball=Path(args.afterglow_tarball) if args.afterglow_tarball else None,
			check=args.check,
		)
	for change in changes:
		print(change)
	if args.check:
		print(f"{len(changes)} stale" if changes else "every hash is current")
		return 1 if changes else 0
	print(f"pinned: {len(changes)} changes" if changes else "pinned: nothing to change")
	return 0


def _cmd_trim(args: argparse.Namespace) -> int:
	recipe = load(args.recipe)
	work = resolve_work(args.work)
	report = trim_image(recipe, work, Path(args.image), args.profile)
	print(f"removed {len(report.removed)}, missing {len(report.missing)}, freed {report.bytes_freed} bytes")
	for name, count in report.sources[1:]:
		print(f"extra trim list {name}: {count} entries")
	for entry in report.missing:
		print(f"missing: {entry.kind} {entry.path}", file=sys.stderr)
	return 0


def _cmd_sounds(args: argparse.Namespace) -> int:
	rendered = sounds_module.render_all()
	if args.write_pins:
		sounds_module.write_pins(rendered)
		print(f"wrote {sounds_module.PINS_FILE}: {len(rendered)} sums")
	try:
		sounds_module.check_pins(rendered)
	except sounds_module.SoundError as error:
		print(f"sounds: {error}", file=sys.stderr)
		return 1
	if args.out:
		out = Path(args.out)
		out.mkdir(parents=True, exist_ok=True)
		for name, data in rendered.items():
			(out / name).write_bytes(data)
		print(f"wrote {len(rendered)} files ({sum(map(len, rendered.values()))} bytes) to {out}")
	else:
		print(f"{len(rendered)} sounds match {sounds_module.PINS_FILE.name}")
	return 0


def _cmd_parts(args: argparse.Namespace) -> int:
	recipe = load(args.recipe)
	work = resolve_work(args.work)
	image = Path(args.image)
	if (work / "golden") in image.resolve().parents:
		raise PartsError("refusing to change a golden disk; make an image with `rl image` first")
	zero = recipe.section("outputs", "disk", "zero_free") if args.zero_free is None else args.zero_free
	if zero:
		result = zero_free_clusters(image)
		holes = dig_holes(image)
		print(
			f"zero-free: {result.zeroed_clusters} of {result.free_clusters} free clusters held data and were zeroed "
			f"({result.zeroed_mib:.1f} MiB); holes {'punched' if holes else 'not punched (fallocate is not installed)'}",
			file=sys.stderr,
		)
	chunk = parse_size(args.chunk_size, "--chunk-size") if args.chunk_size else recipe.chunk_size
	level = args.level or recipe.section("outputs", "parts", "zstd_level")
	out = Path(args.out) if args.out else work / "dist" / "parts"
	started = time.monotonic()
	parts = make_parts(image, out, chunk, level)
	print(
		json.dumps(
			{
				"out": str(out),
				"size": parts.size,
				"chunk": parts.chunk,
				"parts": parts.parts,
				"zeroParts": parts.zero_parts,
				"compressedBytes": parts.compressed_bytes,
				"sha256": parts.sha256,
				"seconds": int(time.monotonic() - started),
			}
		)
	)
	return 0


def _cmd_audit(args: argparse.Namespace) -> int:
	image = Path(args.image)
	if not image.is_file():
		print(f"rl: no such image: {image}", file=sys.stderr)
		return 2
	recipe = load(args.recipe) if args.recipe else None
	report = audit_image(FatImage(image), expected_savers(recipe) if recipe else (), expected_devices(recipe) if recipe else ())
	text = report.render(f"Shortcut and registry audit of {image.name}")
	if args.out:
		Path(args.out).write_text(text)
	else:
		print(text, end="")
	blocking = report.blocking(args.strict)
	for finding in blocking:
		print(f"dead: {finding.kind}: {finding.where} -> {finding.target}", file=sys.stderr)
	return 1 if blocking else 0


def _cmd_manifest(args: argparse.Namespace) -> int:
	recipe = load(args.recipe)
	dist = Path(args.dist)
	out = Path(args.out) if args.out else dist / "build-manifest.json"
	document = build_manifest(
		recipe,
		dist,
		out.name if out.parent == dist else "build-manifest.json",
		timings=parse_pairs(",".join(args.timing or [])),
		hashes=parse_pairs(",".join(args.input or [])),
		v86_version=args.v86_version or "",
		extra=parse_pairs(",".join(args.extra or [])),
		peak_disk_mb=args.peak_disk_mb or 0,
		built=args.built,
	)
	write_manifest(document, out)
	print(out)
	return 0


def _cmd_summary(args: argparse.Namespace) -> int:
	print(job_summary(json.loads(Path(args.manifest).read_text())))
	return 0


def _cmd_hash(args: argparse.Namespace) -> int:
	if args.check:
		result = check_sums(Path(args.check), Path(args.base) if args.base else None)
		for name in result.failed:
			print(f"FAILED: {name}", file=sys.stderr)
		for name in result.missing:
			print(f"MISSING: {name}", file=sys.stderr)
		print(f"checked {result.checked}, failed {len(result.failed)}, missing {len(result.missing)}")
		return 0 if result.ok else 1
	text = sums_text([Path(path) for path in args.paths], Path(args.base) if args.base else None)
	if args.out:
		Path(args.out).write_text(text)
	else:
		print(text, end="")
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
	sub.add_argument(
		"--in-place-iso",
		action="store_true",
		help="make the install CD by overwriting files of a copy of the official ISO (the earlier method, a fallback for one release)",
	)
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

	sub = commands.add_parser("verify", help="re-check every input pin against the work directory, and the lock file against the recipe")
	sub.add_argument("recipe", help="recipe TOML file")
	sub.add_argument("--lock", metavar="FILE", help="the lock file (default: beside the recipe, NAME.lock.json)")
	sub.add_argument("--no-lock", action="store_true", help="skip the lock file check")
	sub.add_argument(
		"--require",
		action="append",
		metavar="INPUT[,INPUT]",
		help=f"fail when this input is not in the work directory ({', '.join(REQUIRABLE)}); repeat or separate with commas",
	)
	_add_work(sub)
	sub.set_defaults(func=_cmd_verify)

	sub = commands.add_parser("lock", help="write the lock file: the inputs the recipe resolves to, with their sums")
	sub.add_argument("recipe", help="recipe TOML file")
	sub.add_argument("--out", metavar="FILE", help="the lock file (default: beside the recipe, NAME.lock.json)")
	sub.set_defaults(func=_cmd_lock)

	sub = commands.add_parser("key", help="print the cache keys and paths of a recipe, as name=value lines (for CI)")
	sub.add_argument("recipe", help="recipe TOML file")
	_add_work(sub)
	sub.set_defaults(func=_cmd_key)

	sub = commands.add_parser("licences", help="write the licences page for a recipe as Markdown")
	sub.add_argument("recipe", help="recipe TOML file")
	sub.add_argument("--out", metavar="FILE", help="write the page here instead of printing it")
	sub.set_defaults(func=_cmd_licences)

	sub = commands.add_parser(
		"iso", help="write the remastered install ISO: the official ISO rebuilt with the Afterglow menu and the image's notices"
	)
	sub.add_argument("recipe", help="recipe TOML file")
	sub.add_argument("--image", metavar="FILE", help="the finished image (default: WORK/images/NAME.img)")
	sub.add_argument("--out", metavar="FILE", help="the ISO to write (default: WORK/dist/NAME-remaster.iso)")
	sub.add_argument("--iso", metavar="FILE", help="the official ISO (default: the one `rl fetch` kept; checked against the pin)")
	_add_work(sub)
	sub.set_defaults(func=_cmd_iso)

	sub = commands.add_parser(
		"pin", help="move the Afterglow pin (optional) and refresh every hash that follows from it: tar, style, wallpaper, icon results"
	)
	sub.add_argument("recipe", help="recipe TOML file")
	sub.add_argument(
		"--afterglow", metavar="REF", help="first move the pin to this commit, tag or branch of the recipe's Afterglow repository"
	)
	sub.add_argument(
		"--pre-merge", metavar="NOTE", help="with --afterglow: record that the commit is on an unmerged branch (omit once it is merged)"
	)
	sub.add_argument("--golden", metavar="FILE", help="the golden disk the icon results are measured against (default: the recipe's)")
	sub.add_argument("--afterglow-tarball", metavar="FILE", help="use a local .tar.gz of the commit instead of downloading it")
	sub.add_argument(
		"--savers",
		nargs="?",
		const="",
		default=None,
		metavar="REF",
		help="pin the builds from other repositories (the Afterglow savers) instead: optionally first move them to this commit, tag or "
		"branch, then measure the source tar and every output",
	)
	sub.add_argument("--savers-tarball", metavar="FILE", help="with --savers: use a local .tar.gz of the commit instead of downloading it")
	sub.add_argument("--check", action="store_true", help="change nothing; list the stale hashes and exit 1 if there are any")
	_add_work(sub)
	sub.set_defaults(func=_cmd_pin)

	sub = commands.add_parser(
		"build", help="build one of the recipe's [builds] and check every output against its SHA-256 (the savers, afterfetch.exe)"
	)
	sub.add_argument("recipe", help="recipe TOML file")
	sub.add_argument("name", help="the build's name, as in [builds.NAME]")
	sub.add_argument("--savers-tarball", metavar="FILE", help="use a local .tar.gz of the pinned commit instead of downloading it")
	_add_work(sub)
	sub.set_defaults(func=_cmd_build)

	sub = commands.add_parser("sounds", help="make the Afterglow sounds and check them against pins/afterglow-sounds.json")
	sub.add_argument("--out", metavar="DIR", help="write the WAV files to this folder (a folder to listen from, never the repository)")
	sub.add_argument("--write-pins", action="store_true", help="write the sums of the sounds as made now to the pins file, then check")
	sub.set_defaults(func=_cmd_sounds)

	sub = commands.add_parser("trim", help=f"trim a working copy of a disk with a profile ({', '.join(profile_names())})")
	sub.add_argument("recipe", help="recipe TOML file (supplies the default profile)")
	sub.add_argument("image", help="the disk image to trim in place; never a golden disk")
	sub.add_argument("--profile", help="built-in profile name, instead of the recipe's (its extra lists still apply)")
	_add_work(sub)
	sub.set_defaults(func=_cmd_trim)

	sub = commands.add_parser(
		"audit",
		help="list every shortcut and registry launch point of a built image with its target, and whether the target is on the disk",
	)
	sub.add_argument("image", help="the finished disk image (read only)")
	sub.add_argument(
		"--recipe",
		metavar="FILE",
		help="the recipe the image was built from: every screensaver it writes must be on the disk",
	)
	sub.add_argument("--out", metavar="FILE", help="write the Markdown report here instead of printing it")
	sub.add_argument(
		"--strict",
		action="store_true",
		help="fail on any dead entry; by default only shortcuts, Run keys, the Winlogon shell and control panel applets fail",
	)
	sub.set_defaults(func=_cmd_audit)

	sub = commands.add_parser("parts", help="split an image into zstd parts for v86, with a manifest")
	sub.add_argument("recipe", help="recipe TOML file (supplies the part size and level)")
	sub.add_argument("image", help="the image to split; free space is zeroed first unless --no-zero-free")
	sub.add_argument("--out", metavar="DIR", help="parts folder (default: WORK/dist/parts)")
	sub.add_argument("--chunk-size", metavar="SIZE", help="part size in bytes or such as 8MiB, instead of the recipe's")
	sub.add_argument("--level", type=int, help="zstd level, instead of the recipe's")
	sub.add_argument(
		"--zero-free",
		action=argparse.BooleanOptionalAction,
		default=None,
		help="zero free clusters and punch holes first (default: the recipe's)",
	)
	_add_work(sub)
	sub.set_defaults(func=_cmd_parts)

	sub = commands.add_parser("manifest", help="write the build manifest for a folder of outputs")
	sub.add_argument("recipe", help="recipe TOML file")
	sub.add_argument("dist", help="folder of outputs; every file in it is listed")
	sub.add_argument("--out", metavar="FILE", help="manifest file (default: DIST/build-manifest.json)")
	sub.add_argument("--timing", action="append", metavar="STAGE=SECONDS", help="a stage's seconds; repeat")
	sub.add_argument("--input", action="append", metavar="NAME=SHA256", help="the hash of an input a consumer added; repeat")
	sub.add_argument("--extra", action="append", metavar="NAME=VALUE", help="a fact to record, such as a commit; repeat")
	sub.add_argument("--v86-version", metavar="VERSION")
	sub.add_argument("--peak-disk-mb", type=int)
	sub.add_argument("--built", metavar="UTC_TIMESTAMP", help="build time (default: $SOURCE_DATE_EPOCH or now)")
	sub.set_defaults(func=_cmd_manifest)

	sub = commands.add_parser("summary", help="print a build manifest as a Markdown job summary")
	sub.add_argument("manifest", help="build-manifest.json")
	sub.set_defaults(func=_cmd_summary)

	sub = commands.add_parser("hash", help="print SHA-256 sums for files and folders, or check a sums file")
	sub.add_argument("paths", nargs="*", help="files and folders to sum")
	sub.add_argument("--base", metavar="DIR", help="print names relative to DIR (with --check: where the names are found)")
	sub.add_argument("--out", metavar="FILE", help="write the sums to FILE instead of printing them")
	sub.add_argument("--check", metavar="SUMS", help="check a sums file instead")
	sub.set_defaults(func=_cmd_hash)
	return parser


def main(argv: list[str] | None = None) -> int:
	args = build_parser().parse_args(argv)
	try:
		return args.func(args)
	except (
		RecipeError,
		FetchError,
		WorkDirError,
		InstallError,
		VmError,
		ImageError,
		PinError,
		SettingsError,
		TrimError,
		PatchError,
		PartsError,
		ManifestError,
		SumsError,
		ZeroFreeError,
		LockError,
		LicenceError,
		IsoError,
		IsoBuildError,
		MtoolsError,
	) as error:
		print(f"rl: {error}", file=sys.stderr)
		return 2
