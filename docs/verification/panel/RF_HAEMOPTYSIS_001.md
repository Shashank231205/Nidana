# RF_HAEMOPTYSIS_001 — Significant haemoptysis

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **emergency physician**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** proposed unsourced thresholds (`> 2 weeks`, `> 10 mL`, `> 30 mL`); was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — safety engineer** proposed unsourced thresholds (`> 100 mL`).

> **Warning — Indian practice reviewer** used approving language.

## RF_HAEMOPTYSIS_001 – Panel Brief

**Headline:** The rule misses patients with atypical, low‑volume haemoptysis who present with dyspnoea but no chest pain—common in tuberculosis‑endemic settings and not captured by the current criteria.

### Misses
**Concrete patient example (miss):**  
- **Demographics:** 45‑year‑old male, age recorded 45, immunosuppressed (HIV + CD4 < 200).  
- **Chief complaint:** “I feel short of breath, especially when I’m walking up a hill.” No chest pain described.  
- **Physical exam:** Tachypnoea 30/min, audible wheeze, mild tachycardia. No pleuritic chest pain, no hemodynamic instability.  
- **History:** Lives in a rural district where tuberculosis prevalence is high; cough > 2 weeks, productive sputum reported, but no fever or night sweats.  
- **Haemoptysis:** Small amount of blood‑stained sputum (≈ 5 mL) noted in the past 24 h; patient reports feeling “like I’m drowning” when breathing heavily.  
- **Why it fires:** The rule requires **chest_pain_present**; the patient’s presentation lacks that predicate, so the rule does not trigger despite meeting the haemoptysis + dyspnoea condition.  

**Why this matters:** In this population, TB‑related pulmonary haemoptysis often presents without chest pain, especially in the early stage or in immunosuppressed individuals. Missing such cases could delay life‑saving anti‑TB therapy and lead to rapid deterioration.

**Clinical implication:** The rule should be expanded to include **haemoptysis_present AND dyspnoea_present** (without the chest‑pain requirement) or incorporate a severity threshold (e.g., > 10 mL of blood or > 30 mL of sputum) to capture these atypical presentations.

**Next steps for verification:**  
1. Review the local epidemiology of TB‑related haemoptysis in this region to set an appropriate threshold.  
2. Consider adding a “low‑volume haemoptysis” branch that triggers escalation based solely on dyspnoea severity and volume, rather than chest pain.  
3. Validate the rule with a small cohort of recent TB cases to ensure sensitivity for this presentation.

---

### Safety Engineer – Over‑referrals & Edge Cases
**Concrete patient example (over‑referral):**  
- **Patient:** 45‑year‑old female with a recent history of mild asthma exacerbation. She coughed up a moderate amount of blood‑stained sputum (≈ 50 mL) and reported mild chest discomfort (pressure‑like) but no significant dyspnoea.  
- **Why the rule fires unnecessarily:** The presence of **haemoptysis_present** combined with **chest_pain_present** satisfies the rule’s condition, leading to an unnecessary escalation band that may divert resources from patients with more severe presentations (e.g., massive haemoptysis without pain).

**The case for leaving it alone**  
- **Strengths:** Simplicity, alignment with guideline thresholds (e.g., ACCP, British Thoracic Society) that recommend escalation for haemoptysis accompanied by dyspnoea or chest pain, reducing cognitive load for clinicians.  
- **Limitations:** Excludes silent massive haemoptysis, potentially leading to delayed diagnosis of life‑threatening conditions; may cause over‑referral in mild asthma exacerbations, diverting attention from more urgent cases.

**Outside my seat**  
- **Schema gap:** The rule does not incorporate **blood_volume** or **oxygen_saturation** predicates, which are critical for assessing severity of haemoptysis. Adding these would allow the system to flag high‑risk cases even without dyspnoea or chest pain.

