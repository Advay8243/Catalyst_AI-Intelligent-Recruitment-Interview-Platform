import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScreeningClient } from "@/components/screening-client";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/screening",
}));

const candidate = {
  id: "cand-1",
  name: "Maya Chen",
  email: "maya@example.com",
  phone: "+1 555 0100",
  currentTitle: "Senior Product Designer",
  jobTitle: "Lead Product Designer",
  jdScore: 88,
  hrScore: 76,
  fitReason: "Strong product systems experience and excellent research background.",
  hrAnalysis: "Clear communicator with strong stakeholder examples.",
  scoreBreakdown: { skills: 92, experience: 85, education: 80, relevance: 91 },
  skills: ["Figma", "Research"],
};

function json(data: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(data),
  } as Response);
}

describe("ScreeningClient", () => {
  beforeEach(() => {
    push.mockReset();
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/jobs")) return json({ items: [{ id: "job-1", title: "Lead Product Designer" }] });
      return json({ items: [candidate], total: 1, page: 1, pageSize: 10 });
    }));
  });

  it("renders the required candidate table and scores", async () => {
    render(<ScreeningClient />);
    expect(await screen.findByText("Maya Chen")).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).getByText("Candidate")).toBeInTheDocument();
    expect(within(table).getByText("JD → Resume Score")).toBeInTheDocument();
    expect(within(table).getByText("HR Screening Score")).toBeInTheDocument();
    expect(within(table).getByText("Why Candidate Fits")).toBeInTheDocument();
    expect(within(table).getByText("88%")).toBeInTheDocument();
    expect(within(table).getByText("76%")).toBeInTheDocument();
  });

  it("opens a JD score breakdown", async () => {
    const user = userEvent.setup();
    render(<ScreeningClient />);
    await user.click(await screen.findByRole("button", { name: "JD score for Maya Chen" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("JD → Resume Score");
    expect(within(dialog).getByText("Required skills")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
  });

  it("sends search text to the backend query", async () => {
    const user = userEvent.setup();
    render(<ScreeningClient />);
    await screen.findByText("Maya Chen");
    await user.type(screen.getByRole("textbox", { name: "Search candidates" }), "maya chen");
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map(([url]) => String(url));
      expect(calls.some((url) => url.includes("search=maya+chen"))).toBe(true);
    });
  });

  it("sends filters and sorting to the backend query", async () => {
    const user = userEvent.setup();
    render(<ScreeningClient />);
    await screen.findByText("Maya Chen");
    await user.selectOptions(screen.getByLabelText("Filter by decision status"), "ADVANCED");
    await user.selectOptions(screen.getByLabelText("Minimum score"), "80");
    await user.selectOptions(screen.getByLabelText("Sort candidates"), "name");
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map(([url]) => String(url));
      expect(calls.some((url) => url.includes("status=ADVANCED") && url.includes("min_score=80") && url.includes("sort=name"))).toBe(true);
    });
  });

  it("navigates to the candidate call route", async () => {
    const user = userEvent.setup();
    render(<ScreeningClient />);
    await user.click(await screen.findByRole("button", { name: "Call Maya Chen" }));
    expect(push).toHaveBeenCalledWith("/screening/call/cand-1");
  });

  it("opens candidate review from the email status", async () => {
    const user = userEvent.setup();
    render(<ScreeningClient />);
    expect(await screen.findByText("✉ Not Sent")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Email history for Maya Chen" }));
    expect(push).toHaveBeenCalledWith("/screening/candidates/cand-1");
  });

  it("colors JD and HR scores using the configured thresholds", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/jobs")) return json({ items: [{ id: "job-1", title: "Lead Product Designer" }] });
      return json({
        items: [
          { ...candidate, id: "high", name: "High Scorer", jdScore: 92, hrScore: 90 },
          { ...candidate, id: "mid", name: "Mid Scorer", jdScore: 70, hrScore: 65 },
          { ...candidate, id: "low", name: "Low Scorer", jdScore: 40, hrScore: 50 },
        ],
        total: 3,
        page: 1,
        pageSize: 10,
      });
    }));
    render(<ScreeningClient />);
    expect(await screen.findByText("92%")).toHaveClass("text-[#027a48]");
    expect(screen.getByText("70%")).toHaveClass("text-[#b54708]");
    expect(screen.getByText("40%")).toHaveClass("text-[#b42318]");
  });
});
