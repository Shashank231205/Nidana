# RF_TEMPORAL_ARTERITIS_001 — Features suggesting temporal arteritis

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **emergency physician**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** proposed unsourced thresholds (`> 50 years`).

**Rule ID:** RF_TEMPORAL_ARTERITIS_001  

**Headline:** The rule misses patients with classic temporal‑arteritis presentation who are under 50 years old and lack scalp tenderness, thereby failing to trigger escalation despite meeting all diagnostic criteria.

### Misses  

**Patient example (58‑year‑old woman):**  
- **Demographics:** 58‑year‑old woman, known family history of giant‑cell arteritis, but no personal history.  
- **Clinical presentation:** Sudden severe headache with visual disturbance (visual field loss, “tunnel vision”), jaw claudication (pain on chewing), mild neck stiffness. No scalp tenderness reported.  
- **Other findings:** Fever, mild tachycardia, elevated ESR/CRP (common in GCA). No chest pain, dyspnea, or other abdominal/GI symptoms.  
- **Why the rule fires:** None of the three criteria are satisfied:  
  1. **Scalp tenderness present AND age > 50** – absent (age = 58, but no scalp tenderness).  
  2. **Jaw claudication present AND age > 50** – jaw claudication is present, but age is not > 50.  
  3. **Headache + visual disturbance + scalp tenderness** – scalp tenderness is absent.  
- **Result:** The rule remains inactive, and the patient’s presentation, which is life‑threatening (risk of vision loss and cranial ischemia), would not be escalated to a higher band or referred for urgent imaging/IV steroids.

### Over‑referrals  

**Patient example (elderly man with unrelated pain):**  
- **Demographics:** 72‑year‑old man with known hypertension and diabetes.  
- **Clinical presentation:** Chronic low‑grade back pain, no jaw claudication, no visual symptoms, no scalp tenderness.  
- **Why the rule fires:** He meets **all** criteria (age > 50, scalp tenderness present, headache + visual disturbance). Even though he does not have temporal arteritis, the rule would still trigger escalation, potentially leading to unnecessary imaging, labs, and possibly unnecessary steroid therapy, which incurs cost and risk of side effects.

### The case for leaving it alone  

**Strengths of the current rule:**  
- **Simplicity:** Only three explicit, clinically validated triggers are required, reducing false‑positive escalations.  
- **Safety net:** Escalation to a higher band triggers urgent imaging (e.g., temporal artery duplex) and immediate treatment, aligning with guideline‑driven care pathways.  
- **Evidence base:** Temporal arteritis is most strongly associated with scalp tenderness and age > 50; the rule mirrors the primary diagnostic criteria used in major rheumatology guidelines.  

**Potential weaknesses:**  
- **Clinical nuance:** Temporal arteritis can present without scalp tenderness, especially in patients with jaw claudication and visual symptoms (e.g., anterior ischemic optic neuropathy).  
- **Resource impact:** Missing a case may lead to irreversible vision loss, outweighing the cost of occasional unnecessary escalations.  
- **Data limitation:** The absence of retrieved corpus passages suggests the rule may be based on a narrower clinical narrative that does not reflect real‑world presentations.

**Decision point for a clinician:**  
Whether to retain the rule hinges on balancing the risk of missing a life‑threatening presentation (visual loss) against the cost of over‑referral to imaging and treatment that may not be indicated. If the clinical pathway can be augmented to include “jaw claudication + visual disturbance” as a trigger (or a separate rule flagging visual loss), the rule would capture the missed case without inflating false positives.

### Outside my seat  

- **Schema gap:** The system lacks a predicate for “visual loss” (visual_loss_present) and “jaw claudication” as a distinct symptom beyond “jaw pain.” Adding these predicates would allow the rule to capture the missed temporal arteritis presentation without relying on scalp tenderness.  
- **Potential integration with other rules:** The rule should be reviewed alongside any existing rule for “acute visual loss” or “jaw claudication” to avoid redundant escalations.

### The one decision I would put to a clinician  

**Should the rule be expanded to include “jaw claudication + visual disturbance (visual_loss_present) + age > 50” as a trigger, thereby capturing patients like the missed case above, while maintaining the current escalation action for confirmed scalp‑tenderness cases?**  

If yes, the clinician should consider adding a fourth condition (jaw_claudication_present AND visual_loss_present AND age_over_50) and possibly a separate rule for “visual loss” to prevent over‑referral. If no, the clinician should document the risk of missed temporal arteritis and consider alternative clinical triggers (e.g., high CRP, polymyalgia rheumatica symptoms) that can be incorporated into a broader triage algorithm.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_TEMPORAL_ARTERITIS_001 misses patients with classic temporal‑arteritis presentation who are **under 50 years old** and lack scalp tenderness, thereby failing to trigger escalation despite meeting all diagnostic criteria.

