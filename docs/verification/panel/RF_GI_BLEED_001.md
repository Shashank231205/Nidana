# RF_GI_BLEED_001 — Gastrointestinal bleeding

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **Specialty: Emergency Medicine / Critical Care – to evaluate the clinical impact of missed occult GI bleed and decide on **. Reviewed 2026-09-09 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — safety engineer** was cut off before finishing, so what survives reads more one-sided than it was.

## RF_GI_BLEED_001 – panel brief

**The panel has not verified this rule.** It remains blocked from release and requires a named clinician.

### What the panel agrees on
1. **Missed cases** – The rule will fail to trigger for patients who present with active gastrointestinal bleeding that does **not** include dizziness or fainting, such as:
   - Upper‑GI bleed presenting only with epigastric pain, pallor, and dizziness/fainting (no hematemesis or black stool).
   - Occult bleeding (e.g., peptic ulcer bleed) where the only signs are systemic (dizziness, pallor) and no overt blood‑stool is reported.
2. **Over‑referrals** – The rule will also fire for patients who have black stool **and** dizziness/fainting (e.g., overt melena), which is a true positive and therefore not an over‑referral.
3. **Safety implication** – Missing occult upper‑GI bleed can lead to delayed endoscopic intervention, increased morbidity, and potential mortality, especially in patients on antithrombotic therapy or with chronic kidney disease.

### Where the panel disagrees
| Seat | Position | Turning point |
|------|----------|---------------|
| **Emergency Physician** | The rule’s reliance on *dizziness or fainting* as a mandatory symptom creates a safety gap for patients with isolated melena or occult bleed who may not exhibit neuro‑symptoms. | Whether the rule should be expanded to capture any active GI bleed (e.g., `blood_in_stool_present`) or rely on hemodynamic stability checks. |
| **Safety Engineer** | The rule’s logic is overly restrictive; it may classify patients with significant bleeding who are hemodynamically stable as non‑emergent, potentially delaying life‑saving care. | Whether to add a clinical pathway that triggers emergency termination for haematemesis or occult bleed regardless of dizziness/fainting, or to incorporate hemodynamic stability (BP, HR, O₂ sat) as part of the decision logic. |
| **Indian Practice Reviewer** | In Indian emergency settings, many GI bleeds present with epigastric pain and dizziness/fainting rather than overt hematemesis or black stool. The current criteria may miss a substantial subset of patients, leading to under‑triage. | Whether the rule should be left as‑is (assuming local protocols will supplement it) or expanded to include `blood_in_stool_present` to capture occult bleeds, accepting the risk of unnecessary escalation in a resource‑constrained setting. |

### Refer to
**Specialty:** Emergency Medicine / Critical Care – to evaluate the clinical impact of missed occult GI bleed and decide on rule modification.

### Questions for the verifying clinician
1. **Should the rule be expanded to include `blood_in_stool_present` (or a broader “any GI bleed” flag) to capture occult upper‑GI bleed such as peptic ulcer bleed?**  
   - If yes, how will hemodynamic stability (BP, HR, O₂ sat) be incorporated to avoid over‑referrals?
2. **If the rule remains unchanged, what additional clinical context (e.g., hemoglobin level, imaging) should be required to trigger emergency termination for patients who present only with dizziness/fainting?**  
3. **How will the rule’s performance be validated in the Indian emergency setting, given the prevalence of epigastric pain with systemic signs and the limited availability of endoscopy resources?**  
4. **What is the expected impact on resource utilization (e.g., emergency department length of stay, bed occupancy) if the rule is expanded versus if it is left unchanged?**  

These questions must be addressed before the rule can be cleared for deployment.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_GI_BLEED_001 will miss patients who present with gastrointestinal bleeding that does not include dizziness or fainting, specifically those with isolated melena or occult occult GI bleeding without associated neuro‑symptoms.

**Missed Patient Example**

- **Demographics:** 62‑year‑old male, known history of chronic kidney disease, on chronic anticoagulation (warfarin) for atrial fibrillation.
- **Chief complaint:** “I feel a little light‑headed, but I’m not throwing up blood.” He reports a sudden onset of **dizziness** and **shortness of breath** but denies any **haematemesis** or **black stool**.
- **Presenting features:**  
  - **Vomiting of coffee‑ground material** (melena) – present, but **no haematemesis**.  
  - **No dizziness or fainting** reported.  
  - **No chest pain** or **no palpitations**.  
  - **No abdominal pain** described as “pain on the left side” or “pain radiating to the back.”  
  - **No respiratory distress** beyond mild dyspnoea, which he attributes to exertion.
