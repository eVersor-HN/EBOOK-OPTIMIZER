"""Local web interface for EBOOK-OPTIMIZER.

Binds to 127.0.0.1 only and needs nothing beyond the standard library.
The browser is just the display; the work happens in this Python process.

Start:  python -m ebook_optimizer.web
"""

import json
import mimetypes
import os
import shutil
import string
import subprocess
import sys
import threading
import time
import traceback
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from ..core import convert as conv
from ..core.cbz import COMIC_EXT
from ..core.imaging import backend_name
from ..core.pipeline import process, target_name
from ..core.pool import default_jobs
from ..core.profiles import (DEFAULT_PROFILE, DEFAULT_TARGET, TARGET_ORDER,
                             TARGETS, get_profile, profiles_by_brand)
from ..core.util import ext_of, pct_saved

from .. import __version__ as VERSION

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
NATIVE_EXT = {'.epub', '.kepub'} | COMIC_EXT

# Calibre also reads .txt, .html and friends. Walking a folder must not
# sweep those up, or every README would be converted along with the books.
SCAN_SKIP_EXT = {'.txt', '.text', '.htm', '.html', '.xhtm', '.xhtml',
                 '.md', '.markdown', '.textile', '.opf', '.recipe',
                 '.zip', '.rar', '.shtm', '.shtml'}

# Folders we write into ourselves, skipped when walking so a second run
# does not re-optimise its own output.
OUTPUT_DIR_NAMES = {'optimized', 'optimiert'}

# Running and finished jobs.
_jobs = {}


# ------------------------------------------------------------------ Data ---

def known_ext(scanning=False):
    ext = set(NATIVE_EXT)
    if conv.available():
        ext |= {'.' + f for f in conv.input_formats()}
    if scanning:
        ext -= SCAN_SKIP_EXT
    return ext


def status():
    return {
        'version': VERSION,
        'calibre': bool(conv.available()),
        'calibreVersion': conv.version(),
        'backend': backend_name(),
        'cpus': default_jobs(),
        'deviceGroups': [
            {'brand': brand,
             'devices': [{'key': p.key, 'name': p.name, 'width': p.width,
                          'height': p.height, 'gray': p.grayscale}
                         for p in group]}
            for brand, group in profiles_by_brand()],
        'defaultProfile': DEFAULT_PROFILE,
        'targets': [{'key': TARGETS[k].key, 'name': TARGETS[k].name,
                     'budget': TARGETS[k].budget,
                     'quantize': TARGETS[k].quantize,
                     'summary': TARGETS[k].summary,
                     'measured': TARGETS[k].measured}
                    for k in TARGET_ORDER],
        'defaultTarget': DEFAULT_TARGET,
        'formats': (sorted(set(conv.output_formats()) | {'cbz'})
                    if conv.available() else ['cbz', 'epub', 'kepub']),
        'nativeFormats': ['epub', 'kepub', 'cbz'],
    }


def list_dir(path):
    """Folder contents, for the browser's folder picker."""
    if not path:
        # Top level: drives on Windows, the home folder elsewhere.
        if sys.platform == 'win32':
            drives = ['%s:\\' % d for d in string.ascii_uppercase
                      if os.path.exists('%s:\\' % d)]
            return {'path': '', 'parent': None, 'sep': os.sep,
                    'rootLabel': 'Drives',
                    'dirs': [{'name': d, 'path': d} for d in drives],
                    'files': []}
        path = os.path.expanduser('~')

    path = os.path.abspath(path)
    if not os.path.isdir(path):
        raise ValueError('Not a folder: %s' % path)

    parent = os.path.dirname(path.rstrip(os.sep))
    if parent == path or (sys.platform == 'win32'
                          and len(path.rstrip(os.sep)) <= 2):
        parent = ''

    dirs, files = [], []
    exts = known_ext(scanning=True)
    try:
        entries = sorted(os.scandir(path), key=lambda e: e.name.lower())
    except PermissionError:
        raise ValueError('No access to %s' % path)
    for e in entries:
        if e.name.startswith('.'):
            continue
        try:
            if e.is_dir():
                dirs.append({'name': e.name, 'path': e.path})
            elif ext_of(e.name) in exts:
                files.append({'name': e.name, 'path': e.path,
                              'size': e.stat().st_size})
        except OSError:
            continue
    return {'path': path, 'parent': parent, 'sep': os.sep,
            'rootLabel': 'Drives' if sys.platform == 'win32' else 'Home',
            'dirs': dirs, 'files': files}


_PICK_CODE = """
import sys
import tkinter
import tkinter.filedialog as fd

mode, initial = sys.argv[1], sys.argv[2] or None
root = tkinter.Tk()
root.withdraw()
root.attributes('-topmost', True)
if mode == 'files':
    picked = fd.askopenfilenames(initialdir=initial,
                                 title='Select e-books or comics')
    out = chr(10).join(picked or ())
else:
    out = fd.askdirectory(initialdir=initial, title='Select a folder') or ''
sys.stdout.write(out)
"""


