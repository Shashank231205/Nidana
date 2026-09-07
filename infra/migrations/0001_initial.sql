-- Nidana initial schema. Forward-only.
--
-- Two schemas, per ADR 0006. `clinical` holds the record and contains no
-- patient reference of any kind; `restricted` holds the linkage. A dump of
-- `clinical` is therefore unlinkable rather than merely pseudonymous, which is
-- what the build spec claims and what this arrangement actually delivers.
--
-- Append-only is enforced by the grants in roles.sql, not by triggers or
-- application convention: the application role has no UPDATE or DELETE on
-- these tables.

BEGIN;

CREATE SCHEMA IF NOT EXISTS clinical;
CREATE SCHEMA IF NOT EXISTS restricted;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- Sessions
-- ---------------------------------------------------------------------------

CREATE TYPE clinical.session_status AS ENUM (
    'active', 'completed', 'terminated_emergency', 'handed_off'
);

CREATE TABLE clinical.sessions (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    status            clinical.session_status NOT NULL DEFAULT 'active',
    complaint_family  TEXT,
    band              TEXT,
    specialty         TEXT,
    locale            TEXT NOT NULL DEFAULT 'en',
    -- A clinical decision must be reproducible from a tag plus the log, so the
    -- versions that produced it are columns rather than buried in a payload.
    rule_set_version  TEXT NOT NULL,
    prompt_versions   JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_version     TEXT,
    transport         TEXT
);

CREATE INDEX sessions_band_idx ON clinical.sessions (band);
CREATE INDEX sessions_created_at_idx ON clinical.sessions (created_at);
CREATE INDEX sessions_status_idx ON clinical.sessions (status);

-- ---------------------------------------------------------------------------
-- Turns
-- ---------------------------------------------------------------------------

CREATE TABLE clinical.session_turns (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id        UUID NOT NULL REFERENCES clinical.sessions (id),
    turn_index        INT NOT NULL,
    patient_utterance TEXT NOT NULL,
    agent_utterance   TEXT,
    language          TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, turn_index)
);

CREATE INDEX session_turns_session_idx ON clinical.session_turns (session_id, turn_index);

-- ---------------------------------------------------------------------------
-- Findings
-- ---------------------------------------------------------------------------

-- provenance is NOT NULL and jsonb rather than a source_span text column, per
-- ADR 0002. It carries the source type, offsets, and quoted text, and the
-- application verifies the span against the stored utterance at extraction.
-- The storage layer enforces that it exists; it cannot enforce that it
-- verifies, which is why verification happens where the utterance is in hand.
CREATE TABLE clinical.findings (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id   UUID NOT NULL REFERENCES clinical.sessions (id),
    turn_index   INT NOT NULL,
    field        TEXT NOT NULL,
    value        JSONB NOT NULL,
    provenance   JSONB NOT NULL,
    confidence   TEXT NOT NULL,
    negated      BOOLEAN NOT NULL DEFAULT FALSE,
    codings      JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT provenance_carries_text
        CHECK (provenance ? 'text' AND length(provenance ->> 'text') > 0),
    CONSTRAINT provenance_names_its_source
        CHECK (provenance ? 'source_type' AND provenance ? 'source_id'),
    -- A denial records what was denied as a boolean, never a measurement.
    CONSTRAINT negation_carries_a_boolean
        CHECK (NOT negated OR jsonb_typeof(value) = 'boolean')
);

CREATE INDEX findings_session_idx ON clinical.findings (session_id);
CREATE INDEX findings_field_idx ON clinical.findings (session_id, field);

-- ---------------------------------------------------------------------------
-- Triage
-- ---------------------------------------------------------------------------

CREATE TABLE clinical.triage_results (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id        UUID NOT NULL REFERENCES clinical.sessions (id),
    band              TEXT NOT NULL,
    specialty         TEXT NOT NULL,
    payload           JSONB NOT NULL,
    critic_adjusted   BOOLEAN NOT NULL DEFAULT FALSE,
    critic_from_band  TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- A recorded escalation must name where it came from, or the audit cannot
    -- reconstruct what the critic did.
    CONSTRAINT critic_adjustment_names_its_origin
        CHECK (NOT critic_adjusted OR critic_from_band IS NOT NULL)
);

