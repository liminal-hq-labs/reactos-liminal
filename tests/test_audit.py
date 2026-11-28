# Tests for the shortcut and registry audit, on a small FAT image made in the test with links and hives written here.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import shutil

import pytest
from hive_fixture import build_hive, expand, key, sz

from reactos_liminal.audit import DEAD, ICON_MISSING, OK, UNCHECKED, Disk, audit_image, command_target, parse_ini
from reactos_liminal.cli import main
from reactos_liminal.lnk import make_lnk

pytestmark = pytest.mark.skipif(shutil.which("mformat") is None, reason="needs mtools")

USER = "Documents and Settings/Administrator"
MENU = f"{USER}/Start Menu/Programs"


def put(fat, tmp_path, path, data):
	"""Write `data` to `path` on the image, making the folders."""
	folder = ""
	for part in path.split("/")[:-1]:
		folder = f"{folder}/{part}".strip("/")
		fat.make_directory(folder)
	source = tmp_path / "upload.bin"
	source.write_bytes(data)
	fat.copy_in(source, path)


def statuses(report, kind):
	"""The statuses of one kind, in the order found."""
	return [finding.status for finding in report.findings if finding.kind == kind]


@pytest.fixture
def disk(fat, tmp_path):
	for program in ("notepad.exe", "cmd.exe", "console.dll", "calc.exe"):
		put(fat, tmp_path, f"ReactOS/system32/{program}", b"MZ")
	put(fat, tmp_path, "ReactOS/Fonts/ok.ttf", b"x")
	return fat


def test_a_shortcut_to_a_missing_program_is_dead_and_one_to_a_present_program_is_ok(disk, tmp_path):
	put(disk, tmp_path, f"{MENU}/Notepad.lnk", make_lnk("C:\\ReactOS\\system32\\notepad.exe"))
	put(disk, tmp_path, f"{MENU}/Games/WineMine.lnk", make_lnk("C:\\ReactOS\\system32\\winmine.exe"))
	put(disk, tmp_path, f"{MENU}/Env.lnk", make_lnk("%SystemRoot%\\system32\\CALC.EXE"))
	report = audit_image(disk)
	assert sorted(statuses(report, "shortcut")) == sorted([OK, DEAD, OK])
	assert [finding.where for finding in report.dead] == [f"{MENU}/Games/WineMine.lnk"]


def test_a_link_whose_icon_file_is_missing_is_reported_apart_from_a_dead_one(disk, tmp_path):
	put(disk, tmp_path, f"{MENU}/Notepad.lnk", make_lnk("C:\\ReactOS\\system32\\notepad.exe", icon="C:\\ReactOS\\system32\\gone.dll"))
	report = audit_image(disk)
	assert [finding.status for finding in report.findings] == [OK, ICON_MISSING] and not report.dead


def test_links_outside_the_menus_are_listed_but_named_elsewhere(disk, tmp_path):
	put(disk, tmp_path, "Program Files/tool/tool.lnk", make_lnk("C:\\Program Files\\tool\\tool.exe"))
	report = audit_image(disk)
	assert [(finding.kind, finding.status) for finding in report.findings] == [("shortcut (elsewhere)", DEAD)]
	assert not report.blocking()  # a link a user does not see in a menu does not fail the audit, unless strict
	assert report.blocking(strict=True)


def test_a_file_that_is_not_a_link_is_unchecked_not_a_crash(disk, tmp_path):
	put(disk, tmp_path, f"{MENU}/Broken.lnk", b"garbage")
	assert audit_image(disk).findings[0].status == UNCHECKED


