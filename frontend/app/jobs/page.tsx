"use client";

import {
  BriefcaseBusiness,
  Pencil,
  Plus,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { UploadDialog } from "@/components/upload-dialog";
import { Badge, Button, Input, Skeleton } from "@/components/ui";
import {
  createJob,
  deleteJob,
  draftJob,
  getJobs,
  publishJob,
  updateJob,
} from "@/lib/api";
import type { Job } from "@/lib/types";

type JobTab = "published" | "draft";

function jobTabStatus(job: Job): JobTab {
  return job.status === "published" ? "published" : "draft";
}

function statusLabel(job: Job) {
  return jobTabStatus(job) === "published" ? "Published" : "Draft";
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState<Job | null>(null);
  const [selected, setSelected] = useState<Job | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [listSearch, setListSearch] = useState("");
  const [tab, setTab] = useState<JobTab>("published");
  const [draft, setDraft] = useState({
    title: "",
    department: "",
    location: "",
    employment_type: "full-time",
    experience_required: "",
    description: "",
    required_skills: "",
    preferred_skills: "",
    responsibilities: "",
    education: "",
    certifications: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setJobs(await getJobs());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load jobs.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredJobs = useMemo(() => {
    const term = listSearch.trim().toLowerCase();
    return jobs
      .filter((job) => jobTabStatus(job) === tab)
      .filter((job) => {
        if (!term) return true;
        const haystack = [
          job.title,
          job.department,
          job.location,
          job.description,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(term);
      });
  }, [jobs, listSearch, tab]);

  const openEdit = (job: Job) => {
    const data = job.requirements?.structured_data ?? {};
    setEditing(job);
    setDraft({
      title: job.title ?? "",
      department: job.department ?? data.department ?? "",
      location: job.location ?? data.location ?? "",
      employment_type: job.employment_type ?? data.employment_type ?? "full-time",
      experience_required: data.experience_required ?? "",
      description: job.description ?? "",
      required_skills: (data.required_skills ?? []).join(", "),
      preferred_skills: (data.preferred_skills ?? []).join(", "),
      responsibilities: (data.responsibilities ?? []).join("\n"),
      education: (data.education ?? []).join(", "),
      certifications: (data.certifications ?? []).join(", "),
    });
  };

  const split = (value: string) =>
    value
      .split(/[,\n]/)
      .map((item) => item.trim())
      .filter(Boolean);

  const saveEdit = async (status?: "draft" | "published") => {
    if (!editing) return;
    try {
      const updated = await updateJob(editing.id, {
        title: draft.title,
        department: draft.department || undefined,
        location: draft.location || undefined,
        employment_type: draft.employment_type || undefined,
        experience_required: draft.experience_required || undefined,
        description: draft.description,
        required_skills: split(draft.required_skills),
        preferred_skills: split(draft.preferred_skills),
        responsibilities: split(draft.responsibilities),
        education: split(draft.education),
        certifications: split(draft.certifications),
        status,
      });
      setNotice(`Updated ${updated.title}`);
      setEditing(null);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update job.");
    }
  };

  const createBlankDraft = async () => {
    try {
      const job = await createJob({
        title: "Untitled role",
        description: "Draft job description placeholder text for editing.",
        status: "draft",
      });
      openEdit(job);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create draft.");
    }
  };

  const summaryBullets = selected?.requirements?.structured_data?.summary_bullets ?? [];
  const skills = selected?.requirements?.structured_data?.required_skills ?? [];

  return (
    <div className="min-h-screen">
      <header className="border-b bg-white px-5 py-5 sm:px-8 lg:px-10">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-4 pl-12 sm:pl-0 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="mb-1 flex items-center gap-2 text-xs font-medium text-[#98a2b3]"><span>Recruitment</span><span>/</span><span className="text-[#667085]">Jobs</span></div>
            <h1 className="text-2xl font-bold tracking-tight text-[#101828]">Jobs & Job Descriptions</h1>
            <p className="mt-1 text-sm text-[#667085]">Manage published and draft job descriptions.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => void createBlankDraft()}><Plus className="size-4" />Draft JD</Button>
            <Button onClick={() => setUploadOpen(true)}><Upload className="size-4" />Upload JD</Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1200px] space-y-5 p-5 sm:p-8 lg:p-10">
        {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}
        {notice && <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">{notice}</div>}

        <section className="overflow-hidden rounded-xl border bg-white shadow-panel">
          <div className="border-b px-5 py-4">
            <h2 className="font-semibold">All Jobs</h2>
            <p className="text-xs text-[#667085]">{loading ? "Loading…" : `${filteredJobs.length} shown`}</p>
          </div>
          <div className="space-y-3 border-b px-5 py-4">
            <label className="relative block">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#98a2b3]" />
              <Input
                value={listSearch}
                onChange={(event) => setListSearch(event.target.value)}
                placeholder="Search jobs…"
                aria-label="Search jobs"
                className="pl-9 pr-9"
              />
              {listSearch && (
                <button
                  aria-label="Clear job search"
                  onClick={() => setListSearch("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#98a2b3]"
                >
                  <X className="size-4" />
                </button>
              )}
            </label>
            <div className="flex gap-2">
              {(["published", "draft"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setTab(value)}
                  className={`rounded-full px-4 py-1.5 text-xs font-semibold capitalize ${tab === value ? "bg-primary text-white" : "border text-[#475467] hover:border-primary hover:text-primary"}`}
                >
                  {value === "published" ? "Published" : "Draft"}
                </button>
              ))}
            </div>
          </div>
          {loading ? (
            <div className="space-y-3 p-5">{Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-16 rounded-xl" />)}</div>
          ) : filteredJobs.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <BriefcaseBusiness className="mx-auto mb-3 size-8 text-[#98a2b3]" />
              <p className="font-semibold">No {tab} jobs</p>
              <p className="mt-1 text-sm text-[#667085]">Create a draft or upload a JD to get started.</p>
            </div>
          ) : (
            <div className="divide-y">
              {filteredJobs.map((job) => (
                <div key={job.id} className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <button className="text-left" onClick={() => setSelected(job)}>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-[#101828]">{job.title}</p>
                      <Badge tone={jobTabStatus(job) === "published" ? "green" : "amber"}>{statusLabel(job)}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-[#667085]">
                      {[job.department, job.location, job.employment_type].filter(Boolean).join(" · ") || "Details pending"}
                      {typeof job.application_count === "number" ? ` · ${job.application_count} candidate${job.application_count === 1 ? "" : "s"}` : ""}
                    </p>
                  </button>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" size="sm" onClick={() => openEdit(job)}><Pencil className="size-4" />Edit</Button>
                    {jobTabStatus(job) !== "published" && (
                      <Button size="sm" onClick={() => void publishJob(job.id).then(load)}>Publish</Button>
                    )}
                    {jobTabStatus(job) === "published" && (
                      <Button variant="secondary" size="sm" onClick={() => void draftJob(job.id).then(load)}>Draft</Button>
                    )}
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => {
                        if (confirm(job.application_count ? "This job has candidates and will be moved to draft instead of deleted. Continue?" : `Remove job “${job.title}”?`)) {
                          void deleteJob(job.id).then(load);
                        }
                      }}
                    >
                      <Trash2 className="size-4" />Remove
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {selected && !editing && (
          <section className="rounded-xl border bg-white p-5 shadow-panel">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="mb-1 font-semibold text-[#101828]">JD Summary</h2>
                <p className="text-sm text-[#667085]">{selected.title}</p>
              </div>
              <Button variant="secondary" size="sm" onClick={() => setSelected(null)}>Close</Button>
            </div>
            <ul className="space-y-2 text-sm text-[#475467]">
              {(summaryBullets.length
                ? summaryBullets
                : ["Open Edit or re-save this JD to generate a 5–10 bullet summary."]
              ).map((bullet) => (
                <li key={bullet} className="flex gap-2"><span className="text-primary">•</span><span>{bullet}</span></li>
              ))}
            </ul>
            {skills.length > 0 && (
              <div className="mt-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#98a2b3]">Relevant skills</p>
                <div className="flex flex-wrap gap-1.5">
                  {skills.map((skill) => <Badge key={skill} tone="gray">{skill}</Badge>)}
                </div>
              </div>
            )}
          </section>
        )}

        {editing && (
          <section className="rounded-xl border bg-white p-5 shadow-panel sm:p-6">
            <h2 className="mb-4 font-semibold">Edit job</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {([
                ["title", "Job Title"],
                ["department", "Department"],
                ["location", "Location"],
                ["employment_type", "Employment Type"],
                ["experience_required", "Experience Required"],
              ] as const).map(([key, label]) => (
                <label key={key} className="block text-sm">
                  <span className="mb-1 block font-medium">{label}</span>
                  <Input value={draft[key]} onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))} />
                </label>
              ))}
              <label className="block text-sm sm:col-span-2">
                <span className="mb-1 block font-medium">Job Description</span>
                <textarea rows={5} value={draft.description} onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))} className="w-full rounded-lg border p-3 text-sm" />
              </label>
              {([
                ["required_skills", "Required Skills"],
                ["preferred_skills", "Preferred Skills"],
                ["responsibilities", "Responsibilities"],
                ["education", "Education"],
                ["certifications", "Certifications"],
              ] as const).map(([key, label]) => (
                <label key={key} className="block text-sm sm:col-span-2">
                  <span className="mb-1 block font-medium">{label}</span>
                  <textarea rows={key === "responsibilities" ? 4 : 2} value={draft[key]} onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))} className="w-full rounded-lg border p-3 text-sm" />
                </label>
              ))}
            </div>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <Button variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
              <Button variant="secondary" onClick={() => void saveEdit("draft")}>Save Draft</Button>
              <Button onClick={() => void saveEdit("published")}>Save & Publish</Button>
            </div>
          </section>
        )}
      </div>

      <UploadDialog
        kind="jd"
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        jobId=""
        onComplete={() => void load()}
        onNotice={(message, isError) => {
          if (isError) setError(message);
          else setNotice(message);
        }}
      />
    </div>
  );
}
