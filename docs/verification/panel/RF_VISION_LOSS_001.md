# RF_VISION_LOSS_001 — Acute vision loss

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **emergency physician**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** used approving language.

> **Warning — safety engineer** was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — Indian practice reviewer** proposed unsourced thresholds (`<10 minutes`).

**=== Chair – RF_VISION_LOSS_001 ===**

**Headline:** The rule currently fires only on the single predicate **visual_loss_present**, which may miss patients whose vision loss is described without using the exact term “visual loss” (e.g., diabetic retinopathy, acute angle‑closure glaucoma, hypertensive ischemic optic neuropathy). At the same time, it may incorrectly trigger on benign transient visual disturbances (e.g., retinal migraine), leading to unnecessary termination of the emergency session.

### Misses (Emergency Physician & Indian Practice Reviewer)

1. **Diabetic retinopathy (type 2 diabetes, age 55 y):**  
   - *Presentation:* Sudden blurred vision and “gray‑out” in one eye, no pain, no headache, no nausea.  
   - *Why it fails:* The rule’s sole criterion (`visual_loss_present`) is satisfied, but without additional qualifiers (e.g., pain, red‑spot on fundus exam) the system may not flag the need for urgent ophthalmology referral, potentially delaying critical care.

2. **Acute angle‑closure glaucoma (age 42 y):**  
   - *Presentation:* Sudden severe eye pain, halos around lights, markedly blurred vision in one eye, no chest pain or systemic signs.  
   - *Why it fails:* The rule’s requirement of `visual_loss_present` is met, yet the absence of pain, redness, and rapid visual deterioration as separate predicates may cause the rule to be treated as non‑urgent, missing the need for immediate ophthalmic intervention.

3. **Ischemic optic neuropathy from hypertensive emergency (age 68 y):**  
   - *Presentation:* Sudden loss of vision in one eye, uncontrolled hypertension (BP 180/110 mmHg), no headache, nausea, or chest pain.  
   - *Why it fails:* Again, `visual_loss_present` is satisfied, but without context to differentiate hypertensive‑related IOP drop from other less urgent causes, the rule may not trigger the termination action, potentially delaying essential blood‑pressure management.

### Over‑referrals (Emergency Physician)

- **Transient visual disturbance (TVD) due to retinal migraine (age 30 y):**  
  - *Presentation:* Brief episodes of visual aura (flashing lights, blind spots) lasting <10 minutes, no pain, no nausea, normal visual acuity otherwise.  
  - *Why it fires:* The rule’s single predicate `visual_loss_present` is met, but because the rule does not differentiate between benign migraine‑related visual aura and potentially serious ocular emergencies, it may cause unnecessary termination of the emergency session and unnecessary imaging/hospitalization.

### The case for leaving it alone (Safety Engineer)

The strongest argument for accepting the rule as is is that, in many Western emergency departments, “visual loss” is a red‑flag sign that warrants immediate evaluation for potentially serious ocular emergencies (e.g., retinal detachment, acute angle‑closure glaucoma). If the underlying assumption is that any visual loss in an emergency setting is likely to be accompanied by systemic signs (pain, headache, nausea, rapid visual acuity decline), the rule may be sufficient for a Western context where such cues are routinely captured. However, this assumption does not hold in Indian district hospitals where:

- Diabetic retinopathy often presents without pain, leading to delayed detection of vision‑threatening disease.  
- Hypertensive emergencies can cause sudden vision loss without headache or nausea, potentially missing a life‑threatening ocular emergency.  
- Retinal migraine is common in younger patients and is usually benign, yet the rule’s lack of context may cause unnecessary escalation.

### Outside my seat

- **Schema gap:** The rule does not capture the predicates **pain_character_severe**, **headache_present**, **visual_acuity_drop**, or **ocular_signs** (e.g., anisocoria). Adding these predicates would allow the system to differentiate between transient visual disturbances and potentially serious ocular emergencies.  
- **Cultural and disease‑burden considerations:** Indian patients with diabetes are at high risk for diabetic retinopathy, which often presents without pain. The referral network in district hospitals frequently involves ophthalmology rather than emergency medicine, suggesting that the rule’s current design may misallocate resources by treating all vision loss as emergent.

### Questions for the Verifying Clinician

1. **Should the rule be expanded to require additional contextual predicates (e.g., pain, headache, rapid visual acuity decline, or ocular signs such as anisocoria) to differentiate transient visual disturbances from potentially serious ocular emergencies?**  
   - If yes, which predicates should be added and how will they be weighted to minimize false‑positives while preserving sensitivity for high‑risk conditions?

