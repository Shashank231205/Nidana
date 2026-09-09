# RF_ANAPHYLAXIS_001 — Possible anaphylaxis

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **Emergency Medicine / Critical Care**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** was cut off before finishing, so what survives reads more one-sided than it was.

## RULE_ID: RF_ANAPHYLAXIS_001

**Headline:** The rule RF_ANAPHYLAXIS_001 misses patients with anaphylaxis who present primarily with respiratory distress and no obvious cutaneous signs (e.g., lip or tongue swelling), thereby failing to trigger the emergency termination.

### Misses
**Concrete Patient (Emergency Physician Review):**  
- **Demographics:** 45‑year‑old male, age 45, admitted via emergency department at 2 a.m. after arriving by ambulance.  
- **Chief Complaint:** Sudden onset of severe wheezing and acute shortness of breath, described as “cannot catch a breath.” No history of prior allergic reactions reported.  
- **Physical Findings:**  
  - **Breathing Difficulty Present** (tachypnea 38 breaths/min, audible wheeze on auscultation, accessory muscle use).  
  - **No Lip or Tongue Swelling Present** (no visible edema of the oral mucosa or lips).  
  - **No Rash Present** (no urticaria, erythema, or hives).  
  - **No Stridor Present** (no high‑pitched inspiratory sound).  
- **Why This Patient Fails the Rule:** The rule requires **either** (a) lip or tongue swelling **and** breathing difficulty, **or** (b) allergen exposure **and** rash **and** breathing difficulty. This patient meets only the breathing‑difficulty criterion without the required cutaneous signs, so the rule does not fire and the emergency department does not terminate the encounter as “possible anaphylaxis.”

**Implication:** Without a trigger, the patient may not receive emergent epinephrine administration, antihistamines, or airway management, potentially leading to rapid decompensation or death. This scenario is especially concerning in a high‑volume emergency department where time to diagnosis and treatment is critical.

**Key Takeaway for Clinicians:** Consider anaphylaxis in any patient with sudden, severe respiratory distress, even in the absence of classic cutaneous manifestations. Use a broader clinical algorithm (e.g., consider anaphylaxis when there is unexplained hypoxia, wheezing, and no alternative explanation) and do not rely solely on the presence of lip/tongue swelling.

### Over‑referrals
**Concrete Patient (Safety Engineer Review):**  
- **Patient:** 60‑year‑old female with known history of seasonal pollen allergy, admitted for chest pain. She reports a mild rash on her face and lips, but no significant breathing difficulty or stridor.  
- **Why it Fires:** The rule’s criteria (lip/or‑tongue swelling **and** breathing difficulty) are satisfied, even though the underlying cause may be a mild allergic reaction rather than a true anaphylactic emergency. This could lead to unnecessary termination of the emergency session, potentially delaying recognition and treatment of a life‑threatening allergic reaction that could be occurring concurrently (e.g., rash or other systemic signs not captured in the current input).

### The case for leaving it alone
**Strengths of the current rule:**  
1. **Specificity for classic anaphylaxis signs:** It captures the most immediately life‑threatening manifestations (swelling + respiratory distress or stridor), which aligns with established emergency protocols for anaphylaxis.  
2. **Simplicity:** By focusing on a limited set of high‑risk signs, it reduces false‑positive triggers, limiting unnecessary terminations.  
3. **Clinical precedent:** Many emergency protocols already use swelling + respiratory distress as a trigger for immediate action, making the rule consistent with existing guidelines.

**Potential weaknesses:**  
- **Missed early systemic presentations:** Anaphylaxis can present initially with gastrointestinal symptoms, altered mental status, or cardiovascular changes (e.g., hypotension, tachycardia) that do not involve swelling or breathing difficulty.  
- **Risk of delayed treatment:** Failure to trigger on such presentations could lead to delayed administration of epinephrine, increasing morbidity and mortality.  
- **Resource impact:** Over‑referrals on mild allergic reactions may waste staff time and resources on patients who do not require emergent termination of care.

