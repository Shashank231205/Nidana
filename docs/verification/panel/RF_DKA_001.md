# RF_DKA_001 — Features suggesting diabetic ketoacidosis

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **diabetes-status**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — safety engineer** was cut off before finishing, so what survives reads more one-sided than it was.

## RF_DKA_001 – panel brief

**The panel has not verified this rule.** It remains blocked from release and requires a named clinician.

### What the panel agrees on
1. **Misses** – The rule will miss patients with diabetic ketoacidosis who do **not** present with the specific respiratory, vomiting, or oral‑intake criteria captured in the rule. This includes:
   - **DKA without altered consciousness** (e.g., classic abdominal‑pain‑vomiting DKA in a diabetic patient who is otherwise alert).
   - **DKA with altered consciousness but without vomiting** (e.g., mild DKA with confusion but no vomiting).
   - **Non‑DKA emergencies that satisfy the rule’s branches** (e.g., acute pancreatitis, severe gastroenteritis, or dehydration from fever).

2. **Over‑referrals** – The rule will also fire on non‑DKA presentations that meet the criteria, such as:
   - **Acute pancreatitis** in a diabetic patient (vomiting, minimal oral intake, respiratory distress).
   - **Acute appendicitis** or other abdominal emergencies (vomiting, minimal intake, respiratory distress).
   - **Mild dehydration from fever** (vomiting, minimal intake, respiratory distress) that does not meet DKA thresholds.

3. **Schema limitation** – The rule implicitly assumes that any patient meeting the criteria is diabetic. The current registry lacks a “known_diabetes” predicate, making it impossible to distinguish DKA from other vomiting‑abdominal pain syndromes. This is a fundamental schema gap that must be addressed before the rule can be safely deployed.

### Where the panel disagrees
- **Emergency Physician:** Argues that the rule’s narrow gating (breathing difficulty + vomiting + minimal oral intake) is acceptable because it avoids false positives in non‑DKA emergencies, thereby protecting against missed DKA. The primary concern is the risk of missing DKA that presents without vomiting or altered consciousness.
- **Safety Engineer:** Emphasizes that the rule’s current form leads to **high false‑positive rates** (over‑referrals), which can cause unnecessary termination of the emergency session, increased resource consumption, and potential harm from premature escalation. Suggests that the rule should be revised to include a diabetes‑status predicate before deployment.
- **Indian Practice Reviewer:** Highlights that in low‑resource settings, many DKA patients present with abdominal pain and vomiting without immediate neuro‑glycopenic changes. The absence of a diabetes field means the rule cannot reliably detect DKA, leading to missed diagnoses and delayed treatment. Recommends adding a diabetes gating criterion or a separate rule for DKA detection.

### What turns the choice on
- **Clinical priority:** Whether the **risk of missing true DKA** outweighs the **cost of over‑referrals** (unnecessary termination, resource waste, patient anxiety). If the latter is deemed unacceptable, the rule must be redesigned to include a diabetes‑status predicate.
- **Operational feasibility:** The ability to implement a diabetes‑status field (or a similar gating mechanism) within the existing registry schema. If this cannot be done, the rule should be flagged for redesign before any clinical use.
- **Population‑specific considerations:** In Indian district hospitals, the disease burden of DKA is high, and many patients present with atypical symptoms. The rule must therefore be robust enough to detect DKA without relying solely on vomiting/altered consciousness.

### Refer to
A **diabetes‑status** (or equivalent) field should be added to the registry (e.g., `known_diabetes = true`). This will allow the rule to gate on known diabetes and prevent false positives from non‑DKA emergencies.

