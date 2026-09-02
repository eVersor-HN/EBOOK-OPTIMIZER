"""Optimise images in parallel, with a clean fall back to serial.

The process pool is deliberately optional: in embedded environments -
Calibre ships its own Python, PyInstaller builds, sandboxes - starting
child processes can fail. The same function then simply carries on
serially instead of aborting the whole run.
"""

import os
import sys

from .imaging import optimize_image


def pool_usable():
    """Can a process pool even start here?

    Windows spawns child processes and re-imports the main module to do
    so. When the script came from stdin, a REPL or an embedded
    environment such as Calibre, that import fails in every child - with
    a traceback on stderr, before our fallback can even take over. So
    check up front rather than clean up afterwards.
    """
    main = sys.modules.get('__main__')
    path = getattr(main, '__file__', None)
    return bool(path) and os.path.isfile(path)


def default_jobs():
    """A sensible default: every core, but not an unbounded number."""
    return max(1, min(8, os.cpu_count() or 1))


def _job(args):
    """Must live at module level - Windows spawns its child processes."""
    name, data, profile, kw = args
    return name, optimize_image(data, profile, **kw)


def optimize_many(items, profile, jobs=1, **kw):
    """items: list of (name, bytes). Returns dict name -> ImageResult.

    Input order does not matter; the result is a dictionary and page
    ordering happens in the caller.
    """
    if not items:
        return {}

    # For a handful of small images the pool costs more than it saves.
    if jobs <= 1 or len(items) < 4 or not pool_usable():
        return dict(_job((n, d, profile, kw)) for n, d in items)

    try:
        from concurrent.futures import ProcessPoolExecutor
        payload = [(n, d, profile, kw) for n, d in items]
        with ProcessPoolExecutor(max_workers=min(jobs, len(items))) as ex:
            return dict(ex.map(_job, payload, chunksize=1))
    except Exception:
        # No reason to abort - serial produces the same result.
        return dict(_job((n, d, profile, kw)) for n, d in items)