### Outside my seat
- **Schema gap:** The rule does not incorporate “allergic exposure” as a required predicate; many patients with anaphylaxis have a known allergen exposure but may not exhibit swelling or respiratory distress at the moment of presentation. Adding “allergen_exposure_present” could capture more cases without increasing false positives dramatically.  
- **Temporal dimension:** The rule does not account for the progression of anaphylaxis; a patient may initially present without swelling but later develop it. A rule that allows escalation based on subsequent findings (e.g., rash or hypotension) could improve detection.

### The one decision I would put to a clinician
**Should the rule be expanded to include an additional trigger for systemic anaphylaxis presentations (e.g., severe allergic exposure **and** any one of the following: altered mental status, chest pain, vomiting, or hypotension) while retaining the original swelling‑plus‑respiratory criteria to avoid over‑referrals?**  
- **If yes:** This would capture patients like the 45‑year‑old male with epigastric pain and altered consciousness, potentially preventing delayed treatment.  
- **If no:** The current design should be maintained to avoid unnecessary terminations and resource waste, relying on clinicians to supplement the rule with clinical judgment when signs are not captured.

---

## Disagreements (as requested)

### Misses vs. Over‑referrals
- **Emergency Physician Review:** Emphasizes the risk of missing patients with respiratory distress without swelling/rash.  
- **Safety Engineer Review:** Highlights the risk of over‑referring mild allergic reactions (e.g., rash + mild dyspnoea) that may not require immediate termination, potentially diverting resources.

**What the choice turns on:**  
- **Misses** argue that the rule’s current thresholds are too restrictive, leading to delayed life‑saving interventions.  
- **Over‑referrals** argue that expanding the rule could waste time and resources on patients who do not truly need emergent termination, potentially causing unnecessary stress on staff and equipment.

**Decision point:** The clinician must weigh the higher morbidity/mortality risk of missed anaphylaxis against the operational cost of unnecessary terminations.

---

## Refer to
- **Specialty:** Emergency Medicine / Critical Care (to ensure appropriate escalation algorithms are in place).  
- **Question for Clinician:** Does the benefit of capturing all anaphylaxis presentations outweigh the risk of unnecessary emergency termination, and should the rule be modified to include systemic signs while preserving the original respiratory‑plus‑swelling criteria?

---

**Note:** The panel has not verified this rule. It remains blocked from release and requires a named clinician to approve any modifications.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_ANAPHYLAXIS_001 misses patients with anaphylaxis who present primarily with respiratory distress and no obvious cutaneous signs (e.g., lip or tongue swelling), thereby failing to trigger the emergency termination.

**Missed Patient (Concrete Example):**

- **Demographics:** 45‑year‑old male, age 45, admitted via emergency department at 2 a.m. after arriving by ambulance.
- **Chief Complaint:** Sudden onset of severe wheezing and acute shortness of breath, described as “cannot catch a breath.” No history of prior allergic reactions reported.
- **Physical Findings:**  
  - **Breathing Difficulty Present** (tachypnea 38 breaths/min, audible wheeze on auscultation, accessory muscle use).  
  - **No Lip or Tongue Swelling Present** (no visible edema of the oral mucosa or lips).  
  - **No Rash Present** (no urticaria, erythema, or hives).  
  - **No Stridor Present** (no high‑pitched inspiratory sound).  
- **Other Relevant Data:**  
  - No known history of known allergen exposure (e.g., medication, insect sting).  
  - No chest pain, dyspnea without wheeze, or other cardiac‑related symptoms.  
  - Vital signs: HR 110 bpm, BP 130/80 mmHg, SpO₂ 92 % on room air (may be higher with supplemental O₂).  
  - No recent trauma or penetrating mechanism.  
- **Why This Patient Fails the Rule:** The rule requires **either** (a) lip or tongue swelling **and** breathing difficulty, **or** (b) allergen exposure **and** rash **and** breathing difficulty. This patient meets only the breathing‑difficulty criterion without the required cutaneous signs, so the rule does not fire and the emergency department does not terminate the encounter as “possible anaphylaxis.”

