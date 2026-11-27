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


def test_doctor_requires_xorriso_and_an_iso_writer(monkeypatch):
	"""7z does not stand in for xorriso any more (the disc's tree is extracted with it), and either ISO writer will do."""
	everything = {tool.name for tool in doctor.TOOLS}
	monkeypatch.setattr(doctor, "_version", lambda tool, path: "")
	monkeypatch.setattr(doctor, "writers_on_path", lambda: [])

	def lines_without(*absent):
		present = everything - set(absent)
		monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}" if name in present else None)
		return doctor.check()

	lines, ok = lines_without("xorriso")
	assert not ok and any(line.startswith("MISSING xorriso") for line in lines)
	lines, ok = lines_without("mkisofs")
	assert not any(line.startswith("MISSING mkisofs") for line in lines)
	assert any(line.startswith("absent  mkisofs") and "covered by genisoimage" in line for line in lines)
	lines, ok = lines_without("mkisofs", "genisoimage")
	assert not ok and any(line.startswith("MISSING mkisofs") for line in lines)


def test_doctor_reports_the_iso_writer_against_the_pin(monkeypatch):
	from reactos_liminal.isobuild import Writer
	from reactos_liminal.recipe import ISO_WRITER_PIN

	pinned = Writer("/usr/bin/genisoimage", *ISO_WRITER_PIN.split())
	other = Writer("/usr/bin/mkisofs", "mkisofs", "3.02a09")
	monkeypatch.setattr(doctor, "writers_on_path", lambda: [pinned])
	assert f"ok      ISO writer {ISO_WRITER_PIN} matches the recipe's pin" in doctor._iso_writer_lines()
	monkeypatch.setattr(doctor, "writers_on_path", lambda: [other])
	(line,) = doctor._iso_writer_lines()
	assert line.startswith("differs ") and "mkisofs 3.02a09" in line and ISO_WRITER_PIN in line
	monkeypatch.setattr(doctor, "writers_on_path", lambda: [other, pinned])
	assert doctor._iso_writer_lines()[0].startswith("ok ")
	monkeypatch.setattr(doctor, "writers_on_path", lambda: [])
	assert doctor._iso_writer_lines() == []  # the tool lines report that no writer is installed


def test_doctor_lists_the_cabinet_tools_as_optional():
	by_name = {tool.name: tool for tool in doctor.TOOLS}
	assert by_name["gcab"].required is False and by_name["cabextract"].required is False
	assert by_name["mkisofs"].alternative == "genisoimage" and by_name["mkisofs"].required
