"""Formatkonvertierung ueber Calibres ebook-convert.

Bewusste Arbeitsteilung: Calibre konvertiert, wir optimieren. Calibres
Konverter deckt rund 50 Eingabe- und 20 Ausgabeformate ab und ist seit
Jahren im Feld erprobt - das nachzubauen waere Aufwand ohne Gewinn.

Ohne Calibre laeuft alles Uebrige weiter; nur die Konvertierung faellt
dann mit einer klaren Meldung aus, statt den Lauf abzubrechen.
"""

import os
import shutil
import subprocess
import sys

CONVERTER = 'ebook-convert'
DEBUGGER = 'calibre-debug'

# Wird beim ersten Aufruf gefuellt.
_cache = {}

# Rueckfalliste, falls Calibre sich nicht befragen laesst. Entspricht dem
# Stand von Calibre 9; die echte Liste wird zur Laufzeit abgefragt.
FALLBACK_OUTPUT = ('azw3', 'docx', 'epub', 'fb2', 'htmlz', 'kepub', 'lit',
                   'lrf', 'mobi', 'oeb', 'pdb', 'pdf', 'pmlz', 'rb', 'rtf',
                   'snb', 'tcr', 'txt', 'txtz', 'zip')

FALLBACK_INPUT = ('azw', 'azw3', 'azw4', 'cb7', 'cbc', 'cbr', 'cbz', 'chm',
                  'djvu', 'docx', 'epub', 'fb2', 'htm', 'html', 'htmlz',
                  'kepub', 'lit', 'lrf', 'md', 'mobi', 'odt', 'opf', 'pdb',
                  'pdf', 'pml', 'prc', 'rar', 'rb', 'rtf', 'snb', 'tcr',
                  'txt', 'txtz', 'xhtml', 'zip')

# Was auf dem jeweiligen Geraet am besten laeuft.
DEVICE_FORMAT = {
    'pb_verse_pro': 'epub',
    'pb_verse': 'epub',
    'kobo_clara_bw': 'kepub',
    'kobo_clara_colour': 'kepub',
    'generic_6in_300ppi': 'epub',
}

# Diese Formate koennen wir nach der Konvertierung noch selbst anfassen.
OPTIMIZABLE = {'epub', 'kepub', 'cbz'}

# Comicformate gehen einen eigenen Weg (siehe core.cbz).
COMIC_IN = {'cbz', 'cbr', 'cbt', 'cb7'}


class CalibreMissing(RuntimeError):
    """Calibre wird gebraucht, ist aber nicht auffindbar."""


def _candidate_dirs():
    if sys.platform == 'win32':
        pf = os.environ.get('ProgramFiles', r'C:\Program Files')
        pf86 = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
        return [os.path.join(pf, 'Calibre2'), os.path.join(pf86, 'Calibre2'),
                os.path.join(pf, 'Calibre'), os.path.join(pf86, 'Calibre')]
    if sys.platform == 'darwin':
        return ['/Applications/calibre.app/Contents/MacOS',
                os.path.expanduser('~/Applications/calibre.app/Contents/MacOS')]
    return ['/usr/bin', '/usr/local/bin', '/opt/calibre',
            os.path.expanduser('~/calibre-bin/calibre')]


def _find(tool):
    """Sucht ein Calibre-Werkzeug im PATH und an den ueblichen Orten."""
    found = shutil.which(tool)
    if found:
        return found
    exe = tool + ('.exe' if sys.platform == 'win32' else '')
    for d in _candidate_dirs():
        p = os.path.join(d, exe)
        if os.path.isfile(p):
            return p
    return None


def converter_path():
    if 'converter' not in _cache:
        _cache['converter'] = _find(CONVERTER)
    return _cache['converter']


def available():
    """Ist Calibre benutzbar?"""
    return converter_path() is not None


def version():
    """Calibre-Version als Text, oder None."""
    exe = converter_path()
    if not exe:
        return None
    if 'version' not in _cache:
        try:
            out = _run([exe, '--version'], timeout=60)
            _cache['version'] = out.strip().splitlines()[0]
        except Exception:
            _cache['version'] = None
    return _cache['version']


def _run(args, timeout=1800):
    kw = {}
    if sys.platform == 'win32':
        # Kein aufblitzendes Konsolenfenster, wenn wir aus einer GUI kommen.
        kw['creationflags'] = 0x08000000       # CREATE_NO_WINDOW
    proc = subprocess.run(args, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout, **kw)
    out = (proc.stdout or b'').decode('utf-8', 'replace')
    if proc.returncode != 0:
        raise RuntimeError('ebook-convert scheiterte (Code %d):\n%s'
                           % (proc.returncode, out[-1500:]))
    return out


def _query_formats():
    """Fragt die echten Formatlisten bei Calibre ab."""
    dbg = _find(DEBUGGER)
    if not dbg:
        return None
    code = ('from calibre.customize.ui import available_input_formats, '
            'available_output_formats\n'
            "print('IN:' + ','.join(sorted(available_input_formats())))\n"
            "print('OUT:' + ','.join(sorted(available_output_formats())))")
    try:
        out = _run([dbg, '-c', code], timeout=120)
    except Exception:
        return None
    got = {}
    for line in out.splitlines():
        if line.startswith('IN:'):
            got['input'] = tuple(sorted(x for x in line[3:].split(',') if x))
        elif line.startswith('OUT:'):
            got['output'] = tuple(sorted(x for x in line[4:].split(',') if x))
    return got if 'output' in got else None


def formats():
    """(Eingabeformate, Ausgabeformate) - live abgefragt, sonst Rueckfall."""
    if 'formats' not in _cache:
        got = _query_formats() if available() else None
        if got:
            _cache['formats'] = (got.get('input', FALLBACK_INPUT),
                                 got['output'])
        else:
            _cache['formats'] = (FALLBACK_INPUT, FALLBACK_OUTPUT)
    return _cache['formats']


def output_formats():
    return formats()[1]


def input_formats():
    return formats()[0]


def convert(src, dst, profile=None, extra_args=None, timeout=1800):
    """Konvertiert eine Datei mit Calibre.

    profile: DeviceProfile - setzt Bildschirmgroesse und Ausgabeprofil,
             damit Calibre nicht auf Verdacht skaliert.
    """
    exe = converter_path()
    if not exe:
        raise CalibreMissing(
            'Fuer die Formatkonvertierung wird Calibre benoetigt, es wurde '
            'aber nicht gefunden. Installiere Calibre von '
            'https://calibre-ebook.com und starte den Vorgang erneut. '
            'Das Verkleinern von EPUB und Comics funktioniert auch ohne.')

    args = [exe, src, dst]
    if profile is not None:
        # Calibre soll Bilder nicht zusaetzlich anfassen - das machen wir.
        args += ['--output-profile', _calibre_profile(profile)]
    if extra_args:
        args += list(extra_args)
    _run(args, timeout=timeout)
    return dst


def _calibre_profile(profile):
    """Uebersetzt unser Geraeteprofil in Calibres Ausgabeprofil."""
    key = getattr(profile, 'key', '')
    if key.startswith('kobo'):
        return 'kobo'
    if key.startswith('pb'):
        return 'generic_eink_hd'
    return 'generic_eink_hd'


def needs_conversion(src_ext, target_fmt):
    """Muss ueberhaupt konvertiert werden?"""
    src = src_ext.lstrip('.').lower()
    tgt = target_fmt.lstrip('.').lower()
    if src == tgt:
        return False
    # Comic zu Comic laeuft ueber unseren eigenen Weg.
    if src in COMIC_IN and tgt == 'cbz':
        return False
    return True
