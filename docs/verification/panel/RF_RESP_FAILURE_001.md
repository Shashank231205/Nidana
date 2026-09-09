# RF_RESP_FAILURE_001 — Respiratory compromise

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **emergency physician**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

**Rule ID:** RF_RESP_FAILURE_001  

**Headline:** The rule currently only flags patients who are *unable to speak sentences*, have *stridor*, or are *breathless at rest with altered consciousness*. It therefore misses patients who are **breathless at rest but do not have altered consciousness** (e.g., severe asthma or COPD exacerbation).

### Misses
**Concrete patient example (Rule RF_RESP_FAILURE_001):**

- **Age:** 62 years (male)  
- **Chief complaint:** “I’m having trouble catching my breath. My chest feels tight, and I’m sweating a lot.”  
- **Presenting features:**  
  - **Breathless at rest** – unable to complete a full sentence when asked, “I can’t even talk in short phrases.”  
  - **No altered consciousness** – fully alert, oriented, and able to follow simple commands.  
  - **No stridor** – voice is not hoarse or raspy.  
  - **No chest pain, dyspnea‑related chest pain, or other systemic signs** (no wheeze, no cyanosis, no chest tenderness).  

**Why this patient is missed:**  
The rule’s criteria require **altered consciousness** in addition to breathlessness. A severe asthma/COPD exacerbation can cause marked dyspnea and tachypnea without any change in mental status, so the rule will not fire and the patient will not be terminated from the emergency department.

### Over‑referrals
The rule may also fire on patients who are **unable to speak sentences** (e.g., severe laryngospasm) even when the underlying problem is not a true respiratory compromise (e.g., a vocal‑cord injury). This could lead to unnecessary termination of the emergency encounter for patients who are merely hoarse or have a temporary voice loss.

### The case for leaving it alone
The rule is designed to capture **life‑threatening respiratory compromise** (e.g., impending cardiac arrest, severe bronchospasm with impending hypoxemia). If the clinician believes that **any** patient who is breathless at rest and fully conscious is not a true emergency, the rule could be considered overly restrictive. However, in practice, many patients with severe asthma or COPD exacerbations present exactly as described above and would be at risk of delayed treatment if the rule does not fire.

### Outside my seat
- **Schema gap:** The rule does not incorporate **breathing rate** or **oxygen saturation** thresholds, which are commonly used in emergency protocols to define “severe dyspnea.” Adding these predicates would allow the rule to capture patients who are breathless but not yet altered.  
- **Potential integration with other rules:** The rule could be combined with a rule for **severe asthma/COPD exacerbation** (e.g., `asthma_worsening_present`) to trigger escalation without firing on every breathless patient.

### The one decision I would put to a clinician
**Should the rule be expanded to include “breathless at rest without altered consciousness” as a trigger for termination, or should it remain limited to the current three criteria to avoid over‑referral on patients with severe asthma/COPD exacerbations?** This decision hinges on the balance between preventing missed life‑threatening respiratory compromise and avoiding unnecessary termination of otherwise stable patients.

---

**Safety Engineer Review**

**Headline:** The rule can miss patients who develop respiratory compromise from causes other than altered consciousness (e.g., severe asthma exacerbation or anaphylaxis) and may incorrectly terminate care for presentations that do not meet the full set of criteria.

**Misses**

**Patient 1 – Severe Asthma Exacerbation (Non‑COPD Obstructive Airway Disease)**  
- **Age / Sex:** 42‑year‑old male, no age‑specific predicate needed.  
- **Presentation:** Sudden wheeze, tachypnea, markedly increased work of breathing. He is **unable_to_speak_sentences = true** and **stridor_present = true**.  
- **Comorbidities:** No known diabetes, heart disease, or chest‑pain history that would trigger the “breathless_at_rest AND altered_consciousness_present” branch.  
- **Why it fails:** The rule’s respiratory‑compromise criteria are overly restrictive; anaphylaxis meets the “unable_to_speak_sentences AND stridor_present” branch but does not require altered consciousness, so the rule will not trigger and the patient may receive insufficient emergency care.

