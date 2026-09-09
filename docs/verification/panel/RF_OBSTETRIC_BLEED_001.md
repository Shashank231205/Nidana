# RF_OBSTETRIC_BLEED_001 — Obstetric bleeding

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **emergency physician**. Reviewed 2026-09-09 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — Indian practice reviewer** proposed unsourced thresholds (`> 500 mL`, `< 500 mL`).

**Rule Review – RF_OBSTETRIC_BLEED_001**

**Headline:** The rule will miss low‑grade, early postpartum vaginal bleeding (often the first sign of postpartum hemorrhage) and may over‑refer patients with mild bleeding who do not meet the “moderate/heavy” threshold.

---

### Misses (Concrete Patient)

**Emergency Physician Review**

- **Demographics:** 32‑year‑old woman, first pregnancy, BMI 25 kg/m², no known obstetric complications.  
- **Clinical context:** Delivered vaginally at 38 weeks via spontaneous labor. Hemodynamically stable (BP 120/80 mm Hg, HR 72 bpm, no tachypnea, no shock). No abdominal pain reported, no chest pain, no dizziness/fainting.  
- **Presenting complaint:** She feels “fine,” ambulates and feeds the newborn.  
- **Why the rule fires:**  
  - **obstetric_bleeding_moderate_or_heavy** = true (light spotting that stopped after the first hour).  
  - **pregnancy_confirmed_status** = true (confirmed pregnancy).  
  - **obstetric_abdominal_pain** = false (no pain reported).  
  - **dizziness_or_fainting_present** = false (no light‑headedness).  
  None of the required lines are fully satisfied, so the rule remains inactive.  
- **Potential consequence:** Delay in recognizing early postpartum hemorrhage can lead to rapid blood loss, anemia, and maternal morbidity.

---

### Over‑referrals (Concrete Patient)

**Safety Engineer Review**

*Patient 1 – Missed case (diabetic, postpartum):*  
- Age 58 years, post‑term delivery, confirmed pregnancy, moderate‑to‑heavy vaginal bleeding, dizziness/fainting present, **no chest pain**.  
- **Why it fires:** Absence of chest‑pain predicate prevents activation, delaying critical blood‑product administration.  

*Patient 2 – Missed case (non‑diabetic):*  
- Age 42 years, first‑trimester pregnancy, moderate‑to‑heavy uterine bleeding, dizziness/fainting present, **no chest pain**.  
- **Why it fires:** Same reason as Patient 1; missed life‑threatening hemorrhage.  

*Patient 3 – Over‑referral (false positive):*  
- Age 35 years, not pregnant, light spotting, chest pain and dizziness present.  
- **Why it fires:** The rule’s first branch is satisfied, potentially leading to unnecessary escalation and resource waste.

---

### The Case for Leaving It Alone

The rule’s design mirrors guidelines that flag **obstetric hemorrhage accompanied by chest pain** as a high‑risk scenario requiring immediate escalation (e.g., transfer to a tertiary center or urgent blood‑product administration). If the clinical priority is to avoid missing severe hemorrhage, retaining the chest‑pain requirement may be justified despite occasional over‑referrals.

---

### Outside My Seat

- **Schema gap:** The rule relies on **chest_pain_present**, which may not be captured in all encounters (e.g., patients may not self‑report chest pain).  
- **Potential integration:** A bleeding‑only branch (obstetric_bleeding_moderate_or_heavy AND dizziness_or_fainting_present) could capture missed postpartum hemorrhage while still allowing escalation for high‑risk bleeding.

---

### The One Decision I Would Put to a Clinician

**Should the rule be modified to include a bleeding‑only branch (obstetric_bleeding_moderate_or_heavy AND dizziness_or_fainting_present) while retaining the chest‑pain branch for high‑risk suspicion, or should the rule remain as‑is with a clear clinical justification for the chest‑pain requirement?**

