# RF_PRE_ECLAMPSIA_001 — Features suggesting pre-eclampsia

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **emergency physician**. Reviewed 2026-09-09 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** was cut off before finishing, so what survives reads more one-sided than it was.

**Rule ID:** RF_PRE_ECLAMPSIA_001  

**Headline:** The rule will miss patients with classic pre‑eclampsia features (headache, visual disturbance, hypertension) who present primarily with epigastric pain and facial/hand swelling—especially when pregnancy status is not confirmed or documented—because the rule only fires on the three exact symptom combinations that include visual disturbance, which many patients with pre‑eclampsia do not experience.

### Misses
**Concrete patient (missed case):**  
- **Demographics:** 34‑year‑old woman, 5 ft 6 in, BMI ≈ 28, no known hypertension, no known diabetes, no known renal disease.  
- **Clinical presentation at 2 am:**  
  - Severe epigastric pain radiating to the right shoulder (typical “epigastric pain” symptom).  
  - Swelling of both hands and face (periorbital edema).  
  - No reported headache, visual disturbances, or abdominal pain.  
  - No pregnancy status reported (the rule assumes “pregnancy_confirmed_status” is true).  
- **Why the rule fires:** None of the three encoded combinations (`obstetric_visual_disturbance + pregnancy_confirmed_status`, `epigastric_pain_present + pregnancy_confirmed_status`, `swelling_face_or_hands_present + obstetric_visual_disturbance`) are satisfied because the patient lacks the required visual‑disturbance component.  
- **Result:** The rule will terminate the emergency session without flagging pre‑eclampsia, potentially delaying critical blood‑pressure monitoring and antenatal care.

### Over‑referrals
**Concrete patient (over‑referral):**  
- **Demographics:** 45‑year‑old woman, post‑partum.  
- **Clinical presentation:** Chest pain present, swelling of face and hands, and visual disturbance (e.g., headache, photophobia).  
- **Result:** The rule would fire and terminate the emergency session, even though the presentation is more likely related to postpartum complications (e.g., postpartum haemorrhage, pulmonary edema). This demonstrates that the rule’s symptom set is not specific enough to pre‑eclampsia and may lead to unnecessary termination of care for other serious conditions.

### The case for leaving it alone
The rule could be defended as follows:  
- **Clinical relevance:** Visual disturbances (headache, photophobia) are classic early signs of pre‑eclampsia and are strongly associated with severe disease.  
- **Safety:** Failing to detect visual disturbance may delay critical intervention for severe pre‑eclampsia, which can rapidly progress to eclampsia.  
- **Evidence base:** Published guidelines (e.g., ACOG, WHO) emphasize visual disturbance as a mandatory criterion for pre‑eclampsia diagnosis, even if other symptoms (pain, swelling) are present.

**However**, the rule’s reliance on a single symptom (visual disturbance) that many patients with pre‑eclampsia do not experience (especially in low‑resource settings where visual signs are less prominent) creates a high risk of missing cases. The absence of a blood‑pressure threshold further limits specificity, as hypertension alone does not differentiate pre‑eclampsia from other hypertensive disorders.

### Outside my seat
- **Schema gap:** The rule does not capture the full spectrum of pre‑eclampsia criteria (e.g., proteinuria, severe hypertension) because the system lacks a quantitative blood‑pressure measurement. This gap could be addressed by integrating a blood‑pressure threshold or a severity score if such data become available.  
- **Cultural/setting considerations:** In many low‑resource hospitals, visual disturbances may be absent or misattributed to migraine or ocular strain. The rule’s design may not reflect local clinical practice where pain and swelling are the primary triggers.

### The one decision I would put to a clinician
**Should the rule be revised to include epigastric pain and facial swelling as sufficient criteria for pre‑eclampsia detection when visual disturbance is absent, or should it retain the visual‑disturbance requirement and be complemented by additional severity indicators (e.g., blood pressure, proteinuria) once such data become available?**  

This decision hinges on balancing the need to catch missed cases (e.g., diabetic pre‑eclampsia) against the risk of over‑referral to unrelated emergencies.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule will miss a patient with classic pre‑eclampsia features (headache, visual disturbance, hypertension) who presents with epigastric pain and swelling of the face/hands but **does not report visual disturbance or obstetric visual disturbance**, because the rule only fires on those three specific symptom combinations.

**Missed patient (example):**

- **Demographics:** 34‑year‑old woman, 5 ft 6 in, BMI ≈ 28, no known hypertension, no known diabetes, no known renal disease.
- **Clinical presentation at 2 am:**  
  - Severe epigastric pain radiating to the right shoulder (typical “epigastric pain” symptom).  
  - Swelling of both hands and face (periorbital edema).  
  - No reported headache, visual disturbances, or abdominal pain.  
  - No chest pain, dyspnea, or other acute coronary syndrome features.  
  - No pregnancy status reported (the rule assumes “pregnancy_confirmed_status” is true).  
