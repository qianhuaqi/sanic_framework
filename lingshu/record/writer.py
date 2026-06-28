"""Safe append-only local Runtime Record writer and minimal recovery."""

from __future__ import annotations

import asyncio
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from lingshu.core.errors import FatalScope, RecordError, StorageError
from lingshu.core.time import MonotonicClock, SystemMonotonicClock
from lingshu.record.model import DurabilityMode, WatermarkState
from lingshu.record.queue import BoundedRecordQueue
from lingshu.runtime import Deadline

_REQUIRED_EVENT_FIELDS = frozenset(
    {
        "schema_version",
        "record_id",
        "request_id",
        "worker_id",
        "revision_id",
        "event_type",
        "event_sequence",
        "wall_time",
        "monotonic_ns",
        "component",
        "severity",
        "outcome",
        "attributes",
        "truncated",
    }
)


@dataclass(frozen=True, slots=True)
class StorageWatermarks:
    """Monotonic byte thresholds for storage pressure."""

    soft_bytes: int
    hard_bytes: int
    critical_bytes: int

    def __post_init__(self) -> None:
        if not 0 < self.soft_bytes < self.hard_bytes < self.critical_bytes:
            raise ValueError("watermarks must be positive and strictly increasing")

    def state_for(self, used_bytes: int) -> WatermarkState:
        if used_bytes < 0:
            raise ValueError("used_bytes must be non-negative")
        if used_bytes >= self.critical_bytes:
            return WatermarkState.CRITICAL
        if used_bytes >= self.hard_bytes:
            return WatermarkState.HARD
        if used_bytes >= self.soft_bytes:
            return WatermarkState.SOFT
        return WatermarkState.NORMAL


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """Bounded startup recovery outcome."""

    recovered_events: int
    truncated_files: tuple[str, ...]
    quarantined_files: tuple[str, ...]


