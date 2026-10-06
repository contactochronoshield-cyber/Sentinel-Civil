"""
Sentinel Central - Organization Registry.

Keeps a local registry of organizations managed by
a Sentinel Central instance.

This module does not handle authentication or licensing.
"""

from .organization import Organization


class OrganizationRegistry:
    def __init__(self):
        self._organizations = {}

    def register(self, organization):
        if not isinstance(organization, Organization):
            raise TypeError(
                "organization must be an Organization"
            )

        organization_id = organization.organization_id

        if organization_id in self._organizations:
            raise ValueError(
                f"Organization already registered: "
                f"{organization_id}"
            )

        self._organizations[organization_id] = organization

        return organization

    def get(self, organization_id):
        return self._organizations.get(
            organization_id
        )

    def exists(self, organization_id):
        return organization_id in self._organizations

    def remove(self, organization_id):
        return self._organizations.pop(
            organization_id,
            None,
        )

    def list(self):
        return list(
            self._organizations.values()
        )

    def count(self):
        return len(self._organizations)

    def export(self):
        return [
            organization.to_dict()
            for organization in self.list()
        ]
