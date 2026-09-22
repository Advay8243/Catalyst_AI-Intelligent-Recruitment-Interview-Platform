import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { UploadDialog } from "@/components/upload-dialog";

type MockXHR = {
  upload: { onprogress: ((event: ProgressEvent) => void) | null };
  open: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;
  status: number;
  responseText: string;
  onload: (() => void) | null;
  onerror: (() => void) | null;
};

describe("UploadDialog", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "XMLHttpRequest",
      vi.fn(function MockXHR(this: MockXHR) {
        this.upload = { onprogress: null };
        this.open = vi.fn();
        this.send = vi.fn(() => {
          this.status = 201;
          this.responseText = JSON.stringify({
            job_id: "job-1",
            results: [{ filename: "alex.docx", status: "success" }],
            success_count: 1,
            failure_count: 0,
            duplicate_count: 0,
          });
          this.onload?.();
        });
      }),
    );
  });

  it("posts resumes to the selected job batch endpoint", async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    const onNotice = vi.fn();
    render(
      <UploadDialog
        kind="resume"
        open
        onOpenChange={vi.fn()}
        jobId="job-1"
        onComplete={onComplete}
        onNotice={onNotice}
      />,
    );

    const file = new File(["resume"], "alex.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    await user.upload(screen.getByLabelText("Resume files"), file);
    await user.click(screen.getByRole("button", { name: /Upload & analyze/i }));

    await waitFor(() => {
      expect(XMLHttpRequest).toHaveBeenCalled();
      const instance = vi.mocked(XMLHttpRequest).mock.results[0].value as MockXHR;
      expect(instance.open).toHaveBeenCalledWith(
        "POST",
        expect.stringContaining("/jobs/job-1/resumes/batch"),
      );
      expect(onComplete).toHaveBeenCalled();
    });
  });
});
