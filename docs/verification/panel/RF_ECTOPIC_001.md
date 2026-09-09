# RF_ECTOPIC_001 — Possible ectopic pregnancy

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **Specialty: Obstetrics/Gynecology**. Reviewed 2026-09-09 by granite4.1:3b (panel 1.0.0).

> **Warning — safety engineer** was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — Indian practice reviewer** proposed unsourced thresholds (`over 3 days`); was cut off before finishing, so what survives reads more one-sided than it was.

## RF_ECTOPIC_001 – Panel Brief

**Headline:** The rule will miss ectopic pregnancies that present with atypical pain (e.g., epigastric or shoulder‑tip pain) and vaginal bleeding, especially in patients with a history of tubal surgery or prior PID, and may over‑refer patients who do not truly have an ectopic pregnancy.

### Misses
**Concrete patient example (58‑year‑old woman):**  
- **Demographics & History:** 58‑year‑old woman with a known history of prior tubal surgery (salpingectomy) for PID. She is otherwise healthy, no documented obstetric complications.  
- **Current Presentation (2 am):** She experiences **shoulder‑tip (referred) pain radiating to the left arm**, dizziness, and light‑headedness. She reports **no abdominal or obstetric abdominal pain** on questioning. Vaginal bleeding is present (light spotting) but she denies any “abdominal pain reported” or “obstetric abdominal pain.”  
- **Why the rule fails:** The rule requires **abdominal_pain_reported** (or “obstetric abdominal pain”) together with **pregnancy_possible_or_confirmed**. This patient’s pain is **shoulder‑tip pain**, which is not captured by the rule’s pain criteria, and she meets the pregnancy‑possible criterion (prior tubal surgery). Consequently, the rule will **not fire**, and the emergency department will not escalate to termination of the emergency session despite a likely life‑threatening ectopic pregnancy.

### Over‑referrals
**Potential over‑referral:** Patients who present with chest pain or shoulder‑tip pain but do **not** have a true ectopic pregnancy (e.g., myocardial infarction, tension pneumothorax) may satisfy the rule’s first branch (`abdominal_pain_reported AND pregnancy_possible_or_confirmed`) without a genuine ectopic condition, leading to premature termination of the emergency session and possible delay in definitive care for a non‑ectopic condition.

### The case for leaving it alone
The rule is designed to catch ectopic pregnancies that are **obvious** (painful, with vaginal bleeding). In many clinical settings, ectopic pregnancies are often accompanied by **obvious abdominal pain** (cramping, tenderness) and **vaginal bleeding**. The majority of patients who present with an ectopic pregnancy will satisfy at least one of the rule’s branches, so the rule is likely to **detect the majority of clinically significant cases**. The primary limitation is the **absence of shoulder‑tip pain** as a trigger, which is a recognized presentation in patients with tubal‑related ectopics, especially after prior tubal surgery.

### Outside my seat
- **Schema gap:** The rule relies on the existence of the `abdominal_pain_reported` predicate, which may not capture all forms of ectopic pain (e.g., referred shoulder pain). If the system’s data model does not map shoulder‑tip pain to this predicate, the rule will remain silent for a subset of patients.  
- **Clinical nuance:** Ectopic pregnancies in women with prior tubal surgery often present with **shoulder‑tip pain** and **light‑headedness** due to intra‑abdominal pressure, without overt abdominal pain. This nuance is not reflected in the rule’s criteria.

### The one decision I would put to a clinician
**Should the rule be expanded to include “shoulder‑tip pain present” (or “referred shoulder pain”) as an alternative trigger for ectopic pregnancy detection, especially in patients with a history of tubal surgery or prior ectopic pregnancy?**  
If **yes**, the clinician should consider adding a fourth branch:  

`shoulder_tip_pain_present AND sex_female AND pregnancy_possible_or_confirmed`, ensuring that patients with tubal‑related ectopics are not missed. If **no**, the clinician should document the risk of missed tubal ectopics and consider alternative triage pathways for patients with prior tubal surgery presenting with shoulder‑tip pain.

---

## Disagreements (Safety Engineer vs. Indian Practice Reviewer)

### Safety Engineer Position
- **Missed‑case risk:** The rule’s reliance on specific pain descriptors and bleeding signs creates a high likelihood of missing ectopic pregnancies that present without those features—particularly in populations where atypical presentations are common.
- **Over‑referral risk:** The rule’s broad acceptance of chest pain alone can trigger escalation for atypical presentations that do not require emergency termination, potentially wasting resources and exposing patients to unnecessary interventions.

