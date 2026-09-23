import os
import tempfile

from sentinel.asset_evidence import AssetEvidenceEngine


fd, db = tempfile.mkstemp(prefix="sentinel-asset-", suffix=".db")
os.close(fd)

engine = AssetEvidenceEngine(db)

asset = engine.register_asset(
    asset_id="RADIO-017",
    asset_type="RADIO",
    manufacturer="Chrono",
    model="CR-RADIO-01",
    firmware="1.0.0",
    authorization_state="AUTHORIZED",
)

assert asset["lifecycle_state"] == "PROVISIONED"

engine.observe(
    "RADIO-017",
    "ACTIVE",
    98,
    source="radio_monitor",
    measurements={
        "rssi": -61,
        "latency_ms": 21,
        "packet_loss_percent": 0.2,
    },
)

engine.observe(
    "RADIO-017",
    "DEGRADED",
    67,
    source="radio_monitor",
    measurements={
        "rssi": -78,
        "latency_ms": 119,
        "packet_loss_percent": 4.2,
    },
)

engine.record_incident(
    "RADIO-017",
    "RADIO_COMMUNICATION_DEGRADATION",
    confidence=0.88,
    evidence={
        "rssi_drop": True,
        "packet_loss_increase": True,
    },
)

engine.observe(
    "RADIO-017",
    "CRITICAL",
    32,
    source="radio_monitor",
    measurements={
        "rssi": -91,
        "latency_ms": 410,
        "packet_loss_percent": 31.0,
    },
)

engine.observe(
    "RADIO-017",
    "OFFLINE",
    0,
    source="radio_monitor",
)

engine.record_maintenance(
    "RADIO-017",
    action="RADIO_REPLACEMENT",
    result="REPLACED",
    evidence={
        "reason": "hardware_failure",
    },
)

engine.observe(
    "RADIO-017",
    "RECOVERED",
    96,
    source="maintenance",
)

asset = engine.get_asset("RADIO-017")
history = engine.history("RADIO-017")
events = engine.events("RADIO-017")

assert asset["asset_id"] == "RADIO-017"
assert asset["lifecycle_state"] == "RECOVERED"
assert len(history) == 5
assert len(events) >= 5

for observation in history:
    assert len(observation["evidence_hash"]) == 64

for event in events:
    assert len(event["evidence_hash"]) == 64

print("=== SENTINEL ASSET EVIDENCE ===")
print("VERSION:", engine.VERSION)
print("ASSET:", asset["asset_id"])
print("STATE:", asset["lifecycle_state"])
print("HISTORY:", len(history))
print("EVENTS:", len(events))
print("FIRST STATE:", history[0]["state"])
print("LAST STATE:", history[-1]["state"])
print("EVIDENCE HASH:", history[-1]["evidence_hash"])
print("ASSET_EVIDENCE_TEST=PASS")

engine.close()
os.unlink(db)
