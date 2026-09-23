"""
Sentinel Radio ↔ RF Correlation Engine.

Passive/authorized correlation only.
No RF transmission, interception, injection, audio capture,
authentication bypass, or remote radio control.

Correlation is not proof of causality.
"""

import hashlib
import json
import sqlite3
import time
import uuid


class RadioCorrelationEngine:
    VERSION = "1.0.0"

    def __init__(self, db_path=":memory:", enabled=False):
        self.enabled = bool(enabled)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS correlation_events (
                event_id TEXT PRIMARY KEY,
                timestamp REAL,
                site_id TEXT,
                radio_id TEXT,
                component_id TEXT,
                event_type TEXT,
                severity TEXT,
                confidence REAL,
                evidence TEXT,
                previous_hash TEXT,
                event_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS correlation_incidents (
                incident_id TEXT PRIMARY KEY,
                timestamp_start REAL,
                timestamp_end REAL,
                site_id TEXT,
                radio_id TEXT,
                component_id TEXT,
                incident_type TEXT,
                state TEXT,
                confidence REAL,
                evidence TEXT
            );
            """
        )
        self.conn.commit()

    @staticmethod
    def _hash(payload):
        return hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def _last_hash(self, site_id=None, radio_id=None, component_id=None):
        row = self.conn.execute(
            """
            SELECT event_hash
            FROM correlation_events
            WHERE
                (site_id IS ?)
                AND (radio_id IS ?)
                AND (component_id IS ?)
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (site_id, radio_id, component_id),
        ).fetchone()

        return row["event_hash"] if row else None

    def _emit(
        self,
        event_type,
        severity,
        evidence,
        confidence,
        site_id=None,
        radio_id=None,
        component_id=None,
    ):
        timestamp = time.time()

        payload = {
            "event_type": event_type,
            "severity": severity,
            "confidence": confidence,
            "evidence": evidence,
            "site_id": site_id,
            "radio_id": radio_id,
            "component_id": component_id,
            "timestamp": timestamp,
        }

        previous_hash = self._last_hash(
            site_id=site_id,
            radio_id=radio_id,
            component_id=component_id,
        )

        event_hash = self._hash(
            {
                "previous_hash": previous_hash,
                "payload": payload,
            }
        )

        event_id = str(uuid.uuid4())

        self.conn.execute(
            """
            INSERT INTO correlation_events (
                event_id,
                timestamp,
                site_id,
                radio_id,
                component_id,
                event_type,
                severity,
                confidence,
                evidence,
                previous_hash,
                event_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                timestamp,
                site_id,
                radio_id,
                component_id,
                event_type,
                severity,
                float(confidence),
                json.dumps(evidence, sort_keys=True),
                previous_hash,
                event_hash,
            ),
        )

        self.conn.commit()

        return {
            "event_id": event_id,
            "event_type": event_type,
            "severity": severity,
            "confidence": float(confidence),
            "evidence": evidence,
            "event_hash": event_hash,
        }

    @staticmethod
    def _event_time(event):
        value = event.get("timestamp")

        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def correlate(
        self,
        radio_observations,
        rf_observations,
        site_id=None,
        radio_id=None,
        component_id=None,
        window_seconds=300,
    ):
        """
        Correlate radio and RF observations within a time window.

        Expected observations are dictionaries. The engine intentionally
        accepts telemetry rather than directly controlling either subsystem.
        """

        if not self.enabled:
            return {
                "enabled": False,
                "incident": False,
                "events": [],
            }

        radio_observations = list(radio_observations or [])
        rf_observations = list(rf_observations or [])

        if not radio_observations or not rf_observations:
            return {
                "enabled": True,
                "incident": False,
                "events": [],
                "reason": "insufficient_cross_domain_observations",
            }

        latest_radio = radio_observations[-1]
        latest_rf = rf_observations[-1]

        radio_time = self._event_time(latest_radio)
        rf_time = self._event_time(latest_rf)

        if radio_time is not None and rf_time is not None:
            if abs(radio_time - rf_time) > window_seconds:
                return {
                    "enabled": True,
                    "incident": False,
                    "events": [],
                    "reason": "observations_outside_correlation_window",
                }

        evidence = []
        radio_failure = False
        rf_degradation = False
        backhaul_failure = False

        radio_health = latest_radio.get("health_score")

        if radio_health is not None:
            try:
                radio_failure = float(radio_health) < 65
            except (TypeError, ValueError):
                pass

        radio_trends = set(latest_radio.get("trends") or [])

        if {
            "signal_decline",
            "connection_instability",
            "latency_increase",
            "packet_loss_increase",
        } & radio_trends:
            radio_failure = True

            evidence.append(
                {
                    "domain": "radio",
                    "trends": sorted(radio_trends),
                }
            )

        rf_health = latest_rf.get("health_score")

        if rf_health is not None:
            try:
                rf_degradation = float(rf_health) < 85
            except (TypeError, ValueError):
                pass

        rf_trends = set(latest_rf.get("trends") or [])

        if {
            "snr_degradation",
            "noise_increase",
            "signal_degradation",
            "packet_loss_increase",
            "latency_increase",
            "backhaul_instability",
        } & rf_trends:
            rf_degradation = True

            evidence.append(
                {
                    "domain": "rf",
                    "trends": sorted(rf_trends),
                }
            )

        if latest_rf.get("backhaul_available") is False:
            backhaul_failure = True

            evidence.append(
                {
                    "domain": "backhaul",
                    "state": "unavailable",
                }
            )

        events = []

        if backhaul_failure and radio_failure:
            confidence = 0.90

            events.append(
                self._emit(
                    "RADIO_BACKHAUL_FAILURE",
                    "CRITICAL",
                    evidence,
                    confidence,
                    site_id,
                    radio_id,
                    component_id,
                )
            )

            events.append(
                self._emit(
                    "RADIO_INFRASTRUCTURE_INCIDENT",
                    "CRITICAL",
                    evidence,
                    confidence,
                    site_id,
                    radio_id,
                    component_id,
                )
            )

            incident_type = "BACKHAUL_RADIO_CASCADE"

        elif rf_degradation and radio_failure:
            confidence = 0.82

            events.append(
                self._emit(
                    "RADIO_INFRASTRUCTURE_INCIDENT",
                    "WARNING",
                    evidence,
                    confidence,
                    site_id,
                    radio_id,
                    component_id,
                )
            )

            incident_type = "RADIO_RF_CORRELATION"

        else:
            return {
                "enabled": True,
                "incident": False,
                "events": [],
                "evidence": evidence,
            }

        incident_id = str(uuid.uuid4())

        self.conn.execute(
            """
            INSERT INTO correlation_incidents (
                incident_id,
                timestamp_start,
                timestamp_end,
                site_id,
                radio_id,
                component_id,
                incident_type,
                state,
                confidence,
                evidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                time.time(),
                None,
                site_id,
                radio_id,
                component_id,
                incident_type,
                "OPEN",
                confidence,
                json.dumps(evidence, sort_keys=True),
            ),
        )

        self.conn.commit()

        return {
            "enabled": True,
            "incident": True,
            "incident_id": incident_id,
            "incident_type": incident_type,
            "state": "OPEN",
            "confidence": confidence,
            "events": events,
            "evidence": evidence,
        }

    def recover(
        self,
        site_id=None,
        radio_id=None,
        component_id=None,
    ):
        row = self.conn.execute(
            """
            SELECT incident_id
            FROM correlation_incidents
            WHERE state = 'OPEN'
              AND (site_id IS ?)
              AND (radio_id IS ?)
              AND (component_id IS ?)
            ORDER BY timestamp_start DESC
            LIMIT 1
            """,
            (site_id, radio_id, component_id),
        ).fetchone()

        if row is None:
            return {
                "recovered": False,
                "reason": "no_open_incident",
            }

        timestamp = time.time()

        self.conn.execute(
            """
            UPDATE correlation_incidents
            SET
                timestamp_end = ?,
                state = 'RECOVERED'
            WHERE incident_id = ?
            """,
            (timestamp, row["incident_id"]),
        )

        self.conn.commit()

        event = self._emit(
            "INCIDENT_RECOVERED",
            "INFO",
            {
                "incident_id": row["incident_id"],
            },
            0.95,
            site_id,
            radio_id,
            component_id,
        )

        return {
            "recovered": True,
            "incident_id": row["incident_id"],
            "event": event,
        }

    def get_incidents(self, site_id=None):
        if site_id is None:
            rows = self.conn.execute(
                """
                SELECT *
                FROM correlation_incidents
                ORDER BY timestamp_start DESC
                """
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT *
                FROM correlation_incidents
                WHERE site_id = ?
                ORDER BY timestamp_start DESC
                """,
                (site_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_events(self, site_id=None):
        if site_id is None:
            rows = self.conn.execute(
                """
                SELECT *
                FROM correlation_events
                ORDER BY timestamp DESC
                """
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT *
                FROM correlation_events
                WHERE site_id = ?
                ORDER BY timestamp DESC
                """,
                (site_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def close(self):
        self.conn.close()


__all__ = ["RadioCorrelationEngine"]
