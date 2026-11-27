# Progress output on stderr, so stdout stays for results.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import sys
import time


def log(tag: str, message: str) -> None:
	print(f"[{tag} {time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)
