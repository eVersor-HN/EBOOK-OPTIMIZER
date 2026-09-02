"""Standalone command line - runs without Calibre, needs only Pillow.

Examples:
    python -m ebook_optimizer.cli book.epub
    python -m ebook_optimizer.cli D:\\Library --recursive --preset small
    python -m ebook_optimizer.cli manga.cbr --to azw3 --manga
"""

import argparse
import os
import sys
import tempfile
import traceback

from .core import convert as conv
from .core.cbz import COMIC_EXT
from .core.imaging import backend_name
from .core.pipeline import process, target_name
from .core.pool import default_jobs
from .core.profiles import (DEFAULT_PROFILE, DEFAULT_TARGET, TARGET_ORDER,
                            TARGETS, get_profile, get_target,
                            profiles_by_brand)
from .core.util import ext_of, human_size, pct_saved

EPUB_EXT = {'.epub', '.kepub'}
NATIVE_EXT = EPUB_EXT | COMIC_EXT

# Calibre also reads .txt, .html and friends. When walking a folder that
# would be a trap: every README and stray note would be converted along
# with the books. Files named explicitly are still accepted.
SCAN_SKIP_EXT = {'.txt', '.text', '.htm', '.html', '.xhtm', '.xhtml',
                 '.md', '.markdown', '.textile', '.opf', '.recipe',
                 '.zip', '.rar', '.shtm', '.shtml'}

# Folders we write into ourselves. Without this a second recursive run
# would pick up its own output and optimise it all over again.
# 'optimiert' is the name earlier versions used.
OUTPUT_DIR_NAMES = {'optimized', 'optimiert'}


def all_ext(scanning=False):
    ext = set(NATIVE_EXT)
    if conv.available():
        ext |= {'.' + f for f in conv.input_formats()}
    if scanning:
        ext -= SCAN_SKIP_EXT
    return ext


CALIBRE_LIBRARY_WARNING = (
    "is a calibre library (it contains metadata.db). Editing the "
    "files behind calibre's back desynchronises its database, so "
    "this folder is skipped. Optimise these books inside calibre "
    "with the plugin, or export them first via Save to disk.")


def is_calibre_library(path):
    return os.path.isfile(os.path.join(path, 'metadata.db'))


def collect(paths, recursive, out_dir=None):
    exts = all_ext(scanning=True)
    named = all_ext()
    skip_dir = os.path.normcase(os.path.abspath(out_dir)) if out_dir else None
    out = []
    for p in paths:
        if os.path.isdir(p):
            if is_calibre_library(p):
                print('Skipped: %s %s' % (p, CALIBRE_LIBRARY_WARNING),
                      file=sys.stderr)
                continue
            if recursive:
                for root, dirs, files in os.walk(p):
                    if is_calibre_library(root):
                        print('Skipped: %s %s'
                              % (root, CALIBRE_LIBRARY_WARNING),
                              file=sys.stderr)
                        dirs[:] = []
                        continue
                    dirs[:] = [
                        d for d in dirs
                        if d.lower() not in OUTPUT_DIR_NAMES
                        and os.path.normcase(
                            os.path.abspath(os.path.join(root, d)))
                        != skip_dir]
                    for fn in sorted(files):
                        if ext_of(fn) in exts:
                            out.append(os.path.join(root, fn))
            else:
                for fn in sorted(os.listdir(p)):
                    full = os.path.join(p, fn)
                    if os.path.isfile(full) and ext_of(fn) in exts:
                        out.append(full)
        elif os.path.isfile(p):
            if ext_of(p) in named:
                out.append(p)
            else:
                print('Skipped, unknown format: %s' % p, file=sys.stderr)
        else:
            print('Not found: %s' % p, file=sys.stderr)
    return out


def target_path(src, args, fmt):
    stem = os.path.splitext(os.path.basename(src))[0]
    if args.in_place:
        return os.path.join(os.path.dirname(src), target_name(stem, fmt))
    out_dir = args.out_dir or os.path.join(os.path.dirname(src), 'optimized')
    if not args.dry_run:
        os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, target_name(stem + args.suffix, fmt))


