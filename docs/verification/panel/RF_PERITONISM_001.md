# RF_PERITONISM_001 — Acute abdomen with peritonism

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **emergency physician**. Reviewed 2026-09-09 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — Indian practice reviewer** proposed unsourced thresholds (`over 48 hours`); was cut off before finishing, so what survives reads more one-sided than it was.

**=== RF_PERITONISM_001 – Panel Brief ===**

**Headline:** The rule fails to fire on patients who meet the clinical definition of acute abdomen with peritonism but do not report “pain worsens on movement,” because the encoded criteria require that specific pain‑worsening feature.

**Agreement (All Seats)**  
1. **Missed Patient Profile** – A 45‑year‑old male with a sudden, severe epigastric pain radiating to the left lower quadrant, nausea, and vomiting, but with diffuse epigastric discomfort rather than localized tenderness. The rule’s first branch (tenderness + pain‑worsened‑by‑movement) is not satisfied.  
2. **Edge‑Case Miss** – A 62‑year‑old male with chronic kidney disease, known diverticulitis, and absent bowel sounds but no vomiting; the rule’s third branch (bowels absent + vomiting) fails.  
3. **Potential Over‑Referral** – A 35‑year‑old male with mild gastroenteritis, diffuse pain, and vomiting; the rule’s first branch fires, potentially escalating a non‑acute case.

**Disagreement (Where Seats Conflict)**  

- **Emergency Physician vs. Indian Practice Reviewer**  
  - *Emergency Physician*: Argues that the rule’s failure stems from a lack of “pain‑worsened‑by‑movement” reporting, which is a common Western descriptor for peritonitis.  
  - *Indian Practice Reviewer*: Points out that many Indian patients describe pain as diffuse crampy or radiating, and vomiting may be minimal or not captured as “vomiting_present.” The rule’s schema (tenderness + pain‑worsened‑by‑movement) may therefore miss a substantial subset of cases, especially those caused by H. pylori‑related perforation or septic peritonitis that do not meet the Western pain description.

**What Turns the Choice On**  
- **Clinical vs. Cultural Pain Descriptors:** Whether the rule should prioritize the Western pain‑worsened‑by‑movement criterion (which may miss many Indian patients) or be revised to include broader pain descriptors (e.g., diffuse epigastric discomfort) that align with local presentation patterns.  
- **Resource & Referral Constraints:** In Indian district hospitals, limited imaging and transport delays may exacerbate missed cases if the rule does not fire early, whereas in Western settings the same presentation might be captured earlier by other rules or clinical judgment.

**Refer to**  
- **Specialty:** Emergency Medicine / Critical Care – to evaluate whether the rule’s criteria need to be broadened to capture pain descriptors that are not universally reported (e.g., diffuse epigastric pain) and to consider adding a separate branch for partial bowel obstruction with systemic signs.  
- **Next Step:** Conduct a systematic review of local emergency intake data to quantify how often “pain worsens on movement” is absent, and pilot a revised rule that includes an alternative trigger (e.g., vomiting + any abdominal tenderness) before full deployment.

**Questions for the Verifying Clinician**

1. **Is the requirement for “pain worsens on movement” essential for all patients with peritonitis, or can it be relaxed to include any documented abdominal tenderness without the movement component?**  
2. **Should a separate branch be added for “vomiting present” combined with any abdominal tenderness (or absent bowel sounds) to capture cases where the movement‑worsened pain is not reported?**  
3. **How will the revised rule impact the current referral pathway in resource‑limited settings, particularly in Indian district hospitals where imaging is delayed?**  
4. **What data can be collected now to quantify the frequency of missed cases due to the movement‑worsened pain criterion, and how will this inform rule refinement?**  

**Conclusion:** The panel has not verified the rule; it remains blocked from release pending a clinician’s decision on whether to broaden the criteria to address both Western and Indian clinical presentation gaps while maintaining safety.

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule fails to fire on a patient who meets the clinical definition of acute abdomen with peritonism but does not report “pain worse on movement,” because the current criteria require that specific pain‑worsening feature.

**Missed Patient (Concrete Example)**  

