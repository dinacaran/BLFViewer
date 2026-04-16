from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from core.blf_reader import BLFReaderService
from core.dbc_decoder import DBCDecoder
from core.signal_store import SignalStore

# ── Streaming constants ────────────────────────────────────────────────────
# Emit tree update so user can see & select signals while decoding
_TREE_EMIT_INTERVAL = 2_000    # frames between signal-tree updates

# Emit partial data notification so live-plotted signals refresh
_PLOT_EMIT_INTERVAL = 5_000    # frames between plot-refresh pings

# Progress log interval
_PROGRESS_INTERVAL  = 10_000


class LoadWorker(QObject):
    progress    = Signal(str)
    finished    = Signal(object)     # SignalStore
    failed      = Signal(str)

    # ── Streaming signals ─────────────────────────────────────────────────
    # Fired during decode so the UI can respond before full completion:
    #   tree_update  → dict payload to populate the signal tree early
    #   partial_ready→ notification that plotted signals have new samples
    tree_update   = Signal(dict)
    partial_ready = Signal()

    def __init__(self, blf_path: str | Path, dbc_path: str | Path) -> None:
        super().__init__()
        self.blf_path = str(blf_path)
        self.dbc_path = str(dbc_path)

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit("Loading DBC...")
            decoder = DBCDecoder(self.dbc_path)
            for msg in decoder.load_messages:
                self.progress.emit(msg)

            self.progress.emit("Opening BLF and starting decode...")
            reader = BLFReaderService(self.blf_path)
            store  = SignalStore()
            self._live_store = store   # expose for partial plotting

            base_ts: float | None = None  # perf: normalise inline, skip end-pass

            for index, frame in enumerate(reader, start=1):
                # ── Inline timestamp normalisation ────────────────────────
                # Subtract base_ts here so data is plot-ready immediately.
                # normalize_timestamps() at the end becomes a no-op.
                if base_ts is None:
                    base_ts = frame.timestamp
                    store.base_ts = base_ts
                frame.timestamp -= base_ts

                store.note_frame(frame)
                samples = decoder.decode_frame(frame)

                if samples:
                    store.add_samples_direct(samples)   # avoids list() re-wrap
                    store.add_raw_frame(frame, samples)
                else:
                    store.unmatched_frames += 1

                # ── Streaming: early signal tree ──────────────────────────
                if index % _TREE_EMIT_INTERVAL == 0:
                    self.tree_update.emit(store.build_tree_payload())

                # ── Streaming: plot refresh ping ──────────────────────────
                if index % _PLOT_EMIT_INTERVAL == 0:
                    self.partial_ready.emit()

                # ── Progress log ──────────────────────────────────────────
                if index == 1 or index % _PROGRESS_INTERVAL == 0:
                    self.progress.emit(
                        f"Processed {index:,} frames | "
                        f"decoded: {store.decoded_frames:,} | "
                        f"signals: {len(store._series_by_key):,} | "
                        f"samples: {store.total_samples:,}"
                    )

            # ── Finalise ───────────────────────────────────────────────────
            # normalize_timestamps is now a no-op (inline above), but we keep
            # the call so the raw_frames timestamps are also corrected.
            store.normalize_timestamps(already_normalized=True)

            store.diagnostics_text = (
                store.channel_summary_text()
                + "\n\nFirst frame IDs seen in BLF:\n"
                + ("\n".join(store.first_frame_ids) if store.first_frame_ids else "(none)")
                + "\n\n"
                + decoder.diagnostics_text()
            )
            self.progress.emit(store.channel_summary_text())
            self.progress.emit(
                f"Completed | total frames: {store.total_frames:,} | "
                f"decoded frames: {store.decoded_frames:,} | "
                f"unmatched: {store.unmatched_frames:,} | "
                f"samples: {store.total_samples:,}"
            )
            self.finished.emit(store)
        except Exception as exc:
            import traceback
            self.failed.emit(f"{exc}\n\n{traceback.format_exc()}")
