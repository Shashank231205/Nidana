# RF_PE_001 — Possible pulmonary embolism

**This rule remains blocked from release.** A panel review is not a verification: it records that the reading has been done and refers the rule to a clinician. Only a named, qualified person can clear `verify_before_ship`, and nothing below does.

Referred to: **clinical-pathology specialist**. Reviewed 2026-09-10 by granite4.1:3b (panel 1.0.0).

> **Warning — emergency physician** was cut off before finishing, so what survives reads more one-sided than it was.

> **Warning — Indian practice reviewer** used approving language.

## RF_PE_001 – panel brief

**The panel has not verified this rule.** It remains blocked from release and requires a named clinician.

### What the panel agrees on
1. **Missed cases** – The rule fails to fire for patients who present with dyspnoea and unilateral leg swelling but lack chest‑pain or haemoptysis. This is a real clinical gap, especially in populations (e.g., diabetics with COPD in India) where chest pain is not a reliable symptom of PE.
2. **Over‑referral risk** – Patients who truly have PE (e.g., classic chest‑pain‑plus‑dyspnoea‑plus‑recent‑immobility) will be correctly flagged, but the rule’s reliance on chest pain may cause unnecessary escalation for atypical presentations, potentially delaying care for those who would benefit from earlier imaging.
3. **Schema limitation** – The rule does not capture “recent immobility” as a binary flag; it expects a documented period (e.g., “bedridden for >24 h”), which may not be recorded in all clinical notes. This could lead to missed cases even when the presentation is otherwise appropriate.

### Where the panel disagrees
- **Emergency physician** (Western‑focused) argues that the rule’s inclusion of chest‑pain and haemoptysis is justified because these are common and readily documented in many emergency settings, reducing false‑positive imaging referrals.
- **Indian practice reviewer** contends that in Indian district hospitals, a high proportion of PE cases present without chest pain (e.g., diabetics with COPD), and the rule’s requirement for chest pain may lead to missed diagnoses, increasing morbidity and mortality.
- **Safety engineer** suggests that the rule’s narrowness may cause over‑referral for patients who truly have PE (e.g., classic chest‑pain‑plus‑dyspnoea‑plus‑immobility), potentially delaying necessary care for those with atypical presentations.

**What turns the choice on**
- **Clinical context:** Whether the rule is deployed in a setting where chest pain is a reliable symptom (Western emergency medicine) versus a setting where it is often absent (Indian district hospitals with a high prevalence of diabetes and COPD).
- **Resource constraints:** If imaging capacity is limited, a broader rule that flags on leg swelling and recent immobility may be preferable to avoid unnecessary referrals. Conversely, if imaging is readily available, retaining the rule may be acceptable to avoid false‑positives.
- **Risk of missed PE:** The Indian reviewer’s concern about under‑triage of a common PE phenotype (diabetic‑COPD patients) versus the emergency physician’s concern about over‑triage in settings where chest pain is common.

### Refer to
A **clinical‑pathology specialist** (e.g., emergency medicine or critical care physician with experience in low‑resource settings) should review the rule to determine the appropriate balance between specificity for chest‑pain‑related PE and sensitivity for atypical presentations.

### Questions for the verifying clinician
1. **Is the rule’s symptom set (chest pain + haemoptysis) appropriate for the primary clinical environment where it will be used?** If not, should an alternative symptom (e.g., leg swelling + recent immobility) be added as a sufficient trigger?
2. **How will the rule be integrated with existing triage pathways and imaging protocols in the target setting?** Will additional clinical decision support (e.g., Wells score) be required to guide escalation for atypical presentations?
3. **What is the expected impact on false‑positive imaging referrals and on the timeliness of anticoagulation initiation for patients with atypical PE presentations?** Should the rule be modified to include a “clinical judgment” step for patients lacking chest pain?
4. **Are there any local data or guideline recommendations that support expanding the rule to capture leg swelling + recent immobility as a primary trigger?** If so, how can these be incorporated without compromising safety?
5. **What resources (e.g., training, documentation standards) are needed to ensure that clinicians reliably capture “recent immobility” and other ancillary criteria that are not currently captured in the current data model?**

