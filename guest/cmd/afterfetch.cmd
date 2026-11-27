@echo off
rem afterfetch: an Afterglow logo and a few facts about this system, in the console's own colours.
rem Runs in the ReactOS command prompt (cmd.exe); installed in %SystemRoot%\system32, so it is on the PATH.
rem Every fact has a fallback, so a missing tool or key leaves a dash rather than an error.
rem
rem (c) Copyright 2026 Liminal HQ, Scott Morris
rem SPDX-License-Identifier: Apache-2.0 OR MIT
setlocal

set WHO=-
set HOST=-
set OSNAME=ReactOS
set KERNEL=-
set UPTIME=-
set MEMORY=-
set DISPLAY=-

rem Who and where: whoami prints computer\user.
for /f "tokens=1,2 delims=\" %%a in ('whoami') do set HOST=%%a& set WHO=%%b

rem The release and the NT version it answers to, from the two lines `ver` prints after its banner:
rem   Version 0.4.16-x86 ...
rem   Running on: ReactOS [Version 5.2.3790] Service Pack 3
for /f "tokens=1,2,5,8" %%a in ('ver') do (
	if "%%a"=="Version" set OSNAME=ReactOS %%b
	if "%%a"=="Running" set KERNEL=NT %%c SP%%d
)
set KERNEL=%KERNEL:]=%

rem Uptime: "System Up Time:   0 days, 0 Hours, 1 Minutes, 54 Seconds". The number of days arrives padded with spaces, so a second
rem loop trims it.
for /f "tokens=4,6,8 delims=:, " %%a in ('uptime') do for %%d in (%%a) do set UPTIME=%%dd %%bh %%cm

rem Memory: the two "Physical Memory" lines of systeminfo, which takes a few seconds. This ReactOS cmd cannot redirect to nul, so
rem its warning about the product id goes to a file, and the two lines pass through another.
set AFTMP=%TEMP%\afterfetch
systeminfo 2> "%AFTMP%.err" | find "Physical Memory" > "%AFTMP%.txt"
for /f "usebackq tokens=1,4* delims=: " %%a in ("%AFTMP%.txt") do (
	if "%%a"=="Total" set MEMTOTAL=%%b %%c
	if "%%a"=="Available" set MEMFREE=%%b %%c
)
del "%AFTMP%.err" "%AFTMP%.txt"
if defined MEMTOTAL set MEMORY=%MEMFREE% free of %MEMTOTAL%

rem The display: the adapter's default settings, which the image sets (a DWORD printed as 0x400).
set DISPLAYKEY=HKLM\SYSTEM\CurrentControlSet\Services\bochsmp\Device0
for /f "tokens=3" %%a in ('reg query "%DISPLAYKEY%" /v DefaultSettings.XResolution ^| find "REG_DWORD"') do set /a WIDTH=%%a
for /f "tokens=3" %%a in ('reg query "%DISPLAYKEY%" /v DefaultSettings.YResolution ^| find "REG_DWORD"') do set /a HEIGHT=%%a
if defined WIDTH if defined HEIGHT set DISPLAY=%WIDTH% x %HEIGHT%

set RULE=----------------------

echo.
echo.                 .   .   .
echo.           .      \  :  /      .            %WHO%@%HOST%
echo.               .   \ : /   .                %RULE%
echo.                .:########:.                OS:       %OSNAME%
echo.            .:##############:.              Kernel:   %KERNEL%
echo.           :##################:             Uptime:   %UPTIME%
echo.       ====:##################:====         Memory:   %MEMORY%
echo.      ----------------------------------    Display:  %DISPLAY%
echo.       ~~~~  ~~~~~~~~~  ~~~~~~~  ~~~~       Shell:    cmd.exe
echo.         ~~~~~~~  ~~~~~~~~~~  ~~~~~~
echo.            ~~~~~~~~~~  ~~~~~~~~~
echo.               ~~~~~~~~~~~~~~
echo.
endlocal
