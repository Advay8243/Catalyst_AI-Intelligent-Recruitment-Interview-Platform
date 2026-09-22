import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OverviewPage from "@/app/overview/page";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

function json(data: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(data),
  } as Response);
}

describe("OverviewPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/dashboard/stats")) {
        return json({
          total_candidates: 3,
          pending_hr_screening: 1,
          hr_screened: 2,
          needs_review: 0,
          accepted: 1,
          rejected: 1,
          emails_sent: 2,
          active_job_descriptions: 1,
          average_jd_resume_score: 84.5,
          average_hr_screening_score: 76.2,
          candidates_per_job: [
            { job_id: "job-1", title: "Data Engineer", status: "published", candidate_count: 3 },
          ],
        });
      }
      if (url.includes("/dashboard/activity")) {
        return json({
          items: [
            {
              id: "1",
              event_type: "resume_uploaded",
              title: "Resume Uploaded",
              description: "Resume uploaded: alex.docx.",
              timestamp: "2026-09-21T10:00:00Z",
              candidate_name: "Alex",
              job_title: "Data Engineer",
            },
          ],
        });
      }
      if (url.endsWith("/jobs")) {
        return json([{ id: "job-1", title: "Data Engineer", status: "published" }]);
      }
      return json({});
    }));
  });

  it("renders live dashboard metrics and activity", async () => {
    const user = userEvent.setup();
    render(<OverviewPage />);
    expect(await screen.findByText("Total Candidates")).toBeInTheDocument();
    expect(screen.getByText("Accepted")).toBeInTheDocument();
    expect(screen.getByText("84.5%")).toBeInTheDocument();
    expect(screen.getByText("Resume Uploaded")).toBeInTheDocument();
    expect(screen.getAllByText("Data Engineer").length).toBeGreaterThan(0);
    await user.selectOptions(screen.getByLabelText("Filter dashboard by job"), "job-1");
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map(([url]) => String(url));
      expect(calls.some((url) => url.includes("job_id=job-1"))).toBe(true);
    });
  });
});
