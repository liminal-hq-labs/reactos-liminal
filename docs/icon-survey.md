# Icon survey

Which icon groups in ReactOS 0.4.16's `shell32.dll` and other files the Afterglow icon set replaces, what frames each one holds, and how that follows Afterglow's `desktop/icons/map.json`. **Which groups are replaced is decided by the map**, not by the tables in this repository (see [How the map and the tables divide the work](#how-the-map-and-the-tables-divide-the-work)); the tables below are the survey of what the stock files hold, written when each group was first checked. The machine-readable table is [`reactos_liminal/shell32_icons.json`](../reactos_liminal/shell32_icons.json); `reactos_liminal/icon_survey.py` regenerates the frame columns from a stock file. How ReactOS chooses and draws folder icons (and why a folder never changes with its contents) is written up in the owner's "ReactOS folder icon behaviour" note; the facts this patcher depends on are repeated below.

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

Two `shell32.dll` groups are left alone, and each has a `reason` row in `shell32_icons.json`: 29 (the share hand, never drawn by 0.4.16) and 31 (the folder-wait icon, unused by 0.4.16). Every other group the survey lists is replaced, because Afterglow's icon set v2 draws the removable drive (8), the RAM disk (13), Favourites (44, 322), the CSIDL_DRIVES folder (43), the NetHood folder (15), the items under Entire Network (172), the not-connected drive (54), Log Off (45, 325) and the video, audio, batch and `.ini` file types (224, 225, 153, 151) that earlier icon sets did not.

## How the map and the tables divide the work

Afterglow's `map.json` says, for each of its icons, which ReactOS resource it replaces: a module and an icon group (or, for the Explorer toolbar, the four bitmap strips and a cell), with more resources under `also`. A resource is null unless Afterglow verified it against the ReactOS 0.4.16 source and the stock file, so nothing is guessed. The patchers read it on every run:

- **`afterglow.icons`** replaces every `shell32.dll` group the map names, `also` entries included.
- **`afterglow.cpl-icons` and `afterglow.program-icons`** replace every group the map names for each file listed in `icon_families.json` (the Control Panel applets, `cmd.exe`, `notepad.exe`, `cabview.dll`, `shimgvw.dll` and `netshell.dll`, the Network Connections folder).
- **`afterglow.toolbar-bitmaps`** replaces every `browseui.dll` cell the map names for strips 214 to 217.

The tables in this repository hold only what the map cannot say: the SHA-256 of each stock file that guards its patch, the strip sizes, the frames each group holds, and any group the map does not name that is replaced anyway (`afterglow` on a row, which the map overrides if it later names that group) or left alone (`reason`). A new icon set, such as a redrawn drive icon or a hand-tuned 16 px frame, is therefore a new Afterglow pin and `rl pin` ([Afterglow pin](afterglow-pin.md)), with no code or table change. A group the map verifies that the stock file cannot take (fewer than three frame ids of its own) stops the build rather than being skipped.

Two groups changed icon when the map became the source: group 20 (the Programs folder by id) is now `programsfolder`, and group 21 (the Recent folder) `recent`, as the map names them; the Start menu entries 326 and 327 keep `programs` and `documents`.

## What the patcher does with the frames

- The stock group lists nine frames (three sizes at 4, 8 and 32 bits per pixel) in most cases. The new group lists three, 32-bit only, and each takes the id of a stock 32-bit frame of the same size; the other ids stay in `.rsrc` unreferenced. Afterglow supplies no 4 or 8 bit frames, so a 256-colour or 16-colour display would pick the 32-bit frame and dither; the demo and the v86 build run at 32 bits per pixel.
- The groups with fewer than three ids (none today) would need the directory to grow, and are refused.
- The new bytes go in a new `.agico` section at the end of the file, and the data entries are pointed at it. The resource directory is not rewritten, so nothing else in the 7.4 MB `.rsrc` moves. The PE checksum is recomputed and checked on the stock file first (the algorithm reproduces the stock value `0xa6e850`).
- The 16 px frames are whatever Afterglow's `render.py` writes: the hand-tuned frames of icon set v2 where Afterglow has drawn them, the scripted render of the 16 px master elsewhere. A later redraw is picked up by moving the Afterglow pin and running `rl pin`.

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

The table above is the first set. Afterglow's map now also verifies cut 5, copy to clipboard 6, paste 7, favourites 2, properties 15, map drive 29 and disconnect 30, and the patcher replaces those too; 18 cells in all. The rest have no Afterglow icon and stay as ReactOS draws them. Afterglow renders 16, 32 and 48 px only, so the 24 px cells are the 48 px frame halved with an integer, alpha-weighted 2 × 2 average; the hot strips get the same cells as the normal ones because Afterglow draws no hot state. The patcher writes the cells in place, so each strip keeps its id, size and depth; it refuses a strip that differs.

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

Applets the base trim removes (`joy.cpl` 102, `telephon.cpl` 100, `usrmgr.cpl` 40 and 100) are not patched, though the map verifies them; `ncpa.cpl` (a stub with no resources; Network Connections shows `netshell.dll` group 100) and `odbccp32i.cpl`, `openglcfg.cpl`, `wined3dcfg.cpl` (not in the base install). The inner icons of the applets' own dialogs (mouse speed, battery states, sound events and so on) are not applet icons and are not replaced.

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

`netshell.dll` group 100 (Network Connections folder, the `also` entry of `netconn`) is patched too. The Applications Manager (`rapps.exe` 10, Afterglow `appmanager`) and Internet Browser (`iexplore.exe` 1, `browser`) icons are not: the `base` trim profile removes `rapps.exe` and `Program Files/Internet Explorer` from the image, and the trim refuses to remove a patched file (RL-19). The desktop shortcuts that remain show ReactOS's own fallback icon.

### Verified by the map but not patched

The map verifies these resources, and none is patched today. Adding one is a stock-file SHA-256 in `icon_families.json` (a `files` entry), then `rl pin`; the patcher takes the groups from the map.

- **Removed by the `base` trim**, which refuses to remove a patched file (RL-19): the Applications Manager (`rapps.exe` 10, `appmanager`), Internet Browser (`iexplore.exe` 1, `browser`; the profile removes `Program Files/Internet Explorer`), Calculator, Paint, WordPad and its `.rtf` type, Character Map, Minesweeper, Solitaire, Spider, Remote Desktop, Media Player, Sound Recorder, On-Screen Keyboard, Magnifier, DirectX Diagnostic, `control.exe`, `joy.cpl`, `telephon.cpl` and `usrmgr.cpl`. A recipe that keeps one of them can list its stock file.
- **On the image, not yet listed:** Registry Editor and its file type (`regedit.exe` 100, 101), Task Manager, Event Viewer, Device Manager, Services, System Configuration, Utility Manager, Clipboard Viewer, the Windows Update installer, `ieframe.dll` (HTML files), `hh.exe`, `winhlp32.exe` and `sndvol32.exe`, and Explorer (`explorer.exe` 101, which `afterglow.start` copies as `agexplorer.exe` from the stock file, so a second patch there needs the two combined). Each needs its stock SHA-256 from the golden disk and a check that its groups have three frame ids of their own.
- **Tray:** `stobject.dll` (volume, battery, hotplug), `ctfmon.exe` and `kbswitch.exe` (keyboard layout). Afterglow draws a state per icon here; the patcher would take them from the map the same way.
- **Dialogs and the program icon in `user32.dll`:** `user32.dll` already carries the Afterglow pointers from `afterglow.pointers`, which patches the stock file in its own pass. Patching icons into the same file needs the two patchers combined or run in sequence on one copy, which the pipeline does not do (each patcher starts from the golden file); left for a decision (RL-26.4).
