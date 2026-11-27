# Plan: icon round 4

The rest of what the Afterglow image still loads in stock ReactOS art after icon round 3, and the patch list for the art drawn for it in Afterglow's icons v6 ([liminal-hq/afterglow-themes#64](https://github.com/liminal-hq/afterglow-themes/pull/64), approved by the owner and merged at `fd023f4f147690b7055004d29fa010cd3dbd08ae`; the art is byte for byte the reviewed branch head `5b4ce87`). Folder Options comes first: the owner found its dialog still stock. The patch is two packages: WP-ICON4-1 writes everything today's patchers accept, and WP-ICON4-2 extends the patchers for the rest. When both land, `SPEC.md`, `docs/icon-survey.md` and `docs/decisions.md` say what was built and this plan is removed.

## Method

- **The survey.** Round 3's survey of every PE file of the stock 0.4.16 i386 install (`plans/icon-round-3.md`): 769 icon groups and 1,184 bitmaps, of which the next tier (84 icons, 27 bitmaps) and the third tier (245 icons, 117 bitmaps) are this round's.
- **What is loaded.** Every resource of the two tiers was looked up in the ReactOS 0.4.16 source (`0.4.16-release`): the code that loads it (`LoadImage`, `LoadIcon`, `LoadBitmap`, `ImageList_*`, `TB_ADDBITMAP`, property sheet watermarks and headers), the dialog templates of `lang/en-US.rc`, and the registry values that name it (`DefaultIcon` in `hivecls.inf`, `hivesft.inf` and the `.rgs` scripts, the class keys' `Icon` in `hivesys.inf` and the INF files, urlmon's zone icons). A resource nothing in 0.4.16 loads is left alone, as the never-loaded P4 rows were in round 3.
- **The files.** Scratch copies of the stock files, copied read-only from the golden disk with mtools (`mcopy`, no mount, nothing written). No VM was booted.
- **Dry runs.** This repository's own `patch_icon_groups` and `stock_group_problem` were run on the scratch copies with Afterglow's rendered `.ico` files at `5b4ce87`, and `patch_dialog_bitmaps.write_bitmaps` with its rendered bitmaps, one resource at a time; every written file parsed again.

## Coverage

