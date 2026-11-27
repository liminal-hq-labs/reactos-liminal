# afterfetch

`afterfetch` is a small command in the image that prints an Afterglow sunset beside a few facts about the system, in the style of neofetch, in colour. Type `afterfetch` at any command prompt. The sun runs from gold through orange to coral at the horizon, a rose line, then water that darkens from lilac through violet and periwinkle to slate; two rows of swatches show the console's 16 colours.

```text
                 .   .   .
           .      \  :  /      .          administrator@reactos
               .   \ : /   .              ---------------------
                .:########:.              OS:       ReactOS 0.4.16-x86
            .:##############:.            Kernel:   NT 5.2.3790 SP3
           :##################:           Uptime:   0d 0h 1m
       ====:##################:====       Memory:   387 MB free of 511 MB
      ----------------------------------  Display:  1024 x 768, 32-bit
       ~~~~  ~~~~~~~~~  ~~~~~~~  ~~~~     Shell:    cmd.exe
         ~~~~~~~  ~~~~~~~~~~  ~~~~~~
            ~~~~~~~~~~  ~~~~~~~~~
               ~~~~~~~~~~~~~~
```

The text above is what the program writes when its output is not a console (a pipe or a file): plain ASCII, no swatches. On a console the `#` cells are solid colour.

## Two commands, one name

The image holds both `afterfetch.exe` (the program, in colour) and `afterfetch.cmd` (a batch fallback that prints plain text). The command prompt searches `PATHEXT`, which is `.COM;.EXE;.BAT;.CMD` in this ReactOS, so `afterfetch` runs the `.exe`; type `afterfetch.cmd` for the batch version. Checked in the guest: `afterfetch` with both present printed the coloured picture.

## The program

The source is [`tools/afterfetch`](../tools/afterfetch), Rust, authored here and licensed like the rest of the repository.

- **No C runtime, no standard library.** `no_std` and `no_main`, a `start` entry point, and a handful of Win32 imports (`kernel32`, `advapi32`, `user32`, `gdi32`) listed in `imports.allow`. `check.sh` fails on any import off that list, on a wide-character entry point, on a C runtime and on an instruction a Pentium lacks. The subsystem is console 4.0, so it also runs on Windows 9x and NT. The executable is about 8.5 KB.
- **Built for a Pentium.** `core` is compiled from source for an `i586` target with MMX, SSE and x87 off, because the prebuilt one assumes SSE2. The linker is the toolchain's own `rust-lld` (flavour `lld-link`), so no system linker is needed.
- **Pure parts and a thin shell.** `lib.rs` holds the palette, the logo, the formatting of each fact and the layout, with no Windows call; `main.rs` gathers the facts and backs the layout with the console. `cargo test --lib` runs the pure parts on the host.

## Colours

Colour is the console's own attributes: `SetConsoleTextAttribute` before each run of text, so the same call works on ReactOS, Windows NT and Windows 9x. The image sets the console's 16-colour table from the Afterglow Dusk palette (`ColorTable00`–`15`, from Afterglow's `afterglow-original.reg`), so a colour index is an Afterglow colour:

| Role | Index | Dusk colour |
|---|---|---|
| Sun, top | 14 | `#ffd08e` gold |
| Sun, lower | 6 | `#ffaa40` orange |
| Sun at the horizon | 12 | `#f995a6` coral |
| Horizon line | 4 | `#f43f5e` rose |
| Water, near | 13 | `#e4b8f8` lilac |
| Water, middle | 5 | `#c98be6` violet |
| Water, deep | 1 | `#7f95f2` periwinkle |
| Water, darkest, quiet text | 8 | `#7c8796` slate |

The unit tests hold this table against the Dusk values, so an index cannot drift off its colour. The sun's body is a space on a coloured background (a solid cell), so it needs no font glyph. The background is the console's own, and the attribute at start is read with `GetConsoleScreenBufferInfo` and put back at the end of every line and at exit, so the prompt keeps its colours (and a scroll cannot paint the new line). A console too narrow for both columns gets the facts without the logo.

## What it prints

| Row | Source |
|---|---|
| user and computer | `GetUserNameA`, `GetComputerNameA`, in lower case |
| OS | the registry's `ProductName`, and the release from `BuildLab` (`20260829-0.4.16-release-…`), with `-x86` for an Intel 32-bit processor (`GetSystemInfo`) |
| Kernel | `GetVersionExA`: NT major.minor.build, and the service pack's number |
| Uptime | `GetTickCount`, as days, hours and minutes; the count is 32 bits, so it wraps after 49 days |
| Memory | `GlobalMemoryStatus`: free and total physical memory in whole megabytes |
| Display | `GetSystemMetrics` for the size and `GetDeviceCaps` for the colour depth: the mode the desktop is in, not the registry's default |
| Shell | the file name of `%COMSPEC%` |

Each is native, so it is instant (the batch version waits several seconds for `systeminfo`) and reads the real value rather than a registry default. A value that cannot be read prints a dash.

## How it reaches the image

`rl image` builds it from source as the first step ([pipeline.md](pipeline.md)), with `tools/afterfetch/build.sh` and the project's own pinned toolchain (Rust 1.98.0, `rust-src`, `llvm-tools`; `rustup` installs it from `rust-toolchain.toml`). The base recipe's `[builds.afterfetch]` pins the SHA-256 of the output, `[[files]]` writes it with `source = "built:afterfetch"`, and `./rl pin` measures the pin. The build is reproducible: built twice in different directories, the two files are byte-identical (a fixed link timestamp, no debug information, no build path in panic text), which is what lets the output be pinned. No binary is committed. `./rl doctor` reports `rustup`, `cargo` and whether the pinned toolchain has `rust-src` and `rust-lld`. Building takes about six seconds once `core` has been compiled.

A recipe that extends the base and lists its own `[[files]]` replaces the base list ([recipes.md](recipes.md)); it repeats the two `afterfetch` entries to keep the command. `built:afterfetch` works there, because the base recipe declares the build.

CI builds it in the shared Rust image (`.github/workflows/ci.yml`, job `afterfetch.exe`): rustfmt, clippy, the unit tests, the build, the executable checks and a second build in another directory that must match.

## The batch fallback

[`guest/cmd/afterfetch.cmd`](../guest/cmd/afterfetch.cmd) prints the same picture in one colour (`cmd.exe` can colour only the whole screen). It takes its facts from `whoami`, `ver`, `uptime`, `systeminfo` and the display adapter's registry key. What this ReactOS `cmd.exe` taught while it was written:

- `>nul` and `2>nul` fail with "Can't redirect to file /dev/null", so `systeminfo`'s warning about the product id goes to a temporary file in `%TEMP%`.
- `for /f` runs a command in single quotes and takes `usebackq` for a quoted file name; a `[` or `]` in `delims` is a syntax error, so the NT version's closing bracket is removed with `%KERNEL:]=%`.
- The days from `uptime` arrive padded with spaces, so a second `for` trims them.
- A batch file with Unix line endings runs, so the file is stored as the repository stores everything else.