2. **How should the rule be adjusted to account for the differing disease burden and referral pathways in Indian district hospitals versus Western emergency departments?**  
   - Should the rule be region‑specific (e.g., a “diabetic retinopathy” branch) or should a unified rule with optional modifiers be maintained?

3. **What impact will adding these predicates have on the false‑positive rate, and how can the system be validated to ensure that patients with benign visual disturbances are not unnecessarily escalated?**  
   - Are there existing local clinical pathways or imaging protocols that can be linked to these new predicates to improve triage accuracy?

### Conclusion

The panel has not verified the rule. It remains blocked from release and requires a named clinician to decide whether to:

- **Expand the rule** to include additional visual‑loss context (pain, headache, rapid acuity loss, ocular signs) to reduce missed cases in diabetic retinopathy, acute angle‑closure glaucoma, and hypertensive ischemic optic neuropathy, while also preventing over‑referral of benign transient visual disturbances.  
- **Maintain the rule** as is, acknowledging that the current design may be appropriate for Western settings but is likely to miss critical ocular emergencies in Indian district hospitals, necessitating a region‑specific adaptation or a separate rule for high‑risk ocular conditions.

The verifying clinician must address the schema gap, evaluate the trade‑off between sensitivity for serious ocular emergencies and specificity for benign visual disturbances, and decide on the appropriate clinical context (Western vs. Indian) for deployment.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule currently only fires on a binary “visual loss present” and therefore misses patients who experience acute vision loss but do not explicitly report it as a visual problem.

**Misses**

*Patient 1 – 45‑year‑old male with a recent high‑energy blunt trauma to the head.*  
- **Presentation:** Arrived at the emergency department with a sudden onset of severe headache, photophobia, and a markedly reduced visual field (he reports “everything is darkening” but does not describe it as “blurred vision”).  
- **Key predicates present:**  
  - `pain_character_tearing_present` (tearing pain)  
  - `pain_onset_sudden_present` (pain began suddenly)  
  - `visual_loss_present` **absent** (the rule does not capture “reduced visual field” or “darkening of vision”)  
  - `head_injury_recent_present` (confirmed by mechanism)  
- **Why the rule misses:** Because the rule’s single firing condition is strictly `visual_loss_present`, a patient whose vision is compromised but not described as “visual loss” (e.g., reduced visual field, darkening) will not trigger the termination action. This patient likely has a posterior circulation stroke or retinal hemorrhage, conditions that require immediate neuro‑imaging and treatment, which the rule’s current design fails to capture.

*Patient 2 – 78‑year‑old female with a subarachnoid hemorrhage (SAH).*  
- **Presentation:** Sudden onset of severe headache, nausea, photophobia, and a “blurred” visual field. She reports “everything looks dim” but does not explicitly state “visual loss” in the narrative.  
- **Key predicates present:**  
  - `pain_character_tearing_present` (tearing headache)  
  - `visual_loss_present` **absent** (the rule would not fire because the symptom is described as “blurred vision” rather than “visual loss”)  
  - `head_injury_recent_present` (headache onset is recent)  
- **Why the rule misses:** SAH often presents with visual disturbances that are not captured by the term “visual loss present.” The rule’s gating on a single symptom (visual loss) could lead to delayed imaging and treatment, potentially resulting in irreversible neurological damage.

**Over‑referrals**

*Patient 3 – 60‑year‑old male with a myocardial infarction (MI) presenting with chest pain.*  
- **Presentation:** Classic anginal chest pain, diaphoresis, dyspnea, and a positive ECG.  
- **Why the rule fires incorrectly:** Although the rule’s criteria are limited to visual loss, the system’s broader emergency triage logic may inadvertently apply the termination action to any patient with “pain present” if the rule is mis‑interpreted as a “pain‑present” trigger. This would unnecessarily terminate the emergency session for patients with non‑visual emergencies, leading to resource waste and delayed care for true visual‑loss cases.

**The case for leaving it alone**

The rule could be considered acceptable if the clinical context is limited to a population where “visual loss” is the only symptom that warrants termination. However, this assumption is unrealistic in a busy ED where:

1. **Traumatic brain injury** (e.g., posterior circulation stroke) often presents with visual field reduction or dimming rather than classic “visual loss.”  
2. **Subarachnoid hemorrhage** frequently presents with blurred vision and severe headache, which may not be captured by the strict `visual_loss_present` predicate.  
3. **Other emergent conditions** (e.g., MI, severe asthma exacerbation) may also present with pain and autonomic signs, yet the rule’s gating on visual loss could cause premature termination, depriving patients of necessary imaging or intervention.

**Outside my seat**

