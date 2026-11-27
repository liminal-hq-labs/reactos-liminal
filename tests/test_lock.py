# Tests for `rl lock` and `rl verify`: the lock records what a recipe resolves to, and verify fails clearly on drift.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import json
import shutil

import pytest

from reactos_liminal.cli import main
from reactos_liminal.lock import build_lock, check_lock, failures, lock_path, verify, write_lock
from reactos_liminal.recipe import load
from tests.conftest import ISO_BYTES, ISO_NAME, REPO


def by_name(checks):
	return {check.name: check for check in checks}


@pytest.fixture
def locked(fake_iso_recipe, tmp_path):
	recipe, _, _ = fake_iso_recipe
	write_lock(recipe)
	return recipe, tmp_path / "work"


def test_the_lock_records_the_resolved_inputs_and_is_stable(fake_iso_recipe):
	recipe, _, _ = fake_iso_recipe
	first = build_lock(recipe)
	assert first["inputs"]["reactos_iso"]["sha256"] == recipe.section("inputs", "reactos_iso")["sha256"]
	assert first == build_lock(recipe)
	assert json.dumps(first).count(str(REPO)) == 0  # no machine-specific path


def test_the_lock_sits_beside_the_recipe(fake_iso_recipe):
	recipe, _, _ = fake_iso_recipe
	assert lock_path(recipe) == recipe.chain[0].with_name("recipe.lock.json")


def test_a_matching_lock_passes(locked):
	recipe, _ = locked
	assert [check.status for check in check_lock(recipe)] == ["ok"]


def test_a_missing_lock_is_drift_that_says_what_to_run(fake_iso_recipe):
	recipe, _, _ = fake_iso_recipe
	[check] = check_lock(recipe)
	assert check.status == "drift" and "rl lock" in check.detail


def test_a_pin_changed_without_relocking_is_named_by_key(locked):
	recipe, _ = locked
	recipe.data["inputs"]["reactos_iso"]["sha256"] = "0" * 64
	[check] = check_lock(recipe)
	assert check.status == "drift" and "inputs.reactos_iso.sha256" in check.detail


def test_a_changed_trim_list_or_payload_is_drift(locked, tmp_path):
	recipe, _ = locked
	payload = recipe.chain[0].parent / "payload.txt"
	payload.write_bytes(b"one")
	recipe.data["files"] = [{"source": "payload.txt", "destination": "X/PAYLOAD.TXT"}]
	write_lock(recipe)
	assert check_lock(recipe)[0].status == "ok"
	payload.write_bytes(b"two")
	[check] = check_lock(recipe)
	assert check.status == "drift" and "payload.txt" in check.detail


def test_a_lock_that_is_not_json_is_drift(locked):
	recipe, _ = locked
	lock_path(recipe).write_text("{")
	assert check_lock(recipe)[0].status == "drift"


def test_verify_checks_the_cached_iso_against_its_pin(locked):
	recipe, work = locked
	downloads = work / "dl"
	downloads.mkdir(parents=True)
	(downloads / ISO_NAME).write_bytes(ISO_BYTES)
	checks = by_name(verify(recipe, work))
	assert checks["iso"].status == "ok" and checks["iso-zip"].status == "absent"
	assert not failures(checks.values())
	(downloads / ISO_NAME).write_bytes(ISO_BYTES + b"x")
	checks = verify(recipe, work)
	assert by_name(checks)["iso"].status == "drift"
	assert [check.name for check in failures(checks)] == ["iso"]


def test_an_absent_input_fails_only_when_required(locked):
	recipe, work = locked
	checks = verify(recipe, work)
	assert not failures(checks)
	assert [check.name for check in failures(checks, ("iso",))] == ["iso"]


def test_verify_checks_the_afterglow_tar_and_the_built_style(locked):
	recipe, work = locked
	recipe.data["inputs"]["afterglow"] = {
		"repo": "x/y",
		"commit": "a" * 40,
		"tar_sha256": __import__("hashlib").sha256(b"tar").hexdigest(),
		"msstyles_sha256": __import__("hashlib").sha256(b"style").hexdigest(),
		"apply_reg": "r.reg",
	}
	(work / "afterglow").mkdir(parents=True)
	(work / "afterglow" / ("a" * 40 + ".tar")).write_bytes(b"tar")
	(work / "afterglow-files").mkdir()
	(work / "afterglow-files" / "afterglow.msstyles").write_bytes(b"style")
	checks = by_name(verify(recipe, work, check_lock_file=False))
	assert checks["afterglow-tar"].status == "ok" and checks["msstyles"].status == "ok"
	(work / "afterglow-files" / "afterglow.msstyles").write_bytes(b"other")
	assert [check.name for check in failures(verify(recipe, work, check_lock_file=False))] == ["msstyles"]


def test_the_cli_lock_and_verify(fake_iso_recipe, tmp_path, capsys):
	recipe, _, _ = fake_iso_recipe
	path = str(recipe.chain[0])
	work = str(tmp_path / "work")
	assert main(["verify", path, "--work", work]) == 1
	assert "rl lock" in capsys.readouterr().out
	assert main(["lock", path]) == 0
	assert main(["verify", path, "--work", work]) == 0
	assert main(["verify", path, "--work", work, "--require", "iso"]) == 1
	assert "rl verify: 1 check(s) failed" in capsys.readouterr().err
	assert main(["verify", path, "--work", work, "--require", "nothing"]) == 2


def test_the_committed_lock_matches_the_base_recipe(tmp_path):
	recipe = load(REPO / "recipes" / "afterglow.toml")
	assert [check.status for check in check_lock(recipe)] == ["ok"], "run ./rl lock recipes/afterglow.toml"


def test_verify_never_writes(locked):
	recipe, work = locked
	verify(recipe, work)
	assert not work.exists()
	assert shutil.which("true")  # the work directory was never created


def test_the_cache_keys_name_the_pins_and_the_golden_disk(base_recipe_path, tmp_path, capsys):
	work = tmp_path / "work"
	assert main(["key", str(base_recipe_path), "--work", str(work)]) == 0
	keys = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines())
	recipe = load(base_recipe_path)
	assert keys["iso_sha256"] == recipe.section("inputs", "reactos_iso")["sha256"]
	assert keys["afterglow_commit"] == recipe.section("inputs", "afterglow")["commit"]
	assert keys["golden_path"].startswith(str(work / "golden")) and keys["golden_key"][:16] in keys["golden_path"]
	assert keys["iso_path"] == str(work / "dl" / "ReactOS-0.4.16-i386.iso")
	assert not work.exists()  # printing keys writes nothing


def test_the_lock_records_a_recipes_own_reg_file_by_relative_path(fake_iso_recipe):
	recipe, _, _ = fake_iso_recipe
	folder = recipe.chain[0].parent
	reg_file = folder / "own.reg"
	reg_file.write_text("Windows Registry Editor Version 5.00\n")
	recipe.data["settings"]["reg_files"] = [*recipe.data["settings"]["reg_files"], str(reg_file)]
	lock = build_lock(recipe)
	assert list(lock["reg_files"]) == ["reg:own.reg"]
	reg_file.write_text("Windows Registry Editor Version 5.00\n; changed\n")
	assert build_lock(recipe) != lock


def test_the_committed_lock_matches_the_compact_recipe():
	recipe = load(REPO / "recipes" / "afterglow-compact.toml")
	assert [check.status for check in check_lock(recipe)] == ["ok"]
	assert recipe.section("trim", "profile") == "base"
