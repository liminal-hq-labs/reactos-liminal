# Source patches

This folder holds source patches against the ReactOS tree that express, in the form a ReactOS developer would use, the same changes the binary patchers make: replaced bitmaps under `dll/win32/msgina/resources/`, `dll/win32/syssetup/resources/` and `base/setup/reactos/res/`, the edited `SysColors[]` table in `win32ss/gdi/ntgdi/stockobj.c`, the cursor resources in `win32ss/user/user32/resources/`, and any later change of the same kind. None exist yet.

## Licence

**Everything in this folder is licensed GPL-2.0-or-later**, the licence of the ReactOS files the patches modify. This is the one exception to the repository's `Apache-2.0 OR MIT` licence. The GPL-2.0 text is in the ReactOS source tree (`COPYING`) and at <https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt>.

## Rules

- Patches are against one pinned upstream release, today ReactOS 0.4.16 (tag `0.4.16-release`), in `patches/reactos-0.4.16/`.
- Each patch file starts with a header naming the files it changes, the date of the change and that the change is by Liminal HQ Labs, as GPL-2.0 section 2(a) asks.
- CI checks every patch applies cleanly to the tag (`git apply --check`) and that the bitmaps in it hash to the pinned Afterglow manifest.
- No ReactOS source file, whole or in part beyond the patch context, is committed anywhere else in the repository.
