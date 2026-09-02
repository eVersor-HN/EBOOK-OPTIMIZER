"""PDF optimisation that keeps the PDF a PDF.

Scanned books must not go through a text converter - that throws the
page facsimiles away. Instead the images inside the PDF are rewritten
for the target panel and everything else (text layer, structure,
outline) is left in place, so the result stays searchable.

What happens per image:
  * downscale to the panel, greyscale on monochrome devices
  * two candidates are encoded and the smaller one wins:
      - JPEG at a per-image measured quality (the usual budget search)
      - JPEG 2000 at a fixed, visually validated rate. Scans carry
        grain, and grain makes the pixel metric useless there - it
        counts reshuffled noise, not legibility. The rates used here
        were chosen by eye on real 1940s book scans: rate 20 reads
        identically to the source, rate 40 is minimally softer.
  * the original is kept when neither candidate is smaller

Deliberately not touched:
  * images with masks (SMask or JBIG2 stencils). Those are MRC scans -
    a bilevel text mask over a background - as produced by archive.org.
    They are already close to optimal and repainting only one layer
    breaks the composite.
  * bilevel images (JBIG2/CCITT), which are already tiny
  * everything that is not an image

Needs pikepdf. Without it, PDF optimisation reports the missing module
instead of falling back to anything destructive.
"""

import io
import os

from .imaging import _find_quality, target_box
from .util import human_size  # noqa: F401  (re-exported for callers)

# Visually validated on real book scans; see the module docstring.
JP2_RATE_IDENTICAL = 20
JP2_RATE_SMALLER = 40


class PdfReport:
    def __init__(self, path):
        self.path = path
        self.old_size = 0
        self.new_size = 0
        self.images = 0
        self.images_changed = 0
        self.images_kept = 0
        self.notes = []

    @property
    def saved(self):
        return self.old_size - self.new_size


def pikepdf_available():
    try:
        import pikepdf                              # noqa: F401
        return True
    except Exception:
        return False


class PikepdfMissing(RuntimeError):
    """PDF optimisation needs pikepdf, which is not installed."""


def _eligible(pikepdf, obj):
    """Is this XObject an image we can safely rewrite?"""
    if obj.get('/Subtype') != pikepdf.Name('/Image'):
        return False
    if '/SMask' in obj or '/Mask' in obj:
        return False                    # MRC composite, leave alone
    if obj.get('/ImageMask', False):
        return False                    # stencil mask
    if int(obj.get('/BitsPerComponent', 8)) == 1:
        return False                    # bilevel, already tiny
    return True


def _encode_jp2(im, rate):
    buf = io.BytesIO()
    im.save(buf, 'JPEG2000', irreversible=True, quality_mode='rates',
            quality_layers=[rate])
    return buf.getvalue()


def optimize_pdf(src, dst, profile, quality=80, force_grayscale=None,
                 quantize_gray=True, progressive=True, jobs=1,
                 target_error=None, png_mode=None, fonts=None):
    """Rewrite the images inside a PDF for the target device.

    Signature-compatible with the other optimisers; quantize_gray,
    png_mode and fonts do not apply to PDFs and are accepted only so the
    pipeline can pass one option set everywhere.
    Returns a PdfReport.
    """
    if not pikepdf_available():
        raise PikepdfMissing(
            'PDF optimisation needs the Python module "pikepdf" '
            '(pip install pikepdf). Converting PDFs to other formats '
            'works without it.')
    import pikepdf
    from PIL import Image

    rep = PdfReport(src)
    rep.old_size = os.path.getsize(src)
    to_gray = force_grayscale if force_grayscale is not None \
        else profile.grayscale
    # target_error None means a pinned quality was requested; the JP2
    # candidate then uses the looser, still eye-checked rate.
    jp2_rate = (JP2_RATE_IDENTICAL
                if (target_error or 0) <= 0.25 else JP2_RATE_SMALLER)

    pdf = pikepdf.open(src)
    try:
        seen = set()
        for page in pdf.pages:
            res = page.get('/Resources')
            xo = res.get('/XObject') if res else None
            if not xo:
                continue
            for name in list(xo.keys()):
                obj = xo[name]
                try:
                    if obj.objgen in seen:
                        continue
                    seen.add(obj.objgen)
                    if not _eligible(pikepdf, obj):
                        continue
                    rep.images += 1
                    raw_len = len(obj.read_raw_bytes())
                    try:
                        im = pikepdf.PdfImage(obj).as_pil_image()
                        im.load()
                    except Exception:
                        rep.images_kept += 1
                        continue
                    ow, oh = im.size
                    mw, mh = target_box(profile, ow, oh)
                    if ow > mw or oh > mh:
                        im.thumbnail((mw, mh), Image.LANCZOS)
                    if to_gray:
                        im = im.convert('L')
                    elif im.mode not in ('L', 'RGB'):
                        im = im.convert('RGB')

                    if target_error:
                        _q, jpeg = _find_quality(im, target_error, to_gray,
                                                 progressive)
                    else:
                        from .imaging import _encode_jpeg
                        jpeg = _encode_jpeg(im, quality, to_gray,
                                            progressive)
                    try:
                        jp2 = _encode_jp2(im, jp2_rate)
                    except Exception:
                        jp2 = None

                    best, filt = jpeg, '/DCTDecode'
                    if jp2 is not None and len(jp2) < len(best):
                        best, filt = jp2, '/JPXDecode'
                    if len(best) >= raw_len:
                        rep.images_kept += 1
                        continue

                    obj.write(best, filter=pikepdf.Name(filt))
                    obj['/ColorSpace'] = pikepdf.Name(
                        '/DeviceGray' if im.mode == 'L' else '/DeviceRGB')
                    obj['/BitsPerComponent'] = 8
                    obj['/Width'] = im.width
                    obj['/Height'] = im.height
                    for k in ('/DecodeParms', '/Decode', '/Intent',
                              '/Interpolate'):
                        if k in obj:
                            del obj[k]
                    rep.images_changed += 1
                except Exception as e:
                    rep.images_kept += 1
                    if len(rep.notes) < 5:
                        rep.notes.append('%s: %s' % (name, str(e)[:60]))

        pdf.save(dst,
                 compress_streams=True,
                 object_stream_mode=pikepdf.ObjectStreamMode.generate,
                 recompress_flate=True)
    finally:
        pdf.close()

    rep.new_size = os.path.getsize(dst)
    return rep
