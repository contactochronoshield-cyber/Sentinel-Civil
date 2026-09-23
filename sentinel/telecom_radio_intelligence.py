import json
import sqlite3
import time
import uuid
import hashlib


class TelecomRadioIntelligence:
    VERSION = "1.0.0"

    TECHNOLOGIES = {
        "LTE": {
            "domain": "CELLULAR",
            "role": "ACCESS",
        },
        "5G_NR": {
            "domain": "CELLULAR",
            "role": "ACCESS",
        },
        "WIFI": {
            "domain": "LAN",
            "role": "ACCESS",
        },
        "PMR": {
            "domain": "CRITICAL_RADIO",
            "role": "VOICE",
        },
        "DMR": {
            "domain": "CRITICAL_RADIO",
            "role": "VOICE",
        },
        "TETRA": {
            "domain": "CRITICAL_RADIO",
            "role": "VOICE",
        },
        "LORA": {
            "domain": "LPWAN",
            "role": "SENSOR",
        },
        "LORAWAN": {
            "domain": "LPWAN",
            "role": "GATEWAY",
        },
        "MICROWAVE": {
            "domain": "BACKHAUL",
            "role": "TRANSPORT",
        },
        "SATELLITE": {
            "domain": "SATELLITE",
            "role": "TRANSPORT",
        },
    }

    CRITICALITY_LEVELS = {
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }

    STATES = {
        "UNKNOWN",
        "NORMAL",
        "DEGRADED",
        "CRITICAL",
        "OFFLINE",
        "RECOVERED",
    }

    def __init__(self, db_path=":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telecom_radios (
                radio_id TEXT PRIMARY KEY,
                technology TEXT NOT NULL,
                domain TEXT NOT NULL,
                role TEXT NOT NULL,
                site_id TEXT,
                manufacturer TEXT,
                model TEXT,
                firmware TEXT,
                criticality TEXT NOT NULL,
                backhaul_dependency INTEGER NOT NULL DEFAULT 0,
                power_dependency INTEGER NOT NULL DEFAULT 0,
                metadata TEXT,
                created_at REAL NOT NULL
            )
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telecom_radio_observations (
                observation_id TEXT PRIMARY KEY,
                radio_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                state TEXT NOT NULL,
                health_score INTEGER,
                signal_level REAL,
                snr REAL,
                latency_ms REAL,
                packet_loss REAL,
                availability REAL,
                evidence TEXT,
                FOREIGN KEY (radio_id)
                    REFERENCES telecom_radios(radio_id)
            )
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telecom_radio_events (
                event_id TEXT PRIMARY KEY,
                radio_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                previous_state TEXT,
                new_state TEXT,
                evidence TEXT,
                evidence_hash TEXT NOT NULL,
                FOREIGN KEY (radio_id)
                    REFERENCES telecom_radios(radio_id)
            )
            """
        )

        self.conn.commit()

    @staticmethod
    def _hash(payload):
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

        return hashlib.sha256(encoded).hexdigest()

    def register_radio(
        self,
        radio_id,
        technology,
        site_id=None,
        manufacturer=None,
        model=None,
        firmware=None,
        criticality="MEDIUM",
        backhaul_dependency=False,
        power_dependency=False,
        metadata=None,
    ):
        technology = technology.upper()

        if technology not in self.TECHNOLOGIES:
            raise ValueError(
                f"Unsupported technology: {technology}"
            )

        if criticality not in self.CRITICALITY_LEVELS:
            raise ValueError(
                f"Invalid criticality: {criticality}"
            )

        profile = self.TECHNOLOGIES[technology]

        self.conn.execute(
            """
            INSERT OR REPLACE INTO telecom_radios (
                radio_id,
                technology,
                domain,
                role,
                site_id,
                manufacturer,
                model,
                firmware,
                criticality,
                backhaul_dependency,
                power_dependency,
                metadata,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                radio_id,
                technology,
                profile["domain"],
                profile["role"],
                site_id,
                manufacturer,
                model,
                firmware,
                criticality,
                int(bool(backhaul_dependency)),
                int(bool(power_dependency)),
                json.dumps(
                    metadata or {},
                    sort_keys=True,
                ),
                time.time(),
            ),
        )

        self.conn.commit()

        return self.get_radio(radio_id)

    def get_radio(self, radio_id):
        row = self.conn.execute(
            """
            SELECT *
            FROM telecom_radios
            WHERE radio_id = ?
            """,
            (radio_id,),
        ).fetchone()

        if row is None:
            return None

        result = dict(row)
        result["backhaul_dependency"] = bool(
            result["backhaul_dependency"]
        )
        result["power_dependency"] = bool(
            result["power_dependency"]
        )
        result["metadata"] = json.loads(
            result["metadata"] or "{}"
        )

        return result

    def classify(self, radio_id):
        radio = self.get_radio(radio_id)

        if radio is None:
            raise ValueError(
                f"Unknown radio: {radio_id}"
            )

        return {
            "radio_id": radio["radio_id"],
            "technology": radio["technology"],
            "domain": radio["domain"],
            "role": radio["role"],
            "site_id": radio["site_id"],
            "criticality": radio["criticality"],
            "backhaul_dependency": radio[
                "backhaul_dependency"
            ],
            "power_dependency": radio[
                "power_dependency"
            ],
        }

    def observe(
        self,
        radio_id,
        state="UNKNOWN",
        health_score=None,
        signal_level=None,
        snr=None,
        latency_ms=None,
        packet_loss=None,
        availability=None,
        evidence=None,
        timestamp=None,
    ):
        radio = self.get_radio(radio_id)

        if radio is None:
            raise ValueError(
                f"Unknown radio: {radio_id}"
            )

        state = state.upper()

        if state not in self.STATES:
            raise ValueError(
                f"Invalid state: {state}"
            )

        now = (
            timestamp
            if timestamp is not None
            else time.time()
        )

        observation_id = str(uuid.uuid4())

        self.conn.execute(
            """
            INSERT INTO telecom_radio_observations (
                observation_id,
                radio_id,
                timestamp,
                state,
                health_score,
                signal_level,
                snr,
                latency_ms,
                packet_loss,
                availability,
                evidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation_id,
                radio_id,
                now,
                state,
                health_score,
                signal_level,
                snr,
                latency_ms,
                packet_loss,
                availability,
                json.dumps(
                    evidence or {},
                    sort_keys=True,
                ),
            ),
        )

        previous = self.conn.execute(
            """
            SELECT state
            FROM telecom_radio_observations
            WHERE radio_id = ?
              AND observation_id != ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (
                radio_id,
                observation_id,
            ),
        ).fetchone()

        previous_state = (
            previous["state"]
            if previous is not None
            else None
        )

        if (
            previous_state is not None
            and previous_state != state
        ):
            self._event(
                radio_id=radio_id,
                event_type="RADIO_STATE_CHANGED",
                severity=self._severity_for_state(state),
                previous_state=previous_state,
                new_state=state,
                evidence={
                    "health_score": health_score,
                    "state": state,
                },
                timestamp=now,
            )

        self.conn.commit()

        return {
            "observation_id": observation_id,
            "radio_id": radio_id,
            "technology": radio["technology"],
            "state": state,
            "health_score": health_score,
            "timestamp": now,
        }

    @staticmethod
    def _severity_for_state(state):
        if state == "CRITICAL":
            return "CRITICAL"

        if state in {
            "DEGRADED",
            "OFFLINE",
        }:
            return "WARNING"

        return "INFO"

    def _event(
        self,
        radio_id,
        event_type,
        severity,
        previous_state,
        new_state,
        evidence,
        timestamp,
    ):
        payload = {
            "radio_id": radio_id,
            "event_type": event_type,
            "severity": severity,
            "previous_state": previous_state,
            "new_state": new_state,
            "evidence": evidence or {},
            "timestamp": timestamp,
        }

        evidence_hash = self._hash(payload)

        event_id = str(uuid.uuid4())

        self.conn.execute(
            """
            INSERT INTO telecom_radio_events (
                event_id,
                radio_id,
                timestamp,
                event_type,
                severity,
                previous_state,
                new_state,
                evidence,
                evidence_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                radio_id,
                timestamp,
                event_type,
                severity,
                previous_state,
                new_state,
                json.dumps(
                    evidence or {},
                    sort_keys=True,
                ),
                evidence_hash,
            ),
        )

        return event_id

    def history(self, radio_id):
        rows = self.conn.execute(
            """
            SELECT *
            FROM telecom_radio_observations
            WHERE radio_id = ?
            ORDER BY timestamp ASC
            """,
            (radio_id,),
        ).fetchall()

        return [dict(row) for row in rows]

    def events(self, radio_id=None):
        if radio_id is None:
            rows = self.conn.execute(
                """
                SELECT *
                FROM telecom_radio_events
                ORDER BY timestamp ASC
                """
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT *
                FROM telecom_radio_events
                WHERE radio_id = ?
                ORDER BY timestamp ASC
                """,
                (radio_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def close(self):
        self.conn.close()
