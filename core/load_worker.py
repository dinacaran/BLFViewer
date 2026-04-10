from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from core.blf_reader import BLFReaderService
from core.dbc_decoder import DBCDecoder
from core.signal_store import SignalStore


class LoadWorker(QObject):
    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

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
            store = SignalStore()

            for index, frame in enumerate(reader, start=1):
                store.note_frame(frame, decoded=False)
                samples = decoder.decode_frame(frame)
                store.add_samples(samples)
                store.add_raw_frame(frame, samples)
                if index == 1 or index % 10_000 == 0:
                    self.progress.emit(
                        f"Processed {index:,} frames | channels found: {len(store.channels):,} | decoded frames: {store.decoded_frames:,} | samples: {store.total_samples:,}"
                    )

            store.normalize_timestamps()
            store.diagnostics_text = (
                store.channel_summary_text()
                + "\n\nFirst frame IDs seen in BLF:\n"
                + ("\n".join(store.first_frame_ids) if store.first_frame_ids else "(none)")
                + "\n\n"
                + decoder.diagnostics_text()
            )
            self.progress.emit(store.channel_summary_text())
            self.progress.emit(
                f"Completed | total frames: {store.total_frames:,} | decoded frames: {store.decoded_frames:,} | unmatched frames: {store.unmatched_frames:,} | samples: {store.total_samples:,}"
            )
            self.finished.emit(store)
        except Exception as exc:
            self.failed.emit(str(exc))
