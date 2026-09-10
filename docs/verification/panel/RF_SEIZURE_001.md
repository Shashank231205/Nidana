# RF_SEIZURE_001 — Seizure activity

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **clinical neurology/ emergency medicine specialist**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** was cut off before finishing, so what survives reads more one-sided than it was.

## RF_SEIZURE_001 – panel brief

**The panel has not verified this rule.** It remains blocked from release and requires a named clinician.

### What the panel agrees on
1. **Missed cases** – The rule will terminate the emergency session for patients who present with generalized tonic‑clonic seizures but do **not** describe “seizure activity” (jerking, loss of consciousness) in the voice‑recorded narrative. Such subtle presentations (altered consciousness, rigors) are captured by predicates like `altered_consciousness_present` or `rigors_present`, which are not part of the current `seizure_present` flag. Consequently, patients with status epilepticus or febrile seizures may be discharged without the needed emergent work‑up.

2. **Over‑referral risk** – Patients who present with chest pain, dyspnea, or other systemic signs unrelated to seizure activity will also trigger termination because the rule’s single firing condition is met. This could unnecessarily consume resources and cause patient anxiety.

### Where the panel disagrees
- **Emergency physician:** Argues that expanding the rule to include `altered_consciousness_present`, `rigors_present`, or similar descriptors would capture missed seizures (e.g., subtle altered consciousness in children or febrile seizures) without increasing unnecessary terminations.
- **Safety engineer:** Warns that broadening the rule could lead to **over‑referral** on patients who do not truly need emergency termination (e.g., chest‑pain‑only patients), potentially increasing resource utilization and ICU bed occupancy.

**What the choice turns on:**  
- **Clinical safety vs. operational efficiency:** Does the benefit of capturing subtle seizure manifestations outweigh the risk of unnecessary emergency termination for non‑seizure presentations?  
- **Implementation feasibility:** Can the existing triage system reliably capture and flag the additional descriptors (e.g., altered consciousness, rigors) without creating new documentation burdens?

### Refer to
A **clinical neurology/ emergency medicine** specialist should review the rule to decide whether to:
1. **Expand the activation criteria** to include observable seizure descriptors (e.g., `altered_consciousness_present`, `rigors_present`) while maintaining a safety net for known epileptics, **or**  
2. **Retain the current narrow definition** and accept the risk of missed status epilepticus, ensuring that only truly seizure‑related presentations trigger termination.

### Questions for the verifying clinician
1. **Should the rule be revised to trigger on additional predicates (e.g., `altered_consciousness_present`, `rigors_present`) that capture subtle seizure activity, while keeping a separate pathway for patients with known epilepsy to avoid over‑triage?**  
2. **If expanded, how should the system differentiate between true seizure activity and other causes of altered consciousness (e.g., metabolic encephalopathy, drug toxicity) to prevent false positives?**  
3. **What documentation improvements are needed to reliably capture “seizure activity” in voice‑recorded narratives, and how will these be validated during triage?**  
4. **What impact would such a change have on overall emergency termination rates and associated costs (e.g., ICU bed occupancy, staff time) in the Indian practice setting?**  

These questions must be addressed before the rule can be cleared for deployment.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_SEIZURE_001 misses patients who present with generalized tonic‑clonic seizures but do not report “seizure activity” in the symptom narrative, because the only encoded criterion (`seizure_present`) is not captured by the available predicates.

**Miss constructed**

- **Patient:** 45‑year‑old male, no known history of epilepsy, admitted via ambulance at 02:15 am after a brief loss of consciousness.
- **Presentation:** Upon arrival he is confused, has a mildly elevated heart rate (110 bpm) and a normal respiratory rate, but there is no documented description of “seizure activity” (e.g., frothing, jerking, loss of consciousness) in the voice‑recorded narrative. The clinician only notes “he was unresponsive for a few seconds and then regained consciousness.”
- **Available predicates:** The rule does not reference any of the seizure‑related predicates such as `altered_consciousness_present`, `loss_of_consciousness_present`, or `head_injury_recent_present`. Because the rule’s single firing condition is `seizure_present`, which is never encoded in the patient’s voice data, the rule will not trigger.
- **Result:** The patient will be discharged from the emergency department without a seizure‑specific work‑up, potentially missing an underlying treatable cause (e.g., metabolic encephalopathy, intracranial bleed) that could have been identified earlier.