- **Why the rule fires:** None of the three encoded combinations (`obstetric_visual_disturbance + pregnancy_confirmed_status`, `epigastric_pain_present + pregnancy_confirmed_status`, `swelling_face_or_hands_present + obstetric_visual_disturbance`) are satisfied because the patient lacks the required visual‑disturbance component.  
- **Result:** The rule will terminate the emergency session without flagging pre‑eclampsia, potentially delaying critical blood‑pressure monitoring and antenatal care.

**Implication:** Patients with pre‑eclampsia who present primarily with epigastric pain and facial/hand swelling—especially when pregnancy status is not confirmed or documented—will be missed, leading to delayed diagnosis and management of a potentially life‑threatening condition.

### safety engineer

**Headline:** The rule fails to fire on a common presentation of pre‑eclampsia that meets all symptom criteria but lacks the required “obstetric_visual_disturbance” (visual disturbance) – a presentation that is well‑documented in low‑resource settings and is not captured by the symptom list alone.

### Misses
**Patient 1 – Missed case (diabetic pre‑eclampsia):**  
- **Age:** 38 years (female)  
- **Pregnancy status:** 24 weeks gestation (confirmed by obstetrician)  
- **Comorbidities:** Type 2 diabetes mellitus, hypertension (BP 130/85 mm Hg)  
- **Symptoms:**  
  - Epigastric‑type abdominal pain (radiating to the back) reported as “sharp, pressure‑like” without any mention of chest pain.  
  - Mild swelling of the hands and face (painless, non‑edematous).  
  - No visual disturbances, dizziness, or other obstetric visual signs.  
- **Why it fails:** The rule requires **obstetric_visual_disturbance** (visual disturbance) *and* pregnancy_confirmed_status. This patient has epigastric pain and facial swelling but lacks visual disturbance, so the rule does not fire despite meeting the symptom criteria.

**Patient 2 – Missed case (non‑visual pre‑eclampsia):**  
- **Age:** 25 years (female)  
- **Pregnancy status:** 36 weeks gestation (confirmed)  
- **Comorbidities:** Gestational diabetes, mild hypertension (BP 132/88 mm Hg)  
- **Symptoms:**  
  - Epigastric pain present (no chest pain reported).  
  - Swelling of face and hands (painless).  
  - No visual symptoms (no headache, photophobia, or visual disturbances).  
- **Why it fails:** Same symptom combination as Patient 1 but without the required visual disturbance, so the rule does not trigger.

### Over‑referrals
**Patient 3 – Over‑referral example:**  
- **Age:** 45 years (female)  
- **Pregnancy status:** Not pregnant (post‑partum)  
- **Symptoms:** Chest pain present, swelling of face and hands, and visual disturbance (e.g., headache, photophobia).  
- **Result:** The rule would fire and terminate the emergency session, even though the presentation is not pre‑eclampsia but rather postpartum complications (e.g., postpartum haemorrhage, pulmonary edema). This demonstrates that the rule’s symptom set is not specific enough to pre‑eclampsia and may lead to unnecessary termination of care for other serious conditions.

### The case for leaving it alone
The rule could be defended as follows:
- **Clinical relevance:** Visual disturbances (headache, photophobia) are classic early signs of pre‑eclampsia and are strongly associated with severe disease.  
- **Safety:** Failing to detect visual disturbance may delay critical intervention for severe pre‑eclampsia, which can rapidly progress to eclampsia.  
- **Evidence base:** Published guidelines (e.g., ACOG, WHO) emphasize visual disturbance as a mandatory criterion for pre‑eclampsia diagnosis, even if other symptoms (pain, swelling) are present.  

**However**, the rule’s reliance on a single symptom (visual disturbance) that many patients with pre‑eclampsia do not experience (especially in low‑resource settings where visual signs are less prominent) creates a high risk of missing cases. The absence of a blood‑pressure threshold further limits specificity, as hypertension alone does not differentiate pre‑eclampsia from other hypertensive disorders.

### Outside my seat
- **Schema gap:** The rule does not capture the full spectrum of pre‑eclampsia criteria (e.g., proteinuria, severe hypertension) because the system lacks a quantitative blood‑pressure measurement. This gap could be addressed by integrating a blood‑pressure threshold or a severity score if such data become available.
- **Cultural/setting considerations:** In many low‑resource hospitals, visual disturbances may be absent or misattributed to migraine or ocular strain. The rule’s design may not reflect local clinical practice where pain and swelling are the primary triggers.

### The one decision I would put to a clinician
**Should the rule be revised to include epigastric pain and facial swelling as sufficient criteria for pre‑eclampsia detection when visual disturbance is absent, or should it retain the visual‑disturbance requirement and be complemented by additional severity indicators (e.g., blood pressure, proteinuria) once such data become available?**  

This decision hinges on balancing the need to catch missed cases (e.g., diabetic pre‑eclampsia) against the risk of over‑referral to unrelated emergencies.

