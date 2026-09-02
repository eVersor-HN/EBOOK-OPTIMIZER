"""Image processing with a swappable backend.

Order: Pillow (preferred, fully tested) -> Qt/QImage via
calibre.utils.img (fallback, in case Calibre ships without Pillow).

Public API:
    optimize_image(data, profile, quality=..., ...) -> ImageResult
"""

import io
from dataclasses import dataclass

RASTER_EXT = {'.jpg', '.jpeg', '.jpe', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff'}
JPEG_FMTS = {'JPEG', 'JPG'}


@dataclass
class ImageResult:
    data: bytes             # optimised bytes, or the original if changed=False
    fmt: str                # 'JPEG' | 'PNG' | 'GIF' | ...
    width: int
    height: int
    changed: bool           # False = original kept (no gain, or skipped)
    reason: str = ''        # why it was skipped


# Beyond this multiple of the screen ratio an image counts as a long
# strip (webtoon) and is constrained by width only.
TALL_FACTOR = 2.0


def target_box(profile, ow, oh):
    """Maximum target size for an image of ow x oh.

    Three cases:
      * Landscape (a comic double spread): rotate the box, or the page
        would be shrunk far more than necessary.
      * Long strip (webtoon): constrain the width only. Forcing an
        800x3403 strip into screen height would leave 340x1448, which is
        unreadable. The reader scrolls anyway.
      * Ordinary page: fit inside the box.
    """
    max_w, max_h = profile.box
    if ow > oh and max_w < max_h:
        return max_h, max_w
    if oh > 0 and ow > 0:
        screen_ratio = float(max_h) / max_w
        if float(oh) / ow > screen_ratio * TALL_FACTOR:
            # Leave the height effectively unbounded.
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
        ow, oh = im.size                     # original size, before draft()
        if src_fmt == 'JPEG' and not upscale:
            # The JPEG decoder can scale down during decoding via DCT
            # scaling, which saves most of the time. draft() never goes
            # below the requested size; thumbnail() still does the exact
            # scaling afterwards.
            want_gray = (force_grayscale if force_grayscale is not None
                         else profile.grayscale)
            im.draft('L' if want_gray else None, target_box(profile, ow, oh))
        im.load()
    except Exception as e:
        return ImageResult(data, '', 0, 0, False, 'unreadable: %s' % e)

    src_fmt = (im.format or '').upper()

    # Leave animated GIF/WebP alone - a single frame would lose data.
    if getattr(im, 'n_frames', 1) > 1:
        return ImageResult(data, src_fmt, ow, oh, False, 'animated')

    has_alpha = im.mode in ('RGBA', 'LA', 'PA') or 'transparency' in im.info

    # --- Decide the target format(s) ------------------------------------
    # png_to_jpeg: False = keep the format, True = force JPEG,
    #              'auto' = encode both, the smaller result wins.
    base_fmt = src_fmt if src_fmt in ('JPEG', 'PNG', 'GIF', 'WEBP') else 'PNG'
    candidates = [base_fmt]
    if base_fmt in ('PNG', 'GIF', 'WEBP') and not has_alpha:
        if png_to_jpeg is True:
            candidates = ['JPEG']
        elif png_to_jpeg == 'auto':
            # JPEG first: it is cheap and provides the reference the
            # expensive PNG pass is judged against.
            candidates = ['JPEG', 'PNG']

    # --- Scale (down only) ----------------------------------------------
    max_w, max_h = target_box(profile, ow, oh)
    if upscale or ow > max_w or oh > max_h:
        im.thumbnail((max_w, max_h), Image.LANCZOS)

    # --- Colour ----------------------------------------------------------
    to_gray = force_grayscale if force_grayscale is not None else profile.grayscale
    keep_alpha = has_alpha and 'JPEG' not in candidates
    if to_gray:
        if keep_alpha:
            im = im.convert('LA')
        else:
            im = _flatten(im, has_alpha).convert('L')
    elif im.mode not in ('RGB', 'L', 'P'):
        im = _flatten(im, has_alpha).convert('RGB') if not keep_alpha else im

    # --- Encode (all candidates, smallest wins) --------------------------
    # Encoding PNG properly is by far the most expensive step. When JPEG is
    # available as an alternative, PNG is first encoded cheaply as a probe;
    # the expensive pass only follows if that probe is within striking
    # distance. The decision rests on a measurement, not an assumption
    # about the image content.
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
                    # A full encode is rarely more than a fifth smaller
                    # than the fast one, so if the probe is above that,
                    # PNG cannot win any more.
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
        return ImageResult(data, src_fmt, ow, oh, False, 'encoding failed')

    out, out_fmt = best
    # Bigger than the original is never a win, not even when the format
    # changed along the way.
    if len(out) >= len(data):
        return ImageResult(data, src_fmt, ow, oh, False, 'no gain')
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
        # The panel resolves only 16 grey levels; storing more than that
        # is wasted space.
        enc = _quantize_gray(enc, profile.gray_levels)
    buf = io.BytesIO()
    if fast:
        enc.save(buf, 'PNG', compress_level=1)
    else:
        enc.save(buf, 'PNG', optimize=True)
    return buf.getvalue()


def _flatten(im, has_alpha):
    """Composite transparency onto a white background."""
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
    """Fallback through calibre.utils.img (QImage).

    Only used when Pillow is missing from the Calibre environment.
    Fewer options than the Pillow path - no palette quantisation.
    """
    from calibre.utils.img import (image_from_data, image_to_data,
                                   grayscale_image, resize_image)

    try:
        img = image_from_data(data)
    except Exception as e:
        return ImageResult(data, '', 0, 0, False, 'unreadable: %s' % e)

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
        return ImageResult(data, src_fmt, ow, oh, False, 'no gain')
    return ImageResult(out, out_fmt, img.width(), img.height(), True)


# --------------------------------------------------------------- Fassade ---

def backend_name():
    if _pillow_available():
        return 'Pillow'
    if _qt_available():
        return 'Qt/QImage (calibre)'
    return 'none'


def optimize_image(data, profile, quality=80, png_to_jpeg=False,
                   force_grayscale=None, quantize_gray=True, upscale=False,
                   progressive=True):
    """Optimise a single image for the target device.

    force_grayscale: None = let the profile decide, True/False = force it.
    progressive: progressive JPEGs are about 6 % smaller. Very old e-ink
        devices can struggle with them - switch it off in that case.
    """
    if _pillow_available():
        fn = _pil_optimize
    elif _qt_available():
        fn = _qt_optimize
    else:
        return ImageResult(data, '', 0, 0, False, 'no image backend available')
    try:
        return fn(data, profile, quality, png_to_jpeg, force_grayscale,
                  quantize_gray, upscale, progressive)
    except Exception as e:
        return ImageResult(data, '', 0, 0, False, 'error: %s' % e)


EXT_FOR_FMT = {'JPEG': '.jpg', 'PNG': '.png', 'GIF': '.gif', 'WEBP': '.webp'}
MIME_FOR_FMT = {'JPEG': 'image/jpeg', 'PNG': 'image/png',
                'GIF': 'image/gif', 'WEBP': 'image/webp'}
