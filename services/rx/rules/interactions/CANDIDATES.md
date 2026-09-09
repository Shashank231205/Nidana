# Drug interaction data: what is available, and the licence problem

**Nothing is implemented.** `services/rx/clinical/checks.py` runs duplicate
therapy and allergy checks, which need only the patient's own record. Pairwise
drug–drug interaction checking needs a dataset, and this file records which
datasets exist and why none of them has been adopted yet.

Brand-to-molecule resolution is a solved problem here as of
`scripts/build_brand_index.py` — 175,953 Indian brands from an MIT-licensed
source. Interactions are the remaining half, and they are harder for a reason
that is legal rather than technical.

## The candidates

### DDInter — the best data, on a licence that may not fit

236,834 interactions across 1,833 approved drugs, with mechanism descriptions,
risk levels, management strategies and alternative medications. Bulk CSV
download by ATC class. Published in *Nucleic Acids Research* (DDInter 2021,
DDInter 2.0 in 2025), so the curation is documented rather than scraped.

It is the most usable dataset found, and the risk levels and management
strategies are exactly the fields a pharmacist-facing check needs.

**Licence: CC BY-NC-SA 4.0.** Non-commercial only, share-alike on derivatives.

This is a decision for the repository owner, not an engineering one:

- If Nidana is deployed non-commercially, this is usable with attribution, and
  the share-alike term applies to any derived interaction dataset.
- If Nidana is or becomes a commercial product, it is not usable without
  separate permission from the authors.

The share-alike clause deserves attention even in the non-commercial case: a
derived file committed to this repository would carry CC BY-NC-SA, which is a
stronger claim on the repository than an MIT dataset makes.

### RxNorm / RxNav — public domain, but no longer carries interactions

US National Library of Medicine. The RxNorm terminology is **public domain** as
a US government work, with no licence needed for the API, and it is the obvious
choice for molecule normalisation — mapping the molecule names this repo's
brand index produces onto stable RXCUI identifiers.

But the **NLM Drug Interaction API was discontinued on 2 January 2024**, and
RxNav's interaction features went with it. RxNorm remains excellent for
normalisation and supplies nothing for interactions.

### DrugBank — comprehensive, commercially licensed

The reference dataset most interaction checkers are built on, and the source
that replaced NLM's own interaction API. Free for academic use with
registration; commercial use is licensed and priced. Not free in the sense this
project needs.

### The prediction literature

BIOSNAP (1,514 drugs, 48,514 interactions), TWOSIDES, and the deep-learning DDI
benchmarks are research artefacts. TWOSIDES in particular is derived from
adverse event *reports*, which is a different kind of claim from a curated
interaction: it records statistical association in a spontaneous reporting
system, not an established pharmacological mechanism.

**These should not be used here.** A predicted interaction presented to a
pharmacist with the same weight as a documented one is the failure mode this
service is built to avoid, and no confidence score displayed alongside it fixes
that.

## What is missing from all of them for this setting

Even with a licence resolved, three gaps remain and a pharmacist should be told
about them rather than discovering them:

1. **Indian formulations are combination-heavy.** The brand index shows 112,171
   of 253,973 products carrying two molecules. Pairwise interaction data
   assumes single molecules, so a two-brand prescription can be a four-molecule
   interaction problem, and the number of pairs to check grows accordingly.

2. **Ayurvedic and traditional preparations are absent.** The source dataset is
   allopathy-only by its own field. Co-prescription is common, and an
   interaction checker silent on those preparations will look authoritative
   while covering only part of what the patient is taking.

3. **Severity grading is institutional.** As with the critical value
   thresholds, what counts as a major interaction differs between sources.
   DDInter's risk levels are its own, and adopting them adopts its judgement.

## What would need to happen

1. The repository owner decides whether CC BY-NC-SA fits this project's
   licensing and distribution intent. That question is not answerable from
   inside the code.
2. If yes: download by ATC class, map DDInter's drug names onto the molecule
   names the brand index produces — the join is the real engineering work here,
   since neither side uses RXCUI — and keep the derived file out of the
   repository the way the brand index and knowledge index already are.
3. The unmatched molecules are reported rather than dropped silently. A
   molecule the interaction dataset does not know is a molecule whose
   interactions are unchecked, and the pharmacist must be told which.

## Sources

- [DDInter](https://ddinter.scbdd.com/) — data under CC BY-NC-SA 4.0
- [DDInter, *Nucleic Acids Research* 2022](https://academic.oup.com/nar/article/50/D1/D1200/6389535)
- [DDInter 2.0, *Nucleic Acids Research* 2025](https://academic.oup.com/nar/article/53/D1/D1356/7740584)
- [RxNorm overview](https://www.nlm.nih.gov/research/umls/rxnorm/overview.html) — public domain
- [RxNorm terms of service](https://www.nlm.nih.gov/research/umls/rxnorm/docs/termsofservice.html)

Compiled 2026-09-09. No interaction data has been downloaded or committed.
