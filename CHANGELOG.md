# What's New in EBOOK-OPTIMIZER

Built forward. Tracked clearly. Newest first.

---

## 0.4.2 · 2026-09-02

- **The Calibre plugin is confirmed to load in a real Calibre** (9.14, Windows). Until now that
  was only covered by tests against stand-in APIs.
- **New device matrix test** (`test_devices.py`): all 36 device profiles run through EPUB and CBZ
  optimisation with the results opened and validated, through an AZW3 conversion exercising every
  per-brand Calibre profile mapping, through both quality targets and a pinned quality, and
  through the CBZ, CBT and CB7 comic containers. Everything passes.
- Writing that test pinned down one deliberate subtlety of the contract: when every re-encode of
  an image would be larger than the source, the untouched original is kept even if it exceeds the
  panel. That honours the size promise and is visually optimal - the reader scales at display
  time. The test now asserts exactly this.

## 0.4.1 · 2026-09-02

- **CB7 comics actually work now.** The README claimed CB7 support but the comic scanner never
  recognised the extension. On Windows 10 and later they now work out of the box, because the
  system ships bsdtar as `System32	ar.exe` and bsdtar reads 7z - the tool just had to know to
  look for it under that name.
- A leftover German string comparison flooded the per-file notes with one "no gain" line per
  unchanged image. Notes are quiet again.
- An unknown `--to` format is rejected up front with the list of available ones, instead of
  failing once per file inside Calibre.
- AZW3/MOBI conversion now hands Calibre the right output profile per brand - Kindle models map
  to Calibre's Kindle profiles, Kobo to Kobo, PocketBook to PocketBook - instead of everything
  being treated as a generic panel. Calibre sizes covers and margins from this.
- The web server no longer keeps every finished job in memory forever.
- Dead code removed, the last German comments translated.

## 0.4.0 · 2026-09-02

- **The quality is no longer a setting.** Every image is now encoded a few times and keeps the
  lowest quality that still looks untouched on the panel. Measured across comic pages, manga
  pages, webtoon strips, watercolour plates, 1897 halftone scans and an illustrated novel, the
  quality an image actually needs ranges from 45 to 85 — a single fixed number is wrong for most
  of them. The four presets are gone; two targets remain, *Looks the same* and *Clearly smaller*,
  and `--quality N` still pins a fixed value.
- Results: colour comic −94.4 % (was −92.8 %), watercolour plates −58.7 % (was −31.8 %), halftone
  photo book −21.4 % (was −15.5 %). About 7 % smaller overall than a fixed quality of 80, at the
  cost of roughly 45 % more processing time.
- **Choose folder / Choose files really open the system dialog now.** In 0.3.2 the buttons were
  there but a server left running from an earlier version served the new page with old Python
  behind it, so the request 404'd and the error was hidden in a small status line. Errors are now
  shown as a banner, and the page warns outright when the server is running an older version.
- **New `test_formats.py`**: generates a source file in every format Calibre can write and runs
  each one through the tool. 19 input formats produce an optimised EPUB, and all 20 output
  formats behave correctly.
- **PDF in, EPUB out works**, including PDFs with text and images.
- **CBZ output is refused for books** with a readable reason instead of failing deep inside
  Calibre. CBZ is a comic container.
- **TXT, TCR, PDB and TXTZ discard every image**, which the result now says out loud rather than
  reporting it as a saving of 100 %.

## 0.3.2 · 2026-09-02

- **Choose folder** and **Choose files** buttons now open your operating system's own dialog. The
  button next to the path field used to be labelled "Open", which read like it should open a file
  dialog while it only jumped to whatever was already typed in the field - so with an empty field
  it appeared to do nothing at all. It is now labelled "Show", and the real picker sits above it.
- "Open folder" after a run now reports it when the folder is gone instead of silently claiming
  success.

## 0.3.1 · 2026-09-02

- A second recursive run no longer picks up its own output. The default `optimized` folder sits
  inside the folder you scanned, so the first run's results were being optimised all over again.
  Output folders are now skipped when walking, including one named explicitly with `--out-dir`.

## 0.3.0 · 2026-09-02

- The whole tool is now in English: interface, command line, messages and source.
- The interface is light by default, with a calmer palette, and follows your system's dark mode
  instead of forcing one look.
