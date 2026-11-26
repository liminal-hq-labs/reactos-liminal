#!/usr/bin/env bash
# Download the pinned v86 release and unpack the emulator and its BIOS files into a folder outside the repository.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT

# The files are served as they came and are not committed. The archive and every file written are checked against SHA-256 sums
# recorded here; nothing is written if a sum differs, and nothing else is written.
# Usage: V86_DIR=DIR bash tools/fetch-v86.sh   (default DIR: ~/.cache/reactos-liminal/v86)

set -euo pipefail

version="0.5.473"
commit="315b2b0b758703ef0e6cc7b4088d6068f83f3c20"
npm_url="https://registry.npmjs.org/v86/-/v86-${version}.tgz"
bios_url="https://raw.githubusercontent.com/copy/v86/${commit}/bios"
npm_sha256="364ab67a68c1d83646e2ddf7caf73c24574694a132b2b43689ad0f72e7242636"

# destination name, source inside the package (or "bios" for the raw file), SHA-256
files=(
	"libv86.mjs package/build/libv86.mjs f9f3b4cae7dafb882e10e51aae9137ec52d5aed5ffbc9026f9081c73bbaae4c8"
	"v86.wasm package/build/v86.wasm 2f0c4150f266415b754a84a32e6f8e4c975a1d3abb94c78b047fa30027db1ef1"
	"v86-fallback.wasm package/build/v86-fallback.wasm 4eb64c9b7908d5931c1868eea4824b3a0a628eb86e6eac09d133776b50922d81"
	"bios/seabios.bin bios 73e3f359102e3a9982c35fce98eb7cd08f18303ac7f1ba6ebfbe6cdc1c244d98"
	"bios/vgabios.bin bios a4bc0d80cc3ca028c73dafa8fee396b8d054ce87ebd8abfbd31b06b437607880"
)


dest="${V86_DIR:-$HOME/.cache/reactos-liminal/v86}"
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "$(realpath -m "$dest")/" in
	"$repo"/*) echo "fetch-v86: the destination must be outside the repository: $dest" >&2; exit 2 ;;
esac

check() { # file expected-sha256 label
	local got
	got="$(sha256sum "$1" | cut -d' ' -f1)"
	if [ "$got" != "$2" ]; then
		echo "fetch-v86: checksum mismatch for $3: expected $2, got $got" >&2
		exit 1
	fi
}

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

echo "fetch-v86: downloading v86 ${version}"
curl --fail --silent --show-error --location --output "$work/v86.tgz" "$npm_url"
check "$work/v86.tgz" "$npm_sha256" "the v86 ${version} package"
mkdir "$work/pkg"
tar -xzf "$work/v86.tgz" -C "$work/pkg"

mkdir -p "$work/out/bios"
for entry in "${files[@]}"; do
	read -r name src sum <<<"$entry"
	if [ "$src" = bios ]; then
		curl --fail --silent --show-error --location --output "$work/out/$name" "$bios_url/$(basename "$name")"
	else
		cp "$work/pkg/$src" "$work/out/$name"
	fi
	check "$work/out/$name" "$sum" "$name"
done

mkdir -p "$dest/bios"
for entry in "${files[@]}"; do
	read -r name _ _ <<<"$entry"
	cp "$work/out/$name" "$dest/$name"
done
echo "fetch-v86: v86 ${version} is in $dest"
