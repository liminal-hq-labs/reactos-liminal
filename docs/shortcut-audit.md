# Shortcut and registry audit

`rl audit IMAGE` lists what a built image launches and whether the file is on its disk. It reads the FAT32 partition through mtools and the registry hives in memory; it changes nothing and needs no guest. `--out FILE` writes the Markdown report, and the exit status is 1 when a dead entry fails the audit.

## What it checks

| Kind | Where it comes from | Fails the audit |
|---|---|---|
| shortcut | every `.lnk` under a `Start Menu`, `Desktop` or `Quick Launch` folder: the file its link information names (an icon file that is missing is listed apart) | yes |
| shortcut (elsewhere) | any other `.lnk`, such as the ones WineVDM keeps in `Program Files/otvdm` | only with `--strict` |
| run | `Run`, `RunOnce`, `RunServices` and `RunServicesOnce` in the machine, default-user and each profile's hive | yes |
| winlogon | the shell, the console shell, the GINA, `Userinit` and the notification DLLs | yes |
| applet | `Control Panel\Cpls` | yes |
| app path | `App Paths` | only with `--strict` |
| uninstall | the uninstall string and display icon of each `Uninstall` key | only with `--strict` |
| association | the command of each verb of each file type and program in `Classes` (`%1` stands for the file the user opens and is not checked) | only with `--strict` |
| font | each entry of the font list, against `ReactOS/Fonts` | only with `--strict` |
| desktop.ini | `IconFile`, `IconResource` and `LocalizedResourceName` | only with `--strict` |

A path is resolved as the guest would: `%SystemRoot%`, `%SystemDrive%`, `%ProgramFiles%` and the like are expanded, case is ignored as FAT does, a bare name is looked for in `system32` and the Windows folder, and anything on another drive, a URL or a variable that is not fixed (`%USERPROFILE%`) is `unchecked`. A link that holds only an item ID list names no path and is `unchecked` too.

## The result

Run on the images built from Afterglow `68d755c8`:

