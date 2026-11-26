# ReactOS Liminal specification

The source of truth for behaviour. A change that alters behaviour updates this file in the same change. Each part is marked **Built** or **Planned**; today everything is planned.

## Purpose

Build Afterglow-dressed ReactOS install media, disk images and browser snapshots from a recipe.

ReactOS images dressed by hand drift: the changes live only in a disk, nobody can say which file made which customization, and a rebuild is a day of clicking. ReactOS Liminal turns the official ReactOS 0.4.16 release ISO plus pinned inputs into finished artefacts with no hand step, so every customization is code, every input is pinned by SHA-256, and every output is recorded.

## Users and scenarios

- A maintainer building a themed ReactOS disk for a demo, screenshots or a talk.
- A maintainer remastering the install media so Setup, the logon screens and the first desktop wear Afterglow.
- A consumer project (Quill's Try ReactOS page first) that pins a release, extends a base recipe with its own payload and gets back v86 disk parts, a saved state and a manifest.
- Afterglow, building screenshots of its desktop theme for its docs.

## Non-goals

- Not a ReactOS fork. No ReactOS source changes upstream; bugs found on the way are reported to ReactOS.
- No art of its own. Afterglow draws; ReactOS Liminal applies.
- No Quill-specific content (programs, documents, the emblem, the public page).
- The boot screen stays as ReactOS draws it (FreeLoader's boot, the kernel boot animation), apart from the boot menu entry described below. A guard compares boot frames in every QEMU run.
- No Microsoft Windows images, fonts or redistributables; no VMware Tools.
- No network inside the guest.
- One ReactOS release at a time: 0.4.16. A new release means new pins and a check of every resource id and size.
- No upstream binaries in git, ever.

## Components

| Component | What | Status |
|---|---|---|
| `rl` | Entry point: a bash shim that runs `python3 -I -m reactos_liminal` | Planned |
| `reactos_liminal/` | Python 3.12, standard library only: the recipe reader, lock writer, fetcher, steps, PE resource writer, MSCF cabinet writer, ISO remaster and a read-only hive reader | Planned |
| `pins/` | The upstream ISO (URL, zip and ISO SHA-256) and the hash of every file a patcher accepts; the v86 version | Planned |
| `recipes/` | Base and example recipes: `base/reactos-0.4.16.toml`, `kiosk-v86.toml`, `afterglow-desktop.toml`, `afterglow-iso.toml` | Planned |
| `guest/` | Unattended answer files, registry files, guest command scripts and trim lists | Planned |
| `vm/` | Private QEMU runs: start, screenshot through the monitor, stop | Planned |
| `harness/`, `web/` | The v86 state builder (TypeScript on Bun, driving headless Chromium) and a minimal page for it; not a public page | Planned |
| `patches/` | GPL-2.0-or-later source patches against the ReactOS 0.4.16 tree, expressing the same changes as the binary patchers | Planned |

## Recipes

**Planned.** A recipe is a TOML file. It is declarative where that pays off (inputs, pins, settings, outputs, which steps run) and names code for the steps themselves.

- `[recipe]` names the recipe and optionally `extends` another, by path or as `rl:<path>` inside a pinned ReactOS Liminal release. A later table replaces an earlier one key by key; a `[[steps]]` list is appended unless an entry names `replace = "<id>"`.
- `[inputs.*]` names every input with its pin: the ReactOS ISO (`pin = "pins/reactos-0.4.16.toml#iso"`), the Afterglow release and its manifest SHA-256, a consumer's own directories.
- `[install]` holds the unattended answers: locale, time zone, computer name, owner name, classic shell.
- `[settings]` holds the display mode, page file and Afterglow scheme (default `Dusk`).
- `[[steps]]` lists the steps by `use` (`trim`, `files`, `registry`, `shortcuts`, `afterglow.style`, `afterglow.pointers`, `afterglow.wallpaper`, `logon.msgina`, `logon.win32k-colours`, `hook`), each with an `id` and its parameters.
- `[outputs]` chooses the disk, the v86 parts and state, and the remastered ISO.

A recipe chooses and parameterizes steps; it cannot add a new kind of write. The QEMU stage logic, ready detection, the patchers' safety checks and the remaster stay code.

**The lock file.** A build writes `<recipe>.lock.json` next to its outputs: every resolved input with its SHA-256, the step list after `extends`, the tool versions (QEMU, xorriso, mtools, zstd, Chromium) and every output's hash. The disk before the state build, the parts and the ISO are expected to be reproducible; the saved state is recorded but depends on timing.

## The `rl` command

**Planned.**

```text
rl build RECIPE [--out DIR] [--work DIR] [--iso FILE] [--from-golden FILE] [--only STEP] [--keep-work]
rl verify LOCKFILE                      # rebuild and compare hashes
rl fetch RECIPE                         # download and check every pinned input, nothing else
rl explain RECIPE                       # the resolved recipe after extends, and each step's inputs and outputs
rl patch msgina|win32k|user32|setup-art FILE --manifest M --scheme S --out OUT
rl unpatch …                            # restore from the saved original, or remove the selecting registry value
rl remaster RECIPE --iso FILE --out OUT.iso
rl vm run|shot|stop DISK                # private QEMU with its own monitor socket and pid file
rl serve DIR                            # range-capable static server for a local look in a browser
```

`--work` must be outside the repository; `rl` refuses a work directory inside it. `--iso` takes the user's own copy of the official ISO, checked against the pin.

## Outputs

**Planned.**

| Output | What |
|---|---|
| Golden disk | An unattended install from the official ISO: one FAT32 partition, 4 GiB sparse raw image |
| Disk image | The golden disk trimmed, configured and dressed; free space zeroed and holes punched |
| v86 parts | 1 MiB zstd parts of the disk, with a manifest |
| v86 state | A saved machine state, taken when the recipe's ready predicate holds (a serial marker or a pixel test) |
| Remastered ISO | The official ISO with an extra cabinet, edited `txtsetup.sif` and `unattend.inf`, themed Setup art and live environment, `LICENSES/`, `NOTICE.txt` and `CHANGES.txt`; `reactos.cab` byte-identical to upstream |
| Lock and build manifest | Every input and output hash, the tool versions and timings |

## Hash guards and patching

**Planned.** Every patcher edits a file the user already has, and only the one exact file it was written for.

- **Exact-hash guard.** Each patcher holds an allow-list of input SHA-256 values from `pins/` and refuses any other file, including one with a single changed byte. Tests prove the refusal.
- **Same-size, in-place writes.** A bitmap is replaced only by one of the same type, id, width, height and depth, as Afterglow's manifest declares in `replaces`; a manifest entry that does not match the resource found is refused. The patchers write bitmap bytes, colour-table bytes, a new resource section (pointers) and the PE checksum, nothing else; copyright strings and version resources stay.
- **Unique pattern.** A table edit (the 31-entry `SysColors[]` in `win32k.sys`) first checks the pattern occurs exactly once.
- **Undo.** Every patch keeps the original or selects the patched copy by one registry value, and `rl unpatch` reverses it.
- **Copy before write.** Every image is copied before it is written; originals are never touched.

### What is patched

| Target | Change | Off switch | Status |
|---|---|---|---|
| Visual style, schemes, caption metrics, pointer scheme, wallpaper | Files and registry from Afterglow's release | Display Properties | Planned |
| `user32.dll` | System pointers in a new resource section | Restore the original | Planned |
| `msgina.dll` → `agmsgina.dll` | Logon banner, bar, Shut Down dialog art; selected by `Winlogon\GinaDLL`, with `EnforceFriendlyShutdown` = 1 | Delete `GinaDLL` (`rl unpatch logon`) | Planned |
| `win32k.sys` | Cold-boot colours (the `SysColors[]` entries), on by default, as a separate `agwin32k.sys` selected by `SubSystems\Kmode` if ReactOS honours it | One registry value, or restore the original | Planned |
| `reactos.exe`, `syssetup.dll` | Setup watermark and header art | Restore the original | Planned |
| Install media | Extra cabinet, `txtsetup.sif` `[Cabinets]`, both `unattend.inf` files, live environment, volume label and autorun icon | Use the official ISO | Planned |
| `freeldr.ini` | A minimal menu (`MinimalUI=Yes`) with a gold selection bar and an entry "Afterglow for ReactOS"; the stock entry stays as the fallback | Pick the stock entry | Planned |
| Kernel boot logo (`agntoskr.exe`), Start button art (`explorer.exe`), console colours, screensaver | Under evaluation in spikes; each would be hash-guarded with its source patch in `patches/` | — | Planned, pending spikes |

### What is not patched

`reactos.cab` stays byte-identical to upstream. FreeLoader's code, the boot screen, `ntoskrnl.exe` (apart from a separate patched copy if the boot-logo spike succeeds), `bootvid.dll` and `hal.dll` are untouched. No ReactOS logo or orb is used in ReactOS Liminal's own art.

## Release gating

**Planned.**

- `release.yml` runs on `workflow_dispatch` only, never on push, tag or schedule. Its publishing job uses the protected `release` environment, with the owner as required reviewer; the owner pushes the tag. Agents never dispatch it.
- The ISO is built only from the official upstream ISO named in `pins/reactos-0.4.16.toml`, downloaded and checked against both hashes (the SourceForge zip and the ISO). No upstream binary is stored in git or in a cache that outlives the run.
- A release build remasters twice; both ISOs must be byte-identical. An unattended install from the remaster must reach an Afterglow desktop, the boot-frame guard must pass, and with cold-boot colours on, the cold-boot logon backdrop is checked.
- Release assets: the ISO (compressed), `SHA256SUMS`, `BUILD-MANIFEST.json` (the lock), the corresponding source (the ReactOS 0.4.16 source archive, the WineVDM source of the installed build, the patches in `patches/`), `NOTICE.txt` and release notes saying it is unofficial.
- The remastered ISO may be published from v0.1.0, and only after the licence checklist below is complete. Releases are not immutable on GitHub, but a published release is never edited to change its assets: a fix is a new release.

### Licence checklist

Completed by the owner before the first ISO release:

1. `NOTICE.txt` and `LICENSES/` match the 0.4.16 tree's `COPYING`, `CREDITS`, `media/doc/` and `media/fonts/doc/`.
2. The corresponding-source bundle is complete: the 0.4.16 source archive (hash matches the tag), WineVDM's source, the patches applying cleanly, this repository's tag.
3. The modified-files notice is in `CHANGES.txt`, the release notes and, where it costs nothing, the patched file's version resource.
4. The name, the wordmark question and the ReactOS project's trademark guidance are settled, and the courtesy note to the ReactOS project is sent.
5. The CC-BY-NC wallpapers are dropped or kept unchanged and credited.
6. Afterglow's clean-room record is confirmed: no ReactOS bitmap copied or traced.
7. No Microsoft file is on the ISO or the installed disk.
8. The off switches are documented and tested.
9. Legal advice is taken on the open points, or the owner decides it is not needed.

## Settings and defaults

**Planned.**

| Setting | Default | Meaning |
|---|---|---|
| `settings.scheme` | `Dusk` | Afterglow scheme for the style, logon and Setup art |
| `settings.display` | `bochsmp`, 1024 × 768 × 32 | Guest display driver and mode |
| `install.locale` | `0409` | Guest locale |
| `install.time_zone_index` | `85` (GMT) | Guest time zone |
| `install.computer_name` | `REACTOS` | Guest computer name |
| `steps.cold-boot-colours.enabled` | `true` | The `win32k.sys` colour patch |
| `media.live` | `true` | Theme the ISO's live environment |
| `outputs.state.threads` | `1` | zstd threads for the state (multi-threaded long-distance matching crashed once) |

## Security and privacy

- Every QEMU run is private: its own monitor socket and pid file, stopped by its own pid, never by a process name.
- Screenshots go through the QEMU monitor. Nothing captures the host desktop.
- The guest has no network.
- Downloads are checked against pinned hashes before use; an archive with unsafe paths is refused.
- On a public repository, workflow artefacts are downloadable by any signed-in GitHub user, so artefacts holding ReactOS binaries are short-lived (7 days at most) and never advertised.

## Limits

- Work space: the scripted build peaks at about 930 MB outside the repository.
- GitHub release assets are limited to 2 GiB each; the remastered ISO is about 410 MB before compression.
- One ReactOS release (0.4.16) at a time.
