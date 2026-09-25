"""
Sentinel-Civil
Fiber & PON Intelligence

Version: 1.0.0

Passive/authorized fiber and PON infrastructure intelligence.

This module models:
- OLT
- ONT/ONU
- ODN
- Fiber links
- Splitters
- Distribution hubs / FDH
- Optical observations
- Optical degradation events

It does not perform:
- unauthorized optical access
- traffic interception
- optical injection
- destructive testing
- modification of operator infrastructure
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class FiberPONIntelligence:
    VERSION = "1.0.0"

    STATES = {
        "UNKNOWN",
        "NORMAL",
        "DEGRADED",
        "CRITICAL",
        "OFFLINE",
        "RECOVERED",
    }

    ASSET_TYPES = {
        "OLT",
        "ONT",
        "ONU",
        "ODN",
        "FIBER",
        "SPLITTER",
        "FDH",
        "ODF",
        "CTO",
        "NAP",
    }

    EVENT_TYPES = {
        "OPTICAL_DEGRADATION",
        "OPTICAL_RECOVERY",
        "OPTICAL_LOSS",
        "LINK_DOWN",
        "LINK_UP",
        "POWER_ANOMALY",
        "TEMPERATURE_ANOMALY",
        "LASER_BIAS_ANOMALY",
        "RX_POWER_CHANGE",
        "TX_POWER_CHANGE",
        "PON_DEGRADATION",
        "COMMON_PATH_DEGRADATION",
    }

    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS fiber_assets (
                asset_id TEXT PRIMARY KEY,
                asset_type TEXT NOT NULL,
                site_id TEXT,
                parent_id TEXT,
                vendor TEXT,
                model TEXT,
                serial_number TEXT,
                firmware TEXT,
                state TEXT NOT NULL,
                criticality TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS optical_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                rx_power_dbm REAL,
                tx_power_dbm REAL,
                temperature_c REAL,
                voltage_v REAL,
                laser_bias_ma REAL,
                signal_loss_db REAL,
                link_state TEXT,
                source TEXT,
                FOREIGN KEY(asset_id) REFERENCES fiber_assets(asset_id)
            );

            CREATE TABLE IF NOT EXISTS fiber_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT,
                evidence_json TEXT,
                evidence_hash TEXT NOT NULL,
                source TEXT,
                FOREIGN KEY(asset_id) REFERENCES fiber_assets(asset_id)
            );
            """
        )
        self.conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(payload: Dict[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")

        return hashlib.sha256(encoded).hexdigest()

    def register_asset(
        self,
        asset_id: str,
        asset_type: str,
        site_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        vendor: Optional[str] = None,
        model: Optional[str] = None,
        serial_number: Optional[str] = None,
        firmware: Optional[str] = None,
        criticality: str = "NORMAL",
    ) -> None:
        if asset_type not in self.ASSET_TYPES:
            raise ValueError(f"Unsupported asset type: {asset_type}")

        now = self._now()

        self.conn.execute(
            """
            INSERT OR REPLACE INTO fiber_assets (
                asset_id,
                asset_type,
                site_id,
                parent_id,
                vendor,
                model,
                serial_number,
                firmware,
                state,
                criticality,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                asset_type,
                site_id,
                parent_id,
                vendor,
                model,
                serial_number,
                firmware,
                "UNKNOWN",
                criticality,
                now,
                now,
            ),
        )

        self.conn.commit()

    def observe(
        self,
        asset_id: str,
        rx_power_dbm: Optional[float] = None,
        tx_power_dbm: Optional[float] = None,
        temperature_c: Optional[float] = None,
        voltage_v: Optional[float] = None,
        laser_bias_ma: Optional[float] = None,
        signal_loss_db: Optional[float] = None,
        link_state: Optional[str] = None,
        source: str = "LOCAL",
    ) -> Dict[str, Any]:

        asset = self.get_asset(asset_id)

        if asset is None:
            raise ValueError(f"Unknown asset: {asset_id}")

        timestamp = self._now()

        self.conn.execute(
            """
            INSERT INTO optical_observations (
                asset_id,
                timestamp,
                rx_power_dbm,
                tx_power_dbm,
                temperature_c,
                voltage_v,
                laser_bias_ma,
                signal_loss_db,
                link_state,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                timestamp,
                rx_power_dbm,
                tx_power_dbm,
                temperature_c,
                voltage_v,
                laser_bias_ma,
                signal_loss_db,
                link_state,
                source,
            ),
        )

        state = self.classify(
            rx_power_dbm=rx_power_dbm,
            signal_loss_db=signal_loss_db,
            link_state=link_state,
        )

        self.conn.execute(
            """
            UPDATE fiber_assets
            SET state = ?, updated_at = ?
            WHERE asset_id = ?
            """,
            (state, timestamp, asset_id),
        )

        self.conn.commit()

        return {
            "asset_id": asset_id,
            "state": state,
            "timestamp": timestamp,
        }

    def classify(
        self,
        rx_power_dbm: Optional[float] = None,
        signal_loss_db: Optional[float] = None,
        link_state: Optional[str] = None,
    ) -> str:

        if link_state is not None:
            normalized = link_state.upper()

            if normalized in {"DOWN", "OFFLINE"}:
                return "OFFLINE"

            if normalized in {"UP", "ONLINE"}:
                if (
                    signal_loss_db is not None
                    and signal_loss_db >= 3.0
                ):
                    return "DEGRADED"

                return "NORMAL"

        if signal_loss_db is not None:
            if signal_loss_db >= 6.0:
                return "CRITICAL"

            if signal_loss_db >= 3.0:
                return "DEGRADED"

        if rx_power_dbm is not None:
            if rx_power_dbm <= -28.0:
                return "CRITICAL"

            if rx_power_dbm <= -25.0:
                return "DEGRADED"

        return "NORMAL"

    def record_event(
        self,
        asset_id: str,
        event_type: str,
        severity: str,
        description: str = "",
        evidence: Optional[Dict[str, Any]] = None,
        source: str = "LOCAL",
    ) -> str:

        if event_type not in self.EVENT_TYPES:
            raise ValueError(f"Unsupported event type: {event_type}")

        payload = evidence or {}

        evidence_hash = self._hash(payload)
        timestamp = self._now()

        self.conn.execute(
            """
            INSERT INTO fiber_events (
                asset_id,
                timestamp,
                event_type,
                severity,
                description,
                evidence_json,
                evidence_hash,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                timestamp,
                event_type,
                severity,
                description,
                json.dumps(payload, sort_keys=True, default=str),
                evidence_hash,
                source,
            ),
        )

        self.conn.commit()

        return evidence_hash

    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            """
            SELECT *
            FROM fiber_assets
            WHERE asset_id = ?
            """,
            (asset_id,),
        ).fetchone()

        return dict(row) if row else None

    def observations(self, asset_id: str):
        rows = self.conn.execute(
            """
            SELECT *
            FROM optical_observations
            WHERE asset_id = ?
            ORDER BY id
            """,
            (asset_id,),
        ).fetchall()

        return [dict(row) for row in rows]

    def events(self, asset_id: Optional[str] = None):
        if asset_id is None:
            rows = self.conn.execute(
                """
                SELECT *
                FROM fiber_events
                ORDER BY id
                """
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT *
                FROM fiber_events
                WHERE asset_id = ?
                ORDER BY id
                """,
                (asset_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def close(self) -> None:
        self.conn.close()
