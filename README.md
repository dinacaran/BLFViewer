![BLFviewer_Mutileaxis_plot](https://github.com/user-attachments/assets/e9f531d7-88e5-4292-8741-a5f2326ae3fd)
## BLF Viewer for window


> A portable, zero-install Windows tool for loading Vector BLF measurement files,
> decoding CAN signals with DBC databases, and plotting them interactively.


![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?logo=windows)
![License](https://img.shields.io/badge/License-MIT-green)
![Release](https://img.shields.io/github/v/release/dinacaran/blfviewer)

---

## Screenshots
Multiple Axis plot:
![BLFviewer_Mutileaxis_plot_2](https://github.com/user-attachments/assets/e3f563f3-687e-4da7-8073-71570b88b69a)

Stacked plot:
![BLFviewer_stacked_plot_2](https://github.com/user-attachments/assets/8cc5735b-272b-4c88-baaa-384028d93fbe)

Raw CAN frame:
![BLFviewer_stacked_CANRawframe2](https://github.com/user-attachments/assets/68357783-3140-48f2-841d-89e2550ec593)


---

## Features

- **Load Vector `.blf` files** — via the open-source `python-can` library
- **Decode signals using `.dbc` files** — full physical value conversion including factor, offset, and unit
- **Multi-signal plot** — zoom, pan, and interactive cursor with per-signal value readout
- **Multi-axis mode** — each signal gets its own independent Y axis (overlaid)
- **Stacked mode** — INCA/CANdb-style layout with one lane per signal, shared X axis
- **Show Data Points** — toggle sample markers for all plotted signals
- **Export to CSV** — export selected signals with timestamps
- **Raw CAN frame viewer** — inspect decoded and undecoded frames
- **Save / Load configuration** — persist your BLF path, DBC path, signals, and colors
- **Portable `.exe`** — single folder, no Python installation required on target machine

---

## Getting Started

### Run from Source

**Requirements:** Python 3.11 or later

```bash
git clone https://github.com/dinacaran/blfviewer.git
cd blf-viewer
pip install -r requirements.txt
python app.py
```

### Download Portable .exe (Windows)

Go to the [Releases](https://github.com/dinacaran/blfviewer/releases) page
and download the latest `BLFViewer_vX.X.X_Windows.zip`.  
Unzip anywhere and run `BLFViewer.exe` — no installation needed.

---

## Usage

| Step | Action |
|------|--------|
| 1 | Click **Open BLF** → select your `.blf` measurement file |
| 2 | Click **Open DBC** → select the matching `.dbc` database |
| 3 | Click **Load + Decode** → decodes all signals in the background |
| 4 | In the left panel, **double-click** a signal (or drag it) to plot it |
| 5 | Move the **cursor** over the plot to read time and value |
| 6 | Use **Multi-Axis** or **Stacked** for different layout modes |
| 7 | Click **Export Selected CSV** to save signal data |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Space` | Plot selected signal(s) from the tree |
| `F` | Fit all plots to window |
| `Delete` | Remove selected signal from plot |
| `Ctrl+Up / Down` | Reorder selected signal in the plot list |
| `Ctrl+S` | Save current configuration |

---

## Build Portable .exe

```bash
pip install pyinstaller
pyinstaller BLFViewerPortable.spec
```

Output is in `dist/BLFViewer/` — zip that folder and distribute.

The GitHub Actions workflow (`.github/workflows/build.yml`) builds and
uploads the `.exe` automatically on every tagged release.

---

## Project Structure

```
blf-viewer/
├── app.py                      # Entry point
├── core/
│   ├── blf_reader.py           # python-can BLF reader
│   ├── dbc_decoder.py          # cantools DBC decoder
│   ├── signal_store.py         # In-memory signal series store
│   ├── load_worker.py          # Background QThread worker
│   └── export.py               # CSV export
├── gui/
│   ├── main_window.py          # Main Qt window
│   ├── plot_widget.py          # Interactive plot panel
│   ├── signal_tree.py          # Left-panel signal tree
│   └── raw_frame_dialog.py     # Raw CAN frame viewer
├── requirements.txt
├── BLFViewerPortable.spec      # PyInstaller spec
└── .github/workflows/build.yml # Auto-build on release tag
```

---

## Dependencies

| Package | Version | License |
|---------|---------|---------|
| [python-can](https://github.com/hardbyte/python-can) | ≥ 4.3 | LGPL v3 |
| [cantools](https://github.com/eerimoq/cantools) | ≥ 39.0 | MIT |
| [PySide6](https://wiki.qt.io/Qt_for_Python) | ≥ 6.6 | LGPL v3 |
| [pyqtgraph](https://www.pyqtgraph.org) | ≥ 0.13 | MIT |
| [numpy](https://numpy.org) | ≥ 1.26 | BSD |

All dependencies are compatible with MIT distribution.

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

Found a bug? [Open an issue](https://github.com/dinacaran/blfviewer/issues) with:
- Your OS and Python version
- A minimal description of the BLF / DBC setup (no proprietary data needed)
- The full error message or unexpected behaviour

---

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md). This tool is for **offline analysis only**
and must not be used in any safety-critical or real-time context.

Vector Informatik GmbH is not affiliated with this project.

---

## License

MIT — see [LICENSE](LICENSE).
#   B L F V i e w e r 
 
 