- The interface now walks you through four steps - what to convert, which device, how hard to
  compress, which output format - and then one Go button.
- **36 device profiles across 8 brands** instead of 5: Kindle (including Paperwhite 11th and 12th
  generation, Oasis, Colorsoft and Scribe), Kobo (Nia through Elipsa 2E), PocketBook, Onyx Boox,
  Tolino, Nook, reMarkable, plus generic 6", 7", 8" and 10.3" fallbacks.
- **Compression presets** - Maximum quality, Balanced, Small, Smallest - derived from measurements
  rather than taste. Each one states what it actually costs, and manual control is still there.
- Quality was measured across a colour comic page, a greyscale manga page, a webtoon strip, a
  watercolour plate and an 1897 halftone scan. Above quality 85 files grow steeply with nothing
  visible left to gain on an e-ink panel; below 60 fine halftone artwork starts to suffer first.
- `--list-devices` and `--list-presets` print what is available, with the measured numbers.
- `--device` is the new name for `--profile`, which still works.
- Output folders are now called `optimized` rather than `optimiert`.

## 0.2.0 · 2026-09-02

- Format conversion: 20 output formats including EPUB, KEPUB, AZW3, MOBI, PDF, FB2 and DOCX, from
  49 input formats, using Calibre's converter. Optimising EPUB, KEPUB and CBZ still works without
  Calibre installed.
- Kobo KEPUB files are produced with real Kobo spans and written as `.kepub.epub`, the way Kobo
  devices expect them.
- New local web interface at `http://127.0.0.1:8756`: choose a whole folder or individual files,
  pick the device and output format, watch per-file progress and results. Starts with
  `python -m ebook_optimizer.web` or `start-web.bat`.
- Comics are now optimised before Calibre ever sees them. Calibre's comic input fits every page
  to screen height, which turned webtoon long strips into unreadable slivers.
- Webtoon long strips are recognised and constrained by width only, so an 800×3403 strip keeps its
  proportions instead of being squeezed into 340×1448.
- Roughly four times faster: JPEGs are decoded at reduced size, the expensive PNG encode is only
  attempted when a quick probe shows it can still win, and pages are spread across CPU cores. A
  54 MB, 24-page comic went from 4.04 s to 0.97 s, with 5.8 % smaller output.
- Progressive JPEG is now the default, worth about 6 %. `--no-progressive` restores the old
  behaviour for very old devices.
- A file is never written back larger than it started, even when the image format changed. This
  previously only held when the format stayed the same, so converting a PNG to JPEG could grow it.
- Scanning a folder no longer sweeps up plain text, HTML and Markdown. Calibre can read those, so
  pointing the scanner at a library used to convert every README and stray note alongside the
  books.
- Images whose file name occurs in more than one folder are optimised but no longer renamed.
  References are rewritten by file name, so renaming one would have broken the other.
- `--in-place` no longer overwrites an existing `.bak`. Backups are numbered instead, so a second
  run cannot destroy the only surviving original.
- The command line and web interface both state whether Calibre was found, and which formats are
  available without it.
- `verify.py` no longer needs `lxml`; the standard library covers everything it checks.
- Files that grow are reported with a correct sign instead of `--0.1%`.
- New `test_calibre_stub.py` runs the plugin code against stand-in Calibre APIs, covering the
  entire background job with real EPUB and CBZ files.

## 0.1.0 · 2026-09-02

- First release. Optimises EPUB and comic archives for e-ink readers.
- Images are downscaled to the target panel and never upscaled; landscape double-page spreads are
  fitted along their long edge.
- Greyscale conversion, with optional quantisation to the 16 grey levels an e-ink panel can show.
- Embedded fonts and their `@font-face` rules are removed, including the matching OPF manifest
  entries.
- PNG, GIF and WebP can be rewritten to JPEG, with every reference updated across OPF, XHTML and
  CSS.
- CBZ, CBR and CBT are read and always written as CBZ, with natural page ordering, `ComicInfo.xml`
  preserved and optional right-to-left reading direction.
- Transparency, animated GIFs and corrupt images are skipped rather than damaged.
- Device profiles for PocketBook Verse Pro and Verse, Kobo Clara BW and Clara Colour, and a
  generic 6-inch 300 ppi panel.
- Runs as a Calibre plugin and as a standalone command line tool.
