"""
Sentinel Central - Organization Context.

Defines the organization identity under which an
Enterprise operation is executed.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OrganizationContext:
    organization_id: str
    actor: str = "SYSTEM"

    def __post_init__(self):
        if not self.organization_id.strip():
            raise ValueError(
                "organization_id cannot be empty"
            )

        if not self.actor.strip():
            raise ValueError(
                "actor cannot be empty"
            )
