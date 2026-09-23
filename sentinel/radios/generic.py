from .base import RadioAdapter


class GenericBluetoothAdapter(RadioAdapter):
    name = "generic-bluetooth"

    def identify(self, device):
        result = super().identify(device)

        result["vendor_adapter"] = self.name

        if not device.get("manufacturer"):
            result["status"] = "UNSUPPORTED"

        return result