def test_registry_launch_points_are_checked_in_the_software_hive(disk, tmp_path):
	hive = build_hive(
		{
			"Microsoft": key(
				{},
				{
					"Windows": key(
						{},
						{
							"CurrentVersion": key(
								{},
								{
									"Run": key(
										{"Good": sz('"C:\\ReactOS\\system32\\cmd.exe" /k'), "Bad": sz("C:\\ReactOS\\system32\\gone.exe -q")}
									),
									"App Paths": key({}, {"wordpad.exe": key({"": sz("%SystemRoot%\\system32\\wordpad.exe")})}),
									"Control Panel": key({}, {"Cpls": key({"Console": expand("%SystemRoot%\\system32\\console.dll")})}),
									"Uninstall": key({}, {"App": key({"UninstallString": sz("C:\\Program Files\\App\\uninst.exe /S")})}),
								},
							)
						},
					),
					"Windows NT": key(
						{},
						{"CurrentVersion": key({}, {"Winlogon": key({"Shell": sz("explorer.exe"), "Userinit": sz("userinit.exe,")})})},
					),
				},
			),
			"Classes": key(
				{},
				{
					"rtffile": key(
						{}, {"shell": key({}, {"open": key({}, {"command": key({"": sz('C:\\ReactOS\\system32\\wordpad.exe "%1"')})})})}
					),
					"exefile": key({}, {"shell": key({}, {"open": key({}, {"command": key({"": sz('"%1" %*')})})})}),
				},
			),
		}
	)
	put(disk, tmp_path, "ReactOS/system32/config/SOFTWARE", hive)
	report = audit_image(disk)
	assert statuses(report, "run") == [OK, DEAD]
	assert statuses(report, "app path") == [DEAD]
	assert statuses(report, "applet") == [OK]
	assert statuses(report, "uninstall") == [DEAD]
	assert statuses(report, "winlogon") == [DEAD, DEAD]
	assert sorted(statuses(report, "association")) == [DEAD, UNCHECKED]
	assert {finding.kind for finding in report.blocking()} == {"run", "winlogon"}
	assert {finding.kind for finding in report.blocking(strict=True)} >= {"app path", "association", "uninstall"}


def test_the_font_list_is_checked_against_the_fonts_folder(disk, tmp_path):
	hive = build_hive(
		{
			"Microsoft": key(
				{},
				{
					"Windows NT": key(
						{},
						{"CurrentVersion": key({}, {"Fonts": key({"Good (TrueType)": sz("ok.ttf"), "Gone (TrueType)": sz("gone.ttf")})})},
					)
				},
			)
		}
	)
	put(disk, tmp_path, "ReactOS/system32/config/SOFTWARE", hive)
	assert statuses(audit_image(disk), "font") == [OK, DEAD]


def test_a_desktop_ini_that_names_a_missing_icon_is_dead(disk, tmp_path):
	put(disk, tmp_path, "Data/desktop.ini", b"[.ShellClassInfo]\r\nIconFile=%SystemRoot%\\system32\\gone.dll\r\nIconIndex=3\r\n")
	put(disk, tmp_path, "More/desktop.ini", "[.ShellClassInfo]\r\nIconResource=C:\\ReactOS\\system32\\cmd.exe,0\r\n".encode("utf-16"))
	assert [(finding.kind, finding.status) for finding in audit_image(disk).findings] == [("desktop.ini", DEAD), ("desktop.ini", OK)]


def test_resolving_a_path(disk):
	checker = Disk(disk)
	assert checker.resolve("C:\\ReactOS\\system32\\CMD.EXE")[0] == OK
	assert checker.resolve("cmd.exe")[0] == OK  # found on the guest's PATH
	assert checker.resolve("nothing.exe")[0] == DEAD
	assert checker.resolve("D:\\setup.exe")[0] == UNCHECKED
	assert checker.resolve("%USERPROFILE%\\x.exe")[0] == UNCHECKED
	assert checker.resolve("http://example.test/")[0] == UNCHECKED


@pytest.mark.parametrize(
	("command", "target"),
	[
		('"C:\\Program Files\\A B\\a.exe" /x', "C:\\Program Files\\A B\\a.exe"),
		("C:\\Program Files\\A B\\a.exe /x", "C:\\Program Files\\A B\\a.exe"),
		("rundll32.exe shell32.dll,Control_RunDLL", "rundll32.exe"),
		("userinit", "userinit"),
		("", ""),
	],
)
def test_the_file_a_command_runs(command, target):
	assert command_target(command) == target


