# Red flag citations, for clinician review

**Nothing in this file changes a rule.** Every rule in this directory still
carries `verify_before_ship: true` and every `source:` line still reads
PLACEHOLDER. This is the reading a reviewing clinician would otherwise have to
do themselves, not a substitute for their signature.

The same reasoning as `services/labs/rules/critical_values/CANDIDATES.md`
applies: `verify_before_ship: true` does not mean *no source has been found*.
It means *a named clinician reviewed this criterion and accepts responsibility
for it*. Finding the guideline is the easy half.

## What this pass found, in one line

The *logic* of these rules holds up. Nearly every criterion combination below
maps onto a real published criterion from a guideline that is current. What
does not follow is the **translation** — every one of these guidelines assumes
an examiner who can see, touch and measure the patient, and Consult has a
reported history and nothing else. That gap is the reviewer's decision on each
rule, and it is set out per family below.

---

## Cardiorespiratory

### RF_ACS_001 — possible acute coronary syndrome

Candidate: **NICE CG95**, recent-onset chest pain of suspected cardiac origin
(2010, recommendations added 2016; 2019 surveillance found no evidence
changing them).

CG95 opens by asking whether the person has pain now and, if not, when the last
episode was — a timing question this rule does not encode at all, because
Consult captures pain onset but does not branch on the 12-hour mark CG95 uses.
A reviewer should decide whether that omission is safe here.

The rule's four combinations — radiation to jaw or left arm, diaphoresis,
dyspnoea over 40, pressure character worse on exertion — are the classic
features CG95 treats as raising suspicion. It is the *width* that needs
signing: CG95 stratifies with an ECG and troponin, and this rule has neither,
so it must be wider than the guideline to be equally safe.

The `notes:` block on this rule already flags that diabetes prevalence in this
population argues for a lower threshold still. That remains an unmade clinical
decision, and it is the single most consequential one in this file.

### RF_AORTIC_001 — possible aortic dissection

No dedicated national guideline was searched for this rule. Tearing character,
radiation to the back and sudden onset are the textbook triad and appear in
every acute chest pain differential, but a reviewer should name the source they
rely on rather than inheriting a triad from general knowledge. **Not
researched; left for the reviewer.**

### RF_PE_001 — possible pulmonary embolism

Not researched. Wells and PERC exist and are validated, but both include
examination findings and clinician gestalt that Consult cannot supply, so the
translation problem here is worse than average. A reviewer should decide
whether a symptom-only PE screen is defensible at all or whether this rule
should be widened to catch and refer rather than to suspect.

### RF_RESP_FAILURE_001 — respiratory compromise

Not researched, and probably the least in need of it: inability to speak in
sentences, stridor, and breathlessness at rest with altered consciousness are
airway and breathing failure by definition rather than by criterion. The
reviewer's question is not the threshold but whether reported inability to
speak sentences can be trusted from a patient who is, by the same criterion,
struggling to speak.

### RF_ANAPHYLAXIS_001 — possible anaphylaxis

Candidate: **Resuscitation Council UK, Emergency treatment of anaphylaxis**
(May 2021 guidance, current).

This one maps well. RCUK defines anaphylaxis as sudden onset with rapid
progression of **airway and/or breathing and/or circulation** problems, usually
with skin and mucosal changes. The rule's first two combinations are airway
(lip or tongue swelling, stridor); the third is exposure plus skin plus
breathing.

The reviewer's decision: RCUK is explicit that skin changes alone are **not**
anaphylaxis, and equally that anaphylaxis can occur *without* them. This rule
requires a breathing or airway feature in all three branches, which is
consistent — but it has no circulation branch at all. A patient with allergen
exposure who is faint and clammy with no airway feature does not fire this
rule. That is a real gap, and whether to close it is a clinical call.

### RF_SYNCOPE_001 — syncope with cardiac features

Not researched. Syncope during exertion, with chest pain, or with palpitations
are the features that separate cardiac syncope from vasovagal in every source,
but the reviewer should name theirs.

### RF_HAEMOPTYSIS_001 — significant haemoptysis

