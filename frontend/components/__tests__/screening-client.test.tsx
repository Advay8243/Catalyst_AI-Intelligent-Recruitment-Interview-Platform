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
  jobId: "job-1",
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
      if (url.includes("/candidates/compare")) {
        return json({
          job_id: "job-1",
          job_title: "Lead Product Designer",
          items: [
            {
              candidate_id: "cand-1",
              full_name: "Maya Chen",
              email: "maya@example.com",
              job_id: "job-1",
              job_title: "Lead Product Designer",
              jd_score: 88,
              hr_score: 76,
              required_skills_score: 90,
              preferred_skills_score: 80,
              experience_score: 85,
              responsibilities_score: 70,
              education_score: 75,
              matched_required_skills: ["Figma"],
              matched_preferred_skills: ["Research"],
              missing_required_skills: [],
              experience_years: 6,
              education: ["BFA"],
              strengths: ["Clear communicator"],
              missing_information: [],
              ai_recommendation: "advance",
              human_decision: "pending",
            },
            {
              candidate_id: "cand-2",
              full_name: "Alex Morgan",
              email: "alex@example.com",
              job_id: "job-1",
              job_title: "Lead Product Designer",
              jd_score: 70,
              hr_score: 65,
              required_skills_score: 60,
              preferred_skills_score: 50,
              experience_score: 70,
              responsibilities_score: 55,
              education_score: 60,
              matched_required_skills: ["Figma"],
              matched_preferred_skills: [],
              missing_required_skills: ["Systems"],
              experience_years: 4,
              education: ["BA"],
              strengths: [],
              missing_information: ["Missing required skill: Systems"],
              ai_recommendation: "review",
              human_decision: "pending",
            },
          ],
        });
      }
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
    await user.selectOptions(screen.getByLabelText("Filter by decision status"), "advanced");
    await user.selectOptions(screen.getByLabelText("Minimum JD score"), "80");
    await user.selectOptions(screen.getByLabelText("Filter by email status"), "sent");
    await user.selectOptions(screen.getByLabelText("Sort candidates"), "name");
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map(([url]) => String(url));
      expect(
        calls.some(
          (url) =>
            url.includes("decision_status=advanced")
            && url.includes("min_score=80")
            && url.includes("email_status=sent")
            && url.includes("sort=name"),
        ),
      ).toBe(true);
    });
  });

  it("navigates to the candidate call route", async () => {
    const user = userEvent.setup();
    render(<ScreeningClient />);
    await user.click(await screen.findByRole("button", { name: "Call Maya Chen" }));
    expect(push).toHaveBeenCalledWith("/screening/call/cand-1?job_id=job-1");
  });

  it("opens candidate review from the email status", async () => {
    const user = userEvent.setup();
    render(<ScreeningClient />);
    expect(await screen.findByText("✉ Not Sent")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Email history for Maya Chen" }));
    expect(push).toHaveBeenCalledWith("/screening/candidates/cand-1?job_id=job-1");
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

  it("compares selected candidates side by side", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/jobs")) return json({ items: [{ id: "job-1", title: "Lead Product Designer" }] });
      if (url.includes("/candidates/compare")) {
        return json({
          job_id: "job-1",
          job_title: "Lead Product Designer",
          items: [
            {
              candidate_id: "cand-1",
              full_name: "Maya Chen",
              email: "maya@example.com",
              job_id: "job-1",
              job_title: "Lead Product Designer",
              jd_score: 88,
              hr_score: 76,
              required_skills_score: 90,
              preferred_skills_score: 80,
              experience_score: 85,
              responsibilities_score: 70,
              education_score: 75,
              matched_required_skills: ["Figma"],
              matched_preferred_skills: ["Research"],
              missing_required_skills: [],
              experience_years: 6,
              education: ["BFA"],
              strengths: ["Clear communicator"],
              missing_information: [],
              ai_recommendation: "advance",
              human_decision: "pending",
            },
            {
              candidate_id: "cand-2",
              full_name: "Alex Morgan",
              email: "alex@example.com",
              job_id: "job-1",
              job_title: "Lead Product Designer",
              jd_score: 70,
              hr_score: 65,
              required_skills_score: 60,
              preferred_skills_score: 50,
              experience_score: 70,
              responsibilities_score: 55,
              education_score: 60,
              matched_required_skills: ["Figma"],
              matched_preferred_skills: [],
              missing_required_skills: ["Systems"],
              experience_years: 4,
              education: ["BA"],
              strengths: [],
              missing_information: ["Missing required skill: Systems"],
              ai_recommendation: "review",
              human_decision: "pending",
            },
          ],
        });
      }
      return json({
        items: [
          candidate,
          { ...candidate, id: "cand-2", name: "Alex Morgan", email: "alex@example.com", jdScore: 70, hrScore: 65 },
        ],
        total: 2,
        page: 1,
        pageSize: 10,
      });
    }));
    const user = userEvent.setup();
    render(<ScreeningClient />);
    await screen.findByText("Maya Chen");
    await user.click(screen.getByRole("checkbox", { name: "Select Maya Chen for comparison" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Alex Morgan for comparison" }));
    await user.click(screen.getByRole("button", { name: "Compare selected candidates" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Compare · Lead Product Designer");
    expect(dialog).toHaveTextContent("Required skills");
    expect(dialog).toHaveTextContent("Missing information");
    expect(dialog).toHaveTextContent("AI recommendation");
    expect(dialog).toHaveTextContent("Human decision");
    expect(dialog).toHaveTextContent("Alex Morgan");
  });
});