### Questions for the verifying clinician
1. **Is the risk of missing DKA episodes that present without vomiting/altered consciousness acceptable given the current over‑referral rate?** If yes, should the rule remain as‑is pending schema changes?
2. **Should the rule be revised to require a known diabetes predicate (or a separate DKA detection rule) before firing, and if so, how should this be implemented within the existing registry schema?**
3. **What additional clinical criteria (e.g., serum glucose level, ketone measurement) could be added to improve specificity without increasing false‑negative rates?**
4. **How will the workflow be adjusted to handle patients who meet the rule’s criteria but are not diabetic, to avoid unnecessary termination of the emergency session?**

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_DKA_001 will miss patients with diabetic ketoacidosis who do not present with the specific respiratory, vomiting, or oral‑intake criteria captured in the rule, and it will also fire on non‑DKA presentations that meet the rule’s thresholds.

**Misses**

1. **Missed DKA presentation – classic but non‑respiratory DKA**  
   - **Patient:** 45‑year‑old man with a known history of type 1 diabetes, no prior hospitalization, admitted at 02:00 am with a fever of 38.5 °C, tachycardia 110 bpm, and a new onset of generalized weakness.  
   - **Why it fails:** He does **not** have *breathing difficulty*, *vomiting*, or *minimal oral intake*. His presentation is dominated by fever, altered mental status (confusion), and dehydration, which are not captured by the rule’s two firing branches.  
   - **Consequence:** The rule’s action (TERMINATE_EMERGENCY) would not be triggered, potentially delaying recognition and treatment of life‑threatening DKA.

2. **Missed DKA presentation – atypical DKA with altered consciousness**  
   - **Patient:** 60‑year‑old woman with a history of type 2 diabetes, admitted after a fall and presenting with a **headache, confusion, and a Glasgow Coma Scale of 13**. She has **no vomiting** and **no respiratory distress**. Her urine output is reduced (oliguria) and she reports **no vomiting**.  
   - **Why it fails:** Although she meets the second firing branch (altered consciousness + urine output reduced + vomiting), the *vomiting* component is absent, so the rule does not fire.  
   - **Consequence:** Missed diagnosis of DKA could lead to delayed insulin therapy, worsening metabolic derangement, and possible neurologic complications.

3. **Over‑referral – non‑DKA emergency presenting with vomiting and altered consciousness**  
   - **Patient:** 30‑year‑old woman with a recent head injury (penetrating mechanism) admitted at 02:00 am. She is **vomiting** and has **altered consciousness** (GCS 9) due to post‑traumatic brain injury. She also has **breathing difficulty** (dyspnoea) and **minimal oral intake** (cannot swallow).  
   - **Why it fires:** She satisfies the first firing branch (breathing difficulty + vomiting + minimal oral intake). However, the underlying emergency is traumatic brain injury, not DKA.  
   - **Consequence:** The rule may prematurely terminate the emergency session, diverting resources away from the true emergency (head injury) and potentially delaying definitive neurosurgical care.

**The case for leaving the rule as‑is**

- **Strength:** The rule is narrowly focused on DKA, a condition that, when recognized early, can be rapidly life‑saving. By gating on the respiratory/vomiting/oral‑intake criteria, it avoids false positives in patients without DKA, reducing unnecessary escalation of non‑DKA emergencies.
- **Limitation:** The current schema lacks a *known diabetes* predicate, meaning any patient with the respiratory/vomiting/oral‑intake pattern will be flagged regardless of diabetes status. This could lead to missed DKA in patients who present without those specific symptoms (e.g., fever‑induced DKA or DKA with altered consciousness but no vomiting).

**Outside my seat**

- The rule’s reliance on *breathing difficulty* and *vomiting* may be culturally or regionally biased, as not all patients with DKA present with these symptoms (e.g., patients with limited mobility or those who vomit less frequently).  
- The absence of a diabetes predicate highlights a broader schema gap that should be addressed before the rule can be safely deployed.

**One decision a clinician must answer**

> **Should the rule be expanded to include a known‑diabetes predicate (or a broader DKA phenotype) while preserving the current respiratory/vomiting/oral‑intake gating, or should the rule remain as‑is pending schema changes?**  