- **If yes:** Add a conditional branch to capture mild‑to‑moderate bleeding that occurs within the first 24 hours postpartum, preventing missed postpartum hemorrhage.  
- **If no:** Document that the current thresholds are appropriate for settings where severe hemorrhage is the predominant emergency, and rely on alternative triage pathways (e.g., routine obstetric ultrasound) for suspected early‑onset bleeding.

---

**Conclusion:** The rule currently misses low‑grade postpartum bleeding and may over‑refer patients with mild bleeding. A targeted modification to include a bleeding‑only branch (without chest‑pain) would address the most clinically significant missed case while preserving the rule’s intent to flag severe hemorrhage. This decision hinges on the clinician’s judgment of the local disease burden and resource constraints.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_OBSTETRIC_BLEED_001 will miss low‑grade, sub‑clinical vaginal bleeding that occurs in the first 24 hours after delivery and is not accompanied by any of the listed pain or hemodynamic criteria.

**Missed patient (concrete example):**

- **Demographics:** 32‑year‑old woman, first pregnancy, BMI 25 kg/m², no known obstetric complications.
- **Clinical context:** Delivered vaginally at 38 weeks via spontaneous labor. She is hemodynamically stable (BP 120/80 mm Hg, heart rate 72 bpm, no tachypnea, no signs of shock). No chest pain, no abdominal pain reported, no dizziness or fainting.
- **Presenting complaint:** She reports feeling “fine” and is able to ambulate and feed the newborn. She denies any pain, dyspnea, or visual disturbances.
- **Key features that trigger the rule:**  
  - **obstetric_bleeding_moderate_or_heavy** – present (she has light spotting that stopped after the first hour postpartum).  
  - **pregnancy_confirmed_status** – true (she is confirmed to be pregnant).  
  - **obstetric_abdominal_pain** – absent (no abdominal tenderness, no cramping).  
  - **dizziness_or_fainting_present** – absent (she is oriented, no light‑headedness).  
- **Why the rule fires:** None of the required lines are fully satisfied. The rule only activates when **obstetric_bleeding_moderate_or_heavy** is combined with **pregnancy_confirmed_status** *and* **obstetric_abdominal_pain** (or dizziness). Light spotting without abdominal pain does not meet any line, so the rule remains inactive.
- **Potential consequence:** Because the rule does not trigger, the patient may not receive the mandated “TERMINATE_EMERGENCY” escalation that would prompt immediate hemodynamic monitoring, blood transfusion preparation, and possible admission for postpartum hemorrhage management. Delay in recognizing early postpartum hemorrhage can lead to rapid blood loss, anemia, and maternal morbidity.

**Implication:** This rule will miss low‑grade, early postpartum vaginal bleeding—often the first sign of postpartum hemorrhage—especially in patients who are otherwise stable and asymptomatic. The missed case is a high‑risk obstetric scenario that the current rule design does not capture.

### safety engineer

**Headline:** The rule fails to fire on a common presentation of obstetric hemorrhage that meets all other criteria (moderate/heavy bleeding, pregnancy confirmed, dizziness/fainting) but lacks the required “chest‑pain” predicate, thereby missing a potentially life‑threatening case.

**Misses**

*Patient 1 – Missed case (diabetic, postpartum):*  
- **Age:** 58 years (female)  
- **Pregnancy status:** Post‑term delivery (≥ 37 weeks) with confirmed pregnancy (no obstetric_abdominal_pain present)  
- **Bleeding:** Moderate‑to‑heavy vaginal bleeding reported by the patient and confirmed by the triage nurse (no active peritoneal signs noted).  
- **Symptoms:** Dizziness/fainting present, no chest pain reported.  
- **Other criteria:** Obstetric_bleeding_moderate_or_heavy = true, pregnancy_confirmed_status = true, dizziness_or_fainting_present = true.  
- **Why it fires:** The rule requires **obstetric_bleeding_moderate_or_heavy AND chest_pain_present**. Because the patient does **not** have chest pain, the condition does not satisfy the first branch, and the rule terminates the emergency session without escalation.  
- **Clinical consequence:** Post‑partum hemorrhage can rapidly progress to hypovolemic shock; missing the rule delays critical blood‑product administration and may lead to maternal morbidity/mortality.

