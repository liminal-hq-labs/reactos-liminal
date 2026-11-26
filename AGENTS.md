# AGENTS.md

## Table of contents

- [Project status](#project-status)
- [Spelling and writing](#spelling-and-writing)
- [Markdown formatting](#markdown-formatting)
- [Authoring voice](#authoring-voice)
- [Commit messages](#commit-messages)
- [Pull requests](#pull-requests)
- [Git workflow](#git-workflow)
- [Local tooling](#local-tooling)
- [Licence headers](#licence-headers)
- [Architecture rules](#architecture-rules)
- [Working with ReactOS images](#working-with-reactos-images)
- [Licensing and releases](#licensing-and-releases)
- [Testing](#testing)
- [Documentation](#documentation)
- [Repository layout](#repository-layout)

## Project status

ReactOS Liminal is a [Liminal HQ Labs](https://github.com/liminal-hq-labs) experiment: build Afterglow-dressed ReactOS install media, disk images and browser snapshots from a recipe. It is **experimental**, so interfaces, file formats and behaviour may change between any two commits. It is **unofficial**: not made, endorsed or supported by the ReactOS project. `SPEC.md` is the source of truth for behaviour, and `docs/decisions.md` records why. The [Labs charter](https://github.com/liminal-hq-labs/.github/blob/main/docs/labs-charter.md) covers what that status means and how a project graduates.

## Spelling and writing

**REQUIREMENT:** Use **Canadian English** in UI strings, comments, commit messages, pull request text and documentation: `colour`, `centre`, `behaviour`, `cancelled`, `licence` (noun) and `license` (verb), and `-ize` endings such as `customize`. Keep American spellings where an API, file format, registry value or protocol requires them (`SysColors`, `color`).

- Use a real em dash (`—`) in prose, never `--`. A command-line flag such as `--check` is not prose.
- Sentence case in the UI and in headings. Title Case for window titles.
- Write tight. No padding, no restating the heading.
- Use "ReactOS" only descriptively. Never present this project or its media as ReactOS itself; the product name is "Afterglow for ReactOS — unofficial remaster by Liminal HQ Labs".

## Markdown formatting

**REQUIREMENT:** Do not hard-wrap markdown prose. Write each paragraph or bullet as one line and let the renderer reflow it. This applies to `README.md`, `SPEC.md`, `docs/` and pull request descriptions. Commit message bodies are the one exception: hard-wrap them at roughly 72 characters. Code comments wrap normally.

## Authoring voice

**REQUIREMENT:** Ship the result, not how it was arrived at. Write comments, identifiers, docs and pull request text as the author of the artifact, for the person who meets it later.

- No "this PR", reviewer names or commit hashes in comments or docs. State the fact or the reasoning directly.
- When a comment has been edited more than once, rewrite it as one clean explanation.
- Commit messages and a pull request's `## Test plan` are the exceptions: they are the right place to record why a change happened and how it was checked.

## Commit messages

**Format:** Conventional Commits (`feat`, `fix`, `docs`, `test`, `ci`, `build`, `chore`, `refactor`, `perf`, `style`), with an optional scope.

- The body explains what and why, not how. Use markdown with **bold labels** and no headings. Hard-wrap.
- Backtick every code-level reference (identifiers, paths, config keys, flags, module names). User-facing strings use quotes.
- End with a `Co-Authored-By:` trailer for the model that wrote the change.
- Write the message to a file with a single-quoted heredoc and commit with `git commit -F <file>`, so backticks and `$()` are not expanded. Check the result with `git log -1 --pretty=fuller`.

## Pull requests

The pull request title and body become the merge commit message (the repository merges with the title and body), so write them as the final merge message.

- **Title:** capitalized, imperative, about 70 characters, no Conventional Commit prefix, outcome-focused.
- **Body:** `## Summary` with flat bullets that each open with a **bold lead-in**, then `## Test plan` with `- [x]` or `- [ ]` items naming the commands run. The last item is an unchecked `- [ ] Not verified: …` saying what was not checked.
- **Labels:** one category label (`enhancement`, `bug`, `documentation`, `testing`, `ci`, `build`, `chore`) plus scope labels from the repository's set where useful: `reactos`, `afterglow`, `recipe`, `install`, `trim`, `logon`, `setup-media`, `v86`, `licensing`, and the house labels such as `release`, `security`, `performance`, `infrastructure` and `blocked`.
- Open pull requests ready for review unless there is a stated blocker.
- Keep the branch up to date with `main` before merging: use the Update branch button or merge `main` into it. Never rebase a shared branch.
- Merge only on green CI, with a merge commit. Branches are deleted on merge.
- Fix a bug with a test that fails before the fix, and state exactly what was and was not run.

## Git workflow

- `main` is the default branch. Work on topic branches (`feat/`, `fix/issue-<n>-…`, `docs/`, `chore/`, `ci/`, `build/`). Never commit to `main`.
- **Merge commits only.** No squash and no rebase merges. Branches are deleted on merge.
- **Never** push, tag, publish or dispatch workflows unless asked. `build.yml` and `release.yml` are dispatched by the owner only.
- **Never** run `git add -A` or `git commit -a`, because checkouts may be shared. Stage explicit paths.
- **Never** remove files with wildcard patterns (no `rm` with globs, no `find -delete` with patterns). Name each path explicitly.
- Prefer the `gh` CLI for GitHub work.
- Planning files such as `PLAN.md` stay out of git.

## Local tooling

- **Editor settings:** `.editorconfig` is authoritative: tabs everywhere except YAML, which uses spaces.
- **Python** (3.12, standard library only in the pipeline) is formatted and linted with `ruff format` and `ruff check`, configured for tabs, and tested with `pytest` (`python3 -m pytest`; tests that need QEMU are marked `qemu` and skipped unless run with `-m qemu`). Run project Python with `-I`. Write plain, readable variable names, not single letters, except for loop variables and lambdas.
- **Shell** scripts pass shellcheck. **TypeScript** in `harness/` passes its typecheck and Prettier.
- **Shared CI images** come from [`liminal-hq/.github`](https://github.com/liminal-hq/.github). Pick the leanest tier that fits and pin it by digest. A project image belongs here only when no shared tier covers it.
- **Dependabot** is off. Add `.github/dependabot.yml` only when the project opts in.

## Licence headers

Every source, script, YAML, TOML and SVG file starts with a one-line summary, a blank comment line and the copyright block:

```python
# One-line summary of the file.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
```

Use `#` comments for Python, shell, YAML, TOML and Dockerfiles, `;` for `.reg` and `.inf` files, `rem` for `.cmd` files and an XML comment for SVG. Markdown, JSON and lockfiles don't need one. `scripts/check-headers.sh` enforces it. The project is licensed `Apache-2.0 OR MIT`, except the source patches in `patches/`, which are GPL-2.0-or-later (see `patches/README.md`).

## Architecture rules

- **SPEC first.** A change to behaviour, interfaces, recipes, settings or defaults updates `SPEC.md` in the same change.
- **Recipes declare, code acts.** A recipe chooses and parameterizes steps and pins inputs; it cannot add a new kind of write. Every input is pinned by SHA-256 and every build writes a lock file.
- **Hash-guarded patches.** Every patcher accepts only the exact upstream file it was written for (an SHA-256 allow-list in `pins/`), writes same-size in place, checks a table pattern is unique before editing it, keeps copyright and version strings, and records its undo. A test proves a one-byte-changed input is refused.
- **Art lives in Afterglow.** No art or art generator here; Afterglow's release and manifest are a pinned input. Afterglow keeps vector masters with scripted renders.
- **No consumer content.** Nothing Quill-specific (or specific to any other consumer) lives here; consumers extend a base recipe.
- **Decision IDs.** New decisions in `docs/decisions.md` take the `RL-` prefix and a number, with sub-decisions as `RL-1.1`.

## Working with ReactOS images

- **`WORK` lives outside the repository.** Work directories, downloads, disks, ISOs and states go under a directory outside the checkout; tools refuse a work directory inside it.
- **Large files never enter git:** no ISO, disk image, `.vdi`, `.qcow2`, state file, cabinet or zstd part.
- **No ReactOS binaries in git**, patched or not, and no ReactOS source files. Test fixtures are synthetic and generated at test time.
- **Copy before write.** Never modify an original image or ISO; copy it first.
- **Private QEMU only.** Each VM gets its own monitor socket and pid file in its work directory and is stopped through its monitor or its own pid. **Never** kill processes by name (`pkill`, `killall`), and never touch a VM or emulator you did not start.
- **No host desktop capture.** Screenshots come from the QEMU monitor (`screendump`) or the v86 page, never from the host's screen.
- **No network in the guest.**
- Clean up work directories you created; disk space on build machines is tight.

## Licensing and releases

- **Licence checklist gate.** No remastered ISO is published until the licence checklist in `SPEC.md` is complete and the owner approves the `release` environment.
- Releases are cut only on the owner's go: the owner pushes the tag and approves the deployment. Agents never dispatch `release.yml`.
- Every release names itself unofficial, attaches the corresponding source and `NOTICE.txt`, and lists every modified file with its before and after hashes.
- Source patches against ReactOS go in `patches/` under GPL-2.0-or-later and nowhere else.

## Testing

- `bash scripts/check-headers.sh` — SPDX headers
- `bash scripts/check-banner.sh` — hero banner rules and text fit (needs `xmllint`, `rsvg-convert`, `python3` and Chromium; `--shots DIR` writes frames to look at)
- `docker run --rm -v "$PWD:/workdir" davidanson/markdownlint-cli2:v0.17.2 "**/*.md"` — markdown
- `docker run --rm -v "$PWD:/mnt" -w /mnt koalaman/shellcheck:stable rl scripts/*.sh` — shell scripts
- `docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint` — workflows
- `ruff format --check`, `ruff check` and `python3 -m pytest` — Python
- `bash scripts/check-no-binaries.sh` — git holds no upstream binary or image

State exactly what was and was not run when reporting results.

## Documentation

- Update `SPEC.md` when behaviour changes, and add or amend a `docs/decisions.md` entry when a decision is made. A change that alters behaviour without touching the doc that describes it is incomplete.
- `README.md` is for people who want to use or understand the project: short, scannable, no padding. Keep architecture and history out of it, and keep the `> **Status:**` line and the unofficial notice honest.
- `NOTICE.md` lists third-party components and licences; keep it current when a release would ship something new.
- `CLAUDE.md` is a summary of this file. Keep them in sync.

## Repository layout

```text
README.md SPEC.md AGENTS.md CLAUDE.md NOTICE.md LICENSE-APACHE LICENSE-MIT
.editorconfig .markdownlint.jsonc .gitignore
assets/        hero banner
docs/          decisions and project notes
reactos_liminal/  the `rl` package (Python, standard library only); `rl` is its shim
recipes/       recipes; `afterglow.toml` is the base
profiles/      trim profiles (`none`, `base`, `demo`)
guest/         files that go to the guest: answers template, registry files, the settings script
tests/         pytest tests (synthetic fixtures only)
patches/       GPL-2.0-or-later source patches against ReactOS (licence note only so far)
scripts/       header check, banner check and its Chromium text-fit harness
.github/       CI workflow, issue and pull request templates, release notes configuration
```
