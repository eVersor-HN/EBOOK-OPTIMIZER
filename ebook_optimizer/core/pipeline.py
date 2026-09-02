"""Combines conversion and optimisation in the right order.

The order is not arbitrary:

* Comic source -> always us first, Calibre second. Calibre's comic
  input otherwise fits every page to screen height; an 800x3403 webtoon
  strip comes out as 316x1448, which is mush. With --no-process Calibre
  only packages what we hand it.
* Target is EPUB or KEPUB -> convert first, optimise second. Those
  containers can be opened and their images replaced.
* Target is AZW3, MOBI, PDF ... -> optimise first, convert second. We
  cannot get back into those, so the images have to be small already.

That keeps the result as small as possible in every case - and readable.
"""

import os
import shutil
import tempfile

from . import convert as conv
from .cbz import COMIC_EXT, optimize_comic
from .epub import optimize_epub
from .util import ext_of

EPUB_EXT = {'.epub', '.kepub'}
# Containers we can open and shrink ourselves.
OPTIMIZABLE = {'epub', 'kepub', 'cbz'}

# Calibre must not touch our already optimised comic pages again, or it
# will scale long strips down to screen height and ruin them.
COMIC_PASSTHROUGH = ['--no-process', '--keep-aspect-ratio',
                     '--disable-trim', '--dont-sharpen']


class Result:
    def __init__(self, src):
        self.src = src
        self.dst = None
        self.old_size = os.path.getsize(src) if os.path.exists(src) else 0
        self.new_size = 0
        self.converted_from = None
        self.converted_to = None
        self.detail = ''
        self.notes = []

    @property
    def saved(self):
        return self.old_size - self.new_size


def target_name(stem, fmt):
    """File name for the target format. Kobo expects .kepub.epub."""
    fmt = fmt.lstrip('.').lower()
    if fmt == 'kepub':
        return stem + '.kepub.epub'
    return stem + '.' + fmt


def _optimize_container(src, dst, fmt, profile, opts):
    """Shrink a container we are able to open."""
    if fmt == 'cbz':
        rep = optimize_comic(
            src, dst, profile,
            quality=opts.get('quality', 80),
            to_jpeg=opts.get('png_mode', 'auto'),
            force_grayscale=opts.get('force_grayscale'),
            manga=opts.get('manga', False),
            quantize_gray=opts.get('quantize_gray', True),
            progressive=opts.get('progressive', True),
            jobs=opts.get('jobs', 1))
        return rep, '%s, %d/%d pages' % (rep.source_format, rep.pages_changed,
                                         rep.pages)
    rep = optimize_epub(
        src, dst, profile,
        quality=opts.get('quality', 80),
        png_to_jpeg=opts.get('png_mode', 'auto'),
        fonts=opts.get('fonts', 'strip'),
        force_grayscale=opts.get('force_grayscale'),
        quantize_gray=opts.get('quantize_gray', True),
        progressive=opts.get('progressive', True),
        jobs=opts.get('jobs', 1))
    return rep, '%d/%d images, %d fonts removed' % (
        rep.images_changed, rep.images, rep.fonts_removed)


def process(src, dst, profile, target_fmt=None, **opts):
    """Process one file into dst.

    target_fmt: output format without the dot ('epub', 'azw3', ...).
                None keeps the format; comics always become CBZ.
    Returns a Result.
    """
    res = Result(src)
    ext = ext_of(src)
    is_comic = ext in COMIC_EXT

    # --- Decide the target format ---------------------------------------
    if target_fmt:
        fmt = target_fmt.lstrip('.').lower()
    elif is_comic:
        fmt = 'cbz'
    else:
        fmt = ext.lstrip('.').lower()
    res.converted_to = fmt

    tmpdir = tempfile.mkdtemp(prefix='ebook_opt_pipe_')
    try:
        work = src

        # --- Case 1: comic source ---------------------------------------
        # Our optimisation first, packaging at most afterwards.
        if is_comic:
            if fmt == 'cbz':
                rep, detail = _optimize_container(work, dst, 'cbz', profile,
                                                  opts)
            else:
                mid = os.path.join(tmpdir, 'klein.cbz')
                rep, detail = _optimize_container(work, mid, 'cbz', profile,
                                                  opts)
                extra = list(COMIC_PASSTHROUGH)
                if opts.get('manga'):
                    extra.append('--right2left')
                conv.convert(mid, dst, profile=profile, extra_args=extra)
                res.converted_from = ext.lstrip('.')
            res.detail = detail
            res.notes = list(getattr(rep, 'notes', []))

        # --- Case 2: a container we can open ----------------------------
        elif fmt in OPTIMIZABLE:
            if conv.needs_conversion(ext, fmt):
                # The extension decides: '.kepub' produces Kobo's
                # variant, '.epub' an ordinary EPUB. For our optimisation
                # both are then handled the same way.
                mid = os.path.join(tmpdir, 'konvertiert.' + fmt)
                conv.convert(work, mid, profile=profile)
                res.converted_from = ext.lstrip('.')
                work = mid
            rep, detail = _optimize_container(work, dst, 'epub', profile, opts)
            res.detail = detail
            res.notes = list(getattr(rep, 'notes', []))

        # --- Case 3: a sealed target format ------------------------------
        else:
            # Make it as small as possible first, then let Calibre pack it.
            if ext not in EPUB_EXT:
                pre = os.path.join(tmpdir, 'zwischen.epub')
                conv.convert(work, pre, profile=profile)
                work = pre
            mid = os.path.join(tmpdir, 'klein.epub')
            rep, detail = _optimize_container(work, mid, 'epub', profile, opts)
            res.detail = detail
            res.notes = list(getattr(rep, 'notes', []))
            conv.convert(mid, dst, profile=profile)
            res.converted_from = ext.lstrip('.')

        res.dst = dst
        res.new_size = os.path.getsize(dst)
        return res
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
