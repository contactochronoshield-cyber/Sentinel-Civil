"""
Sentinel Central - Enterprise Licensing.

Local license model for Sentinel Central Enterprise.

This module does not contact Chrono Shield Networks
and does not affect Sentinel Civil Community.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


LICENSE_STATUSES = {
    "PENDING",
    "APPROVED",
    "ACTIVE",
    "SUSPENDED",
    "EXPIRED",
    "REVOKED",
}

PLANS = {
    "PROFESSIONAL",
    "ENTERPRISE",
    "GOVERNMENT",
}


def _now():
    return datetime.now(timezone.utc)


def _timestamp(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    return str(value)


@dataclass
class EnterpriseLicense:
    license_id: str
    organization_id: str
    plan: str
    status: str = "PENDING"
    issued_at: Optional[str] = None
    expires_at: Optional[str] = None
    max_nodes: Optional[int] = None
    max_users: Optional[int] = None
    features: Dict[str, bool] = field(
        default_factory=dict
    )
    metadata: Dict = field(
        default_factory=dict
    )

    def __post_init__(self):
        self.plan = self.plan.upper()
        self.status = self.status.upper()

        if not self.license_id.strip():
            raise ValueError(
                "license_id cannot be empty"
            )

        if not self.organization_id.strip():
            raise ValueError(
                "organization_id cannot be empty"
            )

        if self.plan not in PLANS:
            raise ValueError(
                f"Unsupported license plan: {self.plan}"
            )

        if self.status not in LICENSE_STATUSES:
            raise ValueError(
                f"Unsupported license status: {self.status}"
            )

        if self.max_nodes is not None and self.max_nodes < 1:
            raise ValueError(
                "max_nodes must be positive"
            )

        if self.max_users is not None and self.max_users < 1:
            raise ValueError(
                "max_users must be positive"
            )

        if self.issued_at is None:
            self.issued_at = _timestamp(_now())

    def approve(self):
        if self.status != "PENDING":
            raise ValueError(
                "Only PENDING licenses can be approved"
            )

        self.status = "APPROVED"
        return self

    def activate(self):
        if self.status != "APPROVED":
            raise ValueError(
                "Only APPROVED licenses can be activated"
            )

        self.status = "ACTIVE"
        return self

    def suspend(self):
        if self.status != "ACTIVE":
            raise ValueError(
                "Only ACTIVE licenses can be suspended"
            )

        self.status = "SUSPENDED"
        return self

    def revoke(self):
        if self.status == "REVOKED":
            return self

        self.status = "REVOKED"
        return self

    def is_expired(self):
        if not self.expires_at:
            return False

        try:
            expires = datetime.fromisoformat(
                self.expires_at.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            return True

        return _now() >= expires

    def is_active(self):
        if self.status != "ACTIVE":
            return False

        if self.is_expired():
            self.status = "EXPIRED"
            return False

        return True

    def allows_feature(self, feature):
        if not self.is_active():
            return False

        return bool(
            self.features.get(feature, False)
        )

    def allows_nodes(self, node_count):
        if not self.is_active():
            return False

        if self.max_nodes is None:
            return True

        return node_count <= self.max_nodes

    def allows_users(self, user_count):
        if not self.is_active():
            return False

        if self.max_users is None:
            return True

        return user_count <= self.max_users

    def to_dict(self):
        return {
            "license_id": self.license_id,
            "organization_id": self.organization_id,
            "plan": self.plan,
            "status": self.status,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "max_nodes": self.max_nodes,
            "max_users": self.max_users,
            "features": dict(self.features),
            "metadata": dict(self.metadata),
        }


class LicenseManager:
    def __init__(self):
        self._licenses = {}

    def register(self, license):
        if not isinstance(
            license,
            EnterpriseLicense,
        ):
            raise TypeError(
                "license must be an EnterpriseLicense"
            )

        if license.license_id in self._licenses:
            raise ValueError(
                f"License already registered: "
                f"{license.license_id}"
            )

        self._licenses[
            license.license_id
        ] = license

        return license

    def get(self, license_id):
        return self._licenses.get(
            license_id
        )

    def get_for_organization(
        self,
        organization_id,
    ):
        return [
            license
            for license in self._licenses.values()
            if license.organization_id
            == organization_id
        ]

    def revoke(self, license_id):
        license = self.get(license_id)

        if license is None:
            raise KeyError(license_id)

        license.revoke()

        return license

    def list(self):
        return list(
            self._licenses.values()
        )

    def export(self):
        return [
            license.to_dict()
            for license in self.list()
        ]
