# Tests for the edits to the disc's tree: the guarded text edits, the install CD against the published disc, the second cabinet.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import shutil
import subprocess

import pytest
from iso_fixtures import FILES, make_tree, stock_sums

from reactos_liminal import isotree
from reactos_liminal.isobuild import IsoBuildError, detect_writer, read_primary_tree, write_iso
from reactos_liminal.isotree import (
	add_cabinet,
	apply_install,
	apply_menu,
	build_cabinet,
	changed_files,
	check_no_answers,
	insert_after,
	replace_line,
)


@pytest.fixture(autouse=True)
def synthetic_stock(monkeypatch):
	monkeypatch.setattr(isotree, "STOCK_SUMS", stock_sums())


def test_a_line_is_replaced_once_and_keeps_its_line_ending():
	assert replace_line(b"a=1\r\nb=2\r\n", b"b=", b"b=9") == b"a=1\r\nb=9\r\n"
	assert replace_line(b"a=1\nb=2", b"b=", b"b=9") == b"a=1\nb=9"
	with pytest.raises(IsoBuildError, match="found 0"):
		replace_line(b"a=1\n", b"c=", b"c=9")
	with pytest.raises(IsoBuildError, match="found 2"):
		replace_line(b"a=1\na=2\n", b"a=", b"a=9")


def test_a_line_is_added_after_another():
	assert (
		insert_after(b"x\r\nCabinet = a.cab\r\ny\r\n", b"Cabinet = a", b"Cabinet = b.cab")
		== b"x\r\nCabinet = a.cab\r\nCabinet = b.cab\r\ny\r\n"
	)


def test_the_menu_text_carries_the_afterglow_name_and_the_default_stays_live(tmp_path):
	tree = make_tree(tmp_path)
	apply_menu(tree)
	text = (tree / "freeldr.ini").read_bytes().decode()
	assert "TitleText=ReactOS (Afterglow) Boot Media\r\n" in text
	assert 'Setup="ReactOS (Afterglow) Setup (Text Mode)"\r\n' in text
	assert 'LiveImg="ReactOS (Afterglow) Live Environment (Graphics Mode)"\r\n' in text
	assert "DefaultOS=LiveImg\r\n" in text


def test_the_menu_edit_refuses_a_menu_it_does_not_know(tmp_path):
	tree = make_tree(tmp_path)
	(tree / "freeldr.ini").write_bytes(b"[FREELOADER]\r\nDefaultOS=LiveImg\r\n")
	with pytest.raises(IsoBuildError, match="TitleText"):
		apply_menu(tree)


def test_the_install_cd_and_the_published_disc_differ_in_exactly_three_files(tmp_path):
	published = make_tree(tmp_path / "published")
	install = make_tree(tmp_path / "install")
	for tree in (published, install):
		apply_menu(tree)
	apply_install(install, b"[Unattend]\r\nUnattendSetupEnabled = yes\r\nAutoPartition = 1\r\n")
	assert changed_files(published, install) == ["freeldr.ini", "i386/txtsetup.sif", "i386/unattend.inf"]
	assert b"DefaultOS=Setup\r\n" in (install / "freeldr.ini").read_bytes()
	assert b'SetupDebugOptions = "/NODEBUG"\r\n' in (install / "i386/txtsetup.sif").read_bytes()
	assert (install / "i386/unattend.inf").read_bytes() == b"[Unattend]\nUnattendSetupEnabled = yes\nAutoPartition = 1\n"


def test_the_answers_are_never_allowed_on_the_published_disc(tmp_path):
	published = make_tree(tmp_path / "published")
	apply_menu(published)
	check_no_answers(published)
	install = make_tree(tmp_path / "install")
	apply_install(install, b"[Unattend]\r\nUnattendSetupEnabled = yes\r\n")
	with pytest.raises(IsoBuildError, match="unattend.inf is not the stock file"):
		check_no_answers(install)
	# the answers file is stock but Setup was made the default entry: still the install CD
	mixed = make_tree(tmp_path / "mixed")
	(mixed / "freeldr.ini").write_bytes(replace_line((mixed / "freeldr.ini").read_bytes(), b"DefaultOS=", b"DefaultOS=Setup"))
	with pytest.raises(IsoBuildError, match="install CD"):
		check_no_answers(mixed)


