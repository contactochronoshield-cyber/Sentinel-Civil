import hashlib
import json
import os
import sqlite3
import time
import uuid


class RFHealthEngine:
    """
    Evaluates RF infrastructure health from observable telemetry.

    This engine does not claim physical failure without evidence.
    It reports behavior compatible with degradation.
    """

    def evaluate(self, telemetry):
        score = 100
        reasons = []

        snr = telemetry.get("snr")
        noise = telemetry.get("noise")
        rssi = telemetry.get("rssi")
        packet_loss = telemetry.get("packet_loss")
        latency = telemetry.get("latency")
        backhaul = telemetry.get("backhaul_available")
        power = telemetry.get("power_available")
        battery = telemetry.get("backup_battery")

        if snr is not None:
            if snr < 5:
                score -= 30
                reasons.append("snr_critical")
            elif snr < 10:
                score -= 18
                reasons.append("snr_degraded")
            elif snr < 15:
                score -= 8
                reasons.append("snr_reduced")

        if noise is not None:
            if noise >= -70:
                score -= 25
                reasons.append("noise_high")
            elif noise >= -80:
                score -= 12
                reasons.append("noise_increased")

        if rssi is not None:
            if rssi <= -90:
                score -= 25
                reasons.append("signal_weak")
            elif rssi <= -80:
                score -= 12
                reasons.append("signal_reduced")

        if packet_loss is not None:
            if packet_loss >= 10:
                score -= 25
                reasons.append("packet_loss_high")
            elif packet_loss >= 5:
                score -= 12
                reasons.append("packet_loss_increased")

        if latency is not None:
            if latency >= 200:
                score -= 20
                reasons.append("latency_high")
            elif latency >= 120:
                score -= 10
                reasons.append("latency_increased")

        if backhaul is False:
            score -= 30
            reasons.append("backhaul_unavailable")

        if power is False:
            score -= 30
            reasons.append("power_failure")

        if battery is not None:
            if battery < 10:
                score -= 20
                reasons.append("backup_battery_critical")
            elif battery < 25:
                score -= 10
                reasons.append("backup_battery_low")

        score = max(0, min(100, score))

        if score >= 85:
            risk = "NORMAL"
        elif score >= 65:
            risk = "DEGRADED"
        elif score >= 40:
            risk = "WARNING"
        else:
            risk = "CRITICAL"

        return {
            "health_score": score,
            "risk": risk,
            "reasons": reasons,
        }


class RFTrendEngine:
    def analyze(self, history):
        if len(history) < 3:
            return []

        first = history[0]
        last = history[-1]
        trends = []

        def value(item, key):
            return item.get(key)

        first_snr = value(first, "snr")
        last_snr = value(last, "snr")

        if (
            first_snr is not None
            and last_snr is not None
            and last_snr < first_snr - 4
        ):
            trends.append("snr_degradation")

        first_noise = value(first, "noise")
        last_noise = value(last, "noise")

        if (
            first_noise is not None
            and last_noise is not None
            and last_noise > first_noise + 5
        ):
            trends.append("noise_increase")

        first_rssi = value(first, "rssi")
        last_rssi = value(last, "rssi")

        if (
            first_rssi is not None
            and last_rssi is not None
            and last_rssi < first_rssi - 6
        ):
            trends.append("signal_degradation")

        first_loss = value(first, "packet_loss")
        last_loss = value(last, "packet_loss")

        if (
            first_loss is not None
            and last_loss is not None
            and last_loss > max(first_loss * 2, first_loss + 1)
        ):
            trends.append("packet_loss_increase")

        first_latency = value(first, "latency")
        last_latency = value(last, "latency")

        if (
            first_latency is not None
            and last_latency is not None
            and last_latency > first_latency * 1.5
        ):
            trends.append("latency_increase")

        backhaul_changes = [
            value(item, "backhaul_available")
            for item in history
            if value(item, "backhaul_available") is not None
        ]

        if len(set(backhaul_changes)) > 1:
            trends.append("backhaul_instability")

        return trends


