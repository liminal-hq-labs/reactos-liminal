# Pipeline

The stages `rl` runs, what each keeps, and where. Everything large goes in the work directory (`--work`, `$RL_WORK`, `~/.cache/reactos-liminal`), never in the repository.

## `rl install`

An unattended install of the pinned ISO into a blank raw 4 GiB disk, in three private QEMU runs. Each run ends when the guest restarts or powers off itself.

1. **Text mode.** The derived install CD boots; setup partitions, formats, copies files and writes the boot loader. The installed `freeldr.ini` is then set back to `DefaultOS=ReactOS` and `TimeOut=3`, because an unattended install of this debug build writes a kernel-debugger entry with no menu delay.
2. **Graphical stage.** Setup registers components and restarts.
3. **First boot.** A `GuiRunOnce` line writes `ci: desktop` to the serial port and powers the guest off. The run counts as finished only when that marker is in the serial file and `explorer.exe` is on the disk.

The derived CD is a copy of the official one with three files overwritten in place at the same size: the answers (`/i386/unattend.inf`, from `guest/unattend.inf.in` and the recipe's `[install]` table), `/freeldr.ini` (Setup as the default entry) and `/i386/txtsetup.sif` (the installer's kernel without the debugger). Nothing else on the disc changes.

The disk is raw because setup fails to install the FAT32 boot code on a qcow2 disk.

### The golden disk cache

The result is `golden/<recipe>-<key>.img` in the work directory. The key hashes the ISO's SHA-256, the rendered answers, the memory and disk size, and the files that run the install, so a disk is reused exactly while nothing that shapes it changes. `--force` installs again.

### Private machines

Each machine keeps `mon.sock`, `vm.pid`, `vm.log` and `serial.txt` in its own directory under the work directory. It runs headless, has no network, and is stopped through its monitor or its own pid. QEMU is started through a link named `vmbox`, which no tool that kills by process name will match. Screenshots are the monitor's `screendump`, converted to PNG, once a minute during a run; a timed-out stage keeps its last frame.

### Time

With KVM the three runs take about three to five minutes in all (`--stage-timeout` bounds each; 1,800 seconds with KVM, 7,200 without). Without KVM expect hours.

### Dry run

`rl install RECIPE --dry-run` prints the golden disk's path and key, whether it is cached, where the ISO would come from, each step and the three QEMU command lines. It downloads nothing, writes nothing and starts no process, so CI can test it.

## `rl image`

Turns the golden disk into the finished image in a fixed order: copy, patchers, trim, files, licences, settings. The golden disk is only read.

