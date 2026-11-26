# ReactOS Liminal

<p align="center"><img src="assets/hero.svg" alt="ReactOS Liminal — Build Afterglow-dressed ReactOS install media, disk images and browser snapshots from a recipe" width="100%"></p>

<p align="center">
  <a href="https://github.com/liminal-hq-labs/reactos-liminal/actions/workflows/ci.yml"><img src="https://github.com/liminal-hq-labs/reactos-liminal/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <img src="https://img.shields.io/badge/status-experimental-e8657c" alt="Status: experimental">
  <img src="https://img.shields.io/badge/ReactOS-unofficial-ffc94d" alt="ReactOS: unofficial">
  <img src="https://img.shields.io/badge/licence-Apache--2.0%20OR%20MIT-4a2470" alt="Licence: Apache-2.0 OR MIT">
</p>

Build Afterglow-dressed ReactOS install media, disk images and browser snapshots from a recipe.

**Unofficial.** ReactOS Liminal is a Liminal HQ Labs project. It is not made, endorsed or supported by the ReactOS project; report problems here, not to ReactOS. ReactOS™ is a trademark of the ReactOS project.

ReactOS Liminal turns the official ReactOS 0.4.16 install ISO into finished artefacts with no hand step: an unattended install, a trimmed disk image, the [Afterglow](https://github.com/liminal-hq/afterglow-themes) desktop theme with a themed logon and Setup, a remastered install ISO, and disk parts and a saved state for the v86 emulator in a browser. A build is a declarative recipe whose every input is pinned by SHA-256, so nothing lives only in a disk image and every patch refuses a file it was not written for.

> **Status:** experimental. The `rl` command can check your tools, validate a recipe and fetch the pinned ISO; nothing builds a disk here yet. The working pipeline (unattended install, trim, Afterglow desktop, v86 parts and state) runs today inside [Quill](https://github.com/liminal-hq-labs/quill)'s Try ReactOS demo and moves here in stages ([docs/migration.md](docs/migration.md)), followed by the recipe format, the `rl` command, the logon and Setup theming and the remastered ISO. There are no releases. Releases, from v0.1.0, may carry the remastered ISO, published only through an owner-approved release environment and after the licence checklist in [SPEC.md](SPEC.md#release-gating).

## What it's for

- Building a themed ReactOS disk for a demo or a screenshot, the same way every time, from a recipe instead of a hand-configured virtual machine.
- Remastering the official install media so Setup, the logon screens and the first desktop wear Afterglow's art, with the stock boot entry kept as the fallback.
- Building v86 disk parts and a saved machine state, so ReactOS boots in a browser tab in seconds.
- Applying patches that are reproducible and safe: each is pinned to the exact upstream file by hash, refuses anything else, and records its undo.
- Feeding Quill's browser demo, which pins a ReactOS Liminal release and adds only its own programs and documents on top.

## Install and run

On Linux with Python 3.12 and QEMU, mtools, xorriso and zstd on the path:

```sh
./rl doctor                                  # check the tools
./rl explain recipes/afterglow.toml          # the resolved, validated recipe
./rl fetch recipes/afterglow.toml            # download and check the pinned ISO (or pass --iso FILE)
```

Large files go in `~/.cache/reactos-liminal` (`--work` or `$RL_WORK` change it), never in the repository. The build commands (`rl install`, `rl image`, `rl parts`) land next.

Releases will attach the remastered ISO with its checksums, build manifest and corresponding source, built in CI from the official ISO and published only behind an owner-approved release environment.

## How it fits

- **[ReactOS](https://reactos.org/).** Every artefact starts from the official ReactOS 0.4.16 release ISO, checked by hash. ReactOS Liminal is not a fork: it changes no ReactOS source upstream, keeps the boot screen as ReactOS draws it, and holds no ReactOS binary in git. Source patches that express its changes against the ReactOS tree are GPL-2.0-or-later and live in [`patches/`](patches/README.md).
- **[Afterglow](https://github.com/liminal-hq/afterglow-themes).** All art (the visual style, colour schemes, pointers, icons, wallpapers, logon and Setup bitmaps) lives in Afterglow's `desktop/` folder as vector masters with scripted renders, and ships in Afterglow releases with a manifest of what each asset replaces. ReactOS Liminal only applies it.
- **[Quill](https://github.com/liminal-hq-labs/quill).** Quill's Try ReactOS page is a consumer: it pins a ReactOS Liminal release, extends a base recipe with the Quill programs and documents, and gets back disk parts, a state and a manifest. Nothing Quill-specific lives here.

The remastered media is named "Afterglow for ReactOS — unofficial remaster by Liminal HQ Labs", and its boot entry reads "Afterglow for ReactOS".

## Documentation

- [SPEC.md](SPEC.md) — scope, the recipe format, the `rl` command, outputs, hash guards and release gating, each marked planned or built
- [docs/decisions.md](docs/decisions.md) — decisions and why
- [docs/recipes.md](docs/recipes.md) — the recipe tables and defaults
- [docs/migration.md](docs/migration.md) — where the pipeline came from and what has moved
- [NOTICE.md](NOTICE.md) — third-party components and licences, to be confirmed before an ISO release
- [patches/README.md](patches/README.md) — the GPL source patches folder
- [AGENTS.md](AGENTS.md) — contributor and agent rules

## Contributing

Issues and pull requests are welcome. The house rules are in [AGENTS.md](AGENTS.md); run the checks it lists before opening a pull request.

## Part of Liminal HQ Labs

ReactOS Liminal is a [Liminal HQ Labs](https://github.com/liminal-hq-labs) experiment. Experiments from Liminal HQ — early, rough and open. If it proves itself, it [graduates](https://github.com/liminal-hq-labs/.github/blob/main/docs/labs-charter.md#graduation) to [Liminal HQ](https://github.com/liminal-hq).

## Licence

The code, recipes and docs are licensed under either of the [Apache License, Version 2.0](LICENSE-APACHE) or the [MIT licence](LICENSE-MIT), at your option. The source patches in [`patches/`](patches/README.md) modify GPL files of ReactOS and are licensed GPL-2.0-or-later, like the files they patch. Afterglow's art is Afterglow's, under its own Apache-2.0 OR MIT licence. ReactOS itself, and everything on its install media, keeps its own licences; [NOTICE.md](NOTICE.md) lists them.