def test_ini_pairs_are_lower_cased_and_sections_ignored():
	assert parse_ini("[A]\nIconFile = x.dll\nIconIndex=1\n") == {"iconfile": "x.dll", "iconindex": "1"}


def test_the_report_names_the_dead_entries_and_counts_the_rest(disk, tmp_path):
	put(disk, tmp_path, f"{MENU}/Games/WineMine.lnk", make_lnk("C:\\ReactOS\\system32\\winmine.exe"))
	put(disk, tmp_path, f"{MENU}/Notepad.lnk", make_lnk("C:\\ReactOS\\system32\\notepad.exe"))
	text = audit_image(disk).render("Audit")
	assert text.startswith("# Audit") and "**1 ok**, **1 dead**" in text
	assert f"`{MENU}/Games/WineMine.lnk`" in text and "| shortcut | 1 | 1 | 0 | 0 |" in text


def test_the_command_fails_on_a_dead_shortcut_and_passes_on_a_clean_image(disk, tmp_path, capsys):
	put(disk, tmp_path, f"{MENU}/Notepad.lnk", make_lnk("C:\\ReactOS\\system32\\notepad.exe"))
	assert main(["audit", str(disk.image)]) == 0
	put(disk, tmp_path, f"{MENU}/WineMine.lnk", make_lnk("C:\\ReactOS\\system32\\winmine.exe"))
	assert main(["audit", str(disk.image), "--out", str(tmp_path / "report.md")]) == 1
	assert "WineMine.lnk" in capsys.readouterr().err and "1 dead" in (tmp_path / "report.md").read_text()


def test_the_command_refuses_a_missing_image(tmp_path, capsys):
	assert main(["audit", str(tmp_path / "none.img")]) == 2
	assert "no such image" in capsys.readouterr().err


def _system_hive(bound=True, image_path="system32\\drivers\\ac97.sys"):
	device = {"Service": sz("ac97"), "Class": sz("MEDIA")} if bound else {"Class": sz("MEDIA")}
	pci = key({}, {"VEN_8086&DEV_2415&SUBSYS_00008086&REV_02": key({}, {"3&609b8881&03": key(device)})})
	return build_hive(
		{
			"ControlSet001": key(
				{},
				{
					"Enum": key({}, {"PCI": pci}),
					"Services": key({}, {"ac97": key({"ImagePath": expand(image_path)})}),
				},
			)
		}
	)


def test_a_pre_installed_device_with_its_driver_on_the_disk_is_ok(disk, tmp_path):
	put(disk, tmp_path, "ReactOS/system32/drivers/ac97.sys", b"MZ")
	put(disk, tmp_path, "ReactOS/system32/config/SYSTEM", _system_hive())
	report = audit_image(disk, expected_devices=("PCI\\VEN_8086&DEV_2415",))
	assert statuses(report, "device") == [OK]
	assert statuses(report, "preinstalled device") == []
	assert not report.blocking()


def test_a_device_whose_driver_was_trimmed_is_dead_but_not_blocking_unless_expected(disk, tmp_path):
	put(disk, tmp_path, "ReactOS/system32/config/SYSTEM", _system_hive())
	report = audit_image(disk)
	assert statuses(report, "device") == [DEAD]
	assert not report.blocking() and report.blocking(strict=True)


def test_an_expected_device_that_is_not_bound_fails_the_audit(disk, tmp_path):
	put(disk, tmp_path, "ReactOS/system32/config/SYSTEM", _system_hive(bound=False))
	report = audit_image(disk, expected_devices=("PCI\\VEN_8086&DEV_2415",))
	assert statuses(report, "preinstalled device") == [DEAD]
	assert report.blocking()


def test_the_recipe_that_lists_the_pre_install_expects_the_card(base_recipe_path):
	from reactos_liminal.audit import expected_devices
	from reactos_liminal.recipe import load

	recipe = load(base_recipe_path)
	assert expected_devices(recipe) == ()
	recipe.data["settings"]["reg_files"] = [*recipe.data["settings"]["reg_files"], "ac97-preinstall"]
	assert expected_devices(recipe) == ("PCI\\VEN_8086&DEV_2415",)
