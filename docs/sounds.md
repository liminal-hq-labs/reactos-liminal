# Sounds

The Afterglow images have a sound scheme, so a fresh image makes sound without anyone setting it up. It is **original**: every file is synthesized by `reactos_liminal/sounds.py` from sine partials, decaying envelopes, a seeded noise source and a few echo taps, with the standard library only. No third-party sample, recording or tool is involved, so the files carry the project's licence, `Apache-2.0 OR MIT`. `rl image` makes them when it builds; no WAV is committed (`scripts/check-no-binaries.sh` stays true), and `pins/afterglow-sounds.json` holds each file's SHA-256, which a test regenerates and compares.

```sh
./rl sounds                    # make the sounds and check them against the pins
./rl sounds --out ~/sounds     # also write the WAV files to a folder, to listen to them
./rl sounds --write-pins       # after a change to the sounds: write the new sums, then check
```

## What is written

The base recipe sets `[sounds] scheme = true` and `samples = true`, so the full, compact and Quill remix images all have both. A recipe that extends it keeps them; `scheme = false` and `samples = false` write nothing.

| File | Length | Rate | Size | What it is |
|---|---|---|---|---|
| `Afterglow_Startup.wav` | 1.90 s | 11,025 Hz | 81.9 KB | A warm D major arpeggio that settles into a soft chord, the start of a session |
| `Afterglow_Logon.wav` | 1.20 s | 11,025 Hz | 51.7 KB | A shorter, brighter A major rise |
| `Afterglow_Logoff.wav` | 1.10 s | 11,025 Hz | 47.4 KB | The logon figure falling |
| `Afterglow_Shutdown.wav` | 1.20 s | 11,025 Hz | 51.7 KB | A slow descent to a low D, the end of a session |
| `Afterglow_Default.wav` | 0.21 s | 11,025 Hz | 9.1 KB | The default beep: one soft tone |
| `Afterglow_Critical_Stop.wav` | 0.67 s | 11,025 Hz | 28.9 KB | Two low, hollow tones falling a minor third, gentle for an error |
| `Afterglow_Exclamation.wav` | 0.52 s | 11,025 Hz | 22.4 KB | A double ping on A |
| `Afterglow_Asterisk.wav` | 0.55 s | 11,025 Hz | 23.7 KB | A single high bell, for information |
| `Afterglow_Question.wav` | 0.50 s | 11,025 Hz | 21.6 KB | Two notes rising and left open |
| `Afterglow_Menu_Command.wav` | 0.04 s | 11,025 Hz | 2.0 KB | A very short, round tick |
| `Afterglow_Start.wav` | 0.07 s | 11,025 Hz | 3.1 KB | A slightly lower, softer tick for the Start menu and navigation |
| `Afterglow_Minimize.wav` | 0.12 s | 11,025 Hz | 5.2 KB | A quick glide down |
| `Afterglow_Maximize.wav` | 0.12 s | 11,025 Hz | 5.2 KB | A quick glide up |
| `Afterglow_Open.wav` | 0.12 s | 11,025 Hz | 5.2 KB | Two tiny rising notes |
| `Afterglow_Close.wav` | 0.12 s | 11,025 Hz | 5.2 KB | Two tiny falling notes |
| `Afterglow_Recycle.wav` | 0.45 s | 11,025 Hz | 19.4 KB | Crumpling paper that ends with a small bell |
| `Dusk melody.wav` | 5.00 s | 8,000 Hz | 156.3 KB | A five-second tune in D major, to play in Media Player |
| `Left and right.wav` | 1.60 s | 8,000 Hz | 50.0 KB | A stereo check: a tone on the left, then a different one on the right, twice |

The first sixteen go in `C:\ReactOS\Media` beside ReactOS's own `ReactOS_*.wav` files, which stay. The last two go in `C:\Sounds`, so Media Player's File, Open has something to play. The desktop has a "Sound test" shortcut that opens Media Player on `Dusk melody.wav`. Together the files are 590 KB (about 350 KB after the zstd compression of the v86 parts), mostly the tune and the stereo check. All are 16-bit stereo.

## The scheme

