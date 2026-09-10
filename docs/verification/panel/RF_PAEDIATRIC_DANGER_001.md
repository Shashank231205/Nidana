# RF_PAEDIATRIC_DANGER_001 — Paediatric danger signs

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **emergency physician**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** proposed unsourced thresholds (`< 5 years`, `< 5 years`); was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — safety engineer** proposed unsourced thresholds (`< 5 years`, `< 5 years`, `>5 years`, `<5 years`, `>5 years`, `<5 years`).

> **Warning — Indian practice reviewer** proposed unsourced thresholds (`< 5 years`, `< 5 years`).

**Rule ID:** RF_PAEDIATRIC_DANGER_001  

**Headline:** The rule is overly narrow for children < 5 years and will miss a subset of high‑risk infants who present with subtle, non‑obvious signs (e.g., altered consciousness due to post‑trauma amnesia, mild respiratory distress, and reduced feeding) that are not captured by the four listed criteria. This missed case poses a significant risk of delayed diagnosis and treatment of serious conditions (e.g., early sepsis, occult trauma, or metabolic emergency).  

### Misses  

**Concrete patient (miss):**  
- **Age:** 4‑month‑old infant (age < 5 years, so the age filter is satisfied).  
- **Primary complaint:** “Crying a lot and not feeding well” – caregiver reports the baby is “quiet and not moving much,” but does not describe classic altered consciousness (e.g., lethargy, loss of responsiveness).  
- **Physical signs:**  
  - **Mild respiratory distress:** Slow, shallow breathing with occasional retractions; audible wheeze audible on auscultation.  
  - **No documented oral intake:** The baby has not taken a full feeding in the past 24 h.  
  - **No seizure activity:** No convulsive movements reported.  
- **Additional red‑flag features present (but not captured by the rule):**  
  - Diaphoresis (profuse sweating).  
  - High‑energy mechanism (minor fall while being held).  
  - Recent immobility (left unattended for a short period).  
  - Pain‑related signs (increased irritability, grimacing when touched).  

**Why the rule fires:** None of the four listed criteria are met in full:  
1. **Altered consciousness** – not reported as a seizure; post‑trauma amnesia is not captured.  
2. **Breathing difficulty** – only mild respiratory distress; the rule’s “breathing difficulty present” may be interpreted as severe distress, which is not present.  
3. **Oral intake minimal/none** – the rule’s wording (“no feeding for > 12 h”) may be misinterpreted as “no feeding at all,” which the caregiver may not have reported.  
4. **Seizure** – absent.  

**Result of the rule:** The rule would **not** trigger a termination of the emergency encounter, potentially delaying critical assessment and management of an underlying serious condition (e.g., early sepsis or occult trauma).  

### Over‑referrals  

**Concrete patient (over‑referral):**  
- **Age:** 6‑year‑old girl with a mild cough and occasional wheeze after a viral upper‑respiratory infection.  
- **Why the rule fires:** She meets **age < 5 years** and **breathing difficulty** (wheeze) criteria, even though she does not have altered consciousness, minimal oral intake, or a seizure. This triggers termination of the emergency session despite the presentation being likely benign and not meeting full WHO IMCI danger‑sign thresholds for a child >5 years.  

**Implication:** The rule may prematurely terminate care for children who are not in immediate danger, potentially leading to unnecessary discharge or loss of follow‑up for a condition that could be monitored safely.  

### The case for leaving it alone  

**Strengths of the current rule:**  
1. **Simplicity** – Limits the emergency team to a narrow set of high‑risk presentations that are most common in paediatric emergencies (e.g., seizures, severe respiratory distress, inability to feed).  
2. **Resource allocation** – By focusing on the most life‑threatening signs, it may reduce unnecessary imaging or invasive procedures in children who are not acutely compromised.  

**Weaknesses that could justify leaving it unchanged:**  
- **Limited age range** – The rule only applies to children < 5 years, a group where many danger signs (e.g., altered consciousness, severe respiratory distress) are already well‑recognised and often captured by clinical exam.  
- **Potential for false negatives** – In high‑energy trauma settings, altered consciousness may manifest as post‑trauma amnesia rather than a seizure, causing the rule to miss a critical injury.  

**Decision point:** Whether the risk of missing a serious but less‑obvious sign (e.g., altered consciousness due to brain injury) outweighs the risk of over‑referral in milder presentations.  

