"""FHIR R4 mapping.

The property that matters most: provenance survives export. A resource carrying
a clinical fact with no trace back to what the patient said is the artefact this
system exists not to produce, so an Observation without its Provenance is a
failure of the export rather than a cosmetic gap.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from spine.fhir.mapping import (
    FHIR_ADMINISTRATIVE_GENDER,
    OBSERVATION_INTERPRETATION,
    JsonObject,
    Unmappable,
    bundle,
    export_record,
    medication_statement,
    observation_from_finding,
    observation_from_lab,
    patient_resource,
)
from spine.schemas.finding import Finding
from spine.schemas.lab import Flag, LabResult, ReferenceRange
from spine.schemas.medication import (
    Molecule,
    PrescribedMedication,
    ResolutionStatus,
    Route,
)
from spine.schemas.primitives import Confidence, Quantity, Sex
from spine.schemas.provenance import (
    BoundingBox,
    OcrRegion,
    locate_document,
    locate_utterance,
)
from spine.schemas.record import (
    Allergy,
    Comorbidity,
    Demographics,
    Record,
    SubjectType,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
UTTERANCE = "chest pain since 6 hours, goes to my jaw, no sweating"


def finding(
    field: str,
    value: str | float | int | bool | Quantity,
    quote: str,
    *,
    negated: bool = False,
) -> Finding:
    return Finding(
        field=field,
        value=value,
        confidence=Confidence.HIGH,
        negated=negated,
        provenance=locate_utterance(
            source_id="u1", source_text=UTTERANCE, quote=quote, turn_index=1
        ),
    )


def session(*findings: Finding, sex: Sex = Sex.MALE, age: int | None = 54) -> Record:
    return Record(
        subject_type=SubjectType.SESSION,
        subject_id=uuid4(),
        demographics=Demographics(age_years=age, sex=sex),
    ).with_findings(*findings)


def resources_of(record: Record, kind: str) -> list[JsonObject]:
    """Resources of one type from an export.

    Typed as JsonObject rather than dict[str, object] because a FHIR resource is
    nested JSON and every assertion here indexes into it.
    """
    return [r for r in export_record(record, NOW).resources if r["resourceType"] == kind]


class TestProvenanceSurvivesExport:
    """The property that distinguishes this record from any other."""

    def test_every_observation_has_a_provenance(self) -> None:
        record = session(
            finding("radiation", "jaw", "goes to my jaw"),
            finding("diaphoresis", False, "no sweating", negated=True),
        )
        assert len(resources_of(record, "Observation")) == 2
        assert len(resources_of(record, "Provenance")) == 2

    def test_the_provenance_carries_the_patients_own_words(self) -> None:
        record = session(finding("radiation", "jaw", "goes to my jaw"))
        provenance = resources_of(record, "Provenance")[0]
        entity = provenance["entity"]
        assert isinstance(entity, list)
        assert entity[0]["what"]["display"] == "goes to my jaw"

    def test_the_provenance_targets_its_observation(self) -> None:
        record = session(finding("radiation", "jaw", "goes to my jaw"))
        observation = resources_of(record, "Observation")[0]
        provenance = resources_of(record, "Provenance")[0]
        target = provenance["target"]
        assert isinstance(target, list)
        assert target[0]["reference"] == f"Observation/{observation['id']}"

    def test_the_provenance_names_the_source_type(self) -> None:
        record = session(finding("radiation", "jaw", "goes to my jaw"))
        provenance = resources_of(record, "Provenance")[0]
        agent = provenance["agent"]
        assert isinstance(agent, list)
        assert agent[0]["type"]["text"] == "patient_utterance"


class TestObservationMapping:
    def test_a_quantity_maps_with_its_unit(self) -> None:
        observation = observation_from_finding(
            finding("onset_duration_hours", Quantity(value=6, unit="hours"), "6 hours"),
            uuid4(),
            NOW,
        )
        assert observation["valueQuantity"] == {"value": 6.0, "unit": "hours"}

    def test_a_denial_maps_to_false_rather_than_being_omitted(self) -> None:
        """'Asked and denied' is distinct from 'never asked'."""
        observation = observation_from_finding(
            finding("diaphoresis", False, "no sweating", negated=True), uuid4(), NOW
        )
        assert observation["valueBoolean"] is False

    def test_an_affirmed_boolean_maps_to_true(self) -> None:
        observation = observation_from_finding(
            finding("diaphoresis", True, "no sweating"), uuid4(), NOW
        )
        assert observation["valueBoolean"] is True

    def test_an_enum_maps_to_a_string_value(self) -> None:
        observation = observation_from_finding(
            finding("radiation", "jaw", "goes to my jaw"), uuid4(), NOW
        )
        assert observation["valueString"] == "jaw"

    def test_a_bare_number_maps_to_a_quantity(self) -> None:
        observation = observation_from_finding(
            finding("severity_nrs", 7, "6 hours"), uuid4(), NOW
        )
        assert observation["valueQuantity"] == {"value": 7.0}

    def test_the_field_name_becomes_the_code_text(self) -> None:
        observation = observation_from_finding(
            finding("radiation", "jaw", "goes to my jaw"), uuid4(), NOW
        )
        assert observation["code"]["text"] == "radiation"


class TestLabMapping:
    def test_a_high_result_carries_its_interpretation(self) -> None:
        result = LabResult(
            analyte="Potassium",
            value=6.9,
            unit="mmol/L",
            reference_range=ReferenceRange(low=3.5, high=5.1, unit="mmol/L"),
            provenance=locate_document(
                source_id="l.pdf", source_text="Potassium 6.9", quote="6.9", page=1
            ),
        )
        observation = observation_from_lab(result, uuid4(), NOW)
        assert observation["interpretation"][0]["coding"][0]["code"] == "H"

    def test_a_result_with_no_range_carries_no_interpretation(self) -> None:
        """Nobody judged it, so coding it would assert a judgement."""
        result = LabResult(
            analyte="Ferritin",
            value=12,
            unit="ng/mL",
            provenance=locate_document(
                source_id="l.pdf", source_text="Ferritin 12", quote="12", page=1
            ),
        )
        observation = observation_from_lab(result, uuid4(), NOW)
        assert "interpretation" not in observation

    def test_flag_unknown_has_no_interpretation_code(self) -> None:
        assert Flag.UNKNOWN not in OBSERVATION_INTERPRETATION

    def test_the_reference_range_is_exported(self) -> None:
        result = LabResult(
            analyte="Potassium",
            value=4.0,
            unit="mmol/L",
            reference_range=ReferenceRange(low=3.5, high=5.1, unit="mmol/L"),
            provenance=locate_document(
                source_id="l.pdf", source_text="Potassium 4.0", quote="4.0", page=1
            ),
        )
        exported = observation_from_lab(result, uuid4(), NOW)["referenceRange"][0]
        assert exported["low"]["value"] == 3.5
        assert exported["high"]["value"] == 5.1

    def test_the_collection_date_is_preferred_when_present(self) -> None:
        result = LabResult(
            analyte="Potassium",
            value=4.0,
            unit="mmol/L",
            collected_on=date(2026, 3, 1),
            provenance=locate_document(
                source_id="l.pdf", source_text="Potassium 4.0", quote="4.0", page=1
            ),
        )
        observation = observation_from_lab(result, uuid4(), NOW)
        assert str(observation["effectiveDateTime"]).startswith("2026-03-01")


def region() -> OcrRegion:
    return OcrRegion(
        source_id="rx.jpg",
        box=BoundingBox(x=1, y=1, width=9, height=9),
        text="line",
        ocr_confidence=0.9,
    )


class TestMedicationMapping:
    def test_a_resolved_medication_maps(self) -> None:
        medication = PrescribedMedication(
            written_as="Glycomet 500",
            molecules=(Molecule(name="metformin"),),
            resolution=ResolutionStatus.RESOLVED,
            resolution_confidence=0.95,
            provenance=region(),
            frequency="twice daily",
            route=Route.ORAL,
        )
        statement = medication_statement(medication, uuid4(), NOW)
        assert not isinstance(statement, Unmappable)
        assert statement["medicationCodeableConcept"]["text"] == "metformin"

    def test_the_dosage_carries_the_frequency_as_written(self) -> None:
        medication = PrescribedMedication(
            written_as="Glycomet 500",
            molecules=(Molecule(name="metformin"),),
            resolution=ResolutionStatus.RESOLVED,
            resolution_confidence=0.95,
            provenance=region(),
            frequency="1-0-1",
            route=Route.ORAL,
        )
        statement = medication_statement(medication, uuid4(), NOW)
        assert not isinstance(statement, Unmappable)
        assert statement["dosage"][0]["text"] == "1-0-1"

    @pytest.mark.parametrize(
        "resolution",
        [ResolutionStatus.REFUSED, ResolutionStatus.UNREADABLE],
    )
    def test_an_unresolved_medication_is_unmappable(
        self, resolution: ResolutionStatus
    ) -> None:
        """A MedicationStatement asserts a known molecule."""
        medication = PrescribedMedication(
            written_as="Ecosprin?",
            resolution=resolution,
            resolution_confidence=0.3,
            provenance=region(),
        )
        result = medication_statement(medication, uuid4(), NOW)
        assert isinstance(result, Unmappable)

    def test_the_unmappable_reason_explains_the_refusal(self) -> None:
        medication = PrescribedMedication(
            written_as="Ecosprin?",
            resolution=ResolutionStatus.REFUSED,
            resolution_confidence=0.3,
            provenance=region(),
        )
        result = medication_statement(medication, uuid4(), NOW)
        assert isinstance(result, Unmappable)
        assert "known molecule" in result.reason

    def test_an_ambiguous_medication_is_unmappable(self) -> None:
        medication = PrescribedMedication(
            written_as="Zyloric?",
            resolution=ResolutionStatus.AMBIGUOUS,
            resolution_confidence=0.55,
            provenance=region(),
            candidates=("allopurinol", "zolpidem"),
        )
        assert isinstance(medication_statement(medication, uuid4(), NOW), Unmappable)


class TestPatientResource:
    def test_the_patient_carries_no_identifying_detail(self) -> None:
        """The clinical schema holds no patient reference (ADR 0006)."""
        resource = patient_resource(uuid4(), Demographics(age_years=54, sex=Sex.MALE))
        assert "name" not in resource
        assert "birthDate" not in resource
        assert "telecom" not in resource

    @pytest.mark.parametrize("sex", list(Sex))
    def test_every_sex_maps_to_a_fhir_gender(self, sex: Sex) -> None:
        assert sex in FHIR_ADMINISTRATIVE_GENDER

    def test_unknown_is_a_recorded_value_not_an_omission(self) -> None:
        """An absent gender and a recorded-unknown gender are different facts."""
        resource = patient_resource(uuid4(), Demographics(sex=Sex.UNKNOWN))
        assert resource["gender"] == "unknown"

    def test_an_unknown_age_produces_no_extension(self) -> None:
        resource = patient_resource(uuid4(), Demographics(age_years=None, sex=Sex.MALE))
        assert "extension" not in resource


class TestExport:
    def test_allergies_export_as_allergy_intolerance(self) -> None:
        record = Record(
            subject_type=SubjectType.SESSION,
            subject_id=uuid4(),
            allergies=(Allergy(substance="Penicillin", reaction="rash"),),
        )
        exported = resources_of(record, "AllergyIntolerance")
        assert exported[0]["code"]["text"] == "Penicillin"

    def test_a_reaction_is_carried_through(self) -> None:
        record = Record(
            subject_type=SubjectType.SESSION,
            subject_id=uuid4(),
            allergies=(Allergy(substance="Penicillin", reaction="rash"),),
        )
        exported = resources_of(record, "AllergyIntolerance")[0]
        assert exported["reaction"][0]["manifestation"][0]["text"] == "rash"

    def test_comorbidities_export_as_conditions(self) -> None:
        record = Record(
            subject_type=SubjectType.SESSION,
            subject_id=uuid4(),
            comorbidities=(Comorbidity(name="Type 2 diabetes"),),
        )
        assert resources_of(record, "Condition")[0]["code"]["text"] == "Type 2 diabetes"

    def test_an_empty_record_still_exports_a_patient(self) -> None:
        record = Record(subject_type=SubjectType.SESSION, subject_id=uuid4())
        result = export_record(record, NOW)
        assert len(result.resources) == 1
        assert result.is_complete

    def test_the_bundle_is_a_collection_not_a_document(self) -> None:
        """A document requires a Composition and a signed author."""
        record = session(finding("radiation", "jaw", "goes to my jaw"))
        wrapped = bundle(export_record(record, NOW).resources, uuid4())
        assert wrapped["type"] == "collection"

    def test_every_resource_appears_in_the_bundle(self) -> None:
        record = session(
            finding("radiation", "jaw", "goes to my jaw"),
            finding("diaphoresis", False, "no sweating", negated=True),
        )
        exported = export_record(record, NOW)
        wrapped = bundle(exported.resources, uuid4())
        assert len(wrapped["entry"]) == len(exported.resources)
