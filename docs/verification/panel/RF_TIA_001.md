# RF_TIA_001 — Resolved focal neurological deficit

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **emergency physician**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — safety engineer** proposed unsourced thresholds (`> 5 minutes`, `> 5 minutes`); was cut off before finishing, so what survives reads more one-sided than it was.

**Rule ID:** RF_TIA_001  

**Headline:** The rule misses patients whose resolved focal neurological deficit is now manifested only as post‑stroke sequelae (e.g., dysphagia, gait instability) and does not fire because none of the three required signs (face asymmetry, arm weakness, speech disturbance) are present. This creates a safety gap: patients with silent or evolving cerebrovascular events may receive lower‑level care and delay urgent imaging/secondary‑prevention evaluation.

### Misses  

**Patient 1 – 68‑year‑old male**  
- **Onset:** Brief visual loss (central scotoma), mild facial droop, mild arm weakness (TIA). Symptoms resolved spontaneously within 10 min.  
- **Current presentation:** Presents with right‑side weakness of the face and arm (now only mild), dysphagia for solids, mild ataxic gait, mild tremor of the right hand. No facial asymmetry, no overt arm weakness, no speech disturbance.  
- **Why the rule fires:** `deficit_resolved` is true, but none of the three predicates (`face_asymmetry_present`, `arm_weakness_present`, `speech_disturbance_present`) are met. The rule therefore does not escalate, potentially missing a patient who now has post‑stroke sequelae that require urgent evaluation.

**Patient 2 – 55‑year‑old female**  
- **Onset:** Brief left‑leg weakness lasting ~45 min; symptoms resolved spontaneously.  
- **Current presentation:** No residual weakness, but now has mild dysphagia, gait instability, and tremor of the right hand. No facial asymmetry, no arm weakness, no speech disturbance.  
- **Why the rule fires:** Same logic as Patient 1 – resolved deficit without any of the three required signs, so the rule does not trigger escalation.

### Over‑referrals  

**Patient 3 – 70‑year‑old male with known hypertension**  
- **Onset:** Chest pain and dyspnea present; symptoms resolved within 2 h.  
- **Current presentation:** No residual chest pain, dyspnea, or other concerning symptoms.  
- **Why the rule fires:** The rule’s condition (`deficit_resolved`) is true, but the patient does not meet any of the three neurological signs, so the rule does not escalate. Escalation would be unnecessary, but failing to escalate could miss an acute coronary syndrome presentation that is common in this population.

### The case for leaving it alone  

Arguments in favor of retaining the rule include:

1. **Resource constraints:** Escalating every resolved deficit could overload the emergency department and referral network, delaying care for patients with genuine emergencies (e.g., cardiac arrest).  
2. **Clinical consensus in Western settings:** In many Western emergency departments, symptom resolution is often taken as a proxy for stability, reducing unnecessary escalation.  
3. **Data limitation:** The local corpus contains no passages demonstrating how patients describe resolved deficits, suggesting that the failure mode may not yet be a documented problem in this context.

### Outside my seat  

- **Cultural symptom reporting:** Indian patients may under‑report subtle deficits (e.g., mild speech disturbance) due to cultural stigma around neurological issues, potentially leading to under‑recognition of early stroke.  
- **Referral network:** The referral pathway to tertiary centers is often delayed due to transport and cost barriers, making timely escalation critical for conditions that benefit from early intervention (e.g., acute ischemic stroke).

### The one decision I would put to a clinician  

**Should the rule be modified to include a “resolved deficit” flag that triggers escalation if any of the following are present:**

1. **Postpartum or postoperative headache with visual disturbance** (reflecting subarachnoid hemorrhage).  
2. **Severe chest pain or dyspnea** (reflecting acute coronary syndrome).  
3. **Any new neurological symptom that resolves but is accompanied by a history of recurrent neurological events or systemic warning signs (e.g., neck stiffness, altered consciousness).**

If the clinician decides to retain the rule as‑is, the justification must address the risk of missing early stroke in this population and the potential for over‑referral to cardiac cases. If modification is chosen, the next step is to define concrete clinical criteria (e.g., “headache + visual disturbance + recent seizure history”) that can be encoded into the rule without exceeding the available predicate list.

---

