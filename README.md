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

**36 device profiles** across Kindle, Kobo, PocketBook, Boox, Tolino, Nook and reMarkable.
There is no fixed quality setting: every image is measured and gets the lowest quality that still
looks untouched on the panel.

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
[Devices](#devices) ·
[Quality: measured, not set](#quality-measured-not-set) ·
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
| Colour comic, 35 pages | 83.0 MB | 4.7 MB | −94.4 % |
| Same volume, greyscale scan | 49.2 MB | 4.7 MB | −90.5 % |
| Illustrated novel, 164 images | 23.7 MB | 19.1 MB | −19.5 % |
| Webtoon long strips | 3.7 MB | 2.1 MB | −43.8 % |
| Illustrated book, 29 colour plates | 1.4 MB | 608 KB | −58.7 % |
| Halftone photo book, 59 images | 1.2 MB | 978 KB | −21.4 % |
| Novel with a cover and no other images | 183 KB | 157 KB | −14.3 % |

Measured on Windows 11 / Python 3.13 / Pillow 12.2 with 8 workers, on public-domain and Creative
Commons files, so the numbers can be reproduced.

Normal books are not a special case: the illustrated novel is *Pride and Prejudice* with 164
figures, and it behaves like everything else. A book whose only image is its cover still saves
something; a file that genuinely cannot be made smaller is returned untouched. **If a file cannot
be made smaller, the original is what you get back.**

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

**`EBOOK-OPTIMIZER-0.4.2.zip` — SHA-256:**

```
4a8f36792b7155b99f6e80bf7620c1636de7731955834ff213a3b0459eb5e136
```

```powershell
# Windows (PowerShell)
Get-FileHash .\EBOOK-OPTIMIZER-0.4.2.zip -Algorithm SHA256
```

```bash
# macOS                                    # Linux
shasum -a 256 EBOOK-OPTIMIZER-0.4.2.zip    sha256sum EBOOK-OPTIMIZER-0.4.2.zip
```

The printed hash must match, case-insensitive. If it does not, do not use the file — it is not
the genuine build.

---

## Usage

### Web interface

```bash
python -m ebook_optimizer.web
```

Opens `http://127.0.0.1:8756`. **Choose folder** and **Choose files** open your system's own
dialog, or you can type a path. Four steps and then one button: **what to convert** — a whole
folder, recursively if you want, or individual files — **which device**, **how hard to compress**,
**which output format**, then Go. Progress and per-file results appear as they arrive. The
interface is light by default and follows your system's dark mode. The server binds to localhost
only; it is a user interface, not a network service. On Windows you can double-click
`start-web.bat` instead.

### Command line

```bash
# Dry run: calculate the saving, write nothing
python -m ebook_optimizer.cli ~/Books -r -n

# Optimise a whole library, keeping each file's format
python -m ebook_optimizer.cli ~/Books -r

# Trade a little softness for much smaller files
python -m ebook_optimizer.cli ~/Books -r --target smaller

# Optimise and convert to Kindle format
python -m ebook_optimizer.cli manga.cbr --device kindle_pw_12 --to azw3

# Kobo, written as .kepub.epub the way Kobo expects
python -m ebook_optimizer.cli book.epub --device kobo_libra_2 --to kepub

# What is available on this machine?
python -m ebook_optimizer.cli --list-devices
python -m ebook_optimizer.cli --list-targets
python -m ebook_optimizer.cli --list-formats
```

### Calibre plugin

```bash
python build_plugin.py
```

In Calibre: *Preferences → Plugins → Load plugin from file* →
`dist/EBOOK-OPTIMIZER-calibre-plugin.zip`, then restart. The plugin adds a toolbar button that
optimises the selected books.

---

## Devices

36 profiles, each holding the panel's native resolution and whether it shows colour. Pick one with
`--device`, or from the dropdown in the interface. `--list-devices` prints the keys.

| Brand | Models |
|---|---|
| **Kindle** | 11th gen · Paperwhite 10th/11th/12th gen · Oasis 3 · Colorsoft · Scribe |
| **Kobo** | Nia · Clara HD/2E · Clara BW · Clara Colour · Libra 2 · Libra Colour · Sage · Elipsa 2E |
| **PocketBook** | Verse · Verse Pro · Touch HD 3 · Era · InkPad 4 · InkPad Color 3 |
| **Boox** | Palma · Page · Note Air series · Tab Ultra series |
| **Tolino** | Page 2 · Shine 5 · Vision 6 |
| **Nook** | GlowLight 4 · GlowLight 4e |
| **reMarkable** | 2 · Paper Pro |
| **Generic** | 6" · 7" · 8" · 10.3" fallbacks |

Colour devices (Kaleido and Gallery panels) keep their colour; every monochrome panel gets
greyscale, because it cannot show anything else.

---

## Quality: measured, not set

There is no fixed quality number in this tool, because a fixed number is wrong for most images.
Measured across comic pages, manga pages, webtoon strips, watercolour plates, 1897 halftone scans
and an illustrated novel, the quality needed to look untouched on a 16-level e-ink panel ranges
from **45 to 85, depending entirely on the image**. Quality 80 wastes 40 % of the bytes on a flat
watercolour plate and is not quite enough for a detailed halftone page.

So each image is encoded a few times and keeps the lowest quality that still meets your target:

| Target | Budget | What it means |
|---|---|---|
| **Looks the same** *(default)* | 0.10 % | Indistinguishable on the device |
| **Clearly smaller** | 0.75 % | A touch softer on close inspection, much smaller files |

The budget is the share of pixels allowed to land **two or more grey levels** away from the
reference, once both are reduced to the 16 levels an e-ink panel can actually display. A single
level of difference is the smallest step the panel can make and does not count, because it cannot
be seen.

This costs about three extra JPEG encodes per image — a 35-page, 83 MB comic takes 2.3 s instead
of 1.6 s — and returns roughly **7 % smaller files than a fixed quality of 80**, with every image
meeting the same visible standard instead of the same number.

`--quality N` pins a fixed quality and switches the measurement off.

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

### Formats

Every combination below is checked by `test_formats.py`, which generates a source file in each
format with Calibre and runs it through the tool.

**19 input formats produce an optimised EPUB:** AZW3, DOCX, EPUB, FB2, HTMLZ, KEPUB, LIT, LRF,
MOBI, PDB, PDF, PMLZ, RB, RTF, SNB, TCR, TXT, TXTZ, ZIP — plus CBZ, CBR, CBT and CB7 as comics.

**PDF works**, including PDFs with both text and images: Calibre extracts what it can and the
images are then optimised like any others. How well a PDF converts depends on the PDF, since a
PDF carries no structure of its own.

Two honest limits:

- **CBZ output is refused for books.** CBZ is a comic container; asking for a novel in one gets a
  readable error rather than a broken file.
- **CB7 needs a 7z-capable unpacker.** On Windows 10 and later nothing extra is required - the
  system's own `tar.exe` is bsdtar and reads 7z. Elsewhere, `7z` or `bsdtar` on `PATH` covers it.
- **TXT, TCR, PDB and TXTZ store text only.** Converting into one throws every image away. The
  tool says so in the result rather than reporting a spectacular saving.

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
| `-d, --device` | Target device (default `pb_verse_pro`); `-p, --profile` still works |
| `-c, --target` | `identical` (default) or `smaller` — how the result should look |
| `-t, --to` | Output format — `epub`, `kepub`, `azw3`, `mobi`, `pdf`, `cbz`, … |
| `-q, --quality` | Pin a fixed JPEG quality and switch the per-image measurement off |
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
| `--list-devices` | Print every device profile and exit |
| `--list-targets` | Explain the quality targets and exit |
| `--list-formats` | Print available output formats and exit |

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
- **The Calibre plugin loads and registers in a real Calibre** (verified on Calibre 9.14,
  Windows). The toolbar action itself is covered by `test_calibre_stub.py` against stand-in
  Calibre APIs. Please
  [open an issue](https://github.com/eVersor-HN/EBOOK-OPTIMIZER/issues) if anything misbehaves.
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
python test_formats.py                           # every input and output format (needs Calibre)
python test_devices.py                           # all 36 devices x optimisation, conversion, quality modes
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
