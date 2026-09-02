"""Edge cases: corrupt images, transparency, animation, exotic modes."""

import io
import os
import sys
import tarfile
import tempfile
import zipfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ebook_optimizer.core.cbz import optimize_comic  # noqa: E402
from ebook_optimizer.core.epub import optimize_epub  # noqa: E402
from ebook_optimizer.core.imaging import optimize_image  # noqa: E402
from ebook_optimizer.core.profiles import get_profile  # noqa: E402

P = get_profile('pb_verse_pro')
FAILS = []


def check(name, cond, extra=''):
    print('  %-46s %s %s' % (name, 'ok' if cond else 'FAIL', extra))
    if not cond:
        FAILS.append(name)


def enc(im, fmt, **kw):
    b = io.BytesIO()
    im.save(b, fmt, **kw)
    return b.getvalue()


print('Image edge cases')

# 1 Keeping the format must not lose transparency
rgba = Image.new('RGBA', (1800, 1200), (255, 0, 0, 0))
rgba.paste(Image.new('RGBA', (400, 400), (0, 0, 255, 255)), (10, 10))
r = optimize_image(enc(rgba, 'PNG'), P, png_to_jpeg='auto')
out = Image.open(io.BytesIO(r.data))
check('alpha PNG keeps its transparency', out.mode in ('LA', 'PA', 'RGBA', 'P'),
      out.mode)
check('alpha PNG stays PNG', r.fmt == 'PNG', r.fmt)

# 2 Forced JPEG must not destroy alpha, so it has to stay PNG
r = optimize_image(enc(rgba, 'PNG'), P, png_to_jpeg=True)
check('alpha PNG is not forced to JPEG', r.fmt == 'PNG', r.fmt)

# 3 Animated GIF left alone, oversized so scaling would otherwise kick in
frames = []
for i in range(6):
    f = Image.new('P', (2000, 1500), 0)
    f.paste(Image.new('P', (600, 400), 200), (i * 120, i * 90))
    frames.append(f)
b = io.BytesIO()
frames[0].save(b, 'GIF', save_all=True, append_images=frames[1:], duration=100)
gif = b.getvalue()
assert Image.open(io.BytesIO(gif)).n_frames > 1, 'the test GIF is not animated'
r = optimize_image(gif, P)
check('animated GIF is left untouched',
      not r.changed and r.data == gif and r.reason == 'animated', r.reason)

# 4 A corrupt file must not crash; the original comes back
r = optimize_image(b'\x89PNG\r\n\x1a\n GARBAGE' * 20, P)
check('corrupt image is caught', not r.changed, r.reason)

# 5 CMYK JPEG
cmyk = Image.new('CMYK', (1600, 1200), (10, 20, 30, 5))
r = optimize_image(enc(cmyk, 'JPEG', quality=95), P)
check('CMYK JPEG is converted', r.changed and
      Image.open(io.BytesIO(r.data)).mode == 'L')

# 6 A small image is never upscaled
small = Image.new('RGB', (120, 90), (200, 100, 50))
r = optimize_image(enc(small, 'PNG'), P)
sz = Image.open(io.BytesIO(r.data)).size if r.changed else (120, 90)
check('small image is not upscaled', sz == (120, 90), str(sz))

# 7 Landscape double spread: the box rotates instead of crushing it
wide = Image.new('RGB', (3000, 2000), (30, 30, 30))
r = optimize_image(enc(wide, 'JPEG', quality=95), P)
w, h = Image.open(io.BytesIO(r.data)).size
check('double spread uses its long edge', w == 1448 and h <= 1072, '%dx%d' % (w, h))

# 8 1-bit image-Strichzeichnung
bw = Image.new('1', (2000, 2600), 1)
r = optimize_image(enc(bw, 'PNG'), P)
check('1-bit image can be processed', r.changed or r.reason == 'no gain', r.reason)


print('\nArchive edge cases')
tmp = tempfile.mkdtemp()

# 9 EPUB with no images und ohne Fonts
epub = os.path.join(tmp, 'leer.epub')
with zipfile.ZipFile(epub, 'w') as z:
    zi = zipfile.ZipInfo('mimetype'); zi.compress_type = zipfile.ZIP_STORED
    z.writestr(zi, b'application/epub+zip')
    z.writestr('META-INF/container.xml',
               '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
               '<rootfiles><rootfile full-path="c.opf"/></rootfiles></container>')
    z.writestr('c.opf', '<package><manifest/></package>')
    z.writestr('t.xhtml', '<html><body><p>nur Text</p></body></html>')
out = os.path.join(tmp, 'leer_out.epub')
rep = optimize_epub(epub, out, P)
check('EPUB without images runs through', rep.images == 0 and os.path.exists(out))
with zipfile.ZipFile(out) as z:
    check('EPUB without images stays readable', z.testzip() is None and
          z.read('t.xhtml').startswith(b'<html'))

# 10 EPUB containing junk files
epub2 = os.path.join(tmp, 'junk.epub')
with zipfile.ZipFile(epub2, 'w') as z:
    zi = zipfile.ZipInfo('mimetype'); zi.compress_type = zipfile.ZIP_STORED
    z.writestr(zi, b'application/epub+zip')
    z.writestr('__MACOSX/._x', b'junk' * 500)
    z.writestr('.DS_Store', b'junk' * 500)
    z.writestr('a.xhtml', '<html><body>x</body></html>')
out2 = os.path.join(tmp, 'junk_out.epub')
optimize_epub(epub2, out2, P)
with zipfile.ZipFile(out2) as z:
    names = z.namelist()
check('junk files removed',
      not any('MACOSX' in n or 'DS_Store' in n for n in names), str(names))

# 11 CBZ mit unsortierten Namen (2 vor 10)
cbz = os.path.join(tmp, 'u.cbz')
with zipfile.ZipFile(cbz, 'w') as z:
    for i in (1, 2, 10, 11, 3):
        im = Image.new('RGB', (1800, 2400), (i * 20, 100, 150))
        z.writestr('p%d.jpg' % i, enc(im, 'JPEG', quality=90))
outc = os.path.join(tmp, 'u_out.cbz')
rep = optimize_comic(cbz, outc, P)
with zipfile.ZipFile(outc) as z:
    order = [n for n in z.namelist()]
check('natural ordering, p2 before p10',
      order.index('p2.jpg') < order.index('p10.jpg'), str(order))
check('all pages preserved', rep.pages == 5, str(rep.pages))

# 12 CBT (tar) is recognised
cbt = os.path.join(tmp, 't.cbt')
with tarfile.open(cbt, 'w') as t:
    for i in (1, 2):
        d = enc(Image.new('RGB', (1600, 2200), (i * 50, 50, 50)), 'JPEG')
        ti = tarfile.TarInfo('page%d.jpg' % i); ti.size = len(d)
        t.addfile(ti, io.BytesIO(d))
outt = os.path.join(tmp, 't_out.cbz')
try:
    rep = optimize_comic(cbt, outt, P)
    check('CBT is read and written as CBZ', rep.pages == 2 and
          zipfile.is_zipfile(outt), rep.source_format)
except Exception as e:
    check('CBT is read and written as CBZ', False, str(e))

# 13 CBR without an unpacker: a clear error, not a crash
cbr = os.path.join(tmp, 'x.cbr')
with open(cbr, 'wb') as f:
    f.write(b'Rar!\x1a\x07\x00' + b'\x00' * 500)
try:
    optimize_comic(cbr, os.path.join(tmp, 'x_out.cbz'), P)
    check('CBR without an unpacker reports an error', False, 'no exception raised')
except Exception as e:
    check('CBR without an unpacker reports an error', 'CBR' in str(e) or 'rar' in str(e).lower(),
          str(e)[:60])

print('')
print('Hardening regressions')

# 14 The result must never be larger than the original, not even when
#    the format changes. This used to be checked only for equal formats.
noise = Image.effect_noise((300, 300), 90).convert('RGB')
small_jpeg = enc(noise, 'JPEG', quality=35)
r = optimize_image(small_jpeg, P, png_to_jpeg='auto', quality=95)
check('no result larger than the original',
      len(r.data) <= len(small_jpeg),
      '%d -> %d' % (len(small_jpeg), len(r.data)))
check('a discarded result is reported as "no gain"',
      r.changed or r.reason == 'no gain', r.reason)

# 15 Same file name in two folders: references are rewritten by base
#    name, so no format conversion may happen here.
big = Image.new('RGB', (1800, 2400), (200, 30, 30))
for _y in range(0, 2400, 8):
    big.paste((30, 30, 200), (0, _y, 1800, _y + 4))
png = enc(big, 'PNG')
dup = os.path.join(tmp, 'dup.epub')
with zipfile.ZipFile(dup, 'w') as z:
    z.writestr('mimetype', 'application/epub+zip')
    z.writestr('OEBPS/content.opf',
               '<?xml version="1.0"?><package '
               'xmlns="http://www.idpf.org/2007/opf" version="3.0"><manifest>'
               '<item id="a" href="a/bild.png" media-type="image/png"/>'
               '<item id="b" href="b/bild.png" media-type="image/png"/>'
               '</manifest><spine/></package>')
    z.writestr('OEBPS/a/bild.png', png)
    z.writestr('OEBPS/b/bild.png', png)
dup_out = os.path.join(tmp, 'dup_out.epub')
rep = optimize_epub(dup, dup_out, P, png_to_jpeg=True)
with zipfile.ZipFile(dup_out) as z:
    dnames = z.namelist()
check('ambiguous image name is not renamed',
      'OEBPS/a/bild.png' in dnames and 'OEBPS/b/bild.png' in dnames,
      str([n for n in dnames if 'bild' in n]))
check('both images optimised regardless', rep.images_changed == 2,
      str(rep.images_changed))
check('the reason appears in the report',
      any('used more than once' in n for n in rep.notes), str(rep.notes[:1]))

# 16 An unambiguous name is still converted, and the reference follows
uni = os.path.join(tmp, 'uni.epub')
# Noise compresses badly as PNG and well as JPEG, so JPEG wins here.
photo = enc(Image.effect_noise((1800, 2400), 60).convert('RGB'), 'PNG')
with zipfile.ZipFile(uni, 'w') as z:
    z.writestr('mimetype', 'application/epub+zip')
    z.writestr('OEBPS/x.png', photo)
    z.writestr('OEBPS/t.xhtml', '<html><img src="x.png"/></html>')
uni_out = os.path.join(tmp, 'uni_out.epub')
rep = optimize_epub(uni, uni_out, P, png_to_jpeg=True)
with zipfile.ZipFile(uni_out) as z:
    unames = z.namelist()
    html = z.read('OEBPS/t.xhtml').decode('utf-8')
check('unambiguous name is converted to JPEG', 'OEBPS/x.jpg' in unames, str(unames))
check('the XHTML reference follows along',
      'x.jpg' in html and 'x.png' not in html, html.strip()[:50])

print('\n%s' % ('ALL EDGE CASES PASSED' if not FAILS
                else 'FAILED: %s' % ', '.join(FAILS)))
sys.exit(1 if FAILS else 0)
