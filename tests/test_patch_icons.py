# Tests for the icon patcher and the PE resource code, on a synthetic shell32.dll built here (no ReactOS file is used).
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import json
import struct

import pytest
from pe_fixtures import FILE_ALIGNMENT, SECTION_ALIGNMENT, dib, group_of, ico, make_dll, stock_dll

from reactos_liminal import icon_survey, patch_icons
from reactos_liminal.patchers import PatchError, run_patchers
from reactos_liminal.pe_resources import RT_GROUP_ICON, RT_ICON, PeFile


def test_a_group_is_replaced_by_three_frames_that_reuse_stock_frame_ids():
	new, report = patch_icons.patch_icon_groups(stock_dll(), {4: ico(0x40)})
	pe = PeFile(new)
	frames = group_of(pe, 4)
	assert [(frame.width, frame.bit_count) for frame in frames] == [(48, 32), (32, 32), (16, 32)]
	assert [frame.icon_id for frame in frames] == [4, 5, 6]  # the 32-bit stock frames of the same sizes
	icon_frames = pe.data_entries(RT_ICON)
	for frame in frames:
		assert pe.entry_data(icon_frames[frame.icon_id][0]) == dib(frame.width, 0x40)
	assert "group 4" in report[0]


def test_the_resource_directory_does_not_move_or_grow_and_a_section_is_appended():
	stock = stock_dll()
	new, _ = patch_icons.patch_icon_groups(stock, {4: ico(0x40)})
	before, after = PeFile(stock), PeFile(new)
	assert after.section_count == before.section_count + 1
	assert after.sections[-1].name == ".agico"
	assert [section for section in after.sections[:-1]] == before.sections
	rsrc = before.sections[1]
	assert new[rsrc.raw_offset : rsrc.raw_offset + 0x60] == stock[rsrc.raw_offset : rsrc.raw_offset + 0x60]  # directory header unchanged
	assert after.data_entries(RT_GROUP_ICON).keys() == before.data_entries(RT_GROUP_ICON).keys()
	assert len(new) % FILE_ALIGNMENT == 0
	assert struct.unpack_from("<I", new, after.optional + 56)[0] % SECTION_ALIGNMENT == 0  # SizeOfImage


def test_other_groups_are_untouched():
	stock = stock_dll()
	new, _ = patch_icons.patch_icon_groups(stock, {4: ico(0x40)})
	assert group_of(PeFile(new), 30) == group_of(PeFile(stock), 30)


def test_a_group_without_a_48_frame_gets_three_frames_when_it_has_ids_for_them():
	frames = {index: dib(16, index) for index in range(1, 5)}
	groups = {30: [(1, 32, 8), (2, 16, 8), (3, 32, 32), (4, 16, 32)]}
	new, _ = patch_icons.patch_icon_groups(make_dll(groups, frames), {30: ico(0x20)})
	frames_out = group_of(PeFile(new), 30)
	assert [frame.width for frame in frames_out] == [48, 32, 16]
	assert len({frame.icon_id for frame in frames_out}) == 3


def test_a_group_with_too_few_frame_ids_is_refused_rather_than_growing_the_directory():
	with pytest.raises(PatchError, match="not grown"):
		patch_icons.patch_icon_groups(stock_dll(), {30: ico(0x20)})


def test_a_missing_group_is_refused():
	with pytest.raises(PatchError, match="no icon group 99"):
		patch_icons.patch_icon_groups(stock_dll(), {99: ico(0x20)})


@pytest.mark.parametrize("sizes, bits", [((16, 32), 32), ((16, 32, 48), 8), ((16, 24, 32), 32)])
def test_an_icon_that_is_not_48_32_and_16_px_at_32_bit_is_refused(sizes, bits):
	with pytest.raises(PatchError):
		patch_icons.patch_icon_groups(stock_dll(), {4: ico(0x20, sizes, bits)})


def test_a_file_with_no_room_for_a_section_header_is_refused():
	with pytest.raises(PatchError, match="no room"):
		patch_icons.patch_icon_groups(stock_dll(header_room=False), {4: ico(0x20)})


def test_the_checksum_is_filled_in():
	new, _ = patch_icons.patch_icon_groups(stock_dll(), {4: ico(0x40)})
	pe = PeFile(new)
	stored = struct.unpack_from("<I", pe.data, pe.optional + 64)[0]
	pe.update_checksum()
	assert stored == struct.unpack_from("<I", pe.data, pe.optional + 64)[0] != 0


def test_the_patch_is_deterministic():
	assert patch_icons.patch_icon_groups(stock_dll(), {4: ico(0x40)})[0] == patch_icons.patch_icon_groups(stock_dll(), {4: ico(0x40)})[0]


# The patcher, run through run_patchers with a fake Afterglow tree whose renderer writes known icons.