---

## The reviews behind this brief

### emergency physician

**Headline:** The rule RF_PE_001 misses patients with a classic “silent” presentation of acute pulmonary embolism—i.e., those who have dyspnoea and leg swelling but no chest‑pain or haemoptysis, which are required by the rule’s three branches.

**Missed patient (concrete example):**

- **Demographics:** 58‑year‑old woman, BMI ≈ 30 kg/m², no known history of deep‑vein thrombosis.
- **Chief complaint:** “I feel like I can’t catch my breath,” reported at rest, with a mild “tightness” in the chest that she attributes to anxiety rather than pain.
- **Physical findings:** Unilateral swelling of the left leg (ankle and calf distal to the knee), warm to touch, no warmth or redness over the calf. No audible crackles or wheeze noted on exam.
- **History:** Recent travel for a 5‑day business trip; spent most of the trip sitting on a long flight (≈ 12 h) with limited mobility. No known cardiac disease, hypertension, or diabetes.
- **Why it fails the rule:**  
  1. **Dyspnoea_present** – present.  
  2. **Pain_onset_sudden** – absent (the patient’s “tightness” is not described as pain).  
  3. **Unilateral_leg_swelling** – present.  
  → None of the three encoded branches are satisfied, so the rule never terminates the emergency session.

**Why this patient is a realistic missed case:**

- Silent PE is well‑documented in the literature, especially in patients with asymptomatic or minimally symptomatic presentations.  
- Many such patients present with dyspnoea and leg swelling but lack chest‑pain or haemoptysis, which are the only pain‑related criteria the rule checks.  
- The absence of chest‑pain or haemoptysis means the rule never fires, potentially delaying imaging and anticoagulation.

**Implication:** An emergency physician who relies solely on this rule may miss a life‑threatening PE in a patient who otherwise appears stable but is experiencing a classic “silent” embolic event. Immediate imaging (CT pulmonary angiography) should be pursued in any patient with dyspnoea and unilateral leg swelling, regardless of chest‑pain status.

### safety engineer

**Headline:** The rule RF_PE_001 is too narrow and will miss a subset of patients who present with classic pulmonary embolism (PE) features but lack the specific limb‑swelling or haemoptysis cues that drive two of its branches.

**Misses**

**Patient 1 – Atypical PE (no leg swelling, no haemoptysis):**  
- **Age / Sex:** 62‑year‑old male, known history of deep‑vein thrombosis (DVT) from a prior surgery.  
- **Presentation:** 30 minutes after a short walk, he develops sudden dyspnoea and a sensation of “tightness” in his chest. He reports **chest pain** (sharp, pleuritic) and **dyspnoea** (shortness of breath at rest). No leg swelling is reported, and there is no haemoptysis.  
- **Why it fails:** The rule’s first two branches require **unilateral leg swelling** (branch 1) or **haemoptysis** (branch 2). This patient meets only the **chest‑pain + dyspnoea** combination, which triggers the third branch, but the rule’s design assumes that chest pain alone is sufficient to flag PE when leg swelling or haemoptysis are absent. In reality, a PE with chest pain alone can still be life‑threatening and may be missed if the clinician does not consider the broader clinical context (e.g., recent immobilisation, known DVT history).  

**Patient 2 – Young adult with PE mimicking other thoracic emergencies:**  
- **Age / Sex:** 28‑year‑old female, no known cardiovascular disease.  
- **Presentation:** Sudden onset of dyspnoea and **dizziness/fainting** after a minor fall. She reports **chest pain** (sharp, pleuritic) and **dyspnoea**. No leg swelling, no haemoptysis, and no recent immobilisation is noted.  
- **Why it fails:** The rule’s third branch (chest‑pain + dyspnoea + recent immobility) is triggered only if the patient has a documented period of immobility (e.g., bedridden, recent surgery). In this case, the immobility is not captured, so the rule will not fire even though the clinical picture is classic for PE.  

**Over‑referrals**

