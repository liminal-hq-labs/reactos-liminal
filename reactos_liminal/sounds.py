# The Afterglow sound scheme: original, synthesized WAV files, the registry that selects them and the sample folder.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Every sound is made here from sine partials, decaying envelopes, a seeded noise source and a few echo taps, with the standard library
# only: no third-party sample, no recording, no tool. The same code gives the same bytes, so `pins/afterglow-sounds.json` holds each
# file's SHA-256 and a test regenerates them. The licence is the project's (Apache-2.0 OR MIT), because the sounds are this code's output.
#
# The design is a dusk palette in sound: a warm, glassy pluck (a sine with a few soft overtones and a slow decay) in D major, with
# rising figures for arriving (startup, logon, open, connect), falling figures for leaving (logoff, shutdown, close, disconnect) and
# short, round ticks for the things you do all day (menu, Start, minimize, maximize). Warnings are low and gentle, never shrill. A sound
# is a 16-bit stereo PCM WAV (a mono piece is written as two equal channels, because ReactOS's AC'97 path plays stereo only) at 11,025
# Hz, and 8,000 Hz for the sample folder's longer pieces, rates that carry every tone here and keep the download light. Its highest
# sample is scaled to -6 dBFS.

import hashlib
import io
import json
import math
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .paths import REPO

PINS_FILE = REPO / "pins" / "afterglow-sounds.json"
MEDIA_FOLDER = "ReactOS/media"  # `%SystemRoot%\Media`
MEDIA_GUEST = "%SystemRoot%\\Media"
SAMPLES_GUEST = "C:\\Sounds"
SAMPLES_FOLDER = "Sounds"
SCHEME_NAME = "Afterglow"
PEAK_DBFS = -6.0
RATE = 11025
LOW_RATE = 8000


class SoundError(Exception):
	"""A sound that does not match its pin, or a name the set does not have."""


def midi(note: str) -> float:
	"""The frequency in Hz of a note name such as `F#5` or `Bb3` (A4 is 440 Hz)."""
	steps = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
	number = steps[note[0]]
	rest = note[1:]
	if rest[0] == "#":
		number += 1
		rest = rest[1:]
	elif rest[0] == "b":
		number -= 1
		rest = rest[1:]
	return 440.0 * 2.0 ** ((number + 12 * (int(rest) + 1) - 69) / 12.0)


class Noise:
	"""A seeded xorshift32 source, so a noise sound is the same on every machine."""

	def __init__(self, seed: int):
		self.state = seed or 1

	def next(self) -> float:
		"""A number from -1 to 1."""
		state = self.state
		state ^= (state << 13) & 0xFFFFFFFF
		state ^= state >> 17
		state ^= (state << 5) & 0xFFFFFFFF
		self.state = state
		return state / 2147483648.0 - 1.0


Buffer = list[float]


def silence(seconds: float, rate: int) -> Buffer:
	return [0.0] * int(round(seconds * rate))


def add(target: Buffer, voice: Buffer, start: float, rate: int, gain: float = 1.0) -> None:
	"""Mix `voice` into `target` from `start` seconds, growing nothing: what runs past the end is dropped."""
	offset = int(round(start * rate))
	for index, value in enumerate(voice):
		position = offset + index
		if position >= len(target):
			break
		target[position] += value * gain


# A partial is (multiple of the base frequency, level, decay-time multiplier). Higher partials fade faster, as in a struck glass.
GLASS = ((1.0, 1.0, 1.0), (2.0, 0.28, 0.55), (3.0, 0.09, 0.35), (1.003, 0.35, 1.2))
SOFT = ((1.0, 1.0, 1.0), (2.0, 0.12, 0.5), (1.004, 0.3, 1.1))
HOLLOW = ((1.0, 1.0, 1.0), (3.0, 0.18, 0.6), (5.0, 0.06, 0.4))


def pluck(
	frequency: float, length: float, tau: float, rate: int, partials: tuple = GLASS, attack: float = 0.004, release: float = 0.02
) -> Buffer:
	"""A struck, decaying tone of `length` seconds: `tau` is the decay time of the base partial, `attack` the rise and `release` the
	closing fade that keeps the end free of a click."""
	count = int(round(length * rate))
	attack_samples = max(1, int(attack * rate))
	release_samples = max(1, int(release * rate))
	out = [0.0] * count
	for multiple, level, decay_scale in partials:
		partial_frequency = frequency * multiple
		if partial_frequency >= rate / 2.2:
			continue
		step = 2.0 * math.pi * partial_frequency / rate
		decay = math.exp(-1.0 / (rate * tau * decay_scale))
		amplitude = level
		phase = 0.0
		for index in range(count):
			out[index] += amplitude * math.sin(phase)
			phase += step
			amplitude *= decay
	for index in range(min(attack_samples, count)):
		out[index] *= index / attack_samples
	for index in range(min(release_samples, count)):
		out[count - 1 - index] *= index / release_samples
	return out