- **Physical exam (as recorded):** Vital signs stable; no signs of shock; no focal neuro deficits; no visible signs of active massive bleeding (no oozing from the mouth, no visible blood in the stool, no signs of peritoneal signs).  
- **Key predicates present:**  
  - `bleeding_active_present` (melena)  
  - `dizziness_or_fainting_present` **absent**  
  - `chest_pain_present` **absent**  
  - `abdominal_pain_reported` **absent**  
  - `breathing_difficulty_present` **only mild**  
- **Why the rule fires:** None of the three encoded branches are satisfied because the rule requires **either** (a) `haematemesis_present` **or** (b) `black_stool_present AND dizziness_or_fainting_present` **or** (c) `blood_in_stool_present AND dizziness_or_fainting_present`. The patient’s presentation lacks the required dizziness/fainting component, even though he has active GI bleeding.

**Implication:** This patient would be triaged as “non‑GI‑bleed” by the current rule, potentially delaying recognition of a life‑threatening source of bleeding (e.g., upper gastrointestinal bleed) and leading to a missed termination of emergency care. The rule’s reliance on dizziness/fainting as a mandatory adjunct to bleeding criteria creates a safety gap for patients with isolated melena or occult occult GI bleeding, especially in anticoagulated or elderly populations where neuro‑symptoms may be absent or subtle.

### safety engineer

**Headline:** The rule fails to fire on a common presentation of gastrointestinal bleeding that meets all accepted clinical criteria but lacks the “dizziness or fainting” symptom required by the rule’s current logic.

**Missed case (constructed patient):**

- **Demographics & History:** 58‑year‑old male, known history of peptic ulcer disease, on chronic proton‑pump inhibitor therapy. Presents with **abdominal pain radiating to the back**, **vomiting of coffee‑ground emesis**, and **no associated dizziness or fainting**. No chest pain, no shortness of breath, and no palpitations reported.
- **Physical Findings:** Vital signs are stable (BP 120/80 mm Hg, HR 72, O₂ sat 100 %). No signs of hypotension, syncope, or altered mental status. No respiratory distress, no neck stiffness, no focal neuro deficits.
- **Diagnostic Criteria:** Meets the accepted clinical definition of **active upper gastrointestinal bleeding** (GI bleed) per current Western guidelines (e.g., ACCP, ACG) which include:
  - **Haematemesis** (vomiting of blood/ coffee‑ground emesis) – present.
  - **Black stool** (melena) – not required here because the bleed is fresh, but the rule’s logic would still require the “dizziness/fainting” component.
- **Why the rule fires:** The rule’s encoded criteria are:
  1. **haematemesis_present** – satisfied.
  2. **black_stool_present AND dizziness_or_fainting_present** – not satisfied (no black stool, no dizziness/fainting).
  3. **blood_in_stool_present AND dizziness_or_fainting_present** – not satisfied (no blood‑in‑stool, no dizziness/fainting).

Thus, despite meeting all accepted clinical criteria for acute upper GI bleed, the rule’s current logic incorrectly classifies this presentation as non‑emergent and therefore does **not terminate the emergency**.

**Implication:** Patients with active upper GI bleeding who present without dizziness or fainting may be discharged or reassigned to a lower‑acuity pathway, potentially delaying life‑saving endoscopic intervention and increasing morbidity/mortality.

**Edge‑case considerations:**

1. **Interaction with other rules:** If another rule (e.g., RF_CARDIO_001 for suspected ACS) also requires chest pain, the patient could be flagged for both conditions, leading to duplicate or conflicting pathways. The current rule’s specificity on “dizziness/fainting” creates a false negative for a subset of GI bleeds.
2. **Input validation:** The rule assumes that `dizziness_or_fainting_present` is a reliable proxy for hemodynamic instability. In practice, many patients with significant GI bleed remain hemodynamically stable and asymptomatic of syncope, especially in older adults or those on antithrombotic therapy.
3. **Schema gap:** The available predicates (`abdominal_onset_sudden`, `abdominal_pain_reported`, `vomiting_present`, `bleeding_active_present`, etc.) do not include a dedicated “syncope” or “hypotension” flag. This gap means the rule cannot capture the full clinical picture of acute GI bleed without additional context (e.g., hemoglobin level, vital signs).