### Indian practice reviewer

**Headline:** The rule RF_PRE_ECLAMPSIA_001, as written for a Western emergency setting, will miss a substantial subset of pre‑eclampsia presentations that are common in Indian district hospitals—particularly those with mild or atypical features such as hypertension‑related visual disturbances without severe epigastric pain, and swelling of the face/hands that may be subtle.

### Misses
**Concrete patient (missed case):**  
- **Demographics:** 32‑year‑old woman, age 32, primigravida, BMI ≈ 22 kg/m².  
- **Pregnancy status:** 24 weeks gestation, confirmed by ultrasound (no obstetric visual disturbance reported).  
- **Symptoms:** She reports **headache** (no photophobia), **dizziness** (no syncope), and **mild swelling of the hands** (visible but not prominent). No epigastric pain, no visual disturbances, no severe hypertension signs.  
- **Why it fails:** The rule requires at least one of the three exact symptom combinations:  
  1. *obstetric_visual_disturbance* + *pregnancy_confirmed_status*  
  2. *epigastric_pain_present* + *pregnancy_confirmed_status*  
  3. *swelling_face_or_hands_present* + *obstetric_visual_disturbance*  

  This patient presents **only** with mild swelling of the hands and non‑visual symptoms (headache, dizziness). None of the three exact combinations are satisfied, so the rule does **not** fire, and the patient would not be escalated to a higher‑level facility despite having early signs of pre‑eclampsia.

### Over‑referrals
**Concrete patient (over‑referral):**  
- **Demographics:** 35‑year‑old woman, age 35, known hypertension (BP ≈ 140/90 mmHg) from a previous pregnancy, now 28 weeks gestation.  
- **Symptoms:** Presents with **severe epigastric pain** radiating to the back, **visual disturbances** (blurred vision, mild photophobia), **dizziness**, and **moderate swelling of the hands and face**.  
- **Why it fires:** She satisfies the first combination (*obstetric_visual_disturbance* + *pregnancy_confirmed_status*). Even though her hypertension is already known, the rule’s symptom set triggers escalation. In a low‑resource setting where blood pressure is not routinely measured, this patient may be unnecessarily escalated to a tertiary center, incurring higher costs and logistical burden.

### The case for leaving it alone
**Strengths of the current rule:**  
- **Simplicity:** The rule uses only three concrete, observable symptoms that are relatively easy for frontline staff to assess without advanced equipment.  
- **Safety:** By triggering on severe epigastric pain and visual disturbances, it captures the most life‑threatening manifestations of pre‑eclampsia, which are the primary reasons for emergency escalation.  
- **Evidence base:** The symptom thresholds (severe epigastric pain, visual changes) are derived from Western clinical guidelines that have been validated in high‑resource settings where blood pressure measurement is routine.

**Limitations that could justify modification:**  
- **Miss rate in low‑resource settings:** Indian district hospitals often lack reliable blood‑pressure monitoring and may not have access to imaging or detailed obstetric history. Relying solely on symptom combinations may miss early‑stage pre‑eclampsia where visual disturbances are absent.  
- **Resource constraints:** Escalating every mild swelling case could overload tertiary centers, increase referral costs, and delay appropriate antenatal care.  
- **Cultural symptom perception:** Headache and dizziness are common in pregnancy and may be attributed to dehydration or normal pregnancy discomfort, reducing the likelihood of reporting them as “pre‑eclampsia‑specific” symptoms.

### Outside my seat
- **Schema gap:** The rule does not incorporate **hypertension** as a symptom (blood pressure is not measured in this system). Including a hypertension‑related criterion (e.g., known hypertension or documented elevated BP) would align the rule with local clinical practice.  
- **Severity weighting:** The rule triggers on any one symptom combination, potentially leading to over‑referral for milder cases. A tiered approach (e.g., requiring two of the three symptoms for escalation) could improve appropriateness.

### The one decision I would put to a clinician
**Should the rule be expanded to include mild hypertension (known hypertension or documented elevated BP) as a qualifying factor, and/or should a threshold for swelling severity be added to reduce false‑negative rates?**  
- **If yes:** Re‑evaluate the symptom thresholds to reflect Indian obstetric practice (e.g., mild swelling of hands/face alone may be sufficient, and mild hypertension should count).  
- **If no:** Maintain the current design and document the risk of missing early‑stage pre‑eclampsia, emphasizing that any escalation should be accompanied by a rapid blood‑pressure check and imaging if available.

---

**Conclusion:** The rule, as presently encoded, risks missing a significant proportion of pre‑eclampsia cases in Indian district hospitals due to reliance on visual disturbances and epigastric pain that are not universally present. Simultaneously, it may over‑refer mild cases, creating unnecessary burden. A clinician should decide whether to broaden the symptom criteria (e.g., include mild hypertension and more sensitive swelling criteria) to improve detection without inflating referrals.
