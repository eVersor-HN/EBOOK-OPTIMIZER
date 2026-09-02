"""Laesst ui.py und config.py gegen nachgebaute Calibre-APIs laufen.

Kein Ersatz fuer einen echten Calibre-Start: ob die APIs so heissen und
sich so verhalten, kann nur Calibre selbst beantworten. Alles andere deckt
dieser Test ab - Importfehler, Tippfehler in Attributnamen, falsche
Signaturen im eigenen Code und die komplette Job-Logik in _run()
inklusive echter EPUB-/CBZ-Optimierung.
"""

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FAILS = []


def check(name, cond, extra=''):
    print('  %-46s %s %s' % (name, 'ok' if cond else 'FAIL', extra))
    if not cond:
        FAILS.append(name)


# ------------------------------------------------------- Calibre-Attrappen ---

def _mod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


class _Q(object):
    """Minimaler Qt-Widget-Ersatz: merkt sich, was gesetzt wurde."""

    def __init__(self, *a, **kw):
        self._items = []
        self._idx = 0
        self._checked = False
        self._value = 0

    # QComboBox
    def addItem(self, label, data=None):
        self._items.append((label, data))

    def setCurrentIndex(self, i):
        self._idx = i

    def currentData(self):
        return self._items[self._idx][1]

    def count(self):
        return len(self._items)

    # QCheckBox
    def setChecked(self, v):
        self._checked = bool(v)

    def isChecked(self):
        return self._checked

    # QSpinBox
    def setRange(self, a, b):
        self._range = (a, b)

    def setValue(self, v):
        self._value = v

    def value(self):
        return self._value

    # Layouts / Labels
    def addLayout(self, *a):
        pass

    def addRow(self, *a):
        pass

    def addWidget(self, *a):
        pass

    def addStretch(self, *a):
        pass

    def setWordWrap(self, *a):
        pass


class JSONConfig(dict):
    """Verhaelt sich wie Calibres JSONConfig: Defaults als Rueckfallebene."""

    def __init__(self, name):
        dict.__init__(self)
        self.defaults = {}

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults[key]


class InterfaceAction(object):
    name = ''
    action_spec = ()

    def __init__(self):
        self.gui = None
        self.qaction = types.SimpleNamespace(
            triggered=types.SimpleNamespace(connect=lambda f: None))


class InterfaceActionBase(object):
    def __init__(self, *a, **kw):
        pass


class ThreadedJob(object):
    def __init__(self, kind, desc, func, args, kwargs, callback):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.callback = callback
        self.failed = False
        self.result = None


_mod('calibre')
_mod('calibre.customize', InterfaceActionBase=InterfaceActionBase)
_mod('calibre.gui2',
     error_dialog=lambda *a, **kw: ('error', a),
     info_dialog=lambda *a, **kw: ('info', a))
_mod('calibre.gui2.actions', InterfaceAction=InterfaceAction)
_mod('calibre.gui2.threaded_jobs', ThreadedJob=ThreadedJob)
_mod('calibre.utils')
_mod('calibre.utils.config', JSONConfig=JSONConfig)
_mod('qt.core', QCheckBox=_Q, QComboBox=_Q, QFormLayout=_Q, QLabel=_Q,
     QSpinBox=_Q, QVBoxLayout=_Q, QWidget=_Q)

# calibre_plugins.ebook_optimizer -> das echte Paket
import ebook_optimizer                                            # noqa: E402

cp = _mod('calibre_plugins')
cp.ebook_optimizer = ebook_optimizer
sys.modules['calibre_plugins.ebook_optimizer'] = ebook_optimizer
for _sub in ('core', 'core.cbz', 'core.epub', 'core.imaging',
             'core.profiles', 'core.util'):
    __import__('ebook_optimizer.' + _sub)
    sys.modules['calibre_plugins.ebook_optimizer.' + _sub] = sys.modules['ebook_optimizer.' + _sub]


# --------------------------------------------------------------- Testfaelle ---

def test_plugin_entry():
    print('Plugin-Einstiegspunkt')
    import importlib
    importlib.reload(ebook_optimizer)
    sys.modules['calibre_plugins.ebook_optimizer'] = ebook_optimizer
    cls = getattr(ebook_optimizer, 'EbookOptimizerPlugin', None)
    check('EbookOptimizerPlugin wird bei Calibre-Import definiert', cls is not None)
    if cls is None:
        return
    check('Version ist ein Tupel', isinstance(cls.version, tuple),
          str(cls.version))
    check('actual_plugin zeigt auf ui:EbookOptimizerAction',
          cls.actual_plugin == 'calibre_plugins.ebook_optimizer.ui:EbookOptimizerAction')
    check('minimum_calibre_version gesetzt',
          isinstance(cls.minimum_calibre_version, tuple))