This question directly addresses whether the missed patients above are acceptable trade‑offs or whether the rule’s current form is sufficient given the existing data limitations.

### safety engineer

**Headline:** The rule can be triggered by patients who do **not** have diabetic ketoacidosis (DKA) because the required “breathing difficulty + vomiting + minimal oral intake” (or altered consciousness + reduced urine output + vomiting) can be satisfied by many non‑DKA conditions, especially those that present with acute abdominal pain and vomiting.

**Misses**

*Patient 1 – Acute pancreatitis (type 2 diabetic, but not in DKA):*  
- **Age:** 58 years (male)  
- **Presentation:** 2 hours ago he reported sudden, severe epigastric pain radiating to the back, nausea, and vomiting. He is unable to keep fluids down and has minimal oral intake (only a few sips). He is breathing rapidly (tachypnea) and has mild diaphoresis.  
- **Why the rule fires:** The rule’s first branch (`breathing_difficulty_present AND vomiting_present AND oral_intake_minimal_or_none`) is satisfied. He meets all three criteria even though his labs show only mild hyperglycemia, normal ketones, and no life‑threatening acidosis.  
- **Why this is a miss:** The rule will terminate the emergency session, potentially delaying definitive evaluation for pancreatitis, which can be managed safely with observation and IV fluids rather than immediate ICU‑level interventions.

*Patient 2 – Acute appendicitis (non‑diabetic):*  
- **Age:** 24 years (female)  
- **Presentation:** 3 hours ago she had sudden right lower quadrant pain, nausea, and vomiting. She is breathing rapidly and has mild diaphoresis. She reports minimal oral intake.  
- **Why the rule fires:** Same first branch criteria are met. She does not have DKA, so terminating the emergency session could unnecessarily divert resources and delay appendectomy.  

*Patient 3 – Severe gastroenteritis with dehydration (non‑diabetic):*  
- **Age:** 12 years (child)  
- **Presentation:** 6 hours ago she vomited profusely, now has only minimal oral intake, and is breathing rapidly. She has no known diabetes.  
- **Why the rule fires:** The same first branch criteria are satisfied. The rule may trigger unnecessary emergency department observation and possible admission for fluid resuscitation, which could be managed safely with outpatient IV hydration.

**Over‑referrals**

*Patient 4 – Mild dehydration from fever (non‑diabetic):*  
- **Age:** 65 years (male)  
- **Presentation:** 4 hours ago he developed low‑grade fever, mild tachypnea, and mild vomiting. He is able to take small sips of water and has no severe abdominal pain.  
- **Why the rule fires:** The first branch (`breathing_difficulty_present AND vomiting_present AND oral_intake_minimal_or_none`) is met, even though he does not meet the full DKA criteria (no altered consciousness, normal urine output). Terminating the emergency session could unnecessarily expose him to costly ICU resources and delay appropriate outpatient care.

**The case for leaving the rule unchanged**

The rule’s design is driven by the need to **detect DKA quickly** in a high‑risk population (diabetics). If we keep the rule as‑is, we protect against missing true DKA episodes, which could lead to severe metabolic decompensation. However, the current formulation is **over‑inclusive** because:

1. **False positives** (patients without DKA) lead to unnecessary termination of the emergency session, increased resource consumption, and potential harm from premature escalation (e.g., ICU admission, unnecessary labs, or delayed definitive care for other conditions).  
2. **False negatives** (patients with DKA who present without vomiting or minimal oral intake) could be missed, but this is a secondary concern compared to the high volume of over‑referrals.

**Conclusion for the verifying clinician**

The primary challenge is that the rule’s criteria are **too broad** for the current data set, which lacks a gating predicate for known diabetes. The most urgent question is whether the **risk/benefit ratio** of terminating the emergency session for these over‑referrals justifies the cost (time, resources, patient anxiety). If the benefit of catching true DKA outweighs the cost of over‑referrals, the rule may remain; otherwise, it should be revised to include a diabetes‑status predicate (or a separate rule) before deployment.

