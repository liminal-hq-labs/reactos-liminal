# Tests for the disk parts: names, sizes, the zero-part shortcut, the manifest and a round trip through zstd.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib
import json
import os
import shutil

import pytest

from reactos_liminal.cli import main
from reactos_liminal.parts import PartsError, make_parts, part_name, read_parts

pytestmark = pytest.mark.skipif(shutil.which("zstd") is None, reason="needs zstd")

CHUNK = 64 * 1024


def make_image(tmp_path, pieces):
	"""A raw image from (kind, length) pieces: 'zero' or 'data'."""
	data = b"".join(bytes(length) if kind == "zero" else os.urandom(length) for kind, length in pieces)
	path = tmp_path / "disk.img"
	path.write_bytes(data)
	return path, data


def test_names_are_byte_ranges():
	assert part_name(0, 8388608) == "0-8388608.img.zst"
	assert part_name(8388608, 8388608) == "8388608-16777216.img.zst"


def test_every_chunk_gets_a_part_and_they_join_back_to_the_image(tmp_path):
	image, data = make_image(tmp_path, [("data", CHUNK), ("zero", CHUNK * 2), ("data", CHUNK + 1000)])
	result = make_parts(image, tmp_path / "parts", CHUNK, level=3)
	assert result.size == len(data) and result.parts == 5 and result.zero_parts == 2
	names = sorted(path.name for path in (tmp_path / "parts").iterdir())
	assert names == sorted(["manifest.json", *(part_name(start, CHUNK) for start in range(0, len(data), CHUNK))])
	assert read_parts(tmp_path / "parts") == data
	assert result.sha256 == hashlib.sha256(data).hexdigest()


def test_the_manifest_has_the_fields_v86_and_the_summary_read(tmp_path):
	image, data = make_image(tmp_path, [("zero", CHUNK * 3)])
	make_parts(image, tmp_path / "parts", CHUNK, level=3)
	manifest = json.loads((tmp_path / "parts" / "manifest.json").read_text())
	assert manifest["image"] == "disk.img" and manifest["size"] == len(data) and manifest["chunk"] == CHUNK
	assert manifest["parts"] == 3 and manifest["zeroParts"] == 3 and manifest["level"] == 3
	assert manifest["compressedBytes"] == sum(path.stat().st_size for path in (tmp_path / "parts").glob("*.zst"))
	assert manifest["sha256"] == hashlib.sha256(data).hexdigest()


def test_a_short_last_chunk_holds_only_its_bytes(tmp_path):
	image, data = make_image(tmp_path, [("zero", CHUNK + 10)])
	make_parts(image, tmp_path / "parts", CHUNK, level=3)
	assert read_parts(tmp_path / "parts") == data


def test_parts_are_identical_across_runs(tmp_path):
	image, _ = make_image(tmp_path, [("data", CHUNK), ("zero", CHUNK)])
	make_parts(image, tmp_path / "one", CHUNK, level=3)
	make_parts(image, tmp_path / "two", CHUNK, level=3)
	for path in (tmp_path / "one").glob("*.zst"):
		assert path.read_bytes() == (tmp_path / "two" / path.name).read_bytes()


@pytest.mark.parametrize("chunk", [1000, CHUNK + 1, 1024])
def test_a_bad_chunk_size_is_refused(tmp_path, chunk):
	image, _ = make_image(tmp_path, [("zero", CHUNK)])
	with pytest.raises(PartsError, match="power of two"):
		make_parts(image, tmp_path / "parts", chunk)


def test_the_cli_takes_the_chunk_size_from_the_recipe_and_can_override_it(base_recipe_path, tmp_path, capsys):
	image, _ = make_image(tmp_path, [("zero", 9 * 1024 * 1024)])
	work = tmp_path / "work"
	assert (
		main(
			[
				"parts",
				str(base_recipe_path),
				str(image),
				"--no-zero-free",
				"--level",
				"3",
				"--out",
				str(tmp_path / "p8"),
				"--work",
				str(work),
			]
		)
		== 0
	)
	assert json.loads(capsys.readouterr().out)["chunk"] == 8 * 1024 * 1024  # the recipe's default
	assert json.loads((tmp_path / "p8" / "manifest.json").read_text())["parts"] == 2
	args = [
		"parts",
		str(base_recipe_path),
		str(image),
		"--no-zero-free",
		"--level",
		"3",
		"--chunk-size",
		"1MiB",
		"--out",
		str(tmp_path / "p1"),
	]
	assert main([*args, "--work", str(work)]) == 0
	assert json.loads((tmp_path / "p1" / "manifest.json").read_text())["parts"] == 9


def test_the_cli_refuses_a_golden_disk(base_recipe_path, tmp_path, capsys):
	golden = tmp_path / "work" / "golden" / "g.img"
	golden.parent.mkdir(parents=True)
	golden.write_bytes(bytes(CHUNK))
	assert main(["parts", str(base_recipe_path), str(golden), "--work", str(tmp_path / "work")]) == 2
	assert "golden" in capsys.readouterr().err
