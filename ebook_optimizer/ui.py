"""Calibre integration: a toolbar button that optimises the selected books."""

import os
import shutil
import tempfile
import traceback

from calibre.gui2 import Dispatcher, error_dialog, info_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.threaded_jobs import ThreadedJob

from calibre_plugins.ebook_optimizer.config import (
    PNG_MODE_ARG, current_png_mode, effective_quality, effective_quantize,
    effective_target_error, prefs)
from calibre_plugins.ebook_optimizer.core.cbz import optimize_comic
from calibre_plugins.ebook_optimizer.core.epub import optimize_epub
from calibre_plugins.ebook_optimizer.core.profiles import get_profile
from calibre_plugins.ebook_optimizer.core.util import human_size, pct_saved

EPUB_FMTS = ('EPUB', 'KEPUB')
COMIC_FMTS = ('CBZ', 'CBR', 'CBT')


def _run(book_ids, db, opts, log, abort, notifications):
    """Runs in Calibre's background thread."""
    profile = get_profile(opts['profile'])
    force_gray = False if opts['keep_color'] else None
    png_mode = PNG_MODE_ARG.get(opts['png_mode'], 'auto')
    # Deliberately serial inside Calibre: a process pool is unreliable in
    # embedded Python environments, and the job already runs off the UI
    # thread. The speed here comes from draft() decoding.
    common = dict(progressive=opts['progressive'], jobs=1,
                  target_error=opts['target_error'])
    results = []
    total = len(book_ids)

    for i, book_id in enumerate(book_ids):
        if abort.is_set():
            break
        notifications.put((i / max(total, 1),
                           'Optimising %d of %d' % (i + 1, total)))
        title = db.field_for('title', book_id) or str(book_id)
        fmts = [f.upper() for f in (db.formats(book_id) or ())]

        src_fmt = next((f for f in EPUB_FMTS + COMIC_FMTS if f in fmts), None)
        if src_fmt is None:
            log('%s: no EPUB or comic format' % title)
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
                    force_grayscale=force_gray,
                    quantize_gray=opts['quantize'], **common)
                out_fmt = src_fmt
            else:
                dst = os.path.join(tmpdir, 'out.cbz')
                rep = optimize_comic(
                    src, dst, profile, quality=opts['quality'],
                    to_jpeg=png_mode, force_grayscale=force_gray,
                    manga=opts['manga'], quantize_gray=opts['quantize'],
                    **common)
                out_fmt = 'CBZ'

            if rep.new_size >= rep.old_size:
                log('%s: no gain, skipped' % title)
                continue

            if opts['add_as_format']:
                # Same-format optimisation replaces the stored file, since
                # a calibre book holds one file per format. Keep the
                # untouched original as ORIGINAL_<FMT> first - calibre's
                # own convention, restorable from the book's format menu.
                # Only on the first run, or a second click would overwrite
                # the true original with the once-optimised copy.
                if out_fmt in fmts and 'ORIGINAL_' + out_fmt not in fmts:
                    try:
                        db.save_original_format(book_id, out_fmt)
                    except Exception:
                        log('%s: could not keep an original-format copy'
                            % title)
                with open(dst, 'rb') as f:
                    db.add_format(book_id, out_fmt, f, replace=True)
                if opts['replace_original'] and src_fmt != out_fmt:
                    try:
                        db.remove_formats({book_id: (src_fmt,)})
                    except Exception:
                        log('%s: could not remove the original format'
                            % title)

            results.append((book_id, title, rep.old_size, rep.new_size))
            log('%s: %s -> %s (-%.1f%%)'
                % (title, human_size(rep.old_size), human_size(rep.new_size),
                   pct_saved(rep.old_size, rep.new_size)))
        except Exception:
            log('%s: FAILED\n%s' % (title, traceback.format_exc()))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return results


class EbookOptimizerAction(InterfaceAction):
    name = 'EBOOK-OPTIMIZER'
    action_spec = ('Optimize for e-reader', None,
                   'Shrink the selected books for an e-ink reader', None)
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.start)

    def start(self):
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows:
            return error_dialog(self.gui, 'Nothing selected',
                                'Select one or more books in the list first.',
                                show=True)
        book_ids = list(self.gui.library_view.get_selected_ids())
        db = self.gui.current_db.new_api
        opts = {k: prefs[k] for k in (
            'profile', 'fonts', 'keep_color', 'manga', 'progressive',
            'add_as_format', 'replace_original')}
        opts['png_mode'] = current_png_mode()
        opts['quality'] = effective_quality() or 80
        opts['target_error'] = effective_target_error()
        opts['quantize'] = effective_quantize()

        # ThreadedJob invokes the callback in the WORKER thread (see
        # calibre gui2/threaded_jobs.py, start_work). Building Qt dialogs
        # there freezes the interface, so the callback goes through
        # Dispatcher, which re-emits the call on the GUI thread.
        job = ThreadedJob(
            'ebook_optimizer', 'Optimizing %d book(s)' % len(book_ids),
            _run, (book_ids, db, opts), {}, Dispatcher(self.done))
        self.gui.job_manager.run_threaded_job(job)
        self.gui.status_bar.show_message('Optimization started', 3000)

    def done(self, job):
        if job.failed:
            return self.gui.job_exception(job)
        results = job.result or []
        if not results:
            return info_dialog(self.gui, 'Finished',
                               'No file could be made smaller.', show=True)
        old = sum(r[2] for r in results)
        new = sum(r[3] for r in results)
        lines = ['%s: %s -> %s' % (t, human_size(o), human_size(n))
                 for _bid, t, o, n in results[:20]]
        if len(results) > 20:
            lines.append('... and %d more' % (len(results) - 20))
        msg = ('%d file(s) optimized.\nSaved: %s (%.1f%%)\n\n%s'
               % (len(results), human_size(old - new), pct_saved(old, new),
                  '\n'.join(lines)))
        # Refresh the changed rows so the size column updates.
        try:
            self.gui.library_view.model().refresh_ids(
                [r[0] for r in results])
        except Exception:
            pass
        info_dialog(self.gui, 'EBOOK-OPTIMIZER', msg, show=True)