**Patient 3 – Non‑PE presentation that satisfies the rule’s criteria:**  
- **Age / Sex:** 45‑year‑old male, no known DVT.  
- **Presentation:** Sudden dyspnoea and **dyspnoea on exertion**; reports **chest pain** (pressure‑like) and **dyspnoea**. No leg swelling, no haemoptysis, and no documented recent immobilisation.  
- **Why it fires:** The rule’s third branch (chest‑pain + dyspnoea + recent immobility) can be satisfied by many non‑PE conditions (e.g., myocardial infarction, severe asthma exacerbation). If the clinician does not perform further work‑up (e.g., imaging, D‑dimer), the rule will lead to an unnecessary termination of the emergency session, potentially delaying definitive care for a true PE.  

**The case for leaving it alone**

The rule is derived from a guideline that emphasizes the presence of **leg swelling or haemoptysis** as red‑flag features for PE. In many clinical settings—especially where the patient population has a high prevalence of DVT or where the emergency department workflow prioritises rapid escalation for those specific cues—the omission of leg swelling/haemoptysis may be intentional to avoid over‑triage. If the rule is used in a context where:

1. **Leg swelling and haemoptysis are common and readily documented** (e.g., in patients with known DVT or recent surgery), and  
2. **Further diagnostic testing (e.g., CT pulmonary angiography) is readily available**,  

then the rule’s narrowness may not materially increase missed PE cases. The cost of over‑referral (unnecessary imaging, patient anxiety) is modest compared with the potential harm of missing a PE in a patient who truly has those limb‑swelling or haemoptysis cues.

**Outside my seat**

- **Schema gap:** The rule does not capture **recent immobility** as a binary flag; it expects a documented period (e.g., “bedridden for >24 h”). If the system only stores discrete events (e.g., “post‑operative”), the rule may fail to fire even when clinically appropriate. This suggests a need for a more flexible temporal predicate (e.g., “immobility within the last 48 h”) that can be derived from existing encounter notes.  
- **Potential integration with other rules:** RF_PE_001 overlaps with other pulmonary‑embolism‑related rules (e.g., RF_AORTIC_001) that use different symptom sets. If a patient meets criteria for both rules, the order of evaluation matters—terminating the session after the first match could prematurely close a case that actually requires a different pathway (e.g., imaging protocol).  

**The one decision I would put to a clinician**

**Should the rule be expanded to include a “recent immobility” predicate (e.g., documented bedrest or postoperative status) and/or a broader chest‑pain definition (including pleuritic or pressure‑like chest pain) to capture patients like Patient 1 and Patient 2, while simultaneously adding a safety check to avoid over‑referral in cases where leg swelling/haemoptysis are absent?**  

If the clinician decides to keep the rule as‑is, the justification should address the balance between missed PE risk and the cost of unnecessary escalation. If the clinician decides to modify the rule, the next steps involve:

1. **Defining “recent immobility”** (e.g., “immobilised for ≥24 h” or “post‑operative” flag).  
2. **Clarifying chest‑pain descriptors** to include pleuritic/pressure‑like pain.  
3. **Adding a post‑rule triage step** (e.g., prompt for further imaging or D‑dimer) to mitigate over‑referral.  

Only after these clarifications should the rule be considered ready for clinical deployment.

### Indian practice reviewer

**Headline:** The rule RF_PE_001, as written for a Western emergency setting, fails to capture a common presentation of pulmonary embolism (PE) that is prevalent in Indian district hospitals—PE occurring in patients with diabetes and chronic obstructive pulmonary disease (COPD) who present with dyspnoea and leg swelling but lack chest‑pain or haemoptysis.

