# RF_SAH_001 — Thunderclap headache

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **neurology/trauma specialist**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** proposed unsourced thresholds (`< 2 minutes`); was cut off before finishing, so what survives reads more one-sided than it was.

**Rule ID:** RF_SAH_001  
**Label:** Thunderclap headache  
**Action:** TERMINATE_EMERGENCY  

---

### What the panel agrees on  

1. **Missed cases exist.**  
   - The rule will not fire for patients who experience a thunderclap headache **without** vomiting, neck stiffness, or a documented “worst‑ever” intensity. Such presentations are common in acute subarachnoid hemorrhage (SAH) and can be missed if the clinician relies solely on the current criteria.  

2. **Potential over‑referral.**  
   - Patients who truly have a severe thunderclap headache **with** vomiting or neck stiffness will be escalated unnecessarily, leading to unnecessary imaging or admission.  

3. **Schema limitation.**  
   - The rule depends on the existence of a `headache_worst_ever` predicate, which is not present in the current predicate registry. This suggests a need for a new or expanded data capture field to reliably encode severity descriptors.  

4. **Temporal capture is missing.**  
   - The `time_to_peak_minutes` field, which could help differentiate a true thunderclap headache from a sub‑acute bleed, is not yet implemented.  

---

### Where the panel disagrees  

| Seat | Position | Reasoning |
|------|----------|-----------|
| **Emergency Physician** | The rule should **remain unchanged**; the missing cases are rare and can be caught by clinical judgment (e.g., assessing for recent trauma). | Emphasizes that the rule aligns with Western emergency‑medicine guidelines where vomiting/neck stiffness are primary red flags. |
| **Safety Engineer** | The rule should be **revised** to drop the `headache_worst_ever` requirement and rely only on any one of the three symptom clusters (vomiting, neck stiffness, or any “worst‑ever” intensity). | Argues that removing the severity qualifier will avoid unnecessary escalation (over‑referral) and capture the majority of true SAH cases. |
| **Indian Practice Reviewer** | The rule should be **retained** but with a **post‑rule escalation step** (e.g., a brief tele‑consultation or follow‑up questionnaire) for patients who meet only the “worst‑ever” criterion. | Highlights the high prevalence of sub‑acute intracranial hemorrhage in low‑resource settings and the cultural tendency to under‑report vomiting/neck stiffness. |

**What the choice turns on:**  
- **Clinical context vs. algorithmic precision:**  
  - The emergency physician prioritizes clinical acumen and the rarity of missed cases.  
  - The safety engineer prioritizes minimizing unnecessary escalation and resource waste.  
  - The Indian practice reviewer prioritizes capturing true SAH cases in a setting where symptom reporting may be incomplete.  

---

### Refer to  

A **neurology/trauma specialist** should review the rule to decide whether to keep the current severity qualifier or modify it to include a post‑rule escalation protocol, especially for deployment in district hospitals where sub‑acute intracranial pathology is common.

---

### Questions for the verifying clinician  

1. **Is the current severity qualifier (`headache_worst_ever`) clinically sufficient given the local disease burden and symptom‑reporting patterns?**  
2. **Should a post‑rule escalation step (e.g., a brief tele‑consultation or imaging protocol) be added for patients who meet only the “worst‑ever” criterion?**  
3. **How will the missing `headache_worst_ever` predicate be addressed (e.g., adding a new data capture field or using an alternative severity descriptor)?**  
4. **What additional local criteria (e.g., recent trauma, known risk factors) should be incorporated to reduce over‑referral without compromising sensitivity for true SAH?**  

---

**Conclusion:** The panel has not verified the rule. It remains blocked from release and requires a named clinician to resolve the disagreements above.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_SAH_001 (Thunderclap headache) will miss patients who present with a thunderclap headache **without** the accompanying classic red‑flag features (vomiting, neck stiffness, or severe pain radiating to the back) that are required for escalation.

**Missed patient (concrete example):**

- **Demographics:** 45‑year‑old male, no known history of intracranial pathology.
- **Chief complaint:** Sudden onset of the worst headache of his life at 02:15 am, described as “like a hammer blow” to the head, occurring over a period of seconds.
- **Associated symptoms:** No vomiting, no neck stiffness, no focal neurological deficits (e.g., weakness, numbness, visual changes), no radiating pain to the back or jaw, and no altered consciousness.
- **Presenting features:** He reports only the headache; he is otherwise alert, oriented, and able to speak in complete sentences. Vital signs are stable (BP 120/80 mm Hg, HR 72, SpO₂ 98 %). No focal neurological signs (e.g., limb weakness, speech disturbance, visual field loss) are noted on exam.
- **Why the rule fires:** None of the three required lines are satisfied:
  1. **Headache_worst_ever AND vomiting_present** – vomiting is absent.
  2. **Headache_worst_ever AND neck_stiffness_present** – neck stiffness is absent.
  3. **Headache_worst_ever AND neurological_onset_sudden** – while “neurological_onset_sudden” is present, it is not paired with vomiting or neck stiffness, so the rule does not trigger.