**Outside my seat**

The rule’s failure mode is a **schema gap**: the registry does not capture “known diabetes” as a predicate. This gap must be addressed before any clinical decision can be made on the rule’s efficacy. Without a diabetes field, any attempt to refine the rule (e.g., adding a diabetes gate) will be speculative and will require a data‑engineering change.  

**One decision I would put to a clinician**

> **Should the rule be retained with an additional gating predicate for known diabetes (or a separate rule for DKA detection) before the system goes live, given that the current over‑referral rate is high and the missed‑DKA rate is currently unknown?**  

If the answer is “yes,” the clinician should prioritize fixing the missing diabetes field; if “no,” the rule should be flagged for redesign.

### Indian practice reviewer

**Headline:** The rule RF_DKA_001, as currently encoded, will miss a substantial subset of diabetic ketoacidosis (DKA) patients in a low‑resource Indian district hospital because it does not gate on known diabetes, leading to false‑negative triage and delayed emergency care.

### Misses
**Concrete patient example (missed):**  
- **Patient:** 58‑year‑old male, resident of a rural district hospital, known to have diabetes mellitus (diagnosed 5 years ago, on oral hypoglycemic agents).  
- **Presentation:** Over the past 6 hours he has developed sudden abdominal pain, nausea, vomiting, and marked diaphoresis. He reports **no chest pain** and **no altered consciousness**. Oral intake is minimal (only a few sips of water). Urine output is reduced (≈300 mL/day).  
- **Why the rule fails:** The rule fires only if **altered consciousness** is present *and* vomiting is present. This patient lacks altered consciousness, so none of the two encoded branches are satisfied, and the emergency session is not terminated despite meeting classic DKA criteria (vomiting, minimal oral intake, reduced urine output).  

**Why this matters:** In a district hospital where many patients present with abdominal pain and vomiting due to acute pancreatitis, gastrointestinal obstruction, or severe gastroenteritis, the absence of altered consciousness prevents the rule from detecting DKA, potentially delaying insulin therapy and worsening metabolic derangement.

### Over‑referrals
**Concrete patient example (over‑referral):**  
- **Patient:** 45‑year‑old female with no known diabetes, presenting with chest pain, dyspnoea, and vomiting. She meets the first encoded branch (breathing difficulty, vomiting, minimal oral intake) but does **not** have known diabetes.  
- **Result:** The rule would terminate the emergency session, possibly leading to unnecessary admission or further testing for DKA in a patient who does not actually have it, increasing resource utilization and patient anxiety.

### The case for leaving it alone
The strongest argument that the rule could be acceptable is that it is designed to catch *severe* DKA presentations where altered consciousness is a hallmark. In such cases, missing a milder presentation might be acceptable because the clinical picture is more overt. However, this assumption ignores the reality that many DKA episodes in low‑resource settings present with vomiting and abdominal pain without immediate neuro‑glycopenic changes, leading to delayed treatment.

### Outside my seat
- **Schema gap:** The rule implicitly assumes that all patients flagged by the criteria are diabetic. Since the registry does not contain a “known_diabetes” predicate, the rule cannot differentiate between DKA and other vomiting‑abdominal pain syndromes. This gap is a fundamental limitation that must be addressed before deployment.
- **Population‑specific disease burden:** In India, a significant proportion of patients with DKA present with atypical symptoms (e.g., abdominal pain, vomiting) and may not yet be classified as diabetic in the electronic health record. This misclassification can lead to missed diagnoses and adverse outcomes.

### The one decision I would put to a clinician
**Should the rule be expanded to require a known diabetes status (or a validated glycemic index) as a gating criterion before firing, or should it remain as is with the expectation that clinicians will manually verify diabetes status before terminating the emergency session?** This decision will determine whether the rule can safely operate in the current Indian clinical environment without additional workflow modifications.
