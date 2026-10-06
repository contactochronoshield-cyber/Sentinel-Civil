"""
Sentinel Central - Central Service.

Main orchestration and recovery layer.
"""

from .organization import Organization
from .licensing import EnterpriseLicense
from .policy import OrganizationPolicy
from .node_registry import CentralNode
from .storage import CentralStorage

from .registry import OrganizationRegistry
from .licensing import LicenseManager
from .policy import PolicyManager
from .limits import LimitController
from .access import AccessController
from .node_registry import NodeRegistry
from .node_health import NodeHealthManager
from .audit import AuditManager


class CentralService:
    def __init__(
        self,
        database_path,
        health_timeout_seconds=300,
    ):
        self.storage = CentralStorage(
            database_path
        )

        self.organizations = (
            OrganizationRegistry()
        )

        self.licenses = LicenseManager()

        self.policies = PolicyManager()

        self.limits = LimitController(
            license_manager=self.licenses,
            policy_manager=self.policies,
        )

        self.access = AccessController(
            organization_registry=self.organizations,
            license_manager=self.licenses,
            policy_manager=self.policies,
        )

        self.nodes = NodeRegistry(
            organization_registry=self.organizations,
            limit_controller=self.limits,
            storage=self.storage,
        )

        self.audit = AuditManager(
            self.storage
        )

        self.health = NodeHealthManager(
            node_registry=self.nodes,
            timeout_seconds=health_timeout_seconds,
            storage=self.storage,
        )

        self.restore()

        self.audit.record(
            event="SYSTEM_STARTED",
            result="SUCCESS",
            actor="SYSTEM",
        )

    def restore(self):
        for data in (
            self.storage.list_organizations()
        ):
            organization = Organization(
                **data
            )

            if not self.organizations.exists(
                organization.organization_id
            ):
                self.organizations.register(
                    organization
                )

        for data in (
            self.storage.list_licenses()
        ):
            license = EnterpriseLicense(
                **data
            )

            if self.licenses.get(
                license.license_id
            ) is None:
                self.licenses.register(
                    license
                )

        for data in (
            self.storage.list_policies()
        ):
            policy = OrganizationPolicy(
                **data
            )

            if self.policies.get(
                policy.organization_id
            ) is None:
                self.policies.register(
                    policy
                )

        return {
            "organizations": (
                self.organizations.count()
            ),
            "licenses": len(
                self.licenses.list()
            ),
            "policies": len(
                self.policies.list()
            ),
            "nodes": self.nodes.count(),
        }

    def register_organization(
        self,
        organization,
    ):
        result = self.organizations.register(
            organization
        )

        self.storage.save_organization(
            organization
        )

        self.audit.record(
            event="ORGANIZATION_CREATED",
            result="SUCCESS",
            organization_id=(
                organization.organization_id
            ),
            actor="SYSTEM",
            resource="ORGANIZATION",
            resource_id=(
                organization.organization_id
            ),
        )

        return result

    def register_license(
        self,
        license,
    ):
        result = self.licenses.register(
            license
        )

        self.storage.save_license(
            license
        )

        self.audit.record(
            event="LICENSE_CREATED",
            result="SUCCESS",
            organization_id=(
                license.organization_id
            ),
            actor="SYSTEM",
            resource="LICENSE",
            resource_id=(
                license.license_id
            ),
            metadata={
                "plan": license.plan
            },
        )

        return result

    def approve_license(
        self,
        license_id,
        actor="SYSTEM",
    ):
        license = self.licenses.get(
            license_id
        )

        if license is None:
            self.audit.record(
                event="LICENSE_APPROVAL",
                result="FAILURE",
                actor=actor,
                resource="LICENSE",
                resource_id=license_id,
                metadata={
                    "reason": "LICENSE_NOT_FOUND"
                },
            )

            return {
                "allowed": False,
                "reason": "LICENSE_NOT_FOUND",
            }

        license.approve()

        self.storage.save_license(
            license
        )

        self.audit.record(
            event="LICENSE_APPROVED",
            result="SUCCESS",
            organization_id=(
                license.organization_id
            ),
            actor=actor,
            resource="LICENSE",
            resource_id=license.license_id,
        )

        return license

    def activate_license(
        self,
        license_id,
        actor="SYSTEM",
    ):
        license = self.licenses.get(
            license_id
        )

        if license is None:
            self.audit.record(
                event="LICENSE_ACTIVATION",
                result="FAILURE",
                actor=actor,
                resource="LICENSE",
                resource_id=license_id,
                metadata={
                    "reason": "LICENSE_NOT_FOUND"
                },
            )

            return {
                "allowed": False,
                "reason": "LICENSE_NOT_FOUND",
            }

        license.activate()

        self.storage.save_license(
            license
        )

        self.audit.record(
            event="LICENSE_ACTIVATED",
            result="SUCCESS",
            organization_id=(
                license.organization_id
            ),
            actor=actor,
            resource="LICENSE",
            resource_id=license.license_id,
        )

        return license

    def suspend_license(self, context, license_id):
        license_obj = self.licenses.get(license_id)

        if license_obj is None:
            self.audit.record(
                event="ACCESS_DENIED",
                result="DENIED",
                organization_id=context.organization_id,
                actor=context.actor,
                resource="LICENSE",
                resource_id=license_id,
                metadata={
                    "reason": "LICENSE_NOT_FOUND",
                },
            )

            return {
                "allowed": False,
                "reason": "LICENSE_NOT_FOUND",
                "license": None,
            }

        if license_obj.organization_id != context.organization_id:
            self.audit.record(
                event="ACCESS_DENIED",
                result="DENIED",
                organization_id=context.organization_id,
                actor=context.actor,
                resource="LICENSE",
                resource_id=license_id,
                metadata={
                    "reason": "CROSS_ORGANIZATION_ACCESS",
                    "owner_organization_id":
                        license_obj.organization_id,
                },
            )

            return {
                "allowed": False,
                "reason": "CROSS_ORGANIZATION_ACCESS",
                "license": None,
            }

        if license_obj.status != "ACTIVE":
            self.audit.record(
                event="LICENSE_SUSPEND_DENIED",
                result="DENIED",
                organization_id=context.organization_id,
                actor=context.actor,
                resource="LICENSE",
                resource_id=license_id,
                metadata={
                    "reason": "LICENSE_NOT_ACTIVE",
                    "status": license_obj.status,
                },
            )

            return {
                "allowed": False,
                "reason": "LICENSE_NOT_ACTIVE",
                "license": license_obj,
            }

        license_obj.suspend()
        self.storage.save_license(license_obj)

        self.audit.record(
            event="LICENSE_SUSPENDED",
            result="SUCCESS",
            organization_id=context.organization_id,
            actor=context.actor,
            resource="LICENSE",
            resource_id=license_id,
        )

        return {
            "allowed": True,
            "reason": "LICENSE_SUSPENDED",
            "license": license_obj,
        }

    def register_policy(
        self,
        policy,
    ):
        result = self.policies.register(
            policy
        )

        self.storage.save_policy(
            policy
        )

        self.audit.record(
            event="POLICY_CREATED",
            result="SUCCESS",
            organization_id=(
                policy.organization_id
            ),
            actor="SYSTEM",
            resource="POLICY",
            resource_id=(
                policy.organization_id
            ),
        )

        return result

    def check_feature_access(
        self,
        organization_id,
        feature,
        actor="SYSTEM",
    ):
        result = self.access.can_use_feature(
            organization_id,
            feature,
        )

        self.audit.record(
            event=(
                "ACCESS_ALLOWED"
                if result["allowed"]
                else "ACCESS_DENIED"
            ),
            result=(
                "SUCCESS"
                if result["allowed"]
                else "DENIED"
            ),
            organization_id=organization_id,
            actor=actor,
            resource="FEATURE",
            resource_id=feature,
            metadata={
                "reason": result["reason"],
            },
        )

        return result

    def register_node(
        self,
        node,
        actor="SYSTEM",
    ):
        result = self.nodes.register(
            node
        )

        self.audit.record(
            event=(
                "NODE_REGISTERED"
                if result["allowed"]
                else "NODE_REGISTRATION_DENIED"
            ),
            result=(
                "SUCCESS"
                if result["allowed"]
                else "DENIED"
            ),
            organization_id=(
                node.organization_id
            ),
            actor=actor,
            resource="NODE",
            resource_id=node.node_id,
            metadata={
                "reason": result["reason"]
            },
        )

        return result

    def heartbeat(
        self,
        node_id,
        actor="NODE",
    ):
        result = self.health.heartbeat(
            node_id
        )

        self.audit.record(
            event="NODE_HEARTBEAT",
            result=(
                "SUCCESS"
                if result["allowed"]
                else "FAILURE"
            ),
            organization_id=result.get(
                "organization_id"
            ),
            actor=actor,
            resource="NODE",
            resource_id=node_id,
            metadata={
                "state": result.get(
                    "state"
                ),
                "reason": result.get(
                    "reason"
                ),
            },
        )

        return result

    def check_node(
        self,
        node_id,
    ):
        result = self.health.check_node(
            node_id
        )

        if result.get("found"):
            self.audit.record(
                event="NODE_HEALTH_CHECK",
                result=(
                    "SUCCESS"
                    if result.get("online")
                    else "FAILURE"
                ),
                organization_id=(
                    result.get(
                        "organization_id"
                    )
                ),
                actor="SYSTEM",
                resource="NODE",
                resource_id=node_id,
                metadata={
                    "state": result.get(
                        "state"
                    ),
                    "reason": result.get(
                        "reason"
                    ),
                },
            )

        return result

    def check_all_nodes(self):
        return self.health.check_all()

    def get_node_for_organization(
        self,
        context,
        node_id,
    ):
        node = self.nodes.get(node_id)

        if node is None:
            self.audit.record(
                event="ACCESS_DENIED",
                result="DENIED",
                organization_id=context.organization_id,
                actor=context.actor,
                resource="NODE",
                resource_id=node_id,
                metadata={
                    "reason": "NODE_NOT_FOUND",
                },
            )

            return {
                "allowed": False,
                "reason": "NODE_NOT_FOUND",
                "node": None,
            }

        if (
            node.organization_id
            != context.organization_id
        ):
            self.audit.record(
                event="ACCESS_DENIED",
                result="DENIED",
                organization_id=context.organization_id,
                actor=context.actor,
                resource="NODE",
                resource_id=node_id,
                metadata={
                    "reason": (
                        "CROSS_ORGANIZATION_ACCESS"
                    ),
                    "owner_organization_id": (
                        node.organization_id
                    ),
                },
            )

            return {
                "allowed": False,
                "reason": (
                    "CROSS_ORGANIZATION_ACCESS"
                ),
                "node": None,
            }

        self.audit.record(
            event="ACCESS_ALLOWED",
            result="SUCCESS",
            organization_id=context.organization_id,
            actor=context.actor,
            resource="NODE",
            resource_id=node_id,
            metadata={
                "reason": (
                    "ORGANIZATION_ACCESS_ALLOWED"
                ),
            },
        )

        return {
            "allowed": True,
            "reason": (
                "ORGANIZATION_ACCESS_ALLOWED"
            ),
            "node": node,
        }

    def get_license_for_organization(
        self,
        context,
        license_id,
    ):
        license_obj = self.licenses.get(
            license_id
        )

        if license_obj is None:
            self.audit.record(
                event="ACCESS_DENIED",
                result="DENIED",
                organization_id=context.organization_id,
                actor=context.actor,
                resource="LICENSE",
                resource_id=license_id,
                metadata={
                    "reason": "LICENSE_NOT_FOUND",
                },
            )

            return {
                "allowed": False,
                "reason": "LICENSE_NOT_FOUND",
                "license": None,
            }

        if (
            license_obj.organization_id
            != context.organization_id
        ):
            self.audit.record(
                event="ACCESS_DENIED",
                result="DENIED",
                organization_id=context.organization_id,
                actor=context.actor,
                resource="LICENSE",
                resource_id=license_id,
                metadata={
                    "reason": "CROSS_ORGANIZATION_ACCESS",
                    "owner_organization_id": (
                        license_obj.organization_id
                    ),
                },
            )

            return {
                "allowed": False,
                "reason": "CROSS_ORGANIZATION_ACCESS",
                "license": None,
            }

        self.audit.record(
            event="ACCESS_ALLOWED",
            result="SUCCESS",
            organization_id=context.organization_id,
            actor=context.actor,
            resource="LICENSE",
            resource_id=license_id,
            metadata={
                "reason": "ORGANIZATION_ACCESS_ALLOWED",
            },
        )

        return {
            "allowed": True,
            "reason": "ORGANIZATION_ACCESS_ALLOWED",
            "license": license_obj,
        }

    def get_policy_for_organization(
        self,
        context,
        organization_id,
    ):
        policy = self.policies.get(
            organization_id
        )

        if policy is None:
            self.audit.record(
                event="ACCESS_DENIED",
                result="DENIED",
                organization_id=context.organization_id,
                actor=context.actor,
                resource="POLICY",
                resource_id=organization_id,
                metadata={
                    "reason": "POLICY_NOT_FOUND",
                },
            )

            return {
                "allowed": False,
                "reason": "POLICY_NOT_FOUND",
                "policy": None,
            }

        if (
            policy.organization_id
            != context.organization_id
        ):
            self.audit.record(
                event="ACCESS_DENIED",
                result="DENIED",
                organization_id=context.organization_id,
                actor=context.actor,
                resource="POLICY",
                resource_id=organization_id,
                metadata={
                    "reason": "CROSS_ORGANIZATION_ACCESS",
                    "owner_organization_id": (
                        policy.organization_id
                    ),
                },
            )

            return {
                "allowed": False,
                "reason": "CROSS_ORGANIZATION_ACCESS",
                "policy": None,
            }

        self.audit.record(
            event="ACCESS_ALLOWED",
            result="SUCCESS",
            organization_id=context.organization_id,
            actor=context.actor,
            resource="POLICY",
            resource_id=organization_id,
            metadata={
                "reason": "ORGANIZATION_ACCESS_ALLOWED",
            },
        )

        return {
            "allowed": True,
            "reason": "ORGANIZATION_ACCESS_ALLOWED",
            "policy": policy,
        }

    def register_node_for_organization(
        self,
        context,
        node,
    ):
        if node.organization_id != context.organization_id:
            self.audit.record(
                event="ACCESS_DENIED",
                result="DENIED",
                organization_id=context.organization_id,
                actor=context.actor,
                resource="NODE",
                resource_id=node.node_id,
                metadata={
                    "reason": "CROSS_ORGANIZATION_ACCESS",
                    "target_organization_id": (
                        node.organization_id
                    ),
                },
            )

            return {
                "allowed": False,
                "reason": "CROSS_ORGANIZATION_ACCESS",
                "node": None,
            }

        result = self.register_node(node)

        if result.get("allowed"):
            return {
                **result,
                "node": node,
            }

        return {
            **result,
            "node": None,
        }

    def close(self):
        self.storage.close()
