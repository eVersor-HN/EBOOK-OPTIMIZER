"""Kleine Hilfsfunktionen ohne externe Abhaengigkeiten."""

import posixpath
import re

_NUM_RE = re.compile(r'(\d+)')

JUNK_PREFIXES = ('__MACOSX/', '.git/')
JUNK_NAMES = {'.ds_store', 'thumbs.db', 'desktop.ini'}


def natural_key(name):
    """Sortierschluessel: 'p2.jpg' vor 'p10.jpg'."""
    parts = _NUM_RE.split(name.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def is_junk(name):
    low = name.lower()
    if any(low.startswith(p.lower()) for p in JUNK_PREFIXES):
        return True
    return posixpath.basename(low) in JUNK_NAMES


def human_size(n):
    n = float(n)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if abs(n) < 1024.0 or unit == 'GB':
            return '%.1f %s' % (n, unit) if unit != 'B' else '%d B' % n
        n /= 1024.0


def pct_saved(old, new):
    if not old:
        return 0.0
    return (old - new) / float(old) * 100.0


def ext_of(name):
    return posixpath.splitext(name)[1].lower()