def swell(frequency: float, length: float, rate: int, partials: tuple = SOFT, rise: float = 0.09, fall: float = 0.5) -> Buffer:
	"""A held tone that rises over `rise` seconds and fades over the last `fall` seconds, for the chord that closes a figure."""
	count = int(round(length * rate))
	rise_samples = max(1, int(rise * rate))
	fall_samples = max(1, int(fall * rate))
	out = [0.0] * count
	for multiple, level, _ in partials:
		step = 2.0 * math.pi * frequency * multiple / rate
		phase = 0.0
		for index in range(count):
			out[index] += level * math.sin(phase)
			phase += step
	for index in range(count):
		gain = 1.0
		if index < rise_samples:
			gain = 0.5 - 0.5 * math.cos(math.pi * index / rise_samples)
		remaining = count - 1 - index
		if remaining < fall_samples:
			gain *= 0.5 - 0.5 * math.cos(math.pi * remaining / fall_samples)
		out[index] *= gain
	return out


def chirp(start_frequency: float, end_frequency: float, length: float, rate: int, tau: float) -> Buffer:
	"""A short sine that glides from one pitch to another, for minimize and maximize."""
	count = int(round(length * rate))
	out = [0.0] * count
	phase = 0.0
	for index in range(count):
		progress = index / count
		frequency = start_frequency + (end_frequency - start_frequency) * progress
		phase += 2.0 * math.pi * frequency / rate
		fade_in = min(1.0, index / (0.004 * rate))
		fade_out = min(1.0, (count - 1 - index) / (0.01 * rate))
		out[index] = math.sin(phase) * math.exp(-index / (rate * tau)) * fade_in * fade_out
	return out


def crinkle(length: float, rate: int, seed: int) -> Buffer:
	"""Soft crumpling paper: low-passed noise in short, uneven bursts that thin out, for the empty recycle bin."""
	noise = Noise(seed)
	count = int(round(length * rate))
	out = [0.0] * count
	burst_end = 0
	level = 0.0
	filtered = 0.0
	for index in range(count):
		if index >= burst_end:
			burst_end = index + int((0.012 + 0.03 * abs(noise.next())) * rate)
			level = (0.3 + 0.7 * abs(noise.next())) * math.exp(-index / (rate * length * 0.45))
		filtered += 0.35 * (noise.next() - filtered)
		position = (burst_end - index) / rate
		out[index] = (
			filtered * level * min(1.0, position * 90.0) * min(1.0, index / (0.004 * rate)) * min(1.0, (count - 1 - index) / (0.01 * rate))
		)
	return out


def tick(frequency: float, length: float, rate: int, tau: float, seed: int, grit: float = 0.12) -> Buffer:
	"""A round little click: a quickly decaying sine with a touch of filtered noise at the front."""
	noise = Noise(seed)
	count = int(round(length * rate))
	out = [0.0] * count
	filtered = 0.0
	for index in range(count):
		envelope = math.exp(-index / (rate * tau))
		filtered += 0.5 * (noise.next() - filtered)
		out[index] = (math.sin(2.0 * math.pi * frequency * index / rate) + grit * filtered * 4.0) * envelope
		out[index] *= min(1.0, index / (0.0015 * rate))
	for index in range(min(int(0.006 * rate), count)):
		out[count - 1 - index] *= index / (0.006 * rate)
	return out


def echo(buffer: Buffer, rate: int, taps: tuple[tuple[float, float], ...], tail: float, warmth: float = 0.45) -> Buffer:
	"""Add soft room echoes (`(delay in seconds, level)` pairs) after a one-pole low-pass, and `tail` seconds of room after the end."""
	out = buffer + [0.0] * int(round(tail * rate))
	wet = 0.0
	smoothed = []
	for value in buffer:
		wet += warmth * (value - wet)
		smoothed.append(wet)
	for delay, level in taps:
		offset = int(round(delay * rate))
		for index, value in enumerate(smoothed):
			if index + offset < len(out):
				out[index + offset] += value * level
	return out


