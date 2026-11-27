# Overwrite a file inside an ISO 9660 image in place, keeping its size and its place, so everything else on the disc (the ISO 9660 and
# UDF directories, the boot record, every other file) stays byte for byte as shipped.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# A rebuilt image (xorriso -map) did not work: the boot loader could not load the registry hive from it. Each edit here is a function
# from the file's old bytes to its new bytes, which must have the same length.
import re
import subprocess
from pathlib import Path

SECTOR = 2048


class IsoPatchError(Exception):
	"""An edit that cannot keep the file's size, or a file that is not on the disc."""


def find_file(iso: Path, path_on_disc: str) -> tuple[int, int]:
	"""The start block and size of a file on the disc, as `xorriso -find PATH -exec report_lba` reports them."""
	done = subprocess.run(
		["xorriso", "-indev", str(iso), "-find", path_on_disc, "-exec", "report_lba"],
		capture_output=True,
		text=True,
		check=False,
	)
	for line in (done.stdout + done.stderr).splitlines():
		if line.startswith("File data lba"):
			fields = re.split(r"[ ,]+", line)
			return int(fields[4]), int(fields[6])
	raise IsoPatchError(f"{path_on_disc} is not on {iso}")


def replace_text_file(old: bytes, text: bytes) -> bytes:
	"""A text file (an answers file) in place of the old one, padded with a comment line to the old size."""
	data = text.replace(b"\r\n", b"\n")
	if not data.endswith(b"\n"):
		data += b"\n"
	if len(data) > len(old) - 2:
		raise IsoPatchError(f"the new file is {len(data)} bytes; the file on the disc holds {len(old)}")
	return data + b";" + b" " * (len(old) - len(data) - 1)


def set_default_os(old: bytes, name: str) -> bytes:
	"""In freeldr.ini, make `name` the default boot entry. The shorter name is paid for with blank lines, which setup's reader skips."""
	key = b"DefaultOS="
	value_start = old.index(key) + len(key)
	value_end = value_start
	while old[value_end : value_end + 1] not in (b"\r", b"\n"):
		value_end += 1
	new_name = name.encode()
	line_end = b"\r\n" if old[value_end : value_end + 2] == b"\r\n" else b"\n"
	fill = (value_end - value_start) - len(new_name)
	if fill < 0 or fill % len(line_end):
		raise IsoPatchError(f"cannot keep the size of freeldr.ini with {name}")
	blank_lines = line_end * (fill // len(line_end))
	return old[:value_start] + new_name + old[value_end : value_end + len(line_end)] + blank_lines + old[value_end + len(line_end) :]


def substitute(old: bytes, find: str, replacement: str) -> bytes:
	"""Replace the one occurrence of `find`, padding with spaces to its length."""
	find_bytes, new_bytes = find.encode(), replacement.encode()
	if old.count(find_bytes) != 1 or len(new_bytes) > len(find_bytes):
		raise IsoPatchError(f"cannot replace {find!r} with {replacement!r}")
	return old.replace(find_bytes, new_bytes + b" " * (len(find_bytes) - len(new_bytes)))


def patch_in_place(iso: Path, lba: int, size: int, edit) -> None:
	"""Read `size` bytes at block `lba`, pass them through `edit`, and write the result back; the length must not change."""
	with open(iso, "r+b") as image:
		image.seek(lba * SECTOR)
		old = image.read(size)
		new = edit(old)
		if len(new) != size:
			raise IsoPatchError(f"the edit changed the size from {size} to {len(new)}")
		image.seek(lba * SECTOR)
		image.write(new)
