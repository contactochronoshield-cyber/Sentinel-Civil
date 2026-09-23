class RadioAdapter:
    """
    Base interface for authorized radio vendor adapters.

    Adapters must never bypass authentication or undocumented APIs.
    """

    name = "generic"
    manufacturers = ()

    def supports(self, device):
        manufacturer = (
            device.get("manufacturer") or ""
        ).lower()

        return any(
            vendor.lower() in manufacturer
            for vendor in self.manufacturers
        )

    def identify(self, device):
        return {
            "manufacturer": device.get("manufacturer"),
            "model": device.get("model"),
            "firmware": device.get("firmware"),
            "vendor_adapter": self.name,
            "status": "SUPPORTED",
        }

    def telemetry(self, device):
        return {
            "status": "UNSUPPORTED"
        }