`settings.reg_files` is not where the scheme is named: `sounds.scheme` adds the generated registry file `afterglow-sounds` to the settings CD, after the named files. It adds the scheme "Afterglow" to `HKCU\AppEvents\Schemes\Names` (ReactOS's "ReactOS Default" and "No sounds" stay in the list of Control Panel, Sounds and Audio Devices, Sounds), selects it, and writes each event's file under `Apps\<app>\<event>\Afterglow` and `\.Current`, which is the value the system plays. "No sounds" in that list silences everything.

| Event | File |
|---|---|
| `SystemStart` (the first logon after a boot) | `Afterglow_Startup.wav` |
| `WindowsLogon` (every later logon) | `Afterglow_Logon.wav` |
| `WindowsLogoff` | `Afterglow_Logoff.wav` |
| `SystemExit` (shutdown) | `Afterglow_Shutdown.wav` |
| `.Default` (default beep) | `Afterglow_Default.wav` |
| `SystemHand` (critical stop), `AppGPFault`, `CriticalBatteryAlarm` | `Afterglow_Critical_Stop.wav` |
| `SystemExclamation`, `DeviceFail`, `LowBatteryAlarm` | `Afterglow_Exclamation.wav` |
| `SystemAsterisk` | `Afterglow_Asterisk.wav` |
| `SystemQuestion` | `Afterglow_Question.wav` |
| `MailBeep`, `SystemNotification`, `PrintComplete` | `Afterglow_Asterisk.wav` |
| `DeviceConnect`, `DeviceDisconnect` | `Afterglow_Open.wav`, `Afterglow_Close.wav` |
| `MenuCommand`, `Navigating` (Explorer) | `Afterglow_Menu_Command.wav`, `Afterglow_Start.wav` |
| `Minimize`, `RestoreDown` / `Maximize`, `RestoreUp` | `Afterglow_Minimize.wav` / `Afterglow_Maximize.wav` |
| `Open`, `Close` | `Afterglow_Open.wav`, `Afterglow_Close.wav` |
| `EmptyRecycleBin` (Explorer) | `Afterglow_Recycle.wav` |
| `MenuPopup` | none, as in Windows |

A saved state (the browser snapshot) does not replay the startup chime: Winlogon plays it once, at the first logon of a boot, and a restored state is already past that.

## Design notes

- **Palette.** A dusk in sound: a warm, glassy pluck (a sine with soft overtones and a slow decay) in D major, with a little detune for shimmer and a short room echo. Nothing is shrill.
- **Direction.** Arriving rises (startup, logon, open, connect, maximize); leaving falls (logoff, shutdown, close, disconnect, minimize). The question is left open, the critical stop is a low falling third, and the exclamation and asterisk are single bright pings.
- **The everyday ticks.** The menu, Start, minimize, maximize, open and close sounds are under 0.12 seconds, because they play all day. Each is a round tick or a short glide, not a beep.
- **Level and format.** Every file is 16-bit stereo PCM, with its highest sample at -6 dBFS and the last six milliseconds faded to zero, so no sound ends on a step. A mono WAV is written as two equal channels: in QEMU's AC'97 card a mono file does not play (Media Player stays at 0:00 and the capture is empty), and stereo plays at 8,000, 11,025, 16,000 and 22,050 Hz. Rates are 11,025 Hz for the system sounds and 8,000 Hz for the tune and the stereo check, which keeps the set under 600 KB.
- **Reproducible.** The noise is a seeded xorshift generator and every other step is arithmetic, so the same code gives the same bytes. `tests/test_sounds.py` checks the pins, the format, the peak, the lengths, the stereo placement, that each event names a file of the set, and the size budget (under 600 KB).

## Media Player and Sound Recorder

`mplay32.exe` (Multimedia Player) and `sndrec32.exe` (Sound Recorder) are in every image. The `base` trim used to remove them; it no longer does, so the compact image and the Quill remix keep them, and ReactOS's own Start menu shortcuts for them stay (Programs, Accessories, Entertainment). Both are written for the sound card: in the Quill remix on QEMU's AC'97 card, Media Player opens `Dusk melody.wav` and plays it to the end, and Sound Recorder opens from its Start menu entry (44.1 kHz, 16 bits, stereo, a 30 second buffer). Recording was not tried: whether a microphone reaches the guest depends on the host.
