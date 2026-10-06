"""
Sentinel FieldProof Photo Verification
"""

import os
import re

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
    if not text:
        return {}

    result = {}

    certificate_match = re.search(
        r"SCF\s*:\s*([A-Za-z0-9_-]+)",
        text,
        re.IGNORECASE,
    )

    hash_match = re.search(
        r"SHA256\s*:\s*([a-fA-F0-9]{64})",
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
    photo_path = os.path.expanduser(photo_path)
    certificate_path = os.path.expanduser(certificate_path)

    # 1. Verify photo exists
    if not os.path.isfile(photo_path):
        return {
            "status": UNVERIFIABLE,
            "reason": "PHOTO_NOT_READABLE",
        }

    # 2. Load certificate
    try:
        certificate = load_certificate(certificate_path)
    except (OSError, ValueError):
        return {
            "status": UNVERIFIABLE,
            "reason": "CERTIFICATE_NOT_READABLE",
        }

    # 3. Fingerprint evidence
    evidence = create_evidence_record(
        photo_path,
        certificate_id=certificate.get("certificate_id"),
        asset_id=certificate.get("asset_id"),
    )

    # 4. Verify certificate integrity
    if not verify_certificate_integrity(certificate):
        return {
            "status": TAMPER_INDICATED,
            "reason": "CERTIFICATE_HASH_MISMATCH",
            "certificate_id": certificate.get("certificate_id"),
            "asset_id": certificate.get("asset_id"),
            "certificate_integrity": False,
            "evidence": evidence,
        }

    # 5. Extract SCF information from OCR text
    extracted = extract_scf_from_text(ocr_text or "")

    detected_certificate_id = (
        certificate_id
        or extracted.get("certificate_id")
    )

    # 6. No certificate identity available
    if not detected_certificate_id:
        return {
            "status": UNVERIFIABLE,
            "reason": "NO_CERTIFICATE_ID_DETECTED",
            "certificate_id": certificate.get("certificate_id"),
            "asset_id": certificate.get("asset_id"),
            "certificate_integrity": True,
            "evidence": evidence,
            "extracted": extracted,
        }

    # 7. Compare document against certificate
    result = compare_document(
        certificate=certificate,
        certificate_id=detected_certificate_id,
        asset_id=asset_id,
        action=action,
        technician=technician,
        document_hash=evidence["sha256"],
    )

    # 8. Check extracted certificate hash
    expected_hash = (
        certificate
        .get("integrity", {})
        .get("hash", "")
        .lower()
    )

    detected_hash = extracted.get("sha256")

    if detected_hash and detected_hash != expected_hash:
        result["status"] = MISMATCH
        result.setdefault(
            "mismatches",
            []
        ).append(
            "certificate_sha256"
        )

    # 9. Attach verification metadata
    result["evidence"] = evidence
    result["extracted"] = extracted

    return result
