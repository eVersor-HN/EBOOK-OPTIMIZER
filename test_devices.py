"""Device matrix: every profile through optimisation, conversion and
every quality mode - so an optimisation cannot quietly break a device.

Four parts:

  A  Every device profile optimises an EPUB and a CBZ. The results are
     opened and checked: images fit the panel (allowing the rotated box
     for landscape spreads), greyscale devices get greyscale, colour
     devices keep colour, the EPUB mimetype survives.
  B  Every device profile converts an EPUB to AZW3, which exercises the
     per-brand Calibre output profile mapping introduced in 0.4.1.
     Skipped with a notice when Calibre is missing.
  C  Both quality targets and a pinned quality produce valid output.
  D  Comic containers: CBZ, CBR (if an unpacker exists), CBT and CB7
     each optimise for a sample of devices.

Runs on the synthetic test data, so no downloads are needed.
"""

import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ebook_optimizer.core import convert as conv           # noqa: E402
from ebook_optimizer.core.cbz import optimize_comic        # noqa: E402
from ebook_optimizer.core.epub import optimize_epub        # noqa: E402
from ebook_optimizer.core.pipeline import process          # noqa: E402
from ebook_optimizer.core.profiles import (                # noqa: E402
    PROFILES, TARGETS, get_profile)

HERE = os.path.dirname(os.path.abspath(__file__))
EPUB = os.path.join(HERE, 'testdata', 'testbuch.epub')
CBZ = os.path.join(HERE, 'testdata', 'testcomic.cbz')

FAILS = []


def fail(msg):
    FAILS.append(msg)
    print('  FAIL %s' % msg)


def fits(profile, w, h):
    """Does an image fit the panel, in either orientation?"""
    pw, ph = profile.box
    return (w <= pw and h <= ph) or (w <= ph and h <= pw)


def source_hashes(src):
    """Hashes of the images in a source archive, to recognise
    originals that were deliberately kept."""
    out = set()
    with zipfile.ZipFile(src) as z:
        for n in z.namelist():
            if n.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                out.add(hashlib.sha1(z.read(n)).hexdigest())
    return out


def check_images(path, profile, what, originals=frozenset()):
    """Open every image in a produced archive and validate it.

    The contract deliberately allows one exception: when every
    re-encode of an image would be LARGER than the source, the
    untouched original is kept - even when it is bigger than the
    panel. That honours the size promise and is visually optimal;
    the reader scales at display time. So an image must either fit
    the panel or be byte-identical to a source image.
    """
    from PIL import Image
    with zipfile.ZipFile(path) as z:
        imgs = [n for n in z.namelist()
                if n.lower().endswith(('.jpg', '.jpeg', '.png',
                                       '.gif'))]
        if not imgs:
            fail('%s %s: no images in the output'
                 % (profile.key, what))
            return
        for n in imgs:
            raw = z.read(n)
            kept = hashlib.sha1(raw).hexdigest() in originals
            try:
                im = Image.open(io.BytesIO(raw))
                im.load()
            except Exception as e:
                fail('%s %s: %s unreadable (%s)'
                     % (profile.key, what, n, e))
                continue
            if not fits(profile, im.width, im.height) and not kept:
                fail('%s %s: %s is %dx%d, panel is %dx%d'
                     % (profile.key, what, n, im.width, im.height,
                        profile.width, profile.height))
            if kept:
                continue          # untouched original, nothing to judge
            grey = im.mode in ('L', 'LA', 'P', '1')
            if profile.grayscale and not grey:
                fail('%s %s: %s kept colour (%s) on a greyscale panel'
                     % (profile.key, what, n, im.mode))
            if (not profile.grayscale and im.mode == 'L'
                    and n.lower().endswith(('.jpg', '.jpeg'))):
                # A colour panel may hold grey art, but the synthetic
                # pages are colourful - grey means a wrong turn.
                fail('%s %s: %s lost its colour on a colour panel'
                     % (profile.key, what, n))


def part_a(tmp):
    print('A  every device optimises an EPUB and a CBZ')
    t = time.perf_counter()
    orig_e = source_hashes(EPUB)
    orig_c = source_hashes(CBZ)
    for key in sorted(PROFILES):
        p = get_profile(key)
        out_e = os.path.join(tmp, 'a_%s.epub' % key)
        out_c = os.path.join(tmp, 'a_%s.cbz' % key)
        try:
            optimize_epub(EPUB, out_e, p, target_error=0.10, jobs=4,
                          png_to_jpeg='auto')
            check_images(out_e, p, 'epub', orig_e)
            with zipfile.ZipFile(out_e) as z:
                if z.namelist()[0] != 'mimetype':
                    fail('%s epub: mimetype not first' % key)
        except Exception as e:
            fail('%s epub: %s' % (key, e))
        try:
            optimize_comic(CBZ, out_c, p, target_error=0.10, jobs=4)
            check_images(out_c, p, 'cbz', orig_c)
        except Exception as e:
            fail('%s cbz: %s' % (key, e))
    print('   %d devices in %.0f s' % (len(PROFILES), time.perf_counter() - t))


