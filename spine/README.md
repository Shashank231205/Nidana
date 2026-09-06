# The spine

Built once, used by all five services. Every structural mistake here multiplies
by five, which is why it is built before any service.

## Layout

| Folder | Holds | Status |
|---|---|---|
| `schemas/` | every clinical data shape — the single source of truth | built |
| `rules/` | the deterministic rule engine and its loaders | built |
| `terminology/` | SNOMED CT and ICD-10 lookup | not started |
| `audit/` | append-only, hash-chained event log | not started |
| `inference/` | the one adapter every model call goes through | not started |
| `identity/` | patient resolution across services | not started |
| `persistence/` | repositories | not started |
| `fhir/` | FHIR R4 mapping | not started |

## The three things that matter most

**Groundedness.** Every clinical fact carries the span it came from. `Provenance`
is a discriminated union of five variants, one per service: verbatim words for
Consult, transcript plus audio offset for Scribe, OCR bounding box for Rx, page
and cell for Labs, the examiner's signed entry for Forensics. A span that does
not verify as an exact substring of its source is a fabrication and is rejected.

**The rule engine.** One engine, several rule sets. Consult contributes red
flags, Rx interaction and duplicate therapy checks, Labs critical values, Scribe
note completeness, Forensics protocol compliance. Rules are declarative YAML,
versioned and cited. Anything where being wrong causes physical harm lives here
and never in a prompt.

**Predicate resolution.** Rules reference named predicates, not raw field names.
Loading resolves every atom against the field registry and fails loudly on one
that does not exist. Without this, a typo produces a rule that evaluates false
forever while its negative tests keep passing — the most dangerous defect this
repository can contain.

## Boundaries

The spine holds the engine, never the rules. Rule content belongs to the service
that owns it, at `services/<name>/rules/`.

The spine defines every clinical shape. No service defines a parallel one.

Nothing in the spine imports from a service.
