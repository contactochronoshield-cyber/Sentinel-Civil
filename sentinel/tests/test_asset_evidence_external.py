import os
import tempfile

from sentinel.asset_evidence import AssetEvidenceEngine


fd, db = tempfile.mkstemp(prefix="sentinel-external-", suffix=".db")
os.close(fd)

engine = AssetEvidenceEngine(db)

engine.register_asset(
    asset_id="RADIO-017",
    asset_type="RADIO",
    manufacturer="Chrono",
    model="CR-RADIO-01",
    firmware="1.0.0",
    authorization_state="AUTHORIZED",
)

radio_event = engine.record_external_event(
    asset_id="RADIO-017",
    source="radio_resources",
    event_type="RADIO_BATTERY_DRAIN_ANOMALY",
    severity="CRITICAL",
    state="CRITICAL",
    confidence=0.91,
    evidence={
        "battery_percent": 8,
    },
    source_integrity="SOURCE_UNHASHED",
)

rf_event = engine.record_external_event(
    asset_id="RADIO-017",
    source="rf_infrastructure",
    event_type="RF_INFRASTRUCTURE_DEGRADATION",
    severity="WARNING",
    state="DEGRADED",
    confidence=0.87,
    evidence={
        "snr_drop": True,
        "noise_increase": True,
    },
    source_integrity="SOURCE_HASHED",
)

site_event = engine.record_external_event(
    asset_id="RADIO-017",
    source="site_correlation",
    event_type="SITE_COMMUNICATION_DEGRADATION",
    severity="CRITICAL",
    state="CRITICAL",
    confidence=0.88,
    evidence={
        "affected_radios": 3,
        "affected_components": 1,
    },
    source_integrity="SOURCE_HASHED",
)

assert radio_event["source"] == "radio_resources"
assert rf_event["source"] == "rf_infrastructure"
assert site_event["source"] == "site_correlation"

assert radio_event["event_type"] == "RADIO_BATTERY_DRAIN_ANOMALY"
assert rf_event["event_type"] == "RF_INFRASTRUCTURE_DEGRADATION"
assert site_event["event_type"] == "SITE_COMMUNICATION_DEGRADATION"

assert len(radio_event["evidence_hash"]) == 64
assert len(rf_event["evidence_hash"]) == 64
assert len(site_event["evidence_hash"]) == 64

events = engine.events("RADIO-017")

assert len(events) == 4

sources = [event["source"] for event in events]

assert sources == [
    "asset_evidence",
    "radio_resources",
    "rf_infrastructure",
    "site_correlation",
]

print("=== SENTINEL ASSET EVIDENCE EXTERNAL EVENTS ===")
print("VERSION:", engine.VERSION)
print("EVENTS:", len(events))
print("RADIO EVENT:", radio_event["event_type"])
print("RF EVENT:", rf_event["event_type"])
print("SITE EVENT:", site_event["event_type"])
print("RADIO INTEGRITY:", radio_event["source_integrity"])
print("RF INTEGRITY:", rf_event["source_integrity"])
print("SITE INTEGRITY:", site_event["source_integrity"])
print("ASSET_EVIDENCE_EXTERNAL_TEST=PASS")

engine.close()
os.unlink(db)