- **Demographics:** 45‑year‑old male, no known age restriction.  
- **Chief complaint:** Sudden onset of severe epigastric pain radiating to the left lower quadrant, accompanied by nausea and vomiting, but **no description of pain worsening on movement**.  
- **Physical exam:** Abdomen is **tender** and **distended**; bowel sounds are absent; **no mention of pain worsening on movement** (the patient reports pain is constant and worsens with deep inspiration).  
- **Vomiting:** Present (vomiting since the onset of pain).  
- **Other findings:** No evidence of bowel obstruction (no audible gurgling, no visible distension beyond the abdomen), no signs of intra‑abdominal bleeding (no hematemesis, no melena), and no other systemic signs (no fever, no respiratory distress).  

**Why this patient is missed:**  
The rule’s first branch requires **both** `abdominal_tenderness_reported_present` **and** `pain_worse_on_movement`. This patient meets the tenderness criterion, but because his pain does **not** worsen on movement, the branch condition is not satisfied. The second branch (`abdominal_onset_sudden AND abdominal_tenderness_reported_present AND vomiting_present`) is also not met because the rule does not capture the “vomiting present” condition without the explicit “pain worsens on movement” component. The third branch (`bowels_absent AND vomiting_present`) is irrelevant here because the patient does not have documented bowel obstruction (no “bowels absent” flag is recorded). Consequently, the rule terminates the emergency session despite the patient clearly meeting the clinical definition of peritonism.

**Implication:** Patients with acute abdomen due to conditions such as spontaneous bacterial peritonitis, ruptured appendicitis, or early perforated peptic ulcer—where vomiting is present but pain does not worsen on movement—will be discharged or not escalated to surgery, potentially leading to delayed diagnosis and worsening morbidity.

**Next Steps for Clinician:**  
1. **Re‑evaluate the criteria** to include vomiting as a sufficient trigger for termination without requiring the “pain worsens on movement” component.  
2. **Consider adding a separate branch** for “vomiting present with any abdominal tenderness,” or broaden the definition of peritonism to include vomiting as a primary trigger.  
3. **Document the clinical scenario** where this rule fails (e.g., “patient with acute abdomen, vomiting, no pain‑on‑movement worsening”) to inform future rule refinements and to alert clinicians to manually assess for peritonism when the rule does not fire.

### safety engineer

**Headline:** The rule fails to fire on a patient who meets the clinical definition of acute abdomen with peritonism but does not report “abdominal tenderness” because the pain is described as diffuse epigastric discomfort rather than localized tenderness.

**Misses**

**Patient 1 – Concrete Miss**

- **Demographics:** 62‑year‑old male, chronic kidney disease, no known history of intra‑abdominal pathology.
- **Chief complaint:** “I have a severe, burning pain in my upper abdomen that feels like it’s spreading to my back. It’s not localized to any one spot, and it worsens when I move around or cough.”
- **Presenting features:**  
  - Vomiting since the pain began (present).  
  - No mention of “abdominal tenderness” or “pain worse on movement.”  
  - No bowel sounds reported, but the pain is described as diffuse epigastric rather than localized tenderness.  
- **Why the rule fires:** None of the three encoded branches are satisfied:  
  1. **abdominal_tenderness_reported_present** – not reported (pain is described as diffuse, not localized tenderness).  
  2. **abdominal_onset_sudden** – onset is described as gradual worsening, not an acute onset.  
  3. **bowels_absent** – no information about obstipation; the rule assumes peritonitis implies absent bowel sounds, which is not captured here.  
- **Result:** The rule would be silent; the patient would not be escalated to “TERMINATE_EMERGENCY,” potentially delaying recognition of peritonitis.

**Patient 2 – Edge‑Case Miss (Bowel Absent but No Vomiting)**

- **Demographics:** 45‑year‑old female, known diverticulitis, recent antibiotic use.
- **Chief complaint:** “I have severe abdominal pain that feels like it’s spreading to my back. I haven’t had any bowel movements in the past 48 hours, but I haven’t vomited yet.”
- **Presenting features:**  
  - **bowels_absent** – true (no stool/flatus).  
  - **vomiting_present** – false (no vomiting reported).  
  - **abdominal_tenderness_reported_present** – not reported (pain is described as diffuse, not localized tenderness).  
