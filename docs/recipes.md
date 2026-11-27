# Recipes

A recipe is a TOML file. `rl explain RECIPE` prints it resolved (after `extends`, with every default filled in) as JSON, and refuses a recipe that does not validate, naming the key that is wrong. [SPEC.md](../SPEC.md) is the source of truth for what each key means.

## Tables

| Table | Keys | Default |
|---|---|---|
| `[recipe]` | `name` (required), `description`, `extends` | — |
| `[inputs.reactos_iso]` | `name`, `url`, `zip_sha256`, `sha256` (all required) | — |
| `[inputs.afterglow]` | `repo`, `commit`, `tar_sha256`, `msstyles_sha256` (required), `apply_reg`, `wallpaper`, `wallpaper_sha256` | `desktop/install/afterglow-original.reg`, none, none |
| `[install]` | `locale`, `time_zone_index`, `computer_name`, `owner_name`, `classic_shell`, `memory_mb`, `disk_size_mb` | `0409`, `85`, `REACTOS`, `ReactOS user`, `true`, `768`, `4096` |
| `[iso]` | `writer` (`NAME VERSION`: `genisoimage 1.1.11` or `mkisofs 3.02a09`), `volume` (up to 32 letters, digits, spaces, underscores), `epoch` (seconds; the time on every file and volume date) | `genisoimage 1.1.11`, `ReactOS`, `1756425600` |
| `[settings]` | `display_width`, `display_height`, `page_file`, `icon_size`, `wallpaper`, `wallpaper_style`, `reg_files`, `remove_desktop_shortcuts` | `1024`, `768`, `"64 64"`, `32`, none, `"stretch"`, `["display", "quiet", "watermark-off"]` (the base recipe adds `afterglow-logon`, `regional-canada` and `pointer-defaults`), none |
| `[builds.afterfetch]` | `source` (a Rust project, relative to the recipe that declares it), `sha256` of its build output (both required) | the base recipe builds `tools/afterfetch` |
| `[[files]]` | `source` (relative to the recipe, or `built:NAME` for a `[builds]` output), `destination` (under the disk root) | none (the base recipe writes `afterfetch.exe` and `afterfetch.cmd`; a recipe that extends it keeps those entries and merges its own by destination, see [Extending a recipe](#extending); `built:afterfetch` works in a consumer recipe because the base recipe declares the build) |
| `[[shortcuts]]` | `name`, `target` (required), `arguments`, `working_dir`, `description`, `icon`, `icon_index`, `show` (1, 3 or 7) | none |
| `[wallpapers]` | `scenes` (`"all"`, or a list of Afterglow scenes such as `["dusk-light-smooth"]`; `[]` is none), `replace_stock` (remove ReactOS's own wallpapers) | `[]`, `false` (the base recipe sets `"all"` and `true`; the compact recipe sets them back) |
| `[trim]` | `profile`: `none` or `base`; `extra`: a list of trim files, resolved relative to the recipe that lists them, applied after the profile | `none`; no extras |
| `[patchers]` | `list`: `afterglow.pointers`, `afterglow.start`, `afterglow.icons`, `afterglow.cpl-icons`, `afterglow.program-icons`, `afterglow.dialog-icons`, `afterglow.map-icons`, `afterglow.toolbar-bitmaps`, `afterglow.dialog-bitmaps`, `afterglow.logon`, `afterglow.boot` | `[]` (the base recipe lists all of them, in an order the loader checks: a patcher that builds on another's copy of a file is listed after it) |
| `[outputs.disk]` | `zero_free` | `true` |
| `[outputs.parts]` | `chunk_size`, `zstd_level` | `8MiB`, `19` |

Hashes are 64 lowercase hex digits; the Afterglow commit is the full 40 digits. A size is a number of bytes or a string such as `"8MiB"`. `chunk_size` is a power of two of at least 64 KiB.

`reg_files` names files in `guest/reg/`: `display` (made from the display size), `quiet`, `watermark-off`, `mouse-linear`, `hide-desktop-icons`, `afterglow-logon` (selects `agmsgina.dll`; needs the `afterglow.logon` patcher), `regional-canada` (English (Canada), the location Canada and 24-hour time, for the user and `HKU\.DEFAULT`) and `pointer-defaults` (the pointer shadow on, and the stock "ReactOS Default" system scheme emptied so the list is "Afterglow" and "(None)"). An entry that ends in `.reg` is a path to a registry file of your own, relative to the recipe that lists it, and is applied after the named files, like `trim.extra` is applied after the profile: a downstream recipe lists `"quill.reg"` and keeps the base recipe's named files. When a recipe that extends another lists named files, those replace the base recipe's named files; the paths of every recipe in the chain are kept, base first. The file must exist and start with the line `Windows Registry Editor Version 5.00`, and `rl lock` records its sum. The desktop icon size and wallpaper are always written from their keys. See [trim.md](trim.md) for the profiles.

### Wallpaper

`inputs.afterglow.wallpaper` names an Afterglow scene as `<palette>-<mode>-<style>` (the base recipe uses `dusk-dark-smooth`, the signature scene and the one that matches the Dusk scheme `apply_reg` selects), and `wallpaper_sha256` pins the BMP it renders to. `settings.wallpaper` is the path inside the guest (a path on `C:` with backslashes); `rl image` renders the scene from its SVG master with Afterglow's `scripts/render-wallpapers.mjs` (needs `node`, `rsvg-convert` and ImageMagick 7), checks the 1024 × 768 BMP against the pin and writes it to that path. `settings.wallpaper_style` is `stretch` (the default), `centre` or `tile`. A `[[files]]` entry whose destination is the same path wins, and nothing is rendered (`rl image --dry-run` says so): that is how a downstream recipe puts its own wallpaper there. List the BMP beside the recipe as a `[[files]]` entry whose `destination` is the path on the disk of `settings.wallpaper` (`C:\\ReactOS\\quill.bmp` is `ReactOS/quill.bmp`; the comparison ignores case). The BMP is the recipe's own bytes, so a recipe that overlays art (an emblem on the scene) renders it itself, before the build; the scene pin it inherits is still measured by `rl pin` but not rendered by `rl image`. The BMP is the centre 4:3 crop of the 16:9 master, so a recipe with another display size should stretch or pick its own file.

### The wallpaper list

Display Properties > Background lists the images in `C:\ReactOS` and in `WallPaperDir`, which is `C:\ReactOS\Web\Wallpaper`, of the types GDI+ opens (BMP, JPEG, GIF, PNG and others), plus the current wallpaper first; the name of each is its file name without the extension. The `[wallpapers]` table chooses what is in that folder:

- `scenes` writes Afterglow scenes there as 24-bit 1024 × 768 BMPs (2.3 MB each) named like ReactOS's own wallpapers (Nebula, Borealis): short, title case, no hyphens and no `Afterglow` prefix, because the file name is what the list shows. The palette name is the dark smooth scene and a variant adds a word: `dusk-dark-smooth` is `Dusk`, `dusk-light-smooth` is `Dusk Light`, `dusk-dark-stepped` is `Dusk Stepped` and `dusk-light-stepped` is `Dusk Light Stepped`. The five palettes are Aurora, Dusk, Ember, Graphite and Indigo, so the list is Aurora, Aurora Light, Aurora Light Stepped, Aurora Stepped, Dusk and so on (20 names, each under 32 characters). `"all"` is every scene in `pins/afterglow-wallpapers.json` (the 20 in the pinned Afterglow commit). Each BMP is checked against its sum in that file, which `rl pin` measures; it also refuses a file pinned for another Afterglow commit. The scene that is the desktop wallpaper is written once, to `settings.wallpaper`, and a `[[files]]` entry for a scene's path replaces that scene.
- `replace_stock = true` removes ReactOS's own wallpapers and their credits files (`profiles/wallpapers/stock.txt`) before the files are written, so the list holds only the recipe's. It is separate from the trim, which the full recipe does not use. `CHANGES.txt` lists the removals, and the stock wallpapers' licences leave `NOTICE.txt` with them.

The base recipe sets `scenes = "all"` and `replace_stock = true`, and its `settings.wallpaper` is the dusk file of the set, so the default stays `dusk-dark-smooth`. A table merges key by key across `extends`, and a value a child sets again replaces the inherited one, so `afterglow-compact.toml` sets `scenes = []`, `replace_stock = false` and its own `settings.wallpaper` (`C:\ReactOS\afterglow-wallpaper.bmp`): the compact image has one wallpaper and no extras, and the trim has already removed the stock files. A downstream recipe can narrow the set (`scenes = ["dusk-dark-smooth", "dusk-light-smooth"]`) the same way. The set adds about 46 MB to the full image.

## Extending

`extends = "other.toml"` (a path beside the recipe) or `extends = "rl:recipes/afterglow.toml"` (a path inside this repository) layers a recipe on another. Tables merge key by key; a list or a string in the extending recipe replaces the one it extends. A cycle is refused. `[[files]]` is the second exception to "a list replaces": entries merge by destination. An entry of the extending recipe replaces the inherited entry for the same destination in place (case-insensitive, `/` or `\\`), and its other entries follow the inherited ones. A `source` is relative to the recipe that wrote the entry, so an inherited entry still finds its file. There is no way to drop an inherited entry; override its destination with another file instead.

```toml
[recipe]
name = "my-demo"
extends = "rl:recipes/afterglow.toml"

[install]
computer_name = "MYDEMO"

[trim]
extra = ["my-demo-trim.txt"]
```

`my-demo-trim.txt` sits beside this recipe and holds `f PATH` and `d PATH` lines ([trim.md](trim.md#adding-your-own-removals)). A recipe that extends another keeps the extra lists of the recipes it extends and adds its own after them; every other list replaces.

## The base recipe and the compact recipe

`recipes/afterglow.toml` is the full ReactOS with the Afterglow desktop: `trim.profile = "none"`, so the trim removes nothing (every app, game, screensaver, applet and font, and Gecko, so the Internet Browser works when the guest has a network); its one removal is ReactOS's own wallpapers, which the 20 Afterglow wallpapers replace in the Display Properties list ([above](#the-wallpaper-list)). `recipes/afterglow-compact.toml` is the same recipe extended with `[trim] profile = "base"`, the compact trim ([trim.md](trim.md)); it keeps one wallpaper, in `C:\ReactOS\afterglow-wallpaper.bmp`; it has its own name (`afterglow-compact`, so its disk is `images/afterglow-compact.img`) and its own lock file, `afterglow-compact.lock.json`. The two have the same golden-disk key, because the install does not depend on the trim, so `rl image recipes/afterglow-compact.toml --golden GOLDEN_DISK_OF_THE_BASE_RECIPE` reuses the base recipe's golden disk instead of installing again (a golden disk's file name carries the recipe name). `./rl lock` and `./rl verify` take a recipe each, and CI verifies both locks.

A consumer that wants the compact image extends `rl:recipes/afterglow-compact.toml`; one that extends `rl:recipes/afterglow.toml` gets the full image. Quill's remix recipe (`site/try-reactos/qagrr/qagrr.toml`) extends `rl:recipes/afterglow.toml` and relied on the trim that recipe then carried, so it needs `extends = "rl:recipes/afterglow-compact.toml"` to keep its compaction (RL-48); that change is made in the Quill repository when it takes this release.

## Work directory

Downloads, disks and scratch files go in the work directory: `--work DIR`, else `$RL_WORK`, else `~/.cache/reactos-liminal`. It must be outside the repository.
