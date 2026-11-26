# The real unattended install, in QEMU. Skipped unless asked for: pytest -m qemu, with RL_TEST_ISO naming the official ISO (and
# optionally RL_TEST_WORK for the work directory, so an earlier golden disk is reused). Takes minutes with KVM, hours without.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import os
import shutil
from pathlib import Path

import pytest

from reactos_liminal.install import golden_path, run_install
from reactos_liminal.mtools import FatImage
from reactos_liminal.recipe import load

REPO = Path(__file__).resolve().parent.parent
ISO = os.environ.get("RL_TEST_ISO")

pytestmark = [
	pytest.mark.qemu,
	pytest.mark.skipif(not ISO or shutil.which("qemu-system-i386") is None, reason="needs QEMU and RL_TEST_ISO"),
]


def test_the_install_produces_a_bootable_golden_disk(tmp_path):
	recipe = load(REPO / "recipes" / "afterglow.toml")
	work = Path(os.environ.get("RL_TEST_WORK") or tmp_path / "work")
	golden = run_install(recipe, work, Path(ISO))
	assert golden == golden_path(recipe, work) and golden.is_file()
	disk = FatImage(golden)
	assert disk.exists("ReactOS/explorer.exe")
	assert disk.exists("ReactOS/system32/user32.dll")
	freeldr = disk.read("freeldr.ini")
	assert b"DefaultOS=ReactOS" in freeldr and b"TimeOut=3" in freeldr
	# A second run for the same inputs finds the cache and starts nothing.
	assert run_install(recipe, work, Path(ISO)) == golden