### Misses
**Patient example (58‑year‑old woman):**  
- **Demographics:** 58‑year‑old woman, known history of giant‑cell arteritis (GCA) in a first‑degree relative, but no personal history of disease.  
- **Clinical presentation:** Sudden onset of severe headache with visual disturbance (visual field loss, “tunnel vision”), jaw claudication (pain on chewing), and mild neck stiffness. No scalp tenderness reported.  
- **Other findings:** Fever, mild tachycardia, and elevated ESR/CRP (common in GCA). No chest pain, no dyspnea, and no other abdominal or GI symptoms.  
- **Why the rule fires:** None of the three criteria are satisfied:  
  1. **Scalp tenderness present AND age > 50** – absent (age = 58, but no scalp tenderness).  
  2. **Jaw claudication present AND age > 50** – jaw claudication is present, but age is not > 50.  
  3. **Headache + visual disturbance + scalp tenderness** – scalp tenderness is absent.  
- **Result:** The rule remains inactive, and the patient’s presentation, which is life‑threatening (risk of vision loss and cranial ischemia), would not be escalated to a higher band or referred for urgent imaging/IV steroids.

### Over‑referrals
**Patient example (elderly man with unrelated pain):**  
- **Demographics:** 72‑year‑old man with known hypertension and diabetes.  
- **Clinical presentation:** Chronic low‑grade back pain, no jaw claudication, no visual symptoms, no scalp tenderness.  
- **Why the rule fires:** He meets **all** criteria (age > 50, scalp tenderness present, and headache + visual disturbance). Even though he does **not** have temporal arteritis, the rule would still trigger escalation, potentially leading to unnecessary imaging, labs, and possibly unnecessary steroid therapy, which incurs cost and risk of side effects.

### The case for leaving it alone
The rule is designed to capture **classic temporal‑arteritis features** that are strongly associated with **elderly patients** (≥ 50 years) who often present with **scalp tenderness**—a hallmark that is less common in younger patients.  
- **Argument:** Temporal arteritis is a medical emergency; missing it in patients > 50 years could lead to irreversible vision loss. The current criteria are therefore appropriate for the primary population they target (older adults).  
- **Counter‑argument:** The rule’s age threshold (≥ 50) excludes a significant subset of patients who can still develop GCA, especially those with a strong family history or elevated inflammatory markers, as demonstrated by the 58‑year‑old woman example. If the rule were left unchanged, many high‑risk patients could be missed, potentially leading to permanent ocular damage.

### Outside my seat
- **Schema gap:** The rule does not incorporate **age < 50** as a separate branch, which could be justified by the epidemiology of GCA in younger patients (e.g., autoimmune disease flares).  
- **Predictive gap:** The rule lacks a **visual‑field‑loss** or **ocular‑symptom** predicate, which are essential for detecting GCA in patients without scalp tenderness. Adding a predicate for **visual disturbance** (e.g., “visual_loss_present”) would allow the rule to fire for younger patients who present with jaw claudication and visual symptoms.

### The one decision I would put to a clinician
**Should the rule be expanded to include a separate branch for patients **≥ 40 years** who present with **jaw claudication** and **visual disturbance** (without requiring scalp tenderness), thereby ensuring that younger patients with temporal arteritis are not missed?**  

If the clinician decides to add such a branch, the rule’s escalation logic should be revisited to avoid over‑referral of unrelated elderly patients. If the clinician decides to keep the rule as‑is, the risk of missing GCA in younger patients must be documented and mitigated through additional clinical context (e.g., family history, elevated ESR/CRP).

### safety engineer

**Headline:** The rule fails to fire on a presentation that meets all clinical criteria for temporal arteritis but does not include “scalp tenderness,” thereby missing a diagnosis that can be rapidly life‑threatening.

### Misses
**Patient scenario (missed case):**  
- **Age:** 62 years (age_over_50 is true).  
- **Sex:** Female.  
- **Chief complaint:** Sudden severe headache with visual disturbance (visual loss) and jaw claudication (limited opening of the mouth).  
- **No scalp tenderness** reported (scalp_tenderness_present is false).  
- **Other relevant findings:**  
  - Fever ≥ 38 °C (fever_reported_present).  
  - New‑onset visual loss (visual_loss_present).  
  - Neck stiffness (neck_stiffness_present).  
  - No chest pain (chest_pain_present is false).  
- **Why the rule does not fire:** The rule requires either  
  1. **scalp_tenderness_present AND age_over_50**, or  
  2. **jaw_claudication_present AND age_over_50**, or  
  3. **headache_visual_disturbance AND scalp_tenderness_present**.  
  In this patient, only **jaw_claudication_present** and **age_over_50** are true; the required **scalp_tenderness_present** is absent, so none of the three conditions are satisfied.

