# Contributing to BLF Viewer

Thank you for considering a contribution! This is a small open-source tool
and all contributions — bug reports, feature suggestions, and code — are welcome.

---

## Reporting Bugs

Please [open an issue](https://github.com/dinacaran/blfviewer/issues) and include:

- **OS** and **Python version** (e.g. Windows 11, Python 3.12.2)
- **Package versions**: paste the output of `pip show python-can cantools PySide6 pyqtgraph`
- **Steps to reproduce** — what did you do, what did you expect, what happened?
- **Error message or traceback** — check the Log tab in the app, or run from terminal
- **File details** (no actual BLF/DBC data needed):
  - Approximate BLF file size and duration
  - Number of channels and messages in the DBC

> ⚠️ **Never attach real BLF or DBC files to issues** — they may contain
> proprietary OEM or supplier data.

---

## Suggesting Features

Open an issue with the label `enhancement`. Describe:
- The use case (what are you trying to do?)
- The expected behaviour
- Any reference tools that already do this (e.g. CANalyzer, INCA, CANdb++)

---

## Submitting a Pull Request

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b fix/my-bug-fix
   # or
   git checkout -b feature/my-new-feature
   ```

2. **Keep changes focused** — one bug fix or one feature per PR.
   Large PRs are hard to review; split them up if possible.

3. **Do not modify the core decode pipeline** (`blf_reader.py`, `dbc_decoder.py`,
   `signal_store.py`) unless the PR is specifically about a decode bug.
   These modules are the most sensitive — changes here can silently corrupt
   signal values.

4. **Test against a real BLF + DBC** before submitting.
   We do not yet have an automated test suite, so manual validation is expected.

5. **Update `CHANGELOG.md`** under an `[Unreleased]` section.

6. Open the PR with a clear description of what changed and why.

---

## Code Style

- Python 3.11+ features are fine (`match`, `|` unions, `slots=True`, etc.)
- Follow the existing file structure: core modules have no Qt imports;
  GUI modules have no `cantools` / `python-can` imports
- Keep GUI rebuild operations surgical — prefer `_apply_curve_style()`
  over full `_rebuild_curves()` where possible (performance)

---

## Development Setup

```bash
git clone https://github.com/dinacaran/blfviewer.git
cd blf-viewer
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
python app.py
```

---

## License

By contributing, you agree that your contributions will be licensed
under the MIT License that covers this project.