CREATE INDEX triage_results_session_idx ON clinical.triage_results (session_id);
CREATE INDEX triage_results_band_idx ON clinical.triage_results (band);

-- ---------------------------------------------------------------------------
-- Red flag firings
-- ---------------------------------------------------------------------------

-- A dedicated table rather than living inside audit payloads. The M3 gate
-- measures red flag sensitivity and the M5 gate requires reconstructing a
-- decision from the log; both need these rows queryable rather than buried in
-- JSON.
CREATE TABLE clinical.red_flag_events (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id     UUID NOT NULL REFERENCES clinical.sessions (id),
    turn_index     INT NOT NULL,
    rule_id        TEXT NOT NULL,
    action         TEXT NOT NULL,
    matched_atoms  TEXT[] NOT NULL DEFAULT '{}',
    capabilities   TEXT[] NOT NULL DEFAULT '{}',
    unverified     BOOLEAN NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX red_flag_events_session_idx ON clinical.red_flag_events (session_id);
CREATE INDEX red_flag_events_rule_idx ON clinical.red_flag_events (rule_id);

-- ---------------------------------------------------------------------------
-- Audit
-- ---------------------------------------------------------------------------

-- Polymorphic subject per ADR 0006: Rx works from a prescription and Labs from
-- a report, and neither is a session. No shared parent table is introduced,
-- because modules 2-5 have not specified their subjects and an abstraction
-- invented now would be guesswork.
CREATE TABLE clinical.audit_events (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_type       TEXT NOT NULL,
    subject_id         UUID NOT NULL,
    sequence           INT NOT NULL,
    event_type         TEXT NOT NULL,
    actor              TEXT NOT NULL,
    payload            JSONB NOT NULL DEFAULT '{}'::jsonb,
    prompt_version     TEXT,
    model_version      TEXT,
    rule_set_version   TEXT,
    transport          TEXT,
    corrects_sequence  INT,
    previous_hash      CHAR(64) NOT NULL,
    entry_hash         CHAR(64) NOT NULL,
    occurred_at        TIMESTAMPTZ NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- One entry per position per subject. A gap or a repeat breaks the chain
    -- and verification will find it, but the constraint stops it being written.
    UNIQUE (subject_type, subject_id, sequence),
    CONSTRAINT correction_points_backwards
        CHECK (corrects_sequence IS NULL OR corrects_sequence < sequence)
);

CREATE INDEX audit_events_subject_idx
    ON clinical.audit_events (subject_type, subject_id, sequence);
CREATE INDEX audit_events_created_at_idx ON clinical.audit_events (created_at);

-- ---------------------------------------------------------------------------
-- Consent
-- ---------------------------------------------------------------------------

-- DPDP Act 2023 requires explicit, logged consent. Withdrawal is a new row,
-- never an update, consistent with the append-only rule everywhere else.
CREATE TABLE clinical.session_consents (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id        UUID NOT NULL REFERENCES clinical.sessions (id),
    purpose           TEXT NOT NULL,
    granted           BOOLEAN NOT NULL,
    consent_text_version TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX session_consents_session_idx ON clinical.session_consents (session_id);

-- ---------------------------------------------------------------------------
-- Facilities
-- ---------------------------------------------------------------------------

CREATE TABLE clinical.facilities (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name              TEXT NOT NULL,
    location          geography(Point, 4326) NOT NULL,
    capabilities      TEXT[] NOT NULL DEFAULT '{}',
    hours             JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_verified_at  TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX facilities_location_idx ON clinical.facilities USING GIST (location);
CREATE INDEX facilities_capabilities_idx ON clinical.facilities USING GIN (capabilities);

-- ---------------------------------------------------------------------------
-- Patients, in the restricted schema
-- ---------------------------------------------------------------------------

CREATE TABLE restricted.patients (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    identifiers  JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The linkage lives here rather than as a column on clinical.sessions. With
-- the FK on sessions, the clinical tables would still carry a patient
-- reference; with it here, they carry none.
CREATE TABLE restricted.patient_session_links (
    patient_id  UUID NOT NULL REFERENCES restricted.patients (id),
    session_id  UUID NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (patient_id, session_id)
);

CREATE INDEX patient_session_links_session_idx
    ON restricted.patient_session_links (session_id);

COMMIT;
