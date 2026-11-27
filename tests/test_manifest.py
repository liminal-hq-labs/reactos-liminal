# Tests for the build manifest, the job summary and the hash tools.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import json

import pytest

from reactos_liminal.cli import main
from reactos_liminal.hashing import SumsError, check_sums, sums_text
from reactos_liminal.manifest import ManifestError, build_manifest, job_summary, parse_pairs, write_manifest
from reactos_liminal.recipe import load


@pytest.fixture
def dist(tmp_path):
	folder = tmp_path / "dist"
	(folder / "parts").mkdir(parents=True)
	(folder / "parts" / "0-8388608.img.zst").write_bytes(b"a" * 10)
	(folder / "parts" / "8388608-16777216.img.zst").write_bytes(b"b" * 5)
	(folder / "parts" / "manifest.json").write_text("{}")
	(folder / "state.bin.zst").write_bytes(b"state")
	return folder


def test_pairs():
	assert parse_pairs("a=1,b=two") == {"a": "1", "b": "two"} and parse_pairs("") == {}
	with pytest.raises(ManifestError):
		parse_pairs("nonsense")


def test_the_manifest_lists_outputs_and_pins(base_recipe_path, dist):
	manifest = build_manifest(
		load(base_recipe_path),
		dist,
		timings={"install": "150", "image": "85"},
		hashes={"payload": "f" * 64},
		v86_version="0.5.473",
		extra={"quill_commit": "abc"},
		peak_disk_mb=900,
		built="2026-11-26T00:00:00Z",
	)
	assert manifest["built"] == "2026-11-26T00:00:00Z"
	assert set(manifest["outputs"]) == {"state.bin.zst", "parts/manifest.json"}
	assert manifest["outputs"]["state.bin.zst"]["sha256"] == hashlib.sha256(b"state").hexdigest()
	assert manifest["parts"]["files"] == 2 and manifest["parts"]["bytes"] == 15
	pin = manifest["pinned"]
	assert pin["reactos_iso_sha256"].startswith("6f15ca6e") and pin["chunk_size"] == 8 * 1024 * 1024
	assert pin["trim_profile"] == "none" and pin["patchers"] == [
		"afterglow.pointers",
		"afterglow.start",
		"afterglow.logon",
		"afterglow.icons",
		"afterglow.cpl-icons",
		"afterglow.program-icons",
		"afterglow.dialog-icons",
		"afterglow.map-icons",
		"afterglow.toolbar-bitmaps",
		"afterglow.dialog-bitmaps",
		"afterglow.boot",
	]
	assert (
		pin["afterglow"]["commit"] == load(base_recipe_path).section("inputs", "afterglow")["commit"]
		and pin["v86"] == "0.5.473"
		and pin["extra"] == {"quill_commit": "abc"}
	)
	assert manifest["timings_seconds"] == {"install": 150, "image": 85}
	assert len(pin["unattend_inf_sha256"]) == 64


def test_the_manifest_is_reproducible_with_a_fixed_time(base_recipe_path, dist, monkeypatch):
	monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
	first = build_manifest(load(base_recipe_path), dist)
	second = build_manifest(load(base_recipe_path), dist)
	assert first == second and first["built"] == "2023-11-14T22:13:20Z"


def test_the_manifest_file_is_not_listed_in_itself(base_recipe_path, dist):
	write_manifest(build_manifest(load(base_recipe_path), dist), dist / "build-manifest.json")
	assert "build-manifest.json" not in build_manifest(load(base_recipe_path), dist)["outputs"]


def test_the_summary_has_the_tables_and_the_source_offer(base_recipe_path, dist):
	text = job_summary(build_manifest(load(base_recipe_path), dist, timings={"install": "150"}, v86_version="0.5.473"))
	for expected in (
		"## ReactOS image",
		"| `state.bin.zst` |",
		"| install | 150 |",
		"trim profile `none`",
		"8388608 bytes",
		"Before this is published",
	):
		assert expected in text
	assert "822e8647792a2c43f033e3e00ed273d59f163c7b" in text


def test_cli_manifest_and_summary(base_recipe_path, dist, capsys):
	assert (
		main(
			[
				"manifest",
				str(base_recipe_path),
				str(dist),
				"--timing",
				"install=150",
				"--v86-version",
				"0.5.473",
				"--built",
				"2026-11-26T00:00:00Z",
			]
		)
		== 0
	)
	path = dist / "build-manifest.json"
	assert capsys.readouterr().out.strip() == str(path)
	assert json.loads(path.read_text())["timings_seconds"] == {"install": 150}
	assert main(["summary", str(path)]) == 0
	assert "ReactOS image" in capsys.readouterr().out


def test_sums_round_trip_and_catch_changes(dist):
	sums = dist / "SHA256SUMS"
	sums.write_text(sums_text([dist], base=dist))
	assert "state.bin.zst" in sums.read_text() and "  parts/0-8388608.img.zst" in sums.read_text()
	assert check_sums(sums).ok
	(dist / "state.bin.zst").write_bytes(b"changed")
	(dist / "parts" / "manifest.json").unlink()
	result = check_sums(sums)
	assert result.failed == ["state.bin.zst"] and result.missing == ["parts/manifest.json"] and not result.ok


def test_sums_match_sha256sum_format(tmp_path):
	path = tmp_path / "f"
	path.write_bytes(b"abc")
	assert sums_text([path], base=tmp_path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad  f\n"


def test_bad_sums_input_is_refused(tmp_path):
	bad = tmp_path / "SUMS"
	bad.write_text("not a sum line\n")
	with pytest.raises(SumsError, match="line 1"):
		check_sums(bad)
	with pytest.raises(SumsError, match="no such"):
		sums_text([tmp_path / "nope"])


def test_cli_hash_and_check(dist, tmp_path, capsys):
	sums = tmp_path / "SUMS"
	assert main(["hash", str(dist), "--base", str(dist), "--out", str(sums)]) == 0
	assert main(["hash", "--check", str(sums), "--base", str(dist)]) == 0
	assert "failed 0" in capsys.readouterr().out
	(dist / "state.bin.zst").write_bytes(b"x")
	assert main(["hash", "--check", str(sums), "--base", str(dist)]) == 1
	assert "FAILED: state.bin.zst" in capsys.readouterr().err