@pytest.fixture
def icon_setup(fat, tmp_path, monkeypatch):
	stock = stock_dll()
	stock_file = tmp_path / "stock.dll"
	stock_file.write_bytes(stock)
	fat.make_directory("ReactOS")
	fat.make_directory("ReactOS/system32")
	fat.copy_in(stock_file, "ReactOS/system32/shell32.dll")
	table = {
		"stock_sha256": hashlib.sha256(stock).hexdigest(),
		"groups": [{"group": 4, "afterglow": "folder", "apply": True, "tier": "core"}, {"group": 30, "afterglow": None, "apply": False}],
	}
	monkeypatch.setattr(patch_icons, "load_table", lambda: table)
	tree = tmp_path / "tree"
	icons_dir = tree / "desktop" / "icons"
	icons_dir.mkdir(parents=True)
	(icons_dir / "render.py").write_text(
		"import os, sys\nos.makedirs(os.path.join(sys.argv[1], 'ico'))\n"
		f"open(os.path.join(sys.argv[1], 'ico', 'folder.ico'), 'wb').write({ico(0x40)!r})\n"
	)
	folder_sum = hashlib.sha256(ico(0x40)).hexdigest()
	(icons_dir / "SHA256SUMS").write_text(f"{folder_sum}  ico/folder.ico\n")
	(icons_dir / "map.json").write_text(json.dumps({"icons": [{"id": "folder", "resource": {"module": "shell32.dll", "group": 4}}]}))
	expected = hashlib.sha256(patch_icons.patch_icon_groups(stock, {4: ico(0x40)})[0]).hexdigest()
	digest = patch_icons.icon_set_digest({"ico/folder.ico": folder_sum})
	monkeypatch.setattr(patch_icons, "load_pins", lambda: {"results": {digest: expected}})
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	return fat, tree, scratch, stock, expected, icons_dir


def test_the_patcher_returns_a_patched_copy_that_matches_its_pin(icon_setup, tmp_path):
	fat, tree, scratch, _stock, expected, _icons = icon_setup
	patched = run_patchers(["afterglow.icons"], fat, tree, tmp_path, scratch)
	assert [item.image_path for item in patched] == ["ReactOS/system32/shell32.dll"]
	assert hashlib.sha256(patched[0].local_file.read_bytes()).hexdigest() == expected


def test_a_changed_stock_file_is_refused(icon_setup, tmp_path):
	fat, tree, scratch, stock, _expected, _icons = icon_setup
	changed = tmp_path / "changed.dll"
	changed.write_bytes(stock[:-1] + b"\x01")
	fat.copy_in(changed, "ReactOS/system32/shell32.dll")
	with pytest.raises(PatchError, match="not the stock shell32.dll"):
		run_patchers(["afterglow.icons"], fat, tree, tmp_path, scratch)


def test_an_icon_that_does_not_match_afterglows_sums_is_refused(icon_setup, tmp_path):
	fat, tree, scratch, _stock, _expected, icons_dir = icon_setup
	(icons_dir / "SHA256SUMS").write_text(f"{'0' * 64}  ico/folder.ico\n")
	with pytest.raises(PatchError, match="Afterglow records"):
		run_patchers(["afterglow.icons"], fat, tree, tmp_path, scratch)


def test_an_unpinned_icon_set_is_refused(icon_setup, tmp_path, monkeypatch):
	fat, tree, scratch, *_ = icon_setup
	monkeypatch.setattr(patch_icons, "load_pins", lambda: {"results": {}})
	with pytest.raises(PatchError, match="no pinned result"):
		run_patchers(["afterglow.icons"], fat, tree, tmp_path, scratch)


def test_a_wrong_pinned_result_is_refused_and_leaves_no_file(icon_setup, tmp_path, monkeypatch):
	fat, tree, scratch, *_ = icon_setup
	digest = patch_icons.icon_set_digest({"ico/folder.ico": hashlib.sha256(ico(0x40)).hexdigest()})
	monkeypatch.setattr(patch_icons, "load_pins", lambda: {"results": {digest: "0" * 64}})
	with pytest.raises(PatchError, match="expected"):
		run_patchers(["afterglow.icons"], fat, tree, tmp_path, scratch)
	assert not (scratch / "shell32-afterglow.dll").exists()


def test_a_map_that_puts_the_icon_in_another_group_is_refused(icon_setup, tmp_path):
	fat, tree, scratch, _stock, _expected, icons_dir = icon_setup
	(icons_dir / "map.json").write_text(json.dumps({"icons": [{"id": "folder", "resource": {"module": "shell32.dll", "group": 5}}]}))
	with pytest.raises(PatchError, match="map.json puts"):
		run_patchers(["afterglow.icons"], fat, tree, tmp_path, scratch)


# The shipped table and pins.


def test_the_shipped_table_and_pins_agree():
	table = icon_survey.load_table()
	assert patch_icons.load_pins()["stock_sha256"] == table["stock_sha256"]
	groups = [row["group"] for row in table["groups"]]
	assert groups == sorted(set(groups))
	applied = [row for row in table["groups"] if row["apply"]]
	assert {row["group"] for row in applied if row["tier"] == "core"} == {4, 5, 16, 18, 30, 32, 33, 35, 235, 236, 237, 238}
	for row in applied:
		assert row["afterglow"] and row["name"]
	assert all("reason" in row for row in table["groups"] if not row["apply"])


def test_a_frame_shared_with_another_group_is_not_reused():
	"""Group 2 lists the same frame ids as group 1, so replacing group 1 would change group 2 too: refused when too few ids remain."""
	frames = {index: dib(16, index) for index in range(1, 4)}
	groups = {1: [(1, 48, 32), (2, 32, 32), (3, 16, 32)], 2: [(3, 16, 32)]}
	with pytest.raises(PatchError, match="of its own"):
		patch_icons.patch_icon_groups(make_dll(groups, frames), {1: ico(0x20)})