### Outside my seat  

- **Schema gap:** The rule does not incorporate **breathing_difficulty_present** as a stand‑alone criterion for children >5 years, which may be appropriate given that wheeze alone can be common in viral bronchiolitis.  
- **Data limitation:** No retrieved passages from the local corpus provide context on how this rule is used in practice, limiting the ability to assess real‑world performance.  

### The one decision I would put to a clinician  

**Should the rule be expanded to include “altered consciousness” (captured as post‑trauma amnesia or loss of consciousness) as a trigger, and if so, should the trigger be limited to children < 5 years or should it apply to all paediatric patients?**  

This question directly addresses the primary missed case (a 4‑year‑old with post‑trauma amnesia) and forces a decision on whether the rule’s scope should be broadened to capture the most common form of altered consciousness in this age group, while also considering the trade‑off of potentially increasing false‑positive terminations for older children.  

---  

**Agreement:** The panel has not verified anything. The rule remains blocked from release and requires a named clinician to decide on the above modifications.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule currently only flags children < 5 years with classic “danger‑sign” presentations (altered consciousness, severe breathing difficulty, minimal oral intake, or a seizure) and therefore misses a subset of high‑risk infants who present with subtle, non‑obvious signs that are not captured by the four listed criteria.

**Missed patient (example):**

| Feature | Details |
|---|---|
| **Age** | 4‑month‑old infant (age < 5 years, so the rule’s age filter is satisfied). |
| **Primary complaint** | “Crying a lot and not feeding well” – the caregiver reports the baby is “quiet and not moving much” but does not describe classic altered consciousness (e.g., lethargy, loss of responsiveness). |
| **Physical signs** | • Mild respiratory distress (slow, shallow breathing, occasional retractions) – not severe enough to meet the “breathing difficulty present” criterion. <br>• No documented oral intake (the baby has not taken a full feeding in the past 24 h). <br>• No seizure activity reported. |
| **Other red‑flag features present** (but not captured by the rule) | • **Diaphoresis** (profuse sweating) – a known sign of severe pain or shock in infants. <br>• **High‑energy mechanism** (the infant was involved in a minor fall while being held). <br>• **Recent immobility** (the baby was left unattended for a short period). <br>• **Pain‑related signs** (increased irritability, grimacing when touched). |
| **Why the rule fires:** None of the four listed criteria are met in full: <br>1. Altered consciousness – not reported. <br>2. Breathing difficulty – only mild retractions, not “difficult breathing.” <br>3. Oral intake minimal/none – the baby has not taken a full feeding, but the rule’s wording (“oral intake minimal or none”) could be interpreted as “no feeding at all,” which the caregiver may not have reported. <br>4. Seizure – absent. |
| **Result of the rule:** The rule would **not** trigger a termination of the emergency encounter, potentially delaying critical assessment and management of an underlying serious condition (e.g., early sepsis, occult trauma, or a metabolic emergency). |

**Implication:** Infants who present with subtle signs of distress (e.g., increased irritability, sweating, mild respiratory changes, and reduced feeding) but lack the overt manifestations captured by the rule may be inadvertently discharged or reassigned to a lower‑priority pathway, increasing the risk of delayed diagnosis and worsening outcomes.

**Next steps for the clinician:**

1. **Expand the rule** to include “altered consciousness” as a broader category (e.g., “lethargy, decreased responsiveness, or abnormal sleep pattern”) rather than only overt seizure activity.  
2. **Add a breathing‑difficulty criterion** that captures mild‑to‑moderate respiratory distress (e.g., retractions, audible wheeze, or reduced breath sounds) rather than only severe respiratory compromise.  
3. **Consider oral‑intake status** as a separate flag (e.g., “no feeding for > 12 h” or “unable to maintain adequate weight gain”) to capture infants who are not feeding but may still have other danger signs.  
4. **Integrate additional predicates** such as diaphoresis, high‑energy mechanism, and recent immobility to capture subtle but clinically significant presentations that are currently missed.

These adjustments would ensure that infants with early warning signs of serious illness are identified and managed promptly, reducing the risk of missed diagnoses in the high‑acuity paediatric population.

### safety engineer

