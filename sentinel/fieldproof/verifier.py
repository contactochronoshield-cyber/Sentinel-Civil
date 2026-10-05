"""
Sentinel FieldProof verifier.

Verifies the immutable cryptographic core of an SCF certificate.
Sync metadata is not part of the certificate hash.
"""

import hashlib
import json
import os


def _canonical_json(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _certificate_core(certificate):
    """
    Extract the immutable SCF certificate core.

    Excludes:
    - integrity
    - sync

    These fields must not affect the physical proof hash.
    """

    return {
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


def verify_certificate(certificate):
    """
    Verify an SCF certificate represented as a dictionary.
    """

    if not isinstance(certificate, dict):
        return {
            "valid": False,
            "reason": "CERTIFICATE_NOT_OBJECT",
        }

    integrity = certificate.get("integrity")

    if not isinstance(integrity, dict):
        return {
            "valid": False,
            "reason": "INTEGRITY_BLOCK_MISSING",
        }

    expected = integrity.get("hash")

    if not expected:
        return {
            "valid": False,
            "reason": "HASH_MISSING",
        }

    algorithm = integrity.get("algorithm")

    if algorithm != "SHA-256":
        return {
            "valid": False,
            "reason": "UNSUPPORTED_HASH_ALGORITHM",
        }

    canonical = _canonical_json(
        _certificate_core(certificate)
    )

    actual = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    valid = actual == expected

    return {
        "valid": valid,
        "certificate_id": certificate.get("certificate_id"),
        "expected_hash": expected,
        "actual_hash": actual,
        "sync_state": certificate.get(
            "sync",
            {},
        ).get("state"),
        "reason": (
            "HASH_MATCH"
            if valid
            else "HASH_MISMATCH"
        ),
    }


def verify_file(path):
    """
    Load and verify an SCF JSON certificate.
    """

    path = os.path.expanduser(path)

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:
        certificate = json.load(f)

    return verify_certificate(certificate)
