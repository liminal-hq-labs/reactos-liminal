#!/usr/bin/env bash
# Builds afterfetch.exe into dist/ with no C compiler and no C library: Rust, rust-lld's lld-link and a Pentium target.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# usage: tools/afterfetch/build.sh [OUT_DIR]      (default OUT_DIR: tools/afterfetch/dist)
#
# `core` is built from source (-Zbuild-std) for a Pentium: the prebuilt one assumes SSE2, which a Pentium lacks. The options are
# unstable, so RUSTC_BOOTSTRAP=1 lets the pinned stable toolchain accept them. The linker is the toolchain's own rust-lld. Set
# CARGO_TARGET_DIR to keep the build output outside the tree. The result is reproducible: the same source and toolchain give the same file.
set -euo pipefail
cd "$(dirname "$0")"
export RUSTC_BOOTSTRAP=1
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-4}"
out="${1:-$PWD/dist}"
cargo build --release --locked --target win32.json \
	-Zbuild-std=core,compiler_builtins -Zbuild-std-features=compiler-builtins-mem -Zjson-target-spec
target="${CARGO_TARGET_DIR:-$PWD/target}"
mkdir -p "$out"
cp "$target/win32/release/afterfetch.exe" "$out/afterfetch.exe"
echo "build: $out/afterfetch.exe ($(wc -c < "$out/afterfetch.exe") bytes)"
