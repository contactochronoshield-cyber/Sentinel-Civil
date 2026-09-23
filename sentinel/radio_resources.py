"""
Sentinel Civil-Core
Radio Resource Intelligence

Passive and authorized telemetry only.

Tracks:
- data usage
- battery consumption
- Bluetooth activity
- Wi-Fi activity
- cellular activity
- latency
- packet loss
- connection duration

Does not capture:
- audio
- messages
- communication content
- private traffic payloads
"""

import sqlite3
import uuid
from datetime import datetime, timezone


class RadioResourceEngine:
    VERSION = "1.0.0"

    def __init__(self, db_path=":memory:", enabled=False):
        self.db_path = db_path
        self.enabled = bool(enabled)

        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row

        self._create_schema()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _clamp(value, minimum=0, maximum=100):
        return max(minimum, min(maximum, int(value)))

    def _create_schema(self):
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS radio_resource_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                radio_id TEXT NOT NULL,

                data_rx_bytes INTEGER,
                data_tx_bytes INTEGER,
                data_total_bytes INTEGER,

                battery_percent INTEGER,

                bluetooth_active INTEGER,
                bluetooth_connections INTEGER,

                wifi_active INTEGER,
                cellular_active INTEGER,

                latency_ms REAL,
                packet_loss_percent REAL,

                connection_seconds INTEGER,

                resource_score INTEGER,
                risk TEXT,

                evidence TEXT
            )
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS radio_resource_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                radio_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                evidence TEXT
            )
            """
        )

        self.db.commit()

    @staticmethod
    def _risk(score):
        if score >= 85:
            return "NORMAL"

        if score >= 65:
            return "DEGRADED"

        if score >= 40:
            return "WARNING"

        return "CRITICAL"

    def evaluate(self, telemetry):
        if not self.enabled:
            return {
                "enabled": False,
                "radio_id": telemetry.get("radio_id"),
            }

        radio_id = telemetry.get("radio_id")

        if not radio_id:
            raise ValueError("radio_id is required")

        score = 100
        evidence = []
        events = []

        battery = telemetry.get("battery_percent")

        if battery is not None:
            if battery < 10:
                score -= 30
                evidence.append("battery_critical")
                events.append(
                    ("RADIO_BATTERY_DRAIN_ANOMALY", "CRITICAL")
                )
            elif battery < 20:
                score -= 20
                evidence.append("battery_degraded")
            elif battery < 35:
                score -= 8
                evidence.append("battery_low")

        latency = telemetry.get("latency_ms")

        if latency is not None:
            if latency >= 200:
                score -= 25
                evidence.append("latency_critical")
            elif latency >= 120:
                score -= 15
                evidence.append("latency_degraded")
            elif latency >= 80:
                score -= 7
                evidence.append("latency_elevated")

        packet_loss = telemetry.get("packet_loss_percent")

        if packet_loss is not None:
            if packet_loss >= 10:
                score -= 25
                evidence.append("packet_loss_critical")
            elif packet_loss >= 5:
                score -= 15
                evidence.append("packet_loss_degraded")
            elif packet_loss >= 1:
                score -= 5
                evidence.append("packet_loss_elevated")

        bluetooth_active = telemetry.get("bluetooth_active")

        if bluetooth_active:
            bluetooth_connections = telemetry.get(
                "bluetooth_connections",
                0
            )

            if bluetooth_connections >= 4:
                evidence.append("bluetooth_activity_high")

        data_total = telemetry.get("data_total_bytes")

        if data_total is not None:
            if data_total >= 500 * 1024 * 1024:
                evidence.append("high_data_usage")

        score = self._clamp(score)
        risk = self._risk(score)

        observation_id = str(uuid.uuid4())

        self.db.execute(
            """
            INSERT INTO radio_resource_observations (
                observation_id,
                timestamp,
                radio_id,
                data_rx_bytes,
                data_tx_bytes,
                data_total_bytes,
                battery_percent,
                bluetooth_active,
                bluetooth_connections,
                wifi_active,
                cellular_active,
                latency_ms,
                packet_loss_percent,
                connection_seconds,
                resource_score,
                risk,
                evidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation_id,
                self._now(),
                radio_id,
                telemetry.get("data_rx_bytes"),
                telemetry.get("data_tx_bytes"),
                telemetry.get("data_total_bytes"),
                battery,
                int(bool(bluetooth_active))
                if bluetooth_active is not None else None,
                telemetry.get("bluetooth_connections"),
                int(bool(telemetry.get("wifi_active")))
                if telemetry.get("wifi_active") is not None else None,
                int(bool(telemetry.get("cellular_active")))
                if telemetry.get("cellular_active") is not None else None,
                latency,
                packet_loss,
                telemetry.get("connection_seconds"),
                score,
                risk,
                ",".join(sorted(set(evidence))),
            ),
        )

        for event_type, severity in events:
            self.db.execute(
                """
                INSERT INTO radio_resource_events (
                    event_id,
                    timestamp,
                    radio_id,
                    event_type,
                    severity,
                    evidence
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    self._now(),
                    radio_id,
                    event_type,
                    severity,
                    "battery drain / resource degradation",
                ),
            )

        self.db.commit()

        return {
            "enabled": True,
            "observation_id": observation_id,
            "radio_id": radio_id,
            "resource_score": score,
            "risk": risk,
            "evidence": sorted(set(evidence)),
            "events": [
                {
                    "event_type": event_type,
                    "severity": severity,
                }
                for event_type, severity in events
            ],
        }

    def history(self, radio_id, limit=20):
        rows = self.db.execute(
            """
            SELECT *
            FROM radio_resource_observations
            WHERE radio_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (radio_id, int(limit)),
        ).fetchall()

        return [dict(row) for row in rows]

    def events(self, radio_id=None, limit=50):
        if radio_id:
            rows = self.db.execute(
                """
                SELECT *
                FROM radio_resource_events
                WHERE radio_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (radio_id, int(limit)),
            ).fetchall()
        else:
            rows = self.db.execute(
                """
                SELECT *
                FROM radio_resource_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()

        return [dict(row) for row in rows]

    def close(self):
        self.db.close()
