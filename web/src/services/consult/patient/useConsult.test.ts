/* The ordering these tests pin is a safety property, not a UI detail.
 *
 * The vanilla build collected the consent checkbox and never posted it, so
 * every first turn returned 403 and no consultation could complete. A test
 * that only asserts "a question appears" would have passed against a mock
 * that did not care about the order.
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useConsult } from "./useConsult";

const SESSION = "11111111-2222-3333-4444-555555555555";

interface Call {
  readonly path: string;
  readonly body: unknown;
}

let calls: Call[] = [];

function mockFetch(responder: (path: string) => [number, unknown]): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.toString();
      calls.push({
        path,
        body: init?.body === undefined ? undefined : JSON.parse(String(init.body)),
      });
      const [status, payload] = responder(path);
      return {
        ok: status >= 200 && status < 300,
        status,
        statusText: "",
        json: async () => payload,
      } as Response;
    }),
  );
}

const question = {
  shape: "next_question",
  session_id: SESSION,
  turn_index: 0,
  question: "Where is the pain?",
  emergency: null,
  triage: null,
  disclosures: [],
};

beforeEach(() => {
  calls = [];
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("consent ordering", () => {
  it("records consent before taking any turn", async () => {
    mockFetch((path) => {
      if (path.endsWith("/v1/sessions")) return [201, { session_id: SESSION }];
      if (path.endsWith("/consent")) return [200, { granted: true }];
      return [200, question];
    });

    const { result } = renderHook(() => useConsult());
    await act(async () => {
      await result.current.begin(true);
    });

    const paths = calls.map((call) => call.path);
    const consentAt = paths.findIndex((path) => path.endsWith("/consent"));
    const turnAt = paths.findIndex((path) => path.endsWith("/turns"));

    expect(consentAt).toBeGreaterThanOrEqual(0);
    expect(turnAt).toBeGreaterThan(consentAt);
  });

  it("sends the purpose the DPDP Act binds the consent to", async () => {
    mockFetch((path) => {
      if (path.endsWith("/v1/sessions")) return [201, { session_id: SESSION }];
      if (path.endsWith("/consent")) return [200, { granted: true }];
      return [200, question];
    });

    const { result } = renderHook(() => useConsult());
    await act(async () => {
      await result.current.begin(true);
    });

    const consent = calls.find((call) => call.path.endsWith("/consent"));
    expect(consent?.body).toEqual({ granted: true, purpose: "triage" });
  });

  it("surfaces the backend's 403 detail rather than a generic message", async () => {
    const detail =
      "session has no recorded consent and takes no turns; post the patient's decision first";
    mockFetch((path) => {
      if (path.endsWith("/v1/sessions")) return [201, { session_id: SESSION }];
      if (path.endsWith("/consent")) return [200, { granted: true }];
      return [403, { detail }];
    });

    const { result } = renderHook(() => useConsult());
    await act(async () => {
      await result.current.begin(true);
    });

    await waitFor(() => {
      expect(result.current.state.phase).toBe("error");
    });
    expect(result.current.state.error).toBe(detail);
  });
});

describe("disclosures", () => {
  it("keeps a disclosure a later response omits", async () => {
    const disclosure = "RF_ACS_001: ran on a model's reading";
    let turnCount = 0;
    mockFetch((path) => {
      if (path.endsWith("/v1/sessions")) return [201, { session_id: SESSION }];
      if (path.endsWith("/consent")) return [200, { granted: true }];
      turnCount += 1;
      if (turnCount === 1) return [200, { ...question, disclosures: [disclosure] }];
      return [
        200,
        {
          ...question,
          shape: "completed_triage",
          question: null,
          triage: { band: "U3", return_criteria: ["Chest pain returns"] },
          disclosures: [],
        },
      ];
    });

    const { result } = renderHook(() => useConsult());
    await act(async () => {
      await result.current.begin(true);
    });
    expect(result.current.state.disclosures).toEqual([disclosure]);

    await act(async () => {
      await result.current.answer("here");
    });

    expect(result.current.state.phase).toBe("outcome");
    expect(result.current.state.disclosures).toEqual([disclosure]);
  });
});

describe("shape dispatch", () => {
  it("routes a terminal emergency to the emergency phase", async () => {
    mockFetch((path) => {
      if (path.endsWith("/v1/sessions")) return [201, { session_id: SESSION }];
      if (path.endsWith("/consent")) return [200, { granted: true }];
      return [
        200,
        {
          ...question,
          shape: "terminal_emergency",
          question: null,
          emergency: { capabilities_required: ["cath_lab"] },
        },
      ];
    });

    const { result } = renderHook(() => useConsult());
    await act(async () => {
      await result.current.begin(true);
    });

    expect(result.current.state.phase).toBe("emergency");
  });

  it("reports an unreachable server with the remedy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("network");
      }),
    );

    const { result } = renderHook(() => useConsult());
    await act(async () => {
      await result.current.begin(true);
    });

    expect(result.current.state.phase).toBe("error");
    expect(result.current.state.error).toContain("Check that it is running");
  });
});
