"""
Sentinel FieldProof Photo

Offline-first physical evidence image handling.

This module intentionally has no heavy OCR/QR dependency.
It validates and fingerprints the photograph so optional
QR/OCR engines can be attached later.
"""

import hashlib
import os

from PIL import Image


SCHEMA = "SFP-1.0"


def sha256_file(path):
    path = os.path.expanduser(path)

    digest = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest()


def inspect_photo(path):
    path = os.path.expanduser(path)

    if not os.path.isfile(path):
        return {
            "valid": False,
            "reason": "PHOTO_NOT_FOUND",
        }

    try:
        with Image.open(path) as image:
            image.verify()

        with Image.open(path) as image:
            width, height = image.size
            image_format = image.format
            mode = image.mode

    except Exception:
        return {
            "valid": False,
            "reason": "INVALID_IMAGE",
        }

    return {
        "valid": True,
        "schema": SCHEMA,
        "filename": os.path.basename(path),
        "size_bytes": os.path.getsize(path),
        "sha256": sha256_file(path),
        "format": image_format,
        "mode": mode,
        "width": width,
        "height": height,
    }


def prepare_for_analysis(path, max_width=1600):
    """
    Creates a normalized JPEG copy for future OCR/QR analysis.

    The original photograph is never modified.
    """

    path = os.path.expanduser(path)

    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    directory = os.path.dirname(path) or "."
    name = os.path.splitext(os.path.basename(path))[0]

    output_path = os.path.join(
        directory,
        f"{name}.fieldverify.jpg",
    )

    with Image.open(path) as image:
        image = image.convert("RGB")

        if image.width > max_width:
            ratio = max_width / image.width
            new_height = int(image.height * ratio)

            image = image.resize(
                (max_width, new_height)
            )

        image.save(
            output_path,
            format="JPEG",
            quality=90,
        )

    return output_path
