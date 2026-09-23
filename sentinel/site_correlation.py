"""
Sentinel Site Correlation Engine.

Aggregates correlated radio/RF incidents belonging to the same site.

This module detects common-site patterns. It does not prove root cause.
Passive/authorized monitoring only.
"""

import json
import sqlite3
import time
import uuid


class SiteCorrelationEngine:
    VERSION = "1.0.0"

    def __init__(self, db_path=":memory:", enabled=False):
        self.enabled = bool(enabled)

        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

        self._create_schema()

    def _create_schema(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS site_incidents (
                incident_id TEXT PRIMARY KEY,
                timestamp REAL,
                site_id TEXT,
                incident_type TEXT,
                state TEXT,
                affected_radios INTEGER,
                affected_components INTEGER,
                confidence REAL,
                evidence TEXT
            );
            """
        )

        self.conn.commit()

    def aggregate(
        self,
        site_id,
        incidents,
        minimum_radios=2,
    ):
        """
        Aggregate incidents belonging to the same site.

        incidents must contain dictionaries with at least:
        radio_id, incident_type, state, confidence.

        No causal inference is performed.
        """

        if not self.enabled:
            return {
                "enabled": False,
                "incident": False,
                "reason": "disabled",
            }

        incidents = list(incidents or [])

        open_incidents = [
            item
            for item in incidents
            if item.get("state") == "OPEN"
        ]

        radio_ids = {
            item.get("radio_id")
            for item in open_incidents
            if item.get("radio_id")
        }

        component_ids = {
            item.get("component_id")
            for item in open_incidents
            if item.get("component_id")
        }

        if len(radio_ids) < minimum_radios:
            return {
                "enabled": True,
                "incident": False,
                "reason": "insufficient_affected_radios",
                "affected_radios": len(radio_ids),
            }

        incident_types = {
            item.get("incident_type")
            for item in open_incidents
            if item.get("incident_type")
        }

        evidence = {
            "site_id": site_id,
            "affected_radios": sorted(radio_ids),
            "affected_components": sorted(component_ids),
            "incident_types": sorted(incident_types),
            "incident_count": len(open_incidents),
        }

        confidence_values = [
            float(item.get("confidence", 0))
            for item in open_incidents
        ]

        average_confidence = (
            sum(confidence_values) / len(confidence_values)
            if confidence_values
            else 0.0
        )

        confidence = min(
            0.95,
            average_confidence + min(0.10, len(radio_ids) * 0.02),
        )

        incident_id = str(uuid.uuid4())

        timestamp = time.time()

        self.conn.execute(
            """
            INSERT INTO site_incidents (
                incident_id,
                timestamp,
                site_id,
                incident_type,
                state,
                affected_radios,
                affected_components,
                confidence,
                evidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                timestamp,
                site_id,
                "SITE_COMMUNICATION_DEGRADATION",
                "OPEN",
                len(radio_ids),
                len(component_ids),
                confidence,
                json.dumps(evidence, sort_keys=True),
            ),
        )

        self.conn.commit()

        return {
            "enabled": True,
            "incident": True,
            "incident_id": incident_id,
            "site_id": site_id,
            "incident_type": "SITE_COMMUNICATION_DEGRADATION",
            "state": "OPEN",
            "affected_radios": len(radio_ids),
            "affected_components": len(component_ids),
            "confidence": confidence,
            "evidence": evidence,
        }

    def recover(self, incident_id):
        row = self.conn.execute(
            """
            SELECT *
            FROM site_incidents
            WHERE incident_id = ?
              AND state = 'OPEN'
            """,
            (incident_id,),
        ).fetchone()

        if row is None:
            return {
                "recovered": False,
                "reason": "open_site_incident_not_found",
            }

        self.conn.execute(
            """
            UPDATE site_incidents
            SET
                state = 'RECOVERED'
            WHERE incident_id = ?
            """,
            (incident_id,),
        )

        self.conn.commit()

        return {
            "recovered": True,
            "incident_id": incident_id,
            "event_type": "INCIDENT_RECOVERED",
        }

    def get_incidents(self, site_id=None):
        if site_id is None:
            rows = self.conn.execute(
                """
                SELECT *
                FROM site_incidents
                ORDER BY timestamp DESC
                """
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT *
                FROM site_incidents
                WHERE site_id = ?
                ORDER BY timestamp DESC
                """,
                (site_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def close(self):
        self.conn.close()


__all__ = ["SiteCorrelationEngine"]
