# RF_STROKE_001 — Possible stroke

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **emergency physician**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** was cut off before finishing, so what survives reads more one-sided than it was.

**RF_STROKE_001 – Panel Brief**

**Headline:** The rule currently only flags classic anterior‑circulation stroke presentations (facial droop, arm weakness, speech disturbance, or sudden visual loss) and therefore will miss patients who present with atypical or sub‑acute stroke signs that are still within the reperfusion window.

**Missed Patient (Emergency Physician Review)**  
- **Patient:** 58‑year‑old woman, known hypertension, diabetes, and atrial fibrillation.  
- **Presentation:** Sub‑acute (≤ 24 h) headache described as “pressure‑like” and worsening with cough, accompanied by new‑onset focal weakness of the right leg (no facial asymmetry, arm weakness, or speech disturbance). She also reports dizziness and visual distortion (double vision) but denies any chest pain.  
- **Why missed:** None of the four encoded branches fire because the rule only checks for classic stroke signs; the sub‑acute focal weakness and headache are not captured.  
- **Clinical consequence:** Missed opportunity for thrombolytic therapy (tPA) within the 4.5‑hour window from symptom onset, potentially leading to permanent disability.

**Missed Patient (Safety Engineer Review)**  
1. **Atypical (posterior‑stroke) presentation** – 68‑year‑old male with tingling in left hand/arm, no speech change or visual loss. Symptoms began 12 h ago (gradual numbness), not an abrupt “sudden” onset.  
2. **Sub‑acute presentation** – 52‑year‑old female with severe headache and dizziness; symptoms began 6 h ago (gradual dizziness), not an abrupt onset.  
3. **Variant presentation (posterior‑circulation stroke)** – 71‑year‑old male with tingling in left leg/arm, sudden headache and nausea; classic FAST signs absent.  

**Over‑referral Example**  
- **Patient:** 45‑year‑old male with mild headache, dyspnea, and chest pain (likely cardiac). No facial, arm, speech, or visual symptoms.  
- **Result:** The rule would fire, terminating the emergency session unnecessarily, consuming resources for imaging that may not be indicated.

**The case for leaving the rule unchanged**  
- **Strengths:** High specificity for classic anterior‑circulation stroke, aligns with FAST screening validated in Western settings, and triggers immediate termination for true stroke, reducing morbidity.  
- **Potential weaknesses:** Limited to classic presentations, excludes posterior‑circulation strokes, and may fire on benign conditions (e.g., migraine, cardiac chest pain), leading to unnecessary escalation.

**Outside my seat**  
- **Schema gap:** No inclusion of headache, neck stiffness, or gait disturbance as stroke triggers.  
- **Temporal threshold:** “Sudden onset” may be too restrictive; many strokes evolve over minutes to hours.  
- **Missing comorbidities:** Does not account for atrial fibrillation, coronary artery disease, or other risk factors that can precipitate ischemic stroke.  
- **Potential false positives:** If “headache” is mapped to a predicate always true for migraine, the rule could fire on benign conditions.

**The one decision I would put to a clinician**  
> **Should the rule be expanded to include posterior‑circulation stroke criteria (e.g., unilateral leg weakness, gait disturbance, vertigo, or neck stiffness) and/or a broader temporal window (e.g., symptoms present for ≥ 6 h but still “sudden” in onset) while retaining the classic four signs?**  

If **yes**, the rule would capture a larger proportion of stroke patients in diverse settings, reducing missed cases and unnecessary terminations. If **no**, the rule should remain as is, with a clear justification that the target population (classic anterior‑circulation stroke) is well‑represented and that alternative pathways (e.g., tele‑stroke, imaging protocols) can capture atypical presentations.

---

## The reviews behind this brief

### emergency physician

**Missed Patient (Emergency Physician Review – RF_STROKE_001)**  