### Indian Practice Reviewer Position
- **Missed‑case risk:** The rule fails to fire on a common presentation of ectopic pregnancy in low‑resource Indian settings—painless, sub‑acute vaginal bleeding in a woman with a confirmed pregnancy, which is often managed safely in the community rather than escalated to emergency termination.
- **Potential harm:** Delayed escalation could lead to rupture, hemorrhage, and maternal morbidity, especially given limited access to tertiary care and the high prevalence of delayed presentation due to cultural and economic barriers.

### What the choice turns on
- **Clinical context vs. symptom specificity:** Whether the rule should prioritize **painful abdominal symptoms** (as in Western guidelines) or broaden to include **painless vaginal bleeding** in confirmed pregnancies (as observed in Indian district hospitals).  
- **Resource implications:** Balancing the need to avoid missed ectopic pregnancies against the cost of unnecessary emergency escalation in settings where many ectopics are managed expectantly.

---

## Refer to
- **Specialty:** Obstetrics/Gynecology (with a focus on low‑resource clinical practice).  
- **Reason:** The rule’s design and the observed clinical patterns differ significantly between high‑resource and Indian district‑hospital environments, necessitating a review by clinicians familiar with local practice patterns and disease prevalence.

---

**Note:** The panel has not verified this rule. It remains blocked from release and requires a named clinician to approve any modifications.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_ECTOPIC_001 will miss ectopic pregnancies that present with atypical pain (e.g., epigastric or shoulder‑tip pain) and vaginal bleeding, but lack the specific “abdominal pain reported” or “obstetric abdominal pain” wording, especially in patients with a history of cervical insufficiency or prior tubal surgery.

### Misses
**Concrete patient example (58‑year‑old woman):**

- **Demographics & History:** 58‑year‑old woman with a known history of prior tubal surgery (salpingectomy) for PID. She is otherwise healthy, no known contraindications to pregnancy, and has no documented obstetric complications.
- **Current Presentation (2 am):** She presents with **shoulder‑tip (referred) pain** radiating to the left arm, **dizziness**, and **light‑headedness**. She reports **no abdominal or obstetric abdominal pain** on questioning. Vaginal bleeding is present (light spotting) but she denies any “abdominal pain reported” or “obstetric abdominal pain.”
- **Key Features Missing from Rule:**  
  - The rule requires **abdominal pain reported** (or “obstetric abdominal pain”) together with **pregnancy possible or confirmed**.  
  - This patient’s pain is **shoulder‑tip pain** (referred pain from the ectopic site) and **no abdominal pain** is reported.  
  - She meets the pregnancy‑possible criterion (prior tubal surgery) but the rule’s pain criteria are not satisfied.
- **Result of Rule:** Because the rule’s first three branches all fail (no abdominal pain reported, no obstetric abdominal pain, and no vaginal bleeding reported), the rule will **not fire**, and the emergency department will not escalate to termination of the emergency session despite a likely life‑threatening ectopic pregnancy.

### Over‑referrals
The rule’s design also creates a risk of **over‑referral** for patients who have other conditions that present with chest pain or shoulder‑tip pain (e.g., myocardial infarction, tension pneumothorax) but do not have the required abdominal pain component. If a patient presents with chest pain, shoulder‑tip pain, and no abdominal pain, the rule may fire unnecessarily, leading to premature termination of the emergency session and possible delay in definitive care for a non‑ectopic condition.

### The case for leaving it alone
The rule is intended to catch ectopic pregnancies that are **obvious** (painful, with vaginal bleeding). In many clinical settings, ectopic pregnancies are often accompanied by **obvious abdominal pain** (cramping, tenderness) and **vaginal bleeding**. The majority of patients who present with an ectopic pregnancy will satisfy at least one of the rule’s branches, so the rule is likely to **detect the majority of clinically significant cases**. The primary limitation is the **absence of shoulder‑tip pain** as a trigger, which is a recognized presentation in patients with tubal ectopics, especially after prior tubal surgery.

### Outside my seat
- **Schema gap:** The rule relies on the existence of the `abdominal_pain_reported` predicate, which may not capture all forms of ectopic pain (e.g., referred shoulder pain). If the system’s data model does not map shoulder‑tip pain to this predicate, the rule will remain silent for a subset of patients.
- **Clinical nuance:** Ectopic pregnancies in women with prior tubal surgery often present with **shoulder‑tip pain** and **light‑headedness** due to intra‑abdominal pressure, without overt abdominal pain. This nuance is not reflected in the rule’s criteria.

