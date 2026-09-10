# RF_MENINGISM_001 — Possible meningitis

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **clinician specializing in infectious diseases and emergency medicine**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — safety engineer** was cut off before finishing, so what survives reads more one-sided than it was.

## RF_MENINGISM_001 – panel brief

**The panel has not verified this rule.** It remains blocked from release and requires a named clinician.

### What the panel agrees on
1. **Missed cases** – The rule will miss patients who present with severe headache, neck stiffness, and altered consciousness but have no fever. Such patients (e.g., a 45‑year‑old male with bacterial meningitis) will not trigger the rule because fever is a mandatory component.  
2. **Potential over‑referrals** – Patients who have fever, neck stiffness, and a mild rash (even if the rash is not severe) will be escalated to emergency care, potentially leading to unnecessary neurosurgical intervention and resource waste.  
3. **Clinical context matters** – In resource‑limited district hospitals in India, fever may be absent in a substantial proportion of bacterial meningitis cases, making the rule’s reliance on fever a significant limitation.

### Where the panel disagrees
- **Emergency Physician:** Argues that the rule should be broadened to include severe neck stiffness alone (or combined with altered consciousness) to capture missed cases, even if fever is absent.  
- **Safety Engineer:** Proposes that the rule’s label should be expanded to “suspected meningitis” and that the rule should not be triggered solely on fever, as this reduces false‑negative risk.  
- **Indian Practice Reviewer:** Suggests that the rule should be relaxed to allow detection without fever, acknowledging that the current design may miss a large subset of meningitis cases in this population.  

**What turns on the choice:**  
- **If the clinician decides to keep fever as a mandatory criterion**, the justification must demonstrate that the high prevalence of fever‑positive presentations outweighs the risk of missing fever‑negative cases, and that the rule’s simplicity and safety net for fever‑positive patients are sufficient.  
- **If the clinician decides to relax the fever requirement**, the justification must show that the reduction in over‑referrals (and associated cost and patient anxiety) does not compromise the rule’s ability to identify life‑threatening meningitis when fever is present.

### Refer to
A clinician specializing in infectious diseases and emergency medicine should review the rule to determine whether the trade‑off between missed cases and over‑referrals is acceptable for the local clinical environment.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_MENINGISM_001 will miss patients with meningitis who present primarily with atypical or non‑classic signs (e.g., neck stiffness without fever, or altered consciousness without rash) and who do not meet the three‑branch criteria encoded in the rule.

**Missed Patient (Concrete Example):**

- **Demographics:** 45‑year‑old male, age recorded = 45 years, immunosuppressed (chronic steroid use), no known diabetes or hypertension.
- **Chief Complaint:** Severe headache, photophobia, and neck stiffness reported by the patient and observed by staff. No fever reported (temperature = 36.5 °C). No rash, altered consciousness, or focal neurological deficits noted.
- **Presenting Features:** 
  - Neck stiffness present (patient cannot flex neck forward without pain).
  - Photophobia present (patient reports “eyes hurt in bright light”).
  - No fever reported; temperature measured at 36.5 °C.
  - No rash, altered mental status, seizures, or focal deficits.
- **Associated Symptoms:** Mild nausea/vomiting, but no respiratory distress, dyspnea, or chest pain. No recent head injury, recent immunization, or known meningitis risk factors (e.g., recent intravenous drug use, neutropenia).
- **Exclusion Criteria:** 
  - No chest pain, no recent trauma, no recent intravenous drug use, no known immunosuppression beyond chronic steroids (which alone does not preclude meningitis but is a risk factor).
  - No abdominal or gastrointestinal signs (no vomiting, diarrhea, or abdominal tenderness).
  - No red‑flag features such as seizures, severe neck pain, or rapid deterioration.
- **Why This Patient Fails the Rule:** The rule requires **either** (a) neck stiffness + fever, **or** (b) neck stiffness + photophobia, **or** (c) fever + rash + altered consciousness. This patient only satisfies the second branch (neck stiffness + photophobia) and therefore does **not** meet any of the three encoded conditions, leading to a false‑negative triage.

**Implication:** Such a patient would be discharged or not escalated to the emergency department for meningitis work‑up, potentially delaying life‑saving treatment and increasing morbidity or mortality.

**Key Takeaway for Clinicians:** The current rule’s reliance on fever and rash as mandatory components may miss a substantial subset of meningitis cases, especially in immunocompromised patients or those with atypical presentations. Consider expanding criteria to include severe neck stiffness alone, or incorporate additional clinical red flags (e.g., altered consciousness, seizures) to capture missed cases.

### safety engineer

**Headline:** The rule can miss a presentation of bacterial meningitis that meets the encoded criteria but is not captured by the current label or clinical narrative.

**Missed patient (example):**  
- **Age:** 12‑year‑old child (outside the “adult” label).  
- **Presentation:** Sudden onset of fever (≥38 °C), neck stiffness, photophobia, and a new onset of **altered consciousness** (irritability, difficulty arousing).  
- **Key features:** No chest pain, no rash, no abdominal pain, no vomiting, no recent head injury, and no known immunosuppression.  
- **Why it fails:** The rule’s label “Possible meningitis” and the narrative focus on fever + neck stiffness (or fever + rash + altered consciousness) do not explicitly capture the classic triad of fever, neck stiffness, and altered mental status. A child presenting solely with these three signs will not trigger the rule because the label and the clinician‑reviewed narrative prioritize other manifestations (e.g., rash) that are not present here.  

