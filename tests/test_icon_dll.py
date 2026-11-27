# Tests for the resource-only DLL writer behind the Show Desktop button's imageres.dll.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import struct

import pytest
from pe_fixtures import ico

from reactos_liminal.icon_dll import build_icon_dll
from reactos_liminal.pe_resource import pe_checksum
from reactos_liminal.pe_resources import RT_GROUP_ICON, RT_ICON, PeError, PeFile, parse_group, read_ico


def test_the_dll_holds_one_group_with_the_frames_of_its_icon():
	icon = ico(0x30)
	pe = PeFile(build_icon_dll({110: icon}))
	groups = pe.data_entries(RT_GROUP_ICON)
	assert list(groups) == [110]
	frames = parse_group(pe.entry_data(groups[110][0]))
	assert [(frame.width, frame.bit_count) for frame in frames] == [(16, 32), (32, 32), (48, 32)]
	icons = pe.data_entries(RT_ICON)
	for frame, (_width, _height, _bits, image) in zip(frames, read_ico(icon), strict=True):
		assert pe.entry_data(icons[frame.icon_id][0]) == image
		assert frame.size == len(image)


def test_two_groups_get_frame_ids_that_do_not_clash():
	pe = PeFile(build_icon_dll({110: ico(1), 5: ico(2, sizes=(16, 32))}))
	groups = pe.data_entries(RT_GROUP_ICON)
	ids = [frame.icon_id for group in sorted(groups) for frame in parse_group(pe.entry_data(groups[group][0]))]
	assert len(ids) == len(set(ids)) == 5
	assert sorted(pe.data_entries(RT_ICON)) == sorted(ids)


def test_the_file_is_a_valid_checksummed_pe_with_no_code_and_the_same_bytes_every_time():
	first = build_icon_dll({110: ico(7)})
	assert first == build_icon_dll({110: ico(7)})
	pe = PeFile(first)
	assert struct.unpack_from("<I", first, pe.optional + 16)[0] == 0  # no entry point
	checksum_offset = pe.optional + 64
	assert struct.unpack_from("<I", first, checksum_offset)[0] == pe_checksum(first, checksum_offset)
	assert len(first) % 0x200 == 0


def test_a_frame_that_is_not_32_bit_is_refused():
	with pytest.raises(PeError, match="8-bit"):
		build_icon_dll({110: ico(1, bit_count=8)})


def test_no_groups_is_refused():
	with pytest.raises(PeError):
		build_icon_dll({})
