# Plan: the Afterglow savers in the images

The Afterglow screensavers ([liminal-hq-labs/afterglow-savers](https://github.com/liminal-hq-labs/afterglow-savers)) go into both Afterglow images: Afterglow Maze, Cracktro, Twilight and Ink, plus the Afterglow Collection, listed in Display Properties > Screen Saver, with the Collection selected after ten minutes. Quill Ghostwriter, the sixth saver, is Quill's and only Quill's remix recipe writes it. The whole plan, with the packages that land in afterglow-savers and in Quill, is that repository's `docs/packing.md`; this file holds the three packages that land here, WP-PACK-3 to WP-PACK-5, in build order. When they land, SPEC.md, `docs/recipes.md` and `docs/decisions.md` say what was built and this plan is removed.

## What changes here

- **A build from another repository at a pinned commit.** `[builds.NAME]` today names an in-tree Rust project (`source`) and pins one `NAME.exe` (`sha256`). The savers are six files from one workspace in another repository, so `[builds]` gains a second form: `repo`, `commit` and `tar_sha256` (the source tar GitHub serves for that commit, fetched and checked as `[inputs.afterglow]` is), an optional `script` (default `build.sh`, relative to the project root), and `outputs`, a table of file name to SHA-256, which `[[files]]` names as `built:NAME/FILE`. afterfetch keeps the in-tree form unchanged.
- **The Rust rule.** AGENTS.md says "Rust is for `afterfetch.exe` alone". It becomes: the Rust in this repository is `afterfetch.exe` alone; a build may also compile a Rust project from another repository at a pinned commit, its outputs pinned by SHA-256 and never committed. Proposed as RL-63, recorded by WP-PACK-3.
- **A named registry file,** `screensaver-afterglow`, after `quiet` in the base recipe's `reg_files`: `SCRNSAVE.EXE` = `C:\ReactOS\system32\AGCOLLCT.SCR`, `ScreenSaveActive` `"1"`, `ScreenSaveTimeOut` `"600"`, `ScreenSaverIsSecure` `"0"` under `HKCU\Control Panel\Desktop`. Nothing else: the savers' own settings (`Sound` on at `Volume` 28, the Dusk palette) are the program's defaults, so no key under `HKCU\Software\Liminal HQ\Afterglow Screensavers` is written. Proposed as RL-64, recorded by WP-PACK-4.
- **No consumer content.** The base recipe declares and writes the five Afterglow files. The build also makes `AGQUILL.SCR`, but only Quill's remix recipe declares its sum (in its own `[builds.afterglow-savers.outputs]`, which merges key by key) and writes it.

## Cost

The five i586 files are 1,025,536 bytes on the disk (`AGCOLLCT.SCR` 400,896; `AGMAZE.SCR` 164,864; `AGCRACK.SCR` 162,816; `AGTWILIT.SCR` 160,768; `AGINK.SCR` 136,192). At zstd 19 they come to about 451 KB compressed one by one and 239 KB together, so the v86 parts grow by roughly 0.25 to 0.45 MB depending on where the files fall in the chunks; WP-PACK-5 measures it. The build adds a Rust build of one workspace (six `.scr` files with `-Zbuild-std`) to `rl image`, a few minutes on a CI runner. A consumer's saved v86 state must be rebuilt over the new disk (a state restored over a changed disk may find files moved under it); Quill's remix does that in its own package.

## WP-PACK-3 — builds from a pinned commit with several outputs

**Finish line.** The second `[builds]` form loads, validates, fetches, builds, locks, pins, verifies and appears in the manifest and the licences page; `rl build RECIPE NAME` builds one build and checks its sums; no recipe changes yet.

**Files owned.** `reactos_liminal/recipe.py`, `rustbuild.py`, `fetch.py`, `lock.py`, `pin.py`, `doctor.py`, `cli.py`, `manifest.py`, `licences.py`, `image.py` (the `built:` lookup only), `tests/`, `SPEC.md`, `docs/recipes.md`, `docs/pipeline.md`, `docs/decisions.md` (RL-63), `AGENTS.md` and `CLAUDE.md` (the Rust rule), `NOTICE.md`.

**Must not touch.** `recipes/`, `tools/afterfetch` and its pin, the patchers, `guest/`, `profiles/`, `build.yml`, `release.yml`.

**Details.**

- The tar is fetched into the work directory (`rl fetch` and `rl key` know it, so `build.yml` can cache it by commit and sum), and extracted once per commit under `WORK/builds/NAME/src-<commit>` with `tarfile`'s `data` filter: relative symlinks inside the tree are allowed (afterglow-savers' `platforms/win32/crates` is one), anything that leaves the tree is refused.
- The build runs `bash SCRIPT OUT_DIR` in the extracted root with `CARGO_TARGET_DIR=WORK/builds/NAME/target` and `CARGO_BUILD_JOBS`. Each listed output must exist and match its sum; other files in `OUT_DIR` are ignored.
- `declaring_file` becomes per output: the sum of an output is written by `rl lock` and `rl pin` into the recipe in the chain that declares that output, so a consumer's extra output stays in the consumer's recipe.
- `rl doctor` names what the savers need when a recipe uses them: rustup, the toolchain the project pins (1.98.0) with `rust-src` and `llvm-tools`.
- `rl manifest` records each build's repo, commit and output sums; `rl licences` lists the savers under `Apache-2.0 OR MIT` with their source commit.

**Tests** (synthetic fixtures only): a tar made at test time with a `build.sh` that writes two small files; a wrong tar sum, a missing output, a wrong output sum, a member outside the tree and an absolute symlink are each refused; `built:NAME/FILE` for an undeclared output is refused at load; a child recipe's extra output merges and is locked in the child's file; afterfetch's tests pass unchanged. Gate: `ruff format --check`, `ruff check`, `python3 -m pytest`, `bash scripts/check-headers.sh`, markdownlint, actionlint, shellcheck.

## WP-PACK-4 — the recipe wiring

Needs WP-PACK-3 merged and the afterglow-savers commit S (the merge of that repository's WP-PACK-2, after its ReactOS guest check).

**Finish line.** `recipes/afterglow.toml` builds the savers at S and writes the five files to `ReactOS/system32`; `screensaver-afterglow` selects the Collection; the compact recipe inherits both; both locks are current; CI builds the savers on every pull request.

**Files owned.** `recipes/afterglow.toml`, `recipes/afterglow.lock.json`, `recipes/afterglow-compact.lock.json`, `guest/reg/screensaver-afterglow.reg`, `reactos_liminal/recipe.py` (the new name only), `.github/workflows/ci.yml` (a job), `.github/workflows/build.yml` (the savers tar's cache and `--require`), `.github/workflows/release.yml` (the savers source with the corresponding source, if its source job lists the inputs), `SPEC.md`, `docs/recipes.md`, `docs/decisions.md` (RL-64), `NOTICE.md`, `tests/`.

**Must not touch.** The `[builds]` code, `tools/afterfetch`, the Afterglow pin, `profiles/base.txt`.

**The recipe.**

```toml
[builds.afterglow-savers]
repo = "liminal-hq-labs/afterglow-savers"
commit = "<S>"
tar_sha256 = "<measured by ./rl pin>"
script = "scripts/build-scr.sh"
[builds.afterglow-savers.outputs]
"AGMAZE.SCR" = "<sha256>"
"AGCRACK.SCR" = "<sha256>"
"AGTWILIT.SCR" = "<sha256>"
"AGINK.SCR" = "<sha256>"
"AGCOLLCT.SCR" = "<sha256>"

[[files]]
source = "built:afterglow-savers/AGMAZE.SCR"
destination = "ReactOS/system32/AGMAZE.SCR"
# one entry each for AGCRACK, AGTWILIT, AGINK and AGCOLLCT
```

A test checks that the `base` trim profile names none of the five files, so the compact image keeps them, and that `screensaver-afterglow` applies after `quiet`.

**CI.** A job "Afterglow savers" in `ci.yml`, in the shared `ci-rust` image by digest, with `rustup toolchain install 1.98.0 --component rust-src,llvm-tools`: `./rl build recipes/afterglow.toml afterglow-savers --work "$RUNNER_TEMP/rl-work"`. The five sums must equal the ones afterglow-savers' CI prints for S.

**Tests.** `./rl pin recipes/afterglow.toml`, `./rl lock` and `./rl verify` for both recipes, `./rl build`, `./rl image recipes/afterglow-compact.toml --dry-run`, the Python checks, markdownlint, actionlint, shellcheck.

## WP-PACK-5 — the images booted, on WP-PACK-4's branch

**Finish line.** Both images are built locally with the savers and booted in QEMU; the checks below pass in each; the cost is measured and written into `docs/recipes.md` as a short "Screensavers" section; the evidence is in the pull request. A fault in a saver goes back to afterglow-savers as a fix and a new S, never patched here.

**Steps.**

1. `./rl install recipes/afterglow.toml` (or the cached golden disk), `./rl image` for the full recipe and for the compact one with `--golden`, `./rl audit` on both.
2. `./rl parts` for both on `main` and on the branch: the disk's used bytes, the parts' total and the number of parts that changed.
3. Boot each image with afterglow-savers' `scripts/guest/guest.py --in-image --source <image>` (its WP-PACK-2 adds that mode), headless with KVM, `-display none` and its own monitor socket; keys go to the guest through the monitor only. It checks: the list holds the five by name (and ReactOS's own savers in the full image); each monitor preview runs; Settings opens the Afterglow dialog owned by Display Properties, with Sound on and Volume 28; Cancel writes nothing, OK writes the saver's key; Preview runs full screen and a key ends it; the Collection starts by itself at the timeout (a one-minute copy of the setting in the guest copy); the AC97 capture holds each score, quiet, and silence from the preview and the dialog.

**Evidence** in `~/Documents/Liminal HQ/Afterglow/Savers/images/`: `full-list.png`, `full-dialog-<saver>.png`, `full-fullscreen-<saver>.png`, `full-idle-collection.png`, `compact-list.png`, `compact-dialog-collection.png`, and a sizes table in the pull request.

## Rules for every package

- A worktree under `~/source/worktrees/reactos-liminal/<topic>` on a topic branch; never the main checkout. Commits written to a file and made with `git commit -F`, Conventional Commit subjects, bold-label bodies hard-wrapped, a `Co-Authored-By` trailer naming the builder's own model; files staged by name. Push only the package's branch and open the pull request; never merge, tag or dispatch.
- Private QEMU only: never `pkill` or `killall`, never capture the host screen, never send input to `:0`. Anything that needs X (Wine for a cross-check) runs on its own Xvfb with `DISPLAY` set explicitly on every command and `WAYLAND_DISPLAY` unset.
- Guest copies and work directories under `~/.cache/reactos-liminal` (check `df -h /home` first), removed when done with one `rm -r` of each literal path.

## Owner decisions

Each has a default in place; the file named swaps it.

| Question | Default | Where to swap |
| --- | --- | --- |
| The compact image keeps the savers | Yes, with the Collection selected | `recipes/afterglow-compact.toml`: a trim extra naming each `ReactOS/system32/AG….SCR`, and `reg_files` without `screensaver-afterglow` |
| The default saver and timeout | The Collection after ten minutes | `guest/reg/screensaver-afterglow.reg` |
| ReactOS's own savers in the full image | Kept beside Afterglow's (the full image removes nothing) | A trim extra in `recipes/afterglow.toml` naming the stock `.scr` files |
| Saver settings written into the image | None; the program's defaults | A recipe-level `.reg` file under `HKCU\Software\Liminal HQ\Afterglow Screensavers\<Saver>` |