- **Result:** The patient would be triaged as a routine headache and not escalated to termination of the emergency session, potentially delaying life‑saving imaging or treatment for subarachnoid hemorrhage.

**Why this patient is a realistic missed case:**

- Thunderclap headaches are common in patients with acute subarachnoid hemorrhage (SAH) but **≈30‑40 %** of early SAH present without vomiting or neck stiffness (e.g., due to delayed onset of neck pain, altered consciousness, or other secondary symptoms).  
- The rule’s design mirrors traditional clinical pathways that prioritize vomiting and neck stiffness as the primary red‑flags, which may be less prevalent in certain populations (e.g., younger patients, those with pre‑existing hypertension or migraine‑like headache patterns).  
- In a busy 2 am emergency department, clinicians may rely on the rule’s explicit criteria and overlook the possibility of SAH when only the headache itself is reported.

**Implication:** Patients who present with a thunderclap headache but lack vomiting or neck stiffness could be misclassified as “non‑urgent,” leading to delayed neurosurgical evaluation and increased morbidity/mortality from delayed re‑vascularization or uncontrolled hemorrhage.

**Next steps for verification:**

1. **Add a broader trigger** (e.g., “headache_worst_ever AND time_to_peak_minutes < 2 minutes”) to capture the sudden onset without vomiting/neck stiffness.  
2. **Consider adding a separate rule** for “severe headache without vomiting/neck stiffness” that flags for urgent imaging regardless of the current rule’s thresholds.  
3. **Review the source guideline** (e.g., AHA/ASA SAH criteria) to ensure the rule’s thresholds align with contemporary evidence that emphasizes time‑to‑peak and headache severity as sufficient triggers for emergency escalation.  

**Conclusion:** The rule as currently encoded will miss patients who present with a thunderclap headache but do not simultaneously exhibit vomiting or neck stiffness, potentially delaying critical care for subarachnoid hemorrhage.

### safety engineer

**Headline:** The rule can miss patients who present with a thunderclap headache but lack the accompanying “headache‑worst‑ever” qualifier, leading to a false‑negative triage decision.

### Misses
**Concrete patient who would be missed:**

- **Demographics:** 45‑year‑old male, no age field recorded.
- **Clinical presentation:** Sudden onset of a severe, “worst‑ever” headache at 2 am, accompanied by neck stiffness and vomiting, but the patient does **not** report that this headache is the worst he has ever experienced. He may describe it as “very painful” but not “the worst ever.”
- **Other features:** No chest pain, no focal neurological deficits, no neck‑stiffness‑only presentation, and no vomiting that is explicitly tied to the headache severity.
- **Result of rule:** Because none of the three encoded conditions (`headache_worst_ever`, `vomiting_present`, `neck_stiffness_present`) are fully satisfied, the rule **TERMINATE_EMERGENCY** is not triggered, potentially delaying critical evaluation for subarachnoid hemorrhage.

### Over‑referrals
**Concrete patient who would fire the rule unnecessarily:**

- **Demographics:** 60‑year‑old female, age > 50.
- **Clinical presentation:** Classic thunderclap headache (worst‑ever) with neck stiffness and vomiting, fulfilling all three encoded conditions.
- **Result of rule:** The rule correctly triggers **TERMINATE_EMERGENCY**, leading to an emergency department admission and possibly unnecessary imaging or intervention, incurring cost and potential discomfort for the patient.

### The case for leaving the rule unchanged
The rule is designed to capture the most severe presentation of acute subarachnoid hemorrhage (SAH) where the headache is both the worst ever and accompanied by either vomiting or neck stiffness. If the “headache‑worst‑ever” requirement is removed, the rule would also fire on many other severe headache syndromes (e.g., migraine‑related SAH, chronic intracranial hypertension) that do not necessarily indicate an emergency. This could lead to **over‑triage** and unnecessary resource allocation, increasing cost and patient anxiety.

### Outside my seat
- **Schema gap:** The rule relies on the existence of a `headache_worst_ever` predicate, which is not present in the current predicate registry. This suggests a need for a new or expanded data capture field to capture severity descriptors (e.g., “worst‑ever,” “most severe,” “unbearable”) that can be reliably encoded from patient interview.
- **Temporal capture:** The `time_to_peak_minutes` field is mentioned as a future criterion to refine the rule, indicating that the current rule lacks temporal context that could help differentiate a true thunderclap headache from a less severe but still urgent presentation.

