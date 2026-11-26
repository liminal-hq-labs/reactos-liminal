# Tests for the private QEMU helper. The live test starts a real, idle machine and is marked `qemu`.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import shutil
from pathlib import Path

import pytest

from reactos_liminal.vm import PrivateVm, VmError, VmSpec, key_for


def test_key_names():
	assert key_for("a") == "a"
	assert key_for("A") == "shift-a"
	assert key_for(" ") == "spc"
	assert key_for("\\") == "backslash"
	assert key_for(":") == "shift-semicolon"


def test_the_command_is_private_and_headless(tmp_path):
	vm = PrivateVm(tmp_path / "vm")
	command = vm.command(VmSpec(disk=Path("d.img"), cdrom=Path("c.iso"), boot_order="d", memory_mb=256, accel="tcg,thread=multi"))
	joined = " ".join(command)
	assert "-display none" in joined and "-nic none" in joined and "-daemonize" in command
	assert f"unix:{tmp_path / 'vm' / 'mon.sock'},server,nowait" in joined
	assert f"-pidfile {tmp_path / 'vm' / 'vm.pid'}" in joined
	assert "-m 256" in joined and "-accel tcg,thread=multi" in joined
	assert "format=raw" in joined and "-no-reboot" in command
	assert "-boot order=d" in joined


def test_the_machine_can_be_allowed_to_reboot(tmp_path):
	command = PrivateVm(tmp_path).command(VmSpec(disk=Path("d.img"), allow_reboot=True, accel="kvm"))
	assert "-no-reboot" not in command
	assert "-cdrom" not in command and not any("media=cdrom" in argument for argument in command)


def test_a_machine_that_was_never_started(tmp_path):
	vm = PrivateVm(tmp_path)
	assert not vm.running() and vm.pid() is None
	vm.stop()  # nothing to stop, and nothing else is touched
	with pytest.raises(VmError, match="cannot reach the monitor"):
		vm.monitor(["info status"])
	assert not vm.screenshot(tmp_path / "x.png")


def test_a_stale_pid_file_is_not_a_running_machine(tmp_path):
	(tmp_path / "vm.pid").write_text("999999999")
	assert not PrivateVm(tmp_path).running()


@pytest.mark.qemu
@pytest.mark.skipif(shutil.which("qemu-system-i386") is None, reason="needs QEMU")
def test_an_idle_machine_starts_answers_and_stops_by_its_own_pid(tmp_path):
	disk = tmp_path / "blank.img"
	with open(disk, "wb") as blank:
		blank.truncate(16 * 1024 * 1024)
	vm = PrivateVm(tmp_path / "vm")
	pid = vm.start(VmSpec(disk=disk, memory_mb=32, accel="tcg"))
	try:
		assert vm.running() and vm.pid() == pid
		assert "running" in vm.monitor(["info status"])
		assert vm.screenshot(tmp_path / "screen.png")
		assert (tmp_path / "screen.png").read_bytes().startswith(b"\x89PNG")
	finally:
		vm.stop()
	assert not vm.running()
