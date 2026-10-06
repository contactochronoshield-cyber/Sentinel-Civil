"""
Sentinel FieldVerify human-readable report.
"""


def render_report(result):
    status = result.get("status", "UNVERIFIABLE")

    lines = [
        "================================",
        "       SENTINEL CIVIL",
        "        FIELDVERIFY",
        "================================",
        "",
        f"RESULT: {status}",
        "",
        f"CERTIFICATE: {result.get('certificate_id', '-')}",
        f"ASSET: {result.get('asset_id', '-')}",
        "",
        f"CERTIFICATE INTEGRITY: "
        f"{result.get('certificate_integrity', False)}",
        "",
        f"QR DETECTED: "
        f"{result.get('qr', {}).get('detected', False)}",
        f"OCR AVAILABLE: "
        f"{result.get('ocr', {}).get('available', False)}",
        "",
        "EVIDENCE SHA-256:",
        result.get("evidence", {}).get(
            "sha256",
            "-"
        ),
        "",
        "MISMATCHES:",
    ]

    mismatches = result.get(
        "mismatches",
        []
    )

    if mismatches:
        lines.extend(
            f"- {item}"
            for item in mismatches
        )
    else:
        lines.append("- NONE")

    lines.extend(
        [
            "",
            "IMPORTANT:",
            "Documentary verification does not",
            "prove physical performance of the",
            "intervention.",
            "",
            "================================",
        ]
    )

    return "\n".join(lines)