def pick(mode='dir', initial=''):
    """Open the operating system's own file or folder dialog.

    A web page cannot ask for a path on the machine the server runs on,
    so the dialog is opened here instead. It runs in a short-lived child
    process on purpose: Tk wants the main thread, and a crashing dialog
    must not be able to take the server with it.
    """
    kw = {}
    if sys.platform == 'win32':
        kw['creationflags'] = 0x08000000       # CREATE_NO_WINDOW
    try:
        proc = subprocess.run(
            [sys.executable, '-c', _PICK_CODE, mode, initial or ''],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=600, **kw)
    except FileNotFoundError:
        raise ValueError('Could not start the dialog: Python not found.')
    except subprocess.TimeoutExpired:
        raise ValueError('The dialog was left open too long.')
    if proc.returncode != 0:
        err = (proc.stderr or b'').decode('utf-8', 'replace')
        if 'tkinter' in err.lower():
            raise ValueError(
                'No file dialog available: this Python was built without '
                'tkinter. Type the path into the field instead.')
        raise ValueError('The dialog could not be opened.')
    out = (proc.stdout or b'').decode('utf-8', 'replace').strip()
    if not out:
        return []                     # cancelled
    return [os.path.normpath(x) for x in out.splitlines() if x.strip()]


def _is_calibre_library(path):
    return os.path.isfile(os.path.join(path, 'metadata.db'))


def scan(paths, recursive):
    """Collect every processable file below the given paths.

    Calibre libraries are refused: editing their files behind calibre's
    back desynchronises metadata.db. Those books belong to the plugin
    inside calibre.
    """
    exts = known_ext(scanning=True)
    found = []
    for p in paths:
        if os.path.isfile(p):
            if ext_of(p) in exts:
                found.append((p, None))
        elif os.path.isdir(p):
            if _is_calibre_library(p):
                raise ValueError(
                    'This is a calibre library (it contains metadata.db). '
                    'Editing its files directly would desynchronise '
                    "calibre's database. Optimise these books inside "
                    'calibre with the plugin instead, or export them '
                    'first via Save to disk.')
            if recursive:
                for root, dirs, files in os.walk(p):
                    if _is_calibre_library(root):
                        dirs[:] = []
                        continue
                    dirs[:] = [d for d in dirs
                               if d.lower() not in OUTPUT_DIR_NAMES]
                    for fn in sorted(files):
                        if ext_of(fn) in exts:
                            found.append((os.path.join(root, fn), p))
            else:
                for fn in sorted(os.listdir(p)):
                    full = os.path.join(p, fn)
                    if os.path.isfile(full) and ext_of(fn) in exts:
                        found.append((full, p))
    out, seen = [], set()
    for f, root in found:
        k = os.path.normcase(os.path.abspath(f))
        if k not in seen:
            seen.add(k)
            out.append({'path': f, 'name': os.path.basename(f),
                        'size': os.path.getsize(f), 'root': root})
    return out


# ------------------------------------------------------------------- Job ---

def _worker(job_id, files, opts):
    job = _jobs[job_id]
    profile = get_profile(opts['profile'])
    target_fmt = opts.get('format') or None
    out_dir = opts.get('outDir') or ''
    png_mode = {'keep': False, 'auto': 'auto', 'jpeg': True}[
        opts.get('pngMode', 'auto')]

    for i, f in enumerate(files):
        if job['cancel']:
            job['state'] = 'cancelled'
            break
        src = f['path']
        job['current'] = os.path.basename(src)
        job['done'] = i
        ext = ext_of(src)
        fmt = target_fmt or ('cbz' if ext in COMIC_EXT else ext.lstrip('.'))
        stem = os.path.splitext(os.path.basename(src))[0]
        d = out_dir or os.path.join(os.path.dirname(src), 'optimized')
        if out_dir and f.get('root'):
            # Mirror the scanned folder's structure, or files from
            # different sub-folders would collide by name.
            rel = os.path.relpath(os.path.dirname(src), f['root'])
            if rel != '.':
                d = os.path.join(out_dir, rel)
        try:
            os.makedirs(d, exist_ok=True)
            dst = os.path.join(d, target_name(stem, fmt))
            root, extn = os.path.splitext(dst)
            tmp = root + '.ebook_opt_tmp' + extn
            res = process(
                src, tmp, profile, target_fmt=fmt,
                quality=int(opts.get('quality') or 80),
                target_error=opts.get('targetError'),
                png_mode=png_mode,
                fonts='keep' if opts.get('keepFonts') else 'strip',
                force_grayscale=False if opts.get('keepColor') else None,
                manga=bool(opts.get('manga')),
                quantize_gray=not opts.get('noQuantize'),
                progressive=not opts.get('noProgressive'),
                jobs=int(opts.get('jobs', 1)))

            detail = res.detail
            if res.converted_from:
                detail = '%s to %s, %s' % (res.converted_from,
                                           res.converted_to, detail)
            grew = res.new_size >= res.old_size and fmt == ext.lstrip('.')
            if grew:
                os.remove(tmp)
                # Keep the output tree complete: the untouched original
                # goes in when nothing could be gained.
                shutil.copyfile(src, dst)
                job['results'].append({
                    'name': f['name'], 'old': res.old_size,
                    'new': res.old_size, 'pct': 0.0, 'skipped': True,
                    'detail': 'no gain, original copied unchanged',
                    'out': dst})
            else:
                os.replace(tmp, dst)
                job['results'].append({
                    'name': f['name'], 'old': res.old_size,
                    'new': res.new_size,
                    'pct': pct_saved(res.old_size, res.new_size),
                    'skipped': False, 'detail': detail, 'out': dst})
                job['totalOld'] += res.old_size
                job['totalNew'] += res.new_size
        except conv.CalibreMissing as e:
            job['results'].append({'name': f['name'], 'error': str(e)})
        except Exception as e:
            job['results'].append({
                'name': f['name'],
                'error': str(e) or e.__class__.__name__})
            job['trace'] = traceback.format_exc()[-2000:]

    job['done'] = len(files)
    if job['state'] == 'running':
        job['state'] = 'finished'
    job['finished'] = time.time()