ROOM = ((0.047, 0.28), (0.083, 0.2), (0.131, 0.14), (0.197, 0.09), (0.283, 0.05))
SMALL_ROOM = ((0.031, 0.2), (0.057, 0.12), (0.089, 0.07))


def figure(notes: list[tuple[str, float]], length: float, rate: int, tau: float, partials: tuple = GLASS) -> Buffer:
	"""A run of plucked notes, each `(name, start second)`, mixed into `length` seconds."""
	out = silence(length, rate)
	for name, start in notes:
		add(out, pluck(midi(name), length - start, tau, rate, partials), start, rate)
	return out


def startup() -> Buffer:
	out = figure([("D4", 0.0), ("A4", 0.15), ("D5", 0.30), ("F#5", 0.45), ("A5", 0.60)], 1.7, RATE, 0.38)
	for name, level in (("D5", 0.45), ("A5", 0.4), ("E6", 0.22), ("F#4", 0.35)):
		add(out, swell(midi(name), 1.0, RATE, fall=0.55), 0.68, RATE, level)
	return echo(out, RATE, ROOM, 0.2)


def logon() -> Buffer:
	out = figure([("A4", 0.0), ("C#5", 0.12), ("E5", 0.24), ("A5", 0.36)], 1.0, RATE, 0.26)
	for name, level in (("E5", 0.4), ("A5", 0.35)):
		add(out, swell(midi(name), 0.58, RATE, fall=0.4), 0.42, RATE, level)
	return echo(out, RATE, ROOM, 0.2)


def logoff() -> Buffer:
	out = figure([("E5", 0.0), ("C#5", 0.13), ("A4", 0.26), ("E4", 0.39)], 0.9, RATE, 0.24)
	return echo(out, RATE, ROOM, 0.2)


def shutdown() -> Buffer:
	out = figure([("A5", 0.0), ("F#5", 0.16), ("D5", 0.32), ("A4", 0.48)], 1.0, RATE, 0.26)
	for name, level in (("D4", 0.5), ("A4", 0.35)):
		add(out, swell(midi(name), 0.48, RATE, rise=0.05, fall=0.4), 0.52, RATE, level)
	return echo(out, RATE, ROOM, 0.2)


def beep() -> Buffer:
	return echo(pluck(midi("A5"), 0.17, 0.06, RATE, SOFT), RATE, SMALL_ROOM, 0.04)


def critical_stop() -> Buffer:
	out = silence(0.55, RATE)
	add(out, pluck(midi("F4"), 0.55, 0.16, RATE, HOLLOW), 0.0, RATE)
	add(out, pluck(midi("D4"), 0.35, 0.18, RATE, HOLLOW), 0.2, RATE)
	add(out, pluck(midi("D3"), 0.35, 0.16, RATE, SOFT), 0.2, RATE, 0.8)
	return echo(out, RATE, SMALL_ROOM, 0.12)


def exclamation() -> Buffer:
	out = silence(0.42, RATE)
	add(out, pluck(midi("A5"), 0.42, 0.1, RATE), 0.0, RATE)
	add(out, pluck(midi("A5"), 0.28, 0.1, RATE), 0.14, RATE, 0.8)
	return echo(out, RATE, SMALL_ROOM, 0.1)


def asterisk() -> Buffer:
	out = silence(0.45, RATE)
	add(out, pluck(midi("E6"), 0.45, 0.13, RATE), 0.0, RATE)
	add(out, pluck(midi("A5"), 0.45, 0.14, RATE, SOFT), 0.0, RATE, 0.5)
	return echo(out, RATE, SMALL_ROOM, 0.1)


def question() -> Buffer:
	return echo(figure([("A4", 0.0), ("D5", 0.13)], 0.42, RATE, 0.14, SOFT), RATE, SMALL_ROOM, 0.08)


def menu_command() -> Buffer:
	return tick(1700.0, 0.045, RATE, 0.007, 11)


def start_click() -> Buffer:
	return tick(1050.0, 0.07, RATE, 0.012, 23)


def minimize() -> Buffer:
	return chirp(950.0, 520.0, 0.12, RATE, 0.08)


def maximize() -> Buffer:
	return chirp(520.0, 950.0, 0.12, RATE, 0.08)


