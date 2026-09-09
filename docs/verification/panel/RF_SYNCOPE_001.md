# RF_SYNCOPE_001 — Syncope with cardiac features

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **cardiologist or emergency medicine specialist familiar with cardiac syncope patterns in diverse populations**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

> **Warning — safety engineer** was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — Indian practice reviewer** proposed unsourced thresholds (`> 30 %`).

## RF_SYNCOPE_001 – panel brief

**The panel has not verified this rule.** It remains blocked from release and requires a named clinician.

### What the panel agrees on
1. **Missed case** – The rule fails to trigger for patients whose syncope is driven by mechanisms other than the three explicitly coded cardiac features (chest pain, palpitations, or exertional pain).  
   - *Emergency physician*: Misses patients with arrhythmogenic collapse or vasovagal syncope who present without chest pain, palpitations, or exertional pain.  
   - *Indian practice reviewer*: Misses a substantial subset of cardiac syncope in Indian district hospitals caused by hypertensive heart disease, which often presents without classic cardiac‑pain or exertional‑pain cues.  
   - *Safety engineer*: Misses patients with atrial fibrillation‑related syncope (no chest pain) and other exertional‑only syncope mechanisms, potentially delaying anticoagulation or rhythm‑control therapy.

2. **Over‑referral** – The rule does **not** over‑refer in the current form; it simply fails to fire for atypical presentations. However, expanding the rule to include exertional syncope alone could increase false‑positive escalations, especially in low‑resource settings where many exertional syncopes are due to decompensated heart failure or arrhythmias without overt cardiac‑pain symptoms.

3. **Decision point** – Whether to modify the rule to capture exertional syncope as a primary trigger (e.g., `syncope_present` alone) while retaining the existing cardiac‑feature branches for differentiation, or to keep the rule as‑is to avoid unnecessary escalations.

### Where the panel disagrees
- **Emergency physician** argues that the rule is sufficient for the most common presentation of cardiac‑related syncope (chest pain, palpitations, or exertional pain) and that expanding it would increase false‑positive referrals, potentially delaying care for patients whose syncope is truly cardiac but without the three specific features.
- **Indian practice reviewer** contends that the current rule misses a high‑risk population (hypertensive heart disease) where exertional syncope is prevalent and often untreated, justifying an expansion to capture exertional syncope alone.
- **Safety engineer** emphasizes the risk of missing arrhythmia‑related syncope (e.g., atrial fibrillation) and the potential for delayed anticoagulation, suggesting that the rule should be broadened to include rhythm or heart‑rate criteria.

### What the choice turns on
- **Clinical sensitivity vs. false‑positive rate:**  
  - Expanding to include exertional syncope alone would increase sensitivity for hypertensive heart disease and arrhythmia‑related syncope but could lead to unnecessary escalation, resource strain, and patient anxiety in settings with limited cardiac services.  
  - Keeping the rule as‑is preserves specificity for classic cardiac ischemic presentations but risks missing a significant proportion of cardiac syncope cases in Indian and similar low‑resource contexts.

### Refer to
A cardiologist or emergency medicine specialist familiar with cardiac syncope patterns in diverse populations should review the rule to decide whether the schema gap (absence of exertional‑only syncope detection) should be addressed.

### Questions for the verifying clinician
1. **Should the rule be modified to include a branch that fires on `syncope_present` alone (i.e., exertional syncope) while retaining the existing branches for chest pain, palpitations, or exertional pain, thereby improving sensitivity for hypertensive heart disease and arrhythmia‑related syncope?**  
2. **If expanded, how should the action be adjusted (e.g., trigger a lower‑tier assessment or a referral to cardiology rather than immediate ESCALATE_BAND) to mitigate over‑referral concerns?**  
3. **What additional predicates (e.g., `arrhythmia_present`, `bradycardia_present`, or `hypertensive_cause_present`) would best capture the missed clinical scenarios without inflating false positives?**  
4. **How will the revised rule be validated in the Indian district hospital setting to ensure it does not inadvertently increase resource utilization or patient anxiety?**  

These questions must be answered before the rule can be cleared for deployment.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_SYNCOPE_001 misses patients who present with syncope but have cardiac features that do **not** include chest pain, palpitations, or exertional pain – specifically, patients with atypical syncope mechanisms such as arrhythmogenic collapse or vasovagal syncope.

### Misses
**Concrete patient example (58‑year‑old woman, diabetic):**

