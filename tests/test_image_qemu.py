# The real image build, with the settings applied in a build VM. Skipped unless asked for: pytest -m qemu, with RL_TEST_WORK naming a
# work directory that holds the golden disk `rl install` made (and, offline, the fetched Afterglow source). About two minutes with KVM.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import os
import shutil
from pathlib import Path

import pytest

from reactos_liminal.fetch import sha256_file
from reactos_liminal.image import build_image
from reactos_liminal.install import golden_path
from reactos_liminal.mtools import FatImage
from reactos_liminal.recipe import load

REPO = Path(__file__).resolve().parent.parent
WORK = os.environ.get("RL_TEST_WORK")

pytestmark = [
	pytest.mark.qemu,
	pytest.mark.skipif(not WORK or shutil.which("qemu-system-i386") is None, reason="needs QEMU and RL_TEST_WORK with a golden disk"),
]


def test_the_image_is_patched_trimmed_and_configured(tmp_path):
	recipe = load(REPO / "recipes" / "afterglow.toml")
	work = Path(WORK)
	if not golden_path(recipe, work).is_file():
		pytest.skip("no golden disk in RL_TEST_WORK; run `rl install` first")
	out = tmp_path / "image.img"
	build_image(recipe, work, out=out)
	disk = FatImage(out)
	patched = tmp_path / "user32.dll"
	disk.copy_out("ReactOS/system32/user32.dll", patched)
	assert sha256_file(patched) == "31f2137f45e8e15f3478333150d67996c7566e426ea7856e860a293a8ef7d477"
	assert disk.exists("ReactOS/Resources/Themes/Afterglow/afterglow.msstyles")
	assert not disk.exists("ReactOS/system32/sol.exe")  # trimmed
	assert disk.exists("ReactOS/system32/drivers/e1000.sys")  # the base profile keeps the network drivers
