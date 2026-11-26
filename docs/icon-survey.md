# Icon survey

Which icon groups in ReactOS 0.4.16's `shell32.dll` the Afterglow icon set replaces, what frames each one holds, and how that matches Afterglow's `desktop/icons/map.json`. The machine-readable table is [`reactos_liminal/shell32_icons.json`](../reactos_liminal/shell32_icons.json); `reactos_liminal/icon_survey.py` regenerates the frame columns from a stock file. How ReactOS chooses and draws folder icons (and why a folder never changes with its contents) is written up in the owner's "ReactOS folder icon behaviour" note; the facts this patcher depends on are repeated below.

The stock file is `shell32.dll` of the 0.4.16 i386 install, 10,935,296 bytes, SHA-256 `88858710130e8e97eecfc246e61dd1aaf45b410718f4b818be39a9a69a01cf72`. It holds 237 icon groups and 1,445 icon frames, every group has one language, and no two groups share a frame id (checked on the file).

## What the shell asks for

- **Sizes.** 16, 32 and 48 px, never 24. The desktop and the Icons view use 48; List, Details, the Explorer tree and Start menu submenus use 16; programs that load an icon at the system size get 32.
- **Folders.** A plain folder is group 4 whether it is empty or full; ReactOS does not look inside it. Only the Recycle Bin is content-aware (groups 32 and 33). The open folder (group 5) shows only in the common file dialog's Look in list and in regedit, because the tree and Browse for Folder are given the closed icon again.
- **Shortcut arrow.** Group 30 is the only overlay. The icon cache copies its colour pixels over the target's icon at the same size. Stock has no 48 px frame, so the 32 px arrow is stretched there; the Afterglow arrow has a real 48 px frame.
- **Registry.** `DefaultIcon` values name a group by negative id (`-16`, `-35`, `-235`) or by zero-based position (`shell32.dll,31` is group 32), so replacing the group in the file changes every consumer, including programs that load it by id.

## Groups replaced

Every group below is rewritten with three 32-bit frames (48, 32 and 16 px) from Afterglow's `ico/NAME.ico`. **core** rows are groups Afterglow's `map.json` names too; **extra** rows are verified here from the ReactOS source and the stock file but not yet named in Afterglow's map, and the patcher accepts them only because the table says so (it still refuses a map that puts the same icon in a different group).

| Group | Name | Used for | Stock frames | Afterglow icon | Tier |
|---|---|---|---|---|---|
| 4 | `IDI_SHELL_FOLDER` | Every plain folder: closed, the tree's selected state, the desktop, all views | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `folder` | core |
| 5 | `IDI_SHELL_FOLDER_OPEN` | Open folder; in 0.4.16 only the file dialog's Look in list and regedit | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `folderopen` | core |
| 7 | `IDI_SHELL_3_14_FLOPPY` | Floppy drive | `16@4 16@8 16@32 32@4 32@8 32@32 48@4 48@8 48@32` | `floppy` | extra |
| 9 | `IDI_SHELL_DRIVE` | Fixed disk | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `hdd` | extra |
| 10 | `IDI_SHELL_NETDRIVE` | Network drive | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `netdrive` | extra |
| 12 | `IDI_SHELL_CDROM` | CD-ROM drive | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `cd` | extra |
| 16 | `IDI_SHELL_MY_COMPUTER` | My Computer | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `mycomputer` | core |
| 18 | `IDI_SHELL_MY_NETWORK_PLACES` | My Network Places | `48@8 32@8 16@8 48@32 32@32 16@32` | `network` | core |
| 30 | `IDI_SHELL_SHORTCUT` | Shortcut arrow overlay, copied over the target's icon by the icon cache | `32@8 16@8 32@32 16@32` | `arrow` | core |
| 32 | `IDI_SHELL_EMPTY_RECYCLE_BIN` | Recycle Bin, empty | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `recycle` | core |
| 33 | `IDI_SHELL_FULL_RECYCLE_BIN` | Recycle Bin, full | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `recyclefull` | core |
| 35 | `IDI_SHELL_DESKTOP` | Desktop root in the tree and in file dialogs | `48@32 32@32 16@32` | `desktop` | core |
| 137 | `IDI_SHELL_CONTROL_PANEL3` | Control Panel | `48@8 32@8 16@8 48@32 32@32 16@32` | `controlpanel` | extra |
| 235 | `IDI_SHELL_MY_DOCUMENTS` | My Documents (desktop item and folder), Shared Documents | `48@4 32@4 16@4 48@32 32@8 16@8 48@24 32@32 16@32` | `mydocs` | core |
| 236 | `IDI_SHELL_MY_PICTURES` | My Pictures, Shared Pictures | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `mypictures` | core |
| 237 | `IDI_SHELL_MY_MUSIC` | My Music, Shared Music | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `mymusic` | core |
| 238 | `IDI_SHELL_MY_MOVIES` | My Videos, Shared Videos | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `myvideos` | core |