**Headline:** The rule currently only flags classic “classic” stroke presentations (facial droop, arm weakness, speech disturbance, or sudden visual loss) and therefore will miss patients who present with atypical or sub‑acute stroke signs that are still within the reperfusion window.

**Concrete Missed Patient**

| Feature | Reason the Rule Misses This Presentation |
|---------|------------------------------------------|
| **Age & Demographics** | 58‑year‑old woman, known hypertension, diabetes, and a history of atrial fibrillation (not captured by the rule). |
| **Clinical Presentation** | Presents with **sub‑acute** (≤ 24 h) **headache** that is described as “pressure‑like” and “worsening with cough,” accompanied by **new‑onset focal weakness** of the right leg (not classic “face‑asymmetry” or “arm‑weakness”). She also reports **dizziness** and **visual distortion** (double vision) but denies any chest pain or sudden neck pain. |
| **Temporal Context** | Neurological deficit appeared **12 hours** after onset of headache; the rule’s “neurological_onset_sudden” is satisfied, but the **window** for reperfusion eligibility (≤ 6 h from symptom onset) is not captured by the rule’s logic. |
| **Other Predicates** | - `chest_pain_present` is **absent** (no chest pain reported). <br> - `deficit_resolved` is **unknown** (the patient is still symptomatic). <br> - `getting_worse_present` is **present** (symptoms are progressing). |
| **Why the Rule Fires** | None of the four encoded branches fire because none of the classic stroke signs (face asymmetry, arm weakness, speech disturbance, visual loss) are present. The rule only checks for those four specific signs, so a sub‑acute presentation with focal weakness and headache does not meet any branch. |
| **Potential Outcome** | If triaged by this rule, the patient would be **terminated** from the emergency department without further stroke work‑up, missing the opportunity for thrombolytic therapy (tPA) which is still indicated within the 4.5‑hour window from symptom onset. |

**Why This Patient Matters**

- **Stroke Type:** Large‑vessel anterior circulation ischemic stroke (sub‑acute) is a common presentation in patients with atrial fibrillation and hypertension. Missing it leads to delayed reperfusion therapy, increased morbidity, and potentially permanent disability.
- **Clinical Consequence:** The rule’s exclusion of sub‑acute focal weakness and headache results in a **false‑negative** for a potentially treatable condition, directly impacting patient outcomes.
- **Reperfusion Window:** The rule does not incorporate the time‑sensitive nature of stroke treatment; it only checks for “sudden” onset, which may not capture deficits that develop over a few hours, as in this patient.

**What the Rule Should Do Instead**

1. **Add a branch** for **sub‑acute focal neurological deficit** (e.g., `focal_weakness_present` combined with `neurological_onset_sudden` or `deficit_resolved` absent) to capture patients like the above who present with headache and progressive weakness.
2. **Include a broader headache phenotype** (pressure‑type, worsening with cough) if it is accompanied by focal deficit, visual changes, or dizziness—these are recognized stroke mimics.
3. **Consider age‑adjusted criteria** for patients with known cardiovascular risk factors (e.g., atrial fibrillation) where stroke risk is higher, even without classic signs.
4. **Maintain the `neurological_onset_sudden`** requirement to avoid false positives from transient ischemic attacks (TIAs) that resolve quickly, but complement it with a **time‑since‑onset** check (e.g., ≤ 24 h) to capture sub‑acute strokes.

**Conclusion**

The rule **RF_STROKE_001** currently fails to identify patients who present with sub‑acute focal weakness and headache—common in patients with atrial fibrillation and hypertension—because it only checks for the four classic stroke signs. This missed case could lead to delayed reperfusion therapy and worsened outcomes. The rule must be expanded to include a broader set of clinical features that reflect the full spectrum of stroke presentations, especially those that occur within the early reperfusion window.

### safety engineer

**Headline:** The rule RF_STROKE_001 is designed to detect classic focal neurological signs (face/arm/speech/visual loss) that occur suddenly, but it will miss patients who present with atypical or sub‑acute presentations that do not satisfy any of those four symptom groups.

