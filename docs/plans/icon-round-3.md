# Plan: icon round 3

What the Afterglow image still shows in stock ReactOS art once the current pin is patched, ranked by where a visitor to the web demo meets it, and the patch list for the art drawn for it in Afterglow's icons v5 ([liminal-hq/afterglow-themes#63](https://github.com/liminal-hq/afterglow-themes/pull/63), branch `feat/icons-round3`, commit `31449040`). The patch is one package, WP-ICON3-1, with its brief below. When it lands, `SPEC.md`, `docs/icon-survey.md` and `docs/decisions.md` say what was built and this plan is removed.

## What the owner saw

The My Computer window of the Quill remix, at Shell Icon Size 48:

| Seen | Resource | Status before this round |
|---|---|---|
| NT Object Namespace | `ntobjshex.dll` group 1 (`IDI_NTOBJECTFOLDER`; the CLSID's `DefaultIcon` is `%MODULE%,0`, the first group) | Stock: the module has no stock SHA-256 here and the map named none of its groups |
| System Registry | `ntobjshex.dll` group 7 (`IDI_REGISTRYKEY`; `DefaultIcon` `%MODULE%,-7`) | Stock, as above |
| Control Panel | `shell32.dll` group 137 | Afterglow already (`controlpanel`) |
| Floppy, Local Disk, CD Drive | `shell32.dll` 7, 9, 12 | Afterglow already |
| Explorer toolbar: Back, Forward, Up, Search, Folders, Move To, Copy To, Delete, Undo, Views | `browseui.dll` strips 214 to 217, cells 0, 1, 28, 17, 43, 44, 45, 10, 8, 22 | Afterglow already, but soft: see below |
| The Go button beside the address bar | `browseui.dll` bitmaps 230 and 231 (`IDB_SHELL_GO`, `_HOT`), 20 × 20, 32-bit | Stock (the blue footprints) |
| The tree: Desktop, My Documents, My Computer, My Network Places, Recycle Bin | `shell32.dll` 35, 235, 16, 18, 32 | Afterglow already |

**The toolbar glyphs are Afterglow's, drawn soft.** The stock strips are green arrows and Tango-style glyphs; the screenshot shows Afterglow's gold arrows, violet magnifier and rose cross. They read as stock-like for two reasons: the shapes follow the familiar classic idiom, and `afterglow.toolbar-bitmaps` makes the 24 px cells by halving the 48 px frame (`patch_bitmaps.halve`), so the 1.5-unit keyline of the 48 px master lands at 0.75 px and blurs. Afterglow has rendered its own 24 px profile of every toolbar glyph since icons v2 (`ico24/ID.ico`, keyline tuned for 24 px), and the patcher never reads it. Using it is part of WP-ICON3-1; a different glyph language is an owner decision.

## Method

- **Files.** Every PE file under `ReactOS/` and `Program Files/` of the stock 0.4.16 i386 install, copied read-only from the golden disk with mtools (`mcopy`, no mount, nothing written to the disk): 1,344 files, 129 of them with icon groups. `shell32.dll` and `browseui.dll` match their pinned stock SHA-256. No VM was booted.
- **Resources.** Every `RT_GROUP_ICON` with its frames and every `RT_BITMAP` with its size and depth, read with `reactos_liminal.pe_resources`: 769 icon groups and 1,184 bitmaps.
- **What is patched.** A group or cell is Afterglow when `docs/icon-coverage.md` (the current pin) lists it as patched, and a bitmap when the toolbar cells or the `bitmaps` list of Afterglow `main`'s map name it: 207 groups and 69 bitmaps (the 69 include the 54 card faces of Afterglow #62, drawn and still waiting for their patch).
- **Where a visitor meets it.** Each remaining resource is placed by the ReactOS 0.4.16 source (the code and templates that load it, read from the `0.4.16-release` tree) and by the path a visitor takes through the demo: desktop, Start menu, My Computer, an Explorer window, the Run dialog, Control Panel, then the programs. Afterglow's [stock art survey](https://github.com/liminal-hq/afterglow-themes/blob/main/docs/reactos-stock-art-survey.md) has the per-resource tables of every file; this plan is the ranked remainder.
- **The trim.** "Compact" says whether the `base` trim keeps the file; everything ranked P1 and P2 is in both images.

## Survey: what is still stock

| Priority | Where it appears | Icon groups | Bitmaps | Files | This round |
|---|---|---|---|---|---|
| **P1** | My Computer: NT Object Namespace, System Registry and what they hold | 8 | 0 | `ntobjshex.dll` | All 8: 5 new icons, 3 existing through `also` |
| **P1** | Explorer address bar: the Go button | 0 | 2 | `browseui.dll` | Both: new `go` bitmap |
| **P1** | Run dialog, delete, recycle and replace confirmations, Properties of several files | 5 | 0 | `shell32.dll` 25, 133, 142, 161, 256 | All 5: 1 new icon, 4 existing |
| **P1** | Display Properties: the (None) wallpaper entry | 1 | 0 | `shell32.dll` 200 | New `none` |
| **P2** | Registry Editor: value icons and the address button | 3 | 0 | `regedit.exe` 102, 135, 136 | 135 and 136 (new); 102 is 12 px only, left stock |
| **P2** | Task Manager: a window with no icon, the tray meter | 2 | 2 | `taskmgr.exe` 137, 138; bitmaps 150, 153 | 137 and 138 (`program`); the tray meter bitmaps left |
| P2 | Applications Manager: toolbar and categories | 29 | 0 | `rapps.exe` 11 to 23, 50 to 65 | Next tier |
| P2 | Device Manager: device classes, root and toolbar | 37 | 2 | `setupapi.dll`, `devmgr.dll` 21, 22 | Next tier |
| P2 | Folder Options, General tab pictures | 6 | 0 | `shell32.dll` 182 to 187 | Next tier |
| P2 | Taskbar and Start Menu Properties previews | 0 | 25 | `explorer.exe` 143 to 189 (the shell runs `agexplorer.exe`, whose copies these are) | Next tier |
| P2 | Tray balloon icons | 12 | 0 | `comctl32.dll` 22, 25, 28, 501, three copies (`system32` and two in `winsxs`) | Next tier (the source of these four ids is not in the local 0.4.16 tree, so the map cannot verify them yet) |
| P3 | Control Panel applets' inner pages (Sounds, Power schemes, Internet Options, System, Add/Remove, input, display adapter and monitor tabs) | 87 | 9 | `mmsys.cpl`, `powercfg.cpl`, `inetcpl.cpl`, `sysdm.cpl`, `appwiz.cpl`, `hdwwiz.cpl`, `input.dll`, `desk.cpl`, `timedate.cpl` and 9 more | Later |
| P3 | Programs and libraries (help viewer, image viewer toolbar, zip folders, certificates, console IME, NTVDM and others) | 70 | 74 | 50 files | Later |
| P3 | Common dialogs: the Win 3.1 file dialog's drives, the Change Icon picker library | 48 | 1 | `comdlg32.dll`, `pifmgr.dll` | Later |
| P3 | Administrative tools' inner icons | 17 | 10 | `eventvwr.exe`, `servman.exe`, `certmgr.exe`, `cleanmgr.exe`, `frag.exe` | Later |
| P3 | Tray and hardware: Mouse Keys states (16 px, 8-bit only), Safely Remove window, network and logon pictures | 21 | 2 | `stobject.dll` 440 to 449, `hotplug.dll`, `netshell.dll`, `msgina.dll`, `indicdll.dll`, `msutb.dll` | Later |
| P3 | The standard toolbar strips programs ask for (`IDB_STD_*`, `IDB_VIEW_*`, `IDB_HIST_*`) | 0 | 21 | `comctl32.dll`, three copies | Later |
| P3 | Printers folder, drive properties | 2 | 0 | `shell32.dll` 17, 1001 | Later |
| P4 | Never loaded by 0.4.16 (unused `shell32.dll` groups and strips, `explorer.exe` 102 to 111, 205, 250 to 256, the brand band, Setup's wizard) | 187 | 18 | `shell32.dll`, `explorer.exe`, `browseui.dll`, `syssetup.dll` | Not drawn |
| Left out | ReactOS logo art: `IDI_WINLOGO`, the System Properties picture and its mask, `userinit.exe`'s | 1 | 4 | `user32.dll` 105, `sysdm.cpl` 55 and 56, `userinit.exe` 100 and 101 | Branding rule: never restyled |
| Elsewhere | Card backs (11 neutral backs), the boot screen, the classic system bitmaps | 0 | 59 | `cards.dll`, `ntoskrnl.exe`, `user32.dll` | Their own patchers and passes (the card faces' patch is its own work-queue item) |
| Not shown | The other visual styles' bitmaps (Afterglow's style is active) | 0 | 851 | `lautus`, `lunar`, `mizu`, `modern` `.msstyles` | None |
| Trimmed | Files the `base` trim removes (full image only) | 26 | 35 | `mspaint.exe`, `osk.exe`, `sndrec32.exe`, the savers and others | Full image, later |
| | **Total still stock** | **562** | **1,115** | | **20 resources this round** |

Every P1 resource is covered by this round, and two of the P2 programs' icons with them. The 20 resources are 18 icon groups and 2 bitmaps.

The review sheets (stock beside Afterglow at 48, 32 and 16 px on the white list, cream and Dusk, per group; the toolbar's 24 px cells now and from the 24 px profile; and the next tier in stock) are in the owner's `Afterglow/ReactOS/Screenshots/10 Icon round 3`.

## Patch list

Every row was dry-run with this repository's own `patch_icon_groups` on scratch copies of the stock files and Afterglow's rendered `.ico` files at commit `31449040`, and the Go bitmap was written in place over scratch copies of `browseui.dll` 230 and 231: every group took its icon and every file parsed again.

| Module (path) | Stock SHA-256 | Resource | Afterglow | Stock frames | Own ids | Written | Table change |
|---|---|---|---|---|---|---|---|
| `ntobjshex.dll` (`ReactOS/system32`) | `3a969f9afdfa3f17ad13e8b3156bf2167444d9628d8e107d00e98e37e7eb6868` | group 1 | `ntnamespace` (new) | `16@8 32@8 48@8 16@32 32@32 48@32` | 6 | 48, 32, 16 | New `map-icons` file in `icon_families.json` |
| | | group 2 | `folder` | as group 1 | 6 | 48, 32, 16 | |
| | | group 3 | `folderopen` | as group 1 | 6 | 48, 32, 16 | |
| | | group 4 | `ntobject` (new) | `48@8 32@8 16@8 48@32 32@32 16@32` | 6 | 48, 32, 16 | |
| | | group 5 | `ntdevice` (new) | `48@8 32@8 24@8 16@8 48@32 32@32 24@32 16@32` | 8 | 48, 32, 16 (the 24 px ids go unreferenced) | |
| | | group 6 | `ntport` (new) | `16@8 32@8 16@32 32@32` | 4 | 48, 32, 16 | |
| | | group 7 | `regkey` (new) | as group 1 | 6 | 48, 32, 16 | |
| | | group 8 | `regbinary` (new) | as group 4 | 6 | 48, 32, 16 | |
| `regedit.exe` (`ReactOS`) | already in `icon_families.json` | group 135 | `regstring` (new) | `16@32` | 1 | 16 (fitted) | None |
| | | group 136 | `regbinary` (new) | `16@32` | 1 | 16 (fitted) | None |
| `taskmgr.exe` (`ReactOS/system32`) | already listed | group 137 | `program` | `32@32` | 1 | 32 (fitted) | None |
| | | group 138 | `program` | `16@32` | 1 | 16 (fitted) | None |
| `shell32.dll` (`ReactOS/system32`) | `88858710…cf72` (pinned) | group 25 | `run` | 9 frames | 9 | 48, 32, 16 | None |
| | | group 133 | `documents` | 6 frames | 6 | 48, 32, 16 | None |
| | | group 142 | `recyclefull` | 9 frames | 9 | 48, 32, 16 | None |
| | | group 161 | `delpermanent` (new) | `32@32 32@8` | 2 | 32, 16 (fitted) | None |
| | | group 200 | `none` (new) | 8 frames | 8 | 48, 32, 16 | None |
| | | group 256 | `folder` | 6 frames | 6 | 48, 32, 16 | None |
| `browseui.dll` (`ReactOS/system32`) | `4a8f287b…7e` (pinned) | bitmap 230 | `bmp/go.bmp` (new) | 20 × 20, 32-bit, `BI_RGB`, straight alpha, 1,640 bytes | — | in place, same size | Code: the toolbar patcher writes the map's `bitmaps` for `browseui.dll` |
| | | bitmap 231 | `bmp/go.bmp` | as 230 | — | in place | as above |
| | | strips 214 and 215, 18 cells | the existing glyphs | 24 px cells | — | in place | Code: cells from `ico24/ID.ico`, not the halved 48 px frame |

**Size and slot constraints, checked against the stock resources.**

- **Depth.** Every group is written with 32-bit frames only, as every Afterglow group is; no 16-colour or 256-colour variant is needed, because the patcher writes no 4 or 8-bit frames anywhere and the demo and v86 builds run at 32 bits per pixel. The Go bitmap is 32-bit like the stock one, so it is written over it byte for byte in length.
- **Frame ids.** No target group shares a frame with another (`stock_group_problem` is clean for all 18), and none is below one id of its own. The four fitted groups keep the sizes the stock group holds: `regedit.exe` 135 and 136 and `taskmgr.exe` 138 at 16 px, `taskmgr.exe` 137 at 32 px, and `shell32.dll` 161 at 32 px plus a 16 px frame on its spare id.
- **Size growth.** The new `.agico` sections add 120,832 bytes to `ntobjshex.dll`, 2,560 to `regedit.exe`, 5,632 to `taskmgr.exe` and 80,896 to `shell32.dll` (on top of what its existing groups add). `browseui.dll` does not grow.
- **Left out by constraint.** `regedit.exe` 102 (`IDI_ARROW`, the address button, loaded at 12 × 12 and holding one `12@24` frame) is refused by `stock_group_problem` (a size other than 16, 24, 32 or 48) and Afterglow renders no 12 px frame. The Mouse Keys tray states (`stobject.dll` 440 to 449) hold only `16@8` frames.
- **The trim.** Every file above is kept by the `base` trim, so the full and the compact image take the same list.

## WP-ICON3-1 — patch the round-3 art (builder brief, in full)

Paste this to a Sonnet builder.

> **Task.** Patch Afterglow's icon round 3 into both ReactOS Liminal images: the 18 icon groups and the Go button's two bitmaps in the patch list of `docs/plans/icon-round-3.md`, and the Explorer toolbar's 24 px cells from Afterglow's 24 px profile. Read `AGENTS.md`, `SPEC.md`, `docs/icon-survey.md`, `docs/afterglow-pin.md`, `docs/plans/icon-round-3.md` and the Afterglow PR [liminal-hq/afterglow-themes#63](https://github.com/liminal-hq/afterglow-themes/pull/63) first. Work in a worktree under `~/source/worktrees/reactos-liminal/<topic>` on a `feat/` branch; never in the main checkout. Use the work directory `~/.cache/reactos-liminal` (or `RL_WORK`), never one inside the repository.
>
> **Needs.** The Afterglow PR merged on the owner's look, at its merge commit M. Until then you may build against its branch head `31449040` with `./rl pin RECIPE --afterglow 31449040 --pre-merge "liminal-hq/afterglow-themes#63"` and move to M before your PR leaves draft.
>
> **Finish line.** `./rl image` of `recipes/afterglow.toml` and `recipes/afterglow-compact.toml` writes every row of the patch list; `docs/icon-coverage.md` (regenerated by `./rl pin`) lists all 20 resources as patched, including both Go bitmaps, with no unverified row for `go`; the toolbar's 24 px cells are Afterglow's `ico24` frames; a booted image shows them (below); the gate is green.
>
> **Files owned.** `reactos_liminal/icon_families.json` (one `map-icons` file), `reactos_liminal/patch_bitmaps.py`, `reactos_liminal/patch_icons.py` (only `verified_icons` and what reads Afterglow's render), `reactos_liminal/coverage.py`, `reactos_liminal/bitmap_strips.json` (only if the Go bitmap needs a row), `recipes/afterglow.toml`, `recipes/afterglow.lock.json`, `recipes/afterglow-compact.lock.json`, `pins/icon-families.json`, `docs/icon-coverage.md` (generated), `docs/icon-survey.md`, `SPEC.md`, `docs/decisions.md` (RL-65), `tests/`, and the removal of `docs/plans/icon-round-3.md`.
>
> **Must not touch.** Any art (art lives in Afterglow), `guest/`, `profiles/`, `tools/afterfetch` and its pin, `afterglow.dialog-bitmaps` (one patcher per file: `browseui.dll` stays the toolbar patcher's), `.github/workflows/`.
>
> **Steps.**
>
> 1. **Pin.** `./rl pin recipes/afterglow.toml --afterglow <M or 31449040 with --pre-merge>`, then the compact recipe. The new `shell32.dll`, `regedit.exe` and `taskmgr.exe` groups need no table change: the patchers read them from the map.
> 2. **`ntobjshex.dll`.** Add a `map-icons` file to `icon_families.json`: path `ReactOS/system32/ntobjshex.dll`, stock SHA-256 `3a969f9afdfa3f17ad13e8b3156bf2167444d9628d8e107d00e98e37e7eb6868` (481,792 bytes; check it on the golden disk). Its eight groups come from the map.
> 3. **The Go button.** Extend `afterglow.toolbar-bitmaps` so that, for `browseui.dll`, it also writes every entry of the map's `bitmaps` list whose module is `browseui.dll` (230 and 231, art `bmp/go.bmp`, `[20, 20]`, 32 bits). Write the bitmap without its 14-byte file header over the stock resource in place; refuse a stock resource whose info header or length (40 + 20 × 20 × 4 = 1,640 bytes) differs from the entry, and art of another size or depth. Read `bmp/go.bmp` from Afterglow's render and check it against Afterglow's `desktop/icons/SHA256SUMS` (the `bmp/go.bmp` line) as the `.ico` files are checked. Record each with `note_patched(..., kind="bitmap")` so the coverage report can list it.
> 4. **The 24 px cells.** `cell_rows(ico, 24)` takes the 24 px frame of Afterglow's `ico24/ID.ico` instead of `halve`-ing the 48 px frame; verify `ico24/` files against `SHA256SUMS` like `ico/`. Afterglow ships an `ico24` file for all 18 toolbar glyphs and Go; refuse a toolbar cell whose `ico24` file is missing rather than falling back. Remove `halve` if nothing else uses it, and update the module docstring.
> 5. **Coverage.** `go` has `resource: null` in the map and two `bitmaps` entries (kind `bitmap`, a new kind in the map). Add the map's `bitmaps` entries for modules a patcher in this repository writes as rows (`bitmap 230`, `bitmap 231`), so `go` is reported as patched and not unverified; keep the existing rows' order and wording otherwise. `./rl pin --check` must pass after `./rl pin`.
> 6. **Docs.** `SPEC.md`: the toolbar patcher also writes the Go button and builds its 24 px cells from Afterglow's 24 px profile. `docs/icon-survey.md`: the Explorer toolbar section (24 px from `ico24`, the Go bitmap), `ntobjshex.dll` in "Every other module the map names", the fitted groups (`regedit.exe` 135 and 136, `taskmgr.exe` 137 and 138, `shell32.dll` 161) in "Groups with one or two frames". `docs/decisions.md`: RL-65 "Round-3 art follows the pin" with RL-65.1 (Go written in place by the toolbar patcher) and RL-65.2 (24 px cells from the 24 px profile). Remove `docs/plans/icon-round-3.md` and the line that links it.
> 7. **Tests** (synthetic fixtures only, made at test time): a PE with a 20 × 20 32-bit `RT_BITMAP` is patched in place and keeps its length; a 21 × 20 stock bitmap, a 24-bit one and art of another size are each refused; a one-byte-changed stock `browseui.dll` stand-in is refused by its hash; a toolbar cell takes the `ico24` frame's pixels, not the halved 48 px frame's (make the two differ); a missing `ico24` file is refused; the coverage report lists a `bitmaps` entry as patched.
> 8. **Booted check.** Build both images with `./rl image`. Boot each in your own private headless QEMU with its monitor socket and pid file under a short path in `/tmp` (for example `/tmp/rl-i3-<pid>/mon`), no network, and stop it through its monitor or its own pid; never `pkill` or `killall`, and never touch a VM you did not start. Take screens with the monitor's `screendump` only (no host screen capture) of: My Computer (both namespace folders, the Go button, the toolbar), NT Object Namespace opened (directories, a device such as `\Device`, a port under `\RPC Control`, other objects), System Registry opened to a key with values, Registry Editor with string and binary values, the Run dialog, the confirmation when deleting a file with Shift held and when sending one to the Recycle Bin, Display Properties' wallpaper list scrolled to (None), Task Manager's Applications tab. Save them as PNGs to `~/Documents/Liminal HQ/Afterglow/ReactOS/Screenshots/10 Icon round 3/` named `after-<what>-<full|compact>.png`. Delete the scratch disks and the run folder when done, one path per command, and keep `df -h /home` above 20 GB.
>
> **Gate.** `ruff format --check`, `ruff check`, `python3 -m pytest`, `bash scripts/check-headers.sh`, `bash scripts/check-no-binaries.sh`, markdownlint (`docker run --rm -v "$PWD:/workdir" davidanson/markdownlint-cli2:v0.17.2 "**/*.md"`), `./rl pin --check` for both recipes.
>
> **Commits and PR.** Conventional Commits written to a file and committed with `git commit -F`, body in markdown with bold labels and no headings, hard-wrapped, ending `Co-Authored-By: <your model> <noreply@anthropic.com>`; stage explicit paths, never `git add -A`. PR title capitalized imperative, `## Summary` with bold lead-in bullets, `## Test plan` with the commands, ending with an unchecked `- [ ] Not verified: …`. Labels `enhancement`, `afterglow`, `reactos`. Open it; do not merge. Report the PR URL, the coverage counts, the screenshot paths and anything the booted check showed still in stock.

## WP-ICON3-2 — design the next tier (designer brief)

> **Task.** An Opus design pass in `liminal-hq/afterglow-themes` (worktree, `feat/` branch, PR not merged) for the P2 rows of the survey in `docs/plans/icon-round-3.md` that this round left: the Applications Manager's toolbar and categories (`rapps.exe` 11 to 23 and 50 to 65, mostly 24 px or `24@8 24@32`, so check the frames per group), Device Manager's device classes (`setupapi.dll`, the 11 `hivesys.inf` names first, then the class installers' table; drawn as the device, not an applet plate, because the tree shows them at 16 px), its root and toolbar bitmaps (`devmgr.dll` 21 and 22), the Folder Options pictures (`shell32.dll` 182 to 187, 32 px only), and the Taskbar Properties previews (`explorer.exe` bitmaps, 336 × 35 and 300 × 180, which `afterglow.start` would write into `agexplorer.exe`). Verify every id against the ReactOS 0.4.16 source and the stock binary before naming it in the map; the tray balloon icons (`comctl32.dll` 22, 25 and 28) need the comctl32 source, which the local tree lacks. Deliver vector masters with scripted renders, map entries, before-and-after sheets in `Screenshots/11 …`, and a patch list for a reactos-liminal builder.

## WP-ICON3-3 — make the survey a command (builder brief)

> **Task.** Add `rl survey-icons GOLDEN_OR_IMAGE [--out FILE]` to reactos-liminal: read every PE file of a disk read-only with mtools (never mounted, never written), list every `RT_GROUP_ICON` (frames) and `RT_BITMAP` (size and depth), mark each patched or stock from `docs/icon-coverage.md` and the pinned map's `bitmaps` and toolbar cells, mark whether the `base` trim keeps the file, and write the counts by module as Markdown. It reproduces the counts in this plan's survey table (769 groups, 1,184 bitmaps, 207 and 69 patched at the current pin). Standard library only, `-I`, tests with synthetic PE fixtures, `SPEC.md` and `docs/icon-survey.md` updated. Owned: `reactos_liminal/icon_survey.py`, `cli.py` (one command), `tests/`, the two docs.

## Rules for every package

The repository's `AGENTS.md` applies in full: no ReactOS binary, image or art in git; every patcher hash-guarded and same-size or new-section; private QEMU only and no host desktop capture; worktrees under `~/source/worktrees/reactos-liminal/`; scratch cleaned up with plain commands, one full path each.

## Owner decisions

- **Toolbar glyph language.** The glyphs are Afterglow's already and keep their shapes; WP-ICON3-1 makes them crisper with the 24 px profile. A different language (on the dusk plate, or two-tone violet and gold) would be an Afterglow redraw of `back` to `views` in `gen_e.py` and `gen_v2.py`.
- **The Go button** is a gold arrow on a violet disc, so it does not repeat the bare Forward arrow; the alternative (a bare arrow, or an Enter-style bent arrow) is `draw_go` in Afterglow's `gen_v5.py`.
- **A registry value in System Registry** (`ntobjshex.dll` 8) takes `regbinary`; giving it `regstring` or its own icon is one `also` entry in Afterglow's `map.json`.
- **An NT object** is a cube in Registry Editor's colours; a plain page (`doc`) instead would be one map change and dropping `ntobject` from `gen_v5.py`.
- **Registry Editor's 12 px address button** (`regedit.exe` 102) stays stock; covering it needs a 12 px frame in Afterglow's render and 12 px allowed in `patch_icons.SIZES` and `stock_group_problem`.
- **ReactOS logo art** (`user32.dll` 105, `sysdm.cpl` 55 and 56, `userinit.exe` 100 and 101) stays stock under the branding rule.
- **Pinning before the merge.** WP-ICON3-1 may start on the Afterglow branch head with `--pre-merge` and moves to the merge commit before review; waiting for the merge instead is the safer and slower path.
