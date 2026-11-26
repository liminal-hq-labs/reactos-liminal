# Notice

ReactOS Liminal is an unofficial Liminal HQ Labs project. It is not made, endorsed or supported by the ReactOS project. ReactOS™ is a trademark of the ReactOS project. Microsoft and Windows are trademarks of their owners.

## This repository

- Code, recipes and docs: `Apache-2.0 OR MIT` ([LICENSE-APACHE](LICENSE-APACHE), [LICENSE-MIT](LICENSE-MIT)).
- Source patches in [`patches/`](patches/README.md): GPL-2.0-or-later.
- Afterglow art, fetched at build time from [liminal-hq/afterglow-themes](https://github.com/liminal-hq/afterglow-themes): `Apache-2.0 OR MIT`, original work with a clean-room record in Afterglow's `PROVENANCE.md`.

## Components in built media (to be confirmed)

Built disks and remastered ISOs contain ReactOS 0.4.16 and the components below. **Every row is to be confirmed** file by file against the 0.4.16 source tree's `COPYING`, `CREDITS`, `media/doc/3rd Party Files.txt` and `media/fonts/doc/` before any ISO release, as part of the licence checklist in [SPEC.md](SPEC.md#licence-checklist). A release ships the confirmed list as `NOTICE.txt` and the licence texts in `LICENSES/`; `rl image` writes both, with `CHANGES.txt`, from `reactos_liminal/licences.py`, and `rl licences` writes the [licences page](docs/licences.md).

| Component | Licence (to be confirmed) |
|---|---|
| ReactOS kernel, drivers and most of user mode | GPL-2.0-or-later, with the ReactOS runtime linking exception in `COPYING` |
| Wine-derived DLLs (parts of `user32`, `uxtheme`, `comctl32`, `shell32` and others) | LGPL-2.1-or-later |
| Third-party code listed in `media/doc/3rd Party Files.txt` (zlib, libpng, FreeType, mbed TLS, ACPICA, rdesktop, TreeList and others) | Their own licences, including GPL-3.0-or-later, GPL-2.0, Apache-2.0, MIT and BSD-style |
| Wine Gecko (`system32\gecko`), if not trimmed | MPL-2.0 and others inside |
| WineVDM (`otvdm`), installed by ReactOS setup | GPL-2.0, per its `LICENSE` file |
| Fonts (Liberation, Croscore, DejaVu-derived, ReactOS clones, Source Sans Pro, Fixedsys Excelsior, UniVGA16 and others in `media/fonts/`) | OFL-1.1, GPL with the font exception and others; provenance of files named like Microsoft fonts to be checked |
| Wallpapers on the official ISO | CC-BY-NC-3.0 (Backwoods, Borealis, Borealis Dark, Deep Sea; `Angelus.txt` says NC-SA), CC0-1.0 (Grass, Polarlicht), CC-BY-SA-4.0 (Mizu), CC-BY-1.0 (Nebula), CC-BY-4.0 (Silhouette, Silhouette Dark) |
| Friendly Shut Down art in `msgina.dll` | Public domain (Splitwirez); replaced by Afterglow art in the remaster |

## Corresponding source

Each ISO release attaches the ReactOS 0.4.16 source archive (tag `0.4.16-release`, with its hash), the WineVDM source of the installed build, the patches in `patches/` and this repository at the release tag.
