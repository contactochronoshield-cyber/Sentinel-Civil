"""
Sentinel Central - Organization Core.

Defines the identity of an organization operating Sentinel Central.
This module does not grant Enterprise access by itself.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


ORGANIZATION_TYPES = {
    "ISP",
    "WISP",
    "GOVERNMENT",
    "COMPANY",
    "UNIVERSITY",
    "COMMUNITY",
    "NONPROFIT",
    "OTHER",
}

LEGAL_STATUSES = {
    "REGISTERED",
    "UNREGISTERED_GROUP",
    "PUBLIC_ENTITY",
    "PRIVATE_ENTITY",
    "UNKNOWN",
}


@dataclass
class Organization:
    organization_id: str
    name: str
    organization_type: str
    legal_status: str
    country: Optional[str] = None
    website: Optional[str] = None
    contact_email: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    def __post_init__(self):
        self.organization_type = self.organization_type.upper()
        self.legal_status = self.legal_status.upper()

        if self.organization_type not in ORGANIZATION_TYPES:
            raise ValueError(
                f"Unsupported organization type: "
                f"{self.organization_type}"
            )

        if self.legal_status not in LEGAL_STATUSES:
            raise ValueError(
                f"Unsupported legal status: "
                f"{self.legal_status}"
            )

        if not self.organization_id.strip():
            raise ValueError(
                "organization_id cannot be empty"
            )

        if not self.name.strip():
            raise ValueError(
                "organization name cannot be empty"
            )

    def to_dict(self):
        return {
            "organization_id": self.organization_id,
            "name": self.name,
            "organization_type": self.organization_type,
            "legal_status": self.legal_status,
            "country": self.country,
            "website": self.website,
            "contact_email": self.contact_email,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }
