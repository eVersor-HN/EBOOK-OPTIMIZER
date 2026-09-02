"""Randfaelle: kaputte Bilder, Transparenz, Animation, exotische Modi."""

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


print('Bild-Randfaelle')

# 1 Transparenz darf bei Format-Beibehaltung nicht verloren gehen
rgba = Image.new('RGBA', (1800, 1200), (255, 0, 0, 0))
rgba.paste(Image.new('RGBA', (400, 400), (0, 0, 255, 255)), (10, 10))
r = optimize_image(enc(rgba, 'PNG'), P, png_to_jpeg='auto')
out = Image.open(io.BytesIO(r.data))
check('Alpha-PNG behaelt Transparenz', out.mode in ('LA', 'PA', 'RGBA', 'P'),
      out.mode)
check('Alpha-PNG bleibt PNG', r.fmt == 'PNG', r.fmt)

# 2 Erzwungenes JPEG darf Alpha nicht zerstoeren -> muss PNG bleiben
r = optimize_image(enc(rgba, 'PNG'), P, png_to_jpeg=True)
check('Alpha-PNG wird nicht zu JPEG gezwungen', r.fmt == 'PNG', r.fmt)

# 3 Animiertes GIF unangetastet (uebergross, damit Skalierung greifen wuerde)
frames = []
for i in range(6):
    f = Image.new('P', (2000, 1500), 0)
    f.paste(Image.new('P', (600, 400), 200), (i * 120, i * 90))
    frames.append(f)
b = io.BytesIO()
frames[0].save(b, 'GIF', save_all=True, append_images=frames[1:], duration=100)
gif = b.getvalue()
assert Image.open(io.BytesIO(gif)).n_frames > 1, 'Testdaten sind nicht animiert'
r = optimize_image(gif, P)
check('animiertes GIF bleibt unveraendert',
      not r.changed and r.data == gif and r.reason == 'animiert', r.reason)

# 4 Defekte Datei -> kein Absturz, Original zurueck
r = optimize_image(b'\x89PNG\r\n\x1a\n GARBAGE' * 20, P)
check('defektes Bild wird abgefangen', not r.changed, r.reason)

# 5 CMYK-JPEG
cmyk = Image.new('CMYK', (1600, 1200), (10, 20, 30, 5))
r = optimize_image(enc(cmyk, 'JPEG', quality=95), P)
check('CMYK-JPEG konvertiert', r.changed and
      Image.open(io.BytesIO(r.data)).mode == 'L')

# 6 Kleines Bild wird nicht hochskaliert
small = Image.new('RGB', (120, 90), (200, 100, 50))
r = optimize_image(enc(small, 'PNG'), P)
sz = Image.open(io.BytesIO(r.data)).size if r.changed else (120, 90)
check('kleines Bild wird nicht vergroessert', sz == (120, 90), str(sz))

# 7 Querformat-Doppelseite: Box wird gedreht, nicht kaputt skaliert
wide = Image.new('RGB', (3000, 2000), (30, 30, 30))
r = optimize_image(enc(wide, 'JPEG', quality=95), P)
w, h = Image.open(io.BytesIO(r.data)).size
check('Doppelseite nutzt lange Kante', w == 1448 and h <= 1072, '%dx%d' % (w, h))

# 8 1-Bit-Strichzeichnung
bw = Image.new('1', (2000, 2600), 1)
r = optimize_image(enc(bw, 'PNG'), P)
check('1-Bit-Bild verarbeitbar', r.changed or r.reason == 'kein Gewinn', r.reason)


print('\nArchiv-Randfaelle')
tmp = tempfile.mkdtemp()

# 9 EPUB ohne Bilder und ohne Fonts
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
check('EPUB ohne Bilder laeuft durch', rep.images == 0 and os.path.exists(out))
with zipfile.ZipFile(out) as z:
    check('EPUB ohne Bilder bleibt lesbar', z.testzip() is None and
          z.read('t.xhtml').startswith(b'<html'))

