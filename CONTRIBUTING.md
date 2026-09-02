# Contributing

Bug reports, ideas and pull requests are welcome.

## Reporting a bug

Open an [issue](https://github.com/eVersor-HN/EBOOK-OPTIMIZER/issues) and include:

- what you ran (the exact command, or which options in the web interface),
- what you expected and what happened instead,
- the output of `python -m ebook_optimizer.cli --list-formats`, which shows the Python, Pillow and
  Calibre situation on your machine,
- if a specific file fails: its format, roughly how large it is, and — where the licence allows —
  the file itself or a minimal archive that reproduces the problem.

For anything involving conversion, please say whether Calibre is installed and which version.

## Setting up

```bash
git clone https://github.com/eVersor-HN/EBOOK-OPTIMIZER.git
cd EBOOK-OPTIMIZER
pip install pillow
python make_testdata.py
```

Calibre is only needed if you are touching the conversion paths.

## Before opening a pull request

Run everything:

```bash
python test_edge.py
python test_calibre_stub.py
python -m ebook_optimizer.cli testdata/testbuch.epub testdata/testcomic.cbz -o out
python verify.py out/testbuch.epub out/testcomic.cbz 8
```

All four must pass. If you change image handling, add a case to `test_edge.py`; if you change the
plugin or its settings, add one to `test_calibre_stub.py`.

## What matters in this codebase

- **Never make a file bigger.** Any change to the image pipeline has to preserve the rule that a
  result larger than the input is discarded in favour of the original bytes.
- **Measure, do not assume.** Claims about compression or speed belong in the pull request with
  the numbers that produced them, on real files. Several plausible-sounding optimisations were
  rejected here precisely because they measured badly.
- **Fail clearly, never halfway.** A missing dependency, an unreadable image or an unsupported
  format should produce a readable message and leave the original untouched.
- **`core/` stays free of Calibre and Qt imports.** It must keep working as a plain Python
  package. The Calibre-specific code lives in `ui.py` and `config.py`, the conversion wrapper in
  `core/convert.py` shells out and degrades gracefully when Calibre is absent.

## Style

- PEP 8, four spaces, lines under 80 characters where it does not hurt readability.
- Comments explain *why*, not *what*. The existing comments are the model: they justify decisions
  that would otherwise look arbitrary, such as why `mimetype` must be stored first or why comics
  are optimised before Calibre sees them.
- Everything is in English: identifiers, comments, docstrings and all user-facing text.

## Licence

By contributing you agree that your work is licensed under the
[GPL-3.0](LICENSE), like the rest of the project.