**Headline:** The rule is overly narrow for the age group it targets and will miss a subset of paediatric danger signs that are common in low‑resource settings, potentially delaying life‑saving care.

### Misses  
**Concrete patient (miss):**  
- **Patient:** 4‑year‑old boy (age = 4 years) presenting to the emergency department with a high‑energy trauma (e.g., motor‑vehicle crash) and a recent loss of consciousness.  
- **Presenting features:**  
  - **Altered consciousness** (post‑trauma amnesia, not described as a seizure).  
  - **Breathing difficulty** (tachypnea, audible wheeze, reduced breath sounds).  
  - **No oral intake** (unable to take fluids).  
- **Why the rule fires:** None of the four criteria are met because the rule requires **age < 5 years** *and* one of the four listed signs. In this child, the **altered consciousness** is not captured as “seizure_present” (the symptom is post‑trauma amnesia, which is not coded as a seizure). The other three signs (breathing difficulty, oral intake minimal/none) are present, but the rule’s logic only triggers when **altered consciousness** is present. Consequently, the rule will **not terminate** the emergency session, potentially missing a reversible cause of respiratory compromise and altered mental status.  

**Implication:** A missed diagnosis of acute brain injury or severe respiratory compromise could lead to delayed neuro‑imaging, inadequate ventilation, and irreversible neurologic injury.

### Over‑referrals  
**Concrete patient (over‑referral):**  
- **Patient:** 6‑year‑old girl with a mild cough and occasional wheeze after a viral upper‑respiratory infection.  
- **Why the rule fires:** She meets **age < 5 years** and **breathing difficulty** (wheeze) criteria, even though she does not have altered consciousness, minimal oral intake, or a seizure. This triggers termination of the emergency session despite the presentation being likely benign and not meeting the full WHO IMCI danger‑sign thresholds for a child >5 years.  

**Implication:** The rule may prematurely terminate care for children who are not in immediate danger, potentially leading to unnecessary discharge or loss of follow‑up for a condition that could be monitored safely.

### The case for leaving it alone  
**Strengths of the current rule:**  
1. **Simplicity** – It limits the emergency team to a narrow set of high‑risk presentations that are most common in paediatric emergencies (e.g., seizures, severe respiratory distress, inability to feed).  
2. **Resource allocation** – By focusing on the most life‑threatening signs, it may reduce unnecessary imaging or invasive procedures in children who are not acutely compromised.  

**Weaknesses that could justify leaving it unchanged:**  
- **Limited age range** – The rule only applies to children <5 years, a group where many danger signs (e.g., altered consciousness, severe respiratory distress) are already well‑recognised and often captured by clinical exam.  
- **Potential for false negatives** – In high‑energy trauma settings, altered consciousness may manifest as post‑trauma amnesia rather than a seizure, causing the rule to miss a critical injury.  

**Decision point:** Whether the risk of missing a serious but less‑obvious sign (e.g., altered consciousness due to brain injury) outweighs the risk of over‑referral in milder presentations.

### Outside my seat  
- **Schema gap:** The rule does not incorporate **breathing_difficulty_present** as a stand‑alone criterion for children >5 years, which may be appropriate given that wheeze alone can be common in viral bronchiolitis.  
- **Data limitation:** No retrieved passages from the local corpus provide context on how this rule is used in practice, limiting the ability to assess real‑world performance.

### The one decision I would put to a clinician  
**Should the rule be expanded to include “altered consciousness” (captured as post‑trauma amnesia or loss of consciousness) as a trigger, and if so, should the trigger be limited to children <5 years or should it apply to all paediatric patients?**  

This question directly addresses the primary missed case (a 4‑year‑old with post‑trauma amnesia) and forces a decision on whether the rule’s scope should be broadened to capture the most common form of altered consciousness in this age group, while also considering the trade‑off of potentially increasing false‑positive terminations for older children.

### Indian practice reviewer

**Headline:** The rule RF_PAEDIATRIC_DANGER_001, as written for a Western emergency setting, fails to capture a subset of paediatric danger signs that are common in Indian district hospitals and are driven by the local disease burden (e.g., severe acute malnutrition, enteric fever, and post‑operative complications). Consequently, children who present with these signs may not be escalated to higher‑level care, potentially leading to preventable morbidity or mortality.

### Misses
**Concrete patient example (58‑year‑old child, age < 5 years):**

