# Tests for `afterglow.map-icons` and the icon coverage report, on synthetic files.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import json

import pytest
from pe_fixtures import group_of, ico, stock_dll

from reactos_liminal import coverage, patch_base, patch_family
from reactos_liminal.patchers import PatchError, run_patchers
from reactos_liminal.pe_resources import PeFile
from reactos_liminal.trim import build_profile

GAME = "ReactOS/system32/game.exe"
GONE = "ReactOS/system32/gone.exe"
MAP = {
	"icons": [
		{"id": "sol", "kind": "program", "resource": {"module": "game.exe", "group": 4, "evidence": ["source", "binary"]}},
		# verified from the source alone, and the stock file holds it: patched
		{"id": "spider", "kind": "program", "resource": {"module": "game.exe", "group": 30, "evidence": ["source"]}},
		# verified from the source alone, and the stock file does not hold it: skipped
		{"id": "ghost", "kind": "program", "resource": {"module": "game.exe", "group": 77, "evidence": ["source"]}},
		# a module whose file is not on the disk: skipped
		{"id": "phone", "kind": "applet", "resource": {"module": "gone.exe", "group": 1, "evidence": ["source", "binary"]}},
		# a module on the disk with no stock hash: unverified
		{"id": "other", "kind": "program", "resource": {"module": "unlisted.exe", "group": 1, "evidence": ["source", "binary"]}},
		{"id": "monitor", "kind": None, "status": "unmapped"},
		{"id": "mouse", "kind": "toolbar", "resource": {"module": "browseui.dll", "bitmaps": [214], "cell": 3, "evidence": ["source"]}},
	]
}


@pytest.fixture
def setup(fat, tmp_path, monkeypatch):
	game_bytes = stock_dll()
	fat.make_directory("ReactOS")
	fat.make_directory("ReactOS/system32")
	for name in ("game.exe", "unlisted.exe"):
		local = tmp_path / name
		local.write_bytes(game_bytes)
		fat.copy_in(local, f"ReactOS/system32/{name}")
	families = {
		"map-icons": {
			"files": [
				{"path": GAME, "stock_sha256": hashlib.sha256(game_bytes).hexdigest()},
				{"path": GONE, "stock_sha256": "0" * 64},
			]
		}
	}
	monkeypatch.setattr(patch_family, "load_families", lambda: families)
	tree = tmp_path / "tree"
	icons_dir = tree / "desktop" / "icons"
	icons_dir.mkdir(parents=True)
	icon = ico(0x40)
	names = ["sol", "spider", "ghost", "phone"]
	(icons_dir / "render.py").write_text(
		"import os, sys\nos.makedirs(os.path.join(sys.argv[1], 'ico'))\n"
		f"for name in {names!r}:\n\topen(os.path.join(sys.argv[1], 'ico', name + '.ico'), 'wb').write({icon!r})\n"
	)
	icon_sum = hashlib.sha256(icon).hexdigest()
	(icons_dir / "SHA256SUMS").write_text("".join(f"{icon_sum}  ico/{name}.ico\n" for name in names))
	(icons_dir / "map.json").write_text(json.dumps(MAP))
	scratch = tmp_path / "scratch"
	scratch.mkdir()
	return fat, tree, scratch, game_bytes, icons_dir


def test_a_source_only_group_the_stock_file_holds_is_patched_and_one_it_lacks_is_skipped(setup, tmp_path):
	fat, tree, scratch, game_bytes, _ = setup
	with patch_base.recording() as recorder:
		patched = run_patchers(["afterglow.map-icons"], fat, tree, tmp_path, scratch)
	assert [item.image_path for item in patched] == [GAME]
	pe = PeFile(patched[0].local_file.read_bytes())
	assert group_of(pe, 4) != group_of(PeFile(game_bytes), 4)
	assert [frame.width for frame in group_of(pe, 30)] == [32, 16]  # a two-frame group is fitted
	assert ("game.exe", "group", 77) not in recorder.patched
	assert "no icon group 77" in recorder.skipped[("game.exe", "group", 77)][0]
	assert [key for key in recorder.skipped if key[0] == "gone.exe"] == [("gone.exe", "group", 1)]


