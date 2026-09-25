import os
import tempfile

from sentinel.asset_evidence import AssetEvidenceEngine
from sentinel.fiber_pON_intelligence import FiberPONIntelligence


fd, db = tempfile.mkstemp(
    prefix="sentinel-fiber-evidence-",
    suffix=".db",
)
os.close(fd)

asset_engine = AssetEvidenceEngine(db)
fiber_engine = FiberPONIntelligence()


# ============================================================
# 1. Registrar el activo en Asset Evidence
# ============================================================

asset_engine.register_asset(
    asset_id="ONT-017",
    asset_type="ONT",
    manufacturer="GENERIC",
    model="LAB-ONT",
    firmware="1.0.0",
    authorization_state="AUTHORIZED",
)


# ============================================================
# 2. Registrar la topología en Fiber/PON
# ============================================================

fiber_engine.register_asset(
    "OLT-BOG-01",
    "OLT",
    site_id="SITE-BOG-01",
    vendor="GENERIC",
    model="LAB-OLT",
)

fiber_engine.register_asset(
    "FDH-BOG-07",
    "FDH",
    site_id="SITE-BOG-01",
    parent_id="OLT-BOG-01",
)

fiber_engine.register_asset(
    "SPLITTER-07",
    "SPLITTER",
    site_id="SITE-BOG-01",
    parent_id="FDH-BOG-07",
)

fiber_engine.register_asset(
    "ONT-017",
    "ONT",
    site_id="SITE-BOG-01",
    parent_id="SPLITTER-07",
)


# ============================================================
# 3. Observación óptica
# ============================================================

observation = fiber_engine.observe(
    "ONT-017",
    rx_power_dbm=-26.0,
    tx_power_dbm=1.8,
    temperature_c=41.0,
    voltage_v=3.3,
    laser_bias_ma=19.0,
    signal_loss_db=3.8,
    link_state="UP",
    source="LAB",
)

assert observation["state"] == "DEGRADED"


# ============================================================
# 4. Evento Fiber/PON
# ============================================================

fiber_hash = fiber_engine.record_event(
    "ONT-017",
    "OPTICAL_DEGRADATION",
    "MEDIUM",
    "Optical degradation observed",
    {
        "rx_power_dbm": -26.0,
        "signal_loss_db": 3.8,
        "source": "LAB",
    },
    source="LAB",
)

assert len(fiber_hash) == 64


# ============================================================
# 5. Normalizar hacia Asset Evidence
# ============================================================

external_event = asset_engine.record_external_event(
    asset_id="ONT-017",
    source="fiber_pon_intelligence",
    event_type="OPTICAL_DEGRADATION",
    severity="WARNING",
    state="DEGRADED",
    confidence=0.90,
    evidence={
        "fiber_event_hash": fiber_hash,
        "rx_power_dbm": -26.0,
        "signal_loss_db": 3.8,
        "link_state": "UP",
        "site_id": "SITE-BOG-01",
        "asset_type": "ONT",
        "source": "LAB",
    },
    source_integrity="SOURCE_HASHED",
)


# ============================================================
# 6. Verificaciones
# ============================================================

assert external_event["source"] == "fiber_pon_intelligence"
assert external_event["event_type"] == "OPTICAL_DEGRADATION"
assert external_event["state"] == "DEGRADED"
assert external_event["source_integrity"] == "SOURCE_HASHED"
assert len(external_event["evidence_hash"]) == 64

events = asset_engine.events("ONT-017")

assert len(events) >= 1

fiber_events = [
    event
    for event in events
    if event["event_type"] == "OPTICAL_DEGRADATION"
]

assert len(fiber_events) >= 1

print("=== SENTINEL FIBER → ASSET EVIDENCE ===")
print("FIBER VERSION:", fiber_engine.VERSION)
print("ASSET:", "ONT-017")
print("FIBER STATE:", observation["state"])
print("FIBER EVENT HASH:", fiber_hash)
print("EXTERNAL SOURCE:", external_event["source"])
print("EXTERNAL EVENT:", external_event["event_type"])
print("EXTERNAL STATE:", external_event["state"])
print("EXTERNAL INTEGRITY:", external_event["source_integrity"])
print("ASSET EVENTS:", len(events))
print("FIBER_ASSET_EVIDENCE_TEST=PASS")


fiber_engine.close()
asset_engine.close()
os.unlink(db)
