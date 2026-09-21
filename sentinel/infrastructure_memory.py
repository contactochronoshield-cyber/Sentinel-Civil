import hashlib
import json
import os
import sqlite3
import time
import uuid


class InfrastructureMemory:
    """
    Sentinel Civil Infrastructure Memory.

    Persistent infrastructure health memory with:

    - baseline management
    - observations
    - degradation state machine
    - gradual recovery
    - incident lifecycle
    - evidence hashing
    - trend detection
    - confidence
    - metric deltas
    """

    STATES = (
        "UNVERIFIED",
        "STABLE",
        "AGING",
        "DRIFTED",
        "DEGRADED",
        "CRITICAL",
    )

    SEVERITY = {
        "UNVERIFIED": 0,
        "STABLE": 1,
        "AGING": 2,
        "DRIFTED": 3,
        "DEGRADED": 4,
        "CRITICAL": 5,
    }

    RECOVERY_HYSTERESIS = 1

    INCIDENT_STATES = {
        "DEGRADED",
        "CRITICAL",
    }

    def __init__(
        self,
        db_path,
        node_name="sentinel-node",
    ):
        self.db_path = os.path.abspath(
            os.path.expanduser(db_path)
        )
        self.node_name = node_name
        self._init_db()

    def _connect(self):
        directory = os.path.dirname(self.db_path)

        if directory:
            os.makedirs(
                directory,
                exist_ok=True
            )

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        return conn

    def _init_db(self):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS infrastructure_baselines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_name TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                baseline_json TEXT NOT NULL,
                baseline_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(node_name, asset_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS infrastructure_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_name TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                state TEXT NOT NULL,
                trend TEXT NOT NULL,
                confidence TEXT NOT NULL,
                reasons_json TEXT NOT NULL,
                observation_json TEXT NOT NULL,
                delta_json TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                evidence_hash TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS infrastructure_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_name TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                event_type TEXT NOT NULL,
                start_state TEXT NOT NULL,
                peak_state TEXT NOT NULL,
                end_state TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                peak_delta_json TEXT,
                peak_reasons_json TEXT,
                recovery_duration_seconds INTEGER,
                observation_count INTEGER DEFAULT 0,
                status TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_infra_obs_asset
            ON infrastructure_observations(
                node_name,
                asset_id,
                id
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_infra_incidents_asset
            ON infrastructure_incidents(
                node_name,
                asset_id,
                id
            )
        """)

        conn.commit()
        conn.close()

    def _now(self):
        return time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    def _epoch(self):
        return int(time.time())

    def _canonical_json(self, value):
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def _hash(self, value):
        payload = self._canonical_json(value)

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

    def _new_evidence_id(self):
        return (
            "SC-EV-"
            + time.strftime("%Y%m%d%H%M%S")
            + "-"
            + uuid.uuid4().hex[:8].upper()
        )

    def set_baseline(
        self,
        asset_id,
        asset_type,
        metrics,
    ):
        timestamp = self._now()

        baseline_hash = self._hash(metrics)

        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO infrastructure_baselines (
                node_name,
                asset_id,
                asset_type,
                baseline_json,
                baseline_hash,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(node_name, asset_id)
            DO UPDATE SET
                asset_type = excluded.asset_type,
                baseline_json = excluded.baseline_json,
                baseline_hash = excluded.baseline_hash,
                updated_at = excluded.updated_at
        """, (
            self.node_name,
            asset_id,
            asset_type,
            self._canonical_json(metrics),
            baseline_hash,
            timestamp,
            timestamp,
        ))

        conn.commit()
        conn.close()

        return {
            "asset_id": asset_id,
            "asset_type": asset_type,
            "baseline_hash": baseline_hash,
            "timestamp": timestamp,
        }

    def get_baseline(self, asset_id):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                asset_type,
                baseline_json,
                baseline_hash,
                created_at,
                updated_at
            FROM infrastructure_baselines
            WHERE node_name = ?
              AND asset_id = ?
        """, (
            self.node_name,
            asset_id,
        ))

        row = cur.fetchone()
        conn.close()

        if row is None:
            return None

        return {
            "asset_type": row["asset_type"],
            "metrics": json.loads(
                row["baseline_json"]
            ),
            "baseline_hash": row["baseline_hash"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _numeric_delta(
        self,
        baseline,
        current,
    ):
        delta = {}

        keys = (
            set(baseline.keys())
            | set(current.keys())
        )

        for key in keys:
            old = baseline.get(key)
            new = current.get(key)

            if (
                isinstance(old, (int, float))
                and isinstance(new, (int, float))
            ):
                delta[key] = round(
                    new - old,
                    4
                )

        return delta

    def _metric_directions(self, delta):
        signals = []

        if delta.get("rssi_dbm", 0) <= -5:
            signals.append({
                "metric": "rssi_dbm",
                "severity": "medium",
            })

        if delta.get("snr_db", 0) <= -5:
            signals.append({
                "metric": "snr_db",
                "severity": "medium",
            })

        if delta.get("latency_ms", 0) >= 10:
            signals.append({
                "metric": "latency_ms",
                "severity": "medium",
            })

        if delta.get("jitter_ms", 0) >= 10:
            signals.append({
                "metric": "jitter_ms",
                "severity": "medium",
            })

        if delta.get("packet_loss_pct", 0) >= 1:
            signals.append({
                "metric": "packet_loss_pct",
                "severity": "high",
            })

        if delta.get("retries_pct", 0) >= 2:
            signals.append({
                "metric": "retries_pct",
                "severity": "medium",
            })

        if delta.get("throughput_mbps", 0) <= -5:
            signals.append({
                "metric": "throughput_mbps",
                "severity": "high",
            })

        if delta.get("link_speed_mbps", 0) <= -10:
            signals.append({
                "metric": "link_speed_mbps",
                "severity": "medium",
            })

        if delta.get("noise_db", 0) >= 5:
            signals.append({
                "metric": "noise_db",
                "severity": "medium",
            })

        if delta.get("temperature_c", 0) >= 15:
            signals.append({
                "metric": "temperature_c",
                "severity": "medium",
            })

        if delta.get("humidity_pct", 0) >= 20:
            signals.append({
                "metric": "humidity_pct",
                "severity": "low",
            })

        return signals

    def _reasons(self, delta):
        return [
            signal["metric"]
            for signal in self._metric_directions(delta)
        ]

    def _classify_candidate(
        self,
        delta,
        previous_states,
    ):
        signals = self._metric_directions(delta)
        count = len(signals)

        if count == 0:
            return "STABLE"

        if count == 1:
            return "AGING"

        if count == 2:
            return "DRIFTED"

        if count <= 4:
            return "DEGRADED"

        recent = previous_states[-3:]

        if (
            recent.count("CRITICAL") >= 1
            or recent.count("DEGRADED") >= 2
        ):
            return "CRITICAL"

        return "DEGRADED"

    def get_history_count(self, asset_id):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            SELECT COUNT(*)
            FROM infrastructure_observations
            WHERE node_name = ?
              AND asset_id = ?
        """, (
            self.node_name,
            asset_id,
        ))

        count = cur.fetchone()[0]
        conn.close()

        return count

    def _get_recent_states(
        self,
        asset_id,
        limit=8,
    ):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            SELECT state
            FROM infrastructure_observations
            WHERE node_name = ?
              AND asset_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (
            self.node_name,
            asset_id,
            limit,
        ))

        rows = cur.fetchall()
        conn.close()

        return [
            row["state"]
            for row in reversed(rows)
        ]

    def _apply_state_machine(
        self,
        candidate_state,
        previous_state,
        recent_states,
    ):
        if previous_state is None:
            return candidate_state

        candidate_level = self.SEVERITY.get(
            candidate_state,
            0
        )

        previous_level = self.SEVERITY.get(
            previous_state,
            0
        )

        if candidate_level >= previous_level:
            return candidate_state

        if previous_state == "STABLE":
            return candidate_state

        healthy_count = 0

        for state in reversed(recent_states):
            if state in (
                "STABLE",
                "AGING",
                "DRIFTED",
            ):
                healthy_count += 1
            else:
                break

        if healthy_count < self.RECOVERY_HYSTERESIS:
            return previous_state

        recovery_level = previous_level - 1

        recovery_level = max(
            recovery_level,
            candidate_level
        )

        for state, level in self.SEVERITY.items():
            if level == recovery_level:
                return state

        return candidate_state

    def _calculate_trend(self, states):
        if len(states) < 2:
            return "INITIAL"

        values = [
            self.SEVERITY.get(
                state,
                0
            )
            for state in states
        ]

        if values[-1] > values[0]:
            return "WORSENING"

        if values[-1] < values[0]:
            return "IMPROVING"

        if all(
            value == values[0]
            for value in values
        ):
            return "STABLE"

        return "FLUCTUATING"

    def _confidence(
        self,
        state,
        reasons,
        history_count,
    ):
        if state == "UNVERIFIED":
            return "LOW"

        if (
            history_count >= 12
            and len(reasons) >= 3
        ):
            return "HIGH"

        if (
            history_count >= 5
            and len(reasons) >= 2
        ):
            return "MEDIUM"

        return "LOW"

    def _get_open_incident(self, asset_id):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM infrastructure_incidents
            WHERE node_name = ?
              AND asset_id = ?
              AND status = 'OPEN'
            ORDER BY id DESC
            LIMIT 1
        """, (
            self.node_name,
            asset_id,
        ))

        row = cur.fetchone()
        conn.close()

        if row is None:
            return None

        return dict(row)

    def _start_incident(
        self,
        asset_id,
        asset_type,
        state,
        delta,
        reasons,
        timestamp,
    ):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO infrastructure_incidents (
                node_name,
                asset_id,
                asset_type,
                event_type,
                start_state,
                peak_state,
                end_state,
                start_time,
                end_time,
                peak_delta_json,
                peak_reasons_json,
                recovery_duration_seconds,
                observation_count,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.node_name,
            asset_id,
            asset_type,
            "INFRASTRUCTURE_DEGRADATION",
            state,
            state,
            None,
            timestamp,
            None,
            self._canonical_json(delta),
            self._canonical_json(reasons),
            None,
            1,
            "OPEN",
        ))

        incident_id = cur.lastrowid

        conn.commit()
        conn.close()

        return incident_id

    def _update_incident(
        self,
        incident,
        state,
        delta,
        reasons,
    ):
        peak_state = incident["peak_state"]

        if self.SEVERITY.get(
            state,
            0
        ) > self.SEVERITY.get(
            peak_state,
            0
        ):
            peak_state = state
            peak_delta = delta
            peak_reasons = reasons
        else:
            peak_delta = json.loads(
                incident["peak_delta_json"]
                or "{}"
            )

            peak_reasons = json.loads(
                incident["peak_reasons_json"]
                or "[]"
            )

        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            UPDATE infrastructure_incidents
            SET
                peak_state = ?,
                peak_delta_json = ?,
                peak_reasons_json = ?,
                observation_count =
                    observation_count + 1
            WHERE id = ?
        """, (
            peak_state,
            self._canonical_json(
                peak_delta
            ),
            self._canonical_json(
                peak_reasons
            ),
            incident["id"],
        ))

        conn.commit()
        conn.close()

    def _close_incident(
        self,
        incident,
        end_state,
        timestamp,
    ):
        try:
            start_epoch = time.mktime(
                time.strptime(
                    incident["start_time"],
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            duration = max(
                0,
                int(
                    self._epoch()
                    - start_epoch
                )
            )

        except Exception:
            duration = None

        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            UPDATE infrastructure_incidents
            SET
                end_state = ?,
                end_time = ?,
                recovery_duration_seconds = ?,
                status = 'RECOVERED'
            WHERE id = ?
        """, (
            end_state,
            timestamp,
            duration,
            incident["id"],
        ))

        conn.commit()
        conn.close()

        return {
            "incident_id": incident["id"],
            "peak_state": incident["peak_state"],
            "end_state": end_state,
            "recovery_duration_seconds": duration,
            "status": "RECOVERED",
        }

    def _process_incident(
        self,
        asset_id,
        asset_type,
        state,
        delta,
        reasons,
        timestamp,
    ):
        incident = self._get_open_incident(
            asset_id
        )

        if state in self.INCIDENT_STATES:

            if incident is None:
                incident_id = self._start_incident(
                    asset_id,
                    asset_type,
                    state,
                    delta,
                    reasons,
                    timestamp,
                )

                return {
                    "status": "OPENED",
                    "incident_id": incident_id,
                }

            self._update_incident(
                incident,
                state,
                delta,
                reasons,
            )

            return {
                "status": "OPEN",
                "incident_id": incident["id"],
            }

        if incident is not None:

            if state in (
                "AGING",
                "DRIFTED",
            ):
                self._update_incident(
                    incident,
                    state,
                    delta,
                    reasons,
                )

                return {
                    "status": "RECOVERING",
                    "incident_id": incident["id"],
                    "recovery_state": state,
                }

            if state == "STABLE":

                recovery = self._close_incident(
                    incident,
                    state,
                    timestamp,
                )

                return {
                    "status": "RECOVERED",
                    **recovery,
                }

        return {
            "status": "NONE"
        }

    def observe(
        self,
        asset_id,
        asset_type,
        metrics,
    ):
        baseline = self.get_baseline(
            asset_id
        )

        previous_states = (
            self._get_recent_states(
                asset_id,
                limit=8,
            )
        )

        previous_state = (
            previous_states[-1]
            if previous_states
            else None
        )

        if baseline is None:

            state = "UNVERIFIED"

            delta = {}

            reasons = [
                "NO_BASELINE"
            ]

        else:

            delta = self._numeric_delta(
                baseline["metrics"],
                metrics,
            )

            candidate_state = (
                self._classify_candidate(
                    delta,
                    previous_states,
                )
            )

            state = self._apply_state_machine(
                candidate_state,
                previous_state,
                previous_states,
            )

            reasons = self._reasons(
                delta
            )

        trend = self._calculate_trend(
            previous_states + [state]
        )

        history_count = (
            self.get_history_count(
                asset_id
            ) + 1
        )

        confidence = self._confidence(
            state,
            reasons,
            history_count,
        )

        timestamp = self._now()

        evidence_id = (
            self._new_evidence_id()
        )

        evidence_payload = {
            "evidence_id": evidence_id,
            "node_name": self.node_name,
            "asset_id": asset_id,
            "asset_type": asset_type,
            "state": state,
            "trend": trend,
            "confidence": confidence,
            "reasons": reasons,
            "metrics": metrics,
            "delta": delta,
            "baseline_hash": (
                baseline["baseline_hash"]
                if baseline
                else None
            ),
            "timestamp": timestamp,
        }

        evidence_hash = self._hash(
            evidence_payload
        )

        incident = self._process_incident(
            asset_id,
            asset_type,
            state,
            delta,
            reasons,
            timestamp,
        )

        conn = self._connect()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO infrastructure_observations (
                node_name,
                asset_id,
                asset_type,
                state,
                trend,
                confidence,
                reasons_json,
                observation_json,
                delta_json,
                evidence_id,
                evidence_hash,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.node_name,
            asset_id,
            asset_type,
            state,
            trend,
            confidence,
            self._canonical_json(
                reasons
            ),
            self._canonical_json(
                metrics
            ),
            self._canonical_json(
                delta
            ),
            evidence_id,
            evidence_hash,
            timestamp,
        ))

        observation_id = cur.lastrowid

        conn.commit()
        conn.close()

        return {
            "observation_id": observation_id,
            "asset_id": asset_id,
            "asset_type": asset_type,
            "state": state,
            "trend": trend,
            "confidence": confidence,
            "reasons": reasons,
            "metrics": metrics,
            "delta": delta,
            "history_count": history_count,
            "evidence_id": evidence_id,
            "evidence_hash": evidence_hash,
            "incident": incident,
            "timestamp": timestamp,
        }

    def get_events(
        self,
        asset_id=None,
    ):
        conn = self._connect()
        cur = conn.cursor()

        if asset_id:

            cur.execute("""
                SELECT *
                FROM infrastructure_incidents
                WHERE node_name = ?
                  AND asset_id = ?
                ORDER BY id
            """, (
                self.node_name,
                asset_id,
            ))

        else:

            cur.execute("""
                SELECT *
                FROM infrastructure_incidents
                WHERE node_name = ?
                ORDER BY id
            """, (
                self.node_name,
            ))

        rows = cur.fetchall()
        conn.close()

        return [
            dict(row)
            for row in rows
        ]

    def get_observations(
        self,
        asset_id=None,
        limit=50,
    ):
        conn = self._connect()
        cur = conn.cursor()

        if asset_id:

            cur.execute("""
                SELECT *
                FROM infrastructure_observations
                WHERE node_name = ?
                  AND asset_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (
                self.node_name,
                asset_id,
                limit,
            ))

        else:

            cur.execute("""
                SELECT *
                FROM infrastructure_observations
                WHERE node_name = ?
                ORDER BY id DESC
                LIMIT ?
            """, (
                self.node_name,
                limit,
            ))

        rows = cur.fetchall()
        conn.close()

        return [
            dict(row)
            for row in rows
        ]
