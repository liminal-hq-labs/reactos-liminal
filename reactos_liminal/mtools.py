# Read and write the FAT32 partition of a raw disk image with mtools, without mounting it.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import os
import re
import subprocess
from pathlib import Path

PARTITION_OFFSET = 1048576  # the install puts the one partition at 1 MiB


class MtoolsError(Exception):
	"""An mtools command that failed."""


class FatImage:
	"""The first partition of a raw disk image. Paths are inside the partition, with forward slashes: `ReactOS/system32/user32.dll`."""

	def __init__(self, image: Path, offset: int = PARTITION_OFFSET):
		self.image = Path(image)
		self.spec = f"{self.image}@@{offset}"
		self.env = dict(os.environ, MTOOLS_SKIP_CHECK="1")

	def run(self, tool: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
		done = subprocess.run([tool, "-i", self.spec, *args], capture_output=True, env=self.env, check=False)
		if check and done.returncode != 0:
			message = (done.stderr or done.stdout).decode(errors="replace").strip()
			raise MtoolsError(f"{tool} {' '.join(args)}: {message}")
		return done

	def exists(self, path: str) -> bool:
		return self.run("mdir", "-a", f"::/{path}", check=False).returncode == 0

	def read(self, path: str) -> bytes:
		return self.run("mtype", f"::/{path}").stdout

	def copy_out(self, path: str, destination: Path) -> None:
		self.run("mcopy", "-n", f"::/{path}", str(destination))

	def copy_in(self, source: Path, path: str) -> None:
		self.run("mcopy", "-o", str(source), f"::/{path}")

	def make_directory(self, path: str) -> None:
		self.run("mmd", f"::/{path}", check=False)  # an existing folder is fine

	def delete_file(self, path: str) -> bool:
		return self.run("mdel", f"::/{path}", check=False).returncode == 0

	def delete_tree(self, path: str) -> bool:
		return self.run("mdeltree", f"::/{path}", check=False).returncode == 0

	def set_attributes(self, path: str, flags: str) -> None:
		"""`flags` as for mattrib, for example "-r -h -s" or "+h +s"."""
		self.run("mattrib", *flags.split(), f"::/{path}", check=False)

	def free_bytes(self) -> int:
		listing = self.run("mdir", "::/").stdout.decode(errors="replace")
		match = re.search(r"([\d ,.]+) bytes free", listing)
		if not match:
			raise MtoolsError("mdir did not report the free space")
		return int(re.sub(r"\D", "", match.group(1)))
