# Pre-installed AC'97 driver

`guest/reg/ac97-preinstall.reg` (the recipe name `ac97-preinstall`) writes what ReactOS's own plug and play writes for every device the Quill demo's emulator (v86) has and the install's QEMU machine did not, including its AC'97 sound card (8086:2415), so the machine starts with its devices and the card's driver already installed. `guest/reg/ac97-volume-control.reg` (`ac97-volume-control`) makes Volume Control show the card's master line. A recipe opts in by listing the names in `settings.reg_files`; the Quill demo does.

## Why

ReactOS 0.4.16 has the driver (`ac97.sys`, `ac97.inf`, the `wdmaud`, `sysaudio` and `kmixer` audio stack) in the system. The image is installed in QEMU, whose hardware is not v86's: the disk and CD controllers, the video adapter (another revision and subsystem), the network card, the PCI bus (so every instance id differs: `3&7980b9c0` on v86, `3&609b8881` on QEMU), the ACPI devices and the sound card are all new to ReactOS at v86's first boot. Its plug and play installs each of them one after another, and the sound card is the last, so the card's registers stay at their reset values for 30 to 60 seconds after the desktop appears. The browser machine's disk is not kept, so this is repeated at every cold boot and after every Reset. Measured in the page harness, cold boot: the desktop at 13 to 17 s, the card first touched by the driver 46 to 58 s after the desktop; after a Reset, 31 s after the desktop.

The install does not need the card: pre-installing only the AC'97 keys (made from a QEMU capture) changed nothing, because ReactOS looked for them under QEMU's instance ids and found none. The file has to describe v86's hardware as v86 reports it.

## What the file holds

The registry keys the first v86 boot adds or changes, from an export of `HKLM\SYSTEM\ControlSet001` and one of `HKLM\SOFTWARE` taken before and after, less what the system rewrites at each start:

| Keys | What |
|---|---|
| `SYSTEM\…\Enum\PCI`, `Enum\ACPI`, `Enum\IDE`, `Enum\PCIIDE`, `Enum\DISPLAY`, `Enum\Root\System`, `Enum\SW` | Each device ReactOS installed: hardware and compatible ids, `Service`, `Driver`, `Class`, `ConfigFlags`. The AC'97 card is `PCI\VEN_8086&DEV_2415&SUBSYS_00008086&REV_02\3&7980b9c0&03` |
| `SYSTEM\…\Control\Class\{…}` | The driver entries for the devices (`ac97.sys`, `ac97.inf`, the `wave`, `midi` and `mixer` driver names, the card's own switches) and for the three audio software devices |
| `SYSTEM\…\Services` | The driver services the devices add (`ac97`, `wdmaud`, `sysaudio`, `kmixer`, `ne2000`, parts of `Tcpip`) and the changed values: `AudioSrv` set to start automatically, the load `Tag`s and `Control\GroupOrderList` |
| `SYSTEM\…\Control\DeviceClasses\…\Device Parameters` | The `CLSID` and `FriendlyName` ("AC'97 Sound Card", "AC'97 Mixer") the INF gives each audio interface, once |
| `SYSTEM\…\Control\MediaCategories`, `MediaInterfaces` | The kernel streaming category names |
| `SOFTWARE\…\Drivers32` `wave1`, `Classes\CLSID`, `Classes\Interface` | What winmm reads to find `wdmaud.drv`, and the audio stack's COM classes. Without them the card is bound and set up but Sound and Audio Devices lists "No Devices" and no sound plays |

Left out, because the system writes them at every start from the machine it runs on: resource lists (`LogConf`, `AllocConfig`, `BootConfig`, the `Control` key under each `Enum` entry), the device interface keys themselves (`Control\DeviceClasses`, apart from `Device Parameters`), `ServiceCurrent`, the environment, the profile load times, `Explorer\SessionInfo`, and the one-off `RunOnce` commands of the audio install (they only finish what the file already holds). No file is copied: the driver files are on the ReactOS disk, and the compact trim keeps them.

## Volume Control

ReactOS's Volume Control (`sndvol32`) shows only the lines its saved choice (`HKCU\Software\Microsoft\Windows\CurrentVersion\Applets\Volume Control\<mixer name>\<destination>`, value `LineStates`, a list of 132-byte records: a DWORD of flags, 0 to show and 4 to hide, and the line name as 64 UTF-16 characters) lists as shown, and a fresh user has no choice, so its window opens empty although the card has the master line and seven more. `ac97-volume-control.reg` writes the choice for the mixer named "AC'97 Sound Card": the master line (destination `Volume Control`) on the Playback side, and the Microphone on the Recording side. The seven other lines (Aux, Video, CD Audio, Line In, Microphone, Phone Line, PC Speaker) are codec registers of the virtual card that connect to nothing on the playback side; only the master volume and the PCM-out volume reach the speakers, and the microphone is the one record source the card's capture path reads (the record select register's other choices record silence). The Recording destination's name (`Recording Control`) is the standard one and has not been seen on the guest.

## Regenerating

1. Export `HKEY_LOCAL_MACHINE\SYSTEM\ControlSet001` and `HKEY_LOCAL_MACHINE\SOFTWARE` from the image as the install left it: boot it in QEMU and run `regedit /e C:\SYS.REG HKEY_LOCAL_MACHINE\SYSTEM\ControlSet001` (and the same for `SOFTWARE`), then copy the files off the disk with mtools.
2. Do the same in v86 from a cold boot, a couple of minutes after the desktop appears (so every install has finished). The guest has no disk to copy from, so send the file out of its serial port: `cmd /c regedit /e C:\E.REG HKEY_LOCAL_MACHINE\SYSTEM\ControlSet001&type C:\E.REG>COM1`, and collect the bytes of `serial0-output-byte` events in the page.
3. `python3 -I tools/ac97/make-ac97-reg.py BEFORE.reg AFTER.reg guest/reg/ac97-preinstall.reg --software BEFORE_SW.reg AFTER_SW.reg`

The tool keeps only what the second boot added or changed, so another image gives the same file when ReactOS writes the same state, and a reviewer can read the diff against the tool's rules (the runtime exclusions at the top of the tool).

## Audit

`rl audit` reads the SYSTEM hive: each PCI device with a `Service` is a `device` finding that is `ok` when its driver file is on the disk and `dead` when it is not. With `--recipe` naming `ac97-preinstall`, the card (`PCI\VEN_8086&DEV_2415`) must be bound to a service, or the audit fails with a dead `preinstalled device` entry. `CHANGES.txt` lists the device and the services the file adds under "Settings applied".

## What it does not do

It does not change how the card behaves; the Quill demo's card model does. It does not make a different machine faster: a recipe whose emulator reports other hardware needs its own capture. It does not carry a saved machine state: a state saved with the card already set up (the demo's) restores the same registry.
