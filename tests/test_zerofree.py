# Tests for zeroing free clusters, on a small FAT32 image made in the test.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import pytest

from reactos_liminal.mtools import PARTITION_OFFSET
from reactos_liminal.zerofree import ZeroFreeError, dig_holes, zero_free_clusters


def test_deleted_data_is_zeroed_and_live_data_is_kept(fat, tmp_path):
	secret = b"DELETED-DATA-" * 4000
	kept = b"LIVE-DATA-" * 4000
	for name, content in (("gone.bin", secret), ("live.bin", kept)):
		source = tmp_path / name
		source.write_bytes(content)
		fat.copy_in(source, name)
	fat.delete_file("gone.bin")
	assert secret[:13] in fat.image.read_bytes()  # a delete leaves the data behind
	result = zero_free_clusters(fat.image)
	assert result.zeroed_clusters > 0 and result.free_clusters >= result.zeroed_clusters
	assert b"DELETED-DATA-" not in fat.image.read_bytes()
	assert fat.read("live.bin") == kept
	again = zero_free_clusters(fat.image)
	assert again.zeroed_clusters == 0  # nothing left to clear


def test_the_size_of_the_image_does_not_change(fat):
	before = fat.image.stat().st_size
	zero_free_clusters(fat.image)
	assert fat.image.stat().st_size == before


def test_a_disk_without_a_partition_is_refused(tmp_path):
	path = tmp_path / "blank.img"
	path.write_bytes(bytes(PARTITION_OFFSET + 4096))
	with pytest.raises(ZeroFreeError, match="boot sector"):
		zero_free_clusters(path)


def test_holes_can_be_punched(fat):
	zero_free_clusters(fat.image)
	assert isinstance(dig_holes(fat.image), bool)
	assert fat.image.stat().st_size == PARTITION_OFFSET + 8 * 1024 * 1024
