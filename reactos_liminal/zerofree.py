# Zero every free cluster of the FAT32 partition in a raw disk image, then punch holes so the image is sparse again. Deleted files
# leave their data behind; zeroing it lets the image compress and split into tiny parts.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .mtools import PARTITION_OFFSET

FAT32_ENTRY_MASK = 0x0FFFFFFF


class ZeroFreeError(Exception):
	"""The partition is not a FAT32 volume this can read."""


@dataclass(frozen=True)
class ZeroFreeResult:
	free_clusters: int
	zeroed_clusters: int
	cluster_bytes: int

	@property
	def zeroed_mib(self) -> float:
		return self.zeroed_clusters * self.cluster_bytes / 2**20


def zero_free_clusters(image: Path, partition_offset: int = PARTITION_OFFSET) -> ZeroFreeResult:
	"""Zero the data of every free cluster. Only the free clusters are written; files, directories and the FAT are untouched."""
	with open(image, "r+b") as disk:
		disk.seek(partition_offset)
		boot_sector = disk.read(512)
		if len(boot_sector) < 512 or boot_sector[510:512] != b"\x55\xaa":
			raise ZeroFreeError("no boot sector at the partition offset")
		bytes_per_sector, sectors_per_cluster, reserved_sectors, fat_count = struct.unpack("<HBHB", boot_sector[11:17])
		# A small volume records its size in the 16-bit field and leaves the 32-bit one zero.
		total_sectors = struct.unpack("<H", boot_sector[19:21])[0] or struct.unpack("<I", boot_sector[32:36])[0]
		sectors_per_fat = struct.unpack("<I", boot_sector[36:40])[0]
		if not (bytes_per_sector and sectors_per_cluster and sectors_per_fat and fat_count):
			raise ZeroFreeError("the partition is not FAT32")
		first_data_sector = reserved_sectors + fat_count * sectors_per_fat
		cluster_count = (total_sectors - first_data_sector) // sectors_per_cluster
		disk.seek(partition_offset + reserved_sectors * bytes_per_sector)
		fat = disk.read(sectors_per_fat * bytes_per_sector)
		cluster_bytes = sectors_per_cluster * bytes_per_sector
		zeros = bytes(cluster_bytes)
		free = zeroed = 0
		for cluster in range(2, cluster_count + 2):
			if struct.unpack_from("<I", fat, cluster * 4)[0] & FAT32_ENTRY_MASK:
				continue
			position = partition_offset + (first_data_sector + (cluster - 2) * sectors_per_cluster) * bytes_per_sector
			disk.seek(position)
			if disk.read(cluster_bytes) != zeros:
				disk.seek(position)
				disk.write(zeros)
				zeroed += 1
			free += 1
	return ZeroFreeResult(free, zeroed, cluster_bytes)


def dig_holes(image: Path) -> bool:
	"""Make the all-zero runs of the image sparse with `fallocate --dig-holes`. False when fallocate is not installed."""
	if shutil.which("fallocate") is None:
		return False
	done = subprocess.run(["fallocate", "--dig-holes", str(image)], capture_output=True, text=True, check=False)
	if done.returncode != 0:
		raise ZeroFreeError(f"fallocate failed: {done.stderr.strip()}")
	return True
