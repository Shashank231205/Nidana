# RF_AORTIC_001 — Possible aortic dissection

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **clinical guideline review**. Reviewed 2026-09-09 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — Indian practice reviewer** was cut off before finishing, so what survives reads more one-sided than it was.

## RF_AORTIC_001 – panel brief

**The panel has not verified this rule.** It remains blocked from release and requires a named clinician.

### What the panel agrees on
1. **Missed presentation** – The rule will not fire for patients who experience *tearing‑type back pain* without any accompanying chest pain. This is a realistic clinical scenario, especially in low‑resource settings where patients may not describe pain in Western terms.
2. **Potential over‑referral** – Patients who meet the encoded criteria (chest pain + tearing pain *or* chest pain + radiates to back + sudden onset) but do **not** have aortic dissection may be unnecessarily escalated to emergency imaging or ICU care, incurring unnecessary resource use.
3. **Schema limitation** – The available predicate set does not include a dedicated flag for “tearing‑type abdominal pain” (e.g., `abdominal_pain_character_tearing_present`). Consequently, the rule cannot fully capture the canonical presentation of aortic dissection without forcing a chest‑pain prerequisite.

### Where the panel disagrees
- **Emergency Physician** argues that the rule should be kept as‑is because:
  - It aligns with guideline‑driven safety (tearing chest pain is a strong indicator of aortic dissection).
  - It avoids false positives in patients who may have other severe abdominal conditions.
- **Safety Engineer** argues that the rule should be relaxed to allow detection solely on the combination of `pain_radiates_to_back` and `pain_onset_sudden`, even without chest pain, because:
  - Many aortic dissection patients present with isolated back pain.
  - Retaining the chest‑pain gate may lead to missed diagnoses, especially in populations where chest pain is under‑reported.

### What turns the choice on
- **Clinical priority:** Whether the primary goal is to **prevent missed diagnoses** (favoring relaxation of the chest‑pain requirement) or to **maintain safety** by avoiding unnecessary escalation (favoring retention of the chest‑pain gate).
- **Resource constraints:** In Indian district hospitals, the cost of unnecessary ICU admission or transport may be prohibitive, whereas missing a dissection could be life‑threatening.
- **Data availability:** The current predicate registry lacks a dedicated flag for “tearing‑type abdominal pain,” making it difficult to implement a rule variant without schema changes.

### Refer to
A **clinical guideline review** (e.g., AHA/ACC 2023) and an **Indian emergency medicine consensus** should be consulted to determine whether the chest‑pain prerequisite is justified in the local epidemiology and resource environment.

### Questions for the verifying clinician
1. **Is the absence of chest pain a clinically valid exclusion criterion for aortic dissection in the target population?** If not, should the rule be modified to fire on `pain_radiates_to_back & pain_onset_sudden` alone?
2. **What is the prevalence of aortic dissection presenting with isolated back pain in the region where this rule will be deployed?** Data on presentation patterns will inform whether the current rule’s omission of back‑pain‑only criteria is a safety issue.
3. **What are the resource implications of relaxing the rule?** Will the change lead to a measurable reduction in unnecessary ICU admissions or imaging costs, and what is the expected impact on early detection rates?
4. **Can a temporary rule variant be implemented (e.g., a secondary triage pathway) while the schema is updated to include `abdominal_pain_character_tearing_present`?** This would allow immediate clinical use without delaying schema changes.
5. **How will the rule be communicated to frontline staff in low‑resource settings where chest‑pain reporting may be incomplete?** Are there alternative descriptors (e.g., “pain radiates to the back” or “pain feels like a knife”) that can be captured to trigger the rule?

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_AORTIC_001 will miss patients with a classic “tearing” chest pain who also have neck‑stiffness, severe neck pain, and a rapid onset of back pain – a presentation that is common in aortic dissection but does not satisfy the required chest‑pain‑plus‑pain‑radiation‑or‑sudden‑onset pattern.

**Missed patient (concrete example):**

- **Demographics:** 58‑year‑old male, known hypertension, no known aortic disease.
- **Chief complaint:** “It feels like a knife is stabbing through my chest” (pain_character_tearing). He reports the pain began **suddenly** while he was walking up stairs, with no preceding crushing pressure.
- **Associated symptoms:** Moderate neck stiffness, severe pain radiating to the left arm, dyspnoea on exertion, diaphoresis, and a feeling of impending doom. No back pain or radiation to the back is reported.
- **Why the rule fires:** The rule requires **chest_pain_present AND pain_radiates_to_back** (or chest_pain_present AND pain_character_tearing **without** the radiation component). Because the rule’s first line (`chest_pain_present AND pain_character_tearing`) is satisfied, but the second line (`chest_pain_present AND pain_radiates_to_back AND pain_onset_sudden`) is **not** (the back‑radiation criterion is missing), the rule does not trigger.
- **Result:** The patient is triaged as having a possible aortic dissection, but because the rule does not fire, he is not escalated to the emergency department’s vascular imaging protocol, delaying critical diagnosis and management.