- **Why the rule fires:** The rule requires **both** bowel absent **and** vomiting. Since vomiting is absent, none of the three branches fire, even though the patient meets the clinical definition of peritonitis (absent bowel sounds, severe diffuse pain, no localized tenderness).  
- **Result:** The patient would be discharged or reassigned to a lower‑acuity pathway, risking delayed surgical intervention.

**Over‑Referrals (Potential Cost)**

**Patient 3 – False Positive (Non‑Acute Abdomen)**

- **Demographics:** 35‑year‑old male, recent minor gastrointestinal infection.
- **Chief complaint:** “I have a mild stomach ache that feels like indigestion. The pain is worse when I move, and I’ve been vomiting a little.”
- **Presenting features:**  
  - **abdominal_tenderness_reported_present** – true (pain worsens on movement).  
  - **vomiting_present** – true.  
  - **abdominal_onset_sudden** – not clearly documented as “sudden” (onset is described as gradual).  
- **Why the rule fires:** The rule’s first branch is satisfied (tenderness + pain worsens on movement). Even though the presentation is likely a simple gastroenteritis, the rule would trigger “TERMINATE_EMERGENCY,” leading to unnecessary emergency department admission and resource consumption.

**Why the Rule Behaves This Way**

1. **Schema Limitation:** The available predicates do not capture the *type* of pain (localized tenderness vs. diffuse epigastric discomfort). “abdominal_tenderness_reported_present” assumes the patient can articulate that the pain is localized to a specific area, which is not always the case in acute peritonitis where patients may describe diffuse pain.
2. **Edge‑Case Miss:** The rule’s reliance on **both** bowel absent *and* vomiting creates a false negative for patients whose peritonitis is manifested primarily by diffuse pain and lack of vomiting. This edge case is not covered by any retrieved passages, indicating a missing clinical nuance.
3. **Interaction with Other Rules:** If another rule (e.g., RF_GASTROINTESTINAL_001) flags “vomiting” or “abdominal pain” without the specific “tenderness” qualifier, the patient could be escalated to a lower‑acuity pathway, potentially delaying definitive care.

**The Case for Leaving the Rule Alone**

The strongest argument that the rule could be acceptable is that the current clinical guidelines for acute abdomen with peritonism explicitly require *documented* abdominal tenderness (or palpable peritoneal signs) as a primary trigger. If the intake protocol reliably captures localized tenderness, the rule’s failure to fire on diffuse pain may be justified. However, this assumption is not validated by the local corpus and may vary across settings (e.g., resource‑limited hospitals where tenderness is not always palpable).

**Outside My Seat**

- **Schema Gap:** The absence of a predicate for “diffuse epigastric pain” or “pain described as non‑localized” suggests a missing clinical construct in the registry schema. This gap could affect many rules that rely on tenderness as a primary trigger.
- **Potential Bias:** The rule may inadvertently favor patients who can articulate tenderness, potentially disadvantaging patients from populations where pain localization is less distinct (e.g., certain cultural or age groups).

**The One Decision a Clinician Must Answer**

**Should the rule be revised to include a pain‑type qualifier (e.g., “pain described as diffuse epigastric” or “pain not localized to a single point”) or should it remain as‑is, with the understanding that the intake protocol must capture localized tenderness reliably?** This decision hinges on whether the current schema can be extended to capture pain localization, and whether the clinical benefit of catching missed peritonitis outweighs the risk of false positives.

### Indian practice reviewer

**Missed Patient (Indian District Hospital Context)**  

**Rule:** RF_PERITONISM_001 – *Acute abdomen with peritonism*  
**Action:** TERMINATE_EMERGENCY  

**Why this rule may miss a patient in an Indian district hospital**

1. **Clinical Presentation Diverges from Western Descriptors**  
   - **Pain Characteristics:** In many Indian patients with perforated viscus (e.g., acute appendicitis, peptic ulcer perforation), the pain is often described as *crampy* or *diffuse* rather than *sharp, pressure‑like, or worsened by movement*. The encoded criterion “abdominal_tenderness_reported_present AND pain_worse_on_movement” may be absent because the tenderness is subtle and the patient may not associate movement with increased pain.  
   - **Vomiting Pattern:** Vomiting is frequently reported as *regurgitation of bile* or *mucus‑laden fluid* rather than classic *vomiting_present* flags. The rule’s second branch (abdominal_onset_sudden AND vomiting_present) may not fire because the onset is perceived as *gradual abdominal distension* rather than an acute “crisis” and vomiting is not explicitly documented as a separate event.  