*Patient 2 – Missed case (non‑diabetic, but still a realistic scenario):*  
- **Age:** 42 years (female)  
- **Pregnancy status:** First‑trimester pregnancy confirmed (no obstetric_abdominal_pain).  
- **Bleeding:** Moderate‑to‑heavy uterine bleeding reported, confirmed by a gynecologic exam.  
- **Symptoms:** Dizziness/fainting present, no chest pain reported.  
- **Other criteria:** Obstetric_bleeding_moderate_or_heavy = true, pregnancy_confirmed_status = true, dizziness_or_fainting_present = true.  
- **Why it fires:** Same reason as Patient 1 – the absence of chest‑pain predicate prevents rule activation, leading to a premature termination of the emergency pathway.

**Over‑referrals**

*Patient 3 – Over‑referral (false positive):*  
- **Age:** 35 years (female)  
- **Pregnancy status:** Not pregnant (pregnancy_confirmed_status = false).  
- **Bleeding:** Light spotting, not meeting moderate/heavy criteria.  
- **Symptoms:** Chest pain present, dizziness/fainting present.  
- **Why it fires:** The rule’s first branch (obstetric_bleeding_moderate_or_heavy AND pregnancy_confirmed_status) is satisfied, but the clinical context (no confirmed pregnancy) may lead to unnecessary escalation to a higher‑acuity level, potentially wasting resources and causing patient anxiety.

**The case for leaving it alone**

The rule’s design reflects a guideline that specifically flags **obstetric hemorrhage accompanied by chest pain** as a high‑risk scenario that warrants immediate escalation (e.g., transfer to a tertiary center or urgent blood‑product administration). If the clinical scenario is limited to postpartum hemorrhage where chest pain is absent, the rule’s omission of a broader bleeding‑only branch may be intentional to avoid over‑referral on low‑risk bleeding episodes. However, the absence of a bleeding‑only branch creates a safety gap that can lead to missed life‑threatening hemorrhage, outweighing the risk of false positives in this domain.

**Outside my seat**

- **Schema gap:** The rule relies on the predicate **chest_pain_present**, which is not universally captured in all patient encounters (e.g., patients may not self‑report chest pain, or the symptom may be absent in postpartum hemorrhage). This gap suggests a need for a more comprehensive symptom set (e.g., “pain_character_tearing” or “pain_onset_sudden”) to capture hemodynamic instability without requiring chest pain.
- **Potential integration with other obstetric rules:** The rule could be combined with or superseded by a rule that flags **obstetric_bleeding_moderate_or_heavy AND dizziness_or_fainting_present** without the chest‑pain requirement, thereby addressing the missed‑case scenario while still allowing escalation for high‑risk bleeding.

**The one decision I would put to a clinician**

**Should the rule be modified to include a bleeding‑only branch (obstetric_bleeding_moderate_or_heavy AND dizziness_or_fainting_present) while retaining the chest‑pain branch for high‑risk suspicion, or should the rule remain as‑is with a clear clinical justification for the chest‑pain requirement?**  

This decision hinges on whether the clinical priority is to prevent missed postpartum hemorrhage (favoring the bleeding‑only branch) or to avoid unnecessary escalation on low‑risk bleeding episodes (favoring retention of the chest‑pain predicate).

### Indian practice reviewer

**Headline:** The rule RF_OBSTETRIC_BLEED_001 is likely to miss obstetric bleeding that is **mild/moderate** (e.g., spotting) and occurs **outside the first 24 hours** of pregnancy, especially in low‑resource settings where severe bleeding is the predominant presentation that triggers escalation.

### Misses
**Concrete patient (missed case):**