def open_window() -> Buffer:
	return figure([("D6", 0.0), ("A6", 0.05)], 0.12, RATE, 0.03, SOFT)


def close_window() -> Buffer:
	return figure([("A6", 0.0), ("D6", 0.05)], 0.12, RATE, 0.03, SOFT)


def recycle() -> Buffer:
	out = crinkle(0.4, RATE, 5)
	out += silence(0.05, RATE)
	add(out, pluck(midi("A6"), 0.1, 0.05, RATE, SOFT), 0.37, RATE, 0.35)
	return out


def melody() -> Buffer:
	"""The five-second demo piece: a D major pentatonic tune over a slow bass, 96 beats a minute, ending on a long D."""
	eighth = 0.3125
	tune = [
		("F#5", 0, 2),
		("A5", 2, 2),
		("B5", 4, 1),
		("A5", 5, 1),
		("F#5", 6, 2),
		("E5", 8, 2),
		("D5", 10, 2),
		("E5", 12, 1),
		("F#5", 13, 1),
		("D5", 14, 2),
	]
	out = silence(5.0, LOW_RATE)
	for name, position, beats in tune:
		length = 5.0 - position * eighth
		add(out, pluck(midi(name), length, 0.32 + 0.12 * beats, LOW_RATE), position * eighth, LOW_RATE)
	for chord, position in ((("D3", "A3", "F#4"), 0), (("G3", "D4", "B4"), 6), (("D3", "A3", "F#4"), 12)):
		for name in chord:
			add(out, pluck(midi(name), 5.0 - position * eighth, 1.1, LOW_RATE, SOFT, 0.03), position * eighth, LOW_RATE, 0.32)
	faded = echo(out, LOW_RATE, ROOM, 0.0, 0.5)
	fade = int(0.5 * LOW_RATE)
	for index in range(fade):
		faded[len(faded) - 1 - index] *= index / fade
	return faded


def left_and_right() -> tuple[Buffer, Buffer]:
	"""A stereo check: a tone in the left channel, then a different one in the right, twice."""
	left = silence(1.6, LOW_RATE)
	right = silence(1.6, LOW_RATE)
	for start in (0.0, 0.8):
		add(left, pluck(midi("D5"), 0.45, 0.2, LOW_RATE), start, LOW_RATE)
		add(right, pluck(midi("A5"), 0.45, 0.2, LOW_RATE), start + 0.4, LOW_RATE)
	return left, right


@dataclass(frozen=True)
class Sound:
	"""One file: its name on the disk, the folder it goes to, how it is made and what it is for."""

	file: str
	make: Callable[[], Buffer | tuple[Buffer, Buffer]]
	rate: int
	note: str


SYSTEM_SOUNDS = (
	Sound("Afterglow_Startup.wav", startup, RATE, "A warm D major arpeggio that settles into a soft chord, the start of a session"),
	Sound("Afterglow_Logon.wav", logon, RATE, "A shorter, brighter A major rise"),
	Sound("Afterglow_Logoff.wav", logoff, RATE, "The logon figure falling"),
	Sound("Afterglow_Shutdown.wav", shutdown, RATE, "A slow descent to a low D, the end of a session"),
	Sound("Afterglow_Default.wav", beep, RATE, "The default beep: one soft tone"),
	Sound("Afterglow_Critical_Stop.wav", critical_stop, RATE, "Two low, hollow tones falling a minor third, gentle for an error"),
	Sound("Afterglow_Exclamation.wav", exclamation, RATE, "A double ping on A"),
	Sound("Afterglow_Asterisk.wav", asterisk, RATE, "A single high bell, for information"),
	Sound("Afterglow_Question.wav", question, RATE, "Two notes rising and left open"),
	Sound("Afterglow_Menu_Command.wav", menu_command, RATE, "A very short, round tick"),
	Sound("Afterglow_Start.wav", start_click, RATE, "A slightly lower, softer tick for the Start menu and navigation"),
	Sound("Afterglow_Minimize.wav", minimize, RATE, "A quick glide down"),
	Sound("Afterglow_Maximize.wav", maximize, RATE, "A quick glide up"),
	Sound("Afterglow_Open.wav", open_window, RATE, "Two tiny rising notes"),
	Sound("Afterglow_Close.wav", close_window, RATE, "Two tiny falling notes"),
	Sound("Afterglow_Recycle.wav", recycle, RATE, "Crumpling paper that ends with a small bell"),
)
SAMPLE_SOUNDS = (
	Sound("Dusk melody.wav", melody, LOW_RATE, "A five-second tune in D major, to play in Media Player"),
	Sound("Left and right.wav", left_and_right, LOW_RATE, "A stereo check: a tone on the left, then a different one on the right, twice"),
)
# The sample folder holds no copies; the system sounds are in the Media folder.
SAMPLE_COPIES = ()

