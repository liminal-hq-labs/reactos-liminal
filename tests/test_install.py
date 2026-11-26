# Tests for the unattended install: the answers, the key of the golden disk cache and the dry-run plan. No QEMU runs here.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import re
import subprocess

import pytest

from reactos_liminal import install
from reactos_liminal.cli import main
from reactos_liminal.install import InstallError, fix_installed_freeldr, golden_key, golden_path, plan_install, render_unattend, run_install


@pytest.fixture
def no_processes(monkeypatch):
	"""Any attempt to start a process fails the test: a dry run must not run QEMU, xorriso or anything else."""

	def refuse(*args, **kwargs):
		raise AssertionError(f"a process was started: {args!r}")

	monkeypatch.setattr(subprocess, "run", refuse)
	monkeypatch.setattr(subprocess, "Popen", refuse)


def test_answers_take_the_recipe_values(fake_iso_recipe):
	recipe, _, _ = fake_iso_recipe
	recipe.data["install"].update(locale="1009", computer_name="DEMO", owner_name="Demo user", time_zone_index=35)
	text = render_unattend(recipe)
	assert "LocaleID = 1009" in text
	assert 'ComputerName = "DEMO"' in text
	assert 'FullName = "Demo user"' in text
	assert "TimeZoneIndex = 35" in text
	assert "DefaultThemesOff = yes" in text
	assert not [marker for marker in re.findall(r"@[A-Z_]+@", text) if marker != "@NAME@"]  # the header names the markers


def test_the_classic_shell_switch(fake_iso_recipe):
	recipe, _, _ = fake_iso_recipe
	recipe.data["install"]["classic_shell"] = False
	assert "DefaultThemesOff = no" in render_unattend(recipe)


def test_an_answer_with_a_quote_is_refused(fake_iso_recipe):
	recipe, _, _ = fake_iso_recipe
	recipe.data["install"]["owner_name"] = 'Bad "name"'
	with pytest.raises(InstallError, match="OWNER_NAME"):
		render_unattend(recipe)


def test_the_answers_fit_on_the_disc():
	"""The official unattend.inf holds 2,575 bytes and the edit keeps that size, so the rendered answers must be smaller."""
	from reactos_liminal.recipe import load
	from tests.conftest import REPO

	assert len(render_unattend(load(REPO / "recipes" / "afterglow.toml")).encode()) < 2575 - 2


def test_installed_freeldr_gets_the_normal_entry_and_delay():
	broken = b'[FREELOADER]\r\nDefaultOS=ReactOS_Debug\r\nTimeOut=0\r\n\r\n[Operating Systems]\r\nReactOS="ReactOS"\r\n'
	fixed = fix_installed_freeldr(broken)
	assert fixed == b'[FREELOADER]\r\nDefaultOS=ReactOS\r\nTimeOut=3\r\n\r\n[Operating Systems]\r\nReactOS="ReactOS"\r\n'
	assert fix_installed_freeldr(fixed) == fixed
	assert fix_installed_freeldr(broken.replace(b"\r\n", b"\n")) == fixed


def test_the_key_follows_what_shapes_the_disk(fake_iso_recipe, monkeypatch, tmp_path):
	recipe, _, _ = fake_iso_recipe
	first = golden_key(recipe)
	assert golden_key(recipe) == first
	recipe.data["install"]["computer_name"] = "OTHER"
	assert golden_key(recipe) != first
	recipe.data["install"]["computer_name"] = "REACTOS"
	assert golden_key(recipe) == first
	recipe.data["inputs"]["reactos_iso"]["sha256"] = "2" * 64
	assert golden_key(recipe) != first
	recipe.data["inputs"]["reactos_iso"]["sha256"] = "1" * 64
	template = tmp_path / "unattend.inf.in"
	template.write_text(install.UNATTEND_TEMPLATE.read_text() + "; changed\n")
	monkeypatch.setattr(install, "UNATTEND_TEMPLATE", template)
	monkeypatch.setattr(install, "SHAPING_FILES", (template, *install.SHAPING_FILES[1:]))
	assert golden_key(recipe) != first


def test_things_that_do_not_shape_the_disk_leave_the_key_alone(fake_iso_recipe):
	recipe, _, _ = fake_iso_recipe
	first = golden_key(recipe)
	recipe.data["trim"] = {"profile": "demo"}
	recipe.data["outputs"]["parts"]["chunk_size"] = 1 << 20
	recipe.data["settings"]["icon_size"] = 48
	assert golden_key(recipe) == first


def test_the_plan_names_every_stage_and_runs_nothing(fake_iso_recipe, tmp_path, no_processes):
	recipe, _, _ = fake_iso_recipe
	plan = plan_install(recipe, tmp_path / "work", accel="kvm")
	assert not plan.cached
	assert list(plan.commands) == ["text", "gui", "desktop"]
	text_command = plan.commands["text"]
	assert "-no-reboot" in text_command and "-daemonize" in text_command
	assert "order=d" in text_command and "order=c" in plan.commands["gui"]
	assert any(argument.startswith("unix:") and argument.endswith("mon.sock,server,nowait") for argument in text_command)
	assert "-pidfile" in text_command
	description = plan.describe()
	assert "download file://" in description
	assert "DefaultOS=ReactOS and TimeOut=3" in description


def test_the_cli_dry_run_prints_the_plan(fake_iso_recipe, tmp_path, no_processes, capsys):
	recipe, _, iso_bytes = fake_iso_recipe
	iso = tmp_path / "mine.iso"
	iso.write_bytes(iso_bytes)
	code = main(["install", str(recipe.chain[0]), "--dry-run", "--iso", str(iso), "--work", str(tmp_path / "work"), "--accel", "kvm"])
	assert code == 0
	output = capsys.readouterr().out
	assert "cache: miss" in output and "QEMU, stage desktop" in output
	assert not (tmp_path / "work").exists()  # nothing was created


def test_a_current_golden_disk_is_reused_without_running_anything(fake_iso_recipe, tmp_path, no_processes):
	recipe, _, _ = fake_iso_recipe
	work = tmp_path / "work"
	golden = golden_path(recipe, work)
	golden.parent.mkdir(parents=True)
	golden.write_bytes(b"a finished disk")
	assert plan_install(recipe, work).cached
	assert run_install(recipe, work) == golden
	assert golden.read_bytes() == b"a finished disk"
