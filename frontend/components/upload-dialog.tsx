"use client";

import { CheckCircle2, FileText, LoaderCircle, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import {
  createJobFromDescription,
  uploadJobDescriptionFile,
  uploadResumeToJob,
} from "@/lib/api";
import type { Job } from "@/lib/types";
import { Button, Dialog, DialogContent, Input, Progress } from "@/components/ui";

type UploadKind = "jd" | "resume";

const ACCEPTED_TYPES = ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function isSupportedDocument(file: File) {
  return /\.(pdf|docx)$/i.test(file.name);
}

export function UploadDialog({
  kind,
  open,
  onOpenChange,
  jobId,
  onComplete,
  onNotice,
}: {
  kind: UploadKind;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  jobId: string;
  onComplete: (createdJob?: Job) => void;
  onNotice: (message: string, error?: boolean) => void;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [jdText, setJdText] = useState("");
  const [mode, setMode] = useState<"file" | "paste">("file");
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("");
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const upload = async () => {
    if (kind === "resume" && !jobId) {
      onNotice("Select or upload a job description before uploading resumes.", true);
      return;
    }
    if (mode === "file" && !files.length) return;
    if (kind === "jd" && mode === "paste" && jdText.trim().length < 20) {
      onNotice("Paste a complete job description (at least 20 characters).", true);
      return;
    }
    if (mode === "file" && files.some((file) => !isSupportedDocument(file))) {
      onNotice("Unable to process this resume. Please verify that the uploaded file is a valid PDF or DOCX.", true);
      return;
    }

    setUploading(true);
    setProgress(8);
    try {
      if (kind === "jd") {
        setStage("Processing job description");
        const job = mode === "paste"
          ? await createJobFromDescription(jdText.trim())
          : await uploadJobDescriptionFile(files[0], setProgress);
        setProgress(100);
        setStage("Job description analyzed");
        onNotice(`JD processed: ${job.title}`);
        onComplete(job);
      } else {
        let created = 0;
        for (const [index, file] of files.entries()) {
          setStage(`Parsing resume ${index + 1} of ${files.length}`);
          await uploadResumeToJob(jobId, file, (value) => {
            setProgress(Math.round(((index + value / 100) / files.length) * 100));
          });
          created += 1;
        }
        setProgress(100);
        setStage("Resume analysis completed");
        onNotice(`${created} candidate${created === 1 ? "" : "s"} created and analyzed.`);
        onComplete();
      }
      setTimeout(() => onOpenChange(false), 400);
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Upload failed", true);
      setStage("");
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !uploading && onOpenChange(next)}>
      <DialogContent
        title={kind === "resume" ? "Upload resumes" : "Add job description"}
        description={
          kind === "resume"
            ? "Upload PDF or DOCX resumes against the selected job. Analysis runs immediately."
            : "Upload a PDF/DOCX or paste the job description to create a job."
        }
      >
        {kind === "resume" && !jobId && (
          <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            Select a job first, or upload a job description before adding resumes.
          </p>
        )}
        {kind === "jd" && (
          <div className="mt-5 grid grid-cols-2 rounded-lg bg-muted p-1">
            <button className={`rounded-md py-2 text-sm font-medium ${mode === "file" ? "bg-white shadow-sm" : "text-[#667085]"}`} onClick={() => setMode("file")}>Upload file</button>
            <button className={`rounded-md py-2 text-sm font-medium ${mode === "paste" ? "bg-white shadow-sm" : "text-[#667085]"}`} onClick={() => setMode("paste")}>Paste text</button>
          </div>
        )}
        <div className="mt-5">
          {mode === "paste" && kind === "jd" ? (
            <textarea value={jdText} onChange={(event) => setJdText(event.target.value)} rows={12} placeholder="Paste the full job description here…" aria-label="Job description text" className="w-full resize-none rounded-xl border p-4 text-sm leading-6 shadow-sm focus:border-primary" />
          ) : (
            <>
              <Input ref={inputRef} type="file" multiple={kind === "resume"} accept={ACCEPTED_TYPES} className="hidden" onChange={(event) => setFiles(Array.from(event.target.files ?? []))} aria-label={kind === "resume" ? "Resume files" : "Job description file"} />
              <button onClick={() => inputRef.current?.click()} className="flex min-h-44 w-full flex-col items-center justify-center rounded-xl border-2 border-dashed border-[#d0d5dd] bg-[#fcfcfd] p-6 hover:border-primary">
                <span className="mb-3 flex size-11 items-center justify-center rounded-full border bg-white"><UploadCloud className="size-5 text-[#667085]" /></span>
                <span className="text-sm font-semibold text-primary">Click to upload <span className="font-normal text-[#667085]">or drag and drop</span></span>
                <span className="mt-1 text-xs text-[#98a2b3]">PDF or DOCX · 10MB max each</span>
              </button>
              {files.length > 0 && <div className="mt-3 space-y-2">{files.map((file) => <div key={`${file.name}-${file.size}`} className="flex items-center gap-3 rounded-lg border p-3"><FileText className="size-5 text-primary" /><span className="min-w-0 flex-1 truncate text-sm font-medium">{file.name}</span><span className="text-xs text-[#98a2b3]">{(file.size / 1024 / 1024).toFixed(1)} MB</span></div>)}</div>}
            </>
          )}
        </div>
        {stage && <div className="mt-5 rounded-xl bg-[#f8f9fb] p-4"><div className="mb-2 flex items-center gap-2 text-sm font-medium">{uploading ? <LoaderCircle className="size-4 animate-spin text-primary" /> : <CheckCircle2 className="size-4 text-green-600" />}{stage}<span className="ml-auto text-xs text-[#667085]">{progress}%</span></div><Progress value={progress} /></div>}
        <div className="mt-6 flex justify-end gap-2"><Button variant="secondary" disabled={uploading} onClick={() => onOpenChange(false)}>Cancel</Button><Button disabled={uploading || (kind === "resume" && !jobId) || (mode === "file" ? !files.length : !jdText.trim())} onClick={() => void upload()}>{uploading ? <LoaderCircle className="size-4 animate-spin" /> : <UploadCloud className="size-4" />}Upload & analyze</Button></div>
      </DialogContent>
    </Dialog>
  );
}
