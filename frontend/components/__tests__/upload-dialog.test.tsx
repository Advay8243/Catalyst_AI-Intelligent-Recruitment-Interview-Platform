import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { UploadDialog } from "@/components/upload-dialog";

const opened: string[] = [];

describe("UploadDialog", () => {
  beforeEach(() => {
    opened.length = 0;
    vi.stubGlobal("XMLHttpRequest", class {
      status = 201;
      responseText = JSON.stringify({
        candidate: { id: "cand-1" },
        analysis: { overall_score: 87 },
      });
      upload = { onprogress: null as ((event: ProgressEvent) => void) | null };
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;
      open(_method: string, url: string) {
        opened.push(url);
      }
      send() {
        this.onload?.();
      }
    });
  });

  it("posts resumes to the selected job resume endpoint", async () => {
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

    const file = new File(["resume"], "jordan.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    await user.upload(screen.getByLabelText("Resume files"), file);
    await user.click(screen.getByRole("button", { name: /upload & analyze/i }));

    await waitFor(() => {
      expect(onComplete).toHaveBeenCalled();
      expect(onNotice).toHaveBeenCalledWith("1 candidate created and analyzed.");
    });
    expect(opened).toEqual(["http://localhost:8000/jobs/job-1/resume"]);
  });
});