2. **Diagnostic Gap – Bowel Status**  
   - The encoded criterion “bowels_absent” (neither stool nor flatus passed) is a strict requirement for the third branch. In resource‑limited settings, patients may present with *partial obstruction* where *flatus* is still audible or *soft stools* are passed intermittently, yet the intake agent may not capture this nuance, leading to a false‑negative.  
   - **Schema Issue:** The field registry explicitly defines “bowels_absent” as *no stool or flatus*, but the local data capture often records only *absence of stool* or *no audible flatus*. This mismatch can cause the rule to fail for patients who meet the clinical definition of peritonitis but not the exact wording used in the rule.  

3. **Population‑Specific Disease Burden**  
   - **Helicobacter pylori‑Associated Ulcer Perforation:** A common cause of acute abdomen in South Asia is *ulcer perforation* due to *H. pylori* infection. The pain may be *epigastric* and *radiate to the back* without the classic *pain‑worsened‑by‑movement* pattern, especially if the ulcer is *chronic* and the patient is on *NSAIDs*.  
   - **Gastro‑intestinal Tract Infections (e.g., Shigellosis):** Rapidly progressive peritonitis from *colonic ischemia* or *septic peritonitis* can present with *fever, tachycardia, and diffuse abdominal tenderness* but *no overt vomiting* or *no “pain‑worsened‑by‑movement”* description.  

4. **Referral Network Constraints**  
   - **Limited Imaging Availability:** Many district hospitals lack *immediate CT or ultrasound* for suspected perforation. Clinicians may defer definitive diagnosis to a tertiary center, leading to *delayed escalation* despite the rule’s intent to *terminate emergency*.  
   - **Transportation & Cost Barriers:** Patients may present late because of *financial constraints* or *distance to referral centers*, causing the rule to fire *after* the condition has progressed to a life‑threatening stage.  

**Concrete Patient Example**

| Attribute | Detail |
|-----------|--------|
| **Age** | 45‑year‑old male, works as a daily‑wage laborer |
| **Location** | Rural district hospital, no dedicated emergency department with 24‑hour imaging |
| **Chief Complaint** | “My stomach feels heavy and hurts, but I’m not sure if it’s a real emergency.” |
| **History** | Chronic *H. pylori* gastritis, on *over‑the‑counter NSAIDs* for mild pain for the past 6 months. |
| **Onset** | Gradual increase in abdominal distension over 48 hours; no sudden “crisis” described. |
| **Pain Description** | Diffuse crampy pain radiating to the back; not described as *pressure‑like* or *worsened by movement*. |
| **Vomiting** | Occasional *regurgitation of bile* (not counted as “vomiting_present” in intake). |
| **Bowel Status** | No audible flatus; stool passed only *once* 3 days ago (patient may not recognize this as “bowels_absent”). |
| **Associated Symptoms** | Mild fever (101 °F), tachycardia, mild dehydration, but these are not captured as separate flags. |
| **Intake Agent Entry** | “Abdominal tenderness reported = Yes”, “Pain worsened by movement = No”, “Vomiting present = No”, “Bowel status = No”. |
| **Result of Rule** | The rule **does not fire** because none of the three encoded branches are fully satisfied. |
| **Potential Outcome** | If the rule had fired, the patient could have been *immediately transferred* to a tertiary center for *CT‑guided peritoneal drainage*. As it stands, the condition may progress to *peritonitis* and *septic shock* before transport, increasing morbidity and mortality. |

**Key Takeaway**

The rule’s reliance on *pain‑worsened‑by‑movement* and *explicit vomiting* may miss a substantial subset of Indian patients whose presentation aligns more closely with *chronic ulcer perforation* or *septic peritonitis* that does not meet the Western‑described “acute abdomen” criteria. This mismatch reflects both the *disease burden* (e.g., H. pylori‑related perforation) and the *referral network limitations* (limited imaging, transport constraints) specific to district hospitals in India. The rule should either broaden the pain descriptors or include a separate branch for *partial bowel obstruction* with *fever* and *systemic signs* to capture these missed cases.
