/* The five services, and the screens inside each.
 *
 * One list, used by the header, the sub-nav and the router. A service added
 * here appears in all three; a service added to only one of them is the bug
 * this shape prevents.
 */

export interface Screen {
  readonly id: string;
  readonly label: string;
}

export interface Service {
  readonly id: string;
  readonly label: string;
  /** What it does, in words a clinician would use. Shown on the entry page. */
  readonly summary: string;
  readonly screens: readonly Screen[];
}

export const SERVICES: readonly Service[] = [
  {
    id: "consult",
    label: "Consult",
    summary: "Triage a patient and hand the findings to a clinician.",
    screens: [
      { id: "sessions", label: "Sessions" },
      { id: "audit", label: "Audit trail" },
    ],
  },
  {
    id: "scribe",
    label: "Scribe",
    summary: "Turn a consultation recording into a note the clinician signs.",
    screens: [
      { id: "encounters", label: "Encounters" },
      { id: "draft", label: "Draft a note" },
    ],
  },
  {
    id: "rx",
    label: "Rx",
    summary: "Check a prescription for interactions and dispensing blocks.",
    screens: [
      { id: "check", label: "Check a prescription" },
      { id: "read", label: "Read from text" },
    ],
  },
  {
    id: "labs",
    label: "Labs",
    summary: "Find critical values in a report and say what was not checked.",
    screens: [
      { id: "report", label: "Interpret a report" },
      { id: "extract", label: "Extract from text" },
      { id: "thresholds", label: "Thresholds" },
    ],
  },
  {
    id: "forensics",
    label: "Forensics",
    summary: "Record a medico-legal examination with an unbroken chain of custody.",
    screens: [
      { id: "examinations", label: "Examinations" },
      { id: "statutes", label: "Statute lookup" },
    ],
  },
];

export const serviceById = (id: string): Service | undefined =>
  SERVICES.find((service) => service.id === id);
