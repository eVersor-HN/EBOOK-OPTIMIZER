"""EBOOK-OPTIMIZER - shrink e-books and comics for e-ink readers.

Two roles:
  * a Calibre plugin (class EbookOptimizerPlugin below)
  * a standalone Python package (python -m ebook_optimizer.cli ...)

The Calibre import is guarded on purpose so the command line runs
without Calibre installed.
"""

__version_tuple__ = (0, 4, 5)
__version__ = '.'.join(str(x) for x in __version_tuple__)

try:
    from calibre.customize import InterfaceActionBase
except Exception:                                    # no Calibre present
    InterfaceActionBase = None


if InterfaceActionBase is not None:

    class EbookOptimizerPlugin(InterfaceActionBase):
        name = 'EBOOK-OPTIMIZER'
        description = ('Shrink e-books and comics for e-ink readers: '
                       'images scaled to the panel, greyscale, embedded '
                       'fonts removed, CBR converted to CBZ.')
        supported_platforms = ['windows', 'osx', 'linux']
        author = 'Marco Aurelio Fattizzo'
        version = __version_tuple__
        minimum_calibre_version = (5, 0, 0)
        actual_plugin = 'calibre_plugins.ebook_optimizer.ui:EbookOptimizerAction'

        def is_customizable(self):
            return True

        def config_widget(self):
            from calibre_plugins.ebook_optimizer.config import ConfigWidget
            return ConfigWidget()

        def save_settings(self, config_widget):
            config_widget.save_settings()
