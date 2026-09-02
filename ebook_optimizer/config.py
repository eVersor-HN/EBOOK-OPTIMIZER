"""Einstellungen des Calibre-Plugins (nur innerhalb von Calibre nutzbar)."""

from calibre.utils.config import JSONConfig
from qt.core import (QCheckBox, QComboBox, QFormLayout, QLabel, QSpinBox,
                     QVBoxLayout, QWidget)

from calibre_plugins.ebook_optimizer.core.profiles import DEFAULT_PROFILE, PROFILES

prefs = JSONConfig('plugins/ebook_optimizer')
prefs.defaults['profile'] = DEFAULT_PROFILE
prefs.defaults['quality'] = 80
prefs.defaults['fonts'] = 'strip'
prefs.defaults['png_mode'] = 'auto'      # wie die CLI: kleineres Ergebnis
prefs.defaults['png_to_jpeg'] = False    # Altbestand, nur noch zum Migrieren
prefs.defaults['keep_color'] = False
prefs.defaults['quantize'] = True
prefs.defaults['progressive'] = True
prefs.defaults['manga'] = False
prefs.defaults['add_as_format'] = True   # Ergebnis als neues Format anhaengen
prefs.defaults['replace_original'] = False


PNG_MODES = (('Format behalten', 'keep'),
             ('kleineres Ergebnis gewinnt', 'auto'),
             ('immer JPEG', 'jpeg'))

# Uebersetzung in das Argument, das core.imaging erwartet.
PNG_MODE_ARG = {'keep': False, 'auto': 'auto', 'jpeg': True}


def current_png_mode():
    """Aktueller PNG-Modus, inkl. Migration der alten bool-Einstellung."""
    if 'png_mode' not in prefs and prefs.get('png_to_jpeg'):
        return 'jpeg'
    mode = prefs['png_mode']
    return mode if mode in PNG_MODE_ARG else 'auto'


class ConfigWidget(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.profile = QComboBox(self)
        keys = sorted(PROFILES)
        for k in keys:
            self.profile.addItem(PROFILES[k].name, k)
        idx = keys.index(prefs['profile']) if prefs['profile'] in keys else 0
        self.profile.setCurrentIndex(idx)
        form.addRow('Zielgeraet:', self.profile)

        self.quality = QSpinBox(self)
        self.quality.setRange(30, 100)
        self.quality.setValue(int(prefs['quality']))
        form.addRow('JPEG-Qualitaet:', self.quality)

        self.fonts = QComboBox(self)
        self.fonts.addItem('entfernen', 'strip')
        self.fonts.addItem('behalten', 'keep')
        self.fonts.setCurrentIndex(0 if prefs['fonts'] == 'strip' else 1)
        form.addRow('Eingebettete Schriften:', self.fonts)

        self.png_mode = QComboBox(self)
        for label, key in PNG_MODES:
            self.png_mode.addItem(label, key)
        cur = current_png_mode()
        self.png_mode.setCurrentIndex(
            [k for _l, k in PNG_MODES].index(cur))
        form.addRow('PNG/GIF/WebP:', self.png_mode)

        self.keep_color = QCheckBox('Farbe behalten (kein Graustufen-Zwang)', self)
        self.keep_color.setChecked(bool(prefs['keep_color']))
        root.addWidget(self.keep_color)

        self.quantize = QCheckBox('PNG auf 16 Graustufen reduzieren', self)
        self.quantize.setChecked(bool(prefs['quantize']))
        root.addWidget(self.quantize)

        self.progressive = QCheckBox(
            'Progressive JPEGs (rund 6 % kleiner, sehr alte Geraete koennen '
            'damit Probleme haben)', self)
        self.progressive.setChecked(bool(prefs['progressive']))
        root.addWidget(self.progressive)

        self.manga = QCheckBox('Comics: Leserichtung rechts-nach-links', self)
        self.manga.setChecked(bool(prefs['manga']))
        root.addWidget(self.manga)

        self.add_as_format = QCheckBox(
            'Ergebnis als zusaetzliches Format zum Buch hinzufuegen', self)
        self.add_as_format.setChecked(bool(prefs['add_as_format']))
        root.addWidget(self.add_as_format)

        self.replace_original = QCheckBox(
            'Originalformat danach aus der Bibliothek entfernen', self)
        self.replace_original.setChecked(bool(prefs['replace_original']))
        root.addWidget(self.replace_original)

        hint = QLabel(
            'Hinweis: "Originalformat entfernen" loescht die unkomprimierte '
            'Fassung aus der Calibre-Bibliothek. Vorher Backup pruefen.', self)
        hint.setWordWrap(True)
        root.addWidget(hint)
        root.addStretch(1)

    def save_settings(self):
        prefs['profile'] = self.profile.currentData()
        prefs['quality'] = self.quality.value()
        prefs['fonts'] = self.fonts.currentData()
        prefs['png_mode'] = self.png_mode.currentData()
        prefs['keep_color'] = self.keep_color.isChecked()
        prefs['quantize'] = self.quantize.isChecked()
        prefs['progressive'] = self.progressive.isChecked()
        prefs['manga'] = self.manga.isChecked()
        prefs['add_as_format'] = self.add_as_format.isChecked()
        prefs['replace_original'] = self.replace_original.isChecked()