- The **full image** has no dead entry. Its two missing icon files are WineVDM's own installer shortcuts (`install.lnk` and `install (no console).lnk` in `Program Files/otvdm`), whose icon is `C:\Windows\System32\msiexec.exe`; they are not in a menu.
- The **compact image** had 39 dead shortcuts, in `Default User`, `NetworkService` and `Administrator`: Calculator, WordPad, Paint, Character Map, ReactX Diagnostic, SnapShot, Virtual CDRom Control Panel, Magnify, On-Screen Keyboard, Multimedia Player, Sound Recorder, Remote Desktop Connection and the three games, plus the empty Games and Communications folders. The trim now removes them ([trim.md](trim.md#shortcuts-of-removed-programs)), and the Start menu lists only programs the disk holds. It still has 43 dead registry entries for the programs it removed: three App Paths, 14 file-type commands and the 26 font entries of the fonts it removes. They launch nothing a user sees, so they are reported and not fixed (RL-62).

## Full image

272 entries on a disk of 1700 files: **261 ok**, **0 dead**, 2 with a missing icon file, 9 unchecked.

### Dead entries

None.

### Missing icon files

| Kind | Where | Target | Note |
|---|---|---|---|
| shortcut (elsewhere) | `Program Files/otvdm/install (no console).lnk` | `C:\Windows\System32\msiexec.exe` | the icon file |
| shortcut (elsewhere) | `Program Files/otvdm/install.lnk` | `C:\Windows\System32\msiexec.exe` | the icon file |

### Entries checked, by kind

| Kind | Ok | Dead | Icon missing | Unchecked |
|---|---:|---:|---:|---:|
| app path | 4 | 0 | 0 | 0 |
| applet | 1 | 0 | 0 | 0 |
| association | 84 | 0 | 0 | 7 |
| font | 52 | 0 | 0 | 0 |
| run | 5 | 0 | 0 | 0 |
| shortcut | 104 | 0 | 0 | 0 |
| shortcut (elsewhere) | 0 | 0 | 2 | 2 |
| uninstall | 2 | 0 | 0 | 0 |
| winlogon | 9 | 0 | 0 | 0 |

## Compact image

226 entries on a disk of 1480 files: **172 ok**, **43 dead**, 2 with a missing icon file, 9 unchecked.

### Dead entries

| Kind | Where | Target | Note |
|---|---|---|---|
| app path | `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\pbrush.exe` | `%SystemRoot%\system32\mspaint.exe` |  |
| app path | `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\wordpad.exe` | `%SystemRoot%\system32\wordpad.exe` |  |
| app path | `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\write.exe` | `%SystemRoot%\system32\wordpad.exe` |  |
| association | `HKLM\SOFTWARE\Classes\Applications\mplay32.exe\shell\open\command` | `%SystemRoot%\system32\mplay32.exe` |  |
| association | `HKLM\SOFTWARE\Classes\Applications\mspaint.exe\shell\open\command` | `%SystemRoot%\system32\mspaint.exe` |  |
| association | `HKLM\SOFTWARE\Classes\Applications\wordpad.exe\shell\open\command` | `%SystemRoot%\system32\wordpad.exe` |  |
| association | `HKLM\SOFTWARE\Classes\AVIFile\shell\open\command` | `%SystemRoot%\system32\mplay32.exe` |  |
| association | `HKLM\SOFTWARE\Classes\bmpfile\shell\edit\command` | `%SystemRoot%\system32\mspaint.exe` |  |
| association | `HKLM\SOFTWARE\Classes\CDAFile\shell\open\command` | `%SystemRoot%\system32\mplay32.exe` |  |
| association | `HKLM\SOFTWARE\Classes\jpegfile\shell\edit\command` | `%SystemRoot%\system32\mspaint.exe` |  |
| association | `HKLM\SOFTWARE\Classes\MIDFile\shell\open\command` | `%SystemRoot%\system32\mplay32.exe` |  |
| association | `HKLM\SOFTWARE\Classes\pngfile\shell\edit\command` | `%SystemRoot%\system32\mspaint.exe` |  |
| association | `HKLM\SOFTWARE\Classes\rdpfile\shell\open\command` | `%SystemRoot%\system32\mstsc.exe` |  |
| association | `HKLM\SOFTWARE\Classes\rtffile\shell\open\command` | `%SystemRoot%\system32\wordpad.exe` |  |
| association | `HKLM\SOFTWARE\Classes\rtffile\shell\print\command` | `%SystemRoot%\system32\wordpad.exe` |  |
| association | `HKLM\SOFTWARE\Classes\SoundRec\shell\open\command` | `%SystemRoot%\system32\mplay32.exe` |  |
| association | `HKLM\SOFTWARE\Classes\TIFImage.Document\shell\edit\command` | `%SystemRoot%\system32\mspaint.exe` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Droid Sans Fallback (TrueType)` | `DroidSansFallback.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Arial Black (TrueType)` | `ariblk.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Comic Sans MS (TrueType)` | `comic.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Comic Sans MS Bold (TrueType)` | `comicbd.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Franklin Gothic Medium Medium (TrueType)` | `framd.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Franklin Gothic Medium Medium Italic (TrueType)` | `framdit.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\FreeSans Bold (TrueType)` | `FreeSansBold.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\FreeSans Bold Oblique (TrueType)` | `FreeSansBoldOblique.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\FreeSans Oblique (TrueType)` | `FreeSansOblique.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Georgia Book (TrueType)` | `georgia.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Georgia Bold (TrueType)` | `georgiab.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Georgia Italic (TrueType)` | `georgiai.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Georgia Bold Italic (TrueType)` | `georgiaz.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Lucida Console Book (TrueType)` | `lucon.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Palatino Linotype (TrueType)` | `pala.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Palatino Linotype Bold (TrueType)` | `palab.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Palatino Linotype Bold Italic (TrueType)` | `palabi.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Palatino Linotype Italic (TrueType)` | `palai.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Trebuchet MS (TrueType)` | `trebuc.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Trebuchet MS Bold (TrueType)` | `trebucbd.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Trebuchet MS Bold Italic (TrueType)` | `trebucbi.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Trebuchet MS Italic (TrueType)` | `trebucit.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Verdana Bold (TrueType)` | `verdanab.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Verdana Bold Italic (TrueType)` | `verdanaz.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Verdana Italic (TrueType)` | `verdanai.ttf` |  |
| font | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts\Verdana (TrueType)` | `verdana.ttf` |  |

### Missing icon files

| Kind | Where | Target | Note |
|---|---|---|---|
| shortcut (elsewhere) | `Program Files/otvdm/install (no console).lnk` | `C:\Windows\System32\msiexec.exe` | the icon file |
| shortcut (elsewhere) | `Program Files/otvdm/install.lnk` | `C:\Windows\System32\msiexec.exe` | the icon file |

### Entries checked, by kind

| Kind | Ok | Dead | Icon missing | Unchecked |
|---|---:|---:|---:|---:|
| app path | 1 | 3 | 0 | 0 |
| applet | 1 | 0 | 0 | 0 |
| association | 70 | 14 | 0 | 7 |
| font | 26 | 26 | 0 | 0 |
| run | 5 | 0 | 0 | 0 |
| shortcut | 58 | 0 | 0 | 0 |
| shortcut (elsewhere) | 0 | 0 | 2 | 2 |
| uninstall | 2 | 0 | 0 | 0 |
| winlogon | 9 | 0 | 0 | 0 |
