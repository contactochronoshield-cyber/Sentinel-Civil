"""
Sentinel Central - Enterprise Access Control.

Combines organization, licensing and policy decisions.
This module does not provide authentication.
"""

from .organization import Organization
from .licensing import EnterpriseLicense
from .policy import OrganizationPolicy


ALLOWED = "ALLOWED"
DENIED = "DENIED"


class AccessController:
    def __init__(
        self,
        organization_registry,
        license_manager,
        policy_manager,
    ):
        self.organization_registry = (
            organization_registry
        )
        self.license_manager = license_manager
        self.policy_manager = policy_manager

    def can_use_feature(
        self,
        organization_id,
        feature,
    ):
        organization = (
            self.organization_registry.get(
                organization_id
            )
        )

        if not isinstance(
            organization,
            Organization,
        ):
            return {
                "allowed": False,
                "status": DENIED,
                "reason": "ORGANIZATION_NOT_FOUND",
                "organization_id": organization_id,
                "feature": feature,
            }

        licenses = (
            self.license_manager
            .get_for_organization(
                organization_id
            )
        )

        active_license = None

        for license in licenses:
            if license.is_active():
                active_license = license
                break

        if not isinstance(
            active_license,
            EnterpriseLicense,
        ):
            return {
                "allowed": False,
                "status": DENIED,
                "reason": "LICENSE_INACTIVE",
                "organization_id": organization_id,
                "feature": feature,
            }

        if not active_license.allows_feature(
            feature
        ):
            return {
                "allowed": False,
                "status": DENIED,
                "reason": "LICENSE_FEATURE_DISABLED",
                "organization_id": organization_id,
                "feature": feature,
                "license_id": (
                    active_license.license_id
                ),
            }

        policy = self.policy_manager.get(
            organization_id
        )

        if not isinstance(
            policy,
            OrganizationPolicy,
        ):
            return {
                "allowed": False,
                "status": DENIED,
                "reason": "POLICY_NOT_FOUND",
                "organization_id": organization_id,
                "feature": feature,
                "license_id": (
                    active_license.license_id
                ),
            }

        if not policy.allows_feature(
            feature
        ):
            return {
                "allowed": False,
                "status": DENIED,
                "reason": "POLICY_FEATURE_DISABLED",
                "organization_id": organization_id,
                "feature": feature,
                "license_id": (
                    active_license.license_id
                ),
            }

        return {
            "allowed": True,
            "status": ALLOWED,
            "reason": (
                "LICENSE_AND_POLICY_ALLOW"
            ),
            "organization_id": organization_id,
            "feature": feature,
            "license_id": (
                active_license.license_id
            ),
        }
