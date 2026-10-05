"""
Sentinel FieldProof QR support.

QR generation is optional so Sentinel Civil remains
lightweight and usable offline on Termux.
"""

import os


def payload_for_certificate(certificate):
    """
    Return a compact QR payload identifying the certificate
    and its integrity hash.
    """

    return (
        f"SCF:{certificate.certificate_id}\n"
        f"SHA256:{certificate.integrity['hash']}"
    )


def generate_qr(certificate, output_path):
    """
    Generate a PNG QR code if the optional 'qrcode'
    package is installed.

    Returns:
        output_path on success
        None when the optional dependency is unavailable
    """

    try:
        import qrcode
    except ImportError:
        return None

    output_path = os.path.expanduser(output_path)

    directory = os.path.dirname(output_path)

    if directory:
        os.makedirs(directory, exist_ok=True)

    payload = payload_for_certificate(certificate)

    image = qrcode.make(payload)
    image.save(output_path)

    return output_path
