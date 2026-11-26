# Checks on the build and release workflows that a YAML linter cannot make: pinned actions, least privilege, triggers and the release gate.
# The workflows themselves cannot be run from here, so these keep their promises from drifting.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import re

import pytest

from reactos_liminal import licences
from tests.conftest import REPO

WORKFLOWS = REPO / ".github" / "workflows"
BUILD = (WORKFLOWS / "build.yml").read_text()
RELEASE = (WORKFLOWS / "release.yml").read_text()


@pytest.mark.parametrize("text", [BUILD, RELEASE], ids=["build", "release"])
def test_every_action_is_pinned_to_a_commit_with_a_version_comment(text):
	uses = re.findall(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$", text, re.MULTILINE)
	assert uses
	for target, rest in uses:
		if target.startswith("./"):
			continue
		assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", target), target
		assert re.search(r"#\s*v\d+\.\d+\.\d+", rest), f"{target} has no version comment"


@pytest.mark.parametrize("text", [BUILD, RELEASE], ids=["build", "release"])
def test_permissions_are_read_only_at_the_top_and_every_job_has_a_timeout(text):
	assert re.search(r"^permissions:\n  contents: read\n", text, re.MULTILINE)
	assert "pull_request_target" not in text
	jobs = text.split("\njobs:\n", 1)[1]
	for block in re.split(r"\n  (?=[\w-]+:\n)", jobs):
		if "uses: ./" in block:  # a called workflow sets its own timeouts
			continue
		assert "timeout-minutes:" in block, block.splitlines()[0]


def test_the_build_runs_on_dispatch_and_pipeline_pull_requests_not_on_every_push():
	triggers = BUILD.split("permissions:", 1)[0]
	assert "workflow_dispatch:" in triggers and "pull_request:" in triggers and "workflow_call:" in triggers
	assert "\n  push:" not in triggers
	assert "'reactos_liminal/**'" in triggers and "'recipes/**'" in triggers


def test_the_release_starts_on_a_v_tag_or_dispatch_only():
	triggers = RELEASE.split("permissions:", 1)[0]
	assert "tags:\n      - 'v*'" in triggers and "workflow_dispatch:" in triggers
	assert "branches:" not in triggers and "schedule:" not in triggers and "pull_request" not in triggers


def test_only_the_publish_job_can_write_and_it_needs_the_release_environment():
	assert RELEASE.count("contents: write") == 1
	publish = RELEASE.split("\n  publish:\n", 1)[1]
	assert "environment:\n      name: release" in publish and "contents: write" in publish
	assert "needs: [plan, build, source]" in publish
	assert "gh release create" in publish


def test_a_release_build_requires_kvm_and_artefacts_are_kept_seven_days():
	assert "require-kvm: true" in RELEASE
	for text in (BUILD, RELEASE):
		assert text.count("retention-days: 7") == text.count("upload-artifact@")


def test_the_caches_are_keyed_on_the_pins_and_the_pins_are_checked_after_them():
	assert "reactos-iso-${{ steps.keys.outputs.iso_sha256 }}" in BUILD
	assert "afterglow-${{ steps.keys.outputs.afterglow_commit }}" in BUILD
	assert "golden-${{ steps.keys.outputs.golden_key }}" in BUILD
	assert BUILD.index("Restore the ISO") < BUILD.index("Verify the pins") < BUILD.index("Install ReactOS unattended")
	assert "./rl verify" in BUILD and "--require iso,afterglow-tar" in BUILD
	assert "if: steps.iso-cache.outputs.cache-hit != 'true' || steps.afterglow-cache.outputs.cache-hit != 'true'" in BUILD


def test_the_build_runs_every_stage_the_issue_lists_in_order():
	order = ["rl verify", "rl install", "rl image", "rl parts", "rl licences", "rl manifest"]
	positions = [BUILD.index("./" + name) for name in order]
	assert positions == sorted(positions)


def test_the_release_names_the_reactos_source_the_licence_files_name():
	assert f"REACTOS_SOURCE_COMMIT: {licences.REACTOS_COMMIT}" in RELEASE
	assert f"REACTOS_SOURCE_TAG: {licences.REACTOS_TAG}" in RELEASE


def test_the_release_notes_for_the_first_release_exist_and_say_unofficial():
	notes = (REPO / "docs" / "releases" / "0.1.0.md").read_text()
	assert "unofficial" in notes.lower() and "not made, endorsed or supported by the ReactOS Project" in notes


def test_v0_1_0_publishes_no_iso():
	assert "./rl iso" not in BUILD and "remaster.iso" not in BUILD
	assert ".iso" not in RELEASE
	notes = (REPO / "docs" / "releases" / "0.1.0.md").read_text()
	assert "later release" in notes and "No install ISO yet" in notes
