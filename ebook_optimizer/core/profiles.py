"""Geraeteprofile fuer die Bildoptimierung.

Reine Datenklassen, keine Abhaengigkeit zu Calibre oder Pillow.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceProfile:
    key: str
    name: str
    width: int              # Panel-Breite in Pixeln (Hochformat)
    height: int             # Panel-Hoehe in Pixeln (Hochformat)
    grayscale: bool         # True bei monochromem E-Ink
    gray_levels: int        # 16 bei E Ink Carta, 0 = keine Quantisierung

    @property
    def box(self):
        """Maximale Bildabmessung (Breite, Hoehe) im Hochformat."""
        return (self.width, self.height)

    @property
    def long_edge(self):
        return max(self.width, self.height)


PROFILES = {
    'pb_verse_pro': DeviceProfile(
        key='pb_verse_pro', name='PocketBook Verse Pro',
        width=1072, height=1448, grayscale=True, gray_levels=16),
    'pb_verse': DeviceProfile(
        key='pb_verse', name='PocketBook Verse',
        width=758, height=1024, grayscale=True, gray_levels=16),
    'kobo_clara_bw': DeviceProfile(
        key='kobo_clara_bw', name='Kobo Clara BW',
        width=1072, height=1448, grayscale=True, gray_levels=16),
    'kobo_clara_colour': DeviceProfile(
        key='kobo_clara_colour', name='Kobo Clara Colour',
        width=1072, height=1448, grayscale=False, gray_levels=0),
    'generic_6in_300ppi': DeviceProfile(
        key='generic_6in_300ppi', name='Generisch 6" / 300 ppi',
        width=1072, height=1448, grayscale=True, gray_levels=16),
}

DEFAULT_PROFILE = 'pb_verse_pro'


def get_profile(key):
    try:
        return PROFILES[key]
    except KeyError:
        raise ValueError(
            'Unbekanntes Profil %r. Verfuegbar: %s'
            % (key, ', '.join(sorted(PROFILES))))