**Conclusion:** The current RF_TIA_001 rule, as written for a Western emergency setting, will miss patients with resolved deficits now manifested as post‑stroke sequelae and does not fire for patients with resolved cardiac symptoms, creating a safety gap in an Indian district hospital with limited capacity for timely escalation.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_TIA_001 misses patients who have a resolved focal neurological deficit that is not accompanied by any of the three specific signs (face asymmetry, arm weakness, or speech disturbance) – i.e., patients with a resolved TIA who present with only post‑stroke sequelae (e.g., weakness of the opposite side, dysphagia, gait instability) and do not meet the “deficit_resolved AND [face/ arm/ speech]” criteria.

**Missed patient example**

| Feature | Details |
|---------|---------|
| **Age / Sex** | 68‑year‑old male |
| **Chief complaint** | “I feel fine now, but I’m worried about the dizziness I had two weeks ago.” |
| **History** | 2‑week history of transient ischemic attack (TIA) with classic symptoms: brief visual loss (central scotoma), mild facial droop, and mild arm weakness. Symptoms resolved within 10 minutes; no permanent deficit was noted. |
| **Current presentation** | Presents now with **post‑stroke sequelae**: right‑side weakness of the face and arm (now only mild), dysphagia for solids, mild ataxic gait, and a mild tremor of the right hand. No facial asymmetry, no overt arm weakness, and no speech disturbance (only mild dysarthria). |
| **Key predicates present** | - `deficit_resolved` (TIA resolved) <br> - `face_asymmetry_present` **absent** <br> - `arm_weakness_present` **absent** <br> - `speech_disturbance_present` **absent** |
| **Predicates NOT present** | All three required signs are missing; the rule therefore does **not** fire. |
| **Why this patient is a miss** | The rule’s design assumes that any resolved TIA will be flagged if the patient still exhibits the classic triad of facial droop, arm weakness, or speech change. A resolved TIA that has progressed to post‑stroke sequelae (e.g., dysphagia, gait instability) will not meet any of those three criteria, so the rule will not escalate the patient to the higher band for further work‑up. Consequently, the patient may receive a lower‑level care pathway (e.g., observation) rather than the recommended urgent imaging and secondary‑prevention evaluation. |
| **Potential consequence** | Delayed detection of a silent or evolving cerebrovascular event could lead to missed opportunity for antiplatelet therapy, endovascular treatment, or rehabilitation, increasing risk of a full ischemic stroke or permanent disability. |

**Take‑away for the clinician**

- **Rule limitation:** RF_TIA_001 only flags patients who still exhibit the *classic* signs of a TIA (facial asymmetry, arm weakness, speech disturbance). It does **not** capture patients who have already resolved those signs but now present with post‑stroke sequelae.
- **Clinical implication:** Any patient with a resolved TIA who now has persistent dysphagia, gait instability, tremor, or other motor deficits should be escalated regardless of the absence of facial/ arm/ speech criteria.
- **Action:** Consider adding a secondary trigger (e.g., `post_stroke_sequelae_present` or `dysphagia_present`) to ensure that patients with post‑stroke sequelae are still flagged for urgent evaluation.

### safety engineer

**Headline:** The rule fails to capture patients whose resolved focal neurological deficit is due to a transient ischemic attack (TIA) that was not recognized as a stroke at presentation, leading to delayed re‑evaluation and possible missed opportunity for acute thrombolysis.

**Misses**

**Patient 1 – Missed case**

- **Demographics:** 68‑year‑old male, age recorded = 68, no age‑specific thresholds used.
- **Clinical presentation:** Sudden onset of left‑sided weakness of the face and arm (asymmetry) lasting **≈ 30 minutes**. The patient reported “a brief blackout” but felt completely fine afterward. No chest pain, no dyspnea, no focal neck pain, and no other concerning symptoms.
- **Key predicates present:**  
  - `deficit_resolved` – the weakness resolved spontaneously; the patient was discharged home after the episode.  
  - `face_asymmetry_present` – present at onset, but the rule’s branch only requires the symptom to be present **and** the deficit to be resolved.  
- **Predicates NOT used by the rule:**  
  - `neurological_onset_sudden` – satisfied (the event was sudden).  
  - `high_energy_mechanism` – not applicable (no trauma).  
  - `pain_character_tearing` – absent (no pain reported).  
  - `breathing_difficulty_present`, `dizziness_or_fainting_present`, `visual_loss_present`, `seizure_present` – absent.  
