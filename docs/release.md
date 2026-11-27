# Releasing

How a release is cut, and the one-time setup the owner does in GitHub. Agents never push a tag, dispatch a workflow or approve the environment: the owner does all three.

## What a release carries

A release of "Afterglow for ReactOS — unofficial remaster by Liminal HQ Labs" attaches:

- **The v86 disk parts**, `v86-disk-parts-vX.Y.Z.tar`: the zstd parts of the built image with their `manifest.json`. A saved v86 state is added when the build makes one.
- **`SHA256SUMS`** covering every attached file.
- **`build-manifest.json`**, the SHA-256 of every output, the pinned inputs, the trim profile, the patchers and the stage timings.
- **`afterglow.lock.json`**, the lock file the build was verified against.
- **`licences.md`**, the licences page for this build ([licences.md](licences.md) is the committed copy).
- **The source:** `reactos-liminal-vX.Y.Z-source.tar.gz` (this repository at the release commit, with the recipe, the tools and the patches) and `SOURCE.txt` (the ReactOS source by tag and commit, the WineVDM pointer and the written offer).

**No ISO in v0.1.0.** The owner decided on 2026-11-26 that the remastered ISO waits for a later release: today it is the stock ReactOS disc with the licence texts, notice and list of changes added, which is not worth shipping, and Setup is not themed yet. `rl iso` is built and tested, and the ISO will be published once Setup theming gives it something of its own. Until then neither workflow builds or attaches it.

The release body is `docs/releases/X.Y.Z.md`, which must exist and be non-empty. Releases are not immutable (RL-11.1), but a published release's assets are never edited: a fix is a new release.

## Before you start

1. The licence checklist in [SPEC.md](../SPEC.md#licence-checklist) is complete. The workflow cannot check it; approving the environment is the owner's statement that it is.
2. `main` holds the commit to release and CI is green. Run `./rl lock recipes/afterglow.toml` and `./rl lock recipes/afterglow-compact.toml` and commit the results before tagging, so `./rl verify` passes for both: any pin or trim-list change since the last lock leaves it stale.
3. `docs/releases/X.Y.Z.md` is written. Check that what it says is in the build.
4. The WineVDM (otvdm) release that ReactOS 0.4.16 installs is identified, and `SOURCE.txt` and `NOTICE.txt` name it. The workflow points at the project but cannot know the release.

## One-time setup

All in the repository's **Settings** on GitHub.

1. **Settings → Environments → New environment.** Name it exactly `release` and choose **Configure environment**.
2. Under **Deployment protection rules**, tick **Required reviewers**, add yourself, and click **Save protection rules**. Leave **Prevent self-review** unticked: you start the release and you approve it, so with it ticked nobody could.
3. Under **Deployment branches and tags**, choose **Selected branches and tags**, click **Add deployment branch or tag rule**, set **Ref type** to Branch and the name pattern to `main`, and click **Add rule**. Add a second rule with **Ref type** Tag and the pattern `v*`.
4. Add no secrets and no variables to the environment. The workflow uses the repository's own token with `contents: write` on the publish job only.
5. **Settings → General → Releases.** Leave **Enable release immutability** off (RL-11.1).
6. **Settings → Actions → General → Artifact and log retention.** Set it to 7 days (RL-11.2). The workflow also sets 7 days on each artefact it uploads.
7. **Settings → Actions → General → Workflow permissions.** **Read repository contents and packages permissions** is the right setting; the workflows ask for more only where they need it.
8. Optional: **Settings → Rules → Rulesets → New ruleset → New tag ruleset.** Target tags matching `v*`, restrict creations to yourself, and set the enforcement to Active, so only you can start a release by pushing a tag.

## Cutting a release

Either way, the run builds first (about ten minutes with a warm cache, longer with a cold one: the install takes three to five minutes with KVM), then stops at the publish job and waits for you.

1. **Push the tag.** From an up-to-date `main`: `git tag -s vX.Y.Z -m "Afterglow for ReactOS vX.Y.Z"` and `git push origin vX.Y.Z`. The run starts by itself. Or **dispatch it:** **Actions → Release → Run workflow**, branch `main`, and enter `vX.Y.Z`; the tag is created on that commit when the release is published.
2. Open the run. The **Check the release** job fails fast on a tag that is not `vX.Y.Z`, a commit that is not on `main` and missing release notes.
3. Wait for **Build** and **Corresponding source** to finish. Read the build's job summary: the sizes, the hashes and the pinned inputs.
4. When **Publish the release** shows **Waiting**, click **Review deployments**, tick `release`, optionally leave a comment, and click **Approve and deploy**. To stop instead, click **Reject**.
5. Open the new release. Check that every asset is there and that `SHA256SUMS` matches a download (`sha256sum -c SHA256SUMS`).

If the build has no KVM the release fails rather than skipping the QEMU stages: a release is never made from a build that did not run them.

## What the workflows do

- **`build.yml`** runs on dispatch, on a pull request that touches the pipeline paths and when `release.yml` calls it. It installs its tools with apt on the Ubuntu runner, (the shared `ci-dos` image has QEMU and mtools but not xorriso, `genisoimage` (the ISO writer the recipe pins, which writes the install CD), `gcab`, zstd, the LLVM tools or numpy and Pillow), turns on KVM, restores the caches, checks the pins, then runs `rl install`, `rl image`, `rl parts`, `rl licences` and `rl manifest`, and uploads `release-files` and `v86-parts`.
- **`release.yml`** checks the tag, calls `build.yml` with KVM required, archives this repository and writes the source pointer, and publishes behind the `release` environment.

### Caches

| Cache | Key | Size | Why |
|---|---|---:|---|
| ReactOS ISO | `reactos-iso-<ISO SHA-256>` | about 400 MB | Saves a 360 MB download from SourceForge |
| Afterglow source | `afterglow-<commit>-<tar SHA-256>` | about 2 MB | Saves a GitHub download and the extraction, and holds the tar that `rl verify` re-checks |
| Golden disk | `golden-<rl golden key>` | about 160 MB (zstd of a 4 GiB sparse disk holding about 420 MB) | Saves the unattended install, three to five minutes with KVM |

GitHub keeps 10 GB of caches per repository and evicts the least recently used. One set of the three is about 570 MB, and only the golden disk changes often (when the answers, the memory or disk size or the install code change), so about a dozen golden disks fit beside the ISO. A cache made on a pull request is readable only by that pull request, while one made by a dispatch on `main` is readable by every pull request, so dispatch the build on `main` once after the pins change to warm it for everyone. A restored ISO or Afterglow tar is hashed again by `rl verify` before it is used, so a cache can never change what a build uses.