def test_a_group_verified_in_the_binary_that_is_missing_is_an_error(setup, tmp_path):
	fat, tree, scratch, _, icons_dir = setup
	broken = json.loads(json.dumps(MAP))
	broken["icons"][2]["resource"]["evidence"] = ["source", "binary"]
	(icons_dir / "map.json").write_text(json.dumps(broken))
	with pytest.raises(PatchError, match="no icon group 77"), patch_base.recording():
		run_patchers(["afterglow.map-icons"], fat, tree, tmp_path, scratch)


def test_a_file_the_trim_removes_is_skipped_and_the_patch_list_is_otherwise_the_same(setup, tmp_path):
	fat, tree, scratch, *_ = setup
	with patch_base.recording(), patch_base.skipping(lambda path: path == GAME):
		assert run_patchers(["afterglow.map-icons"], fat, tree, tmp_path, scratch) == []


def test_the_map_icons_table_names_no_group(setup):
	"""A module's groups come from the map: the family's files carry a path and a stock sum, and no group id."""
	real = json.loads(patch_family.FAMILIES_FILE.read_text())["families"]["map-icons"]["files"]
	assert real and all(set(file_spec) <= {"path", "stock_sha256", "module", "stock_path"} for file_spec in real)


def test_the_coverage_report_gives_every_map_resource_one_status(setup, tmp_path):
	fat, tree, scratch, *_ = setup
	with patch_base.recording() as recorder:
		run_patchers(["afterglow.map-icons"], fat, tree, tmp_path, scratch)
	entries = {entry["id"]: entry for entry in MAP["icons"]}
	rows = coverage.build_rows(entries, recorder, {"game.exe", "gone.exe"}, {"unlisted.exe": ["ReactOS/system32/unlisted.exe"]})
	status = {row.icon_id: row.status for row in rows}
	assert status == {
		"sol": "patched",
		"spider": "patched",
		"ghost": "skipped",
		"phone": "skipped",
		"other": "unverified",
		"monitor": "unverified",
		"mouse": "unverified",  # the toolbar patcher did not run in this test
	}
	other = next(row for row in rows if row.icon_id == "other")
	assert "unlisted.exe" in other.detail and "no stock SHA-256" in other.detail
	assert coverage.counts(rows) == {"patched": 2, "skipped": 2, "unverified": 3}
	text = coverage.render(rows, build_profile("none", []))
	assert "2 patched, 2 skipped, 3 unverified" in text and "`monitor`" in text


def test_a_group_the_tables_add_is_listed_after_the_maps_rows():
	recorder = patch_base.PinRecorder()
	recorder.patched[("console.dll", "group", 40)] = ("console", ["ReactOS/system32/console.dll"])
	rows = coverage.build_rows({"console": {"id": "console"}}, recorder, {"console.dll"}, {})
	assert [(row.icon_id, row.status, row.evidence) for row in rows] == [("console", "patched", "table")]


def test_the_compact_column_says_whether_the_base_trim_keeps_the_file():
	row = coverage.Row("calc", "calc.exe", "group 110", "source+binary", "patched", ("ReactOS/system32/calc.exe",), "")
	kept = coverage.Row("cmd", "cmd.exe", "group 1", "source+binary", "patched", ("ReactOS/system32/cmd.exe",), "")
	text = coverage.render([row, kept], build_profile("base", []))
	assert "| removed by trim |" in text.splitlines()[-2] and "| kept |" in text.splitlines()[-1]


def test_the_committed_report_names_only_icons_the_tables_know():
	"""The committed `docs/icon-coverage.md` has a row for each of the three statuses' headings and the table header."""
	if coverage.REPORT_FILE.is_file():
		text = coverage.REPORT_FILE.read_text()
		assert text.startswith("# Icon coverage") and "| Icon | Module | Resource |" in text


def test_explorer_and_its_copy_replace_the_first_icon_group_the_file_views_draw():
	"""The map names group 101 of `explorer.exe` (the Start menu entry); group 100 is the first in the file, which is the icon Explorer's
	file views draw for `explorer.exe` and for `agexplorer.exe`, so this repository's table adds it to both."""
	files = json.loads(patch_family.FAMILIES_FILE.read_text())["families"]["program-icons"]["files"]
	rows = {spec["path"]: spec.get("groups") for spec in files if spec["path"].endswith("explorer.exe")}
	assert rows == {
		"ReactOS/explorer.exe": [{"group": 100, "afterglow": "explorer"}],
		"ReactOS/agexplorer.exe": [{"group": 100, "afterglow": "explorer"}],
	}
