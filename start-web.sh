#!/bin/sh
# Ebook Optimizer - lokale Oberflaeche starten
cd "$(dirname "$0")" || exit 1
exec python3 -m ebook_optimizer.web "$@"
