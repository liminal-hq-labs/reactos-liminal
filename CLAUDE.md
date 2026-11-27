# CLAUDE.md

A summary of [AGENTS.md](AGENTS.md), which is canonical. Keep the two in sync.

## What this is

ReactOS Liminal is a Liminal HQ Labs experiment: build Afterglow-dressed ReactOS install media, disk images and browser snapshots from a recipe. Experimental and unofficial (not endorsed by the ReactOS project), so anything may change. Behaviour lives in `SPEC.md`, decisions in `docs/decisions.md` (prefix `RL-`).

## Rules to remember

- **Canadian English.** Real em dashes. Sentence case. No hard-wrapped markdown prose. Ship the result, not the journey: no "this PR" or reviewer names in code or docs. "ReactOS" only descriptively.
- **Conventional Commits.** Body in markdown with bold labels and no headings, hard-wrapped, written to a file and committed with `git commit -F`. End with a `Co-Authored-By` trailer.
- **Pull requests.** Title capitalized and imperative, no Conventional Commit prefix. Body: `## Summary` with bold lead-ins, `## Test plan` with checkboxes ending in an unchecked "Not verified: …". Title and body become the merge commit message. One category label plus scope labels (`reactos`, `afterglow`, `recipe`, `install`, `trim`, `logon`, `setup-media`, `v86`, `licensing`). Keep the branch up to date with `main`; merge only on green CI.
- **Git.** Topic branches, merge commits only, branches deleted on merge. Never push, tag, publish or dispatch workflows unless asked. Never `git add -A` or `git commit -a`. Never `rm` with globs. `PLAN.md` stays out of git.
- **Formatting.** Tabs everywhere except YAML. Python: `ruff format` and `ruff check` with tabs, `pytest` (QEMU tests marked `qemu`), run with `python3 -I`; plain readable variable names, no single letters except loop variables and lambdas.
- **Headers.** SPDX header on every source, script, YAML, TOML and SVG file: summary line, blank, "(c) Copyright 2026 Liminal HQ, Scott Morris", `SPDX-License-Identifier: Apache-2.0 OR MIT`. `patches/` is GPL-2.0-or-later.
- **Architecture.** SPEC first. Recipes declare, code acts; every input pinned by SHA-256. Every patch hash-guarded, same-size, with its undo. Art lives in Afterglow; no Quill content.
- **Images.** `WORK` outside the repo; large files and ReactOS binaries never in git; copy before write; private QEMU with its own monitor socket and pid file; never kill by name; no host desktop capture; no guest network.
- **ISO.** Discs are rebuilt from a tree with ReactOS's own flags (`-iso-level 4`, no Rock Ridge, Joliet or boot info table, hybrid boot record), never appended or written by xorriso: FreeLoader reads only the primary tree, does not drop a trailing dot and copies names into 32 bytes. One writer is pinned in `[iso]`. The unattended answers are never on the published disc. See `docs/iso.md`.
- **Rust.** `tools/afterfetch` is the one Rust project: `afterfetch.exe`, `no_std` for a Pentium, built from source by `rl image` (`[builds.afterfetch]`, output pinned by SHA-256, reproducible), toolchain pinned by its `rust-toolchain.toml`. `bash tools/afterfetch/check.sh` runs fmt, clippy, host tests, the build and the executable checks. No binary in git.
- **Releases.** Licence checklist in `SPEC.md` first; owner tags (or dispatches) and approves the `release` environment; agents never tag or dispatch `release.yml`.
- **CI.** One job per check. Shared images come from `liminal-hq/.github`. Dependabot is off unless the project opts in.
- **Docs.** Update `SPEC.md` and `docs/decisions.md` in the same change as the behaviour.

## Commands

```sh
bash scripts/check-headers.sh
bash scripts/check-banner.sh     # add --shots /tmp/shots for review frames
docker run --rm -v "$PWD:/workdir" davidanson/markdownlint-cli2:v0.17.2 "**/*.md"
docker run --rm -v "$PWD:/mnt" -w /mnt koalaman/shellcheck:stable scripts/*.sh
docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint
```