def build_parser():
    ap = argparse.ArgumentParser(
        prog='EBOOK-OPTIMIZER',
        description='Shrink e-books and comics for e-ink readers, and '
                    'convert them to the format your device reads.')
    ap.add_argument('paths', nargs='*', help='files or folders')

    ap.add_argument('-d', '--device', '-p', '--profile', dest='profile',
                    default=DEFAULT_PROFILE, metavar='DEVICE',
                    help='target device (default %s). --list-devices shows '
                         'them all.' % DEFAULT_PROFILE)
    ap.add_argument('-c', '--target', choices=TARGET_ORDER,
                    default=DEFAULT_TARGET,
                    help='how the result should look (default %s). The '
                         'quality is then measured per image instead of '
                         'fixed. --list-targets explains it.'
                         % DEFAULT_TARGET)
    ap.add_argument('-t', '--to', metavar='FORMAT',
                    help='output format, e.g. epub, kepub, azw3, mobi, pdf, '
                         'cbz. Without it the format is kept; comics always '
                         'become CBZ. Anything but epub/kepub/cbz needs '
                         'Calibre.')
    ap.add_argument('-q', '--quality', type=int, metavar='1-100',
                    help='pin a fixed JPEG quality and switch the per-image '
                         'measurement off')
    ap.add_argument('-r', '--recursive', action='store_true',
                    help='walk sub-folders')
    ap.add_argument('-o', '--out-dir',
                    help='output folder (default: ./optimized)')
    ap.add_argument('--suffix', default='', help='suffix for output files')
    ap.add_argument('--in-place', action='store_true',
                    help='replace originals, keeping numbered .bak backups')
    ap.add_argument('--no-backup', action='store_true',
                    help='no .bak backup with --in-place')
    ap.add_argument('--fonts', choices=['strip', 'keep'], default='strip',
                    help='remove embedded fonts (default) or keep them')
    ap.add_argument('--png-mode', choices=['keep', 'auto', 'jpeg'],
                    default='auto',
                    help='image format: keep it, let the smaller result win '
                         '(default), or always JPEG')
    ap.add_argument('--keep-color', action='store_true',
                    help='keep colour, skip greyscale conversion')
    ap.add_argument('--no-quantize', action='store_true',
                    help='do not reduce PNGs to 16 grey levels')
    ap.add_argument('--manga', action='store_true',
                    help='comics: right-to-left reading direction')
    ap.add_argument('-j', '--jobs', type=int, default=default_jobs(),
                    help='parallel workers (default %d)' % default_jobs())
    ap.add_argument('--no-progressive', action='store_true',
                    help='baseline instead of progressive JPEG. Progressive '
                         'is about 6 %% smaller, but very old e-ink devices '
                         'can struggle with it.')
    ap.add_argument('-n', '--dry-run', action='store_true',
                    help='calculate only, write nothing')
    ap.add_argument('-v', '--verbose', action='store_true')

    ap.add_argument('--list-devices', action='store_true',
                    help='list device profiles and exit')
    ap.add_argument('--list-targets', action='store_true',
                    help='explain the quality targets and exit')
    ap.add_argument('--list-formats', action='store_true',
                    help='list available output formats and exit')
    return ap


def print_devices():
    print('Device profiles - use the key with --device:\n')
    for brand, group in profiles_by_brand():
        print('  %s' % brand)
        for p in group:
            print('    %-22s %-26s %4dx%-5d%s'
                  % (p.key, p.name, p.width, p.height,
                     '' if p.grayscale else '  colour'))
        print()


def print_targets():
    print('Quality targets - use the key with --target:\n')
    for key in TARGET_ORDER:
        t = TARGETS[key]
        mark = '   (default)' if key == DEFAULT_TARGET else ''
        print('  %-10s at most %.2f %% of pixels differ visibly%s'
              % (t.key, t.budget, mark))
        print('    %s' % t.summary)
        print('    %s' % t.measured)
        print()
    print('  There is no fixed quality behind these. Each image is encoded a')
    print('  few times and the lowest quality that still meets the target is')
    print('  kept, because the quality an image actually needs ranges from 45')
    print('  to 85 depending entirely on the image.')
    print('  "Differs visibly" means a pixel lands two or more grey levels')
    print('  away once reduced to the 16 levels an e-ink panel can show.')
    print('')
    print('  Use --quality N instead to pin one fixed quality.')


