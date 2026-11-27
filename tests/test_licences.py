# Tests for the licence, notice and changes files, the licences page, and their step in `rl image`.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import pytest

from reactos_liminal import licences, patchers, trim
from reactos_liminal import recipe as recipe_module
from reactos_liminal.cli import main
from reactos_liminal.image import PIPELINE, build_image
from reactos_liminal.licences import (
	TEXTS,
	ChangeRecord,
	LicenceError,
	PatchChange,
	changes_text,
	licence_texts,
	licences_page,
	notice_text,
	to_ascii,
)
from reactos_liminal.mtools import FatImage
from reactos_liminal.patchers import PatchedFile
from reactos_liminal.recipe import load
from reactos_liminal.trim import LICENCE_PATHS, TrimEntry, TrimReport
from tests.conftest import REPO
from tests.test_image import golden  # noqa: F401


@pytest.fixture
def base():
	return load(REPO / "recipes" / "afterglow.toml")


@pytest.fixture
def compact():
	return load(REPO / "recipes" / "afterglow-compact.toml")


def test_the_held_texts_match_their_recorded_sums_and_are_the_licences():
	texts = licence_texts()
	assert set(texts) == {"GPL-2.0.txt", "LGPL-2.1.txt", "Apache-2.0.txt", "MIT.txt"}
	assert b"GNU GENERAL PUBLIC LICENSE" in texts["GPL-2.0.txt"] and b"Version 2, June 1991" in texts["GPL-2.0.txt"]
	assert b"GNU LESSER GENERAL PUBLIC LICENSE" in texts["LGPL-2.1.txt"].upper() and b"Version 2.1" in texts["LGPL-2.1.txt"]


def test_a_changed_licence_text_is_refused(monkeypatch, tmp_path):
	bad = tmp_path / "GPL.txt"
	bad.write_text("not the licence")
	changed = (licences.LicenceText("GPL-2.0-only", "x", bad, "GPL-2.0.txt", "0" * 64, "x"),)
	monkeypatch.setattr(licences, "TEXTS", changed)
	with pytest.raises(LicenceError, match="does not match"):
		licence_texts()


def test_the_licence_folder_is_the_protected_path_the_trim_keeps():
	assert licences.IMAGE_LICENCE_FOLDER in LICENCE_PATHS
	assert licences.IMAGE_NOTICE in LICENCE_PATHS and licences.IMAGE_CHANGES in LICENCE_PATHS


def test_the_notice_says_unofficial_and_carries_the_source_offer_and_credits(base):
	text = notice_text(base).decode("ascii")
	assert "unofficial remaster of ReactOS 0.4.16" in text
	assert "not made, endorsed or supported by the ReactOS" in text
	assert licences.REACTOS_COMMIT in text and licences.REACTOS_TAG in text
	assert "three years" in text and "LICENSES\\GPL-2.0.txt" in text
	assert "ReactOS Team" in text and "Afterglow" in text
	assert base.section("inputs", "reactos_iso")["sha256"] in text
	assert "\r\n" in text and "\n" not in text.replace("\r\n", "")
	assert "Gecko" in text  # the base recipe is the full image, so Gecko is left in
	assert "Wallpapers shipped with ReactOS" not in text  # its wallpapers are replaced by Afterglow's, and their licences go with them


def test_the_notice_leaves_out_gecko_and_the_wallpapers_when_the_trim_removes_them(compact):
	text = notice_text(compact).decode("ascii")
	assert "Gecko" not in text and "Wallpapers shipped with ReactOS" not in text


def test_text_for_the_disk_is_ascii_and_refuses_anything_else():
	assert to_ascii("a — b ™") == "a - b (TM)"
	with pytest.raises(LicenceError, match="not ASCII"):
		to_ascii("café")


