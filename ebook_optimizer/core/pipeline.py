"""Verbindet Konvertieren und Optimieren in der richtigen Reihenfolge.

Die Reihenfolge ist nicht beliebig:

* Comic als Quelle -> immer zuerst wir, dann Calibre. Calibres
  Comic-Eingabe passt sonst jede Seite an die Bildschirmhoehe an; bei
  einem 800x3403-Webtoonstreifen kommen dabei 316x1448 heraus, also
  Matsch. Mit --no-process verpackt Calibre nur noch, was wir liefern.
* Zielformat ist EPUB oder KEPUB -> erst konvertieren, dann optimieren.
  Diese Behaelter koennen wir oeffnen und die Bilder darin anfassen.
* Zielformat ist AZW3, MOBI, PDF ... -> erst optimieren, dann konvertieren.
  Dort kommen wir nachtraeglich nicht mehr hinein, also muessen die Bilder
  schon vorher klein sein.

Damit ist das Ergebnis in jedem Fall so klein wie moeglich - und bleibt
lesbar.
"""

import os
import shutil
import tempfile

from . import convert as conv
from .cbz import COMIC_EXT, optimize_comic
from .epub import optimize_epub
from .util import ext_of

EPUB_EXT = {'.epub', '.kepub'}
# Behaelter, die wir selbst oeffnen und verkleinern koennen.
OPTIMIZABLE = {'epub', 'kepub', 'cbz'}

# Calibre soll unsere bereits optimierten Comicseiten nicht noch einmal
# anfassen - sonst skaliert es Langstreifen auf Bildschirmhoehe kaputt.
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
    """Dateiname fuers Zielformat. Kobo will .kepub.epub sehen."""
    fmt = fmt.lstrip('.').lower()
    if fmt == 'kepub':
        return stem + '.kepub.epub'
    return stem + '.' + fmt


def _optimize_container(src, dst, fmt, profile, opts):
    """Verkleinert einen Behaelter, den wir oeffnen koennen."""
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
        return rep, '%s, %d/%d Seiten' % (rep.source_format, rep.pages_changed,
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
    return rep, '%d/%d Bilder, %d Fonts raus' % (
        rep.images_changed, rep.images, rep.fonts_removed)


def process(src, dst, profile, target_fmt=None, **opts):
    """Verarbeitet eine Datei nach dst.

    target_fmt: Zielformat ohne Punkt ('epub', 'azw3', ...). None = Format
                beibehalten (Comics werden immer zu CBZ).
    Rueckgabe: Result
    """
    res = Result(src)
    ext = ext_of(src)
    is_comic = ext in COMIC_EXT

    # --- Zielformat bestimmen -------------------------------------------
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

        # --- Fall 1: Comic als Quelle -----------------------------------
        # Immer zuerst unsere Optimierung, danach hoechstens noch verpacken.
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

        # --- Fall 2: Behaelter, den wir oeffnen koennen ------------------
        elif fmt in OPTIMIZABLE:
            if conv.needs_conversion(ext, fmt):
                # Die Endung entscheidet: '.kepub' erzeugt Kobos Variante,
                # '.epub' ein gewoehnliches EPUB. Fuer unsere Optimierung
                # sind danach beide gleich zu behandeln.
                mid = os.path.join(tmpdir, 'konvertiert.' + fmt)
                conv.convert(work, mid, profile=profile)
                res.converted_from = ext.lstrip('.')
                work = mid
            rep, detail = _optimize_container(work, dst, 'epub', profile, opts)
            res.detail = detail
            res.notes = list(getattr(rep, 'notes', []))

        # --- Fall 3: verschlossenes Zielformat ---------------------------
        else:
            # Erst so klein wie moeglich machen, dann verpacken lassen.
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
