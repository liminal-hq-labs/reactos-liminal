# Tests for the bitmap resource reader and the in-place replacement, on a synthetic PE file.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import struct

import pytest
from pe_fixture import make_dib, make_pe

from reactos_liminal.pe_resource import PeError, PeFile, pe_checksum, replace_bitmap, u32

OLD = make_dib(8, 4, 24, fill=0x11)
OTHER = make_dib(4, 4, 24, fill=0x22)


def test_the_slot_of_a_bitmap_is_found():
	data = make_pe({7: OLD, 9: OTHER})
	slot = PeFile(data).bitmap(7)
	assert slot.size == len(OLD)
	assert data[slot.data_offset : slot.data_offset + slot.size] == OLD


def test_a_missing_bitmap_is_reported():
	with pytest.raises(PeError, match="not in the file"):
		PeFile(make_pe({7: OLD})).bitmap(8)


def test_a_bitmap_in_two_languages_is_refused():
	with pytest.raises(PeError, match="2 languages"):
		PeFile(make_pe({7: OLD}, languages={7: 2})).bitmap(7)


def test_not_a_pe_file_is_refused():
	with pytest.raises(PeError, match="not a PE"):
		PeFile(b"MZ" + b"\0" * 200)


def test_a_same_size_replacement_changes_only_that_bitmap_and_the_checksum():
	data = make_pe({7: OLD, 9: OTHER})
	new = make_dib(8, 4, 24, fill=0x77)
	patched = replace_bitmap(data, 7, new, same_size=True)
	pe = PeFile(patched)
	assert patched[pe.bitmap(7).data_offset :][: len(new)] == new
	assert patched[pe.bitmap(9).data_offset :][: len(OTHER)] == OTHER
	differing = {index for index, (before, after) in enumerate(zip(data, patched, strict=True)) if before != after}
	checksum = PeFile(data).checksum_offset
	assert all(
		index in range(checksum, checksum + 4)
		or PeFile(data).bitmap(7).data_offset <= index < PeFile(data).bitmap(7).data_offset + len(OLD)
		for index in differing
	)
	assert u32(patched, checksum) == pe_checksum(patched, checksum)


def test_a_same_size_replacement_of_another_size_is_refused():
	with pytest.raises(PeError, match="slot is"):
		replace_bitmap(make_pe({7: OLD}), 7, OTHER, same_size=True)


def test_a_shorter_bitmap_lowers_the_size_field_and_zeroes_the_rest_of_the_slot():
	data = make_pe({7: OLD, 9: OTHER})
	patched = replace_bitmap(data, 7, OTHER, same_size=False)
	pe = PeFile(patched)
	slot = pe.bitmap(7)
	assert slot.size == len(OTHER)
	assert patched[slot.data_offset : slot.data_offset + len(OLD)] == OTHER + b"\0" * (len(OLD) - len(OTHER))
	assert len(patched) == len(data)


def test_a_longer_bitmap_is_refused_even_when_size_may_change():
	with pytest.raises(PeError, match="slot holds"):
		replace_bitmap(make_pe({7: OTHER}), 7, OLD, same_size=False)


def test_the_checksum_counts_an_odd_length_file():
	data = bytearray(make_pe({7: OLD}))
	checksum = PeFile(bytes(data)).checksum_offset
	struct.pack_into("<I", data, checksum, 0)
	assert pe_checksum(bytes(data) + b"\1", checksum) != pe_checksum(bytes(data), checksum)
