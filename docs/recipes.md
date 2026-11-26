# Recipes

A recipe is a TOML file. `rl explain RECIPE` prints it resolved (after `extends`, with every default filled in) as JSON, and refuses a recipe that does not validate, naming the key that is wrong. [SPEC.md](../SPEC.md) is the source of truth for what each key means.

## Tables

| Table | Keys | Default |
|---|---|---|
| `[recipe]` | `name` (required), `description`, `extends` | — |
| `[inputs.reactos_iso]` | `name`, `url`, `zip_sha256`, `sha256` (all required) | — |
| `[inputs.afterglow]` | `repo`, `commit`, `tar_sha256`, `msstyles_sha256` (required), `apply_reg` | `desktop/install/afterglow-original.reg` |
| `[install]` | `locale`, `time_zone_index`, `computer_name`, `owner_name`, `classic_shell`, `memory_mb`, `disk_size_mb` | `0409`, `85`, `REACTOS`, `ReactOS user`, `true`, `768`, `4096` |
| `[settings]` | `display_width`, `display_height`, `page_file`, `icon_size`, `wallpaper`, `reg_files` | `1024`, `768`, `"64 64"`, `32`, none, `["display", "quiet", "watermark-off"]` |
| `[trim]` | `profile`: `none`, `base` or `demo` | `none` |
| `[patchers]` | `list`: patcher names | `[]` |
| `[outputs.disk]` | `zero_free` | `true` |
| `[outputs.parts]` | `chunk_size`, `zstd_level` | `8MiB`, `19` |

Hashes are 64 lowercase hex digits; the Afterglow commit is the full 40 digits. A size is a number of bytes or a string such as `"8MiB"`. `chunk_size` is a power of two of at least 64 KiB.

## Extending

`extends = "other.toml"` (a path beside the recipe) or `extends = "rl:recipes/afterglow.toml"` (a path inside this repository) layers a recipe on another. Tables merge key by key; a list or a string in the extending recipe replaces the one it extends. A cycle is refused.

```toml
[recipe]
name = "my-demo"
extends = "rl:recipes/afterglow.toml"

[install]
computer_name = "MYDEMO"
```

## Work directory

Downloads, disks and scratch files go in the work directory: `--work DIR`, else `$RL_WORK`, else `~/.cache/reactos-liminal`. It must be outside the repository.
