"""Append-only, resumable attempt accounting for a frozen local study schedule.

This module records metadata only. It never starts an agent, Docker container,
provider call, or target. A reservation must precede a run; completion requires
an independently validated immutable JSONL/receipt pair. Pending reservations
block retries and finalization rather than silently disappearing.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from experiments.schedule import ScheduleError, validate_schedule
from experiments.validate_artifacts import validate_artifacts, validate_manifest


JOURNAL_VERSION = "0.1.0"
LEDGER_VERSION = "0.1.0"
_SAFE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_ATTEMPT_NAME = re.compile(r"attempt-([0-9]{4})\.(reserved|completed)\.json\Z")
_MISSING_REASONS = frozenset({
    "NOT_STARTED", "SAFETY_HALT", "RESOURCE_LIMIT",
    "SETUP_FAILURES_EXHAUSTED", "OTHER_DECLARED",
})
# The task handoff begins before the initial observation. Retrying after this
# boundary risks selectively discarding a start the adapter may have observed.
_VISIBLE_AGENT_EVENTS = frozenset({
    "TASK_HANDOFF_START", "INITIAL_OBSERVATION", "TOOL_CALL", "TOOL_OBSERVATION", "STOP",
})


class AttemptLedgerError(ValueError):
    """The immutable attempt history cannot support an auditable next action."""


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise AttemptLedgerError(f"cannot hash required input {path}: {exc}") from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AttemptLedgerError(f"cannot read immutable JSON record {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AttemptLedgerError(f"immutable JSON record is not an object: {path}")
    return value


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_once(path: Path, value: Mapping[str, Any]) -> None:
    """Publish a fully fsynced record without ever replacing an existing path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(dict(value), ensure_ascii=False, sort_keys=True,
                            indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(serialized)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        # A hard link is atomic and fails if the immutable destination exists.
        os.link(temporary, path)
        _sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


class AttemptLedgerWriter:
    """Create immutable slot reservations/completions and a final all-slot ledger.

    The caller must provide task rows from the frozen task definitions. This
    writer validates the schedule against them and the manifest, but it is not
    the experiment orchestrator or a substitute for the safety/readiness gate.
    """

    def __init__(
        self, *, root: Path, manifest_path: Path, schedule_path: Path,
        tasks: Sequence[Mapping[str, Any]],
    ) -> None:
        self.root = root.resolve()
        self.manifest_path = manifest_path.resolve()
        self.schedule_path = schedule_path.resolve()
        for path in (self.manifest_path, self.schedule_path):
            try:
                path.relative_to(self.root)
            except ValueError as exc:
                raise AttemptLedgerError("manifest and schedule must reside inside the study root") from exc
        integrity = validate_manifest(self.manifest_path, require_git=True)
        if not integrity["passed"]:
            raise AttemptLedgerError("invalid frozen manifest: " + "; ".join(integrity["errors"]))
        self.manifest = _read_json(self.manifest_path)
        self.schedule = _read_json(self.schedule_path)
        self.experiment_id = str(self.manifest["experiment_id"])
        if not _SAFE_RUN_ID.fullmatch(self.experiment_id):
            raise AttemptLedgerError("experiment_id must be a short filesystem-safe identifier")
        self.manifest_sha256 = _sha256(self.manifest_path)
        self.schedule_sha256 = _sha256(self.schedule_path)
        if self.manifest.get("schedule_sha256") != self.schedule_sha256:
            raise AttemptLedgerError("manifest does not freeze the exact schedule hash")
        try:
            validate_schedule(self.schedule, manifest=self.manifest, tasks=tasks)
        except ScheduleError as exc:
            raise AttemptLedgerError(f"frozen schedule validation failed: {exc}") from exc
        self.slots = {slot["slot_id"]: slot for slot in self.schedule["slots"]}
        self.journal_dir = self.root / "experiments" / "attempt_journal" / self.experiment_id
        self.ledger_path = self.root / "experiments" / "ledgers" / f"{self.experiment_id}.json"
        self.run_dir = self.root / "experiments" / "runs" / self.experiment_id
        self._meta = {
            "schema_version": JOURNAL_VERSION,
            "experiment_id": self.experiment_id,
            "manifest_sha256": self.manifest_sha256,
            "schedule_sha256": self.schedule_sha256,
        }
        self._assert_local_paths()

    def _assert_local_paths(self) -> None:
        """Reject inherited symlink parents that could redirect generated data."""

        for path in (
            self.root / "experiments", self.root / "experiments" / "attempt_journal",
            self.journal_dir, self.root / "experiments" / "ledgers",
            self.ledger_path, self.root / "experiments" / "runs", self.run_dir,
        ):
            if path.is_symlink() or not path.resolve().is_relative_to(self.root):
                raise AttemptLedgerError(f"generated artifact path is redirected or escapes the study root: {path}")

    @contextmanager
    def _guard(self) -> Iterator[None]:
        self._assert_local_paths()
        if self.ledger_path.is_symlink():
            raise AttemptLedgerError("final ledger must not be a symlink")
        if self.journal_dir.is_symlink():
            raise AttemptLedgerError("journal directory must not be a symlink")
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.journal_dir / ".writer.lock"
        if lock_path.is_symlink():
            raise AttemptLedgerError("journal lock must not be a symlink")
        with lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                if (_sha256(self.manifest_path) != self.manifest_sha256
                        or _sha256(self.schedule_path) != self.schedule_sha256):
                    raise AttemptLedgerError("manifest or schedule changed after writer initialization")
                meta_path = self.journal_dir / "meta.json"
                if meta_path.is_symlink():
                    raise AttemptLedgerError("journal identity must not be a symlink")
                if not meta_path.exists():
                    _write_once(meta_path, self._meta)
                if _read_json(meta_path) != self._meta:
                    raise AttemptLedgerError("journal identity/hash differs from frozen inputs")
                allowed = {".writer.lock", "meta.json"} | set(self.slots)
                unexpected = {path.name for path in self.journal_dir.iterdir()} - allowed
                if unexpected:
                    raise AttemptLedgerError(f"unexpected journal entries: {sorted(unexpected)}")
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _slot_dir(self, slot_id: str) -> Path:
        if slot_id not in self.slots:
            raise AttemptLedgerError(f"slot is absent from frozen schedule: {slot_id}")
        path = self.journal_dir / slot_id
        if path.is_symlink():
            raise AttemptLedgerError("slot journal directory must not be a symlink")
        return path

    def _state(self, slot_id: str) -> tuple[list[tuple[dict[str, Any], dict[str, Any] | None]], dict[str, Any] | None]:
        directory = self._slot_dir(slot_id)
        if not directory.exists():
            return [], None
        if not directory.is_dir():
            raise AttemptLedgerError(f"slot journal path is not a directory: {slot_id}")
        names = {path.name for path in directory.iterdir()}
        unexpected = {name for name in names if name != "missing.json" and not _ATTEMPT_NAME.fullmatch(name)}
        if unexpected:
            raise AttemptLedgerError(f"unexpected or interrupted journal files for {slot_id}: {sorted(unexpected)}")
        attempt_indexes = sorted({int(_ATTEMPT_NAME.fullmatch(name).group(1))
                                  for name in names if _ATTEMPT_NAME.fullmatch(name)})
        if attempt_indexes != list(range(1, len(attempt_indexes) + 1)) or len(attempt_indexes) > 3:
            raise AttemptLedgerError(f"attempt indexes are noncontiguous or exceed three for {slot_id}")
        attempts: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
        for index in attempt_indexes:
            reservation_path = directory / f"attempt-{index:04d}.reserved.json"
            completion_path = directory / f"attempt-{index:04d}.completed.json"
            if reservation_path.is_symlink() or completion_path.is_symlink():
                raise AttemptLedgerError(f"attempt records must not be symlinks in {slot_id}")
            if not reservation_path.is_file():
                raise AttemptLedgerError(f"completion exists without reservation in {slot_id}")
            reservation = _read_json(reservation_path)
            if (
                reservation.get("schema_version") != JOURNAL_VERSION
                or reservation.get("slot_id") != slot_id
                or reservation.get("attempt_index") != index
                or reservation.get("experiment_id") != self.experiment_id
                or reservation.get("task_id") != self.slots[slot_id]["task_id"]
                or reservation.get("condition") != self.slots[slot_id]["condition"]
                or reservation.get("manifest_sha256") != self.manifest_sha256
                or reservation.get("schedule_sha256") != self.schedule_sha256
                or not isinstance(reservation.get("run_id"), str)
                or not _SAFE_RUN_ID.fullmatch(reservation["run_id"])
            ):
                raise AttemptLedgerError(f"reservation identity is invalid for {slot_id} attempt {index}")
            completion = _read_json(completion_path) if completion_path.exists() else None
            if completion is not None and (
                completion.get("schema_version") != JOURNAL_VERSION
                or completion.get("slot_id") != slot_id
                or completion.get("attempt_index") != index
                or completion.get("run_id") != reservation["run_id"]
                or completion.get("classification") not in {"SETUP_FAILURE", "SELECTED"}
            ):
                raise AttemptLedgerError(f"completion identity is invalid for {slot_id} attempt {index}")
            if index < len(attempt_indexes) and (
                completion is None or completion["classification"] != "SETUP_FAILURE"
            ):
                raise AttemptLedgerError(f"only a completed setup failure may precede another attempt in {slot_id}")
            attempts.append((reservation, completion))
        missing_path = directory / "missing.json"
        if missing_path.is_symlink():
            raise AttemptLedgerError(f"missing-slot record must not be a symlink in {slot_id}")
        missing = _read_json(missing_path) if "missing.json" in names else None
        if missing is not None and (
            missing.get("schema_version") != JOURNAL_VERSION
            or missing.get("slot_id") != slot_id
            or missing.get("reason") not in _MISSING_REASONS
        ):
            raise AttemptLedgerError(f"missing-slot record is invalid for {slot_id}")
        return attempts, missing

    def _all_run_ids(self) -> set[str]:
        run_ids: set[str] = set()
        for slot_id in self.slots:
            attempts, _ = self._state(slot_id)
            for reservation, _ in attempts:
                run_id = reservation["run_id"]
                if run_id in run_ids:
                    raise AttemptLedgerError(f"run ID appears in multiple reservations: {run_id}")
                run_ids.add(run_id)
        return run_ids

    def reserve(self, *, slot_id: str, run_id: str) -> Path:
        """Durably assign a fresh run ID to a slot *before* execution starts."""

        if not isinstance(run_id, str) or not _SAFE_RUN_ID.fullmatch(run_id):
            raise AttemptLedgerError("run_id must be a short filesystem-safe identifier")
        with self._guard():
            if self.ledger_path.exists():
                raise AttemptLedgerError("finalized ledger already exists; no further attempts allowed")
            attempts, missing = self._state(slot_id)
            if missing is not None:
                raise AttemptLedgerError("slot has already been marked missing")
            if attempts and (attempts[-1][1] is None or attempts[-1][1]["classification"] != "SETUP_FAILURE"):
                raise AttemptLedgerError("previous attempt is pending or selected; retry forbidden")
            if attempts:
                previous, completion = attempts[-1]
                actual = self._validated_completion(slot_id, previous)
                self._check_completion(completion, actual, previous["run_id"])
            if len(attempts) >= 3:
                raise AttemptLedgerError("maximum three attempts per slot exceeded")
            if run_id in self._all_run_ids():
                raise AttemptLedgerError("run_id has already been reserved")
            if self.run_dir.is_symlink():
                raise AttemptLedgerError("raw run directory must not be a symlink")
            proposed_paths = (self.run_dir / f"{run_id}.jsonl",
                              self.run_dir / f"{run_id}.receipt.json")
            if any(path.exists() or path.is_symlink() for path in proposed_paths):
                raise AttemptLedgerError("raw attempt already exists; reservation must precede execution")
            slot = self.slots[slot_id]
            index = len(attempts) + 1
            record = {
                "schema_version": JOURNAL_VERSION, "experiment_id": self.experiment_id,
                "slot_id": slot_id, "attempt_index": index, "run_id": run_id,
                "task_id": slot["task_id"], "condition": slot["condition"],
                "manifest_sha256": self.manifest_sha256,
                "schedule_sha256": self.schedule_sha256,
                "reserved_at": _utc_now(),
            }
            path = self._slot_dir(slot_id) / f"attempt-{index:04d}.reserved.json"
            _write_once(path, record)
            return path

    def _validated_completion(self, slot_id: str, reservation: Mapping[str, Any]) -> dict[str, Any]:
        run_id = str(reservation["run_id"])
        log_path = self.run_dir / f"{run_id}.jsonl"
        receipt_path = self.run_dir / f"{run_id}.receipt.json"
        if self.run_dir.is_symlink() or log_path.is_symlink() or receipt_path.is_symlink():
            raise AttemptLedgerError("raw run directory and attempt artifacts must not be symlinks")
        integrity = validate_artifacts(
            manifest_path=self.manifest_path, log_path=log_path, receipt_path=receipt_path,
            require_git=True, require_action_verifier=True,
        )
        if not integrity["passed"]:
            raise AttemptLedgerError(f"raw attempt {run_id} failed integrity: {'; '.join(integrity['errors'])}")
        receipt = _read_json(receipt_path)
        slot = self.slots[slot_id]
        if (
            receipt.get("run_id") != run_id or receipt.get("task_id") != slot["task_id"]
            or receipt.get("condition") != slot["condition"]
        ):
            raise AttemptLedgerError(f"raw attempt identity disagrees with scheduled slot {slot_id}")
        try:
            event_types = [json.loads(line)["event_type"]
                           for line in log_path.read_text(encoding="utf-8").splitlines()]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise AttemptLedgerError(f"cannot classify raw attempt {run_id}: {exc}") from exc
        handoff_or_action = any(event_type in _VISIBLE_AGENT_EVENTS for event_type in event_types)
        classification = (
            "SETUP_FAILURE" if receipt.get("terminal_outcome") == "INFRASTRUCTURE_ABORT"
            and not handoff_or_action else "SELECTED"
        )
        return {
            "schema_version": JOURNAL_VERSION, "slot_id": slot_id,
            "attempt_index": reservation["attempt_index"], "run_id": run_id,
            "classification": classification,
            "terminal_outcome": receipt["terminal_outcome"],
            "log_sha256": _sha256(log_path), "receipt_sha256": _sha256(receipt_path),
            "completed_at": _utc_now(),
        }

    @staticmethod
    def _check_completion(
        recorded: Mapping[str, Any], actual: Mapping[str, Any], run_id: str
    ) -> None:
        stable_fields = (
            "schema_version", "slot_id", "attempt_index", "run_id",
            "classification", "terminal_outcome", "log_sha256", "receipt_sha256",
        )
        if any(recorded.get(key) != actual.get(key) for key in stable_fields):
            raise AttemptLedgerError(f"completed raw attempt changed after journal write: {run_id}")

    def complete(self, *, slot_id: str, run_id: str) -> Path:
        """Bind an existing immutable raw log/receipt to its reservation."""

        with self._guard():
            if self.ledger_path.exists():
                raise AttemptLedgerError("finalized ledger already exists")
            attempts, missing = self._state(slot_id)
            if missing is not None or not attempts:
                raise AttemptLedgerError("slot is missing or has no reservation")
            reservation, completion = attempts[-1]
            if reservation["run_id"] != run_id or completion is not None:
                raise AttemptLedgerError("attempt is not the current pending reservation")
            record = self._validated_completion(slot_id, reservation)
            path = self._slot_dir(slot_id) / f"attempt-{reservation['attempt_index']:04d}.completed.json"
            _write_once(path, record)
            return path

    def mark_missing(self, *, slot_id: str, reason: str) -> Path:
        """Declare a missing scheduled slot without silently imputing failure."""

        if reason not in _MISSING_REASONS:
            raise AttemptLedgerError("unrecognized missing-slot reason")
        with self._guard():
            if self.ledger_path.exists():
                raise AttemptLedgerError("finalized ledger already exists")
            attempts, missing = self._state(slot_id)
            if missing is not None or any(completion is None for _, completion in attempts):
                raise AttemptLedgerError("slot already missing or contains an unresolved reservation")
            if attempts and attempts[-1][1]["classification"] == "SELECTED":
                raise AttemptLedgerError("selected attempt cannot be marked missing")
            if (reason == "NOT_STARTED" and attempts) or (
                reason == "SETUP_FAILURES_EXHAUSTED" and len(attempts) != 3
            ) or (len(attempts) == 3 and reason != "SETUP_FAILURES_EXHAUSTED"):
                raise AttemptLedgerError("missing reason disagrees with the attempt history")
            path = self._slot_dir(slot_id) / "missing.json"
            _write_once(path, {"schema_version": JOURNAL_VERSION, "slot_id": slot_id,
                               "reason": reason, "recorded_at": _utc_now()})
            return path

    def _assemble(self) -> dict[str, Any]:
        ledger_slots: list[dict[str, Any]] = []
        listed_run_ids = self._all_run_ids()
        for slot in self.schedule["slots"]:
            slot_id = slot["slot_id"]
            attempts, missing = self._state(slot_id)
            if any(completion is None for _, completion in attempts):
                raise AttemptLedgerError(f"slot has unresolved reservation: {slot_id}")
            for reservation, completion in attempts:
                actual = self._validated_completion(slot_id, reservation)
                self._check_completion(completion, actual, reservation["run_id"])
            selected = bool(attempts and attempts[-1][1]["classification"] == "SELECTED")
            if selected and missing is not None:
                raise AttemptLedgerError(f"selected slot also marked missing: {slot_id}")
            if not selected and missing is None:
                raise AttemptLedgerError(f"slot has no selected attempt or explicit missing reason: {slot_id}")
            ledger_slots.append({
                "slot_id": slot_id,
                "status": "RECORDED" if selected else "MISSING",
                "attempts": [
                    {"run_id": reservation["run_id"], "classification": completion["classification"]}
                    for reservation, completion in attempts
                ],
                "selected_run_id": attempts[-1][0]["run_id"] if selected else None,
                "missing_reason": None if selected else missing["reason"],
            })
        if self.run_dir.exists():
            if self.run_dir.is_symlink() or not self.run_dir.is_dir():
                raise AttemptLedgerError("raw run directory must be a real directory")
            if any(path.is_symlink() for path in self.run_dir.iterdir()):
                raise AttemptLedgerError("raw run directory must not contain symlinks")
            expected_names = {f"{run_id}.{suffix}" for run_id in listed_run_ids
                              for suffix in ("jsonl", "receipt.json")}
            actual_names = {path.name for path in self.run_dir.iterdir()}
            if actual_names != expected_names:
                raise AttemptLedgerError("raw run directory contains unreserved, partial, or missing attempts")
        elif listed_run_ids:
            raise AttemptLedgerError("reserved raw run directory is absent")
        return {
            "schema_version": LEDGER_VERSION,
            "experiment_id": self.experiment_id,
            "schedule_sha256": self.schedule_sha256,
            "slots": ledger_slots,
        }

    def finalize(self) -> Path:
        """Write or verify an immutable final ledger covering every scheduled slot."""

        with self._guard():
            if self.ledger_path.is_symlink():
                raise AttemptLedgerError("final ledger must not be a symlink")
            document = self._assemble()
            if self.ledger_path.exists():
                if _read_json(self.ledger_path) != document:
                    raise AttemptLedgerError("existing finalized ledger disagrees with immutable journal/raw evidence")
                return self.ledger_path
            _write_once(self.ledger_path, document)
            return self.ledger_path
