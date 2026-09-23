import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScreeningClient } from "@/components/screening-client";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: push }),
  usePathname: () => "/screening",
  useSearchParams: () => ({ get: () => null }),
}));

const job = {
  id: "job-1",
  title: "Lead Product Designer",
  status: "published",
  requirements: {
    structured_data: {
      summary_bullets: [
        "Role: Lead Product Designer",
        "Required skills: Figma, Research",
        "4+ years product design experience",
        "Lead design systems work",
        "Collaborate with engineering",
      ],
    },
  },
};

const candidate = {
  id: "cand-1",
  name: "Maya Chen",
  email: "maya@example.com",
  phone: "+1 555 0100",
  jobTitle: "Lead Product Designer",
  jobId: "job-1",
  jdScore: 88,
  hrScore: 76,
  fitReason: "Fits: Strong Figma experience",
  fitPoints: ["Strong Figma experience aligned with required skills"],
  gapPoints: ["No evidence of required AWS experience"],
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
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/jobs")) return json({ items: [job] });
      if (url.includes("/jobs/search")) {
        return json({ query: "designer", items: [{ job, similarity: 0.91 }] });
      }
      if (url.includes("/generate-scores") && init?.method === "POST") {
        return json({
          job_id: "job-1",
          analyzed_count: 1,
          shortlisted_count: 1,
          skipped_below_threshold: 0,
        });
      }
      if (url.includes("/candidates?")) {
        return json({ items: [candidate], total: 1, page: 1, pageSize: 10, total_uploaded: 1, shortlisted_threshold: 60 });
      }
      return json({ items: [], total: 0, page: 1, pageSize: 10 });
    }));
  });

  it("selects a JD, generates scores, and shows shortlisted results", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ScreeningClient />);
    await user.click(await screen.findByRole("button", { name: "Lead Product Designer" }));
    expect(await screen.findByText("JD Summary")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Generate AI Scores" }));
    expect(screen.getByText(/Analyzing resumes thoroughly/i)).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(4600);
    expect(await screen.findByText("Shortlisted Candidates")).toBeInTheDocument();
    expect(await screen.findByText("Maya Chen")).toBeInTheDocument();
    expect(screen.getByText("AI Calculated Score")).toBeInTheDocument();
    expect(screen.getByText("AI Suggestion — Why Fits / Not Fits")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("opens AI Calculated Score breakdown", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ScreeningClient />);
    await user.click(await screen.findByRole("button", { name: "Lead Product Designer" }));
    await user.click(screen.getByRole("button", { name: "Generate AI Scores" }));
    await vi.advanceTimersByTimeAsync(4600);
    await user.click(await screen.findByRole("button", { name: "AI Calculated Score for Maya Chen" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("AI Calculated Score");
    expect(within(dialog).getByText("Required skills")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("applies compact filters to the shortlisted query", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ScreeningClient />);
    await user.click(await screen.findByRole("button", { name: "Lead Product Designer" }));
    await user.click(screen.getByRole("button", { name: "Generate AI Scores" }));
    await vi.advanceTimersByTimeAsync(4600);
    await screen.findByText("Maya Chen");
    await user.selectOptions(screen.getByLabelText("Filter by decision status"), "advanced");
    await user.selectOptions(screen.getByLabelText("Minimum AI Calculated Score"), "80");
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map(([url]) => String(url));
      expect(
        calls.some((url) => url.includes("decision_status=advanced") && url.includes("min_score=80")),
      ).toBe(true);
    });
    vi.useRealTimers();
  });
});
