"""Settings dialog for the Calibre plugin (only usable inside Calibre)."""

from calibre.utils.config import JSONConfig
from qt.core import (QCheckBox, QComboBox, QFormLayout, QLabel, QSpinBox,
                     QVBoxLayout, QWidget)

from calibre_plugins.ebook_optimizer.core.profiles import (
    DEFAULT_PRESET, DEFAULT_PROFILE, PRESET_ORDER, PRESETS, profiles_by_brand)

prefs = JSONConfig('plugins/ebook_optimizer')
prefs.defaults['profile'] = DEFAULT_PROFILE
prefs.defaults['preset'] = DEFAULT_PRESET
prefs.defaults['quality'] = 0            # 0 = follow the preset
prefs.defaults['fonts'] = 'strip'
prefs.defaults['png_mode'] = 'auto'      # same values as the command line
prefs.defaults['png_to_jpeg'] = False    # legacy key, kept for migration
prefs.defaults['keep_color'] = False
prefs.defaults['quantize'] = True
prefs.defaults['progressive'] = True
prefs.defaults['manga'] = False
prefs.defaults['add_as_format'] = True   # attach the result as a new format
prefs.defaults['replace_original'] = False

PNG_MODES = (('Automatic - smaller result wins', 'auto'),
             ('Keep the original format', 'keep'),
             ('Always JPEG', 'jpeg'))

# Translation into the argument core.imaging expects.
PNG_MODE_ARG = {'keep': False, 'auto': 'auto', 'jpeg': True}


def current_png_mode():
    """Current image-format mode, migrating the old boolean setting."""
    if 'png_mode' not in prefs and prefs.get('png_to_jpeg'):
        return 'jpeg'
    mode = prefs['png_mode']
    return mode if mode in PNG_MODE_ARG else 'auto'


def current_preset():
    p = prefs['preset']
    return p if p in PRESETS else DEFAULT_PRESET


def effective_quality():
    """Quality actually used: the manual override, else the preset."""
    manual = int(prefs['quality'] or 0)
    return manual if manual else PRESETS[current_preset()].quality


def effective_quantize():
    return bool(prefs['quantize']) and PRESETS[current_preset()].quantize


class ConfigWidget(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.profile = QComboBox(self)
        self._profile_keys = []
        for brand, group in profiles_by_brand():
            for p in group:
                self.profile.addItem('%s %s  (%dx%d)%s'
                                     % (brand, p.name, p.width, p.height,
                                        '' if p.grayscale else '  colour'),
                                     p.key)
                self._profile_keys.append(p.key)
        cur = prefs['profile']
        if cur in self._profile_keys:
            self.profile.setCurrentIndex(self._profile_keys.index(cur))
        form.addRow('Device:', self.profile)

        self.preset = QComboBox(self)
        for key in PRESET_ORDER:
            p = PRESETS[key]
            self.preset.addItem('%s  (quality %d)' % (p.name, p.quality), key)
        self.preset.setCurrentIndex(PRESET_ORDER.index(current_preset()))
        form.addRow('Compression:', self.preset)

        self.quality = QSpinBox(self)
        self.quality.setRange(0, 100)
        self.quality.setValue(int(prefs['quality'] or 0))
        self.quality.setSpecialValueText('follow the preset')
        form.addRow('JPEG quality:', self.quality)

        self.fonts = QComboBox(self)
        self.fonts.addItem('Remove', 'strip')
        self.fonts.addItem('Keep', 'keep')
        self.fonts.setCurrentIndex(0 if prefs['fonts'] == 'strip' else 1)
        form.addRow('Embedded fonts:', self.fonts)

        self.png_mode = QComboBox(self)
        for label, key in PNG_MODES:
            self.png_mode.addItem(label, key)
        self.png_mode.setCurrentIndex(
            [k for _l, k in PNG_MODES].index(current_png_mode()))
        form.addRow('Image format:', self.png_mode)

        self.keep_color = QCheckBox('Keep colour (e-ink shows greyscale '
                                    'anyway)', self)
        self.keep_color.setChecked(bool(prefs['keep_color']))
        root.addWidget(self.keep_color)

        self.quantize = QCheckBox('Reduce PNGs to 16 grey levels', self)
        self.quantize.setChecked(bool(prefs['quantize']))
        root.addWidget(self.quantize)

        self.progressive = QCheckBox(
            'Progressive JPEG (about 6 % smaller; very old devices can '
            'struggle with it)', self)
        self.progressive.setChecked(bool(prefs['progressive']))
        root.addWidget(self.progressive)

        self.manga = QCheckBox('Comics: right-to-left reading direction',
                               self)
        self.manga.setChecked(bool(prefs['manga']))
        root.addWidget(self.manga)

        self.add_as_format = QCheckBox(
            'Add the result to the book as an extra format', self)
        self.add_as_format.setChecked(bool(prefs['add_as_format']))
        root.addWidget(self.add_as_format)

        self.replace_original = QCheckBox(
            'Remove the original format from the library afterwards', self)
        self.replace_original.setChecked(bool(prefs['replace_original']))
        root.addWidget(self.replace_original)

        hint = QLabel(
            'Removing the original format deletes the uncompressed copy '
            'from your Calibre library. Make sure you have a backup.', self)
        hint.setWordWrap(True)
        root.addWidget(hint)
        root.addStretch(1)

    def save_settings(self):
        prefs['profile'] = self.profile.currentData()
        prefs['preset'] = self.preset.currentData()
        prefs['quality'] = self.quality.value()
        prefs['fonts'] = self.fonts.currentData()
        prefs['png_mode'] = self.png_mode.currentData()
        prefs['keep_color'] = self.keep_color.isChecked()
        prefs['quantize'] = self.quantize.isChecked()
        prefs['progressive'] = self.progressive.isChecked()
        prefs['manga'] = self.manga.isChecked()
        prefs['add_as_format'] = self.add_as_format.isChecked()
        prefs['replace_original'] = self.replace_original.isChecked()
