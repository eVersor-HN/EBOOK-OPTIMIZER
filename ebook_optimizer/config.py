"""Settings dialog for the Calibre plugin (only usable inside Calibre)."""

from calibre.utils.config import JSONConfig
from qt.core import (QCheckBox, QComboBox, QFormLayout, QLabel, QSpinBox,
                     QVBoxLayout, QWidget)

from calibre_plugins.ebook_optimizer.core.profiles import (
    DEFAULT_PROFILE, DEFAULT_TARGET, TARGET_ORDER, TARGETS,
    profiles_by_brand)

prefs = JSONConfig('plugins/ebook_optimizer')
prefs.defaults['profile'] = DEFAULT_PROFILE
prefs.defaults['target'] = DEFAULT_TARGET
prefs.defaults['quality'] = 0            # 0 = measure per image
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


def current_target():
    t = prefs['target']
    return t if t in TARGETS else DEFAULT_TARGET


def effective_quality():
    """Fixed quality, or 0 when the quality is measured per image."""
    return int(prefs['quality'] or 0)


def effective_target_error():
    """Error budget, or None when a fixed quality was pinned."""
    if int(prefs['quality'] or 0):
        return None
    return TARGETS[current_target()].budget


def effective_quantize():
    return bool(prefs['quantize']) and TARGETS[current_target()].quantize


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

        self.target = QComboBox(self)
        for key in TARGET_ORDER:
            t = TARGETS[key]
            self.target.addItem(
                '%s  (at most %.2f %% of pixels differ)'
                % (t.name, t.budget), key)
        self.target.setCurrentIndex(TARGET_ORDER.index(current_target()))
        form.addRow('Result should look:', self.target)

        self.quality = QSpinBox(self)
        self.quality.setRange(0, 100)
        self.quality.setValue(int(prefs['quality'] or 0))
        self.quality.setSpecialValueText('measure per image')
        form.addRow('Fixed JPEG quality:', self.quality)

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
            'Store the result on the book (same-format originals are kept '
            'as ORIGINAL_EPUB etc.)', self)
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
        prefs['target'] = self.target.currentData()
        prefs['quality'] = self.quality.value()
        prefs['fonts'] = self.fonts.currentData()
        prefs['png_mode'] = self.png_mode.currentData()
        prefs['keep_color'] = self.keep_color.isChecked()
        prefs['quantize'] = self.quantize.isChecked()
        prefs['progressive'] = self.progressive.isChecked()
        prefs['manga'] = self.manga.isChecked()
        prefs['add_as_format'] = self.add_as_format.isChecked()
        prefs['replace_original'] = self.replace_original.isChecked()