# Event -> (Registry app key, the sound file, or None to leave the event silent). The same files serve several events.
EVENTS: tuple[tuple[str, str, str | None], ...] = (
	(".Default", ".Default", "Afterglow_Default.wav"),
	(".Default", "AppGPFault", "Afterglow_Critical_Stop.wav"),
	(".Default", "Close", "Afterglow_Close.wav"),
	(".Default", "CriticalBatteryAlarm", "Afterglow_Critical_Stop.wav"),
	(".Default", "DeviceConnect", "Afterglow_Open.wav"),
	(".Default", "DeviceDisconnect", "Afterglow_Close.wav"),
	(".Default", "DeviceFail", "Afterglow_Exclamation.wav"),
	(".Default", "LowBatteryAlarm", "Afterglow_Exclamation.wav"),
	(".Default", "MailBeep", "Afterglow_Asterisk.wav"),
	(".Default", "Maximize", "Afterglow_Maximize.wav"),
	(".Default", "MenuCommand", "Afterglow_Menu_Command.wav"),
	(".Default", "MenuPopup", None),
	(".Default", "Minimize", "Afterglow_Minimize.wav"),
	(".Default", "Open", "Afterglow_Open.wav"),
	(".Default", "PrintComplete", "Afterglow_Asterisk.wav"),
	(".Default", "RestoreDown", "Afterglow_Minimize.wav"),
	(".Default", "RestoreUp", "Afterglow_Maximize.wav"),
	(".Default", "SystemAsterisk", "Afterglow_Asterisk.wav"),
	(".Default", "SystemExclamation", "Afterglow_Exclamation.wav"),
	(".Default", "SystemExit", "Afterglow_Shutdown.wav"),
	(".Default", "SystemHand", "Afterglow_Critical_Stop.wav"),
	(".Default", "SystemNotification", "Afterglow_Asterisk.wav"),
	(".Default", "SystemQuestion", "Afterglow_Question.wav"),
	(".Default", "SystemStart", "Afterglow_Startup.wav"),
	(".Default", "WindowsLogoff", "Afterglow_Logoff.wav"),
	(".Default", "WindowsLogon", "Afterglow_Logon.wav"),
	("Explorer", "EmptyRecycleBin", "Afterglow_Recycle.wav"),
	("Explorer", "Navigating", "Afterglow_Start.wav"),
)


def encode(channels: list[Buffer], rate: int) -> bytes:
	"""A 16-bit PCM WAV with its highest sample at `PEAK_DBFS`. The header is the standard library's, so the bytes depend on the audio
	alone."""
	fade = int(0.006 * rate)  # the last few milliseconds close to zero, so no sound ends on a step
	for channel in channels:
		for index in range(min(fade, len(channel))):
			channel[len(channel) - 1 - index] *= index / fade
	peak = max((abs(value) for channel in channels for value in channel), default=0.0)
	scale = (10.0 ** (PEAK_DBFS / 20.0) * 32767.0 / peak) if peak else 0.0
	if len(channels) == 1:  # the card's mixer path takes stereo only: a mono sound is written as two equal channels
		channels = [channels[0], channels[0]]
	length = len(channels[0])
	frames = bytearray()
	for index in range(length):
		for channel in channels:
			frames += int(round(channel[index] * scale)).to_bytes(2, "little", signed=True)
	sink = io.BytesIO()
	with wave.open(sink, "wb") as writer:
		writer.setnchannels(len(channels))
		writer.setsampwidth(2)
		writer.setframerate(rate)
		writer.writeframes(bytes(frames))
	return sink.getvalue()


def render(sound: Sound) -> bytes:
	made = sound.make()
	channels = list(made) if isinstance(made, tuple) else [made]
	return encode(channels, sound.rate)


def render_all() -> dict[str, bytes]:
	"""Every file of the set by name: the system sounds and the sample folder's own files (not its copies)."""
	return {sound.file: render(sound) for sound in SYSTEM_SOUNDS + SAMPLE_SOUNDS}


