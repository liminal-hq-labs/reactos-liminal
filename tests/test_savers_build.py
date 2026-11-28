# Tests for builds from another repository at a pinned commit (the Afterglow savers): the source tar, the outputs, the lock, the pin, the
# audit and what the real recipes write. The source tar is made in the test; nothing is downloaded.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import gzip
import hashlib
import io
import json
import shutil
import tarfile

import pytest
from conftest import make_fat_image

from reactos_liminal.audit import DEAD, OK, audit_image, expected_savers
from reactos_liminal.cli import main
from reactos_liminal.licences import licences_page, notice_text
from reactos_liminal.lock import build_lock, cache_keys, verify
from reactos_liminal.pin import PinError, pin_savers
from reactos_liminal.recipe import RecipeError, load
from reactos_liminal.rustbuild import BuildError, build_program, build_programs, built_file, declaring_file, fetch_build_source, used_builds

COMMIT = "1" * 40
SCRIPT = b'#!/usr/bin/env bash\nset -e\nmkdir -p "$1"\nprintf "one" > "$1/ONE.SCR"\nprintf "two" > "$1/TWO.SCR"\nprintf "extra" > "$1/EXTRA.SCR"\n'
ONE = hashlib.sha256(b"one").hexdigest()
TWO = hashlib.sha256(b"two").hexdigest()
ZEROS = "0" * 64

RECIPE = """[recipe]
name = "base"

[inputs.reactos_iso]
name = "x.iso"
url = "file:///x.zip"
zip_sha256 = "{ZEROS}"
sha256 = "{ZEROS}"

[builds.pack]
repo = "owner/pack"
commit = "{COMMIT}"
tar_sha256 = "{tar}"
script = "scripts/build.sh"

[builds.pack.outputs]
"ONE.SCR" = "{one}"
"TWO.SCR" = "{two}"

[[files]]
source = "built:pack/ONE.SCR"
destination = "ReactOS/system32/ONE.SCR"

[[files]]
source = "built:pack/TWO.SCR"
destination = "ReactOS/system32/TWO.SCR"
"""


def make_tar(path, members=None):
	"""A source tar the way GitHub serves one: one top folder holding scripts/build.sh. Returns (the .tar.gz, the sum of the tar)."""
	raw = io.BytesIO()
	with tarfile.open(fileobj=raw, mode="w") as archive:
		for name, data in {"pack-1/scripts/build.sh": SCRIPT, **(members or {})}.items():
			info = tarfile.TarInfo(name)
			info.size = len(data)
			archive.addfile(info, io.BytesIO(data))
	compressed = path / "pack.tar.gz"
	compressed.write_bytes(gzip.compress(raw.getvalue(), mtime=0))
	return compressed, hashlib.sha256(raw.getvalue()).hexdigest()


def write_recipe(directory, tar=None, one=ONE, two=TWO):
	path = directory / "base.toml"
	path.write_text(RECIPE.format(ZEROS=ZEROS, COMMIT=COMMIT, tar=tar or ZEROS, one=one, two=two))
	return path


@pytest.fixture
def pack(tmp_path):
	"""(recipe path, source tar.gz, work directory) for a recipe pinned to the synthetic tar."""
	tarball, digest = make_tar(tmp_path)
	return write_recipe(tmp_path, tar=digest), tarball, tmp_path / "work"


def test_the_tar_is_fetched_checked_and_built_and_each_output_is_checked(pack):
	path, tarball, work = pack
	recipe = load(path)
	assert used_builds(recipe) == ["pack"]
	output = build_program(recipe, work, "pack", tarball=tarball)
	assert (output / "ONE.SCR").read_bytes() == b"one" and (output / "TWO.SCR").read_bytes() == b"two"
	assert (work / "builds" / "pack" / f"src-{COMMIT}" / "scripts" / "build.sh").is_file()


def test_files_name_one_output_each(pack):
	path, tarball, work = pack
	recipe = load(path)
	assert {entry["source"] for entry in recipe.data["files"]} == {"built:pack/ONE.SCR", "built:pack/TWO.SCR"}
	built = {"pack": build_program(recipe, work, "pack", tarball=tarball)}
	assert built_file(built, "built:pack/TWO.SCR").read_bytes() == b"two"
	assert build_programs(recipe, work)["pack"] == built["pack"]


def test_a_wrong_tar_sum_is_refused_and_nothing_is_kept(tmp_path):
	tarball, _ = make_tar(tmp_path)
	recipe = load(write_recipe(tmp_path, tar="a" * 64))
	with pytest.raises(BuildError, match="source tar is"):
		fetch_build_source(recipe, tmp_path / "work", "pack", tarball)
	assert not (tmp_path / "work" / "builds" / "pack" / f"src-{COMMIT}").exists()


