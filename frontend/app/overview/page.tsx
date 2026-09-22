"use client";

import {
  BriefcaseBusiness,
  CheckCircle2,
  ClipboardList,
  Mail,
  RefreshCw,
  Search,
  Users,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorBanner } from "@/components/empty-state";
import { Badge, Button, Skeleton } from "@/components/ui";
import { getDashboardActivity, getDashboardStats, getJobs } from "@/lib/api";
import type { DashboardActivity, DashboardStats, Job } from "@/lib/types";
import { friendlyErrorMessage, scoreTextClass } from "@/lib/utils";

export default function OverviewPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState("");
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activity, setActivity] = useState<DashboardActivity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextJobs, nextStats, nextActivity] = await Promise.all([
        getJobs(),
        getDashboardStats(jobId || undefined),
        getDashboardActivity(jobId || undefined, 12),
      ]);
      setJobs(nextJobs.filter((job) => job.status !== "archived"));
      setStats(nextStats);
      setActivity(nextActivity);
    } catch (caught) {
      setStats(null);
      setActivity(null);
      setError(friendlyErrorMessage(caught, "Unable to load dashboard."));
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  const cards = stats
    ? [
        ["Total Candidates", stats.total_candidates, Users],
        ["Pending HR Screening", stats.pending_hr_screening, ClipboardList],
        ["HR Screened", stats.hr_screened, Search],
        ["Needs Review", stats.needs_review, RefreshCw],
        ["Accepted", stats.accepted, CheckCircle2],
        ["Rejected", stats.rejected, XCircle],
        ["Emails Sent", stats.emails_sent, Mail],
        ["Active Job Descriptions", stats.active_job_descriptions, BriefcaseBusiness],
      ] as const
    : [];

  return (
    <div className="min-h-screen">
      <header className="border-b bg-white px-5 py-5 sm:px-8 lg:px-10">
        <div className="mx-auto flex max-w-[1500px] flex-col gap-4 pl-12 sm:pl-0 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="mb-1 flex items-center gap-2 text-xs font-medium text-[#98a2b3]">
              <span>Recruitment</span><span>/</span><span className="text-[#667085]">Overview</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-[#101828]">Recruiter Dashboard</h1>
            <p className="mt-1 text-sm text-[#667085]">Live pipeline metrics from jobs, screening, decisions, and email activity.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Filter dashboard by job"
              value={jobId}
              onChange={(event) => setJobId(event.target.value)}
              className="h-10 min-w-52 rounded-lg border bg-white px-3 text-sm shadow-sm"
            >
              <option value="">All jobs</option>
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>{job.title}</option>
              ))}
            </select>
            <Button variant="secondary" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />Refresh
            </Button>
            <Link href="/screening"><Button>Open candidate table</Button></Link>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1500px] space-y-5 p-5 sm:p-8 lg:p-10">
        {error && <ErrorBanner message={error} onRetry={() => void load()} />}

        {!error && !loading && jobs.length === 0 && (
          <section className="rounded-xl border bg-white shadow-panel">
            <EmptyState
              icon={<BriefcaseBusiness className="size-6" />}
              title="No jobs yet"
              description="Create or publish a job description to start tracking recruitment metrics."
              action={<Link href="/jobs"><Button>Go to Jobs</Button></Link>}
            />
          </section>
        )}

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {loading
            ? Array.from({ length: 8 }).map((_, index) => <Skeleton key={index} className="h-28 rounded-xl" />)
            : cards.map(([label, value, Icon]) => (
              <div key={label} className="rounded-xl border bg-white p-5 shadow-panel">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-[#98a2b3]">{label}</p>
                    <p className="mt-3 text-3xl font-bold text-[#101828]">{value}</p>
                  </div>
                  <span className="flex size-10 items-center justify-center rounded-full bg-[#fff0f7] text-primary">
                    <Icon className="size-5" />
                  </span>
                </div>
              </div>
            ))}
        </section>

        <section className="grid gap-5 xl:grid-cols-[1.2fr_1fr]">
          <div className="rounded-xl border bg-white shadow-panel">
            <div className="border-b px-5 py-4">
              <h2 className="font-semibold">Pipeline quality</h2>
              <p className="text-xs text-[#667085]">Average scores for the selected scope</p>
            </div>
            {loading ? (
              <div className="space-y-3 p-5"><Skeleton className="h-16 rounded-xl" /><Skeleton className="h-16 rounded-xl" /></div>
            ) : stats && stats.total_candidates === 0 ? (
              <EmptyState
                icon={<Users className="size-6" />}
                title="No candidates"
                description="Upload resumes against a job to populate JD → Resume and HR screening averages."
                action={<Link href="/screening"><Button>Open screening</Button></Link>}
              />
            ) : (
              <div className="grid gap-4 p-5 sm:grid-cols-2">
                <ScoreSummary
                  label="Average JD → Resume Score"
                  score={stats?.average_jd_resume_score ?? null}
                />
                <ScoreSummary
                  label="Average HR Screening Score"
                  score={stats?.average_hr_screening_score ?? null}
                />
              </div>
            )}
          </div>

          <div className="rounded-xl border bg-white shadow-panel">
            <div className="border-b px-5 py-4">
              <h2 className="font-semibold">Candidates per job</h2>
              <p className="text-xs text-[#667085]">Active job descriptions only</p>
            </div>
            {loading ? (
              <div className="space-y-3 p-5"><Skeleton className="h-10 rounded-lg" /><Skeleton className="h-10 rounded-lg" /></div>
            ) : !stats?.candidates_per_job.length ? (
              <EmptyState
                icon={<BriefcaseBusiness className="size-6" />}
                title="No active jobs"
                description="Publish a job description to see candidates grouped by role."
                action={<Link href="/jobs"><Button variant="secondary">Manage jobs</Button></Link>}
              />
            ) : (
              <div className="divide-y">
                {stats.candidates_per_job.map((job) => (
                  <div key={job.job_id} className="flex items-center justify-between gap-3 px-5 py-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{job.title}</p>
                      <Badge tone={job.status === "published" ? "green" : "amber"}>{job.status}</Badge>
                    </div>
                    <p className="text-sm font-semibold text-[#101828]">{job.candidate_count}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="rounded-xl border bg-white shadow-panel">
          <div className="border-b px-5 py-4">
            <h2 className="font-semibold">Recent activity</h2>
            <p className="text-xs text-[#667085]">Resume uploads, scores, calls, decisions, and emails</p>
          </div>
          {loading ? (
            <div className="space-y-3 p-5">{Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-12 rounded-lg" />)}</div>
          ) : !activity?.items.length ? (
            <EmptyState
              icon={<ClipboardList className="size-6" />}
              title="No activity yet"
              description="Activity appears after resumes are uploaded, screened, decided, or emailed."
            />
          ) : (
            <ol className="divide-y">
              {activity.items.map((item) => (
                <li key={item.id} className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-medium text-[#101828]">{item.title}</p>
                    <p className="mt-1 text-sm text-[#667085]">{item.description}</p>
                    <p className="mt-1 text-xs text-[#98a2b3]">
                      {[item.candidate_name, item.job_title, item.actor ? `By ${item.actor}` : null]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <time className="text-xs text-[#98a2b3]">{formatDateTime(item.timestamp)}</time>
                    {item.candidate_id && (
                      <Link
                        href={`/screening/candidates/${encodeURIComponent(item.candidate_id)}${item.job_id ? `?job_id=${encodeURIComponent(item.job_id)}` : ""}`}
                        className="text-xs font-semibold text-primary hover:underline"
                      >
                        View
                      </Link>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}

function ScoreSummary({ label, score }: { label: string; score: number | null }) {
  return (
    <div className="rounded-xl border bg-[#fafbfc] p-5">
      <p className="text-sm text-[#667085]">{label}</p>
      <p className={`mt-3 text-4xl font-bold ${score == null ? "text-[#98a2b3]" : scoreTextClass(score)}`}>
        {score == null ? "—" : `${score}%`}
      </p>
    </div>
  );
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
