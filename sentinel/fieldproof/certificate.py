import hashlib
import json
import os
import time
import uuid


class FieldProofCertificate:
    """
    Sentinel FieldProof certificate.

    The certificate core is immutable after creation.
    Sync metadata is intentionally excluded from the
    integrity hash so LOCAL/SYNCED transitions do not
    invalidate the physical proof.
    """

    SCHEMA = "SCF-1.0"
    VERSION = "1.0.0"

    def __init__(
        self,
        node_id,
        asset_id,
        intervention_type,
        action,
        result,
        technician=None,
        initial_state=None,
        final_state=None,
        evidence_refs=None,
        metadata=None,
        certificate_id=None,
        created_at=None,
    ):
        self.certificate_id = certificate_id or self._new_id()
        self.created_at = created_at or self._timestamp()

        self.node_id = node_id
        self.asset_id = asset_id
        self.intervention_type = intervention_type
        self.action = action
        self.result = result
        self.technician = technician
        self.initial_state = initial_state
        self.final_state = final_state
        self.evidence_refs = evidence_refs or []
        self.metadata = metadata or {}

        self.integrity = {
            "algorithm": "SHA-256",
            "hash": None,
        }

        self.sync = {
            "state": "LOCAL",
            "synced_at": None,
        }

        self._calculate_hash()

    @staticmethod
    def _timestamp():
        return time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        )

    @staticmethod
    def _new_id():
        return (
            "SC-FP-"
            + time.strftime("%Y%m%d%H%M%S")
            + "-"
            + uuid.uuid4().hex[:8].upper()
        )

    @staticmethod
    def _canonical_json(payload):
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def _certificate_core(self):
        """
        Immutable certificate content.

        IMPORTANT:
        - integrity is excluded
        - sync state is excluded
        """

        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "certificate_id": self.certificate_id,
            "created_at": self.created_at,
            "node_id": self.node_id,
            "asset_id": self.asset_id,
            "intervention": {
                "type": self.intervention_type,
                "action": self.action,
                "result": self.result,
            },
            "states": {
                "initial": self.initial_state,
                "final": self.final_state,
            },
            "technician": self.technician,
            "evidence_refs": self.evidence_refs,
            "metadata": self.metadata,
        }

    def _payload_without_hash(self):
        """
        Compatibility helper.

        The hash is calculated only from the immutable
        certificate core.
        """

        return self._certificate_core()

    def _calculate_hash(self):
        canonical = self._canonical_json(
            self._certificate_core()
        )

        digest = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

        self.integrity["hash"] = digest
        return digest

    def to_dict(self):
        payload = self._certificate_core()

        payload["sync"] = dict(self.sync)
        payload["integrity"] = dict(self.integrity)

        return payload

    def to_json(self, indent=2):
        return json.dumps(
            self.to_dict(),
            indent=indent,
            ensure_ascii=False,
        )

    def save(self, directory):
        os.makedirs(
            os.path.expanduser(directory),
            exist_ok=True,
        )

        path = os.path.join(
            os.path.expanduser(directory),
            f"{self.certificate_id}.json",
        )

        with open(
            path,
            "w",
            encoding="utf-8",
        ) as f:
            f.write(self.to_json())

        return path

    def verify(self):
        expected = self.integrity.get("hash")

        if not expected:
            return False

        canonical = self._canonical_json(
            self._certificate_core()
        )

        actual = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

        return actual == expected

    def mark_synced(self, synced_at=None):
        """
        Update synchronization metadata without changing
        the immutable certificate hash.
        """

        self.sync = {
            "state": "SYNCED",
            "synced_at": synced_at or self._timestamp(),
        }

        return self.integrity["hash"]

    def printable_text(self):
        status = self.sync["state"]

        return "\n".join(
            [
                "================================",
                "        SENTINEL CIVIL",
                "          FIELDPROOF",
                "================================",
                f"ID: {self.certificate_id}",
                f"SCHEMA: {self.SCHEMA}",
                "",
                f"DATE: {self.created_at}",
                f"NODE: {self.node_id}",
                f"ASSET: {self.asset_id}",
                "",
                f"TYPE: {self.intervention_type}",
                f"ACTION: {self.action}",
                f"RESULT: {self.result}",
                "",
                f"INITIAL: {self.initial_state or '-'}",
                f"FINAL: {self.final_state or '-'}",
                f"TECH: {self.technician or '-'}",
                "",
                f"STATUS: {status}",
                "",
                "SHA-256:",
                self.integrity["hash"],
                "",
                "Digital evidence references:",
                str(len(self.evidence_refs)),
                "",
                "================================",
                " Sentinel FieldProof / SCF",
                "================================",
            ]
        )