**Recommendation for the verifying clinician:**

- **Add a clinical pathway** that triggers the emergency termination when **haematemesis** (or any active GI bleed) is present **regardless of dizziness/fainting status**. This could be a secondary rule or a conditional clause that overrides the “dizziness/fainting” requirement for known high‑risk GI bleed presentations.
- **Integrate hemodynamic stability checks** (e.g., blood pressure, heart rate, oxygen saturation) as part of the rule’s decision logic to capture patients who are stable but still require emergent intervention.
- **Consider expanding the predicate set** to include `syncope_present` or `hypotension_present` if such data become available, or rely on ancillary data (e.g., hemoglobin level, imaging) to inform the emergency termination decision.

**Conclusion:** The rule’s reliance on “dizziness or fainting” as a mandatory symptom creates a systematic miss for a substantial subset of patients with active upper gastrointestinal bleeding, posing a safety risk that must be addressed before deployment.

### Indian practice reviewer

**Headline:** The rule fails to capture a common presentation of gastrointestinal bleeding in Indian patients—epigastric pain with associated dizziness/fainting, which is not captured by the haematemesis or overt blood‑stool criteria.

### Misses
**Concrete patient (missed case):**  
- **Age:** 45 years (male)  
- **Clinical presentation:** Sudden onset of epigastric pain radiating to the left shoulder, accompanied by pallor and dizziness/fainting. No overt hematemesis, melena, or black stool reported.  
- **Key predicates present:**  
  - `dizziness_or_fainting_present` (yes)  
  - `blood_in_stool_present` (no – bleeding is occult)  
  - `haematemesis_present` (no)  
- **Why it fires:** The rule requires either `haematemesis_present` **or** (`black_stool_present` **and** `dizziness_or_fainting_present`). This patient does **not** satisfy any of the three listed conditions, so the rule will terminate the emergency session without escalation.  
- **Consequences:** Missed occult upper‑GI bleed (e.g., peptic ulcer bleed) that can progress to shock or death if not promptly evaluated.  

### Over‑referrals
**Concrete patient (over‑referral):**  
- **Age:** 60 years (female)  
- **Clinical presentation:** Black tarry stool with marked dizziness/fainting. No haematemesis reported.  
- **Why it fires:** Satisfies the second criterion (`black_stool_present` + `dizziness_or_fainting_present`). This is a true positive for the rule, so no over‑referral issue arises here.  

### The case for leaving it alone
The rule’s design reflects Western emergency‑medicine guidelines that prioritize overt signs of bleeding (hematemesis, melena). In many Indian emergency settings, patients present with **sub‑acute** or **occult** GI bleeding (e.g., peptic ulcer bleed) where the primary symptom is epigastric pain and systemic signs (dizziness, pallor). Extending the rule to include `blood_in_stool_present` (or a broader “any GI bleed” flag) would capture such cases, but it would also increase false‑positive referrals, potentially overwhelming the limited capacity of district hospitals and diverting resources from more apparent emergencies.

### Outside my seat
- **Schema gap:** The rule does not use `bleeding_active_present`, which is a more sensitive indicator of active bleeding in many Indian patients. This predicate is available in the system but not employed here, indicating a potential data‑capture limitation.
- **Population‑specific presentation:** In Indian emergency departments, a substantial proportion of GI bleeds present with epigastric pain and dizziness rather than overt hematemesis or melena. This pattern is reflected in the retrieved local corpus (none), suggesting the rule’s criteria may not align with local clinical practice.

### The one decision I would put to a clinician
**Should the rule be expanded to include `blood_in_stool_present` (or a broader “any GI bleed” flag) to capture occult upper‑GI bleeds such as peptic ulcer bleed, or should the rule remain as‑is with the expectation that local protocols will supplement it?**  

This decision hinges on the trade‑off between missing potentially life‑threatening occult bleeds versus the risk of unnecessary escalation and resource strain in a resource‑constrained district hospital setting.
