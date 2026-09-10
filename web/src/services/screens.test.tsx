/* The screens, and the one property they all share.
 *
 * Every service in this product reports what it could not check as plainly as
 * what it found, because an empty findings list reads as "nothing wrong" when
 * what is true may be "this was not examined". These tests pin that: a screen
 * that renders findings and silently drops the coverage gap is the failure
 * being guarded against, and it looks perfectly fine in a screenshot.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RxCheck } from "./rx/RxCheck";
import { LabsThresholds } from "./labs/LabsThresholds";
import { CriticalFindings } from "./labs/CriticalFindings";
import { ForensicsStatutes } from "./forensics/ForensicsStatutes";
import { ConsultAudit } from "./consult/clinician/ConsultAudit";

function mockJson(payload: unknown, status = 200): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: status >= 200 && status < 300,
      status,
      statusText: "",
      json: async () => payload,
    })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Rx: interactions that were not checked", () => {
  const base = {
    check_id: "c1",
    findings: [],
    blocks_dispensing: false,
    brand_resolution_available: true,
    interaction_checking_available: false,
    molecules_not_interaction_checked: [],
  };

  async function runCheck(payload: unknown): Promise<void> {
    mockJson(payload, 201);
    render(<RxCheck actor="Priya" />);
    await userEvent.type(screen.getAllByPlaceholderText("Brand as written")[0]!, "Crocin");
    await userEvent.type(
      screen.getAllByPlaceholderText("Molecules, comma separated")[0]!,
      "paracetamol",
    );
    await userEvent.click(screen.getByRole("button", { name: "Run every check" }));
  }

  it("says interactions were not checked rather than showing an empty result", async () => {
    await runCheck(base);
    await waitFor(() => {
      expect(screen.getByText(/Interactions were not checked/)).toBeInTheDocument();
    });
    expect(screen.getByText(/not the same as finding none/)).toBeInTheDocument();
  });

  it("names the molecules a configured dataset does not cover", async () => {
    await runCheck({
      ...base,
      interaction_checking_available: true,
      molecules_not_interaction_checked: ["ashwagandha"],
    });
    await waitFor(() => {
      expect(screen.getByText("ashwagandha")).toBeInTheDocument();
    });
    expect(screen.getByText(/skipped rather than cleared/)).toBeInTheDocument();
  });

  it("shows a dispensing block where one exists", async () => {
    await runCheck({
      ...base,
      interaction_checking_available: true,
      blocks_dispensing: true,
      findings: [
        {
          kind: "duplicate_molecule",
          severity: "major",
          molecules: ["paracetamol"],
          written_as: ["Crocin", "Combiflam"],
          message: "paracetamol appears on 2 lines",
          source: "Derived from the resolved molecule list",
          blocks_dispensing: true,
        },
      ],
    });
    await waitFor(() => {
      expect(screen.getByText("Do not dispense")).toBeInTheDocument();
    });
    expect(screen.getByText(/paracetamol appears on 2 lines/)).toBeInTheDocument();
  });
});

describe("Labs: unverified thresholds", () => {
  it("says how many thresholds nobody has signed", async () => {
    mockJson({ count: 10, unverified: ["potassium", "sodium"] });
    render(<LabsThresholds />);
    await waitFor(() => {
      expect(screen.getByText("2 of 10 unverified")).toBeInTheDocument();
    });
    expect(screen.getByText("potassium")).toBeInTheDocument();
  });

  it("says so plainly when every threshold is verified", async () => {
    mockJson({ count: 10, unverified: [] });
    render(<LabsThresholds />);
    await waitFor(() => {
      expect(screen.getByText("Every threshold has been verified.")).toBeInTheDocument();
    });
  });
});

describe("Labs: a clear result is not reassurance", () => {
  it("shows unit mismatches above an empty finding list", () => {
    render(
      <CriticalFindings findings={[]} unitMismatches={["troponin i"]} hasCritical={false} />,
    );
    expect(screen.getByText("Not checked")).toBeInTheDocument();
    expect(screen.getByText("troponin i")).toBeInTheDocument();
    expect(
      screen.getByText(/among the analytes that could be checked/),
    ).toBeInTheDocument();
  });

  it("marks a finding whose threshold nobody verified", () => {
    render(
      <CriticalFindings
        findings={[
          {
            analyte: "potassium",
            value: 6.9,
            unit: "mmol/L",
            flag: "high",
            threshold: 6.0,
            source: "PLACEHOLDER",
            unverified: true,
            message: "Potassium above the critical threshold",
          },
        ]}
        unitMismatches={[]}
        hasCritical
      />,
    );
    expect(screen.getByText("Critical value")).toBeInTheDocument();
    expect(screen.getByText(/This threshold is a placeholder/)).toBeInTheDocument();
  });
});

describe("Forensics: the statute table is not legal advice", () => {
  it("says a lawyer has not checked the correspondence", async () => {
    mockJson({
      query: "302",
      numbering: "ipc",
      matches: [
        {
          ipc: "302",
          bns: "103",
          title: "Punishment for murder",
          changed: true,
          repealed: false,
          needs_legal_check: true,
          note: null,
        },
      ],
      legally_reviewed: false,
    });
    render(<ForensicsStatutes />);
    await userEvent.type(screen.getByLabelText("Section number"), "302");
    await userEvent.click(screen.getByRole("button", { name: "Look up" }));

    await waitFor(() => {
      expect(screen.getByText("BNS 103")).toBeInTheDocument();
    });
    expect(screen.getByText(/has not been checked by a lawyer/)).toBeInTheDocument();
    expect(screen.getByText(/wording changed, not only the number/)).toBeInTheDocument();
  });

  it("says nothing was found rather than showing an empty list", async () => {
    mockJson({ query: "124A", numbering: "ipc", matches: [], legally_reviewed: false });
    render(<ForensicsStatutes />);
    await userEvent.type(screen.getByLabelText("Section number"), "124A");
    await userEvent.click(screen.getByRole("button", { name: "Look up" }));

    await waitFor(() => {
      expect(screen.getByText(/No correspondence recorded/)).toBeInTheDocument();
    });
  });
});

describe("Consult: a broken audit chain is visible", () => {
  const entry = (sequence: number, previous: string, hash: string) => ({
    sequence,
    event_type: "consent_recorded",
    actor: "patient",
    occurred_at: "2026-09-10T00:00:00Z",
    payload: {},
    corrects_sequence: null,
    previous_hash: previous,
    entry_hash: hash,
  });

  async function open(entries: unknown[]): Promise<void> {
    mockJson({ session_id: "s1", entries });
    render(<ConsultAudit />);
    await userEvent.type(screen.getByLabelText("Session identifier"), "s1");
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
  }

  it("says nothing when every entry links to the one before it", async () => {
    await open([entry(0, "0".repeat(64), "aaa"), entry(1, "aaa", "bbb")]);
    await waitFor(() => {
      expect(screen.getByText("2 entries")).toBeInTheDocument();
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("raises an alert when an entry does not link to its predecessor", async () => {
    await open([entry(0, "0".repeat(64), "aaa"), entry(1, "tampered", "bbb")]);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/altered or an entry is missing/);
    });
  });
});

describe("errors carry the backend's remedy", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 503,
        statusText: "Service Unavailable",
        json: async () => ({
          detail: "service is still starting; the brand index is not loaded yet",
        }),
      })),
    );
  });

  it("shows the detail rather than a generic message", async () => {
    render(<LabsThresholds />);
    await waitFor(() => {
      expect(screen.getByText(/the brand index is not loaded yet/)).toBeInTheDocument();
    });
  });
});