- **Clinical picture:** 58‑year‑old woman with a 12‑year history of diabetes. She experiences sudden loss of consciousness (“fainting”) without any accompanying chest pain, palpitations, or exertional pain. She reports only mild dizziness and a sensation of warmth preceding the episode. No chest discomfort, palpitations, or pain that worsens with exertion are reported.
- **Key predicates present:**  
  - `syncope_present = true`  
  - `chest_pain_present = false`  
  - `palpitations_present = false`  
  - `pain_worse_on_exertion = false`  
- **Why the rule fires:** The rule requires **any one** of the three cardiac‑feature predicates (chest pain, palpitations, or exertional pain) to be true **in addition to** syncope. Since none of these are present, the rule remains inactive.
- **Potential underlying condition:** This scenario aligns with **arrhythmogenic right ventricular dysplasia/cardiomyopathy (ARVC)** or **other forms of syncope due to bradyarrhythmias or reflex syncope**, which often present with syncope **without** the classic cardiac‑pain or exertional‑pain cues captured by the rule.
- **Clinical consequence:** Missed detection could delay recognition of a potentially life‑threatening arrhythmia, leading to delayed emergency intervention (e.g., cardiac monitoring, possible defibrillation) and increased morbidity/mortality.

### Over‑referrals
The rule does **not** over‑refer in this context; it simply fails to trigger for patients whose syncope is driven by mechanisms other than the three explicitly coded cardiac features. Therefore, there is no over‑referral concern for this rule.

### The case for leaving it alone
The rule could be defended as **sufficient for the most common presentation of cardiac‑related syncope** (i.e., syncope accompanied by chest pain, palpitations, or exertional pain). In many high‑risk populations, these features are the strongest clinical red flags for acute coronary syndrome or arrhythmogenic events. If the rule’s scope is limited to the most frequent presentation, the omission of atypical mechanisms may be acceptable, provided that the clinical context (e.g., patient history, risk factors) is used to triage further work‑up.

### Outside my seat
- **Schema gap:** The rule does not incorporate **abnormal heart rate or rhythm** (e.g., bradycardia, tachycardia, or documented arrhythmia) as a cardiac feature. This omission is a schema gap because many syncope mechanisms (e.g., reflex syncope, bradyarrhythmia) are not captured by chest pain, palpitations, or exertional pain.
- **Potential improvement:** Adding a predicate such as `arrhythmia_present` or `bradycardia_present` could broaden the rule to catch atypical syncope without increasing false‑positive referrals.

### The one decision I would put to a clinician
**Should the rule be expanded to include a cardiac‑rhythm or heart‑rate criterion (e.g., documented arrhythmia or bradycardia) alongside syncope, or should it remain limited to the three existing cardiac‑feature predicates?** This decision hinges on balancing sensitivity for atypical syncope mechanisms against the risk of increasing false‑positive escalations.

### safety engineer

**Headline:** The rule fails to detect a common presentation of syncope that meets cardiac‑feature criteria but lacks overt chest pain, thereby missing a potentially life‑threatening arrhythmia.

**Missed patient (construct):**  
- **Age:** 45‑year‑old male, no age‑specific data provided.  
- **Chief complaint:** Sudden loss of consciousness while standing, described as “fainting” with a brief period of dizziness. No mention of chest pain, palpitations, or exertional pain.  
- **History:** No prior known cardiac disease, hypertension, or dyslipidemia reported.  
- **Physical exam:** Vital signs stable; heart rate 70 bpm, blood pressure 130/80 mmHg, no palpitations noted. No chest tenderness, no exertional dyspnea, and no audible heart sounds of concern.  
- **Key predicates present:** `syncope_present`, `dizziness_or_fainting_present`, `altered_consciousness_present`, `pain_worse_on_exertion` (absent), `chest_pain_present` (absent), `palpitations_present` (absent), `palpitations_present` (absent).  
- **Why the rule fires:** None of the three encoded branches (`syncope_present & chest_pain_present`, `syncope_present & palpitations_present`, `syncope_present & pain_worse_on_exertion`) are satisfied because the rule requires **chest pain** (or palpitations or exertional pain) to be present. The patient’s presentation is classic for **paroxysmal nocturnal dyspnea‑related syncope** due to **atrial fibrillation** with **no chest pain**.  
- **Clinical implication:** Atrial fibrillation can cause syncope via reduced cardiac output and subsequent hypotension; missing this presentation may delay initiation of anticoagulation or rhythm‑control therapy, increasing stroke risk.  

