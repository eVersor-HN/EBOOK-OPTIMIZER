"""Bilder parallel optimieren - mit sauberem Rueckfall auf seriell.

Der Prozesspool ist bewusst optional: in eingebetteten Umgebungen
(Calibre bringt sein eigenes Python mit, PyInstaller-Builds, Sandboxes)
kann das Starten von Kindprozessen fehlschlagen. Dann rechnet dieselbe
Funktion einfach seriell weiter, statt den ganzen Lauf abzubrechen.
"""

import os
import sys

from .imaging import optimize_image


def pool_usable():
    """Laesst sich hier ueberhaupt ein Prozesspool starten?

    Windows startet Kindprozesse per spawn und importiert dazu das
    Hauptmodul nach. Kommt das Skript von stdin, aus der REPL oder aus
    einer eingebetteten Umgebung (Calibre), schlaegt dieser Import in
    jedem Kindprozess fehl - mit Traceback auf stderr, bevor unser
    Rueckfall ueberhaupt greift. Deshalb vorher pruefen statt hinterher
    aufraeumen.
    """
    main = sys.modules.get('__main__')
    path = getattr(main, '__file__', None)
    return bool(path) and os.path.isfile(path)


def default_jobs():
    """Sinnvolle Voreinstellung: alle Kerne, aber nicht endlos viele."""
    return max(1, min(8, os.cpu_count() or 1))


def _job(args):
    """Muss auf Modulebene liegen - Windows startet Kindprozesse per spawn."""
    name, data, profile, kw = args
    return name, optimize_image(data, profile, **kw)


def optimize_many(items, profile, jobs=1, **kw):
    """items: Liste von (name, bytes). Ergebnis: dict name -> ImageResult.

    Die Reihenfolge der Eingabe spielt keine Rolle, das Ergebnis ist ein
    Dictionary - Seitensortierung passiert beim Aufrufer.
    """
    if not items:
        return {}

    # Bei wenigen oder kleinen Bildern kostet der Pool mehr, als er bringt.
    if jobs <= 1 or len(items) < 4 or not pool_usable():
        return dict(_job((n, d, profile, kw)) for n, d in items)

    try:
        from concurrent.futures import ProcessPoolExecutor
        payload = [(n, d, profile, kw) for n, d in items]
        with ProcessPoolExecutor(max_workers=min(jobs, len(items))) as ex:
            return dict(ex.map(_job, payload, chunksize=1))
    except Exception:
        # Kein Grund zum Abbruch - seriell kommt dasselbe heraus.
        return dict(_job((n, d, profile, kw)) for n, d in items)