**Why this patient is a realistic missed case:**

1. **Teardrop‑type chest pain** is the hallmark of classic aortic dissection and is often described as “stabbing” or “tearing.” Many patients with this presentation do **not** experience pain radiating to the back, especially if the dissection is in the ascending aorta and the pain is limited to the chest.
2. **Neck stiffness** is a red‑flag sign that is frequently absent from the rule’s criteria, yet it is a well‑documented predictor of aortic dissection.
3. **Sudden onset** without prior crushing chest pain is common, particularly in younger patients with hypertension, who may not recall a gradual progression.
4. **No imaging or history** of back pain is required by the rule, so the absence of back‑radiation does not trigger escalation.

**Implication:** Patients who present with tearing chest pain, neck stiffness, and dyspnoea—without any documented back pain—will be under‑triaged and may receive delayed definitive care, potentially leading to irreversible complications.

**Next steps for verification:**

- Add a clause that allows escalation when **chest_pain_present AND pain_character_tearing** (regardless of back‑radiation) and **neck_stiffness_present** are both true.
- Consider incorporating **age_over_40** or **high_energy_mechanism** as additional risk factors to reduce false‑negative rates.
- Ensure that the rule’s action (TERMINATE_EMERGENCY) is triggered for any patient meeting the above criteria, regardless of whether back‑radiation is present.

### safety engineer

**Headline:** The rule fails to fire on a classic presentation of aortic dissection that meets all encoded criteria but lacks the “chest‑pain” component, representing a safety‑engineer edge case.

### Misses
**Concrete patient (Missed case):**  
- **Age:** 58‑year‑old male (age > 40, so age criteria are satisfied).  
- **Presentation:** Sudden onset of severe epigastric pressure and tearing‑type pain radiating to the back, accompanied by marked diaphoresis and dyspnoea.  
- **Key predicates present:**  
  - `pain_radiates_to_back` (fulfills the first encoded line).  
  - `pain_onset_sudden` (fulfills the first encoded line).  
  - `chest_pain_present` is **absent**; therefore the rule never activates.  
- **Why it is missed:** The rule requires the presence of `chest_pain_present` in addition to either `pain_character_tearing` **or** `pain_radiates_to_back & pain_onset_sudden`. A patient whose pain is exclusively tearing‑type and back‑radiating does not satisfy the combined “chest‑pain + tearing” condition, so the rule never fires.

### Over‑referrals
**Concrete patient (Potential over‑referral):**  
- **Age:** 45‑year‑old female with known hypertension and a family history of aortic disease.  
- **Presentation:** Sudden severe back pain with diaphoresis, dyspnoea, and mild chest discomfort (characterized as pressure‑like).  
- **Why it fires:** The patient meets both encoded conditions (`chest_pain_present` + `tearing` **or** `chest_pain_present` + `radiates_to_back` + `sudden onset`). Even though the tearing pain is not the classic “classic” tearing described in most guidelines, the rule’s logic still triggers because the chest‑pain component is present. This illustrates that the rule may be overly sensitive to any chest‑pain signal, potentially leading to unnecessary termination of emergency care for patients whose pain is primarily back‑radiating.

### The case for leaving it alone
**Strengths of the rule as written:**  
1. **Safety‑first principle:** By requiring chest pain, the rule avoids false positives in patients who may have other severe abdominal conditions (e.g., ruptured ectopic pregnancy) that could be misinterpreted as aortic dissection.  
2. **Clinical concordance:** Many emergency protocols (e.g., AHA/ACC guidelines) explicitly state that aortic dissection is strongly suggested when tearing chest pain is present, reinforcing the rule’s alignment with established practice.  
3. **Schema limitation:** The available predicate set does not include a dedicated “tearing‑type abdominal pain” flag; the only way to capture that feature is via the existing `chest_pain_present` gate, which is a limitation of the current data model rather than a design flaw.

**Weaknesses that remain:**  
- **Missed presentation:** Patients whose pain is exclusively tearing and radiating to the back (as in the concrete patient above) will not be flagged, potentially delaying life‑saving imaging or intervention.  
- **Potential over‑referral:** The rule may fire on patients whose chest discomfort is mild or non‑tearing, leading to unnecessary emergency department activation and resource consumption.

### Outside my seat
- **Schema gap:** The absence of a dedicated predicate for “tearing‑type abdominal pain” (e.g., `abdominal_pain_character_tearing`) means the rule cannot fully capture the canonical presentation of aortic dissection without forcing a chest‑pain prerequisite. This gap should be addressed by expanding the predicate registry to include pain‑character‑specific flags.

### The one decision I would put to a clinician
**Decision point:** Whether to retain the requirement of `chest_pain_present` as a gating condition or to relax it to allow detection solely on the combination of `pain_radiates_to_back` and `pain_onset_sudden`.  
**Why it matters:**  
- **If retained:** The rule remains aligned with guideline‑driven safety but risks missing a significant subset of patients (e.g., those with isolated tearing back pain).  
- **If relaxed:** The rule may capture more true cases of aortic dissection, reducing missed‑diagnosis risk, but could also increase false‑positive referrals, necessitating a review of downstream triage actions (e.g., imaging protocol, disposition pathway).

