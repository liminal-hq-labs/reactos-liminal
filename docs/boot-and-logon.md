# Boot and logon art

How the Afterglow logon banner and boot screen reach the image. The art itself (the vector masters, the palette and the renderers) lives in `liminal-hq/afterglow-themes` under `desktop/logon/` and `desktop/boot/`; this repository only applies it. Decisions: RL-27 to RL-30 in [decisions.md](decisions.md).

Each patcher takes a stock file from the golden disk, accepts only the exact ReactOS 0.4.16 file it was written for (a SHA-256 allow-list; any other file, a single changed byte included, is refused), checks Afterglow's rendered art against the sums Afterglow records, writes the new art over the old resource, and checks the result against a sum pinned in the code. The patched files are ReactOS code, so they stay in the work directory and on the image, never in git.

## Logon: `afterglow.logon`

ReactOS 0.4.16 draws every logon box (Welcome, Logon, "Please wait…", Security, Locked, Unlock, Change Password) with `msgina.dll` and two 24-bit bitmaps: the 413 × 72 banner (resource 20000) and the 413 × 5 bar (20001). The patcher renders Afterglow's `banner-a.svg` and `bar.svg` with Afterglow's `render.py`, writes each over its resource in place at exactly the same size and depth, recomputes the PE checksum, and installs the result as `ReactOS/system32/agmsgina.dll`. The stock `msgina.dll` stays on the disk.

The `afterglow-logon` registry file (`guest/reg/afterglow-logon.reg`, listed in the recipe's `settings.reg_files`) sets `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\GinaDLL` to `agmsgina.dll`, which winlogon loads instead of `msgina.dll`. The settings step refuses the file when the recipe does not also list the patcher, so the value never points at a file that is not there.

**Off switch.** Delete the `GinaDLL` value (or leave `afterglow-logon` out of `reg_files`): winlogon falls back to the stock `msgina.dll`. No other file changes.

**Not patched.** The friendly Shut Down dialog art, the cold-boot backdrop colours (`win32k.sys`) and the Setup bitmaps (`reactos.exe`, `syssetup.dll`) need art Afterglow has not drawn yet; they follow when it does.

## Boot: `afterglow.boot`

The kernel's boot screen is FreeLoader's menu, then the kernel's own logo at 640 × 480 in 16 colours. The patcher writes two files:

- **`ReactOS/system32/agntoskr.exe`**, a copy of `ntoskrnl.exe` with the Afterglow logo in bitmap 5. The stock logo is 190 × 224 in a 16,504-byte slot; the Afterglow logo is 414 × 366 (the most the "safe to turn off" screen can hold), 16 colours, RLE4-compressed to 11,288 bytes, so it is written over the slot and the resource's size field is lowered. The stock `ntoskrnl.exe` is untouched. The logo's 16 palette entries are the palette of the whole boot screen, which the kernel loads once and shows everything through, and the progress bar's box is kept empty.
- **`freeldr.ini`** on the installed disk (hidden and system attributes put back after the write). The first entry reads "ReactOS (Afterglow)", is the default and starts `Kernel=agntoskr.exe`; the stock entry stays as "ReactOS", one keypress down, and every other entry is unchanged. The menu is FreeLoader's minimal one (`MinimalUI=Yes`, a gold selection bar on black, countdown "Starting ReactOS (Afterglow) in %d s", 10 seconds). It shows no title and no FreeLoader credit line; attribution is carried by the entry name, the release notes and the docs.

**The VGA DAC truncates colours.** The display keeps only the top six bits of each channel, so the boot screen shows each palette colour as `(value >> 2) << 2`, with the two low bits set when the six-bit value is odd, not as drawn. The palette stores the design colours as they are; Afterglow's `palette.json` records both the stored and the shown value, and the boot-frame check below compares against the shown ones.

**Off switch.** Pick the stock entry in the boot menu, or leave `afterglow.boot` out of the recipe's `patchers.list`.

**Two freeldr.ini files.** The install CD's menu (the installer's) is written while the golden disk is made (`rl install` rebuilds the disc from its tree) and is not touched here; this patcher edits the one on the installed disk. The patcher accepts only the file an unattended install leaves (after `rl install` puts back `DefaultOS=ReactOS` and `TimeOut=3`).

## The boot guard

`tests/test_boot_qemu.py` (`pytest -m qemu`, never in CI) boots a built image in a private QEMU and takes `screendump` frames of the boot menu, the kernel logo and the logon screen:

- the menu frame must show the gold selection bar on a black screen;
- the kernel logo frame must hold the Afterglow logo at (113, 23), pixel for pixel through the DAC's colours, everywhere but the progress bar's box;
- the logon frame must hold the Afterglow banner, found by its first row, with no pixel different.

Set `RL_TEST_IMAGE` to the built image. The test copies it, so the image is not written. Run it through `flock ~/.cache/reactos-liminal/qemu.lock` so only one QEMU runs at a time.
