# The install disc

How `rl` writes ReactOS install discs, and why it writes them the way it does. Two discs are made from the official ISO's file tree: the **install CD** that `rl install` boots (it carries the unattended answers and never leaves the work directory) and the **remastered ISO** that `rl iso` writes (the one that may be published). Both go through [`reactos_liminal/isobuild.py`](../reactos_liminal/isobuild.py) and the edits in [`isotree.py`](../reactos_liminal/isotree.py). The decision is RL-54 in [decisions.md](decisions.md).

## Why a rebuilt disc used to fail

An earlier rebuild with `xorriso -map` stopped in FreeLoader with "Could not load SYSTEM.ALT hive", and that was blamed on rebuilding. The cause is the names.

- **FreeLoader reads one tree.** It reads only the Primary Volume Descriptor's directory tree (`boot/freeldr/freeldr/lib/fs/iso.c`), never the version 2 descriptor, Joliet or Rock Ridge.
- **It compares names naively.** It cuts a name at `;` and compares with `_stricmp`, but does not remove the trailing dot that ISO 9660 levels 1 to 3 add to a name with no extension. A writer's default stores `system` as `SYSTEM.;1`, which is `SYSTEM.` to FreeLoader and never matches `system`. The live entry, the stock default, loads the hive `system` first and stops. Setup's own files all have extensions, so Setup still started, which hid the cause.
- **The official disc is ISO 9660:1999.** It is written by cdrtools `mkisofs -iso-level 4`, which stores names exactly as given: lower case, no version, no forced dot, up to 207 characters, spaces kept.
- **The 32-byte buffer.** FreeLoader copies a name into `CHAR Name[32]` with no bounds check, so a name of 32 characters or more in a folder it searches overflows its stack. The stock disc keeps its long names (to 92 characters) in `reactos/winsxs` and `Profiles`, which FreeLoader never searches.
- **What is not involved.** The boot sector reads the PVD itself and tolerates `;1`. El Torito, the boot info table and the volume label play no part: a disc labelled differently boots the same, and Setup finds its source from its own image path.

The older appended-session `rl iso` had a second problem: xorriso re-recorded the names of every file in the new session's tree under its own rules, so `Default User` became `Default_User` and the side-by-side manifests were cut to 30 characters, which would have broken the live environment's profiles and assemblies.

## The recipe

The flags are ReactOS's own (`boot/boot_images.cmake`):

```sh
TZ=UTC mkisofs -quiet -o out.iso -iso-level 4 \
	-publisher "ReactOS Project" -preparer "ReactOS Project" -volid ReactOS -volset ReactOS \
	-eltorito-platform x86 -eltorito-boot loader/isoboot.bin -no-emul-boot -boot-load-size 4 \
	-hide boot.catalog -sort bootfiles.sort -duplicates-once -no-cache-inodes tree
```

With cdrkit's `genisoimage`, `-eltorito-platform x86 -eltorito-boot` becomes `-b loader/isoboot.bin -c boot.catalog` and `-duplicates-once` is dropped (the disc is about 455 MB instead of 407 MB). Then a hybrid boot record is written over the first 512 bytes: `loader/isombr.bin`'s boot code, the boot image's LBA times 4 at offset 432, one active partition of type 0x96, and the image padded to a whole cylinder (what ReactOS's `isohybrid -b isombr.bin -t 0x96` does).

- **Never** `-R`, `-J` or `-boot-info-table`. FreeLoader reads neither extension, and the table overwrites boot code in `isoboot.bin` (the disc then hangs printing drive numbers).
- **Never xorriso as the writer.** Version 1.5.8 cannot write ISO 9660:1999, mangles long names and spaces, and aborts with a buffer overflow on names of 58 or more characters. xorriso only extracts the official disc (`-osirrox on`, which keeps empty folders).
- **The label is free.** `[iso] volume` sets it (default `ReactOS`).

## What `rl` checks

`write_iso` writes the disc beside its destination and moves it into place only when every check passes, so a disc FreeLoader cannot read is never left behind.

- **Before writing:** no name of 32 characters or more in a folder FreeLoader searches (the root, `loader`, `i386` and its `system32` folders, `reactos` and its `system32` folders); the boot image and the hybrid boot code are in the tree.
- **After writing:** every file and folder in the tree is in the Primary Volume Descriptor's tree under exactly its own name (no upper-casing, `;1`, trailing dot, cut or changed name, and nothing extra); every file FreeLoader opens (`loader/freeldr.sys`, `freeldr.ini`, `i386/txtsetup.sif`, `reactos/system32/config/system` and the rest) is found by FreeLoader's own comparison; the El Torito entry is no-emulation, x86, a load size of 4 sectors, at `/loader/isoboot.bin`; the hybrid record's offset 432 is the boot LBA times 4 and its partition type is 0x96.

