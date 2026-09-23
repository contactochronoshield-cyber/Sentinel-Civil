import os
import tempfile

from sentinel.telecom_radio_intelligence import (
    TelecomRadioIntelligence,
)


def main():
    fd, db = tempfile.mkstemp(
        prefix="telecom-radio-",
        suffix=".db",
    )
    os.close(fd)

    engine = TelecomRadioIntelligence(db)

    try:
        engine.register_radio(
            radio_id="RADIO-017",
            technology="5G_NR",
            site_id="SITE-BOG-01",
            manufacturer="Chrono",
            model="CR-5G-RADIO",
            firmware="1.0.0",
            criticality="HIGH",
            backhaul_dependency=True,
            power_dependency=True,
        )

        engine.register_radio(
            radio_id="RADIO-018",
            technology="LORAWAN",
            site_id="SITE-BOG-01",
            criticality="MEDIUM",
        )

        engine.register_radio(
            radio_id="RADIO-019",
            technology="MICROWAVE",
            site_id="SITE-BOG-01",
            criticality="CRITICAL",
            backhaul_dependency=True,
        )

        five_g = engine.classify("RADIO-017")
        lora = engine.classify("RADIO-018")
        microwave = engine.classify("RADIO-019")

        assert five_g["technology"] == "5G_NR"
        assert five_g["domain"] == "CELLULAR"
        assert five_g["role"] == "ACCESS"
        assert five_g["backhaul_dependency"] is True

        assert lora["technology"] == "LORAWAN"
        assert lora["domain"] == "LPWAN"
        assert lora["role"] == "GATEWAY"

        assert microwave["technology"] == "MICROWAVE"
        assert microwave["domain"] == "BACKHAUL"
        assert microwave["role"] == "TRANSPORT"

        engine.observe(
            "RADIO-017",
            state="NORMAL",
            health_score=98,
            signal_level=-72,
            snr=24,
            availability=99.9,
        )

        engine.observe(
            "RADIO-017",
            state="DEGRADED",
            health_score=61,
            signal_level=-94,
            snr=8,
            latency_ms=180,
            packet_loss=7.5,
            availability=92.0,
            evidence={
                "signal_degradation": True,
                "latency_increase": True,
            },
        )

        engine.observe(
            "RADIO-017",
            state="CRITICAL",
            health_score=25,
            signal_level=-108,
            snr=2,
            latency_ms=800,
            packet_loss=35.0,
            availability=61.0,
        )

        history = engine.history("RADIO-017")
        events = engine.events("RADIO-017")

        assert len(history) == 3
        assert len(events) == 2

        assert events[0]["event_type"] == (
            "RADIO_STATE_CHANGED"
        )
        assert events[1]["new_state"] == "CRITICAL"

        assert all(
            len(event["evidence_hash"]) == 64
            for event in events
        )

        print("=== TELECOM RADIO INTELLIGENCE ===")
        print("VERSION:", engine.VERSION)
        print(
            "5G:",
            five_g["domain"],
            five_g["role"],
        )
        print(
            "LORAWAN:",
            lora["domain"],
            lora["role"],
        )
        print(
            "MICROWAVE:",
            microwave["domain"],
            microwave["role"],
        )
        print("5G HISTORY:", len(history))
        print("5G EVENTS:", len(events))
        print(
            "LAST STATE:",
            history[-1]["state"],
        )
        print(
            "LAST EVENT:",
            events[-1]["event_type"],
        )
        print(
            "EVIDENCE HASH:",
            events[-1]["evidence_hash"],
        )
        print(
            "TELECOM_RADIO_INTELLIGENCE_TEST=PASS"
        )

    finally:
        engine.close()
        os.unlink(db)


if __name__ == "__main__":
    main()
