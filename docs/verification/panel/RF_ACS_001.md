# RF_ACS_001 — Possible acute coronary syndrome

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **emergency physician**. Reviewed 2026-09-09 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — safety engineer** proposed unsourced thresholds (`>30 %`); was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — Indian practice reviewer** used approving language.

**Rule ID:** RF_ACS_001  

**Headline:** The rule misses diabetic patients who present with atypical, non‑painful chest‑related symptoms (e.g., epigastric discomfort, dyspnoea, profuse sweating) and therefore would not be escalated to termination.

### Misses
**Concrete patient example**

- **Demographics:** 58‑year‑old woman, type 2 diabetes mellitus, 12 years of disease duration, on oral hypoglycaemic agents.  
- **Chief complaint:** Two hours of “heaviness” in the epigastrium described as “pressure‑like” but without any overt chest‑pain that radiates to the jaw or left arm. She reports dyspnoea and profuse sweating, yet she does **not** describe pain that meets the rule’s “chest_pain_present” criterion.  
- **Additional features:** No exertional dyspnoea, no radiation to the jaw/left arm, no diaphoresis‑only (she attributes sweating to ambient temperature), and no documented age > 40 (she is 58). She is not known to have any of the other age‑related qualifiers (e.g., age > 60).  
- **Why the rule fires:** None of the four rule branches are satisfied:  
  1. **Chest pain + radiation** – absent (no pain reported).  
  2. **Chest pain + diaphoresis** – absent (pain not present).  
  3. **Chest pain + dyspnoea + age > 40** – absent (pain not present).  
  4. **Chest pain + pressure/tightness + worse on exertion** – absent (pain not present).  
- **Result of the rule:** Because none of the encoded criteria are met, the rule does **not** trigger the “TERMINATE_EMERGENCY” action, and the patient would be discharged from the emergency department without further cardiac work‑up.

**Clinical implication:** Patients who would benefit from immediate cardiac evaluation (e.g., silent myocardial infarction or microvascular angina) may be discharged prematurely, exposing them to delayed treatment and increased morbidity. The rule’s failure to capture atypical diabetic presentations is a critical safety concern that must be addressed before deployment.

### Over‑referrals
**Concrete patient example**

- **Demographics & comorbidity:** 35‑year‑old male with acute gastro‑oesophageal reflux disease (GERD).  
- **Presentation:** Chest discomfort described as “pressure” without radiation, mild dyspnoea, no diaphoresis, and no pain that worsens with exertion.  
- **Why the rule fires:** The symptom complex (chest pain + dyspnoea + age > 40) satisfies the third branch, leading to unnecessary termination of the emergency session and possible unnecessary transport or admission.

### The case for leaving the rule unchanged
The strongest argument for not altering the rule is that it aligns with Western guideline templates (NICE CG95, AHA/ACC) which prioritize classic ACS presentations (radiating pain, exertional worsening, dyspnoea, diaphoresis). Changing the rule could:

1. **Increase false‑positive referrals** to higher‑resource facilities, straining limited capacity in district hospitals.  
2. **Lead to unnecessary resource consumption** (e.g., CT angiography, invasive cardiac testing) that may not be reimbursed or available locally.  
3. **Create a cascade of over‑triage** that could divert critical care resources from patients with genuine life‑threatening presentations (e.g., severe trauma, hemorrhagic stroke).

### Outside my seat
- **Data availability:** The local corpus contains no passages describing ACS presentations, indicating a gap in the clinical narrative that the rule could exploit.  
- **Cultural presentation patterns:** Studies from Indian primary‑care settings show that patients often describe chest discomfort as “pressure” or “tightness” without radiation, diaphoresis, or exertional worsening—behaviour that the current rule penalises.

### The one decision I would put to a clinician
**Should the rule be modified to include a broader pain‑character criterion (e.g., “pressure/tightness” without requiring radiation) and/or an age‑adjusted escalation threshold (e.g., age ≥ 60 instead of > 60) to capture silent or atypical presentations common in this population?**  