class RFInfrastructureMonitor:
    VERSION = "1.0.0"

    def __init__(self, db_path=None, enabled=False):
        self.enabled = bool(enabled)
        self.db_path = db_path or os.path.expanduser(
            "~/.sentinel/rf-infrastructure.db"
        )

        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        self.health_engine = RFHealthEngine()
        self.trend_engine = RFTrendEngine()

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        self._create_schema()

    def _create_schema(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS rf_sites (
                site_id TEXT PRIMARY KEY,
                name TEXT,
                site_type TEXT,
                authorized INTEGER DEFAULT 0,
                status TEXT,
                first_seen TEXT,
                last_seen TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS rf_components (
                component_id TEXT PRIMARY KEY,
                site_id TEXT,
                component_type TEXT,
                display_name TEXT,
                manufacturer TEXT,
                model TEXT,
                serial_hash TEXT,
                authorized INTEGER DEFAULT 0,
                status TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS rf_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_id TEXT,
                timestamp REAL,
                snr REAL,
                noise REAL,
                rssi REAL,
                packet_loss REAL,
                latency REAL,
                backhaul_available INTEGER,
                power_available INTEGER,
                backup_battery REAL,
                coverage_indicator REAL,
                temperature REAL,
                humidity REAL
            );

            CREATE TABLE IF NOT EXISTS rf_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_id TEXT,
                timestamp REAL,
                health_score INTEGER,
                risk TEXT,
                reasons TEXT,
                trends TEXT
            );

            CREATE TABLE IF NOT EXISTS rf_events (
                event_id TEXT PRIMARY KEY,
                site_id TEXT,
                component_id TEXT,
                event_type TEXT,
                severity TEXT,
                timestamp REAL,
                payload TEXT,
                previous_hash TEXT,
                event_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS rf_maintenance (
                maintenance_id TEXT PRIMARY KEY,
                site_id TEXT,
                component_id TEXT,
                status TEXT,
                reason TEXT,
                started_at REAL,
                completed_at REAL
            );

            CREATE INDEX IF NOT EXISTS idx_rf_obs_component
                ON rf_observations(component_id);

            CREATE INDEX IF NOT EXISTS idx_rf_events_component
                ON rf_events(component_id);
            """
        )
        self.conn.commit()

    @staticmethod
    def hash_identifier(value):
        if value is None:
            return None

        return hashlib.sha256(
            str(value).encode("utf-8")
        ).hexdigest()

    def register_site(
        self,
        site_id,
        name=None,
        site_type=None,
        authorized=False,
    ):
        now = time.time()

        self.conn.execute(
            """
            INSERT OR IGNORE INTO rf_sites (
                site_id,
                name,
                site_type,
                authorized,
                status,
                first_seen,
                last_seen,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                site_id,
                name,
                site_type,
                int(bool(authorized)),
                "AUTHORIZED" if authorized else "UNAUTHORIZED",
                now,
                now,
                now,
                now,
            ),
        )

        self.conn.execute(
            """
            UPDATE rf_sites
            SET last_seen = ?, updated_at = ?
            WHERE site_id = ?
            """,
            (now, now, site_id),
        )

        self.conn.commit()

    def register_component(
        self,
        component_id,
        site_id,
        component_type,
        display_name=None,
        manufacturer=None,
        model=None,
        serial=None,
        authorized=False,
    ):
        now = time.time()

        self.conn.execute(
            """
            INSERT OR REPLACE INTO rf_components (
                component_id,
                site_id,
                component_type,
                display_name,
                manufacturer,
                model,
                serial_hash,
                authorized,
                status,
                created_at,
                updated_at
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                COALESCE(
                    (
                        SELECT created_at
                        FROM rf_components
                        WHERE component_id = ?
                    ),
                    ?
                ),
                ?
            )
            """,
            (
                component_id,
                site_id,
                component_type,
                display_name,
                manufacturer,
                model,
                self.hash_identifier(serial),
                int(bool(authorized)),
                "AUTHORIZED" if authorized else "UNAUTHORIZED",
                component_id,
                now,
                now,
            ),
        )

        self.conn.commit()

    def _history(self, component_id):
        rows = self.conn.execute(
            """
            SELECT
                timestamp,
                snr,
                noise,
                rssi,
                packet_loss,
                latency,
                backhaul_available,
                power_available,
                backup_battery,
                coverage_indicator,
                temperature,
                humidity
            FROM rf_observations
            WHERE component_id = ?
            ORDER BY timestamp ASC
            """,
            (component_id,),
        ).fetchall()

        return [dict(row) for row in rows]

    def _last_event_hash(self, site_id, component_id):
        row = self.conn.execute(
            """
            SELECT event_hash
            FROM rf_events
            WHERE site_id = ? AND component_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (site_id, component_id),
        ).fetchone()

        return row["event_hash"] if row else ""

    def emit_event(
        self,
        site_id,
        component_id,
        event_type,
        severity,
        payload=None,
    ):
        timestamp = time.time()
        event_id = str(uuid.uuid4())
        previous_hash = self._last_event_hash(
            site_id,
            component_id,
        )

        event_payload = payload or {}

        material = json.dumps(
            {
                "event_id": event_id,
                "site_id": site_id,
                "component_id": component_id,
                "event_type": event_type,
                "severity": severity,
                "timestamp": timestamp,
                "payload": event_payload,
                "previous_hash": previous_hash,
            },
            sort_keys=True,
        )

        event_hash = hashlib.sha256(
            material.encode("utf-8")
        ).hexdigest()

        self.conn.execute(
            """
            INSERT INTO rf_events (
                event_id,
                site_id,
                component_id,
                event_type,
                severity,
                timestamp,
                payload,
                previous_hash,
                event_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                site_id,
                component_id,
                event_type,
                severity,
                timestamp,
                json.dumps(event_payload, sort_keys=True),
                previous_hash,
                event_hash,
            ),
        )

        self.conn.commit()

        return event_id

    def observe(self, component_id, telemetry):
        history = self._history(component_id)

        health = self.health_engine.evaluate(telemetry)

        history_with_current = history + [
            {
                **telemetry,
                "timestamp": time.time(),
            }
        ]

        trends = self.trend_engine.analyze(
            history_with_current
        )

        self.conn.execute(
            """
            INSERT INTO rf_observations (
                component_id,
                timestamp,
                snr,
                noise,
                rssi,
                packet_loss,
                latency,
                backhaul_available,
                power_available,
                backup_battery,
                coverage_indicator,
                temperature,
                humidity
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                component_id,
                time.time(),
                telemetry.get("snr"),
                telemetry.get("noise"),
                telemetry.get("rssi"),
                telemetry.get("packet_loss"),
                telemetry.get("latency"),
                None
                if telemetry.get("backhaul_available") is None
                else int(bool(telemetry.get("backhaul_available"))),
                None
                if telemetry.get("power_available") is None
                else int(bool(telemetry.get("power_available"))),
                telemetry.get("backup_battery"),
                telemetry.get("coverage_indicator"),
                telemetry.get("temperature"),
                telemetry.get("humidity"),
            ),
        )

        self.conn.execute(
            """
            INSERT INTO rf_health (
                component_id,
                timestamp,
                health_score,
                risk,
                reasons,
                trends
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                component_id,
                time.time(),
                health["health_score"],
                health["risk"],
                json.dumps(health["reasons"]),
                json.dumps(trends),
            ),
        )

        self.conn.commit()

        recovery = self.recovery_status(component_id)

        return {
            **health,
            "trends": trends,
            "recovery": recovery,
        }

    def detect_failure_precursor(self, component_id):
        history = self._history(component_id)

        if len(history) < 8:
            stage = (
                "INSUFFICIENT_HISTORY"
                if len(history) < 5
                else "OBSERVING"
            )

            return {
                "precursor": False,
                "confidence": 0.0,
                "reasons": ["insufficient_history"],
                "stage": stage,
                "observations": len(history),
            }

        trends = self.trend_engine.analyze(history)

        reasons = []

        if "snr_degradation" in trends:
            reasons.append("snr_degradation")

        if "noise_increase" in trends:
            reasons.append("noise_increase")

        if "signal_degradation" in trends:
            reasons.append("signal_degradation")

        if "packet_loss_increase" in trends:
            reasons.append("packet_loss_increase")

        if "latency_increase" in trends:
            reasons.append("latency_increase")

        if "backhaul_instability" in trends:
            reasons.append("backhaul_instability")

        precursor = len(reasons) >= 2

        confidence = min(
            0.95,
            0.25
            + (0.10 * len(reasons))
            + (0.02 * min(len(history), 10)),
        )

        if not precursor:
            confidence = 0.0

        return {
            "precursor": precursor,
            "confidence": round(confidence, 3),
            "reasons": reasons,
            "stage": "PRECURSOR" if precursor else "OBSERVING",
            "observations": len(history),
        }

    def classify_infrastructure_event(
        self,
        telemetry,
        trends=None,
        history_count=0,
    ):
        """
        Classifies observable infrastructure behavior.

        The classifier deliberately avoids claiming a physical
        component failure unless the available evidence supports
        a more specific interpretation.
        """

        trends = trends or []

        if telemetry.get("power_available") is False:
            return "POWER_FAILURE"

        if telemetry.get("backhaul_available") is False:
            return "REPEATER_BACKHAUL_FAILURE"

        if telemetry.get("backup_battery") is not None:
            if telemetry["backup_battery"] < 10:
                return "BACKUP_BATTERY_LOW"

        # Noise/SNR degradation alone does not prove interference.
        # An explicit authorized RF indicator is required before
        # classifying the observation as an interference anomaly.
        rf_interference_evidence = (
            telemetry.get("rf_interference_indicator") is True
            and "noise_increase" in trends
            and "snr_degradation" in trends
        )

        if history_count >= 8 and rf_interference_evidence:
            return "RF_INTERFERENCE_ANOMALY"

        if (
            "signal_degradation" in trends
            and "snr_degradation" in trends
            and "coverage_degradation" in trends
        ):
            return "COVERAGE_DEGRADATION"

        if "backhaul_instability" in trends:
            return "REPEATER_DEGRADED"

        if (
            "snr_degradation" in trends
            or "signal_degradation" in trends
            or "noise_increase" in trends
            or "packet_loss_increase" in trends
            or "latency_increase" in trends
        ):
            return "RF_INFRASTRUCTURE_DEGRADATION"

        return None

    def recovery_status(self, component_id):
        """
        Determines whether the component is recovering based on
        recent health observations.

        This does not claim that a physical repair occurred.
        It only reports recovery of observed service indicators.
        """

        rows = self.conn.execute(
            """
            SELECT health_score, risk
            FROM rf_health
            WHERE component_id = ?
            ORDER BY timestamp DESC
            LIMIT 4
            """,
            (component_id,),
        ).fetchall()

        if len(rows) < 3:
            return {
                "state": "NO_RECOVERY",
                "observations": len(rows),
                "reason": "insufficient_history",
            }

        scores = [row["health_score"] for row in rows]
        risks = [row["risk"] for row in rows]

        latest = scores[0]
        previous = scores[1]

        if (
            latest >= 85
            and previous < 85
        ):
            return {
                "state": "RECOVERED",
                "observations": len(rows),
                "health_score": latest,
                "previous_score": previous,
            }

        if latest > previous:
            return {
                "state": "RECOVERING",
                "observations": len(rows),
                "health_score": latest,
                "previous_score": previous,
                "risk": risks[0],
            }

        return {
            "state": "NO_RECOVERY",
            "observations": len(rows),
            "health_score": latest,
            "previous_score": previous,
            "risk": risks[0],
        }

    def start_maintenance(
        self,
        site_id,
        component_id=None,
        reason=None,
    ):
        maintenance_id = str(uuid.uuid4())

        self.conn.execute(
            """
            INSERT INTO rf_maintenance (
                maintenance_id,
                site_id,
                component_id,
                status,
                reason,
                started_at,
                completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                maintenance_id,
                site_id,
                component_id,
                "ACTIVE",
                reason,
                time.time(),
            ),
        )

        self.conn.commit()

        self.emit_event(
            site_id,
            component_id,
            "MAINTENANCE_STARTED",
            "INFO",
            {"reason": reason},
        )

        return maintenance_id

    def complete_maintenance(self, maintenance_id):
        row = self.conn.execute(
            """
            SELECT site_id, component_id
            FROM rf_maintenance
            WHERE maintenance_id = ?
            """,
            (maintenance_id,),
        ).fetchone()

        if row is None:
            return False

        now = time.time()

        self.conn.execute(
            """
            UPDATE rf_maintenance
            SET status = ?, completed_at = ?
            WHERE maintenance_id = ?
            """,
            (
                "COMPLETED",
                now,
                maintenance_id,
            ),
        )

        self.conn.commit()

        self.emit_event(
            row["site_id"],
            row["component_id"],
            "MAINTENANCE_COMPLETED",
            "INFO",
            {},
        )

        return True

    def get_events(self, site_id=None, component_id=None):
        if site_id and component_id:
            rows = self.conn.execute(
                """
                SELECT *
                FROM rf_events
                WHERE site_id = ? AND component_id = ?
                ORDER BY timestamp ASC
                """,
                (site_id, component_id),
            ).fetchall()
        elif site_id:
            rows = self.conn.execute(
                """
                SELECT *
                FROM rf_events
                WHERE site_id = ?
                ORDER BY timestamp ASC
                """,
                (site_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT *
                FROM rf_events
                ORDER BY timestamp ASC
                """
            ).fetchall()

        return [dict(row) for row in rows]

    def close(self):
        self.conn.close()


__all__ = [
    "RFHealthEngine",
    "RFTrendEngine",
    "RFInfrastructureMonitor",
]
