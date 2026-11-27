# Where things live: the repository, and the work directory that must stay outside it.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_WORK = Path("~/.cache/reactos-liminal").expanduser()


class WorkDirError(Exception):
	"""The work directory is not usable."""


def resolve_work(arg: str | os.PathLike | None = None) -> Path:
	"""The work directory: `--work`, else `$RL_WORK`, else ~/.cache/reactos-liminal. Refuses a path inside the repository."""
	raw = arg or os.environ.get("RL_WORK") or DEFAULT_WORK
	work = Path(raw).expanduser().resolve()
	if work == REPO or REPO in work.parents:
		raise WorkDirError(f"the work directory must be outside the repository ({REPO}): {work}")
	return work


def ensure(work: Path, *parts: str) -> Path:
	"""Create and return a sub-directory of the work directory."""
	d = work.joinpath(*parts)
	d.mkdir(parents=True, exist_ok=True)
	return d
