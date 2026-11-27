# Recipes

A recipe is a TOML file. `rl explain RECIPE` prints it resolved (after `extends`, with every default filled in) as JSON, and refuses a recipe that does not validate, naming the key that is wrong. [SPEC.md](../SPEC.md) is the source of truth for what each key means.

## Tables

| Table | Keys | Default |
|---|---|---|
| `[recipe]` | `name` (required), `description`, `extends` | — |
| `[inputs.reactos_iso]` | `name`, `url`, `zip_sha256`, `sha256` (all required) | — |
| `[inputs.afterglow]` | `repo`, `commit`, `tar_sha256`, `msstyles_sha256` (required), `apply_reg`, `wallpaper`, `wallpaper_sha256` | `desktop/install/afterglow-original.reg`, none, none |
| `[install]` | `locale`, `time_zone_index`, `computer_name`, `owner_name`, `classic_shell`, `memory_mb`, `disk_size_mb` | `0409`, `85`, `REACTOS`, `ReactOS user`, `true`, `768`, `4096` |
| `[settings]` | `display_width`, `display_height`, `page_file`, `icon_size`, `wallpaper`, `wallpaper_style`, `reg_files`, `remove_desktop_shortcuts` | `1024`, `768`, `"64 64"`, `32`, none, `"stretch"`, `["display", "quiet", "watermark-off"]` (the base recipe adds `afterglow-logon`), none |
| `[[files]]` | `source` (relative to the recipe), `destination` (under the disk root) | none |
| `[[shortcuts]]` | `name`, `target` (required), `arguments`, `working_dir`, `description`, `icon`, `icon_index`, `show` (1, 3 or 7) | none |
| `[trim]` | `profile`: `none` or `base`; `extra`: a list of trim files, resolved relative to the recipe that lists them, applied after the profile | `none`; no extras |
| `[patchers]` | `list`: `afterglow.pointers`, `afterglow.start`, `afterglow.icons`, `afterglow.cpl-icons`, `afterglow.program-icons`, `afterglow.toolbar-bitmaps`, `afterglow.logon`, `afterglow.boot` | `[]` (the base recipe lists all of them) |
| `[outputs.disk]` | `zero_free` | `true` |
| `[outputs.parts]` | `chunk_size`, `zstd_level` | `8MiB`, `19` |

Hashes are 64 lowercase hex digits; the Afterglow commit is the full 40 digits. A size is a number of bytes or a string such as `"8MiB"`. `chunk_size` is a power of two of at least 64 KiB.

`reg_files` names files in `guest/reg/`: `display` (made from the display size), `quiet`, `watermark-off`, `mouse-linear`, `hide-desktop-icons` and `afterglow-logon` (selects `agmsgina.dll`; needs the `afterglow.logon` patcher). The desktop icon size and wallpaper are always written from their keys. See [trim.md](trim.md) for the profiles.

### Wallpaper

`inputs.afterglow.wallpaper` names an Afterglow scene as `<palette>-<mode>-<style>` (the base recipe uses `dusk-dark-smooth`, the signature scene and the one that matches the Dusk scheme `apply_reg` selects), and `wallpaper_sha256` pins the BMP it renders to. `settings.wallpaper` is the path inside the guest (a path on `C:` with backslashes); `rl image` renders the scene from its SVG master with Afterglow's `scripts/render-wallpapers.mjs` (needs `node`, `rsvg-convert` and ImageMagick 7), checks the 1024 × 768 BMP against the pin and writes it to that path. `settings.wallpaper_style` is `stretch` (the default), `centre` or `tile`. A `[[files]]` entry whose destination is the same path wins, and nothing is rendered: that is how a downstream recipe puts its own wallpaper there. The BMP is the centre 4:3 crop of the 16:9 master, so a recipe with another display size should stretch or pick its own file.

## Extending

`extends = "other.toml"` (a path beside the recipe) or `extends = "rl:recipes/afterglow.toml"` (a path inside this repository) layers a recipe on another. Tables merge key by key; a list or a string in the extending recipe replaces the one it extends. A cycle is refused.

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

## Work directory

Downloads, disks and scratch files go in the work directory: `--work DIR`, else `$RL_WORK`, else `~/.cache/reactos-liminal`. It must be outside the repository.
