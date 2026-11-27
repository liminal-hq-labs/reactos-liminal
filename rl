#!/usr/bin/env bash
# Entry point for the `rl` command: runs the reactos_liminal package in isolated mode.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$here"
exec python3 -I -c 'import sys; sys.path.insert(0, sys.argv.pop(1)); from reactos_liminal.cli import main; sys.exit(main())' "$here" "$@"
