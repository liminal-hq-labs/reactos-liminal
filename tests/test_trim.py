# Tests for the trim profiles and the guard that keeps a trim from removing a patched file or a licence file.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import hashlib

import pytest

from reactos_liminal import trim
from reactos_liminal.image import ImageError, trim_image
from reactos_liminal.trim import (
	LICENCE_PATHS,
	TrimEntry,
	TrimError,
	apply_profile,
	check_profile,
	load_profile,
	parse_profile,
	profile_names,
	protection_conflicts,
)

NIC_DRIVERS = [f"f ReactOS/system32/drivers/{name}.sys" for name in ("e1000", "rtl8139", "pcnet", "dc21x4", "nvnet", "netkvm")]


def lines(profile):
	return [f"{entry.kind} {entry.path}" for entry in profile.entries]


def test_the_three_profiles_exist():
	assert profile_names() == ["base", "demo", "none"]


def test_none_removes_nothing():
	assert load_profile("none").entries == []


def test_demo_is_the_quill_demo_trim_exactly():
	"""The entries of Quill's trim-list-1.txt, -2.txt and -3.txt, in order, as they shipped: 137 entries with this digest."""
	entries = lines(load_profile("demo"))
	assert len(entries) == 137
	assert hashlib.sha256("\n".join(entries).encode()).hexdigest() == "5d09e135c4efc7bae60cba7c0ac4b24c2f305a153ef9e5e3a4f5737025d0c02a"
	for driver in NIC_DRIVERS:
		assert driver in entries  # the demo removes the network card drivers


def test_base_is_demo_minus_the_network_card_drivers():
	demo, base = lines(load_profile("demo")), lines(load_profile("base"))
	assert [line for line in demo if line not in base] == NIC_DRIVERS
	assert [line for line in demo if line in base] == base  # same entries, same order
	assert not any("tcpip" in line.lower() or "afd" in line.lower() or "tdi" in line.lower() for line in base)


@pytest.mark.parametrize("name", ["none", "demo", "base"])
def test_shipped_profiles_never_reach_a_protected_path(name):
	check_profile(load_profile(name))
	check_profile(load_profile(name), ["ReactOS/system32/user32.dll", "ReactOS/system32/agmsgina.dll"])


def test_parse_rules():
	profile = parse_profile("x", "# comment\n\nf a/b.txt\nd c d\n")
	assert profile.entries == [TrimEntry("f", "a/b.txt"), TrimEntry("d", "c d")]
	for bad in ("x a/b", "f", "f ../etc", "d /abs"):
		with pytest.raises(TrimError):
			parse_profile("x", bad)


def test_unknown_profile_is_named():
	with pytest.raises(TrimError, match="known: base, demo, none"):
		load_profile("tiny")


@pytest.mark.parametrize(
	"entry",
	[
		TrimEntry("f", "ReactOS/system32/user32.dll"),
		TrimEntry("f", "reactos/SYSTEM32/User32.DLL"),  # FAT ignores case
		TrimEntry("d", "ReactOS/system32"),  # holds the patched file
		TrimEntry("d", "ReactOS"),
	],
)
def test_a_patched_file_is_protected(entry):
	assert "patched file" in protection_conflicts(entry, ["ReactOS/system32/user32.dll"])


@pytest.mark.parametrize(
	"entry",
	[
		TrimEntry("f", "NOTICE.txt"),
		TrimEntry("f", "CHANGES.txt"),
		TrimEntry("d", "LICENSES"),
		TrimEntry("f", "LICENSES/GPL-2.0.txt"),
		TrimEntry("d", "Program Files/otvdm"),
		TrimEntry("f", "Program Files/otvdm/LICENSE"),
	],
)
def test_licence_files_are_protected(entry):
	assert "licence file" in protection_conflicts(entry)


def test_unrelated_paths_pass():
	assert protection_conflicts(TrimEntry("f", "ReactOS/system32/sol.exe"), ["ReactOS/system32/user32.dll"]) is None
	assert protection_conflicts(TrimEntry("d", "ReactOS/system32/gecko")) is None  # Gecko's licence goes with Gecko
	assert set(LICENCE_PATHS) >= {"LICENSES", "NOTICE.txt", "CHANGES.txt"}


def test_a_profile_that_reaches_a_patched_file_is_refused_before_any_removal(fat, tmp_path):
	source = tmp_path / "f.bin"
	source.write_bytes(b"x" * 1000)
	fat.make_directory("ReactOS")
	fat.copy_in(source, "ReactOS/a.bin")
	fat.copy_in(source, "ReactOS/user32.dll")
	profile = parse_profile("p", "f ReactOS/a.bin\nf ReactOS/user32.dll\n")
	with pytest.raises(TrimError, match="patched file"):
		apply_profile(fat, profile, ["ReactOS/user32.dll"])
	assert fat.exists("ReactOS/a.bin")  # nothing was removed, not even the entry before the bad one


def test_apply_removes_files_and_folders_and_reports_what_is_missing(fat, tmp_path):
	source = tmp_path / "f.bin"
	source.write_bytes(b"x" * 100_000)
	fat.make_directory("d")
	fat.make_directory("d/sub")
	fat.copy_in(source, "d/sub/one.bin")
	fat.copy_in(source, "two.bin")
	fat.copy_in(source, "keep.bin")
	profile = parse_profile("p", "d d\nf two.bin\nf not-there.bin\n")
	report = apply_profile(fat, profile)
	assert [entry.path for entry in report.removed] == ["d", "two.bin"]
	assert [entry.path for entry in report.missing] == ["not-there.bin"]
	assert report.bytes_freed >= 200_000
	assert fat.exists("keep.bin") and not fat.exists("d") and not fat.exists("two.bin")


def test_a_trim_never_touches_a_golden_disk(tmp_path, base_recipe_path):
	from reactos_liminal.recipe import load

	golden = tmp_path / "work" / "golden" / "x.img"
	golden.parent.mkdir(parents=True)
	golden.write_bytes(b"")
	with pytest.raises(ImageError, match="golden"):
		trim_image(load(base_recipe_path), tmp_path / "work", golden)


def test_the_profiles_directory_is_in_the_repository():
	assert trim.PROFILES_DIR.is_dir()