**Patient 2 – Anaphylaxis (Allergic Reaction)**  
- **Age / Sex:** 28‑year‑old female, no age‑specific predicate needed.  
- **Presentation:** Develops sudden dyspnea, wheeze, facial swelling, and hypotension. She is **unable_to_speak_sentences = true** and **stridor_present = true** (due to airway edema).  
- **Comorbidities:** No chest‑pain, no known heart disease, and no altered consciousness (consciousness is intact).  
- **Why it fails:** The rule will not fire because the underlying cause (anaphylaxis) does not meet the “altered_consciousness_present” requirement, potentially leading to inadequate emergency treatment.

**Over‑referrals**

**Patient 3 – Mild COPD Exacerbation with No Altered Consciousness**  
- **Age / Sex:** 65‑year‑old male, no age‑specific predicate needed.  
- **Presentation:** Mild dyspnea, productive cough, wheeze, but remains fully conscious (altered_consciousness_present = false). He is **unable_to_speak_sentences = true** and **stridor_present = true** (due to bronchospasm).  
- **Why it fires:** The rule will terminate the emergency session, potentially leading to unnecessary escalation to ICU or intubation when the patient’s condition is manageable with supplemental oxygen and bronchodilators.

**The case for leaving it alone**

The rule’s design reflects a conservative safety margin by requiring **altered consciousness** alongside respiratory distress, which aligns with protocols that prioritize treating patients who are already in a compromised neurologic state (e.g., cardiac arrest or severe hypoxemia). If the clinical context is one where altered consciousness is a reliable indicator of imminent respiratory failure (e.g., in a setting where anaphylaxis is rare or not recognized), the rule’s behavior may be acceptable. However, this assumption is not universally valid across all patient populations and settings.

**Outside my seat**

- **Schema Gap:** The rule does not incorporate a predicate for **“severe bronchospasm”** or **“anaphylaxis.”** Adding such predicates would require schema changes (e.g., a new “allergy_reaction_present” or “severe_copd_exacerbation_present”) and corresponding data capture in the EMR.  
- **Potential Interaction with Other Rules:** If another rule (e.g., RF_RESP_FAILURE_002 for “severe asthma”) is active, the current rule may never fire, leading to a cascade of missed interventions. Cross‑rule dependency analysis is needed to ensure that respiratory‑compromise detection is not duplicated or mutually exclusive.

**The one decision I would put to a clinician**

**Should the rule be expanded to include respiratory‑compromise criteria that do not require altered consciousness (e.g., severe wheeze + inability to speak sentences + stridor), thereby reducing the risk of missing anaphylaxis and severe asthma exacerbations while still maintaining a safety threshold for patients who are already neurologically compromised?**  

If the answer is affirmative, the clinician should consider adding a secondary branch (e.g., “unable_to_speak_sentences AND stridor_present”) that triggers termination regardless of consciousness status, and then evaluate the impact on over‑referral rates in the target population. If the answer is negative, the rule should remain as‑is, with a clear documentation of its limitations and the need for supplemental clinical judgment when patients present with respiratory distress but intact consciousness.

---

**Indian Practice Reviewer**

**Headline:** The rule RF_RESP_FAILURE_001 is likely to miss patients with respiratory compromise caused by atypical presentations such as severe dyspnoea without altered consciousness, which are common in the Indian population.

### Misses

**Concrete patient example (58‑year‑old male, rural district hospital):**

- **Age:** 58 years (age_over_50)  
- **Presentation:** Sudden onset of severe dyspnoea at rest, unable to speak full sentences, no stridor, no altered consciousness.  
- **Key features:** No chest pain, no wheeze, no fever, no recent trauma. Dyspnoea is present even while resting in bed, and the patient is not yet hypoxic enough to meet the “altered_consciousness_present” criterion.  
- **Why it fails the rule:** The rule fires only if **breathless_at_rest **AND **altered_consciousness_present** occur together. This patient meets the breathlessness criterion but lacks altered consciousness, so the rule will not terminate the emergency session.  
- **Potential outcome:** The patient may be discharged or transferred to a lower‑level facility before the respiratory compromise is recognized, leading to delayed definitive care.

### Over‑referrals

**Concrete patient example (diabetic patient):**

