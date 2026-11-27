# Tests for tools/fetch-v86.sh with curl replaced by a stub, so nothing is downloaded.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import os
import subprocess

from tests.conftest import REPO

SCRIPT = REPO / "tools" / "fetch-v86.sh"


def run(tmp_path, dest, body):
	"""Run the script with a `curl` that writes `body` to its --output file."""
	bin_dir = tmp_path / "bin"
	bin_dir.mkdir(exist_ok=True)
	stub = bin_dir / "curl"
	stub.write_text(
		'#!/usr/bin/env bash\nwhile [ $# -gt 0 ]; do if [ "$1" = --output ]; then out=$2; fi; shift; done\nprintf "%s" "'
		+ body
		+ '" > "$out"\n'
	)
	stub.chmod(0o755)
	env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", V86_DIR=str(dest))
	return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=False)


def test_a_download_with_the_wrong_sum_writes_nothing(tmp_path):
	dest = tmp_path / "v86"
	done = run(tmp_path, dest, "not the real package")
	assert done.returncode == 1
	assert "checksum mismatch" in done.stderr
	assert not dest.exists()


def test_a_destination_inside_the_repository_is_refused(tmp_path):
	done = run(tmp_path, REPO / "v86-test", "x")
	assert done.returncode == 2
	assert "outside the repository" in done.stderr
	assert not (REPO / "v86-test").exists()