Frames are `size@bits per pixel`, in the stock order.

## Groups left as ReactOS draws them

Nine groups remain after the second phase (see [Start menu, file types and the rest of shell32](#start-menu-file-types-and-the-rest-of-shell32)). Afterglow has no art for any of them.

| Group | What | Stock frames | Why |
|---|---|---|---|
| 8 | Removable drive | `48@8 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon for a removable drive |
| 13 | RAM disk | `48@8 48@32 32@4 32@32` | no Afterglow icon for a RAM disk; the stock group has no 16 px frame |
| 15 | NetHood folder | `48@8 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon |
| 29 | Share hand | `16@4 32@4 48@4 16@8 32@8 48@8 16@32 32@32 48@32` | never drawn by 0.4.16 |
| 31 | Folder wait | `32@8 16@8 32@32 16@32` | unused by 0.4.16 |
| 43 | CSIDL_DRIVES folder entry | `48@8 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon |
| 44 | Favorites | `48@4 32@4 16@4 48@24 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon |
| 54 | Drive not connected | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon |
| 172 | Items under Entire Network | `48@8 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon |

## Reconciling with Afterglow's map

At the pinned commit `map.json` has 74 icons; 12 carry a `resource` (the core rows above), and the table here matches each one. The patcher checks this on every run: a map entry that names another group, or that loses the group of a core row, stops the build. The extra rows are the drive icons (floppy 7, fixed disk 9, network drive 10, CD 12) and the Control Panel (137), whose Afterglow entries still have `resource: null`. Suggested next step for Afterglow: record those five, and decide printers (138, 38), fonts (39), Favorites (44), Recent (21), Start Menu (40) and NetHood (15) when the art exists.

## What the patcher does with the frames

- The stock group lists nine frames (three sizes at 4, 8 and 32 bits per pixel) in most cases. The new group lists three, 32-bit only, and each takes the id of a stock 32-bit frame of the same size; the other ids stay in `.rsrc` unreferenced. Afterglow supplies no 4 or 8 bit frames, so a 256-colour or 16-colour display would pick the 32-bit frame and dither; the demo and the v86 build run at 32 bits per pixel.
- The groups with fewer than three ids (none today) would need the directory to grow, and are refused.
- The new bytes go in a new `.agico` section at the end of the file, and the data entries are pointed at it. The resource directory is not rewritten, so nothing else in the 7.4 MB `.rsrc` moves. The PE checksum is recomputed and checked on the stock file first (the algorithm reproduces the stock value `0xa6e850`).
- The 16 px frames are Afterglow's scripted renders of its 16 px masters (hinted redraws exist for some icons). Hand-drawn 16 px pixel redraws do not exist yet; when they do, the Afterglow pin moves and the patcher picks them up with a new pinned sum.

## Phase 2: the rest of the system icons

The same survey method, run on the other files of the 0.4.16 install (the stock files are the ones on the golden disk). Every file is guarded by its SHA-256; the machine-readable tables are [`reactos_liminal/icon_families.json`](../reactos_liminal/icon_families.json) (groups), [`reactos_liminal/bitmap_strips.json`](../reactos_liminal/bitmap_strips.json) (bitmap cells) and the phase 2 rows of `shell32_icons.json`. Each icon is replaced only where the table, the ReactOS source and the stock file agree.

### Explorer toolbar

The Explorer toolbar images are four `RT_BITMAP` strips in `browseui.dll`: 214 (24 px cells, normal), 215 (24 px, hot), 216 (16 px, normal) and 217 (16 px, hot). Each is 47 cells (1128 × 24 and 752 × 16), 32 bits per pixel with straight alpha, loaded as an image list by `toolsband.cpp` (`ImageList_LoadImage` with a cell width of 0, so the cell is as wide as the strip is tall, and the mask colour magenta unused because the bitmaps carry alpha). The cell numbers are the `*ImageIndex` constants in that file. The other strips in `browseui.dll` are the Go button (230, 231, 20 × 20), the brand band (240) and a 39 × 11 bitmap (545). `shdocvw.dll` borrows strip 216 for the Favourites band. `shell32.dll` holds strips 204 to 207 and 225 to 228, which nothing in 0.4.16 loads. `comctl32.dll` holds the standard toolbar strips (120, 121, 124, 125, 130, 131: 16 and 24 px, 32 bits) that applications request with `IDB_STD_*`; they are shared by every program, so they are listed but not replaced.

| Cell | Button | Afterglow icon |
|---|---|---|
| 0 | Back | `back` |
| 1 | Forward | `forward` |
| 8 | Undo | `undo` |
| 10 | Delete | `del` |
| 17 | Search | `search` |
| 22 | Views | `views` |
| 28 | Up one level | `up` |
| 43 | Folders | `folders` |
| 44 | Move to | `move` |
| 45 | Copy to | `copy` |
| 46 | Folder Options | `folderopts` |

The other cells (cut 5, paste 7, favourites 2, properties 15, map drive 29, disconnect 30 and the rest) have no Afterglow icon and stay as ReactOS draws them. Afterglow renders 16, 32 and 48 px only, so the 24 px cells are the 48 px frame halved with an integer, alpha-weighted 2 × 2 average; the hot strips get the same cells as the normal ones because Afterglow draws no hot state. The patcher writes the cells in place, so each strip keeps its id, size and depth; it refuses a strip that differs.

### Control Panel applets

The Control Panel folder asks each applet for `CPL_INQUIRE`'s `idIcon` and loads the icon from the `.cpl` by that resource id (`CControlPanelFolder.cpp`, negative icon index), so the groups below are what it shows. Where an applet's source has a second theme-compatibility id both are replaced.

| File | Group | Applet | Stock frames | Afterglow icon |
|---|---|---|---|---|
| `access.cpl` | 110 | Accessibility Options | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `access` |
| `appwiz.cpl` | 1500 | Add or Remove Programs | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `addremove` |
| `desk.cpl` | 40 | Display | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `display` |
| `desk.cpl` | 100 | Display (theme-compatibility id) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `display` |
| `hdwwiz.cpl` | 100 | Add Hardware | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `addhw` |
| `inetcpl.cpl` | 100 | Internet Options | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `inetsettings` |
| `intl.cpl` | 200 | Regional and Language Options | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@8` | `regional` |
| `main.cpl` | 100 | Mouse | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `mouse` |
| `main.cpl` | 200 | Keyboard | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `keyboard` |
| `main.cpl` | 300 | Printers (folder shortcut) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `printers` |
| `main.cpl` | 400 | Fonts (folder shortcut) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `fonts` |
| `main.cpl` | 500 | Administrative Tools (folder shortcut) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `admintools` |
| `mmsys.cpl` | 3004 | Sounds and Audio Devices | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `sound` |
| `powercfg.cpl` | 100 | Power Options | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `power` |
| `sysdm.cpl` | 50 | System | `48@8 32@8 16@8 48@32 32@32 16@32` | `system` |
| `timedate.cpl` | 1 | Date and Time | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `datetime` |

Applets with no Afterglow icon stay as they are: `joy.cpl` (102, game controllers), `telephon.cpl` (100), `usrmgr.cpl` (40 and 100, user accounts), `ncpa.cpl` (a stub with no resources; Network Connections shows `netshell.dll` group 100) and `odbccp32i.cpl`, `openglcfg.cpl`, `wined3dcfg.cpl` (not in the base install). The inner icons of the applets' own dialogs (mouse speed, battery states, sound events and so on) are not applet icons and are not replaced.

### Start menu, file types and the rest of shell32

The classic Start menu asks `shell32.dll` for its icons by id (`CStartMenu.cpp`), the Control Panel and Start Menu folder icons are registry `DefaultIcon` values that name shell32 groups, and the file types whose `DefaultIcon` is `shell32.dll,-N` (`boot/bootdata/hivecls.inf`) take theirs from the groups below. The table lists the groups added in phase 2.

| Group | Name | Used for | Stock frames | Afterglow icon |
|---|---|---|---|---|
| 1 | `IDI_SHELL_DOCUMENT` | Generic document | `48@8 32@8 16@8 48@32 32@32 16@32` | `doc` |
| 3 | `IDI_SHELL_EXE` | Programs without an icon of their own (.exe, .com) | `48@8 32@8 16@8 48@32 32@32 16@32` | `program` |
| 20 | `IDI_SHELL_PROGRAMS_FOLDER` | Programs folder (by id) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `programs` |
| 21 | `IDI_SHELL_RECENT_DOCUMENTS` | Recent folder | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `documents` |
| 22 | `IDI_SHELL_CONTROL_PANEL` | Control Panel in the Start menu and the Control Panel folder | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `controlpanel` |
| 23 | `IDI_SHELL_SEARCH` | Search | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `search` |
| 24 | `IDI_SHELL_HELP` | Help files (.hlp) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `help` |
| 38 | `IDI_SHELL_PRINTERS_FOLDER` | Printers folder (CSIDL) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `printers` |
| 39 | `IDI_SHELL_FONTS_FOLDER` | Fonts folder | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `fonts` |
| 40 | `IDI_SHELL_TSKBAR_STARTMENU` | Taskbar and Start Menu; the Start Menu folder | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `taskbarstart` |
| 138 | `IDI_SHELL_PRINTER2` | Printers (registry DefaultIcon of the Printers item) | `48@8 32@8 16@8 48@32 32@32 16@32` | `printers` |
| 152 | `IDI_SHELL_TEXT_FILE` | Text files (.txt) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `text` |
| 154 | `IDI_SHELL_SYSTEM_FILE` | System files (.dll, .sys, .cpl, .drv, .ocx) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `library` |
| 155 | `IDI_SHELL_FONT_FILE` | Font files (.fon, .fnt) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `font` |
| 156 | `IDI_SHELL_TT_FONT_FILE` | TrueType and OpenType font files | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `font` |
| 210 | `IDI_SHELL_FOLDER_OPTIONS` | Folder Options | `48@32 48@8 48@4 32@32 32@8 32@4 16@8 16@32 16@4` | `folderopts` |
| 257 | `IDI_SHELL_NETWORK_CONNECTIONS2` | Network Connections in the Start menu | `48@4 32@4 24@4 16@4 48@8 32@8 24@8 16@8 48@32 32@32 24@32 16@32` | `netconn` |
| 323 | `IDI_SHELL_SEARCH1` | Start menu: Search | `48@32 48@8 48@4 32@32 32@8 32@4 16@32 16@8 16@4` | `search` |
| 324 | `IDI_SHELL_HELP2` | Start menu: Help and Support | `48@32 48@8 48@4 32@32 32@8 32@4 16@32 16@8 16@4` | `help` |
| 326 | `IDI_SHELL_PROGRAMS_FOLDER1` | Start menu: Programs | `48@32 48@8 48@4 32@32 32@8 32@4 16@32 16@8 16@4` | `programs` |
| 327 | `IDI_SHELL_RECENT_DOCUMENTS1` | Start menu: Documents | `48@32 48@8 48@4 32@32 32@8 32@4 16@32 16@8 16@4` | `documents` |
| 328 | `IDI_SHELL_RUN1` | Start menu: Run | `48@32 48@8 48@4 32@32 32@8 32@4 16@32 16@8 16@4` | `run` |
| 329 | `IDI_SHELL_SHUTDOWN1` | Start menu: Shut Down | `48@32 48@8 48@4 32@32 32@8 32@4 16@32 16@8 16@4` | `shutdown` |
| 330 | `IDI_SHELL_CONTROL_PANEL1` | Start menu: Settings | `48@32 48@8 48@4 32@32 32@8 32@4 16@32 16@8 16@4` | `settings` |

### Programs and file types

The desktop and Start menu programs carry their own icon groups, and a few file types take theirs from a program or a library (`shimgvw.dll` for images, `cabview.dll` for cabinets). The file types set by `DefaultIcon` registry values are not edited: the values name groups that this patcher changes.

| File | Group | Used for | Stock frames | Afterglow icon |
|---|---|---|---|---|
| `cmd.exe` | 1 | Command Prompt | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `cmd` |
| `notepad.exe` | 521 | Notepad | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | `text` |
| `cabview.dll` | 1 | Cabinet (.cab) files | `48@24 32@8 16@8 48@32 32@32 16@32` | `archive` |
| `shimgvw.dll` | 1 | Image files: .jpg, .emf, .wmf | `16@8 24@8 32@8 48@8 16@24 24@24 32@24 48@24 16@32 24@32 32@32 48@32` | `image` |
| `shimgvw.dll` | 2 | Image files: .bmp | `48@8 32@8 24@8 16@8 48@32 32@32 24@32 16@32` | `image` |
| `shimgvw.dll` | 5 | Image files: .gif, .png | `48@8 32@8 24@8 16@8 48@32 32@32 24@32 16@32` | `image` |

The Applications Manager (`rapps.exe` 10, Afterglow `appmanager`) and Internet Browser (`iexplore.exe` 1, `browser`) icons are not patched: the `base` trim profile removes `rapps.exe` and `Program Files/Internet Explorer` from the image, and the trim refuses to remove a patched file (RL-19). They are in the survey for a recipe that keeps them; the desktop shortcuts that remain show ReactOS's own fallback icon.

### What Afterglow cannot supply

Needs new art (reported, not drawn):

- **Programs:** Calculator (`calc.exe` 110), Paint (`mspaint.exe` 500), Registry Editor (`regedit.exe` 100 and its file type 1), Task Manager (`taskmgr.exe`), WordPad (`wordpad.exe`) and its `.rtf` file type group (Afterglow has an `rtf` document icon; the group, `wordpad.exe` -103, is not in the survey table yet), Character Map, Minesweeper, Solitaire, On-Screen Keyboard, Magnifier, Remote Desktop, Media Player, Event Viewer, System Configuration, DirectX Diagnostic, Help Viewer (`hh.exe`, `winhlp32.exe`: Afterglow's `help` icon would fit, deferred), and the Windows Update installer.
- **Start menu and shell32:** Favourites (322, 44), Log Off (325), Recent as a folder with its own look (21 uses `documents`), NetHood (15), Removable drive (8), RAM disk (13), Not-connected drive (54), the CSIDL_DRIVES folder (43), Items under Entire Network (172), the video and audio file types (224, 225) and the batch-file type (153).
- **Explorer toolbar:** cut, paste, favourites, properties, map and disconnect drive, history, full screen and the 24 px hot state.
- **Tray:** the tray icons come from `stobject.dll` (volume, power, hotplug; 29 groups, ids 200 to 449, many 16 px only) and the keyboard layout indicator from `ctfmon.exe` (group 100). Afterglow has `volume`, `clock`, `kbdlayout`, `showdesk` and `trynet`, but each tray group is a state (volume normal and muted, battery levels, hotplug) and the meaning of each id was not verified against the source in this pass, and Afterglow draws one icon per kind, not per state. Not patched; the survey lists the files and ids for a follow-up.
- **Dialogs:** the message box icons (`error`, `info`, `question`, `warning`, `shield`) are `user32.dll` groups, and `user32.dll` already carries the Afterglow pointers from `afterglow.pointers`, which patches the stock file in its own pass. Patching icons into the same file needs the two patchers combined or run in sequence on one copy, which the pipeline does not do (each patcher starts from the golden file); left for a decision.
- **Desktop shortcuts:** the Read Me shortcut takes the `.txt` file-type icon (shell32 group 152, replaced with `text`), not Afterglow's `readme` icon; using `readme` needs the shortcut to name an icon. Internet Browser takes its icon from `iexplore.exe` (group 1, replaced with `browser`).

### Reconciling with Afterglow's map

Afterglow's `map.json` has 74 entries. Its `kind` agrees with the Control Panel family (every applet entry is `applet`), the drive icons (`floppy`, `hdd`, `netdrive`, `cd` are `drive`) and the five extra groups of phase 1 are the same ones this survey verified; the patcher still checks the applet kind on every run. The entries `appmanager`, `browser`, `cmd`, `readme` and the Explorer toolbar entries have no `resource` in the map; this repository's tables carry the files and ids, and a suggested next step for Afterglow is to record them.
