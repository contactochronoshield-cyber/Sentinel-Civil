from sentinel.fiber_pON_intelligence import FiberPONIntelligence


def main():
    engine = FiberPONIntelligence()

    engine.register_asset(
        "OLT-BOG-01",
        "OLT",
        site_id="SITE-BOG-01",
        vendor="GENERIC",
        model="LAB-OLT",
    )

    engine.register_asset(
        "FDH-BOG-07",
        "FDH",
        site_id="SITE-BOG-01",
        parent_id="OLT-BOG-01",
    )

    engine.register_asset(
        "SPLITTER-07",
        "SPLITTER",
        site_id="SITE-BOG-01",
        parent_id="FDH-BOG-07",
    )

    engine.register_asset(
        "ONT-017",
        "ONT",
        site_id="SITE-BOG-01",
        parent_id="SPLITTER-07",
    )

    normal = engine.observe(
        "ONT-017",
        rx_power_dbm=-20.5,
        tx_power_dbm=2.0,
        temperature_c=38.0,
        voltage_v=3.3,
        laser_bias_ma=18.0,
        signal_loss_db=1.2,
        link_state="UP",
        source="LAB",
    )

    degraded = engine.observe(
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

    evidence_hash = engine.record_event(
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

    asset = engine.get_asset("ONT-017")
    observations = engine.observations("ONT-017")
    events = engine.events("ONT-017")

    assert normal["state"] == "NORMAL"
    assert degraded["state"] == "DEGRADED"
    assert asset["state"] == "DEGRADED"
    assert len(observations) == 2
    assert len(events) == 1
    assert len(evidence_hash) == 64

    print("=== SENTINEL FIBER & PON INTELLIGENCE ===")
    print("VERSION:", engine.VERSION)
    print("OLT:", engine.get_asset("OLT-BOG-01")["asset_type"])
    print("FDH:", engine.get_asset("FDH-BOG-07")["asset_type"])
    print("SPLITTER:", engine.get_asset("SPLITTER-07")["asset_type"])
    print("ONT STATE:", asset["state"])
    print("OBSERVATIONS:", len(observations))
    print("EVENTS:", len(events))
    print("EVIDENCE HASH:", evidence_hash)
    print("FIBER_PON_INTELLIGENCE_TEST=PASS")

    engine.close()


if __name__ == "__main__":
    main()
