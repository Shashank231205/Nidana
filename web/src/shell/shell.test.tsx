/* The frame, and the rule that the patient surface has none.
 *
 * The header test is not cosmetic. A nav link on the emergency screen is a way
 * out of an instruction that must not have one, so its absence is a safety
 * property and belongs in the suite rather than in a comment.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Header } from "./Header";
import { SubNav } from "./SubNav";
import { NameEntry } from "./NameEntry";
import { Home } from "./Home";
import { SERVICES, serviceById } from "./services";

afterEach(() => {
  window.location.hash = "";
});

describe("Header", () => {
  it("offers every service", () => {
    render(<Header active={null} actor="Priya" onChangeActor={() => {}} />);
    for (const service of SERVICES) {
      expect(screen.getByRole("link", { name: service.label })).toBeInTheDocument();
    }
  });

  it("marks the active service for a screen reader, not only visually", () => {
    render(<Header active="labs" actor="Priya" onChangeActor={() => {}} />);
    expect(screen.getByRole("link", { name: "Labs" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Rx" })).not.toHaveAttribute("aria-current");
  });

  it("shows who is at the machine", () => {
    render(<Header active={null} actor="Priya Sharma" onChangeActor={() => {}} />);
    expect(screen.getByRole("button", { name: /Priya Sharma/ })).toBeInTheDocument();
  });

  it("shows no name control when nobody has given one", () => {
    render(<Header active={null} actor={null} onChangeActor={() => {}} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("SubNav", () => {
  it("lists the screens of the service it is given", () => {
    const labs = serviceById("labs");
    if (labs === undefined) throw new Error("labs is missing from the service list");
    render(<SubNav service={labs} active="thresholds" />);
    for (const item of labs.screens) {
      expect(screen.getByRole("link", { name: item.label })).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: "Thresholds" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
});

describe("NameEntry", () => {
  it("will not continue without a name", () => {
    render(<NameEntry onSubmit={() => {}} />);
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  });

  it("says the name is not verified", () => {
    render(<NameEntry onSubmit={() => {}} />);
    expect(screen.getByText(/not verified/)).toBeInTheDocument();
  });

  it("passes the name on once one is typed", async () => {
    const onSubmit = vi.fn();
    render(<NameEntry onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Your name"), "Priya Sharma");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(onSubmit).toHaveBeenCalledWith("Priya Sharma");
  });

  it("treats whitespace as no name at all", async () => {
    render(<NameEntry onSubmit={() => {}} />);
    await userEvent.type(screen.getByLabelText("Your name"), "   ");
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  });
});

describe("Home", () => {
  it("names every service and what it does", () => {
    render(<Home actor="Priya" />);
    for (const service of SERVICES) {
      expect(screen.getByRole("link", { name: service.label })).toBeInTheDocument();
      expect(screen.getByText(service.summary)).toBeInTheDocument();
    }
  });
});

describe("the patient surface has no frame", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("renders triage without a header, even with a name recorded", async () => {
    window.sessionStorage.setItem("nidana.actor", "Priya");
    window.location.hash = "#/triage";
    const { App } = await import("../App");
    render(<App />);

    // No service navigation anywhere on the patient's screen.
    expect(screen.queryByRole("navigation", { name: "Services" })).not.toBeInTheDocument();
    for (const service of SERVICES) {
      expect(screen.queryByRole("link", { name: service.label })).not.toBeInTheDocument();
    }
  });
});
