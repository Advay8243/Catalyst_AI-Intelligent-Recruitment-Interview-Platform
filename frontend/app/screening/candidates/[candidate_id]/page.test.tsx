import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CandidateReviewPage from "./page";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ candidate_id: "candidate-1" }),
  useSearchParams: () => ({ get: () => "job-1" }),
  useRouter: () => ({ push }),
}));

const screening = {
  overall_score: 84,
  score_components: {
    communication: 82,
    experience: 88,
    skills: 90,
    motivation: 78,
    availability: 75,
  },
  role_relevance: 89,
  question_analysis: [
    {
      question: "Tell us about your relevant experience.",
      answer: "I led Python services for six years.",
      category: "experience",
      score: 88,
      evidence: ["six years"],
      assessment: "Relevant production experience was clearly described.",
    },
  ],
  strengths: ["Strong production experience."],
  concerns: [],
  recommendation: "advance",
  summary: "Strong evidence across role-relevant skills.",
  label: "AI-assisted screening assessment",
};

function review(decided = false) {
  return {
    application: {
      id: "application-1",
      status: decided ? "accepted" : "new",
      resume_status: "processed",
      screening_status: decided ? "Accepted" : "Awaiting HR Decision",
      current_stage: decided ? "Accepted" : "HR Decision",
      applied_at: "2026-01-01T00:00:00Z",
      screened_at: "2026-01-02T00:00:00Z",
      decision: decided ? "accepted" : null,
      decision_at: decided ? "2026-01-03T00:00:00Z" : null,
      decision_by: decided ? "Current HR user" : null,
    },
    candidate: {
      id: "candidate-1",
      name: "Jordan Rivera",
      email: "jordan@example.test",
      phone: "+1 202 555 0147",
      profile: {},
    },
    job: {
      id: "job-1",
      title: "Platform Engineer",
      description: "Build reliable platform services.",
      responsibilities: ["Build APIs"],
      required_skills: ["Python", "PostgreSQL"],
      preferred_skills: ["AWS"],
      experience_requirements: "5+ years",
    },
    resume: {
      id: "resume-1",
      filename: "jordan.docx",
      mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      parsed_data: {
        skills: ["Python", "PostgreSQL"],
        years_experience: 6,
        education: ["BSc Computer Science"],
        highlights: ["Led a platform migration"],
      },
      uploaded_at: "2026-01-01T00:00:00Z",
    },
    resume_analysis: {
      overall_score: 87,
      scoring: {},
      evidence: {},
      explanation: "Strong Python and PostgreSQL alignment.",
    },
    call_session: {
      id: "call-1",
      status: "completed",
      questions: [],
      transcript: [],
    },
    screening_analysis: screening,
    email_history: [],
    decision_history: [],
    timeline: [
      {
        id: "event-1",
        event_type: "candidate_created",
        timestamp: "2026-01-01T00:00:00Z",
        title: "Candidate Created",
        description: "Candidate record created.",
        metadata: {},
      },
    ],
    audit_events: [],
  };
}

function json(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
  } as Response);
}

describe("CandidateReviewPage", () => {
  beforeEach(() => {
    push.mockReset();
    let decided = false;
    let sent = false;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/decision")) {
        decided = true;
        return json({
          application_id: "application-1",
          decision: "accepted",
          decision_at: "2026-01-03T00:00:00Z",
          status: "advanced",
        });
      }
      if (url.includes("/email-draft")) {
        return json({
          id: "draft-1",
          recipient: "jordan@example.test",
          subject: "Next steps for your Platform Engineer application",
          body: "Hi Jordan,\n\nYou have progressed.",
          email_type: "accepted",
          status: "Draft",
          created_at: "2026-01-03T00:04:00Z",
        });
      }
      if (url.endsWith("/emails") && init?.method === "POST") {
        sent = true;
        return json({
          id: "email-1",
          candidate_id: "candidate-1",
          application_id: "application-1",
          recipient: "jordan@example.test",
          subject: "Edited next steps",
          body: "Edited body",
          email_type: "accepted",
          status: "Sent",
          sent_at: "2026-01-03T00:05:00Z",
          created_at: "2026-01-03T00:05:00Z",
        }, 201);
      }
      const current = review(decided);
      if (sent) {
        (current.email_history as Array<Record<string, unknown>>).push({
          id: "email-1",
          candidate_id: "candidate-1",
          application_id: "application-1",
          recipient: "jordan@example.test",
          subject: "Edited next steps",
          body: "Edited body",
          email_type: "accepted",
          status: "Sent",
          sent_at: "2026-01-03T00:05:00Z",
          created_at: "2026-01-03T00:04:00Z",
        });
      }
      return json(current);
    }));
  });

  it("shows screening evidence, confirms acceptance, edits email, and records history", async () => {
    const user = userEvent.setup();
    render(<CandidateReviewPage />);

    expect(await screen.findByText("Jordan Rivera")).toBeInTheDocument();
    expect(screen.getByText("AI-assisted screening assessment")).toBeInTheDocument();
    expect(screen.getByText("I led Python services for six years.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /accept candidate/i }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Accept candidate?");
    await user.click(screen.getByRole("button", { name: /confirm accept/i }));

    expect(await screen.findByRole("dialog")).toHaveTextContent("Email candidate");
    const subject = await screen.findByRole("textbox", { name: "Subject" });
    await user.clear(subject);
    await user.type(subject, "Edited next steps");
    const message = screen.getByRole("textbox", { name: "Message" });
    await user.clear(message);
    await user.type(message, "Edited body");
    await user.click(screen.getByRole("button", { name: /preview/i }));
    await user.click(screen.getByRole("button", { name: /send email/i }));

    await waitFor(() => {
      expect(screen.getByText("Edited next steps")).toBeInTheDocument();
      expect(screen.getByText("Sent")).toBeInTheDocument();
    });
  });

  it("does not record rejection until the human confirms", async () => {
    const user = userEvent.setup();
    render(<CandidateReviewPage />);
    await screen.findByText("Jordan Rivera");

    await user.click(screen.getByRole("button", { name: /reject candidate/i }));
    await user.type(
      screen.getByRole("textbox", { name: "Decision reason" }),
      "Role requirements were not met.",
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    const fetchMock = vi.mocked(fetch);
    expect(
      fetchMock.mock.calls.filter(([input]) => String(input).includes("/decision")),
    ).toHaveLength(0);
  });
});
