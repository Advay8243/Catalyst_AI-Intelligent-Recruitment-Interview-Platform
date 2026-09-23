"use client";

import {
  Archive,
  BriefcaseBusiness,
  Pencil,
  Plus,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { UploadDialog } from "@/components/upload-dialog";
import { Badge, Button, Input, Skeleton } from "@/components/ui";
import {
  archiveJob,
  createJob,
  deleteJob,
  getJobs,
  getScoringCriteria,
  publishJob,
  searchJobs,
  updateJob,
} from "@/lib/api";
import type { Job, JobSearchHit, ScoringCriteria } from "@/lib/types";

export default function JobsPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState<Job | null>(null);
  const [selected, setSelected] = useState<Job | null>(null);
  const [criteria, setCriteria] = useState<ScoringCriteria | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchHits, setSearchHits] = useState<JobSearchHit[]>([]);
  const [searching, setSearching] = useState(false);
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
    getScoringCriteria().then(setCriteria).catch(() => setCriteria(null));
  }, [load]);

  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchHits([]);
      return;
    }
    const timer = setTimeout(() => {
      setSearching(true);
      searchJobs(searchQuery.trim())
        .then(setSearchHits)
        .catch(() => setSearchHits([]))
        .finally(() => setSearching(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

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

  const selectFromSearch = (hit: JobSearchHit) => {
    setSelected(hit.job);
    setSearchQuery(hit.job.title);
    setSearchHits([]);
  };

  const screenForJob = (job: Job) => {
    router.push(`/screening?job_id=${encodeURIComponent(job.id)}`);
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
            <p className="mt-1 text-sm text-[#667085]">Search JDs semantically, review summaries, and open candidate screening.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => void createBlankDraft()}><Plus className="size-4" />New draft</Button>
            <Button onClick={() => setUploadOpen(true)}><Upload className="size-4" />Upload / paste JD</Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1200px] space-y-5 p-5 sm:p-8 lg:p-10">
        {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}
        {notice && <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">{notice}</div>}

        <section className="rounded-xl border bg-white p-4 shadow-panel">
          <h2 className="mb-3 font-semibold">Search Jobs</h2>
          <label className="relative block">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#98a2b3]" />
            <Input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search semantically…"
              aria-label="Search jobs semantically"
              className="pl-9 pr-9"
            />
            {searchQuery && (
              <button
                aria-label="Clear job search"
                onClick={() => { setSearchQuery(""); setSearchHits([]); }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#98a2b3]"
              >
                <X className="size-4" />
              </button>
            )}
          </label>
          {(searching || searchHits.length > 0) && (
            <div className="mt-3 divide-y rounded-lg border bg-[#fafbfc]">
              {searching && <p className="px-4 py-3 text-sm text-[#667085]">Searching…</p>}
              {!searching && searchHits.map((hit) => {
                const bullets = hit.job.requirements?.structured_data?.summary_bullets ?? [];
                const hitSkills = hit.job.requirements?.structured_data?.required_skills ?? [];
                return (
                  <button
                    key={hit.job.id}
                    className="flex w-full flex-col gap-2 px-4 py-3 text-left hover:bg-white"
                    onClick={() => selectFromSearch(hit)}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold text-[#101828]">{hit.job.title}</span>
                      <div className="flex items-center gap-2">
                        <Badge tone="purple">{Math.round(hit.similarity * 100)}% relevant</Badge>
                        <Badge tone={hit.job.status === "published" ? "green" : hit.job.status === "archived" ? "gray" : "amber"}>
                          {hit.job.status ?? "draft"}
                        </Badge>
                      </div>
                    </div>
                    <p className="text-sm text-[#667085]">
                      {bullets[0] || hit.job.department || hit.job.location || "JD summary pending"}
                    </p>
                    {hitSkills.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {hitSkills.slice(0, 6).map((skill) => (
                          <Badge key={skill} tone="gray">{skill}</Badge>
                        ))}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </section>

        <section className="overflow-hidden rounded-xl border bg-white shadow-panel">
          <div className="border-b px-5 py-4">
            <h2 className="font-semibold">All jobs</h2>
            <p className="text-xs text-[#667085]">{loading ? "Loading…" : `${jobs.length} job${jobs.length === 1 ? "" : "s"}`}</p>
          </div>
          {loading ? (
            <div className="space-y-3 p-5">{Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-16 rounded-xl" />)}</div>
          ) : jobs.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <BriefcaseBusiness className="mx-auto mb-3 size-8 text-[#98a2b3]" />
              <p className="font-semibold">No jobs yet</p>
              <p className="mt-1 text-sm text-[#667085]">Create a draft or upload a JD to get started.</p>
            </div>
          ) : (
            <div className="divide-y">
              {jobs.map((job) => (
                <div key={job.id} className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <button className="text-left" onClick={() => setSelected(job)}>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-[#101828]">{job.title}</p>
                      <Badge tone={job.status === "published" ? "green" : job.status === "archived" ? "gray" : "amber"}>{job.status ?? "draft"}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-[#667085]">
                      {[job.department, job.location, job.employment_type].filter(Boolean).join(" · ") || "Details pending"}
                      {typeof job.application_count === "number" ? ` · ${job.application_count} candidate${job.application_count === 1 ? "" : "s"}` : ""}
                    </p>
                  </button>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" onClick={() => screenForJob(job)}>Screen for this JD</Button>
                    <Button variant="secondary" size="sm" onClick={() => openEdit(job)}><Pencil className="size-4" />Edit</Button>
                    {job.status !== "published" && <Button size="sm" onClick={() => void publishJob(job.id).then(load)}>Publish</Button>}
                    {job.status !== "archived" && (
                      <Button variant="secondary" size="sm" onClick={() => void archiveJob(job.id).then(load)}>
                        <Archive className="size-4" />Archive
                      </Button>
                    )}
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => {
                        if (confirm(job.application_count ? "This job has candidates and will be archived instead of deleted. Continue?" : `Remove job “${job.title}”?`)) {
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
          <section className="grid gap-5 lg:grid-cols-2">
            <div className="rounded-xl border bg-white p-5 shadow-panel">
              <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="mb-1 font-semibold text-[#101828]">JD Summary</h2>
                  <p className="text-sm text-[#667085]">{selected.title}</p>
                </div>
                <Button size="sm" onClick={() => screenForJob(selected)}>Screen for this JD</Button>
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
            </div>
            <div className="rounded-xl border bg-white p-5 shadow-panel">
              <h2 className="mb-1 font-semibold text-[#101828]">AI Screening & Scoring Criteria</h2>
              <p className="mb-4 text-sm text-[#667085]">{criteria?.note ?? "Transparent weighted comparison between JD and resume."}</p>
              <div className="space-y-3">
                {(criteria?.criteria ?? []).map((item) => (
                  <div key={item.key} className="rounded-lg border bg-[#fafbfc] p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-[#101828]">{item.label}</p>
                      <Badge tone="purple">{item.weight_percent}%</Badge>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-[#667085]">{item.description}</p>
                  </div>
                ))}
              </div>
              {!!criteria?.signals?.length && (
                <div className="mt-4">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#98a2b3]">Comparison signals</p>
                  <div className="flex flex-wrap gap-1.5">
                    {criteria.signals.map((signal) => <Badge key={signal} tone="gray">{signal}</Badge>)}
                  </div>
                </div>
              )}
            </div>
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
