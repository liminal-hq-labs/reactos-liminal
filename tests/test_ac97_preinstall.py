# Tests for the pre-installed AC'97 driver: the registry file, the tool that makes it, and what CHANGES.txt says about it.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import importlib.util
import re

from reactos_liminal.licences import ChangeRecord, changes_text
from reactos_liminal.settings import REG_DIR, preinstalled_devices
from tests.conftest import REPO

REG = (REG_DIR / "ac97-preinstall.reg").read_text(encoding="utf-8")
CCS = "HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\"
SW = "HKEY_LOCAL_MACHINE\\SOFTWARE\\"


def _tool():
	spec = importlib.util.spec_from_file_location("make_ac97_reg", REPO / "tools" / "ac97" / "make-ac97-reg.py")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def _multi_strings(text: str) -> list[list[str]]:
	found = []
	for match in re.finditer(r'^"[^"]+"=hex\(7\):((?:[0-9a-f]{2},?\\?\n? *)+)', text, re.MULTILINE):
		raw = bytes(int(token, 16) for token in re.findall(r"[0-9a-f]{2}", match.group(1)))
		found.append(raw.decode("utf-16-le").rstrip("\0").split("\0"))
	return found


def test_the_file_has_the_registry_header_and_only_system_and_software_keys():
	assert REG.splitlines()[0] == "Windows Registry Editor Version 5.00"
	keys = re.findall(r"^\[(.+)\]$", REG, re.MULTILINE)
	assert keys and all(key.startswith((CCS, SW)) for key in keys)


def test_the_card_is_the_v86_one_not_the_qemu_one():
	keys = re.findall(r"^\[(.+)\]$", REG, re.MULTILINE)
	card = [key for key in keys if "\\Enum\\PCI\\VEN_8086&DEV_2415" in key]
	assert card and all("SUBSYS_00008086&REV_02" in key for key in card)
	assert any(key.endswith("\\3&7980b9c0&03") for key in card)  # the instance id v86's PCI bus gives slot 3, not QEMU's 3&609b8881
	assert not any("VEN_8086&DEV_2415&SUBSYS_11001AF4" in key for key in keys)
	assert any("PCI\\VEN_8086&DEV_2415&SUBSYS_00008086&REV_02" in rows for rows in _multi_strings(REG))


def test_the_other_devices_v86_has_are_in_the_file_too():
	for hardware in ("VEN_10EC&DEV_8029", "VEN_1234&DEV_1111", "VEN_8086&DEV_7010", "VEN_8086&DEV_1237"):
		assert f"\\Enum\\PCI\\{hardware}&" in REG
	assert "\\Enum\\IDE\\" in REG and "\\Enum\\ACPI\\" in REG


def test_winmm_finds_the_card_because_of_the_software_hive_entries():
	assert (
		'[HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Drivers32]\n"wave1"="C:\\\\ReactOS\\\\System32\\\\wdmaud.drv"'
		in REG
	)
	assert "[HKEY_LOCAL_MACHINE\\SOFTWARE\\Classes\\CLSID\\{17CCA71B-ECD7-11D0-B908-00A0C9223196}\\InprocServer32]" in REG
	assert "RunOnce" not in REG and "SessionInfo" not in REG and "ProfileList" not in REG
	assert '\\Device Parameters]\n"CLSID"' in REG and '"FriendlyName"="AC\'97 Sound Card"' in REG


def test_the_device_names_its_driver_and_class():
	assert '"Service"="ac97"' in REG
	assert '"Driver"="{4d36e96c-e325-11ce-bfc1-08002be10318}\\\\0000"' in REG
	assert "[" + CCS + "Services\\ac97]" in REG
	assert '"InfPath"="ac97.inf"' in REG


def test_the_audio_service_starts_by_itself():
	block = REG.split("[" + CCS + "Services\\AudioSrv]")[1].split("[")[0]
	assert '"Start"=dword:00000002' in block


def test_what_plug_and_play_writes_at_every_start_is_not_in_the_file():
	assert "\\LogConf" not in REG and "\\Enum\\PCI\\VEN_8086&DEV_2415&SUBSYS_00008086&REV_02\\3&7980b9c0&03\\Control" not in REG
	assert "AllocConfig" not in REG and "BootConfig" not in REG and "ServiceCurrent" not in REG
	device_class_keys = re.findall(r"^\[.+\\Control\\DeviceClasses\\(.+)\]$", REG, re.MULTILINE)
	assert device_class_keys and all(key.endswith("\\Device Parameters") for key in device_class_keys)


def test_the_listing_names_the_device_and_its_services():
	listing = preinstalled_devices(REG)
	assert "PCI\\VEN_8086&DEV_2415&SUBSYS_00008086&REV_02 (driver service ac97)" in listing
	assert {"service ac97", "service wdmaud", "service sysaudio", "service kmixer", "service swenum"} <= set(listing)


