import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EmailComposer } from "@/components/email-composer";

const candidate = {
  id: "candidate-1",
  name: "Jordan Rivera",
  email: "jordan@example.org",
  jdScore: 87,
  hrScore: 84,
  fitReason: "Strong match",
  jobId: "job-1",
  jobTitle: "Platform Engineer",
};

function response(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
  } as Response);
}

describe("EmailComposer", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("email-draft")) {
        return response({
          id: "draft-1",
          recipient: candidate.email,
          subject: "Next Steps for Your Platform Engineer Application",
          body: "Hi Jordan,\n\nYou have progressed.",
          email_type: "advanced",
          status: "Draft",
          created_at: "2026-01-03T00:00:00Z",
        });
      }
      return response({ detail: "Mock provider unavailable" }, 400);
    }));
  });

  it("validates editable recipient, previews, and shows provider failures", async () => {
    const user = userEvent.setup();
    render(
      <EmailComposer
        candidate={candidate}
        open
        onOpenChange={vi.fn()}
        onNotice={vi.fn()}
        decision="advanced"
        jobId="job-1"
      />,
    );

    const recipient = await screen.findByRole("textbox", { name: "Recipient" });
    await user.clear(recipient);
    await user.type(recipient, "not-an-email");
    expect(screen.getByRole("button", { name: /preview/i })).toBeDisabled();

    await user.clear(recipient);
    await user.type(recipient, "coordinator@example.org");
    await user.click(screen.getByRole("button", { name: /preview/i }));
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /send email/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Mock provider unavailable");
  });
});