def print_formats():
    if conv.available():
        print('Calibre: %s' % conv.version())
        print('Output formats: %s'
              % ', '.join(sorted(set(conv.output_formats()) | {'cbz'})))
    else:
        print('Calibre not found. Without it only epub, kepub and cbz are '
              'possible.')
        print('Install it from https://calibre-ebook.com')


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)

    if args.list_devices:
        print_devices()
        return 0
    if args.list_targets:
        print_targets()
        return 0
    if args.list_formats:
        print_formats()
        return 0
    if not args.paths:
        ap.error('give at least one file or folder')

    try:
        profile = get_profile(args.profile)
        target = get_target(args.target)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2

    # A fixed --quality switches the per-image measurement off.
    if args.quality is not None:
        if not 1 <= args.quality <= 100:
            ap.error('--quality must be between 1 and 100')
        quality = args.quality
        target_error = None
    else:
        quality = 80              # only a fallback for formats without search
        target_error = target.budget
    quantize = target.quantize and not args.no_quantize

    target_fmt = args.to.lstrip('.').lower() if args.to else None
    if target_fmt and target_fmt not in ('epub', 'kepub', 'cbz'):
        if not conv.available():
            print('Output format "%s" needs Calibre, which was not found.'
                  % target_fmt, file=sys.stderr)
            print('Install it from https://calibre-ebook.com and try again.',
                  file=sys.stderr)
            return 2
        if target_fmt not in conv.output_formats():
            print('Unknown output format "%s". Available: %s'
                  % (target_fmt,
                     ', '.join(sorted(set(conv.output_formats()) | {'cbz'}))),
                  file=sys.stderr)
            return 2

    files = collect(args.paths, args.recursive, args.out_dir)
    if not files:
        print('No matching files found.')
        return 1

    print('Device : %s (%dx%d, %s)'
          % (profile.label, profile.width, profile.height,
             'greyscale' if profile.grayscale else 'colour'))
    print('Quality: %s'
          % ('fixed at %d' % quality if target_error is None
             else '%s, measured per image (at most %.2f %% of pixels differ)'
                  % (target.name, target.budget)))
    print('Target : %s' % (target_fmt or 'keep original format'))
    print('Calibre: %s' % (conv.version()
                           or 'not found - epub/kepub/cbz only'))
    print('Engine : %s%s' % (backend_name(),
                             '' if args.jobs <= 1
                             else ', %d workers' % args.jobs))
    print('Files  : %d\n' % len(files))

    total_old = total_new = 0
    failed = 0
    force_gray = False if args.keep_color else None
    png_mode = {'keep': False, 'auto': 'auto', 'jpeg': True}[args.png_mode]

    for src in files:
        ext = ext_of(src)
        fmt = target_fmt or ('cbz' if ext in COMIC_EXT else ext.lstrip('.'))
        dst_final = target_path(src, args, fmt)
        if args.dry_run:
            fd, tmp = tempfile.mkstemp(prefix='ebook_opt_probe_',
                                       suffix='.' + fmt)
            os.close(fd)
        else:
            # Calibre picks the output format from the extension, so the
            # temporary file has to keep it.
            root, extn = os.path.splitext(dst_final)
            tmp = root + '.ebook_opt_tmp' + extn
        try:
            rep = process(
                src, tmp, profile, target_fmt=fmt,
                quality=quality, png_mode=png_mode, fonts=args.fonts,
                force_grayscale=force_gray, manga=args.manga,
                quantize_gray=quantize, target_error=target_error,
                progressive=not args.no_progressive, jobs=args.jobs)
            detail = rep.detail
            if rep.converted_from:
                detail = '%s to %s, %s' % (rep.converted_from,
                                           rep.converted_to, detail)
        except conv.CalibreMissing as e:
            failed += 1
            print('  %s: %s' % (os.path.basename(src), e))
            if os.path.exists(tmp):
                os.remove(tmp)
            continue
        except Exception as e:
            failed += 1
            print('  FAILED %s: %s' % (os.path.basename(src), e))
            if args.verbose:
                traceback.print_exc()
            if os.path.exists(tmp):
                os.remove(tmp)
            continue

        total_old += rep.old_size
        total_new += rep.new_size
        print('%-45s %9s -> %9s  (%+.1f%%)  [%s]'
              % (os.path.basename(src)[:45], human_size(rep.old_size),
                 human_size(rep.new_size),
                 -pct_saved(rep.old_size, rep.new_size), detail))
        # Losing every image is not a detail; say it even without -v.
        loud = [n for n in rep.notes if 'image' in n or 'images' in n]
        for n in (rep.notes[:5] if args.verbose else loud[:2]):
            print('      ! %s' % n)

        if args.dry_run:
            os.remove(tmp)
            continue

        if rep.new_size >= rep.old_size and fmt == ext.lstrip('.'):
            print('      -> no gain, original kept')
            os.remove(tmp)
            total_new = total_new - rep.new_size + rep.old_size
            continue

        if args.in_place:
            if not args.no_backup:
                # An existing .bak may be the only copy of the original.
                # Never overwrite it; number the backups instead.
                bak = src + '.bak'
                i = 1
                while os.path.exists(bak):
                    bak = '%s.bak.%d' % (src, i)
                    i += 1
                os.replace(src, bak)
                if args.verbose:
                    print('      -> backup: %s' % os.path.basename(bak))
            elif os.path.exists(src):
                os.remove(src)
        os.replace(tmp, dst_final)

    print('\nTotal: %s -> %s, saved %s (%.1f%%)%s'
          % (human_size(total_old), human_size(total_new),
             human_size(total_old - total_new),
             pct_saved(total_old, total_new),
             '  [dry run, nothing written]' if args.dry_run else ''))
    if failed:
        print('%d file(s) failed.' % failed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
