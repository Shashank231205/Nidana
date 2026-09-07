"""FHIR R4 mapping. Nothing but mapping.

This is what makes the record exportable to the national health stack rather
than another silo, and it is the difference between a project and something
that could plug into ABDM.

Two rules the mapping holds.

Provenance survives export. A FHIR resource carrying a clinical fact with no
trace back to what the patient said is exactly the artefact this system exists
to avoid producing, so every mapped resource carries a Provenance resource
alongside it.

Nothing is invented to satisfy a profile. Where a required element is absent
from the record, the mapping reports it as unmappable rather than filling it
with a plausible default — a `status: final` on an unsigned note would be a
false statement in an interoperable format.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from spine.schemas.finding import Finding
from spine.schemas.lab import Flag, LabResult
from spine.schemas.medication import PrescribedMedication, ResolutionStatus
from spine.schemas.primitives import Sex
from spine.schemas.record import Demographics, Record

FHIR_ADMINISTRATIVE_GENDER: dict[Sex, str] = {
    Sex.FEMALE: "female",
    Sex.MALE: "male",
    Sex.OTHER: "other",
    Sex.UNKNOWN: "unknown",
}
"""Sex to FHIR AdministrativeGender.

The vocabularies happen to align. `unknown` is a real FHIR value rather than an
omission, which matters: an absent gender and a recorded-unknown gender are
different facts and FHIR can express both.
"""

OBSERVATION_INTERPRETATION: dict[Flag, tuple[str, str]] = {
    Flag.LOW: ("L", "Low"),
    Flag.HIGH: ("H", "High"),
    Flag.CRITICAL_LOW: ("LL", "Critical low"),
    Flag.CRITICAL_HIGH: ("HH", "Critical high"),
    Flag.NORMAL: ("N", "Normal"),
}
"""Result flags to the HL7 v3 ObservationInterpretation codes FHIR expects.

