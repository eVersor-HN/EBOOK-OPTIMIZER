"""Prueft optimierte Dateien auf strukturelle Integritaet."""

import io
import posixpath
import re
import sys
import zipfile

from xml.etree import ElementTree as etree
from PIL import Image

OPF_NS = 'http://www.idpf.org/2007/opf'
CN_NS = 'urn:oasis:names:tc:opendocument:xmlns:container'


def fail(msg):
    print('  FAIL %s' % msg)
    return 1


def ok(msg):
    print('  ok   %s' % msg)
    return 0


def verify_epub(path):
    print('EPUB %s' % path)
    errs = 0
    with zipfile.ZipFile(path) as z:
        names = z.namelist()

        bad = z.testzip()
        errs += fail('defekter Eintrag %s' % bad) if bad else ok('ZIP intakt')

        if names[0] != 'mimetype':
            errs += fail('mimetype nicht als erster Eintrag')
        else:
            zi = z.getinfo('mimetype')
            if zi.compress_type != zipfile.ZIP_STORED:
                errs += fail('mimetype ist komprimiert')
            elif z.read('mimetype') != b'application/epub+zip':
                errs += fail('mimetype-Inhalt falsch')
            else:
                errs += ok('mimetype korrekt (STORED, erster Eintrag)')

        # OPF finden
        cn = etree.fromstring(z.read('META-INF/container.xml'))
        opf_path = cn.find('.//{%s}rootfile' % CN_NS).get('full-path')
        opf_dir = posixpath.dirname(opf_path)
        opf = etree.fromstring(z.read(opf_path))
        errs += ok('OPF parsebar (%s)' % opf_path)

        # Manifest-Hrefs muessen existieren
        missing = []
        media = {}
        for item in opf.findall('.//{%s}item' % OPF_NS):
            href = item.get('href')
            full = posixpath.normpath(posixpath.join(opf_dir, href))
            media[full] = item.get('media-type')
            if full not in names:
                missing.append(href)
        errs += fail('Manifest zeigt auf fehlende Dateien: %s' % missing) \
            if missing else ok('alle Manifest-Eintraege vorhanden (%d)' % len(media))

        # media-type muss zum echten Inhalt passen
        mismatch = []
        for full, mt in media.items():
            if not mt or not mt.startswith('image/'):
                continue
            data = z.read(full)
            try:
                real = (Image.open(io.BytesIO(data)).format or '').upper()
            except Exception:
                mismatch.append((full, 'unlesbar'))
                continue
            want = {'JPEG': 'image/jpeg', 'PNG': 'image/png',
                    'GIF': 'image/gif', 'WEBP': 'image/webp'}.get(real)
            if want and want != mt:
                mismatch.append((full, '%s != %s' % (mt, want)))
        errs += fail('media-type passt nicht: %s' % mismatch) \
            if mismatch else ok('media-types stimmen mit Bildinhalt ueberein')

        # Bildreferenzen in XHTML/CSS muessen aufloesbar sein
        dangling = []
        for n in names:
            if not n.lower().endswith(('.xhtml', '.html', '.htm', '.css')):
                continue
            text = z.read(n).decode('utf-8', 'replace')
            base = posixpath.dirname(n)
            for ref in re.findall(r'(?:src|href)\s*=\s*["\']([^"\':#]+)["\']',
                                  text) + re.findall(r'url\(["\']?([^)"\']+)', text):
                if ref.startswith(('http:', 'https:', 'data:', 'mailto:')):
                    continue
                target = posixpath.normpath(posixpath.join(base, ref))
                if target not in names:
                    dangling.append('%s -> %s' % (n, ref))
        errs += fail('tote Referenzen: %s' % dangling) \
            if dangling else ok('keine toten Referenzen in XHTML/CSS')

        # Fonts wirklich weg?
        fonts = [n for n in names
                 if n.lower().endswith(('.ttf', '.otf', '.woff', '.woff2'))]
        ff = []
        for n in names:
            if n.lower().endswith(('.css', '.xhtml', '.html')):
                if '@font-face' in z.read(n).decode('utf-8', 'replace'):
                    ff.append(n)
        if fonts:
            errs += fail('Schriften noch vorhanden: %s' % fonts)
        elif ff:
            errs += fail('@font-face-Regeln uebrig in: %s' % ff)
        else:
            errs += ok('Schriften und @font-face entfernt')

        # Bildgroessen im Rahmen
        toolarge = []
        for n in names:
            if not n.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            im = Image.open(io.BytesIO(z.read(n)))
            if im.width > 1448 or im.height > 1448:
                toolarge.append((n, im.size))
            if im.mode not in ('L', 'P', 'LA', '1'):
                toolarge.append((n, 'Modus %s (nicht grau)' % im.mode))
        errs += fail('Bilder ausserhalb der Vorgabe: %s' % toolarge) \
            if toolarge else ok('alle Bilder skaliert und in Graustufen')

    return errs


def verify_cbz(path, expect_pages, manga=False):
    print('CBZ %s' % path)
    errs = 0
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        errs += fail('defekt') if z.testzip() else ok('ZIP intakt')

        imgs = [n for n in names if n.lower().endswith(('.jpg', '.jpeg', '.png'))]
        errs += (ok('%d Seiten vorhanden' % len(imgs)) if len(imgs) == expect_pages
                 else fail('Seitenzahl %d statt %d' % (len(imgs), expect_pages)))

        if sorted(imgs) != imgs:
            errs += fail('Seitenreihenfolge nicht alphabetisch sortierbar')
        else:
            errs += ok('Seitennamen behalten Reihenfolge')

        bad = []
        for n in imgs:
            im = Image.open(io.BytesIO(z.read(n)))
            if im.width > 1448 or im.height > 1448:
                bad.append((n, im.size))
            if im.mode not in ('L', 'P', '1'):
                bad.append((n, im.mode))
            if z.getinfo(n).compress_type != zipfile.ZIP_STORED:
                bad.append((n, 'nicht STORED'))
        errs += fail('Seitenprobleme: %s' % bad[:4]) if bad \
            else ok('Seiten skaliert, grau, STORED')

        ci = [n for n in names if n.lower().endswith('comicinfo.xml')]
        if not ci:
            errs += fail('ComicInfo.xml verloren')
        else:
            text = z.read(ci[0]).decode('utf-8', 'replace')
            etree.fromstring(text.encode('utf-8'))
            if 'Testcomic' not in text:
                errs += fail('ComicInfo-Metadaten verloren')
            elif manga and 'YesAndRightToLeft' not in text:
                errs += fail('Manga-Leserichtung nicht gesetzt')
            else:
                errs += ok('ComicInfo.xml erhalten und valide')
    return errs


if __name__ == '__main__':
    total = 0
    total += verify_epub(sys.argv[1])
    total += verify_cbz(sys.argv[2], int(sys.argv[3]),
                        manga='--manga' in sys.argv)
    print('\n%s' % ('ALLE PRUEFUNGEN BESTANDEN' if total == 0
                    else '%d PROBLEM(E)' % total))
    sys.exit(1 if total else 0)