def test_an_output_the_script_does_not_write_is_refused(pack):
	path, tarball, work = pack
	path.write_text(path.read_text().replace('"TWO.SCR" = ', '"MISSING.SCR" = ').replace("built:pack/TWO.SCR", "built:pack/MISSING.SCR"))
	with pytest.raises(BuildError, match="did not write MISSING.SCR"):
		build_program(load(path), work, "pack", tarball=tarball)


def test_a_wrong_output_sum_is_refused(pack, tmp_path):
	_, tarball, work = pack
	_, digest = make_tar(tmp_path)
	recipe = load(write_recipe(tmp_path, tar=digest, two="b" * 64))
	with pytest.raises(BuildError, match="TWO.SCR is " + TWO):
		build_program(recipe, work, "pack", tarball=tarball)


def test_an_output_the_recipe_does_not_list_is_ignored(pack):
	path, tarball, work = pack
	output = build_program(load(path), work, "pack", tarball=tarball)
	assert (output / "EXTRA.SCR").is_file()  # written by the script, listed nowhere: no error, and nothing writes it


@pytest.mark.parametrize(
	("name", "kind"),
	[("../escape", "file"), ("pack-1/../../escape", "file"), ("/abs/path", "file"), ("pack-1/link", "absolute"), ("pack-1/up", "outside")],
)
def test_an_archive_member_outside_the_tree_is_refused(tmp_path, name, kind):
	raw = io.BytesIO()
	with tarfile.open(fileobj=raw, mode="w") as archive:
		script = tarfile.TarInfo("pack-1/scripts/build.sh")
		script.size = len(SCRIPT)
		archive.addfile(script, io.BytesIO(SCRIPT))
		member = tarfile.TarInfo(name)
		if kind == "file":
			member.size = 1
			archive.addfile(member, io.BytesIO(b"x"))
		else:
			member.type = tarfile.SYMTYPE
			member.linkname = "/etc/passwd" if kind == "absolute" else "../../outside"
			archive.addfile(member)
	tarball = tmp_path / "bad.tar.gz"
	tarball.write_bytes(gzip.compress(raw.getvalue(), mtime=0))
	recipe = load(write_recipe(tmp_path, tar=hashlib.sha256(raw.getvalue()).hexdigest()))
	with pytest.raises(BuildError, match="unsafe path|leaves the tree"):
		fetch_build_source(recipe, tmp_path / "work", "pack", tarball)


def test_a_relative_link_inside_the_tree_is_allowed(tmp_path):
	raw = io.BytesIO()
	with tarfile.open(fileobj=raw, mode="w") as archive:
		script = tarfile.TarInfo("pack-1/scripts/build.sh")
		script.size = len(SCRIPT)
		archive.addfile(script, io.BytesIO(SCRIPT))
		link = tarfile.TarInfo("pack-1/platforms/crates")
		link.type = tarfile.SYMTYPE
		link.linkname = "../crates"
		archive.addfile(link)
	tarball = tmp_path / "link.tar.gz"
	tarball.write_bytes(gzip.compress(raw.getvalue(), mtime=0))
	recipe = load(write_recipe(tmp_path, tar=hashlib.sha256(raw.getvalue()).hexdigest()))
	tree = fetch_build_source(recipe, tmp_path / "work", "pack", tarball)
	assert (tree / "platforms" / "crates").is_symlink()


def test_a_tar_without_the_script_is_refused(tmp_path):
	raw = io.BytesIO()
	with tarfile.open(fileobj=raw, mode="w") as archive:
		info = tarfile.TarInfo("pack-1/README")
		info.size = 1
		archive.addfile(info, io.BytesIO(b"x"))
	tarball = tmp_path / "none.tar.gz"
	tarball.write_bytes(gzip.compress(raw.getvalue(), mtime=0))
	recipe = load(write_recipe(tmp_path, tar=hashlib.sha256(raw.getvalue()).hexdigest()))
	with pytest.raises(BuildError, match="no scripts/build.sh"):
		fetch_build_source(recipe, tmp_path / "work", "pack", tarball)


def test_a_built_file_must_name_a_declared_output(tmp_path):
	path = write_recipe(tmp_path)
	path.write_text(path.read_text().replace("built:pack/TWO.SCR", "built:pack/NOPE.SCR"))
	with pytest.raises(RecipeError, match="NOPE.SCR names an output"):
		load(path)


