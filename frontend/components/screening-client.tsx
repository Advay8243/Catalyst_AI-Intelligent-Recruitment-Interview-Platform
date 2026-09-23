"use client";

import {
  ArrowDown,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  Columns3,
  FileText,
  LoaderCircle,
  MoreHorizontal,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { EmptyState, ErrorBanner } from "@/components/empty-state";
import { ScoreDrawer, ScorePill } from "@/components/candidate-panels";
import { UploadDialog } from "@/components/upload-dialog";
import { Badge, Button, Dialog, DialogContent, Input, Skeleton } from "@/components/ui";
import {
  compareCandidates,
  generateJobScores,
  getCandidates,
  getJob,
  getJobs,
  searchJobs,
} from "@/lib/api";
import type { Candidate, CandidateComparison, CandidateQuery, Job, JobSearchHit } from "@/lib/types";
import { formatAiRecommendation, formatEmailStatus, friendlyErrorMessage, initials } from "@/lib/utils";

const PAGE_SIZE = 10;
const MAX_COMPARE = 5;
const ANALYZE_MS = 4500;

type Notice = { message: string; error?: boolean };

export function ScreeningClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialJobId = searchParams.get("job_id") ?? "";
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [totalUploaded, setTotalUploaded] = useState<number | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [jdQuery, setJdQuery] = useState("");
  const [jdHits, setJdHits] = useState<JobSearchHit[]>([]);
  const [searchingJobs, setSearchingJobs] = useState(false);
  const [jobId, setJobId] = useState(initialJobId);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [decisionStatus, setDecisionStatus] = useState("");
  const [screeningStatus, setScreeningStatus] = useState("");
  const [emailStatus, setEmailStatus] = useState("");
  const [minScore, setMinScore] = useState("");
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
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [scoresReady, setScoresReady] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeProgress, setAnalyzeProgress] = useState(0);

  useEffect(() => {
    getJobs()
      .then((items) => {
        const active = items.filter((job) => job.status !== "archived");
        setJobs(active);
        if (initialJobId) {
          const match = active.find((job) => job.id === initialJobId);
          if (match) {
            setSelectedJob(match);
            setJobId(match.id);
            setJdQuery(match.title);
          } else {
            getJob(initialJobId)
              .then((job) => {
                setSelectedJob(job);
                setJobId(job.id);
                setJdQuery(job.title);
              })
              .catch(() => undefined);
          }
        }
      })
      .catch((caught) => setError(friendlyErrorMessage(caught, "Could not load jobs.")));
  }, [initialJobId]);

  useEffect(() => {
    if (!jdQuery.trim()) {
      setJdHits([]);
      return;
    }
    const timer = setTimeout(() => {
      setSearchingJobs(true);
      searchJobs(jdQuery.trim())
        .then(setJdHits)
        .catch(() => setJdHits([]))
        .finally(() => setSearchingJobs(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [jdQuery]);

  const query = useMemo<CandidateQuery>(() => ({
    page,
    pageSize: PAGE_SIZE,
    jobId: jobId || undefined,
    decisionStatus,
    screeningStatus,
    emailStatus,
    minScore: minScore || "60",
    sortBy,
    sortOrder,
  }), [page, jobId, decisionStatus, screeningStatus, emailStatus, minScore, sortBy, sortOrder]);

  const loadCandidates = useCallback(async () => {
    if (!jobId || !scoresReady) {
      setCandidates([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await getCandidates(query);
      setCandidates(result.items);
      setTotal(result.total);
      setTotalUploaded(result.totalUploaded);
      setSelectedIds((current) => current.filter((id) => result.items.some((item) => item.id === id)));
    } catch (caught) {
      setCandidates([]);
      setTotal(0);
      setError(friendlyErrorMessage(caught, "Could not load candidates."));
    } finally {
      setLoading(false);
    }
  }, [jobId, query, scoresReady]);

  useEffect(() => {
    void loadCandidates();
  }, [loadCandidates, refreshKey]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 5000);
    return () => clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    if (!analyzing) return;
    setAnalyzeProgress(8);
    const started = Date.now();
    const timer = setInterval(() => {
      const elapsed = Date.now() - started;
      setAnalyzeProgress(Math.min(95, Math.round((elapsed / ANALYZE_MS) * 100)));
    }, 120);
    return () => clearInterval(timer);
  }, [analyzing]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const showNotice = (message: string, noticeError = false) => setNotice({ message, error: noticeError });
  const openDrawer = (candidate: Candidate, panel: "jd" | "hr") => {
    setSelected(candidate);
    setDrawer(panel);
  };

  const selectJob = (job: Job) => {
    setSelectedJob(job);
    setJobId(job.id);
    setJdQuery(job.title);
    setJdHits([]);
    setScoresReady(false);
    setCandidates([]);
    setTotal(0);
    setPage(1);
    setSelectedIds([]);
    router.replace(`/screening?job_id=${encodeURIComponent(job.id)}`);
  };

  const runGenerateScores = async () => {
    if (!jobId) {
      showNotice("Select a JD first.", true);
      return;
    }
    setAnalyzing(true);
    setError("");
    const wait = new Promise((resolve) => setTimeout(resolve, ANALYZE_MS));
    try {
      const [, result] = await Promise.all([wait, generateJobScores(jobId)]);
      setAnalyzeProgress(100);
      setScoresReady(true);
      setSortBy("jdScore");
      setSortOrder("desc");
      setRefreshKey((key) => key + 1);
      showNotice(
        `Analyzed ${result.analyzed_count} resume${result.analyzed_count === 1 ? "" : "s"}. `
        + `${result.shortlisted_count} shortlisted (≥60). `
        + `${result.skipped_below_threshold} below threshold remain stored but hidden.`,
      );
    } catch (caught) {
      showNotice(friendlyErrorMessage(caught, "Could not generate AI scores."), true);
    } finally {
      setTimeout(() => setAnalyzing(false), 250);
    }
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
    if (selectedIds.length < 2 || !jobId) {
      showNotice("Select at least two shortlisted candidates to compare.", true);
      return;
    }
    setComparing(true);
    try {
      setComparison(await compareCandidates(jobId, selectedIds));
    } catch (caught) {
      showNotice(friendlyErrorMessage(caught, "Could not compare candidates."), true);
    } finally {
      setComparing(false);
    }
  };

  const summaryBullets = selectedJob?.requirements?.structured_data?.summary_bullets ?? [];

  return (
    <div className="min-h-screen">
      <header className="border-b bg-white px-5 py-5 sm:px-8 lg:px-10">
        <div className="mx-auto flex max-w-[1500px] flex-col gap-4 pl-12 sm:pl-0 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="mb-1 flex items-center gap-2 text-xs font-medium text-[#98a2b3]"><span>Recruitment</span><span>/</span><span className="text-[#667085]">Candidate Screening</span></div>
            <h1 className="text-2xl font-bold tracking-tight text-[#101828]">Candidate Screening</h1>
            <p className="mt-1 text-sm text-[#667085]">Select a JD, generate AI Calculated Scores, then review shortlisted candidates (≥60).</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setUploadKind("jd")}><FileText className="size-4" />Upload / paste JD</Button>
            <Button onClick={() => setUploadKind("resume")} disabled={!jobId}><Upload className="size-4" />Upload resumes</Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1500px] space-y-5 p-5 sm:p-8 lg:p-10">
        <section className="rounded-xl border bg-white p-4 shadow-panel">
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#667085]">
            <span className="rounded-full bg-[#fff0f7] px-2 py-0.5 text-primary">Step 1</span>
            Select JD with semantic search
          </div>
          <label className="relative block">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#98a2b3]" />
            <Input
              value={jdQuery}
              onChange={(event) => setJdQuery(event.target.value)}
              placeholder='e.g. "Senior Data Engineer with Spark and AWS"'
              aria-label="Semantic search jobs"
              className="pl-9 pr-9"
            />
            {jdQuery && <button aria-label="Clear JD search" onClick={() => { setJdQuery(""); setJdHits([]); }} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#98a2b3]"><X className="size-4" /></button>}
          </label>
          {(searchingJobs || jdHits.length > 0) && (
            <div className="mt-2 max-h-56 overflow-y-auto rounded-lg border bg-[#fafbfc]">
              {searchingJobs && <p className="px-3 py-2 text-sm text-[#667085]">Searching related JDs…</p>}
              {!searchingJobs && jdHits.map((hit) => (
                <button
                  key={hit.job.id}
                  className="flex w-full items-center justify-between gap-3 border-b px-3 py-2 text-left last:border-b-0 hover:bg-white"
                  onClick={() => selectJob(hit.job)}
                >
                  <span>
                    <span className="block text-sm font-semibold text-[#101828]">{hit.job.title}</span>
                    <span className="block text-xs text-[#667085]">{hit.job.department || hit.job.location || "JD"}</span>
                  </span>
                  <Badge tone="purple">{Math.round(hit.similarity * 100)}% match</Badge>
                </button>
              ))}
            </div>
          )}
          {!selectedJob && jobs.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {jobs.slice(0, 6).map((job) => (
                <button key={job.id} onClick={() => selectJob(job)} className="rounded-full border px-3 py-1 text-xs font-medium text-[#475467] hover:border-primary hover:text-primary">
                  {job.title}
                </button>
              ))}
            </div>
          )}
          {selectedJob && (
            <div className="mt-4 rounded-xl border bg-[#fafbfc] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[#101828]">{selectedJob.title}</p>
                  <p className="text-xs text-[#667085]">JD Summary</p>
                </div>
                <Button size="sm" onClick={() => void runGenerateScores()} disabled={analyzing}>
                  <Sparkles className="size-4" />{analyzing ? "Analyzing…" : "Generate AI Scores"}
                </Button>
              </div>
              <ul className="mt-3 grid gap-1.5 text-sm text-[#475467] sm:grid-cols-2">
                {(summaryBullets.length ? summaryBullets : ["Summary will appear after the JD is parsed."]).map((bullet) => (
                  <li key={bullet} className="flex gap-2"><span className="text-primary">•</span><span>{bullet}</span></li>
                ))}
              </ul>
            </div>
          )}
        </section>

        {analyzing && (
          <section className="rounded-xl border border-[#f9dbec] bg-[#fff7fb] p-6 shadow-panel" role="status" aria-live="polite">
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="relative flex size-24 items-center justify-center">
                <div className="absolute inset-0 rounded-full border-4 border-[#f9dbec]" />
                <div
                  className="absolute inset-0 rounded-full border-4 border-primary border-t-transparent animate-spin"
                  style={{ animationDuration: "1.1s" }}
                />
                <LoaderCircle className="size-8 text-primary animate-spin" />
              </div>
              <div>
                <p className="text-lg font-semibold text-[#101828]">Analyzing resumes thoroughly</p>
                <p className="mt-1 text-sm text-[#667085]">Comparing skills, experience, responsibilities, and education against the selected JD…</p>
                <p className="mt-2 text-xs font-medium text-primary">{analyzeProgress}% complete</p>
              </div>
            </div>
          </section>
        )}

        {selectedJob && scoresReady && (
          <>
            <section className="rounded-xl border bg-white p-3 shadow-panel">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-[#fff0f7] px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-primary">Step 2–4</span>
                <select aria-label="Filter by decision status" value={decisionStatus} onChange={(event) => { setDecisionStatus(event.target.value); setPage(1); }} className="h-9 rounded-lg border bg-white px-2 text-sm shadow-sm">
                  <option value="">Decision</option>
                  <option value="pending">Pending</option>
                  <option value="accepted">Accepted</option>
                  <option value="advanced">Advanced</option>
                  <option value="rejected">Rejected</option>
                  <option value="needs_review">Needs Review</option>
                </select>
                <select aria-label="Filter by HR screening status" value={screeningStatus} onChange={(event) => { setScreeningStatus(event.target.value); setPage(1); }} className="h-9 rounded-lg border bg-white px-2 text-sm shadow-sm">
                  <option value="">Screening</option>
                  <option value="not_screened">Not Screened</option>
                  <option value="screening_in_progress">In Progress</option>
                  <option value="awaiting_hr_decision">HR Screened</option>
                </select>
                <select aria-label="Minimum AI Calculated Score" value={minScore} onChange={(event) => { setMinScore(event.target.value); setPage(1); }} className="h-9 rounded-lg border bg-white px-2 text-sm shadow-sm">
                  <option value="">Score ≥60</option>
                  <option value="70">70+</option>
                  <option value="80">80+</option>
                  <option value="90">90+</option>
                </select>
                <select aria-label="Sort candidates" value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(1); }} className="h-9 rounded-lg border bg-white px-2 text-sm shadow-sm">
                  <option value="jdScore">Sort: AI score</option>
                  <option value="hrScore">Sort: HR score</option>
                  <option value="name">Sort: Name</option>
                  <option value="createdAt">Sort: Date</option>
                  <option value="decision">Sort: Decision</option>
                </select>
                <Button variant="secondary" size="icon" aria-label={`Sort ${sortOrder === "desc" ? "descending" : "ascending"}`} onClick={() => setSortOrder((order) => order === "desc" ? "asc" : "desc")}>{sortOrder === "desc" ? <ArrowDown className="size-4" /> : <ArrowUp className="size-4" />}</Button>
                <Button variant="ghost" size="sm" onClick={() => setShowMoreFilters((value) => !value)}><MoreHorizontal className="size-4" />More</Button>
              </div>
              {showMoreFilters && (
                <div className="mt-2 flex flex-wrap gap-2 border-t pt-2">
                  <select aria-label="Filter by email status" value={emailStatus} onChange={(event) => { setEmailStatus(event.target.value); setPage(1); }} className="h-9 rounded-lg border bg-white px-2 text-sm shadow-sm">
                    <option value="">Email status</option>
                    <option value="not_sent">Not Sent</option>
                    <option value="draft">Draft</option>
                    <option value="sent">Sent</option>
                    <option value="failed">Failed</option>
                  </select>
                </div>
              )}
            </section>

            <section className="overflow-hidden rounded-xl border bg-white shadow-panel">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
                <div>
                  <h2 className="font-semibold text-[#101828]">Shortlisted Candidates</h2>
                  <p className="mt-0.5 text-xs text-[#667085]">
                    {loading ? "Loading…" : `${total} shortlisted (≥60)`}
                    {totalUploaded != null ? ` · ${totalUploaded} uploaded for this JD` : ""}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="secondary" size="sm" disabled={selectedIds.length < 2 || comparing} onClick={() => void runCompare()} aria-label="Compare selected candidates">
                    <Columns3 className="size-4" />Compare ({selectedIds.length})
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
                      <th className="w-[145px] px-4 py-3">AI Calculated Score</th>
                      <th className="w-[145px] px-4 py-3">HR Screening Score</th>
                      <th className="px-4 py-3">AI Suggestion — Why Fits / Not Fits</th>
                      <th className="w-[70px] px-3 py-3 text-center">Call</th>
                      <th className="w-[125px] px-3 py-3 text-center">Email</th>
                      <th className="w-[125px] px-3 py-3 text-center">Decision</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {loading ? <TableSkeleton /> : candidates.map((candidate) => (
                      <tr key={`${candidate.id}-${candidate.jobId}`} className="group hover:bg-[#fcfcfd]">
                        <td className="px-3 py-4 text-center">
                          <input type="checkbox" aria-label={`Select ${candidate.name} for comparison`} checked={selectedIds.includes(candidate.id)} onChange={() => toggleSelected(candidate.id)} className="size-4 rounded border-[#d0d5dd]" />
                        </td>
                        <td className="px-5 py-4">
                          <button className="flex max-w-full items-center gap-3 text-left" onClick={() => router.push(`/screening/candidates/${encodeURIComponent(candidate.id)}${candidate.jobId ? `?job_id=${encodeURIComponent(candidate.jobId)}` : ""}`)}>
                            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-[#fff0f7] text-xs font-bold text-[#b00665]">{initials(candidate.name)}</span>
                            <span className="min-w-0">
                              <span className="block truncate text-sm font-semibold text-[#101828] group-hover:text-primary">{candidate.name}</span>
                              <span className="block truncate text-xs text-[#667085]">{candidate.email}</span>
                            </span>
                          </button>
                        </td>
                        <td className="px-4 py-4">
                          <button disabled={candidate.jdScore == null} onClick={() => openDrawer(candidate, "jd")} aria-label={`AI Calculated Score for ${candidate.name}`}>
                            <ScorePill score={candidate.jdScore} />
                          </button>
                        </td>
                        <td className="px-4 py-4">
                          <button disabled={candidate.hrScore == null} onClick={() => openDrawer(candidate, "hr")} aria-label={`HR score for ${candidate.name}`}>
                            <ScorePill score={candidate.hrScore} />
                          </button>
                        </td>
                        <td className="px-4 py-4">
                          <FitGapPreview candidate={candidate} />
                        </td>
                        <td className="px-3 py-4 text-center"><Button variant="ghost" size="icon" aria-label={`Call ${candidate.name}`} onClick={() => router.push(`/screening/call/${encodeURIComponent(candidate.id)}${candidate.jobId ? `?job_id=${encodeURIComponent(candidate.jobId)}` : ""}`)}><Phone className="size-[18px]" /></Button></td>
                        <td className="px-3 py-4 text-center"><button className="inline-flex flex-col items-center gap-1 text-xs font-medium text-[#667085] hover:text-primary" aria-label={`Email history for ${candidate.name}`} onClick={() => router.push(`/screening/candidates/${encodeURIComponent(candidate.id)}${candidate.jobId ? `?job_id=${encodeURIComponent(candidate.jobId)}` : ""}`)}><span>{formatEmailStatus(candidate.emailStatus)}</span></button></td>
                        <td className="px-3 py-4 text-center"><Badge tone={candidate.decisionStatus === "rejected" ? "red" : candidate.decisionStatus === "accepted" || candidate.decisionStatus === "advanced" ? "green" : "amber"}>{candidate.decisionStatus === "accepted" || candidate.decisionStatus === "advanced" ? "Accepted" : candidate.decisionStatus === "rejected" ? "Rejected" : candidate.decisionStatus === "needs_review" ? "Needs Review" : "Pending Review"}</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!loading && error && <ErrorBanner message={error} onRetry={() => setRefreshKey((key) => key + 1)} />}
              {!loading && !error && candidates.length === 0 && (
                <EmptyState
                  icon={<FileText className="size-6" />}
                  title="No shortlisted candidates"
                  description="Upload resumes for this JD, then generate AI scores. Only candidates scoring 60+ appear here."
                  action={<Button onClick={() => setUploadKind("resume")}><Plus className="size-4" />Upload resumes</Button>}
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
          </>
        )}

        {selectedJob && !scoresReady && !analyzing && (
          <EmptyState
            icon={<Sparkles className="size-6" />}
            title="Generate AI Calculated Scores"
            description="Resumes stay stored. Use Generate AI Scores above to thoroughly analyze them against this JD. Only scores ≥60 will appear in Shortlisted Candidates."
          />
        )}
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
              selectJob(createdJob);
            } else {
              setScoresReady(false);
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

function FitGapPreview({ candidate }: { candidate: Candidate }) {
  const fits = candidate.fitPoints?.length ? candidate.fitPoints : [];
  const gaps = candidate.gapPoints?.length ? candidate.gapPoints : [];
  if (!fits.length && !gaps.length) {
    return <p className="line-clamp-3 text-sm text-[#475467]">{candidate.fitReason}</p>;
  }
  return (
    <div className="space-y-2 text-xs text-[#475467]">
      {fits.slice(0, 2).map((point) => <p key={point} className="line-clamp-1"><span className="font-semibold text-green-700">Fits:</span> {point}</p>)}
      {gaps.slice(0, 2).map((point) => <p key={point} className="line-clamp-1"><span className="font-semibold text-amber-700">Gap:</span> {point}</p>)}
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
    { label: "AI Calculated Score", render: (item) => <ScorePill score={item.jdScore} /> },
    { label: "Required skills", render: (item) => <p className="text-xs">{item.matchedRequiredSkills.join(", ") || "None"}</p> },
    { label: "Preferred skills", render: (item) => <p className="text-xs">{item.matchedPreferredSkills.join(", ") || "None"}</p> },
    { label: "Experience", render: (item) => <p className="font-medium">{item.experienceScore == null ? "—" : `${item.experienceScore}%`}</p> },
    { label: "Responsibilities", render: (item) => <p className="font-medium">{item.responsibilitiesScore == null ? "—" : `${item.responsibilitiesScore}%`}</p> },
    { label: "Education", render: (item) => <p className="text-xs">{item.education.join(", ") || "Not provided"}</p> },
    { label: "HR screening", render: (item) => <ScorePill score={item.hrScore} /> },
    { label: "AI recommendation", render: (item) => item.aiRecommendation ? formatAiRecommendation(item.aiRecommendation) : "Pending" },
    { label: "Human decision", render: (item) => item.humanDecision === "pending" ? "Pending Review" : item.humanDecision.replaceAll("_", " ") },
  ];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={`Compare · ${comparison.jobTitle}`} description="Transparent category scores only. Protected characteristics are excluded." className="max-w-[96vw] sm:max-w-5xl">
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

function TableSkeleton() {
  return <>{Array.from({ length: 4 }).map((_, index) => <tr key={index}><td className="px-3 py-4"><Skeleton className="mx-auto size-4 rounded" /></td><td className="px-5 py-4"><Skeleton className="h-8 w-40" /></td><td className="px-4"><Skeleton className="h-6 w-12 rounded-full" /></td><td className="px-4"><Skeleton className="h-6 w-12 rounded-full" /></td><td className="px-4"><Skeleton className="h-8 w-full max-w-sm" /></td><td /><td /><td /></tr>)}</>;
}
