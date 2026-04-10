from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import inspect

import cantools
from cantools.database.errors import DecodeError

from core.blf_reader import RawFrame


@dataclass(slots=True)
class DecodedSignalSample:
    timestamp: float
    channel: int | None
    message_id: int
    message_name: str
    signal_name: str
    value: float | int | str
    unit: str
    is_extended_id: bool
    direction: str


class DBCLoadError(RuntimeError):
    pass


class DBCDecoder:
    def __init__(self, dbc_path: str | Path) -> None:
        self.dbc_path = Path(dbc_path)
        self.database, self.load_messages = self._load_database(self.dbc_path)
        self._decode_signature = None
        self._messages_exact: dict[int, list[Any]] = {}
        self._messages_pgn: dict[int, list[Any]] = {}
        self._dbc_message_ids_preview: list[str] = []
        self.stats = {
            "candidate_exact": 0,
            "candidate_masked": 0,
            "candidate_pgn": 0,
            "decode_success": 0,
            "decode_fail": 0,
        }
        self._build_indexes()

    @staticmethod
    def _load_database(path: Path):
        if not path.exists():
            raise DBCLoadError(f"DBC file not found: {path}")

        load_messages: list[str] = []
        try:
            database = cantools.database.load_file(str(path), strict=True)
            load_messages.append("DBC loaded in strict mode.")
            return database, load_messages
        except Exception as strict_exc:  # pragma: no cover
            load_messages.append(
                "WARNING: Strict DBC validation failed. Retrying with compatibility mode (strict=False)."
            )
            load_messages.append(f"Strict mode details: {strict_exc}")
            try:
                database = cantools.database.load_file(str(path), strict=False)
                load_messages.append(
                    "DBC loaded in compatibility mode. Some malformed signals may decode differently than in Vector tools."
                )
                return database, load_messages
            except Exception as exc:  # pragma: no cover
                raise DBCLoadError(f"Failed to load DBC file '{path}': {exc}") from exc

    def _build_indexes(self) -> None:
        self.load_messages.append(f"DBC messages available: {len(self.database.messages):,}")
        for message in self.database.messages:
            frame_id = int(getattr(message, "frame_id", -1))
            frame_id_text = f"0x{frame_id:08X}" if frame_id > 0x7FF else f"0x{frame_id:03X}"
            if len(self._dbc_message_ids_preview) < 20:
                self._dbc_message_ids_preview.append(f"{message.name} | {frame_id_text} | len={getattr(message, 'length', '?')}")
            self._messages_exact.setdefault(frame_id, []).append(message)
            if frame_id >= 0:
                self._messages_exact.setdefault(frame_id & 0x1FFFFFFF, []).append(message)
                self._messages_exact.setdefault(frame_id & 0x7FF, []).append(message)
            is_extended = bool(getattr(message, "is_extended_frame", False)) or frame_id > 0x7FF
            if is_extended:
                pgn = self._extract_j1939_pgn(frame_id)
                if pgn is not None:
                    self._messages_pgn.setdefault(pgn, []).append(message)

    def _decode_kwargs(self) -> dict[str, Any]:
        if self._decode_signature is None:
            self._decode_signature = inspect.signature(self.database.messages[0].decode) if self.database.messages else None
        kwargs: dict[str, Any] = {"decode_choices": True, "scaling": True}
        if self._decode_signature is not None:
            params = self._decode_signature.parameters
            if "allow_truncated" in params:
                kwargs["allow_truncated"] = True
            if "allow_excess" in params:
                kwargs["allow_excess"] = True
            if "decode_containers" in params:
                kwargs["decode_containers"] = False
        return kwargs

    @staticmethod
    def _extract_j1939_pgn(frame_id: int) -> int | None:
        can_id = frame_id & 0x1FFFFFFF
        if can_id <= 0x7FF:
            return None
        pf = (can_id >> 16) & 0xFF
        ps = (can_id >> 8) & 0xFF
        if pf < 240:
            return pf << 8
        return (pf << 8) | ps

    def identify_message_candidates(self, frame: RawFrame) -> list[Any]:
        candidates: list[Any] = []
        seen: set[tuple[str, int]] = set()

        def add(message: Any, bucket: str) -> None:
            key = (getattr(message, "name", ""), int(getattr(message, "frame_id", -1)))
            if key not in seen:
                seen.add(key)
                candidates.append(message)
                self.stats[bucket] += 1

        try:
            message = self.database.get_message_by_frame_id(frame.arbitration_id)
            add(message, "candidate_exact")
        except Exception:
            pass

        for lookup_id in (frame.arbitration_id, frame.arbitration_id & 0x1FFFFFFF, frame.arbitration_id & 0x7FF):
            bucket = "candidate_exact" if lookup_id == frame.arbitration_id else "candidate_masked"
            for message in self._messages_exact.get(lookup_id, []):
                add(message, bucket)

        if frame.is_extended_id or frame.arbitration_id > 0x7FF:
            pgn = self._extract_j1939_pgn(frame.arbitration_id)
            if pgn is not None:
                for message in self._messages_pgn.get(pgn, []):
                    add(message, "candidate_pgn")

        return candidates

    def decode_frame(self, frame: RawFrame) -> list[DecodedSignalSample]:
        for message in self.identify_message_candidates(frame):
            payload = frame.data
            expected_len = int(getattr(message, "length", len(payload)) or len(payload))
            if expected_len > 0 and len(payload) > expected_len:
                payload = payload[:expected_len]

            try:
                decoded = message.decode(payload, **self._decode_kwargs())
            except TypeError:
                try:
                    decoded = message.decode(payload, decode_choices=True, scaling=True)
                except Exception:
                    self.stats["decode_fail"] += 1
                    continue
            except DecodeError:
                self.stats["decode_fail"] += 1
                continue
            except Exception:
                self.stats["decode_fail"] += 1
                continue

            if not isinstance(decoded, dict) or not decoded:
                self.stats["decode_fail"] += 1
                continue

            samples: list[DecodedSignalSample] = []
            for signal in getattr(message, "signals", []):
                if signal.name not in decoded:
                    continue
                value = decoded[signal.name]
                samples.append(
                    DecodedSignalSample(
                        timestamp=frame.timestamp,
                        channel=frame.channel,
                        message_id=frame.arbitration_id,
                        message_name=message.name,
                        signal_name=signal.name,
                        value=value,
                        unit=signal.unit or "",
                        is_extended_id=frame.is_extended_id,
                        direction=frame.direction,
                    )
                )
            if samples:
                self.stats["decode_success"] += 1
                return samples
            self.stats["decode_fail"] += 1
        return []

    def diagnostics_text(self) -> str:
        lines = [
            f"DBC file: {self.dbc_path}",
            f"DBC messages: {len(self.database.messages):,}",
            "",
            "First DBC message IDs:",
        ]
        lines.extend(self._dbc_message_ids_preview or ["(none)"])
        lines.extend([
            "",
            "Decoder match counters:",
            f"Exact candidates: {self.stats['candidate_exact']:,}",
            f"Masked candidates: {self.stats['candidate_masked']:,}",
            f"PGN candidates: {self.stats['candidate_pgn']:,}",
            f"Decode success count: {self.stats['decode_success']:,}",
            f"Decode fail count: {self.stats['decode_fail']:,}",
        ])
        return "\n".join(lines)
