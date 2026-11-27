# Tests for the tree-based ISO builder: the writer's flags, the name checks that refuse a disc FreeLoader could not read, the 32-byte
# name rule and reproducibility. A small synthetic tree stands in for the official disc.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import shutil
import stat
import struct
import subprocess
import time

import pytest
from iso_fixtures import LONG_NAME, make_tree

from reactos_liminal import isobuild
from reactos_liminal.isobuild import (
	IsoBuildError,
	Writer,
	check_iso,
	check_tree_names,
	detect_writer,
	freeldr_lookup,
	parse_writer_version,
	read_primary_tree,
	write_iso,
	writer_command,
)

needs_writer = pytest.mark.skipif(not isobuild.writers_on_path(), reason="needs mkisofs or genisoimage")
needs_xorriso = pytest.mark.skipif(shutil.which("xorriso") is None, reason="needs xorriso")

CDRTOOLS = Writer("/usr/bin/mkisofs", "mkisofs", "3.02a09")
CDRKIT = Writer("/usr/bin/genisoimage", "genisoimage", "1.1.11")


def test_the_writer_is_named_from_its_version_output():
	assert parse_writer_version("mkisofs 3.02a09 (--)\n\nCopyright") == ("mkisofs", "3.02a09")
	assert parse_writer_version("genisoimage 1.1.11 (Linux)") == ("genisoimage", "1.1.11")
	# cdrkit's `mkisofs` link reports itself as 1.1.x, and is the same program as genisoimage.
	assert parse_writer_version("mkisofs 1.1.11 (Linux)") == ("genisoimage", "1.1.11")
	assert parse_writer_version("something else") is None


def fake_writers(tmp_path, monkeypatch, versions):
	"""Put scripts that print a `-version` line on the path, as `{name: line}`."""
	folder = tmp_path / "bin"
	folder.mkdir()
	for name, line in versions.items():
		script = folder / name
		script.write_text(f"#!/bin/sh\necho '{line}'\n")
		script.chmod(script.stat().st_mode | stat.S_IXUSR)
	monkeypatch.setenv("PATH", str(folder))


def test_the_pinned_writer_is_chosen_when_it_is_installed(tmp_path, monkeypatch):
	fake_writers(tmp_path, monkeypatch, {"mkisofs": "mkisofs 3.02a09 (--)", "genisoimage": "genisoimage 1.1.11 (Linux)"})
	assert [writer.identity for writer in isobuild.writers_on_path()] == ["mkisofs 3.02a09", "genisoimage 1.1.11"]
	assert detect_writer("genisoimage 1.1.11").identity == "genisoimage 1.1.11"
	assert detect_writer("mkisofs 3.02a09").identity == "mkisofs 3.02a09"
	assert detect_writer("genisoimage 9.9").identity == "mkisofs 3.02a09"  # another writer still works; the caller reports it


def test_one_program_under_two_names_is_one_writer(tmp_path, monkeypatch):
	fake_writers(tmp_path, monkeypatch, {"mkisofs": "mkisofs 3.02a09 (--)"})
	(tmp_path / "bin" / "genisoimage").symlink_to(tmp_path / "bin" / "mkisofs")
	assert len(isobuild.writers_on_path()) == 1


def test_no_writer_is_an_error_and_the_identity_is_none(tmp_path, monkeypatch):
	monkeypatch.setenv("PATH", str(tmp_path))
	with pytest.raises(IsoBuildError, match="no ISO writer"):
		detect_writer()
	assert isobuild.writer_identity() == "none"


def flag_values(command, flag):
	return command[command.index(flag) + 1]


def test_cdrtools_gets_reactos_own_flags(tmp_path):
	command = writer_command(CDRTOOLS, tmp_path / "tree", tmp_path / "out.iso", tmp_path / "sort")
	assert flag_values(command, "-iso-level") == "4"
	assert flag_values(command, "-eltorito-boot") == "loader/isoboot.bin"
	assert flag_values(command, "-eltorito-platform") == "x86"
	assert flag_values(command, "-boot-load-size") == "4"
	assert flag_values(command, "-hide") == "boot.catalog"
	assert flag_values(command, "-volid") == "ReactOS"
	for flag in ("-no-emul-boot", "-duplicates-once", "-no-cache-inodes"):
		assert flag in command
	assert command[-1] == str(tmp_path / "tree")


