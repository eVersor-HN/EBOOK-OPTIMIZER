# EBOOK-OPTIMIZER

[![Release](https://img.shields.io/github/v/release/eVersor-HN/EBOOK-OPTIMIZER?color=0e7b7b)](https://github.com/eVersor-HN/EBOOK-OPTIMIZER/releases/latest)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](#system-requirements)

**EBOOK-OPTIMIZER** shrinks e-books and comics for e-ink readers, and converts them to the format
your device actually reads. It rewrites the images inside EPUBs and comic archives for a specific
panel — downscaling, greyscale, quantisation — strips what the device will never use, and hands
the result to Calibre when a different container is needed. A 35-page colour comic goes from
83 MB to 6 MB. A plain-text novel is left untouched, because there is nothing to gain. Everything
runs on your machine: no cloud, no account, no telemetry.

> **Open source.** Licensed under the **GNU General Public License v3.0** — free to use, study,
> modify and redistribute under the same terms. See [LICENSE](LICENSE).

Author / copyright: **© 2026 eVersor-HN**.
This is the **official** distribution repository:
**https://github.com/eVersor-HN/EBOOK-OPTIMIZER**

---

## Contents

[Honest about what it can and cannot do](#honest-about-what-it-can-and-cannot-do) ·
[Download & install](#download--install) ·
[Verify authenticity](#-verify-authenticity-sha-256) ·
[Usage](#usage) ·
[Features](#features) ·
[Options](#options) ·
[System requirements](#system-requirements) ·
[Limits](#limits) ·
[Build & test from source](#build--test-from-source) ·
[Support](#support) ·
[Acknowledgements](#acknowledgements) ·
[License](#license)

---

## Honest about what it can and cannot do

Compression tools tend to report a saving on every file. This one does not, because on some files
there is nothing honest to report.

| File | Before | After | Change |
|---|---|---|---|
| Colour comic, 35 pages | 83.0 MB | 6.0 MB | −92.8 % |
| Same volume, greyscale scan | 49.2 MB | 6.0 MB | −87.9 % |
| Webtoon long strips | 3.7 MB | 2.3 MB | −38.9 % |
| Illustrated book, 29 colour plates | 1.4 MB | 1005 KB | −31.8 % |
| Halftone photo book, 59 images | 1.2 MB | 1.0 MB | −15.5 % |
| Plain-text novel | 183 KB | unchanged | 0 % |

Measured on Windows 11 / Python 3.13 / Pillow 12.2 with 8 workers, on public-domain and Creative
Commons files, so the numbers can be reproduced.

The bottom two rows matter most. The halftone book is a set of 1897 screened scans; re-encoded at
quality 80 they **grow by about 13 %**, because a halftone dot pattern is exactly what JPEG
handles worst. 53 of its 59 images are therefore left alone. A plain novel has no images at all,
so the original is kept byte-for-byte. **If a file cannot be made smaller, the original is what
you get back.**

---

## Download & install

1. Open the [**Releases**](https://github.com/eVersor-HN/EBOOK-OPTIMIZER/releases) page and
   download the latest asset.
2. **Verify it is the genuine file** (see below) before using it.
3. Unpack it anywhere and install Pillow:

```bash
pip install pillow
```

From source instead:

```bash
git clone https://github.com/eVersor-HN/EBOOK-OPTIMIZER.git
cd EBOOK-OPTIMIZER
pip install pillow
```

### Updating

Download the newest release and unpack it over the old folder, or `git pull`. There is no
auto-update. The command line and web interface keep no state; plugin settings live in Calibre's
own configuration and survive an update.

---

## ✅ Verify authenticity (SHA-256)

The same hash appears in three places and must match byte-for-byte: the release notes, this
README, and [`SHA256SUMS.txt`](SHA256SUMS.txt).

**`EBOOK-OPTIMIZER-0.2.0.zip` — SHA-256:**

```
7fe1dca95cf0a884bb46302584f69e4216526d85472e1264c169075c5cc0e678
```

```powershell
# Windows (PowerShell)
Get-FileHash .\EBOOK-OPTIMIZER-0.2.0.zip -Algorithm SHA256
```

```bash
# macOS                                    # Linux
shasum -a 256 EBOOK-OPTIMIZER-0.2.0.zip    sha256sum EBOOK-OPTIMIZER-0.2.0.zip
```

The printed hash must match, case-insensitive. If it does not, do not use the file — it is not
the genuine build.

---

## Usage

### Web interface

```bash
python -m ebook_optimizer.web
```

Opens `http://127.0.0.1:8756`. Pick a whole folder — recursively if you want — or individual
files, choose the target device and output format, and watch the per-file results come in. The
server binds to localhost only; it is a user interface, not a network service. On Windows you can
double-click `start-web.bat` instead.

### Command line

```bash
# Dry run: calculate the saving, write nothing
python -m ebook_optimizer.cli ~/Books -r -n

# Optimise a whole library, keeping each file's format
python -m ebook_optimizer.cli ~/Books -r

# Optimise and convert to Kindle format
python -m ebook_optimizer.cli manga.cbr --to azw3

# Kobo, written as .kepub.epub the way Kobo expects
python -m ebook_optimizer.cli book.epub --to kepub -p kobo_clara_bw

# What can this machine produce?
python -m ebook_optimizer.cli --list-formats
```

### Calibre plugin

```bash
python build_plugin.py
```

In Calibre: *Preferences → Plugins → Load plugin from file* →
`dist/EBOOK-OPTIMIZER-calibre-plugin.zip*`, then restart. The plugin adds a toolbar button that
optimises the selected books.

---

## Features

### Image pipeline

- **Device-aware downscaling.** Images are fitted to the target panel (1072×1448 on a PocketBook
  Verse Pro) and never upscaled. Landscape double-page spreads rotate the target box so they are
  fitted along their long edge instead of being crushed.
- **Long-strip detection.** An image more than twice as tall, relative to its width, as the
  screen ratio is treated as a webtoon strip and constrained *by width only*. Forcing an 800×3403
  strip into screen height would leave 340×1448 — unreadable.
- **Greyscale and quantisation.** E-ink shows no colour, and a Carta panel resolves 16 grey
  levels; storing more than that is wasted space.
- **Format chosen by measurement.** In `auto` mode JPEG is encoded first because it is cheap,
  then PNG is probe-encoded at `compress_level=1`. The expensive optimised PNG encode only runs
  when that probe shows PNG can still win. The smaller result is kept.
- **Size regression guard.** If the result is larger than the input, the original bytes are kept,
  whether or not the format changed.

### Containers

- **EPUB** — embedded fonts removed along with their `@font-face` rules and OPF manifest entries;
  PNG/GIF/WebP rewritten to JPEG including every reference in OPF, XHTML and CSS; `mimetype` kept
  as the first, uncompressed entry, because some readers reject the file otherwise.
- **Comics** — CBZ/CBR/CBT/CB7 in, CBZ out. Natural page ordering (`p2` before `p10`),
  `ComicInfo.xml` preserved, optional right-to-left reading direction, output written with
  `ZIP_STORED` since deflating JPEGs costs time and saves nothing.
- **Damage avoidance** — transparency, animated GIFs and corrupt images are detected and skipped
  rather than destroyed. Junk (`__MACOSX`, `.DS_Store`, `Thumbs.db`) is dropped. An image whose
  base name occurs in two folders is optimised but never renamed, because references are rewritten
  by file name.

### Format conversion

20 output formats — EPUB, KEPUB, AZW3, MOBI, PDF, FB2, DOCX, RTF, TXT and more — from 49 input
formats, delegated to Calibre's `ebook-convert`. The order of operations is deliberate:

| Source → target | Order | Why |
|---|---|---|
| Comic → anything | optimise, then convert | Calibre's comic input fits every page to screen height, which destroys long strips. It is called with `--no-process` and only packages the result. |
| Any → EPUB/KEPUB | convert, then optimise | Those containers can be reopened and their images replaced. |
| Any → AZW3/MOBI/PDF | optimise, then convert | Those cannot be reopened, so images must already be small before Calibre seals them in. |

### Speed

- `Image.draft()` lets the JPEG decoder scale during decoding instead of building the full-size
  image and shrinking it afterwards: **3.6× faster**, with marginally smaller output.
- Pages are distributed across CPU cores, falling back to serial processing wherever no process
  pool can start, such as embedded interpreters or piped scripts.
- A 54 MB, 24-page comic: **4.04 s → 0.97 s** between 0.1.0 and 0.2.0, output 5.8 % smaller.

---

## Options

| Option | Effect |
|---|---|
| `-p, --profile` | Target device (default `pb_verse_pro`) |
| `-t, --to` | Output format — `epub`, `kepub`, `azw3`, `mobi`, `pdf`, `cbz`, … |
| `-q, --quality` | JPEG quality 1–100 (default 80) |
| `-r, --recursive` | Walk sub-folders |
| `-o, --out-dir` | Output folder (default: `optimiert` beside the source) |
| `-j, --jobs` | Parallel workers (default: core count, capped at 8) |
| `--in-place` | Replace originals, keeping numbered `.bak` backups |
| `--fonts strip\|keep` | Remove embedded fonts (default) or keep them |
| `--png-mode keep\|auto\|jpeg` | Keep format / smaller result wins (default) / always JPEG |
| `--keep-color` | Skip greyscale conversion |
| `--no-quantize` | Do not reduce PNGs to 16 grey levels |
| `--manga` | Comics: right-to-left reading direction |
| `--no-progressive` | Baseline instead of progressive JPEG |
| `-n, --dry-run` | Calculate only, write nothing |
| `--list-formats` | Print available output formats and exit |

Device profiles: `pb_verse_pro`, `pb_verse`, `kobo_clara_bw`, `kobo_clara_colour`,
`generic_6in_300ppi`.

---

## System requirements

| | |
|---|---|
| **Python** | 3.8 or newer |
| **Pillow** | `pip install pillow` — the only required dependency |
| **Calibre** | Needed **only** for format conversion. Optimising EPUB, KEPUB and CBZ works without it. |
| **CBR input** | Needs an unpacker: the `rarfile` module, or `unrar` / `7z` / `bsdtar` on `PATH`. |
| **OS** | Windows, macOS, Linux |

Calibre is located automatically through `PATH` and the usual install locations. When it is
missing, the web interface says so at the top of the page, the command line says so in its
header, and every conversion reports it clearly instead of failing part-way through.

---

## Limits

Worth knowing before you point this at a library of several thousand files:

- **Progressive JPEG is on by default** and is worth about 6 %. Very old e-ink devices can
  struggle to decode it. Check one file on your device after the first run; if something fails to
  display, use `--no-progressive`.
- **`--in-place` keeps numbered `.bak` files** and never overwrites an existing one, but that is
  not a substitute for a real backup.
- **The Calibre plugin has not run inside a real Calibre yet.** `test_calibre_stub.py` exercises
  the plugin code against stand-in Calibre APIs, which catches import, naming and logic errors
  but cannot confirm that Calibre's own APIs behave as assumed. Please
  [open an issue](https://github.com/eVersor-HN/EBOOK-OPTIMIZER/issues) if loading it fails.
- **`@font-face` detection uses a regular expression.** Nested blocks are vanishingly rare in
  practice but would be a blind spot.
- **The Qt image backend is untested.** It only comes into play if Calibre ships without Pillow,
  which normally does not happen.
- **Savings vary enormously with content.** Text-only novels save nothing; illustrated non-fiction
  and comic scans save a great deal.

---

## Build & test from source

```bash
python build_plugin.py                           # build the Calibre plugin zip
python make_testdata.py                          # generate synthetic fixtures
python test_edge.py                              # edge cases
python test_calibre_stub.py                      # plugin code against stand-in Calibre APIs
python verify.py out/book.epub out/comic.cbz 8   # structural integrity of written files
```

`test_edge.py` covers alpha preservation, animated GIFs, corrupt images, CMYK, 1-bit images,
no-upscaling, double-page spreads, natural page ordering, CBT reading, CBR without an unpacker,
the size regression guard and ambiguous file names.

`verify.py` checks ZIP integrity, `mimetype` position and compression, OPF parsability, manifest
completeness, media types against actual image content, dangling references, font removal, image
dimensions and greyscale mode, comic page count and ordering, and `ComicInfo.xml` validity.

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Release history is in
[CHANGELOG.md](CHANGELOG.md).

---

## Support

Bug reports and questions belong in
[GitHub Issues](https://github.com/eVersor-HN/EBOOK-OPTIMIZER/issues).

If it saved you a weekend of disk-space triage and you want to say thanks:

| | |
|---|---|
| **Ko-fi** | [ko-fi.com/eversorhn](https://ko-fi.com/eversorhn) |
| **PayPal** | [paypal.me/FAMarco](https://paypal.me/FAMarco) |
| **Bitcoin** | `bc1qv92c3eyeqvhgfnez7spfd7v2aytkhpshsl65yv` |

Entirely optional, and it changes nothing about the software.

---

## Acknowledgements

- [**Calibre**](https://calibre-ebook.com) by Kovid Goyal, which performs all format conversion
  here.
- [**Kindle Comic Converter**](https://github.com/ciromattia/kcc) (ISC), used as a reference when
  deciding which techniques were worth adopting. No code was taken. Its margin cropping was
  deliberately *not* adopted: measured here, it removes about 31 % of page area while making files
  about 64 % **larger**, because a white margin compresses to almost nothing while the content it
  exposes does not. It is a legibility feature, not a compression one.
- Test corpus: [*Pepper&Carrot*](https://www.peppercarrot.com) by David Revoy (CC-BY 4.0) and
  [Project Gutenberg](https://www.gutenberg.org) (public domain).

---

## License

**GNU General Public License v3.0** — see [LICENSE](LICENSE). GPL-3 is required here because the
Calibre plugin links against Calibre's own GPL-3 APIs.
