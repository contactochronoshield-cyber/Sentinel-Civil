"""
Sentinel FieldVerify Photo

Analyzes a photograph or scanned physical document.

Capabilities:
- SHA-256 evidence fingerprint
- Optional QR extraction
- Optional OCR
- SCF certificate verification
- Field/document consistency checks

A successful result means the available digital evidence is
consistent with Sentinel records. It does not prove that the
physical intervention itself occurred.
"""

import re
import os

from .evidence_hash import create_evidence_record
from .fieldverify import (
    load_certificate,
    verify_certificate_integrity,
    compare_document,
    VERIFIED,
    MISMATCH,
    TAMPER_INDICATED,
    UNVERIFIABLE,
)


def extract_scf_from_text(text):
    """
    Extract Sentinel FieldProof certificate ID and SHA-256
    from text such as:

    SCF:SC-FP-...
    SHA256:...
    """

    if not text:
        return {}

    result = {}

    certificate_match = re.search(
        r"SCF:([A-Za-z0-9_-]+)",
        text,
        re.IGNORECASE,
    )

    hash_match = re.search(
        r"SHA256:([a-fA-F0-9]{64})",
        text,
        re.IGNORECASE,
    )

    if certificate_match:
        result["certificate_id"] = certificate_match.group(1)

    if hash_match:
        result["sha256"] = hash_match.group(1).lower()

    return result


def analyze_photo(
    photo_path,
    certificate_path,
    ocr_text=None,
    certificate_id=None,
    asset_id=None,
    action=None,
    technician=None,
):
    """
    Analyze a photograph using optional OCR text.

    ocr_text may come from any OCR engine. Keeping OCR external
    allows Sentinel to remain lightweight and offline-first.
    """

    photo_path = os.path.expanduser(photo_path)
    certificate_path = os.path.expanduser(certificate_path)

    if not os.path.isfile(photo_path):
        return {
            "status": UNVERIFIABLE,
            "reason": "PHOTO_NOT_READABLE",
        }

    try:
        certificate = load_certificate(certificate_path)
    except (OSError, ValueError):
        return {
            "status": UNVERIFIABLE,
            "reason": "CERTIFICATE_NOT_READABLE",
        }

    evidence = create_evidence_record(
        photo_path,
        certificate_id=certificate.get("certificate_id"),
        asset_id=certificate.get("asset_id"),
    )

    if not verify_certificate_integrity(certificate):
        return {
            "status": TAMPER_INDICATED,
            "reason": "CERTIFICATE_HASH_MISMATCH",
            "evidence": evidence,
        }

    extracted = extract_scf_from_text(ocr_text or "")

    detected_certificate_id = (
        certificate_id
        or extracted.get("certificate_id")
    )

    result = compare_document(
        certificate=certificate,
        certificate_id=detected_certificate_id,
        asset_id=asset_id,
        action=action,
        technician=technician,
        document_hash=evidence["sha256"],
    )

    result["evidence"] = evidence
    result["qr_or_ocr"] = extracted

    if (
        extracted.get("sha256")
        and extracted["sha256"]
        != certificate.get("integrity", {}).get("hash", "").lower()
    ):
        result["status"] = MISMATCH
        result.setdefault("mismatches", []).append(
            "certificate_sha256"
        )

    return result