1. **Copy** the golden disk, sparse, to `images/<recipe>.img` in the work directory.
2. **Patchers** each take a stock file from the golden disk and yield a patched copy, which is written to the image. `afterglow.pointers` patches a copy of `user32.dll` with Afterglow's own tool, which refuses any other file, and checks the result against the sum Afterglow records. `afterglow.start` writes `agexplorer.exe`, a copy of `explorer.exe` with Afterglow's Start orb (bitmap 143) and menu banner (bitmap 158) swapped in place for same-size, same-format DIBs that Afterglow's `desktop/start/render.py` draws from vector masters; it checks the stock file's SHA-256, each DIB against the sum Afterglow records and the result against its own pinned sum, and fixes the PE checksum. The stock `explorer.exe` stays; the settings step sets `Winlogon\Shell` to `agexplorer.exe`, so the way back is one value. `afterglow.icons` patches a copy of `shell32.dll` itself: it renders Afterglow's icon set, replaces every group the map verifies, plus the few the tables add with new frames in a new section, and checks the result against the sum in `pins/shell32-icons.json` ([icon-survey.md](icon-survey.md)). `afterglow.cpl-icons` and `afterglow.program-icons` do the same for the Control Panel applets and the programs, and `afterglow.toolbar-bitmaps` writes Afterglow's cells into the Explorer toolbar strips of `browseui.dll` in place; each file is guarded by its own stock hash and each result by `pins/icon-families.json`. `afterglow.logon` and `afterglow.boot` write `agmsgina.dll`, `agntoskr.exe` and the Afterglow `freeldr.ini`, each checked against the stock file's hash and a pinned result ([boot-and-logon.md](boot-and-logon.md)).
3. **Trim** with the recipe's profile, then its `extra` lists ([trim.md](trim.md)); the plan and the report name each list, and the trim cannot remove a patched file or a licence file.
4. **Files** the recipe's `[[files]]` and its Afterglow wallpaper ([recipes.md](recipes.md#wallpaper)), the Afterglow style and pointer files, the `[[shortcuts]]`, and the stock desktop shortcuts it removes.
5. **Licences** `LICENSES/`, `NOTICE.txt` and `CHANGES.txt` are written to the root of the disk ([Licence files](#licence-files)).
6. **Settings** the build VM boots the image with a settings CD in drive D:, starts `APPLY.CMD` from the Run box (sent again until the script reports, because the first Run box after a boot is sometimes ignored), and the script applies every registry file and the page file and shuts the guest down.

`--no-settings` skips step 5; `--dry-run` prints the plan and runs nothing.

### Licence files

Written after the trim and the files, so the trim's protection of them is a guard and never a race. They are plain ASCII with Windows line ends, because ReactOS's Notepad reads the ANSI code page; the em dashes of the docs become hyphens, and a character that cannot be ASCII stops the build.

- **`LICENSES/`** holds `GPL-2.0.txt` and `LGPL-2.1.txt` (ReactOS and its Wine-derived code), and `Apache-2.0.txt` and `MIT.txt` (Afterglow's art and these tools). The official ISO carries no licence texts, so the first two are the SPDX texts held in `licences/`, each checked against the sum recorded in [`licences/README.md`](../licences/README.md); a changed file stops the build.
- **`NOTICE.txt`** says what the image is, that it is an unofficial remaster not endorsed by the ReactOS Project, the corresponding-source offer (the ReactOS tag and commit, WineVDM, this repository, and the archive each release attaches), the components and their licences, and the credits.
- **`CHANGES.txt`** is generated from the run: each patched file with its patcher and its SHA-256 before (from the golden disk) and after, the trim profile with each extra list and every removed path, the files the recipe and Afterglow added, and the settings applied.

`rl licences RECIPE --out docs/licences.md` writes the same facts as a Markdown page for the docs and the release ([licences.md](licences.md)). A test fails when the committed page is out of date.

### Afterglow

The Afterglow source is pinned by commit and by the SHA-256 of the uncompressed tar GitHub serves for it. `rl fetch` downloads it into the work directory, checks the pin, refuses unsafe archive paths and links, and extracts it. `rl image` builds the style with Afterglow's own scripts (needs `llvm-rc`, `lld-link`, and python3 with numpy and Pillow) and checks `afterglow.msstyles` against its pinned sum. `rl pin` moves the pin and refreshes every hash that follows from it, including the icon patchers' results; see [afterglow-pin.md](afterglow-pin.md).

## `rl verify` and `rl lock`

`rl lock RECIPE` writes `NAME.lock.json` beside the recipe: the pinned inputs as the recipe resolves them (the ISO and Afterglow pins), the SHA-256 of the rendered answers file, of the trim lists and of the recipe's `[[files]]` sources. It holds nothing machine-specific and no time, so it is committed and the same everywhere.

`rl verify RECIPE` re-checks, and writes nothing and downloads nothing:

- **The pins against the work directory.** The ISO zip and the ISO in `dl/`, the Afterglow tar in `afterglow/<commit>.tar` (kept by `rl fetch` for this) and the built `afterglow.msstyles`. A file that is not there yet is `absent`, which passes unless `--require` names it (`iso-zip`, `iso`, `afterglow-tar`, `msstyles`); a file whose sum differs is `drift` and always fails. CI runs it after a cache restore, so a restored ISO is checked again before it is used.
- **The lock against the recipe.** Any key that differs is named (`inputs.reactos_iso.sha256: the recipe says …, the lock says …`). A pin edited without `rl lock` is drift.

## `rl iso`

`rl iso RECIPE` writes the remastered install ISO to `WORK/dist/NAME-remaster.iso`: the official ISO with a second session appended. `xorriso -dev` appends rather than rebuilds, so the system area (the boot record) and every file the first session holds stay at the same blocks; only the volume descriptors move on to describe the new session. The session holds `LICENSES/`, `NOTICE.txt` and `CHANGES.txt`, copied out of the finished image so the disc and the disk agree. `-boot_image any keep` carries the El Torito boot entry into the new session, and `-compliance` makes the session write names the way the official disc does (lower case, no `;1` version suffix, long and deep paths allowed): the boot loader opens `system` by that name, and the default of upper-case `SYSTEM.;1` made it fail with "Could not load SYSTEM.ALT hive". Checked on the official ISO: all 1,237 files keep their blocks and sizes, the boot entry still points at `/loader/isoboot.bin`, and the remaster boots to the LiveCD language screen in QEMU, as the official disc does. The extra cabinet, `txtsetup.sif` and Setup art of the full remaster are the next additions to this step. The official ISO is only read, and the output may not be its path.

`rl key RECIPE` prints the paths and keys a CI cache uses (`iso_sha256`, `golden_key`, `afterglow_commit` and the paths they restore to) as `name=value` lines, and writes nothing.

## `rl parts`

Zeroes the free clusters of the image's FAT32 partition (deleted files leave their data behind), punches holes with `fallocate --dig-holes` so the image is sparse again, then writes `START-END.img.zst` for every chunk of the disk and `manifest.json`. It works on the working image and refuses a golden disk.

- **Chunk size** is the recipe key `outputs.parts.chunk_size`, a power of two of at least 64 KiB, default 8 MiB; `--chunk-size` overrides it for a measurement. v86 fetches one whole part per read, so a smaller part transfers fewer wasted bytes on a cold read and a larger one needs fewer requests and compresses better. Pick by measurement: the Quill demo used 1 MiB.
- **Every chunk gets a file,** including all-zero ones (a few bytes each), because v86 asks for any chunk the guest reads. A short last chunk holds only the bytes it covers.
- **Level** is `outputs.parts.zstd_level` (default 19), run through the `zstd` command with one thread per part and four parts at a time. Parts are identical across runs.

On the base image: 512 parts, 468 all zero, 48 MB compressed, about 22 seconds.

## `rl manifest`, `rl summary`, `rl hash`

`rl manifest RECIPE DIST` writes `DIST/build-manifest.json`: every file under `DIST` with its size and SHA-256 (the parts folder summed as one entry, its own `manifest.json` listed), the pinned ISO and Afterglow hashes, the hash of the rendered answers file, the trim profile, the patchers, the part size, the stage timings (`--timing`), the v86 version, and any consumer facts (`--input NAME=SHA256`, `--extra NAME=VALUE`). The time is `$SOURCE_DATE_EPOCH` when set, so a manifest can be reproduced. `rl summary` turns it into a Markdown job summary, with the source and licence material publishing the image would need. `rl hash PATH --base DIR --out SHA256SUMS` writes `sha256sum`-format sums and `rl hash --check SHA256SUMS` checks them.

## v86

`tools/fetch-v86.sh` downloads the pinned v86 release (0.5.473) and its BIOS files into `$V86_DIR` (default `~/.cache/reactos-liminal/v86`), checking the package and every file against recorded SHA-256 sums and writing nothing if one differs. The saved state a v86 page restores works with one v86 build, so the version goes in the manifest.
