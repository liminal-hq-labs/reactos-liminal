# Tests for the image pipeline: its order, the dry-run plan and a build on a synthetic disk (no QEMU, no settings run).
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import subprocess

import pytest

from reactos_liminal import image, patchers, trim
from reactos_liminal import recipe as recipe_module
from reactos_liminal.cli import main
from reactos_liminal.image import ImageError, build_image, plan_image
from reactos_liminal.install import golden_path
from reactos_liminal.mtools import FatImage
from reactos_liminal.patchers import PatchedFile
from reactos_liminal.trim import TrimError


@pytest.fixture
def no_processes(monkeypatch):
	def refuse(*args, **kwargs):
		raise AssertionError(f"a process was started: {args!r}")

	monkeypatch.setattr(subprocess, "run", refuse)
	monkeypatch.setattr(subprocess, "Popen", refuse)


@pytest.fixture
def golden(fake_iso_recipe, fat, tmp_path):
	"""A small FAT disk standing in for the golden disk, placed where `rl image` looks for it."""
	recipe, _, _ = fake_iso_recipe
	work = tmp_path / "work"
	path = golden_path(recipe, work)
	path.parent.mkdir(parents=True)
	fat.image.replace(path)
	disk = FatImage(path)
	for folder in (
		"ReactOS",
		"ReactOS/system32",
		"Documents and Settings",
		"Documents and Settings/Administrator",
		"Documents and Settings/Administrator/Desktop",
	):
		disk.make_directory(folder)
	for name, content in (("ReactOS/system32/user32.dll", b"stock"), ("ReactOS/system32/sol.exe", b"cards"), ("ReactOS/keep.txt", b"keep")):
		source = tmp_path / "f"
		source.write_bytes(content)
		disk.copy_in(source, name)
	for name in ("Applications Manager", "Command Prompt"):
		source = tmp_path / "f"
		source.write_bytes(b"lnk")
		disk.copy_in(source, f"Documents and Settings/Administrator/Desktop/{name}.lnk")
	return recipe, work, path


def test_the_pipeline_order_is_fixed_and_patchers_come_before_the_trim():
	assert image.PIPELINE.index("patchers") < image.PIPELINE.index("trim")
	assert image.PIPELINE[0] == "copy" and image.PIPELINE[-1] == "settings"


def test_the_plan_lists_the_steps_in_order_and_runs_nothing(compact_recipe_path, tmp_path, no_processes):
	plan = plan_image(recipe_module.load(compact_recipe_path), tmp_path / "work")
	text = plan.describe()
	assert text.index("patchers:") < text.index("trim profile") < text.index("files:") < text.index("settings:")
	assert "afterglow.pointers" in text and "126 entries" in text
	assert "regional-canada" in text and "pointer-defaults" in text
	assert "skipped" in plan_image(recipe_module.load(compact_recipe_path), tmp_path / "work", with_settings=False).describe()


def test_the_base_plan_removes_nothing(base_recipe_path, tmp_path, no_processes):
	text = plan_image(recipe_module.load(base_recipe_path), tmp_path / "work").describe()
	assert "trim profile 'none': 0 entries" in text


def test_the_cli_dry_run(base_recipe_path, tmp_path, no_processes, capsys):
	assert main(["image", str(base_recipe_path), "--dry-run", "--work", str(tmp_path / "work")]) == 0
	assert "steps, in this order" in capsys.readouterr().out
	assert not (tmp_path / "work").exists()


def test_a_missing_golden_disk_says_what_to_run(fake_iso_recipe, tmp_path):
	recipe, _, _ = fake_iso_recipe
	with pytest.raises(ImageError, match="rl install"):
		build_image(recipe, tmp_path / "work", with_settings=False)