**Actionable recommendation:** Conduct a comparative analysis of local epidemiology (e.g., proportion of aortic dissection cases presenting with isolated tearing back pain) and consider adding a dedicated predicate such as `abdominal_pain_character_tearing_present` to enable a rule variant that fires on `pain_radiates_to_back & pain_onset_sudden` alone. Until such a schema change is made, clinicians should be aware that patients meeting only the back‑radiating + sudden‑onset criteria may be missed and should be triaged for urgent imaging regardless of chest‑pain presence.

### Indian practice reviewer

**Missed Patient (Indian District Hospital Context)**  

**Rule ID:** RF_AORTIC_001 – *Possible aortic dissection – Action: TERMINATE_EMERGENCY*  

**Headline:** The rule fails to fire on a common presentation of aortic dissection in low‑resource Indian settings where imaging is unavailable, leading to delayed or missed diagnosis.

**Miss Construction**

| Feature | Reason it is missing from the rule |
|---------|-----------------------------------|
| **Age & Sex** | The rule does not consider demographic risk factors that are higher in Indian populations (e.g., younger patients, especially women, may present with atypical pain). |
| **Absence of Chest Pain** | A substantial proportion of aortic dissection patients, especially in rural or low‑income settings, present with *no* chest pain (“pain character tearing” or “pain radiates to back”) because they may be unable to describe pain in Western terms or because the pain is masked by other symptoms (e.g., back pain, neck pain). |
| **Alternative Pain Characteristics** | The rule only captures “pain_character_tearing” *and* “pain_radiates_to_back” when chest pain is present. In Indian patients, the primary complaint may be *back pain* or *neck pain* without any chest discomfort. |
| **Atypical Onset** | The rule requires “pain_onset_sudden” *and* “chest_pain_present”. Many patients, particularly those with chronic diseases (e.g., hypertension, diabetes) common in India, may have a *gradual* onset of back pain that is not immediately recognized as “sudden”. |
| **Comorbidities & Contextual Factors** | The rule does not account for common Indian comorbidities that can mimic or exacerbate aortic dissection (e.g., hypertensive emergencies, diabetes‑related microvascular disease) and the limited availability of CT/MRI for rapid imaging. |
| **Referral Network** | In district hospitals, the emergency department may not have immediate access to advanced imaging (CT‑angiography). The rule’s “terminate emergency” action may lead to unnecessary escalation (e.g., ICU admission, costly transport) when the patient could be safely observed and monitored with a bedside Doppler or bedside ultrasound, which are not standard in many Indian facilities. |

**Concrete Patient Example**

- **Patient:** 45‑year‑old male, resident of a rural district hospital in South India.  
- **Risk Factors:** Hypertensive (BP 160/100 mmHg), known diabetes, recent history of heavy lifting (mechanism of injury).  
- **Presenting Complaint:** Sudden severe *back pain* radiating to the left shoulder, described as “sharp, tearing” pain, no accompanying chest discomfort.  
- **Additional Symptoms:** Mild dyspnoea, diaphoresis, palpitations, but no chest pain reported.  
- **Onset:** Pain began 30 minutes ago while performing manual labor; initially felt like a muscle strain but rapidly worsened.  
- **Physical Findings (if any):** No obvious respiratory distress, no chest pain, no neck stiffness, no focal neurological deficits reported.  
- **Why the Rule Misses:**  
  1. **Chest Pain Requirement:** The rule only fires if *chest_pain_present* is true. This patient reports *no* chest pain, so the first criterion is not met.  
  2. **Pain Character:** Even if chest pain were present, the rule only flags “pain_character_tearing” *when* chest pain is present; the patient’s primary symptom is back pain, which is not captured.  
  3. **Suddenness:** The pain onset is sudden, but the absence of chest pain prevents the rule from firing.  
  4. **Imaging Context:** In a district hospital without CT‑angiography, the rule’s “terminate emergency” action could lead to unnecessary ICU admission, while a more appropriate management (e.g., observation, bedside Doppler) might be feasible and cost‑effective.

**Implication**

If this patient were to present to a Western‑style emergency department that strictly enforces RF_AORTIC_001, the clinician would likely escalate to the ICU or emergency surgery without confirming the diagnosis via imaging, potentially missing the opportunity for timely, low‑cost management (e.g., observation, antihypertensive therapy, and bedside ultrasound). Conversely, if the rule were relaxed to capture *back pain* alone (or pain radiating to the back without chest pain), it could prevent missed dissections in similar Indian patients who present without chest discomfort.

**Conclusion**

The rule’s reliance on *chest pain* as a prerequisite creates a systematic bias against a significant subset of aortic dissection presentations in Indian patients—particularly those who cannot or do not describe chest pain. This missed case is a critical safety concern given the limited availability of advanced imaging in many district hospitals, where the rule’s “terminate emergency” action could lead to unnecessary resource consumption and delayed definitive care.
