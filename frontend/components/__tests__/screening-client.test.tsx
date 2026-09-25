import React from "react";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScreeningClient } from "@/components/screening-client";

const navigation = vi.hoisted(() => ({ push: vi.fn(), jobId: null as string | null }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: navigation.push, replace: navigation.push }),
  usePathname: () => "/screening",
  useSearchParams: () => ({ get: (key: string) => key === "job_id" ? navigation.jobId : null }),
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
  profile: { years_experience: 6 },
  jobTitle: "Lead Product Designer",
  jobId: "job-1",
  jdScore: 88,
  hrScore: 76,
  screened_at: "2026-09-24T13:57:23.293Z",
  fitReason: "Fits: Strong Figma experience",
  fitPoints: ["Strong Figma experience aligned with required skills"],
  gapPoints: ["No evidence of required AWS experience"],
  scoreBreakdown: { skills: 92, experience: 85, education: 80, relevance: 91 },
  skills: ["Figma", "Research"],
};

const lowScoreCandidate = {
  ...candidate,
  id: "cand-2",
  name: "Noah Singh",
  email: "noah@example.com",
  profile: { years_experience: 2 },
  jdScore: 42,
  hrScore: null,
  screened_at: null,
  fitReason: "Limited evidence for the required role.",
  fitPoints: [],
  gapPoints: ["Required design-system experience is not shown."],
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
    navigation.push.mockReset();
    navigation.jobId = null;
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
      if (url.includes("/api/hr/candidates/cand-1/decision") && init?.method === "POST") {
        return json({
          application_id: "application-1",
          decision: "accepted",
          decision_at: "2026-09-24T14:00:00Z",
          status: "advanced",
          previous_status: "new",
          new_status: "advanced",
        });
      }
      if (url.includes("/candidates?")) {
        return json({ items: [candidate, lowScoreCandidate], total: 2, page: 1, pageSize: 10, total_uploaded: 2, shortlisted_threshold: 60 });
      }
      return json({ items: [], total: 0, page: 1, pageSize: 10 });
    }));
  });

  it("selects a JD, generates scores, and shows candidate results", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ScreeningClient />);
    await user.click(await screen.findByRole("button", { name: "Lead Product Designer" }));
    expect(await screen.findByText("JD Summary")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Generate AI Scores" }));
    expect(screen.getByText(/Analyzing resumes thoroughly/i)).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(4600));
    expect(await screen.findByText("Candidates")).toBeInTheDocument();
    expect(await screen.findByText("Maya Chen")).toBeInTheDocument();
    expect(screen.getByText("Noah Singh")).toBeInTheDocument();
    expect(screen.getByText("42%")).toBeInTheDocument();
    expect(screen.getByText("AI Resume Score")).toBeInTheDocument();
    expect(screen.getByText("AI Resume Summary")).toBeInTheDocument();
    expect(screen.getByText("HR Discussion")).toBeInTheDocument();
    expect(screen.getByText("HR Score AI Generated")).toBeInTheDocument();
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByText("Decision")).toBeInTheDocument();
    expect(screen.getByText("6 years experience")).toBeInTheDocument();
    expect(screen.getByText("Evaluated: 24 Sep 2026")).toBeInTheDocument();
    expect(screen.queryByText("80–89")).not.toBeInTheDocument();
    expect(screen.queryByText("70–79")).not.toBeInTheDocument();
    expect(screen.queryByText("Below 60")).not.toBeInTheDocument();
    vi.useRealTimers();
  });

  it("opens AI Calculated Score breakdown", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ScreeningClient />);
    await user.click(await screen.findByRole("button", { name: "Lead Product Designer" }));
    await user.click(screen.getByRole("button", { name: "Generate AI Scores" }));
    await act(() => vi.advanceTimersByTimeAsync(4600));
    await user.click(await screen.findByRole("button", { name: "AI Calculated Score for Maya Chen" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("AI Calculated Score");
    expect(within(dialog).getByText("Required skills")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("loads candidates without a default min_score filter", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ScreeningClient />);
    await user.click(await screen.findByRole("button", { name: "Lead Product Designer" }));
    await user.click(screen.getByRole("button", { name: "Generate AI Scores" }));
    await act(() => vi.advanceTimersByTimeAsync(4600));
    await screen.findByText("Maya Chen");
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map(([url]) => String(url));
      const candidateCalls = calls.filter((url) => url.includes("/candidates?"));
      expect(candidateCalls.length).toBeGreaterThan(0);
      expect(candidateCalls.every((url) => !url.includes("min_score="))).toBe(true);
    });
    vi.useRealTimers();
  });

  it("restores saved scores when returning with a selected job", async () => {
    navigation.jobId = "job-1";
    render(<ScreeningClient />);

    expect(await screen.findByText("Maya Chen")).toBeInTheDocument();
    expect(screen.queryByText("Generate AI Calculated Scores")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AI Calculated Score for Maya Chen" })).toBeInTheDocument();
  });

  it("filters independently by resume and HR screening score", async () => {
    navigation.jobId = "job-1";
    const user = userEvent.setup();
    render(<ScreeningClient />);
    await screen.findByText("Maya Chen");

    await user.selectOptions(screen.getByLabelText("Filter by AI resume score"), "0-59");
    await waitFor(() => {
      const candidateCalls = vi.mocked(fetch).mock.calls.map(([url]) => String(url)).filter((url) => url.includes("/candidates?"));
      expect(candidateCalls.some((url) => url.includes("min_score=0") && url.includes("max_score=59"))).toBe(true);
    });

    await user.selectOptions(screen.getByLabelText("Filter by HR screening score"), "80-100");
    await waitFor(() => {
      const candidateCalls = vi.mocked(fetch).mock.calls.map(([url]) => String(url)).filter((url) => url.includes("/candidates?"));
      expect(candidateCalls.some((url) =>
        url.includes("min_score=0")
        && url.includes("max_score=59")
        && url.includes("min_hr_score=80")
        && url.includes("max_hr_score=100"),
      )).toBe(true);
    });
    expect(screen.getByRole("button", { name: "Clear filters" })).toBeInTheDocument();
  });

  it("updates an evaluated candidate decision from the table", async () => {
    navigation.jobId = "job-1";
    const user = userEvent.setup();
    render(<ScreeningClient />);
    await screen.findByText("Maya Chen");

    const decisionSelect = screen.getByLabelText("Decision status for Maya Chen");
    await user.selectOptions(decisionSelect, "accepted");

    await waitFor(() => {
      const decisionCall = vi.mocked(fetch).mock.calls.find(([url]) => String(url).includes("/api/hr/candidates/cand-1/decision"));
      expect(decisionCall).toBeDefined();
      expect(JSON.parse(String(decisionCall?.[1]?.body))).toMatchObject({
        job_id: "job-1",
        decision: "accepted",
      });
    });
    expect(decisionSelect).toHaveValue("accepted");
    expect(screen.getByLabelText("Decision status for Noah Singh")).toBeDisabled();
  });
});
