"""Format matrix: what can actually go in, and what can come out.

Two questions this answers:

  1. Which input formats can be turned into an optimised EPUB?
  2. Which output formats can be produced from an EPUB?

Source files are generated with Calibre from one known-good EPUB, so the
test needs no copyrighted material. Formats Calibre cannot produce are
skipped rather than reported as failures.

Needs Calibre. Without it only EPUB, KEPUB and CBZ are possible and the
test says so instead of pretending.
"""

import os
import shutil
import sys
import tempfile
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ebook_optimizer.core import convert as conv          # noqa: E402
from ebook_optimizer.core.pipeline import process, target_name  # noqa: E402
from ebook_optimizer.core.profiles import get_profile     # noqa: E402

PROFILE = get_profile('pb_verse_pro')

# 'oeb' writes a folder rather than a file, so it has no place here.
SKIP_OUTPUT = {'oeb'}

# CBZ is a comic container; a book must be refused, not mangled.
EXPECT_REFUSED = {'cbz'}

# Formats worth trying as an input. Everything else Calibre reads is either
# a container we already cover or something it cannot write, so it cannot
# be generated for this test.
INPUT_CANDIDATES = ['azw3', 'docx', 'epub', 'fb2', 'htmlz', 'kepub', 'lit',
                    'lrf', 'mobi', 'pdb', 'pdf', 'pmlz', 'rb', 'rtf', 'snb',
                    'tcr', 'txt', 'txtz', 'zip']

FAILS = []


def line(*cols):
    print('%-10s %10s %10s %8s  %s' % cols)


def make_sources(src_epub, workdir):
    """Write the sample book out in every format Calibre can produce."""
    made = {}
    outs = set(conv.output_formats())
    for fmt in INPUT_CANDIDATES:
        if fmt == 'epub':
            dst = os.path.join(workdir, 'source.epub')
            shutil.copyfile(src_epub, dst)
            made[fmt] = dst
            continue
        if fmt not in outs:
            continue
        dst = os.path.join(workdir, 'source.' + fmt)
        try:
            conv.convert(src_epub, dst, profile=PROFILE, timeout=300)
            if os.path.getsize(dst) > 0:
                made[fmt] = dst
        except Exception:
            pass                       # cannot be generated, so cannot be tested
    return made


def to_epub(sources, workdir):
    print('')
    print('INPUT -> optimised EPUB')
    line('format', 'in', 'out', 'change', 'note')
    print('-' * 62)
    ok = 0
    for fmt in sorted(sources):
        src = sources[fmt]
        dst = os.path.join(workdir, 'out_%s.epub' % fmt)
        try:
            t = time.perf_counter()
            r = process(src, dst, PROFILE, target_fmt='epub',
                        png_mode='auto', target_error=0.10, jobs=4)
            el = time.perf_counter() - t
            pct = (r.new_size - r.old_size) / float(r.old_size) * 100
            line(fmt, '%.0f KB' % (r.old_size / 1024),
                 '%.0f KB' % (r.new_size / 1024), '%+.0f%%' % pct,
                 '%.1fs  %s' % (el, r.detail))
            ok += 1
        except Exception as e:
            line(fmt, '-', '-', '-', 'FAILED: %s' % str(e)[:40])
            FAILS.append('%s -> epub' % fmt)
    print('%d of %d input formats produced an EPUB' % (ok, len(sources)))


def from_epub(src_epub, workdir):
    print('')
    print('EPUB -> every output format')
    line('format', 'in', 'out', 'change', 'note')
    print('-' * 62)
    ok = 0
    targets = sorted((set(conv.output_formats()) | {'cbz'}) - SKIP_OUTPUT)
    for fmt in targets:
        stem = os.path.join(workdir, 'to_%s' % fmt)
        dst = target_name(stem, fmt)
        try:
            t = time.perf_counter()
            r = process(src_epub, dst, PROFILE, target_fmt=fmt,
                        png_mode='auto', target_error=0.10, jobs=4)
            el = time.perf_counter() - t
            pct = (r.new_size - r.old_size) / float(r.old_size) * 100
            note = '%.1fs' % el
            if r.notes:
                note += '  ! ' + r.notes[0][:34]
            if fmt in EXPECT_REFUSED:
                line(fmt, '-', '-', '-',
                     'should have been refused but was not')
                FAILS.append('epub -> %s was not refused' % fmt)
                continue
            line(fmt, '%.0f KB' % (r.old_size / 1024),
                 '%.0f KB' % (r.new_size / 1024), '%+.0f%%' % pct, note)
            ok += 1
        except Exception as e:
            if fmt in EXPECT_REFUSED:
                # CBZ holds comic pages, so a novel has no business in one.
                # Refusing with a readable reason is the correct outcome.
                line(fmt, '-', '-', 'n/a',
                     'refused, as expected: %s' % str(e)[:28])
                ok += 1
                continue
            line(fmt, '-', '-', '-', 'FAILED: %s' % str(e)[:40])
            FAILS.append('epub -> %s' % fmt)
    print('%d of %d output formats behaved correctly' % (ok, len(targets)))


def pdf_stays_pdf(sources, workdir):
    """A PDF kept as PDF must go through the in-place image rewrite,
    not through the destructive text converter."""
    if 'pdf' not in sources:
        return
    print('')
    print('PDF stays PDF (image rewrite, no text conversion)')
    from ebook_optimizer.core.pdf import pikepdf_available
    if not pikepdf_available():
        print('  pikepdf not installed - skipped')
        return
    dst = os.path.join(workdir, 'pdf_roundtrip.pdf')
    r = process(sources['pdf'], dst, PROFILE, target_fmt='pdf',
                target_error=0.10)
    ok = 'images rewritten' in r.detail and os.path.getsize(dst) > 1000
    print('  %s  (%s)' % ('ok' if ok else 'FAIL', r.detail))
    if not ok:
        FAILS.append('pdf stays pdf')


def main():
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'testdata', 'testbuch.epub')
    if not os.path.exists(src):
        print('Run make_testdata.py first.')
        return 1
    if not conv.available():
        print('Calibre not found. Only EPUB, KEPUB and CBZ are possible '
              'without it, so there is no format matrix to test.')
        print('Install it from https://calibre-ebook.com')
        return 0

    print('Calibre: %s' % conv.version())
    workdir = tempfile.mkdtemp(prefix='ebook_opt_fmt_')
    try:
        print('Generating source files...')
        sources = make_sources(src, workdir)
        print('%d source formats available: %s'
              % (len(sources), ', '.join(sorted(sources))))
        to_epub(sources, workdir)
        from_epub(sources['epub'], workdir)
        pdf_stays_pdf(sources, workdir)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print('')
    if FAILS:
        print('%d combination(s) failed: %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('EVERY FORMAT COMBINATION WORKED')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
