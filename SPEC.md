# ReactOS Liminal specification

The source of truth for behaviour. A change that alters behaviour updates this file in the same change. Each part is marked **Built** or **Planned**.

## Purpose

Build Afterglow-dressed ReactOS install media, disk images and browser snapshots from a recipe.

ReactOS images dressed by hand drift: the changes live only in a disk, nobody can say which file made which customization, and a rebuild is a day of clicking. ReactOS Liminal turns the official ReactOS 0.4.16 release ISO plus pinned inputs into finished artefacts with no hand step, so every customization is code, every input is pinned by SHA-256, and every output is recorded.

## Users and scenarios

- A maintainer building a themed ReactOS disk for a demo, screenshots or a talk.
- A maintainer remastering the install media so Setup, the logon screens and the first desktop wear Afterglow.
- A consumer project (Quill's Try ReactOS page first) that pins a release, extends a base recipe with its own payload and gets back v86 disk parts, a saved state and a manifest.
- Afterglow, building screenshots of its desktop theme for its docs.

## Non-goals

- Not a ReactOS fork. No ReactOS source changes upstream; bugs found on the way are reported to ReactOS.
- No art of its own. Afterglow draws; ReactOS Liminal applies.
- No Quill-specific content (programs, documents, the emblem, the public page).
- The boot screen stays as ReactOS draws it (FreeLoader's boot, the kernel boot animation), apart from the boot menu entry and the kernel boot logo described below. A guard compares boot frames in every QEMU run (`pytest -m qemu`, [docs/boot-and-logon.md](docs/boot-and-logon.md)).
- No Microsoft Windows images, fonts or redistributables; no VMware Tools.
- No network inside the guest.
- One ReactOS release at a time: 0.4.16. A new release means new pins and a check of every resource id and size.
- No upstream binaries in git, ever.

## Components

| Component | What | Status |
|---|---|---|
| `rl` | Entry point: a bash shim that runs the `reactos_liminal` package in isolated mode (`pyproject.toml` also installs it as `rl`) | Built |
| `reactos_liminal/` | Python 3.12, standard library only: the recipe reader and validator, the hash-checked fetcher and `rl doctor` are built; the install, trim, image and parts steps follow, then the lock writer, PE resource writer, MSCF cabinet writer, ISO remaster and a read-only hive reader | Partly built |
| `pins/` | The upstream ISO (URL, zip and ISO SHA-256) and the hash of every file a patcher accepts; the v86 version. `shell32-icons.json` (the icon patcher's expected result) is built | Partly built |
| `recipes/` | The base recipe `afterglow.toml` (the full ReactOS, nothing removed) and `afterglow-compact.toml` (the base recipe with the `base` trim); consumers extend one of them | Built |
| `guest/` | Unattended answer files, registry files, guest command scripts and trim lists | Planned |
| `vm/` | Private QEMU runs: start, screenshot through the monitor, stop | Planned |
| `harness/`, `web/` | The v86 state builder (TypeScript on Bun, driving headless Chromium) and a minimal page for it; not a public page | Planned |
| `patches/` | GPL-2.0-or-later source patches against the ReactOS 0.4.16 tree, expressing the same changes as the binary patchers | Planned |

## Recipes

**Built** (the loader and validator; the steps they name are built as they land). A recipe is a TOML file. It is declarative where that pays off (inputs, pins, settings, outputs, which steps run) and names code for the steps themselves.

- `[recipe]` names the recipe and optionally `extends` another, by path or as `rl:<path>` inside a pinned ReactOS Liminal release. A later table replaces an earlier one key by key; a `[[steps]]` list is appended unless an entry names `replace = "<id>"`.
- `[inputs.*]` names every input with its pin: the ReactOS ISO (`pin = "pins/reactos-0.4.16.toml#iso"`), the Afterglow release and its manifest SHA-256, a consumer's own directories.
- `[iso]` holds the ISO writer pin (`NAME VERSION`), the volume label and the epoch that dates every file on the disc.
- `[install]` holds the unattended answers: locale, time zone, computer name, owner name, classic shell.
- `[settings]` holds the display mode, page file, desktop icon size, wallpaper path and registry files (default `Dusk` scheme).
- `[wallpapers]` chooses the wallpapers Display Properties lists: `scenes` (`"all"` or a list of Afterglow scenes, written as BMPs to `ReactOS\Web\Wallpaper` under names such as "Afterglow Dusk (dark, smooth)", with sums in `pins/afterglow-wallpapers.json`) and `replace_stock` (remove ReactOS's own wallpapers, `profiles/wallpapers/stock.txt`). The base recipe sets `all` and `true`; the compact recipe sets `[]` and `false` (RL-55).
- `[trim]` names a trim profile (`none` or `base`; the base recipe uses `none`, and `afterglow-compact.toml` extends it with `base`) and may list `extra` trim files beside the recipe, applied after the profile; `[patchers]` lists the patchers to run, which run before the trim.
- `[builds.NAME]` names a Rust project in this repository (`source`) and pins the SHA-256 of what it builds (`sha256`); `rl image` builds it with the project's own pinned toolchain, and a `[[files]]` entry with `source = "built:NAME"` writes the result. `rl lock` measures the pin.
- `[[files]]` copies a file into the image; across `extends`, entries merge by destination (RL-44), and a source is relative to the recipe that wrote it. An entry that writes `settings.wallpaper` supplies the wallpaper, and the Afterglow scene is not rendered. `[[shortcuts]]` writes a desktop shortcut; `settings.remove_desktop_shortcuts` removes stock shortcuts.
- `[[steps]]` lists the steps by `use` (`trim`, `files`, `registry`, `shortcuts`, `afterglow.style`, `afterglow.pointers`, `afterglow.wallpaper`, `logon.msgina`, `logon.win32k-colours`, `hook`), each with an `id` and its parameters.
- `[outputs]` chooses the disk, the v86 parts and state, and the remastered ISO.

A recipe chooses and parameterizes steps; it cannot add a new kind of write. The QEMU stage logic, ready detection, the patchers' safety checks and the remaster stay code.

**The lock file.** A build writes `<recipe>.lock.json` next to its outputs: every resolved input with its SHA-256, the step list after `extends`, the tool versions (QEMU, xorriso, the ISO writer, mtools, zstd, Chromium) and every output's hash. The disk before the state build, the parts and the ISO are expected to be reproducible; the saved state is recorded but depends on timing.

## The `rl` command

**Built:** `rl doctor`, `rl explain`, `rl fetch`, `rl install`, `rl image`, `rl trim`, `rl parts`, `rl manifest`, `rl summary`, `rl hash`, `rl verify`, `rl lock`, `rl pin`, `rl licences`, `rl iso` and `rl key`. The rest is planned.

```text
rl doctor                               # check that the tools the pipeline needs are installed
rl build RECIPE [--out DIR] [--work DIR] [--iso FILE] [--from-golden FILE] [--only STEP] [--keep-work]
rl verify RECIPE [--require INPUT]      # re-check every input pin in the work directory, and the lock file against the recipe
rl lock RECIPE                          # write the lock file beside the recipe: the resolved inputs and their sums
rl licences RECIPE [--out FILE]         # the licences page, as Markdown
rl key RECIPE                           # the cache keys and paths of a recipe as name=value lines, for CI
rl iso RECIPE [--image FILE] [--out FILE]   # the remastered install ISO: the official ISO rebuilt with the Afterglow menu and the image's notices
rl fetch RECIPE                         # download and check every pinned input, nothing else
rl install RECIPE [--iso FILE] [--dry-run] [--force] [--in-place-iso]   # unattended install in a private QEMU; keeps the golden disk
rl image RECIPE [--golden FILE] [--out FILE] [--dry-run] [--no-settings]   # patchers, trim, files, licences, settings
rl pin RECIPE [--afterglow REF] [--pre-merge NOTE] [--check]   # move the Afterglow pin and refresh the hashes that follow from it
rl trim RECIPE IMAGE [--profile NAME]   # trim a working copy of a disk with a profile
rl parts RECIPE IMAGE [--out DIR] [--chunk-size SIZE]   # zero free space, then zstd parts and manifest.json
rl manifest RECIPE DIST [--timing STAGE=SECONDS]   # build-manifest.json for a folder of outputs
rl summary MANIFEST                     # the manifest as a Markdown job summary
rl hash PATH... [--check SUMS]          # SHA-256 sums in sha256sum format, or a check
rl explain RECIPE                       # the resolved recipe after extends, and each step's inputs and outputs
rl patch msgina|win32k|user32|setup-art FILE --manifest M --scheme S --out OUT
rl unpatch …                            # restore from the saved original, or remove the selecting registry value
rl remaster RECIPE --iso FILE --out OUT.iso
rl vm run|shot|stop DISK                # private QEMU with its own monitor socket and pid file
rl serve DIR                            # range-capable static server for a local look in a browser
```

`--work` (else `$RL_WORK`, else `~/.cache/reactos-liminal`) must be outside the repository; `rl` refuses a work directory inside it. `--iso` takes the user's own copy of the official ISO, checked against the pin.

## Outputs

**Planned.**

| Output | What |
|---|---|
| Golden disk | An unattended install from the official ISO: one FAT32 partition, 4 GiB sparse raw image (`rl install`, built). Kept in the work directory as `golden/<recipe>-<key>.img`, where the key is a hash of the ISO's hash, the rendered answers, the memory and disk size, how the install CD is made (the ISO writer's name and version) and the install code, so a disk is reused only while none of them changes |
| Disk image | The golden disk patched, trimmed, configured and dressed (`rl image`, built); free space zeroed and holes punched (`rl parts`, built) |
| v86 parts | `rl parts` (built): zstd parts of the disk named `START-END.img.zst`, each `outputs.parts.chunk_size` bytes (default 8 MiB; every chunk gets a file, all-zero ones included), with `manifest.json` (image size, chunk, counts, compressed bytes and the raw image's SHA-256) |
| v86 state | A saved machine state, taken when the recipe's ready predicate holds (a serial marker or a pixel test) |
| Remastered ISO | `rl iso` (built, not part of v0.1.0): the official ISO rebuilt from its file tree with ReactOS's own recipe (ISO 9660:1999 names, hybrid boot record, written by the writer `[iso]` pins, reproducible), the menu text "ReactOS (Afterglow)" and `LICENSES/`, `NOTICE.txt` and `CHANGES.txt` from the image, never the unattended answers ([docs/iso.md](docs/iso.md), RL-54); Setup art is planned. The finished remaster is the official ISO with an extra cabinet, edited `txtsetup.sif` and `unattend.inf`, themed Setup art and live environment, `LICENSES/`, `NOTICE.txt` and `CHANGES.txt`; `reactos.cab` byte-identical to upstream |
| Build manifest | `rl manifest` (built): every output's size and SHA-256, the pinned inputs, the trim profile and patchers, the part size and the stage timings; `rl summary` prints it as Markdown. `rl lock` (built) writes `recipes/NAME.lock.json`, the resolved inputs and their sums, and `rl verify` fails on drift |

## Image pipeline and trim profiles

**Built.** `rl image` runs a fixed order for every recipe: copy the golden disk (sparse; it is only ever read), run the patchers, trim, write the recipe's files, the Afterglow style and pointer files and its shortcuts, then write the licence files, then apply the registry settings in a build VM. A recipe cannot reorder it.

- **Patchers before the trim.** Each patcher takes a stock file from the golden disk, is checked against it, and yields a patched copy that is written to the image before the trim. The trim never removes a patched file or a licence file (`LICENSES/`, `NOTICE.txt`, `CHANGES.txt`, `Program Files/otvdm/LICENSE`): a profile entry that is, or holds, one is refused before anything is removed, and every patched file is confirmed present afterwards.
- **Trim profiles** are lists of `f PATH` and `d PATH` lines in `profiles/`: `none` removes nothing and is what the base recipe uses, so the Afterglow remaster is the full ReactOS (every app, game, screensaver, applet and font, and Gecko, so the Internet Browser works when there is a network; its wallpapers are replaced by Afterglow's through `[wallpapers]`, not by the trim); `base` is the compact trim, which keeps the network card drivers and the network stack, and `recipes/afterglow-compact.toml` selects it. A recipe adds its own removals with `[trim] extra`, a list of files in the same format that are resolved relative to the recipe that lists them and applied after the profile, in order; they go through the same protection check, and a missing or malformed file is an error naming `trim.extra`. A downstream project keeps such a list in its own repository. A missing path is reported and skipped. `rl trim` works on a copy and refuses a golden disk.
- **Licences.** `LICENSES/` (GPL-2.0, LGPL-2.1, and the Apache-2.0 and MIT texts of this project and Afterglow), `NOTICE.txt` (what the image is, that it is an unofficial remaster not endorsed by the ReactOS Project, the corresponding-source offer, the components and their licences, the credits) and `CHANGES.txt` (every patched file with its SHA-256 before and after, the trim profile with each extra list and every removed path, the files added and the settings applied) are written to the image after the files step and before the settings, generated from the recipe and from the run, as plain ASCII with Windows line ends. The texts come from `licences/`, each checked against a recorded sum, because the official ISO carries none. `rl licences` writes the same facts as a Markdown page (`docs/licences.md`, a test checks it is current).
- **Settings.** The recipe's display size, desktop icon size, wallpaper path and the registry files it lists (`display`, `quiet`, `watermark-off`, `mouse-linear`, `hide-desktop-icons`, `afterglow-logon`, `regional-canada`, `pointer-defaults`) and any `.reg` files of its own (paths relative to the recipe that lists them, applied after the named files) go on a settings CD; the build VM runs one script that applies them and the page file, then shuts down.
- **Regional defaults (built).** The base recipe lists `regional-canada`: the user locale English (Canada) (`HKCU\Control Panel\International` `Locale` `00001009`, `LocaleName` `en-CA`), the location Canada (`Geo` `Nation` `39`, `Name` `CA`), the formats of Windows' en-CA (`sShortDate` `yyyy-MM-dd`, `sLongDate` `MMMM d, yyyy`, `sCurrency` `$`, `iCountry` `1`, `sCountry` `Canada`, metric `iMeasure` `0`), 24-hour time (`iTime` `1`, `sTimeFormat` `HH:mm:ss`, `iTLZero` `1`, `iTimePrefix` `0`, `s1159` `a.m.`, `s2359` `p.m.`) and the system locale (`HKLM\SYSTEM\CurrentControlSet\Control\Nls\Language` `Default` `1009`), written for the logged-in user and for `HKU\.DEFAULT`. The taskbar clock and the Regional Options sample both format with `sTimeFormat`, so both show 24-hour time. The keyboard layout (US) and `InstallLanguage` (`0409`) are unchanged. The Default User profile template is not changed (RL-49).
- **Pointer defaults (built).** The base recipe lists `pointer-defaults`: `UserPreferencesMask` gains `0x2000` (the pointer shadow box on the Pointer tab; no other bit changes), and the stock system scheme "ReactOS Default" is emptied so the scheme list is "Afterglow" and "(None)" (RL-50, RL-51).
- **Patchers built:** `afterglow.pointers` (a patched copy of `user32.dll` carrying the Afterglow system pointers, checked against the sum Afterglow records), `afterglow.start` (`agexplorer.exe`, a copy of `explorer.exe` with the Afterglow Start orb and menu banner, selected by `Winlogon\Shell`; hash-guarded on the stock file, the art and the result), `afterglow.icons` (a patched copy of `shell32.dll` carrying the Afterglow icon set, below), `afterglow.cpl-icons`, `afterglow.program-icons`, `afterglow.dialog-icons`, `afterglow.toolbar-bitmaps` and `afterglow.dialog-bitmaps` (below), `afterglow.logon` (`agmsgina.dll`, the logon banner and bar, selected by `Winlogon\GinaDLL`) and `afterglow.boot` (`agntoskr.exe` with the boot logo, and the Afterglow `freeldr.ini`). See [docs/boot-and-logon.md](docs/boot-and-logon.md).
- **Wallpaper built:** the recipe names an Afterglow scene and the guest path; `rl image` renders it from the SVG master to a BMP, checks it against the recipe's pin, writes it and sets it (`stretch`, `centre` or `tile`). The base recipe uses `dusk-dark-smooth`.
- **Wallpaper list built.** The base recipe's `[wallpapers]` writes all 20 Afterglow scenes to the folder Display Properties lists and removes ReactOS's own wallpapers, so the Background list shows Afterglow's wallpapers only, with the default selected; each BMP is checked against `pins/afterglow-wallpapers.json`, `rl pin` measures them, and `CHANGES.txt` and `NOTICE.txt` say what was replaced. The compact image has its one wallpaper (RL-55).
- **`afterglow.icons` (built).** Takes `shell32.dll` from the golden disk and refuses any file but the stock 0.4.16 i386 one (SHA-256 in `reactos_liminal/shell32_icons.json`). It renders Afterglow's icon set with Afterglow's own `desktop/icons/render.py`, checks each `.ico` against Afterglow's `SHA256SUMS`, and replaces every `shell32.dll` icon group Afterglow's `map.json` verifies (folders, the drives, My Computer, My Documents and its siblings, Desktop, My Network Places, the Recycle Bin, the Control Panel, the shortcut arrow, the Start menu, Programs, Fonts and Printers items, file types and Folder Options) with three 32-bit frames each (48, 32, 16 px). The table adds only groups the map does not name. A frame id that another group also lists is never reused. The new frames go in a new `.agico` section; the resource directory does not grow. A group with fewer than three frame ids of its own is fitted instead of refused (RL-53): it keeps the sizes the stock group holds and takes a spare id for the next size down. The result is checked against the sum in `pins/shell32-icons.json`, keyed by a digest of the icons used. Folders stay one icon whatever they hold, as in ReactOS. The groups and frames are surveyed in [docs/icon-survey.md](docs/icon-survey.md).
- **`afterglow.cpl-icons` and `afterglow.program-icons` (built).** The same method on other files, each guarded by the SHA-256 of its stock file: the Control Panel applets (`access`, `appwiz`, `desk`, `hdwwiz`, `inetcpl`, `intl`, `main`, `mmsys`, `powercfg`, `sysdm` and `timedate`), and `cmd.exe`, `notepad.exe`, `cabview.dll`, `shimgvw.dll` and `netshell.dll` (the Network Connections folder). The groups of each file are the ones the map verifies for it; the files and their stock sums are in `reactos_liminal/icon_families.json`, and the results are pinned per family in `pins/icon-families.json`. `iexplore.exe` (the Internet Browser program) is patched because the base trim keeps it (RL-40). `rapps.exe` (the Applications Manager) is patched too, because the base trim keeps it (RL-42). Two icons are replaced under resources the map does not verify, each checked against the source and the stock file: the Internet Browser desktop item (`shell32.dll` group 512) and the Console applet (`console.dll` group 40); see [docs/icon-survey.md](docs/icon-survey.md) and RL-39.5.
- **`afterglow.program-icons` also covers** the Administrative Tools and Start menu programs and their dialogs: `devmgr.dll`, `devmgmt.exe`, `eventvwr.exe`, `servman.exe`, `msconfig.exe`, `taskmgr.exe`, `regedit.exe`, `clipbrd.exe`, `kbswitch.exe`, `utilman.exe`, `sndvol32.exe`, `wusa.exe`, `fontsub.exe`, both `notepad.exe` files, the tray icons of `stobject.dll`, `explorer.exe` and its Start copy `agexplorer.exe`, and `msgina.dll` and its logon copy `agmsgina.dll`. A copy built by an earlier patcher is patched on top of that patcher's result, and is left alone when no earlier patcher in the recipe wrote it; the stock file it comes from is still hash-checked (RL-53.1).
- **`afterglow.map-icons` (built).** Every other module Afterglow's `map.json` names, so no icon the map verifies is left to the explicit lists: the games (`sol.exe`, `spider.exe`, `winmine.exe`), the accessories (`calc.exe`, `mspaint.exe`, `wordpad.exe` and `write.exe`, `charmap.exe`, `mplay32.exe`, `sndrec32.exe`, `magnify.exe`, `osk.exe`, `dxdiag.exe`, `mstsc.exe`), the applets `joy.cpl`, `telephon.cpl` and `usrmgr.cpl`, `control.exe`, `ctfmon.exe`, `hh.exe`, `winhlp32.exe` and the HTML file type in `ieframe.dll`. The family lists each file with its stock SHA-256 and no group id; the groups come from the map, and the Start menu shortcuts and file types that draw these files' first icon follow. A group the map verified from the ReactOS source alone (`spider.exe` 100, `sndrec32.exe` 107) is checked in the stock file when the patcher runs: when the group is missing, owns no frame of its own or holds an odd frame size it is left alone, logged and listed as skipped in the coverage report. A file that is not on the disk, or that the recipe's trim removes (the `base` profile removes most of these), is left alone with a log line (RL-53.3), so the patch list and the pins are the same for the full and the compact image. A module on the disk that the map names but this repository holds no stock sum for is reported as unverified. `rl pin` writes the report to `docs/icon-coverage.md` (every map resource: patched, skipped or unverified) and `rl pin --check` fails when it is stale (RL-56).
- **`afterglow.dialog-bitmaps` (built).** Writes the dialog bitmaps of Afterglow's `map.json` `bitmaps` list in place: the About banner and its bar (`shell32.dll` 131 and 138), the Log Off dialog (`shell32.dll` 500 to 502) and the Shut Down dialog (`msgina.dll` and `agmsgina.dll` 20002 to 20004), 24-bit, the DIB of the Afterglow `.bmp` over the stock one of the same size and depth. A bitmap whose stock size or depth differs from the map's is refused; the PE checksum is recomputed; the result is pinned per file under `dialog-bitmaps` in `pins/icon-families.json`. The files and their stock sums are in `reactos_liminal/dialog_bitmaps.json`; no resource id is written in this repository (RL-53.2).
- **Patch order and the trim (built).** The base recipe lists `afterglow.pointers`, `afterglow.start`, `afterglow.logon`, `afterglow.icons`, `afterglow.cpl-icons`, `afterglow.program-icons`, `afterglow.dialog-icons`, `afterglow.map-icons`, `afterglow.toolbar-bitmaps`, `afterglow.dialog-bitmaps` and `afterglow.boot`. Patchers that write the same path build on the newest copy, so the loader requires the earlier of each such pair to be listed first. The patch list is the same for the full and the compact recipe; a patcher leaves alone a file that recipe's trim removes, so no patched file is ever a trim target (RL-53.3).
- **`afterglow.dialog-icons` (built).** Replaces the message-box icon groups of `user32.dll` the map verifies (101 warning, 102 question, 103 error, 104 information, and 100, the default program icon) with three 32-bit frames each, in the copy `afterglow.pointers` made, so the file carries the pointers and the icons. The stock file is checked against its SHA-256, the recipe must list `afterglow.pointers` first, and the result is pinned in `pins/icon-families.json` by a digest of the icons and the base copy (RL-52).
- **`afterfetch` (built).** `afterfetch.exe`, a native Rust console program in `tools/afterfetch`, built from source when the image is built (`[builds.afterfetch]`, output pinned by SHA-256) and installed to `ReactOS/system32` by the base recipe's `[[files]]`, so `afterfetch` runs from any command prompt. It prints an Afterglow sunset with a gold-to-slate gradient (console colour attributes from the image's Afterglow table) beside the user and computer, the OS and NT version, the uptime, the memory, the display and the shell, then restores the console's attributes. `afterfetch.cmd` is the plain-text fallback; the `.exe` wins on `PATHEXT` order. See [docs/afterfetch.md](docs/afterfetch.md), RL-41 and RL-43.
- **`afterglow.toolbar-bitmaps` (built).** Replaces cells of the four Explorer toolbar strips in `browseui.dll` in place (every cell the map verifies: Back, Forward, Up, Search, Folders, Views, Move to, Copy to, Delete, Undo, Cut, Paste, Properties, Favourites, Map Drive, Disconnect and Folder Options), so each strip keeps its id, size and 32-bit depth; a strip that differs is refused. The 24 px cells are the 48 px frame halved with integer arithmetic. The strips are described in `reactos_liminal/bitmap_strips.json`; the cells come from the map.
- **`rl pin` (built).** Afterglow is pinned by commit, and the icon patchers' results are pinned by a digest of the icons they used, so moving the pin moves several hashes. `rl pin RECIPE [--afterglow REF]` moves the pin (a commit, tag or branch), fetches that source, measures the tar, style and wallpaper sums and rewrites them in the recipe, runs the icon patchers against the golden disk to record their results in `pins/`, and then runs every patcher the recipe lists as a check. `--check` changes nothing and exits 1 if a hash is stale. A pin on an unmerged Afterglow branch carries a `pre_merge` note (`--pre-merge`). Run `rl lock` afterwards to refresh the lock file. See [docs/afterglow-pin.md](docs/afterglow-pin.md).

## Hash guards and patching

**Planned.** Every patcher edits a file the user already has, and only the one exact file it was written for.

- **Exact-hash guard.** Each patcher holds an allow-list of input SHA-256 values from `pins/` and refuses any other file, including one with a single changed byte. Tests prove the refusal.
- **Same-size, in-place writes.** A bitmap is replaced only by one of the same type, id, width, height and depth, as Afterglow's manifest declares in `replaces`; a manifest entry that does not match the resource found is refused. The patchers write bitmap bytes, colour-table bytes, a new resource section (pointers) and the PE checksum, nothing else; copyright strings and version resources stay.
- **Unique pattern.** A table edit (the 31-entry `SysColors[]` in `win32k.sys`) first checks the pattern occurs exactly once.
- **Undo.** Every patch keeps the original or selects the patched copy by one registry value, and `rl unpatch` reverses it.
- **Copy before write.** Every image is copied before it is written; originals are never touched.

### What is patched

| Target | Change | Off switch | Status |
|---|---|---|---|
| Visual style, schemes, caption metrics, pointer scheme | Files and registry from Afterglow's release | Display Properties | Planned |
| Wallpaper | A BMP rendered from Afterglow's SVG master, set by registry; the full image lists all 20 scenes in place of ReactOS's wallpapers | Display Properties | Built |
| `user32.dll` | System pointers in a new resource section | Restore the original | Built |
| `shell32.dll` | Every icon group Afterglow's map verifies (folders, drives, desktop items, Recycle Bin, shortcut arrow, Start menu, file types) re-pointed at new frames in a new `.agico` section | Restore the original | Built |
| Control Panel applets (`*.cpl`), `cmd.exe`, `notepad.exe`, `cabview.dll`, `shimgvw.dll`, `netshell.dll`, the Administrative Tools programs, `stobject.dll`, `explorer.exe`, `devmgr.dll`, `msgina.dll` | Icon groups re-pointed at new frames in a new `.agico` section | Restore the originals | Built |
| `browseui.dll` | Explorer toolbar cells, in place | Restore the original | Built |
| `msgina.dll` → `agmsgina.dll` | Logon banner and bar, selected by `Winlogon\GinaDLL` (`afterglow.logon`); the Shut Down dialog art (`afterglow.dialog-bitmaps`, in both files) and icon groups (`afterglow.program-icons`); `EnforceFriendlyShutdown` = 1 follows with its art | Delete the `GinaDLL` value | Built (banner, bar, Shut Down art, icons) |
| `shell32.dll` bitmaps | About banner and bar, Log Off dialog background, mark and button strip, 24-bit, in place (`afterglow.dialog-bitmaps`) | Restore the original | Built |
| `win32k.sys` | Cold-boot colours (the `SysColors[]` entries), on by default, as a separate `agwin32k.sys` selected by `SubSystems\Kmode` if ReactOS honours it | One registry value, or restore the original | Planned |
| `reactos.exe`, `syssetup.dll` | Setup watermark and header art | Restore the original | Planned |
| Install media | Menu text, notices and the install CD are rebuilt (RL-54, built); extra cabinet (writer built, nothing in it yet), Setup art, live environment, volume label and autorun icon follow | Use the official ISO | Partly built |
| `freeldr.ini` | A minimal menu (`MinimalUI=Yes`) with a gold selection bar and an entry "ReactOS (Afterglow)"; the stock entry stays as the fallback (`afterglow.boot`) | Pick the stock entry | Built |
| `explorer.exe` → `agexplorer.exe` | Start button orb (bitmap 143) and Start menu banner (bitmap 158), same size and format; selected by `Winlogon\Shell` | Set `Shell` back to `explorer.exe` | Built |
| Kernel boot logo (`agntoskr.exe`) | Bitmap 5 of a copy of the kernel, 414 × 366 in 16 colours, selected by the entry's `Kernel=` line (`afterglow.boot`) | Pick the stock entry | Built |

### What is not patched

`reactos.cab` stays byte-identical to upstream. FreeLoader's code, `ntoskrnl.exe` (the boot logo is in a separate patched copy, `agntoskr.exe`), `bootvid.dll` and `hal.dll` are untouched. No ReactOS logo or orb is used in ReactOS Liminal's own art.

## Release gating

**Written, not yet run.** The workflows are checked by actionlint and by tests of their promises, but only the owner can dispatch them, so no run has happened.

- `build.yml` runs on `workflow_dispatch`, on pull requests that touch the pipeline paths, and when `release.yml` calls it, never on every push. `release.yml` runs on a `v*` tag the owner pushes or on `workflow_dispatch` from `main`, never on a branch push or a schedule, and builds only a commit that is on `main`. Its publishing job uses the protected `release` environment, with the owner as required reviewer. Agents never push a tag or dispatch either workflow. Setup and steps: [docs/release.md](docs/release.md).
- The ISO is built only from the official upstream ISO named in `pins/reactos-0.4.16.toml`, downloaded and checked against both hashes (the SourceForge zip and the ISO). No upstream binary is stored in git or in a cache that outlives the run.
- A release build remasters twice; both ISOs must be byte-identical. An unattended install from the remaster must reach an Afterglow desktop, the boot-frame guard must pass, and with cold-boot colours on, the cold-boot logon backdrop is checked.
- Release assets for v0.1.0: the v86 disk parts, `SHA256SUMS`, `build-manifest.json`, `afterglow.lock.json`, `licences.md`, the source (this repository at the release commit with the patches in `patches/`, and `SOURCE.txt` naming the ReactOS source by tag and commit, the WineVDM pointer and the written offer) and release notes saying it is unofficial. **No ISO in v0.1.0** (owner decision, 2026-11-26): `rl iso` is built, but the ISO is a stock disc with notices until Setup is themed, so it waits for a later release. `NOTICE.txt` and `CHANGES.txt` are on the disk.
- The remastered ISO is not published in v0.1.0; when it is, only after the licence checklist below is complete. Releases are not immutable on GitHub, but a published release is never edited to change its assets: a fix is a new release.

### Licence checklist

Completed by the owner before the first ISO release:

1. `NOTICE.txt` and `LICENSES/` match the 0.4.16 tree's `COPYING`, `CREDITS`, `media/doc/` and `media/fonts/doc/`.
2. The corresponding-source bundle is complete: the 0.4.16 source archive (hash matches the tag), WineVDM's source, the patches applying cleanly, this repository's tag.
3. The modified-files notice is in `CHANGES.txt`, the release notes and, where it costs nothing, the patched file's version resource.
4. The name, the wordmark question and the ReactOS project's trademark guidance are settled, and the courtesy note to the ReactOS project is sent.
5. The CC-BY-NC wallpapers are dropped or kept unchanged and credited (the full image replaces ReactOS's wallpapers with Afterglow's, and the compact trim removes them).
6. Afterglow's clean-room record is confirmed: no ReactOS bitmap copied or traced.
7. No Microsoft file is on the ISO or the installed disk.
8. The off switches are documented and tested.
9. Legal advice is taken on the open points, or the owner decides it is not needed.

## Settings and defaults

**Planned.**

| Setting | Default | Meaning |
|---|---|---|
| `settings.scheme` | `Dusk` | Afterglow scheme for the style, logon and Setup art |
| `settings.display` | `bochsmp`, 1024 × 768 × 32 | Guest display driver and mode |
| `install.locale` | `0409` | Guest locale |
| `install.time_zone_index` | `85` (GMT) | Guest time zone |
| `install.computer_name` | `REACTOS` | Guest computer name |
| `steps.cold-boot-colours.enabled` | `true` | The `win32k.sys` colour patch |
| `media.live` | `true` | Theme the ISO's live environment |
| `outputs.state.threads` | `1` | zstd threads for the state (multi-threaded long-distance matching crashed once) |

## Security and privacy

- Every QEMU run is private: its own monitor socket and pid file, stopped by its own pid, never by a process name.
- Screenshots go through the QEMU monitor. Nothing captures the host desktop.
- The guest has no network.
- Downloads are checked against pinned hashes before use; an archive with unsafe paths is refused.
- On a public repository, workflow artefacts are downloadable by any signed-in GitHub user, so artefacts holding ReactOS binaries are short-lived (7 days at most) and never advertised.

## Limits

- Work space: the scripted build peaks at about 930 MB outside the repository.
- GitHub release assets are limited to 2 GiB each; the remastered ISO is about 410 MB before compression and is not published in v0.1.0.
- One ReactOS release (0.4.16) at a time.