def test_cdrkit_gets_its_own_spelling_of_the_same_flags(tmp_path):
	command = writer_command(CDRKIT, tmp_path / "tree", tmp_path / "out.iso", tmp_path / "sort", volume="Afterglow")
	assert flag_values(command, "-iso-level") == "4"
	assert flag_values(command, "-b") == "loader/isoboot.bin"
	assert flag_values(command, "-c") == "boot.catalog"
	assert flag_values(command, "-volid") == "Afterglow"
	assert "-duplicates-once" not in command and "-eltorito-boot" not in command


@pytest.mark.parametrize("writer", [CDRTOOLS, CDRKIT])
def test_no_flag_that_breaks_the_boot_path(writer, tmp_path):
	"""Rock Ridge and Joliet are not read by FreeLoader, and the boot info table overwrites the boot sector's code."""
	command = writer_command(writer, tmp_path, tmp_path / "o.iso", tmp_path / "s")
	for flag in ("-R", "-r", "-J", "-joliet", "-rock", "-boot-info-table", "-iso-level=3"):
		assert flag not in command
	assert flag_values(command, "-iso-level") == "4"


def test_a_name_of_32_characters_in_a_folder_freeldr_reads_is_refused(tmp_path):
	tree = make_tree(tmp_path)
	check_tree_names(tree)  # the long side-by-side names are in a folder FreeLoader never reads
	(tree / "i386" / ("a" * 31)).write_bytes(b"x")
	check_tree_names(tree)
	(tree / "i386" / ("b" * 32)).write_bytes(b"x")
	with pytest.raises(IsoBuildError, match="32-byte buffer.*i386/b{32}"):
		check_tree_names(tree)


def test_a_long_folder_name_in_the_root_is_refused_too(tmp_path):
	tree = make_tree(tmp_path)
	(tree / ("c" * 40)).mkdir()
	with pytest.raises(IsoBuildError, match="too long"):
		check_tree_names(tree)


@needs_writer
def test_a_disc_is_written_with_exact_names_a_hybrid_record_and_the_boot_entry(tmp_path):
	tree = make_tree(tmp_path)
	out = write_iso(tree, tmp_path / "out.iso", tmp_path / "scratch", detect_writer(), epoch=1756425600)
	names = read_primary_tree(out)
	for path in ("freeldr.ini", "reactos/system32/config/system", "Profiles/Default User/ntuser.dat", f"reactos/winsxs/{LONG_NAME}"):
		assert path in names  # as given: lower case kept, no `;1`, no forced dot, spaces and long names kept
	assert "Profiles/Empty" in names and names["Profiles/Empty"].is_folder
	assert "boot.catalog" not in names
	assert freeldr_lookup(out, "reactos/system32/config/system") is not None
	media, load_size, lba, platform = isobuild.boot_entry(out)
	assert (media, load_size, platform) == (0, 4, 0)
	assert names["loader/isoboot.bin"].extent == lba
	data = out.read_bytes()
	assert data[510:512] == b"\x55\xaa" and struct.unpack_from("<I", data, 432)[0] == lba * 4 and data[446 + 4] == 0x96
	assert len(data) % (64 * 32 * 512) == 0  # padded to a whole cylinder, as isohybrid does
	assert not (tmp_path / "out.iso.part").exists()


@needs_writer
def test_two_builds_of_the_same_tree_are_byte_for_byte_the_same(tmp_path):
	first_tree = make_tree(tmp_path / "one")
	second_tree = make_tree(tmp_path / "two")
	writer = detect_writer()
	first = write_iso(first_tree, tmp_path / "one.iso", tmp_path / "scratch-one", writer, epoch=1756425600)
	time.sleep(1.1)  # the second build starts later, from a tree written later, in another folder
	second = write_iso(second_tree, tmp_path / "two.iso", tmp_path / "scratch-two", writer, epoch=1756425600)
	assert first.read_bytes() == second.read_bytes()
	third = write_iso(first_tree, tmp_path / "three.iso", tmp_path / "scratch-three", writer, epoch=1756425601)
	assert third.read_bytes() != first.read_bytes()  # the epoch is what the dates come from


