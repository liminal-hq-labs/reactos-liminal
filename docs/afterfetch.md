# afterfetch

`afterfetch` is a small command in the image that prints an Afterglow sunset in ASCII beside a few facts about the system, in the style of neofetch. Type `afterfetch` at any command prompt.

```text
                 .   .   .
           .      \  :  /      .            administrator@reactos
               .   \ : /   .                ----------------------
                .:########:.                OS:       ReactOS 0.4.16-x86
            .:##############:.              Kernel:   NT 5.2.3790 SP3
           :##################:             Uptime:   0d 0h 1m
       ====:##################:====         Memory:   387 MB free of 511 MB
      ----------------------------------    Display:  1024 x 768
       ~~~~  ~~~~~~~~~  ~~~~~~~  ~~~~       Shell:    cmd.exe
         ~~~~~~~  ~~~~~~~~~~  ~~~~~~
            ~~~~~~~~~~  ~~~~~~~~~
               ~~~~~~~~~~~~~~
```

## Where it comes from

The source is [`guest/cmd/afterfetch.cmd`](../guest/cmd/afterfetch.cmd), authored here and licensed like the rest of the repository. The base recipe writes it to `ReactOS/system32/afterfetch.cmd` with a `[[files]]` entry, so it is on the `PATH`. A recipe that extends the base and lists its own `[[files]]` replaces that list and repeats the entry to keep the command ([recipes.md](recipes.md)).

## What it prints

| Row | Source |
|---|---|
| user and computer | `whoami`, which prints `computer\user` |
| OS, kernel | the two lines `ver` prints after its banner (the release, and the NT version ReactOS answers to) |
| Uptime | `uptime` |
| Memory | the two `Physical Memory` lines of `systeminfo`, which takes a few seconds |
| Display | the adapter's `DefaultSettings.XResolution` and `YResolution`, which the image's `display` registry file sets for the Bochs-style adapter QEMU and v86 provide; another adapter shows a dash |

Every row has a fallback, so a missing tool or key leaves a dash instead of an error.

## Colours

The output uses whatever colours the console has. The image's console table is the Afterglow Dusk palette (`ColorTable00`–`15`, `ScreenColors`), so the text is the palette's pale foreground on its navy background. `cmd.exe` can colour only the whole screen, not part of a line, so the logo is one colour.

## What this ReactOS `cmd.exe` taught

Written against ReactOS 0.4.16 and checked by running it in QEMU:

- `>nul` and `2>nul` fail with "Can't redirect to file /dev/null", so `systeminfo`'s warning about the product id goes to a temporary file in `%TEMP%`.
- `for /f` runs a command in single quotes and takes `usebackq` for a quoted file name; a `[` or `]` in `delims` is a syntax error, so the NT version's closing bracket is removed with `%KERNEL:]=%`.
- The days from `uptime` arrive padded with spaces, so a second `for` trims them.
- A batch file with Unix line endings runs, so the file is stored as the repository stores everything else.