Not researched, and deliberately so. The existing `source:` note is right that
tuberculosis prevalence changes this differential materially, and that is a
local epidemiological judgement no UK or US guideline supplies. This rule needs
an Indian source or an Indian clinician; it should not inherit a Western
threshold.

---

## Neurological

### RF_STROKE_001 — possible stroke

Candidate: **NICE NG128**, stroke and TIA in over 16s.

NG128 recommends a validated tool such as **FAST** outside hospital to screen
people with **sudden onset** of neurological symptoms, and treating suspected
stroke as an emergency with immediate transfer. The rule's four branches are
face, arm, speech and visual loss, each gated on sudden onset — FAST plus
vision, which is the common local extension of it.

The reviewer decides two things. First, whether to move to **BE-FAST**: NG128
says "a validated tool such as FAST", and posterior circulation strokes
presenting with balance and eye signs are the recognised FAST miss. Second, the
rule has no time window, and the existing `notes:` block explains why —
`last_known_well_hours` is captured but reperfusion eligibility is a threshold
that needs a verified source before it is written anywhere. That is still true
and still deliberate.

### RF_TIA_001 — resolved focal neurological deficit

Same guideline. NG128 says refer immediately for specialist assessment **within
24 hours**, and explicitly says **do not use ABCD2** or any scoring system to
decide urgency of referral. That is a direct endorsement of this rule's shape:
it does not score, it escalates on the fact of resolution.

The reviewer should note that NG128's 24-hour standard is more urgent than
`ESCALATE_BAND` may deliver depending on band mapping. Worth checking that the
escalated band actually lands inside 24 hours.

### RF_SAH_001 — thunderclap headache

Candidate: **Ottawa SAH Rule** (100% sensitivity, 15.3% specificity in
derivation; externally validated in UK and Japanese cohorts).

The Ottawa high-risk features are age ≥40, neck pain or stiffness, witnessed
loss of consciousness, onset during exertion, thunderclap headache, and limited
neck flexion. The rule here has worst-ever headache with sudden onset, with
vomiting, or with neck stiffness — overlapping but not the same set.

Three things for the reviewer:

- Ottawa defines thunderclap as **instantly peaking**. The rule's `notes:`
  block says `time_to_peak_minutes` is already captured as its own field so a
  verified criterion can be added without a schema change. It should be.
- Ottawa's age ≥40 and onset-during-exertion features are absent here.
- Ottawa's exclusions matter and Consult cannot apply them: it must not be used
  in patients with new neurological deficit, prior SAH or aneurysm, or chronic
  recurrent headache of the same character. A screening rule that fires anyway
  is safer than one that excludes; a reviewer should confirm they want that.

Ottawa is a **rule-out** tool for deciding on imaging. Using its features to
rule *in* suspicion is a different use, and its 15% specificity means this rule
will fire often. That is defensible for a referral system and indefensible for
a diagnostic one.

### RF_MENINGISM_001 — possible meningitis

Not researched. Neck stiffness with fever, neck stiffness with photophobia, and
fever with rash and altered consciousness are standard, and the third branch is
the meningococcal presentation. Note that WHO IMCI lists **stiff neck** as a
general danger sign in children, which supports the pattern independently.

### RF_RAISED_ICP_001, RF_SEIZURE_001, RF_TEMPORAL_ARTERITIS_001, RF_VISION_LOSS_001

Not researched. Temporal arteritis in particular has an established age
threshold (the rule uses over 50) and ESR/biopsy criteria that Consult cannot
apply; the reviewer should confirm the age gate against their source, since a
50-year-old with jaw claudication is the case this rule exists to catch.

---

## Obstetric and abdominal

### RF_ECTOPIC_001 — possible ectopic pregnancy

Candidate: **NICE NG126**, ectopic pregnancy and miscarriage.

NG126 lists as common symptoms abdominal or pelvic pain, amenorrhoea or missed
period, and vaginal bleeding with or without clots; and as other reported
symptoms **shoulder tip pain**, dizziness, fainting or syncope, breast
tenderness, gastrointestinal and urinary symptoms, passage of tissue, and
rectal pressure or pain on defecation.

