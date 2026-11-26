# Trim profiles

A trim profile is a list of files and folders that `rl image` and `rl trim` remove from a copy of the installed disk. The profiles are `profiles/<name>.txt`, one entry per line: `f PATH` removes a file, `d PATH` removes a folder and everything in it, paths are under the FAT32 root, and `#` starts a comment. A path that is not on the disk is reported and skipped.

| Profile | What it removes |
|---|---|
| `none` | Nothing: the disk as installed |
| `base` | The Afterglow remaster's trim: Gecko (57 MB) and the installer folder, Internet Explorer's stub, the games, screensavers, the DirectX helper libraries, the wallpapers, apps and applets a kiosk does not use, 26 fonts, the Btrfs, ext2 and NFS drivers, the other visual styles and their Start menu entries. **It keeps the network card drivers and the network stack.** |
| `demo` | The Quill browser demo's trim, kept exactly as it shipped: everything in `base`, and also the six network card drivers (`e1000`, `rtl8139`, `pcnet`, `dc21x4`, `nvnet`, `netkvm`) that v86 does not emulate |

`base` is `demo` without those six lines, and a test holds that to be the only difference. Both profiles keep WineVDM (`Program Files/otvdm`), which the Windows 3.x programs need.

## Order and protection

Patchers run before the trim. The trim then refuses to remove, and `rl` checks before it removes anything:

- a file a patcher wrote, or a folder that holds one;
- a licence file or folder: `LICENSES/`, `NOTICE.txt`, `CHANGES.txt` and `Program Files/otvdm/LICENSE`.

A profile that reaches one is an error, not a skipped line. Gecko's own licence file goes with Gecko, which every profile removes. After the trim, every patched file is confirmed to be on the disk.

## Writing a profile

Copy `profiles/base.txt`, change the lines, and name it in a recipe's `[trim] profile` (the recipe validator lists the known names, so a new name is added there). Remove less rather than more where in doubt: a missing file costs a few kilobytes and a wrong removal can stop the guest booting. Measure a leaner profile for emulator speed and pointer latency before building from it.

`rl trim RECIPE IMAGE [--profile NAME]` trims a working copy in place and refuses a disk in the work directory's `golden/` folder.