def test_the_image_is_trimmed_and_dressed_and_the_golden_disk_is_untouched(golden, tmp_path, monkeypatch):
	recipe, work, golden_disk = golden
	profiles = tmp_path / "profiles"
	profiles.mkdir()
	(profiles / "tiny.txt").write_text("f ReactOS/system32/sol.exe\n")
	monkeypatch.setattr(trim, "PROFILES_DIR", profiles)
	recipe.data["trim"]["profile"] = "tiny"
	recipe.data["settings"]["remove_desktop_shortcuts"] = ["Applications Manager"]
	payload = tmp_path / "payload.txt"
	payload.write_bytes(b"payload")
	recipe.chain[0].parent.joinpath("payload.txt").write_bytes(b"payload")
	recipe.data["files"] = [{"source": "payload.txt", "destination": "Quill/PAYLOAD.TXT"}]
	recipe.data["shortcuts"] = [
		{
			"name": "Quill",
			"target": "C:\\Quill\\Q.EXE",
			"arguments": "",
			"working_dir": "",
			"description": "",
			"icon": "",
			"icon_index": 0,
			"show": 1,
		}
	]
	before = hashlib.sha256(golden_disk.read_bytes()).hexdigest()
	out = build_image(recipe, work, with_settings=False)
	disk = FatImage(out)
	assert not disk.exists("ReactOS/system32/sol.exe") and disk.exists("ReactOS/keep.txt")
	assert disk.read("Quill/PAYLOAD.TXT") == b"payload"
	assert disk.exists("Documents and Settings/Administrator/Desktop/Quill.lnk")
	assert not disk.exists("Documents and Settings/Administrator/Desktop/Applications Manager.lnk")
	assert disk.exists("Documents and Settings/Administrator/Desktop/Command Prompt.lnk")
	assert hashlib.sha256(golden_disk.read_bytes()).hexdigest() == before


def test_a_patched_file_is_written_before_the_trim_and_survives_it(golden, tmp_path, monkeypatch):
	recipe, work, _ = golden
	patched_file = tmp_path / "patched.bin"
	patched_file.write_bytes(b"patched")
	monkeypatch.setattr(recipe_module, "PATCHERS", ("test.patch",))
	monkeypatch.setattr(patchers, "PATCHERS", {"test.patch": lambda *args: [PatchedFile("ReactOS/system32/user32.dll", patched_file)]})
	monkeypatch.setattr(image, "run_patchers", lambda names, *args: patchers.PATCHERS[names[0]](*args))
	profiles = tmp_path / "profiles"
	profiles.mkdir()
	(profiles / "tiny.txt").write_text("f ReactOS/system32/sol.exe\n")
	monkeypatch.setattr(trim, "PROFILES_DIR", profiles)
	recipe.data["trim"]["profile"] = "tiny"
	recipe.data["patchers"]["list"] = ["test.patch"]
	out = build_image(recipe, work, with_settings=False)
	assert FatImage(out).read("ReactOS/system32/user32.dll") == b"patched"
	# A profile that lists the patched file is refused, and no image is left claiming success.
	(profiles / "tiny.txt").write_text("f ReactOS/system32/sol.exe\nf ReactOS/system32/user32.dll\n")
	with pytest.raises(TrimError, match="patched file"):
		build_image(recipe, work, out=work / "images" / "second.img", with_settings=False)


def test_a_profile_that_reaches_a_licence_file_stops_the_build_before_anything_runs(golden, tmp_path, monkeypatch):
	recipe, work, _ = golden
	profiles = tmp_path / "profiles"
	profiles.mkdir()
	(profiles / "bad.txt").write_text("f NOTICE.txt\n")
	monkeypatch.setattr(trim, "PROFILES_DIR", profiles)
	recipe.data["trim"]["profile"] = "bad"
	with pytest.raises(TrimError, match="licence file"):
		build_image(recipe, work, with_settings=False)
	assert not (work / "images").exists()


def test_the_output_may_not_be_the_golden_disk(golden):
	recipe, work, golden_disk = golden
	with pytest.raises(ImageError, match="golden"):
		build_image(recipe, work, out=golden_disk, with_settings=False)