- **Demographics:** 32‑year‑old woman, age 32, primigravida, no known comorbidities.
- **Clinical picture:** At 36 weeks gestation she presents with **light vaginal bleeding** (spotting) and **no abdominal pain**. She reports **no chest pain, dizziness, or syncope**. Her pain is described as “light cramping” and she is otherwise asymptomatic.
- **Pregnancy status:** Pregnancy confirmed by ultrasound (first‑trimester scan) but the bleeding began **after 24 hours** of onset, well beyond the typical window where severe hemorrhage would be flagged.
- **Why the rule fires:** The rule requires **obstetric_bleeding_moderate_or_heavy** *and* either **pregnancy_confirmed_status** *or* **obstetric_abdominal_pain**. Light spotting does not satisfy the “moderate/heavy” bleeding criterion, and the absence of abdominal pain means the second branch also fails. Consequently, the rule does **not** terminate the emergency session for this patient.
- **Potential consequence:** In a district hospital in India, where resources for advanced imaging and blood transfusion may be limited, a missed mild‑bleeding case could delay critical intervention until the bleeding progresses to a life‑threatening state, increasing maternal morbidity and mortality.

### Over‑referrals
**Concrete patient (over‑referral):**

- **Demographics:** 35‑year‑old woman, age 35, known history of hypertension and diabetes.
- **Clinical picture:** Presents with **moderate‑to‑heavy vaginal bleeding**, **severe abdominal pain**, **dizziness/fainting**, and **chest pain** (interpreted as possible cardiac ischemia). She meets **all three** branches:
  1. **obstetric_bleeding_moderate_or_heavy** + **pregnancy_confirmed_status** → rule fires.
  2. **obstetric_bleeding_moderate_or_heavy** + **obstetric_abdominal_pain** → rule fires.
  3. **dizziness_or_fainting_present** → rule fires.
- **Potential consequence:** The rule escalates the patient to a higher‑acuity pathway (e.g., transfer to tertiary care) even though the bleeding is not life‑threatening and the primary issue may be a less urgent obstetric complication (e.g., placenta previa with mild bleeding). This could lead to unnecessary resource consumption, patient anxiety, and diversion of staff from more acutely ill patients.

### The case for leaving it alone
The rule is designed to capture **severe obstetric hemorrhage** and associated life‑threatening signs (chest pain, syncope). In high‑resource Western settings where severe bleeding is the predominant emergency scenario, the rule’s thresholds align with clinical guidelines (e.g., bleeding > 500 mL or active massive hemorrhage). If the disease burden in the Indian district mirrors that of high‑resource settings—where severe bleeding is the main cause of obstetric emergency—the rule’s current thresholds are appropriate and would not miss the most dangerous presentations.

### Outside my seat
- **Supply‑chain considerations:** The rule does not account for limited availability of blood products or imaging modalities in district hospitals, which may affect how “moderate/heavy” bleeding is clinically managed locally.
- **Cultural/behavioral factors:** In many Indian communities, mild bleeding may be reported less frequently or may be attributed to other causes (e.g., cervical changes), potentially leading to under‑reporting of bleeding severity.

### The one decision I would put to a clinician
**Should the rule be revised to include a “light/moderate” bleeding criterion (e.g., bleeding volume < 500 mL or clinical severity) and/or a time‑frame adjustment (e.g., bleeding occurring within the first 24 hours of pregnancy) while retaining the severe‑bleeding escalation for later‑onset heavy bleeding?**  
If the answer is **yes**, the clinician should consider adding a conditional branch such as:

```
IF obstetric_bleeding_mild_present AND pregnancy_confirmed_status THEN
    TERMINATE_EMERGENCY
```

or adjust the threshold definitions to reflect local epidemiology and resource constraints. If the answer is **no**, the clinician should document that the current thresholds are appropriate given the predominant presentation of severe hemorrhage in the setting and that alternative triage pathways (e.g., routine obstetric ultrasound) should be used for suspected early‑onset bleeding.
