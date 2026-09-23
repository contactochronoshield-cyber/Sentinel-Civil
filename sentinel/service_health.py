"""
Sentinel Civil-Core
Service Health Engine

Aggregates radio, RF, site and network evidence into a
communication-service health state.

This module:
- does not transmit RF
- does not intercept communications
- does not capture audio
- does not bypass authentication
- does not infer causality from correlation alone

Health score is an operational indicator, not a certainty measure.
"""

import sqlite3
import uuid
from datetime import datetime, timezone


class ServiceHealthEngine:
    VERSION = "1.0.0"

    def __init__(self, db_path=":memory:", enabled=False):
        self.db_path = db_path
        self.enabled = bool(enabled)
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS service_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                service_id TEXT NOT NULL,
                health_score INTEGER NOT NULL,
                risk TEXT NOT NULL,
                radio_health INTEGER,
                rf_health INTEGER,
                site_health INTEGER,
                backhaul_health INTEGER,
                vpn_health INTEGER,
                internet_health INTEGER,
                evidence TEXT
            )
            """
        )

        self.db.commit()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _clamp(value, minimum=0, maximum=100):
        return max(minimum, min(maximum, int(value)))

    @staticmethod
    def _risk(score):
        if score >= 85:
            return "NORMAL"

        if score >= 65:
            return "DEGRADED"

        if score >= 40:
            return "WARNING"

        return "CRITICAL"

    @staticmethod
    def _component_score(value):
        if value is None:
            return None

        try:
            return max(0, min(100, int(value)))
        except (TypeError, ValueError):
            return None

    def evaluate(
        self,
        service_id,
        radio_health=None,
        rf_health=None,
        site_health=None,
        backhaul_health=None,
        vpn_health=None,
        internet_health=None,
        evidence=None,
    ):
        if not self.enabled:
            return {
                "enabled": False,
                "service_id": service_id,
            }

        components = {
            "radio_health": self._component_score(radio_health),
            "rf_health": self._component_score(rf_health),
            "site_health": self._component_score(site_health),
            "backhaul_health": self._component_score(backhaul_health),
            "vpn_health": self._component_score(vpn_health),
            "internet_health": self._component_score(internet_health),
        }

        available = [
            value
            for value in components.values()
            if value is not None
        ]

        if not available:
            score = 100
            evidence_list = ["insufficient_component_data"]
        else:
            score = round(sum(available) / len(available))
            evidence_list = list(evidence or [])

        # Explicit hard failures represent service-impacting evidence.
        if backhaul_health == 0:
            evidence_list.append("backhaul_unavailable")

        if vpn_health == 0:
            evidence_list.append("vpn_unavailable")

        if internet_health == 0:
            evidence_list.append("internet_unavailable")

        # Multiple degraded layers should be visible in the evidence.
        degraded_layers = [
            name
            for name, value in components.items()
            if value is not None and value < 65
        ]

        if len(degraded_layers) >= 2:
            evidence_list.append("multi_layer_degradation")

        if len(degraded_layers) >= 3:
            evidence_list.append("multi_layer_service_impact")

        # Keep the score conservative when several layers are degraded.
        if len(degraded_layers) >= 2:
            score -= 5

        if len(degraded_layers) >= 3:
            score -= 10

        score = self._clamp(score)
        risk = self._risk(score)

        observation_id = str(uuid.uuid4())

        self.db.execute(
            """
            INSERT INTO service_health (
                observation_id,
                timestamp,
                service_id,
                health_score,
                risk,
                radio_health,
                rf_health,
                site_health,
                backhaul_health,
                vpn_health,
                internet_health,
                evidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation_id,
                self._now(),
                service_id,
                score,
                risk,
                components["radio_health"],
                components["rf_health"],
                components["site_health"],
                components["backhaul_health"],
                components["vpn_health"],
                components["internet_health"],
                ",".join(sorted(set(evidence_list))),
            ),
        )

        self.db.commit()

        return {
            "enabled": True,
            "observation_id": observation_id,
            "service_id": service_id,
            "health_score": score,
            "risk": risk,
            "components": components,
            "degraded_layers": degraded_layers,
            "evidence": sorted(set(evidence_list)),
        }

    def history(self, service_id, limit=20):
        rows = self.db.execute(
            """
            SELECT *
            FROM service_health
            WHERE service_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (service_id, int(limit)),
        ).fetchall()

        return [dict(row) for row in rows]

    def latest(self, service_id):
        rows = self.history(service_id, 1)

        if not rows:
            return None

        return rows[0]

    def recovery_status(self, service_id):
        history = self.history(service_id, 4)

        if len(history) < 2:
            return {
                "state": "NO_RECOVERY_DATA",
                "observations": len(history),
            }

        latest = history[0]["health_score"]
        previous = history[1]["health_score"]

        if latest > previous:
            if latest >= 85 and previous < 85:
                state = "RECOVERED"
            else:
                state = "RECOVERING"

        elif latest < previous:
            state = "DEGRADING"

        else:
            state = "STABLE"

        return {
            "state": state,
            "observations": len(history),
            "health_score": latest,
            "previous_score": previous,
        }

    def close(self):
        self.db.close()
