"""Baut das installierbare Calibre-Plugin-ZIP.

Wichtig: Calibre erwartet __init__.py im WURZELVERZEICHNIS des ZIP,
nicht in einem Unterordner. Deshalb wird der Inhalt von ebook_optimizer/ gezippt,
nicht der Ordner selbst.
"""

import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'ebook_optimizer')
OUT = os.path.join(HERE, 'dist', 'ebook-optimizer-calibre-plugin.zip')

SKIP_DIRS = {'__pycache__', '.git'}
SKIP_EXT = {'.pyc', '.pyo'}


def build():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    n = 0
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(SRC):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in sorted(files):
                if os.path.splitext(fn)[1] in SKIP_EXT:
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, SRC).replace(os.sep, '/')
                z.write(full, rel)
                n += 1
    return OUT, n


if __name__ == '__main__':
    path, n = build()
    print('%s  (%d Dateien, %.1f KB)'
          % (path, n, os.path.getsize(path) / 1024))
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    assert '__init__.py' in names, '__init__.py fehlt im ZIP-Wurzelverzeichnis'
    assert 'plugin-import-name-ebook_optimizer.txt' in names, 'Marker-Datei fehlt'
    print('Struktur ok:', ', '.join(sorted(names)))