def test_the_changes_file_lists_every_patched_file_with_its_sums(base):
	record = ChangeRecord(
		patched=[PatchChange("afterglow.pointers", "ReactOS/system32/user32.dll", "a" * 64, "b" * 64)],
		trim=TrimReport(
			removed=[TrimEntry("f", "ReactOS/system32/sol.exe"), TrimEntry("d", "ReactOS/system32/gecko")],
			missing=[],
			sources=[("base", 2), ("quill.txt", 1)],
		),
		trim_profile="base",
		settings_applied=True,
		written_files=["ReactOS/Cursors/Afterglow/a.cur"],
	)
	text = changes_text(base, record).decode("ascii")
	assert "ReactOS/system32/user32.dll" in text and "patcher: afterglow.pointers" in text
	assert "before: " + "a" * 64 in text and "after:  " + "b" * 64 in text
	assert "Profile: base." in text and "Extra list quill.txt: 1 entries." in text
	assert "file   ReactOS/system32/sol.exe" in text and "folder ReactOS/system32/gecko" in text
	assert "ReactOS/Cursors/Afterglow/a.cur" in text
	assert "display mode 1024 x 768" in text and "registry files: display, quiet, watermark-off" in text


def test_the_changes_file_says_when_nothing_was_patched_or_applied(base):
	text = changes_text(base, ChangeRecord()).decode("ascii")
	assert "2. Patched files" in text and "  none" in text and "not applied in this build" in text


def test_the_pipeline_has_a_licences_step_after_the_files_and_before_the_settings():
	assert PIPELINE.index("files") < PIPELINE.index("licences") < PIPELINE.index("settings")


def test_the_image_gets_the_licences_notice_and_changes(golden, tmp_path, monkeypatch):  # noqa: F811
	recipe, work, _ = golden
	patched_file = tmp_path / "patched.bin"
	patched_file.write_bytes(b"patched")
	monkeypatch.setattr(recipe_module, "PATCHERS", ("test.patch",))
	monkeypatch.setattr(patchers, "PATCHERS", {"test.patch": lambda *args: [PatchedFile("ReactOS/system32/user32.dll", patched_file)]})
	from reactos_liminal import image

	monkeypatch.setattr(image, "run_patchers", lambda names, *args: patchers.PATCHERS[names[0]](*args))
	profiles = tmp_path / "profiles"
	profiles.mkdir()
	(profiles / "tiny.txt").write_text("f ReactOS/system32/sol.exe\n")
	monkeypatch.setattr(trim, "PROFILES_DIR", profiles)
	recipe.data["trim"]["profile"] = "tiny"
	recipe.data["patchers"]["list"] = ["test.patch"]
	disk = FatImage(build_image(recipe, work, with_settings=False))
	for text in TEXTS:
		assert disk.exists(f"LICENSES/{text.image_name}")
	assert b"GNU GENERAL PUBLIC LICENSE" in disk.read("LICENSES/GPL-2.0.txt")
	assert b"unofficial remaster" in disk.read("NOTICE.txt")
	changes = disk.read("CHANGES.txt").decode("ascii")
	import hashlib

	assert hashlib.sha256(b"stock").hexdigest() in changes and hashlib.sha256(b"patched").hexdigest() in changes
	assert "file   ReactOS/system32/sol.exe" in changes and "not applied in this build" in changes


def test_the_licences_page_is_made_from_the_recipe(base):
	page = licences_page(base)
	assert page.startswith("# Licences") and "unofficial remaster of ReactOS 0.4.16" in page
	assert base.section("inputs", "afterglow")["commit"] in page and "`afterglow.pointers`" in page
	assert "GPL-2.0-or-later" in page and "LGPL-2.1" in page and "three years" in page
	assert "—" in page  # real em dashes in the docs
	assert "removed by the" not in page  # the base recipe removes nothing


def test_the_licences_page_marks_what_the_compact_trim_removes(compact):
	page = licences_page(compact)
	assert "ReactOS\\system32\\gecko (removed by the `base` trim profile)" in page


def test_the_committed_licences_page_matches_the_generator(base):
	assert (REPO / "docs" / "licences.md").read_text() == licences_page(base), (
		"run ./rl licences recipes/afterglow.toml --out docs/licences.md"
	)


def test_the_cli_writes_the_page(tmp_path, capsys):
	out = tmp_path / "licences.md"
	assert main(["licences", str(REPO / "recipes" / "afterglow.toml"), "--out", str(out)]) == 0
	assert out.read_text().startswith("# Licences")
