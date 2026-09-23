import hashlib
import json
import sqlite3
import time
import uuid


class AssetEvidenceEngine:
    VERSION = "1.0.0"

    STATES = (
        "PROVISIONED",
        "ACTIVE",
        "DEGRADED",
        "CRITICAL",
        "OFFLINE",
        "MAINTENANCE",
        "RECOVERED",
        "RETIRED",
    )

    def __init__(self, db_path="asset-evidence.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                asset_type TEXT NOT NULL,
                manufacturer TEXT,
                model TEXT,
                firmware TEXT,
                authorization_state TEXT,
                lifecycle_state TEXT NOT NULL,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                last_health REAL,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS asset_observations (
                observation_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                state TEXT NOT NULL,
                health_score REAL,
                source TEXT,
                measurements TEXT,
                evidence_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS asset_events (
                event_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                previous_state TEXT,
                new_state TEXT,
                source TEXT,
                evidence TEXT,
                evidence_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS asset_incidents (
                incident_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                incident_type TEXT NOT NULL,
                state TEXT NOT NULL,
                confidence REAL,
                evidence TEXT,
                evidence_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS asset_maintenance (
                maintenance_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                action TEXT NOT NULL,
                technician TEXT,
                result TEXT,
                evidence TEXT,
                evidence_hash TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    @staticmethod
    def _hash(payload):
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")

        return hashlib.sha256(raw).hexdigest()

    def register_asset(
        self,
        asset_id,
        asset_type,
        manufacturer=None,
        model=None,
        firmware=None,
        authorization_state="PENDING",
        metadata=None,
    ):
        now = time.time()

        existing = self.conn.execute(
            "SELECT asset_id FROM assets WHERE asset_id = ?",
            (asset_id,),
        ).fetchone()

        if existing:
            raise ValueError(f"Asset already exists: {asset_id}")

        self.conn.execute(
            """
            INSERT INTO assets (
                asset_id,
                asset_type,
                manufacturer,
                model,
                firmware,
                authorization_state,
                lifecycle_state,
                first_seen,
                last_seen,
                last_health,
                metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                asset_type,
                manufacturer,
                model,
                firmware,
                authorization_state,
                "PROVISIONED",
                now,
                now,
                None,
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )

        evidence = {
            "event": "ASSET_REGISTERED",
            "asset_id": asset_id,
            "asset_type": asset_type,
            "manufacturer": manufacturer,
            "model": model,
            "firmware": firmware,
            "authorization_state": authorization_state,
            "timestamp": now,
        }

        self._event(
            asset_id=asset_id,
            event_type="ASSET_REGISTERED",
            previous_state=None,
            new_state="PROVISIONED",
            source="asset_evidence",
            evidence=evidence,
        )

        self.conn.commit()

        return self.get_asset(asset_id)

    def observe(
        self,
        asset_id,
        state,
        health_score=None,
        source="unknown",
        measurements=None,
    ):
        if state not in self.STATES:
            raise ValueError(f"Invalid lifecycle state: {state}")

        asset = self.get_asset(asset_id)

        if asset is None:
            raise ValueError(f"Unknown asset: {asset_id}")

        now = time.time()

        previous_state = asset["lifecycle_state"]

        payload = {
            "asset_id": asset_id,
            "timestamp": now,
            "state": state,
            "health_score": health_score,
            "source": source,
            "measurements": measurements or {},
        }

        evidence_hash = self._hash(payload)

        observation_id = str(uuid.uuid4())

        self.conn.execute(
            """
            INSERT INTO asset_observations (
                observation_id,
                asset_id,
                timestamp,
                state,
                health_score,
                source,
                measurements,
                evidence_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation_id,
                asset_id,
                now,
                state,
                health_score,
                source,
                json.dumps(measurements or {}, sort_keys=True),
                evidence_hash,
            ),
        )

        self.conn.execute(
            """
            UPDATE assets
            SET lifecycle_state = ?,
                last_seen = ?,
                last_health = ?
            WHERE asset_id = ?
            """,
            (
                state,
                now,
                health_score,
                asset_id,
            ),
        )

        if previous_state != state:
            self._event(
                asset_id=asset_id,
                event_type="STATE_CHANGED",
                previous_state=previous_state,
                new_state=state,
                source=source,
                evidence=payload,
            )

        self.conn.commit()

        return {
            "observation_id": observation_id,
            "asset_id": asset_id,
            "state": state,
            "health_score": health_score,
            "evidence_hash": evidence_hash,
        }

    def record_external_event(
        self,
        asset_id,
        source,
        event_type,
        severity="INFO",
        state=None,
        confidence=0.0,
        evidence=None,
        source_integrity="SOURCE_UNHASHED",
        timestamp=None,
    ):
        """
        Record an event generated by another Sentinel subsystem.

        The originating subsystem remains the owner of its telemetry.
        Asset Evidence stores only the normalized event and its evidence
        reference for lifecycle reconstruction.
        """

        if self.get_asset(asset_id) is None:
            raise ValueError(f"Unknown asset: {asset_id}")

        now = timestamp if timestamp is not None else time.time()

        payload = {
            "asset_id": asset_id,
            "source": source,
            "event_type": event_type,
            "severity": severity,
            "state": state,
            "confidence": confidence,
            "evidence": evidence or {},
            "source_integrity": source_integrity,
            "timestamp": now,
        }

        evidence_hash = self._hash(payload)

        event_id = str(uuid.uuid4())

        self.conn.execute(
            """
            INSERT INTO asset_events (
                event_id,
                asset_id,
                timestamp,
                event_type,
                previous_state,
                new_state,
                source,
                evidence,
                evidence_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                asset_id,
                now,
                event_type,
                None,
                state,
                source,
                json.dumps(
                    {
                        "severity": severity,
                        "confidence": confidence,
                        "evidence": evidence or {},
                        "source_integrity": source_integrity,
                    },
                    sort_keys=True,
                ),
                evidence_hash,
            ),
        )

        self.conn.commit()

        return {
            "event_id": event_id,
            "asset_id": asset_id,
            "source": source,
            "event_type": event_type,
            "severity": severity,
            "state": state,
            "confidence": confidence,
            "source_integrity": source_integrity,
            "evidence_hash": evidence_hash,
        }

    def record_incident(
        self,
        asset_id,
        incident_type,
        state="OPEN",
        confidence=0.0,
        evidence=None,
    ):
        if self.get_asset(asset_id) is None:
            raise ValueError(f"Unknown asset: {asset_id}")

        now = time.time()

        payload = {
            "asset_id": asset_id,
            "incident_type": incident_type,
            "state": state,
            "confidence": confidence,
            "evidence": evidence or {},
            "timestamp": now,
        }

        evidence_hash = self._hash(payload)

        incident_id = str(uuid.uuid4())

        self.conn.execute(
            """
            INSERT INTO asset_incidents (
                incident_id,
                asset_id,
                timestamp,
                incident_type,
                state,
                confidence,
                evidence,
                evidence_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                asset_id,
                now,
                incident_type,
                state,
                confidence,
                json.dumps(evidence or {}, sort_keys=True),
                evidence_hash,
            ),
        )

        self.conn.commit()

        return {
            "incident_id": incident_id,
            "asset_id": asset_id,
            "incident_type": incident_type,
            "state": state,
            "confidence": confidence,
            "evidence_hash": evidence_hash,
        }

    def record_maintenance(
        self,
        asset_id,
        action,
        technician=None,
        result=None,
        evidence=None,
    ):
        if self.get_asset(asset_id) is None:
            raise ValueError(f"Unknown asset: {asset_id}")

        now = time.time()

        payload = {
            "asset_id": asset_id,
            "action": action,
            "technician": technician,
            "result": result,
            "evidence": evidence or {},
            "timestamp": now,
        }

        evidence_hash = self._hash(payload)

        maintenance_id = str(uuid.uuid4())

        self.conn.execute(
            """
            INSERT INTO asset_maintenance (
                maintenance_id,
                asset_id,
                timestamp,
                action,
                technician,
                result,
                evidence,
                evidence_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                maintenance_id,
                asset_id,
                now,
                action,
                technician,
                result,
                json.dumps(evidence or {}, sort_keys=True),
                evidence_hash,
            ),
        )

        self.conn.commit()

        return {
            "maintenance_id": maintenance_id,
            "asset_id": asset_id,
            "action": action,
            "result": result,
            "evidence_hash": evidence_hash,
        }

    def _event(
        self,
        asset_id,
        event_type,
        previous_state,
        new_state,
        source,
        evidence,
    ):
        now = time.time()

        payload = {
            "asset_id": asset_id,
            "event_type": event_type,
            "previous_state": previous_state,
            "new_state": new_state,
            "source": source,
            "evidence": evidence,
            "timestamp": now,
        }

        evidence_hash = self._hash(payload)

        self.conn.execute(
            """
            INSERT INTO asset_events (
                event_id,
                asset_id,
                timestamp,
                event_type,
                previous_state,
                new_state,
                source,
                evidence,
                evidence_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                asset_id,
                now,
                event_type,
                previous_state,
                new_state,
                source,
                json.dumps(evidence, sort_keys=True, default=str),
                evidence_hash,
            ),
        )

    def get_asset(self, asset_id):
        row = self.conn.execute(
            """
            SELECT
                asset_id,
                asset_type,
                manufacturer,
                model,
                firmware,
                authorization_state,
                lifecycle_state,
                first_seen,
                last_seen,
                last_health,
                metadata
            FROM assets
            WHERE asset_id = ?
            """,
            (asset_id,),
        ).fetchone()

        if row is None:
            return None

        columns = [
            "asset_id",
            "asset_type",
            "manufacturer",
            "model",
            "firmware",
            "authorization_state",
            "lifecycle_state",
            "first_seen",
            "last_seen",
            "last_health",
            "metadata",
        ]

        result = dict(zip(columns, row))
        result["metadata"] = json.loads(result["metadata"] or "{}")

        return result

    def history(self, asset_id):
        rows = self.conn.execute(
            """
            SELECT
                observation_id,
                timestamp,
                state,
                health_score,
                source,
                measurements,
                evidence_hash
            FROM asset_observations
            WHERE asset_id = ?
            ORDER BY timestamp ASC
            """,
            (asset_id,),
        ).fetchall()

        return [
            {
                "observation_id": row[0],
                "timestamp": row[1],
                "state": row[2],
                "health_score": row[3],
                "source": row[4],
                "measurements": json.loads(row[5] or "{}"),
                "evidence_hash": row[6],
            }
            for row in rows
        ]

    def events(self, asset_id):
        rows = self.conn.execute(
            """
            SELECT
                event_id,
                timestamp,
                event_type,
                previous_state,
                new_state,
                source,
                evidence,
                evidence_hash
            FROM asset_events
            WHERE asset_id = ?
            ORDER BY timestamp ASC
            """,
            (asset_id,),
        ).fetchall()

        return [
            {
                "event_id": row[0],
                "timestamp": row[1],
                "event_type": row[2],
                "previous_state": row[3],
                "new_state": row[4],
                "source": row[5],
                "evidence": json.loads(row[6] or "{}"),
                "evidence_hash": row[7],
            }
            for row in rows
        ]

    def close(self):
        self.conn.close()
