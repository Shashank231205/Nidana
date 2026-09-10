import { useEffect, useState } from "react";
import { request } from "../lib/http";
import type { ServiceId } from "../lib/http";

/* What a service can actually do right now, read from its own /health.
 *
 * This is the answer to a screen that shows a form and nothing else. A
 * clinician opening Rx wants to know before typing whether interaction
 * checking is even configured on this deployment, and the health endpoint
 * already says. Leaving it in a JSON response nobody reads, while the screen
 * looks ready for anything, is how a pharmacist ends up trusting an empty
 * findings list.
 *
 * A capability that is off is shown as prominently as one that is on. That is
 * the same rule the result screens follow.
 */

interface Capability {
  readonly label: string;
  readonly on: boolean;
  /** What it means that this is off. Empty when it is on. */
  readonly caveat?: string;
}

interface Health {
  readonly status?: string;
  readonly [key: string]: unknown;
}

/** A health field as a number, or zero. The payload is unknown by design:
 * each service answers with its own shape and none is validated here. */
const count = (value: unknown): number => (typeof value === "number" ? value : 0);

const capabilitiesFor = (service: ServiceId, health: Health): readonly Capability[] => {
  switch (service) {
    case "consult":
      return [
        { label: "Red flag rules loaded", on: health["rules_loaded"] === true },
        {
          label: "Every rule clinician-verified",
          on:
            count(health["model_attested_rules"]) === 0 &&
            (Array.isArray(health["disclosures"])
              ? health["disclosures"].length === 0
              : true),
          caveat:
            "Some rules run on a model's reading. Every triage they affect says so.",
        },
      ];
    case "rx":
      return [
        {
          label: "Brand to molecule resolution",
          on: health["brand_resolution_available"] === true,
          caveat: "Molecules are taken as typed rather than resolved from a brand index.",
        },
        {
          label: "Interaction checking",
          on: health["interaction_checking_available"] === true,
          caveat:
            "No interaction dataset is configured, so no pair is examined. An empty result is not a clear one.",
        },
      ];
    case "labs":
      return [
        {
          label: `${count(health["thresholds_loaded"])} critical thresholds loaded`,
          on: count(health["thresholds_loaded"]) > 0,
        },
      ];
    case "scribe":
      return [
        { label: "Note rules loaded", on: health["rules_loaded"] === true },
        {
          label: "Audio capture",
          on: false,
          caveat:
            "Transcription runs on this machine and that endpoint is not built. Enter the transcript as text.",
        },
      ];
    case "forensics":
      return [
        { label: "IPC to BNS table loaded", on: true },
        {
          label: "Statutory classification reviewed",
          on: false,
          caveat: "The table renumbers sections. It does not say which section applies.",
        },
      ];
  }
};

export function ServiceStatus({ service }: { readonly service: ServiceId }): JSX.Element {
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    request<Health>(service, "GET", "/health")
      .then((result) => {
        if (live) setHealth(result);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [service]);

  if (failed) {
    return (
      <aside className="status status-down">
        <p className="label">Not reachable</p>
        <p className="body">
          The {service} service is not running on this machine. Nothing on this
          screen will work until it is started.
        </p>
      </aside>
    );
  }

  if (health === null) {
    return (
      <aside className="status">
        <p className="loading">Checking what this service can do</p>
      </aside>
    );
  }

  const capabilities = capabilitiesFor(service, health);

  return (
    <aside className="status">
      <p className="label">On this deployment</p>
      <ul className="plain status-list">
        {capabilities.map((capability) => (
          <li key={capability.label} className="status-item">
            <span
              className={capability.on ? "status-dot status-on" : "status-dot status-off"}
              aria-hidden="true"
            />
            <span className="status-text">
              <span className="data">{capability.label}</span>
              {!capability.on && capability.caveat !== undefined && (
                <span className="meta status-caveat">{capability.caveat}</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
