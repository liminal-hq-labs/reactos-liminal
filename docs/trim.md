# Trim profiles

A trim profile is a list of files and folders that `rl image` and `rl trim` remove from a copy of the installed disk. The profiles are `profiles/<name>.txt`, one entry per line: `f PATH` removes a file, `d PATH` removes a folder and everything in it, paths are under the FAT32 root, and `#` starts a comment. A path that is not on the disk is reported and skipped.

| Profile | What it removes |
|---|---|
| `none` | Nothing: the disk as installed. The base recipe (`recipes/afterglow.toml`) uses it, so the Afterglow remaster is the full ReactOS |
| `base` | The compact trim, selected by `recipes/afterglow-compact.toml` (the profile keeps its file name, `profiles/base.txt`): Gecko (57 MB) and the installer folder, the games, screensavers, the DirectX helper libraries, the wallpapers, apps and applets a kiosk does not use, 26 fonts, the Btrfs, ext2 and NFS drivers, the other visual styles and their Start menu entries. **It keeps the network card drivers and the network stack.** |

The trim is not what replaces ReactOS's wallpapers in the full image: that is the `wallpapers.replace_stock` switch, which removes the files in `profiles/wallpapers/stock.txt` and is not a trim profile ([recipes.md](recipes.md#the-wallpaper-list)). The `base` profile removes the same files, so the compact image has no stock wallpapers either way.

`base` is a complete list in its own right and keeps WineVDM (`Program Files/otvdm`), which the Windows 3.x programs need. It also keeps `Program Files/Internet Explorer/iexplore.exe` (75 KB): the Internet Browser desktop item and the web protocol handlers run it, and with it missing a double-click did nothing and said nothing. Without Gecko its window opens blank; the compact image leaves Gecko out (RL-40), and the full image keeps it, so the browser works there when there is a network (RL-48). It keeps `ReactOS/system32/rapps.exe` (1.7 MB), the Applications Manager that the desktop shortcut and the Start menu entry run (RL-42); only its console twin `rapps.com` is removed. With no network the Manager opens its Updating Database box and then says "Unable to download the package! Check Internet Connection!", so it fails with a message and does not hang; with a network it works as in stock ReactOS.

## Order and protection

Patchers run before the trim. The trim then refuses to remove, and `rl` checks before it removes anything:

- a file a patcher wrote, or a folder that holds one;
- a licence file or folder: `LICENSES/`, `NOTICE.txt`, `CHANGES.txt` and `Program Files/otvdm/LICENSE`.

A list that reaches one is an error, not a skipped line, and that includes every `extra` list. To keep that true when a recipe removes more, the patchers run knowing the recipe's trim (the profile and its `extra` lists): a patcher that would write a file the trim removes leaves it alone and logs it (RL-53.3). The patch list is the same for the full and the compact recipe, and the pins do not change with the trim. The `base` profile removes none of the files the patchers write; a test checks it. Gecko's own licence file goes with Gecko: the full image keeps both, and the compact image removes both. After the trim, every patched file is confirmed to be on the disk.

## Shortcuts of removed programs

A removed program leaves its shortcuts behind, so the Start menu would list Calculator, the games and the rest with nothing to run. `profiles/shortcuts/stock.txt` lists the shortcuts the stock ReactOS install writes into each user's profile (Start menu, Desktop and Quick Launch), one `PATH => TARGET` line each, the path under a profile folder and the target under the FAT32 root. When the trim is built, every shortcut whose target the profile or an `extra` list removes is removed too, from `Default User`, `Administrator`, `NetworkService` and `All Users`, and so is a Start menu folder when all its shortcuts go (`Games`, `Accessories/Communications`). A user who does not have the shortcut is not reported as a missing path. `rl image --dry-run` and the build log name the count.

The list is the stock install's, so it is complete until the install changes: `rl audit` on the full image names any shortcut the list does not know, and on a trimmed image any link whose target is gone ([shortcut-audit.md](shortcut-audit.md)). A shortcut a recipe adds with `[[shortcuts]]` is the recipe's own and is not in the list.

## Adding your own removals

A recipe adds to a profile with `[trim] extra`, a list of files in the same `f PATH` / `d PATH` format:

```toml
[trim]
profile = "base"
extra = ["trim/network-cards.txt"]
```

- Each path is resolved relative to the folder of the recipe file that lists it. When a recipe extends another, each recipe's own paths are resolved against its own folder, and the extending recipe's extra lists are applied after those of the recipes it extends.
- Extra lists are applied after the named profile, in order. An entry an earlier list already removes is not repeated.
- They go through the same protection check as a profile: an entry that removes a patched file or a licence file, or a folder that holds one, is refused before anything is removed.
- `rl image --dry-run` and the trim report name each extra list and its entry count, and `rl explain` shows the resolved paths.
- An extra list that removes a program also removes its stock shortcuts ([above](#shortcuts-of-removed-programs)).
- A file that is missing or malformed is an error that names `trim.extra` and the entry.

A downstream project keeps its own removals in its own repository rather than here. Quill, for example, is a consumer of the Afterglow remaster and removes the six network card drivers v86 does not emulate (`e1000`, `rtl8139`, `pcnet`, `dc21x4`, `nvnet`, `netkvm`); that list is an `extra` file in the Quill repository, named by Quill's recipe.

## Writing a profile

A built-in profile is `profiles/<name>.txt`, and a new name is added to the recipe validator, so a project that needs its own removals writes an `extra` list instead. Remove less rather than more where in doubt: a missing file costs a few kilobytes and a wrong removal can stop the guest booting. Measure a leaner list for emulator speed and pointer latency before building from it.

`rl trim RECIPE IMAGE [--profile NAME]` trims a working copy in place and refuses a disk in the work directory's `golden/` folder. `--profile` takes a built-in name; the recipe's `extra` lists still apply.