## Reproducible

Two builds of the same tree with the same writer are byte for byte the same: every file and folder time is the epoch (`$SOURCE_DATE_EPOCH`, else `[iso] epoch`), the volume descriptors' dates and the date of every directory record are the epoch (the records are rewritten after the writer finishes, because the root's parent record carried the clock's second on some runs), cdrtools' "MKI" sector (the build time and command line) is blanked, files are written in the writer's sorted order, and the hybrid record has a fixed disk id. The two writers give different bytes from each other, so the recipe pins one (`[iso] writer`, `genisoimage 1.1.11`, the version Ubuntu 24.04 ships) and the lock file records it. `rl doctor` and `rl iso` report a different writer; the disc still boots the same. The golden disk's key names the writer that made the install CD, so a different writer builds a new golden disk.

## The two discs

| | Install CD (`rl install`) | Remastered ISO (`rl iso`) |
|---|---|---|
| Menu text | "ReactOS (Afterglow)" in the title and the entry names | the same |
| Default entry | Setup | the live environment, as stock |
| `i386/unattend.inf` | the rendered answers (they partition and format disk 0) | **stock, always** |
| `i386/txtsetup.sif` | Setup starts without the kernel debugger | stock |
| Licence texts, `NOTICE.txt`, `CHANGES.txt` | none | from the finished image |
| Kept | in the work directory, deleted after the install | `WORK/dist/NAME-remaster.iso` |

The two share the menu edit and differ in exactly three files (a test asserts it). `check_no_answers` refuses to write the remastered ISO from a tree whose answers file is not the stock one or whose default entry is Setup. Every text edit is guarded: the stock file must be the exact one ReactOS 0.4.16 ships (an SHA-256 allow-list in `isotree.py`) and each line to change must occur once.

## The second cabinet

`isotree.add_cabinet` adds files as `i386/afterglow.cab` with `i386/afterglow.inf` beside it and one `Cabinet = afterglow.cab` line after `reactos.cab` in `txtsetup.sif`. Setup reads each `[Cabinets]` line in order, takes the file list from the `.inf` beside the cabinet (not from the cabinet itself), and the later cabinet's copy of a file wins, so the stock `reactos.cab` stays byte for byte as shipped. Setup's reader takes MSZIP blocks that each inflate on their own, which `gcab -z` writes. No recipe key feeds it yet; Setup theming will.

## Using the fallback

`rl install --in-place-iso` makes the install CD the earlier way, by overwriting three files of a copy of the official ISO at their own sizes (`isopatch.py`). It stays for one release as a fallback and gives a golden disk of its own key. It does not apply to `rl iso`.

## Evidence

The investigation behind this (`ReactOS ISO rebuild investigation.md`, kept with the Quill notes in `~/Documents/Liminal HQ/Quill/`, with its prototype scripts and screenshots in `iso-rebuild-prototype/`) tried every recipe and booted each in QEMU:

| Recipe | Names in the PVD | Live entry |
|---|---|---|
| Stock disc | as given | boots |
| `xorriso -map`, defaults | `SYSTEM.;1`, 8.3 | "Could not load SYSTEM.ALT hive" |
| `xorriso -as mkisofs -R -J`, level 3 | `SYSTEM.;1` | hive error |
| xorriso with the compliance flags relaxed | `system`, but long names cut | boots, but `Default User` becomes `Default_User` |
| cdrtools `mkisofs` with ReactOS's flags | as given | boots |
| the same, plus the hybrid record | as given | boots, and as a hard disk |
| cdrkit `genisoimage`, level 4 | as given | boots |
| the same with `-boot-info-table` | as given | hangs before the menu |
| a rebuilt install CD with larger answers, a renamed menu entry and a second cabinet | as given | unattended install reached the desktop; the second cabinet's file replaced the stock one |

## Open risks

- **New names in the boot path** must be short. The check refuses 32 characters or more in a searched folder.
- **UEFI.** The 0.4.16 i386 disc has no EFI El Torito entry. If a later release adds `loader/efisys.bin`, add `-eltorito-alt-boot -eltorito-platform efi -eltorito-boot loader/efisys.bin -no-emul-boot`.
- **Real hardware and USB.** The hybrid boot record was proven in QEMU only.
- **Themed files in the second cabinet.** A file that Setup copies from `[SourceDisksFiles]` before the cabinets, or registers early, may need care; test each on an installed disk.
