import hashlib
import json
import os
import sqlite3
import statistics
import subprocess
import time
import uuid

from .radios.generic import GenericBluetoothAdapter


class RadioHealthEngine:
    """
    Passive radio health and precursor engine.

    No RF transmission.
    No communication interception.
    No audio capture.
    """

    def __init__(self):
        pass

    def calculate(
        self,
        telemetry,
        history=None,
    ):
        history = history or []

        score = 100
        reasons = []

        battery = telemetry.get("battery_pct")
        rssi = telemetry.get("rssi_dbm")
        latency = telemetry.get("latency_ms")
        loss = telemetry.get("packet_loss_pct")
        internet = telemetry.get(
            "internet_reachable"
        )

        if battery is not None:
            if battery < 10:
                score -= 30
                reasons.append("battery_critical")
            elif battery < 20:
                score -= 20
                reasons.append("battery_low")
            elif battery < 35:
                score -= 8
                reasons.append("battery_degraded")

        if rssi is not None:
            if rssi <= -90:
                score -= 30
                reasons.append("signal_critical")
            elif rssi <= -80:
                score -= 20
                reasons.append("signal_weak")
            elif rssi <= -70:
                score -= 8
                reasons.append("signal_degraded")

        if latency is not None:
            if latency >= 200:
                score -= 25
                reasons.append("latency_critical")
            elif latency >= 120:
                score -= 15
                reasons.append("latency_high")
            elif latency >= 80:
                score -= 7
                reasons.append("latency_increased")

        if loss is not None:
            if loss >= 10:
                score -= 25
                reasons.append("packet_loss_critical")
            elif loss >= 5:
                score -= 15
                reasons.append("packet_loss_high")
            elif loss >= 1:
                score -= 5
                reasons.append("packet_loss_increased")

        if internet is False:
            score -= 20
            reasons.append("internet_unreachable")

        score = max(
            0,
            min(100, score)
        )

        if score >= 85:
            risk = "NORMAL"
        elif score >= 65:
            risk = "DEGRADED"
        elif score >= 40:
            risk = "WARNING"
        else:
            risk = "CRITICAL"

        precursor = self._failure_precursor(
            telemetry,
            history,
        )

        if precursor["precursor"]:
            reasons.extend(
                precursor["reasons"]
            )

        return {
            "health_score": score,
            "risk": risk,
            "precursor": precursor["precursor"],
            "precursor_reasons": precursor["reasons"],
            "reasons": sorted(set(reasons)),
        }

    def _failure_precursor(
        self,
        telemetry,
        history,
    ):
        if len(history) < 3:
            return {
                "precursor": False,
                "reasons": [],
            }

        reasons = []

        rssi_values = [
            x.get("rssi_dbm")
            for x in history
            if isinstance(
                x.get("rssi_dbm"),
                (int, float)
            )
        ]

        battery_values = [
            x.get("battery_pct")
            for x in history
            if isinstance(
                x.get("battery_pct"),
                (int, float)
            )
        ]

        latency_values = [
            x.get("latency_ms")
            for x in history
            if isinstance(
                x.get("latency_ms"),
                (int, float)
            )
        ]

        if len(rssi_values) >= 3:
            if rssi_values[-1] < rssi_values[0] - 12:
                reasons.append(
                    "signal_drop_fast"
                )

        if len(battery_values) >= 3:
            if (
                battery_values[-1]
                < battery_values[0] - 10
            ):
                reasons.append(
                    "rapid_battery_degradation"
                )

        if len(latency_values) >= 3:
            if (
                latency_values[-1]
                > latency_values[0] * 2
            ):
                reasons.append(
                    "increasing_latency"
                )

        if telemetry.get(
            "internet_reachable"
        ) is False:
            reasons.append(
                "internet_degraded"
            )

        return {
            "precursor": len(reasons) >= 2,
            "reasons": reasons,
        }


