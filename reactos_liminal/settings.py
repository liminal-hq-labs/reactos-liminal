# The registry settings and the build VM run that applies them inside the guest.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# The settings go on a small CD as .reg files with a command script. The build VM boots the image with that CD in drive D:, the Run box
# starts the script, and the script applies every file and shuts the guest down so the disk is clean.
import re
import subprocess
import time
from pathlib import Path

from .log import log
from .paths import REPO
from .recipe import REG_FILES, Recipe, is_reg_path
from .sounds import scheme_reg
from .vm import PrivateVm, VmError, VmSpec, default_accel

REG_DIR = REPO / "guest" / "reg"
APPLY_TEMPLATE = REPO / "guest" / "cmd" / "apply-settings.cmd.in"
# Static files in guest/reg that a recipe may name in `settings.reg_files`; "display" is made from the recipe's display values.
STATIC_REG_FILES = tuple(name for name in REG_FILES if name != "display")
HEADER = "Windows Registry Editor Version 5.00\n"


class SettingsError(Exception):
	"""A settings file that cannot be made, or a build VM run that did not finish."""


def _dword(number: int) -> str:
	return f"dword:{number:08x}"


def display_reg(width: int, height: int) -> str:
	"""1024 x 768 on the Bochs-style adapter v86 and QEMU provide (bochsmp). The driver offers 32 bits only, so a 16-bit default cannot
	be set."""
	section = (
		f'"DefaultSettings.BitsPerPel"={_dword(32)}\n'
		f'"DefaultSettings.XResolution"={_dword(width)}\n'
		f'"DefaultSettings.YResolution"={_dword(height)}\n'
		f'"DefaultSettings.VRefresh"={_dword(1)}\n'
	)
	keys = "HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\bochsmp"
	return f"{HEADER}\n; Display, from the recipe.\n[{keys}\\Device0]\n{section}\n[{keys}\\Device1]\n{section}"


WALLPAPER_STYLES = {
	"centre": ("0", "0"),
	"tile": ("0", "1"),
	"stretch": ("2", "0"),
	"fit": ("6", "0"),
	"fill": ("10", "0"),
}  # WallpaperStyle, TileWallpaper


def appearance_reg(icon_size: int, wallpaper: str | None, style: str = "fill") -> str:
	"""Desktop icon size (the small icons in menus and the taskbar stay 16 px) and, when the recipe sets one, the wallpaper in the style
	the recipe names: filled (the default), stretched, fitted, centred or tiled. The user gets the wallpaper and the style; `HKU\\.DEFAULT`
	gets the style as well, so a profile made from it has the same placement."""
	metrics = "HKEY_CURRENT_USER\\Control Panel\\Desktop\\WindowMetrics"
	text = f'{HEADER}\n; Appearance, from the recipe.\n[{metrics}]\n"Shell Icon Size"="{icon_size}"\n'
	if wallpaper:
		escaped = wallpaper.replace("\\", "\\\\")
		wallpaper_style, tile = WALLPAPER_STYLES[style]
		text += (
			f'\n[HKEY_CURRENT_USER\\Control Panel\\Desktop]\n"Wallpaper"="{escaped}"\n'
			f'"WallpaperStyle"="{wallpaper_style}"\n"TileWallpaper"="{tile}"\n'
			f'\n[HKEY_USERS\\.DEFAULT\\Control Panel\\Desktop]\n"WallpaperStyle"="{wallpaper_style}"\n"TileWallpaper"="{tile}"\n'
		)
	return text


def _own_reg_key(path: Path, taken: dict[str, str]) -> str:
	"""A name for a recipe's own registry file that no other file in the list has."""
	key = path.stem
	number = 2
	while key in taken or key in REG_FILES:
		key = f"{path.stem}-{number}"
		number += 1
	return key


