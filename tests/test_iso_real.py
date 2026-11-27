# The rebuild on the real official ISO: the install CD and the remastered ISO are rebuilt from the pinned disc and checked, and the
# remastered disc is booted to FreeLoader's menu and the live environment in a private QEMU. Skipped unless asked for: `pytest -m slow`
# (the static checks, a few seconds, 1 GB of scratch) or `pytest -m qemu` (the boot, with KVM), with RL_TEST_WORK naming a work
# directory whose `dl/` holds the pinned ISO. Run the boot through `flock ~/.cache/reactos-liminal/qemu.lock`. RL_TEST_SHOTS, when set,
# keeps the frames as PNGs.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import os
import shutil
import time
from pathlib import Path

import pytest

from reactos_liminal.fetch import has_hash
from reactos_liminal.isobuild import BOOT_PATH, check_iso, detect_writer, freeldr_lookup, read_primary_tree, remove_tree, write_iso
from reactos_liminal.isotree import apply_install, apply_menu, check_no_answers, stock_tree
from reactos_liminal.recipe import load
from reactos_liminal.vm import PrivateVm, VmSpec

REPO = Path(__file__).resolve().parent.parent
WORK = os.environ.get("RL_TEST_WORK")
SHOTS = os.environ.get("RL_TEST_SHOTS")
EPOCH = 1756425600


@pytest.fixture(scope="module")
def official():
	recipe = load(REPO / "recipes" / "afterglow.toml")
	pin = recipe.section("inputs", "reactos_iso")
	path = Path(WORK or "/nonexistent") / "dl" / pin["name"]
	if not has_hash(path, pin["sha256"]):
		pytest.skip(f"the pinned ISO is not at {path}")
	if shutil.which("xorriso") is None:
		pytest.skip("needs xorriso")
	try:
		detect_writer()
	except Exception:
		pytest.skip("needs an ISO writer")
	return path


@pytest.fixture(scope="module")
def published(official, tmp_path_factory):
	"""The remastered disc without the notices (those come from a finished image): the menu text on the rebuilt tree."""
	root = tmp_path_factory.mktemp("published")
	tree = root / "tree"
	stock_tree(official, tree)
	apply_menu(tree)
	check_no_answers(tree)
	out = write_iso(tree, root / "published.iso", root / "scratch", detect_writer(), EPOCH)
	yield out
	remove_tree(tree)


@pytest.mark.slow
def test_the_rebuilt_disc_keeps_every_name_of_the_official_disc(official, published):
	stock_names = {path: record.is_folder for path, record in read_primary_tree(official).items()}
	names = {path: record.is_folder for path, record in read_primary_tree(published).items()}
	assert names == stock_names
	assert "Profiles/Default User" in names
	assert "reactos/system32/config/system" in names
	for path in BOOT_PATH:
		assert freeldr_lookup(published, path) is not None, path


@pytest.mark.slow
def test_the_install_cd_differs_from_the_published_disc_in_three_files(official, published, tmp_path):
	from reactos_liminal.isotree import changed_files

	published_tree = tmp_path / "published"
	install_tree = tmp_path / "install"
	for tree in (published_tree, install_tree):
		stock_tree(official, tree)
		apply_menu(tree)
	try:
		apply_install(install_tree, b"[Unattend]\nUnattendSetupEnabled = yes\nAutoPartition = 1\n")
		assert changed_files(published_tree, install_tree) == ["freeldr.ini", "i386/txtsetup.sif", "i386/unattend.inf"]
		with pytest.raises(Exception, match="not the stock file"):
			check_no_answers(install_tree)
		out = write_iso(install_tree, tmp_path / "install.iso", tmp_path / "scratch", detect_writer(), EPOCH)
		check_iso(out, install_tree)
	finally:
		remove_tree(published_tree)
		remove_tree(install_tree)


@pytest.mark.slow
def test_two_builds_of_the_real_disc_are_the_same(official, published, tmp_path):
	tree = tmp_path / "tree"
	stock_tree(official, tree)
	try:
		apply_menu(tree)
		again = write_iso(tree, tmp_path / "again.iso", tmp_path / "scratch", detect_writer(), EPOCH)
		assert again.read_bytes() == published.read_bytes()
	finally:
		remove_tree(tree)


@pytest.mark.qemu
@pytest.mark.skipif(shutil.which("qemu-system-i386") is None or not os.access("/dev/kvm", os.W_OK), reason="needs QEMU with KVM")
def test_the_remastered_disc_boots_to_the_menu_and_the_live_environment(published, tmp_path):
	vm = PrivateVm(tmp_path / "vm")
	vm.directory.mkdir()
	disk = tmp_path / "blank.img"
	with open(disk, "wb") as blank:
		blank.truncate(64 * 1024 * 1024)
	shots = Path(SHOTS) if SHOTS else tmp_path / "shots"
	shots.mkdir(parents=True, exist_ok=True)
	vm.start(VmSpec(disk=disk, cdrom=published, boot_order="d", memory_mb=768, allow_reboot=True))
	try:
		time.sleep(3)
		assert vm.screenshot(shots / "afterglow-iso-menu.png")
		time.sleep(60)  # the menu counts down 3 seconds and the live environment boots
		assert vm.screenshot(shots / "afterglow-iso-live.png")
		assert vm.running()
	finally:
		vm.stop()
