# Decisions

Each decision is numbered and stays here even when superseded, with a note on what replaced it. Open questions move here once they are answered. The **By** column says who made each one: **Owner** for the project owner's decisions, **Assumed** for choices made from the project plan that stand until the owner confirms or changes them, **House** for Liminal HQ Labs defaults.

## Numbering

Decisions take the prefix `RL` and a number (`RL-1`); a sub-decision adds a dot (`RL-1.1`) under the decision it refines.

| # | Decision | Choice | By | Why |
|---|---|---|---|---|
| RL-1 | Home | A Liminal HQ Labs experiment in `liminal-hq-labs/reactos-liminal`, public from the first commit | Owner | Try the idea in the open before it earns a place in Liminal HQ |
| RL-2 | Licence | `Apache-2.0 OR MIT` for the code, recipes and docs | House | House licence, compatible with both ecosystems |
| RL-2.1 | Source patches | Patches against ReactOS source live in `patches/`, licensed GPL-2.0-or-later with a licence note in the folder, the one exception to RL-2 | Owner | They are derived from GPL files and must carry the GPL; a separate folder keeps the split visible |
| RL-3 | Dependency updates | No Dependabot configuration until the project opts in | House | Labs repositories stay quiet by default. See the [Labs charter](https://github.com/liminal-hq-labs/.github/blob/main/docs/labs-charter.md#dependabot-is-opt-in) |
| RL-4 | Scope | Everything that builds a ReactOS image from code: unattended install, trim, Afterglow desktop, logon and Setup theming, remastered ISO, v86 parts and state | Owner | Every customization is code, so nothing lives only in a disk image |
| RL-5 | Layering | ReactOS Liminal owns the pipeline; Afterglow supplies the art as a hash-pinned input; Quill and other projects consume releases | Owner | One owner per fact: a picture belongs to Afterglow, a Quill file to Quill, anything that installs, configures, trims, patches, remasters, boots or snapshots ReactOS to this repository |
| RL-5.1 | Art | All art and art generators live in `liminal-hq/afterglow-themes` under `desktop/`, released with a manifest of what each asset replaces; this repository holds only the tools that apply it | Owner | Afterglow draws, ReactOS Liminal applies |
| RL-5.2 | Vector masters | Art is kept as vector masters with a scripted render to each pixel size and depth; no hand-edited bitmaps | Owner | Renders are reproducible and every size follows the master |
| RL-5.3 | No Quill content | No Quill programs, documents, emblem, shortcuts or page here; Quill supplies them through its own recipe | Owner | A second consumer would replace them, so they belong to the consumer |
| RL-6 | Tooling | Python 3.12 with the standard library for the pipeline, bash for the QEMU and mtools steps, TypeScript on Bun for the v86 state builder | Assumed | The pipeline moving in is mostly Python and shell already; `tomllib` makes the recipe reader standard-library only |
| RL-7 | Recipes | Builds are declarative TOML recipes with `extends`; every input is pinned by SHA-256; a build writes a lock file of every input and output hash | Assumed | Reproducible builds and a consumer contract that is a file, not a disk image |
| RL-8 | No upstream binaries in git | No ReactOS binary, patched binary, ISO, disk image or ReactOS source file is ever committed; patched binaries exist only in build outputs | Assumed | Keeps the repository's licence clean and its size small |
| RL-9 | Hash-guarded patches | Every patcher accepts only the exact upstream file it was written for (SHA-256 allow-list), writes same-size in place, and records its undo | Assumed | A patch can never be right for more than one exact file |
| RL-10 | Cold-boot colours | The `win32k.sys` colour patch is on by default, behind an exact-hash guard and a unique-pattern check, with a cold boot in every release build | Owner | The logon backdrop matches the scheme from the first frame. The plan's caveat stands: ship the patched copy as a separate `agwin32k.sys` selected by one registry value if ReactOS 0.4.16 honours `SubSystems\Kmode`, so the off switch is one value |
| RL-11 | Releases | The remastered ISO may be published in GitHub Releases from v0.1.0, built in CI from the official ISO by `release.yml` (dispatch only), published only through the protected `release` environment with the owner as required reviewer, and only after the licence checklist in `SPEC.md` is complete | Owner | Publishing is the point of a remaster; the environment and the checklist keep each release a deliberate owner act |
| RL-11.1 | Immutable releases | Not turned on | Owner | The owner decided against it; a fix is still a new release rather than an edited one |
| RL-11.2 | Artefact retention | Workflow artefacts and logs kept 7 days | Owner | On a public repository artefacts are downloadable by any signed-in user; short retention limits unadvertised distribution of ReactOS binaries |
| RL-12 | Name | Releases and media are named "Afterglow for ReactOS — unofficial remaster by Liminal HQ Labs"; every README and release body says it is unofficial and not endorsed by the ReactOS project; no ReactOS logo or orb in our own art | Owner | Lead with the Liminal name and use "ReactOS" only descriptively, as the branding review recommends |
| RL-13 | Boot entry | The FreeLoader entry for the remaster reads "Afterglow for ReactOS"; the stock entry stays as the fallback | Owner | The user always has the untouched system one keypress away |
| RL-13.1 | Minimal boot menu | FreeLoader's minimal menu (`MinimalUI=Yes`) with a gold selection bar on black. It shows no title and no FreeLoader credit line; attribution is carried by the entry name, the release notes (unofficial notice, GPL source offer, credits) and the docs | Owner | Chosen design 1 on the design canvas; the missing credit line is acknowledged |
| RL-14 | Boot screen | FreeLoader's boot, the kernel boot animation, `bootvid.dll` and `hal.dll` stay as ReactOS draws them, apart from RL-13 and any boot-logo spike the owner adopts (see the open questions); a guard compares boot frames in every QEMU run | Owner | A remaster should not look like it replaced the system underneath |
| RL-15 | Decision IDs | The `RL-` prefix with dotted sub-decisions | Assumed | Matches the per-area prefix convention of the other Labs projects |

## Open questions

- **Wordmark on the published ISO.** Whether the logon banner of a published ISO may carry the "ReactOS" wordmark in Afterglow type, or uses a wordmark-free banner until the ReactOS project's guidance is checked.
- **`Kmode`.** Whether ReactOS 0.4.16's `smss` honours `SubSystems\Kmode`, which decides how RL-10's off switch works.
- **Logon art after a scheme change.** One `agmsgina-<scheme>.dll` per scheme switched by Afterglow's `apply-scheme.cmd`, or the logon keeps the install-time scheme.
- **Base locale and time zone.** English (US) and GMT in the neutral base recipe, with consumers choosing their own.
- **Kernel boot logo and Start button art.** Whether the spikes (`agntoskr.exe`, the Afterglow Start button) go into the recipes.