| Survey row (round 3) | Icon groups | Bitmaps | Covered this round | Left stock, and why |
|---|---|---|---|---|
| **Folder Options**, General tab (`shell32.dll` 182 to 187) | 6 | 0 | All 6 (new) | — |
| **Folder Options**, View tab (`shell32.dll` 37, a P4 row: the survey missed its dialog template) | 1 | 0 | 1 | — |
| Applications Manager (`rapps.exe`) | 29 | 0 | 28 | 23, the 192 px broken-image picture |
| Device Manager (`setupapi.dll`, `devmgr.dll`) | 37 | 2 | 36 and 2 | `setupapi.dll` 41, blank by design |
| Taskbar and Start Menu Properties previews (`explorer.exe`) | 0 | 25 | 23 | none: 143 and 158 are `afterglow.start`'s already |
| Tray balloons (`comctl32.dll`, three copies) | 12 | 0 | 9 | 501 three times: the drag-list arrow, which no 0.4.16 program uses |
| Registry Editor and Task Manager, round 3's remainder | 5 | 2 | the tray meter (`taskmgr.exe` 153) | `regedit.exe` 102 (12 px), `taskmgr.exe` 150 (the mask); round 3 has the other four groups |
| Control Panel inner pages | 87 | 9 | 45 and 4 | 41 groups no code loads (35 of them `mmsys.cpl`'s numbered icons), `mmsys.cpl` 4624 (72 px), the colour-depth spectra, the time zone map, `appwiz.cpl` 5001 |
| Programs and libraries (the File Types icons among them) | 70 | 74 | 21 and 30 | 49 groups and 42 bitmaps: never loaded, IME, logo, third-party or functional (below); `msgina.dll` 20000 and 20001 are `afterglow.logon`'s already |
| Common dialogs (`comdlg32.dll`, `pifmgr.dll`) | 48 | 1 | 8 | the 76 px collate pictures, `pifmgr.dll` 1 to 39, the Font dialog's type marks |
| Administrative tools | 17 | 10 | 17 and 9 | `frag.exe` 110, never loaded |
| Standard toolbars (`comctl32.dll`, three copies) | 0 | 21 | 18 | `IDT_CHECK` 401 three times, never loaded |
| Tray and hardware | 21 | 2 | 12 | `netshell.dll` 104 and 110 (unused), `msutb.dll` 154 and 155 (placeholders) |
| Printers, drive properties | 2 | 0 | 2 | — |
| **Total** | **335** | **146** | **185 groups and 87 bitmaps** | **146 groups and 55 bitmaps** |

Counts are rows of the survey, one per file, so `comctl32.dll`'s three identical copies count three times: the 185 group rows are 179 resources in `map.json` and the 87 bitmap rows are 75. Two of the groups (`msxml3.dll` 128 and `cleanmgr.exe` 100) and 21 of the bitmap rows (the BI_BITFIELDS strips) need WP-ICON4-2; the rest are written by WP-ICON4-1.

**What stays stock after this round, of everything P1 to P3 holds: 146 icon groups and 55 bitmaps.**

- **Never loaded by 0.4.16 (130 groups, 21 bitmaps).** No code, dialog template or registry value asks for them: `pifmgr.dll` 1 to 39, `rasdlg.dll` (21 and 4), `tapiui.dll` (4 and 2), `modemui.dll` (5), 35 of `mmsys.cpl`'s numbered icons, `ntvdm.exe` 2 to 12, `appwiz.cpl` 1501 to 1504 and 5001, `comctl32.dll` 501 and 401 (three copies each), `vfd.dll` 104 to 106, `msgina.dll` 13 and 110, `netshell.dll` 104 and 110, `powercfg.cpl` 103, `mydocs.dll` 101, `logonui.exe` (winlogon does not run it), `msi.dll` 4097 to 4099, `msutb.dll` 154 and 155, `frag.exe` 110, `zipfldr.dll` 164.
- **Loaded, left by rule (16 groups, 34 bitmaps).** Sizes the render does not make: `regedit.exe` 102 (12 px), `mmsys.cpl` 4624 (72 px), `comdlg32.dll` `PD32_COLLATE` and `PD32_NOCOLLATE` (76 px), `rapps.exe` 23 (192 px). The Korean and Japanese IME art: `indicdll.dll` 10 to 16, `conime.exe` 100 and `imm32.dll`'s 18 soft keyboard bitmaps. The ReactOS logo art: `welcome.exe` 3000 and 101, `logon.scr` 256 and 512. `setupapi.dll` 41 (blank on purpose). The third-party Inno Setup uninstaller of otvdm (`unins000.exe`, one group and two bitmaps). Functional pictures: Display Properties' colour-depth spectra (`desk.cpl` 209 to 211), the time zone map (`timedate.cpl` 115), the Font dialog's type marks (`comdlg32.dll` 38), `cryptui.dll` 200 and 204 (16-colour image lists: the certificate list's marks and the checkboxes), Task Manager's tray mask (`taskmgr.exe` 150), and `fontsub.exe` 2 to 4, three 12 px sort arrows whose loader is not in the local source tree.
- **Elsewhere, unchanged.** The never-loaded P4 rows (187 groups, 18 bitmaps), the full image's trimmed programs (26 groups and 35 bitmaps in `osk.exe`, `mspaint.exe`, `sndrec32.exe`, `mplay32.exe`, `winmine.exe`, the savers and others: the next pass for the full image), the other visual styles' bitmaps (not shown while Afterglow's style is active), and the ReactOS logo art round 3 left out (`user32.dll` 105, `sysdm.cpl` 55 and 56, `userinit.exe` 100 and 101).

The review sheets (stock beside Afterglow per group, the Folder Options dialog first: `before-folder-options.png` and `after-folder-options.png`) are in the owner's `Afterglow/ReactOS/Screenshots/12 Icon round 4`.

## Patch list

Every group row below was dry-run with `patch_icon_groups` and every bitmap row with `write_bitmaps` on the scratch stock copies. "Own ids" are the frame ids the group owns and the patcher writes; "Written" is what it writes into them.

### Folder Options

| File (copies) | Resource | Afterglow | Stock frames | Own ids | Written | Shows |
|---|---|---|---|---|---|---|
| `system32/shell32.dll` | group 182 `IDI_SHELL_SHOW_COMMON_TASKS` | `fo-tasks` (new) | `32@4 32@8 32@32` | 630,632,631 | 48, 32, 16 | Folder Options, General: Show common tasks in folders |
| `system32/shell32.dll` | group 183 `IDI_SHELL_CLASSIC_FOLDERS` | `fo-classic` (new) | `32@4 32@8 32@32` | 633,635,634 | 48, 32, 16 | Folder Options, General: Use Windows classic folders |
| `system32/shell32.dll` | group 184 `IDI_SHELL_OPEN_IN_SOME_WINDOW` | `fo-samewindow` (new) | `32@8 32@32` | 637,636 | 32+16 (fitted) | Folder Options, General: Open each folder in the same window |
| `system32/shell32.dll` | group 185 `IDI_SHELL_OPEN_IN_NEW_WINDOW` | `fo-newwindow` (new) | `32@8 32@32` | 639,638 | 32+16 (fitted) | Folder Options, General: Open each folder in its own window |
| `system32/shell32.dll` | group 186 `IDI_SHELL_SINGLE_CLICK_TO_OPEN` | `fo-singleclick` (new) | `32@8 32@32` | 641,640 | 32+16 (fitted) | Folder Options, General: Single-click to open an item |
| `system32/shell32.dll` | group 187 `IDI_SHELL_DOUBLE_CLICK_TO_OPEN` | `fo-doubleclick` (new) | `32@8 32@32` | 643,642 | 32+16 (fitted) | Folder Options, General: Double-click to open an item |
| `system32/shell32.dll` | group 37 `IDI_SHELL_PROGRAMS_FOLDER2` | `programsfolder` | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | 283,284,285 | 48, 32, 16 | Folder Options, View: the Folder views picture |
| `system32/zipfldr.dll` | group 1 `IDI_ZIPFLDR` | `archive` | `48@24 32@8 16@8 48@32 32@32 16@32` | 4,5,6 | 48, 32, 16 | File Types and Explorer: Compressed (zipped) Folder, .zip (DefaultIcon %MODULE%), and the extraction wizard |
| `system32/url.dll` | group 102 | `html` | `48@8 32@8 16@8 48@32 32@32 16@32` | 4,5,6 | 48, 32, 16 | File Types: Internet Shortcut, .url (url.dll,0), and the http and https protocols |
| `system32/msxml3.dll` | group 128 `IDI_XML_FILE` | `xmlfile` (new) | `48@8 32@8 22@8 16@8 48@32 32@32 22@32 16@32` | — | **refused**: a 22 or 256 px frame | File Types: XML Document, .xml (msxml3.dll,0) |
| `system32/msxml3.dll` | group 129 `IDI_XSL_FILE` | `xmlfile` (new) | `48@8 32@8 24@8 16@8 48@32 32@32 24@32 16@32` | 13,14,16 | 48, 32, 16 | File Types: XSL Stylesheet, .xsl (msxml3.dll,1) |
| `system32/mshta.exe` | group 1 | `html` | `32@32 16@32` | 1,2 | 32+16 (fitted) | File Types: HTML Application, .hta (mshta.exe,-1), and the program |
| `system32/cryptext.dll` | group 1 | `certificate` (new) | `48@32` | 1 | 48 (fitted) | File Types: Security Certificate, .cer and .crt (cryptext.dll,-1) |
| `system32/clipbrd.exe` | group 101 `CLPFILE_ICON` | `paste` | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | 16,17,18 | 48, 32, 16 | File Types: Clipboard file, .clp (clipbrd.exe,1) |
| `system32/eventvwr.exe` | group 11 `IDI_EVENTLOG` | `eventlog` (new) | `48@8 32@8 16@8 48@32 32@32 16@32` | 10,11,12 | 48, 32, 16 | File Types: Event log, .evt (eventvwr.exe,1), and every log in Event Viewer's tree |
| `system32/msiexec.exe` | group 1 | `wusa` | `48@8 32@8 16@8 48@32 32@32 16@32` | 4,5,6 | 48, 32, 16 | File Types: Windows Installer package and patch, .msi and .msp (msiexec.exe), and the program |
| `system32/themeui.dll` | group 1 | `display` | `16@8 32@8 48@8 16@8 32@32 48@32` | 6,5,1 | 48, 32, 16 | File Types: Theme and Visual Style, .theme and .msstyles (themeui.dll,-1) |

### Device Manager

| File (copies) | Resource | Afterglow | Stock frames | Own ids | Written | Shows |
|---|---|---|---|---|---|---|
| `system32/setupapi.dll` | group 1 `IDI_SETUPAPI_DISP_ADAPT` | `monitor` | `48@8 32@8 24@8 16@8 48@32 32@32 24@32 16@32` | 5,6,8 | 48, 32, 16 | Device Manager: Display adapters and Monitors (Icon -1) |
| `system32/setupapi.dll` | group 2 `IDI_SETUPAPI_MOUSE` | `devmouse` (new) | `48@8 32@8 16@8 48@32 32@32 16@32` | 12,13,14 | 48, 32, 16 | Device Manager: Mice and other pointing devices (Icon -2) |
| `system32/setupapi.dll` | group 3 `IDI_SETUPAPI_KEYBOARD` | `kbdlayout` | `48@8 32@8 16@8 48@32 32@32 16@32` | 18,19,20 | 48, 32, 16 | Device Manager: Keyboards (Icon -3) |
| `system32/setupapi.dll` | group 4 `IDI_SETUPAPI_PRINTER` | `printer` (new) | `48@8 32@8 16@8 48@32 32@32 16@32` | 24,25,26 | 48, 32, 16 | setupapi's printer class picture |
| `system32/setupapi.dll` | group 5 `IDI_SETUPAPI_NETCARD` | `devnetcard` (new) | `48@8 32@8 16@8 48@32 32@32 16@32` | 30,31,32 | 48, 32, 16 | Device Manager: Network adapters (Icon -5) |
| `system32/setupapi.dll` | group 6 `IDI_SETUPAPI_NODE` | `lan` | `32@32 32@8 16@32 16@8` | 33,34,35 | 48, 32, 16 | Device Manager and network components: network protocols (Icon -6) |
| `system32/setupapi.dll` | group 7 `IDI_SETUPAPI_COMPUTER` | `trynet` | `48@8 32@8 16@8 48@32 32@32 16@32` | 40,41,42 | 48, 32, 16 | Network components: clients and services (Icon -7) |
| `system32/setupapi.dll` | group 8 `IDI_SETUPAPI_SHCOMPUTER` | `trynet` | `32@8 16@8 32@32 16@32` | 43,45,46 | 48, 32, 16 | setupapi's shared computer picture |
| `system32/setupapi.dll` | group 9 `IDI_SETUPAPI_DRV_CONTROL` | `ntdevice` | `48@8 32@8 16@8 48@32 32@32 16@32` | 50,51,52 | 48, 32, 16 | Device Manager: IDE and floppy controllers (Icon -9) |
| `system32/setupapi.dll` | group 10 `IDI_SETUPAPI_POWER` | `ntdevice` | `32@8 16@8 32@32 16@32` | 53,55,56 | 48, 32, 16 | Device Manager: SCSI and RAID controllers (Icon -10) |
| `system32/setupapi.dll` | group 11 `IDI_SETUPAPI_CARD` | `devcard` (new) | `48@8 32@8 16@8 48@32 32@32 16@32` | 60,61,62 | 48, 32, 16 | setupapi's expansion card picture |
| `system32/setupapi.dll` | group 18 `IDI_SETUPAPI_UNKNOWN` | `devunknown` (new) | `16@8 32@8 48@8 16@32 32@32 48@32` | 68,67,66 | 48, 32, 16 | Device Manager: Other devices, and any class without an icon (UNKNOWN_ICON_INDEX) |
| `system32/setupapi.dll` | group 19 `IDI_SETUPAPI_LEGACY_DRV` | `library` | `32@8 48@8 32@8 16@8 48@32 32@32 16@32` | 73,74,75 | 48, 32, 16 | Device Manager: Non-Plug and Play drivers (Icon -19) |
| `system32/setupapi.dll` | group 20 `IDI_SETUPAPI_USB` | `usb-key` | `48@8 32@8 16@8 48@32 32@32 16@32` | 79,80,81 | 48, 32, 16 | Device Manager: Universal Serial Bus controllers (Icon -20) |
| `system32/setupapi.dll` | group 21 `IDI_SETUPAPI_REM_DRIVE` | `removable` | `32@4 16@4` | 82,83 | 32+16 (fitted) | setupapi's removable drive picture |
| `system32/setupapi.dll` | group 22 `IDI_SETUPAPI_SATELLITE` | `devcard` (new) | `32@4 16@4` | 84,85 | 32+16 (fitted) | setupapi's satellite receiver picture |
| `system32/setupapi.dll` | group 23 `IDI_SETUPAPI_PORTS` | `ntport` | `48@8 32@8 16@8 48@32 32@32 16@32` | 89,90,91 | 48, 32, 16 | Device Manager: Ports (COM and LPT) (Icon -23) |
| `system32/setupapi.dll` | group 24 `IDI_SETUPAPI_HID` | `devmouse` (new) | `48@8 32@8 16@8 48@32 32@32 16@32` | 95,96,97 | 48, 32, 16 | Device Manager: Human Interface Devices (Icon -24) |
| `system32/setupapi.dll` | group 25 `IDI_SETUPAPI_NEEDSNAME1` | `devcard` (new) | `32@4 16@4` | 98,99 | 32+16 (fitted) | setupapi's spare device picture |
| `system32/setupapi.dll` | group 26 `IDI_SETUPAPI_NEEDSNAME2` | `ntport` | `16@8 32@8 16@32 32@32` | 100,103,102 | 48, 32, 16 | setupapi's cable picture |
| `system32/setupapi.dll` | group 27 `IDI_SETUPAPI_MYCOMPUTER` | `mycomputer` | `48@8 32@8 16@8 48@32 32@32 16@32` | 107,108,109 | 48, 32, 16 | Device Manager: Computer, and the HAL (Icon -27) |
| `system32/setupapi.dll` | group 28 `IDI_SETUPAPI_PROCESSOR` | `ntdevice` | `32@8 24@8 16@8 32@8 24@8 16@8 32@32 24@32 16@32` | 110,116,118 | 48, 32, 16 | Device Manager: Processors |
| `system32/setupapi.dll` | group 40 `IDI_SETUPAPI_SIGNED_DRV` | `certificate` (new) | `48@8 32@8 16@8 48@32 32@32 16@32` | 122,123,124 | 48, 32, 16 | setupapi's signed driver picture |
| `system32/setupapi.dll` | group 42 `IDI_SETUPAPI_WARNING` | `warning` | `48@8 32@8 16@8 48@32 32@32 16@32` | 130,131,132 | 48, 32, 16 | setupapi's warning picture |
| `system32/setupapi.dll` | group 43 `IDI_SETUPAPI_DEVICES` | `devcard` (new) | `48@8 32@8 16@8 48@32 32@32 16@32` | 136,137,138 | 48, 32, 16 | setupapi's devices picture |
| `system32/setupapi.dll` | group 50 `IDI_SETUPAPI_FLOPPY` | `floppy` | `48@8 32@8 16@8 48@32 32@32 16@32` | 142,143,144 | 48, 32, 16 | Device Manager: Floppy disk drives (Icon -50) |
| `system32/setupapi.dll` | group 51 `IDI_SETUPAPI_CDROM` | `cd` | `48@8 32@8 16@8 48@32 32@32 16@32` | 148,149,150 | 48, 32, 16 | Device Manager: DVD/CD-ROM drives (Icon -51) |
| `system32/setupapi.dll` | group 52 `IDI_SETUPAPI_NETDRIVE` | `netdrive` | `48@8 32@8 16@8 48@8 32@8 16@8 48@32 32@32 16@32` | 157,158,159 | 48, 32, 16 | setupapi's network drive picture |
| `system32/setupapi.dll` | group 53 `IDI_SETUPAPI_HARDDRIVE` | `hdd` | `48@8 32@8 16@8 48@32 32@32 16@32` | 163,164,165 | 48, 32, 16 | Device Manager: Disk drives and Storage volumes (Icon -53) |
| `system32/setupapi.dll` | group 54 `IDI_SETUPAPI_NEEDSNAME3` | `cd` | `48@8 32@8 16@8 48@32 32@32 16@32` | 169,170,171 | 48, 32, 16 | setupapi's optical drive picture |
| `system32/setupapi.dll` | group 105 `IDI_SETUPAPI_314FLOP` | `floppy` | `48@8 32@8 16@8 48@32 32@32 16@32` | 175,176,177 | 48, 32, 16 | setupapi's 3.5 in floppy picture |
| `system32/setupapi.dll` | group 159 `IDI_SETUPAPI_CHIP` | `ram-module` | `16@8 32@8 16@32 32@32` | 178,181,180 | 48, 32, 16 | setupapi's chip picture |
| `system32/setupapi.dll` | group 161 `IDI_SETUPAPI_ERROR` | `error` | `32@8 32@32` | 183,182 | 32+16 (fitted) | setupapi's error picture |
| `system32/setupapi.dll` | group 500 `IDI_SETUPAPI_WARN_OVERLAY` | `ovl-warning` (new) | `32@8 16@8 32@32 16@32` | 184,186,187 | 48, 32, 16 | Device Manager: the overlay on a device with a problem (overlay 1) |
| `system32/setupapi.dll` | group 501 `IDI_SETUPAPI_ERR_OVERLAY` | `ovl-error` (new) | `32@8 16@8 32@32 16@32` | 188,190,191 | 48, 32, 16 | Device Manager: the overlay on a disabled device (overlay 2) |
| `system32/setupapi.dll` | group 502 `IDI_SETUPAPI_INFO_OVERLAY` | `ovl-info` (new) | `32@8 16@8 32@32 16@32` | 192,194,195 | 48, 32, 16 | Device Manager: the overlay on a device with a note (overlay 3) |
| `system32/deskadp.dll` | group 209 `IDC_DESK_ADAPTER` | `devdisplay` (new) | `32@8 32@32` | 2,1 | 32+16 (fitted) | Display Properties, Settings, Advanced: the Adapter tab |
| `system32/deskmon.dll` | group 208 `IDC_MONITORICO` | `monitor` | `32@8 32@32` | 2,1 | 32+16 (fitted) | Display Properties, Settings, Advanced: the Monitor tab |

### Applications Manager

| File (copies) | Resource | Afterglow | Stock frames | Own ids | Written | Shows |
|---|---|---|---|---|---|---|
| `system32/rapps.exe` | group 11 `IDI_EXIT` | `logoff` | `24@8` | 13 | 32 (fitted) | Applications Manager toolbar: Exit |
| `system32/rapps.exe` | group 12 `IDI_INSTALL` | `install` (new) | `24@8 24@32` | 14,15 | 32+16 (fitted) | Applications Manager toolbar: Install |
| `system32/rapps.exe` | group 13 `IDI_UNINSTALL` | `uninstall` (new) | `24@8 24@32` | 16,17 | 32+16 (fitted) | Applications Manager toolbar: Uninstall |
| `system32/rapps.exe` | group 14 `IDI_SETTINGS` | `settings` | `24@8 24@32` | 18,19 | 32+16 (fitted) | Applications Manager toolbar: Settings |
| `system32/rapps.exe` | group 15 `IDI_MODIFY` | `properties` | `24@8 24@32` | 20,21 | 32+16 (fitted) | Applications Manager toolbar: Modify |
| `system32/rapps.exe` | group 16 `IDI_REFRESH` | `refresh` (new) | `24@8 24@32` | 22,23 | 32+16 (fitted) | Applications Manager toolbar: Refresh |
| `system32/rapps.exe` | group 17 `IDI_APPS` | `programs` | `24@8 24@32` | 24,25 | 32+16 (fitted) | Applications Manager tree: Applications |
| `system32/rapps.exe` | group 18 `IDI_APPUPD` | `wusa` | `24@8 24@32` | 26,27 | 32+16 (fitted) | Applications Manager tree: Updates |
| `system32/rapps.exe` | group 19 `IDI_CATEGORY` | `folder` | `24@8 24@32` | 28,29 | 32+16 (fitted) | Applications Manager tree: Installed and Available for installation |
| `system32/rapps.exe` | group 20 `IDI_UPDATE_DB` | `refresh` (new) | `24@8 24@32` | 30,31 | 32+16 (fitted) | Applications Manager toolbar: Update database |
| `system32/rapps.exe` | group 21 `IDI_CHECK_ALL` | `check` (new) | `24@8 24@32` | 32,33 | 32+16 (fitted) | Applications Manager toolbar: Select all |
| `system32/rapps.exe` | group 22 `IDI_SELECTEDFORINST` | `star` | `24@8 24@32` | 34,35 | 32+16 (fitted) | Applications Manager tree: Selected for installation |
| `system32/rapps.exe` | group 50 `IDI_CAT_AUDIO` | `audio` | `24@8 24@32` | 37,38 | 32+16 (fitted) | Applications Manager category: Audio |
| `system32/rapps.exe` | group 51 `IDI_CAT_DEVEL` | `console-app` | `24@8 24@32` | 39,40 | 32+16 (fitted) | Applications Manager category: Development |
| `system32/rapps.exe` | group 52 `IDI_CAT_DRIVERS` | `devcard` (new) | `24@8 24@32` | 41,42 | 32+16 (fitted) | Applications Manager category: Drivers |
| `system32/rapps.exe` | group 53 `IDI_CAT_EDU` | `readme` | `24@8 24@32` | 43,44 | 32+16 (fitted) | Applications Manager category: Education |
| `system32/rapps.exe` | group 54 `IDI_CAT_ENGINEER` | `settings` | `24@8 24@32` | 45,46 | 32+16 (fitted) | Applications Manager category: Engineering |
| `system32/rapps.exe` | group 55 `IDI_CAT_FINANCE` | `calc` | `24@8 24@32` | 47,48 | 32+16 (fitted) | Applications Manager category: Finance |
| `system32/rapps.exe` | group 56 `IDI_CAT_GAMES` | `sol` | `24@8 24@32` | 49,50 | 32+16 (fitted) | Applications Manager category: Games and Fun |
| `system32/rapps.exe` | group 57 `IDI_CAT_GRAPHICS` | `paint` | `24@8 24@32` | 51,52 | 32+16 (fitted) | Applications Manager category: Graphics |
| `system32/rapps.exe` | group 58 `IDI_CAT_INTERNET` | `browser` | `24@8 24@32` | 53,54 | 32+16 (fitted) | Applications Manager category: Internet and Network |
| `system32/rapps.exe` | group 59 `IDI_CAT_LIBS` | `library` | `24@8 24@32` | 55,56 | 32+16 (fitted) | Applications Manager category: Libraries |
| `system32/rapps.exe` | group 60 `IDI_CAT_OFFICE` | `doc` | `24@8 24@32` | 57,58 | 32+16 (fitted) | Applications Manager category: Office |
| `system32/rapps.exe` | group 61 `IDI_CAT_OTHER` | `appmanager` | `24@8 24@32` | 59,60 | 32+16 (fitted) | Applications Manager category: Other |
| `system32/rapps.exe` | group 62 `IDI_CAT_SCIENCE` | `flask` (new) | `24@8 24@32` | 61,62 | 32+16 (fitted) | Applications Manager category: Science |
| `system32/rapps.exe` | group 63 `IDI_CAT_TOOLS` | `admintools` | `24@8 24@32` | 63,64 | 32+16 (fitted) | Applications Manager category: Tools |
| `system32/rapps.exe` | group 64 `IDI_CAT_VIDEO` | `video` | `24@8 24@32` | 65,66 | 32+16 (fitted) | Applications Manager category: Video |
| `system32/rapps.exe` | group 65 `IDI_CAT_THEMES` | `display` | `24@32` | 67 | 32 (fitted) | Applications Manager category: Themes |

### Tray balloons

| File (copies) | Resource | Afterglow | Stock frames | Own ids | Written | Shows |
|---|---|---|---|---|---|---|
| `system32/comctl32.dll (×3)` | group 22 `IDI_TT_INFO_SM` | `info` | `16@32 16@8 16@4` | 2,3,4 | 48, 32, 16 | Balloon tips: information |
| `system32/comctl32.dll (×3)` | group 25 `IDI_TT_WARN_SM` | `warning` | `16@32 16@8 16@4` | 5,6,7 | 48, 32, 16 | Balloon tips: warning |
| `system32/comctl32.dll (×3)` | group 28 `IDI_TT_ERROR_SM` | `error` | `16@32 16@8 16@4` | 8,9,10 | 48, 32, 16 | Balloon tips: error |

### Mouse Keys

| File (copies) | Resource | Afterglow | Stock frames | Own ids | Written | Shows |
|---|---|---|---|---|---|---|
| `system32/stobject.dll` | group 440 `IDI_MOUSE_DISABLED` | `mk-off` (new) | `16@8` | 71 | 16 (fitted) | Mouse Keys tray icon: Mouse Keys off |
| `system32/stobject.dll` | group 441 `IDI_MOUSE_NOBTN` | `mk-none` (new) | `16@8` | 72 | 16 (fitted) | Mouse Keys tray icon: no button selected |
| `system32/stobject.dll` | group 442 `IDI_MOUSE_L_ACTIVE` | `mk-l` (new) | `16@8` | 73 | 16 (fitted) | Mouse Keys tray icon: left button selected |
| `system32/stobject.dll` | group 443 `IDI_MOUSE_L_DOWN` | `mk-l-down` (new) | `16@8` | 74 | 16 (fitted) | Mouse Keys tray icon: left button held |
| `system32/stobject.dll` | group 444 `IDI_MOUSE_R_ACTIVE` | `mk-r` (new) | `16@8` | 75 | 16 (fitted) | Mouse Keys tray icon: right button selected |
| `system32/stobject.dll` | group 445 `IDI_MOUSE_R_DOWN` | `mk-r-down` (new) | `16@8` | 76 | 16 (fitted) | Mouse Keys tray icon: right button held |
| `system32/stobject.dll` | group 446 `IDI_MOUSE_LR_ACTIVE` | `mk-lr` (new) | `16@8` | 77 | 16 (fitted) | Mouse Keys tray icon: both buttons selected |
| `system32/stobject.dll` | group 447 `IDI_MOUSE_LR_DOWN` | `mk-lr-down` (new) | `16@8` | 78 | 16 (fitted) | Mouse Keys tray icon: both buttons held |
| `system32/stobject.dll` | group 448 `IDI_MOUSE_L_ACTIVE_R_DOWN` | `mk-l-r-down` (new) | `16@8` | 79 | 16 (fitted) | Mouse Keys tray icon: left selected, right held |
| `system32/stobject.dll` | group 449 `IDI_MOUSE_R_ACTIVE_L_DOWN` | `mk-r-l-down` (new) | `16@8` | 80 | 16 (fitted) | Mouse Keys tray icon: right selected, left held |

### Control Panel inner pages

| File (copies) | Resource | Afterglow | Stock frames | Own ids | Written | Shows |
|---|---|---|---|---|---|---|
| `system32/mmsys.cpl` | group 3005 `IDI_PLAY_ICON` | `play` (new) | `32@1` | 145 | 32 (fitted) | Sounds and Audio, Sounds: the play button |
| `system32/mmsys.cpl` | group 3006 `IDI_STOP_ICON` | `stopsq` (new) | `32@1` | 146 | 32 (fitted) | Sounds and Audio, Sounds: the stop button |
| `system32/mmsys.cpl` | group 4366 `IDI_SOUND_SECTION` | `sound` | `48@8 32@8 16@8 48@32 32@32 16@32` | 59,60,61 | 48, 32, 16 | Sounds and Audio, Sounds: a program's events |
| `system32/mmsys.cpl` | group 4367 `IDI_SOUND_ASSIGNED` | `volume` | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | 68,69,70 | 48, 32, 16 | Sounds and Audio, Sounds: an event with a sound |
| `system32/mmsys.cpl` | group 4390 `IDI_NO_HW` | `volumemute` | `32@8 32@32` | 133,132 | 32+16 (fitted) | Sounds and Audio, Volume: no audio device |
| `system32/mmsys.cpl` | group 4393 `IDI_MUTED_ICON` | `volumemute` | `32@8 32@32` | 135,134 | 32+16 (fitted) | Sounds and Audio, Volume: muted |
| `system32/powercfg.cpl` | group 101 `IDI_DC` | `battery5` | `32@8 32@24 32@32` | 13,15,14 | 48, 32, 16 | Power Options: running on batteries |
| `system32/powercfg.cpl` | group 102 `IDI_ACDC` | `acpower` | `32@8 32@24 32@32` | 10,12,11 | 48, 32, 16 | Power Options: plugged in |
| `system32/powercfg.cpl` | group 104 `IDI_HIBERNATE` | `sleep` (new) | `32@8 32@24 32@32` | 19,21,20 | 48, 32, 16 | Power Options, Hibernate |
| `system32/powercfg.cpl` | group 110 `IDI_BAT_CHARGE_CRIT` | `charging0` | `32@8 32@24 32@32` | 22,24,23 | 48, 32, 16 | Power Meter: charging, critical |
| `system32/powercfg.cpl` | group 111 `IDI_BAT_CHARGE_LOW` | `charging1` | `32@8 32@24 32@32` | 25,27,26 | 48, 32, 16 | Power Meter: charging, low |
| `system32/powercfg.cpl` | group 112 `IDI_BAT_CHARGE_HALF` | `charging2` | `32@8 32@24 32@32` | 28,30,29 | 48, 32, 16 | Power Meter: charging, half |
| `system32/powercfg.cpl` | group 113 `IDI_BAT_CHARGE_HIGH` | `charging3` | `32@8 32@24 32@32` | 31,33,32 | 48, 32, 16 | Power Meter: charging, high |
| `system32/powercfg.cpl` | group 114 `IDI_BAT_CHARGE_FULL` | `charging4` | `32@8 32@24 32@32` | 34,36,35 | 48, 32, 16 | Power Meter: charging, full |
| `system32/powercfg.cpl` | group 115 `IDI_BAT_DISCHRG_CRIT` | `battery0` | `32@8 32@24 32@32` | 37,39,38 | 48, 32, 16 | Power Meter: on battery, critical |
| `system32/powercfg.cpl` | group 116 `IDI_BAT_DISCHRG_LOW` | `battery1` | `32@8 32@24 32@32` | 40,42,41 | 48, 32, 16 | Power Meter: on battery, low |
| `system32/powercfg.cpl` | group 117 `IDI_BAT_DISCHRG_HALF` | `battery3` | `32@8 32@24 32@32` | 43,45,44 | 48, 32, 16 | Power Meter: on battery, half |
| `system32/powercfg.cpl` | group 118 `IDI_BAT_DISCHRG_HIGH` | `battery4` | `32@8 32@24 32@32` | 46,48,47 | 48, 32, 16 | Power Meter: on battery, high |
| `system32/powercfg.cpl` | group 119 `IDI_BAT_DISCHRG_FULL` | `battery5` | `32@8 32@24 32@32` | 49,51,50 | 48, 32, 16 | Power Meter: on battery, full |
| `system32/powercfg.cpl` | group 120 `IDI_BAT_UNKNOWN` | `batteryerror` | `32@8 32@24 32@32` | 52,54,53 | 48, 32, 16 | Power Meter: battery state unknown |
| `system32/powercfg.cpl` | group 121 `IDI_BAT_NONE` | `acpower` | `32@8 32@24 32@32` | 55,57,56 | 48, 32, 16 | Power Meter: no battery |
| `system32/batt.dll` | group 2 `IDI_BATTERY` | `battery5` | `32@32 16@32` | 1,2 | 32+16 (fitted) | Device Manager: Batteries (battery.inf Icon 2) |
| `system32/appwiz.cpl` | group 1505 `IDI_APPINETICO` | `program` | `32@32 32@8 16@8 16@32` | 18,19,21 | 48, 32, 16 | Create Shortcut wizard |
| `system32/hdwwiz.cpl` | group 102 `IDI_WARNINGICON` | `warning` | `32@8 32@32` | 11,10 | 32+16 (fitted) | Add Hardware wizard: a problem |
| `system32/hdwwiz.cpl` | group 103 `IDI_SEARCHICON` | `search` | `32@8 32@32` | 13,12 | 32+16 (fitted) | Add Hardware wizard: searching |
| `system32/inetcpl.cpl` | group 1313 `ICO_INTERNET` | `browser` | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | 16,17,18 | 48, 32, 16 | Internet Options, Security: the Internet zone (urlmon ZICON_INTERNET) |
| `system32/inetcpl.cpl` | group 1314 `ICO_CERTIFICATES` | `certificate` (new) | `16@8 32@8 16@32 32@32` | 19,22,21 | 48, 32, 16 | Internet Options, Content: Certificates |
| `system32/inetcpl.cpl` | group 1315 `ICO_HISTORY` | `recent` | `32@8 32@32` | 26,25 | 32+16 (fitted) | Internet Options, General: History |
| `system32/inetcpl.cpl` | group 1316 `ICO_HOME` | `home` (new) | `32@8 32@32` | 30,29 | 32+16 (fitted) | Internet Options, General: Home page |
| `system32/inetcpl.cpl` | group 4480 `ICO_TRUSTED` | `check` (new) | `32@8 32@32` | 28,27 | 32+16 (fitted) | Internet Options, Security: Trusted sites |
| `system32/inetcpl.cpl` | group 4481 `ICO_RESTRICTED` | `error` | `32@8 32@32` | 24,23 | 32+16 (fitted) | Internet Options, Security: Restricted sites |
| `system32/input.dll` | group 1502 `IDI_CPLSYSTEM` | `keyboard` | `48@8 32@8 16@8 48@32 32@32 16@32` | 4,5,6 | 48, 32, 16 | Control Panel: Text Services and Input Languages |
| `system32/input.dll` | group 1503 `IDI_KEYBOARD` | `kbdlayout` | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | 13,14,15 | 48, 32, 16 | Text Services and Input Languages: each installed layout |
| `system32/input.dll` | group 1504 `IDI_DOT` | `dot` (new) | `16@24` | 16 | 16 (fitted) | Text Services and Input Languages: the default layout's mark |
| `system32/mydocs.dll` | group 100 `IDR_MYDOCS` | `mydocs` | `48@4 32@4 16@4 48@32 32@8 16@8 48@24 32@32 16@32` | 4,8,9 | 48, 32, 16 | My Documents drop target (Send To) |
| `system32/netcfgx.dll` | group 100 `IDI_NETWORK` | `lan` | `48@8 32@8 16@8 48@32 32@32 16@32` | 4,5,6 | 48, 32, 16 | TCP/IP properties |
| `system32/netcfgx.dll` | group 101 `IDI_INTERNET` | `browser` | `48@8 32@8 16@8 48@32 32@32 16@32` | 10,11,12 | 48, 32, 16 | TCP/IP, Alternate Configuration, and the network component sheets |
| `system32/netid.dll` | group 101 `IDI_COMPNAME` | `trynet` | `48@8 32@8 24@8 16@8 48@8 32@8 24@8 16@8 48@32 32@32 24@32 16@32` | 9,10,12 | 48, 32, 16 | System Properties, Computer Name |
| `system32/netid.dll` | group 102 `IDI_WARNINGICO` | `warning` | `16@8 16@24 16@32` | 13,14,15 | 48, 32, 16 | System Properties, Computer Name: restart needed |
| `system32/sysdm.cpl` | group 54 `IDI_LICENSE` | `certificate` (new) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | 18,19,20 | 48, 32, 16 | System Properties: the licence dialog |
| `system32/sysdm.cpl` | group 2500 `IDI_UP` | `up` | `32@4` | 21 | 32 (fitted) | Hardware Profiles: move up |
| `system32/sysdm.cpl` | group 2501 `IDI_DOWN` | `down` (new) | `32@4` | 22 | 32 (fitted) | Hardware Profiles: move down |

### Programs and libraries

| File (copies) | Resource | Afterglow | Stock frames | Own ids | Written | Shows |
|---|---|---|---|---|---|---|
| `system32/hhctrl.ocx` | group 100 `IDI_HHICON` | `help` | `48@8 32@8 16@8 48@32 32@32 16@32` | 4,5,6 | 48, 32, 16 | HTML Help window |
| `system32/fontview.exe` | group 800 `IDI_TT` | `font` | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | 7,8,9 | 48, 32, 16 | Font Viewer |
| `system32/gdihv.exe` | group 2000 `IDI_MAIN` | `program` | `48@4 32@4 24@4 16@4 48@8 32@8 24@8 16@8 48@32 32@32 24@32 16@32` | 9,10,12 | 48, 32, 16 | GDI Handle Viewer |
| `system32/iernonce.dll` | group 1 `IDI_ICON` | `wusa` | `48@8 32@8 16@8 48@32 32@32 16@32` | 4,5,6 | 48, 32, 16 | RunOnceEx progress dialog |
| `system32/runonce.exe` | group 10 `IDI_ICON` | `wusa` | `48@8 32@8 16@8 48@32 32@32 16@32` | 4,5,6 | 48, 32, 16 | RunOnce progress dialog |
| `system32/rundll32.exe` | group 100 `IDI_MAIN` | `program` | `48@8 32@8 16@8 48@32 32@32 16@32` | 4,5,6 | 48, 32, 16 | rundll32 |
| `system32/regedt32.exe` | group 101 `IDI_REGEDIT` | `regedit` | `48@8 32@8 16@8 48@32 32@32 16@32 48@24 32@24 16@24` | 4,5,6 | 48, 32, 16 | regedt32 (starts Registry Editor) |
| `system32/ntvdm.exe` | group 1 | `console-app` | `32@4 16@4 32@8 16@8 32@32 16@32` | 1,5,6 | 48, 32, 16 | NTVDM, the DOS console |
| `system32/netplwiz.dll` | group 4400 `IDI_DISCONNECT_NET_DRIVES` | `disconnect` | `48@8 32@8 16@8 48@32 32@32 16@32` | 4,5,6 | 48, 32, 16 | Disconnect Network Drives |
| `system32/msutb.dll` | group 100 `IDI_MAINICON` | `kbdlayout` | `16@32 32@32` | 2,1 | 32+16 (fitted) | Language bar |
| `system32/sndvol32.exe` | group 302 `IDI_SPEAKER_LEFT` | `volume` | `16@4 16@8 16@32` | 10,11,12 | 48, 32, 16 | Volume Control: the left speaker of the balance |
| `system32/sndvol32.exe` | group 303 `IDI_SPEAKER_RIGHT` | `volume` | `16@4 16@8 16@32` | 13,14,15 | 48, 32, 16 | Volume Control: the right speaker of the balance |
| `system32/userenv.dll` | group 1 `IDI_USERENV` | `user` | `48@8 32@8 16@8 48@32 32@32 16@32` | 4,5,6 | 48, 32, 16 | the profile error dialog |
| `system32/winlogon.exe` | group 4 `IDI_WINLOGON` | `shield` | `32@32 32@8 32@4 16@32 16@8 16@4` | 1,2,4 | 48, 32, 16 | Winlogon's dialogs |
| `system32/shell32.dll` | group 17 `IDI_SHELL_PRINTER` | `printer` (new) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | 131,132,133 | 48, 32, 16 | Printers folder: a printer (CPrinterFolder) |
| `system32/shell32.dll` | group 1001 `IDI_SHELL_IDEA` | `info` | `48@32 32@32 16@32 48@8 32@8 16@8 48@4 32@4 16@4` | 1382,1383,1384 | 48, 32, 16 | Drive properties: the tip |

### Administrative tools

| File (copies) | Resource | Afterglow | Stock frames | Own ids | Written | Shows |
|---|---|---|---|---|---|---|
| `system32/certmgr.exe` | group 100 `IDI_CERTMGR` | `certificate` (new) | `16@8 32@8 16@32 32@32` | 1,4,3 | 48, 32, 16 | Certificate Manager |
| `system32/cleanmgr.exe` | group 100 `IDI_CLEANMGR` | `recycle` | `32@4 16@4 48@8 32@8 16@8 256@32 48@32 32@32 16@32` | — | **refused**: a 22 or 256 px frame | Disk Cleanup |
| `system32/frag.exe` | group 114 `IDI_ICON` | `hdd` | `32@4 32@0 48@0 16@0` | 3,1,4 | 48, 32, 16 | Fraginator |
| `system32/eventvwr.exe` | group 12 `IDI_CLOSED_CATEGORY` | `folder` | `16@8 16@32` | 13,14 | 32+16 (fitted) | Event Viewer tree: a closed group |
| `system32/eventvwr.exe` | group 13 `IDI_OPENED_CATEGORY` | `folderopen` | `16@8 16@32` | 15,16 | 32+16 (fitted) | Event Viewer tree: an open group |
| `system32/eventvwr.exe` | group 14 `IDI_INFORMATIONICON` | `info` | `16@32 16@8` | 17,18 | 32+16 (fitted) | Event Viewer list: information |
| `system32/eventvwr.exe` | group 15 `IDI_WARNINGICON` | `warning` | `16@32 16@8` | 19,20 | 32+16 (fitted) | Event Viewer list: warning |
| `system32/eventvwr.exe` | group 16 `IDI_ERRORICON` | `error` | `16@32 16@8` | 21,22 | 32+16 (fitted) | Event Viewer list: error |
| `system32/eventvwr.exe` | group 17 `IDI_AUDITSUCCESSICON` | `key` (new) | `16@8 16@32` | 23,24 | 32+16 (fitted) | Event Viewer list: audit success |
| `system32/eventvwr.exe` | group 18 `IDI_AUDITFAILUREICON` | `shield` | `16@8 16@32` | 25,26 | 32+16 (fitted) | Event Viewer list: audit failure |
| `system32/eventvwr.exe` | group 19 `IDI_NEXT` | `down` (new) | `16@8 16@32` | 27,28 | 32+16 (fitted) | Event Properties: next event |
| `system32/eventvwr.exe` | group 20 `IDI_PREV` | `up` | `16@8 16@32` | 29,30 | 32+16 (fitted) | Event Properties: previous event |
| `system32/eventvwr.exe` | group 21 `IDI_COPY` | `copyclip` | `16@8 16@32` | 31,32 | 32+16 (fitted) | Event Properties: copy |
| `system32/servman.exe` | group 52 `IDI_NODEPENDS` | `info` | `16@4 32@4 16@8 32@8 16@32 32@32` | 10,15,14 | 48, 32, 16 | Service properties, Dependencies: none |
| `system32/servman.exe` | group 53 `IDI_SERVICE` | `settings` | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | 22,23,24 | 48, 32, 16 | Service properties, Dependencies: a service |
| `system32/servman.exe` | group 54 `IDI_DRIVER` | `ntdevice` | `32@4 16@4 32@8 16@8 32@32 16@32` | 25,29,30 | 48, 32, 16 | Service properties, Dependencies: a driver |

### Common dialogs

| File (copies) | Resource | Afterglow | Stock frames | Own ids | Written | Shows |
|---|---|---|---|---|---|---|
| `system32/comdlg32.dll` | group CDROM | `cd` | `16@32 16@8 16@4` | 22,23,24 | 48, 32, 16 | The Windows 3.1 file dialog's drive list: CD drive |
| `system32/comdlg32.dll` | group FLOPPY | `floppy` | `16@32 16@8 16@4` | 19,20,21 | 48, 32, 16 | The Windows 3.1 file dialog's drive list: floppy |
| `system32/comdlg32.dll` | group FOLDER | `folder` | `16@32 16@8 16@4` | 13,14,15 | 48, 32, 16 | The Windows 3.1 file dialog's folder list: a folder |
| `system32/comdlg32.dll` | group FOLDER2 | `folderopen` | `16@32 16@8 16@4` | 16,17,18 | 48, 32, 16 | The Windows 3.1 file dialog's folder list: an open folder |
| `system32/comdlg32.dll` | group HDISK | `hdd` | `16@32 16@8 16@4` | 25,26,27 | 48, 32, 16 | The Windows 3.1 file dialog's drive list: hard disk |
| `system32/comdlg32.dll` | group NETWORK | `netdrive` | `16@32 16@8 16@4` | 28,29,30 | 48, 32, 16 | The Windows 3.1 file dialog's drive list: network drive |
| `system32/comdlg32.dll` | group PD32_PORTRAIT | `portrait` (new) | `32@32 32@8 32@4` | 7,8,9 | 48, 32, 16 | Print and Page Setup: portrait |
| `system32/comdlg32.dll` | group PD32_LANDSCAPE | `landscape` (new) | `32@32 32@8 32@4` | 10,11,12 | 48, 32, 16 | Print and Page Setup: landscape |

### Tray and hardware

| File (copies) | Resource | Afterglow | Stock frames | Own ids | Written | Shows |
|---|---|---|---|---|---|---|
| `system32/hotplug.dll` | group 100 `IDI_HOTPLUG` | `hotplug` | `32@8 32@32 16@8 16@32` | 1,2,4 | 48, 32, 16 | Safely Remove Hardware window |

### Files and their stock SHA-256

| File | Bytes | Stock SHA-256 | Table today | Groups | New section |
|---|---|---|---|---|---|
| `system32/appwiz.cpl` | 422,400 | `e65b88a3e637dbbe9d9739bbb233051e0f83c6c41f0aac2371b1138ab0e60e3b` | cpl-icons | 1 | 15,360 bytes |
| `system32/batt.dll` | 42,496 | `de96b850355f82058a794ba0ab5629f947639b2db19c30980a12f807e191702f` | none (add to `map-icons`) | 1 | 5,632 bytes |
| `system32/certmgr.exe` | 113,664 | `77af451e81e99897983d43029c6f847da8f4fb2e129939966ac3d57192056b69` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/cleanmgr.exe` | 196,096 | `975402b778d5e9d26cd830ce379310b6c9633de8236596c8449c915f31d69d8c` | none (add to `map-icons`) | 1 | — |
| `system32/clipbrd.exe` | 153,600 | `3f07112479426bb55770f88bfe590b198cd1a2030803892e0eab2c6ab3573b8a` | program-icons | 1 | 15,360 bytes |
| `system32/comctl32.dll` | 2,033,152 | `c21b2c46d277371fc23c6138c0ae443e89fe88b9eee36dc8e701f3cfe94ed318` | none (add to `map-icons`) | 3 | 45,568 bytes |
| `system32/comdlg32.dll` | 1,009,664 | `45a54ce402a5a8fbb0f90377463f3a7568b69b42fb482101648ce8be7082a6a2` | none (add to `map-icons`) | 8 | 120,832 bytes |
| `system32/cryptext.dll` | 44,032 | `4189570f65e84619a97c02fd98f14c5c21aae847147d63f5ddd8a22aac8be62f` | none (add to `map-icons`) | 1 | 9,728 bytes |
| `system32/deskadp.dll` | 96,768 | `d506e6c0459faf3d0ce6f6972d806e7ded3a3ad5b38fce3ed31ba6e1fc017a0d` | none (add to `map-icons`) | 1 | 5,632 bytes |
| `system32/deskmon.dll` | 84,480 | `2d55a36abd4efa391a25cf48cf806b5e61bbef493aea074de68f85daf0142f32` | none (add to `map-icons`) | 1 | 5,632 bytes |
| `system32/eventvwr.exe` | 406,528 | `3f0c1bd6542f913991452165c8fed30bd9745f76edcb3d8ad33d4dda0f026c12` | program-icons | 11 | 69,632 bytes |
| `system32/fontview.exe` | 118,272 | `72f2f06c5f6976c2f7a66969bf9c6ce8c4a6d581772480fbea137934f60690d5` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/frag.exe` | 274,944 | `36eb659c01d0fcb054838fd59bb5633154f8dc46f6b5022124b2976fee2b8ca0` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/gdihv.exe` | 70,144 | `ee92f50f0b927b2241b96e2ad85eb8f2079927167ebc10ff7347acabbe8510ba` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/hdwwiz.cpl` | 382,464 | `b3856a9e84b3de1d8059d516bb08879348235c91be616a5c102c187d092dc732` | cpl-icons | 2 | 11,264 bytes |
| `system32/hhctrl.ocx` | 255,488 | `c956f260084f2594281778edf6f2f39d4ccb75a43fea2f8c4f2a20ca21ab3e58` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/hotplug.dll` | 86,528 | `939d7543a68db419fc1602598f1013023745e048e733ed0de83f4f74880d82ba` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/iernonce.dll` | 170,496 | `4708f0c10076caf8a8e89d940404a129043c30b58a000197625833d646ebf430` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/inetcpl.cpl` | 279,552 | `5dafecdd7962ffc1c2d924a4ea3a126f568fd0730656779a1228da575c9a86a5` | cpl-icons | 6 | 52,224 bytes |
| `system32/input.dll` | 377,856 | `a82c2015666584bce7443f1263ab570ef3e4c2514eb0f1662c7b3cee61302ebd` | none (add to `map-icons`) | 3 | 31,744 bytes |
| `system32/mmsys.cpl` | 839,168 | `26b2c616f35dc4118f76e168503208e57a240ad9a31386748f5bf1535150129a` | cpl-icons | 6 | 49,664 bytes |
| `system32/mshta.exe` | 34,304 | `d758e9ab9cc13c2eaa2c821e052bd185c936669f032ca92c71b332505b20eff6` | none (add to `map-icons`) | 1 | 5,632 bytes |
| `system32/msiexec.exe` | 99,840 | `905b62126406ed90d6ffb9e86fb04d11cf68a2df9d1026755c2db82eead8bf53` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/msutb.dll` | 456,704 | `5ab11912dab4244ab57e6940505d5c5e82a819fda026d596ae0a78c889103d8e` | none (add to `map-icons`) | 1 | 5,632 bytes |
| `system32/msxml3.dll` | 3,672,064 | `9736c2aec5e2ed0bf2a874320c6c0ce5718e739eac0ac4e7354841f7c853bd68` | none (add to `map-icons`) | 2 | — |
| `system32/mydocs.dll` | 233,984 | `5f003578ab88f4043cd6ac98cdc789af300cd849a11711444755d271586f6d95` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/netcfgx.dll` | 637,440 | `9e6385bedea8c69d0397e0f585880f3abe0df3e4c7f5e4d2f71aee6f67b7d73f` | none (add to `map-icons`) | 2 | 30,208 bytes |
| `system32/netid.dll` | 249,344 | `065a9f76e246ba6a7bb189442225519edf966f005225d67833357a5dfe7b6d2a` | none (add to `map-icons`) | 2 | 30,208 bytes |
| `system32/netplwiz.dll` | 72,192 | `035cdfb9a7d6bed0ae0036edf89a6adec241d3884ab5b2cfd03035228893e641` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/ntvdm.exe` | 1,808,896 | `1ebb025e9e4df9333c527a8fce8ee5201d1d307ce6f77c44300a6b5ae2575989` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/powercfg.cpl` | 523,776 | `33fada18cdef25c4eeda94df94897a3488466561fcd0b178d38ea64bdadefe67` | cpl-icons | 15 | 226,304 bytes |
| `system32/rapps.exe` | 1,706,496 | `cfa5081f68b60a4fcb11767ae5caa76294a4a80519912c561af5b34e945c8968` | program-icons | 28 | 150,016 bytes |
| `system32/regedt32.exe` | 64,512 | `a93ecd1e067218ec921c973eaa79a3a50b25327a2ab047688c5454862574b6d1` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/rundll32.exe` | 67,584 | `0056d716a0f856285a86098c065ee340179cb89fdcea14882568d5cb8662b4f3` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/runonce.exe` | 63,488 | `b0b19c2e01dc70edf30688bddd380fc9dfbcdc388adcbb9f2df62011da4f69d1` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/servman.exe` | 508,928 | `fedc937af119f17ef243407e02f777f994488bba6dae785610d04f3cf7931668` | program-icons | 3 | 45,568 bytes |
| `system32/setupapi.dll` | 1,466,880 | `458d5da73b3c966ccc9131234b1a0481cd3953138dafc5fb15c034f27ea0f445` | none (add to `map-icons`) | 36 | 504,320 bytes |
| `system32/shell32.dll` | 10,935,296 | `88858710130e8e97eecfc246e61dd1aaf45b410718f4b818be39a9a69a01cf72` | `shell32_icons.json` (the map decides) | 9 | 97,280 bytes |
| `system32/sndvol32.exe` | 262,656 | `22c72feebf88dcdbc2f11054d6add67cd79865c98853bfc4f5db28bea872b8ce` | program-icons | 2 | 30,208 bytes |
| `system32/stobject.dll` | 479,232 | `7c8776d0ca106e67b624a7843f5a57fe62cd5682ab72693d39078a64a68e70f3` | program-icons | 10 | 11,776 bytes |
| `system32/sysdm.cpl` | 998,400 | `d68f02dc31123572208b59a91edfc56bdd51d44fb057075034d8f88dc6d612d2` | cpl-icons | 3 | 24,064 bytes |
| `system32/themeui.dll` | 40,657 | `eee13c1dbbdde51af5b5fffd80bd184412ee65af76a5fc4d8ff85cbe1af78f66` | none (add to `map-icons`) | 1 | 15,663 bytes |
| `system32/url.dll` | 70,656 | `de86f7fe083ec12309996828ad81b49266c0ac9d530e6293e9e7c6e3f0c66f33` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/userenv.dll` | 258,560 | `06d2a7a82e8c947d88cff62759da46e9fd5d1c7b420e85329ec4626fdac6bab7` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/winlogon.exe` | 283,136 | `eb8d0decc975b47f2ac50cba9b23ad86cd619c52de1e5691c225e5badfc988ed` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `system32/zipfldr.dll` | 1,255,936 | `831ac9071cd8637836f3fb127ad0e2a18ea1db8482a41b58fe9364c1639cbb8d` | none (add to `map-icons`) | 1 | 15,360 bytes |
| `winsxs/…5.82.2600.2982/comctl32.dll` | 2,033,152 | `c21b2c46d277371fc23c6138c0ae443e89fe88b9eee36dc8e701f3cfe94ed318` | none (add to `map-icons`) | 3 | 45,568 bytes |
| `winsxs/…6.0.2600.2982/comctl32.dll` | 2,033,152 | `c21b2c46d277371fc23c6138c0ae443e89fe88b9eee36dc8e701f3cfe94ed318` | none (add to `map-icons`) | 3 | 45,568 bytes |

### Bitmaps

| File (copies) | Bitmap | Afterglow | Stock | Art | Written |
|---|---|---|---|---|---|
| `system32/devmgr.dll` | 21 `IDB_ROOT_IMAGE` | `bmp/devmgr-root.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/devmgr.dll` | 22 `IDB_TOOLBAR` | `bmp/devmgr-toolbar.bmp` | 96x16@32 | 32-bit | in place, same length |
| `explorer.exe` | 145 `IDB_TASKBARPROP_AUTOHIDE` | `bmp/tb-autohide.bmp` | 336x35@4 | 24-bit | new section, 35328 bytes |
| `explorer.exe` | 146 `IDB_TASKBARPROP_LOCK_GROUP_QL` | `bmp/tb-lock-group-ql.bmp` | 336x35@24 | 24-bit | in place, same length |
| `explorer.exe` | 147 `IDB_TASKBARPROP_NOLOCK_GROUP_QL` | `bmp/tb-nolock-group-ql.bmp` | 336x35@24 | 24-bit | in place, same length |
| `explorer.exe` | 148 `IDB_TASKBARPROP_LOCK_NOGROUP_QL` | `bmp/tb-lock-nogroup-ql.bmp` | 336x35@24 | 24-bit | in place, same length |
| `explorer.exe` | 149 `IDB_TASKBARPROP_NOLOCK_NOGROUP_QL` | `bmp/tb-nolock-nogroup-ql.bmp` | 336x35@24 | 24-bit | in place, same length |
| `explorer.exe` | 150 `IDB_TASKBARPROP_LOCK_GROUP_NOQL` | `bmp/tb-lock-group-noql.bmp` | 336x35@24 | 24-bit | in place, same length |
| `explorer.exe` | 151 `IDB_TASKBARPROP_NOLOCK_GROUP_NOQL` | `bmp/tb-nolock-group-noql.bmp` | 336x35@24 | 24-bit | in place, same length |
| `explorer.exe` | 152 `IDB_TASKBARPROP_LOCK_NOGROUP_NOQL` | `bmp/tb-lock-nogroup-noql.bmp` | 336x35@24 | 24-bit | in place, same length |
| `explorer.exe` | 153 `IDB_TASKBARPROP_NOLOCK_NOGROUP_NOQL` | `bmp/tb-nolock-nogroup-noql.bmp` | 336x35@24 | 24-bit | in place, same length |
| `explorer.exe` | 154 `IDB_SYSTRAYPROP_SHOW_SECONDS_NODESK` | `bmp/tray-show-seconds-nodesk.bmp` | 336x35@8 | 24-bit | new section, 35328 bytes |
| `explorer.exe` | 155 `IDB_SYSTRAYPROP_HIDE_SECONDS_NODESK` | `bmp/tray-hide-seconds-nodesk.bmp` | 336x35@8 | 24-bit | new section, 35328 bytes |
| `explorer.exe` | 170 `IDB_STARTPREVIEW` | `bmp/start-preview.bmp` | 300x180@8 | 24-bit | new section, 162304 bytes |
| `explorer.exe` | 171 `IDB_STARTPREVIEW_CLASSIC` | `bmp/start-preview-classic.bmp` | 300x180@8 | 24-bit | new section, 162304 bytes |
| `explorer.exe` | 180 `IDB_SYSTRAYPROP_HIDE_CLOCK_NODESK` | `bmp/tray-hide-clock-nodesk.bmp` | 336x35@8 | 24-bit | new section, 35328 bytes |
| `explorer.exe` | 181 `IDB_SYSTRAYPROP_HIDE_NOCLOCK_NODESK` | `bmp/tray-hide-noclock-nodesk.bmp` | 336x35@8 | 24-bit | new section, 35328 bytes |
| `explorer.exe` | 182 `IDB_SYSTRAYPROP_SHOW_CLOCK_NODESK` | `bmp/tray-show-clock-nodesk.bmp` | 336x35@8 | 24-bit | new section, 35328 bytes |
| `explorer.exe` | 183 `IDB_SYSTRAYPROP_SHOW_NOCLOCK_NODESK` | `bmp/tray-show-noclock-nodesk.bmp` | 336x35@8 | 24-bit | new section, 35328 bytes |
| `explorer.exe` | 184 `IDB_SYSTRAYPROP_SHOW_SECONDS_DESK` | `bmp/tray-show-seconds-desk.bmp` | 336x35@8 | 24-bit | new section, 35328 bytes |
| `explorer.exe` | 185 `IDB_SYSTRAYPROP_HIDE_SECONDS_DESK` | `bmp/tray-hide-seconds-desk.bmp` | 336x35@8 | 24-bit | new section, 35328 bytes |
| `explorer.exe` | 186 `IDB_SYSTRAYPROP_HIDE_CLOCK_DESK` | `bmp/tray-hide-clock-desk.bmp` | 336x35@8 | 24-bit | new section, 35328 bytes |
| `explorer.exe` | 187 `IDB_SYSTRAYPROP_HIDE_NOCLOCK_DESK` | `bmp/tray-hide-noclock-desk.bmp` | 336x35@8 | 24-bit | new section, 35328 bytes |
| `explorer.exe` | 188 `IDB_SYSTRAYPROP_SHOW_CLOCK_DESK` | `bmp/tray-show-clock-desk.bmp` | 336x35@8 | 24-bit | new section, 35328 bytes |
| `explorer.exe` | 189 `IDB_SYSTRAYPROP_SHOW_NOCLOCK_DESK` | `bmp/tray-show-noclock-desk.bmp` | 336x35@8 | 24-bit | new section, 35328 bytes |
| `system32/comctl32.dll (×3)` | 120 `IDB_STD_SMALL` | `bmp/std-small.bmp` | 240x16@32 | 32-bit | **refused today**: BI_BITFIELDS stock (108-byte header); goes in a new section once allowed |
| `system32/comctl32.dll (×3)` | 121 `IDB_STD_LARGE` | `bmp/std-large.bmp` | 360x24@32 | 32-bit | **refused today**: BI_BITFIELDS stock (108-byte header); goes in a new section once allowed |
| `system32/comctl32.dll (×3)` | 124 `IDB_VIEW_SMALL` | `bmp/view-small.bmp` | 192x16@32 | 32-bit | **refused today**: BI_BITFIELDS stock (108-byte header); goes in a new section once allowed |
| `system32/comctl32.dll (×3)` | 125 `IDB_VIEW_LARGE` | `bmp/view-large.bmp` | 288x24@32 | 32-bit | **refused today**: BI_BITFIELDS stock (108-byte header); goes in a new section once allowed |
| `system32/comctl32.dll (×3)` | 130 `IDB_HIST_SMALL` | `bmp/hist-small.bmp` | 80x16@32 | 32-bit | **refused today**: BI_BITFIELDS stock (108-byte header); goes in a new section once allowed |
| `system32/comctl32.dll (×3)` | 131 `IDB_HIST_LARGE` | `bmp/hist-large.bmp` | 120x24@32 | 32-bit | **refused today**: BI_BITFIELDS stock (108-byte header); goes in a new section once allowed |
| `system32/hhctrl.ocx` | 1000 `IDB_HHTOOLBAR` | `bmp/hh-toolbar.bmp` | 144x24@32 | 32-bit | **refused today**: BI_BITFIELDS stock (108-byte header); goes in a new section once allowed |
| `system32/hhctrl.ocx` | 1001 `IDB_HHTREEVIEW` | `bmp/hh-tree.bmp` | 48x16@32 | 32-bit | **refused today**: BI_BITFIELDS stock (108-byte header); goes in a new section once allowed |
| `system32/ieframe.dll` | 1400 `IDB_IETOOLBAR` | `bmp/ie-toolbar.bmp` | 192x32@32 | 32-bit | **refused today**: BI_BITFIELDS stock (108-byte header); goes in a new section once allowed |
| `system32/aclui.dll` | 1001 `IDB_USRGRPIMAGES` | `bmp/aclui-principals.bmp` | 48x16@24 | 24-bit | in place, same length |
| `system32/cryptui.dll` | 201 `IDB_CERT` | `bmp/cert.bmp` | 32x32@4 | 24-bit | new section, 3584 bytes |
| `system32/cryptui.dll` | 202 `IDB_CERT_ERROR` | `bmp/cert-error.bmp` | 32x32@4 | 24-bit | new section, 3584 bytes |
| `system32/cryptui.dll` | 203 `IDB_CERT_WARNING` | `bmp/cert-warning.bmp` | 32x32@4 | 24-bit | new section, 3584 bytes |
| `system32/cryptui.dll` | 205 `IDB_CERT_WATERMARK` | `bmp/wiz-cert.bmp` | 164x628@4 | 24-bit | new section, 309248 bytes |
| `system32/cryptui.dll` | 206 `IDB_CERT_HEADER` | `bmp/wizhead-cert.bmp` | 49x49@4 | 24-bit | new section, 7680 bytes |
| `system32/zipfldr.dll` | 200 `IDB_HEADER` | `bmp/wizhead-zip.bmp` | 49x49@24 | 24-bit | in place, same length |
| `system32/zipfldr.dll` | 201 `IDB_WATERMARK` | `bmp/wiz-zip.bmp` | 164x628@24 | 24-bit | in place, same length |
| `system32/newdev.dll` | 100 `IDB_WATERMARK` | `bmp/wiz-newdev.bmp` | 164x400@8 | 24-bit | new section, 197120 bytes |
| `system32/newdev.dll` | 101 `IDB_HEADER` | `bmp/wizhead-newdev.bmp` | 49x49@8 | 24-bit | new section, 7680 bytes |
| `system32/credui.dll` | 200 `IDB_BANNER` | `bmp/credui-banner.bmp` | 320x60@24 | 24-bit | in place, same length |
| `system32/appwiz.cpl` | 5002 `IDB_SHORTCUT` | `bmp/wiz-shortcut.bmp` | 164x400@8 | 24-bit | new section, 197120 bytes |
| `system32/hdwwiz.cpl` | 50 `IDB_WATERMARK` | `bmp/wiz-addhw.bmp` | 164x400@8 | 24-bit | new section, 197120 bytes |
| `system32/hdwwiz.cpl` | 51 `IDB_HEADER` | `bmp/wizhead-addhw.bmp` | 49x49@8 | 24-bit | new section, 7680 bytes |
| `system32/desk.cpl` | 1001 `IDC_MONITOR` | `bmp/desk-monitor.bmp` | 160x120@8 | 24-bit | new section, 57856 bytes |
| `system32/taskmgr.exe` | 153 `IDB_TRAYICON` | `bmp/taskmgr-meter.bmp` | 16x16@4 | 24-bit | new section, 1024 bytes |
| `system32/servman.exe` | 10000 `IDB_PROP` | `bmp/servman-prop.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/servman.exe` | 10001 `IDB_REFRESH` | `bmp/servman-refresh.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/servman.exe` | 10002 `IDB_EXPORT` | `bmp/servman-export.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/servman.exe` | 10003 `IDB_CREATE` | `bmp/servman-create.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/servman.exe` | 10004 `IDB_DELETE` | `bmp/servman-delete.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/servman.exe` | 10005 `IDB_START` | `bmp/servman-start.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/servman.exe` | 10006 `IDB_STOP` | `bmp/servman-stop.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/servman.exe` | 10007 `IDB_PAUSE` | `bmp/servman-pause.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/servman.exe` | 10008 `IDB_RESTART` | `bmp/servman-restart.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 50 `IDB_PREV_PIC` | `bmp/shimgvw-prev.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 51 `IDB_NEXT_PIC` | `bmp/shimgvw-next.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 52 `IDB_BEST_FIT` | `bmp/shimgvw-fit.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 53 `IDB_REAL_SIZE` | `bmp/shimgvw-realsize.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 54 `IDB_SLIDE_SHOW` | `bmp/shimgvw-slideshow.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 55 `IDB_ZOOM_IN` | `bmp/shimgvw-zoomin.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 56 `IDB_ZOOM_OUT` | `bmp/shimgvw-zoomout.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 57 `IDB_ROT_CLOCKW` | `bmp/shimgvw-rotcw.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 58 `IDB_ROT_COUNCW` | `bmp/shimgvw-rotccw.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 59 `IDB_ROT_CWSAVE` | `bmp/shimgvw-rotcwsave.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 60 `IDB_ROT_CCWSAVE` | `bmp/shimgvw-rotccwsave.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 61 `IDB_DELETE` | `bmp/shimgvw-delete.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 62 `IDB_PRINT` | `bmp/shimgvw-print.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 63 `IDB_SAVEAS` | `bmp/shimgvw-saveas.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 64 `IDB_MODIFY` | `bmp/shimgvw-modify.bmp` | 16x16@24 | 24-bit | in place, same length |
| `system32/shimgvw.dll` | 65 `IDB_HELP_TOC` | `bmp/shimgvw-help.bmp` | 16x16@24 | 24-bit | in place, same length |

### Bitmap files

| File | Stock SHA-256 | In `dialog_bitmaps.json` |
|---|---|---|
| `explorer.exe` | `4e54225b041fe93ce0b252c6fda3c6c3cdae6203ba6a2d1e5b77873cd86488f7` | no: add |
| `system32/aclui.dll` | `756209146aec55736385bcf32030b23e7f875f01871a2dee5d9c5c8cae17b462` | no: add |
| `system32/appwiz.cpl` | `e65b88a3e637dbbe9d9739bbb233051e0f83c6c41f0aac2371b1138ab0e60e3b` | no: add |
| `system32/comctl32.dll` | `c21b2c46d277371fc23c6138c0ae443e89fe88b9eee36dc8e701f3cfe94ed318` | no: add |
| `system32/credui.dll` | `159289bb5aa841a0a33360b26980b7be5dc2e0bc67bdaca13d0e1aa8465e382a` | no: add |
| `system32/cryptui.dll` | `b24afeabb5d2e1658c8b120f08197cfc5f3b00d8fd77362de4258bf9c7c08c3b` | no: add |
| `system32/desk.cpl` | `895c813152637459fee8f3dc0b5430ec2bb7475d7e35306cb9751f7f893b6458` | no: add |
| `system32/devmgr.dll` | `0670f9388529d74252a08d0c4b25a93be6a971f0ab770600bf448278cbbf2fd3` | no: add |
| `system32/hdwwiz.cpl` | `b3856a9e84b3de1d8059d516bb08879348235c91be616a5c102c187d092dc732` | no: add |
| `system32/hhctrl.ocx` | `c956f260084f2594281778edf6f2f39d4ccb75a43fea2f8c4f2a20ca21ab3e58` | no: add |
| `system32/ieframe.dll` | `beec78a43103e29e34da38bd4ce3dd27f62c68ff83c903a2ab220e5bae059d6d` | no: add |
| `system32/newdev.dll` | `4555fed28cbe771ba52d746acf48f05407b5af3c34064f5f4ad136f24c6ffcec` | no: add |
| `system32/servman.exe` | `fedc937af119f17ef243407e02f777f994488bba6dae785610d04f3cf7931668` | no: add |
| `system32/shimgvw.dll` | `39a18af40db42e6b1011d7f0f62487a8f580276c6afed3e92587dad0b7958de2` | no: add |
| `system32/taskmgr.exe` | `579a15a60994106506c673ffa92a2c15d7cb156e294b7c005c2e4b27e94e4975` | no: add |
| `system32/zipfldr.dll` | `831ac9071cd8637836f3fb127ad0e2a18ea1db8482a41b58fe9364c1639cbb8d` | no: add |
| `winsxs/…5.82.2600.2982/comctl32.dll` | `c21b2c46d277371fc23c6138c0ae443e89fe88b9eee36dc8e701f3cfe94ed318` | no: add |
| `winsxs/…6.0.2600.2982/comctl32.dll` | `c21b2c46d277371fc23c6138c0ae443e89fe88b9eee36dc8e701f3cfe94ed318` | no: add |

**Size and slot constraints, checked against the stock resources.**

- **Depth.** Every group is written with 32-bit frames only, as every Afterglow group is, including the groups that held only 4-bit, 8-bit or 1-bit frames (`mmsys.cpl` 3005 and 3006 are 32 × 32 at 1 bit; the Mouse Keys states 16 × 16 at 8 bits; the comdlg32 drive icons 16 px at 4, 8 and 32 bits): `patch_icon_groups` takes their ids as they are, and the demo and v86 builds run at 32 bits per pixel. Strips whose image lists keep alpha are 32-bit with straight alpha; every other bitmap is 24-bit, over a 4-bit or 8-bit stock one in a new section (the width and height match, so the loader draws it the same way).
- **Frame ids.** No target group shares a frame with another (`stock_group_problem` is clean for 177 of the 179). Groups with fewer than three ids are fitted as today: they keep the sizes the stock group holds and add the next size down on a spare id (Folder Options 184 to 187, `mshta.exe` 1, the Mouse Keys states, the 16 px balloon and overlay groups). `cryptext.dll` 1 holds one 48 px frame, so the File Types list shrinks the 48 px frame to 16 px: the patch is correct, the small picture is the loader's scaling.
- **Refused today.** `msxml3.dll` 128 (22 px frames beside 48, 32 and 16) and `cleanmgr.exe` 100 (a 256 px frame) fail `stock_group_problem` (a size other than 16, 24, 32 or 48). WP-ICON4-2 lets a frame of a size nobody asks for (22, 256) count as a spare id.
- **24 px groups.** Every Applications Manager group holds only 24 px frames (`24@8 24@32`, or one of them), and the toolbar and tree ask for 24 × 24. Today's patcher writes them as 32 px (and 16 px on a second id), which the image list scales down. WP-ICON4-2 writes Afterglow's one-frame `ico24/ID.ico` into a group whose every stock frame is 24 px. The art is there for all 28.
- **BI_BITFIELDS strips.** `comctl32.dll` 120, 121, 124, 125, 130 and 131 (three identical copies), `hhctrl.ocx` 1000 and 1001 and `ieframe.dll` 1400 are 32-bit with a 108-byte `BITMAPV4HEADER` and `BI_BITFIELDS` masks `00ff0000 0000ff00 000000ff ff000000`. `write_bitmaps` refuses them (it wants compression 0 in the stock file); WP-ICON4-2 accepts exactly that header and writes Afterglow's 40-byte `BI_RGB` art, which is longer, in a new section.
- **explorer.exe is agexplorer.exe.** The shell runs `agexplorer.exe`, the copy `afterglow.start` makes with the Start orb and banner (143 and 158). The previews go into that copy (a `dialog_bitmaps.json` entry with `module` `explorer.exe` and `stock_path` `ReactOS/explorer.exe`, as `agmsgina.dll` is done), after `afterglow.start`; 8 of the 23 are 24-bit in the stock file and go in place, 15 are 4-bit or 8-bit and go in a new section.
- **One file, several patchers.** `afterglow.dialog-bitmaps` already builds on the newest copy an earlier patcher made of the same path. Files that take both icons and bitmaps (`comctl32.dll`, `hhctrl.ocx`, `zipfldr.dll`, `appwiz.cpl`, `hdwwiz.cpl`, `servman.exe`, `taskmgr.exe`, `explorer.exe`) get their icons first, then their bitmaps.
- **Size growth.** The new `.agico` sections add from 5,632 bytes (`deskadp.dll`) to 504,320 bytes (`setupapi.dll`, 36 groups) per file, 1,998,127 bytes in all; the grown bitmaps add 1,777,152 bytes (the 164 × 628 watermark in `cryptui.dll` is the largest, 309,248 bytes).
- **The trim.** Every file above is kept by the `base` trim, so the full and the compact image take the same list.

## WP-ICON4-1 — patch the round-4 art (builder brief, in full)

Paste this to a Sonnet builder.

> **Task.** Patch Afterglow's icon round 4 into both ReactOS Liminal images: every row of the patch list in `docs/plans/icon-round-4.md` that today's patchers accept, **Folder Options first**: 177 icon groups and 66 bitmaps. Leave the rows marked "refused" and "WP-ICON4-2" to that package. Read `AGENTS.md`, `SPEC.md`, `docs/icon-survey.md`, `docs/afterglow-pin.md`, `docs/plans/icon-round-4.md` and the Afterglow PR [liminal-hq/afterglow-themes#64](https://github.com/liminal-hq/afterglow-themes/pull/64) first. Work in a worktree under `~/source/worktrees/reactos-liminal/<topic>` on a `feat/` branch, never in the main checkout. Use the work directory `~/.cache/reactos-liminal` (or `RL_WORK`), never one inside the repository. Round 3's patch (WP-ICON3-1, reactos-liminal#36) is on `main`: start from it.
>
> **Needs.** The Afterglow art, approved by the owner and merged as liminal-hq/afterglow-themes#64 at `fd023f4f147690b7055004d29fa010cd3dbd08ae`. Pin to that commit; no `--pre-merge` is needed.
>
> **Finish line.** `./rl image` of `recipes/afterglow.toml` and `recipes/afterglow-compact.toml` writes every WP-ICON4-1 row; `docs/icon-coverage.md` (regenerated by `./rl pin`) lists them as patched; a booted image shows them (below); the gate is green.
>
> **Files owned.** `reactos_liminal/icon_families.json`, `reactos_liminal/dialog_bitmaps.json`, `reactos_liminal/shell32_icons.json` (only if a shell32 row needs it; the map decides), `reactos_liminal/coverage.py` (only to list the new bitmaps), `recipes/afterglow.toml`, both lock files, `pins/*.json` the pin rewrites, `docs/icon-coverage.md` (generated), `docs/icon-survey.md`, `SPEC.md`, `docs/decisions.md` (RL-66), `tests/`.
>
> **Must not touch.** Any art (art lives in Afterglow), `guest/`, `profiles/`, `tools/afterfetch`, `.github/workflows/`, `browseui.dll`'s strips and cells, and the patcher code WP-ICON4-2 owns (`patch_icons.SIZES`, `fitted_sizes`, `stock_group_problem`, `patch_dialog_bitmaps.write_bitmaps`).
>
> **Steps.**
>
> 1. **Pin.** `./rl pin recipes/afterglow.toml --afterglow fd023f4f147690b7055004d29fa010cd3dbd08ae`, then the compact recipe. The `shell32.dll` rows (Folder Options 182 to 187 and 37, the printer 17, the tip 1001) need no table change: the shell32 patcher reads the map.
> 2. **Folder Options first.** Confirm `shell32.dll` 182 to 187 and 37 are patched, then add to `icon_families.json` (`map-icons`, each with the stock SHA-256 from the "Files" table, checked on the golden disk) the File Types files: `zipfldr.dll`, `url.dll`, `msxml3.dll` (its group 129 now; 128 waits for WP-ICON4-2), `mshta.exe`, `cryptext.dll`, `msiexec.exe` and `themeui.dll`; `clipbrd.exe` and `eventvwr.exe` are already listed. Pin, build, and check the Folder Options rows before going on.
> 3. **The other icon files.** Add every other file the "Files" table marks "none" to `map-icons`: `setupapi.dll`, `deskadp.dll`, `deskmon.dll`, `batt.dll`, `input.dll`, `mydocs.dll`, `netcfgx.dll`, `netid.dll`, `hhctrl.ocx`, `fontview.exe`, `gdihv.exe`, `iernonce.dll`, `runonce.exe`, `rundll32.exe`, `regedt32.exe`, `ntvdm.exe`, `netplwiz.dll`, `msutb.dll`, `userenv.dll`, `winlogon.exe`, `certmgr.exe`, `cleanmgr.exe` (it will report group 100 refused until WP-ICON4-2: record that as skipped, not as a failure), `frag.exe`, `comdlg32.dll`, `hotplug.dll`, and `comctl32.dll` three times (`ReactOS/system32/` and the two `ReactOS/winsxs/x86_microsoft.windows.common-controls_…/` folders; all three have the same SHA-256). The applets and programs already listed (`appwiz.cpl`, `hdwwiz.cpl`, `inetcpl.cpl`, `mmsys.cpl`, `powercfg.cpl`, `sysdm.cpl`, `rapps.exe`, `servman.exe`, `sndvol32.exe`, `stobject.dll`) take their new groups from the map with no table change. `hhctrl.ocx` is the first `.ocx` in the table: check the family loader and the coverage report accept the suffix.
> 4. **Bitmaps.** Add to `dialog_bitmaps.json` every file of the "Bitmap files" table marked "no: add", with its stock SHA-256, and `agexplorer.exe` with `module` `explorer.exe` and `stock_path` `ReactOS/explorer.exe` (built on `afterglow.start`'s copy, so list `afterglow.dialog-bitmaps` after `afterglow.start` in the recipe; the loader should refuse the other order, as it does for `user32.dll`). The resources come from the map's `bitmaps`: those whose `file` is `desktop/icons/strips.py` or under `desktop/icons/panels/`, rendered by `desktop/icons/render.py` as `bmp/NAME.bmp` and checked against `desktop/icons/SHA256SUMS`. The round-4 entries name their art `bmp/NAME.bmp`, the path `desktop/icons/SHA256SUMS` records and `render_art` looks up; the Go button's entries keep the `go.bmp` form the toolbar patcher's `verified_bitmaps` reads, so leave `browseui.dll` to that patcher. Skip the 21 BI_BITFIELDS rows (`comctl32.dll` 120 to 131, `hhctrl.ocx` 1000 and 1001, `ieframe.dll` 1400) until WP-ICON4-2, reporting them as skipped.
> 5. **Coverage.** `docs/icon-coverage.md` lists every new group and bitmap; the skipped rows show as skipped with the reason. `./rl pin --check` passes for both recipes.
> 6. **Docs.** `SPEC.md`: the families, the bitmaps `afterglow.dialog-bitmaps` now writes, `agexplorer.exe`'s two patchers. `docs/icon-survey.md`: the new files and the round-4 counts. `docs/decisions.md`: RL-66 "Round-4 art follows the pin", with RL-66.1 (only resources 0.4.16 loads are mapped; the method of `plans/icon-round-4.md`) and RL-66.2 (the Taskbar Properties previews go into `agexplorer.exe` after `afterglow.start`).
> 7. **Tests** (synthetic fixtures only, made at test time): a `.ocx` file in a family; a bitmap written into a copy another patcher made (the `agexplorer.exe` chain) keeps the earlier patcher's resources; a 24-bit panel over an 8-bit stock bitmap goes in a new section and the file parses; a stock file with a changed byte is refused by its hash.
> 8. **Booted check.** Build both images. Boot each in your own private headless QEMU with its monitor socket and pid file under a short path in `/tmp` (for example `/tmp/rl-i4-<pid>/mon`), no network, and stop it through its monitor or its own pid; never `pkill` or `killall`, and never touch a VM you did not start. Take screens with the monitor's `screendump` only of: **Folder Options** (General with each radio choice, View, File Types scrolled through `.cer`, `.evt`, `.hta`, `.msi`, `.theme`, `.url`, `.xsl`, `.zip`), Device Manager (expanded, with a device showing an overlay if one does), the Applications Manager, Taskbar and Start Menu Properties (both tabs, every checkbox state you can reach), Display Properties (the monitor and the Advanced tabs), Sounds and Audio, Power Options, Internet Options (Security, Content, General), Event Viewer and an event's properties, Service Manager, the image viewer, the help viewer, WordPad's toolbar, the Open dialog's toolbar, Mouse Keys on (Accessibility Options) with its tray icon. Save them as PNGs to `~/Documents/Liminal HQ/Afterglow/ReactOS/Screenshots/12 Icon round 4/` named `after-boot-<what>-<full|compact>.png`. Delete the scratch disks and the run folder when done, one path per command, and keep `df -h /home` above 20 GB.
>
> **Gate.** `ruff format --check`, `ruff check`, `python3 -m pytest`, `bash scripts/check-headers.sh`, `bash scripts/check-no-binaries.sh`, markdownlint (`docker run --rm -v "$PWD:/workdir" davidanson/markdownlint-cli2:v0.17.2 "**/*.md"`), `./rl pin --check` for both recipes.
>
> **Commits and PR.** Conventional Commits written to a file and committed with `git commit -F`, body in markdown with bold labels and no headings, hard-wrapped, ending `Co-Authored-By: <your model> <noreply@anthropic.com>`; stage explicit paths, never `git add -A`. PR title capitalized imperative, `## Summary` with bold lead-in bullets, `## Test plan` with the commands, ending with an unchecked `- [ ] Not verified: …`. Labels `enhancement`, `afterglow`, `reactos`. Open it; do not merge. Report the PR URL, the coverage counts, the screenshot paths and anything the booted check showed still in stock.

## WP-ICON4-2 — the patcher extensions (builder brief)

> **Task.** Extend the patchers so the rows WP-ICON4-1 skipped are written, then patch them: the Applications Manager's 24 px groups with Afterglow's 24 px frame (`ico24/ID.ico`), `msxml3.dll` 128 and `cleanmgr.exe` 100 (a 22 px and a 256 px frame count as spare ids, since nothing asks for those sizes), and the 21 BI_BITFIELDS strips (`comctl32.dll` 120, 121, 124, 125, 130 and 131 in all three copies, `hhctrl.ocx` 1000 and 1001, `ieframe.dll` 1400: accept exactly a 108-byte `BITMAPV4HEADER` with masks `00ff0000 0000ff00 000000ff ff000000` and write the 40-byte `BI_RGB` art in a new section). Same reading, worktree, pin, booted-check, gate, commit and PR rules as WP-ICON4-1, after it merges. Owned: `reactos_liminal/patch_icons.py` (`SIZES`, `fitted_sizes`, `stock_group_problem`, `verified_icons` for `ico24/`), `reactos_liminal/patch_dialog_bitmaps.py` (`write_bitmaps`), `tests/`, `SPEC.md`, `docs/icon-survey.md`, `docs/decisions.md` (RL-67), the regenerated coverage and pins. Tests with synthetic fixtures: a group of only 24 px frames takes a one-frame 24 px icon and keeps its ids; a group with a 22 px or 256 px frame takes 48, 32 and 16 px frames on its ids; a BI_BITFIELDS stock bitmap with those masks takes BI_RGB art in a new section and one with other masks is refused. Booted screens: the Applications Manager's toolbar and tree, the Open dialog's toolbar, WordPad's toolbar, the help viewer, Internet Explorer's toolbar, File Types at `.xml`, Disk Cleanup.

## Rules for every package

The repository's `AGENTS.md` applies in full: no ReactOS binary, image or art in git; every patcher hash-guarded and same-size or new-section; private QEMU only and no host desktop capture; worktrees under `~/source/worktrees/reactos-liminal/`; scratch cleaned up with plain commands, one full path each.

## Owner decisions

- **Folder Options pictures.** The General tab's six are drawn new (task pane window, plain window, one window, two windows, link hand, arrow with click rings); the View tab's Folder views picture reuses `programsfolder`. Another drawing is a change to `draw_fo_*` in Afterglow's `gen_v6.py`; another reuse is one `also` in `map.json`.
- **File Types reuse.** `.hta` and `.url` take `html`, `.clp` `paste`, `.msi` `wusa`, `.theme` `display`; only certificates, event logs and XML get new icons. Each is one `also` entry in `map.json`.
- **The Change Icon picker** lists every group of the file it browses, including `shell32.dll`'s 180 never-loaded groups and `pifmgr.dll`'s 38. They stay stock, as round 3 decided for P4; drawing them is a round of its own.
- **Device classes reuse set E.** Monitors and display adapters share `setupapi.dll` 1, so both classes show `monitor` (the display adapter card, `devdisplay`, is the Advanced tab's); keyboards take `kbdlayout`, controllers, processors and SCSI the chip `ntdevice`, ports `ntport`. Each is one map entry.
- **The time zone map** (`timedate.cpl` 115) stays the stock satellite raster; an Afterglow map would need a vector world outline drawn or sourced.
- **The trimmed programs** (26 groups and 35 bitmaps in the full image only: the On-Screen Keyboard, Paint, Sound Recorder, Media Player, Minesweeper, the savers) are the next pass; nothing here touches them.
- **The 4-bit certificate image lists** (`cryptui.dll` 200 and 204) stay stock: the program draws them through a 16-colour image list, which would quantize Afterglow's art.