**The one decision I would put to a clinician**  
> **Should the rule be expanded to include a severity‑based trigger (e.g., haemoptysis volume > 100 mL or concurrent hypoxaemia) while retaining the dyspnoea/chest‑pain condition to avoid false positives?**  
> - **If yes:** Implement a secondary predicate (e.g., **haemoglobin_drop_present** or **oxygen_sat_below_90%**) that, when combined with haemoptysis, triggers escalation regardless of dyspnoea/chest‑pain.  
> - **If no:** Keep the rule as is, documenting the risk of missing silent massive haemoptysis and emphasizing clinical judgment for volume‑based escalation in high‑risk populations.

---

### Indian Practice Reviewer – Population‑Specific Considerations
**Headline:** The rule, as written for a Western‑derived emergency pathway, will miss a substantial subset of haemoptysis presentations common in Indian district hospitals—particularly those caused by pulmonary tuberculosis (TB) where haemoptysis is often mild, intermittent, and accompanied by atypical symptoms such as productive cough, night sweats, weight loss, and constitutional features.

**Misses**

1. **Patient A – 45‑year‑old male, resident of a rural district hospital, known TB patient (positive sputum smear, on standard 6‑month isoniazid‑rifampicin‑pyrazinamide‑ethambutol regimen).**  
   - **Presentation:** Sudden onset of mild‑to‑moderate haemoptysis (≈ 10–20 coughfuls per day) that he initially attributes to “cold” and “muscle strain.” He reports productive cough with purulent sputum, night sweats, and unintentional weight loss for the past 3 months.  
   - **Why it fails:** The rule requires **dyspnoea_present** *or* **chest_pain_present** alongside haemoptysis. In TB‑related haemoptysis, the cough and constitutional symptoms dominate; the patient’s dyspnoea is usually mild and not described as “severe” or “laboured” in the voice‑recording system, and chest pain is often absent or misinterpreted as pleuritic discomfort that is not captured by the current predicate set. Consequently, the rule never fires.

2. **Patient B – 60‑year‑old female, chronic bronchitis, diagnosed with TB (positive smear, on the same regimen).**  
   - **Presentation:** Occasional, brief episodes of haemoptysis (≈ 2–3 coughfuls) occurring during exertion, but she reports no chest pain, dyspnoea, or fever. She attributes the bleeding to “cold” and “muscle strain” and does not seek care until the symptom recurs.  
   - **Why it fails:** The rule’s criteria demand either dyspnoea or chest pain, both of which are absent or trivial in TB‑related haemoptysis. The current system’s voice‑recording schema captures only severe dyspnoea or chest pain as “breathing difficulty present” or “chest pain present,” which are not triggered by the mild, intermittent symptoms typical of TB.

**Over‑referrals**

- **Patient C – 30‑year‑old male, acute bacterial pneumonia (Pseudomonas) with severe dyspnoea and chest pain.**  
  - **Why it fires:** The rule correctly escalates because haemoptysis is present together with dyspnoea and chest pain, both of which are captured by the available predicates. This scenario is not a miss but a legitimate escalation, highlighting that the rule is appropriate for high‑grade presentations but fails for milder, atypical TB‑related cases.

**The case for leaving it alone**

- **Strength of current design:** The rule is designed to capture the most severe haemoptysis scenarios where patients present with *significant* dyspnoea and/or chest pain—conditions that are strongly associated with life‑threatening causes (e.g., pulmonary embolism, massive pulmonary bleed) in Western emergency pathways. Escalation in these cases aligns with best‑practice triage protocols that prioritize rapid assessment and intervention.
- **Potential drawback:** By focusing on severe dyspnoea and chest pain, the rule may overlook TB‑related haemoptysis, which can be life‑limiting (e.g., TB‑associated massive haemoptysis) but is often under‑reported due to patients’ cultural reluctance to describe pain or breathing difficulty as “severe.” This omission could delay diagnosis and treatment of a disease that is a leading cause of mortality in this population.

**Outside my seat**

