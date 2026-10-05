"""
Sentinel FieldProof ESC/POS output.

Generates raw ESC/POS bytes for thermal printers.
The module does not require a specific printer brand.
"""

from .thermal import render_58mm


ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"
ALIGN_CENTER = ESC + b"a\x01"
ALIGN_LEFT = ESC + b"a\x00"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
CUT = GS + b"V\x00"


def encode_text(text):
    return text.encode("utf-8", errors="replace")


def build_58mm_payload(certificate, include_cut=True):
    """
    Build a raw ESC/POS print payload.

    The resulting bytes can later be sent through:
    - Bluetooth
    - USB
    - TCP/network printer
    """

    ticket = render_58mm(certificate)

    payload = bytearray()

    payload += INIT
    payload += ALIGN_CENTER
    payload += BOLD_ON
    payload += encode_text("SENTINEL CIVIL\n")
    payload += encode_text("FIELDPROOF\n")
    payload += BOLD_OFF

    payload += ALIGN_LEFT
    payload += encode_text("\n")
    payload += encode_text(ticket)
    payload += encode_text("\n\n\n")

    if include_cut:
        payload += CUT

    return bytes(payload)


def save_escpos(certificate, output_path):
    """
    Save raw ESC/POS bytes.

    This lets clients test or send the generated file
    through their own printer software.
    """

    with open(output_path, "wb") as f:
        f.write(build_58mm_payload(certificate))

    return output_path