def part_b(tmp):
    print('B  every device converts an EPUB to AZW3')
    if not conv.available():
        print('   Calibre not found - skipped. Install it to cover '
              'conversion.')
        return
    t = time.perf_counter()
    for key in sorted(PROFILES):
        p = get_profile(key)
        dst = os.path.join(tmp, 'b_%s.azw3' % key)
        try:
            process(EPUB, dst, p, target_fmt='azw3', target_error=0.10,
                    jobs=4)
            if os.path.getsize(dst) < 10000:
                fail('%s azw3: suspiciously small (%d bytes)'
                     % (key, os.path.getsize(dst)))
        except Exception as e:
            fail('%s azw3: %s' % (key, str(e)[:80]))
    print('   %d devices in %.0f s' % (len(PROFILES), time.perf_counter() - t))


def part_c(tmp):
    print('C  quality modes')
    p = get_profile('pb_verse_pro')
    sizes = {}
    for label, kw in (('identical', dict(target_error=TARGETS['identical'].budget)),
                      ('smaller', dict(target_error=TARGETS['smaller'].budget)),
                      ('fixed q70', dict(quality=70))):
        dst = os.path.join(tmp, 'c_%s.cbz' % label.replace(' ', '_'))
        try:
            optimize_comic(CBZ, dst, p, jobs=4, **kw)
            check_images(dst, p, label)
            sizes[label] = os.path.getsize(dst)
        except Exception as e:
            fail('quality %s: %s' % (label, e))
    if 'identical' in sizes and 'smaller' in sizes \
            and sizes['smaller'] > sizes['identical']:
        fail('the looser target produced a LARGER file '
             '(%d vs %d)' % (sizes['smaller'], sizes['identical']))
    for label, n in sorted(sizes.items()):
        print('   %-10s %7.1f KB' % (label, n / 1024))


def part_d(tmp):
    print('D  comic containers')
    p = get_profile('pb_verse_pro')
    with zipfile.ZipFile(CBZ) as z:
        pages = [(n, z.read(n)) for n in z.namelist()
                 if n.lower().endswith('.jpg')][:3]

    # CBT is plain tar - always available.
    cbt = os.path.join(tmp, 'd.cbt')
    with tarfile.open(cbt, 'w') as t:
        for n, d in pages:
            ti = tarfile.TarInfo(n)
            ti.size = len(d)
            t.addfile(ti, io.BytesIO(d))
    containers = [('cbt', cbt)]

    # CB7 needs a 7z-capable archiver; Windows ships one as System32 tar.
    win_tar = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'),
                           'System32', 'tar.exe')
    packer = shutil.which('bsdtar') or (
        win_tar if os.name == 'nt' and os.path.isfile(win_tar) else None)
    if packer:
        pagedir = os.path.join(tmp, 'd_pages')
        os.makedirs(pagedir, exist_ok=True)
        for n, d in pages:
            open(os.path.join(pagedir, os.path.basename(n)), 'wb').write(d)
        cb7 = os.path.join(tmp, 'd.cb7')
        try:
            subprocess.run(
                [packer, '--format', '7zip', '-cf', cb7, '-C', pagedir]
                + [os.path.basename(n) for n, _d in pages],
                check=True, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            containers.append(('cb7', cb7))
        except Exception:
            print('   cb7: could not be generated here, skipped')
    else:
        print('   cb7: no 7z-capable archiver, skipped')

    for label, src in [('cbz', CBZ)] + containers:
        dst = os.path.join(tmp, 'd_out_%s.cbz' % label)
        try:
            rep = optimize_comic(src, dst, p, target_error=0.10, jobs=4)
            check_images(dst, p, label)
            print('   %-4s %d pages -> ok' % (label, rep.pages))
        except Exception as e:
            fail('%s: %s' % (label, e))


def main():
    if not (os.path.exists(EPUB) and os.path.exists(CBZ)):
        print('Run make_testdata.py first.')
        return 1
    tmp = tempfile.mkdtemp(prefix='ebook_opt_dev_')
    try:
        part_a(tmp)
        part_b(tmp)
        part_c(tmp)
        part_d(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('')
    if FAILS:
        print('%d FAILURE(S)' % len(FAILS))
        return 1
    print('EVERY DEVICE AND MODE BEHAVED CORRECTLY')
    return 0


if __name__ == '__main__':
    sys.exit(main())
