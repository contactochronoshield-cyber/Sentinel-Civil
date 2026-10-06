"""
Sentinel Central - Node Health.

Tracks node heartbeats and persists health state
when CentralStorage is configured.
"""

from datetime import datetime, timezone


ONLINE = "ONLINE"
OFFLINE = "OFFLINE"


def _now():
    return datetime.now(timezone.utc)


def _timestamp():
    return _now().strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _parse_timestamp(value):
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


class NodeHealthManager:
    def __init__(
        self,
        node_registry,
        timeout_seconds=300,
        storage=None,
    ):
        if timeout_seconds < 1:
            raise ValueError(
                "timeout_seconds must be positive"
            )

        self.node_registry = node_registry
        self.timeout_seconds = timeout_seconds
        self.storage = storage

    def _persist(self, node):
        if self.storage is not None:
            self.storage.save_node(node)

    def heartbeat(self, node_id):
        node = self.node_registry.get(
            node_id
        )

        if node is None:
            return {
                "allowed": False,
                "reason": "NODE_NOT_FOUND",
                "node_id": node_id,
            }

        node.last_seen = _timestamp()
        node.state = ONLINE

        self._persist(node)

        return {
            "allowed": True,
            "reason": "HEARTBEAT_ACCEPTED",
            "node_id": node_id,
            "organization_id": (
                node.organization_id
            ),
            "state": node.state,
            "last_seen": node.last_seen,
        }

    def check_node(self, node_id):
        node = self.node_registry.get(
            node_id
        )

        if node is None:
            return {
                "found": False,
                "reason": "NODE_NOT_FOUND",
                "node_id": node_id,
            }

        if not node.last_seen:
            node.state = OFFLINE
            self._persist(node)

            return {
                "found": True,
                "online": False,
                "node_id": node_id,
                "state": OFFLINE,
                "reason": "NO_HEARTBEAT",
            }

        try:
            last_seen = _parse_timestamp(
                node.last_seen
            )
        except ValueError:
            node.state = OFFLINE
            self._persist(node)

            return {
                "found": True,
                "online": False,
                "node_id": node_id,
                "state": OFFLINE,
                "reason": "INVALID_LAST_SEEN",
            }

        age = (
            _now() - last_seen
        ).total_seconds()

        online = age <= self.timeout_seconds

        node.state = (
            ONLINE
            if online
            else OFFLINE
        )

        self._persist(node)

        return {
            "found": True,
            "online": online,
            "node_id": node_id,
            "organization_id": (
                node.organization_id
            ),
            "state": node.state,
            "last_seen": node.last_seen,
            "age_seconds": round(
                age,
                3,
            ),
            "timeout_seconds": (
                self.timeout_seconds
            ),
            "reason": (
                "HEALTHY"
                if online
                else "HEARTBEAT_TIMEOUT"
            ),
        }

    def check_all(self):
        results = []

        for node in self.node_registry.list():
            results.append(
                self.check_node(
                    node.node_id
                )
            )

        return results