**Clinical implication:** Temporal arteritis can progress to irreversible vision loss and mediastinal involvement within days to weeks. Missing the diagnosis delays critical high‑dose glucocorticoid therapy, increasing morbidity and mortality.

### Over‑referrals
**Patient scenario (over‑referral):**  
- **Age:** 45 years (age_over_50 is false).  
- **Sex:** Male.  
- **Chief complaint:** Epigastric pain radiating to the jaw, dyspnea, and mild chest pain (chest_pain_present is true).  
- **Why the rule fires:** The rule’s first condition (scalp_tenderness_present AND age_over_50) is not met, but the second condition (jaw_claudication_present AND age_over_50) is not present either. However, the rule still fires because the system may infer “jaw claudication” from vague chest‑pain descriptors in some datasets, leading to unnecessary escalation. This illustrates a potential edge case where the rule could be triggered by mis‑mapped symptoms, increasing resource use without clinical benefit.

### The case for leaving it alone
**Strengths of the current rule:**  
- **Simplicity:** Only three explicit, clinically validated triggers are required, reducing false‑positive escalations.  
- **Safety net:** Escalation to a higher band triggers urgent imaging (e.g., temporal artery duplex) and immediate treatment, which aligns with guideline‑driven care pathways.  
- **Evidence base:** Temporal arteritis is most strongly associated with scalp tenderness and age > 50; the rule mirrors the primary diagnostic criteria used in major rheumatology guidelines.

**Potential weaknesses:**  
- **Clinical nuance:** Temporal arteritis can present without scalp tenderness, especially in patients with jaw claudication and visual symptoms (e.g., anterior ischemic optic neuropathy).  
- **Resource impact:** Missing a case may lead to irreversible vision loss, outweighing the cost of occasional unnecessary escalations.  
- **Data limitation:** The absence of retrieved corpus passages suggests the rule may be based on a narrower clinical narrative that does not reflect real‑world presentations.

**Decision point for a clinician:**  
Whether to retain the rule hinges on balancing the risk of missing a life‑threatening presentation (visual loss) against the cost of over‑referral to imaging and treatment that may not be indicated. If the clinical pathway can be augmented to include “jaw claudication + visual disturbance” as a trigger (or a separate rule flagging visual loss), the rule would capture the missed case without inflating false positives.

### Outside my seat
- **Schema gap:** The system lacks a predicate for “visual loss” (visual_loss_present) and “jaw claudication” as a distinct symptom beyond “jaw pain.” Adding these predicates would allow the rule to capture the missed temporal arteritis presentation without relying on scalp tenderness.
- **Potential integration with other rules:** The rule should be reviewed alongside any existing rule for “acute visual loss” or “jaw claudication” to avoid redundant escalations.

### The one decision I would put to a clinician
**Should the rule be expanded to include “jaw claudication + visual disturbance (visual loss) + age > 50” as a trigger, thereby capturing patients like the missed case above, while maintaining the current escalation action for confirmed scalp‑tenderness cases?**  

If yes, the clinician should consider adding a fourth condition (jaw_claudication_present AND visual_loss_present AND age_over_50) and possibly a separate rule for “visual loss” to prevent over‑referral. If no, the clinician should document the risk of missed temporal arteritis and consider alternative clinical triggers (e.g., high CRP, polymyalgia rheumatica symptoms) that can be incorporated into a broader triage algorithm.

### Indian practice reviewer

**Rule ID:** RF_TEMPORAL_ARTERITIS_001  

**Label:** Features suggesting temporal arteritis  

**Action:** ESCALATE_BAND  

---

### Misses  

**Patient 1 – Missed Case**

- **Age:** 68 years (well above the age > 50 threshold)  
- **Presentation:** 58‑year‑old woman (hypothetical for illustration) with a new, severe headache that feels like a “tight band” around the forehead. She also reports **scalp tenderness** on palpation of the temporal region.  
- **Additional Features:** No jaw claudication, no jaw pain, no visual disturbances, no jaw swelling, and no other systemic signs (fever, weight loss, or new‑onset rash).  
- **Why it fails the rule:** The rule requires **scalp_tenderness_present AND age_over_50**. While scalp tenderness is present, the rule does **not** capture the classic headache‑only presentation that is common in Indian patients with temporal arteritis. Consequently, this patient would not be escalated despite meeting the age criterion.

**Patient 2 – Missed Case (Alternative Presentation)**  

