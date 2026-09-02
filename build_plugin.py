"""Build the installable Calibre plugin ZIP.

Important: Calibre expects __init__.py at the ROOT of the ZIP, not in a
sub-folder. So the contents of ebook_optimizer/ are zipped, not the
folder itself.
"""

import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'ebook_optimizer')
OUT = os.path.join(HERE, 'dist', 'EBOOK-OPTIMIZER-calibre-plugin.zip')

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
    print('%s  (%d files, %.1f KB)'
          % (path, n, os.path.getsize(path) / 1024))
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    assert '__init__.py' in names, '__init__.py missing at the ZIP root'
    assert 'images/icon.png' in names, 'toolbar icon missing'
    assert 'plugin-import-name-ebook_optimizer.txt' in names, \
        'marker file missing'
    print('Structure ok:', ', '.join(sorted(names)))
