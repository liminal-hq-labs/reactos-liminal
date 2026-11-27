# A private QEMU machine: its own monitor socket, pid file, log and serial file in its own directory, stopped through its monitor or
# its own pid and never by a process name. Screenshots come from the monitor's `screendump`, never from the host's screen.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import contextlib
import os
import shutil
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .ppm import ppm_to_png

# Characters the monitor's `sendkey` names differently from the character itself.
KEY_NAMES = {
	" ": "spc",
	"\\": "backslash",
	".": "dot",
	":": "shift-semicolon",
	"/": "slash",
	"-": "minus",
	"_": "shift-minus",
	",": "comma",
	">": "shift-dot",
	"&": "shift-7",
	'"': "shift-apostrophe",
	"=": "equal",
	"(": "shift-9",
	")": "shift-0",
	"%": "shift-5",
	";": "semicolon",
}


class VmError(Exception):
	"""The machine did not start, did not answer or did not stop."""


def default_accel() -> str:
	return "kvm" if os.access("/dev/kvm", os.W_OK) else "tcg,thread=multi"


def key_for(character: str) -> str:
	if character in KEY_NAMES:
		return KEY_NAMES[character]
	if character.isupper():
		return "shift-" + character.lower()
	return character


@dataclass
class VmSpec:
	"""What to run: one raw disk, an optional CD and how it boots."""

	disk: Path
	cdrom: Path | None = None
	boot_order: str | None = None  # "c" disk, "d" CD
	memory_mb: int = 768
	accel: str = ""
	disk_cache: str = "writeback"
	allow_reboot: bool = False  # False: a guest restart ends the run, which is how each install stage finishes


class PrivateVm:
	"""One QEMU process, kept in `directory`: mon.sock, vm.pid, vm.log and serial.txt."""

	def __init__(self, directory: Path):
		self.directory = Path(directory)
		self.socket_path = self.directory / "mon.sock"
		self.pid_path = self.directory / "vm.pid"
		self.log_path = self.directory / "vm.log"
		self.serial_path = self.directory / "serial.txt"
		self.executable = self.directory / "vmbox"

	def command(self, spec: VmSpec, qemu: str = "qemu-system-i386") -> list[str]:
		"""The full QEMU command line. A pure function, so a dry run can print it."""
		accel = spec.accel or default_accel()
		argv = [
			str(self.executable) if self.executable.exists() else qemu,
			*["-accel", accel],
			*["-machine", "pc", "-cpu", "pentium3", "-m", str(spec.memory_mb)],
			*["-vga", "std", "-nic", "none", "-display", "none"],
			*["-drive", f"file={spec.disk},format=raw,if=ide,index=0,cache={spec.disk_cache}"],
		]
		if spec.cdrom is not None:
			argv += ["-drive", f"file={spec.cdrom},media=cdrom,readonly=on,index=2"]
		if spec.boot_order:
			argv += ["-boot", f"order={spec.boot_order}"]
		argv += [
			*["-monitor", f"unix:{self.socket_path},server,nowait"],
			*["-pidfile", str(self.pid_path), "-D", str(self.log_path)],
			*["-serial", f"file:{self.serial_path}", "-daemonize"],
		]
		if not spec.allow_reboot:
			argv.append("-no-reboot")
		return argv

	def start(self, spec: VmSpec, qemu: str = "qemu-system-i386") -> int:
		"""Start the machine and return its pid. The binary is reached through a link called `vmbox`, a name no tool that kills by
		process name will match."""
		self.directory.mkdir(parents=True, exist_ok=True)
		if self.running():
			raise VmError(f"a machine is already running in {self.directory} (pid {self.pid()})")
		for stale in (self.socket_path, self.pid_path, self.serial_path):
			stale.unlink(missing_ok=True)
		binary = shutil.which(qemu)
		if binary is None:
			raise VmError(f"{qemu} is not installed")
		self.executable.unlink(missing_ok=True)
		self.executable.symlink_to(binary)
		done = subprocess.run(self.command(spec, qemu), capture_output=True, text=True, check=False)
		if done.returncode != 0:
			raise VmError(f"QEMU did not start: {(done.stderr or done.stdout).strip()}")
		return self._wait_for_pid()

	def _wait_for_pid(self) -> int:
		for _ in range(100):
			if self.pid_path.exists() and self.pid_path.read_text().strip():
				return int(self.pid_path.read_text())
			time.sleep(0.1)
		raise VmError("QEMU wrote no pid file")

	def pid(self) -> int | None:
		try:
			return int(self.pid_path.read_text())
		except (OSError, ValueError):
			return None

	def running(self) -> bool:
		pid = self.pid()
		if pid is None:
			return False
		try:
			os.kill(pid, 0)
		except ProcessLookupError:
			return False
		except PermissionError:
			return True
		return True

	def monitor(self, commands: list[str], pause: float = 0.15) -> str:
		"""Send monitor commands in order and return what the monitor printed."""
		connection = socket.socket(socket.AF_UNIX)
		connection.settimeout(0.3)
		try:
			connection.connect(str(self.socket_path))
		except OSError as error:
			raise VmError(f"cannot reach the monitor at {self.socket_path}: {error}") from error
		output = []
		try:
			with contextlib.suppress(OSError):
				output.append(connection.recv(4096).decode(errors="replace"))
			for command in commands:
				connection.sendall(command.encode() + b"\n")
				time.sleep(pause)
				with contextlib.suppress(OSError):
					output.append(connection.recv(65536).decode(errors="replace"))
		finally:
			connection.close()
		return "".join(output)

	def screenshot(self, destination: Path) -> bool:
		"""A PNG of the guest's screen from the monitor's screendump. False when the machine is not answering."""
		ppm_path = self.directory / "screen.ppm"
		ppm_path.unlink(missing_ok=True)
		try:
			self.monitor([f"screendump {ppm_path}"], pause=0.5)
			for _ in range(20):
				if ppm_path.exists() and ppm_path.stat().st_size > 0:
					break
				time.sleep(0.1)
			time.sleep(0.2)
			ppm_to_png(ppm_path, destination)
		except (VmError, ValueError, OSError):
			return False
		return True

	def type_text(self, text: str, key_pause: float = 0.12) -> None:
		"""Type a string one key at a time (a burst crashes the Run box)."""
		for character in text:
			self.monitor([f"sendkey {key_for(character)}"], pause=key_pause)

	def run_dialog(self, command: str) -> None:
		"""Win+R, the command, Enter."""
		self.monitor(["sendkey meta_l-r"])
		time.sleep(3.5)
		self.type_text(command)
		time.sleep(0.5)
		self.monitor(["sendkey ret"])

	def wait_exit(self, timeout: float) -> bool:
		"""Wait for the guest to end itself (its own shutdown or restart). False on timeout."""
		deadline = time.monotonic() + timeout
		while self.running():
			if time.monotonic() > deadline:
				return False
			time.sleep(1)
		return True

	def stop(self, grace: float = 10.0) -> None:
		"""Quit through the monitor; if the process is still there, end this machine's own pid. Never by name."""
		if not self.running():
			return
		with contextlib.suppress(VmError):
			self.monitor(["quit"], pause=0.2)
		if self.wait_exit(grace):
			return
		pid = self.pid()
		if pid is not None:
			try:
				os.kill(pid, signal.SIGTERM)
			except ProcessLookupError:
				return
			self.wait_exit(grace)