@pytest.mark.skipif(shutil.which("xorriso") is None, reason="needs xorriso")
def test_a_disc_whose_edited_files_are_not_the_stock_ones_is_refused(tmp_path, monkeypatch):
	tree = make_tree(tmp_path / "src")
	iso = tmp_path / "stock.iso"
	subprocess.run(["xorriso", "-as", "mkisofs", "-iso-level", "4", "-o", str(iso), str(tree)], check=True, capture_output=True)
	destination = tmp_path / "extracted"
	isotree.stock_tree(iso, destination)
	assert (destination / "freeldr.ini").is_file()
	shutil.rmtree(destination)
	monkeypatch.setitem(isotree.STOCK_SUMS, "i386/txtsetup.sif", "0" * 64)
	with pytest.raises(IsoBuildError, match="not the file ReactOS 0.4.16 ships"):
		isotree.stock_tree(iso, tmp_path / "extracted-again")
	assert not (tmp_path / "extracted-again").exists()


needs_cab = pytest.mark.skipif(shutil.which("gcab") is None, reason="needs gcab")


@needs_cab
def test_the_second_cabinet_lists_its_files_and_is_the_same_each_time(tmp_path):
	files = {"readme.txt": b"from the second cabinet\r\n", "a.dll": b"MZ" * 50}
	first = build_cabinet(files, 1756425600, tmp_path / "one")
	second = build_cabinet(files, 1756425600, tmp_path / "two")
	assert first == second
	cabinet, listing = first
	assert cabinet[:4] == b"MSCF"
	assert (
		listing
		== b'[Version]\r\nSignature = "$Windows NT$"\r\n\r\n[Directories]\r\n1 = "\\"\r\n\r\n[SourceFiles]\r\na.dll=1\r\nreadme.txt=1\r\n'
	)
	if shutil.which("cabextract"):
		(tmp_path / "cab").write_bytes(cabinet)
		listed = subprocess.run(["cabextract", "-l", str(tmp_path / "cab")], capture_output=True, text=True, check=True).stdout
		assert "readme.txt" in listed and "a.dll" in listed


@needs_cab
def test_the_cabinet_goes_on_the_disc_after_the_stock_one(tmp_path):
	tree = make_tree(tmp_path)
	before = (tree / "i386" / "reactos.cab").read_bytes()
	add_cabinet(tree, {"readme.txt": b"x"}, 0, tmp_path / "scratch")
	text = (tree / "i386/txtsetup.sif").read_bytes().decode()
	assert "Cabinet = reactos.cab\r\nCabinet = afterglow.cab\r\n" in text
	assert (tree / "i386/afterglow.cab").is_file() and (tree / "i386/afterglow.inf").is_file()
	assert (tree / "i386/reactos.cab").read_bytes() == before == FILES["i386/reactos.cab"]


def test_a_cabinet_needs_files(tmp_path):
	if shutil.which("gcab") is None:
		pytest.skip("needs gcab")
	with pytest.raises(IsoBuildError, match="at least one file"):
		build_cabinet({}, 0, tmp_path)


def test_the_install_disc_boots_the_new_names_and_the_answers_are_on_it(tmp_path):
	try:
		writer = detect_writer()
	except IsoBuildError:
		pytest.skip("needs an ISO writer")
	tree = make_tree(tmp_path)
	apply_menu(tree)
	apply_install(tree, b"[Unattend]\r\nUnattendSetupEnabled = yes\r\n")
	out = write_iso(tree, tmp_path / "install.iso", tmp_path / "scratch", writer, 1756425600)
	assert "i386/unattend.inf" in read_primary_tree(out)
