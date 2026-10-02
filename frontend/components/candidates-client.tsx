"use client";

import { Search, Upload, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorBanner } from "@/components/empty-state";
import { UploadDialog } from "@/components/upload-dialog";
import { Button, Input, Skeleton } from "@/components/ui";
import { getCandidates, getJobs } from "@/lib/api";
import type { Candidate, Job } from "@/lib/types";
import { friendlyErrorMessage, initials } from "@/lib/utils";

export function CandidatesClient() {
  const router = useRouter();
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [uploadJobId, setUploadJobId] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    getJobs()
      .then((items) => {
        const published = items.filter((job) => job.status === "published");
        setJobs(published);
        if (published.length && !uploadJobId) {
          setUploadJobId(published[0].id);
        }
      })
      .catch(() => setJobs([]));
  }, [uploadJobId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getCandidates({
        page: 1,
        pageSize: 50,
        search: search.trim() || undefined,
        sortBy: "name",
        sortOrder: "asc",
      });
      setCandidates(result.items);
      setTotal(result.total);
    } catch (caught) {
      setCandidates([]);
      setTotal(0);
      setError(friendlyErrorMessage(caught, "Could not load candidates."));
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    const timer = setTimeout(() => void load(), search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  return (
    <div className="min-h-screen">
      <header className="border-b bg-white px-5 py-5 sm:px-8 lg:px-10">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-4 pl-12 sm:pl-0 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="mb-1 flex items-center gap-2 text-xs font-medium text-[#98a2b3]">
              <span>Recruitment</span><span>/</span><span className="text-[#667085]">Candidates</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-[#101828]">Candidates</h1>
            <p className="mt-1 text-sm text-[#667085]">Upload and manage candidate resumes. AI scoring happens in Candidate Screening.</p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-[#667085]">Associate with job</span>
              <select
                aria-label="Job for resume upload"
                value={uploadJobId}
                onChange={(event) => setUploadJobId(event.target.value)}
                className="h-10 min-w-[200px] rounded-lg border bg-white px-3 text-sm shadow-sm"
              >
                <option value="">Select a published job</option>
                {jobs.map((job) => (
                  <option key={job.id} value={job.id}>{job.title}</option>
                ))}
              </select>
            </label>
            <Button onClick={() => setUploadOpen(true)} disabled={!uploadJobId}>
              <Upload className="size-4" />Upload Resume
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1200px] space-y-5 p-5 sm:p-8 lg:p-10">
        {notice && (
          <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">{notice}</div>
        )}
        <label className="relative block">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#98a2b3]" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by name, email, or skill…"
            aria-label="Search candidates"
            className="pl-9"
          />
        </label>

        {error && <ErrorBanner message={error} onRetry={() => void load()} />}

        <section className="overflow-hidden rounded-xl border bg-white shadow-panel">
          <div className="border-b px-5 py-4">
            <h2 className="font-semibold">All candidates</h2>
            <p className="text-xs text-[#667085]">{loading ? "Loading…" : `${total} candidate${total === 1 ? "" : "s"}`}</p>
          </div>
          {loading ? (
            <div className="space-y-3 p-5">{Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-16 rounded-xl" />)}</div>
          ) : candidates.length === 0 ? (
            <EmptyState
              icon={<Users className="size-6" />}
              title="No candidates found"
              description="Upload a resume and associate it with a published job to add candidates."
            />
          ) : (
            <ul className="divide-y">
              {candidates.map((candidate) => (
                <li key={`${candidate.id}-${candidate.jobId ?? "none"}`}>
                  <button
                    type="button"
                    className="flex w-full items-center gap-4 px-5 py-4 text-left hover:bg-[#fcfcfd]"
                    onClick={() => router.push(`/screening/candidates/${encodeURIComponent(candidate.id)}${candidate.jobId ? `?job_id=${encodeURIComponent(candidate.jobId)}` : ""}`)}
                  >
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-[#fff0f7] text-sm font-bold text-[#b00665]">
                      {initials(candidate.name)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-semibold text-[#101828]">{candidate.name}</span>
                      <span className="block text-sm text-[#667085]">{candidate.email}</span>
                      {candidate.phone && <span className="mt-0.5 block text-xs text-[#98a2b3]">{candidate.phone}</span>}
                      {candidate.jobTitle && <span className="mt-0.5 block text-xs text-[#98a2b3]">Applied: {candidate.jobTitle}</span>}
                      {candidate.skills && candidate.skills.length > 0 && (
                        <span className="mt-1 block text-xs text-[#475467]">
                          Skills: {candidate.skills.slice(0, 6).join(", ")}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <UploadDialog
        kind="resume"
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        jobId={uploadJobId}
        onComplete={() => {
          setNotice("Resume uploaded. It is now available in Candidate Screening for the selected job.");
          void load();
        }}
        onNotice={(message, isError) => {
          if (isError) setError(message);
          else setNotice(message);
        }}
      />
    </div>
  );
}
