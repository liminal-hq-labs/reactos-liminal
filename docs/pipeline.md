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
2. **Patchers** each take a stock file from the golden disk and yield a patched copy, which is written to the image. `afterglow.pointers` patches a copy of `user32.dll` with Afterglow's own tool, which refuses any other file, and checks the result against the sum Afterglow records.
3. **Trim** with the recipe's profile, then its `extra` lists ([trim.md](trim.md)); the plan and the report name each list, and the trim cannot remove a patched file or a licence file.
4. **Files** the recipe's `[[files]]`, the Afterglow style and pointer files, the `[[shortcuts]]`, and the stock desktop shortcuts it removes.
5. **Settings** the build VM boots the image with a settings CD in drive D:, starts `APPLY.CMD` from the Run box (sent again until the script reports, because the first Run box after a boot is sometimes ignored), and the script applies every registry file and the page file and shuts the guest down.

`--no-settings` skips step 5; `--dry-run` prints the plan and runs nothing.

### Afterglow

The Afterglow source is pinned by commit and by the SHA-256 of the uncompressed tar GitHub serves for it. `rl fetch` downloads it into the work directory, checks the pin, refuses unsafe archive paths and links, and extracts it. `rl image` builds the style with Afterglow's own scripts (needs `llvm-rc`, `lld-link`, and python3 with numpy and Pillow) and checks `afterglow.msstyles` against its pinned sum.
