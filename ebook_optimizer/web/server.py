"""Lokale Weboberflaeche fuer den Ebook Optimizer.

Laeuft ausschliesslich auf der eigenen Maschine (127.0.0.1) und braucht
nichts ausser der Standardbibliothek. Der Browser dient nur als Anzeige;
gerechnet wird im Python-Prozess.

Start:  python -m ebook_optimizer.web
"""

import json
import mimetypes
import os
import string
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
from ..core.profiles import DEFAULT_PROFILE, PROFILES, get_profile
from ..core.util import ext_of, human_size, pct_saved

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
NATIVE_EXT = {'.epub', '.kepub'} | COMIC_EXT

# Laufende und abgeschlossene Auftraege.
_jobs = {}
_lock = threading.Lock()


# ----------------------------------------------------------------- Daten ---

# Siehe cli.SCAN_SKIP_EXT: beim Durchsuchen keine Allerweltsdateien.
SCAN_SKIP_EXT = {'.txt', '.text', '.htm', '.html', '.xhtm', '.xhtml',
                 '.md', '.markdown', '.textile', '.opf', '.recipe',
                 '.zip', '.rar', '.shtm', '.shtml'}


def known_ext(scanning=False):
    ext = set(NATIVE_EXT)
    if conv.available():
        ext |= {'.' + f for f in conv.input_formats()}
    if scanning:
        ext -= SCAN_SKIP_EXT
    return ext


def status():
    return {
        'calibre': bool(conv.available()),
        'calibreVersion': conv.version(),
        'backend': backend_name(),
        'cpus': default_jobs(),
        'profiles': [{'key': k, 'name': p.name,
                      'size': '%dx%d' % (p.width, p.height),
                      'gray': p.grayscale}
                     for k, p in sorted(PROFILES.items(),
                                        key=lambda kv: kv[1].name)],
        'defaultProfile': DEFAULT_PROFILE,
        'formats': sorted(set(conv.output_formats()) | {'cbz'})
                   if conv.available() else ['epub', 'kepub', 'cbz'],
        'nativeFormats': ['epub', 'kepub', 'cbz'],
    }


def list_dir(path):
    """Verzeichnisinhalt fuer die Ordnerauswahl im Browser."""
    if not path:
        # Wurzelebene: unter Windows die Laufwerke, sonst das Heimatverzeichnis
        if sys.platform == 'win32':
            drives = ['%s:\\' % d for d in string.ascii_uppercase
                      if os.path.exists('%s:\\' % d)]
            return {'path': '', 'parent': None,
                    'dirs': [{'name': d, 'path': d} for d in drives],
                    'files': []}
        path = os.path.expanduser('~')

    path = os.path.abspath(path)
    if not os.path.isdir(path):
        raise ValueError('Kein Ordner: %s' % path)

    parent = os.path.dirname(path.rstrip(os.sep))
    if parent == path or (sys.platform == 'win32'
                          and len(path.rstrip(os.sep)) <= 2):
        parent = ''

    dirs, files = [], []
    exts = known_ext(scanning=True)
    try:
        entries = sorted(os.scandir(path), key=lambda e: e.name.lower())
    except PermissionError:
        raise ValueError('Kein Zugriff auf %s' % path)
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
    return {'path': path, 'parent': parent, 'dirs': dirs, 'files': files}


def scan(paths, recursive):
    """Sammelt alle verarbeitbaren Dateien unter den angegebenen Pfaden."""
    exts = known_ext(scanning=True)
    found = []
    for p in paths:
        if os.path.isfile(p):
            if ext_of(p) in exts:
                found.append(p)
        elif os.path.isdir(p):
            if recursive:
                for root, _d, files in os.walk(p):
                    for fn in sorted(files):
                        if ext_of(fn) in exts:
                            found.append(os.path.join(root, fn))
            else:
                for fn in sorted(os.listdir(p)):
                    full = os.path.join(p, fn)
                    if os.path.isfile(full) and ext_of(fn) in exts:
                        found.append(full)
    out, seen = [], set()
    for f in found:
        k = os.path.normcase(os.path.abspath(f))
        if k not in seen:
            seen.add(k)
            out.append({'path': f, 'name': os.path.basename(f),
                        'size': os.path.getsize(f)})
    return out


# ---------------------------------------------------------------- Auftrag ---