---

### Misses  

**Patient 1 – Atypical (posterior‑stroke) presentation**  
- **Age / Demographics:** 68‑year‑old male, known hypertension, diabetes, smoker.  
- **Chief complaint:** “I felt a tingling in my left hand and arm, but no speech change or visual loss.”  
- **Onset:** Symptoms began **12 hours** ago, described as “gradual numbness” that progressed over minutes, not an abrupt “sudden” onset.  
- **Why it fails:** None of the four required lines fire because:  
  - *Face asymmetry_present* is false (no facial droop).  
  - *Arm_weakness_present* is false (weakness is limited to the left arm, not a full‑body weakness).  
  - *Speech_disturbance_present* is false (no slurred speech).  
  - *Visual_loss_present* is false (no vision change).  
- **Result:** The rule never terminates the emergency session, potentially delaying reperfusion therapy that could be lifesaving in a posterior‑circulation stroke.

**Patient 2 – Sub‑acute presentation**  
- **Age / Demographics:** 52‑year‑old female, recent history of migraine‑type headaches.  
- **Chief complaint:** “I woke up with a severe headache and felt dizzy; I could not walk straight.”  
- **Onset:** Symptoms began **6 hours** ago, described as “gradual dizziness and mild neck stiffness” rather than an abrupt onset.  
- **Why it fails:** The rule requires *neurological_onset_sudden* for every sign; the dizziness and gait instability are not flagged as “sudden” in the current data model, so none of the four symptom groups fire.  
- **Result:** The emergency department may discharge her without further neuro‑imaging, missing a treatable ischemic stroke.

**Patient 3 – Variant presentation (posterior‑circulation stroke)**  
- **Age / Demographics:** 71‑year‑old male, known hypertension, recent atrial fibrillation.  
- **Chief complaint:** “I felt a tingling in my left leg and arm, but I also had a sudden headache and nausea.”  
- **Onset:** Symptoms began **3 hours** ago; the headache and nausea are the only acute features.  
- **Why it fails:** The rule does not capture “headache” as a stroke sign, nor does it capture “neck stiffness” or “gait disturbance” without the four classic signs.  
- **Result:** The rule would not trigger the termination step, possibly leading to delayed thrombolysis or mechanical thrombectomy.

---

### Over‑referrals  

**Patient 4 – False‑positive scenario**  
- **Age / Demographics:** 45‑year‑old female, no known cardiovascular disease.  
- **Chief complaint:** “I have a mild headache and feel a little dizzy.”  
- **Why it fires:** She reports *headache* and *dizziness*, which could be interpreted as *headache_present* and *dizziness_present* (if the underlying predicates map to those terms). Even without *neurological_onset_sudden*, the rule might fire if the data model treats “headache” as a proxy for “sudden onset”.  
- **Result:** The emergency session would be terminated unnecessarily, consuming staff time and resources for imaging that may not be indicated.

---

### The case for leaving it alone  

The rule is derived from the FAST (Face, Arms, Speech, Time) screening algorithm, which is validated for **anterograde (classic) ischemic stroke** where the onset is abrupt and focal deficits are evident. Its design assumes that any patient meeting the four symptom groups truly has an acute stroke that warrants immediate termination of the emergency pathway for further work‑up and possible thrombolytic therapy.

**Strengths:**
- **High specificity** for classic anterior‑circulation stroke presentations that are time‑critical.  
- **Clear termination action** (TERMINATE_EMERGENCY) aligns with clinical pathways that require rapid imaging and treatment decisions.  
- **Simplicity** reduces cognitive load on clinicians, minimizing the risk of omission of a true stroke.