def test_changes_txt_lists_the_pre_installed_device_only_when_the_recipe_asks(base_recipe_path):
	from reactos_liminal.recipe import load

	recipe = load(base_recipe_path)
	plain = changes_text(recipe, ChangeRecord(settings_applied=True)).decode("ascii")
	assert "devices installed ahead of plug and play" not in plain
	recipe.data["settings"]["reg_files"] = [*recipe.data["settings"]["reg_files"], "ac97-preinstall"]
	text = changes_text(recipe, ChangeRecord(settings_applied=True)).decode("ascii")
	assert "devices installed ahead of plug and play" in text
	assert "PCI\\VEN_8086&DEV_2415&SUBSYS_00008086&REV_02 (driver service ac97)" in text


def test_the_tool_keeps_new_and_changed_keys_and_drops_runtime_ones():
	tool = _tool()
	pci = "Enum\\PCI\\VEN_8086&DEV_2415&SUBSYS_00008086&REV_02\\3&7980b9c0&03"
	before = {
		tool.PREFIX + "Services\\AudioSrv": {'"Start"': '"Start"=dword:00000003'},
		tool.PREFIX + "Services\\Pci": {'"Tag"': '"Tag"=dword:00000002'},
		tool.PREFIX + "Control\\ServiceCurrent": {"@": "@=dword:00000007"},
	}
	after = {
		tool.PREFIX + "Services\\AudioSrv": {'"Start"': '"Start"=dword:00000002'},
		tool.PREFIX + "Services\\Pci": {'"Tag"': '"Tag"=dword:00000002'},
		tool.PREFIX + "Control\\ServiceCurrent": {"@": "@=dword:00000008"},
		tool.PREFIX + pci: {'"Service"': '"Service"="ac97"', '"BootConfig"': '"BootConfig"=hex(8):01'},
		tool.PREFIX + pci + "\\LogConf": {'"BasicConfigVector"': '"BasicConfigVector"=hex(a):01'},
		tool.PREFIX + pci + "\\Control": {'"ActiveService"': '"ActiveService"="ac97"'},
		tool.PREFIX + "Control\\DeviceClasses\\{x}\\#Wave": {},
		tool.PREFIX + "Control\\DeviceClasses\\{x}\\#Wave\\Control": {'"Linked"': '"Linked"=dword:00000001'},
		tool.PREFIX + "Control\\DeviceClasses\\{x}\\#Wave\\Device Parameters": {'"FriendlyName"': '"FriendlyName"="AC\'97 Sound Card"'},
		tool.PREFIX + "Control\\Class\\{4d36e96c-e325-11ce-bfc1-08002be10318}\\0000": {'"Driver"': '"Driver"="ac97.sys"'},
	}
	software_before = {
		SW + "Microsoft\\Windows NT\\CurrentVersion\\Drivers32": {'"midi"': '"midi"="x"'},
		SW + "Microsoft\\Windows\\CurrentVersion\\RunOnce": {},
	}
	software_after = {
		SW + "Microsoft\\Windows NT\\CurrentVersion\\Drivers32": {'"midi"': '"midi"="x"', '"wave1"': '"wave1"="wdmaud.drv"'},
		SW + "Microsoft\\Windows\\CurrentVersion\\RunOnce": {'"WDM_WDMAUD"': '"WDM_WDMAUD"="rundll32"'},
		SW + "Microsoft\\Windows\\CurrentVersion\\Explorer\\SessionInfo\\1": {},
	}
	text = tool.build(before, after, (software_before, software_after))
	assert "SUBSYS_00008086&REV_02\\3&7980b9c0&03]" in text and '"Service"="ac97"' in text
	assert '"Start"=dword:00000002' in text and "Services\\Pci" not in text  # a changed value is kept, an unchanged key is not
	assert "BootConfig" not in text and "LogConf" not in text and "ActiveService" not in text and "ServiceCurrent" not in text
	assert "Linked" not in text and '"FriendlyName"="AC\'97 Sound Card"' in text
	assert '"Driver"="ac97.sys"' in text
	assert '"wave1"="wdmaud.drv"' in text and '"midi"' not in text and "RunOnce" not in text and "SessionInfo" not in text


def test_the_volume_control_file_shows_the_master_line_and_the_microphone_only():
	text = (REG_DIR / "ac97-volume-control.reg").read_text(encoding="utf-8")
	assert text.splitlines()[0] == "Windows Registry Editor Version 5.00"
	blocks = dict(re.findall(r"^\[.+\\AC'97 Sound Card\\(.+)\]\n\"LineStates\"=hex:((?:[0-9a-f,\\\n ]+))$", text, re.MULTILINE))
	assert set(blocks) == {"Volume Control", "Recording Control"}
	shown = {}
	for name, hexdump in blocks.items():
		raw = bytes(int(token, 16) for token in re.findall(r"[0-9a-f]{2}", hexdump.replace("\\\n", "")))
		assert len(raw) % 132 == 0  # a DWORD of flags and 64 UTF-16 characters, as sndvol32 reads them
		records = [
			(int.from_bytes(raw[at : at + 4], "little"), raw[at + 4 : at + 132].decode("utf-16-le").rstrip("\0"))
			for at in range(0, len(raw), 132)
		]
		assert records and all(flags == 0 for flags, _ in records), name  # a listed line is shown; a line not listed is hidden
		shown[name] = [line for _, line in records]
	assert shown == {"Volume Control": ["Volume Control"], "Recording Control": ["Microphone"]}