- **Data‑availability gap:** The retrieved local corpus contains no passages describing haemoptysis management in Indian settings, indicating a lack of locally relevant clinical narratives that could inform the threshold for “significant” haemoptysis. This gap suggests that the rule’s thresholds (dyspnoea and chest pain) may not reflect the actual symptomatology experienced by patients in district hospitals.
- **Cultural and socioeconomic factors:** In many Indian districts, patients may under‑report or misinterpret dyspnoea and chest pain, leading to under‑triage of TB‑related haemoptysis. This cultural context should be considered when revising the rule or accompanying guidelines.

**The one decision I would put to a clinician**

> **Should the rule’s haemoptysis criteria be broadened to include mild‑to‑moderate haemoptysis accompanied by atypical symptoms (productive cough, night sweats, constitutional features) characteristic of pulmonary TB, while retaining the escalation for severe dyspnoea and chest pain?**  
> 
> This decision hinges on whether the safety of detecting life‑threatening TB‑related haemoptysis outweighs the risk of over‑referral in cases where the bleeding is mild and the patient’s presentation is atypical. The clinician should weigh the epidemiological burden of TB in this population against the potential for missed cases and the associated downstream consequences (delayed TB treatment, increased morbidity, and resource strain on the district hospital).

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_HAEMOPTYSIS_001 misses patients with atypical, low‑volume haemoptysis who present with dyspnoea but no chest pain, a presentation that is common in tuberculosis‑endemic settings and is not captured by the current criteria.

**Missed patient (example):**  
- **Demographics:** 45‑year‑old male, age recorded 45, immunosuppressed (HIV + CD4 < 200).  
- **Chief complaint:** “I feel short of breath, especially when I’m walking up a hill.” No chest pain described.  
- **Physical exam:** Tachypnoea 30/min, audible wheeze, mild tachycardia. No pleuritic chest pain, no hemodynamic instability.  
- **History:** Lives in a rural district where tuberculosis prevalence is high; cough > 2 weeks, productive sputum reported, but no fever or night sweats.  
- **Haemoptysis:** Small amount of blood‑stained sputum (≈ 5 mL) noted in the past 24 h; patient reports feeling “like I’m drowning” when breathing heavily.  
- **Why it fires:** The rule requires **chest_pain_present**; the patient’s presentation lacks that predicate, so the rule does not trigger despite meeting the haemoptysis + dyspnoea condition.  

**Why this matters:** In this population, TB‑related pulmonary haemoptysis often presents without chest pain, especially in the early stage or in immunosuppressed individuals. Missing such cases could delay life‑saving anti‑TB therapy and lead to rapid deterioration.  

**Clinical implication:** The rule should be expanded to include **haemoptysis_present AND dyspnoea_present** (without the chest‑pain requirement) or incorporate a severity threshold (e.g., > 10 mL of blood or > 30 mL of sputum) to capture these atypical presentations.  

**Next steps for verification:**  
1. Review the local epidemiology of TB‑related haemoptysis in this region to set an appropriate threshold.  
2. Consider adding a “low‑volume haemoptysis” branch that triggers escalation based solely on dyspnoea severity and volume, rather than chest pain.  
3. Validate the rule with a small cohort of recent TB cases to ensure sensitivity for this presentation.

### safety engineer

**Headline:** The rule fails to fire for patients who experience significant haemoptysis without the presence of dyspnoea or chest pain, potentially leading to delayed recognition of life‑threatening pulmonary complications.

### Misses
**Concrete patient example (miss):**  
- **Patient:** 62‑year‑old male, known chronic obstructive pulmonary disease (COPD) with a history of smoking 20 cigarettes/day for 40 years.  
- **Presentation:** Developed a sudden, large‑volume cough producing blood‑stained sputum (≈200 mL) at home while resting comfortably, with no accompanying dyspnoea or chest pain.  
- **Key features:** No wheeze, no chest pain, normal respiratory rate (22 breaths/min), oxygen saturation 96 % on room air, no fever or cough‑related chest pain reported.  
- **Why the rule misses:** The rule requires either **dyspnoea_present** *or* **chest_pain_present** alongside **haemoptysis_present**. This patient’s presentation lacks both dyspnoea and chest pain, so the rule’s condition is not met, and the escalation action is not triggered.