**Implication:** Without a trigger, the patient may not receive emergent epinephrine administration, antihistamines, or airway management, potentially leading to rapid decompensation or death. This scenario is especially concerning in a high‑volume emergency department where time to diagnosis and treatment is critical.

**Key Takeaway for Clinicians:** Consider anaphylaxis in any patient with sudden, severe respiratory distress, even in the absence of classic cutaneous manifestations. Use a broader clinical algorithm (e.g., consider anaphylaxis when there is unexplained hypoxia, wheezing, and no alternative explanation) and do not rely solely on the presence of lip/tongue swelling.

### safety engineer

**Headline:** The rule fails to detect anaphylaxis that presents without respiratory distress or swelling, potentially leading to delayed emergency care.

### Misses
**Concrete patient (missed case):**  
- **Patient:** 45‑year‑old male, no known history of allergies, admitted via emergency department for acute abdominal pain.  
- **Presentation:** Presents with severe epigastric pain radiating to the back, vomiting, and altered mental status (confusion). No signs of lip or tongue swelling, no stridor, and no breathing difficulty are reported.  
- **Why it fires:** The rule requires either (a) lip/or‑tongue swelling **and** breathing difficulty, or (b) lip/or‑tongue swelling **and** stridor, or (c) allergen exposure **and** rash **and** breathing difficulty. None of these criteria are met because the patient has no swelling, no stridor, and no documented allergic exposure or rash. Consequently, the rule does not trigger, and the emergency team may not initiate the intended termination of the emergency session, potentially delaying recognition and treatment of a life‑threatening allergic reaction that could be occurring concurrently (e.g., a rash or other systemic signs not captured in the current input).

### Over‑referrals
**Concrete patient (over‑referral):**  
- **Patient:** 60‑year‑old female with known history of seasonal pollen allergy, admitted for chest pain. She reports a mild rash on her face and lips, but no significant breathing difficulty or stridor.  
- **Why it fires:** The rule’s criteria (lip/or‑tongue swelling **and** breathing difficulty) are satisfied, even though the underlying cause may be a mild allergic reaction rather than a true anaphylactic emergency. This could lead to unnecessary termination of the emergency session, diverting resources from more severe presentations that truly require immediate intervention.

### The case for leaving it alone
**Strengths of the current rule:**  
1. **Specificity for classic anaphylaxis signs:** It captures the most immediately life‑threatening manifestations (swelling + respiratory distress or stridor), which aligns with established emergency protocols for anaphylaxis.  
2. **Simplicity:** By focusing on a limited set of high‑risk signs, it reduces false‑positive triggers, limiting unnecessary terminations.  
3. **Clinical precedent:** Many emergency protocols already use swelling + respiratory distress as a trigger for immediate action, making the rule consistent with existing guidelines.

**Potential weaknesses:**  
- **Missed early systemic presentations:** Anaphylaxis can present initially with gastrointestinal symptoms, altered mental status, or cardiovascular changes (e.g., hypotension, tachycardia) that do not involve swelling or breathing difficulty.  
- **Risk of delayed treatment:** Failure to trigger on such presentations could lead to delayed administration of epinephrine, increasing morbidity and mortality.  
- **Resource impact:** Over‑referrals on mild allergic reactions may waste staff time and resources on patients who do not require emergent termination of care.

### Outside my seat
- **Schema gap:** The rule does not incorporate “allergic exposure” as a required predicate; many patients with anaphylaxis have a known allergen exposure but may not exhibit swelling or respiratory distress at the moment of presentation. Adding “allergen_exposure_present” could capture more cases without increasing false positives dramatically.  
- **Temporal dimension:** The rule does not account for the progression of anaphylaxis; a patient may initially present without swelling but later develop it. A rule that allows escalation based on subsequent findings (e.g., rash or hypotension) could improve detection.

