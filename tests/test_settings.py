# Tests for the registry settings, the settings CD and the guest script.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import shutil
import subprocess

import pytest

from reactos_liminal import settings
from reactos_liminal.recipe import RecipeError, load


def test_display_values_are_dwords():
	text = settings.display_reg(1024, 768)
	assert text.count("Services\\bochsmp\\Device") == 2
	assert '"DefaultSettings.XResolution"=dword:00000400' in text
	assert '"DefaultSettings.YResolution"=dword:00000300' in text
	assert '"DefaultSettings.BitsPerPel"=dword:00000020' in text


def test_appearance_with_and_without_a_wallpaper():
	plain = settings.appearance_reg(48, None)
	assert '"Shell Icon Size"="48"' in plain and "Wallpaper" not in plain
	with_wallpaper = settings.appearance_reg(32, "C:\\ReactOS\\Web\\Wallpaper\\X.bmp")
	assert '"Wallpaper"="C:\\\\ReactOS\\\\Web\\\\Wallpaper\\\\X.bmp"' in with_wallpaper
	assert '"WallpaperStyle"="2"' in with_wallpaper


def test_the_recipe_chooses_the_static_files(fake_iso_recipe, tmp_path):
	recipe, _, _ = fake_iso_recipe
	recipe.data["settings"]["reg_files"] = ["display", "mouse-linear", "hide-desktop-icons"]
	names = list(settings.settings_files(recipe))
	assert names == ["display", "appearance", "mouse-linear", "hide-desktop-icons"]
	files = tmp_path / "ag"
	files.mkdir()
	(files / "afterglow.reg").write_text("A")
	(files / "pointers.reg").write_text("P")
	assert list(settings.settings_files(recipe, files))[-2:] == ["afterglow-afterglow", "afterglow-pointers"]


def test_every_static_reg_file_is_a_registry_file_with_a_header():
	for name in settings.STATIC_REG_FILES:
		text = (settings.REG_DIR / f"{name}.reg").read_text()
		assert text.startswith("Windows Registry Editor Version 5.00")
		assert "SPDX-License-Identifier: Apache-2.0 OR MIT" in text


def test_an_unknown_reg_file_is_refused_by_the_recipe(base_recipe_path, tmp_path):
	path = tmp_path / "r.toml"
	path.write_text(base_recipe_path.read_text().replace('reg_files = ["display", "quiet", "watermark-off"]', 'reg_files = ["nope"]'))
	with pytest.raises(RecipeError, match="reg_files"):
		load(path)


def test_cd_names_fit_eight_dot_three():
	assert settings.cd_file_name(3, "hide-desktop-icons") == "03_HIDED.REG"
	assert settings.cd_file_name(1, "display") == "01_DISPL.REG"


def test_the_apply_script_takes_the_page_file():
	script = settings.apply_script("128 256")
	assert '/d "C:\\pagefile.sys 128 256"' in script
	assert "@PAGE_FILE@" not in script and "shutdown -s -t 0" in script


def test_the_cd_tree_has_crlf_files_and_the_script(fake_iso_recipe, tmp_path):
	recipe, _, _ = fake_iso_recipe
	tree = tmp_path / "cd"
	names = settings.write_settings_cd_tree(recipe, tree)
	assert names[0] == "01_DISPL.REG"
	assert b"\r\n" in (tree / names[0]).read_bytes() and b"\n\n" not in (tree / names[0]).read_bytes().replace(b"\r\n", b"")
	assert (tree / "APPLY.CMD").read_bytes().startswith(b"@echo off\r\n")


@pytest.mark.skipif(shutil.which("xorriso") is None, reason="needs xorriso")
def test_the_settings_iso_holds_the_files(fake_iso_recipe, tmp_path):
	recipe, _, _ = fake_iso_recipe
	tree = tmp_path / "cd"
	settings.write_settings_cd_tree(recipe, tree)
	iso = tmp_path / "setup.iso"
	settings.make_settings_iso(tree, iso)
	listing = subprocess.run(["xorriso", "-indev", str(iso), "-find", "/", "-type", "f"], capture_output=True, text=True, check=True).stdout
	assert "APPLY.CMD" in listing.upper() and ".REG" in listing.upper()


def test_the_build_vm_runs_small_and_safe(tmp_path):
	spec = settings.build_vm_spec(tmp_path / "a.img", tmp_path / "s.iso", "kvm")
	assert spec.memory_mb == 256 and spec.disk_cache == "writethrough" and spec.cdrom == tmp_path / "s.iso"