### Misses
**Concrete patient (missed case):**  
- **Demographics:** 58‑year‑old male, known type‑2 diabetes mellitus for 10 years, smoker (20 cigarettes/day), on chronic bronchitis therapy.  
- **Chief complaint:** Sudden onset of dyspnoea (shortness of breath) over the last 2 hours, described as “laboured breathing” and “feeling of breathlessness even at rest.” No chest pain described.  
- **Physical findings:** Unilateral swelling of the left leg (ankle and calf), warm to touch, no warmth or erythema on the right side. No haemoptysis reported.  
- **History:** Recent immobilisation due to a minor fall 3 days ago, leading to a temporary inability to ambulate. No prior known PE, no recent surgery or trauma.  
- **Why the rule fires:** The rule requires **chest_pain_present** (which is absent) and **pain_onset_sudden** (present) together with **dyspnoea_present** (present) **and** either **unilateral_leg_swelling** (present) **or** **haemoptysis_present** (absent). Because the required **chest_pain_present** is missing, the rule does not fire.  

**Implication:** This patient would be triaged as “non‑PE” by the current rule, potentially delaying diagnosis and treatment of a life‑threatening condition. In Indian district hospitals, diabetic‑related PE is a leading cause of sudden dyspnoea and leg swelling, especially in smokers and those with COPD, yet the rule’s chest‑pain requirement excludes them.

### Over‑referrals
**Concrete patient (over‑referral):**  
- **Demographics:** 45‑year‑old female, no known comorbidities.  
- **Chief complaint:** Sudden onset of dyspnoea, associated with **haemoptysis** (coughing up blood) and **pain on exertion** (described as chest‑pain).  
- **Physical findings:** Unilateral leg swelling, recent immobility after a minor fall.  
- **Rule outcome:** Fires because all three branches are satisfied (dyspnoea + pain on exertion + leg swelling; dyspnoea + haemoptysis + pain on exertion; dyspnoea + chest pain + recent immobility). This patient would be escalated to the emergency department for imaging and anticoagulation, which is appropriate for classic PE presentation.

**Consideration:** While this scenario is correctly captured, the rule’s reliance on chest pain may cause missed cases in populations where chest pain is less common (e.g., diabetics with COPD), leading to under‑triage of potentially fatal PE.

### The case for leaving it alone
The rule’s design reflects Western emergency medicine guidelines that prioritize chest pain as a primary symptom of PE. In many high‑income settings, chest pain is a hallmark of acute coronary syndrome, which can mimic PE. By requiring chest pain, the rule reduces false‑positive referrals to imaging, a critical safety measure in resource‑constrained environments where imaging capacity is limited.

**However:** In Indian district hospitals, the disease burden includes a high prevalence of diabetes and COPD, where PE often presents without chest pain. Allowing the rule to remain unchanged would risk delayed diagnosis and increased morbidity/mortality among a sizable subset of patients.

### Outside my seat
- **Supply chain / referral network:** The rule does not account for the typical referral pathway in Indian district hospitals, where patients with suspected PE are often first evaluated in primary care or community health centres before being referred to tertiary centres. If the rule is applied early, it could prevent timely escalation, whereas a broader rule might ensure that patients with atypical presentations are still flagged for specialist review.
- **Cultural communication gaps:** The rule assumes patients can articulate “chest pain” in the same way Western patients do. In many Indian communities, dyspnoea and leg swelling may be described as “breathing difficulty” or “leg swelling,” which may not be captured by the current predicate `chest_pain_present`.

### The one decision I would put to a clinician
**Should the rule be modified to include an alternative symptom (e.g., leg swelling with dyspnoea) as a sufficient trigger for termination, or should the rule remain as is with a concurrent clinical judgment to consider PE in patients lacking chest pain?**  
- **If modified:** Define a new branch (e.g., `dyspnoea_present AND unilateral_leg_swelling AND recent_immobility_present`) to capture the diabetic‑COPD PE phenotype, acknowledging that chest pain may be absent.
- **If retained:** Implement a clinical decision rule that prompts clinicians to consider PE in any patient with dyspnoea and leg swelling, especially in diabetics or smokers, even if chest pain is absent, and use additional risk scores (e.g., Wells criteria) to triage further.

**Why this matters:** The decision directly impacts patient safety, resource allocation, and the feasibility of applying the rule across diverse clinical settings in India. A well‑justified change would ensure that the rule remains clinically effective without unnecessarily increasing false‑positive referrals.
