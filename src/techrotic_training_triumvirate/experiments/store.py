"""SQLite WAL persistence for restart-safe deterministic experiment control."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from techrotic_training_triumvirate.schemas import (
    JsonObject,
    JsonValue,
    canonical_json,
    content_hash,
)

from .engine import advance
from .model import (
    EvidenceClass,
    ExperimentContractError,
    ExperimentPlan,
    ExperimentState,
    VerifiedEvent,
)


class ExperimentStoreError(ValueError):
    """Transactional state, budget, lease, or artifact evidence is inconsistent."""


class ExperimentStore:
    """Single-file durable controller state with full-event replay verification."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA synchronous=FULL")
        mode = self._connection.execute("PRAGMA journal_mode=WAL").fetchone()
        if mode is None or str(mode[0]).lower() != "wal":
            raise ExperimentStoreError("experiment database must use SQLite WAL")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                plan_json TEXT NOT NULL,
                state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                experiment_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                event_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                parent_hash TEXT,
                event_hash TEXT NOT NULL,
                PRIMARY KEY (experiment_id, sequence),
                UNIQUE (experiment_id, event_id),
                UNIQUE (experiment_id, event_hash),
                FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
            );
            CREATE TABLE IF NOT EXISTS budget_reservations (
                experiment_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                reserved_hours REAL NOT NULL,
                charged_hours REAL,
                status TEXT NOT NULL,
                PRIMARY KEY (experiment_id, attempt_id),
                FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
            );
            CREATE TABLE IF NOT EXISTS device_leases (
                gpu_uuid TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                FOREIGN KEY (experiment_id, attempt_id)
                    REFERENCES budget_reservations(experiment_id, attempt_id)
            );
            CREATE TABLE IF NOT EXISTS workers (
                experiment_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                identity_json TEXT NOT NULL,
                cancel_path TEXT NOT NULL,
                status TEXT NOT NULL,
                PRIMARY KEY (experiment_id, attempt_id),
                FOREIGN KEY (experiment_id, attempt_id)
                    REFERENCES budget_reservations(experiment_id, attempt_id)
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                experiment_id TEXT NOT NULL,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                evidence_class TEXT NOT NULL,
                admission_eligible INTEGER NOT NULL,
                PRIMARY KEY (experiment_id, name),
                FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
            );
            """
        )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> ExperimentStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self._connection.execute("ROLLBACK")
            raise
        else:
            self._connection.execute("COMMIT")

    def create_plan(self, plan: ExperimentPlan) -> str:
        encoded = canonical_json(plan.to_object())
        with self._transaction():
            existing = self._connection.execute(
                "SELECT plan_json FROM experiments WHERE experiment_id=?",
                (plan.experiment_id,),
            ).fetchone()
            if existing is not None:
                if existing["plan_json"] != encoded:
                    raise ExperimentStoreError(
                        "experiment ID collides with another plan"
                    )
                return plan.experiment_id
            self._connection.execute(
                """
                INSERT INTO experiments(experiment_id,plan_json,state)
                VALUES(?,?,?)
                """,
                (plan.experiment_id, encoded, ExperimentState.PLANNED.value),
            )
        return plan.experiment_id

    def plan(self, experiment_id: str) -> ExperimentPlan:
        row = self._connection.execute(
            "SELECT plan_json FROM experiments WHERE experiment_id=?", (experiment_id,)
        ).fetchone()
        if row is None:
            raise ExperimentStoreError("unknown experiment")
        return ExperimentPlan.from_object(json.loads(cast(str, row["plan_json"])))

    def state(self, experiment_id: str) -> ExperimentState:
        row = self._connection.execute(
            "SELECT state FROM experiments WHERE experiment_id=?", (experiment_id,)
        ).fetchone()
        if row is None:
            raise ExperimentStoreError("unknown experiment")
        try:
            return ExperimentState(cast(str, row["state"]))
        except ValueError as exc:
            raise ExperimentStoreError("stored experiment state is invalid") from exc

    @staticmethod
    def _event_hash(
        *,
        experiment_id: str,
        sequence: int,
        parent_hash: str | None,
        event: VerifiedEvent,
    ) -> str:
        return content_hash(
            {
                "experiment_id": experiment_id,
                "sequence": sequence,
                "parent_hash": parent_hash,
                "event": event.to_object(),
            }
        )

    def _assert_launch_unfenced(self, experiment_id: str) -> None:
        if self.state(experiment_id) in {
            ExperimentState.PAUSING,
            ExperimentState.PAUSED,
        }:
            raise ExperimentStoreError("pause fence prevents new worker resources")

    def _assert_pause_quiescent(self, experiment_id: str) -> None:
        """Refuse PAUSED until training is verified and all owned work is settled."""

        trained = self._connection.execute(
            "SELECT 1 FROM events WHERE experiment_id=? AND kind=? LIMIT 1",
            (experiment_id, EventKind.TRAINING_VERIFIED.value),
        ).fetchone()
        if trained is None:
            raise ExperimentStoreError("pause needs a verified TRAINED boundary")
        leased = self._connection.execute(
            "SELECT 1 FROM device_leases WHERE experiment_id=? LIMIT 1",
            (experiment_id,),
        ).fetchone()
        if leased is not None:
            raise ExperimentStoreError("pause cannot confirm with an active GPU lease")
        unsettled = self._connection.execute(
            """
            SELECT 1 FROM budget_reservations
            WHERE experiment_id=? AND charged_hours IS NULL LIMIT 1
            """,
            (experiment_id,),
        ).fetchone()
        if unsettled is not None:
            raise ExperimentStoreError("pause requires reconciled budget reservations")
        running = self._connection.execute(
            """
            SELECT 1 FROM workers
            WHERE experiment_id=? AND status!='stopped' LIMIT 1
            """,
            (experiment_id,),
        ).fetchone()
        if running is not None:
            raise ExperimentStoreError("pause requires verified worker-host completion")

    def append_event(self, experiment_id: str, event: VerifiedEvent) -> ExperimentState:
        fingerprint = content_hash(event.to_object())
        with self._transaction():
            existing = self._connection.execute(
                "SELECT fingerprint FROM events WHERE experiment_id=? AND event_id=?",
                (experiment_id, event.event_id),
            ).fetchone()
            if existing is not None:
                if existing["fingerprint"] != fingerprint:
                    raise ExperimentStoreError(
                        "repeated event ID has different verified contents"
                    )
                return self.state(experiment_id)

            state = self.state(experiment_id)
            transition = advance(state, event)
            if event.kind is EventKind.PAUSE_CONFIRMED:
                self._assert_pause_quiescent(experiment_id)
            previous = self._connection.execute(
                """
                SELECT sequence,event_hash FROM events
                WHERE experiment_id=? ORDER BY sequence DESC LIMIT 1
                """,
                (experiment_id,),
            ).fetchone()
            sequence = 1 if previous is None else int(previous["sequence"]) + 1
            parent_hash = (
                None if previous is None else cast(str, previous["event_hash"])
            )
            event_hash = self._event_hash(
                experiment_id=experiment_id,
                sequence=sequence,
                parent_hash=parent_hash,
                event=event,
            )
            self._connection.execute(
                """
                INSERT INTO events(
                    experiment_id,sequence,event_id,kind,timestamp,payload_json,
                    fingerprint,parent_hash,event_hash
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    experiment_id,
                    sequence,
                    event.event_id,
                    event.kind.value,
                    event.timestamp,
                    canonical_json(event.payload),
                    fingerprint,
                    parent_hash,
                    event_hash,
                ),
            )
            self._connection.execute(
                "UPDATE experiments SET state=? WHERE experiment_id=?",
                (transition.state.value, experiment_id),
            )
            return transition.state

    def replay(self, experiment_id: str) -> tuple[ExperimentState, tuple[str, ...]]:
        rows = self._connection.execute(
            "SELECT * FROM events WHERE experiment_id=? ORDER BY sequence",
            (experiment_id,),
        ).fetchall()
        state = ExperimentState.PLANNED
        previous_hash: str | None = None
        hashes: list[str] = []
        for expected_sequence, row in enumerate(rows, start=1):
            if int(row["sequence"]) != expected_sequence:
                raise ExperimentStoreError("event sequence is not contiguous")
            parent = cast(str | None, row["parent_hash"])
            if parent != previous_hash:
                raise ExperimentStoreError("event parent hash chain is broken")
            payload: object = json.loads(cast(str, row["payload_json"]))
            if not isinstance(payload, dict):
                raise ExperimentStoreError("stored event payload is not an object")
            event = VerifiedEvent.from_object(
                {
                    "event_id": cast(str, row["event_id"]),
                    "kind": cast(str, row["kind"]),
                    "timestamp": cast(str, row["timestamp"]),
                    "payload": payload,
                }
            )
            if content_hash(event.to_object()) != row["fingerprint"]:
                raise ExperimentStoreError("stored event fingerprint differs")
            expected_hash = self._event_hash(
                experiment_id=experiment_id,
                sequence=expected_sequence,
                parent_hash=previous_hash,
                event=event,
            )
            if expected_hash != row["event_hash"]:
                raise ExperimentStoreError("stored event hash differs")
            state = advance(state, event).state
            previous_hash = expected_hash
            hashes.append(expected_hash)
        if self.state(experiment_id) is not state:
            raise ExperimentStoreError("materialized state differs from event replay")
        return state, tuple(hashes)

    def reserve_budget(
        self, experiment_id: str, attempt_id: str, hours: float
    ) -> JsonObject:
        if not math.isfinite(hours) or hours <= 0:
            raise ExperimentStoreError("budget reservation must be finite and positive")
        plan = self.plan(experiment_id)
        with self._transaction():
            existing = self._connection.execute(
                """
                SELECT reserved_hours,charged_hours,status FROM budget_reservations
                WHERE experiment_id=? AND attempt_id=?
                """,
                (experiment_id, attempt_id),
            ).fetchone()
            if existing is not None:
                if not math.isclose(float(existing["reserved_hours"]), hours):
                    raise ExperimentStoreError(
                        "attempt budget was already reserved with another cap"
                    )
                return self.budget_snapshot(experiment_id)

            self._assert_launch_unfenced(experiment_id)
            used = self._connection.execute(
                """
                SELECT COALESCE(SUM(
                    CASE
                        WHEN charged_hours IS NULL THEN reserved_hours
                        ELSE charged_hours
                    END
                ),0.0)
                FROM budget_reservations WHERE experiment_id=?
                """,
                (experiment_id,),
            ).fetchone()
            committed = float(used[0]) if used is not None else 0.0
            if committed + hours > plan.gpu_hours + 1e-12:
                raise ExperimentStoreError("experiment GPU budget is exhausted")
            self._connection.execute(
                """
                INSERT INTO budget_reservations(
                    experiment_id,attempt_id,reserved_hours,charged_hours,status
                ) VALUES(?,?,?,NULL,'reserved')
                """,
                (experiment_id, attempt_id, hours),
            )
            return self.budget_snapshot(experiment_id)

    def reconcile_budget(
        self,
        experiment_id: str,
        attempt_id: str,
        *,
        actual_hours: float | None,
        lifetime_established: bool,
    ) -> JsonObject:
        with self._transaction():
            row = self._connection.execute(
                """
                SELECT reserved_hours,charged_hours,status FROM budget_reservations
                WHERE experiment_id=? AND attempt_id=?
                """,
                (experiment_id, attempt_id),
            ).fetchone()
            if row is None:
                raise ExperimentStoreError("cannot reconcile an unknown reservation")
            reserved = float(row["reserved_hours"])
            charged = row["charged_hours"]
            if charged is not None:
                expected = reserved if not lifetime_established else actual_hours
                if expected is None or not math.isclose(
                    float(charged), float(expected)
                ):
                    raise ExperimentStoreError("attempt budget was already reconciled")
                return self.budget_snapshot(experiment_id)

            if lifetime_established:
                if (
                    actual_hours is None
                    or not math.isfinite(actual_hours)
                    or actual_hours < 0
                    or actual_hours > reserved
                ):
                    raise ExperimentStoreError(
                        "established runtime must lie within its reservation"
                    )
                final_charge = actual_hours
                status = "charged"
            else:
                final_charge = reserved
                status = "conservative"
            self._connection.execute(
                """
                UPDATE budget_reservations
                SET charged_hours=?,status=?
                WHERE experiment_id=? AND attempt_id=?
                """,
                (final_charge, status, experiment_id, attempt_id),
            )
            return self.budget_snapshot(experiment_id)

    def budget_snapshot(self, experiment_id: str) -> JsonObject:
        plan = self.plan(experiment_id)
        rows = self._connection.execute(
            """
            SELECT attempt_id,reserved_hours,charged_hours,status
            FROM budget_reservations WHERE experiment_id=? ORDER BY attempt_id
            """,
            (experiment_id,),
        ).fetchall()
        attempts: list[JsonObject] = []
        committed = 0.0
        for row in rows:
            reserved = float(row["reserved_hours"])
            charged_raw = row["charged_hours"]
            charged = None if charged_raw is None else float(charged_raw)
            committed += reserved if charged is None else charged
            attempts.append(
                {
                    "attempt_id": cast(str, row["attempt_id"]),
                    "reserved_hours": reserved,
                    "charged_hours": charged,
                    "status": cast(str, row["status"]),
                }
            )
        return {
            "authorized_gpu_hours": plan.gpu_hours,
            "committed_gpu_hours": committed,
            "remaining_gpu_hours": max(0.0, plan.gpu_hours - committed),
            "attempts": cast(list[JsonValue], attempts),
        }

    def acquire_device_lease(
        self, experiment_id: str, attempt_id: str, *, acquired_at: str
    ) -> None:
        plan = self.plan(experiment_id)
        with self._transaction():
            self._assert_launch_unfenced(experiment_id)
            reservation = self._connection.execute(
                """
                SELECT 1 FROM budget_reservations
                WHERE experiment_id=? AND attempt_id=?
                """,
                (experiment_id, attempt_id),
            ).fetchone()
            if reservation is None:
                raise ExperimentStoreError("device lease requires a budget reservation")
            try:
                self._connection.execute(
                    """
                    INSERT INTO device_leases(
                        gpu_uuid,experiment_id,attempt_id,acquired_at
                    )
                    VALUES(?,?,?,?)
                    """,
                    (plan.gpu_uuid, experiment_id, attempt_id, acquired_at),
                )
            except sqlite3.IntegrityError as exc:
                raise ExperimentStoreError(
                    "physical GPU already has an active lease"
                ) from exc

    def release_device_lease(self, experiment_id: str, attempt_id: str) -> None:
        plan = self.plan(experiment_id)
        with self._transaction():
            row = self._connection.execute(
                "SELECT experiment_id,attempt_id FROM device_leases WHERE gpu_uuid=?",
                (plan.gpu_uuid,),
            ).fetchone()
            if row is None:
                return
            if row["experiment_id"] != experiment_id or row["attempt_id"] != attempt_id:
                raise ExperimentStoreError(
                    "refusing to release another attempt's lease"
                )
            self._connection.execute(
                "DELETE FROM device_leases WHERE gpu_uuid=?", (plan.gpu_uuid,)
            )

    def record_worker(
        self,
        experiment_id: str,
        attempt_id: str,
        *,
        identity: JsonObject,
        cancel_path: str,
        status: str = "running",
    ) -> None:
        if status != "running":
            raise ExperimentStoreError("only a verified host completion may stop a worker")
        with self._transaction():
            existing = self._connection.execute(
                """
                SELECT identity_json,cancel_path FROM workers
                WHERE experiment_id=? AND attempt_id=?
                """,
                (experiment_id, attempt_id),
            ).fetchone()
            encoded = canonical_json(identity)
            if existing is not None:
                if (
                    existing["identity_json"] != encoded
                    or existing["cancel_path"] != cancel_path
                ):
                    raise ExperimentStoreError(
                        "worker identity changed for one attempt"
                    )
                return
            self._assert_launch_unfenced(experiment_id)
            self._connection.execute(
                """
                INSERT INTO workers(
                    experiment_id,attempt_id,identity_json,cancel_path,status
                ) VALUES(?,?,?,?,?)
                """,
                (experiment_id, attempt_id, encoded, cancel_path, status),
            )

    def record_worker_completion(
        self, experiment_id: str, attempt_id: str
    ) -> None:
        """Match an owned host's completed record before releasing the pause fence."""

        root = Path(self.plan(experiment_id).artifact_root).resolve()
        if (
            not attempt_id
            or Path(attempt_id).name != attempt_id
            or attempt_id in {".", ".."}
        ):
            raise ExperimentStoreError("invalid attempt identity")
        marker = (root / attempt_id / "host-complete.json").resolve()
        if not marker.is_relative_to(root) or not marker.is_file():
            raise ExperimentStoreError("owned worker completion marker is missing")
        try:
            completion: object = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExperimentStoreError("invalid worker completion marker") from exc
        if not isinstance(completion, dict):
            raise ExperimentStoreError("worker completion must be an object")
        with self._transaction():
            worker = self._connection.execute(
                """
                SELECT identity_json,status FROM workers
                WHERE experiment_id=? AND attempt_id=?
                """,
                (experiment_id, attempt_id),
            ).fetchone()
            if worker is None:
                raise ExperimentStoreError("worker completion has no recorded owner")
            identity: object = json.loads(cast(str, worker["identity_json"]))
            if not isinstance(identity, dict):
                raise ExperimentStoreError("stored worker identity is invalid")
            required = ("launch_nonce", "source_hash", "config_hash", "spec_hash")
            if any(
                not isinstance(identity.get(field), str)
                or completion.get(field) != identity[field]
                for field in required
            ):
                raise ExperimentStoreError("worker completion identity differs")
            if (
                completion.get("schema") != "ttt.worker_host_completion"
                or completion.get("schema_version") != 1
                or completion.get("attempt_id") != attempt_id
                or completion.get("reason") != "exited"
                or type(completion.get("returncode")) is not int
                or completion["returncode"] != 0
                or completion.get("admission_eligible") is not False
            ):
                raise ExperimentStoreError("worker host did not complete successfully")
            if worker["status"] not in {"running", "stopped"}:
                raise ExperimentStoreError("invalid stored worker status")
            self._connection.execute(
                """
                UPDATE workers SET status='stopped'
                WHERE experiment_id=? AND attempt_id=?
                """,
                (experiment_id, attempt_id),
            )

    def record_artifact(
        self,
        experiment_id: str,
        *,
        name: str,
        path: str,
        sha256: str,
        evidence_class: EvidenceClass,
        admission_eligible: bool,
    ) -> None:
        if len(sha256) != 64 or any(
            character not in "0123456789abcdef" for character in sha256
        ):
            raise ExperimentStoreError("artifact SHA-256 is invalid")
        if admission_eligible and evidence_class is not EvidenceClass.ADMISSION:
            raise ExperimentStoreError(
                "simulation/diagnostic artifacts can never be admission eligible"
            )
        with self._transaction():
            try:
                self._connection.execute(
                    """
                    INSERT INTO artifacts(
                        experiment_id,name,path,sha256,evidence_class,admission_eligible
                    ) VALUES(?,?,?,?,?,?)
                    """,
                    (
                        experiment_id,
                        name,
                        path,
                        sha256,
                        evidence_class.value,
                        1 if admission_eligible else 0,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ExperimentStoreError("artifact name already exists") from exc

    def artifact_inventory(self, experiment_id: str) -> tuple[JsonObject, ...]:
        rows = self._connection.execute(
            """
            SELECT name,path,sha256,evidence_class,admission_eligible
            FROM artifacts WHERE experiment_id=? ORDER BY name
            """,
            (experiment_id,),
        ).fetchall()
        return tuple(
            {
                "name": cast(str, row["name"]),
                "path": cast(str, row["path"]),
                "sha256": cast(str, row["sha256"]),
                "evidence_class": cast(str, row["evidence_class"]),
                "admission_eligible": bool(row["admission_eligible"]),
            }
            for row in rows
        )


def open_replayed(path: str | Path, experiment_id: str) -> ExperimentStore:
    """Open state and fail immediately if its event chain no longer replays."""

    store = ExperimentStore(path)
    try:
        store.replay(experiment_id)
    except (ExperimentStoreError, ExperimentContractError):
        store.close()
        raise
    return store
