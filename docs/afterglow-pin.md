# Afterglow pin

The Afterglow source is one pinned input of the base recipe (`[inputs.afterglow]` in `recipes/afterglow.toml`): a commit of `liminal-hq/afterglow-themes`, the SHA-256 of the uncompressed tar GitHub serves for it, the SHA-256 of the visual style built from it and the SHA-256 of the wallpaper rendered from it (and of each other scene, in `pins/afterglow-wallpapers.json`). The icon patchers add to that the SHA-256 of each file they patch, in `pins/shell32-icons.json` and `pins/icon-families.json`, keyed by a digest of the icons used.

## What the icon patchers read

The patchers take their list of groups from Afterglow's `desktop/icons/map.json`: every resource it verifies for a module they patch (see [docs/icon-survey.md](icon-survey.md)). The art is whatever `desktop/icons/render.py` writes at the pinned commit, each file checked against Afterglow's `SHA256SUMS`. Nothing in this repository names the five drive icons, or any other icon, so a redrawn icon, a hand-tuned 16 px frame or a new icon in a module already patched is a new pin and nothing else.

## Moving the pin

```sh
./rl pin recipes/afterglow.toml --afterglow REF
```

`REF` is a commit, a tag or a branch of the recipe's Afterglow repository. `rl pin` needs the golden disk (`rl install` once) and the tools `rl image` needs (`llvm-rc`, `lld-link`, `node`, `rsvg-convert`, ImageMagick 7, and python3 with numpy and Pillow). It:

1. resolves `REF` to a commit and fetches that commit's source;
2. measures the tar sum, the style sum and the wallpaper sum, and rewrites those lines of `[inputs.afterglow]` (nothing else in the recipe file changes); it also renders every scene the source draws and rewrites `pins/afterglow-wallpapers.json` with the commit and each scene's BMP sum;
3. runs the icon and bitmap patchers (with the pointer, Start and logon patchers whose copies they build on) against the golden disk in a recording mode and replaces the results in `pins/shell32-icons.json` and `pins/icon-families.json` (an icon set no longer in use is dropped);
4. runs every patcher the recipe lists with the new pins, so a stale pin fails here and not at the end of an image build.

`./rl pin recipes/afterglow.toml` alone re-measures the current pin, and `--check` changes nothing and exits 1 if any hash is stale (a drift check for CI or after editing a table). A patcher that pins its own result in code (`afterglow.logon`, `afterglow.start` and `afterglow.boot`) still needs that constant moved by hand when Afterglow changes that art; `rl pin` reports it with the patcher's own message.

Review the diff, run `python3 -m pytest` and `ruff check`, and commit the recipe and both `pins/` files together. The golden disk does not change with the pin.

## A pin on an unmerged branch

A pin may name a commit that is on an Afterglow branch that has not merged, to build against art that is still in review. Mark it:

```sh
./rl pin recipes/afterglow.toml --afterglow feat/icons-v2-16px --pre-merge "afterglow-themes feat/icons-v2-16px (pull request 56)"
```

The note is stored as `pre_merge` beside the commit, and a later `rl pin --afterglow REF` without `--pre-merge` removes it. A pre-merge pin is a stand-in: it is bumped to the merged `main` commit or a tag as soon as the pull request lands, because a commit on a force-pushed branch can disappear from GitHub (RL-45 records the move from the icon set v2 branch).

**Current state.** The pin is a commit on Afterglow `main`, `c706631c`, with no `pre_merge` note. It adds icons v5 (RL-65) to what `29928832` carried: the tar sum, the icon results and the toolbar family's key moved, and no style or wallpaper sum did. `29928832` added the card faces for Solitaire and Spider (pull request 62) to what `68d755c8` carried: the tar sum, the `cards.dll` result and the dialog family's key moved, and no style, wallpaper or other icon sum did (RL-63). `68d755c8` carried It carries the window frame polish (Afterglow pull request 61: no gold line under a window caption and no stray pixel at the frame's corners, which changes only the visual style, `afterglow.msstyles` `a6b5467c`) and the CD media art (pull request 59) on top of the full-image pass below; moving the pin from `4c8847f1` changed the tar sum and the style sum, and no icon, bitmap or wallpaper sum. Afterglow's own full-image pass (pull request 60) carries everything in `abad4b3e` (the icon set v3, the dialog art) and the full-image pass: icons v4 for the files the full image still showed in stock (Program Manager, Management Console, Telnet, the console programs, the screen savers, OpenGL and WineD3D, the Bluetooth class, User Accounts' pictures), the Show Desktop button icon, the card back and marks in `desktop/cards`, and the `colours` list of `map.json` (the dusk felt). Moving the pin from `abad4b3e` to `4c8847f1` changed the tar sum, the icon results and nothing else. Five media icons (`cd-disc`, `floppy-disk`, `usb-key`, `ram-module`, `monitor`) and four more are `unmapped` in the map: they have no ReactOS resource, so no patcher takes them ([icon-coverage.md](icon-coverage.md)). Whenever the art changes again, run `rl pin --afterglow` with the new commit.