### Over‑referrals
**Concrete patient example (over‑referral):**  
- **Patient:** 45‑year‑old female with a recent history of mild asthma exacerbation. She coughed up a moderate amount of blood‑stained sputum (≈50 mL) and reported mild chest discomfort (pressure‑like) but no significant dyspnoea.  
- **Why the rule fires unnecessarily:** The presence of **haemoptysis_present** combined with **chest_pain_present** satisfies the rule’s condition, leading to an unnecessary escalation band that may divert resources from patients with more severe presentations (e.g., massive haemoptysis without pain).

### The case for leaving it alone
**Strengths of the current rule:**  
1. **Simplicity:** The rule uses only two well‑established clinical signs (dyspnoea and chest pain) that are commonly taught in emergency protocols for acute haemoptysis, reducing cognitive load for clinicians.  
2. **Safety net:** By requiring either dyspnoea or chest pain, it avoids false positives in patients who may have minor haemoptysis without serious underlying pathology, potentially preventing unnecessary escalation.  
3. **Alignment with guideline thresholds:** Many emergency‑medicine guidelines (e.g., ACCP, British Thoracic Society) recommend escalation for haemoptysis accompanied by dyspnoea or chest pain, reflecting clinical consensus.

**Limitations that justify modification:**  
- **Exclusion of silent massive haemoptysis:** Patients with severe pulmonary embolism or tumour haemorrhage may present with massive blood loss without dyspnoea or chest pain, leading to delayed diagnosis and increased morbidity.  
- **Potential for over‑referral:** As shown above, mild asthma exacerbations can trigger the rule, diverting attention from patients with more urgent presentations.  
- **Lack of severity weighting:** The rule does not differentiate between low‑volume, symptom‑free haemoptysis and high‑volume, symptomatic events, which may affect resource allocation and patient triage.

### Outside my seat
- **Schema gap:** The rule does not incorporate **blood_volume** or **oxygen_saturation** predicates, which are critical for assessing severity of haemoptysis. Adding these would allow the system to flag high‑risk cases even without dyspnoea or chest pain.  
- **Population‑specific prevalence:** The note about tuberculosis prevalence suggests that the rule may need adjustment for populations where pulmonary infections (e.g., TB) are common, as they can cause haemoptysis without accompanying dyspnoea or chest pain.

### The one decision I would put to a clinician
**Should the rule be expanded to include a severity‑based trigger (e.g., haemoptysis volume > 100 mL or concurrent hypoxaemia) while retaining the dyspnoea/chest‑pain condition to avoid false positives?**  
- **If yes:** Implement a secondary predicate (e.g., **haemoglobin_drop_present** or **oxygen_sat_below_90%**) that, when combined with haemoptysis, triggers escalation regardless of dyspnoea/chest‑pain.  
- **If no:** Keep the rule as is, documenting the risk of missing silent massive haemoptysis and emphasizing clinical judgment for volume‑based escalation in high‑risk populations.

---

**Conclusion:** The current rule’s reliance solely on dyspnoea or chest pain creates a blind spot for silent massive haemoptysis, potentially leading to delayed treatment. A modest expansion to incorporate volume or oxygenation thresholds, while preserving the existing dyspnoea/chest‑pain condition, could improve safety without significantly increasing false‑positive escalations.

### Indian practice reviewer

**Headline:** The rule RF_HAEMOPTYSIS_001, as written for a Western‑derived emergency pathway, will miss a substantial subset of haemoptysis presentations common in Indian district hospitals—particularly those caused by pulmonary tuberculosis (TB) where haemoptysis is often mild, intermittent, and accompanied by atypical symptoms such as productive cough, night sweats, weight loss, and constitutional features.

**Misses**

