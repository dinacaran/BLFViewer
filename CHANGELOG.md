# Changelog

All notable changes to BLF Viewer are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [0.1.0] — 2026-04-10 — Initial Public Release

### Added
- Load Vector `.blf` files via `python-can`
- Decode CAN signals using `.dbc` database files via `cantools`
- Interactive multi-signal plot with zoom, pan, and cursor readout
- Cursor value table showing per-signal interpolated values at cursor position
- **Multi-axis mode** — independent Y axis per signal (overlaid, left-side axes)
- **Stacked mode** — INCA/CANdb-style layout, one lane per signal, shared X axis
- **Show Data Points** — toggle sample markers for all plotted signals simultaneously
- **Export selected signals to CSV** with timestamps
- **Raw CAN frame viewer** — inspect decoded and undecoded frames with signal breakdown
- **Save / Load configuration** — persist BLF path, DBC path, plotted signals, and colors
- Drag-and-drop signals from the tree onto the plot
- Double-click or right-click to plot signals from tree
- Move Up / Move Down reordering of plotted signals
- Per-signal color customisation via right-click menu
- Plot background color customisation
- Keyboard shortcuts: `Space`, `F`, `Delete`, `Ctrl+Up/Down`, `Ctrl+S`
- Collapsible left (signal tree) and bottom (log/diagnostics) panels
- Background decode thread — UI stays responsive during large file loads
- Raw frame display capped at 100,000 frames to prevent out-of-memory on large files
- Memory-efficient signal storage using `array.array` for timestamps and values
- Portable Windows `.exe` build via PyInstaller
- GitHub Actions workflow for automated release builds

### Known Limitations
- BLF files with CAN FD frames are partially supported (data is read; FD-specific
  bit-rate-switch fields are ignored)
- Multiplexed DBC signals are decoded as independent signals (mux value not validated)
- No support for LIN, FlexRay, or Ethernet frames in BLF files
- Raw frame viewer shows only the first 100,000 frames for memory safety

---

## Versioning Policy

- **Patch** (0.1.x) — bug fixes, no new features
- **Minor** (0.x.0) — new features, backwards-compatible
- **Major** (x.0.0) — breaking changes to config format or major architecture change
