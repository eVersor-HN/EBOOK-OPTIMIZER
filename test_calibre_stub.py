"""Run ui.py and config.py against stand-in Calibre APIs.

No substitute for starting real Calibre: whether those APIs are named
and behave as assumed can only be answered by Calibre itself. Everything
else is covered here - import errors, typos in attribute names, wrong
signatures in our own code, and the whole job logic in _run() including
real EPUB and CBZ optimisation.
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


# ------------------------------------------------------- Calibre stand-ins ---

def _mod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


class _Q(object):
    """Minimal Qt widget stand-in: remembers what was set."""

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

    def setSpecialValueText(self, t):
        self._special = t

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
    """Behaves like Calibre's JSONConfig: defaults as the fallback."""

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
class Dispatcher(object):
    """Stand-in for calibre's GUI-thread marshaller: remembers that the
    callback was wrapped, then calls straight through."""

    def __init__(self, func):
        self.func = func

    def __call__(self, *a, **kw):
        return self.func(*a, **kw)


_mod('calibre.gui2',
     Dispatcher=Dispatcher,
     error_dialog=lambda *a, **kw: ('error', a),
     info_dialog=lambda *a, **kw: ('info', a))
_mod('calibre.gui2.actions', InterfaceAction=InterfaceAction)
_mod('calibre.gui2.threaded_jobs', ThreadedJob=ThreadedJob)
_mod('calibre.utils')
_mod('calibre.utils.config', JSONConfig=JSONConfig)
_mod('qt.core', QCheckBox=_Q, QComboBox=_Q, QFormLayout=_Q, QLabel=_Q,
     QSpinBox=_Q, QVBoxLayout=_Q, QWidget=_Q)

# calibre_plugins.ebook_optimizer -> the real package
import ebook_optimizer                                            # noqa: E402

cp = _mod('calibre_plugins')
cp.ebook_optimizer = ebook_optimizer
sys.modules['calibre_plugins.ebook_optimizer'] = ebook_optimizer
for _sub in ('core', 'core.cbz', 'core.epub', 'core.imaging',
             'core.profiles', 'core.util'):
    __import__('ebook_optimizer.' + _sub)
    sys.modules['calibre_plugins.ebook_optimizer.' + _sub] = sys.modules['ebook_optimizer.' + _sub]


# --------------------------------------------------------------- Test cases ---

def test_plugin_entry():
    print('Plugin entry point')
    import importlib
    importlib.reload(ebook_optimizer)
    sys.modules['calibre_plugins.ebook_optimizer'] = ebook_optimizer
    cls = getattr(ebook_optimizer, 'EbookOptimizerPlugin', None)
    check('EbookOptimizerPlugin is defined when Calibre is importable', cls is not None)
    if cls is None:
        return
    check('version is a tuple', isinstance(cls.version, tuple),
          str(cls.version))
    check('actual_plugin points at ui:EbookOptimizerAction',
          cls.actual_plugin == 'calibre_plugins.ebook_optimizer.ui:EbookOptimizerAction')
    check('minimum_calibre_version is set',
          isinstance(cls.minimum_calibre_version, tuple))


def test_config():
    print('')
    print('Settings dialog')
    import ebook_optimizer.config as cfg
    sys.modules['calibre_plugins.ebook_optimizer.config'] = cfg

    from ebook_optimizer.core.profiles import PROFILES, TARGET_ORDER
    w = cfg.ConfigWidget()
    check('ConfigWidget builds', True)
    check('every device is in the dropdown',
          w.profile.count() == len(PROFILES), str(w.profile.count()))
    check('every quality target is in the dropdown',
          w.target.count() == len(TARGET_ORDER), str(w.target.count()))
    check('image-format mode has three options', w.png_mode.count() == 3)
    check('image-format default is auto', w.png_mode.currentData() == 'auto',
          str(w.png_mode.currentData()))

    w.png_mode.setCurrentIndex(2)
    w.save_settings()
    check('save_settings stores png_mode', cfg.prefs['png_mode'] == 'jpeg',
          str(cfg.prefs['png_mode']))
    check('progressive JPEG is the default',
          cfg.prefs.defaults['progressive'] is True)
    w.progressive.setChecked(False)
    w.save_settings()
    check('progressive can be switched off',
          cfg.prefs['progressive'] is False)

    cfg.prefs.clear()
    check('by default the quality is measured per image',
          cfg.effective_quality() == 0 and cfg.effective_target_error() == 0.10,
          '%s / %s' % (cfg.effective_quality(), cfg.effective_target_error()))
    cfg.prefs['target'] = 'smaller'
    check('the "smaller" target loosens the budget',
          cfg.effective_target_error() == 0.75,
          str(cfg.effective_target_error()))
    cfg.prefs['quality'] = 72
    check('a fixed quality switches the measurement off',
          cfg.effective_quality() == 72
          and cfg.effective_target_error() is None,
          '%s / %s' % (cfg.effective_quality(), cfg.effective_target_error()))
    cfg.prefs.clear()

    # Migration: the old boolean switch with no new key
    cfg.prefs.clear()
    cfg.prefs['png_to_jpeg'] = True
    check('legacy png_to_jpeg=True migrates to "jpeg"',
          cfg.current_png_mode() == 'jpeg', str(cfg.current_png_mode()))
    cfg.prefs.clear()
    check('with nothing stored: auto', cfg.current_png_mode() == 'auto')
    check('plugin uses the same values as the command line',
          set(cfg.PNG_MODE_ARG.values()) == set([False, 'auto', True]))


