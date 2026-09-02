"""Standalone-CLI - laeuft ohne Calibre, braucht nur Python 3.8+ und Pillow.

Beispiele:
    python -m ebook_optimizer.cli buch.epub
    python -m ebook_optimizer.cli D:\\Bibliothek --recursive --out-dir D:\\Optimiert
    python -m ebook_optimizer.cli manga.cbr --manga --quality 75 --in-place
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
from .core.profiles import DEFAULT_PROFILE, PROFILES, get_profile
from .core.util import ext_of, human_size, pct_saved

EPUB_EXT = {'.epub', '.kepub'}
# Ohne Calibre koennen wir nur unsere eigenen Behaelter; mit Calibre alles,
# was dessen Konverter liest.
NATIVE_EXT = EPUB_EXT | COMIC_EXT


# Calibre liest auch .txt, .html und Konsorten. Beim Durchsuchen eines
# Ordners waere das ein Fallstrick: jede README und jede Notiz wuerde
# mitkonvertiert. Direkt benannte Dateien bleiben erlaubt.
SCAN_SKIP_EXT = {'.txt', '.text', '.htm', '.html', '.xhtm', '.xhtml',
                 '.md', '.markdown', '.textile', '.opf', '.recipe',
                 '.zip', '.rar', '.shtm', '.shtml'}


def all_ext(scanning=False):
    ext = set(NATIVE_EXT)
    if conv.available():
        ext |= {'.' + f for f in conv.input_formats()}
    if scanning:
        ext -= SCAN_SKIP_EXT
    return ext


def collect(paths, recursive):
    exts = all_ext(scanning=True)
    named = all_ext()
    out = []
    for p in paths:
        if os.path.isdir(p):
            if recursive:
                for root, _d, files in os.walk(p):
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
                print('Uebersprungen (kein bekanntes Format): %s' % p,
                      file=sys.stderr)
        else:
            print('Nicht gefunden: %s' % p, file=sys.stderr)
    return out


def target_path(src, args, fmt):
    base = os.path.basename(src)
    stem = os.path.splitext(base)[0]
    if args.in_place:
        return os.path.join(os.path.dirname(src), target_name(stem, fmt))
    out_dir = args.out_dir or os.path.join(os.path.dirname(src), 'optimiert')
    if not args.dry_run:
        os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, target_name(stem + args.suffix, fmt))


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='EBOOK-OPTIMIZER',
        description='EPUB/Comic-Optimierung fuer E-Ink-Reader')
    ap.add_argument('paths', nargs='*', help='Dateien oder Ordner')
    ap.add_argument('-p', '--profile', default=DEFAULT_PROFILE,
                    choices=sorted(PROFILES), help='Zielgeraet')
    ap.add_argument('-q', '--quality', type=int, default=80,
                    help='JPEG-Qualitaet 1-100 (Standard 80)')
    ap.add_argument('-r', '--recursive', action='store_true',
                    help='Ordner rekursiv durchsuchen')
    ap.add_argument('-o', '--out-dir', help='Zielordner (Standard: ./optimiert)')
    ap.add_argument('--suffix', default='', help='Suffix fuer Zieldateien')
    ap.add_argument('--in-place', action='store_true',
                    help='Originale ersetzen (legt .bak an, ausser mit --no-backup)')
    ap.add_argument('--no-backup', action='store_true')
    ap.add_argument('--fonts', choices=['strip', 'keep'], default='strip',
                    help='Eingebettete Schriften entfernen oder behalten')
    ap.add_argument('--png-mode', choices=['keep', 'auto', 'jpeg'],
                    default='auto',
                    help='PNG/GIF/WebP: Format behalten, automatisch das '
                         'kleinere Ergebnis waehlen (Standard) oder immer JPEG')
    ap.add_argument('--keep-color', action='store_true',
                    help='Farbe behalten (kein Graustufen-Zwang)')
    ap.add_argument('--no-quantize', action='store_true',
                    help='PNG nicht auf 16 Graustufen reduzieren')
    ap.add_argument('--manga', action='store_true',
                    help='Comics: Leserichtung rechts-nach-links setzen')
    ap.add_argument('-t', '--to', metavar='FORMAT',
                    help='Zielformat, z. B. epub, kepub, azw3, mobi, pdf, '
                         'cbz. Ohne Angabe bleibt das Format erhalten '
                         '(Comics werden immer zu CBZ). Alles ausser '
                         'epub/kepub/cbz benoetigt Calibre.')
    ap.add_argument('--list-formats', action='store_true',
                    help='Verfuegbare Zielformate anzeigen und beenden')
    ap.add_argument('-j', '--jobs', type=int, default=default_jobs(),
                    help='Bilder parallel verarbeiten (Standard: %d)'
                         % default_jobs())
    ap.add_argument('--no-progressive', action='store_true',
                    help='Baseline-JPEG statt progressiv. Progressive JPEGs '
                         'sind rund 6 %% kleiner, sehr alte E-Ink-Geraete '
                         'koennen damit aber Probleme haben')
    ap.add_argument('-n', '--dry-run', action='store_true',
                    help='Nur rechnen, nichts ueberschreiben')
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args(argv)

    if args.list_formats:
        if conv.available():
            print('Calibre: %s' % conv.version())
            print('Zielformate: %s' % ', '.join(sorted(
                set(conv.output_formats()) | {'cbz'})))
        else:
            print('Calibre nicht gefunden - ohne Calibre sind nur '
                  'epub, kepub und cbz moeglich.')
            print('Installation: https://calibre-ebook.com')
        return 0

    target_fmt = args.to.lstrip('.').lower() if args.to else None
    if target_fmt and target_fmt not in ('epub', 'kepub', 'cbz') \
            and not conv.available():
        print('Fuer das Zielformat "%s" wird Calibre benoetigt, es wurde '
              'aber nicht gefunden.' % target_fmt)
        print('Installiere Calibre von https://calibre-ebook.com und '
              'versuche es erneut.')
        return 2

    if not args.paths:
        ap.error('Bitte mindestens eine Datei oder einen Ordner angeben.')

    profile = get_profile(args.profile)
    files = collect(args.paths, args.recursive)
    if not files:
        print('Keine passenden Dateien gefunden.')
        return 1

    print('Profil : %s (%dx%d, %s)' % (
        profile.name, profile.width, profile.height,
        'Graustufen' if profile.grayscale else 'Farbe'))
    print('Backend: %s%s' % (
        backend_name(),
        '' if args.jobs <= 1 else ', %d parallel' % args.jobs))
    print('JPEG   : %s' % ('baseline' if args.no_progressive
                           else 'progressiv (rund 6 % kleiner)'))
    print('Calibre: %s' % (conv.version() or 'nicht gefunden '
                              '(nur epub/kepub/cbz moeglich)'))
    print('Ziel   : %s' % (target_fmt or 'Format beibehalten'))
    print('Dateien: %d\n' % len(files))

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
            # Calibre erkennt das Ausgabeformat an der Endung - die
            # Temp-Datei muss sie deshalb behalten.
            _root, _extn = os.path.splitext(dst_final)
            tmp = _root + '.ebook_opt_tmp' + _extn
        try:
            rep = process(
                src, tmp, profile, target_fmt=fmt,
                quality=args.quality, png_mode=png_mode, fonts=args.fonts,
                force_grayscale=force_gray, manga=args.manga,
                quantize_gray=not args.no_quantize,
                progressive=not args.no_progressive, jobs=args.jobs)
            detail = rep.detail
            if rep.converted_from:
                detail = '%s->%s, %s' % (rep.converted_from,
                                         rep.converted_to, detail)
        except Exception as e:
            failed += 1
            print('  FEHLER %s: %s' % (os.path.basename(src), e))
            if args.verbose:
                traceback.print_exc()
            if os.path.exists(tmp):
                os.remove(tmp)
            continue

        total_old += rep.old_size
        total_new += rep.new_size
        # Vorzeichen mitformatieren: gewachsene Dateien sonst als "--0.1%"
        print('%-45s %9s -> %9s  (%+.1f%%)  [%s]' % (
            os.path.basename(src)[:45], human_size(rep.old_size),
            human_size(rep.new_size), -pct_saved(rep.old_size, rep.new_size),
            detail))
        if args.verbose:
            for n in rep.notes[:5]:
                print('      ! %s' % n)

        if args.dry_run:
            os.remove(tmp)
            continue

        if rep.new_size >= rep.old_size:
            print('      -> kein Gewinn, Original bleibt')
            os.remove(tmp)
            total_new = total_new - rep.new_size + rep.old_size
            continue

        if args.in_place:
            if not args.no_backup:
                # Ein vorhandenes .bak ist die einzige Kopie des Originals -
                # niemals ueberschreiben, sondern durchnummerieren.
                bak = src + '.bak'
                i = 1
                while os.path.exists(bak):
                    bak = '%s.bak.%d' % (src, i)
                    i += 1
                os.replace(src, bak)
                if args.verbose:
                    print('      -> Sicherung: %s' % os.path.basename(bak))
            elif os.path.exists(src):
                os.remove(src)
        os.replace(tmp, dst_final)

    print('\nGesamt: %s -> %s  gespart %s (%.1f%%)%s' % (
        human_size(total_old), human_size(total_new),
        human_size(total_old - total_new), pct_saved(total_old, total_new),
        '  [Testlauf, nichts geschrieben]' if args.dry_run else ''))
    if failed:
        print('%d Datei(en) fehlgeschlagen.' % failed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
