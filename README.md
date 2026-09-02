# Ebook Optimizer (EO)

**Shrink e-books and comics for e-readers — then convert them to whatever your device actually reads.**

A local, offline tool that rewrites the images inside EPUBs and comic archives for a specific
e-ink panel, strips what the device will never use, and hands the result to Calibre when you need
a different container. Nothing is uploaded, nothing phones home, and no file is ever written back
larger than it started.

Open source under **GPL-3.0** — architecture, methods and measurements are all in the open below.

> 💸 You just watched 40 GB of library evaporate into 4, and the only number that stayed exactly the same was the amount you have donated.
> **PayPal:** paypal.me/FAMarco
> **Bitcoin:** `bc1qv92c3eyeqvhgfnez7spfd7v2aytkhpshsl65yv`

---

## Measured, not promised

Every number below was measured on real files on a normal desktop, not estimated. The sample
corpus is public-domain and Creative Commons material, so anyone can reproduce it.

| File | Before | After | Saved |
|---|---|---|---|
| Colour comic, 35 pages (CC-BY) | 83.0 MB | 6.0 MB | **−92.8 %** |
| Same volume as a greyscale scan | 49.2 MB | 6.0 MB | **−87.9 %** |
| Webtoon long strips | 3.7 MB | 2.3 MB | **−39.3 %** |
| Illustrated book, 29 colour plates | 1.4 MB | 1005 KB | **−31.8 %** |
| Halftone photo book, 59 images | 1.2 MB | 1.0 MB | **−15.5 %** |
| Plain-text novel | 183 KB | *untouched* | correct |

The last two rows matter more than the first. A 1897 halftone scan **grows by ~13 %** when
re-encoded at quality 80 — its high-frequency screen pattern is exactly what JPEG handles worst.
53 of those 59 images were therefore left alone. A plain novel has nothing to compress, so the
original is kept byte-for-byte. **A tool that reports a saving on those files is lying to you.**

---

## Before you start: Calibre

Optimising **EPUB, KEPUB and CBZ** works standalone — Python and Pillow, nothing else.