def test_an_in_tree_build_has_one_program_and_no_output_name(tmp_path):
	path = tmp_path / "r.toml"
	path.write_text(
		RECIPE.replace(
			'[builds.pack]\nrepo = "owner/pack"\ncommit = "{COMMIT}"\ntar_sha256 = "{tar}"\nscript = "scripts/build.sh"\n\n[builds.pack.outputs]\n"ONE.SCR" = "{one}"\n"TWO.SCR" = "{two}"\n',
			'[builds.pack]\nsource = "tool"\nsha256 = "{one}"\n',
		)
		.format(ZEROS=ZEROS, one=ONE)
		.replace("built:pack/TWO.SCR", "built:pack/X.SCR")
	)
	with pytest.raises(RecipeError, match="one program"):
		load(path)


def test_a_build_is_one_form_or_the_other(tmp_path):
	path = write_recipe(tmp_path)
	path.write_text(path.read_text().replace('script = "scripts/build.sh"', 'script = "scripts/build.sh"\nsha256 = "' + ZEROS + '"'))
	with pytest.raises(RecipeError, match="not both"):
		load(path)


def test_an_output_name_is_a_plain_file_name(tmp_path):
	path = write_recipe(tmp_path)
	path.write_text(path.read_text().replace('"TWO.SCR" = ', '"../TWO.SCR" = '))
	with pytest.raises(RecipeError, match="plain file name"):
		load(path)


def test_the_lock_records_the_pin_and_verify_checks_the_kept_tar(pack):
	path, tarball, work = pack
	recipe = load(path)
	lock = build_lock(recipe)["builds"]["pack"]
	assert lock["commit"] == COMMIT and lock["outputs"] == {"ONE.SCR": ONE, "TWO.SCR": TWO}
	assert [check.status for check in verify(recipe, work, check_lock_file=False) if check.name == "pack-tar"] == ["absent"]
	fetch_build_source(recipe, work, "pack", tarball)
	assert [check.status for check in verify(recipe, work, check_lock_file=False) if check.name == "pack-tar"] == ["ok"]
	kept = work / "builds" / "pack" / f"{COMMIT}.tar"
	kept.write_bytes(kept.read_bytes() + b"x")
	assert [check.status for check in verify(recipe, work, check_lock_file=False) if check.name == "pack-tar"] == ["drift"]


def test_the_cache_keys_name_the_commit_and_the_tar(pack):
	path, _, work = pack
	keys = cache_keys(load(path), work)
	assert keys["pack_commit"] == COMMIT and keys["pack_path"] == str(work / "builds" / "pack")


def test_a_consumer_recipes_extra_output_is_pinned_in_the_consumers_file(pack, tmp_path):
	path, tarball, work = pack
	child = tmp_path / "child.toml"
	child.write_text(
		'[recipe]\nname = "child"\nextends = "base.toml"\n\n[builds.pack.outputs]\n"EXTRA.SCR" = "'
		+ ZEROS
		+ '"\n\n[[files]]\nsource = "built:pack/EXTRA.SCR"\ndestination = "ReactOS/system32/EXTRA.SCR"\n'
	)
	recipe = load(child)
	assert set(recipe.section("builds", "pack")["outputs"]) == {"ONE.SCR", "TWO.SCR", "EXTRA.SCR"}
	assert declaring_file(recipe, "pack", output="EXTRA.SCR") == child
	assert declaring_file(recipe, "pack", output="ONE.SCR") == path
	changes = pin_savers(child, work, tarball=tarball, check=True)
	assert changes == [f"builds.pack.outputs.EXTRA.SCR: {ZEROS} -> {hashlib.sha256(b'extra').hexdigest()}"]
	assert ZEROS in child.read_text()
	pin_savers(child, work, tarball=tarball)
	assert hashlib.sha256(b"extra").hexdigest() in child.read_text() and ONE in path.read_text()
	assert pin_savers(child, work, tarball=tarball, check=True) == []


def test_pin_savers_measures_every_stale_sum_and_writes_them(tmp_path):
	tarball, digest = make_tar(tmp_path)
	path = write_recipe(tmp_path, tar="e" * 64, one="f" * 64)
	work = tmp_path / "work"
	changes = pin_savers(path, work, tarball=tarball, check=True)
	assert changes == [f"builds.pack.tar_sha256: {'e' * 64} -> {digest}", f"builds.pack.outputs.ONE.SCR: {'f' * 64} -> {ONE}"]
	assert "e" * 64 in path.read_text()  # --check writes nothing
	assert pin_savers(path, work, tarball=tarball) == changes
	text = path.read_text()
	assert digest in text and ONE in text and "e" * 64 not in text
	assert load(path).section("builds", "pack")["tar_sha256"] == digest
	assert pin_savers(path, work, tarball=tarball, check=True) == []


