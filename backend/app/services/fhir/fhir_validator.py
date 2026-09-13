import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

ISO_DATE_REGEX = re.compile(
    r"^\d{4}(-\d{2}(-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?)?)?$"
)

SUPPORTED_RESOURCE_TYPES = {
    "Composition",
    "Patient",
    "Encounter",
    "Condition",
    "MedicationStatement",
    "AllergyIntolerance",
    "Observation",
    "Procedure",
    "DocumentReference",
    "DiagnosticReport",
}


class FHIRValidationResult(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class FHIRValidator:
    """
    Deterministic internal FHIR R4 consistency validator.
    Validates structural rules, internal reference integrity,
    required bundle semantics, and clinical safety constraints.
    """

    def validate_bundle(self, bundle: Dict[str, Any]) -> FHIRValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        if not isinstance(bundle, dict):
            return FHIRValidationResult(valid=False, errors=["Bundle must be a JSON object"])

        # 1. Root Bundle validation
        if bundle.get("resourceType") != "Bundle":
            errors.append(f"Invalid root resourceType: expected 'Bundle', got '{bundle.get('resourceType')}'")

        bundle_type = bundle.get("type")
        if bundle_type not in ("document", "collection"):
            errors.append(f"Invalid bundle type: expected 'document' or 'collection', got '{bundle_type}'")

        entries = bundle.get("entry")
        if not isinstance(entries, list) or len(entries) == 0:
            errors.append("Bundle must contain a non-empty 'entry' list")
            return FHIRValidationResult(valid=False, errors=errors, warnings=warnings)

        # 2. Check document constraints
        if bundle_type == "document":
            first_entry = entries[0]
            first_res = first_entry.get("resource", {}) if isinstance(first_entry, dict) else {}
            if first_res.get("resourceType") != "Composition":
                errors.append(
                    f"First entry in a FHIR document bundle must be a 'Composition', got '{first_res.get('resourceType')}'"
                )

        # 3. Index resources by ID and reference tokens
        resource_ids_by_type: Dict[str, Set[str]] = {}
        available_references: Set[str] = set()
        patient_found = False
        encounter_found = False

        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"Entry at index {idx} must be an object")
                continue

            res = entry.get("resource")
            if not isinstance(res, dict):
                errors.append(f"Entry at index {idx} missing 'resource' object")
                continue

            r_type = res.get("resourceType")
            if not r_type:
                errors.append(f"Resource at entry {idx} missing 'resourceType'")
                continue

            if r_type not in SUPPORTED_RESOURCE_TYPES:
                errors.append(f"Unsupported FHIR resourceType '{r_type}' at entry {idx}")

            r_id = res.get("id")
            if not r_id:
                errors.append(f"Resource '{r_type}' at entry {idx} missing 'id'")
            else:
                r_id_str = str(r_id)
                if r_type not in resource_ids_by_type:
                    resource_ids_by_type[r_type] = set()

                if r_id_str in resource_ids_by_type[r_type]:
                    errors.append(f"Duplicate resource ID '{r_id_str}' for resourceType '{r_type}'")
                resource_ids_by_type[r_type].add(r_id_str)

                # Track available references
                available_references.add(f"{r_type}/{r_id_str}")
                available_references.add(r_id_str)

            full_url = entry.get("fullUrl")
            if full_url:
                available_references.add(full_url)

            if r_type == "Patient":
                patient_found = True
            elif r_type == "Encounter":
                encounter_found = True

        if not patient_found:
            errors.append("Document bundle must contain a 'Patient' resource")
        if not encounter_found:
            errors.append("Document bundle must contain an 'Encounter' resource")

        # 4. Deep reference and field validation
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            res = entry.get("resource")
            if not isinstance(res, dict):
                continue

            self._validate_resource(res, available_references, errors, warnings)

        return FHIRValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _validate_resource(
        self,
        res: Dict[str, Any],
        available_references: Set[str],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        r_type = res.get("resourceType")

        # Check references recursively
        self._check_references_recursive(res, available_references, errors, r_type)

        # Check specific resource safety invariants
        if r_type == "Patient":
            if not res.get("name") and not res.get("identifier"):
                errors.append("Patient must have at least one name or identifier")
            gender = res.get("gender")
            if gender and gender not in ("male", "female", "other", "unknown"):
                errors.append(f"Invalid Patient.gender '{gender}'")
            bdate = res.get("birthDate")
            if bdate and not ISO_DATE_REGEX.match(str(bdate)):
                errors.append(f"Invalid Patient.birthDate format '{bdate}'")

        elif r_type == "Encounter":
            status = res.get("status")
            if not status:
                errors.append("Encounter missing required 'status'")
            subject = res.get("subject", {})
            if not subject.get("reference"):
                errors.append("Encounter missing required subject reference to Patient")

        elif r_type == "Composition":
            if not res.get("status"):
                errors.append("Composition missing required 'status'")
            if not res.get("type"):
                errors.append("Composition missing required 'type'")
            if not res.get("subject", {}).get("reference"):
                errors.append("Composition missing required subject reference to Patient")
            if not res.get("author"):
                errors.append("Composition missing required 'author'")

        elif r_type == "Condition":
            if not res.get("code") or not (res.get("code", {}).get("text") or res.get("code", {}).get("coding")):
                errors.append("Condition missing clinical code or text")
            if not res.get("subject", {}).get("reference"):
                errors.append("Condition missing required subject reference")

        elif r_type == "MedicationStatement":
            if not res.get("status"):
                errors.append("MedicationStatement missing required 'status'")
            has_med = bool(res.get("medicationCodeableConcept") or res.get("medicationReference"))
            if not has_med:
                errors.append("MedicationStatement missing medicationCodeableConcept or medicationReference")

        elif r_type == "Observation":
            if not res.get("status"):
                errors.append("Observation missing required 'status'")
            if not res.get("code"):
                errors.append("Observation missing required 'code'")

        elif r_type == "AllergyIntolerance":
            if not res.get("patient", {}).get("reference"):
                errors.append("AllergyIntolerance missing patient reference")

    def _check_references_recursive(
        self,
        node: Any,
        available_references: Set[str],
        errors: List[str],
        source_res_type: Optional[str],
    ) -> None:
        if isinstance(node, dict):
            if "reference" in node and isinstance(node["reference"], str):
                ref = node["reference"]
                # Exclude external absolute URLs if standard
                if not ref.startswith("http://") and not ref.startswith("https://"):
                    if ref not in available_references:
                        errors.append(
                            f"Dangling reference '{ref}' found in {source_res_type}: target not found in bundle"
                        )
            for v in node.values():
                self._check_references_recursive(v, available_references, errors, source_res_type)
        elif isinstance(node, list):
            for item in node:
                self._check_references_recursive(item, available_references, errors, source_res_type)


fhir_validator = FHIRValidator()