The rule's four branches and its `escalate_if: [dizziness_or_fainting_present]`
modifier all sit inside that list. NG126 also says women who are
haemodynamically unstable, or where there is significant concern about pain or
bleeding, go directly to A&E, which supports `TERMINATE_EMERGENCY`.

The rule's own note — that it fires on suspicion, that a negative or absent
pregnancy test does not suppress it, and that unknown pregnancy status is not
treated as not-pregnant — is the correct reading of NG126.

Gap for the reviewer: NG126's symptom list is broader than these four branches.
Amenorrhoea alone with pain is a branch this rule does not have, unless
`pregnancy_possible_or_confirmed` already resolves from a missed period. That
predicate's definition should be checked, because it carries most of the weight
of this rule.

### RF_PRE_ECLAMPSIA_001 — features suggesting pre-eclampsia

Candidate: **FOGSI–GESTOSIS–ICOG Good Clinical Practice Recommendations on
Hypertensive Disorders in Pregnancy**. Indian, which matters more here than
usual.

The danger signs of severe pre-eclampsia in that document, and in the wider
literature on eclampsia, are **headache, visual disturbance and epigastric or
right upper quadrant pain** — the three symptoms this rule already turns on.
The match is close enough that the reviewer's work is confirmation rather than
construction.

The existing `source:` note explains that no blood pressure threshold is
encoded because Consult does not measure blood pressure. FOGSI's own criteria
are BP-anchored (>160/110, or >140/90 with danger signs), so this rule is
deliberately using only the second half of a two-part definition. A reviewer
should confirm that firing on danger signs without a BP is what they want — it
is more sensitive and less specific than FOGSI intends, which is probably right
for a referral system.

Swelling of face or hands is the rule's third branch and is the weakest: oedema
was dropped from the pre-eclampsia definition decades ago because it is so
common in normal pregnancy. It is paired with visual disturbance here, which
mitigates it, but it is the branch most likely to generate noise.

### RF_TORSION_001 — possible testicular torsion

Candidate: **EAU Guidelines on Paediatric Urology**, acute scrotum chapter.

EAU states that sudden onset of severe pain with a vagal reaction — nausea,
vomiting — is typical of testicular torsion, that it is a **clinical
diagnosis**, and that immediate surgical exploration should not be postponed
for imaging. Salvage is time-dependent with a critical window around four to
six hours.

Both of the rule's branches (sudden onset with vomiting; sudden onset under 18)
sit inside that. The existing note asking whether the criteria are wide enough
is the right question, and the source suggests an answer: sudden severe scrotal
pain **alone**, with no second feature, arguably should fire, since the
guideline treats the history as sufficient grounds to operate.

### RF_OBSTETRIC_BLEED_001, RF_REDUCED_FETAL_MOVEMENT_001

Not researched. Reduced fetal movement has an established RCOG green-top
guideline and an equivalent Indian standard; both should be looked at, and
whether `ESCALATE_BAND` is sufficient for *absent* — as opposed to reduced —
movements is a real question.

### RF_PERITONISM_001, RF_GI_BLEED_001

Not researched.

---

## Systemic and risk

### RF_SEPSIS_001 — sepsis screen positive

Candidate: **NICE NG51**, suspected sepsis (2016, amended January 2024
following the Academy of Medical Royal Colleges 2022 recommendations).

NG51's high-risk criteria for people over 12 include **new altered mental
state**, raised respiratory rate and hypotension. Only the first of those is
reportable without observations, and the rule uses it. The 5-to-11 criteria are
softer and more usable here: altered behaviour, not responding normally to
social cues, or appearing ill.

The existing `source:` note already says the honest thing — Consult takes no
observations, so this is a symptom screen and not a physiological score, and a
clinician must decide whether that is sufficient. NG51's own structure confirms
the problem rather than solving it: most of its high-risk criteria are
measurements. The 2024 amendment moved NG51 further toward clinical judgement
and away from a fixed trigger, which is a point in favour of widening this rule
rather than narrowing it.

