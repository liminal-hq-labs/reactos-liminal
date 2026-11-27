# Migration from Quill

The pipeline that builds the Afterglow ReactOS disk was first written inside [Quill](https://github.com/liminal-hq-labs/quill), for its Try ReactOS page, and moves here in stages. This page records where each file came from and what changed on the way.

## History

The code was developed in `liminal-hq-labs/quill` in pull requests #100 (the page, the harness, the trim and the scripted build from the official ISO) and #105 (the pinned Afterglow theme, its pointers, the smooth wallpaper and the 48 px shortcut icons). It was **copied** here, file by file, and rewritten where the move needed it. It was not imported with `git filter-repo`: that would bring Quill-named history into a repository that is not Quill, and `git log` of each source path stays available in Quill.

The copy was taken from the `site/try-reactos/guest/` and `site/try-reactos/tools/` directories as they stood at Quill commit `08e0bd8c0105a1c41f33bf57f9877f7586798b42`, the last commit to touch either directory after #105 merged. Every moved file keeps its original copyright and SPDX header: `(c) Copyright 2026 Liminal HQ, Scott Morris` and `SPDX-License-Identifier: Apache-2.0 OR MIT`.

## What moves, what stays

Generic things move here: the unattended install, the trim, the golden disk, the Afterglow fetch and prepare steps, the pointer patch, the parts and manifest tools and the QEMU helpers. Quill-specific things stay in Quill and become Quill's recipe later: the emblem overlay (`quillify.py` and its wallpaper), the Quill programs and demo documents, the desktop icon builder for the Quill shortcuts, and the page and harness.

The base build was the Afterglow remaster with the `base` trim; that trim is now the compact recipe (`recipes/afterglow-compact.toml`), and the base recipe is the full ReactOS (RL-48). Quill is a downstream consumer of it and owns its own extra trim: the six network card drivers (`e1000`, `rtl8139`, `pcnet`, `dc21x4`, `nvnet`, `netkvm`) that v86 does not emulate move to the Quill repository as a trim file named in its recipe's `[trim] extra` (see [RL-5](decisions.md) and [RL-20](decisions.md)).

## Where each file went

| Quill file (`site/try-reactos/…`) | Here | Status |
|---|---|---|
| `guest/install-golden.sh` | `reactos_liminal/install.py` (`rl install`) | Moved |
| `guest/unattend.inf` | `guest/unattend.inf.in`, filled in from the recipe's `[install]` table | Moved |
| `guest/patch-iso.py` | `reactos_liminal/isopatch.py` | Moved |
| `guest/vm/*` (`qrun.sh`, `mon.py`, `run.sh`, `typ.sh`, `shot.sh`, `wait-exit.sh`) | `reactos_liminal/vm.py` (the same operations, one class) and `reactos_liminal/ppm.py` (screenshots no longer need ImageMagick) | Moved |
| `guest/trim.sh` | `reactos_liminal/trim.py` (`rl trim`) | Moved |
| `guest/trim-list-1..3.txt` | `profiles/base.txt`, the three lists joined in order minus the six network card drivers as already built; the Quill lists move to the Quill repository as an `extra` file holding those six drivers; `profiles/none.txt` removes nothing | Moved |
| `guest/trim-log.txt` | Not moved: a record of one run's bytes freed per item. `rl trim` reports the total | — |
| `guest/build-image.sh` | `reactos_liminal/image.py` (`rl image`) and `reactos_liminal/settings.py`; the Quill payload steps (programs, demo documents, `QUILLDESK.ICO`, the wallpaper file) become the Quill recipe's `[[files]]` and `[[shortcuts]]` | Moved |
| `guest/apply-settings.cmd`, `guest/polish/apply-mouse.cmd` | `guest/cmd/apply-settings.cmd.in`, one script that applies every registry file on the settings CD | Moved |
| `guest/demo-settings.reg`, `guest/polish/*.reg` | Split by purpose into `guest/reg/quiet.reg`, `hide-desktop-icons.reg`, `watermark-off.reg` and `mouse-linear.reg`, plus the display and appearance files the recipe generates. The Quill `Run` key and wallpaper file stay in Quill's recipe | Moved |
| `guest/make-lnk.py` | `reactos_liminal/lnk.py` (writes the same bytes; a test pins two sums) | Moved |
| `guest/zero-free.py` | `reactos_liminal/zerofree.py`, run by `rl parts` with the `fallocate --dig-holes` step `build-all.sh` ran after it | Moved |
| `guest/fetch-afterglow.sh`, `guest/prepare-afterglow.sh`, `guest/afterglow.pin` | `reactos_liminal/afterglow.py` and the `inputs.afterglow` table of the base recipe. The wallpaper step is not moved: the emblem overlay stays in Quill | Moved |
| `guest/prepare-pointers.sh` | `reactos_liminal/patchers.py`, the `afterglow.pointers` patcher | Moved |
| `tools/make-parts.mjs` | `reactos_liminal/parts.py` (`rl parts`): the same part names and `manifest.json` fields, in Python with the `zstd` command, so there is no Node or Bun step | Moved |
| `tools/build-manifest.py`, `tools/job-summary.py` | `reactos_liminal/manifest.py` (`rl manifest`, `rl summary`), with the pinned facts read from the recipe and a consumer's own facts passed as `--input` and `--extra` | Moved |
| `tools/fetch-v86.sh` | `tools/fetch-v86.sh`, unpacking into `$V86_DIR` (default `~/.cache/reactos-liminal/v86`) and refusing a folder inside the repository | Moved |
| (new) | `reactos_liminal/hashing.py` (`rl hash`): `sha256sum`-format sums and a check | New |
| `guest/build-all.sh` | Replaced by the `rl` commands and a recipe | Planned |
| `guest/test_afterglow.py` | Split into this repository's tests, and Quill's overlay tests | Planned |
| `guest/quillify.py`, `guest/quill-*.svg`, `guest/make_desk_icon.py`, `guest/make-wallpaper.sh`, `demo/`, `harness/`, the page | Stay in Quill | — |
| `guest/memfill.c`, `guest/build-memfill.sh` | Stay in Quill (not used by the build) | — |

The table is updated by each change that moves a file.

## What changed in the move

- **Python, not shell, for the logic.** The shell scripts that grew logic (the install, the trim, the fetches) are Python modules, so they can be tested without QEMU. The tools they call (QEMU, mtools, xorriso, zstd) are the same.
- **Recipe parameters instead of constants.** The ISO pin, the locale, the time zone, the computer and owner names, the trim profile and the part size are recipe keys. The names are neutral (`REACTOS`, "ReactOS user"); Quill's recipe sets its own.
- **Part size.** The Quill build cut the disk into 1 MiB parts. The recipe key `outputs.parts.chunk_size` defaults to 8 MiB, the starting point for the measurement that picks the final size.
- **Install.** The three QEMU runs, the answers, the in-place ISO edits and the installed `freeldr.ini` fix behave as before. The golden disk is cached under a name that carries a hash of everything that shapes it (the ISO's hash, the rendered answers, the memory and disk size, and the code that runs the install), instead of a stamp file beside one fixed path. `rl install --dry-run` prints the plan and the QEMU commands without running anything.
- **Parts.** The 1 MiB part size is now the recipe key `outputs.parts.chunk_size`, defaulting to 8 MiB (a note in the recipe says why). On the base image that is 512 parts, 468 of them all zero, 48 MB compressed at zstd level 19.
- **Order.** Patchers run before the trim, and the trim never removes a patched file or a licence file ([RL-19](decisions.md)). Quill's build ran the pointer patch before the trim as well, but nothing enforced it.
- **Profiles.** The trim lists are named profiles in `profiles/`. `base` is the Afterglow remaster's trim and keeps the network card drivers; a downstream trim such as Quill's is an `extra` file in the downstream repository.
- **Work directory.** Large files go under `~/.cache/reactos-liminal` (or `--work`, or `$RL_WORK`) and never inside the repository; the commands refuse a work directory inside the checkout.
