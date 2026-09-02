"""EPUB optimisation for e-ink devices.

What it does:
  * scale images to the panel, convert to greyscale, re-encode
  * remove embedded fonts, including @font-face rules and OPF manifest
    entries
  * optionally rewrite PNG/GIF/WebP to JPEG, updating every reference

Structure and metadata are otherwise left alone.
"""

import posixpath
import re
import zipfile

from .imaging import EXT_FOR_FMT, MIME_FOR_FMT, RASTER_EXT
from .pool import optimize_many
from .util import ext_of, is_junk

FONT_EXT = {'.ttf', '.otf', '.woff', '.woff2', '.ttc', '.eot'}
TEXT_EXT = {'.xhtml', '.html', '.htm', '.xml', '.opf', '.ncx', '.css', '.svg'}
STORED_EXT = RASTER_EXT | {'.woff', '.woff2'}

FONT_FACE_RE = re.compile(r'@font-face\s*\{[^{}]*\}', re.I | re.S)
# Nested @font-face blocks essentially do not occur in practice.


class EpubReport:
    def __init__(self, path):
        self.path = path
        self.old_size = 0
        self.new_size = 0
        self.images = 0
        self.images_changed = 0
        self.fonts_removed = 0
        self.converted = 0
        self.notes = []

    @property
    def saved(self):
        return self.old_size - self.new_size


def _decode(data):
    for enc in ('utf-8', 'utf-16', 'latin-1'):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return None, None


def _strip_font_faces(text):
    return FONT_FACE_RE.sub('', text)


def _rewrite_refs(text, renames):
    """Replace old file names with new ones in href/src/url()."""
    for old, new in renames.items():
        o = posixpath.basename(old)
        n = posixpath.basename(new)
        if o == n:
            continue
        text = re.sub(r'(?<![\w.-])' + re.escape(o) + r'(?![\w])', n, text)
    return text


def _patch_opf(text, renames, removed):
    """Update the manifest: drop fonts, fix renamed images."""
    # Delete removed entries, the whole <item> tag.
    for href in removed:
        base = re.escape(posixpath.basename(href))
        text = re.sub(
            r'<item\b[^>]*href\s*=\s*["\'][^"\']*' + base + r'["\'][^>]*/?>'
            r'(?:</item>)?',
            '', text, flags=re.I)
    # Renames: file name plus media-type.
    for old, new in renames.items():
        ob = re.escape(posixpath.basename(old))
        nb = posixpath.basename(new)
        fmt = None
        for f, e in EXT_FOR_FMT.items():
            if nb.lower().endswith(e):
                fmt = f
                break
        mime = MIME_FOR_FMT.get(fmt, 'image/jpeg')

        def _fix(m, ob=ob, nb=nb, mime=mime):
            tag = m.group(0)
            tag = re.sub(ob, nb, tag)
            tag = re.sub(r'media-type\s*=\s*["\'][^"\']*["\']',
                         'media-type="%s"' % mime, tag, flags=re.I)
            return tag

        text = re.sub(r'<item\b[^>]*href\s*=\s*["\'][^"\']*' + ob + r'["\'][^>]*/?>',
                      _fix, text, flags=re.I)
    return text