- **Clinical picture:** A 3‑year‑old boy admitted to a district hospital with severe acute malnutrition (weight for age < -3 SD). He presents with **breathing difficulty** (tachypnea, intercostal retractions) and **altered consciousness** (irritability, inability to follow simple commands).  
- **Why the rule misses:** The rule only triggers on four specific danger signs: altered consciousness, breathing difficulty, minimal oral intake, or seizure. Severe acute malnutrition often manifests primarily as **breathing difficulty** and **altered consciousness**, but the rule does not capture the broader “breathing difficulty present” condition when accompanied by altered consciousness. Thus, a child meeting the WHO IMCI criteria for “severe acute malnutrition with respiratory distress and altered mental status” will not be flagged, delaying critical resuscitation and nutrition support.
- **Potential consequence:** Delayed recognition could lead to rapid decompensation, shock, and organ failure, especially in a setting where rapid escalation to a tertiary care center is not guaranteed due to limited transport options and resource constraints.

### Over‑referrals
**Concrete patient example (58‑year‑old child, age < 5 years):**

- **Clinical picture:** A 4‑year‑old girl presents with **vomiting** (≥ 3 episodes in the past 24 h) and **vomiting since injury** (recent minor trauma). She has **no altered consciousness**, **no breathing difficulty**, and **no oral intake minimal**.  
- **Why the rule fires:** The rule’s criteria are overly restrictive; a child with isolated vomiting without any of the four listed danger signs will still be escalated to termination of emergency care, unnecessarily diverting resources and causing parental anxiety. This over‑referral is costly in a resource‑limited environment where many vomiting episodes are benign (e.g., gastroenteritis) and can be managed safely with outpatient care.

### The case for leaving it alone
The strongest argument that the rule is already adequate is that the WHO IMCI criteria are widely accepted and have been validated in high‑resource settings. Proponents argue that:

1. **Safety first:** Any missed danger sign could lead to severe outcomes, and the rule’s simplicity ensures that clinicians focus on the most critical signs (altered consciousness, breathing difficulty, minimal intake, seizure).  
2. **Standardization:** Using a uniform set of criteria across diverse settings reduces clinician cognitive load and improves inter‑facility communication.  
3. **Evidence base:** The rule’s design mirrors WHO recommendations, which have been tested in multiple countries and shown to improve survival rates in acute pediatric emergencies.

**However**, this argument overlooks the specific epidemiology and referral network of Indian district hospitals, where:

- **Disease burden** (e.g., severe acute malnutrition, enteric fever) often presents primarily with respiratory distress and altered consciousness, which the rule already captures, but the **absence of a broader “breathing difficulty” clause** prevents detection of cases where altered consciousness is secondary to other complications (e.g., meningitis, encephalitis).  
- **Resource constraints** (limited transport, high patient‑to‑doctor ratio) mean that missing a child with severe respiratory distress could be catastrophic, outweighing the cost of over‑referral in less severe cases.

### Outside my seat
- **Data gap:** The retrieved local corpus passages indicate that the rule’s predicates (e.g., `breathing_difficulty_present`) are not consistently captured in the patient data used for triage in Indian settings. This suggests a schema gap that could affect rule performance.
- **Cultural/behavioral factors:** In many Indian districts, parents may present with “vomiting” without accompanying respiratory distress, leading to over‑referral. Conversely, severe respiratory distress may be under‑reported due to language barriers or cultural stigma around seeking emergency care.

### The one decision I would put to a clinician
**Should the rule be expanded to include “breathing difficulty present” as a standalone trigger (in addition to altered consciousness) to capture severe acute malnutrition and other respiratory emergencies that may not present with altered consciousness?**  

If yes, the clinician should consider:
- **Evidence:** Review studies on pediatric emergency triage in low‑resource settings that demonstrate the added benefit of respiratory distress as a primary trigger.
- **Implementation:** Define a threshold for breathing difficulty (e.g., tachypnea > 40 breaths/min, audible wheeze) and integrate it into the rule’s firing logic.
- **Impact assessment:** Evaluate whether the expanded rule reduces missed cases without disproportionately increasing over‑referrals, considering the local referral network and resource availability.

**If no, the clinician should maintain the current rule and focus on improving documentation and caregiver education to better capture respiratory distress, thereby mitigating the missed‑case risk.**
