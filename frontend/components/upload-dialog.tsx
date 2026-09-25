"use client";

import { CheckCircle2, FileText, LoaderCircle, UploadCloud, XCircle } from "lucide-react";
import { useRef, useState } from "react";
import {
  createJob,
  parseJobDescription,
  uploadResumesBatch,
} from "@/lib/api";
import type { Job, JobRequirements } from "@/lib/types";
import { Button, Dialog, DialogContent, Input, Progress } from "@/components/ui";

type UploadKind = "jd" | "resume";

const ACCEPTED_TYPES = ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function isSupportedDocument(file: File) {
  return /\.(pdf|docx)$/i.test(file.name);
}

function splitList(value: string) {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinList(items?: string[]) {
  return (items ?? []).join(", ");
}

type FileStatus = {
  name: string;
  status: "pending" | "success" | "failed" | "duplicate";
  message?: string;
};

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
  const [mode, setMode] = useState<"file" | "form">("file");
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [fileStatuses, setFileStatuses] = useState<FileStatus[]>([]);
  const [description, setDescription] = useState("");
  const [form, setForm] = useState({
    title: "",
    department: "",
    location: "",
    employment_type: "full-time",
    experience_required: "",
    required_skills: "",
    preferred_skills: "",
    responsibilities: "",
    education: "",
    certifications: "",
  });
  const inputRef = useRef<HTMLInputElement>(null);

  const applyExtracted = (extracted: JobRequirements, text: string) => {
    setDescription(text);
    setForm({
      title: extracted.title ?? "",
      department: extracted.department ?? "",
      location: extracted.location ?? "",
      employment_type: extracted.employment_type ?? "full-time",
      experience_required: extracted.experience_required ?? "",
      required_skills: joinList(extracted.required_skills),
      preferred_skills: joinList(extracted.preferred_skills),
      responsibilities: (extracted.responsibilities ?? []).join("\n"),
      education: joinList(extracted.education),
      certifications: joinList(extracted.certifications),
    });
    setMode("form");
  };

  const parseJd = async () => {
    if (!files.length || !isSupportedDocument(files[0])) {
      onNotice("Upload a valid PDF or DOCX job description.", true);
      return;
    }
    setUploading(true);
    setProgress(20);
    setStage("Parsing job description");
    try {
      const preview = await parseJobDescription({ file: files[0] });
      setProgress(100);
      applyExtracted(preview.editable, preview.description);
      onNotice("Review extracted JD fields before saving.");
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "JD parsing failed", true);
      setStage("");
    } finally {
      setUploading(false);
    }
  };

  const saveJob = async (status: "draft" | "published") => {
    if (description.trim().length < 20 || !form.title.trim()) {
      onNotice("Title and a complete job description are required.", true);
      return;
    }
    setUploading(true);
    setStage(status === "draft" ? "Saving draft" : "Publishing job");
    try {
      const job = await createJob({
        description: description.trim(),
        title: form.title.trim(),
        department: form.department.trim() || undefined,
        location: form.location.trim() || undefined,
        employment_type: form.employment_type || undefined,
        experience_required: form.experience_required.trim() || undefined,
        required_skills: splitList(form.required_skills),
        preferred_skills: splitList(form.preferred_skills),
        responsibilities: splitList(form.responsibilities),
        education: splitList(form.education),
        certifications: splitList(form.certifications),
        status,
      });
      setProgress(100);
      onNotice(status === "draft" ? `Draft saved: ${job.title}` : `JD published: ${job.title}`);
      onComplete(job);
      setTimeout(() => onOpenChange(false), 400);
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Unable to save job", true);
    } finally {
      setUploading(false);
    }
  };

  const uploadResumes = async () => {
    if (!jobId) {
      onNotice("Select or upload a job description before uploading resumes.", true);
      return;
    }
    if (!files.length) return;
    if (files.some((file) => !isSupportedDocument(file))) {
      onNotice("Unable to process this resume. Please verify that the uploaded file is a valid PDF or DOCX.", true);
      return;
    }
    if (files.some((file) => file.size > 10 * 1024 * 1024)) {
      onNotice("Each resume must be 10MB or smaller.", true);
      return;
    }
    setUploading(true);
    setFileStatuses(files.map((file) => ({ name: file.name, status: "pending" })));
    setStage(`Processing ${files.length} resume${files.length === 1 ? "" : "s"}`);
    setProgress(12);
    try {
      const result = await uploadResumesBatch(jobId, files, setProgress);
      setFileStatuses(
        result.results.map((item) => ({
          name: item.filename,
          status: item.status,
          message: item.message,
        })),
      );
      setProgress(100);
      setStage("Batch processing complete");
      const parts = [
        `${result.success_count} succeeded`,
        result.duplicate_count ? `${result.duplicate_count} duplicate` : "",
        result.failure_count ? `${result.failure_count} failed` : "",
      ].filter(Boolean);
      onNotice(parts.join(" · "), result.failure_count > 0 && result.success_count === 0);
      if (result.success_count > 0) onComplete();
      if (result.failure_count === 0) setTimeout(() => onOpenChange(false), 500);
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
            ? "Upload one or more PDF/DOCX resumes for the selected job. Failed files do not block the rest."
            : "Upload a JD file, review extracted fields, then save as draft or publish."
        }
        className="max-w-2xl"
      >
        {kind === "resume" && !jobId && (
          <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            Select a job first, or upload a job description before adding resumes.
          </p>
        )}
        <div className="mt-5 max-h-[60vh] space-y-4 overflow-y-auto pr-1">
          {kind === "jd" && mode === "form" ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {([
                ["title", "Job Title"],
                ["department", "Department"],
                ["location", "Location"],
                ["employment_type", "Employment Type"],
                ["experience_required", "Experience Required"],
              ] as const).map(([key, label]) => (
                <label key={key} className="block text-sm">
                  <span className="mb-1 block font-medium text-[#344054]">{label}</span>
                  <Input value={form[key]} onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))} />
                </label>
              ))}
              <label className="block text-sm sm:col-span-2">
                <span className="mb-1 block font-medium text-[#344054]">Job Description</span>
                <textarea rows={5} value={description} onChange={(event) => setDescription(event.target.value)} className="w-full rounded-lg border p-3 text-sm" />
              </label>
              {([
                ["required_skills", "Required Skills (comma-separated)"],
                ["preferred_skills", "Preferred Skills (comma-separated)"],
                ["responsibilities", "Responsibilities (one per line)"],
                ["education", "Education"],
                ["certifications", "Certifications"],
              ] as const).map(([key, label]) => (
                <label key={key} className="block text-sm sm:col-span-2">
                  <span className="mb-1 block font-medium text-[#344054]">{label}</span>
                  <textarea rows={key === "responsibilities" ? 4 : 2} value={form[key]} onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))} className="w-full rounded-lg border p-3 text-sm" />
                </label>
              ))}
            </div>
          ) : (
            <>
              <Input ref={inputRef} type="file" multiple={kind === "resume"} accept={ACCEPTED_TYPES} className="hidden" onChange={(event) => setFiles(Array.from(event.target.files ?? []))} aria-label={kind === "resume" ? "Resume files" : "Job description file"} />
              <button onClick={() => inputRef.current?.click()} className="flex min-h-44 w-full flex-col items-center justify-center rounded-xl border-2 border-dashed border-[#d0d5dd] bg-[#fcfcfd] p-6 hover:border-primary">
                <span className="mb-3 flex size-11 items-center justify-center rounded-full border bg-white"><UploadCloud className="size-5 text-[#667085]" /></span>
                <span className="text-sm font-semibold text-primary">Click to upload <span className="font-normal text-[#667085]">or drag and drop</span></span>
                <span className="mt-1 text-xs text-[#98a2b3]">PDF or DOCX · 10MB max each</span>
              </button>
              {files.length > 0 && (
                <div className="space-y-2">
                  {files.map((file) => {
                    const status = fileStatuses.find((item) => item.name === file.name);
                    return (
                      <div key={`${file.name}-${file.size}`} className="flex items-center gap-3 rounded-lg border p-3">
                        <FileText className="size-5 text-primary" />
                        <span className="min-w-0 flex-1 truncate text-sm font-medium">{file.name}</span>
                        <span className="text-xs text-[#98a2b3]">{(file.size / 1024 / 1024).toFixed(1)} MB</span>
                        {status?.status === "success" && <CheckCircle2 className="size-4 text-green-600" />}
                        {status?.status === "failed" && <XCircle className="size-4 text-red-600" aria-label={status.message} />}
                        {status?.status === "duplicate" && <span className="text-xs font-medium text-amber-700">Duplicate</span>}
                        {status?.status === "pending" && <LoaderCircle className="size-4 animate-spin text-primary" />}
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
        {stage && <div className="mt-5 rounded-xl bg-[#f8f9fb] p-4"><div className="mb-2 flex items-center gap-2 text-sm font-medium">{uploading ? <LoaderCircle className="size-4 animate-spin text-primary" /> : <CheckCircle2 className="size-4 text-green-600" />}{stage}<span className="ml-auto text-xs text-[#667085]">{progress}%</span></div><Progress value={progress} /></div>}
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <Button variant="secondary" disabled={uploading} onClick={() => onOpenChange(false)}>Cancel</Button>
          {kind === "jd" && mode === "form" ? (
            <>
              <Button variant="secondary" disabled={uploading} onClick={() => void saveJob("draft")}>Save Draft</Button>
              <Button disabled={uploading} onClick={() => void saveJob("published")}>Publish JD</Button>
            </>
          ) : kind === "jd" ? (
            <Button disabled={uploading || !files.length} onClick={() => void parseJd()}>
              {uploading ? <LoaderCircle className="size-4 animate-spin" /> : <UploadCloud className="size-4" />}
              Parse & review
            </Button>
          ) : (
            <Button disabled={uploading || !jobId || !files.length} onClick={() => void uploadResumes()}>
              {uploading ? <LoaderCircle className="size-4 animate-spin" /> : <UploadCloud className="size-4" />}
              Upload & analyze
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