def disk_files(scheme: bool, samples: bool, rendered: dict[str, bytes] | None = None) -> dict[str, bytes]:
	"""Where each file goes on the disk: the system sounds in `ReactOS/media` when `scheme` is set, and the samples and the chime copy in
	`Sounds` when `samples` is. Nothing is made when neither is."""
	if not (scheme or samples):
		return {}
	rendered = render_all() if rendered is None else rendered
	files = {}
	if scheme:
		files.update({f"{MEDIA_FOLDER}/{sound.file}": rendered[sound.file] for sound in SYSTEM_SOUNDS})
	if samples:
		files.update({f"{SAMPLES_FOLDER}/{sound.file}": rendered[sound.file] for sound in SAMPLE_SOUNDS})
		files.update({f"{SAMPLES_FOLDER}/{name}": rendered[source] for source, name in SAMPLE_COPIES})
	return files


def describe(scheme: bool, samples: bool) -> str:
	"""One line for the plan: what the files step writes for these two switches, or an empty string."""
	parts = []
	if scheme:
		parts.append(f"the {SCHEME_NAME} sound scheme ({len(SYSTEM_SOUNDS)} synthesized files in {MEDIA_FOLDER})")
	if samples:
		parts.append(f"{len(SAMPLE_SOUNDS) + len(SAMPLE_COPIES)} sample sounds in {SAMPLES_FOLDER}")
	return " and ".join(parts)


def expand_string(text: str) -> str:
	"""A registry file's value for a REG_EXPAND_SZ string (`hex(2):`), the type ReactOS writes for a sound so `%SystemRoot%` is expanded
	when it is played."""
	return "hex(2):" + ",".join(f"{byte:02x}" for byte in (text + "\0").encode("utf-16-le"))


def scheme_reg() -> str:
	"""The registry file that adds the Afterglow scheme, selects it and writes it as the current sounds. The scheme sits beside ReactOS's
	own ("ReactOS Default" and "No sounds", which stay in the list). An event that has no sound keeps the value empty."""
	lines = [
		"Windows Registry Editor Version 5.00",
		"",
		"; The Afterglow sound scheme: files in %SystemRoot%\\Media, written by `rl image`. It is added to the scheme list (Control Panel,",
		"; Sounds and Audio Devices, Sounds), selected, and written as the current value of every event, which is what the system plays.",
		'; Select "No sounds" in that list to silence the system. Applied once, inside the guest, by apply-settings.cmd.',
		";",
		"; (c) Copyright 2026 Liminal HQ, Scott Morris",
		"; SPDX-License-Identifier: Apache-2.0 OR MIT",
		"",
		"[HKEY_CURRENT_USER\\AppEvents\\Schemes]",
		f'@="{SCHEME_NAME}"',
		"",
		"[HKEY_CURRENT_USER\\AppEvents\\Schemes\\Names\\" + SCHEME_NAME + "]",
		f'@="{SCHEME_NAME}"',
	]
	for app, event, file in EVENTS:
		value = expand_string(f"{MEDIA_GUEST}\\{file}" if file else "")
		base = f"[HKEY_CURRENT_USER\\AppEvents\\Schemes\\Apps\\{app}\\{event}"
		lines += ["", f"{base}\\{SCHEME_NAME}]", f"@={value}", "", f"{base}\\.Current]", f"@={value}"]
	return "\n".join(lines) + "\n"


def sha256(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


def load_pins(path: Path = PINS_FILE) -> dict[str, str]:
	return json.loads(path.read_text(encoding="utf-8"))["sha256"]


def check_pins(rendered: dict[str, bytes], pins: dict[str, str] | None = None) -> None:
	"""Raise when a generated file differs from its pin, or the set and the pins list different files."""
	pins = load_pins() if pins is None else pins
	if set(pins) != set(rendered):
		raise SoundError(f"the sound set and {PINS_FILE.name} differ: {sorted(set(pins) ^ set(rendered))}")
	for name, data in rendered.items():
		if sha256(data) != pins[name]:
			raise SoundError(f"{name} does not match its pin: {sha256(data)} (pinned {pins[name]})")


def write_pins(rendered: dict[str, bytes], path: Path = PINS_FILE) -> None:
	text = json.dumps({"sha256": {name: sha256(data) for name, data in sorted(rendered.items())}}, indent="\t") + "\n"
	path.write_text(text, encoding="utf-8")
