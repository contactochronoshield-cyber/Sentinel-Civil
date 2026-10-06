"""
Sentinel Central - Enterprise Limits.

Combines commercial license limits with
organization policy limits.

The effective limit is always the most restrictive
limit configured by either layer.
"""


class LimitController:
    def __init__(
        self,
        license_manager,
        policy_manager,
    ):
        self.license_manager = license_manager
        self.policy_manager = policy_manager

    def _active_license(self, organization_id):
        licenses = (
            self.license_manager
            .get_for_organization(
                organization_id
            )
        )

        for license in licenses:
            if license.is_active():
                return license

        return None

    def _policy(self, organization_id):
        return self.policy_manager.get(
            organization_id
        )

    @staticmethod
    def _effective_limit(
        license_limit,
        policy_limit,
    ):
        limits = [
            value
            for value in (
                license_limit,
                policy_limit,
            )
            if value is not None
        ]

        if not limits:
            return None

        return min(limits)

    def node_limit(self, organization_id):
        license = self._active_license(
            organization_id
        )

        if license is None:
            return {
                "allowed": False,
                "reason": "LICENSE_INACTIVE",
                "limit": None,
            }

        policy = self._policy(
            organization_id
        )

        if policy is None:
            return {
                "allowed": False,
                "reason": "POLICY_NOT_FOUND",
                "limit": None,
            }

        limit = self._effective_limit(
            license.max_nodes,
            policy.max_nodes,
        )

        return {
            "allowed": True,
            "reason": "LIMIT_CALCULATED",
            "limit": limit,
            "license_limit": license.max_nodes,
            "policy_limit": policy.max_nodes,
        }

    def user_limit(self, organization_id):
        license = self._active_license(
            organization_id
        )

        if license is None:
            return {
                "allowed": False,
                "reason": "LICENSE_INACTIVE",
                "limit": None,
            }

        policy = self._policy(
            organization_id
        )

        if policy is None:
            return {
                "allowed": False,
                "reason": "POLICY_NOT_FOUND",
                "limit": None,
            }

        limit = self._effective_limit(
            license.max_users,
            policy.max_users,
        )

        return {
            "allowed": True,
            "reason": "LIMIT_CALCULATED",
            "limit": limit,
            "license_limit": license.max_users,
            "policy_limit": policy.max_users,
        }

    def can_add_nodes(
        self,
        organization_id,
        current_nodes,
        additional_nodes=1,
    ):
        result = self.node_limit(
            organization_id
        )

        if not result["allowed"]:
            return result

        limit = result["limit"]

        if limit is None:
            allowed = True
        else:
            allowed = (
                current_nodes
                + additional_nodes
                <= limit
            )

        return {
            **result,
            "current": current_nodes,
            "requested": additional_nodes,
            "projected": (
                current_nodes
                + additional_nodes
            ),
            "allowed": allowed,
            "reason": (
                "WITHIN_LIMIT"
                if allowed
                else "NODE_LIMIT_EXCEEDED"
            ),
        }

    def can_add_users(
        self,
        organization_id,
        current_users,
        additional_users=1,
    ):
        result = self.user_limit(
            organization_id
        )

        if not result["allowed"]:
            return result

        limit = result["limit"]

        if limit is None:
            allowed = True
        else:
            allowed = (
                current_users
                + additional_users
                <= limit
            )

        return {
            **result,
            "current": current_users,
            "requested": additional_users,
            "projected": (
                current_users
                + additional_users
            ),
            "allowed": allowed,
            "reason": (
                "WITHIN_LIMIT"
                if allowed
                else "USER_LIMIT_EXCEEDED"
            ),
        }