- **Why the rule fires:** The rule’s condition is **`deficit_resolved AND face_asymmetry_present`**. The patient’s face asymmetry was present at onset, the deficit resolved spontaneously, and the rule does not check whether the deficit was recognized as a stroke. Consequently, the rule escalates the encounter to the next band, potentially causing unnecessary escalation and resource use for a patient who no longer requires acute stroke services.

**Patient 2 – Over‑referral risk**

- **Demographics:** 55‑year‑old female, age recorded = 55, no age thresholds used.
- **Clinical presentation:** Sudden onset of left‑leg weakness (asymmetry) lasting **≈ 45 minutes**. The patient reported “a brief episode of weakness” and felt completely normal afterward. No chest pain, no dyspnea, no focal neck pain, and no other concerning symptoms.
- **Key predicates present:**  
  - `deficit_resolved` – weakness resolved spontaneously.  
  - `arm_weakness_present` – present at onset.  
- **Why the rule fires:** The rule’s condition is **`deficit_resolved AND arm_weakness_present`**. Even though the weakness was transient and the patient was discharged, the rule escalates the encounter, potentially leading to unnecessary imaging, specialist referral, and delay in returning to routine care.

**Why these patients are missed**

1. **Resolution without documentation:** The rule assumes that “deficit_resolved” implies the patient’s clinical status is known to be stable. In practice, many patients with resolved deficits are discharged without a formal documentation of the event’s resolution, leaving the system unaware that the episode was transient.
2. **Lack of severity context:** The rule does not incorporate any severity or duration thresholds (e.g., “deficit lasted > 5 minutes” or “deficit was recognized as a stroke”). Consequently, brief, self‑limited episodes are treated the same as longer‑lasting deficits that may require acute stroke management.
3. **No post‑episode follow‑up check:** The rule does not capture whether the patient was evaluated for stroke risk (e.g., imaging, blood pressure check) after discharge. A resolved deficit that was never formally assessed for stroke risk can be escalated unnecessarily.

**Implications**

- **Resource waste:** Escalating both patients to a higher band incurs additional imaging, specialist consultations, and possibly admission, costing time and resources without clinical benefit.
- **Potential harm:** Delaying re‑evaluation of a TIA that could have benefited from thrombolytic therapy may lead to permanent neurological deficits.
- **Clinical workflow impact:** The rule’s binary “deficit_resolved” condition creates a false sense of security, prompting escalation for any resolved deficit, regardless of its clinical significance.

**Recommendations**

1. **Add a severity/duration predicate:** Require that `deficit_duration_minutes` be greater than a clinically relevant threshold (e.g., > 5 minutes) or that the deficit be recognized as a stroke by a clinician. This prevents transient deficits from triggering escalation.
2. **Integrate post‑episode documentation:** Require that the deficit be documented as “resolved” by a clinician (e.g., discharge summary note indicating the episode was transient) before the rule fires.
3. **Consider additional clinical context:** Include predicates such as `stroke_evaluation_completed` or `imaging_completed` to ensure that the patient has been assessed for stroke risk after discharge.
4. **Review escalation criteria:** Consult with stroke pathway experts to define when escalation is truly warranted versus when it is an over‑referral.

**Conclusion**

The rule **RF_TIA_001** fails to differentiate between a transient focal neurological deficit that was recognized as a TIA and a brief, self‑limited episode that was never formally assessed for stroke risk. Constructing concrete patients (as above) demonstrates that the rule’s current logic leads to unnecessary escalation, highlighting a critical edge case that must be addressed before deployment.

### Indian practice reviewer

**Headline:** The rule RF_TIA_001, as written for a Western clinical setting, will miss a subset of patients who present with resolved focal neurological deficits in a low‑resource Indian district hospital, where the referral pathway and disease burden differ markedly.

### Misses  

**Patient 1 – 58‑year‑old male, known hypertensive, lives in a rural area with limited access to tertiary care**  
- **Onset:** 4 hours ago; symptoms (left‑sided weakness, mild speech slurring) had resolved spontaneously.  
- **Presenting complaint:** “I felt a tingling in my left hand and my speech was a little slurred, but now I feel fine.”  
- **Key features:**  
  - `deficit_resolved = true` (symptoms have resolved).  
  - `face_asymmetry_present = false` (no asymmetry noted).  
  - `arm_weakness_present = false` (no weakness reported).  
  - `speech_disturbance_present = false` (speech is now normal).  