### The one decision I would put to a clinician
**Should the rule be expanded to include “shoulder‑tip pain present” (or “referred shoulder pain”) as an alternative trigger for ectopic pregnancy detection, especially in patients with a history of tubal surgery or prior ectopic pregnancy?**  
If yes, the clinician should consider adding a fourth branch:  
`shoulder_tip_pain_present AND sex_female AND pregnancy_possible_or_confirmed`, ensuring that patients with tubal‑related ectopics are not missed. If no, the clinician should document the risk of missed tubal ectopics and consider alternative triage pathways for patients with prior tubal surgery presenting with shoulder‑tip pain.

### safety engineer

**Headline:** The rule can miss ectopic pregnancies that present without classic chest‑pain or shoulder‑tip pain, especially in patients who have no vaginal bleeding or abdominal pain reported, and it may fire on atypical presentations that are not truly indicative of an ectopic pregnancy.

**Misses**

**Patient 1 – Missed case (diabetic, rural‑India presentation):**  
- **Demographics:** 58‑year‑old woman, diabetic for 12 years, age 58 (outside the age‑under‑18/under‑5 thresholds).  
- **Clinical picture:** Two hours of diffuse epigastric discomfort she describes as “indigestion” or “heartburn,” with mild nausea and sweating. No pain she would call “chest pain.” No vaginal bleeding reported.  
- **Why it fails the rule:**  
  1. **Pain criterion:** Neither `abdominal_pain_reported` nor `obstetric_abdominal_pain` is present.  
  2. **Pregnancy indicator:** `pregnancy_possible_or_confirmed` is true (known diabetes → pregnancy status unknown, per author’s note).  
  3. **Other required fields:** `sex_female`, `vaginal_bleeding_reported` (false), `shoulder_tip_pain_present` (false), `dizziness_or_fainting_present` (false).  
- **Result:** The rule does not fire, and the patient’s ectopic pregnancy would not be escalated to termination of emergency care, potentially delaying life‑saving management.

**Patient 2 – Over‑referral (atypical presentation):**  
- **Demographics:** 45‑year‑old woman, no known pregnancy, but presents with severe epigastric pain radiating to the shoulder, dyspnoea, and syncope.  
- **Clinical picture:** Presents with `chest_pain_present` (tension‑type) and `shoulder_tip_pain_present` (due to diaphragmatic irritation), but **no abdominal pain** or `vaginal_bleeding_reported`. Pregnancy status is unknown (pregnancy_possible_or_confirmed true).  
- **Why it fires:** The rule’s first line (`abdominal_pain_reported AND pregnancy_possible_or_confirmed`) is satisfied by the presence of `chest_pain_present` (interpreted as “abdominal pain” in this rule) and unknown pregnancy status. The patient does **not** have a true ectopic pregnancy, yet the rule escalates to termination of emergency care, leading to unnecessary resource use and potential harm from unnecessary interventions.

**Edge Cases & Interactions**

1. **Unknown pregnancy status:** Because the rule does not require a confirmed pregnancy test, any patient with a positive pregnancy status (even if unknown) will fire if any abdominal‑pain criterion is met, regardless of bleeding or other classic signs. This creates a high false‑positive rate in settings where pregnancy testing is limited or unavailable.

2. **Interaction with other triage rules:** If another rule (e.g., RF_AORTIC_001) also flags for chest pain without bleeding, the combined escalation could lead to duplicate or redundant interventions, increasing workload and risk of iatrogenic complications.

3. **Input validation failures:** If any of the required predicates (`abdominal_pain_reported`, `obstetric_abdominal_pain`, `vaginal_bleeding_reported`) are missing or incorrectly coded (e.g., a typo in `sex_female`), the rule will not fire even when a true ectopic pregnancy is present, leading to missed cases.

**Conclusion for the Safety Engineer**

- **Missed‑case risk:** The rule’s reliance on specific pain descriptors and bleeding signs creates a high likelihood of missing ectopic pregnancies that present without those features—particularly in populations where atypical presentations (e.g., diabetic patients) are common.
- **Over‑referral risk:** The rule’s broad acceptance of chest pain alone can trigger escalation for atypical presentations that do not require emergency termination, potentially wasting resources and exposing patients to unnecessary interventions.
- **Recommendation:** Refine the rule to include a broader set of clinical signs (e.g., rapid heart rate, hemodynamic instability) and to incorporate a pregnancy‑status verification step (e.g., confirm pregnancy via ultrasound or HCG level) before escalating to termination of emergency care. Additionally, add a “pregnancy_status_confirmed” predicate to reduce false positives driven solely by unknown pregnancy status.

