"""
Sentinel FieldVerify

Verification layer for physical/documentary evidence associated
with Sentinel FieldProof certificates.

Important:
A successful verification proves consistency with a Sentinel
certificate. It does not, by itself, prove that a technician
physically performed the intervention.
"""

import hashlib
import json
import os


VERIFIED = "VERIFIED"
MISMATCH = "MISMATCH"
UNVERIFIABLE = "UNVERIFIABLE"
TAMPER_INDICATED = "TAMPER_INDICATED"


def sha256_file(path):
    path = os.path.expanduser(path)

    digest = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest()


def load_certificate(path):
    path = os.path.expanduser(path)

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_certificate_integrity(certificate):
    if not isinstance(certificate, dict):
        return False

    integrity = certificate.get("integrity", {})

    if integrity.get("algorithm") != "SHA-256":
        return False

    expected = integrity.get("hash")

    if not expected:
        return False

    core = {
        "schema": certificate.get("schema"),
        "version": certificate.get("version"),
        "certificate_id": certificate.get("certificate_id"),
        "created_at": certificate.get("created_at"),
        "node_id": certificate.get("node_id"),
        "asset_id": certificate.get("asset_id"),
        "intervention": certificate.get("intervention"),
        "states": certificate.get("states"),
        "technician": certificate.get("technician"),
        "evidence_refs": certificate.get("evidence_refs"),
        "metadata": certificate.get("metadata"),
    }

    canonical = json.dumps(
        core,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    actual = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    return actual == expected


def compare_document(
    certificate,
    certificate_id=None,
    asset_id=None,
    action=None,
    technician=None,
    document_hash=None,
):
    """
    Compare information extracted from a physical document
    against a Sentinel FieldProof certificate.
    """

    if not isinstance(certificate, dict):
        return {
            "status": UNVERIFIABLE,
            "reason": "CERTIFICATE_NOT_OBJECT",
        }

    if not verify_certificate_integrity(certificate):
        return {
            "status": TAMPER_INDICATED,
            "reason": "CERTIFICATE_HASH_MISMATCH",
        }

    mismatches = []

    if certificate_id is not None:
        expected = certificate.get("certificate_id")
        if certificate_id != expected:
            mismatches.append("certificate_id")

    if asset_id is not None:
        expected = certificate.get("asset_id")
        if asset_id != expected:
            mismatches.append("asset_id")

    if action is not None:
        expected = certificate.get("intervention", {}).get("action")
        if action != expected:
            mismatches.append("action")

    if technician is not None:
        expected = certificate.get("technician")
        if technician != expected:
            mismatches.append("technician")

    result = {
        "certificate_id": certificate.get("certificate_id"),
        "asset_id": certificate.get("asset_id"),
        "status": VERIFIED if not mismatches else MISMATCH,
        "mismatches": mismatches,
        "certificate_integrity": True,
    }

    if document_hash:
        result["document_sha256"] = document_hash

    return result


def verify_physical_evidence(
    certificate_path,
    evidence_path=None,
    certificate_id=None,
    asset_id=None,
    action=None,
    technician=None,
):
    """
    High-level verification entry point.

    evidence_path can be a photograph, scanned document,
    or any other digital representation of the physical evidence.
    """

    try:
        certificate = load_certificate(certificate_path)
    except (OSError, json.JSONDecodeError):
        return {
            "status": UNVERIFIABLE,
            "reason": "CERTIFICATE_NOT_READABLE",
        }

    document_hash = None

    if evidence_path:
        try:
            document_hash = sha256_file(evidence_path)
        except OSError:
            return {
                "status": UNVERIFIABLE,
                "reason": "EVIDENCE_NOT_READABLE",
            }

    return compare_document(
        certificate=certificate,
        certificate_id=certificate_id,
        asset_id=asset_id,
        action=action,
        technician=technician,
        document_hash=document_hash,
    )
