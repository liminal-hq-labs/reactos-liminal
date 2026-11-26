# Licence texts

The licence texts that `rl image` writes into the image's `LICENSES` folder, held here because the official ReactOS 0.4.16 ISO carries none: it holds only `readme.txt` and a wallpaper credits file. `rl image` checks each file against the SHA-256 below and stops if one differs.

| File | Licence | Source | SHA-256 |
|---|---|---|---|
| `GPL-2.0-only.txt` | GNU General Public License, version 2 | [SPDX licence list data](https://github.com/spdx/license-list-data), `text/GPL-2.0-only.txt`, commit `cc4fe1ac462bd3ad3c81a07234baf7d9541ee871` | `aaf135472f81c5b4a0dca9367e5bb5e9750032b5bebe5442b36e4c0a47430df3` |
| `LGPL-2.1-only.txt` | GNU Lesser General Public License, version 2.1 | SPDX licence list data, `text/LGPL-2.1-only.txt`, commit `cc4fe1ac462bd3ad3c81a07234baf7d9541ee871` | `5749785c8bdefafcb5d798270ed0a967036fe2ca63dcedade1627565dfef81d2` |

The Apache-2.0 and MIT texts that cover Afterglow's art and these tools are the repository's own `LICENSE-APACHE` and `LICENSE-MIT`. ReactOS is GPL-2.0-or-later and its Wine-derived code LGPL-2.1-or-later; the "only" texts are the same licence texts, because the "or later" is a grant in each file's header and not a different text.

The licences of ReactOS's other bundled parts (fonts, third-party libraries, wallpapers) are named in `NOTICE.txt` and the generated [licences page](../docs/licences.md), and their texts travel with the corresponding source. A text is added here when a release ships a component whose licence is not covered above.
