"""
Sentinel Central - Node Registry.

Registers Sentinel nodes under an organization,
enforces Enterprise node limits, and optionally
persists nodes using CentralStorage.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


NODE_STATES = {
    "ONLINE",
    "OFFLINE",
    "DEGRADED",
    "MAINTENANCE",
    "UNKNOWN",
}


def _timestamp():
    return datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


@dataclass
class CentralNode:
    node_id: str
    organization_id: str
    name: str
    node_type: str = "SENTINEL_CIVIL"
    state: str = "UNKNOWN"
    version: Optional[str] = None
    location: Optional[str] = None
    last_seen: Optional[str] = None
    metadata: Dict = field(
        default_factory=dict
    )

    def __post_init__(self):
        self.state = self.state.upper()

        if not self.node_id.strip():
            raise ValueError(
                "node_id cannot be empty"
            )

        if not self.organization_id.strip():
            raise ValueError(
                "organization_id cannot be empty"
            )

        if not self.name.strip():
            raise ValueError(
                "node name cannot be empty"
            )

        if self.state not in NODE_STATES:
            raise ValueError(
                f"Unsupported node state: {self.state}"
            )

        if self.last_seen is None:
            self.last_seen = _timestamp()

    def mark_seen(self):
        self.last_seen = _timestamp()

    def set_state(self, state):
        state = state.upper()

        if state not in NODE_STATES:
            raise ValueError(
                f"Unsupported node state: {state}"
            )

        self.state = state
        self.mark_seen()

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "organization_id": self.organization_id,
            "name": self.name,
            "node_type": self.node_type,
            "state": self.state,
            "version": self.version,
            "location": self.location,
            "last_seen": self.last_seen,
            "metadata": dict(self.metadata),
        }


class NodeRegistry:
    def __init__(
        self,
        organization_registry,
        limit_controller,
        storage=None,
    ):
        self.organization_registry = (
            organization_registry
        )
        self.limit_controller = (
            limit_controller
        )
        self.storage = storage
        self._nodes = {}

    def register(self, node):
        if not isinstance(
            node,
            CentralNode,
        ):
            raise TypeError(
                "node must be a CentralNode"
            )

        if node.node_id in self._nodes:
            raise ValueError(
                f"Node already registered: "
                f"{node.node_id}"
            )

        organization = (
            self.organization_registry.get(
                node.organization_id
            )
        )

        if organization is None:
            return {
                "allowed": False,
                "reason": "ORGANIZATION_NOT_FOUND",
                "node_id": node.node_id,
                "organization_id": (
                    node.organization_id
                ),
            }

        current_count = self.count(
            node.organization_id
        )

        limit_result = (
            self.limit_controller.can_add_nodes(
                node.organization_id,
                current_count,
                1,
            )
        )

        if not limit_result["allowed"]:
            return {
                **limit_result,
                "node_id": node.node_id,
                "organization_id": (
                    node.organization_id
                ),
                "reason": (
                    "NODE_REGISTRATION_DENIED"
                    if limit_result["reason"]
                    == "NODE_LIMIT_EXCEEDED"
                    else limit_result["reason"]
                ),
            }

        self._nodes[node.node_id] = node

        if self.storage is not None:
            self.storage.save_node(node)

        return {
            "allowed": True,
            "reason": "NODE_REGISTERED",
            "node_id": node.node_id,
            "organization_id": (
                node.organization_id
            ),
            "current": current_count + 1,
            "limit": limit_result["limit"],
        }

    def get(self, node_id):
        node = self._nodes.get(node_id)

        if node is not None:
            return node

        if self.storage is not None:
            data = self.storage.get_node(
                node_id
            )

            if data is not None:
                node = CentralNode(**data)
                self._nodes[node_id] = node
                return node

        return None

    def exists(self, node_id):
        return self.get(node_id) is not None

    def remove(self, node_id):
        node = self._nodes.pop(
            node_id,
            None,
        )

        if self.storage is not None:
            self.storage.delete_node(
                node_id
            )

        return node

    def list(self):
        if self.storage is not None:
            stored_nodes = self.storage.list_nodes()

            for data in stored_nodes:
                node_id = data["node_id"]

                if node_id not in self._nodes:
                    self._nodes[node_id] = (
                        CentralNode(**data)
                    )

        return list(
            self._nodes.values()
        )

    def list_for_organization(
        self,
        organization_id,
    ):
        return [
            node
            for node in self.list()
            if node.organization_id
            == organization_id
        ]

    def count(self, organization_id=None):
        if organization_id is None:
            return len(self.list())

        return len(
            self.list_for_organization(
                organization_id
            )
        )

    def save(self, node):
        if node.node_id not in self._nodes:
            raise KeyError(node.node_id)

        if self.storage is not None:
            self.storage.save_node(node)

    def export(self):
        return [
            node.to_dict()
            for node in self.list()
        ]
