"""Bildverarbeitung mit austauschbarem Backend.

Reihenfolge: Pillow (bevorzugt, voll getestet) -> Qt/QImage via
calibre.utils.img (Fallback, falls Calibre ohne Pillow ausgeliefert wird).

Oeffentliche API:
    optimize_image(data, profile, quality=..., ...) -> ImageResult
"""

import io
from dataclasses import dataclass

RASTER_EXT = {'.jpg', '.jpeg', '.jpe', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff'}
JPEG_FMTS = {'JPEG', 'JPG'}


@dataclass
class ImageResult:
    data: bytes             # optimierte Bytes (oder Original, wenn changed=False)
    fmt: str                # 'JPEG' | 'PNG' | 'GIF' | ...
    width: int
    height: int
    changed: bool           # False = Original beibehalten (kein Gewinn / uebersprungen)
    reason: str = ''        # Grund, falls uebersprungen


# Ab diesem Vielfachen des Bildschirmverhaeltnisses gilt ein Bild als
# Langstreifen (Webtoon) und wird nur noch in der Breite begrenzt.
TALL_FACTOR = 2.0


def target_box(profile, ow, oh):
    """Maximale Zielabmessung fuer ein Bild der Groesse ow x oh.

    Drei Faelle:
      * Querformat (Comic-Doppelseite): Box drehen, sonst wuerde die Seite
        unnoetig stark verkleinert.
      * Langstreifen (Webtoon): nur die Breite begrenzen. Wuerde man einen
        800x3403-Streifen in die Bildschirmhoehe zwaengen, blieben 340x1448
        uebrig - unlesbar. Der Leser scrollt ohnehin.
      * Normale Seite: in die Box einpassen.
    """
    max_w, max_h = profile.box
    if ow > oh and max_w < max_h:
        return max_h, max_w
    if oh > 0 and ow > 0:
        screen_ratio = float(max_h) / max_w
        if float(oh) / ow > screen_ratio * TALL_FACTOR:
            # Hoehe faktisch unbegrenzt lassen.
            return max_w, oh
    return max_w, max_h


# ---------------------------------------------------------------- Pillow ---

def _pillow():
    from PIL import Image
    return Image


def _pillow_available():
    try:
        _pillow()
        return True
    except Exception:
        return False


def _pil_optimize(data, profile, quality, png_to_jpeg, force_grayscale,
                  quantize_gray, upscale=False, progressive=True):
    Image = _pillow()
    try:
        im = Image.open(io.BytesIO(data))
        src_fmt = (im.format or '').upper()
        ow, oh = im.size                     # Originalmasse, vor draft()
        if src_fmt == 'JPEG' and not upscale:
            # Der JPEG-Decoder kann per DCT-Skalierung gleich verkleinert
            # dekodieren. Das spart den groessten Teil der Zeit; draft()
            # unterschreitet die Zielgroesse nie, das Feinskalieren
            # uebernimmt danach wie gehabt thumbnail().
            want_gray = (force_grayscale if force_grayscale is not None
                         else profile.grayscale)
            im.draft('L' if want_gray else None, target_box(profile, ow, oh))
        im.load()
    except Exception as e:
        return ImageResult(data, '', 0, 0, False, 'nicht lesbar: %s' % e)

    src_fmt = (im.format or '').upper()

    # Animierte GIF/WebP unangetastet lassen - Einzelbild waere Datenverlust.
    if getattr(im, 'n_frames', 1) > 1:
        return ImageResult(data, src_fmt, ow, oh, False, 'animiert')

    has_alpha = im.mode in ('RGBA', 'LA', 'PA') or 'transparency' in im.info

    # --- Zielformat(e) bestimmen ----------------------------------------
    # png_to_jpeg: False = Format behalten, True = erzwingen,
    #              'auto' = beides kodieren, kleineres Ergebnis gewinnt.
    base_fmt = src_fmt if src_fmt in ('JPEG', 'PNG', 'GIF', 'WEBP') else 'PNG'
    candidates = [base_fmt]
    if base_fmt in ('PNG', 'GIF', 'WEBP') and not has_alpha:
        if png_to_jpeg is True:
            candidates = ['JPEG']
        elif png_to_jpeg == 'auto':
            # JPEG zuerst: es ist billig und liefert den Vergleichswert,
            # an dem sich der teure PNG-Durchlauf entscheidet.
            candidates = ['JPEG', 'PNG']

    # --- Skalieren (nur verkleinern) ------------------------------------
    max_w, max_h = target_box(profile, ow, oh)
    if upscale or ow > max_w or oh > max_h:
        im.thumbnail((max_w, max_h), Image.LANCZOS)

    # --- Farbraum --------------------------------------------------------
    to_gray = force_grayscale if force_grayscale is not None else profile.grayscale
    keep_alpha = has_alpha and 'JPEG' not in candidates
    if to_gray:
        if keep_alpha:
            im = im.convert('LA')
        else:
            im = _flatten(im, has_alpha).convert('L')
    elif im.mode not in ('RGB', 'L', 'P'):
        im = _flatten(im, has_alpha).convert('RGB') if not keep_alpha else im

    # --- Kodieren (alle Kandidaten, kleinster gewinnt) -------------------
    # PNG voll zu kodieren ist mit Abstand der teuerste Schritt. Steht JPEG
    # als Alternative bereit, wird PNG erst billig probeweise kodiert; nur
    # wenn diese Probe in Schlagdistanz liegt, folgt der teure Durchlauf.
    # Die Entscheidung beruht damit auf einer Messung, nicht auf einer
    # Annahme ueber den Bildinhalt.
    both = 'PNG' in candidates and 'JPEG' in candidates

    best = None
    jpeg_size = None
    for fmt in candidates:
        try:
            if fmt == 'JPEG':
                cand = _encode_jpeg(im, quality, to_gray, progressive)
                jpeg_size = len(cand)
            elif fmt == 'PNG':
                if both and jpeg_size is not None:
                    probe = _encode_png(im, profile, to_gray, quantize_gray,
                                        fast=True)
                    # Die volle Kodierung wird kaum je mehr als ein Fuenftel
                    # kleiner als die schnelle - liegt die Probe darueber,
                    # kann PNG nicht mehr gewinnen.
                    if len(probe) * 0.8 > jpeg_size:
                        continue
                cand = _encode_png(im, profile, to_gray, quantize_gray)
            elif fmt == 'WEBP':
                buf = io.BytesIO()
                im.save(buf, 'WEBP', quality=quality, method=4)
                cand = buf.getvalue()
            else:
                buf = io.BytesIO()
                im.save(buf, fmt)
                cand = buf.getvalue()
        except Exception:
            continue
        if best is None or len(cand) < len(best[0]):
            best = (cand, fmt)

    if best is None:
        return ImageResult(data, src_fmt, ow, oh, False, 'Kodierung gescheitert')

    out, out_fmt = best
    # Groesser als das Original ist nie ein Gewinn - auch dann nicht, wenn
    # sich dabei das Format geaendert hat.
    if len(out) >= len(data):
        return ImageResult(data, src_fmt, ow, oh, False, 'kein Gewinn')
    return ImageResult(out, out_fmt, im.width, im.height, True)


def _encode_jpeg(im, quality, to_gray, progressive):
    enc = im if im.mode in ('L', 'RGB') else _flatten(im, True)
    if enc.mode not in ('L', 'RGB'):
        enc = enc.convert('L' if to_gray else 'RGB')
    buf = io.BytesIO()
    enc.save(buf, 'JPEG', quality=quality, optimize=True,
             progressive=progressive,
             subsampling=0 if enc.mode == 'L' else 2)
    return buf.getvalue()


def _encode_png(im, profile, to_gray, quantize_gray, fast=False):
    enc = im
    if to_gray and quantize_gray and profile.gray_levels:
        # Panel kann nur 16 Graustufen - mehr zu speichern ist
        # verschenkter Platz.
        enc = _quantize_gray(enc, profile.gray_levels)
    buf = io.BytesIO()
    if fast:
        enc.save(buf, 'PNG', compress_level=1)
    else:
        enc.save(buf, 'PNG', optimize=True)
    return buf.getvalue()


def _flatten(im, has_alpha):
    """Transparenz auf weissem Grund einrechnen."""
    if not has_alpha:
        return im
    Image = _pillow()
    rgba = im.convert('RGBA')
    bg = Image.new('RGB', rgba.size, (255, 255, 255))
    bg.paste(rgba, mask=rgba.split()[-1])
    return bg


def _quantize_gray(im, levels):
    Image = _pillow()
    if im.mode not in ('L', 'LA'):
        im = im.convert('L')
    if im.mode == 'LA':
        return im
    step = 256 // levels
    lut = [min(255, (v // step) * step + step // 2) for v in range(256)]
    im = im.point(lut)
    return im.convert('P', palette=Image.ADAPTIVE, colors=levels)


# -------------------------------------------------------- Qt / Calibre ---

def _qt_available():
    try:
        from calibre.utils.img import image_from_data  # noqa: F401
        return True
    except Exception:
        return False


def _qt_optimize(data, profile, quality, png_to_jpeg, force_grayscale,
                 quantize_gray, upscale=False, progressive=True):
    """Fallback ueber calibre.utils.img (QImage).

    ACHTUNG: nur aktiv, wenn Pillow in der Calibre-Umgebung fehlt.
    Weniger Optionen als der Pillow-Pfad (keine Palettenquantisierung).
    """
    from calibre.utils.img import (image_from_data, image_to_data,
                                   grayscale_image, resize_image)

    try:
        img = image_from_data(data)
    except Exception as e:
        return ImageResult(data, '', 0, 0, False, 'nicht lesbar: %s' % e)

    ow, oh = img.width(), img.height()
    src_fmt = 'JPEG' if data[:2] == b'\xff\xd8' else 'PNG'
    out_fmt = 'JPEG' if (png_to_jpeg or src_fmt == 'JPEG') else 'PNG'

    max_w, max_h = target_box(profile, ow, oh)
    if upscale or ow > max_w or oh > max_h:
        scale = min(max_w / ow, max_h / oh)
        img = resize_image(img, int(ow * scale), int(oh * scale))

    to_gray = force_grayscale if force_grayscale is not None else profile.grayscale
    if to_gray:
        img = grayscale_image(img)

    out = image_to_data(img, compression_quality=quality, fmt=out_fmt)
    if len(out) >= len(data):
        return ImageResult(data, src_fmt, ow, oh, False, 'kein Gewinn')
    return ImageResult(out, out_fmt, img.width(), img.height(), True)


# --------------------------------------------------------------- Fassade ---

def backend_name():
    if _pillow_available():
        return 'Pillow'
    if _qt_available():
        return 'Qt/QImage (calibre)'
    return 'keins'


def optimize_image(data, profile, quality=80, png_to_jpeg=False,
                   force_grayscale=None, quantize_gray=True, upscale=False,
                   progressive=True):
    """Optimiert ein einzelnes Bild fuer das Zielgeraet.

    force_grayscale: None = Profil entscheiden lassen, True/False = erzwingen.
    progressive: progressive JPEGs sind rund 6 % kleiner. Sehr alte E-Ink-
        Geraete koennen damit Probleme haben - dann abschalten.
    """
    if _pillow_available():
        fn = _pil_optimize
    elif _qt_available():
        fn = _qt_optimize
    else:
        return ImageResult(data, '', 0, 0, False, 'kein Bild-Backend verfuegbar')
    try:
        return fn(data, profile, quality, png_to_jpeg, force_grayscale,
                  quantize_gray, upscale, progressive)
    except Exception as e:
        return ImageResult(data, '', 0, 0, False, 'Fehler: %s' % e)


EXT_FOR_FMT = {'JPEG': '.jpg', 'PNG': '.png', 'GIF': '.gif', 'WEBP': '.webp'}
MIME_FOR_FMT = {'JPEG': 'image/jpeg', 'PNG': 'image/png',
                'GIF': 'image/gif', 'WEBP': 'image/webp'}
