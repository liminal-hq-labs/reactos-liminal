# Migration from Quill

The pipeline that builds the Afterglow ReactOS disk was first written inside [Quill](https://github.com/liminal-hq-labs/quill), for its Try ReactOS page, and moves here in stages. This page records where each file came from and what changed on the way.

## History

The code was developed in `liminal-hq-labs/quill` in pull requests #100 (the page, the harness, the trim and the scripted build from the official ISO) and #105 (the pinned Afterglow theme, its pointers, the smooth wallpaper and the 48 px shortcut icons). It was **copied** here, file by file, and rewritten where the move needed it. It was not imported with `git filter-repo`: that would bring Quill-named history into a repository that is not Quill, and `git log` of each source path stays available in Quill.

The copy was taken from the `site/try-reactos/guest/` and `site/try-reactos/tools/` directories as they stood at Quill commit `08e0bd8c0105a1c41f33bf57f9877f7586798b42`, the last commit to touch either directory after #105 merged. Every moved file keeps its original copyright and SPDX header: `(c) Copyright 2026 Liminal HQ, Scott Morris` and `SPDX-License-Identifier: Apache-2.0 OR MIT`.

## What moves, what stays

Generic things move here: the unattended install, the trim, the golden disk, the Afterglow fetch and prepare steps, the pointer patch, the parts and manifest tools and the QEMU helpers. Quill-specific things stay in Quill and become Quill's recipe later: the emblem overlay (`quillify.py` and its wallpaper), the Quill programs and demo documents, the desktop icon builder for the Quill shortcuts, and the page and harness.

The Quill demo trim is kept exactly as the `demo` trim profile. The base build is the Afterglow remaster, and the Quill demo extends it with that profile (see [RL-5](decisions.md)).

## Where each file went

| Quill file (`site/try-reactos/…`) | Here | Status |
|---|---|---|
| `guest/install-golden.sh`, `guest/unattend.inf`, `guest/patch-iso.py` | Not yet | Planned |
| `guest/vm/*` | Not yet | Planned |
| `guest/trim.sh`, `guest/trim-list-1..3.txt` | Not yet | Planned |
| `guest/build-image.sh`, `guest/apply-settings.cmd`, `guest/demo-settings.reg`, `guest/polish/*` | Not yet | Planned |
| `guest/make-lnk.py`, `guest/zero-free.py` | Not yet | Planned |
| `guest/fetch-afterglow.sh`, `guest/prepare-afterglow.sh`, `guest/prepare-pointers.sh`, `guest/afterglow.pin` | Not yet | Planned |
| `tools/make-parts.mjs`, `tools/build-manifest.py`, `tools/job-summary.py`, `tools/fetch-v86.sh` | Not yet | Planned |
| `guest/build-all.sh` | Replaced by the `rl` commands and a recipe | Planned |
| `guest/test_afterglow.py` | Split into this repository's tests, and Quill's overlay tests | Planned |
| `guest/quillify.py`, `guest/quill-*.svg`, `guest/make_desk_icon.py`, `guest/make-wallpaper.sh`, `demo/`, `harness/`, the page | Stay in Quill | — |
| `guest/memfill.c`, `guest/build-memfill.sh` | Stay in Quill (not used by the build) | — |

The table is updated by each change that moves a file.

## What changed in the move

- **Python, not shell, for the logic.** The shell scripts that grew logic (the install, the trim, the fetches) are Python modules, so they can be tested without QEMU. The tools they call (QEMU, mtools, xorriso, zstd) are the same.
- **Recipe parameters instead of constants.** The ISO pin, the locale, the time zone, the computer and owner names, the trim profile and the part size are recipe keys. The names are neutral (`REACTOS`, "ReactOS user"); Quill's recipe sets its own.
- **Part size.** The Quill build cut the disk into 1 MiB parts. The recipe key `outputs.parts.chunk_size` defaults to 8 MiB, the starting point for the measurement that picks the final size.
- **Work directory.** Large files go under `~/.cache/reactos-liminal` (or `--work`, or `$RL_WORK`) and never inside the repository; the commands refuse a work directory inside the checkout.