### The one decision I would put to a clinician
**Should the rule be expanded to include an additional trigger for systemic anaphylaxis presentations (e.g., severe allergic exposure **and** any one of the following: altered mental status, chest pain, vomiting, or hypotension) while retaining the original swelling‑plus‑respiratory criteria to avoid over‑referrals?**  
- **If yes:** This would capture patients like the 45‑year‑old male with epigastric pain and altered consciousness, potentially preventing delayed treatment.  
- **If no:** The current design should be maintained to avoid unnecessary terminations and resource waste, relying on clinicians to supplement the rule with clinical judgment when signs are not captured.

### Indian practice reviewer

**Headline:** The rule’s strict requirement for “breathing difficulty” (dyspnoea) and “stridor” creates a high false‑negative rate for anaphylaxis presentations that are common in Indian patients, especially those with allergic rhinitis or asthma‑type reactions that may not manifest as severe wheeze or stridor.

**Misses**

1. **Patient:** 45‑year‑old male, resident of a rural district hospital, known history of seasonal allergic rhinitis.  
   - **Presentation:** 30 minutes after consuming a locally‑grown mango (a common allergen), he develops a sudden onset of facial swelling, tightness of the throat, and a mild wheeze that is not severe enough to be described as “stridor.” He reports a dry cough and feels short of breath, but the dyspnoea is subtle and not described as “breathing difficulty present” in the full clinical narrative.  
   - **Why it fails:** The rule only fires if **breathing difficulty** (dyspnoea) is present *and* lip/or‑tongue swelling. In this case, the dyspnoea is mild and may be attributed to post‑prandial exertion or early asthma, which is not captured by the current symptom list. Consequently, the rule will not trigger, potentially delaying life‑saving epinephrine administration.

2. **Patient:** 12‑year‑old girl, admitted with a rash and mild wheeze after eating a fruit‑based snack (common in Indian festivals). She has a known history of eczema and occasional urticaria.  
   - **Presentation:** Rash appears within 15 minutes, accompanied by a mild wheeze and facial swelling. She reports a “tight feeling” in her throat but does not describe “breathing difficulty” (dyspnoea) as severe enough to meet the rule’s threshold.  
   - **Why it fails:** The rule’s first two branches require **breathing difficulty** (dyspnoea) in addition to swelling. Mild wheeze and rash alone may be interpreted as a typical allergic reaction without severe respiratory compromise, leading to a missed trigger.

**Over‑referrals**

- **Patient:** 60‑year‑old woman with known hypertension and diabetes, presenting with a sudden onset of abdominal pain, nausea, and mild dyspnoea after a meal. She also reports a rash on her face.  
  - **Why it fires:** The rule’s third branch (allergen exposure + rash + breathing difficulty) can be satisfied even when the primary trigger is not anaphylaxis but a gastrointestinal reaction. This may lead to unnecessary termination of the emergency session and delay appropriate management for a possible gastrointestinal emergency.

**The case for leaving it alone**

- The rule is derived from Western emergency‑medicine guidelines that prioritize severe respiratory compromise (stridor, marked dyspnoea) as a hallmark of anaphylaxis. In high‑income settings, such severe respiratory signs are more consistently reported.  
- In low‑resource Indian settings, allergic reactions often present with mild swelling, rash, and a subtle cough that may be attributed to post‑prandial exertion, asthma, or viral upper‑respiratory infections. Broadening the criteria to include “mild dyspnoea” or “subtle wheeze” could capture these common presentations without inflating false‑positive referrals.

**Outside my seat**

- The rule does not account for cultural or socioeconomic factors that influence symptom reporting. Patients may underreport or misinterpret “breathing difficulty” due to language barriers, limited access to healthcare, or cultural beliefs about mild respiratory symptoms being normal.  
- The absence of retrieved passages from the local corpus suggests that the rule’s design may not reflect the actual clinical narratives encountered in district hospitals, indicating a potential schema gap.

**The one decision I would put to a clinician**

> **Should the rule be modified to include a less stringent respiratory criterion (e.g., mild dyspnoea or wheeze) for patients with known allergic sensitizers, while retaining the stridor requirement only for cases where severe respiratory compromise is clinically evident?**  
> This decision will determine whether the rule remains sensitive enough to catch anaphylaxis in the Indian population without increasing unnecessary referrals for mild allergic reactions.
