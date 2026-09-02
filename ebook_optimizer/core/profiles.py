"""Device profiles and compression presets.

Plain data only - no dependency on Calibre, Qt or Pillow, so this module
stays importable everywhere.

Resolutions are the panel's native portrait pixel dimensions. Colour
devices (Kaleido, Gallery) keep their colour; everything else is
converted to greyscale, because the panel cannot show anything else.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceProfile:
    key: str
    name: str
    brand: str
    width: int              # panel width in pixels (portrait)
    height: int             # panel height in pixels (portrait)
    grayscale: bool         # True for monochrome e-ink
    gray_levels: int        # 16 on E Ink Carta, 0 = no quantisation

    @property
    def box(self):
        """Maximum image size (width, height) in portrait orientation."""
        return (self.width, self.height)

    @property
    def long_edge(self):
        return max(self.width, self.height)

    @property
    def label(self):
        return '%s %s' % (self.brand, self.name) if self.brand else self.name


def _mono(key, brand, name, w, h):
    return DeviceProfile(key=key, name=name, brand=brand, width=w, height=h,
                         grayscale=True, gray_levels=16)


def _colour(key, brand, name, w, h):
    return DeviceProfile(key=key, name=name, brand=brand, width=w, height=h,
                         grayscale=False, gray_levels=0)


_ALL = [
    # -- Amazon Kindle ----------------------------------------------------
    _mono('kindle_11', 'Kindle', '(11th gen)', 1072, 1448),
    _mono('kindle_pw_10', 'Kindle', 'Paperwhite (10th gen)', 1072, 1448),
    _mono('kindle_pw_11', 'Kindle', 'Paperwhite (11th gen)', 1236, 1648),
    _mono('kindle_pw_12', 'Kindle', 'Paperwhite (12th gen)', 1264, 1680),
    _mono('kindle_oasis_3', 'Kindle', 'Oasis (3rd gen)', 1264, 1680),
    _colour('kindle_colorsoft', 'Kindle', 'Colorsoft', 1264, 1680),
    _mono('kindle_scribe', 'Kindle', 'Scribe', 1860, 2480),

    # -- Rakuten Kobo -----------------------------------------------------
    _mono('kobo_nia', 'Kobo', 'Nia', 758, 1024),
    _mono('kobo_clara_hd', 'Kobo', 'Clara HD / Clara 2E', 1072, 1448),
    _mono('kobo_clara_bw', 'Kobo', 'Clara BW', 1072, 1448),
    _colour('kobo_clara_colour', 'Kobo', 'Clara Colour', 1072, 1448),
    _mono('kobo_libra_2', 'Kobo', 'Libra 2 / Libra H2O', 1264, 1680),
    _colour('kobo_libra_colour', 'Kobo', 'Libra Colour', 1264, 1680),
    _mono('kobo_sage', 'Kobo', 'Sage', 1440, 1920),
    _mono('kobo_elipsa_2e', 'Kobo', 'Elipsa 2E', 1404, 1872),

    # -- PocketBook -------------------------------------------------------
    _mono('pb_verse', 'PocketBook', 'Verse', 758, 1024),
    _mono('pb_verse_pro', 'PocketBook', 'Verse Pro', 1072, 1448),
    _mono('pb_touch_hd_3', 'PocketBook', 'Touch HD 3', 1072, 1448),
    _mono('pb_era', 'PocketBook', 'Era', 1264, 1680),
    _mono('pb_inkpad_4', 'PocketBook', 'InkPad 4', 1404, 1872),
    _colour('pb_inkpad_color_3', 'PocketBook', 'InkPad Color 3', 1404, 1872),

    # -- Onyx Boox --------------------------------------------------------
    _mono('boox_palma', 'Boox', 'Palma', 824, 1648),
    _mono('boox_page', 'Boox', 'Page', 1264, 1680),
    _mono('boox_note_air', 'Boox', 'Note Air series', 1404, 1872),
    _mono('boox_tab_ultra', 'Boox', 'Tab Ultra series', 1404, 1872),

    # -- Tolino -----------------------------------------------------------
    _mono('tolino_page_2', 'Tolino', 'Page 2', 758, 1024),
    _mono('tolino_shine_5', 'Tolino', 'Shine 5', 1072, 1448),
    _mono('tolino_vision_6', 'Tolino', 'Vision 6', 1264, 1680),

    # -- Barnes & Noble Nook ----------------------------------------------
    _mono('nook_glowlight_4', 'Nook', 'GlowLight 4', 1072, 1448),
    _mono('nook_glowlight_4e', 'Nook', 'GlowLight 4e', 758, 1024),

    # -- reMarkable -------------------------------------------------------
    _mono('remarkable_2', 'reMarkable', '2', 1404, 1872),
    _colour('remarkable_paper_pro', 'reMarkable', 'Paper Pro', 1620, 2160),

    # -- Generic fallbacks, when a device is not listed --------------------
    _mono('generic_6in_300ppi', 'Generic', '6" · 300 ppi', 1072, 1448),
    _mono('generic_7in_300ppi', 'Generic', '7" · 300 ppi', 1264, 1680),
    _mono('generic_8in_300ppi', 'Generic', '8" · 300 ppi', 1440, 1920),
    _mono('generic_10in_227ppi', 'Generic', '10.3" · 227 ppi', 1404, 1872),
]

PROFILES = {p.key: p for p in _ALL}

DEFAULT_PROFILE = 'pb_verse_pro'

# Order used by the interfaces, so the dropdown is grouped by brand.
BRAND_ORDER = ['Kindle', 'Kobo', 'PocketBook', 'Boox', 'Tolino', 'Nook',
               'reMarkable', 'Generic']


def profiles_by_brand():
    """[(brand, [profile, ...]), ...] in the order above."""
    out = []
    for brand in BRAND_ORDER:
        group = [p for p in _ALL if p.brand == brand]
        if group:
            out.append((brand, group))
    return out


def get_profile(key):
    try:
        return PROFILES[key]
    except KeyError:
        raise ValueError(
            'Unknown device profile %r. Available: %s'
            % (key, ', '.join(sorted(PROFILES))))


# --------------------------------------------------------------- Presets ---

@dataclass(frozen=True)
class Preset:
    key: str
    name: str
    quality: int
    quantize: bool
    summary: str            # what it does, in one line
    measured: str           # what the measurements actually showed


# The numbers below were measured on five representative images - a colour
# comic page, a greyscale manga page, a webtoon strip, a watercolour plate
# and an 1897 halftone scan - each scaled to a 1072x1448 panel.
#
# "Visibly wrong pixels" counts pixels that land two or more grey levels
# away from the reference once both are reduced to the 16 levels an e-ink
# panel can display. A single level of difference is the smallest possible
# step and is not counted, because it cannot be seen.
PRESETS = {
    'maximum': Preset(
        key='maximum', name='Maximum quality', quality=90, quantize=False,
        summary='Largest files. Use when the source is precious.',
        measured='25-60 % larger than balanced, with no measurable '
                 'difference on the panel.'),
    'balanced': Preset(
        key='balanced', name='Balanced', quality=80, quantize=True,
        summary='The default. Big savings, nothing visible on an e-ink panel.',
        measured='At most 0.09 % of pixels differ visibly; on most pages '
                 'far less.'),
    'small': Preset(
        key='small', name='Small', quality=70, quantize=True,
        summary='Noticeably smaller files, still hard to tell apart.',
        measured='19-36 % smaller than balanced. Up to 0.41 % of pixels '
                 'differ visibly, worst on fine halftone artwork.'),
    'smallest': Preset(
        key='smallest', name='Smallest', quality=60, quantize=True,
        summary='For fitting a large library on a small device.',
        measured='32-42 % smaller than balanced. Up to 0.82 % of pixels '
                 'differ visibly - noticeable on detailed artwork, fine '
                 'for text-heavy scans.'),
}

PRESET_ORDER = ['maximum', 'balanced', 'small', 'smallest']
DEFAULT_PRESET = 'balanced'


def get_preset(key):
    try:
        return PRESETS[key]
    except KeyError:
        raise ValueError(
            'Unknown preset %r. Available: %s'
            % (key, ', '.join(PRESET_ORDER)))