@needs_writer
def test_a_long_name_in_a_searched_folder_stops_before_anything_is_written(tmp_path):
	tree = make_tree(tmp_path)
	(tree / "reactos" / "system32" / ("d" * 32)).write_bytes(b"x")
	with pytest.raises(IsoBuildError, match="too long"):
		write_iso(tree, tmp_path / "out.iso", tmp_path / "scratch", detect_writer(), epoch=0)
	assert not (tmp_path / "out.iso").exists() and not (tmp_path / "out.iso.part").exists()


@needs_writer
def test_a_missing_boot_image_is_refused(tmp_path):
	tree = make_tree(tmp_path)
	(tree / "loader" / "isoboot.bin").unlink()
	with pytest.raises(IsoBuildError, match="isoboot.bin"):
		write_iso(tree, tmp_path / "out.iso", tmp_path / "scratch", detect_writer(), epoch=0)


@needs_xorriso
def test_a_disc_with_mangled_names_is_refused(tmp_path):
	"""xorriso's default names (upper case, `;1`, a dot after a name with no extension, 8.3 cut) are what broke the live boot."""
	tree = make_tree(tmp_path)
	mangled = tmp_path / "mangled.iso"
	subprocess.run(
		["xorriso", "-as", "mkisofs", "-iso-level", "3", "-V", "X", "-b", "loader/isoboot.bin", "-no-emul-boot", "-boot-load-size", "4"]
		+ ["-o", str(mangled), str(tree)],
		check=True,
		capture_output=True,
	)
	assert freeldr_lookup(mangled, "reactos/system32/config/system") is None  # `SYSTEM.;1` is not `system` to FreeLoader
	with pytest.raises(IsoBuildError, match="names differ from the tree"):
		check_iso(mangled, tree, hybrid=False)


@needs_xorriso
def test_a_disc_that_cuts_a_long_name_is_refused(tmp_path):
	"""Level 3 names with the lower case and version relaxed still cut a 92-character name, which breaks the side-by-side assemblies."""
	tree = make_tree(tmp_path)
	cut = tmp_path / "cut.iso"
	subprocess.run(
		["xorriso", "-outdev", str(cut), "-rockridge", "off", "-joliet", "off"]
		+ ["-compliance", "iso_9660_level=3:lowercase:omit_version:no_force_dots:deep_paths:long_paths"]
		+ [
			"-boot_image",
			"any",
			"bin_path=/loader/isoboot.bin",
			"-boot_image",
			"any",
			"load_size=2048",
			"-boot_image",
			"any",
			"emul_type=no_emulation",
		]
		+ ["-map", str(tree), "/"],
		check=True,
		capture_output=True,
	)
	with pytest.raises(IsoBuildError, match="names differ"):
		check_iso(cut, tree, hybrid=False)


@needs_writer
def test_a_wrong_boot_entry_is_refused(tmp_path):
	tree = make_tree(tmp_path)
	out = write_iso(tree, tmp_path / "out.iso", tmp_path / "scratch", detect_writer(), epoch=0)
	data = bytearray(out.read_bytes())
	catalog = struct.unpack_from("<I", data, 17 * 2048 + 71)[0]
	struct.pack_into("<H", data, catalog * 2048 + 32 + 6, 1)  # load size 1
	out.write_bytes(data)
	with pytest.raises(IsoBuildError, match="load size of 4"):
		check_iso(out, tree)


@needs_writer
def test_a_hybrid_record_that_points_elsewhere_is_refused(tmp_path):
	tree = make_tree(tmp_path)
	out = write_iso(tree, tmp_path / "out.iso", tmp_path / "scratch", detect_writer(), epoch=0)
	data = bytearray(out.read_bytes())
	struct.pack_into("<I", data, 432, 7)
	out.write_bytes(data)
	with pytest.raises(IsoBuildError, match="hybrid boot record"):
		check_iso(out, tree)