1. **Patient A – 45‑year‑old male, resident of a rural district hospital, known TB patient (positive sputum smear, on standard 6‑month isoniazid‑rifampicin‑pyrazinamide‑ethambutol regimen).**  
   - **Presentation:** Sudden onset of mild‑to‑moderate haemoptysis (≈ 10–20 coughfuls per day) that he initially attributes to “cold” and “muscle strain.” He reports productive cough with purulent sputum, night sweats, and unintentional weight loss for the past 3 months.  
   - **Why it fails:** The rule requires **dyspnoea_present** *or* **chest_pain_present** alongside haemoptysis. In TB‑related haemoptysis, the cough and constitutional symptoms dominate; the patient’s dyspnoea is usually mild and not described as “severe” or “laboured” in the voice‑recording system, and chest pain is often absent or misinterpreted as pleuritic discomfort that is not captured by the current predicate set. Consequently, the rule never fires.

2. **Patient B – 60‑year‑old female, chronic bronchitis, diagnosed with TB (positive smear, on the same regimen).**  
   - **Presentation:** Occasional, brief episodes of haemoptysis (≈ 2–3 coughfuls) occurring during exertion, but she reports no chest pain, dyspnoea, or fever. She attributes the bleeding to “cold” and “muscle strain” and does not seek care until the symptom recurs.  
   - **Why it fails:** The rule’s criteria demand either dyspnoea or chest pain, both of which are absent or trivial in TB‑related haemoptysis. The current system’s voice‑recording schema captures only severe dyspnoea or chest pain as “breathing difficulty present” or “chest pain present,” which are not triggered by the mild, intermittent symptoms typical of TB.

**Over‑referrals**

- **Patient C – 30‑year‑old male, acute bacterial pneumonia (Pseudomonas) with severe dyspnoea and chest pain.**  
  - **Why it fires:** The rule correctly escalates because haemoptysis is present together with dyspnoea and chest pain, both of which are captured by the available predicates. This scenario is not a miss but a legitimate escalation, highlighting that the rule is appropriate for high‑grade presentations but fails for milder, atypical TB‑related cases.

**The case for leaving it alone**

- **Strength of current design:** The rule is designed to capture the most severe haemoptysis scenarios where patients present with *significant* dyspnoea and/or chest pain—conditions that are strongly associated with life‑threatening causes (e.g., pulmonary embolism, massive pulmonary bleed) in Western emergency pathways. Escalation in these cases aligns with best‑practice triage protocols that prioritize rapid assessment and intervention.
- **Potential drawback:** By focusing on severe dyspnoea and chest pain, the rule may overlook TB‑related haemoptysis, which can be life‑limiting (e.g., TB‑associated massive haemoptysis) but is often under‑reported due to patients’ cultural reluctance to describe pain or breathing difficulty as “severe.” This omission could delay diagnosis and treatment of a disease that is a leading cause of mortality in this population.

**Outside my seat**

- **Data‑availability gap:** The retrieved local corpus contains no passages describing haemoptysis management in Indian settings, indicating a lack of locally relevant clinical narratives that could inform the threshold for “significant” haemoptysis. This gap suggests that the rule’s thresholds (dyspnoea and chest pain) may not reflect the actual symptomatology experienced by patients in district hospitals.
- **Cultural and socioeconomic factors:** In many Indian districts, patients may under‑report or misinterpret dyspnoea and chest pain, leading to under‑triage of TB‑related haemoptysis. This cultural context should be considered when revising the rule or accompanying guidelines.

**The one decision I would put to a clinician**

> **Should the rule’s haemoptysis criteria be broadened to include mild‑to‑moderate haemoptysis accompanied by atypical symptoms (productive cough, night sweats, constitutional features) characteristic of pulmonary TB, while retaining the escalation for severe dyspnoea and chest pain?**  
> 
> This decision hinges on whether the safety of detecting life‑threatening TB‑related haemoptysis outweighs the risk of over‑referral in cases where the bleeding is mild and the patient’s presentation is atypical. The clinician should weigh the epidemiological burden of TB in this population against the potential for missed cases and the associated downstream consequences (delayed TB treatment, increased morbidity, and resource strain on the district hospital).