**Why this matters**

- **Clinical consequence:** Generalized tonic‑clonic seizures are a red‑flag emergency that often require immediate neuro‑imaging and medication management. Missing them can lead to delayed diagnosis of conditions such as subarachnoid hemorrhage, metabolic disturbances, or drug toxicity.
- **Safety implication:** The rule’s reliance solely on a non‑present predicate creates a false‑negative scenario, increasing the risk of under‑triage and subsequent morbidity or mortality.

**What the clinician should decide**

- **Should the rule be expanded to trigger on any altered‑consciousness or loss‑of‑consciousness predicates (e.g., `altered_consciousness_present` or `loss_of_consciousness_present`), or should it remain limited to a documented “seizure activity” description?**  
  - If expanded, the rule must be revisited to ensure that only true seizure presentations are flagged, preventing over‑triage on other forms of altered consciousness.
  - If retained, the documentation process should be improved to capture “seizure activity” (e.g., “jerking, loss of consciousness, post‑ictal confusion”) so that the rule can fire appropriately.

### safety engineer

**Headline:** The rule RF_SEIZURE_001 is overly narrow and will miss patients who present with seizure activity but do not meet the single “seizure_present” predicate, leading to delayed or unnecessary termination of the emergency session.

### Misses
**Concrete patient who is missed:**

- **Patient:** 45‑year‑old male, no known history of epilepsy, admitted via ambulance after a motor‑vehicle collision.
- **Presentation:** Sudden loss of consciousness, unresponsiveness, and generalized tonic‑clonic movements lasting ~30 seconds. No audible vocalization or post‑ictal confusion reported at the time of triage.
- **Why it fails:** The rule only requires the predicate `seizure_present`. In this scenario, the clinician may not have recorded “seizure activity” as a distinct observable event (e.g., “generalized tonic‑clonic movements”) or may have used a different terminology (“convulsion”) that does not map to the `seizure_present` flag. Consequently, the rule never fires, and the patient remains in the emergency flow without the intended termination action.

### Over‑referrals
**Concrete patient who fires the rule unnecessarily:**

- **Patient:** 65‑year‑old female with a known history of epilepsy, admitted for abdominal pain and nausea.
- **Presentation:** She reports “seizure‑like activity” (brief loss of consciousness and post‑ictal confusion) but is otherwise stable. The clinician correctly identifies the seizure as part of her epilepsy and does not need emergent termination.
- **Why it fires:** The rule’s single predicate `seizure_present` is satisfied, triggering `TERMINATE_EMERGENCY`. This may prematurely end the encounter, potentially missing a need for further monitoring or treatment of the underlying abdominal condition.

### The case for leaving the rule unchanged
**Strongest argument:** The rule is intended to capture acute seizure activity that requires immediate emergency intervention (e.g., possible status epilepticus). If the rule is expanded, it risks over‑referral on patients who do not truly need emergency termination, increasing resource utilization and patient anxiety.

**Counter‑argument:** The current narrowness may lead to missed status epilepticus in trauma patients, where seizure activity can be subtle or not fully described as “seizure_present.” Expanding the rule to include “generalized tonic‑clonic activity observed” or “unresponsiveness with abnormal movements” could capture these cases without unnecessary termination.

### Outside my seat
- **Schema gap:** The rule relies solely on the `seizure_present` predicate, which may not be captured in all clinical notes (e.g., “convulsion” or “brief loss of consciousness” may be recorded under unrelated symptoms). This suggests a need for a more comprehensive seizure detection schema that includes temporal descriptors (duration, post‑ictal state) and observable cues.
- **Potential integration with other rules:** RF_SEIZURE_001 should be reviewed alongside rules for trauma‑related unconsciousness (e.g., `trauma_unconsciousness_present`) to avoid redundant termination when both are triggered simultaneously.

### The one decision I would put to a clinician
**Decision point:** Whether to broaden the rule’s activation criteria to include observable seizure descriptors (e.g., “generalized tonic‑clonic movements observed”) while maintaining a safety net to prevent false positives in known epileptics. This decision hinges on:
1. **Clinical safety:** Will expanding the rule reduce missed status epilepticus without increasing unnecessary emergency terminations?
2. **Operational feasibility:** Can the existing triage system be updated to capture and flag these descriptors reliably?
3. **Resource impact:** What is the projected change in emergency termination rates and associated costs (e.g., ICU bed occupancy, staff time)?

