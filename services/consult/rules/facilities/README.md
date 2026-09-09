# The facility index

Routing decides what a facility must be able to do. This file says which
facilities can do it. Without it a triage result names a specialty and sends
the patient nowhere in particular.

**No index ships with this repository, deliberately.** Facilities are local:
what a district hospital in Nagpur stocks has nothing to do with one in
Guwahati, and a plausible-looking sample index is the kind of thing that gets
deployed by accident. A deployment builds its own from its own survey.

## Format

CSV, at `services/consult/rules/facilities/index.csv`, or wherever
`load_facility_index()` is pointed.

```csv
id,name,district,latitude,longitude,capabilities,verified_on,phone
GMC_NGP,Government Medical College,Nagpur,21.1458,79.0882,emergency_24x7|intensive_care|antivenom,2026-09-01,0712-2760000
```

| Column | Meaning |
|---|---|
| `id` | Stable identifier. Must be unique; a duplicate is refused rather than resolved. |
| `name` | What a patient would be told to look for. |
| `district` | For reporting, not for matching. |
| `latitude`, `longitude` | Decimal degrees. Used to order candidates, not to promise travel time. |
| `capabilities` | Pipe-separated. Every value must be a member of `Capability`. |
| `verified_on` | ISO date. When someone last confirmed this facility's capabilities. |
| `phone` | Optional. |

## What `capabilities` must mean

**What this facility can do today, not what its category implies.** A district
hospital that should have a blood bank and does not is exactly the case this
index exists to catch. Copying capabilities from IPHS norms would produce an
index describing what facilities are supposed to be, which is not what a
patient in the back of an auto-rickshaw needs.

The permitted values are the `Capability` enum in `spine/schemas/triage.py`,
which is grounded in IPHS 2022. An unrecognised value is a load error, not a
skipped field: a misspelled `snake_antivenom` would silently stop matching
snakebite, and the failure would look like an absence of facilities rather than
a typo.

## What the matcher will and will not do

**All capabilities, or no match.** A facility meeting three of four
requirements is not a 75% match. It is a place that cannot treat this patient,
and offering it is worse than offering nothing, because the patient travels
believing they were routed.

**Distance orders, it does not qualify.** The nearest *capable* facility is the
answer. The nearest facility is not. Great-circle distance is a straight line;
in hill districts road distance can be several times that, so it ranks
candidates rather than estimating a journey.

**No match is a real answer.** An empty result means no known facility can do
what this patient needs. A clinician acts on that — transferring further afield
or treating in place — and it must not be papered over.

**What was skipped is explained.** A patient told to travel past their district
hospital gets a reason: the closer facilities that were rejected, and what each
one lacked.

## Staleness

Entries are trusted for 90 days from `verified_on`. After that they still
match, but every answer carries `stale`.

Ninety days is a judgement, not a measurement — short enough that a closed ward
is noticed within a quarter, long enough that a district with hundreds of
facilities is not re-surveying constantly. A deployment that can refresh more
often should.

Nothing is hidden when the index goes stale. A stale index is better than no
index, and much better than a caller silently believing it is current.

## Building one

There is no open dataset of Indian facility capabilities at this granularity.
The National Health Facility Registry lists facilities but not whether a given
hospital has antivenom in stock tonight, which is the question that matters.

In practice this is a survey: the district health officer, the hospitals
themselves, or an existing referral list already maintained on paper. Whoever
maintains it owns `verified_on`, and that date is the only thing standing
between a routing decision and a guess.
