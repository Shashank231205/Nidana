import { describe, expect, it } from "vitest";
import { hrefFor } from "./useRoute";
import { SERVICES, serviceById } from "./services";

/* The header, the sub-nav and the router all read one list. These pin the
 * property that makes that safe: every link the navigation can produce is a
 * route the router resolves.
 */

describe("service list", () => {
  it("gives every service a unique id", () => {
    const ids = SERVICES.map((service) => service.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("gives every service at least one screen", () => {
    for (const service of SERVICES) {
      expect(service.screens.length).toBeGreaterThan(0);
    }
  });

  it("gives every screen a unique id within its service", () => {
    for (const service of SERVICES) {
      const ids = service.screens.map((screen) => screen.id);
      expect(new Set(ids).size).toBe(ids.length);
    }
  });

  it("finds every service by its own id", () => {
    for (const service of SERVICES) {
      expect(serviceById(service.id)).toBe(service);
    }
  });

  it("returns nothing for an id no service has", () => {
    expect(serviceById("radiology")).toBeUndefined();
  });
});

describe("hrefFor", () => {
  it("builds a service route", () => {
    expect(hrefFor("labs")).toBe("#/labs");
  });

  it("builds a screen route", () => {
    expect(hrefFor("labs", "thresholds")).toBe("#/labs/thresholds");
  });

  it("round-trips every screen in the list back to its own service", () => {
    for (const service of SERVICES) {
      for (const screen of service.screens) {
        const parts = hrefFor(service.id, screen.id).replace("#/", "").split("/");
        expect(parts[0]).toBe(service.id);
        expect(parts[1]).toBe(screen.id);
        expect(serviceById(parts[0] ?? "")).toBe(service);
      }
    }
  });
});
