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

Turns the golden disk into the finished image in a fixed order: copy, patchers, trim, files, settings. The golden disk is only read.

1. **Copy** the golden disk, sparse, to `images/<recipe>.img` in the work directory.
2. **Patchers** each take a stock file from the golden disk and yield a patched copy, which is written to the image. `afterglow.pointers` patches a copy of `user32.dll` with Afterglow's own tool, which refuses any other file, and checks the result against the sum Afterglow records. `afterglow.start` writes `agexplorer.exe`, a copy of `explorer.exe` with Afterglow's Start orb (bitmap 143) and menu banner (bitmap 158) swapped in place for same-size, same-format DIBs that Afterglow's `desktop/start/render.py` draws from vector masters; it checks the stock file's SHA-256, each DIB against the sum Afterglow records and the result against its own pinned sum, and fixes the PE checksum. The stock `explorer.exe` stays; the settings step sets `Winlogon\Shell` to `agexplorer.exe`, so the way back is one value.
3. **Trim** with the recipe's profile, then its `extra` lists ([trim.md](trim.md)); the plan and the report name each list, and the trim cannot remove a patched file or a licence file.
4. **Files** the recipe's `[[files]]` and its Afterglow wallpaper ([recipes.md](recipes.md#wallpaper)), the Afterglow style and pointer files, the `[[shortcuts]]`, and the stock desktop shortcuts it removes.
5. **Settings** the build VM boots the image with a settings CD in drive D:, starts `APPLY.CMD` from the Run box (sent again until the script reports, because the first Run box after a boot is sometimes ignored), and the script applies every registry file and the page file and shuts the guest down.

`--no-settings` skips step 5; `--dry-run` prints the plan and runs nothing.

### Afterglow

The Afterglow source is pinned by commit and by the SHA-256 of the uncompressed tar GitHub serves for it. `rl fetch` downloads it into the work directory, checks the pin, refuses unsafe archive paths and links, and extracts it. `rl image` builds the style with Afterglow's own scripts (needs `llvm-rc`, `lld-link`, and python3 with numpy and Pillow) and checks `afterglow.msstyles` against its pinned sum.

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