- **Age:** 55 years (age_over_40)  
- **Comorbidity:** Type 2 diabetes mellitus, poorly controlled.  
- **Presentation:** Mild dyspnoea at rest, no stridor, no altered consciousness, no chest pain.  
- **Why the rule fires:** The rule’s criteria are broad enough that many non‑cardiac conditions (e.g., severe COPD exacerbation, pulmonary edema) can satisfy the “breathless_at_rest” condition, especially when accompanied by other systemic signs (e.g., cough, fever). In a diabetic population, respiratory infections are common, and the rule may therefore fire on patients who do not truly require emergency termination.  
- **Potential cost:** Unnecessary termination of the emergency session could divert resources from patients with true acute coronary syndrome or other life‑threatening conditions, increasing wait times and resource strain in the district hospital.

### The case for leaving it alone

The rule is derived from Western emergency‑medicine guidelines that prioritize classic cardiac presentations (e.g., chest pain, dyspnoea with altered mental status). In high‑burden settings like Indian district hospitals, the predominant causes of respiratory compromise are often **non‑cardiac** (e.g., severe COPD exacerbation, pulmonary edema, pneumonia). If the rule were left unchanged, it would **miss** many patients who present with dyspnoea without altered consciousness, potentially delaying life‑saving interventions.

### Outside my seat

- **Cultural and disease‑burden considerations:** The prevalence of chronic obstructive pulmonary disease (COPD) and community‑acquired pneumonia is high in rural India. These conditions frequently present with severe dyspnoea at rest but without altered consciousness, which the current rule does not capture.  
- **Referral network implications:** Emergency departments in district hospitals often have limited capacity and resources. Over‑referral to higher‑level centers for patients who do not meet the strict criteria could lead to unnecessary transfers, increasing patient and family burden and hospital load.

### The one decision I would put to a clinician

**Should the rule be revised to include a broader respiratory‑compromise criterion (e.g., “breathless_at_rest” alone, or add “severe dyspnoea” without requiring altered consciousness), or should it remain as is to avoid over‑referral to non‑cardiac emergencies?**  

This decision will determine whether patients with atypical but still serious respiratory compromise are appropriately triaged and whether resources are allocated efficiently across the referral network.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule currently only flags patients who are *unable to speak sentences*, have *stridor*, or are *breathless at rest with altered consciousness*. It therefore misses patients who are **breathless at rest but do not have altered consciousness** (e.g., due to severe asthma or COPD exacerbation).

### Misses
**Concrete patient example (Rule RF_RESP_FAILURE_001):**

- **Age:** 62 years (male)  
- **Chief complaint:** “I’m having trouble catching my breath. My chest feels tight, and I’m sweating a lot.”  
- **Presenting features:**  
  - **Breathless at rest** – unable to complete a full sentence when asked, “I can’t even talk in short phrases.”  
  - **No altered consciousness** – fully alert, oriented, and able to follow simple commands.  
  - **No stridor** – voice is not hoarse or raspy.  
  - **No chest pain, dyspnea‑related chest pain, or other systemic signs** (no wheeze, no cyanosis, no chest tenderness).  

**Why this patient is missed:**  
The rule’s criteria require **altered consciousness** in addition to breathlessness. A severe asthma/COPD exacerbation can cause marked dyspnea and tachypnea without any change in mental status, so the rule will not fire and the patient will not be terminated from the emergency department.

### Over‑referrals
The rule may also fire on patients who are **unable to speak sentences** (e.g., severe laryngospasm) even when the underlying problem is not a true respiratory compromise (e.g., a vocal‑cord injury). This could lead to unnecessary termination of the emergency encounter for patients who are merely hoarse or have a temporary voice loss.

### The case for leaving it alone
The rule is designed to capture **life‑threatening respiratory compromise** (e.g., impending cardiac arrest, severe bronchospasm with impending hypoxemia). If the clinician believes that **any** patient who is breathless at rest and fully conscious is not a true emergency, the rule could be considered overly restrictive. However, in practice, many patients with severe asthma or COPD exacerbations present exactly as described above and would be at risk of delayed treatment if the rule does not fire.

