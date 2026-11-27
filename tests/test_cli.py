# Tests for the command line, the work-directory rule and `rl doctor`.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import json
import subprocess

import pytest

from reactos_liminal import doctor
from reactos_liminal.cli import main
from reactos_liminal.paths import REPO, WorkDirError, resolve_work


def test_help_lists_the_commands(capsys):
	with pytest.raises(SystemExit) as stop:
		main(["--help"])
	assert stop.value.code == 0
	output = capsys.readouterr().out
	for command in ("doctor", "explain", "fetch"):
		assert command in output


def test_the_shim_runs_in_isolated_mode():
	done = subprocess.run([str(REPO / "rl"), "--help"], capture_output=True, text=True, check=False)
	assert done.returncode == 0
	assert "usage: rl" in done.stdout


def test_explain_prints_the_resolved_recipe(base_recipe_path, capsys):
	assert main(["explain", str(base_recipe_path)]) == 0
	document = json.loads(capsys.readouterr().out)
	assert document["recipe"]["outputs"]["parts"]["chunk_size"] == 8 * 1024 * 1024


def test_a_bad_recipe_exits_with_the_key_named(tmp_path, capsys):
	bad = tmp_path / "bad.toml"
	bad.write_text('[recipe]\nname = "Bad Name"\n')
	assert main(["explain", str(bad)]) == 2
	assert "recipe.name" in capsys.readouterr().err


def test_fetch_with_a_local_iso(fake_iso_recipe, tmp_path, capsys):
	recipe, _, iso_bytes = fake_iso_recipe
	iso = tmp_path / "mine.iso"
	iso.write_bytes(iso_bytes)
	assert main(["fetch", str(recipe.chain[0]), "--iso", str(iso), "--work", str(tmp_path / "work")]) == 0
	assert capsys.readouterr().out.strip() == str(iso)


def test_fetch_downloads_into_the_work_directory(fake_iso_recipe, tmp_path, capsys):
	recipe, _, _ = fake_iso_recipe
	work = tmp_path / "work"
	assert main(["fetch", str(recipe.chain[0]), "--work", str(work)]) == 0
	assert capsys.readouterr().out.strip() == str(work / "dl" / "TEST.iso")


def test_work_inside_the_repository_is_refused(fake_iso_recipe, capsys):
	recipe, _, _ = fake_iso_recipe
	assert main(["fetch", str(recipe.chain[0]), "--work", str(REPO / "work")]) == 2
	assert "outside the repository" in capsys.readouterr().err


def test_resolve_work_order(monkeypatch, tmp_path):
	monkeypatch.setenv("RL_WORK", str(tmp_path / "env"))
	assert resolve_work() == tmp_path / "env"
	assert resolve_work(tmp_path / "flag") == tmp_path / "flag"
	monkeypatch.delenv("RL_WORK")
	assert resolve_work().name == "reactos-liminal"
	with pytest.raises(WorkDirError):
		resolve_work(REPO)


def test_doctor_reports_missing_required_tools(monkeypatch, capsys):
	monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
	lines, ok = doctor.check()
	assert not ok
	assert any(line.startswith("MISSING qemu-system-i386") for line in lines)
	assert main(["doctor"]) == 1
	assert "required tools are missing" in capsys.readouterr().err


def test_doctor_accepts_7z_in_place_of_xorriso(monkeypatch):
	present = {"7z"} | {tool.name for tool in doctor.TOOLS if tool.name not in ("xorriso", "7z")}
	monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}" if name in present else None)
	monkeypatch.setattr(doctor, "_version", lambda tool, path: "")
	lines, ok = doctor.check()
	assert ok or all(not line.startswith("MISSING") or "python3" in line for line in lines)
	assert not any(line.startswith("MISSING xorriso") for line in lines)