def optimize_epub(src, dst, profile, quality=80, png_to_jpeg=False,
                  fonts='strip', force_grayscale=None, quantize_gray=True,
                  skip_smaller_than=4096, progressive=True, jobs=1):
    """Optimise an EPUB file.

    fonts: 'strip' to remove them, 'keep' to leave them in place.
    skip_smaller_than: leave images below this size untouched.
    jobs: process images in parallel (1 = serial).
    Returns an EpubReport.
    """
    import os
    rep = EpubReport(src)
    rep.old_size = os.path.getsize(src)

    with zipfile.ZipFile(src, 'r') as zin:
        names = zin.namelist()

        # References are rewritten by base name. If a base name occurs
        # more than once - image.png in two folders - a rename would also
        # hit the other file's references. Such images are therefore
        # optimised but never converted to another format.
        seen = {}
        for n in names:
            if not n.endswith('/') and ext_of(n) in RASTER_EXT:
                b = posixpath.basename(n).lower()
                seen[b] = seen.get(b, 0) + 1
        ambiguous = {b for b, c in seen.items() if c > 1}

        payload = {}          # name -> bytes
        renames = {}          # old name -> new name
        removed = []          # names that were removed (fonts)

        # --- Read everything in and sort it out --------------------------
        raw = {}              # name -> bytes, without fonts and junk
        to_opt = []           # images that will actually be optimised
        keep_fmt = set()      # images whose format has to stay
        for name in names:
            if name.endswith('/') or is_junk(name):
                continue
            data = zin.read(name)
            ext = ext_of(name)

            if ext in FONT_EXT and fonts == 'strip':
                removed.append(name)
                rep.fonts_removed += 1
                continue

            raw[name] = data
            if ext in RASTER_EXT:
                rep.images += 1
                if len(data) >= skip_smaller_than:
                    if posixpath.basename(name).lower() in ambiguous:
                        keep_fmt.add(name)
                        rep.notes.append(
                            '%s: name used more than once, format kept' % name)
                    to_opt.append((name, data))

        # --- Optimise the images, across cores where possible ------------
        done = {}
        common = dict(quality=quality, force_grayscale=force_grayscale,
                      quantize_gray=quantize_gray, progressive=progressive)
        done.update(optimize_many(
            [it for it in to_opt if it[0] not in keep_fmt], profile,
            jobs=jobs, png_to_jpeg=png_to_jpeg, **common))
        done.update(optimize_many(
            [it for it in to_opt if it[0] in keep_fmt], profile,
            jobs=jobs, png_to_jpeg=False, **common))

        # --- Put the results back in place -------------------------------
        for name, data in raw.items():
            res = done.get(name)
            if res is None:
                payload[name] = data
                continue
            ext = ext_of(name)
            if res.changed:
                rep.images_changed += 1
                new_name = name
                want_ext = EXT_FOR_FMT.get(res.fmt, ext)
                if want_ext != ext:
                    new_name = posixpath.splitext(name)[0] + want_ext
                    i = 1
                    while new_name in payload or new_name in names:
                        new_name = '%s_%d%s' % (
                            posixpath.splitext(name)[0], i, want_ext)
                        i += 1
                    renames[name] = new_name
                    rep.converted += 1
                payload[new_name] = res.data
            else:
                payload[name] = data
                if res.reason and res.reason not in ('kein Gewinn',):
                    rep.notes.append('%s: %s' % (name, res.reason))

        # --- Update the text files --------------------------------------
        if renames or removed:
            for name in list(payload):
                if ext_of(name) not in TEXT_EXT:
                    continue
                text, enc = _decode(payload[name])
                if text is None:
                    continue
                orig = text
                if removed and ext_of(name) in ('.css', '.xhtml', '.html', '.htm'):
                    text = _strip_font_faces(text)
                if name.lower().endswith('.opf'):
                    text = _patch_opf(text, renames, removed)
                elif renames:
                    text = _rewrite_refs(text, renames)
                if text != orig:
                    payload[name] = text.encode(enc or 'utf-8')

    # --- Write it back out -----------------------------------------------
    ordered = []
    if 'mimetype' in payload:
        ordered.append('mimetype')
    ordered += [n for n in payload if n != 'mimetype']

    with zipfile.ZipFile(dst, 'w') as zout:
        for name in ordered:
            data = payload[name]
            if name == 'mimetype':
                zi = zipfile.ZipInfo('mimetype')
                zi.compress_type = zipfile.ZIP_STORED
                zout.writestr(zi, data)
                continue
            comp = (zipfile.ZIP_STORED if ext_of(name) in STORED_EXT
                    else zipfile.ZIP_DEFLATED)
            zout.writestr(name, data, compress_type=comp)

    rep.new_size = os.path.getsize(dst)
    return rep
