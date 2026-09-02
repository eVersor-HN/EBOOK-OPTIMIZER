"""Start: python -m ebook_optimizer.web"""

import argparse

from .server import serve


def main():
    ap = argparse.ArgumentParser(
        prog='EBOOK-OPTIMIZER-web',
        description='Startet die lokale Oberflaeche von EBOOK-OPTIMIZER')
    ap.add_argument('--port', type=int, default=8756)
    ap.add_argument('--host', default='127.0.0.1',
                    help='Standard 127.0.0.1 - nur der eigene Rechner')
    ap.add_argument('--no-browser', action='store_true',
                    help='Browser nicht automatisch oeffnen')
    a = ap.parse_args()
    serve(host=a.host, port=a.port, open_browser=not a.no_browser)


if __name__ == '__main__':
    main()