class RadioTrendEngine:

    def analyze(self, history):
        result = {
            "battery_decline": False,
            "signal_decline": False,
            "latency_increase": False,
            "packet_loss_increase": False,
            "availability_decline": False,
            "connection_instability": False,
        }

        if len(history) < 3:
            return result

        def values(key):
            return [
                item.get(key)
                for item in history
                if isinstance(
                    item.get(key),
                    (int, float)
                )
            ]

        rssi = values("rssi_dbm")
        battery = values("battery_pct")
        latency = values("latency_ms")
        loss = values("packet_loss_pct")

        if len(battery) >= 3:
            result["battery_decline"] = (
                battery[-1]
                < battery[0] - 5
            )

        if len(rssi) >= 3:
            result["signal_decline"] = (
                rssi[-1]
                < rssi[0] - 6
            )

        if len(latency) >= 3:
            result["latency_increase"] = (
                latency[-1]
                > latency[0] * 1.5
            )

        if len(loss) >= 3:
            result["packet_loss_increase"] = (
                loss[-1]
                > max(
                    loss[0] * 2,
                    loss[0] + 1
                )
            )

        connected = [
            item.get("bluetooth_connected")
            for item in history
            if "bluetooth_connected" in item
        ]

        if len(connected) >= 3:
            changes = sum(
                connected[i]
                != connected[i - 1]
                for i in range(1, len(connected))
            )

            result["connection_instability"] = (
                changes >= 2
            )

        return result


