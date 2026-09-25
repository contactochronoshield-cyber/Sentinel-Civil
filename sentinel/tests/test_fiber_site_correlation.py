from sentinel.site_correlation import SiteCorrelationEngine


def main():
    engine = SiteCorrelationEngine(
        enabled=True,
    )

    incidents = [
        {
            "asset_id": "ONT-001",
            "component_id": "SPLITTER-07",
            "incident_type": "OPTICAL_DEGRADATION",
            "state": "OPEN",
            "confidence": 0.90,
        },
        {
            "asset_id": "ONT-002",
            "component_id": "SPLITTER-07",
            "incident_type": "OPTICAL_DEGRADATION",
            "state": "OPEN",
            "confidence": 0.88,
        },
        {
            "asset_id": "ONT-003",
            "component_id": "SPLITTER-07",
            "incident_type": "OPTICAL_DEGRADATION",
            "state": "OPEN",
            "confidence": 0.91,
        },
    ]

    result = engine.aggregate_fiber(
        site_id="SITE-BOG-01",
        incidents=incidents,
        minimum_assets=2,
    )

    assert result["enabled"] is True
    assert result["incident"] is True
    assert result["state"] == "OPEN"
    assert result["incident_type"] == "SITE_COMMUNICATION_DEGRADATION"
    assert result["affected_assets"] == 3
    assert result["affected_components"] == 1

    assert result["evidence"]["correlation_type"] == (
        "COMMON_PATH_DEGRADATION"
    )

    assert result["evidence"]["affected_assets"] == [
        "ONT-001",
        "ONT-002",
        "ONT-003",
    ]

    assert 0.0 < result["confidence"] <= 0.95

    stored = engine.get_incidents("SITE-BOG-01")

    assert len(stored) == 1
    assert stored[0]["state"] == "OPEN"

    print("=== SENTINEL FIBER → SITE CORRELATION ===")
    print("VERSION:", engine.VERSION)
    print("SITE:", result["site_id"])
    print("INCIDENT:", result["incident_type"])
    print("CORRELATION:", result["evidence"]["correlation_type"])
    print("AFFECTED ASSETS:", result["affected_assets"])
    print("AFFECTED COMPONENTS:", result["affected_components"])
    print("CONFIDENCE:", result["confidence"])
    print("FIBER_SITE_CORRELATION_TEST=PASS")

    engine.close()


if __name__ == "__main__":
    main()
