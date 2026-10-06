"""
Sentinel Central - Organization Branding.

Stores presentation metadata used by reports,
certificates and dashboards.
"""


from dataclasses import dataclass
from typing import Optional


@dataclass
class OrganizationBranding:
    display_name: str
    logo_path: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    footer_text: Optional[str] = None

    def to_dict(self):
        return {
            "display_name": self.display_name,
            "logo_path": self.logo_path,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "footer_text": self.footer_text,
        }