# 10 EPUB mit Junk-Dateien
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
check('Junk-Dateien entfernt',
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
check('natuerliche Sortierung (p2 vor p10)',
      order.index('p2.jpg') < order.index('p10.jpg'), str(order))
check('alle Seiten erhalten', rep.pages == 5, str(rep.pages))

# 12 CBT (tar) wird erkannt
cbt = os.path.join(tmp, 't.cbt')
with tarfile.open(cbt, 'w') as t:
    for i in (1, 2):
        d = enc(Image.new('RGB', (1600, 2200), (i * 50, 50, 50)), 'JPEG')
        ti = tarfile.TarInfo('page%d.jpg' % i); ti.size = len(d)
        t.addfile(ti, io.BytesIO(d))
outt = os.path.join(tmp, 't_out.cbz')
try:
    rep = optimize_comic(cbt, outt, P)
    check('CBT wird gelesen und zu CBZ', rep.pages == 2 and
          zipfile.is_zipfile(outt), rep.source_format)
except Exception as e:
    check('CBT wird gelesen und zu CBZ', False, str(e))

# 13 CBR ohne Entpacker -> klare Fehlermeldung, kein Absturz
cbr = os.path.join(tmp, 'x.cbr')
with open(cbr, 'wb') as f:
    f.write(b'Rar!\x1a\x07\x00' + b'\x00' * 500)
try:
    optimize_comic(cbr, os.path.join(tmp, 'x_out.cbz'), P)
    check('CBR ohne Entpacker meldet Fehler', False, 'keine Exception')
except Exception as e:
    check('CBR ohne Entpacker meldet Fehler', 'CBR' in str(e) or 'rar' in str(e).lower(),
          str(e)[:60])

print('')
print('Regressionen der Haertung')

# 14 Ergebnis darf nie groesser sein als das Original - auch dann nicht,
#    wenn dabei das Format wechselt (frueher nur bei gleichem Format geprueft).
noise = Image.effect_noise((300, 300), 90).convert('RGB')
small_jpeg = enc(noise, 'JPEG', quality=35)
r = optimize_image(small_jpeg, P, png_to_jpeg='auto', quality=95)
check('kein Ergebnis groesser als das Original',
      len(r.data) <= len(small_jpeg),
      '%d -> %d' % (len(small_jpeg), len(r.data)))
check('verworfenes Ergebnis wird als "kein Gewinn" gemeldet',
      r.changed or r.reason == 'kein Gewinn', r.reason)

# 15 Gleicher Dateiname in zwei Ordnern: Referenzen werden ueber den
#    Basisnamen umgeschrieben, deshalb darf hier nicht konvertiert werden.
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
check('mehrdeutiger Bildname wird nicht umbenannt',
      'OEBPS/a/bild.png' in dnames and 'OEBPS/b/bild.png' in dnames,
      str([n for n in dnames if 'bild' in n]))
check('beide Bilder trotzdem optimiert', rep.images_changed == 2,
      str(rep.images_changed))
check('Grund steht im Bericht',
      any('mehrfach vergeben' in n for n in rep.notes), str(rep.notes[:1]))

# 16 Eindeutiger Name wird weiterhin konvertiert, Referenz zieht mit
uni = os.path.join(tmp, 'uni.epub')
# Rauschen komprimiert als PNG schlecht, als JPEG gut - hier gewinnt JPEG.
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
check('eindeutiger Name wird zu JPEG', 'OEBPS/x.jpg' in unames, str(unames))
check('Referenz im XHTML mitgezogen',
      'x.jpg' in html and 'x.png' not in html, html.strip()[:50])

print('\n%s' % ('ALLE RANDFAELLE BESTANDEN' if not FAILS
                else 'FEHLGESCHLAGEN: %s' % ', '.join(FAILS)))
sys.exit(1 if FAILS else 0)