def test_config():
    print('')
    print('Einstellungsdialog')
    import ebook_optimizer.config as cfg
    sys.modules['calibre_plugins.ebook_optimizer.config'] = cfg

    w = cfg.ConfigWidget()
    check('ConfigWidget baut sich auf', True)
    check('alle Profile im Auswahlfeld', w.profile.count() == 5,
          str(w.profile.count()))
    check('PNG-Modus hat drei Optionen', w.png_mode.count() == 3)
    check('PNG-Standard ist auto', w.png_mode.currentData() == 'auto',
          str(w.png_mode.currentData()))

    w.png_mode.setCurrentIndex(2)
    w.save_settings()
    check('save_settings schreibt png_mode', cfg.prefs['png_mode'] == 'jpeg',
          str(cfg.prefs['png_mode']))
    check('gespeicherte Qualitaet kommt zurueck',
          cfg.prefs['quality'] == w.quality.value())
    check('progressive JPEGs sind voreingestellt',
          cfg.prefs.defaults['progressive'] is True)
    w.progressive.setChecked(False)
    w.save_settings()
    check('progressive laesst sich abschalten',
          cfg.prefs['progressive'] is False)

    # Migration: alter bool-Schalter ohne neuen Schluessel
    cfg.prefs.clear()
    cfg.prefs['png_to_jpeg'] = True
    check('alte Einstellung png_to_jpeg=True wird zu "jpeg"',
          cfg.current_png_mode() == 'jpeg', str(cfg.current_png_mode()))
    cfg.prefs.clear()
    check('ohne Einstellung: auto', cfg.current_png_mode() == 'auto')
    check('Plugin nutzt dieselben Werte wie die CLI',
          set(cfg.PNG_MODE_ARG.values()) == set([False, 'auto', True]))


class FakeDB(object):
    """Nachbau der wenigen new_api-Methoden, die ui.py benutzt."""

    def __init__(self, files):
        self.files = files          # book_id -> (FORMAT, pfad)
        self.added = []
        self.removed = []

    def field_for(self, field, book_id):
        return 'Buch %d' % book_id if field == 'title' else None

    def formats(self, book_id):
        return (self.files[book_id][0],)

    def format(self, book_id, fmt):
        with open(self.files[book_id][1], 'rb') as f:
            return f.read()

    def add_format(self, book_id, fmt, stream, replace=False):
        self.added.append((book_id, fmt, len(stream.read())))
        return True

    def remove_formats(self, spec):
        self.removed.append(spec)


class FakeAbort(object):
    def is_set(self):
        return False


class Aborted(object):
    def is_set(self):
        return True


class FakeQueue(object):
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


def test_job():
    print('')
    print('Hintergrundjob (_run) mit echten Dateien')
    import ebook_optimizer.config as cfg
    sys.modules['calibre_plugins.ebook_optimizer.config'] = cfg
    import ebook_optimizer.ui as ui
    check('ui.py importierbar', True)

    data = os.path.join(HERE, 'testdata')
    epub = os.path.join(data, 'testbuch.epub')
    cbz = os.path.join(data, 'testcomic.cbz')
    if not (os.path.exists(epub) and os.path.exists(cbz)):
        check('Testdaten vorhanden (make_testdata.py ausfuehren)', False)
        return

    db = FakeDB({1: ('EPUB', epub), 2: ('CBZ', cbz)})
    opts = {'profile': 'pb_verse_pro', 'quality': 80, 'fonts': 'strip',
            'png_mode': 'auto', 'keep_color': False, 'quantize': True,
            'manga': False, 'progressive': True, 'add_as_format': True,
            'replace_original': True}
    log_lines = []
    q = FakeQueue()

    results = ui._run([1, 2], db, opts, log_lines.append, FakeAbort(), q)

    check('beide Buecher verarbeitet', len(results) == 2, str(len(results)))
    check('Fortschritt gemeldet', len(q.items) == 2)
    check('kein Traceback im Log',
          not any('FEHLER' in l for l in log_lines),
          '' if not log_lines else log_lines[-1][:60])
    check('EPUB als EPUB zurueckgeschrieben',
          any(f == 'EPUB' for _b, f, _n in db.added))
    check('Comic als CBZ zurueckgeschrieben',
          any(f == 'CBZ' for _b, f, _n in db.added))
    check('Ergebnis ist kleiner als das Original',
          all(new < old for _t, old, new in results),
          str([(o, n) for _t, o, n in results]))
    check('kein Format geloescht, wenn Ein- und Ausgabe gleich sind',
          db.removed == [], str(db.removed))

    # Manga-Schalter muss ohne Fehler durchlaufen
    before = len(log_lines)
    opts2 = dict(opts, manga=True, add_as_format=False)
    ui._run([2], db, opts2, log_lines.append, FakeAbort(), q)
    check('Manga-Option laeuft ohne Fehler',
          not any('FEHLER' in l for l in log_lines[before:]))

    check('Abbruch wird beachtet',
          ui._run([1, 2], db, opts, log_lines.append, Aborted(), q) == [])

    # Buch ohne passendes Format darf nicht abstuerzen
    db2 = FakeDB({3: ('PDF', epub)})
    check('Buch ohne EPUB/Comic wird uebersprungen',
          ui._run([3], db2, opts, log_lines.append, FakeAbort(), q) == [])


def test_action():
    print('')
    print('Toolbar-Aktion')
    import ebook_optimizer.ui as ui
    act = ui.EbookOptimizerAction()
    check('action_spec vollstaendig', len(ui.EbookOptimizerAction.action_spec) == 4)
    act.genesis()
    check('genesis laeuft durch', True)

    class Sel(object):
        def selectedRows(self):
            return []

    act.gui = types.SimpleNamespace(
        library_view=types.SimpleNamespace(selectionModel=lambda: Sel()))
    check('leere Auswahl gibt einen Hinweis statt abzustuerzen',
          act.start()[0] == 'error')


if __name__ == '__main__':
    test_plugin_entry()
    test_config()
    test_job()
    test_action()
    print('')
    print('%s' % ('ALLE STUB-TESTS BESTANDEN' if not FAILS
                  else '%d FEHLER: %s' % (len(FAILS), ', '.join(FAILS))))
    sys.exit(1 if FAILS else 0)