### Outside my seat
- **Schema gap:** The rule does not incorporate **breathing rate** or **oxygen saturation** thresholds, which are commonly used in emergency protocols to define “severe dyspnea.” Adding these predicates would allow the rule to capture patients who are breathless but not yet altered.
- **Potential integration with other rules:** The rule could be combined with a rule for **severe asthma/COPD exacerbation** (e.g., `asthma_worsening_present`) to trigger escalation without firing on every breathless patient.

### The one decision I would put to a clinician
**Should the rule be expanded to include “breathless at rest without altered consciousness” as a trigger for termination, or should it remain limited to the current three criteria to avoid over‑referral on patients with severe asthma/COPD exacerbations?** This decision hinges on the balance between preventing missed life‑threatening respiratory compromise and avoiding unnecessary termination of otherwise stable patients.

### safety engineer

**Headline:** The rule can miss patients who develop respiratory compromise from causes other than altered consciousness (e.g., severe asthma exacerbation or anaphylaxis) and may incorrectly terminate care for presentations that do not meet the full set of criteria.

**Misses**

**Patient 1 – Severe Asthma Exacerbation (Non‑COPD Obstructive Airway Disease)**  
- **Age / Sex:** 42‑year‑old male, no age‑specific predicate needed.  
- **Presentation:** Presents with sudden wheeze, tachypnea, and markedly increased work of breathing. He is unable to speak full sentences (unable_to_speak_sentences = true) and has **stridor_present = true**.  
- **Comorbidities:** No known diabetes, heart disease, or chest‑pain history that would trigger the “breathless_at_rest AND altered_consciousness_present” branch.  
- **Why it fails:** The rule’s respiratory‑compromise branch is anchored on **altered_consciousness_present**, which is absent in a typical severe asthma attack. Consequently, the rule will not fire, and the patient may be discharged or transferred to a lower‑acuity setting before full respiratory support is provided.  

**Patient 2 – Anaphylaxis (Allergic Reaction)**  
- **Age / Sex:** 28‑year‑old female, no age‑specific predicate needed.  
- **Presentation:** Develops sudden dyspnea, wheeze, facial swelling, and hypotension. She is **unable_to_speak_sentences = true** and **stridor_present = true** (due to airway edema).  
- **Comorbidities:** No chest‑pain, no known heart disease, and no altered consciousness (consciousness is intact).  
- **Why it fails:** The rule’s respiratory‑compromise criteria are overly restrictive; anaphylaxis meets the “unable_to_speak_sentences AND stridor_present” branch but does not require altered consciousness, so the rule will not trigger and the patient may receive insufficient emergency care.  

**Over‑referrals**

**Patient 3 – Mild COPD Exacerbation with No Altered Consciousness**  
- **Age / Sex:** 65‑year‑old male, no age‑specific predicate needed.  
- **Presentation:** Mild dyspnea, productive cough, wheeze, but remains fully conscious (altered_consciousness_present = false). He is **unable_to_speak_sentences = true** and **stridor_present = true** (due to bronchospasm).  
- **Why it fires:** The rule will terminate the emergency session, potentially leading to unnecessary escalation to ICU or intubation when the patient’s condition is manageable with supplemental oxygen and bronchodilators.  

**The case for leaving it alone**

The rule’s design reflects a conservative safety margin by requiring **altered_consciousness_present** alongside respiratory distress, which aligns with protocols that prioritize treating patients who are already in a compromised neurologic state (e.g., cardiac arrest or severe hypoxemia). If the clinical context is one where altered consciousness is a reliable indicator of imminent respiratory failure (e.g., in a setting where anaphylaxis is rare or not recognized), the rule’s behavior may be acceptable. However, this assumption is not universally valid across all patient populations and settings.

**Outside my seat**

- **Schema Gap:** The rule does not incorporate a predicate for **“severe bronchospasm”** or **“anaphylaxis”**, which are common causes of respiratory compromise that do not involve altered consciousness. Adding such predicates would require schema changes (e.g., a new “allergy_reaction_present” or “severe_copd_exacerbation_present”) and corresponding data capture in the EMR.  
- **Potential Interaction with Other Rules:** If another rule (e.g., RF_RESP_FAILURE_002 for “severe asthma”) is active, the current rule may never fire, leading to a cascade of missed interventions. Cross‑rule dependency analysis is needed to ensure that respiratory‑compromise detection is not duplicated or mutually exclusive.

