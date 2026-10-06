"""
Sentinel Central - Organization Policies.

Defines operational rules for an organization.
Policies are separate from commercial licensing.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class OrganizationPolicy:
    organization_id: str

    max_nodes: Optional[int] = None
    max_users: Optional[int] = None

    audit_enabled: bool = True
    fieldproof_required: bool = False
    custom_branding_allowed: bool = False

    retention_days: Optional[int] = None

    allowed_features: Dict[str, bool] = field(
        default_factory=dict
    )

    metadata: Dict = field(
        default_factory=dict
    )

    def __post_init__(self):
        if not self.organization_id.strip():
            raise ValueError(
                "organization_id cannot be empty"
            )

        if (
            self.max_nodes is not None
            and self.max_nodes < 1
        ):
            raise ValueError(
                "max_nodes must be positive"
            )

        if (
            self.max_users is not None
            and self.max_users < 1
        ):
            raise ValueError(
                "max_users must be positive"
            )

        if (
            self.retention_days is not None
            and self.retention_days < 1
        ):
            raise ValueError(
                "retention_days must be positive"
            )

    def allows_feature(self, feature):
        return bool(
            self.allowed_features.get(
                feature,
                False,
            )
        )

    def allows_nodes(self, node_count):
        if self.max_nodes is None:
            return True

        return node_count <= self.max_nodes

    def allows_users(self, user_count):
        if self.max_users is None:
            return True

        return user_count <= self.max_users

    def to_dict(self):
        return {
            "organization_id": self.organization_id,
            "max_nodes": self.max_nodes,
            "max_users": self.max_users,
            "audit_enabled": self.audit_enabled,
            "fieldproof_required": self.fieldproof_required,
            "custom_branding_allowed": (
                self.custom_branding_allowed
            ),
            "retention_days": self.retention_days,
            "allowed_features": dict(
                self.allowed_features
            ),
            "metadata": dict(self.metadata),
        }


class PolicyManager:
    def __init__(self):
        self._policies = {}

    def register(self, policy):
        if not isinstance(
            policy,
            OrganizationPolicy,
        ):
            raise TypeError(
                "policy must be an OrganizationPolicy"
            )

        organization_id = policy.organization_id

        if organization_id in self._policies:
            raise ValueError(
                f"Policy already registered: "
                f"{organization_id}"
            )

        self._policies[
            organization_id
        ] = policy

        return policy

    def get(self, organization_id):
        return self._policies.get(
            organization_id
        )

    def remove(self, organization_id):
        return self._policies.pop(
            organization_id,
            None,
        )

    def list(self):
        return list(
            self._policies.values()
        )

    def export(self):
        return [
            policy.to_dict()
            for policy in self.list()
        ]
