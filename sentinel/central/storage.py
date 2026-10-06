"""
Sentinel Central - SQLite Storage.

Local persistence for Sentinel Central.

Customer data remains in the organization's
own Sentinel Central database.
"""

import json
import os
import sqlite3


class CentralStorage:
    def __init__(self, database_path):
        self.database_path = os.path.expanduser(
            database_path
        )

        directory = os.path.dirname(
            self.database_path
        )

        if directory:
            os.makedirs(
                directory,
                exist_ok=True,
            )

        self.connection = sqlite3.connect(
            self.database_path
        )

        self.connection.row_factory = (
            sqlite3.Row
        )

        self.initialize()

    def initialize(self):
        cursor = self.connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS organizations (
                organization_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS licenses (
                license_id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                data TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS policies (
                organization_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                data TEXT NOT NULL
            )
            """
        )

        self.connection.commit()

    def save_organization(self, organization):
        data = json.dumps(
            organization.to_dict(),
            ensure_ascii=False,
        )

        self.connection.execute(
            """
            INSERT OR REPLACE INTO organizations
            (organization_id, data)
            VALUES (?, ?)
            """,
            (
                organization.organization_id,
                data,
            ),
        )

        self.connection.commit()

    def get_organization(
        self,
        organization_id,
    ):
        row = self.connection.execute(
            """
            SELECT data
            FROM organizations
            WHERE organization_id = ?
            """,
            (organization_id,),
        ).fetchone()

        if row is None:
            return None

        return json.loads(row["data"])

    def save_license(self, license):
        data = json.dumps(
            license.to_dict(),
            ensure_ascii=False,
        )

        self.connection.execute(
            """
            INSERT OR REPLACE INTO licenses
            (license_id, organization_id, data)
            VALUES (?, ?, ?)
            """,
            (
                license.license_id,
                license.organization_id,
                data,
            ),
        )

        self.connection.commit()

    def get_license(self, license_id):
        row = self.connection.execute(
            """
            SELECT data
            FROM licenses
            WHERE license_id = ?
            """,
            (license_id,),
        ).fetchone()

        if row is None:
            return None

        return json.loads(row["data"])

    def save_policy(self, policy):
        data = json.dumps(
            policy.to_dict(),
            ensure_ascii=False,
        )

        self.connection.execute(
            """
            INSERT OR REPLACE INTO policies
            (organization_id, data)
            VALUES (?, ?)
            """,
            (
                policy.organization_id,
                data,
            ),
        )

        self.connection.commit()

    def get_policy(self, organization_id):
        row = self.connection.execute(
            """
            SELECT data
            FROM policies
            WHERE organization_id = ?
            """,
            (organization_id,),
        ).fetchone()

        if row is None:
            return None

        return json.loads(row["data"])

    def save_node(self, node):
        data = json.dumps(
            node.to_dict(),
            ensure_ascii=False,
        )

        self.connection.execute(
            """
            INSERT OR REPLACE INTO nodes
            (node_id, organization_id, data)
            VALUES (?, ?, ?)
            """,
            (
                node.node_id,
                node.organization_id,
                data,
            ),
        )

        self.connection.commit()

    def get_node(self, node_id):
        row = self.connection.execute(
            """
            SELECT data
            FROM nodes
            WHERE node_id = ?
            """,
            (node_id,),
        ).fetchone()

        if row is None:
            return None

        return json.loads(row["data"])

    def list_nodes(
        self,
        organization_id=None,
    ):
        if organization_id is None:
            rows = self.connection.execute(
                """
                SELECT data
                FROM nodes
                """
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT data
                FROM nodes
                WHERE organization_id = ?
                """,
                (organization_id,),
            ).fetchall()

        return [
            json.loads(row["data"])
            for row in rows
        ]

    def close(self):
        self.connection.close()

# Runtime extension for node deletion.
def _delete_node(self, node_id):
    self.connection.execute(
        """
        DELETE FROM nodes
        WHERE node_id = ?
        """,
        (node_id,),
    )
    self.connection.commit()


CentralStorage.delete_node = _delete_node

def _list_organizations(self):
    rows = self.connection.execute(
        """
        SELECT data
        FROM organizations
        """
    ).fetchall()

    return [
        json.loads(row["data"])
        for row in rows
    ]


def _list_licenses(self):
    rows = self.connection.execute(
        """
        SELECT data
        FROM licenses
        """
    ).fetchall()

    return [
        json.loads(row["data"])
        for row in rows
    ]


def _list_policies(self):
    rows = self.connection.execute(
        """
        SELECT data
        FROM policies
        """
    ).fetchall()

    return [
        json.loads(row["data"])
        for row in rows
    ]


CentralStorage.list_organizations = _list_organizations
CentralStorage.list_licenses = _list_licenses
CentralStorage.list_policies = _list_policies

def _initialize_audit_table(self):
    self.connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event TEXT NOT NULL,
            result TEXT NOT NULL,
            organization_id TEXT,
            actor TEXT,
            resource TEXT,
            resource_id TEXT,
            metadata TEXT NOT NULL
        )
        """
    )

    self.connection.commit()


def _save_audit_event(self, audit_event):
    data = json.dumps(
        audit_event.metadata,
        ensure_ascii=False,
    )

    self.connection.execute(
        """
        INSERT INTO audit_events (
            timestamp,
            event,
            result,
            organization_id,
            actor,
            resource,
            resource_id,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_event.timestamp,
            audit_event.event,
            audit_event.result,
            audit_event.organization_id,
            audit_event.actor,
            audit_event.resource,
            audit_event.resource_id,
            data,
        ),
    )

    self.connection.commit()


def _list_audit_events(
    self,
    organization_id=None,
    limit=100,
):
    if limit < 1:
        raise ValueError(
            "limit must be positive"
        )

    if organization_id is None:
        rows = self.connection.execute(
            """
            SELECT
                id,
                timestamp,
                event,
                result,
                organization_id,
                actor,
                resource,
                resource_id,
                metadata
            FROM audit_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    else:
        rows = self.connection.execute(
            """
            SELECT
                id,
                timestamp,
                event,
                result,
                organization_id,
                actor,
                resource,
                resource_id,
                metadata
            FROM audit_events
            WHERE organization_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                organization_id,
                limit,
            ),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "event": row["event"],
            "result": row["result"],
            "organization_id": row[
                "organization_id"
            ],
            "actor": row["actor"],
            "resource": row["resource"],
            "resource_id": row[
                "resource_id"
            ],
            "metadata": json.loads(
                row["metadata"]
            ),
        }
        for row in rows
    ]


_original_initialize = CentralStorage.initialize


def _initialize_with_audit(self):
    _original_initialize(self)
    self._initialize_audit_table()


CentralStorage.initialize = (
    _initialize_with_audit
)

CentralStorage._initialize_audit_table = (
    _initialize_audit_table
)

CentralStorage.save_audit_event = (
    _save_audit_event
)

CentralStorage.list_audit_events = (
    _list_audit_events
)