### RF_DKA_001 — features suggesting diabetic ketoacidosis

Not researched, because the blocker on this rule is structural rather than
bibliographic. The existing note is correct: this should be gated on known
diabetes, and comorbidities are not a registry field yet. **That gap should be
closed in the schema before a clinician spends time on the criteria**, since
the criteria will change once the gate exists.

### RF_DEHYDRATION_001 — significant dehydration

Not researched separately; the paediatric branch is covered by IMCI below,
which lists severe dehydration among its danger signs.

### RF_PAEDIATRIC_DANGER_001 — paediatric danger signs

Candidate: **WHO IMCI general danger signs** (age 2 months to 5 years).

The closest match in this file. IMCI's general danger signs are: unable to
drink or breastfeed, vomiting everything, convulsions with the current illness,
and lethargic or unconscious. The rule's four branches are altered
consciousness, breathing difficulty, minimal or no oral intake, and seizure —
three of the four are IMCI danger signs almost verbatim, and breathing
difficulty is IMCI's separate cough-and-difficult-breathing arm.

For the reviewer:

- IMCI's fuller list also includes **stiff neck, severe dehydration, stridor in
  a calm child, oedema of both feet, severe palmar pallor**, and malnutrition
  by MUAC <115mm or WHZ below −3. Several of those are visible signs Consult
  cannot obtain, but stiff neck and stridor are reportable and are not in this
  rule.
- IMCI is **2 months to 5 years**. The rule is `age_under_5` with no lower
  bound — safe here only because `RF_UNDER_TWO_001` fires first and routes to a
  human. That interaction is deliberate and should be confirmed as intended
  rather than rediscovered later.
- "Vomiting everything" is a stronger criterion than vomiting, and this rule
  does not use vomiting at all. Worth a decision.

India runs an adapted **IMNCI** rather than IMCI, and a reviewer working here
should cite the national adaptation rather than the WHO original.

### RF_UNDER_TWO_001

Already verified. It encodes a product scope boundary, not a clinical
criterion. Nothing to research.

### RF_SUICIDE_RISK_001 — suicidal ideation with plan or intent

Candidate: **NICE NG225**, self-harm: assessment, management and preventing
recurrence.

This is the one place where the guideline **argues against part of the rule's
design**, and it is the most important finding in this file after the ACS
diabetes note.

NG225 moves deliberately away from risk prediction and stratification. It says
practitioners should not use risk assessment tools or scales to predict future
suicide or self-harm, or to decide who is offered treatment, and should instead
carry out a psychosocial assessment with a collaborative risk formulation and a
safety plan.

The rule's `modifiers.escalate_if: [means_available_present, patient_is_alone]`
is stratification. It sorts people who have disclosed suicidal intent into more
and less urgent.

Two defences are available and a clinician must pick one:

1. The rule's *base* action is already `TERMINATE_EMERGENCY` for everyone who
   meets it. The modifier cannot filter anyone out and cannot lower a band, by
   construction. So this is not stratification for *access*, only for *urgency
   within an emergency*, which NG225 does not forbid.
2. Or the modifier should go, and every disclosure is treated identically.

I would not choose between those. Defence 1 is the one I believe is correct,
and it is exactly the kind of belief that should not be the reason a rule ships.

Separately, the existing note is right that the patient-facing message for this
rule needs writing with clinical input and does not exist. A rule that
terminates a session for a suicidal patient without a helpline and a named
human at the end of it is worse than no rule.

### RF_HARM_TO_OTHERS_001

Not researched. This is as much a legal and duty-to-warn question as a clinical
one, and in India that means a different body of guidance again. Flagging it as
needing legal input alongside clinical, like the Forensics statutory mapping.

### RF_TRAUMA_MAJOR_001

Not researched. Penetrating and high-energy mechanisms are standard major
trauma triage criteria; a reviewer should cite the trauma network standard they
work to.

### RF_HEAD_INJURY_001 — head injury with concerning features

