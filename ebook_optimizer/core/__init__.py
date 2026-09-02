"""Core optimisation logic - independent of Calibre."""

from .profiles import PROFILES, DEFAULT_PROFILE, get_profile  # noqa: F401
from .epub import optimize_epub  # noqa: F401
from .cbz import optimize_comic  # noqa: F401
from .imaging import backend_name  # noqa: F401

__all__ = ['PROFILES', 'DEFAULT_PROFILE', 'get_profile',
           'optimize_epub', 'optimize_comic', 'backend_name']
