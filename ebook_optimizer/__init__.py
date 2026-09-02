"""Ebook Optimizer - E-Books und Comics fuer E-Reader verkleinern.

Doppelrolle:
  * als Calibre-Plugin (Klasse EbookOptimizerPlugin unten)
  * als eigenstaendiges Python-Paket (python -m ebook_optimizer.cli ...)

Der Calibre-Import ist bewusst abgesichert, damit die CLI ohne Calibre laeuft.
"""

__version_tuple__ = (0, 2, 0)
__version__ = '.'.join(str(x) for x in __version_tuple__)

try:
    from calibre.customize import InterfaceActionBase
except Exception:                                    # kein Calibre vorhanden
    InterfaceActionBase = None


if InterfaceActionBase is not None:

    class EbookOptimizerPlugin(InterfaceActionBase):
        name = 'Ebook Optimizer'
        description = ('Verkleinert E-Books und Comics fuer E-Reader: '
                       'Bilder auf Panelaufloesung, Graustufen, Schriften '
                       'entfernen, CBR nach CBZ.')
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
