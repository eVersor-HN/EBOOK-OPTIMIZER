"""Format conversion through Calibre's ebook-convert.

A deliberate division of labour: Calibre converts, we optimise. Its
converter covers around 50 input and 20 output formats and has been in
the field for years - reimplementing that would be effort without gain.

Without Calibre everything else keeps working; only conversion drops
out, with a clear message rather than a failed run.
"""

import os
import shutil
import subprocess
import sys

CONVERTER = 'ebook-convert'
DEBUGGER = 'calibre-debug'

# Filled on first use.
_cache = {}

# Fallback lists, used when Calibre cannot be queried. They match
# Calibre 9; the real lists are read at runtime.
FALLBACK_OUTPUT = ('azw3', 'docx', 'epub', 'fb2', 'htmlz', 'kepub', 'lit',
                   'lrf', 'mobi', 'oeb', 'pdb', 'pdf', 'pmlz', 'rb', 'rtf',
                   'snb', 'tcr', 'txt', 'txtz', 'zip')

FALLBACK_INPUT = ('azw', 'azw3', 'azw4', 'cb7', 'cbc', 'cbr', 'cbz', 'chm',
                  'djvu', 'docx', 'epub', 'fb2', 'htm', 'html', 'htmlz',
                  'kepub', 'lit', 'lrf', 'md', 'mobi', 'odt', 'opf', 'pdb',
                  'pdf', 'pml', 'prc', 'rar', 'rb', 'rtf', 'snb', 'tcr',
                  'txt', 'txtz', 'xhtml', 'zip')

# The format that works best on each device.
DEVICE_FORMAT = {
    'pb_verse_pro': 'epub',
    'pb_verse': 'epub',
    'kobo_clara_bw': 'kepub',
    'kobo_clara_colour': 'kepub',
    'generic_6in_300ppi': 'epub',
}

# Formats we can still work on after conversion.
OPTIMIZABLE = {'epub', 'kepub', 'cbz'}

# Comic formats take their own path, see core.cbz.
COMIC_IN = {'cbz', 'cbr', 'cbt', 'cb7'}


class CalibreMissing(RuntimeError):
    """Calibre is required here but could not be found."""


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
    """Look for a Calibre tool on PATH and in the usual locations."""
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
    """Is Calibre usable?"""
    return converter_path() is not None


def version():
    """Calibre version as text, or None."""
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
        # No console window flashing up when called from a GUI.
        kw['creationflags'] = 0x08000000       # CREATE_NO_WINDOW
    proc = subprocess.run(args, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout, **kw)
    out = (proc.stdout or b'').decode('utf-8', 'replace')
    if proc.returncode != 0:
        raise RuntimeError('ebook-convert failed with code %d:\n%s'
                           % (proc.returncode, out[-1500:]))
    return out


def _query_formats():
    """Ask Calibre for its actual format lists."""
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
    """(input formats, output formats) - queried live, else the fallback."""
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
    """Convert a file with Calibre.

    profile: DeviceProfile - sets the output profile so Calibre does not
             rescale on its own guesswork.
    """
    exe = converter_path()
    if not exe:
        raise CalibreMissing(
            'Format conversion needs Calibre, which was not found. Install '
            'it from https://calibre-ebook.com and try again. Optimising '
            'EPUB, KEPUB and CBZ works without it.')

    args = [exe, src, dst]
    if profile is not None:
        # Calibre should not touch the images as well - that is our job.
        args += ['--output-profile', _calibre_profile(profile)]
    if extra_args:
        args += list(extra_args)
    _run(args, timeout=timeout)
    return dst


def _calibre_profile(profile):
    """Translate our device profile into Calibre's output profile."""
    key = getattr(profile, 'key', '')
    if key.startswith('kobo'):
        return 'kobo'
    if key.startswith('pb'):
        return 'generic_eink_hd'
    return 'generic_eink_hd'


def needs_conversion(src_ext, target_fmt):
    """Is a conversion needed at all?"""
    src = src_ext.lstrip('.').lower()
    tgt = target_fmt.lstrip('.').lower()
    if src == tgt:
        return False
    # Comic to comic goes through our own path.
    if src in COMIC_IN and tgt == 'cbz':
        return False
    return True