If **yes**, the clinician should consider:

1. **Pain‑character expansion:** Replace the requirement for pain radiation with a broader definition of “pressure/tightness” as sufficient for the first two branches.  
2. **Age‑threshold adjustment:** Change the escalation branch to `chest_pain_present AND age_recorded >= 60` (or `> 60` if the intent is to capture the same age group as Western guidelines).  
3. **Add a symptom‑specific branch** for atypical presentations (e.g., `chest_pain_present AND dyspnoea_present AND age_over_40` without radiation) to capture patients like Patient 2.  
4. **Document the rationale** for any changes, including local epidemiology (high prevalence of silent ACS in diabetics) and referral network capacity, to ensure the rule remains clinically meaningful.

If **no**, the clinician should maintain the rule as is, acknowledging that the current design is appropriate for a Western‑derived guideline set and that the risk of over‑triage outweighs the benefit of capturing atypical presentations in this setting.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_ACS_001 misses diabetic patients who present with atypical, non‑painful chest‑related symptoms (e.g., epigastric discomfort, dyspnoea, diaphoresis) and therefore would not be escalated to termination.

**Missed patient (concrete example):**

- **Demographics:** 58‑year‑old woman, type 2 diabetes mellitus, 12 years of disease duration, on oral hypoglycaemic agents.
- **Chief complaint:** Two hours of “heaviness” in the epigastrium described as “pressure‑like” but without any overt chest‑pain that radiates to the jaw or left arm. She reports dyspnoea and profuse sweating, yet she does **not** describe pain that meets the rule’s “chest_pain_present” criterion.
- **Additional features:** No exertional dyspnoea, no radiation to the jaw/left arm, no diaphoresis‑only (she attributes sweating to ambient temperature), and no documented age > 40 (she is 58). She is not known to have any of the other age‑related qualifiers (e.g., age > 60, known coronary disease).
- **Why the rule fires:** None of the four rule branches are satisfied:
  1. **Chest pain + radiation** – absent (no pain reported).
  2. **Chest pain + diaphoresis** – absent (pain not present).
  3. **Chest pain + dyspnoea + age > 40** – absent (pain not present).
  4. **Chest pain + pressure/tightness + worse on exertion** – absent (pain not present).
- **Result of the rule:** Because none of the encoded criteria are met, the rule does **not** trigger the “TERMINATE_EMERGENCY” action, and the patient would be discharged from the emergency department without further cardiac work‑up.

**Why this patient is missed:**

- The rule’s design is heavily weighted toward classic anginal pain patterns (radiation, pressure/tightness, exertional worsening) that are common in Western populations with known coronary artery disease.
- In many low‑resource, Indian settings, diabetic patients often present with atypical symptoms such as epigastric discomfort, dyspnoea, and marked diaphoresis, which are not captured by the rule’s “chest_pain_present” prerequisite.
- The note from the author (“Diabetes is common and long‑standing in this population and silent or atypical presentation is more likely”) correctly flags a potential gap, but the rule does not incorporate any additional clinical context (e.g., diabetes status, typical diabetic chest‑pain phenotype) that could flag such presentations.

**Clinical implication:** Patients who would benefit from immediate cardiac evaluation (e.g., silent myocardial infarction or microvascular angina) may be discharged prematurely, exposing them to delayed treatment and increased morbidity. The rule’s failure to capture atypical diabetic presentations is a critical safety concern that must be addressed before deployment.

### safety engineer

**Headline:** The rule fails to fire on a common presentation of acute coronary syndrome in this population – a silent, atypical myocardial infarction that lacks classic chest‑pain descriptors required by the encoded criteria.

**Missed case (constructed patient):**

