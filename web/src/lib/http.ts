/* One request function, five services.
 *
 * Each service is its own FastAPI app on its own port, so a call names the
 * service rather than assuming one origin. In development Vite proxies each
 * prefix to the right port; in a deployment they sit behind one reverse proxy
 * on the paths below, which is why the prefix is part of the path and not a
 * host.
 *
 * Error `detail` from the backend is written to state the remedy, so it is
 * carried through verbatim rather than replaced with a generic message.
 */

export type ServiceId = "consult" | "scribe" | "rx" | "labs" | "forensics";

const PREFIX: Record<ServiceId, string> = {
  consult: "/api/consult",
  scribe: "/api/scribe",
  rx: "/api/rx",
  labs: "/api/labs",
  forensics: "/api/forensics",
};

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface ValidationItem {
  readonly msg?: unknown;
  readonly loc?: unknown;
}

function detailFrom(payload: unknown, fallback: string): string {
  if (typeof payload !== "object" || payload === null) return fallback;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    // 422 from FastAPI validation: a list of per-field errors. The field path
    // is kept because "field required" without the field names nothing.
    const messages = (detail as ValidationItem[])
      .map((item) => {
        const message = typeof item.msg === "string" ? item.msg : null;
        if (message === null) return null;
        const where = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "";
        return where.length > 0 ? `${where}: ${message}` : message;
      })
      .filter((message): message is string => message !== null);
    if (messages.length > 0) return messages.join("; ");
  }
  return fallback;
}

export async function request<T>(
  service: ServiceId,
  method: "GET" | "POST",
  path: string,
  body?: unknown,
): Promise<T> {
  const init: RequestInit =
    body === undefined
      ? { method }
      : {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        };

  let response: Response;
  try {
    response = await fetch(PREFIX[service] + path, init);
  } catch {
    throw new ApiError(
      0,
      `Cannot reach the ${service} service on this machine. Check that it is running.`,
    );
  }

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // A non-JSON error body leaves the status line as the detail.
    }
    throw new ApiError(
      response.status,
      detailFrom(payload, `${response.status} ${response.statusText}`),
    );
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
