"""SQLite WAL persistence, event replay, budgets, attempts, and evidence classes."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import cast

from techrotic_training_triumvirate.schemas import (
    JsonObject,
    canonical_json,
    content_hash,
)
from techrotic_training_triumvirate.schemas.base import require_json_object

from .model import (
    EvidenceClass,
    ExperimentPlan,
    ExperimentState,
    OrchestrationError,
    PlanValidationError,
    advance,
    make_event_id,
)


class StoreError(OrchestrationError):
    """Persistent orchestration state is inconsistent or unsafe."""


class BudgetError(StoreError):
    """A reservation would exceed the admitted immutable budget."""


class EvidenceError(StoreError):
    """Evidence cannot be used with the declared experiment class."""


@dataclass(frozen=True, slots=True)
class StoredEvent:
    sequence: int
    event_id: str
    parent_event_hash: str
    event_hash: str
    event_type: str
    timestamp_ns: int
    payload: JsonObject
    state_before: ExperimentState
    state_after: ExperimentState


def _load_object(text: str, *, field: str) -> JsonObject:
    try:
        value: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StoreError(f"{field} contains invalid JSON") from exc
    return require_json_object(value, field=field)


def _sha256(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise StoreError(f"{field} must be a lowercase SHA-256")
    return value


def _safe_inventory(inventory: Mapping[str, str]) -> JsonObject:
    if not inventory:
        raise EvidenceError("artifact inventory must not be empty")
    result: JsonObject = {}
    for name, digest in sorted(inventory.items()):
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or ".." in path.parts
            or name == "."
        ):
            raise EvidenceError("artifact inventory contains an unsafe path")
        result[name] = _sha256(digest, field=f"artifact hash {name}")
    return result


class ExperimentStore:
    """Restart-safe durable owner of one or more deterministic experiments."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(
            str(self.path),
            isolation_level=None,
            timeout=5.0,
        )
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA busy_timeout=5000")
        mode = self._db.execute("PRAGMA journal_mode=WAL").fetchone()
        if mode is None or str(mode[0]).lower() != "wal":
            raise StoreError("SQLite WAL mode could not be enabled")
        self._db.execute("PRAGMA synchronous=FULL")
        self._migrate()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> ExperimentStore:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._db.rollback()
            raise
        else:
            self._db.commit()

    def _migrate(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO schema_meta(key, value)
            VALUES ('schema_version', '1');

            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                plan_json TEXT NOT NULL,
                state TEXT NOT NULL,
                created_at_ns INTEGER NOT NULL,
                updated_at_ns INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                experiment_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                event_id TEXT NOT NULL UNIQUE,
                parent_event_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                timestamp_ns INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                state_before TEXT NOT NULL,
                state_after TEXT NOT NULL,
                PRIMARY KEY (experiment_id, sequence),
                FOREIGN KEY (experiment_id)
                    REFERENCES experiments(experiment_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS budgets (
                experiment_id TEXT PRIMARY KEY,
                gpu_limit_seconds INTEGER NOT NULL,
                cpu_limit_seconds INTEGER NOT NULL,
                gpu_reserved_seconds INTEGER NOT NULL DEFAULT 0,
                gpu_charged_seconds INTEGER NOT NULL DEFAULT 0,
                cpu_reserved_seconds INTEGER NOT NULL DEFAULT 0,
                cpu_charged_seconds INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (experiment_id)
                    REFERENCES experiments(experiment_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS reservations (
                reservation_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                resource TEXT NOT NULL CHECK(resource IN ('gpu', 'cpu')),
                cap_seconds INTEGER NOT NULL,
                charged_seconds INTEGER,
                exit_established INTEGER,
                status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'RECONCILED')),
                FOREIGN KEY (experiment_id)
                    REFERENCES experiments(experiment_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS attempts (
                attempt_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                stage_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                launch_nonce TEXT NOT NULL UNIQUE,
                source_sha256 TEXT NOT NULL,
                config_sha256 TEXT NOT NULL,
                pid INTEGER,
                creation_token TEXT,
                status TEXT NOT NULL,
                UNIQUE (experiment_id, stage_id, ordinal),
                FOREIGN KEY (experiment_id)
                    REFERENCES experiments(experiment_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS device_leases (
                lease_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                device_uuid TEXT NOT NULL,
                launch_nonce TEXT NOT NULL,
                acquired_at_ns INTEGER NOT NULL,
                released_at_ns INTEGER,
                status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'RELEASED')),
                FOREIGN KEY (experiment_id)
                    REFERENCES experiments(experiment_id) ON DELETE RESTRICT,
                FOREIGN KEY (attempt_id)
                    REFERENCES attempts(attempt_id) ON DELETE RESTRICT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_device_lease
                ON device_leases(device_uuid)
                WHERE status='ACTIVE';

            CREATE TABLE IF NOT EXISTS inventories (
                experiment_id TEXT NOT NULL,
                stage_id TEXT NOT NULL,
                inventory_hash TEXT NOT NULL,
                inventory_json TEXT NOT NULL,
                evidence_class TEXT NOT NULL,
                PRIMARY KEY (experiment_id, stage_id),
                FOREIGN KEY (experiment_id)
                    REFERENCES experiments(experiment_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS reviews (
                review_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                packet_id TEXT NOT NULL,
                review_class TEXT NOT NULL CHECK(review_class IN ('human', 'test')),
                ratings_json TEXT NOT NULL,
                imported_at_ns INTEGER NOT NULL,
                FOREIGN KEY (experiment_id)
                    REFERENCES experiments(experiment_id) ON DELETE RESTRICT
            );
            """
        )
        row = self._db.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()
        if row is None or row[0] != "1":
            raise StoreError("unsupported orchestration database schema")

    def create_experiment(self, plan: ExperimentPlan, *, timestamp_ns: int) -> str:
        if timestamp_ns < 0:
            raise StoreError("timestamp_ns must be nonnegative")
        experiment_id = plan.experiment_id
        encoded = canonical_json(plan.to_object())
        with self._transaction():
            row = self._db.execute(
                "SELECT plan_json FROM experiments WHERE experiment_id=?",
                (experiment_id,),
            ).fetchone()
            if row is not None:
                if str(row[0]) != encoded:
                    raise StoreError(
                        "experiment identity collision with different plan"
                    )
                return experiment_id
            self._db.execute(
                """
                INSERT INTO experiments(
                    experiment_id, plan_json, state, created_at_ns, updated_at_ns
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    encoded,
                    ExperimentState.PLANNED.value,
                    timestamp_ns,
                    timestamp_ns,
                ),
            )
            self._db.execute(
                """
                INSERT INTO budgets(
                    experiment_id, gpu_limit_seconds, cpu_limit_seconds
                ) VALUES (?, ?, ?)
                """,
                (
                    experiment_id,
                    plan.gpu_budget_seconds,
                    plan.cpu_budget_seconds,
                ),
            )
        return experiment_id

    def load_plan(self, experiment_id: str) -> ExperimentPlan:
        row = self._db.execute(
            "SELECT plan_json FROM experiments WHERE experiment_id=?",
            (experiment_id,),
        ).fetchone()
        if row is None:
            raise StoreError("unknown experiment")
        try:
            return ExperimentPlan.from_object(json.loads(str(row[0])))
        except (json.JSONDecodeError, PlanValidationError) as exc:
            raise StoreError("stored experiment plan is invalid") from exc

    def state(self, experiment_id: str) -> ExperimentState:
        row = self._db.execute(
            "SELECT state FROM experiments WHERE experiment_id=?",
            (experiment_id,),
        ).fetchone()
        if row is None:
            raise StoreError("unknown experiment")
        try:
            return ExperimentState(str(row[0]))
        except ValueError as exc:
            raise StoreError("stored experiment state is invalid") from exc

    def append_event(
        self,
        experiment_id: str,
        event_type: str,
        payload: JsonObject,
        *,
        timestamp_ns: int,
        idempotency_key: str | None = None,
        event_id: str | None = None,
    ) -> StoredEvent:
        if timestamp_ns < 0:
            raise StoreError("timestamp_ns must be nonnegative")
        payload_json = canonical_json(payload)
        resolved_event_id = event_id or make_event_id(
            experiment_id,
            event_type,
            timestamp_ns,
            payload,
            idempotency_key=idempotency_key,
        )
        with self._transaction():
            existing = self._db.execute(
                """
                SELECT sequence, parent_event_hash, event_hash, event_type,
                       timestamp_ns, payload_json, state_before, state_after,
                       experiment_id
                FROM events WHERE event_id=?
                """,
                (resolved_event_id,),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing[8]) != experiment_id
                    or str(existing[3]) != event_type
                    or int(existing[4]) != timestamp_ns
                    or str(existing[5]) != payload_json
                ):
                    raise StoreError("event ID was reused for different content")
                return StoredEvent(
                    sequence=int(existing[0]),
                    event_id=resolved_event_id,
                    parent_event_hash=str(existing[1]),
                    event_hash=str(existing[2]),
                    event_type=str(existing[3]),
                    timestamp_ns=int(existing[4]),
                    payload=_load_object(str(existing[5]), field="event payload"),
                    state_before=ExperimentState(str(existing[6])),
                    state_after=ExperimentState(str(existing[7])),
                )

            state_row = self._db.execute(
                "SELECT state, plan_json FROM experiments WHERE experiment_id=?",
                (experiment_id,),
            ).fetchone()
            if state_row is None:
                raise StoreError("unknown experiment")
            state_before = ExperimentState(str(state_row[0]))
            plan = ExperimentPlan.from_object(json.loads(str(state_row[1])))
            self._validate_event_boundary(
                plan,
                experiment_id,
                state_before,
                event_type,
                payload,
            )
            transition = advance(state_before, event_type)
            previous = self._db.execute(
                """
                SELECT sequence, event_hash FROM events
                WHERE experiment_id=? ORDER BY sequence DESC LIMIT 1
                """,
                (experiment_id,),
            ).fetchone()
            sequence = 1 if previous is None else int(previous[0]) + 1
            parent_hash = "0" * 64 if previous is None else str(previous[1])
            event_hash = content_hash(
                {
                    "sequence": sequence,
                    "event_id": resolved_event_id,
                    "parent_event_hash": parent_hash,
                    "experiment_id": experiment_id,
                    "event_type": event_type,
                    "timestamp_ns": timestamp_ns,
                    "payload": payload,
                    "state_before": state_before.value,
                    "state_after": transition.state.value,
                }
            )
            self._db.execute(
                """
                INSERT INTO events(
                    experiment_id, sequence, event_id, parent_event_hash,
                    event_hash, event_type, timestamp_ns, payload_json,
                    state_before, state_after
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    sequence,
                    resolved_event_id,
                    parent_hash,
                    event_hash,
                    event_type,
                    timestamp_ns,
                    payload_json,
                    state_before.value,
                    transition.state.value,
                ),
            )
            self._db.execute(
                """
                UPDATE experiments SET state=?, updated_at_ns=?
                WHERE experiment_id=?
                """,
                (transition.state.value, timestamp_ns, experiment_id),
            )
        return StoredEvent(
            sequence=sequence,
            event_id=resolved_event_id,
            parent_event_hash=parent_hash,
            event_hash=event_hash,
            event_type=event_type,
            timestamp_ns=timestamp_ns,
            payload=payload,
            state_before=state_before,
            state_after=transition.state,
        )

    def _validate_event_boundary(
        self,
        plan: ExperimentPlan,
        experiment_id: str,
        state: ExperimentState,
        event_type: str,
        payload: JsonObject,
    ) -> None:
        if event_type == "WORKER_LAUNCHED":
            attempt_id = payload.get("attempt_id")
            reservation_id = payload.get("reservation_id")
            lease_id = payload.get("lease_id")
            if not all(
                isinstance(item, str)
                for item in (attempt_id, reservation_id, lease_id)
            ):
                raise StoreError(
                    "worker launch must bind attempt, reservation and device lease"
                )
            attempt = self._db.execute(
                """
                SELECT 1 FROM attempts
                WHERE attempt_id=? AND experiment_id=?
                """,
                (attempt_id, experiment_id),
            ).fetchone()
            reservation = self._db.execute(
                """
                SELECT 1 FROM reservations
                WHERE reservation_id=? AND experiment_id=?
                  AND attempt_id=? AND resource='gpu' AND status='ACTIVE'
                """,
                (reservation_id, experiment_id, attempt_id),
            ).fetchone()
            lease = self._db.execute(
                """
                SELECT 1 FROM device_leases
                WHERE lease_id=? AND experiment_id=? AND attempt_id=?
                  AND status='ACTIVE'
                """,
                (lease_id, experiment_id, attempt_id),
            ).fetchone()
            if attempt is None or reservation is None or lease is None:
                raise StoreError(
                    "worker launch requires registered attempt, active GPU "
                    "reservation and active device lease"
                )
        if event_type == "RUNTIME_QUALIFIED":
            named_host = payload.get("named_host_acceptance")
            evidence_class = payload.get("evidence_class")
            if plan.simulation:
                if (
                    named_host is not False
                    or evidence_class != EvidenceClass.SIMULATION.value
                ):
                    raise EvidenceError(
                        "simulation runtime evidence must remain test-only"
                    )
            elif (
                named_host is not True
                or evidence_class != EvidenceClass.ACTUAL.value
            ):
                raise EvidenceError(
                    "actual runtime qualification requires named-host actual evidence"
                )
        if event_type == "HUMAN_REVIEW_IMPORTED":
            review_class = payload.get("review_class")
            expected = "test" if plan.simulation else "human"
            if review_class != expected:
                raise EvidenceError(
                    f"{expected} review is required for this experiment class"
                )
        if event_type == "DISPOSITION_VERIFIED":
            outcome = payload.get("outcome")
            if plan.simulation:
                if outcome != "TEST_ONLY":
                    raise EvidenceError(
                        "simulation can complete only with TEST_ONLY disposition"
                    )
            elif outcome not in {
                "ADMITTED",
                "CONDITIONALLY ADMITTED",
                "NOT ADMITTED",
            }:
                raise EvidenceError("actual disposition is unsupported")
        if event_type == "CANCELLED" and state != ExperimentState.CANCELLING:
            raise StoreError("cancellation can complete only from CANCELLING")

    def events(self, experiment_id: str) -> tuple[StoredEvent, ...]:
        rows = self._db.execute(
            """
            SELECT sequence, event_id, parent_event_hash, event_hash, event_type,
                   timestamp_ns, payload_json, state_before, state_after
            FROM events WHERE experiment_id=? ORDER BY sequence
            """,
            (experiment_id,),
        ).fetchall()
        if not rows and self._db.execute(
            "SELECT 1 FROM experiments WHERE experiment_id=?", (experiment_id,)
        ).fetchone() is None:
            raise StoreError("unknown experiment")
        return tuple(
            StoredEvent(
                sequence=int(row[0]),
                event_id=str(row[1]),
                parent_event_hash=str(row[2]),
                event_hash=str(row[3]),
                event_type=str(row[4]),
                timestamp_ns=int(row[5]),
                payload=_load_object(str(row[6]), field="event payload"),
                state_before=ExperimentState(str(row[7])),
                state_after=ExperimentState(str(row[8])),
            )
            for row in rows
        )

    def replay(self, experiment_id: str) -> ExperimentState:
        state = ExperimentState.PLANNED
        parent_hash = "0" * 64
        for expected_sequence, event in enumerate(
            self.events(experiment_id), start=1
        ):
            if event.sequence != expected_sequence:
                raise StoreError("event journal has a sequence gap")
            if event.parent_event_hash != parent_hash:
                raise StoreError("event journal parent hash differs")
            if event.state_before != state:
                raise StoreError("event journal state_before differs")
            transition = advance(state, event.event_type)
            if transition.state != event.state_after:
                raise StoreError("event journal transition differs")
            recomputed = content_hash(
                {
                    "sequence": event.sequence,
                    "event_id": event.event_id,
                    "parent_event_hash": event.parent_event_hash,
                    "experiment_id": experiment_id,
                    "event_type": event.event_type,
                    "timestamp_ns": event.timestamp_ns,
                    "payload": event.payload,
                    "state_before": event.state_before.value,
                    "state_after": event.state_after.value,
                }
            )
            if recomputed != event.event_hash:
                raise StoreError("event journal hash differs")
            state = event.state_after
            parent_hash = event.event_hash
        if self.state(experiment_id) != state:
            raise StoreError("materialized state differs from deterministic replay")
        return state

    def register_attempt(
        self,
        experiment_id: str,
        *,
        stage_id: str,
        ordinal: int,
        launch_nonce: str,
        source_sha256: str,
        config_sha256: str,
    ) -> str:
        _sha256(stage_id, field="stage_id")
        _sha256(source_sha256, field="source_sha256")
        _sha256(config_sha256, field="config_sha256")
        if isinstance(ordinal, bool) or ordinal < 1:
            raise StoreError("attempt ordinal must be a positive integer")
        if not launch_nonce:
            raise StoreError("launch_nonce must not be empty")
        attempt_id = content_hash(
            {
                "experiment_id": experiment_id,
                "stage_id": stage_id,
                "ordinal": ordinal,
                "launch_nonce": launch_nonce,
                "source_sha256": source_sha256,
                "config_sha256": config_sha256,
            }
        )
        with self._transaction():
            existing = self._db.execute(
                """
                SELECT experiment_id, stage_id, ordinal, launch_nonce,
                       source_sha256, config_sha256
                FROM attempts WHERE attempt_id=?
                """,
                (attempt_id,),
            ).fetchone()
            if existing is not None:
                expected = (
                    experiment_id,
                    stage_id,
                    ordinal,
                    launch_nonce,
                    source_sha256,
                    config_sha256,
                )
                actual = (
                    str(existing[0]),
                    str(existing[1]),
                    int(existing[2]),
                    str(existing[3]),
                    str(existing[4]),
                    str(existing[5]),
                )
                if actual != expected:
                    raise StoreError("attempt identity collision")
                return attempt_id
            try:
                self._db.execute(
                    """
                    INSERT INTO attempts(
                        attempt_id, experiment_id, stage_id, ordinal,
                        launch_nonce, source_sha256, config_sha256, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'REGISTERED')
                    """,
                    (
                        attempt_id,
                        experiment_id,
                        stage_id,
                        ordinal,
                        launch_nonce,
                        source_sha256,
                        config_sha256,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise StoreError(
                    "attempt ordinal or launch nonce was already consumed"
                ) from exc
        return attempt_id

    def acquire_device_lease(
        self,
        experiment_id: str,
        *,
        attempt_id: str,
        device_uuid: str,
        launch_nonce: str,
        acquired_at_ns: int,
    ) -> str:
        """Acquire the exact admitted physical UUID transactionally."""

        plan = self.load_plan(experiment_id)
        if device_uuid != plan.target_gpu_uuid:
            raise StoreError("device lease UUID differs from immutable plan")
        if not launch_nonce or acquired_at_ns < 0:
            raise StoreError("device lease identity fields are invalid")
        lease_id = content_hash(
            {
                "experiment_id": experiment_id,
                "attempt_id": attempt_id,
                "device_uuid": device_uuid,
                "launch_nonce": launch_nonce,
            }
        )
        with self._transaction():
            attempt = self._db.execute(
                """
                SELECT launch_nonce FROM attempts
                WHERE attempt_id=? AND experiment_id=?
                """,
                (attempt_id, experiment_id),
            ).fetchone()
            if attempt is None or str(attempt[0]) != launch_nonce:
                raise StoreError("device lease requires the registered attempt nonce")
            existing = self._db.execute(
                """
                SELECT experiment_id, attempt_id, device_uuid, launch_nonce, status
                FROM device_leases WHERE lease_id=?
                """,
                (lease_id,),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing[0]),
                    str(existing[1]),
                    str(existing[2]),
                    str(existing[3]),
                    str(existing[4]),
                ) != (
                    experiment_id,
                    attempt_id,
                    device_uuid,
                    launch_nonce,
                    "ACTIVE",
                ):
                    raise StoreError("device lease identity collision")
                return lease_id
            active = self._db.execute(
                """
                SELECT lease_id FROM device_leases
                WHERE device_uuid=? AND status='ACTIVE'
                """,
                (device_uuid,),
            ).fetchone()
            if active is not None:
                raise StoreError("physical GPU already has an active lease")
            self._db.execute(
                """
                INSERT INTO device_leases(
                    lease_id, experiment_id, attempt_id, device_uuid,
                    launch_nonce, acquired_at_ns, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
                """,
                (
                    lease_id,
                    experiment_id,
                    attempt_id,
                    device_uuid,
                    launch_nonce,
                    acquired_at_ns,
                ),
            )
        return lease_id

    def release_device_lease(self, lease_id: str, *, released_at_ns: int) -> None:
        """Release an owned lease after exit is established or preserved failure."""

        if released_at_ns < 0:
            raise StoreError("released_at_ns must be nonnegative")
        with self._transaction():
            row = self._db.execute(
                """
                SELECT status, released_at_ns FROM device_leases WHERE lease_id=?
                """,
                (lease_id,),
            ).fetchone()
            if row is None:
                raise StoreError("unknown device lease")
            if str(row[0]) == "RELEASED":
                if int(cast(int, row[1])) != released_at_ns:
                    raise StoreError("released device lease cannot be rewritten")
                return
            self._db.execute(
                """
                UPDATE device_leases
                SET status='RELEASED', released_at_ns=?
                WHERE lease_id=?
                """,
                (released_at_ns, lease_id),
            )

    def active_device_leases(self, experiment_id: str) -> tuple[str, ...]:
        rows = self._db.execute(
            """
            SELECT lease_id FROM device_leases
            WHERE experiment_id=? AND status='ACTIVE'
            ORDER BY lease_id
            """,
            (experiment_id,),
        ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def bind_process(
        self,
        attempt_id: str,
        *,
        pid: int,
        creation_token: str,
    ) -> None:
        if pid <= 0 or not creation_token:
            raise StoreError("owned process requires PID and creation token")
        with self._transaction():
            row = self._db.execute(
                "SELECT pid, creation_token FROM attempts WHERE attempt_id=?",
                (attempt_id,),
            ).fetchone()
            if row is None:
                raise StoreError("unknown attempt")
            if row[0] is not None:
                if int(row[0]) != pid or str(row[1]) != creation_token:
                    raise StoreError("attempt process ownership cannot be rebound")
                return
            self._db.execute(
                """
                UPDATE attempts SET pid=?, creation_token=?, status='RUNNING'
                WHERE attempt_id=?
                """,
                (pid, creation_token, attempt_id),
            )

    def reserve_budget(
        self,
        experiment_id: str,
        *,
        attempt_id: str,
        resource: str,
        cap_seconds: int,
    ) -> str:
        if resource not in {"gpu", "cpu"}:
            raise BudgetError("resource must be gpu or cpu")
        if isinstance(cap_seconds, bool) or cap_seconds <= 0:
            raise BudgetError("reservation cap must be a positive integer")
        attempt = self._db.execute(
            """
            SELECT 1 FROM attempts
            WHERE attempt_id=? AND experiment_id=?
            """,
            (attempt_id, experiment_id),
        ).fetchone()
        if attempt is None:
            raise BudgetError("reservation requires a registered attempt")
        reservation_id = content_hash(
            {
                "experiment_id": experiment_id,
                "attempt_id": attempt_id,
                "resource": resource,
                "cap_seconds": cap_seconds,
            }
        )
        reserved_column = f"{resource}_reserved_seconds"
        charged_column = f"{resource}_charged_seconds"
        limit_column = f"{resource}_limit_seconds"
        with self._transaction():
            existing = self._db.execute(
                """
                SELECT experiment_id, attempt_id, resource, cap_seconds
                FROM reservations WHERE reservation_id=?
                """,
                (reservation_id,),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing[0]),
                    str(existing[1]),
                    str(existing[2]),
                    int(existing[3]),
                ) != (experiment_id, attempt_id, resource, cap_seconds):
                    raise BudgetError("reservation identity collision")
                return reservation_id
            budget = self._db.execute(
                f"""
                SELECT {limit_column}, {reserved_column}, {charged_column}
                FROM budgets WHERE experiment_id=?
                """,
                (experiment_id,),
            ).fetchone()
            if budget is None:
                raise BudgetError("unknown experiment budget")
            limit = int(budget[0])
            reserved = int(budget[1])
            charged = int(budget[2])
            if reserved + charged + cap_seconds > limit:
                raise BudgetError("reservation exceeds remaining admitted budget")
            self._db.execute(
                """
                INSERT INTO reservations(
                    reservation_id, experiment_id, attempt_id, resource,
                    cap_seconds, status
                ) VALUES (?, ?, ?, ?, ?, 'ACTIVE')
                """,
                (
                    reservation_id,
                    experiment_id,
                    attempt_id,
                    resource,
                    cap_seconds,
                ),
            )
            self._db.execute(
                f"""
                UPDATE budgets
                SET {reserved_column}={reserved_column}+?
                WHERE experiment_id=?
                """,
                (cap_seconds, experiment_id),
            )
        return reservation_id

    def reconcile_reservation(
        self,
        reservation_id: str,
        *,
        measured_seconds: int | None,
        exit_established: bool,
    ) -> int:
        if measured_seconds is not None and (
            isinstance(measured_seconds, bool) or measured_seconds < 0
        ):
            raise BudgetError("measured_seconds must be nonnegative")
        with self._transaction():
            row = self._db.execute(
                """
                SELECT experiment_id, resource, cap_seconds, charged_seconds,
                       exit_established, status
                FROM reservations WHERE reservation_id=?
                """,
                (reservation_id,),
            ).fetchone()
            if row is None:
                raise BudgetError("unknown reservation")
            experiment_id = str(row[0])
            resource = str(row[1])
            cap = int(row[2])
            charge = (
                cap
                if not exit_established or measured_seconds is None
                else min(cap, measured_seconds)
            )
            if str(row[5]) == "RECONCILED":
                if int(cast(int, row[3])) != charge or bool(row[4]) != exit_established:
                    raise BudgetError("reconciled reservation cannot be rewritten")
                return charge
            reserved_column = f"{resource}_reserved_seconds"
            charged_column = f"{resource}_charged_seconds"
            self._db.execute(
                f"""
                UPDATE budgets
                SET {reserved_column}={reserved_column}-?,
                    {charged_column}={charged_column}+?
                WHERE experiment_id=?
                """,
                (cap, charge, experiment_id),
            )
            self._db.execute(
                """
                UPDATE reservations
                SET charged_seconds=?, exit_established=?, status='RECONCILED'
                WHERE reservation_id=?
                """,
                (charge, int(exit_established), reservation_id),
            )
        return charge

    def budget_snapshot(self, experiment_id: str) -> JsonObject:
        row = self._db.execute(
            """
            SELECT gpu_limit_seconds, cpu_limit_seconds,
                   gpu_reserved_seconds, gpu_charged_seconds,
                   cpu_reserved_seconds, cpu_charged_seconds
            FROM budgets WHERE experiment_id=?
            """,
            (experiment_id,),
        ).fetchone()
        if row is None:
            raise BudgetError("unknown experiment budget")
        return {
            "gpu_limit_seconds": int(row[0]),
            "cpu_limit_seconds": int(row[1]),
            "gpu_reserved_seconds": int(row[2]),
            "gpu_charged_seconds": int(row[3]),
            "cpu_reserved_seconds": int(row[4]),
            "cpu_charged_seconds": int(row[5]),
        }

    def active_reservations(self, experiment_id: str) -> tuple[str, ...]:
        rows = self._db.execute(
            """
            SELECT reservation_id FROM reservations
            WHERE experiment_id=? AND status='ACTIVE'
            ORDER BY reservation_id
            """,
            (experiment_id,),
        ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def record_inventory(
        self,
        experiment_id: str,
        *,
        stage_id: str,
        inventory: Mapping[str, str],
        evidence_class: EvidenceClass,
    ) -> str:
        _sha256(stage_id, field="stage_id")
        normalized = _safe_inventory(inventory)
        inventory_hash = content_hash(normalized)
        encoded = canonical_json(normalized)
        with self._transaction():
            row = self._db.execute(
                """
                SELECT inventory_hash, inventory_json, evidence_class
                FROM inventories WHERE experiment_id=? AND stage_id=?
                """,
                (experiment_id, stage_id),
            ).fetchone()
            if row is not None:
                if (
                    str(row[0]) != inventory_hash
                    or str(row[1]) != encoded
                    or str(row[2]) != evidence_class.value
                ):
                    raise EvidenceError("stage inventory is immutable")
                return inventory_hash
            self._db.execute(
                """
                INSERT INTO inventories(
                    experiment_id, stage_id, inventory_hash,
                    inventory_json, evidence_class
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    stage_id,
                    inventory_hash,
                    encoded,
                    evidence_class.value,
                ),
            )
        return inventory_hash

    def record_review(
        self,
        experiment_id: str,
        *,
        candidate_id: str,
        packet_id: str,
        ratings: Mapping[str, int],
        review_class: str,
        imported_at_ns: int,
    ) -> str:
        plan = self.load_plan(experiment_id)
        expected_class = "test" if plan.simulation else "human"
        if review_class != expected_class:
            raise EvidenceError(
                f"{expected_class} review is required for this experiment class"
            )
        required = {"humour", "surprise", "distinctiveness"}
        if set(ratings) != required:
            raise EvidenceError("review ratings must use the three admitted fields")
        normalized: JsonObject = {}
        for name in sorted(required):
            value = ratings[name]
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= 5
            ):
                raise EvidenceError("review ratings must be integer 1-5")
            normalized[name] = value
        if not candidate_id or not packet_id or imported_at_ns < 0:
            raise EvidenceError("review identity fields are invalid")
        review_id = content_hash(
            {
                "experiment_id": experiment_id,
                "candidate_id": candidate_id,
                "packet_id": packet_id,
                "review_class": review_class,
                "ratings": normalized,
            }
        )
        encoded = canonical_json(normalized)
        with self._transaction():
            row = self._db.execute(
                """
                SELECT experiment_id, candidate_id, packet_id,
                       review_class, ratings_json
                FROM reviews WHERE review_id=?
                """,
                (review_id,),
            ).fetchone()
            if row is not None:
                if (
                    str(row[0]),
                    str(row[1]),
                    str(row[2]),
                    str(row[3]),
                    str(row[4]),
                ) != (
                    experiment_id,
                    candidate_id,
                    packet_id,
                    review_class,
                    encoded,
                ):
                    raise EvidenceError("review identity collision")
                return review_id
            self._db.execute(
                """
                INSERT INTO reviews(
                    review_id, experiment_id, candidate_id, packet_id,
                    review_class, ratings_json, imported_at_ns
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    experiment_id,
                    candidate_id,
                    packet_id,
                    review_class,
                    encoded,
                    imported_at_ns,
                ),
            )
        return review_id

    def assert_actual_evidence(self, experiment_id: str) -> None:
        """Reject test evidence; require actual evidence for substantive readback."""

        plan = self.load_plan(experiment_id)
        if plan.simulation:
            raise EvidenceError("simulation can never qualify an actual candidate")
        rows = self._db.execute(
            """
            SELECT evidence_class FROM inventories WHERE experiment_id=?
            """,
            (experiment_id,),
        ).fetchall()
        classes = {EvidenceClass(str(row[0])) for row in rows}
        if EvidenceClass.SIMULATION in classes:
            raise EvidenceError("simulation inventory cannot enter actual admission")
        if EvidenceClass.ACTUAL not in classes:
            raise EvidenceError(
                "substantive admission requires independently verified actual evidence"
            )

    def status(self, experiment_id: str) -> JsonObject:
        events = self.events(experiment_id)
        return {
            "experiment_id": experiment_id,
            "state": self.state(experiment_id).value,
            "event_count": len(events),
            "last_event_hash": events[-1].event_hash if events else None,
            "budget": self.budget_snapshot(experiment_id),
            "active_reservations": list(self.active_reservations(experiment_id)),
            "active_device_leases": list(
                self.active_device_leases(experiment_id)
            ),
            "simulation": self.load_plan(experiment_id).simulation,
        }