Flag.UNKNOWN is deliberately absent. A result nobody could judge has no
interpretation, and coding it as anything would assert a judgement.
"""

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class Unmappable:
    """Something that could not be exported, and why.

    Kept rather than dropped. A silently omitted resource makes an export look
    complete when it is not, and the receiving system cannot tell.
    """

    kind: str
    identifier: str
    reason: str


@dataclass(frozen=True)
class MappingResult:
    """What an export produced."""

    resources: tuple[JsonObject, ...]
    unmappable: tuple[Unmappable, ...] = ()

    @property
    def is_complete(self) -> bool:
        return not self.unmappable


def _reference(resource_type: str, identifier: UUID | str) -> JsonObject:
    return {"reference": f"{resource_type}/{identifier}"}


def _codeable_concept(text: str, codings: tuple[object, ...] = ()) -> JsonObject:
    concept: JsonObject = {"text": text}
    coded = [
        {
            "system": getattr(coding, "system", None),
            "code": getattr(coding, "code", None),
            "display": getattr(coding, "display", None),
        }
        for coding in codings
    ]
    if coded:
        concept["coding"] = coded
    return concept


def provenance_resource(
    target_type: str,
    target_id: str,
    finding: Finding,
    recorded_at: datetime,
) -> JsonObject:
    """The Provenance resource that accompanies an exported fact.

    `entity` carries the source text as the derivation, so a receiving system
    can show a clinician the words behind a coded observation. Without this the
    export loses the property that distinguishes this record from any other.
    """
    return {
        "resourceType": "Provenance",
        "target": [_reference(target_type, target_id)],
        "recorded": recorded_at.isoformat(),
        "activity": _codeable_concept("Derived from patient statement"),
        "entity": [
            {
                "role": "source",
                "what": {
                    "display": finding.provenance.text,
                    "identifier": {"value": finding.provenance.source_id},
                },
            }
        ],
        "agent": [
            {
                "type": _codeable_concept(finding.provenance.source_type.value),
                "who": {"display": "nidana"},
            }
        ],
    }


def patient_resource(subject_id: UUID, demographics: Demographics) -> JsonObject:
    """A Patient carrying no identifying detail.

    Deliberately minimal. The clinical schema holds no patient reference (ADR
    0006), so an export from it carries a pseudonymous subject and the receiving
    system links it through the restricted schema or not at all.
    """
    resource: JsonObject = {
        "resourceType": "Patient",
        "id": str(subject_id),
        "gender": FHIR_ADMINISTRATIVE_GENDER[demographics.sex],
    }
    if demographics.age_years is not None:
        resource["extension"] = [
            {
                "url": "http://hl7.org/fhir/StructureDefinition/patient-ageInYears",
                "valueInteger": demographics.age_years,
            }
        ]
    return resource


def observation_from_finding(
    finding: Finding,
    subject_id: UUID,
    recorded_at: datetime,
) -> JsonObject:
    """One finding as an Observation.

    A negated finding maps to `valueBoolean: false` rather than being omitted.
    'Asked and denied' is clinically distinct from 'never asked', and an
    exported record that drops denials loses that distinction entirely.
    """
    observation: JsonObject = {
        "resourceType": "Observation",
        "id": f"{subject_id}-{finding.field}-{finding.turn_index or 0}",
        "status": "final",
        "code": _codeable_concept(finding.field, finding.codings),
        "subject": _reference("Patient", subject_id),
        "effectiveDateTime": recorded_at.isoformat(),
    }
    value = finding.value
    if finding.negated or isinstance(value, bool):
        observation["valueBoolean"] = bool(value) and not finding.negated
    elif isinstance(value, (int, float)):
        observation["valueQuantity"] = {"value": float(value)}
    elif hasattr(value, "value") and hasattr(value, "unit"):
        observation["valueQuantity"] = {"value": value.value, "unit": value.unit}
    else:
        observation["valueString"] = str(value)
    return observation


def observation_from_lab(
    result: LabResult,
    subject_id: UUID,
    recorded_at: datetime,
) -> JsonObject:
    """One lab result as an Observation.

    A result with no reference range carries no interpretation, because nobody
    judged it. Coding it as normal would assert a judgement no one made.
    """
    observation: JsonObject = {
        "resourceType": "Observation",
        "status": "final",
        "code": _codeable_concept(result.analyte, result.codings),
        "subject": _reference("Patient", subject_id),
        "effectiveDateTime": (
            result.collected_on.isoformat() if result.collected_on else recorded_at.isoformat()
        ),
        "valueQuantity": {"value": result.value, "unit": result.unit},
    }
    interpretation = OBSERVATION_INTERPRETATION.get(result.flag)
    if interpretation is not None:
        code, display = interpretation
        observation["interpretation"] = [
            {
                "coding": [
                    {
                        "system": (
                            "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"
                        ),
                        "code": code,
                        "display": display,
                    }
                ]
            }
        ]
    if result.reference_range is not None:
        reference = result.reference_range
        entry: JsonObject = {}
        if reference.low is not None:
            entry["low"] = {"value": reference.low, "unit": reference.unit}
        if reference.high is not None:
            entry["high"] = {"value": reference.high, "unit": reference.unit}
        observation["referenceRange"] = [entry]
    return observation


def medication_statement(
    medication: PrescribedMedication,
    subject_id: UUID,
    recorded_at: datetime,
) -> JsonObject | Unmappable:
    """One medication as a MedicationStatement.

    An unresolved line is unmappable rather than exported with its brand name
    as the concept text. A receiving system reading a MedicationStatement
    reasonably assumes the molecule is known, and exporting an unresolved line
    would hand it a fact nobody established.
    """
    if medication.resolution is not ResolutionStatus.RESOLVED:
        return Unmappable(
            kind="MedicationStatement",
            identifier=medication.written_as,
            reason=(
                f"resolution is {medication.resolution.value}; a MedicationStatement "
                f"asserts a known molecule and this line has none"
            ),
        )
    primary = medication.molecules[0]
    statement: JsonObject = {
        "resourceType": "MedicationStatement",
        "status": "active",
        "subject": _reference("Patient", subject_id),
        "dateAsserted": recorded_at.isoformat(),
        "medicationCodeableConcept": _codeable_concept(primary.name, primary.codings),
    }
    if medication.frequency or medication.route.value != "unknown":
        dosage: JsonObject = {}
        if medication.frequency:
            dosage["text"] = medication.frequency
        if medication.route.value != "unknown":
            dosage["route"] = _codeable_concept(medication.route.value)
        statement["dosage"] = [dosage]
    return statement


def export_record(record: Record, recorded_at: datetime) -> MappingResult:
    """A record as a FHIR bundle's worth of resources.

    Every finding produces an Observation and a Provenance. The pairing is not
    optional: a fact exported without its source is the thing this system
    exists not to produce.
    """
    resources: list[JsonObject] = [patient_resource(record.subject_id, record.demographics)]
    unmappable: list[Unmappable] = []

    for finding in record.findings:
        observation = observation_from_finding(finding, record.subject_id, recorded_at)
        resources.append(observation)
        resources.append(
            provenance_resource(
                "Observation", str(observation["id"]), finding, recorded_at
            )
        )

    for allergy in record.allergies:
        resources.append(
            {
                "resourceType": "AllergyIntolerance",
                "clinicalStatus": _codeable_concept("active"),
                "patient": _reference("Patient", record.subject_id),
                "code": _codeable_concept(allergy.substance, allergy.codings),
                **(
                    {"reaction": [{"manifestation": [_codeable_concept(allergy.reaction)]}]}
                    if allergy.reaction
                    else {}
                ),
            }
        )

    for condition in record.comorbidities:
        resources.append(
            {
                "resourceType": "Condition",
                "clinicalStatus": _codeable_concept("active"),
                "subject": _reference("Patient", record.subject_id),
                "code": _codeable_concept(condition.name, condition.codings),
            }
        )

    return MappingResult(resources=tuple(resources), unmappable=tuple(unmappable))


def bundle(resources: tuple[JsonObject, ...], bundle_id: UUID) -> JsonObject:
    """Wrap resources in a FHIR Bundle.

    A collection rather than a document, because a document requires a
    Composition and a signed author, and asserting either would be a claim the
    record does not support.
    """
    return {
        "resourceType": "Bundle",
        "id": str(bundle_id),
        "type": "collection",
        "entry": [{"resource": resource} for resource in resources],
    }