def settings_files(recipe: Recipe, afterglow_files: Path | None = None) -> dict[str, str]:
	"""The registry files to apply, in order, as `{name: text}`: the recipe's own settings, the static files it lists, and the
	Afterglow files that select the style and the pointer scheme."""
	settings = recipe.section("settings")
	if "afterglow-logon" in settings["reg_files"] and "afterglow.logon" not in recipe.section("patchers", "list"):
		raise SettingsError("settings.reg_files names afterglow-logon, which selects agmsgina.dll, but patchers.list lacks afterglow.logon")
	files = {"display": display_reg(settings["display_width"], settings["display_height"])}
	files["appearance"] = appearance_reg(settings["icon_size"], settings.get("wallpaper"), settings["wallpaper_style"])
	for name in settings["reg_files"]:
		if name == "display":
			continue
		if is_reg_path(name):  # a file beside a recipe, applied after the named files
			files[_own_reg_key(Path(name), files)] = Path(name).read_text(encoding="utf-8-sig")
			continue
		files[name] = (REG_DIR / f"{name}.reg").read_text(encoding="utf-8")
	if recipe.section("sounds", "scheme"):
		files["afterglow-sounds"] = scheme_reg()
	if "afterglow.start" in recipe.section("patchers", "list"):
		files["shell-agexplorer"] = (REG_DIR / "shell-agexplorer.reg").read_text(encoding="utf-8")
	if afterglow_files is not None:
		for name in ("afterglow", "pointers"):
			path = afterglow_files / f"{name}.reg"
			if path.is_file():
				files[f"afterglow-{name}"] = path.read_text(encoding="utf-8", errors="replace")
	return files


def cd_file_name(index: int, name: str) -> str:
	stem = re.sub(r"[^A-Za-z0-9]", "", name)[:5].upper()
	return f"{index:02d}_{stem}.REG"


def apply_script(page_file: str) -> str:
	return APPLY_TEMPLATE.read_text(encoding="utf-8").replace("@PAGE_FILE@", page_file)


def write_settings_cd_tree(recipe: Recipe, tree: Path, afterglow_files: Path | None = None) -> list[str]:
	"""Write the files for the settings CD into `tree` and return their CD names. Registry files are CRLF text."""
	tree.mkdir(parents=True, exist_ok=True)
	names = []
	for index, (name, text) in enumerate(settings_files(recipe, afterglow_files).items(), 1):
		cd_name = cd_file_name(index, name)
		(tree / cd_name).write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
		names.append(cd_name)
	script = apply_script(recipe.section("settings", "page_file"))
	(tree / "APPLY.CMD").write_bytes(script.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii"))
	return names


def make_settings_iso(tree: Path, iso: Path) -> None:
	iso.unlink(missing_ok=True)
	done = subprocess.run(
		["xorriso", "-as", "mkisofs", "-quiet", "-V", "SETUP", "-o", str(iso), str(tree)], capture_output=True, text=True, check=False
	)
	if done.returncode != 0:
		raise SettingsError(f"xorriso could not make the settings CD: {done.stderr.strip()}")


def build_vm_spec(image: Path, settings_iso: Path, accel: str | None = None) -> VmSpec:
	return VmSpec(disk=image, cdrom=settings_iso, memory_mb=256, accel=accel or default_accel(), disk_cache="writethrough")


def apply_in_guest(vm: PrivateVm, spec: VmSpec, boot_wait: int | None = None) -> None:
	"""Boot the image with the settings CD, run APPLY.CMD from the Run box and wait for the guest to shut itself down. The first Run
	box after a boot is sometimes ignored, so the command is sent again until the script reports."""
	fast = spec.accel == "kvm"
	wait = boot_wait or (60 if fast else 400)
	vm.start(spec)
	try:
		time.sleep(wait)
		for attempt in range(1, 5):
			vm.run_dialog("cmd /c D:\\APPLY.CMD")
			time.sleep(max(wait // 4, 15))
			if b"apply: start" in vm.serial_path.read_bytes():
				break
			log("settings", f"the Run box did not take it (try {attempt}), sending again")
		if not vm.wait_exit(wait * 3):
			raise SettingsError("the build VM did not shut down after the settings were applied")
	except VmError as error:
		raise SettingsError(str(error)) from error
	finally:
		vm.stop()
	report = vm.serial_path.read_text(errors="replace")
	if "apply: done" not in report:
		raise SettingsError("the settings were not applied; the script did not report done")
	log("settings", "applied: " + ", ".join(line.strip() for line in report.splitlines() if line.startswith("apply:"))[:200])