- **Age:** 52 years (meets age > 50)  
- **Presentation:** 52‑year‑old man with a **new onset jaw claudication** (difficulty chewing hard foods) and **jaw tenderness**. He reports **headache** but without visual disturbances or scalp tenderness.  
- **Why it fails the rule:** The rule’s first branch (`scalp_tenderness_present AND age_over_50`) is not triggered because scalp tenderness is absent. The second branch (`jaw_claudication_present AND age_over_50`) is also not triggered because the rule demands **both** jaw claudication **and** scalp tenderness, which are not present together. Thus, a patient who fulfills the jaw‑claudication criterion alone would be missed.

**Patient 3 – Missed Case (Atypical Presentation)**  

- **Age:** 45 years (still within the age range, but the rule’s age filter is overly restrictive)  
- **Presentation:** 45‑year‑old woman with **headache**, **visual disturbance** (blurred vision), and **scalp tenderness**. She reports **no jaw claudication** and **no jaw pain**.  
- **Why it fails the rule:** Although she meets the third branch (`headache_visual_disturbance AND scalp_tenderness_present`), the rule’s age filter (`age_over_50`) excludes her, even though temporal arteritis can present in younger adults, especially in Indian populations where the disease may manifest earlier.

---

### Over‑referrals (Potential Cost)

**Patient Over‑referral**

- **Age:** 60 years  
- **Presentation:** 60‑year‑old man with **chest pain** (presumed angina) and **scalp tenderness**. He also reports **jaw claudication**.  
- **Why it fires the rule:** He satisfies **all three** rule criteria (scalp tenderness + age > 50, jaw claudication + age > 50, headache + visual disturbance + scalp tenderness).  
- **Resulting Action:** The rule escalates him to a higher band, potentially leading to unnecessary advanced imaging or hospital admission for coronary evaluation, which may not be indicated solely based on temporal arteritis features.

---

### The Case for Leaving It Alone

The rule is derived from Western clinical guidelines that emphasize **jaw claudication** as a hallmark feature of temporal arteritis. In many Western settings, jaw claudication is a strong predictor of the disease, and the age filter (`> 50`) aligns with epidemiology where the disease predominantly affects older adults.

**Strengths:**

1. **Guideline Alignment:** The rule follows established Western criteria that have been validated in high‑income settings where the disease prevalence is higher and the clinical presentation is more stereotypical.  
2. **Safety Net:** Escalation to a higher band ensures that patients who truly have temporal arteritis receive prompt treatment, reducing the risk of irreversible complications (e.g., ischemic stroke).  

**Limitations in Indian Context:**

1. **Disease Prevalence & Presentation:** Temporal arteritis is under‑diagnosed in India, where many patients present with **headache and scalp tenderness** without jaw involvement.  
2. **Age Distribution:** The disease can manifest in younger adults (even < 50), contrary to the age filter, potentially missing cases that would otherwise be caught.  
3. **Resource Constraints:** Escalating every patient with scalp tenderness may divert limited diagnostic resources (e.g., CRP testing, temporal artery biopsy) from other urgent conditions common in district hospitals (e.g., acute bacterial meningitis, severe sepsis).  

**Conclusion:** The rule’s design, while robust in Western epidemiology, risks **under‑recognition** of the disease in Indian patients who present with headache and scalp tenderness alone. This could lead to delayed treatment and increased morbidity. Adjusting the rule to include **headache + visual disturbance + scalp tenderness** (without the mandatory jaw claudication) would better capture the Indian disease phenotype while preserving the escalation for patients who truly meet the broader Western criteria.

---

### Outside My Seat

- **Schema Gap:** The rule does not utilize the **visual_disturbance_present** predicate, which is part of the classic temporal arteritis presentation in many Western guidelines. Including this predicate could improve sensitivity without inflating false‑positive escalation.  
- **Population‑Specific Presentation:** Temporal arteritis in Indian patients often presents with **headache and scalp tenderness** as the primary symptoms, sometimes without jaw involvement. This nuance is not captured by the current criteria.

---

### The One Decision I Would Put to a Clinician

**Should the rule be modified to include the combination of **headache** and **visual disturbance** (plus scalp tenderness) as an alternative branch, thereby reducing the age‑over‑50 restriction to capture younger patients who still meet the core temporal arteritis phenotype?**  

If yes, the clinician should consider:

1. **Evidence Base:** Review recent Indian epidemiological studies on temporal arteritis presentation to confirm that the proposed alternative branch improves detection without increasing false‑positives.  
2. **Resource Impact:** Assess whether the added sensitivity justifies the potential increase in referrals to higher‑band services, especially in resource‑limited district hospitals.  
3. **Safety:** Ensure that the escalation to a higher band is justified by a validated diagnostic pathway (e.g., CRP level, temporal artery biopsy) to avoid unnecessary imaging or hospitalization.  

If no, the clinician should maintain the current rule but implement **clinical context checks** (e.g., asking about jaw involvement) to avoid misclassification of patients who meet the core presentation but lack jaw claudication.
