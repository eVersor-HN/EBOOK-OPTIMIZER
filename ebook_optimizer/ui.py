"""Calibre-Oberflaeche: Toolbar-Button, der die markierten Buecher optimiert."""

import os
import tempfile
import traceback

from calibre.gui2 import error_dialog, info_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.threaded_jobs import ThreadedJob

from calibre_plugins.ebook_optimizer.config import (PNG_MODE_ARG, current_png_mode, prefs)
from calibre_plugins.ebook_optimizer.core.cbz import optimize_comic
from calibre_plugins.ebook_optimizer.core.epub import optimize_epub
from calibre_plugins.ebook_optimizer.core.profiles import get_profile
from calibre_plugins.ebook_optimizer.core.util import human_size, pct_saved

EPUB_FMTS = ('EPUB',)
COMIC_FMTS = ('CBZ', 'CBR', 'CBT')


def _run(book_ids, db, opts, log, abort, notifications):
    """Laeuft im Hintergrund-Thread von Calibre."""
    profile = get_profile(opts['profile'])
    force_gray = False if opts['keep_color'] else None
    png_mode = PNG_MODE_ARG.get(opts['png_mode'], 'auto')
    # In Calibre bewusst seriell: der Prozesspool ist in eingebetteten
    # Python-Umgebungen unzuverlaessig, und der Job laeuft ohnehin im
    # Hintergrund-Thread. Das Tempo kommt hier aus draft().
    common = dict(progressive=opts['progressive'], jobs=1)
    results = []
    total = len(book_ids)

    for i, book_id in enumerate(book_ids):
        if abort.is_set():
            break
        notifications.put((i / max(total, 1), 'Optimiere %d/%d' % (i + 1, total)))
        title = db.field_for('title', book_id) or str(book_id)
        fmts = [f.upper() for f in (db.formats(book_id) or ())]

        src_fmt = next((f for f in EPUB_FMTS + COMIC_FMTS if f in fmts), None)
        if src_fmt is None:
            log('%s: kein EPUB/Comic-Format' % title)
            continue

        tmpdir = tempfile.mkdtemp(prefix='ebook_opt_')
        try:
            src = os.path.join(tmpdir, 'in.' + src_fmt.lower())
            with open(src, 'wb') as f:
                f.write(db.format(book_id, src_fmt))

            if src_fmt in EPUB_FMTS:
                dst = os.path.join(tmpdir, 'out.epub')
                rep = optimize_epub(
                    src, dst, profile, quality=opts['quality'],
                    png_to_jpeg=png_mode, fonts=opts['fonts'],
                    force_grayscale=force_gray, quantize_gray=opts['quantize'],
                    **common)
                out_fmt = 'EPUB'
            else:
                dst = os.path.join(tmpdir, 'out.cbz')
                rep = optimize_comic(
                    src, dst, profile, quality=opts['quality'],
                    to_jpeg=png_mode,
                    force_grayscale=force_gray, manga=opts['manga'],
                    quantize_gray=opts['quantize'], **common)
                out_fmt = 'CBZ'

            if rep.new_size >= rep.old_size:
                log('%s: kein Gewinn, uebersprungen' % title)
                continue

            if opts['add_as_format']:
                with open(dst, 'rb') as f:
                    db.add_format(book_id, out_fmt, f, replace=True)
                if opts['replace_original'] and src_fmt != out_fmt:
                    try:
                        db.remove_formats({book_id: (src_fmt,)})
                    except Exception:
                        log('%s: Originalformat konnte nicht entfernt werden'
                            % title)

            results.append((title, rep.old_size, rep.new_size))
            log('%s: %s -> %s (-%.1f%%)' % (
                title, human_size(rep.old_size), human_size(rep.new_size),
                pct_saved(rep.old_size, rep.new_size)))
        except Exception:
            log('%s: FEHLER\n%s' % (title, traceback.format_exc()))
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    return results


class EbookOptimizerAction(InterfaceAction):
    name = 'Ebook Optimizer'
    action_spec = ('E-Ink optimieren', None,
                   'Markierte Buecher fuer den E-Reader verkleinern', None)
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.start)

    def start(self):
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows:
            return error_dialog(self.gui, 'Nichts markiert',
                                'Bitte zuerst Buecher in der Liste markieren.',
                                show=True)
        book_ids = list(self.gui.library_view.get_selected_ids())
        db = self.gui.current_db.new_api
        opts = {k: prefs[k] for k in (
            'profile', 'quality', 'fonts', 'keep_color', 'quantize',
            'manga', 'progressive', 'add_as_format', 'replace_original')}
        opts['png_mode'] = current_png_mode()

        job = ThreadedJob(
            'ebook_optimizer', 'Optimiere %d Buch/Buecher' % len(book_ids),
            _run, (book_ids, db, opts), {}, self.done)
        self.gui.job_manager.run_threaded_job(job)
        self.gui.status_bar.show_message('Optimierung gestartet', 3000)

    def done(self, job):
        if job.failed:
            return self.gui.job_exception(job)
        results = job.result or []
        if not results:
            return info_dialog(self.gui, 'Fertig',
                               'Keine Datei konnte verkleinert werden.',
                               show=True)
        old = sum(r[1] for r in results)
        new = sum(r[2] for r in results)
        lines = ['%s: %s -> %s' % (t, human_size(o), human_size(n))
                 for t, o, n in results[:20]]
        if len(results) > 20:
            lines.append('... und %d weitere' % (len(results) - 20))
        msg = ('%d Datei(en) optimiert.\nGespart: %s (%.1f%%)\n\n%s'
               % (len(results), human_size(old - new), pct_saved(old, new),
                  '\n'.join(lines)))
        self.gui.library_view.model().refresh_ids(
            [], current_row=self.gui.library_view.currentIndex().row())
        info_dialog(self.gui, 'Ebook Optimizer', msg, show=True)