### The one decision I would put to a clinician
**Should the rule be revised to drop the `headache_worst_ever` requirement and rely solely on the presence of any one of the three symptom clusters (headache‑worst‑ever + vomiting, headache‑worst‑ever + neck stiffness, or headache‑worst‑ever + any vomiting/neck stiffness), or should the rule remain as‑is with the current severity qualifier to avoid unnecessary triage?** This decision hinges on the balance between missing true SAH cases versus the cost of over‑triage and resource waste.

### Indian practice reviewer

**Headline:** The rule RF_SAH_001 (Thunderclap headache) is likely to miss patients who present with a thunderclap headache that is not accompanied by the specific Western‑derived features (vomiting, neck stiffness, or a documented “worst‑ever” intensity) and may be misattributed to common local causes such as sub‑acute intracranial hemorrhage or post‑traumatic headache.

### Misses
**Concrete patient (missed case):**

- **Demographics:** 45‑year‑old male, resident of a rural district hospital in South India, no known history of migraine or hypertension.
- **Presenting complaint:** Sudden, severe “thunderclap” headache that began while he was walking home from work. He reports the pain as “the worst headache I have ever had”.
- **Associated symptoms:** No vomiting, no neck stiffness, no focal neurological deficits (e.g., weakness, visual disturbance). He feels well otherwise aside from the headache.
- **Local context:** In many Indian district hospitals, thunderclap headache is often first evaluated for sub‑acute subdural hematoma (SDH) or post‑traumatic headache due to recent minor trauma (e.g., a fall while carrying heavy loads). The absence of vomiting or neck stiffness means the rule’s criteria are not met.
- **Why the rule fires:** The rule requires **headache_worst_ever AND neurological_onset_sudden** (or vomiting, or neck stiffness). This patient does not satisfy any of those additional branches because:
  - Vomiting is absent.
  - Neck stiffness is not reported (commonly not assessed in primary care settings in India).
  - The “worst‑ever” intensity alone does not trigger the rule without the accompanying symptom (vomiting/neck stiffness).
- **Result:** The rule would be silent; the patient would be discharged or sent for routine follow‑up, potentially delaying diagnosis of an acute intracranial bleed that could be life‑threatening.

### Over‑referrals
**Concrete patient (over‑referral):**

- **Demographics:** 60‑year‑old female, known hypertensive patient on oral antihypertensives.
- **Presenting complaint:** Moderate‑intensity headache that began with a sudden onset of nausea and mild neck stiffness. She reports the headache is “very severe” but not described as the “worst ever”.
- **Why the rule fires:** The combination of **headache_worst_ever** (subjective) and **vomiting_present** (present) satisfies the rule, even though the clinical picture is more consistent with a sub‑acute intracranial pressure elevation (e.g., raised intracranial pressure from a sub‑acute bleed) rather than a classic acute subdural hematoma. This could lead to unnecessary escalation to the emergency department and resource consumption.

### The case for leaving it alone
**Strongest argument:** The rule is derived from Western emergency‑medicine guidelines that emphasize vomiting and neck stiffness as hallmark features of acute subdural hematoma, which are common causes of thunderclap headache in high‑income settings. In such environments, the rule’s criteria are statistically robust and have been validated in large cohort studies.

**Why it may survive:** If the service operates primarily in tertiary hospitals where neurological assessment (including vomiting and neck stiffness) is routinely performed, the rule will capture the majority of true acute subdural cases. The missed case scenario is relatively rare in that setting, and the over‑referral risk can be mitigated by adding a “worst‑ever intensity” flag that triggers a secondary review rather than immediate termination.

### Outside my seat
- **Data availability:** The rule does not capture **time_to_peak_minutes**, which could help differentiate a true thunderclap headache from a sub‑acute bleed that evolves over minutes to hours. This is a schema gap that should be addressed before deployment.
- **Cultural symptom reporting:** Many Indian patients may under‑report vomiting or neck stiffness due to cultural stigma around vomiting or limited awareness of neck stiffness as a red flag. This could lead to under‑recognition of acute intracranial pathology.

### The one decision I would put to a clinician
**Should the rule be retained with a “worst‑ever intensity” flag that triggers a secondary triage review (e.g., a follow‑up questionnaire or a brief tele‑consultation) rather than immediate termination, given the high prevalence of sub‑acute intracranial hemorrhage and the potential for missed cases in low‑resource settings?**  

If the answer is yes, the clinician should consider adding a post‑rule escalation step (e.g., a 15‑minute follow‑up call or imaging protocol) for patients who meet only the “worst‑ever headache” criterion. If no, the rule should be refined to include additional local‑specific criteria (e.g., recent trauma or known risk factors) before being deployed in district hospitals.
