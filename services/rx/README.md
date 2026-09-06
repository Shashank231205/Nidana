# S3 Rx

Prescription intelligence

**Status:** not started. Phase P3.

Specified in `NIDANA.md`. Nothing here is built yet; the folders exist so the
structure is visible and the boundaries are fixed before code lands in them.

## Layout

| Folder | Will hold |
|---|---|
| `clinical/` | this service's deterministic checks — no model calls |
| `agents/` | its agents — no clinical thresholds |
| `prompts/` | prompts as files, loaded at runtime |
| `rules/` | its rule set, declarative and cited |
| `api/` | its HTTP routes |
| `eval/` | its vignettes, harness, and dated reports |

## What it reuses from the spine

The record and finding shapes, the provenance union, the rule engine,
terminology, the audit chain, and the inference adapter. It defines no clinical
data shape of its own.
