#!/usr/bin/env bash
# Fails when git holds a file of a kind that is an upstream ReactOS binary or a disk, ISO or archive of one.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Test fixtures are generated while the tests run and are never committed, so there is no allow-list.
pattern='\.(dll|sys|exe|cab|iso|img|bmp|cur|ani|msstyles|hiv|vdi|vmdk|qcow2|raw|zst|state|scr|cpl|drv|ocx)$'
offenders=$(git ls-files --cached --others --exclude-standard | grep -iE "$pattern" || true)
if [ -n "$offenders" ]; then
	echo "check-no-binaries: these files must not be in git (see AGENTS.md, 'Working with ReactOS images'):"
	while IFS= read -r offender; do echo "  $offender"; done <<<"$offenders"
	exit 1
fi
echo "check-no-binaries: ok"
