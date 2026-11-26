# The boot guard: boot a built image in a private QEMU and compare screendump frames of the boot menu, the kernel boot logo and the
# logon screen with what the art says they should show. Skipped unless asked for: pytest -m qemu, with RL_TEST_IMAGE naming an image
# `rl image` built and RL_TEST_WORK naming the work directory that holds the fetched Afterglow source. Run it through
# `flock ~/.cache/reactos-liminal/qemu.lock` so only one QEMU runs at a time. RL_TEST_SHOTS, when set, is a folder that keeps the
# frames as PNGs. About three minutes with KVM.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from boot_frames import find_banner, logo_differences, menu_looks_minimal_gold_on_black

from reactos_liminal.ppm import ppm_to_png, read_ppm
from reactos_liminal.recipe import load
from reactos_liminal.vm import PrivateVm, VmSpec

REPO = Path(__file__).resolve().parent.parent
IMAGE = os.environ.get("RL_TEST_IMAGE")
WORK = os.environ.get("RL_TEST_WORK")
SHOTS = os.environ.get("RL_TEST_SHOTS")

pytestmark = [
	pytest.mark.qemu,
	pytest.mark.skipif(
		not IMAGE or not WORK or shutil.which("qemu-system-i386") is None or not os.access("/dev/kvm", os.W_OK),
		reason="needs QEMU with KVM, RL_TEST_IMAGE and RL_TEST_WORK",
	),
]


def grab(vm: PrivateVm, name: str):
	"""The guest's screen now, as (width, height, RGB bytes); kept as a PNG when RL_TEST_SHOTS is set."""
	path = vm.directory / "frame.ppm"
	path.unlink(missing_ok=True)
	vm.monitor([f"screendump {path}"], pause=0.5)
	for _ in range(30):
		if path.is_file() and path.stat().st_size > 0:
			break
		time.sleep(0.1)
	time.sleep(0.2)
	frame = read_ppm(path.read_bytes())
	if SHOTS:
		Path(SHOTS).mkdir(parents=True, exist_ok=True)
		ppm_to_png(path, Path(SHOTS) / f"{name}.png")
	return frame


def wait_for(vm: PrivateVm, name: str, accept, timeout: float, interval: float = 1.0):
	"""Take frames until `accept(frame)` returns (True, detail); returns the last detail. Fails with the best detail seen."""
	deadline = time.monotonic() + timeout
	detail = "no frame"
	while time.monotonic() < deadline:
		frame = grab(vm, name)
		ok, detail = accept(frame)
		if ok:
			return detail
		time.sleep(interval)
	pytest.fail(f"{name}: not seen within {timeout:.0f}s; last: {detail}")


@pytest.fixture(scope="module")
def art():
	recipe = load(REPO / "recipes" / "afterglow.toml")
	tree = Path(WORK) / "afterglow" / recipe.section("inputs", "afterglow")["commit"]
	if not tree.is_dir():
		pytest.skip(f"no fetched Afterglow source at {tree}; run `rl fetch` or `rl image` first")
	out = Path(WORK) / "scratch" / "boot-guard-art"
	for folder in ("boot", "logon"):
		subprocess.run(["python3", "-I", str(tree / "desktop" / folder / "render.py"), str(out / folder)], check=True, capture_output=True)
	palette = json.loads((tree / "desktop" / "boot" / "palette.json").read_text())
	box = palette["progressBox"]
	return {
		"logo": (out / "boot" / "afterglow-logo-4bit.bmp").read_bytes(),
		"banner": (out / "logon" / "afterglow-banner.bmp").read_bytes(),
		"box": (box["x"], box["y"], box["width"], box["height"]),
	}


def test_the_boot_menu_the_kernel_logo_and_the_logon_banner_are_afterglow(tmp_path, art):
	disk = tmp_path / "image.img"
	subprocess.run(["cp", "--sparse=always", IMAGE, str(disk)], check=True)
	vm = PrivateVm(tmp_path / "vm")
	try:
		vm.start(VmSpec(disk=disk, boot_order="c", memory_mb=512, allow_reboot=True))
		menu = wait_for(vm, "reactos-liminal-art-boot-logon-menu", menu_looks_minimal_gold_on_black, 30)

		def logo_ok(frame):
			if frame[:2] != (640, 480):
				return False, f"a {frame[0]} x {frame[1]} frame"
			different, compared = logo_differences(frame, art["logo"], art["box"])
			return different == 0, f"{different} of {compared} logo pixels differ"

		logo = wait_for(vm, "reactos-liminal-art-boot-logon-kernel-logo", logo_ok, 60, interval=0.5)

		def banner_ok(frame):
			position, different = find_banner(frame, art["banner"])
			return position is not None and different == 0, f"banner at {position}, {different} pixels differ"

		banner = wait_for(vm, "reactos-liminal-art-boot-logon-logon", banner_ok, 240, interval=2.0)
	finally:
		vm.stop()
	print(f"menu: {menu}; kernel logo: {logo}; logon: {banner}")
