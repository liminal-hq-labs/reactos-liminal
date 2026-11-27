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

| Group | What | Stock frames | Why |
|---|---|---|---|
| 8 | Removable drive | `48@8 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon for a removable drive |
| 13 | RAM disk | `48@8 48@32 32@4 32@32` | no Afterglow icon for a RAM disk; the stock group has no 16 px frame |
| 15 | NetHood folder | `48@8 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon |
| 20 | Programs folder (by id) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon |
| 21 | Recent | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon |
| 29 | Share hand | `16@4 32@4 48@4 16@8 32@8 48@8 16@32 32@32 48@32` | never drawn by 0.4.16 |
| 31 | Folder wait | `32@8 16@8 32@32 16@32` | unused by 0.4.16 |
| 38 | Printers folder (CSIDL) | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | Afterglow has a printers icon, but its group is not verified against Afterglow's map |
| 39 | Fonts folder | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | Afterglow has a fonts icon, but its group is not verified against Afterglow's map |
| 40 | Start Menu folder | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon |
| 43 | CSIDL_DRIVES folder entry | `48@8 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon |
| 44 | Favorites | `48@4 32@4 16@4 48@24 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon |
| 54 | Drive not connected | `48@4 32@4 16@4 48@8 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon |
| 138 | Printers | `48@8 32@8 16@8 48@32 32@32 16@32` | Afterglow has a printers icon, but its group is not verified against Afterglow's map |
| 172 | Items under Entire Network | `48@8 32@8 16@8 48@32 32@32 16@32` | no Afterglow icon |

## Reconciling with Afterglow's map

At the pinned commit `map.json` has 74 icons; 12 carry a `resource` (the core rows above), and the table here matches each one. The patcher checks this on every run: a map entry that names another group, or that loses the group of a core row, stops the build. The extra rows are the drive icons (floppy 7, fixed disk 9, network drive 10, CD 12) and the Control Panel (137), whose Afterglow entries still have `resource: null`. Suggested next step for Afterglow: record those five, and decide printers (138, 38), fonts (39), Favorites (44), Recent (21), Start Menu (40) and NetHood (15) when the art exists.

## What the patcher does with the frames

- The stock group lists nine frames (three sizes at 4, 8 and 32 bits per pixel) in most cases. The new group lists three, 32-bit only, and each takes the id of a stock 32-bit frame of the same size; the other ids stay in `.rsrc` unreferenced. Afterglow supplies no 4 or 8 bit frames, so a 256-colour or 16-colour display would pick the 32-bit frame and dither; the demo and the v86 build run at 32 bits per pixel.
- The groups with fewer than three ids (none today) would need the directory to grow, and are refused.
- The new bytes go in a new `.agico` section at the end of the file, and the data entries are pointed at it. The resource directory is not rewritten, so nothing else in the 7.4 MB `.rsrc` moves. The PE checksum is recomputed and checked on the stock file first (the algorithm reproduces the stock value `0xa6e850`).
- The 16 px frames are Afterglow's scripted renders of its 16 px masters (hinted redraws exist for some icons). Hand-drawn 16 px pixel redraws do not exist yet; when they do, the Afterglow pin moves and the patcher picks them up with a new pinned sum.
