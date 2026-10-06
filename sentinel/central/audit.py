"""
Sentinel Central - Audit Manager.

Local audit trail for operational and security events.

Audit records are stored in the organization's
local Sentinel Central database.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


AUDIT_RESULTS = {
    "SUCCESS",
    "DENIED",
    "FAILURE",
    "INFO",
}


def _timestamp():
    return datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


@dataclass
class AuditEvent:
    event: str
    result: str = "INFO"
    organization_id: Optional[str] = None
    actor: Optional[str] = None
    resource: Optional[str] = None
    resource_id: Optional[str] = None
    metadata: Dict = field(
        default_factory=dict
    )
    timestamp: str = field(
        default_factory=_timestamp
    )

    def __post_init__(self):
        self.result = self.result.upper()

        if not self.event.strip():
            raise ValueError(
                "event cannot be empty"
            )

        if self.result not in AUDIT_RESULTS:
            raise ValueError(
                f"Unsupported audit result: "
                f"{self.result}"
            )

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "event": self.event,
            "result": self.result,
            "organization_id": self.organization_id,
            "actor": self.actor,
            "resource": self.resource,
            "resource_id": self.resource_id,
            "metadata": dict(self.metadata),
        }


class AuditManager:
    def __init__(self, storage):
        self.storage = storage

    def record(
        self,
        event,
        result="INFO",
        organization_id=None,
        actor=None,
        resource=None,
        resource_id=None,
        metadata=None,
    ):
        audit_event = AuditEvent(
            event=event,
            result=result,
            organization_id=organization_id,
            actor=actor,
            resource=resource,
            resource_id=resource_id,
            metadata=metadata or {},
        )

        self.storage.save_audit_event(
            audit_event
        )

        return audit_event

    def list(
        self,
        organization_id=None,
        limit=100,
    ):
        return self.storage.list_audit_events(
            organization_id=organization_id,
            limit=limit,
        )
