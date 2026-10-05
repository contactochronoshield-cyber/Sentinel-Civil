"""
Sentinel FieldProof thermal renderer.

Produces printer-friendly plain text for 58 mm thermal paper.
No printer dependency is required.
"""

import os


WIDTH_58MM = 32


def _line(text="", width=WIDTH_58MM):
    text = str(text)
    return text[:width].center(width)


def _wrap(text, width=WIDTH_58MM):
    text = str(text or "")
    words = text.split()

    if not words:
        return [""]

    lines = []
    current = ""

    for word in words:
        if len(word) > width:
            if current:
                lines.append(current)
                current = ""

            for i in range(0, len(word), width):
                lines.append(word[i:i + width])

            continue

        candidate = word if not current else current + " " + word

        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def render_58mm(certificate):
    """
    Render a FieldProof certificate as a 58 mm text ticket.

    The QR itself is generated separately by qr.py.
    """

    width = WIDTH_58MM
    hash_value = certificate.integrity["hash"]

    lines = [
        "=" * width,
        _line("SENTINEL CIVIL"),
        _line("FIELDPROOF"),
        "=" * width,
        "",
        "CERTIFICATE",
        *_wrap(certificate.certificate_id),
        "",
        f"DATE: {certificate.created_at}",
        f"NODE: {certificate.node_id}",
        f"ASSET: {certificate.asset_id}",
        "",
        "INTERVENTION",
        *_wrap(certificate.intervention_type),
        "",
        "ACTION",
        *_wrap(certificate.action),
        "",
        "RESULT",
        *_wrap(certificate.result),
        "",
        f"TECH: {certificate.technician or '-'}",
        f"STATUS: {certificate.sync['state']}",
        "",
        "SHA-256",
        *_wrap(hash_value),
        "",
        f"EVIDENCE REFS: {len(certificate.evidence_refs)}",
        "",
        "-" * width,
        _line("SCF-1.0"),
        _line("SENTINEL FIELDPROOF"),
        "=" * width,
    ]

    return "\n".join(lines)


def save_58mm(certificate, output_path):
    """
    Save a 58 mm thermal ticket as UTF-8 text.
    """

    output_path = os.path.expanduser(output_path)

    directory = os.path.dirname(output_path)

    if directory:
        os.makedirs(directory, exist_ok=True)

    ticket = render_58mm(certificate)

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as f:
        f.write(ticket)

    return output_path