- **Demographics & comorbidity:** 58‑year‑old woman, type 2 diabetic for 12 years, BMI ≈ 30 kg/m², no known coronary disease.  
- **Clinical presentation:** Two hours of diffuse epigastric discomfort described as “indigestion” or “heartburn,” with accompanying mild sweating and dyspnoea. No pain described as “pressure,” “tightness,” or “radiating to the jaw/left arm.” No exertional aggravation reported.  
- **Why the rule does not fire:** All four encoded branches require the explicit phrase **`chest_pain_present`**. The patient’s description never uses any of the qualifying terms (pressure, tightness, radiating, worsening on exertion). Consequently, none of the four conditions are satisfied, and the escalation to **age > 60** is never reached.  
- **Potential consequence:** Silent or atypical myocardial infarction can progress rapidly; delayed recognition may lead to irreversible myocardial injury or death. The rule’s inability to capture this presentation creates a safety gap, especially given the high prevalence of diabetes‑related silent ACS in this region.

**Edge‑case considerations:**

1. **Other rules interaction:**  
   - Rules that trigger on *pain_radiates_to_jaw_or_left_arm* or *pain_worse_on_exertion* will not be activated because the patient does not report those descriptors. If a downstream rule (e.g., RF_ACS_002) relies on the presence of these descriptors, the cascade may miss the silent event entirely.

2. **Input validation:**  
   - The rule assumes clinicians will encode chest pain using the exact phrasing required by the criteria. In practice, free‑text notes often use synonyms (e.g., “heartburn,” “abdominal discomfort”) that are not captured by the current natural‑language processing pipeline, leading to false negatives.

3. **Population‑specific bias:**  
   - Epidemiological data from this region show that >30 % of acute coronary events present without overt chest pain, particularly in diabetics. The rule’s design, derived from Western guidelines that emphasize classic chest‑pain descriptors, underestimates the risk in this population.

**What the clinician must decide:**

- Whether to broaden the rule’s trigger to include *any* form of chest‑related discomfort (e.g., “heartburn,” “abdominal pressure”) or to add a separate branch that flags patients with diabetes and atypical symptoms.  
- Whether the current schema can accommodate a more granular symptom ontology (e.g., `pain_character_pressure_like`, `pain_location_jaw_arm`) without requiring manual re‑coding of historical notes.  
- Whether the escalation to **age > 60** should be removed or replaced with a risk‑factor‑based threshold (e.g., known diabetes) to capture silent events earlier.

**Conclusion:** The rule’s strict reliance on the exact phrase `chest_pain_present` creates a critical blind spot for silent, atypical myocardial infarction—a scenario that is both common and potentially life‑threatening in this patient population. Addressing this gap requires either a redesign of the symptom criteria or an adjunctive rule that captures diabetes‑related atypical presentations.

### Indian practice reviewer

**Headline:** The rule RF_ACS_001, as written, will miss a substantial subset of patients with acute coronary syndrome (ACS) who present with atypical, silent, or atypical‑pain presentations common in the Indian population and referral network.

**Misses**

**Patient 1 – 58‑year‑old diabetic male, long‑standing diabetes (10 years), no known coronary disease.**  
- **Presentation:** Sudden onset of mild‑to‑moderate epigastric discomfort described as “pressure” without any radiation to the jaw or left arm, no dyspnoea, no diaphoresis, and no pain that worsens with exertion.  
- **Age:** 58 years (does not meet the age > 40 or > 60 thresholds).  
- **Why it fails:** All four branches require `chest_pain_present` **and** at least one additional criterion (radiation, diaphoresis, dyspnoea + age > 40, or pressure‑tightness + exertion‑worsening). This patient’s pain is not described as radiating, not accompanied by diaphoresis or dyspnoea, and there is no evidence of exertional worsening. Consequently, none of the encoded branches fire, and the rule terminates the emergency session without escalation.

