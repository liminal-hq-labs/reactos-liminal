# Tests for the Afterglow sound scheme: the synthesized files, their pins, the registry and what the recipes write.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import io
import math
import struct
import wave

import pytest

from reactos_liminal import image, settings, sounds
from reactos_liminal.recipe import load


@pytest.fixture(scope="module")
def rendered():
	return sounds.render_all()


def samples_of(data: bytes) -> tuple[wave.Wave_read, tuple[int, ...]]:
	with wave.open(io.BytesIO(data)) as reader:
		frames = reader.readframes(reader.getnframes())
		return reader, struct.unpack(f"<{len(frames) // 2}h", frames)


def test_every_sound_matches_its_pin(rendered):
	sounds.check_pins(rendered)


def test_a_changed_file_or_a_missing_pin_is_refused(rendered):
	pins = {name: sounds.sha256(data) for name, data in rendered.items()}
	with pytest.raises(sounds.SoundError, match="does not match"):
		sounds.check_pins({**rendered, "Dusk melody.wav": b"x"}, pins)
	with pytest.raises(sounds.SoundError, match="differ"):
		sounds.check_pins(rendered, {name: pins[name] for name in list(pins)[1:]})


def test_the_sounds_are_the_same_every_time(rendered):
	assert sounds.render_all() == rendered


def test_each_file_is_16_bit_pcm_peaking_at_minus_6_dbfs(rendered):
	expected = round(10 ** (sounds.PEAK_DBFS / 20) * 32767)
	for name, data in rendered.items():
		reader, values = samples_of(data)
		assert reader.getsampwidth() == 2 and reader.getcomptype() == "NONE", name
		assert reader.getnchannels() == 2 and 8000 <= reader.getframerate() <= 48000, name  # the card's path plays stereo only
		assert max(map(abs, values)) == expected, name
		assert abs(values[0]) < 2 and abs(values[-1]) < 8, f"{name} does not start and end at silence"


def test_the_set_is_light_and_the_pieces_are_the_lengths_the_notes_say(rendered):
	files = sounds.disk_files(True, True, rendered)
	assert sum(len(data) for data in files.values()) < 600 * 1024
	lengths = {name: samples_of(data)[0].getnframes() / samples_of(data)[0].getframerate() for name, data in rendered.items()}
	assert 1.5 <= lengths["Afterglow_Startup.wav"] <= 2.5
	assert lengths["Dusk melody.wav"] == pytest.approx(5.0)
	assert all(lengths[name] < 0.2 for name in ("Afterglow_Menu_Command.wav", "Afterglow_Minimize.wav", "Afterglow_Open.wav"))


def test_the_stereo_check_has_a_tone_in_each_channel_at_different_times(rendered):
	reader, values = samples_of(rendered["Left and right.wav"])
	assert reader.getnchannels() == 2
	left, right = values[0::2], values[1::2]
	half = len(left) // 4  # the first tone is on the left, then the right, twice
	assert max(map(abs, left[:half])) > 1000 and max(map(abs, right[:half])) < 50
	assert max(map(abs, right[half : 2 * half])) > 1000 and not math.isclose(max(left), 0)


def test_every_event_names_a_file_of_the_set_and_the_scheme_is_selected(rendered):
	text = sounds.scheme_reg()
	assert text.startswith("Windows Registry Editor Version 5.00") and "SPDX-License-Identifier: Apache-2.0 OR MIT" in text
	assert '[HKEY_CURRENT_USER\\AppEvents\\Schemes]\n@="Afterglow"' in text
	assert '[HKEY_CURRENT_USER\\AppEvents\\Schemes\\Names\\Afterglow]\n@="Afterglow"' in text
	system = {sound.file for sound in sounds.SYSTEM_SOUNDS}
	for _app, _event, file in sounds.EVENTS:
		assert file is None or file in system
	events = {event for _app, event, _file in sounds.EVENTS}
	assert {"SystemStart", "WindowsLogon", "WindowsLogoff", "SystemExit", "SystemHand", "SystemExclamation", "SystemAsterisk"} <= events
	assert {"SystemQuestion", ".Default", "MenuCommand", "Open", "Close", "Minimize", "Maximize", "EmptyRecycleBin"} <= events
	startup = sounds.expand_string("%SystemRoot%\\Media\\Afterglow_Startup.wav")
	assert f"[HKEY_CURRENT_USER\\AppEvents\\Schemes\\Apps\\.Default\\SystemStart\\.Current]\n@={startup}" in text
	assert f"SystemStart\\Afterglow]\n@={startup}" in text
	assert startup.startswith("hex(2):25,00,53,00,79,00") and startup.endswith(",76,00,00,00")  # %Sy ... v, then the terminator
	assert "\\MenuPopup\\.Current]\n@=hex(2):00,00" in text  # a silent event keeps an empty value


def test_every_system_sound_is_used_by_an_event():
	used = {file for _app, _event, file in sounds.EVENTS}
	assert {sound.file for sound in sounds.SYSTEM_SOUNDS} <= used


def test_the_files_go_where_the_switches_say(rendered):
	assert sounds.disk_files(False, False) == {}
	scheme = sounds.disk_files(True, False, rendered)
	assert scheme and all(path.startswith("ReactOS/media/Afterglow_") for path in scheme)
	samples = sounds.disk_files(False, True, rendered)
	assert set(samples) == {"Sounds/Dusk melody.wav", "Sounds/Left and right.wav"}


def test_both_recipes_write_the_scheme_the_samples_and_a_sound_test_shortcut(base_recipe_path, compact_recipe_path):
	for path in (base_recipe_path, compact_recipe_path):
		recipe = load(path)
		assert recipe.section("sounds") == {"scheme": True, "samples": True}
		assert "afterglow-sounds" in settings.settings_files(recipe)
		assert any(item["name"] == "Sound test" and "mplay32.exe" in item["target"] for item in recipe.data["shortcuts"])
		assert "sounds" in " ".join(image.plan_image(recipe, path.parent).steps)


def test_a_recipe_without_the_switch_writes_no_sound(base_recipe_path, tmp_path):
	path = tmp_path / "r.toml"
	path.write_text(base_recipe_path.read_text().replace("scheme = true\nsamples = true", "scheme = false"))
	recipe = load(path)
	assert "afterglow-sounds" not in settings.settings_files(recipe)
	assert image._sound_files(recipe) == {}


def test_the_compact_trim_keeps_media_player_and_sound_recorder():
	from reactos_liminal import trim

	removed = {entry.path for entry in trim.build_profile("base").entries}
	assert "ReactOS/system32/mplay32.exe" not in removed and "ReactOS/system32/sndrec32.exe" not in removed
	assert not any("Multimedia Player" in path or "Sound Recorder" in path for path in removed)
