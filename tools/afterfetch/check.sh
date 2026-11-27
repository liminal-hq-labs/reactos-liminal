#!/usr/bin/env bash
# Checks afterfetch.exe: format, lints, the host tests of the pure parts, then the build and the checks on the executable (a plain
# 32-bit console program: subsystem 4.0, fixed base, no C runtime, Pentium instructions only, ANSI imports on the allowlist).
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# usage: tools/afterfetch/check.sh
#
# Needs the pinned toolchain (rust-toolchain.toml installs it, with rust-src and llvm-tools). With --reproducible the build is run a
# second time in a different directory and the two files are compared.
set -euo pipefail
cd "$(dirname "$0")"
export RUSTC_BOOTSTRAP=1
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-4}"
host="$(rustc -vV | sed -n 's/^host: //p')"
cargo_args=(--target win32.json '-Zbuild-std=core,compiler_builtins' -Zbuild-std-features=compiler-builtins-mem -Zjson-target-spec)

cargo fmt --all -- --check
cargo clippy --release --locked "${cargo_args[@]}" -- -D warnings
cargo test --lib --locked --target "$host"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
CARGO_TARGET_DIR="$work/target" ./build.sh "$work/dist"
exe="$work/dist/afterfetch.exe"

# llvm-objdump comes with the toolchain's llvm-tools component; a system one is the fallback.
objdump="$(rustc --print sysroot)/lib/rustlib/$host/bin/llvm-objdump"
[ -x "$objdump" ] || objdump="$(command -v llvm-objdump llvm-objdump-19 llvm-objdump-18 llvm-objdump-17 2> /dev/null | head -1 || true)"
[ -n "$objdump" ] || { echo "check: llvm-objdump not found"; exit 1; }

fail() { echo "check: $*" >&2; exit 1; }

# A plain 32-bit console program that Windows 95 and ReactOS will load.
if command -v file > /dev/null; then
	case "$(file -b "$exe")" in
	"PE32 executable for MS Windows 4.00 (console), Intel i386"* | "PE32 executable (console) Intel 80386, for MS Windows"*) ;;
	*) fail "file says: $(file -b "$exe")" ;;
	esac
fi
header="$("$objdump" -p "$exe")"
field() { awk -v key="$1" '$1 == key {print $2}' <<< "$header" | head -1; }
[ "$(field MajorSubsystemVersion)" = 4 ] && [ "$(field MinorSubsystemVersion)" = 0 ] || fail "the subsystem version is not 4.0"
grep -q "relocations stripped" <<< "$header" || fail "the executable has relocations (it is built /FIXED)"
dlls="$(awk '/DLL Name:/ {print tolower($3)}' <<< "$header" | sort -u | tr '\n' ' ')"
case "$dlls" in
*msvcrt* | *ucrt* | *vcruntime* | *api-ms-*) fail "imports a C runtime: $dlls" ;;
esac

# Every import is on the allowlist, and none is a wide-character entry point.
got="$(awk '/DLL Name:/ {dll=tolower($3)} /^ +[0-9]+ +[A-Za-z_]/ {print dll "!" $2}' <<< "$("$objdump" -p "$exe")" | sort -u)"
allow="$(grep -v '^#' imports.allow | grep -v '^$' | tr '[:upper:]' '[:lower:]' | sort -u)"
while IFS= read -r import; do
	[ -n "$import" ] || continue
	grep -qxF "$(tr '[:upper:]' '[:lower:]' <<< "$import")" <<< "$allow" || fail "not on the allowlist: $import"
	case "$import" in *W) fail "wide-character entry point: $import" ;; esac
done <<< "$got"

# No instruction a Pentium lacks: a vector register, a conditional move, or the newer bit tricks.
bad="$("$objdump" -d --no-show-raw-insn "$exe" | grep -Ei '(xmm|ymm|zmm)[0-9]|[[:space:]]%?mm[0-7]([^0-9a-z]|$)|[[:space:]](cmov[a-z]+|emms|movbe|popcnt|lzcnt|tzcnt|prefetch[a-z0-9]*|[ls]fence|mfence)[[:space:]]' || true)"
[ -z "$bad" ] || fail "instructions a Pentium lacks:
$(head -20 <<< "$bad")"

echo "check: ok: $(wc -c < "$exe") bytes, imports $(wc -l <<< "$got"), subsystem 4.0, Pentium instructions only"

if [ "${1:-}" = "--reproducible" ]; then
	second="$(mktemp -d)"
	trap 'rm -rf "$work" "$second"' EXIT
	cp -r . "$second/src"
	rm -rf "$second/src/dist" "$second/src/target"
	(cd "$second/src" && CARGO_TARGET_DIR="$second/target" ./build.sh "$second/dist" > /dev/null)
	cmp "$exe" "$second/dist/afterfetch.exe" || fail "two builds in different directories differ"
	echo "check: reproducible: $(sha256sum < "$exe" | cut -d' ' -f1)"
fi