**Edge‑case behavior:**  
- **Rule interaction:** If another rule (e.g., RF_AORTIC_001) also fires on “fever + neck stiffness,” the order of rule evaluation could cause the system to terminate the session before the meningitis rule is fully evaluated, potentially leading to premature discharge.  
- **Input errors:** If any predicate is missing (e.g., `neck_stiffness_present` is not recorded), the rule will not fire even though the clinical picture is clearly meningitis. This highlights the importance of complete data capture for each predicate.  

**Safety implication:**  
- **False‑negative risk:** Missing a child with bacterial meningitis can lead to delayed treatment, increasing morbidity and mortality.  
- **Mitigation:** Expand the rule’s label to include “suspected meningitis” and explicitly encode the triad (fever, neck stiffness, altered consciousness) as a primary detection pathway, regardless of rash or chest pain.  

**Next steps for verification:**  
1. Confirm whether the rule’s label should be broadened to capture the full clinical spectrum of bacterial meningitis.  
2. Review the data‑capture fields to ensure `neck_stiffness_present`, `fever_reported_present`, and `altered_consciousness_present` are mandatory and correctly mapped to the rule’s predicates.  
3. Evaluate rule ordering with other triage rules to prevent premature termination when multiple conditions are present.  

**Conclusion:** The current rule design, based solely on the encoded criteria, risks missing children (or any patients) who present with fever, neck stiffness, and altered consciousness—key hallmarks of bacterial meningitis—unless additional clinical context is incorporated into the label or rule phrasing.

### Indian practice reviewer

**Headline:** The rule RF_MENINGISM_001, as written for a Western emergency setting, will miss a substantial subset of meningitis patients in a resource‑limited district hospital in India because it relies on fever, neck stiffness, and a rash—features that are not universally present in bacterial meningitis here.

### Misses
**Concrete patient (missed case):**  
- **Demographics:** 45‑year‑old male, resident of a rural district hospital in South India.  
- **Clinical presentation:** Presents with severe headache, neck stiffness, and **no fever** (core temperature 36.5 °C). He reports a **persistent photophobia** and **altered consciousness** (GCS = 13).  
- **Why the rule fails:** The rule requires **fever_reported_present** for the first two branches (neck_stiffness_present + fever_reported_present) and (neck_stiffness_present + photophobia_present). In this patient, fever is absent, so none of the three criteria are satisfied, and the rule will not trigger the **TERMINATE_EMERGENCY** action.  
- **Consequences:** Delayed recognition and treatment of bacterial meningitis can lead to irreversible neurologic damage or death, especially in a setting where rapid imaging (CT head) and laboratory confirmation (CSF analysis) may be delayed due to limited resources.

### Over‑referrals (potential false positives)
**Concrete patient (over‑referral):**  
- **Demographics:** 60‑year‑old female, admitted with fever, neck stiffness, and a **mild rash** (petechial) that is not severe enough to meet the “altered consciousness” threshold.  
- **Why the rule fires:** The presence of fever and neck stiffness alone satisfies the first branch (neck_stiffness_present + fever_reported_present). The mild rash, even if present, may be interpreted as a “rash_present” flag in the local data set, causing the rule to terminate emergency care.  
- **Consequences:** This patient may not require emergent neurosurgical intervention (e.g., CSF drainage) and could be managed safely with antibiotics and supportive care, leading to unnecessary escalation of care, increased cost, and potential patient anxiety.

### The case for leaving the rule unchanged
**Strengths of the current rule:**  
1. **Simplicity:** The rule uses three well‑established clinical signs (fever, neck stiffness, rash) that are relatively easy to assess even in low‑resource settings where rapid labs are unavailable.  
2. **Safety net:** By terminating emergency care when any of these signs are present, it ensures that patients who truly have bacterial meningitis receive prompt neurosurgical evaluation, which is critical for survival.  

**Limitations that remain:**  
- **High false‑positive rate:** Many patients with viral or aseptic meningitis (common in tropical regions) present without fever, yet still have neck stiffness and photophobia, causing unnecessary emergency department stays and resource strain.  
- **Missed presentation:** Patients like the 45‑year‑old male with severe headache, neck stiffness, and altered consciousness but no fever will be missed, potentially leading to fatal outcomes.  

**Conclusion:** The rule’s reliance on fever as a mandatory criterion is a major flaw in an Indian district hospital context where fever may be absent in a significant proportion of bacterial meningitis cases. The benefit of catching all fever‑positive presentations must be weighed against the high cost of over‑referrals and the risk of missing disease.

### Outside my seat
- **Supply‑chain considerations:** The rule does not account for limited availability of rapid diagnostic tests (e.g., PCR for *Neisseria meningitidis*), which may delay definitive diagnosis.  
- **Cultural presentation:** Some patients may describe “headache” or “neck stiffness” differently, potentially leading to under‑recognition of the signs.  

### The one decision I would put to a clinician
**Should the rule be modified to include a non‑fever‑dependent branch (e.g., neck stiffness + altered consciousness) to capture patients like the 45‑year‑old male, while retaining fever as an additional safety net to reduce false positives?**  

If the clinician decides to keep the fever requirement, the justification must address the high prevalence of fever‑negative bacterial meningitis in this population and the associated mortality risk. If the clinician decides to relax the fever requirement, the justification must demonstrate that the resulting reduction in over‑referrals does not compromise patient safety.