class LocalRecordWriter:
    """One-process owner of rotated append-only UTF-8 JSON Lines segments."""

    def __init__(
        self,
        root: Path,
        *,
        durability: DurabilityMode = DurabilityMode.FLUSH,
        segment_max_bytes: int = 1_048_576,
        watermarks: StorageWatermarks | None = None,
        clock: MonotonicClock | None = None,
    ) -> None:
        if segment_max_bytes <= 0:
            raise ValueError("segment_max_bytes must be positive")
        self.root = root
        self.durability = durability
        self.segment_max_bytes = segment_max_bytes
        self.watermarks = watermarks
        self.clock = clock or SystemMonotonicClock()
        self.watermark = WatermarkState.NORMAL
        self._root_resolved: Path | None = None
        self._active_dir: Path | None = None
        self._closed_dir: Path | None = None
        self._quarantine_dir: Path | None = None
        self._active_path: Path | None = None
        self._active_bytes = 0
        self._segment_index = 1
        self._closed_segments: list[str] = []
        self._lock_fd: int | None = None
        self._started = False

    @property
    def started(self) -> bool:
        return self._started

    @property
    def active_segment(self) -> Path | None:
        return self._active_path

    def start(self, *, recover: bool = True) -> RecoveryReport:
        """Acquire ownership, validate directories, and recover active tails."""

        if self._started:
            raise _storage_error(
                "record.writer_already_started",
                "Record writer is already started.",
            )
        self._prepare_root()
        self._acquire_lock()
        self._started = True
        try:
            report = self.recover() if recover else RecoveryReport(0, (), ())
            self._write_manifest()
            return report
        except BaseException:
            self.close()
            raise

    def update_watermark(self, used_bytes: int) -> WatermarkState:
        """Update visible pressure from a trusted filesystem measurement."""

        self.watermark = (
            WatermarkState.NORMAL
            if self.watermarks is None
            else self.watermarks.state_for(used_bytes)
        )
        if self._started:
            self._write_manifest()
        return self.watermark

    def write(self, payload: bytes) -> None:
        """Append one complete event line and rotate at the configured bound."""

        self._ensure_started()
        _validate_payload(payload)
        if self.watermark is WatermarkState.CRITICAL:
            raise _storage_error(
                "record.critical_watermark",
                "Record storage is at the critical watermark.",
            )
        if self._active_path is None:
            self._open_segment()
        assert self._active_path is not None
        _reject_symlink(self._active_path)
        with self._active_path.open("ab", buffering=0) as file:
            file.write(payload)
            if self.durability in {DurabilityMode.FLUSH, DurabilityMode.FSYNC}:
                file.flush()
            if self.durability is DurabilityMode.FSYNC:
                os.fsync(file.fileno())
        self._active_bytes += len(payload)
        if self._active_bytes >= self.segment_max_bytes:
            self.rotate()

    def rotate(self) -> Path | None:
        """Atomically move the active segment to the closed retention set."""

        self._ensure_started()
        if self._active_path is None:
            return None
        assert self._closed_dir is not None
        source = self._active_path
        target = self._safe_path(
            self._closed_dir,
            source.name.replace(".open.jsonl", ".jsonl"),
        )
        os.replace(source, target)
        self._closed_segments.append(target.name)
        self._active_path = None
        self._active_bytes = 0
        self._write_manifest()
        return target

    async def flush_queue(
        self,
        queue: BoundedRecordQueue,
        *,
        deadline: Deadline,
    ) -> int:
        """Drain queued events within an absolute Deadline."""

        written = 0
        while len(queue):
            if deadline.expired(self.clock):
                raise _record_error(
                    "record.flush_timeout",
                    "Runtime Record flush deadline was exceeded.",
                )
            payload = queue.pop()
            if payload is None:
                break
            try:
                self.write(payload)
            except Exception:
                queue.restore_front(payload)
                raise
            written += 1
            await asyncio.sleep(0)
        return written

    async def shutdown(
        self,
        queue: BoundedRecordQueue,
        *,
        deadline: Deadline,
    ) -> int:
        """Boundedly flush, rotate, and release writer ownership."""

        try:
            written = await self.flush_queue(queue, deadline=deadline)
            if deadline.expired(self.clock):
                raise _record_error(
                    "record.flush_timeout",
                    "Runtime Record shutdown deadline was exceeded.",
                )
            self.rotate()
            return written
        finally:
            self.close()

    def recover(self) -> RecoveryReport:
        """Truncate incomplete tails and quarantine invalid active segments."""

        self._ensure_started()
        assert self._active_dir is not None
        assert self._closed_dir is not None
        assert self._quarantine_dir is not None
        recovered = 0
        truncated: list[str] = []
        quarantined: list[str] = []
        for path in sorted(self._active_dir.glob("*.open.jsonl")):
            _reject_symlink(path)
            data = path.read_bytes()
            last_newline = data.rfind(b"\n")
            complete = data[: last_newline + 1] if last_newline >= 0 else b""
            if complete != data:
                path.write_bytes(complete)
                truncated.append(path.name)
            try:
                count = _validate_json_lines(complete)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                target = self._safe_path(self._quarantine_dir, f"{path.name}.bad")
                os.replace(path, target)
                quarantined.append(target.name)
                continue
            if not complete:
                path.unlink(missing_ok=True)
                continue
            target = self._safe_path(
                self._closed_dir,
                path.name.replace(".open.jsonl", ".recovered.jsonl"),
            )
            os.replace(path, target)
            self._closed_segments.append(target.name)
            recovered += count
        self._write_manifest()
        return RecoveryReport(recovered, tuple(truncated), tuple(quarantined))

    def retention_candidates(self) -> tuple[Path, ...]:
        """Return closed segments only; active segments are never candidates."""

        self._ensure_started()
        assert self._closed_dir is not None
        return tuple(
            self._safe_path(self._closed_dir, name) for name in self._closed_segments
        )

    def close(self) -> None:
        """Idempotently release the writer lock without deleting active data."""

        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None
            (self.root / ".writer.lock").unlink(missing_ok=True)
        self._started = False

    def _prepare_root(self) -> None:
        if self.root.exists() and self.root.is_symlink():
            raise _storage_error(
                "record.unsafe_path",
                "Record storage root cannot be a symbolic link.",
            )
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._root_resolved = self.root.resolve(strict=True)
        self._active_dir = self._prepare_directory("active")
        self._closed_dir = self._prepare_directory("closed")
        self._quarantine_dir = self._prepare_directory("quarantine")
        self._closed_segments = []
        for path in sorted(self._closed_dir.glob("*.jsonl")):
            _reject_symlink(path)
            if not path.is_file():
                raise _storage_error(
                    "record.unsafe_path",
                    "Record storage contains an invalid closed segment.",
                )
            self._closed_segments.append(path.name)
        try:
            os.chmod(self.root, stat.S_IRWXU)
        except OSError:
            pass

    def _prepare_directory(self, name: str) -> Path:
        path = self.root / name
        if path.exists() and path.is_symlink():
            raise _storage_error(
                "record.unsafe_path",
                "Record storage directories cannot be symbolic links.",
            )
        path.mkdir(exist_ok=True, mode=0o700)
        return self._safe_path(self.root, name)

    def _acquire_lock(self) -> None:
        lock_path = self._safe_path(self.root, ".writer.lock")
        try:
            self._lock_fd = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as exc:
            raise _storage_error(
                "record.writer_locked",
                "Record storage is already owned by another writer.",
                cause=exc,
            ) from exc

    def _open_segment(self) -> None:
        assert self._active_dir is not None
        assert self._closed_dir is not None
        while True:
            name = f"segment-{self._segment_index:08d}.open.jsonl"
            self._segment_index += 1
            path = self._safe_path(self._active_dir, name)
            closed = self._closed_dir / name.replace(".open.jsonl", ".jsonl")
            if not path.exists() and not closed.exists():
                break
        path.touch(mode=0o600, exist_ok=False)
        self._active_path = path
        self._active_bytes = 0
        self._write_manifest()

    def _write_manifest(self) -> None:
        if self._root_resolved is None:
            return
        payload = json.dumps(
            {
                "schema_version": 1,
                "active": self._active_path.name if self._active_path else None,
                "closed": list(self._closed_segments),
                "durability": self.durability.value,
                "watermark": self.watermark.value,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        temporary = self._safe_path(self.root, ".manifest.tmp")
        target = self._safe_path(self.root, "manifest.json")
        with temporary.open("wb") as file:
            file.write(payload)
            file.flush()
            if self.durability is DurabilityMode.FSYNC:
                os.fsync(file.fileno())
        os.replace(temporary, target)

    def _safe_path(self, parent: Path, name: str) -> Path:
        if not name or Path(name).name != name or name in {".", ".."}:
            raise _storage_error("record.unsafe_path", "Record storage path is unsafe.")
        assert self._root_resolved is not None
        candidate = parent / name
        resolved_parent = candidate.parent.resolve(strict=True)
        if (
            resolved_parent != self._root_resolved
            and self._root_resolved not in resolved_parent.parents
        ):
            raise _storage_error(
                "record.unsafe_path",
                "Record storage path escapes its root.",
            )
        if candidate.exists() and candidate.is_symlink():
            raise _storage_error(
                "record.unsafe_path",
                "Record storage files cannot be symbolic links.",
            )
        return candidate

    def _ensure_started(self) -> None:
        if not self._started:
            raise _storage_error(
                "record.writer_not_started",
                "Record writer is not started.",
            )


def _validate_payload(payload: bytes) -> None:
    if not payload or not payload.endswith(b"\n") or payload.count(b"\n") != 1:
        raise ValueError("writer payload must be one complete JSON line")


def _validate_json_lines(data: bytes) -> int:
    count = 0
    for line in data.splitlines():
        document = json.loads(line.decode("utf-8"))
        if not isinstance(document, dict) or not _REQUIRED_EVENT_FIELDS.issubset(document):
            raise ValueError("invalid Runtime Record envelope")
        count += 1
    return count


def _reject_symlink(path: Path) -> None:
    if path.is_symlink():
        raise _storage_error(
            "record.unsafe_path",
            "Record storage cannot traverse symbolic links.",
        )


def _record_error(code: str, message: str) -> RecordError:
    return RecordError(code, message, fatal_scope=FatalScope.WORKER, retryable=True)


def _storage_error(
    code: str,
    message: str,
    *,
    cause: Exception | None = None,
) -> StorageError:
    return StorageError(
        code,
        message,
        fatal_scope=FatalScope.WORKER,
        retryable=False,
        cause=cause,
    )


__all__ = ("LocalRecordWriter", "RecoveryReport", "StorageWatermarks")
