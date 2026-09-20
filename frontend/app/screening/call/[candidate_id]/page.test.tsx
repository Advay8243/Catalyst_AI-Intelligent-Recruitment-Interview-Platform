import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HRScreeningCallPage from "./page";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ candidate_id: "candidate-1" }),
  useRouter: () => ({ push }),
  useSearchParams: () => ({ get: () => "job-1" }),
}));

const baseSession = {
  id: "call-1",
  status: "connected",
  provider: "mock",
  provider_call_id: null,
  candidate: {
    candidate_id: "candidate-1",
    candidate_name: "Jordan Rivera",
    email: "jordan.rivera@example.test",
    phone: "+1 202 555 0147",
    job_id: "job-1",
    job_title: "Platform Engineer",
    jd_resume_score: 87,
    key_matched_skills: ["Python", "PostgreSQL"],
  },
  questions: [
    {
      id: "experience",
      text: "Please summarize your relevant experience.",
      category: "experience",
    },
  ],
  transcript: [
    {
      id: "entry-1",
      sequence: 1,
      speaker: "candidate",
      text: "I led Python and PostgreSQL services for six years.",
      created_at: "2026-01-01T00:01:00Z",
    },
  ],
  created_at: "2026-01-01T00:00:00Z",
};

function json(data: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(data),
  } as Response);
}

describe("HRScreeningCallPage", () => {
  beforeEach(() => {
    push.mockReset();
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/start")) return json({ ...baseSession, status: "connected" });
      if (url.endsWith("/transcript")) {
        return json({
          id: "entry-1",
          sequence: 1,
          speaker: "candidate",
          text: "I led Python and PostgreSQL services for six years.",
          created_at: "2026-01-01T00:01:00Z",
        });
      }
      if (url.endsWith("/complete")) {
        return json({
          session: { ...baseSession, status: "completed" },
          analysis: {
            overall_score: 84,
            communication_score: 82,
            experience_score: 88,
            skills_score: 90,
            motivation_score: 76,
            availability_score: 70,
            question_analysis: [],
            strengths: ["Relevant production experience."],
            concerns: [],
            recommendation: "advance",
            summary: "Strong evidence across relevant experience and skills.",
          },
        });
      }
      return json(baseSession);
    }));
  });

  it("runs the mock call, captures transcript, and renders the HR score", async () => {
    const user = userEvent.setup();
    render(<HRScreeningCallPage />);

    expect(await screen.findByText("Jordan Rivera")).toBeInTheDocument();
    expect(screen.getAllByText("87%").length).toBeGreaterThan(0);

    expect(screen.getByText("Connected")).toBeInTheDocument();

    expect(
      screen.getByText("I led Python and PostgreSQL services for six years."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /end & analyze/i }));
    expect(await screen.findByText("84%")).toBeInTheDocument();
    expect(screen.getByText("HR Screening Score")).toBeInTheDocument();
  });
});
