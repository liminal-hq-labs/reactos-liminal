# The survey of the icon groups in ReactOS 0.4.16's shell32.dll: what each group holds, frame by frame. Run it on a stock copy to
# regenerate the frame columns of docs/icon-survey.md and the stock frames in shell32-icons.json:
#
#     python3 -I -c 'import sys; sys.path.insert(0, "."); from reactos_liminal.icon_survey import main; sys.exit(main(sys.argv[1:]))' \\
#         SHELL32.DLL
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import json
import sys
from pathlib import Path

from .pe_resources import RT_GROUP_ICON, RT_ICON, PeFile, parse_group

TABLE_FILE = Path(__file__).parent / "shell32_icons.json"


def load_table() -> dict:
	"""The table of the shell32 groups the patcher replaces, and the ones it leaves alone."""
	return json.loads(TABLE_FILE.read_text())


def frames_text(frames) -> str:
	"""Frames as `48x32 32x32 16x32`: size, then bits per pixel."""
	return " ".join(f"{frame.width}@{frame.bit_count}" for frame in frames)


def survey(shell32: bytes) -> dict[int, list]:
	"""Group id -> its frames, for every icon group in the file."""
	pe = PeFile(shell32)
	groups = pe.data_entries(RT_GROUP_ICON)
	return {group_id: parse_group(pe.entry_data(offsets[0])) for group_id, offsets in sorted(groups.items())}


def icon_frame_count(shell32: bytes) -> int:
	return len(PeFile(shell32).data_entries(RT_ICON))


def main(argv: list[str]) -> int:
	if not argv:
		print("usage: icon_survey SHELL32.DLL [GROUP ...]", file=sys.stderr)
		return 2
	groups = survey(Path(argv[0]).read_bytes())
	wanted = [int(text) for text in argv[1:]] or sorted(groups)
	print(f"{len(groups)} icon groups")
	for group_id in wanted:
		print(f"{group_id}\t{frames_text(groups[group_id])}")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
