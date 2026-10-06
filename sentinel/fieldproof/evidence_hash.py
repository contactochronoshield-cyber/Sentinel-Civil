"""
Sentinel FieldVerify - Evidence Hash

Creates a SHA-256 fingerprint for a physical-evidence file,
such as a photograph or scanned document.

The hash identifies the exact digital file that was analyzed.
It does NOT prove that the photographed event physically occurred.
"""

import hashlib
import os
import time


SCHEMA = "SFE-1.0"


def sha256_file(path):
    path = os.path.expanduser(path)

    digest = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest()


def create_evidence_record(
    evidence_path,
    certificate_id=None,
    asset_id=None,
    evidence_type="PHYSICAL_PHOTO",
):
    path = os.path.expanduser(evidence_path)

    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    stat = os.stat(path)
    evidence_hash = sha256_file(path)

    return {
        "schema": SCHEMA,
        "evidence_id": (
            "SFE-"
            + time.strftime("%Y%m%d%H%M%S")
            + "-"
            + evidence_hash[:12].upper()
        ),
        "evidence_type": evidence_type,
        "filename": os.path.basename(path),
        "size_bytes": stat.st_size,
        "sha256": evidence_hash,
        "certificate_id": certificate_id,
        "asset_id": asset_id,
        "created_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        ),
    }


def save_evidence_record(record, output_path):
    import json

    output_path = os.path.expanduser(output_path)
    directory = os.path.dirname(output_path)

    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            record,
            f,
            ensure_ascii=False,
            indent=2,
        )

    return output_path