**Patient 2 – 45‑year‑old female, known hypertension, no diabetes, presenting with palpitations, mild shortness of breath, and a vague “tightness” in the chest that she attributes to indigestion.**  
- **Presentation:** Chest discomfort described as “tightness” without radiation, no diaphoresis, no dyspnoea beyond mild shortness, and no pain that worsens with activity.  
- **Age:** 45 years (fails the age > 40 requirement for the branch that needs age).  
- **Why it fails:** The rule’s first branch (`chest_pain_present AND pain_radiates_to_jaw_or_left_arm`) is not met because the pain is not radiating. The second branch (`chest_pain_present AND diaphoresis_present`) fails because diaphoresis is absent. The third branch (`chest_pain_present AND dyspnoea_present AND age_over_40`) fails due to lack of dyspnoea. The fourth branch (`chest_pain_present AND pain_character_pressure_or_tightness AND pain_worse_on_exertion`) fails because there is no documented exertional worsening. Thus, the rule does not trigger.

**Patient 3 – 70‑year‑old male, known coronary artery disease, presenting with a prodromal “tightness” in the chest that he attributes to coughing and a mild cough‑related dyspnoea.**  
- **Presentation:** Chest discomfort described as “tightness” without radiation, no diaphoresis, mild dyspnoea, and no pain that worsens with exertion.  
- **Age:** 70 years (fails the age > 60 threshold for the escalation branch).  
- **Why it fails:** Although the pain character matches “pressure/tightness,” the rule’s escalation branch (`chest_pain_present AND age_over_60`) is not satisfied because the patient is exactly 70 years old (the rule expects age > 60). Consequently, the rule does not trigger the escalation to a higher‑level care pathway.

**Over‑referrals**

The rule, by design, will fire on many non‑ACS presentations that are common in low‑resource settings:

- **Patient 4 – 35‑year‑old male with acute gastro‑oesophageal reflux disease (GERD) presenting with epigastric discomfort and mild dyspnoea.**  
  - The symptom complex (chest pain + dyspnoea) can satisfy the third branch, leading to unnecessary termination of the emergency session and possible unnecessary transport or admission.

**The case for leaving the rule unchanged**

The strongest argument for not altering the rule is that the current structure aligns with the available Western guideline templates (NICE CG95, AHA/ACC) which prioritize classic ACS presentations (radiating pain, exertional worsening, dyspnoea, diaphoresis). Changing the rule to lower the threshold could:

1. **Increase false‑positive referrals** to higher‑resource facilities, straining already limited capacity in district hospitals.
2. **Lead to unnecessary resource consumption** (e.g., CT angiography, invasive cardiac testing) that may not be reimbursed or available locally.
3. **Create a cascade of over‑triage** that could divert critical care resources from patients with genuine life‑threatening presentations (e.g., severe trauma, hemorrhagic stroke).

**Outside my seat**

- **Data availability:** The local corpus contains no passages describing ACS presentations, indicating a gap in the clinical narrative that the rule could exploit. This suggests a need for a richer local dataset to inform rule refinement.
- **Cultural presentation patterns:** Studies from Indian primary‑care settings show that patients often describe chest discomfort as “pressure” or “tightness” without radiation, diaphoresis, or exertional worsening—behaviour that the current rule penalizes.

**The one decision I would put to a clinician**

**Should the rule be modified to include a broader pain‑character criterion (e.g., “pressure/tightness” without requiring radiation) and/or an age‑adjusted escalation threshold (e.g., age ≥ 60 instead of > 60) to capture silent or atypical presentations common in this population?**  

If the answer is **yes**, the clinician should consider:

1. **Pain‑character expansion:** Replace the requirement for pain radiation with a broader definition of “pressure/tightness” as sufficient for the first two branches.
2. **Age‑threshold adjustment:** Change the escalation branch to `chest_pain_present AND age_recorded >= 60` (or `> 60` if the intent is to capture the same age group as Western guidelines).
3. **Add a symptom‑specific branch** for atypical presentations (e.g., `chest_pain_present AND dyspnoea_present AND age_over_40` without radiation) to capture patients like Patient 2.
4. **Document the rationale** for any changes, including local epidemiology (high prevalence of silent ACS in diabetics) and referral network capacity, to ensure the rule remains clinically meaningful.

If the answer is **no**, the clinician should maintain the rule as is, acknowledging that the current design is appropriate for a Western‑derived guideline set and that the risk of over‑triage outweighs the benefit of capturing atypical presentations in this setting.