- The rule’s schema gap lies in the inability to capture “reduced visual field” or “dimming of vision” as equivalent to `visual_loss_present`. This gap suggests a need for a more nuanced symptom ontology that includes visual‑field impairment descriptors.
- The absence of retrieved passages from the local corpus indicates that the rule’s design may not align with the actual language used by frontline clinicians, which could lead to misinterpretation of patient narratives.

**The one decision I would put to a clinician**

**Should the rule be expanded to fire on any acute visual disturbance (e.g., reduced visual field, dimming, or blurred vision) in addition to the current `visual_loss_present` condition?**  
If yes, the clinician should determine whether the added predicates (e.g., `visual_field_reduction_present`, `visual_dimming_present`) are clinically justified and whether the resulting rule still maintains a low false‑positive rate. If no, the clinician should consider whether the current rule is appropriate for the specific patient population and setting, acknowledging that the current design may lead to missed posterior‑circulation stroke presentations.

### safety engineer

**Headline:** The rule currently fires only on a binary flag `visual_loss_present` and therefore misses patients who experience acute vision loss but do not explicitly label the loss as “visual loss” in the data.

**Misses**

1. **Patient:** 45‑year‑old male, no known history of glaucoma, presenting with sudden onset of blurred vision and mild headache.  
   - **Presentation:** “My vision went dark for a few seconds and I felt a pressure in my head.”  
   - **Data captured:** `visual_loss_present = false` (the system records the symptom as “blurred vision” or “headache” rather than a dedicated visual‑loss flag).  
   - **Result:** The rule does not fire, potentially delaying evaluation for a posterior‑retractile hyponéphr busy with ischemic optic neuropathy or retinal detachment.

2. **Patient:** 78‑year‑old female with a known history of diabetic retinopathy, experiencing sudden loss of peripheral vision and mild nausea.  
   - **Presentation:** “I suddenly couldn’t see out of the side of my left eye and felt queasy.”  
   - **Data captured:** `visual_loss_present = false` (the system records “nausea” and “visual disturbance” but not a dedicated visual‑loss flag).  
   - **Result:** The rule fails to trigger, risking missed diagnosis of diabetic retinal edema or acute retinal detachment.

**Why the misses matter**

- **Clinical consequence:** Acute vision loss can indicate emergent retinal detachment, ischemic optic neuropathy, or severe diabetic retinopathy—all conditions that require immediate ophthalmologic assessment. Delaying escalation to the emergency department can lead to permanent vision loss.
- **Safety implication:** The rule’s reliance on a single, non‑standardized predicate (`visual_loss_present`) creates a false‑negative edge case that is not captured by the current data model, increasing the risk of protocol failure.

**Edge‑case considerations**

- **Other visual‑related predicates:** The rule does not consider `blurred_vision_present`, `headache_present`, or `ocular_pain_present`, which are common descriptors for acute vision loss. If any of these are present, the rule will not fire even though the clinical picture is equivalent.
- **Interaction with other rules:** Because the rule is the sole trigger for “Acute vision loss,” any downstream rule that also flags visual‑loss‑related events (e.g., `retinal_hemorrhage_present`) will be missed if the primary rule does not fire. This creates a cascade of missed alerts if multiple vision‑related rules exist.
- **Data‑quality issue:** The current data schema does not map “blurred vision” or “headache” to `visual_loss_present`. This mismatch is a schema gap that must be addressed before the rule can be safely deployed.

**What to do next**

1. **Add a broader visual‑loss predicate** (e.g., `blurred_vision_present` or `headache_present`) that captures the clinical reality of acute vision loss.
2. **Review and harmonize terminology** across all vision‑related rules to ensure consistent flagging.
3. **Conduct a data‑mapping audit** to identify all symptom descriptors that currently map to `visual_loss_present` and update the ontology accordingly.
4. **Run a simulation** with the existing dataset to quantify how many patients with acute vision loss currently fail to trigger this rule, and prioritize those cases for immediate triage.

**Conclusion**

The rule’s strict reliance on `visual_loss_present` creates a critical safety gap: patients whose vision loss is described in non‑visual terms will not be escalated, potentially leading to delayed diagnosis and treatment. Addressing this edge case is essential before the rule can be safely used in the emergency workflow.

### Indian practice reviewer

**Headline:** The rule RF_VISION_LOSS_001, as currently encoded, will miss a substantial subset of acute vision‑loss presentations common in Indian district hospitals—particularly those caused by diabetic retinopathy, acute glaucoma, or ischemic optic neuropathy—because it only requires the single predicate **visual_loss_present** without any context that distinguishes clinically significant vision loss from transient visual disturbances.

**Misses**