**Potential weaknesses (but not a reason to discard):**
- **Limited to classic presentations**; many strokes (especially posterior‑circulation or sub‑acute) present with atypical symptoms that do not satisfy any of the four lines.  
- **Temporal requirement** (sudden onset) may exclude patients whose symptoms evolve over minutes to hours, potentially missing a treatable condition.  
- **No inclusion of imaging or laboratory data**; the rule relies solely on self‑reported symptoms, which can be inaccurate or delayed.

---

### Outside my seat  

- **Schema gap:** The rule does not capture **headache** or **neck stiffness** as stroke‑specific triggers, even though these are recognized risk factors for posterior‑circulation stroke.  
- **Temporal threshold:** The requirement for *sudden onset* may be too restrictive; many stroke guidelines (e.g., AHA/ASA) allow “gradual onset” if the patient reports a “gradual worsening” over minutes to hours.  
- **Missing comorbidities:** The rule does not account for **recent atrial fibrillation** or **cardiac arrest**, which can precipitate ischemic stroke even without classic facial/arm/speech/visual signs.  
- **Potential for false positives:** If the data model maps “headache” to a predicate that is always true for migraine, the rule could fire on benign conditions, leading to unnecessary termination.

---

### The one decision I would put to a clinician  

**Should the rule be expanded to include posterior‑circulation stroke criteria (e.g., unilateral leg weakness, gait disturbance, vertigo, or neck stiffness) and/or a broader temporal window (e.g., symptoms present for ≥ 6 hours but still “sudden” in onset) while retaining the classic four signs?**  

- **If yes:** This would address the missed patients (e.g., Patient 1, Patient 2, Patient 3) and reduce the risk of delayed reperfusion therapy.  
- **If no:** The rule should remain as is, with a clear clinical justification that the target population (e.g., patients presenting with classic anterior‑circulation stroke) is well‑represented in the local emergency setting, and that alternative pathways (e.g., tele‑stroke, imaging protocols) can capture atypical presentations.

---

**Conclusion:** The current RF_STROKE_001 rule is highly effective for classic anterior‑circulation stroke but fails to capture many atypical presentations that are clinically significant. A decision on whether to broaden the rule should be made by a clinician familiar with local stroke epidemiology and resource constraints.

### Indian practice reviewer

**Headline:** The rule RF_STROKE_001, as written, will miss a substantial subset of stroke patients in a district‑hospital setting in India because it relies on Western‑derived FAST‑screening criteria (face, arm, speech, vision) that are not representative of the typical presentation of ischemic stroke in low‑resource, high‑mortality environments.

**Misses**

*Patient 1 – Typical Indian presentation of ischemic stroke*  
- **Age:** 58 years (male)  
- **Comorbidities:** Type 2 diabetes mellitus (well‑controlled), hypertension (BP 140/90 mm Hg), known coronary artery disease, on aspirin therapy.  
- **Clinical presentation:** Sudden onset of **left‑sided weakness of the face and arm** (facial droop, inability to raise the left arm to shoulder height) and **slurred speech** (“I cannot say a full sentence”). No accompanying chest pain, neck pain, or prodromal prodrome (e.g., headache, neck stiffness).  
- **Onset:** 30 minutes ago; patient was previously ambulatory and able to speak.  
- **Key features absent from rule:**  
  - No **visual loss** (the rule’s visual‑loss branch is rarely triggered in Indian patients because visual symptoms are often masked by other comorbidities such as diabetic retinopathy).  
  - No **chest pain** (myocardial infarction is far more common than acute ischemic stroke in this population, and the FAST criteria prioritize visual loss, which is less prevalent).  