class RadioMonitor:
    """
    Sentinel Radio Intelligence.

    Optional passive monitoring module.
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        db_path,
        node_name="sentinel-node",
        enabled=False,
        privacy_mode=True,
    ):
        self.db_path = os.path.abspath(
            os.path.expanduser(db_path)
        )

        self.node_name = node_name
        self.enabled = bool(enabled)
        self.privacy_mode = bool(
            privacy_mode
        )

        self.health_engine = (
            RadioHealthEngine()
        )

        self.trend_engine = (
            RadioTrendEngine()
        )

        self.adapter = (
            GenericBluetoothAdapter()
        )

        self._init_db()

    def _connect(self):
        directory = os.path.dirname(
            self.db_path
        )

        if directory:
            os.makedirs(
                directory,
                exist_ok=True
            )

        conn = sqlite3.connect(
            self.db_path
        )

        conn.row_factory = sqlite3.Row

        return conn

    def _init_db(self):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS radio_inventory (
                radio_id TEXT PRIMARY KEY,
                display_name TEXT,
                manufacturer TEXT,
                model TEXT,
                serial_hash TEXT,
                firmware TEXT,
                bluetooth_identifier_hash TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                authorized INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                vendor_adapter TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS radio_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                radio_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                telemetry_json TEXT NOT NULL,
                health_score INTEGER,
                risk TEXT,
                trend_json TEXT NOT NULL,
                precursor INTEGER NOT NULL DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS radio_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                radio_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT,
                event_hash TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS radio_accessories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                radio_id TEXT NOT NULL,
                accessory_id TEXT NOT NULL,
                accessory_type TEXT,
                connected INTEGER NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS radio_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                radio_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                health_score INTEGER NOT NULL,
                risk TEXT NOT NULL,
                reasons_json TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS radio_anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                radio_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                anomaly_type TEXT NOT NULL,
                confidence REAL,
                reasons_json TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def _now(self):
        return time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    def _hash_identifier(self, value):
        if not value:
            return None

        return hashlib.sha256(
            str(value).encode("utf-8")
        ).hexdigest()

    def _event_hash(
        self,
        payload,
        previous_hash,
    ):
        data = {
            "payload": payload,
            "previous_hash": previous_hash,
        }

        canonical = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

    def _last_event_hash(self):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            SELECT event_hash
            FROM radio_events
            ORDER BY id DESC
            LIMIT 1
        """)

        row = cur.fetchone()
        conn.close()

        if row is None:
            return None

        return row["event_hash"]

    def emit_event(
        self,
        radio_id,
        event_type,
        severity,
        payload=None,
    ):
        payload = payload or {}
        timestamp = self._now()

        event = {
            "node_name": self.node_name,
            "radio_id": radio_id,
            "event_type": event_type,
            "severity": severity,
            "timestamp": timestamp,
            "payload": payload,
        }

        previous_hash = (
            self._last_event_hash()
        )

        event_hash = self._event_hash(
            event,
            previous_hash,
        )

        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO radio_events (
                radio_id,
                event_type,
                severity,
                timestamp,
                payload_json,
                previous_hash,
                event_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            radio_id,
            event_type,
            severity,
            timestamp,
            json.dumps(
                payload,
                sort_keys=True
            ),
            previous_hash,
            event_hash,
        ))

        conn.commit()
        conn.close()

        return {
            "event_type": event_type,
            "severity": severity,
            "previous_hash": previous_hash,
            "event_hash": event_hash,
            "timestamp": timestamp,
        }

    def discover(self):
        """
        Discover nearby Bluetooth devices only.

        Uses Termux:API when available.
        No pairing, connection or RF interaction is attempted.
        """

        if not self.enabled:
            return []

        command = (
            "termux-bluetooth-scaninfo"
        )

        try:
            result = subprocess.run(
                [command],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )

        except (
            FileNotFoundError,
            subprocess.SubprocessError,
            OSError,
        ):
            return []

        if result.returncode != 0:
            return []

        try:
            data = json.loads(
                result.stdout
            )

        except json.JSONDecodeError:
            return []

        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, list):
            return []

        devices = []

        for item in data:
            if not isinstance(item, dict):
                continue

            devices.append(
                self._normalize_device(item)
            )

        return devices

    def _normalize_device(self, device):
        identifier = (
            device.get("address")
            or device.get("mac")
            or device.get("id")
        )

        name = (
            device.get("name")
            or device.get("device_name")
            or "Unknown Bluetooth Device"
        )

        return {
            "display_name": name,
            "manufacturer": device.get(
                "manufacturer"
            ),
            "model": device.get("model"),
            "firmware": device.get("firmware"),
            "transport": "BLE"
            if device.get("ble")
            else "Bluetooth",
            "rssi_dbm": device.get(
                "rssi"
            ),
            "bluetooth_identifier_hash":
                self._hash_identifier(
                    identifier
                ),
            "authorized": False,
            "raw_capabilities": {
                key: value
                for key, value in device.items()
                if key in (
                    "uuids",
                    "services",
                    "ble",
                    "gatt",
                )
            },
        }

    def _radio_id(self, device):
        identity = (
            device.get(
                "bluetooth_identifier_hash"
            )
            or device.get("display_name")
            or uuid.uuid4().hex
        )

        return (
            "radio-"
            + hashlib.sha256(
                identity.encode("utf-8")
            ).hexdigest()[:16]
        )

    def register_device(
        self,
        device,
        authorized=False,
    ):
        radio_id = self._radio_id(
            device
        )

        timestamp = self._now()

        existing = self.get_radio(
            radio_id
        )

        if existing:
            first_seen = existing[
                "first_seen"
            ]
        else:
            first_seen = timestamp

        status = (
            "AUTHORIZED"
            if authorized
            else "UNAUTHORIZED"
        )

        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO radio_inventory (
                radio_id,
                display_name,
                manufacturer,
                model,
                serial_hash,
                firmware,
                bluetooth_identifier_hash,
                first_seen,
                last_seen,
                authorized,
                status,
                vendor_adapter,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(radio_id)
            DO UPDATE SET
                display_name = excluded.display_name,
                manufacturer = excluded.manufacturer,
                model = excluded.model,
                firmware = excluded.firmware,
                last_seen = excluded.last_seen,
                authorized = excluded.authorized,
                status = excluded.status,
                updated_at = excluded.updated_at
        """, (
            radio_id,
            device.get("display_name"),
            device.get("manufacturer"),
            device.get("model"),
            self._hash_identifier(
                device.get("serial")
            ),
            device.get("firmware"),
            device.get(
                "bluetooth_identifier_hash"
            ),
            first_seen,
            timestamp,
            int(bool(authorized)),
            status,
            self.adapter.name,
            timestamp,
            timestamp,
        ))

        conn.commit()
        conn.close()

        return radio_id

    def get_radio(self, radio_id):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM radio_inventory
            WHERE radio_id = ?
        """, (radio_id,))

        row = cur.fetchone()
        conn.close()

        if row is None:
            return None

        return dict(row)

    def get_history(
        self,
        radio_id,
        limit=50,
    ):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            SELECT telemetry_json
            FROM radio_observations
            WHERE radio_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (
            radio_id,
            limit,
        ))

        rows = cur.fetchall()
        conn.close()

        result = []

        for row in reversed(rows):
            try:
                result.append(
                    json.loads(
                        row["telemetry_json"]
                    )
                )
            except json.JSONDecodeError:
                pass

        return result

    def observe(
        self,
        radio_id,
        telemetry,
    ):
        radio = self.get_radio(
            radio_id
        )

        if radio is None:
            raise ValueError(
                "Unknown radio_id"
            )

        history = self.get_history(
            radio_id
        )

        health = (
            self.health_engine.calculate(
                telemetry,
                history,
            )
        )

        trend = (
            self.trend_engine.analyze(
                history + [telemetry]
            )
        )

        timestamp = self._now()

        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO radio_observations (
                radio_id,
                timestamp,
                telemetry_json,
                health_score,
                risk,
                trend_json,
                precursor
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            radio_id,
            timestamp,
            json.dumps(
                telemetry,
                sort_keys=True
            ),
            health["health_score"],
            health["risk"],
            json.dumps(
                trend,
                sort_keys=True
            ),
            int(
                health["precursor"]
            ),
        ))

        cur.execute("""
            INSERT INTO radio_health (
                radio_id,
                timestamp,
                health_score,
                risk,
                reasons_json
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            radio_id,
            timestamp,
            health["health_score"],
            health["risk"],
            json.dumps(
                health["reasons"],
                sort_keys=True
            ),
        ))

        conn.commit()
        conn.close()

        if health["precursor"]:
            self.emit_event(
                radio_id,
                "RADIO_FAILURE_PRECURSOR",
                "WARNING",
                {
                    "health_score":
                        health["health_score"],
                    "reasons":
                        health["precursor_reasons"],
                },
            )

        if health["risk"] != "NORMAL":
            self.emit_event(
                radio_id,
                "RADIO_HEALTH_CHANGED",
                health["risk"],
                {
                    "health_score":
                        health["health_score"],
                    "reasons":
                        health["reasons"],
                },
            )

        return {
            "radio_id": radio_id,
            "timestamp": timestamp,
            **health,
            "trend": trend,
        }

    def maintenance_candidate(
        self,
        radio_id,
    ):
        history = self.get_history(
            radio_id,
            limit=12,
        )

        if len(history) < 5:
            return {
                "maintenance_candidate": False,
                "confidence": 0.0,
                "reasons": [
                    "insufficient_history"
                ],
            }

        trend = (
            self.trend_engine.analyze(
                history
            )
        )

        reasons = [
            key
            for key, value in trend.items()
            if value
        ]

        confidence = min(
            0.95,
            0.50
            + (
                len(reasons) * 0.10
            )
            + (
                min(len(history), 10)
                * 0.02
            )
        )

        return {
            "maintenance_candidate":
                len(reasons) >= 2,
            "confidence":
                round(confidence, 2),
            "reasons": reasons,
        }

    def list_radios(self):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM radio_inventory
            ORDER BY radio_id
        """)

        rows = cur.fetchall()
        conn.close()

        return [
            dict(row)
            for row in rows
        ]

    def get_events(
        self,
        radio_id=None,
        limit=100,
    ):
        conn = self._connect()
        cur = conn.cursor()

        if radio_id:
            cur.execute("""
                SELECT *
                FROM radio_events
                WHERE radio_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (
                radio_id,
                limit,
            ))
        else:
            cur.execute("""
                SELECT *
                FROM radio_events
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))

        rows = cur.fetchall()
        conn.close()

        return [
            dict(row)
            for row in rows
        ]


__all__ = [
    "RadioMonitor",
    "RadioHealthEngine",
    "RadioTrendEngine",
]