**Converting between formats requires [Calibre](https://calibre-ebook.com) to be installed.**
Calibre's `ebook-convert` covers 49 input and 20 output formats and has been in the field for
close to two decades. Reimplementing that would produce a worse converter, so the division of
labour is deliberate: **Calibre converts, we optimise.** Calibre is located automatically via
`PATH` and the usual install locations on Windows, macOS and Linux. If it is missing, every
conversion path says so clearly instead of failing halfway through.

---

## Download & install

```bash
git clone https://github.com/eVersor-HN/ebook-optimizer.git
cd ebook-optimizer
pip install pillow
```

Start the local interface:

```bash
python -m ebook_optimizer.web
```

It serves on `http://127.0.0.1:8756` and opens your browser. The server binds to localhost only —
it is a user interface, not a network service.

Command line, same engine:

```bash
python -m ebook_optimizer.cli D:\Books -r -n          # dry run: what would this save?
python -m ebook_optimizer.cli D:\Books -r             # do it
python -m ebook_optimizer.cli manga.cbr --to epub     # convert as well
python -m ebook_optimizer.cli --list-formats          # what can this machine produce?
```

As a **Calibre plugin**: build the ZIP with `python build_plugin.py`, then load
`dist/ebook-optimizer-calibre-plugin.zip` via *Preferences → Plugins → Load plugin from file*.

### Updating

`git pull` and restart. Plugin settings live in Calibre's own configuration; the CLI and the web
interface are stateless.

---

## ✅ Verify authenticity (SHA-256)

The release asset is the only file you need to check. The authoritative value appears in the
release notes and in `SHA256SUMS.txt` in this repository — all three must match byte-for-byte.

```powershell
Get-FileHash .\ebook-optimizer-0.2.0.zip -Algorithm SHA256
```

If the printed hash does not match, do not use the file — it is not the genuine build.

---

## Features

### Image pipeline

- **Device-aware downscaling.** Images are fitted to the target panel (1072×1448 for a PocketBook
  Verse Pro), never upscaled. Landscape double-page spreads rotate the target box so they are
  fitted along their long edge instead of being crushed.
- **Long-strip detection.** An image more than twice as tall relative to its width as the screen
  ratio is treated as a webtoon strip and constrained **by width only**. Forcing an 800×3403
  strip into screen height leaves 340×1448 — unreadable. The reader scrolls; the strip stays
  intact.
- **Greyscale conversion**, because an e-ink panel shows nothing else, plus optional quantisation
  to the 16 grey levels the panel can actually display.
- **Format chosen by measurement.** In `auto` mode JPEG is encoded first (it is cheap), then PNG
  is probe-encoded at `compress_level=1`. Only if that probe lands within striking distance is
  the expensive optimised PNG produced. The smaller file wins — never an assumption that "PNG is
  always worse".
- **Never larger than the original.** If the result is bigger, the original bytes are kept —
  regardless of whether the format changed. This is the rule that saves halftone scans.

### Containers

- **EPUB:** embedded fonts removed along with their `@font-face` rules and OPF manifest entries;
  PNG/GIF/WebP rewritten to JPEG including every reference in OPF, XHTML and CSS; `mimetype` kept
  as the first, uncompressed entry, or some readers reject the file.
- **Comics:** CBZ / CBR / CBT / CB7 in, CBZ out. Natural page ordering (`p2` before `p10`),
  `ComicInfo.xml` preserved, optional right-to-left manga reading direction, output stored with
  `ZIP_STORED` because deflating JPEGs costs time and saves nothing.
- **Junk removal:** `__MACOSX`, `.DS_Store`, `Thumbs.db`.
- **Damage avoidance:** transparency, animated GIFs and corrupt images are detected and skipped
  rather than destroyed.
- **Ambiguity guard:** references are rewritten by file name, so an image whose base name occurs
  in two folders is optimised but never renamed — otherwise the rewrite would hit the wrong file.

### Format conversion (requires Calibre)

20 output formats including **EPUB, KEPUB** (real Kobo spans, written as `.kepub.epub`), **AZW3,
MOBI, PDF, FB2, DOCX, RTF, TXT** and more, from 49 input formats.

The **order of operations** is not cosmetic:

- **Comic source → us first, Calibre second, always.** Calibre's comic input fits every page to
  screen height, which turns a webtoon strip into mush. We optimise; Calibre then only packages
  the result, with `--no-process`.
- **Target EPUB/KEPUB → convert first, optimise second.** We can open those containers.
- **Target AZW3/MOBI/PDF → optimise first, convert second.** We cannot reopen those, so the images
  must already be small before Calibre seals them in.

### Speed

- `Image.draft()` lets the JPEG decoder scale during decoding instead of building the full-size
  image and shrinking it afterwards: **3.6× faster**, with output marginally *smaller*.
- Pages are spread across CPU cores, falling back to serial processing wherever no process pool
  can start (embedded interpreters, piped scripts).
- Measured end to end on a 54 MB, 24-page comic: **4.04 s → 0.97 s (4.2×), output 5.8 % smaller.**

### Interface

Local web UI: pick a **whole folder** (recursive optional) or individual files, choose device and
output format, watch progress, read per-file results and the total. Everything runs inside your
own Python process.

---

## Tuning

| Option | Effect |
|---|---|
| `-p, --profile` | Target device (default `pb_verse_pro`) |
| `-t, --to` | Output format — `epub`, `kepub`, `azw3`, `mobi`, `pdf`, `cbz`, … |
| `-q, --quality` | JPEG quality 1–100 (default 80) |
| `-r, --recursive` | Walk sub-folders |
| `-o, --out-dir` | Output folder (default: `./optimiert`) |
| `-j, --jobs` | Parallel workers (default: core count, max 8) |
| `--in-place` | Replace originals, keeping numbered `.bak` backups |
| `--fonts strip\|keep` | Remove embedded fonts (default) or keep them |
| `--png-mode keep\|auto\|jpeg` | Keep format / smaller wins (default) / always JPEG |
| `--keep-color` | Skip greyscale conversion |
| `--no-quantize` | Do not reduce PNGs to 16 grey levels |
| `--manga` | Comics: right-to-left reading direction |
| `--no-progressive` | Baseline instead of progressive JPEG (see below) |
| `-n, --dry-run` | Calculate only, write nothing |

**Progressive JPEG is on by default** and worth about 6 %. Very old e-ink devices can struggle
with progressive decoding. Check one file on your device after the first run; if something fails
to display, use `--no-progressive`.

---

## System requirements

- **Python 3.8+** and **Pillow** (`pip install pillow`)
- **Calibre** — only for format conversion, not for optimising EPUB/KEPUB/CBZ
- **CBR input** needs an unpacker: the `rarfile` module, or `unrar` / `7z` / `bsdtar` in `PATH`.
  Without one you get a clear error, not a crash.
- Windows, macOS and Linux. Developed and measured on Windows 11 / Python 3.13 / Pillow 12.2.

---

## Tests

```bash
python make_testdata.py                            # synthetic fixtures
python test_edge.py                                # edge cases: alpha, animation, corrupt files, ordering
python test_calibre_stub.py                        # plugin code against stand-in Calibre APIs
python verify.py out/book.epub out/comic.cbz 8     # structural integrity of the output
```

`verify.py` checks ZIP integrity, `mimetype` position and compression, OPF parsability, manifest
completeness, media types against actual image content, dangling references, font removal, image
dimensions and greyscale mode, comic page count and ordering, and `ComicInfo.xml` validity.

---

## Credits & license

Techniques were compared against [Kindle Comic Converter](https://github.com/ciromattia/kcc)
(ISC). No code was taken — the findings were re-measured here, and KCC's most prominent feature,
margin cropping, was deliberately **not** adopted: it removes ~31 % of page area while making
files ~64 % *larger*, because the white margin compresses to almost nothing and the content it
exposes does not. It is a legibility feature, not a compression one.

Sample corpus: *Pepper&Carrot* by David Revoy (CC-BY 4.0) and Project Gutenberg (public domain).

Licensed under the **GNU General Public License v3.0** — see [LICENSE](LICENSE). GPL-3 is required
here because the Calibre plugin links against Calibre's own GPL-3 APIs.
