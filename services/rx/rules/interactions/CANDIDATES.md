# Drug interaction data: why a commercial deployment needs a paid licence

**The checker is built; the dataset is not.**
`services/rx/clinical/interactions.py` does pairwise interaction checking
against whatever index it is given, and reports the molecules it could not
check as prominently as the interactions it found. What it has no source for is
the data.

Nidana is a commercial product, and that fact removes every free option. This
file records which datasets exist, why each one is or is not usable here, and
what adopting a paid one would involve.

Brand-to-molecule resolution is a solved problem here as of
`scripts/build_brand_index.py` — 175,953 Indian brands from an MIT-licensed
source. Interactions are the remaining half, and they are harder for a reason
that is legal rather than technical.

## The candidates

### DDInter — the best free data, and not available to this product

236,834 interactions across 1,833 approved drugs, with mechanism descriptions,
risk levels, management strategies and alternative medications. Bulk CSV
download by ATC class. Published in *Nucleic Acids Research* (DDInter 2021,
DDInter 2.0 in 2025), so the curation is documented rather than scraped.

**Licence: CC BY-NC-SA 4.0.** Non-commercial only, share-alike on derivatives.

**Ruled out.** The repository owner has confirmed Nidana is a commercial
product, which puts DDInter outside what its licence permits without separate
written permission from the authors. That permission has not been sought and
this file does not assume it would be given.

Worth writing down rather than forgetting, in case that changes: the data is
good, the curation is documented in two *Nucleic Acids Research* papers, and
the risk levels and management strategies are exactly the fields a
pharmacist-facing check needs. If a licence is ever negotiated, the loader in
`services/rx/clinical/interactions.py` takes it without modification.

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

## Where this leaves a commercial deployment

Nidana is commercial, so the free options are exhausted: DDInter is
non-commercial, RxNorm no longer carries interactions, and the prediction
datasets must not be used at all. What remains is a paid licence.

**The commercial options**, none of which has been priced or approached:

- **DrugBank** — the reference most interaction checkers are built on, and the
  source that replaced NLM's own discontinued API. Commercial licensing exists
  and is the obvious first call.
- **First Databank** and **Medi-Span** — the two established clinical drug
  content vendors. Both carry Indian formulary coverage as a separate question
  to ask, because neither is built around it.
- **DDInter, with permission.** Its authors are academics and the paper names
  them; a commercial licence may simply be a conversation.

**What is already built and waiting.** The checker is complete and
source-agnostic. Adopting any of the above means writing one loader that maps
that vendor's severity grades onto `Severity` and produces a coverage list.
Nothing else changes.

**Until then, Rx runs without it**, reporting
`interaction_checking_available: false` on every check rather than an empty
findings list. That distinction is the point: an empty list reads as "no
interactions found", and what is true is "interactions were not checked".

## When a dataset does arrive

1. Download by ATC class, and keep the derived file out of the repository the
   way the brand index and knowledge index already are.
2. Map that vendor's drug names onto the molecule names the brand index
   produces. This is the real engineering work, since neither side uses RXCUI.
3. Report the unmatched molecules rather than dropping them silently. A
   molecule the dataset does not know is one whose interactions are unchecked,
   and the pharmacist must be told which.

## Sources

- [DDInter](https://ddinter.scbdd.com/) — data under CC BY-NC-SA 4.0
- [DDInter, *Nucleic Acids Research* 2022](https://academic.oup.com/nar/article/50/D1/D1200/6389535)
- [DDInter 2.0, *Nucleic Acids Research* 2025](https://academic.oup.com/nar/article/53/D1/D1356/7740584)
- [RxNorm overview](https://www.nlm.nih.gov/research/umls/rxnorm/overview.html) — public domain
- [RxNorm terms of service](https://www.nlm.nih.gov/research/umls/rxnorm/docs/termsofservice.html)

Compiled 2026-09-09. Updated 2026-09-10, when the repository owner confirmed
the product is commercial. No interaction data has been downloaded or
committed.