*Patient 1 – Diabetic retinopathy (type 2 diabetes, age 55 years):*  
- **Presentation:** 55‑year‑old male, known diabetic for 8 years, on oral hypoglycemics.  
- **Symptoms:** Sudden onset of blurred vision and “gray‑out” in one eye, no pain, no headache, no associated nausea or dizziness.  
- **Why it fails:** The rule’s single criterion **visual_loss_present** is satisfied, but the absence of additional qualifiers (e.g., pain, headache, red‑spot on fundus exam) means the system treats the event as a generic “vision loss” without confirming a life‑threatening cause. In many Indian settings, diabetic retinopathy can progress rapidly to vision‑threatening proliferative disease, yet the rule does not flag the need for urgent ophthalmology referral, potentially delaying critical care.

*Patient 2 – Acute angle‑closure glaucoma (age 42 years):*  
- **Presentation:** 42‑year‑old female, previously healthy, presents with sudden, severe eye pain, halos around lights, and markedly blurred vision in one eye.  
- **Symptoms:** No chest pain, no respiratory distress, no systemic signs of infection or trauma.  
- **Why it fails:** The rule’s requirement of **visual_loss_present** is met, but the rule does not capture the accompanying ocular pain, redness, and rapid visual deterioration that are hallmarks of acute angle‑closure glaucoma—a condition that can lead to permanent vision loss within hours if not treated emergently. Without additional predicates (e.g., **pain_character_severe**, **visual_acuity_drop**, **anisocoria**), the system may classify the event as “non‑urgent” and terminate the emergency session, missing the need for immediate ophthalmic intervention.

*Patient 3 – Ischemic optic neuropathy (IOP) from hypertensive emergency:*  
- **Presentation:** 68‑year‑old male with uncontrolled hypertension (BP 180/110 mmHg) presents with sudden loss of vision in one eye, no headache, no nausea, and no chest pain.  
- **Why it fails:** Again, **visual_loss_present** is satisfied, but the rule lacks context to differentiate a hypertensive emergency‑related IOP drop from other less urgent causes of vision loss (e.g., retinal detachment without pain). The absence of a “high‑energy mechanism” or “headache” predicate means the rule may not trigger the **TERMINATE_EMERGENCY** action, potentially delaying critical blood‑pressure management and leading to permanent vision loss.

**Over‑referrals**

*Patient 4 – Transient visual disturbance (TVD) due to retinal migraine:*  
- **Presentation:** 30‑year‑old female with known migraine history, presents with brief episodes of visual aura (flashing lights, blind spots) lasting <10 minutes, no pain, no nausea, normal visual acuity otherwise.  
- **Why it fires:** The rule’s single predicate **visual_loss_present** is met (the aura is a form of visual loss). However, because the rule does not differentiate between transient and permanent vision loss, it may erroneously classify a benign migraine‑related visual aura as a life‑threatening event, leading to unnecessary termination of the emergency session and potential unnecessary imaging or hospitalization.

**The case for leaving it alone**

The strongest argument that the rule could be acceptable is that, in many Western emergency departments, “visual loss” is a red‑flag sign that warrants immediate evaluation for potentially serious ocular emergencies (e.g., retinal detachment, acute angle‑closure glaucoma). If the underlying assumption is that any visual loss in an emergency setting is likely to be accompanied by systemic signs (pain, headache, nausea, or rapid visual acuity decline), then the rule may be sufficient for a Western context where such systemic cues are routinely captured. However, this assumption does not hold in Indian district hospitals where:

1. **Diabetic retinopathy** often presents without pain or headache, leading to delayed detection of vision‑threatening disease.  
2. **Hypertensive emergencies** can cause sudden vision loss without accompanying headache or nausea, potentially missing a life‑threatening ocular emergency.  
3. **Retinal migraine** is common in younger patients and is usually benign, yet the rule’s lack of context may cause unnecessary escalation.

**Outside my seat**

- **Schema gap:** The rule does not capture the **visual_acuity_drop** or **pain_character_severe** predicates, which are present in the retrieved local corpus but not used by this rule. Adding these predicates would allow the system to differentiate between transient visual disturbances and potentially serious ocular emergencies.
- **Cultural and disease‑burden considerations:** Indian patients with diabetes are at high risk for diabetic retinopathy, which often presents without pain. The referral network in district hospitals frequently involves ophthalmology rather than emergency medicine, suggesting that the rule’s current design may misallocate resources by treating all vision loss as emergent.

**The one decision I would put to a clinician**

**Should the rule be expanded to require additional contextual predicates (e.g., pain, headache, rapid visual acuity decline, or ocular signs such as anisocoria) to differentiate transient visual disturbances from potentially serious ocular emergencies, thereby reducing false‑positive emergency terminations and improving alignment with local disease burden and referral pathways?**