If the clinician determines that the benefits of capturing subtle seizure activity outweigh the risk of over‑referral, the rule should be revised; otherwise, additional clinical context (e.g., known epilepsy) should be required before terminating the session.

### Indian practice reviewer

**Headline:** The rule RF_SEIZURE_001, as currently encoded, will miss seizures that are not accompanied by overt “seizure activity” as defined in Western emergency protocols, which is common in many seizure presentations in low‑resource Indian settings.

### Misses
**Concrete patient (missed case):**  
- **Age:** 12 years (child)  
- **Presentation:** A 12‑year‑old boy presents to the emergency department with a sudden onset of **altered consciousness** (became unresponsive, could not follow commands) and **rigors** (shivering). He was previously well and had no known history of epilepsy.  
- **Key features:**  
  - No observable **seizure activity** (no jerking, no loss of tone) – the child’s movements are subtle and may be mistaken for sleepiness.  
  - **Altered consciousness present** (cannot be aroused, GCS < 8).  
  - **Rigors present** (feverish behavior).  
  - **Breathing difficulty present** (slow, shallow respirations).  
  - **No chest pain, abdominal pain, or other systemic signs** that would trigger the alternative branches of the rule.  
- **Why it fires:** The rule requires **seizure_present** (i.e., overt seizure activity). In this case, the seizure manifested primarily as **altered consciousness and rigors**, which are not captured by the “seizure_present” predicate. Consequently, the rule will terminate the emergency session without further evaluation, potentially leading to delayed recognition of a status epilepticus that could be managed with antiepileptic drugs.

### Over‑referrals
**Concrete patient (over‑referral):**  
- **Age:** 45 years (adult)  
- **Presentation:** A 45‑year‑old woman presents with **chest pain** (described as “tightness” radiating to the left arm) and **dyspnea**. She also reports **diaphoresis** and **dizziness**.  
- **Why it fires:** The rule’s single criterion (`seizure_present`) is not satisfied, but the presence of **chest pain** and other systemic signs triggers the termination action. This patient would be escalated to a higher‑level care (e.g., cardiac evaluation) even though the underlying problem is not a seizure, potentially causing unnecessary resource consumption and patient anxiety.

### The case for leaving it alone
The strongest argument that the rule could remain unchanged is that the current schema is limited to **Western emergency medicine** where seizures are typically recognized by overt motor activity (jerking, loss of tone). In many low‑resource Indian emergency settings, clinicians may not reliably identify subtle seizure manifestations (altered consciousness, rigors) as “seizure activity.” If the rule is left unchanged, it may lead to **missed status epilepticus**, which can be life‑threatening if not promptly treated with intravenous antiepileptic drugs. Conversely, the over‑referral risk (e.g., chest‑pain‑only patients) is a smaller concern because the termination action is applied only when the seizure criterion is met, and the alternative branches (e.g., chest pain) are not triggered in this rule.

### Outside my seat
- **Schema gap:** The rule relies on a predicate (`seizure_present`) that is not universally operational across cultures. In Indian emergency departments, the clinical definition of a seizure may differ (e.g., subtle altered consciousness, rigors). This gap suggests that the rule’s schema needs a more inclusive definition of seizure activity that captures non‑motor manifestations.
- **Cultural/clinical practice variation:** Indian emergency physicians often prioritize rapid assessment of altered mental status and fever (common in febrile seizures) over overt motor activity. If the rule were to be adapted, it should incorporate additional predicates such as **altered_consciousness_present** or **rigors_present** to capture missed seizure presentations.

### The one decision I would put to a clinician
**Should the rule be revised to include additional seizure manifestations (e.g., altered consciousness, rigors) as part of the `seizure_present` predicate, or should it remain limited to overt motor activity while being accompanied by a separate pathway for evaluating subtle seizure presentations?**  

This decision directly addresses whether the rule can safely operate in an Indian district hospital setting without missing critical seizure events while avoiding unnecessary escalation of non‑seizure chest‑pain presentations.