Candidate: **NICE NG232**, head injury: assessment and early management (2023).

The cleanest match in this file after IMCI. All three of the rule's branches
are NG232 criteria:

- **amnesia** for events before or after the injury — an NG232 factor in
  deciding on emergency department referral
- **vomiting** episodes since the injury — likewise, with NG232 adding that
  clinical judgement is needed about the cause of vomiting in children 12 and
  under, which this rule does not distinguish
- **anticoagulant or antiplatelet treatment** — NG232 says consider CT even
  with no other indication, because intracranial bleeding can be occult early

One correction the reviewer should make: NG232 **excludes aspirin monotherapy**
from the antiplatelet criterion. The predicate here is
`anticoagulant_use_present`, and whether it currently resolves for aspirin
should be checked — a rule that fires on every patient taking aspirin will fire
constantly and be ignored.

---

## What a reviewer must decide, per rule

Finding the guideline does not produce the rule. For each of the 30, four
things remain:

1. **Whether the criteria translate.** Every guideline above assumes an
   examiner. Consult has reported history. A criterion that reads well and
   cannot be answered by a patient over voice is not a criterion here.
2. **How much wider to go.** Each of these guidelines sits downstream of
   observations, ECGs or bloods that Consult does not have. A rule with less
   information than the guideline assumed must be **wider** to be equally safe,
   and how much wider is a judgement about how much over-referral this setting
   can absorb.
3. **Whether the source applies in India.** Haemoptysis and TB; IMNCI rather
   than IMCI; FOGSI rather than NICE for obstetrics; snakebite and antivenom,
   which appear in no rule here at all. Several of these should not inherit a
   UK threshold.
4. **The action, not just the trigger.** `TERMINATE_EMERGENCY` versus
   `ESCALATE_BAND` is a clinical decision no guideline states, because no
   guideline knows what this system does next.

Then, per rule: set `verify_before_ship: false`, record `verified_on` and the
reviewer, and replace the `source:` line with what they actually relied on.

---

## Sources

- [NICE CG95 — recent-onset chest pain of suspected cardiac origin](https://www.nice.org.uk/guidance/cg95)
- [NICE NG128 — stroke and TIA in over 16s](https://www.nice.org.uk/guidance/ng128/chapter/recommendations)
- [NICE NG51 — suspected sepsis](https://www.nice.org.uk/guidance/ng51/chapter/recommendations)
- [NICE NG126 — ectopic pregnancy and miscarriage](https://www.nice.org.uk/guidance/ng126/chapter/Symptoms-and-signs-of-ectopic-pregnancy-and-initial-assessment)
- [NICE NG232 — head injury](https://www.nice.org.uk/guidance/ng232/chapter/recommendations)
- [NICE NG225 — self-harm](https://www.nice.org.uk/guidance/ng225/chapter/Recommendations)
- [Resuscitation Council UK — emergency treatment of anaphylaxis](https://www.resus.org.uk/library/additional-guidance/guidance-anaphylaxis)
- [WHO — IMCI danger signs evidence review](https://www.who.int/publications/i/item/WHO-MCA-19.02)
- [IMCI chart booklet, 2 months to 5 years](https://comdis-hsd.leeds.ac.uk/wp-content/uploads/sites/50/2016/01/IMCI-English-version.pdf)
- [FOGSI–GESTOSIS–ICOG — hypertensive disorders in pregnancy](https://icogonline.org/wp-content/uploads/pdf/gcpr/hdp_fogsi_gestosis_icog_gcpr_2019.pdf)
- [EAU Guidelines on Paediatric Urology — acute scrotum](https://uroweb.org/guidelines/paediatric-urology/chapter/acute-scrotum)
- [Ottawa SAH rule](https://www.mdcalc.com/calc/3875/ottawa-subarachnoid-hemorrhage-sah-rule-for-headache-evaluation)
- [AIIMS Triage Protocol](http://www.indusem.org/wp-content/uploads/covid/ATP-AIIMS.pdf) — context for what triage in an Indian emergency department actually looks like

Compiled 2026-09-09. No rule was modified.