### Indian practice reviewer

**Missed Patient (Indian District‑Hospital Context)**  

**Rule ID:** RF_ECTOPIC_001  
**Label:** Possible ectopic pregnancy  
**Action:** TERMINATE_EMERGENCY  

**Headline:** The rule fails to fire on a common presentation of ectopic pregnancy in low‑resource Indian settings – a painless, sub‑acute vaginal bleeding in a woman with a confirmed pregnancy, which is often managed safely in the community rather than escalated to emergency termination.

---

### Constructed Miss – Concrete Patient

| Feature | Details |
|---|---|
| **Patient Profile** | 34‑year‑old woman, resident of a rural district hospital in South‑India. Diagnosed with a confirmed intra‑uterine pregnancy (hCG level 12 000 IU/L, ultrasound shows gestational sac). |
| **Chief Complaint** | “I have a dull ache in my lower abdomen for the past 5 days. No sharp chest pain or shoulder tip pain.” |
| **Vaginal Bleeding** | Light, intermittent spotting (≈ 30 mL) over 3 days, no clots, no heavy bleeding. Bleeding is not associated with cramping. |
| **Other Symptoms** | Mild nausea, no fever, no dizziness or syncope. No chest pain, no shoulder tip pain, no dyspnoea, no vomiting. |
| **Pain Characteristics** | Low‑grade, dull, constant but not severe enough to be described as “painful” or “pressure‑like”. |
| **Pregnancy Status** | Pregnancy confirmed by ultrasound; pregnancy test (β‑hCG) is positive. |
| **Age & Menstrual History** | 34 years old; last menstrual period was 2 weeks ago; no recent miscarriage or abnormal bleeding reported. |
| **Medical History** | No known hypertension, diabetes, or prior ectopic pregnancy. |
| **Current Presentation** | She reports “abdominal pain reported” is **not** present in the symptom narrative; the pain is described as “dull ache” without intensity. |
| **Why the Rule Fires** | The rule requires **abdominal_pain_reported** *and* **pregnancy_possible_or_confirmed**. The pain is not reported as “painful” or “pressure‑like”, so the first criterion is not met. |
| **Why the Rule Misses** | • In many Indian district hospitals, ectopic pregnancies are often managed with expectant monitoring and methotrexate if the ectopic is suspected but not symptomatic. <br>• The clinical presentation (painless vaginal bleeding) is common and may be under‑reported because patients equate any abdominal discomfort with “normal pregnancy” and do not describe it as “pain”. <br>• The rule’s emphasis on “painful” abdominal pain (or shoulder tip pain) excludes a subset of ectopic pregnancies that present without such pain. |
| **Potential Harm** | Delayed escalation could lead to rupture, hemorrhage, and maternal morbidity, especially given limited access to tertiary care and the high prevalence of delayed presentation due to cultural and economic barriers. |

---

### Why This Miss Matters

1. **Disease Burden** – Ectopic pregnancy is a leading cause of maternal mortality in low‑resource settings; many cases present with painless bleeding.
2. **Referral Network** – The patient may be managed locally by a gynecologist or obstetrician who does not routinely escalate every case of confirmed pregnancy with any abdominal discomfort.
3. **Cultural/Reporting Norms** – Indian patients often downplay mild discomfort, leading to under‑reporting of “abdominal pain” in the symptom narrative.
4. **Resource Constraints** – Emergency termination is costly and may not be feasible for all patients, especially in district hospitals where resources are limited.

---

### What the Rule Should Accommodate

- **Alternative Pain Indicators** – Accept “light abdominal discomfort” or “dull ache” as sufficient to trigger the rule when combined with confirmed pregnancy.
- **Bleeding‑Only Criteria** – Recognize painless vaginal bleeding in a confirmed pregnancy as a red flag for ectopic pregnancy, even without explicit pain reporting.
- **Clinical Context** – Incorporate local practice patterns (e.g., expectant management of mild ectopic presentations) to avoid unnecessary emergency escalation.

---

**Conclusion:** The current rule fails to capture a clinically significant subset of ectopic pregnancies—those presenting with painless vaginal bleeding in a confirmed pregnancy—potentially leading to missed diagnoses and increased morbidity in Indian district hospitals. Adjusting the rule to include mild abdominal discomfort (or a broader set of non‑painful signs) would improve safety without over‑referring low‑risk cases.
