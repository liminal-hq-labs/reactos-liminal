# Split a raw disk image into zstd-compressed parts that v86's chunked async disk reads: DIR/START-END.img.zst.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Every chunk gets a file, including all-zero ones (a few bytes each), because v86 asks for any chunk the guest reads. A part is named by
# its byte range, START-END, with END the start plus the chunk size (the last part is shorter than its name says). `manifest.json`
# records the sizes and the SHA-256 of the raw image.
import hashlib
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from .recipe import MIN_CHUNK_SIZE

PART_SUFFIX = ".img.zst"


class PartsError(Exception):
	"""A parts directory that cannot be made or does not match its image."""


@dataclass(frozen=True)
class PartsResult:
	size: int
	chunk: int
	level: int
	parts: int
	zero_parts: int
	compressed_bytes: int
	sha256: str


def part_name(start: int, chunk: int) -> str:
	return f"{start}-{start + chunk}{PART_SUFFIX}"


def zstd_compress(data: bytes, level: int) -> bytes:
	"""Compress one chunk with the zstd command (a single thread: the chunks are compressed side by side instead)."""
	argv = ["zstd", f"-{level}", *(["--ultra"] if level > 19 else []), "-T1", "-q", "-c"]
	done = subprocess.run(argv, input=data, capture_output=True, check=False)
	if done.returncode != 0:
		raise PartsError(f"zstd failed: {done.stderr.decode(errors='replace').strip()}")
	return done.stdout


def make_parts(image: Path, out_dir: Path, chunk: int, level: int = 19, workers: int = 4) -> PartsResult:
	"""Write every part and `manifest.json` into `out_dir` (an existing directory of parts is replaced)."""
	if chunk < MIN_CHUNK_SIZE or chunk & (chunk - 1):
		raise PartsError(f"the chunk size must be a power of two of at least 64 KiB, not {chunk}")
	if shutil.which("zstd") is None:
		raise PartsError("zstd is not installed")
	size = image.stat().st_size
	shutil.rmtree(out_dir, ignore_errors=True)
	out_dir.mkdir(parents=True)
	zero_compressed = zstd_compress(bytes(chunk), level)
	digest = hashlib.sha256()
	zero_parts = 0
	compressed_bytes = 0
	pending = []
	with open(image, "rb") as source, ThreadPoolExecutor(max_workers=workers) as pool:
		for start in range(0, size, chunk):
			data = source.read(chunk)
			digest.update(data)
			is_zero = not any(data)
			zero_parts += is_zero
			# A short last chunk is padded with zeros for the all-zero shortcut only; its part holds exactly the bytes it covers.
			if is_zero and len(data) == chunk:
				pending.append((start, zero_compressed))
			else:
				pending.append((start, pool.submit(zstd_compress, data, level)))
			while len(pending) > workers * 4:
				compressed_bytes += _write_part(out_dir, chunk, *pending.pop(0))
		for item in pending:
			compressed_bytes += _write_part(out_dir, chunk, *item)
	result = PartsResult(size, chunk, level, -(-size // chunk), zero_parts, compressed_bytes, digest.hexdigest())
	manifest = {
		"image": image.name,
		"size": result.size,
		"chunk": result.chunk,
		"level": result.level,
		"parts": result.parts,
		"zeroParts": result.zero_parts,
		"compressedBytes": result.compressed_bytes,
		"sha256": result.sha256,
	}
	(out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
	return result


def _write_part(out_dir: Path, chunk: int, start: int, compressed) -> int:
	data = compressed if isinstance(compressed, bytes) else compressed.result()
	(out_dir / part_name(start, chunk)).write_bytes(data)
	return len(data)


def read_parts(parts_dir: Path) -> bytes:
	"""Decompress and join the parts of a directory (for checks; the whole image is held in memory)."""
	manifest = json.loads((parts_dir / "manifest.json").read_text())
	chunk = manifest["chunk"]
	image = bytearray()
	for start in range(0, manifest["size"], chunk):
		done = subprocess.run(
			["zstd", "-d", "-q", "-c"], input=(parts_dir / part_name(start, chunk)).read_bytes(), capture_output=True, check=False
		)
		if done.returncode != 0:
			raise PartsError(f"zstd could not read part {start}")
		image += done.stdout
	return bytes(image)
