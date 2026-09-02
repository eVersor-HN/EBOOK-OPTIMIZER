"""Comic optimisation (CBZ / CBR / CBT) for e-ink devices.

  * scale pages to the panel, convert to greyscale, re-encode
  * CBR/CBT -> CBZ: more widely supported, and no RAR unpacker needed
    to read the result
  * ComicInfo.xml is preserved, manga reading direction is optional
  * written with ZIP_STORED, because JPEGs are already compressed
"""

import os
import posixpath
import re
import shutil
import subprocess
import tempfile
import zipfile

from .imaging import EXT_FOR_FMT, RASTER_EXT, optimize_image
from .pool import optimize_many
from .util import ext_of, is_junk, natural_key

COMIC_EXT = {'.cbz', '.cbr', '.cbt', '.zip', '.rar'}


class CbzReport:
    def __init__(self, path):
        self.path = path
        self.old_size = 0
        self.new_size = 0
        self.pages = 0
        self.pages_changed = 0
        self.source_format = ''
        self.notes = []

    @property
    def saved(self):
        return self.old_size - self.new_size


# ------------------------------------------------------------- Entpacken ---

def _iter_zip(path):
    with zipfile.ZipFile(path, 'r') as z:
        for name in z.namelist():
            if name.endswith('/') or is_junk(name):
                continue
            yield name, z.read(name)


def _iter_tar(path):
    import tarfile
    with tarfile.open(path, 'r:*') as t:
        for m in t.getmembers():
            if not m.isfile() or is_junk(m.name):
                continue
            f = t.extractfile(m)
            if f:
                yield m.name, f.read()


def _iter_rar(path):
    """Unpack a CBR. Tried in order:
    rarfile -> calibre.utils.unrar -> external unrar/7z/bsdtar.
    """
    try:
        import rarfile
        with rarfile.RarFile(path) as rf:
            for info in rf.infolist():
                if info.isdir() or is_junk(info.filename):
                    continue
                yield info.filename, rf.read(info)
        return
    except ImportError:
        pass

    try:
        from calibre.utils.unrar import extract
        tmp = tempfile.mkdtemp(prefix='ebook_opt_rar_')
        try:
            extract(path, tmp)
            for root, _dirs, files in os.walk(tmp):
                for fn in sorted(files):
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, tmp).replace(os.sep, '/')
                    if is_junk(rel):
                        continue
                    with open(full, 'rb') as fh:
                        yield rel, fh.read()
            return
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass

    for cmd in (['unrar', 'x', '-y', '-inul'], ['7z', 'x', '-y'],
                ['bsdtar', '-xf']):
        exe = shutil.which(cmd[0])
        if not exe:
            continue
        tmp = tempfile.mkdtemp(prefix='ebook_opt_rar_')
        try:
            if cmd[0] == 'bsdtar':
                args = [exe, '-xf', path, '-C', tmp]
            elif cmd[0] == '7z':
                args = [exe, 'x', '-y', '-o' + tmp, path]
            else:
                args = [exe, 'x', '-y', '-inul', path, tmp + os.sep]
            subprocess.run(args, check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            for root, _dirs, files in os.walk(tmp):
                for fn in sorted(files):
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, tmp).replace(os.sep, '/')
                    if is_junk(rel):
                        continue
                    with open(full, 'rb') as fh:
                        yield rel, fh.read()
            return
        except Exception:
            continue
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    raise RuntimeError(
        'Cannot unpack CBR: neither the Python module "rarfile" nor '
        'unrar/7z/bsdtar was found.')


def _read_archive(path):
    ext = ext_of(path)
    if zipfile.is_zipfile(path):
        return 'CBZ', list(_iter_zip(path))
    if ext in ('.cbt',):
        return 'CBT', list(_iter_tar(path))
    try:
        return 'CBR', list(_iter_rar(path))
    except Exception:
        import tarfile
        if tarfile.is_tarfile(path):
            return 'CBT', list(_iter_tar(path))
        raise


# ----------------------------------------------------------- ComicInfo ---

MANGA_RE = re.compile(r'<Manga>.*?</Manga>', re.I | re.S)


def _set_manga(xml_bytes):
    try:
        text = xml_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return xml_bytes
    if MANGA_RE.search(text):
        text = MANGA_RE.sub('<Manga>YesAndRightToLeft</Manga>', text)
    else:
        text = re.sub(r'(</ComicInfo>)',
                      '  <Manga>YesAndRightToLeft</Manga>\n\\1', text, count=1,
                      flags=re.I)
    return text.encode('utf-8')


def _new_comicinfo():
    return (b'<?xml version="1.0" encoding="utf-8"?>\n'
            b'<ComicInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
            b'  <Manga>YesAndRightToLeft</Manga>\n'
            b'</ComicInfo>\n')


# ------------------------------------------------------------ Hauptlogik ---

def optimize_comic(src, dst, profile, quality=80, force_grayscale=None,
                   manga=False, to_jpeg='auto', quantize_gray=True,
                   skip_smaller_than=2048, progressive=True, jobs=1,
                   target_error=None):
    """Optimise a comic archive; the output is always CBZ.

    jobs: process pages in parallel (1 = serial).
    Returns a CbzReport.
    """
    rep = CbzReport(src)
    rep.old_size = os.path.getsize(src)

    fmt, entries = _read_archive(src)
    rep.source_format = fmt

    images = [(n, d) for n, d in entries if ext_of(n) in RASTER_EXT]
    others = [(n, d) for n, d in entries if ext_of(n) not in RASTER_EXT]
    images.sort(key=lambda t: natural_key(t[0]))

    # Optimise all pages in one go - this is the expensive part and it
    # spreads across CPU cores.
    todo = [(n, d) for n, d in images if len(d) >= skip_smaller_than]
    done = optimize_many(todo, profile, jobs=jobs, quality=quality,
                         png_to_jpeg=to_jpeg,
                         force_grayscale=force_grayscale,
                         quantize_gray=quantize_gray,
                         progressive=progressive,
                         target_error=target_error)

    out_entries = []
    used = set()
    for name, data in images:
        rep.pages += 1
        if name not in done:
            out_entries.append((name, data))
            used.add(name)
            continue
        res = done[name]
        if res.changed:
            rep.pages_changed += 1
            want_ext = EXT_FOR_FMT.get(res.fmt, ext_of(name))
            new_name = posixpath.splitext(name)[0] + want_ext
            i = 1
            while new_name in used:
                new_name = '%s_%d%s' % (posixpath.splitext(name)[0], i, want_ext)
                i += 1
            out_entries.append((new_name, res.data))
            used.add(new_name)
        else:
            out_entries.append((name, data))
            used.add(name)
            if res.reason and res.reason != 'kein Gewinn':
                rep.notes.append('%s: %s' % (name, res.reason))

    have_comicinfo = False
    for name, data in others:
        if posixpath.basename(name).lower() == 'comicinfo.xml':
            have_comicinfo = True
            if manga:
                data = _set_manga(data)
        out_entries.append((name, data))
    if manga and not have_comicinfo:
        out_entries.append(('ComicInfo.xml', _new_comicinfo()))

    with zipfile.ZipFile(dst, 'w') as zout:
        for name, data in out_entries:
            comp = (zipfile.ZIP_STORED if ext_of(name) in RASTER_EXT
                    else zipfile.ZIP_DEFLATED)
            zout.writestr(name, data, compress_type=comp)

    rep.new_size = os.path.getsize(dst)
    return rep