def test_pin_savers_needs_a_build_from_another_repository(tmp_path):
	path = tmp_path / "r.toml"
	path.write_text(
		f'[recipe]\nname = "r"\n[inputs.reactos_iso]\nname = "x.iso"\nurl = "file:///x"\nzip_sha256 = "{ZEROS}"\nsha256 = "{ZEROS}"\n'
	)
	with pytest.raises(PinError, match="no \\[builds\\]"):
		pin_savers(path, tmp_path / "work")


def test_the_pin_command_and_the_build_command(pack, capsys):
	path, tarball, work = pack
	assert main(["build", str(path), "pack", "--savers-tarball", str(tarball), "--work", str(work)]) == 0
	assert (work / "builds" / "pack" / "dist" / "ONE.SCR").is_file()
	assert main(["pin", str(path), "--savers", "--savers-tarball", str(tarball), "--check", "--work", str(work)]) == 0
	assert "every hash is current" in capsys.readouterr().out
	assert main(["pin", str(path), "--savers", "--afterglow", "x"]) == 2


# What the real recipes write.

SAVERS = ("AGMAZE.SCR", "AGCRACK.SCR", "AGTWILIT.SCR", "AGINK.SCR", "AGCOLLCT.SCR")


@pytest.mark.parametrize("recipe_name", ["base_recipe_path", "compact_recipe_path"])
def test_both_images_write_the_five_savers_to_the_system_folder_and_never_the_quill_one(recipe_name, request):
	recipe = load(request.getfixturevalue(recipe_name))
	writes = {entry["destination"]: entry["source"] for entry in recipe.data["files"] if entry["destination"].endswith(".SCR")}
	assert writes == {f"ReactOS/system32/{name}": f"built:afterglow-savers/{name}" for name in SAVERS}
	table = recipe.section("builds", "afterglow-savers")
	assert set(table["outputs"]) == set(SAVERS) and "AGQUILL.SCR" not in table["outputs"]
	assert table["repo"] == "liminal-hq-labs/afterglow-savers" and table["script"] == "scripts/build-scr.sh"
	assert expected_savers(recipe) == SAVERS


def test_no_trim_profile_names_a_saver_so_the_compact_image_keeps_the_five():
	from reactos_liminal.paths import REPO

	for profile in (REPO / "profiles").rglob("*.txt"):
		named = [line for line in profile.read_text().lower().splitlines() if line.endswith(".scr") and "/ag" in line]
		assert named == [], profile.name


def test_no_registry_file_selects_a_saver():
	from reactos_liminal.paths import REPO

	for reg in (REPO / "guest" / "reg").glob("*.reg"):
		text = reg.read_text(errors="replace").lower()
		assert "scrnsave.exe" not in text, reg.name
	quiet = (REPO / "guest" / "reg" / "quiet.reg").read_text(errors="replace")
	assert '"ScreenSaveActive"="0"' in quiet


def test_ask_for_password_on_resume_is_cleared_in_every_recipe_that_applies_quiet(base_recipe_path, compact_recipe_path):
	from reactos_liminal.paths import REPO

	quiet = (REPO / "guest" / "reg" / "quiet.reg").read_text(errors="replace")
	desktop = quiet.split("[HKEY_CURRENT_USER\\Control Panel\\Desktop]")[1]
	assert '"ScreenSaverIsSecure"="0"' in desktop and '"ScreenSaveActive"="0"' in desktop
	for path in (base_recipe_path, compact_recipe_path):
		assert "quiet" in load(path).section("settings", "reg_files")
	assert "ScreenSaverIsSecure" not in "".join(
		reg.read_text(errors="replace") for reg in (REPO / "guest" / "reg").glob("*.reg") if reg.name != "quiet.reg"
	)


def test_the_compact_trim_drops_the_logon_saver_and_keeps_blank_screen_while_the_full_image_keeps_both(
	base_recipe_path, compact_recipe_path
):
	from reactos_liminal.trim import build_profile, removes

	def trim_of(path):
		recipe = load(path)
		return build_profile(recipe.section("trim", "profile"), recipe.section("trim", "extra"))

	compact = trim_of(compact_recipe_path)
	assert removes(compact, "ReactOS/system32/logon.scr")
	assert not removes(compact, "ReactOS/system32/blankscr.scr")
	assert removes(compact, "ReactOS/system32/mazescr.scr")
	full = trim_of(base_recipe_path)
	assert not removes(full, "ReactOS/system32/logon.scr") and not removes(full, "ReactOS/system32/blankscr.scr")
	assert not removes(load_profile_named("base"), "ReactOS/system32/logon.scr"), "the shared base profile must not name logon.scr"


