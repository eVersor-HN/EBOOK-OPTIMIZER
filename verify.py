"""Check optimised files for structural integrity."""

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
        errs += fail('corrupt entry %s' % bad) if bad else ok('ZIP intact')

        if names[0] != 'mimetype':
            errs += fail('mimetype is not the first entry')
        else:
            zi = z.getinfo('mimetype')
            if zi.compress_type != zipfile.ZIP_STORED:
                errs += fail('mimetype is compressed')
            elif z.read('mimetype') != b'application/epub+zip':
                errs += fail('mimetype content is wrong')
            else:
                errs += ok('mimetype correct: stored, first entry')

        # Locate the OPF
        cn = etree.fromstring(z.read('META-INF/container.xml'))
        opf_path = cn.find('.//{%s}rootfile' % CN_NS).get('full-path')
        opf_dir = posixpath.dirname(opf_path)
        opf = etree.fromstring(z.read(opf_path))
        errs += ok('OPF parses (%s)' % opf_path)

        # Every manifest href must exist
        missing = []
        media = {}
        for item in opf.findall('.//{%s}item' % OPF_NS):
            href = item.get('href')
            full = posixpath.normpath(posixpath.join(opf_dir, href))
            media[full] = item.get('media-type')
            if full not in names:
                missing.append(href)
        errs += fail('manifest points at missing files: %s' % missing) \
            if missing else ok('all %d manifest entries present' % len(media))

        # media-type has to match the actual content
        mismatch = []
        for full, mt in media.items():
            if not mt or not mt.startswith('image/'):
                continue
            data = z.read(full)
            try:
                real = (Image.open(io.BytesIO(data)).format or '').upper()
            except Exception:
                mismatch.append((full, 'unreadable'))
                continue
            want = {'JPEG': 'image/jpeg', 'PNG': 'image/png',
                    'GIF': 'image/gif', 'WEBP': 'image/webp'}.get(real)
            if want and want != mt:
                mismatch.append((full, '%s != %s' % (mt, want)))
        errs += fail('media-type does not match: %s' % mismatch) \
            if mismatch else ok('media-types match the actual image content')

        # Image references in XHTML/CSS have to resolve
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
        errs += fail('dangling references: %s' % dangling) \
            if dangling else ok('no dangling references in XHTML/CSS')

        # Are the fonts really gone?
        fonts = [n for n in names
                 if n.lower().endswith(('.ttf', '.otf', '.woff', '.woff2'))]
        ff = []
        for n in names:
            if n.lower().endswith(('.css', '.xhtml', '.html')):
                if '@font-face' in z.read(n).decode('utf-8', 'replace'):
                    ff.append(n)
        if fonts:
            errs += fail('fonts still present: %s' % fonts)
        elif ff:
            errs += fail('@font-face rules left in: %s' % ff)
        else:
            errs += ok('fonts and @font-face removed')

        # Image sizes within bounds
        toolarge = []
        for n in names:
            if not n.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            im = Image.open(io.BytesIO(z.read(n)))
            if im.width > 1448 or im.height > 1448:
                toolarge.append((n, im.size))
            if im.mode not in ('L', 'P', 'LA', '1'):
                toolarge.append((n, 'mode %s, not greyscale' % im.mode))
        errs += fail('images outside the target: %s' % toolarge) \
            if toolarge else ok('all images scaled and greyscale')

    return errs


def verify_cbz(path, expect_pages, manga=False):
    print('CBZ %s' % path)
    errs = 0
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        errs += fail('corrupt') if z.testzip() else ok('ZIP intact')

        imgs = [n for n in names if n.lower().endswith(('.jpg', '.jpeg', '.png'))]
        errs += (ok('%d pages present' % len(imgs)) if len(imgs) == expect_pages
                 else fail('%d pages instead of %d' % (len(imgs), expect_pages)))

        if sorted(imgs) != imgs:
            errs += fail('page order is not alphabetically sortable')
        else:
            errs += ok('page names keep their order')

        bad = []
        for n in imgs:
            im = Image.open(io.BytesIO(z.read(n)))
            if im.width > 1448 or im.height > 1448:
                bad.append((n, im.size))
            if im.mode not in ('L', 'P', '1'):
                bad.append((n, im.mode))
            if z.getinfo(n).compress_type != zipfile.ZIP_STORED:
                bad.append((n, 'not stored'))
        errs += fail('page problems: %s' % bad[:4]) if bad \
            else ok('pages scaled, greyscale, stored')

        ci = [n for n in names if n.lower().endswith('comicinfo.xml')]
        if not ci:
            errs += fail('ComicInfo.xml is gone')
        else:
            text = z.read(ci[0]).decode('utf-8', 'replace')
            etree.fromstring(text.encode('utf-8'))
            if 'Testcomic' not in text:
                errs += fail('ComicInfo metadata is gone')
            elif manga and 'YesAndRightToLeft' not in text:
                errs += fail('manga reading direction not set')
            else:
                errs += ok('ComicInfo.xml preserved and valid')
    return errs


if __name__ == '__main__':
    total = 0
    total += verify_epub(sys.argv[1])
    total += verify_cbz(sys.argv[2], int(sys.argv[3]),
                        manga='--manga' in sys.argv)
    print('\n%s' % ('ALL CHECKS PASSED' if total == 0
                    else '%d PROBLEM(S)' % total))
    sys.exit(1 if total else 0)