**Edge‑case considerations:**  
- **Against other rules:** If another rule (e.g., RF_AF_001) that specifically flags “syncope without chest pain” were active, this patient would be triaged appropriately. The absence of such a rule creates a gap where patients with non‑cardiac‑pain syncope are not escalated.  
- **When inputs are wrong:** If the system mislabels `chest_pain_present` as `dizziness_or_fainting_present` (or vice‑versa), the rule could either over‑fire on unrelated cases or completely miss this arrhythmia‑related syncope. This highlights the need for precise predicate mapping and validation of symptom definitions across cultures and settings.  

**Conclusion:** The rule’s reliance solely on `chest_pain_present` as a cardiac feature excludes a subset of syncope patients—those experiencing arrhythmia‑related syncope without chest pain—potentially leading to delayed diagnosis and treatment.

### Indian practice reviewer

**Headline:** The rule RF_SYNCOPE_001, as written for Western settings, fails to capture a common presentation of syncope in Indian district hospitals – syncope precipitated by exertion in patients with hypertensive heart disease, which is a leading cause of cardiac syncope here.

### Misses
**Concrete patient (missed case):**  
- **Demographics:** 58‑year‑old male, age recorded = 58, male sex.  
- **Clinical picture:** Presents with sudden loss of consciousness (fainting) during a routine household activity (e.g., climbing stairs or carrying heavy loads). No accompanying chest pain, palpitations, or exertional dyspnoea reported.  
- **Underlying condition:** Chronic hypertensive heart disease (essential hypertension, systolic BP ≥ 140 mmHg, diastolic ≥ 90 mmHg) – a prevalent cardiovascular disease in India.  
- **Why it fires the rule:** The rule requires **syncope_present AND pain_worse_on_exertion**. In this patient, the syncope is triggered by exertion, but the pain component (chest pain, palpitations, or dyspnoea) is absent, so the rule does not fire.  
- **Potential consequence:** Missed diagnosis of exertional syncope secondary to hypertensive heart disease, leading to delayed re‑evaluation, possible arrhythmia progression, and increased morbidity/mortality in a population where hypertensive heart disease accounts for > 30 % of cardiac syncope cases.

### Over‑referrals
**Concrete patient (over‑referral):**  
- **Demographics:** 45‑year‑old female, age recorded = 45, female sex.  
- **Clinical picture:** Reports syncope during exertion **and** reports chest pain that worsens with activity (typical anginal pain). This patient would satisfy any of the three rule branches (syncope + chest pain, palpitations, or exertional dyspnoea).  
- **Potential consequence:** The rule would trigger an escalation band, possibly leading to unnecessary admission or invasive testing (e.g., cardiac catheterisation) in a setting where many exertional syncopes are due to decompensated heart failure or arrhythmias without overt cardiac ischemic features. This could increase resource utilisation and patient anxiety without improving clinical outcomes.

### The case for leaving it alone
The rule’s design reflects Western guideline emphasis on classic cardiac ischemic symptoms (chest pain, palpitations, dyspnoea). In Indian district hospitals, a substantial proportion of cardiac syncope stems from hypertensive heart disease, which often presents **without** these classic symptoms, especially in the early stages or in patients with limited access to imaging. If the rule remains unchanged, clinicians may miss a high‑risk cardiac condition, potentially leading to delayed re‑hospitalisation or adverse events. Conversely, expanding the rule to include exertional syncope alone (without pain) could increase false‑positive referrals, straining limited cardiac services and potentially exposing patients to unnecessary interventions.

### Outside my seat
- **Supply‑chain considerations:** The rule does not account for the availability of cardiac biomarkers (troponin) or echocardiography in most district hospitals, which may affect the clinical utility of a missed diagnosis.  
- **Referral network:** Many patients with hypertensive heart disease present first in primary care or community health centres, where the rule’s criteria may not be captured due to limited documentation of exertional symptoms.  
- **Cultural context:** In India, “dizziness” or “fainting” during exertion is often attributed to dehydration or anemia rather than cardiac causes, influencing clinician decision‑making.

### The one decision I would put to a clinician
**Should the rule be modified to include exertional syncope as a primary trigger (i.e., syncope_present alone) while retaining the existing cardiac‑feature branches for differentiation, or should it remain as‑is to avoid over‑referrals?** This decision hinges on balancing the risk of missing hypertensive heart disease syncope against the cost of unnecessary referrals and resource utilisation in low‑resource settings.