def start_job(files, opts):
    # Keep memory bounded: results of old runs are not needed forever.
    if len(_jobs) > 20:
        for k in sorted(_jobs, key=lambda k: _jobs[k]['started'])[:-10]:
            if _jobs[k].get('finished'):
                _jobs.pop(k, None)
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        'id': job_id, 'state': 'running', 'total': len(files), 'done': 0,
        'current': '', 'results': [], 'totalOld': 0, 'totalNew': 0,
        'cancel': False, 'started': time.time(), 'finished': None,
    }
    threading.Thread(target=_worker, args=(job_id, files, opts),
                     daemon=True).start()
    return job_id


# ---------------------------------------------------------------- Server ---

class Handler(BaseHTTPRequestHandler):
    server_version = 'EbookOptimizer'

    def log_message(self, fmt, *args):
        pass                      # no access log on the console

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode('utf-8'))

    def _static(self, path):
        name = path.lstrip('/') or 'index.html'
        full = os.path.normpath(os.path.join(STATIC, name))
        if not full.startswith(STATIC) or not os.path.isfile(full):
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(full)[0] or 'application/octet-stream'
        with open(full, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path).path
        try:
            if p == '/api/status':
                return self._json(status())
            if p.startswith('/api/job/'):
                job = _jobs.get(p.rsplit('/', 1)[-1])
                if not job:
                    return self._json({'error': 'unknown job'}, 404)
                return self._json({k: v for k, v in job.items()
                                   if k != 'cancel'})
            return self._static(p)
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            data = self._read_body()
            if p == '/api/browse':
                return self._json(list_dir(data.get('path', '')))
            if p == '/api/scan':
                files = scan(data.get('paths', []),
                             bool(data.get('recursive')))
                return self._json({
                    'files': files,
                    'totalSize': sum(f['size'] for f in files)})
            if p == '/api/run':
                files = data.get('files') or []
                if not files:
                    return self._json({'error': 'no files'}, 400)
                return self._json(
                    {'id': start_job(files, data.get('opts', {}))})
            if p == '/api/cancel':
                job = _jobs.get(data.get('id'))
                if job:
                    job['cancel'] = True
                return self._json({'ok': True})
            if p == '/api/pick':
                picked = pick(data.get('mode', 'dir'), data.get('initial'))
                return self._json({'paths': picked})
            if p == '/api/reveal':
                d = data.get('path') or ''
                if not os.path.isdir(d):
                    return self._json(
                        {'error': 'Folder no longer exists: %s' % d}, 404)
                if sys.platform == 'win32':
                    os.startfile(d)                         # noqa: S606
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', d])
                else:
                    subprocess.Popen(['xdg-open', d])
                return self._json({'ok': True})
            self.send_error(404)
        except Exception as e:
            self._json({'error': str(e)}, 500)


def serve(host='127.0.0.1', port=8756, open_browser=True):
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = 'http://%s:%d/' % (host, port)
    print('EBOOK-OPTIMIZER is running at %s' % url)
    print('Press Ctrl+C to stop.')
    if not conv.available():
        print('')
        print('  Note: Calibre was not found.')
        print('  Without it only EPUB, KEPUB and CBZ are available.')
        print('  For every other format: https://calibre-ebook.com')
        print('')
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        httpd.server_close()