def _worker(job_id, files, opts):
    job = _jobs[job_id]
    profile = get_profile(opts['profile'])
    target_fmt = opts.get('format') or None
    out_dir = opts.get('outDir') or ''
    png_mode = {'keep': False, 'auto': 'auto', 'jpeg': True}[
        opts.get('pngMode', 'auto')]

    for i, f in enumerate(files):
        if job['cancel']:
            job['state'] = 'abgebrochen'
            break
        src = f['path']
        job['current'] = os.path.basename(src)
        job['done'] = i
        ext = ext_of(src)
        fmt = target_fmt or ('cbz' if ext in COMIC_EXT else ext.lstrip('.'))
        stem = os.path.splitext(os.path.basename(src))[0]
        d = out_dir or os.path.join(os.path.dirname(src), 'optimiert')
        try:
            os.makedirs(d, exist_ok=True)
            dst = os.path.join(d, target_name(stem, fmt))
            root, extn = os.path.splitext(dst)
            tmp = root + '.ebook_opt_tmp' + extn
            res = process(
                src, tmp, profile, target_fmt=fmt,
                quality=int(opts.get('quality', 80)),
                png_mode=png_mode,
                fonts='keep' if opts.get('keepFonts') else 'strip',
                force_grayscale=False if opts.get('keepColor') else None,
                manga=bool(opts.get('manga')),
                quantize_gray=not opts.get('noQuantize'),
                progressive=not opts.get('noProgressive'),
                jobs=int(opts.get('jobs', 1)))

            detail = res.detail
            if res.converted_from:
                detail = '%s->%s, %s' % (res.converted_from, res.converted_to,
                                         detail)
            grew = res.new_size >= res.old_size and fmt == ext.lstrip('.')
            if grew:
                os.remove(tmp)
                job['results'].append({
                    'name': f['name'], 'old': res.old_size,
                    'new': res.old_size, 'pct': 0.0, 'skipped': True,
                    'detail': 'kein Gewinn, Original bleibt'})
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
    if job['state'] == 'laeuft':
        job['state'] = 'fertig'
    job['finished'] = time.time()


def start_job(files, opts):
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        'id': job_id, 'state': 'laeuft', 'total': len(files), 'done': 0,
        'current': '', 'results': [], 'totalOld': 0, 'totalNew': 0,
        'cancel': False, 'started': time.time(), 'finished': None,
    }
    t = threading.Thread(target=_worker, args=(job_id, files, opts),
                         daemon=True)
    t.start()
    return job_id


# ----------------------------------------------------------------- Server ---

class Handler(BaseHTTPRequestHandler):
    server_version = 'EbookOptimizer'

    def log_message(self, fmt, *args):
        pass                      # keine Zugriffslogs auf der Konsole

    # -- Hilfen ---------------------------------------------------------
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
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

    # -- Routen ---------------------------------------------------------
    def do_GET(self):
        p = urlparse(self.path).path
        try:
            if p == '/api/status':
                return self._json(status())
            if p.startswith('/api/job/'):
                job = _jobs.get(p.rsplit('/', 1)[-1])
                if not job:
                    return self._json({'error': 'unbekannt'}, 404)
                out = {k: v for k, v in job.items() if k != 'cancel'}
                return self._json(out)
            return self._static(p)
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            data = self._body()
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
                    return self._json({'error': 'Keine Dateien'}, 400)
                return self._json({'id': start_job(files,
                                                   data.get('opts', {}))})
            if p == '/api/cancel':
                job = _jobs.get(data.get('id'))
                if job:
                    job['cancel'] = True
                return self._json({'ok': True})
            if p == '/api/reveal':
                # Zielordner im Explorer oeffnen
                d = data.get('path') or ''
                if os.path.isdir(d):
                    if sys.platform == 'win32':
                        os.startfile(d)             # noqa: S606
                    elif sys.platform == 'darwin':
                        os.system('open %s' % json.dumps(d))
                    else:
                        os.system('xdg-open %s' % json.dumps(d))
                return self._json({'ok': True})
            self.send_error(404)
        except Exception as e:
            self._json({'error': str(e)}, 500)


def serve(host='127.0.0.1', port=8756, open_browser=True):
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = 'http://%s:%d/' % (host, port)
    print('Ebook Optimizer laeuft auf %s' % url)
    print('Zum Beenden: Strg+C')
    if not conv.available():
        print('')
        print('  Hinweis: Calibre wurde nicht gefunden.')
        print('  Ohne Calibre sind nur EPUB, KEPUB und CBZ moeglich.')
        print('  Fuer alle weiteren Formate: https://calibre-ebook.com')
        print('')
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nBeendet.')
    finally:
        httpd.server_close()
