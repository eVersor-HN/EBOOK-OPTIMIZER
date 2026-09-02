"""Erzeugt synthetische Testdateien (EPUB + CBZ) mit realistischen Groessen."""

import os
import random
import zipfile

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'testdata')
os.makedirs(OUT, exist_ok=True)


def photo(w, h, seed=0):
    """Bild mit Struktur, damit Kompression realistisch wirkt."""
    random.seed(seed)
    im = Image.new('RGB', (w, h), (250, 248, 244))
    d = ImageDraw.Draw(im)
    for i in range(220):
        x0, y0 = random.randint(0, w), random.randint(0, h)
        x1, y1 = x0 + random.randint(20, w // 3), y0 + random.randint(20, h // 3)
        c = tuple(random.randint(20, 235) for _ in range(3))
        if i % 3 == 0:
            d.ellipse([x0, y0, x1, y1], fill=c)
        elif i % 3 == 1:
            d.rectangle([x0, y0, x1, y1], fill=c)
        else:
            d.line([x0, y0, x1, y1], fill=c, width=random.randint(2, 14))
    for _ in range(3000):
        x, y = random.randint(0, w - 1), random.randint(0, h - 1)
        im.putpixel((x, y), tuple(random.randint(0, 255) for _ in range(3)))
    return im


def make_epub(path):
    """EPUB mit uebergrossen Bildern (PNG + JPEG) und einer fetten Schrift."""
    cover = photo(1600, 2400, 1)
    fig_png = photo(2000, 1400, 2)
    fig_jpg = photo(1800, 1200, 3)

    tmp = {}
    import io
    b = io.BytesIO(); cover.save(b, 'JPEG', quality=95); tmp['cover.jpg'] = b.getvalue()
    b = io.BytesIO(); fig_png.save(b, 'PNG'); tmp['fig1.png'] = b.getvalue()
    b = io.BytesIO(); fig_jpg.save(b, 'JPEG', quality=95); tmp['fig2.jpg'] = b.getvalue()

    fake_font = bytes(random.Random(7).getrandbits(8) for _ in range(900_000))

    opf = '''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
 <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Testbuch</dc:title>
  <dc:language>de</dc:language>
  <dc:identifier id="id">urn:uuid:1234</dc:identifier>
 </metadata>
 <manifest>
  <item id="cover" href="images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>
  <item id="f1" href="images/fig1.png" media-type="image/png"/>
  <item id="f2" href="images/fig2.jpg" media-type="image/jpeg"/>
  <item id="css" href="style.css" media-type="text/css"/>
  <item id="fnt" href="fonts/Serif.ttf" media-type="font/ttf"/>
  <item id="c1" href="text/chapter1.xhtml" media-type="application/xhtml+xml"/>
  <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
 </manifest>
 <spine><itemref idref="c1"/></spine>
</package>'''

    css = '''@font-face {
  font-family: "MeinSerif";
  src: url("fonts/Serif.ttf");
  font-weight: normal;
}
body { font-family: "MeinSerif", serif; line-height: 1.4; }
.fig { max-width: 100%; }
'''

    chapter = '''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head>
<title>Kapitel 1</title><link rel="stylesheet" href="../style.css"/></head>
<body><h1>Kapitel 1</h1>
<p>Ein Absatz Text.</p>
<img class="fig" src="../images/fig1.png" alt="Abbildung 1"/>
<p>Noch ein Absatz.</p>
<img class="fig" src="../images/fig2.jpg" alt="Abbildung 2"/>
</body></html>'''

    nav = '''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Inhalt</title></head><body><nav epub:type="toc">
<ol><li><a href="text/chapter1.xhtml">Kapitel 1</a></li></ol></nav></body></html>'''

    container = '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf"
 media-type="application/oebps-package+xml"/></rootfiles></container>'''

    with zipfile.ZipFile(path, 'w') as z:
        zi = zipfile.ZipInfo('mimetype'); zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b'application/epub+zip')
        z.writestr('META-INF/container.xml', container)
        z.writestr('OEBPS/content.opf', opf)
        z.writestr('OEBPS/style.css', css)
        z.writestr('OEBPS/nav.xhtml', nav)
        z.writestr('OEBPS/text/chapter1.xhtml', chapter)
        z.writestr('OEBPS/fonts/Serif.ttf', fake_font)
        for n, d in tmp.items():
            z.writestr('OEBPS/images/' + n, d, zipfile.ZIP_STORED)


def make_cbz(path, pages=8):
    with zipfile.ZipFile(path, 'w') as z:
        for i in range(1, pages + 1):
            im = photo(2400, 3400, 100 + i)
            import io
            b = io.BytesIO(); im.save(b, 'JPEG', quality=95)
            z.writestr('page%02d.jpg' % i, b.getvalue(), zipfile.ZIP_STORED)
        z.writestr('ComicInfo.xml',
                   '<?xml version="1.0"?>\n<ComicInfo><Title>Testcomic</Title>'
                   '<PageCount>%d</PageCount></ComicInfo>' % pages)


if __name__ == '__main__':
    e = os.path.join(OUT, 'testbuch.epub')
    c = os.path.join(OUT, 'testcomic.cbz')
    make_epub(e)
    make_cbz(c)
    for p in (e, c):
        print('%s  %.2f MB' % (os.path.basename(p),
                               os.path.getsize(p) / 1024 / 1024))
