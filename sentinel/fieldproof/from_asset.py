from .certificate import FieldProofCertificate


def create_from_maintenance(
    maintenance,
    node_id,
    asset_id,
    intervention_type="TECHNICAL_MAINTENANCE",
    initial_state=None,
    final_state=None,
    technician=None,
    metadata=None,
):
    """
    Create a FieldProof certificate from a real
    AssetEvidenceEngine maintenance record.

    The original evidence hash is preserved as a
    reference; FieldProof does not replace it.
    """

    evidence_ref = {
        "type": "asset_maintenance",
        "id": maintenance["maintenance_id"],
        "hash": maintenance["evidence_hash"],
    }

    certificate = FieldProofCertificate(
        node_id=node_id,
        asset_id=asset_id,
        intervention_type=intervention_type,
        action=maintenance["action"],
        result=maintenance.get("result"),
        technician=technician,
        initial_state=initial_state,
        final_state=final_state,
        evidence_refs=[evidence_ref],
        metadata=metadata or {},
    )

    return certificate
