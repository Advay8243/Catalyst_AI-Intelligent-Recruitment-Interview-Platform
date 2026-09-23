"use client";

import {
  ArrowDown,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  Columns3,
  FileText,
  Filter,
  Mail,
  Phone,
  Plus,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Upload,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { EmptyState, ErrorBanner } from "@/components/empty-state";
import { ScoreDrawer, ScorePill } from "@/components/candidate-panels";
import { UploadDialog } from "@/components/upload-dialog";
import { Badge, Button, Dialog, DialogContent, Input, Skeleton } from "@/components/ui";
import { compareCandidates, getCandidates, getJobs } from "@/lib/api";
import type { Candidate, CandidateComparison, CandidateQuery, Job } from "@/lib/types";
import { formatAiRecommendation, formatEmailStatus, friendlyErrorMessage, initials } from "@/lib/utils";

const PAGE_SIZE = 10;
const MAX_COMPARE = 5;

type Notice = { message: string; error?: boolean };

export function ScreeningClient() {
  const router = useRouter();
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState("");
  const [decisionStatus, setDecisionStatus] = useState("");
  const [screeningStatus, setScreeningStatus] = useState("");
  const [emailStatus, setEmailStatus] = useState("");
  const [minScore, setMinScore] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [minHrScore, setMinHrScore] = useState("");
  const [maxHrScore, setMaxHrScore] = useState("");
  const [uploadedFrom, setUploadedFrom] = useState("");
  const [uploadedTo, setUploadedTo] = useState("");
  const [sortBy, setSortBy] = useState("jdScore");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Candidate | null>(null);
  const [drawer, setDrawer] = useState<"jd" | "hr" | null>(null);
  const [uploadKind, setUploadKind] = useState<"jd" | "resume" | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [comparison, setComparison] = useState<CandidateComparison | null>(null);
  const [comparing, setComparing] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    getJobs()
      .then((items) => {
        const usable = items.filter((job) => job.status !== "archived");
        setJobs(usable);
        setJobId((current) => current || usable[0]?.id || "");
      })
      .catch((caught) => {
        setJobs([]);
        setError(friendlyErrorMessage(caught, "Could not load jobs."));
      });
  }, []);

  const query = useMemo<CandidateQuery>(() => ({
    page,
    pageSize: PAGE_SIZE,
    search,
    jobId: jobId || undefined,
    status,
    decisionStatus,
    screeningStatus,
    emailStatus,
    minScore,
    maxScore,
    minHrScore,
    maxHrScore,
    uploadedFrom,
    uploadedTo,
    sortBy,
    sortOrder,
  }), [
    page,
    search,
    jobId,
    status,
    decisionStatus,
    screeningStatus,
    emailStatus,
    minScore,
    maxScore,
    minHrScore,
    maxHrScore,
    uploadedFrom,
    uploadedTo,
    sortBy,
    sortOrder,
  ]);

  const loadCandidates = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getCandidates(query);
      setCandidates(result.items);
      setTotal(result.total);
      setSelectedIds((current) => current.filter((id) => result.items.some((item) => item.id === id)));
    } catch (caught) {
      setCandidates([]);
      setTotal(0);
      setError(friendlyErrorMessage(caught, "Could not load candidates."));
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    void loadCandidates();
  }, [loadCandidates, refreshKey]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 5000);
    return () => clearTimeout(timer);
  }, [notice]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const activeFilters = [
    status,
    decisionStatus,
    screeningStatus,
    emailStatus,
    minScore,
    maxScore,
    minHrScore,
    maxHrScore,
    uploadedFrom,
    uploadedTo,
  ].filter(Boolean).length;
  const showNotice = (message: string, noticeError = false) => setNotice({ message, error: noticeError });
  const openDrawer = (candidate: Candidate, panel: "jd" | "hr") => {
    setSelected(candidate);
    setDrawer(panel);
  };

  const clearFilters = () => {
    setStatus("");
    setDecisionStatus("");
    setScreeningStatus("");
    setEmailStatus("");
    setMinScore("");
    setMaxScore("");
    setMinHrScore("");
    setMaxHrScore("");
    setUploadedFrom("");
    setUploadedTo("");
    setPage(1);
  };

  const toggleSelected = (candidateId: string) => {
    setSelectedIds((current) => {
      if (current.includes(candidateId)) return current.filter((id) => id !== candidateId);
      if (current.length >= MAX_COMPARE) {
        showNotice(`Select up to ${MAX_COMPARE} candidates to compare.`, true);
        return current;
      }
      return [...current, candidateId];
    });
  };

  const runCompare = async () => {
    if (selectedIds.length < 2) {
      showNotice("Select at least two candidates to compare.", true);
      return;
    }
    const compareJobId = jobId || candidates.find((item) => selectedIds.includes(item.id))?.jobId;
    if (!compareJobId) {
      showNotice("Select a job before comparing candidates.", true);
      return;
    }
    setComparing(true);
    try {
      const result = await compareCandidates(compareJobId, selectedIds);
      setComparison(result);
    } catch (caught) {
      showNotice(friendlyErrorMessage(caught, "Could not compare candidates."), true);
    } finally {
      setComparing(false);
    }
  };

  return (
    <div className="min-h-screen">
      <header className="border-b bg-white px-5 py-5 sm:px-8 lg:px-10">
        <div className="mx-auto flex max-w-[1500px] flex-col gap-4 pl-12 sm:pl-0 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="mb-1 flex items-center gap-2 text-xs font-medium text-[#98a2b3]"><span>Recruitment</span><span>/</span><span className="text-[#667085]">Candidate Screening</span></div>
            <h1 className="text-2xl font-bold tracking-tight text-[#101828]">Candidate Screening</h1>
            <p className="mt-1 text-sm text-[#667085]">Search, filter, and compare candidates with transparent score breakdowns.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setUploadKind("jd")}><FileText className="size-4" />Upload / paste JD</Button>
            <Button onClick={() => setUploadKind("resume")}><Upload className="size-4" />Upload resumes</Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1500px] space-y-5 p-5 sm:p-8 lg:p-10">
        <section className="rounded-xl border bg-white p-4 shadow-panel">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
            <label className="relative min-w-0 flex-1 xl:max-w-md">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#98a2b3]" />
              <Input
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Search by name, email, phone, skills, or job title…"
                aria-label="Search candidates"
                className="pl-9 pr-9"
              />
              {searchInput && <button aria-label="Clear search" onClick={() => setSearchInput("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#98a2b3]"><X className="size-4" /></button>}
            </label>
            <select aria-label="Select job" value={jobId} onChange={(event) => { setJobId(event.target.value); setPage(1); setSelectedIds([]); }} className="h-10 min-w-48 rounded-lg border bg-white px-3 text-sm text-[#344054] shadow-sm">
              <option value="">All jobs</option>
              {jobs.filter((job) => job.status !== "archived").map((job) => <option value={job.id} key={job.id}>{job.title}{job.status === "draft" ? " (draft)" : ""}</option>)}
            </select>
            <div className="flex flex-1 flex-wrap gap-2 xl:justify-end">
              <div className="relative">
                <Filter className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#667085]" />
                <select aria-label="Filter by decision status" value={decisionStatus || status} onChange={(event) => { setDecisionStatus(event.target.value); setStatus(""); setPage(1); }} className="h-10 appearance-none rounded-lg border bg-white pl-9 pr-8 text-sm shadow-sm">
                  <option value="">All decisions</option>
                  <option value="pending">Pending decision</option>
                  <option value="accepted">Accepted</option>
                  <option value="advanced">Advanced</option>
                  <option value="rejected">Rejected</option>
                  <option value="needs_review">Needs Review</option>
                </select>
              </div>
              <div className="relative">
                <Filter className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#667085]" />
                <select aria-label="Filter by HR screening status" value={screeningStatus} onChange={(event) => { setScreeningStatus(event.target.value); setPage(1); }} className="h-10 appearance-none rounded-lg border bg-white pl-9 pr-8 text-sm shadow-sm">
                  <option value="">All screening</option>
                  <option value="not_screened">Not Screened</option>
                  <option value="screening_in_progress">Screening In Progress</option>
                  <option value="awaiting_hr_decision">HR Screened</option>
                  <option value="needs_review">Needs Review</option>
                  <option value="accepted">Accepted</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#667085]" />
                <select aria-label="Filter by email status" value={emailStatus} onChange={(event) => { setEmailStatus(event.target.value); setPage(1); }} className="h-10 appearance-none rounded-lg border bg-white pl-9 pr-8 text-sm shadow-sm">
                  <option value="">All email status</option>
                  <option value="not_sent">Not Sent</option>
                  <option value="draft">Draft</option>
                  <option value="sent">Sent</option>
                  <option value="failed">Failed</option>
                </select>
              </div>
              <div className="relative">
                <SlidersHorizontal className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#667085]" />
                <select aria-label="Minimum JD score" value={minScore} onChange={(event) => { setMinScore(event.target.value); setPage(1); }} className="h-10 appearance-none rounded-lg border bg-white pl-9 pr-8 text-sm shadow-sm">
                  <option value="">Min JD score</option>
                  <option value="90">90+</option>
                  <option value="80">80+</option>
                  <option value="70">70+</option>
                  <option value="60">60+</option>
                  <option value="40">40+</option>
                </select>
              </div>
              <select aria-label="Maximum JD score" value={maxScore} onChange={(event) => { setMaxScore(event.target.value); setPage(1); }} className="h-10 rounded-lg border bg-white px-3 text-sm shadow-sm">
                <option value="">Max JD score</option>
                <option value="100">100</option>
                <option value="89">89</option>
                <option value="79">79</option>
                <option value="69">69</option>
                <option value="59">59</option>
              </select>
              <select aria-label="Minimum HR score" value={minHrScore} onChange={(event) => { setMinHrScore(event.target.value); setPage(1); }} className="h-10 rounded-lg border bg-white px-3 text-sm shadow-sm">
                <option value="">Min HR score</option>
                <option value="90">90+</option>
                <option value="80">80+</option>
                <option value="70">70+</option>
                <option value="60">60+</option>
              </select>
              <select aria-label="Maximum HR score" value={maxHrScore} onChange={(event) => { setMaxHrScore(event.target.value); setPage(1); }} className="h-10 rounded-lg border bg-white px-3 text-sm shadow-sm">
                <option value="">Max HR score</option>
                <option value="100">100</option>
                <option value="89">89</option>
                <option value="79">79</option>
                <option value="69">69</option>
              </select>
              <label className="flex h-10 items-center gap-2 rounded-lg border bg-white px-3 text-sm shadow-sm">
                <span className="text-[#667085]">From</span>
                <input aria-label="Date uploaded from" type="date" value={uploadedFrom} onChange={(event) => { setUploadedFrom(event.target.value); setPage(1); }} className="bg-transparent outline-none" />
              </label>
              <label className="flex h-10 items-center gap-2 rounded-lg border bg-white px-3 text-sm shadow-sm">
                <span className="text-[#667085]">To</span>
                <input aria-label="Date uploaded to" type="date" value={uploadedTo} onChange={(event) => { setUploadedTo(event.target.value); setPage(1); }} className="bg-transparent outline-none" />
              </label>
              <select aria-label="Sort candidates" value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(1); }} className="h-10 rounded-lg border bg-white px-3 text-sm shadow-sm">
                <option value="jdScore">Sort: JD score</option>
                <option value="hrScore">Sort: HR score</option>
                <option value="name">Sort: Name</option>
                <option value="createdAt">Sort: Application date</option>
                <option value="decision">Sort: Decision status</option>
              </select>
              <Button variant="secondary" size="icon" aria-label={`Sort ${sortOrder === "desc" ? "descending" : "ascending"}`} onClick={() => setSortOrder((order) => order === "desc" ? "asc" : "desc")}>{sortOrder === "desc" ? <ArrowDown className="size-4" /> : <ArrowUp className="size-4" />}</Button>
            </div>
          </div>
          {activeFilters > 0 && (
            <div className="mt-3 flex items-center gap-2 border-t pt-3 text-xs text-[#667085]">
              <Badge tone="purple">{activeFilters} active</Badge>
              <button className="font-semibold text-primary hover:underline" onClick={clearFilters}>Clear filters</button>
            </div>
          )}
        </section>

        <section className="overflow-hidden rounded-xl border bg-white shadow-panel">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
            <div>
              <h2 className="font-semibold text-[#101828]">Candidates</h2>
              <p className="mt-0.5 text-xs text-[#667085]">{loading ? "Loading…" : `${total} candidate${total === 1 ? "" : "s"} found`}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={selectedIds.length < 2 || comparing}
                onClick={() => void runCompare()}
                aria-label="Compare selected candidates"
              >
                <Columns3 className="size-4" />
                Compare ({selectedIds.length})
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setRefreshKey((key) => key + 1)} disabled={loading}>
                <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />Refresh
              </Button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1280px] table-fixed text-left">
              <thead className="bg-[#f8f9fb] text-[11px] font-bold uppercase tracking-wider text-[#667085]">
                <tr>
                  <th className="w-[48px] px-3 py-3 text-center">Compare</th>
                  <th className="w-[220px] px-5 py-3">Candidate</th>
                  <th className="w-[145px] px-4 py-3">JD → Resume Score</th>
                  <th className="w-[145px] px-4 py-3">HR Screening Score</th>
                  <th className="px-4 py-3">Why Candidate Fits</th>
                  <th className="w-[70px] px-3 py-3 text-center">Call</th>
                  <th className="w-[125px] px-3 py-3 text-center">Email</th>
                  <th className="w-[125px] px-3 py-3 text-center">Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {loading ? <TableSkeleton /> : candidates.map((candidate) => (
                  <tr key={`${candidate.id}-${candidate.jobId}`} className="group hover:bg-[#fcfcfd]">
                    <td className="px-3 py-4 text-center">
                      <input
                        type="checkbox"
                        aria-label={`Select ${candidate.name} for comparison`}
                        checked={selectedIds.includes(candidate.id)}
                        onChange={() => toggleSelected(candidate.id)}
                        className="size-4 rounded border-[#d0d5dd]"
                      />
                    </td>
                    <td className="px-5 py-4">
                      <button className="flex max-w-full items-center gap-3 text-left" onClick={() => router.push(`/screening/candidates/${encodeURIComponent(candidate.id)}${candidate.jobId ? `?job_id=${encodeURIComponent(candidate.jobId)}` : ""}`)}>
                        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-[#fff0f7] text-xs font-bold text-[#b00665]">{initials(candidate.name)}</span>
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-semibold text-[#101828] group-hover:text-primary">{candidate.name}</span>
                          <span className="block truncate text-xs text-[#667085]">{candidate.email}</span>
                          <span className="block truncate text-[11px] text-[#98a2b3]">{candidate.phone ?? "No phone"} · {candidate.jobTitle ?? "Selected job"}{candidate.appliedAt ? ` · Applied ${formatDate(candidate.appliedAt)}` : ""}</span>
                        </span>
                      </button>
                    </td>
                    <td className="px-4 py-4">
                      <button disabled={candidate.jdScore == null} onClick={() => openDrawer(candidate, "jd")} aria-label={`JD score for ${candidate.name}`}>
                        <ScorePill score={candidate.jdScore} />
                        <span className="mt-1 block text-[10px] text-[#98a2b3]">{candidate.resumeStatus ?? "Processed"}</span>
                      </button>
                    </td>
                    <td className="px-4 py-4">
                      <button disabled={candidate.hrScore == null} onClick={() => openDrawer(candidate, "hr")} aria-label={`HR score for ${candidate.name}`}>
                        <ScorePill score={candidate.hrScore} />
                        <span className="mt-1 block max-w-32 text-[10px] text-[#667085]">{candidate.screeningStatus ?? (candidate.hrScore == null ? "Not Screened" : "Awaiting HR Decision")}</span>
                        {candidate.screenedAt && <span className="block text-[10px] text-[#98a2b3]">{formatDate(candidate.screenedAt)}</span>}
                      </button>
                    </td>
                    <td className="px-4 py-4">
                      <p className="line-clamp-2 text-sm leading-5 text-[#475467]" title={candidate.fitReason}>{candidate.fitReason}</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <Badge tone={candidate.status?.toLowerCase() === "rejected" ? "red" : candidate.status?.toLowerCase() === "advanced" || candidate.status?.toLowerCase() === "accepted" ? "green" : "purple"}>{candidate.currentStage ?? "Resume Review"}</Badge>
                        {candidate.screeningRecommendation && <Badge tone="amber">AI: {formatAiRecommendation(candidate.screeningRecommendation)}</Badge>}
                      </div>
                    </td>
                    <td className="px-3 py-4 text-center"><Button variant="ghost" size="icon" aria-label={`Call ${candidate.name}`} onClick={() => router.push(`/screening/call/${encodeURIComponent(candidate.id)}${candidate.jobId ? `?job_id=${encodeURIComponent(candidate.jobId)}` : ""}`)}><Phone className="size-[18px]" /></Button></td>
                    <td className="px-3 py-4 text-center"><button className="inline-flex flex-col items-center gap-1 text-xs font-medium text-[#667085] hover:text-primary" aria-label={`Email history for ${candidate.name}`} onClick={() => router.push(`/screening/candidates/${encodeURIComponent(candidate.id)}${candidate.jobId ? `?job_id=${encodeURIComponent(candidate.jobId)}` : ""}`)}><Mail className="size-[18px]" /><span>{formatEmailStatus(candidate.emailStatus)}</span></button></td>
                    <td className="px-3 py-4 text-center"><Badge tone={candidate.decisionStatus === "rejected" ? "red" : candidate.decisionStatus === "accepted" || candidate.decisionStatus === "advanced" ? "green" : "amber"}>{candidate.decisionStatus === "accepted" || candidate.decisionStatus === "advanced" ? "Accepted" : candidate.decisionStatus === "rejected" ? "Rejected" : candidate.decisionStatus === "needs_review" ? "Needs Review" : "Pending Review"}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!loading && error && <ErrorBanner message={error} onRetry={() => setRefreshKey((key) => key + 1)} />}
          {!loading && !error && !jobId && jobs.length === 0 && (
            <EmptyState
              icon={<FileText className="size-6" />}
              title="No jobs"
              description="Create a job description before uploading resumes."
              action={<Button onClick={() => setUploadKind("jd")}><Plus className="size-4" />Upload / paste JD</Button>}
            />
          )}
          {!loading && !error && candidates.length === 0 && (jobId || jobs.length > 0) && (
            <EmptyState
              icon={<FileText className="size-6" />}
              title={search || activeFilters ? "No matching candidates" : "No candidates yet"}
              description={search || activeFilters ? "Try changing your search or filters." : "Upload resumes to begin screening candidates."}
              action={!search && !activeFilters ? <Button onClick={() => setUploadKind("resume")}><Plus className="size-4" />Upload resumes</Button> : undefined}
            />
          )}
          {!loading && !error && candidates.length > 0 && (
            <div className="flex flex-col items-center justify-between gap-3 border-t px-5 py-4 sm:flex-row">
              <p className="text-xs text-[#667085]">Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}</p>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ChevronLeft className="size-4" />Previous</Button>
                <span className="px-2 text-xs font-medium">Page {page} of {pageCount}</span>
                <Button variant="secondary" size="sm" disabled={page >= pageCount} onClick={() => setPage((value) => value + 1)}>Next<ChevronRight className="size-4" /></Button>
              </div>
            </div>
          )}
        </section>
      </div>

      <ScoreDrawer candidate={selected} type="jd" open={drawer === "jd"} onOpenChange={(open) => !open && setDrawer(null)} />
      <ScoreDrawer candidate={selected} type="hr" open={drawer === "hr"} onOpenChange={(open) => !open && setDrawer(null)} />
      <ComparisonDialog comparison={comparison} open={Boolean(comparison)} onOpenChange={(open) => !open && setComparison(null)} />
      {uploadKind && (
        <UploadDialog
          kind={uploadKind}
          open={Boolean(uploadKind)}
          onOpenChange={(open) => !open && setUploadKind(null)}
          jobId={jobId}
          onComplete={(createdJob) => {
            if (createdJob) {
              setJobs((current) => [createdJob, ...current.filter((job) => job.id !== createdJob.id)]);
              setJobId(createdJob.id);
            }
            setRefreshKey((key) => key + 1);
          }}
          onNotice={showNotice}
        />
      )}
      {notice && <div role={notice.error ? "alert" : "status"} className={`fixed bottom-5 right-5 z-[100] max-w-sm rounded-xl border px-4 py-3 text-sm font-medium shadow-xl ${notice.error ? "border-red-200 bg-red-50 text-red-800" : "border-green-200 bg-white text-green-800"}`}>{notice.message}</div>}
    </div>
  );
}

function ComparisonDialog({
  comparison,
  open,
  onOpenChange,
}: {
  comparison: CandidateComparison | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!comparison) return null;
  const rows: Array<{ label: string; render: (item: CandidateComparison["items"][number]) => ReactNode }> = [
    { label: "Candidate", render: (item) => <div><p className="font-semibold text-[#101828]">{item.fullName}</p><p className="text-xs text-[#667085]">{item.email}</p></div> },
    { label: "JD match", render: (item) => <ScorePill score={item.jdScore} /> },
    { label: "Required skills", render: (item) => <ScoreList score={item.requiredSkillsScore} items={item.matchedRequiredSkills} empty="None matched" /> },
    { label: "Preferred skills", render: (item) => <ScoreList score={item.preferredSkillsScore} items={item.matchedPreferredSkills} empty="None matched" /> },
    { label: "Experience", render: (item) => <div><p className="font-medium">{item.experienceScore == null ? "—" : `${item.experienceScore}%`}</p><p className="text-xs text-[#667085]">{item.experienceYears == null ? "Years not provided" : `${item.experienceYears} years`}</p></div> },
    { label: "Responsibilities", render: (item) => <p className="font-medium">{item.responsibilitiesScore == null ? "—" : `${item.responsibilitiesScore}%`}</p> },
    { label: "Education", render: (item) => <ScoreList score={item.educationScore} items={item.education} empty="Not provided" /> },
    { label: "HR screening", render: (item) => <ScorePill score={item.hrScore} /> },
    { label: "Strengths", render: (item) => <BulletList items={item.strengths} empty="No strengths recorded" /> },
    { label: "Missing information", render: (item) => <BulletList items={item.missingInformation.length ? item.missingInformation : item.missingRequiredSkills.map((skill) => `Missing required skill: ${skill}`)} empty="None noted" /> },
    { label: "AI recommendation", render: (item) => item.aiRecommendation ? formatAiRecommendation(item.aiRecommendation) : "Pending" },
    { label: "Human decision", render: (item) => item.humanDecision === "pending" ? "Pending Review" : item.humanDecision.replaceAll("_", " ") },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={`Compare · ${comparison.jobTitle}`} description="Side-by-side evidence using transparent category scores. Protected characteristics are excluded." className="max-w-[96vw] sm:max-w-5xl">
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-sm">
            <thead>
              <tr>
                <th className="sticky left-0 bg-white px-3 py-2 text-left text-xs font-bold uppercase tracking-wider text-[#667085]">Metric</th>
                {comparison.items.map((item) => (
                  <th key={item.candidateId} className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wider text-[#667085]">{item.fullName}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((row) => (
                <tr key={row.label}>
                  <td className="sticky left-0 bg-white px-3 py-3 align-top text-xs font-semibold uppercase tracking-wide text-[#98a2b3]">{row.label}</td>
                  {comparison.items.map((item) => (
                    <td key={`${row.label}-${item.candidateId}`} className="px-3 py-3 align-top text-[#475467]">{row.render(item)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ScoreList({ score, items, empty }: { score: number | null; items: string[]; empty: string }) {
  return (
    <div>
      <p className="font-medium">{score == null ? "—" : `${score}%`}</p>
      <p className="mt-1 text-xs text-[#667085]">{items.length ? items.join(", ") : empty}</p>
    </div>
  );
}

function BulletList({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <p className="text-xs text-[#98a2b3]">{empty}</p>;
  return (
    <ul className="list-disc space-y-1 pl-4 text-xs text-[#475467]">
      {items.map((item) => <li key={item}>{item}</li>)}
    </ul>
  );
}

function TableSkeleton() {
  return <>{Array.from({ length: 6 }).map((_, index) => <tr key={index}><td className="px-3 py-4"><Skeleton className="mx-auto size-4 rounded" /></td><td className="px-5 py-4"><div className="flex items-center gap-3"><Skeleton className="size-9 rounded-full" /><div className="space-y-2"><Skeleton className="h-3 w-28" /><Skeleton className="h-2.5 w-36" /></div></div></td><td className="px-4"><Skeleton className="h-6 w-12 rounded-full" /></td><td className="px-4"><Skeleton className="h-6 w-12 rounded-full" /></td><td className="px-4"><Skeleton className="h-3 w-full max-w-sm" /></td><td><Skeleton className="mx-auto size-8 rounded-lg" /></td><td><Skeleton className="mx-auto size-8 rounded-lg" /></td><td><Skeleton className="mx-auto h-6 w-16 rounded-full" /></td></tr>)}</>;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}