def load_profile_named(name):
	from reactos_liminal.trim import load_profile

	return load_profile(name)


def test_the_pin_is_a_full_commit_with_a_sum_for_each_output(base_recipe_path):
	table = load(base_recipe_path).section("builds", "afterglow-savers")
	assert len(table["commit"]) == 40 and set(table["commit"]) != {"0"}
	assert all(len(digest) == 64 and set(digest) != {"0"} for digest in [table["tar_sha256"], *table["outputs"].values()])


def test_the_locks_hold_the_savers_pin(base_recipe_path, compact_recipe_path):
	for path, lock_name in ((base_recipe_path, "afterglow.lock.json"), (compact_recipe_path, "afterglow-compact.lock.json")):
		lock = json.loads((path.parent / lock_name).read_text())
		assert lock["builds"]["afterglow-savers"] == build_lock(load(path))["builds"]["afterglow-savers"]
		assert lock["trim_lists"] == build_lock(load(path))["trim_lists"]
		assert not any(key.startswith("extra:/") for key in lock["trim_lists"]), "a lock holds nothing machine-specific"


def test_the_licences_and_notice_name_the_savers_only_for_a_recipe_that_builds_them(base_recipe_path, pack):
	recipe = load(base_recipe_path)
	assert "afterglow-savers" in licences_page(recipe) and b"Afterglow screensavers" in notice_text(recipe)
	other = load(pack[0])
	assert "Afterglow screensavers" not in licences_page(other) and b"Afterglow screensavers" not in notice_text(other)


# The audit.

needs_mtools = pytest.mark.skipif(shutil.which("mformat") is None, reason="needs mtools")


def put(fat, tmp_path, path, data=b"MZ"):
	folder = ""
	for part in path.split("/")[:-1]:
		folder = f"{folder}/{part}".strip("/")
		fat.make_directory(folder)
	source = tmp_path / "upload.bin"
	source.write_bytes(data)
	fat.copy_in(source, path)


@needs_mtools
def test_the_audit_lists_every_saver_in_the_system_folder_as_listed(tmp_path):
	fat = make_fat_image(tmp_path / "disk.img")
	for name in ("AGMAZE.SCR", "matrix.scr"):
		put(fat, tmp_path, f"ReactOS/system32/{name}")
	put(fat, tmp_path, "ReactOS/other/NOT.SCR")
	report = audit_image(fat)
	savers = [(finding.target, finding.status) for finding in report.findings if finding.kind == "screensaver"]
	assert savers == [("agmaze.scr", OK), ("matrix.scr", OK)]
	assert not report.blocking()


@needs_mtools
def test_the_audit_fails_when_a_saver_the_recipe_writes_is_not_on_the_disk(tmp_path, base_recipe_path):
	fat = make_fat_image(tmp_path / "disk.img")
	for name in SAVERS[:-1]:
		put(fat, tmp_path, f"ReactOS/system32/{name}")
	assert main(["audit", str(fat.image)]) == 0
	assert main(["audit", str(fat.image), "--recipe", str(base_recipe_path), "--out", str(tmp_path / "audit.md")]) == 1
	report = audit_image(fat, expected_savers(load(base_recipe_path)))
	assert [finding.target for finding in report.findings if finding.kind == "screensaver" and finding.status == DEAD] == ["AGCOLLCT.SCR"]
	put(fat, tmp_path, "ReactOS/system32/AGCOLLCT.SCR")
	assert main(["audit", str(fat.image), "--recipe", str(base_recipe_path)]) == 0


@needs_mtools
def test_the_compact_image_lists_the_five_and_blank_screen_and_not_the_logon_saver(tmp_path, compact_recipe_path):
	fat = make_fat_image(tmp_path / "disk.img")
	for name in (*SAVERS, "blankscr.scr"):
		put(fat, tmp_path, f"ReactOS/system32/{name}")
	report = audit_image(fat, expected_savers(load(compact_recipe_path)))
	listed = sorted(finding.target.lower() for finding in report.findings if finding.kind == "screensaver" and finding.status == OK)
	assert listed == sorted([*(name.lower() for name in SAVERS), "blankscr.scr"])
	assert "logon.scr" not in listed and not report.blocking()