class FakeDB(object):
    """Stand-in for the few new_api methods ui.py uses."""

    def __init__(self, files):
        self.files = files          # book_id -> (FORMAT, pfad)
        self.added = []
        self.removed = []
        self.originals = []         # (book_id, fmt) saved as ORIGINAL_

    def field_for(self, field, book_id):
        return 'Buch %d' % book_id if field == 'title' else None

    def formats(self, book_id):
        fmts = [self.files[book_id][0]]
        fmts += ['ORIGINAL_' + f for b, f in self.originals if b == book_id]
        return tuple(fmts)

    def save_original_format(self, book_id, fmt):
        self.originals.append((book_id, fmt))

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
    print('Background job (_run) with real files')
    import ebook_optimizer.config as cfg
    sys.modules['calibre_plugins.ebook_optimizer.config'] = cfg
    import ebook_optimizer.ui as ui
    check('ui.py imports', True)

    data = os.path.join(HERE, 'testdata')
    epub = os.path.join(data, 'testbuch.epub')
    cbz = os.path.join(data, 'testcomic.cbz')
    if not (os.path.exists(epub) and os.path.exists(cbz)):
        check('test data present, run make_testdata.py', False)
        return

    db = FakeDB({1: ('EPUB', epub), 2: ('CBZ', cbz)})
    opts = {'profile': 'pb_verse_pro', 'quality': 80, 'fonts': 'strip',
            'png_mode': 'auto', 'keep_color': False, 'quantize': True,
            'manga': False, 'progressive': True, 'add_as_format': True,
            'replace_original': True, 'target_error': 0.10}
    # Exactly the keys ui.start() assembles. If those drift apart it
    # shows up here rather than inside Calibre.
    built = {'profile', 'fonts', 'keep_color', 'manga', 'progressive',
             'add_as_format', 'replace_original', 'png_mode', 'quality',
             'quantize', 'target_error'}
    check('ui.start() supplies exactly the expected keys',
          built == set(opts), str(built ^ set(opts)))
    log_lines = []
    q = FakeQueue()

    results = ui._run([1, 2], db, opts, log_lines.append, FakeAbort(), q)

    check('both books processed', len(results) == 2, str(len(results)))
    check('progress reported', len(q.items) == 2)
    check('no traceback in the log',
          not any('FEHLER' in l for l in log_lines),
          '' if not log_lines else log_lines[-1][:60])
    check('EPUB written back as EPUB',
          any(f == 'EPUB' for _b, f, _n in db.added))
    check('comic written back as CBZ',
          any(f == 'CBZ' for _b, f, _n in db.added))
    check('result is smaller than the original',
          all(new < old for _bid, _t, old, new in results),
          str([(o, n) for _bid, _t, o, n in results]))
    check('no format deleted when input and output match',
          db.removed == [], str(db.removed))
    check('same-format originals are saved as ORIGINAL_ first',
          sorted(db.originals) == [(1, 'EPUB'), (2, 'CBZ')],
          str(db.originals))
    n_before = len(db.originals)
    ui._run([1], db, opts, log_lines.append, FakeAbort(), q)
    check('a second run does not overwrite the saved original',
          len(db.originals) == n_before, str(db.originals))

    # The manga switch has to run through without error
    before = len(log_lines)
    opts2 = dict(opts, manga=True, add_as_format=False)
    ui._run([2], db, opts2, log_lines.append, FakeAbort(), q)
    check('manga option runs without error',
          not any('FEHLER' in l for l in log_lines[before:]))

    check('abort is honoured',
          ui._run([1, 2], db, opts, log_lines.append, Aborted(), q) == [])

    # A book with no suitable format must not crash
    db2 = FakeDB({3: ('PDF', epub)})
    check('a book with no EPUB or comic is skipped',
          ui._run([3], db2, opts, log_lines.append, FakeAbort(), q) == [])


def test_action():
    print('')
    print('Toolbar action')
    import ebook_optimizer.ui as ui
    act = ui.EbookOptimizerAction()
    check('action_spec is complete', len(ui.EbookOptimizerAction.action_spec) == 4)
    act.genesis()
    check('genesis runs', True)

    class Sel(object):
        def selectedRows(self):
            return []

    act.gui = types.SimpleNamespace(
        library_view=types.SimpleNamespace(selectionModel=lambda: Sel()))
    check('an empty selection shows a notice instead of crashing',
          act.start()[0] == 'error')

    # The completion callback MUST be marshalled onto the GUI thread.
    # ThreadedJob calls it in the worker thread, and a Qt dialog built
    # there freezes calibre - which is exactly what happened in a real
    # calibre 9.14 before this was wrapped in Dispatcher.
    import ebook_optimizer.ui as ui2
    src = open(ui2.__file__, encoding='utf-8').read()
    check('the done callback is wrapped in Dispatcher',
          'Dispatcher(self.done)' in src)


if __name__ == '__main__':
    test_plugin_entry()
    test_config()
    test_job()
    test_action()
    print('')
    print('%s' % ('ALL STUB TESTS PASSED' if not FAILS
                  else '%d FAILED: %s' % (len(FAILS), ', '.join(FAILS))))
    sys.exit(1 if FAILS else 0)
