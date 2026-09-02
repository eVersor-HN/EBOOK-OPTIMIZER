"""Entry point: python -m ebook_optimizer.web"""

import argparse

from .server import serve


def main():
    ap = argparse.ArgumentParser(
        prog='EBOOK-OPTIMIZER-web',
        description='Start the local EBOOK-OPTIMIZER interface')
    ap.add_argument('--port', type=int, default=8756)
    ap.add_argument('--host', default='127.0.0.1',
                    help='default 127.0.0.1 - this machine only')
    ap.add_argument('--no-browser', action='store_true',
                    help='do not open the browser automatically')
    a = ap.parse_args()
    serve(host=a.host, port=a.port, open_browser=not a.no_browser)


if __name__ == '__main__':
    main()
