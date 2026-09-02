# What's New in EBOOK-OPTIMIZER

Built forward. Tracked clearly. Newest first.

---

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