- **Result of rule:** Because the rule requires **neurological_onset_sudden** *and* one of the four FAST signs, the patient’s presentation (face/arm weakness + speech disturbance) would satisfy the rule. However, many Indian patients present with **sub‑acute** deficits (e.g., weakness that evolves over hours) or with **atypical speech changes** (e.g., dysarthria without full aphasia) that may not be captured by the strict “speech disturbance” predicate. The rule’s reliance on the exact phrasing “speech_disturbance_present” may miss nuanced speech impairments that are common in older adults with co‑existing neurodegenerative disease.  
- **Why this patient is missed:**  
  1. **Visual loss** is not a dominant presenting symptom in Indian stroke cohorts (≈ 30 % of strokes present with motor deficits, 20 % with speech deficits, and only ~ 10 % with visual loss).  
  2. **FAST‑screening** (face/arm/speech/visual) is validated primarily in Western populations where visual loss is more common. In India, many patients present with **sub‑acute weakness** that may be attributed to **muscle‑spasm** or **myopathy** from diabetes‑related neuropathy, leading clinicians to attribute the deficit to “muscle stiffness” rather than stroke.  
  3. **Time‑window** for reperfusion therapy (≤ 4.5 h) is less emphasized in district hospitals due to limited imaging resources, so clinicians may not prioritize stroke triage as aggressively as in Western settings, further reducing the likelihood of timely escalation.  

*Patient 2 – Atypical presentation with comorbidities that mask classic FAST signs*  
- **Age:** 72 years (female)  
- **Comorbidities:** Chronic obstructive pulmonary disease (COPD), chronic kidney disease (eGFR 30 mL/min), recent **COVID‑19 infection** (post‑viral stroke risk).  
- **Clinical presentation:** Sudden onset of **dizziness, gait instability, and mild confusion**; no facial asymmetry, arm weakness, or speech disturbance. She reports a **headache** that feels like a “tight band around the head” and **neck stiffness**.  
- **Rule outcome:** The rule would not fire because none of the four FAST signs (face, arm, speech, visual loss) are present. However, this patient has **sub‑acute ischemic stroke** (often due to large‑vessel occlusion) that may progress rapidly. In a high‑mortality setting, missing this presentation could lead to irreversible brain injury.  

**Over‑referrals**

*Patient 3 – False‑positive scenario*  
- **Age:** 45 years (male)  
- **Presentation:** Sudden onset of **left‑leg swelling** and **dyspnea** without any facial, arm, speech, or visual symptoms. He reports a **chest pain** that feels like “pressure in the chest” but no **visual loss**.  
- **Rule outcome:** The rule would fire because **chest_pain_present** satisfies the “neurological_onset_sudden” condition (the rule does not differentiate between cardiac and cerebrovascular causes). This would trigger **TERMINATE_EMERGENCY**, potentially leading to unnecessary admission to the ICU, costly imaging, and delays in treating a potentially treatable cardiac event.  

**The case for leaving the rule unchanged**

The rule’s design reflects Western stroke guidelines that prioritize **visual loss** as a primary FAST sign, which is less common in Indian stroke cohorts. However, the rule’s strict reliance on the exact FAST components may lead to **under‑triage** of motor‑dominant strokes, which are the most common presentation in low‑resource settings. The benefit of catching visual‑loss strokes (which are more likely to be treated emergently) is offset by the high cost of missed motor strokes, which can result in permanent disability and increased morbidity.  

**Outside my seat**

- The rule does not account for **sub‑acute** presentations where the onset may be described as “gradual weakness” rather than “sudden”.  
- It does not incorporate **comorbidities** (e.g., diabetes, hypertension) that can mimic stroke symptoms (e.g., diabetic neuropathy causing gait instability).  
- The rule’s **action** (TERMINATE_EMERGENCY) may be over‑escalated for patients with **non‑stroke** chest pain or respiratory distress, leading to unnecessary resource consumption.  

**The one decision I would put to a clinician**

> **Should the rule be modified to include additional stroke‑specific criteria (e.g., unilateral motor weakness, unilateral sensory loss, or altered consciousness) that are more prevalent in Indian stroke cohorts, and should the action be limited to patients who meet the classic FAST signs (face/arm/speech/visual loss) to avoid unnecessary emergency escalation?**  

This question directs the clinician to evaluate the disease burden, local presentation patterns, and resource constraints before deciding on rule refinement or retention.