**The one decision I would put to a clinician**

**Should the rule be expanded to include respiratory‑compromise criteria that do not require altered consciousness (e.g., severe wheeze + inability to speak sentences + stridor), thereby reducing the risk of missing anaphylaxis and severe asthma exacerbations while still maintaining a safety threshold for patients who are already neurologically compromised?**  

If the answer is affirmative, the clinician should consider adding a secondary branch (e.g., “unable_to_speak_sentences AND stridor_present”) that triggers termination regardless of consciousness status, and then evaluate the impact on over‑referral rates in the target population. If the answer is negative, the rule should remain as‑is, with a clear documentation of its limitations and the need for supplemental clinical judgment when patients present with respiratory distress but intact consciousness.

### Indian practice reviewer

**Headline:** The rule RF_RESP_FAILURE_001 is likely to miss patients with respiratory compromise caused by atypical presentations such as severe dyspnoea without altered consciousness, which are common in the Indian population.

### Misses
**Concrete patient example (58‑year‑old male, rural district hospital):**

- **Age:** 58 years (age_over_50)
- **Presentation:** Sudden onset of severe dyspnoea at rest, unable to speak full sentences, no stridor, no altered consciousness.
- **Key features:** No chest pain, no wheeze, no fever, no recent trauma. Dyspnoea is present even while resting in bed, and the patient is not yet hypoxic enough to meet the “altered consciousness” criterion.
- **Why it fails the rule:** The rule fires only if **breathless_at_rest **AND **altered_consciousness_present** occur together. This patient meets the breathlessness criterion but lacks altered consciousness, so the rule will not terminate the emergency session.
- **Potential outcome:** The patient may be discharged or transferred to a lower‑level facility before the respiratory compromise is recognized, leading to delayed definitive care.

### Over‑referrals
**Concrete patient example (diabetic patient):**

- **Age:** 55 years (age_over_40)
- **Comorbidity:** Type 2 diabetes mellitus, poorly controlled.
- **Presentation:** Mild dyspnoea at rest, no stridor, no altered consciousness, no chest pain.
- **Why the rule fires:** The rule’s criteria are broad enough that many non‑cardiac conditions (e.g., severe COPD exacerbation, pulmonary edema) can satisfy the “breathless_at_rest” condition, especially when accompanied by other systemic signs (e.g., cough, fever). In a diabetic population, respiratory infections are common, and the rule may therefore fire on patients who do not truly require emergency termination.
- **Potential cost:** Unnecessary termination of the emergency session could divert resources from patients with true acute coronary syndrome or other life‑threatening conditions, increasing wait times and resource strain in the district hospital.

### The case for leaving it alone
The rule is derived from Western emergency‑medicine guidelines that prioritize classic cardiac presentations (e.g., chest pain, dyspnoea with altered mental status). In high‑burden settings like Indian district hospitals, the predominant causes of respiratory compromise are often **non‑cardiac** (e.g., severe COPD exacerbation, pulmonary edema, pneumonia). If the rule were left unchanged, it would **miss** many patients who present with dyspnoea without altered consciousness, potentially delaying life‑saving interventions.

### Outside my seat
- **Cultural and disease‑burden considerations:** The prevalence of chronic obstructive pulmonary disease (COPD) and community‑acquired pneumonia is high in rural India. These conditions frequently present with severe dyspnoea at rest but without altered consciousness, which the current rule does not capture.
- **Referral network implications:** Emergency departments in district hospitals often have limited capacity and resources. Over‑referral to higher‑level centers for patients who do not meet the strict criteria could lead to unnecessary transfers, increasing patient and family burden and hospital load.

### The one decision I would put to a clinician
**Should the rule be revised to include a broader respiratory‑compromise criterion (e.g., “breathless_at_rest” alone, or add “severe dyspnoea” without requiring altered consciousness), or should it remain as is to avoid over‑referral to non‑cardiac emergencies?** This decision will determine whether patients with atypical but still serious respiratory compromise are appropriately triaged and whether resources are allocated efficiently across the referral network.