- **Why the rule fires:** None of the three encoded branches (`face_asymmetry_present`, `arm_weakness_present`, `speech_disturbance_present`) are met.  
- **Result:** The intake agent will not escalate the case to the emergency band, potentially delaying re‑evaluation for underlying ischemic stroke, which remains time‑critical.  

**Patient 2 – 45‑year‑old female, pregnant (2nd trimester), presenting with postpartum headache and mild visual disturbance**  
- **Onset:** 6 hours ago; she reports “headache and a little blurred vision, but now they have gone away.”  
- **Presenting complaint:** “I had a headache and some vision problems after delivery, but they are gone now.”  
- **Key features:**  
  - `deficit_resolved = true` (headache and visual symptoms resolved).  
  - `face_asymmetry_present = false` (no facial droop noted).  
  - `arm_weakness_present = false` (no weakness reported).  
  - `speech_disturbance_present = false` (speech is normal).  
- **Why the rule fires:** The rule does not capture postpartum subarachnoid hemorrhage or severe venous sinus thrombosis, which often present with transient symptoms that resolve. Missing these can lead to delayed diagnosis of life‑threatening intracranial pathology.  

### Over‑referrals  

**Patient 3 – 70‑year‑old male with known diabetes, presenting with chest pain and dyspnea**  
- **Onset:** 2 hours ago; chest pain and shortness of breath present.  
- **Presenting complaint:** “I have chest pain and feel short of breath, but now the pain is gone.”  
- **Key features:**  
  - `deficit_resolved = true` (chest pain resolved).  
  - All three branches (`face_asymmetry_present`, `arm_weakness_present`, `speech_disturbance_present`) are false.  
- **Result:** The rule will not fire, so the patient will not be escalated to a higher band for cardiac evaluation, potentially missing an acute coronary syndrome presentation that is common in this population.  

### The case for leaving it alone  

The rule’s design reflects Western emergency medicine where the assumption is that any resolved focal neurological deficit is benign. In a district hospital setting with limited imaging and neuro‑specialist availability, the following arguments could justify maintaining the rule:

1. **Resource constraints:** Escalating every resolved deficit would overload the emergency department and referral network, leading to unnecessary admissions and delays for patients with genuine emergencies (e.g., cardiac arrest).  
2. **Clinical consensus:** Many clinicians in low‑resource settings rely on symptom resolution as a proxy for stability, especially when the patient’s overall presentation (e.g., chest pain, severe headache) is captured elsewhere.  
3. **Data limitation:** The local corpus contains no passages that demonstrate how patients describe resolved deficits, suggesting that the rule’s failure mode is not yet a documented problem in this context.

However, these arguments are contingent on the assumption that symptom resolution reliably indicates stability, which may not hold true for conditions like postpartum subarachnoid hemorrhage or early ischemic stroke where residual deficits can be subtle.

### Outside my seat  

- **Cultural symptom reporting:** Indian patients may underreport subtle deficits (e.g., mild speech disturbance) due to cultural stigma around neurological issues, leading to under‑recognition of early stroke.  
- **Referral network:** The referral pathway to tertiary centers is often delayed due to transport and cost barriers, making timely escalation critical for conditions that benefit from early intervention (e.g., acute ischemic stroke).  

### The one decision I would put to a clinician  

**Should the rule be modified to include a “resolved deficit” flag that triggers escalation if any of the following are present:**

1. **Postpartum or postoperative headache with visual disturbance** (reflecting subarachnoid hemorrhage).  
2. **Severe chest pain or dyspnea** (reflecting acute coronary syndrome).  
3. **Any new neurological symptom that resolves but is accompanied by a history of recurrent neurological events or systemic warning signs (e.g., neck stiffness, altered consciousness).**

If the clinician decides to retain the rule as‑is, the justification must address the risk of missing early stroke in this population and the potential for over‑referral to cardiac cases. If modification is chosen, the next step is to define concrete clinical criteria (e.g., “headache + visual disturbance + recent seizure history”) that can be encoded into the rule without exceeding the available predicate list.

---

**Conclusion:** The current RF_TIA_001 rule, as written for a Western emergency setting, will miss patients with resolved deficits that are actually manifestations of serious underlying pathology (e.g., postpartum subarachnoid hemorrhage, early ischemic stroke) in an Indian district hospital. This miss is a critical safety concern given the limited capacity for timely escalation and the high disease burden of stroke and cardiac events in this population.
