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
  status: "not_started",
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
      id: "q1",
      text: "Describe your AWS production experience.",
      category: "skills",
      reason: "JD requires AWS; resume provides weak evidence.",
      focus_skills: ["AWS"],
    },
    {
      id: "q2",
      text: "Please summarize your relevant experience.",
      category: "experience",
    },
  ],
  transcript: [],
  created_at: "2026-01-01T00:00:00Z",
  transcript_source: "none",
  realtime_transcription_available: false,
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
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/start")) {
        return json({
          ...baseSession,
          status: "connected",
          transcript_source: "none",
          realtime_transcription_available: false,
        });
      }
      if (url.endsWith("/paste-transcript") && init?.method === "POST") {
        return json({
          session: {
            ...baseSession,
            status: "connected",
            transcript_source: "pasted",
            transcript: [
              {
                id: "entry-1",
                sequence: 1,
                speaker: "hr",
                text: "Tell me about your Python experience.",
                created_at: "2026-01-01T00:01:00Z",
              },
              {
                id: "entry-2",
                sequence: 2,
                speaker: "candidate",
                text: "I have five years of Python experience.",
                created_at: "2026-01-01T00:01:30Z",
              },
            ],
          },
          entries: [],
        });
      }
      if (url.endsWith("/complete")) {
        return json({
          session: { ...baseSession, status: "completed", transcript_source: "pasted" },
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

  it("shows realtime unavailable and analyzes a pasted transcript", async () => {
    const user = userEvent.setup();
    render(<HRScreeningCallPage />);

    expect(await screen.findByText("Jordan Rivera")).toBeInTheDocument();
    expect(screen.getByText("Real-time transcription unavailable")).toBeInTheDocument();
    expect(screen.getByText("AI-generated questions")).toBeInTheDocument();
    expect(screen.queryByText(/candidate speaking/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/hr speaking/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /paste existing transcript/i }));
    await user.type(
      screen.getByLabelText("Pasted transcript"),
      "HR: Tell me about your Python experience.\nCandidate: I have five years of Python experience.",
    );
    await user.click(screen.getByRole("button", { name: /analyze transcript/i }));

    expect(await screen.findByText("84%")).toBeInTheDocument();
    expect(screen.getByText("HR Screening Score")).toBeInTheDocument();
  });
});
