"use client";

import {
  AlertTriangle,
  ArrowLeft,
  BriefcaseBusiness,
  CalendarDays,
  CheckCircle2,
  Download,
  FileText,
  History,
  Mail,
  Phone,
  Sparkles,
  UserRound,
  XCircle,
} from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { EmailComposer } from "@/components/email-composer";
import { Badge, Button, Dialog, DialogContent, Progress, Skeleton } from "@/components/ui";
import { getCandidateReview, recordDecision, resumeDownloadUrl } from "@/lib/api";
import type { Candidate, CandidateReview, Decision, EmailHistoryItem, EmailType } from "@/lib/types";
import { initials } from "@/lib/utils";

export default function CandidateReviewPage() {
  const { candidate_id: candidateId } = useParams<{ candidate_id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const jobId = searchParams.get("job_id") ?? undefined;
  const [review, setReview] = useState<CandidateReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState<Decision | null>(null);
  const [decisionReason, setDecisionReason] = useState("");
  const [decisionNotes, setDecisionNotes] = useState("");
  const [deciding, setDeciding] = useState(false);
  const [emailOpen, setEmailOpen] = useState(false);
  const [emailType, setEmailType] = useState<EmailType | undefined>();
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setReview(await getCandidateReview(candidateId, jobId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load candidate review.");
    } finally {
      setLoading(false);
    }
  }, [candidateId, jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  const candidateForEmail = useMemo<Candidate | null>(() => {
    if (!review) return null;
    return {
      id: review.candidate.id,
      name: review.candidate.name,
      email: review.candidate.email,
      phone: review.candidate.phone,
      jdScore: review.resume_analysis.overall_score,
      hrScore: review.screening_analysis?.overall_score ?? null,
      fitReason: review.resume_analysis.explanation,
      jobId: review.job.id,
      jobTitle: review.job.title,
      status: review.application.status,
    };
  }, [review]);

  async function decide() {
    if (!review || !confirming) return;
    setDeciding(true);
    setError("");
    try {
      await recordDecision(
        review.candidate.id,
        review.job.id,
        confirming,
        { decisionReason, decisionNotes },
      );
      const recordedDecision = confirming;
      setConfirming(null);
      setDecisionReason("");
      setDecisionNotes("");
      await load();
      if (recordedDecision === "accepted" || recordedDecision === "rejected") {
        setEmailType(recordedDecision);
        setNotice(
          recordedDecision === "accepted"
            ? "Candidate accepted. Review the next-step email before sending."
            : "Candidate rejected. Review the rejection email before sending.",
        );
        setEmailOpen(true);
      } else {
        setNotice("Further review requested. No candidate email was sent.");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to record decision.");
    } finally {
      setDeciding(false);
    }
  }

  if (loading) return <ReviewSkeleton />;
  if (!review) {
    return (
      <main className="mx-auto max-w-3xl p-8">
        <div className="rounded-xl border bg-white p-10 text-center shadow-panel">
          <h1 className="font-semibold">Unable to load candidate</h1>
          <p className="mt-2 text-sm text-[#667085]">{error}</p>
          <Button className="mt-5" onClick={() => router.push("/screening")}>
            <ArrowLeft className="size-4" /> Back to Candidates
          </Button>
        </div>
      </main>
    );
  }

  const screening = review.screening_analysis;
  const decision = review.application.decision;
  const accepted = decision === "accepted" || decision === "advanced";
  const finalDecision = accepted || decision === "rejected";

  return (
    <div className="min-h-screen bg-[#f7f8fa]">
      <header className="border-b bg-white px-5 py-5 sm:px-8">
        <div className="mx-auto max-w-7xl">
          <button onClick={() => router.push("/screening")} className="mb-3 flex items-center gap-2 text-sm font-semibold text-[#667085] hover:text-primary">
            <ArrowLeft className="size-4" /> Back to Candidates
          </button>
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-4">
              <span className="flex size-14 items-center justify-center rounded-full bg-[#fff0f7] text-lg font-bold text-[#b00665]">{initials(review.candidate.name)}</span>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl font-bold">{review.candidate.name}</h1>
                  <StatusBadge status={review.application.screening_status} />
                </div>
                <p className="mt-1 text-sm text-[#667085]">{review.job.title} · Applied {formatDate(review.application.applied_at)}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {finalDecision ? (
                <>
                  <Badge tone={accepted ? "green" : "red"} className="px-3 py-2 text-sm">{accepted ? "Accepted" : "Rejected"}</Badge>
                  <Button onClick={() => { setEmailType(accepted ? "accepted" : "rejected"); setEmailOpen(true); }}><Mail className="size-4" />Compose Candidate Email</Button>
                  {accepted && <Button variant="secondary" onClick={() => { setEmailType("internal"); setEmailOpen(true); }}><Mail className="size-4" />Notify Interviewer / HR</Button>}
                </>
              ) : (
                <>
                  <Button disabled={!screening} onClick={() => setConfirming("accepted")}><CheckCircle2 className="size-4" />Accept Candidate</Button>
                  <Button variant="danger" disabled={!screening} onClick={() => setConfirming("rejected")}><XCircle className="size-4" />Reject Candidate</Button>
                  <Button variant="secondary" disabled={!screening || decision === "needs_review"} onClick={() => setConfirming("needs_review")}><History className="size-4" />Request Further Review</Button>
                </>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-5 p-5 sm:p-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          <Card title="Candidate information" icon={<UserRound />}>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Info label="Email" value={review.candidate.email} icon={<Mail />} />
              <Info label="Phone" value={review.candidate.phone ?? "Not provided"} icon={<Phone />} />
              <Info label="Applied position" value={review.job.title} icon={<BriefcaseBusiness />} />
              <Info label="Application date" value={formatDate(review.application.applied_at)} icon={<CalendarDays />} />
              <Info label="Current stage" value={review.application.current_stage} icon={<Sparkles />} />
              <Info label="Resume status" value={review.application.resume_status} icon={<FileText />} />
            </div>
            <a href={resumeDownloadUrl(review.resume.id)} className="mt-5 inline-flex">
              <Button variant="secondary"><Download className="size-4" />Download {review.resume.filename}</Button>
            </a>
          </Card>

          <Card title="Job description" icon={<BriefcaseBusiness />}>
            <p className="text-sm leading-6 text-[#475467]">{review.job.description}</p>
            <RequirementList title="Responsibilities" items={review.job.responsibilities} />
            <div className="mt-5 grid gap-5 md:grid-cols-2">
              <RequirementList title="Required skills" items={review.job.required_skills} badges />
              <RequirementList title="Preferred skills" items={review.job.preferred_skills} badges />
            </div>
            <p className="mt-5 text-sm"><strong>Experience requirement:</strong> {review.job.experience_requirements}</p>
          </Card>

          <Card title="Resume analysis" icon={<FileText />}>
            <Badge tone="purple">AI-generated analysis</Badge>
            <div className="grid gap-5 md:grid-cols-[180px_1fr]">
              <ScoreCircle score={review.resume_analysis.overall_score} label="JD → Resume" />
              <div>
                <RequirementList title="Extracted skills" items={review.resume.parsed_data.skills ?? []} badges />
                <p className="mt-4 text-sm text-[#475467]"><strong>Experience:</strong> {review.resume.parsed_data.years_experience ?? "Not extracted"} years</p>
                <RequirementList title="Education" items={review.resume.parsed_data.education ?? []} />
                <RequirementList title="Relevant projects / highlights" items={review.resume.parsed_data.projects ?? review.resume.parsed_data.highlights ?? []} />
              </div>
            </div>
            <div className="mt-5 rounded-xl bg-[#f8f9fb] p-4 text-sm leading-6 text-[#475467]">{review.resume_analysis.explanation}</div>
          </Card>

          <Card title="HR screening review" icon={<Sparkles />}>
            {!screening ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
                HR screening has not been completed. Complete the call before recording a decision.
              </div>
            ) : (
              <>
                <div className="flex flex-col gap-5 rounded-xl border bg-[#fcfcfd] p-5 sm:flex-row sm:items-center">
                  <ScoreCircle score={screening.overall_score} label="HR screening" />
                  <div>
                    <Badge tone="purple">{screening.label}</Badge>
                    <p className="mt-3 text-sm leading-6 text-[#475467]">{screening.summary}</p>
                    <p className="mt-2 text-xs font-medium text-[#667085]">This assessment supports review; HR remains responsible for the final decision.</p>
                  </div>
                </div>
                <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <Metric label="Communication" score={screening.score_components.communication ?? 0} />
                  <Metric label="Role relevance" score={screening.role_relevance} />
                  <Metric label="Experience alignment" score={screening.score_components.experience ?? 0} />
                  <Metric label="Skills alignment" score={screening.score_components.skills ?? 0} />
                  <Metric label="Motivation" score={screening.score_components.motivation ?? 0} />
                  <Metric label="Availability" score={screening.score_components.availability ?? 0} />
                </div>
                <div className="mt-6 space-y-4">
                  <h3 className="font-semibold">Question and answer analysis</h3>
                  {screening.question_analysis.map((item, index) => (
                    <div key={`${item.question}-${index}`} className="rounded-xl border p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div><p className="text-xs font-bold uppercase tracking-wide text-[#98a2b3]">Question {index + 1} · {item.category}</p><p className="mt-1 font-medium">{item.question}</p></div>
                        <Badge tone={item.score >= 75 ? "green" : item.score >= 55 ? "amber" : "red"}>{item.score}%</Badge>
                      </div>
                      <div className="mt-3 rounded-lg bg-[#f8f9fb] p-3 text-sm leading-6"><strong>Answer:</strong> {item.answer ?? "No answer captured"}</div>
                      <p className="mt-3 text-sm text-[#475467]"><strong>AI analysis:</strong> {item.assessment}</p>
                      {item.follow_up_question && <p className="mt-2 text-sm text-primary"><strong>Suggested follow-up:</strong> {item.follow_up_question}</p>}
                    </div>
                  ))}
                </div>
                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  <EvidenceList title="Strengths" items={screening.strengths} tone="green" />
                  <EvidenceList title="Concerns" items={screening.concerns} tone="amber" />
                </div>
              </>
            )}
          </Card>

          <Card title="Candidate timeline" icon={<History />}>
            {review.timeline.length ? (
              <ol className="relative ml-3 border-l border-[#d0d5dd]">
                {review.timeline.map((event) => (
                  <li key={event.id} className="relative pb-6 pl-7 last:pb-0">
                    <span className="absolute -left-[7px] top-1.5 size-3 rounded-full border-2 border-white bg-primary ring-2 ring-[#ffd2e8]" />
                    <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                      <div><p className="font-medium">{event.title}</p><p className="mt-1 text-sm leading-6 text-[#667085]">{event.description}</p>{event.actor && <p className="mt-1 text-xs text-[#98a2b3]">By {event.actor}</p>}</div>
                      <time className="shrink-0 text-xs text-[#98a2b3]">{formatDateTime(event.timestamp)}</time>
                    </div>
                  </li>
                ))}
              </ol>
            ) : <p className="text-sm text-[#667085]">No timeline events are available.</p>}
          </Card>

          <Card title="Decision history" icon={<CheckCircle2 />}>
            {review.decision_history.length ? (
              <div className="space-y-3">
                {review.decision_history.map((item) => (
                  <div key={item.id} className="rounded-xl border p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Badge tone={item.decision === "rejected" ? "red" : item.decision === "needs_review" ? "amber" : "green"}>{decisionLabel(item.decision)}</Badge>
                      <time className="text-xs text-[#98a2b3]">{formatDateTime(item.decision_timestamp)}</time>
                    </div>
                    <p className="mt-2 text-sm text-[#667085]">By {item.decision_maker}</p>
                    {item.decision_reason && <p className="mt-2 text-sm"><strong>Reason:</strong> {item.decision_reason}</p>}
                    {item.decision_notes && <p className="mt-2 text-sm"><strong>Notes:</strong> {item.decision_notes}</p>}
                  </div>
                ))}
              </div>
            ) : <p className="text-sm text-[#667085]">No human decision has been recorded.</p>}
          </Card>

          <Card title="Email history" icon={<Mail />}>
            {review.email_history.length ? (
              <div className="divide-y rounded-xl border">
                {review.email_history.map((email) => (
                  <div key={email.id} className="p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-medium">{email.subject}</p>
                      <div className="flex gap-2"><Badge tone={email.email_type === "rejected" ? "red" : email.email_type === "internal" ? "purple" : "green"}>{email.email_type}</Badge><Badge tone="purple">{email.status.replace("_", " ")}</Badge></div>
                    </div>
                    <p className="mt-1 text-xs text-[#667085]">To {email.recipient} · {formatDateTime(email.sent_at ?? email.created_at)}</p>
                    <p className="mt-3 line-clamp-3 whitespace-pre-wrap text-sm leading-6 text-[#475467]">{email.body}</p>
                  </div>
                ))}
              </div>
            ) : <p className="text-sm text-[#667085]">No candidate emails have been mock-sent yet.</p>}
          </Card>
        </div>

        <aside className="space-y-5">
          <Card title="Review status" icon={<Sparkles />}>
            <Badge tone="green" className="mb-4">Human decision</Badge>
            <dl className="space-y-4">
              <CompactInfo label="Resume" value={review.application.resume_status} />
              <CompactInfo label="HR screening" value={review.application.screening_status} />
              <CompactInfo label="AI recommendation" value={screening?.recommendation.replaceAll("_", " ") ?? "Not available"} />
              <CompactInfo label="Screened" value={review.application.screened_at ? formatDateTime(review.application.screened_at) : "Not yet"} />
              <CompactInfo label="Human decision" value={decision ? decisionLabel(decision) : "Pending Review"} />
              {review.application.decision_by && <CompactInfo label="Decision maker" value={review.application.decision_by} />}
              {review.application.decision_at && <CompactInfo label="Decision date" value={formatDateTime(review.application.decision_at)} />}
              {review.application.decision_reason && <CompactInfo label="Reason" value={review.application.decision_reason} />}
              {review.application.decision_notes && <CompactInfo label="Notes" value={review.application.decision_notes} />}
            </dl>
          </Card>
          {screening && (
            <div className="rounded-xl border border-[#ffd2e8] bg-[#fff7fb] p-5">
              <div className="flex gap-3"><AlertTriangle className="mt-0.5 size-5 shrink-0 text-primary" /><div><p className="font-semibold text-[#811149]">Human decision required</p><p className="mt-1 text-sm leading-6 text-[#a1085d]">AI scores and recommendations are assistive signals. Review the resume, transcript, and evidence before deciding.</p></div></div>
            </div>
          )}
        </aside>
      </main>

      <Dialog open={Boolean(confirming)} onOpenChange={(open) => !open && setConfirming(null)}>
        <DialogContent title={confirming === "accepted" ? "Accept candidate?" : confirming === "rejected" ? "Reject candidate?" : "Request further review?"} description="This human decision will be stored with your identity and a timestamp." className="max-w-md">
          <p className="mt-5 text-sm leading-6 text-[#475467]">Confirm that you want to {confirming === "accepted" ? "accept" : confirming === "rejected" ? "reject" : "request further review for"} {review.candidate.name} for the {review.job.title} position. AI recommendations do not trigger this action.</p>
          {confirming === "rejected" && <label className="mt-4 block"><span className="mb-1.5 block text-sm font-medium">Reason (optional)</span><textarea aria-label="Decision reason" rows={3} value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} className="w-full rounded-lg border p-3 text-sm" /></label>}
          {confirming !== "rejected" && <label className="mt-4 block"><span className="mb-1.5 block text-sm font-medium">{confirming === "accepted" ? "Notes" : "Review notes"} (optional)</span><textarea aria-label="Decision notes" rows={3} value={decisionNotes} onChange={(event) => setDecisionNotes(event.target.value)} className="w-full rounded-lg border p-3 text-sm" /></label>}
          <p className="mt-2 text-xs text-[#667085]">Record only job-relevant information. Do not include protected characteristics.</p>
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirming(null)}>Cancel</Button>
            <Button variant={confirming === "rejected" ? "danger" : "primary"} disabled={deciding} onClick={() => void decide()}>{deciding ? "Saving…" : `Confirm ${confirming === "accepted" ? "Accept" : confirming === "rejected" ? "Reject" : "Further Review"}`}</Button>
          </div>
        </DialogContent>
      </Dialog>

      <EmailComposer
        candidate={candidateForEmail}
        open={emailOpen}
        onOpenChange={(open) => {
          setEmailOpen(open);
          if (!open) {
            setEmailType(undefined);
            void load();
          }
        }}
        onNotice={setNotice}
        decision={review.application.decision}
        emailType={emailType}
        jobId={review.job.id}
        onSent={(email: EmailHistoryItem) => setReview((current) => current ? { ...current, email_history: [email, ...current.email_history] } : current)}
      />
      {notice && <div role="status" className="fixed bottom-5 right-5 z-[100] max-w-sm rounded-xl border border-green-200 bg-white px-4 py-3 text-sm font-medium text-green-800 shadow-xl">{notice}</div>}
      {error && <div role="alert" className="fixed bottom-5 left-5 z-[100] max-w-sm rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 shadow-xl">{error}</div>}
    </div>
  );
}

function Card({ title, icon, children }: { title: string; icon: React.ReactElement; children: React.ReactNode }) {
  return <section className="rounded-xl border bg-white p-5 shadow-panel sm:p-6"><h2 className="mb-5 flex items-center gap-2 font-semibold text-[#101828]"><span className="text-primary [&>svg]:size-4">{icon}</span>{title}</h2>{children}</section>;
}

function Info({ label, value, icon }: { label: string; value: string; icon: React.ReactElement }) {
  return <div className="flex gap-3"><span className="mt-0.5 text-[#98a2b3] [&>svg]:size-4">{icon}</span><div><p className="text-xs text-[#98a2b3]">{label}</p><p className="mt-0.5 text-sm font-medium">{value}</p></div></div>;
}

function CompactInfo({ label, value }: { label: string; value: string }) {
  return <div className="flex items-start justify-between gap-4"><dt className="text-sm text-[#667085]">{label}</dt><dd className="text-right text-sm font-semibold">{value}</dd></div>;
}

function RequirementList({ title, items, badges = false }: { title: string; items: string[]; badges?: boolean }) {
  return <div className="mt-4"><h3 className="text-xs font-bold uppercase tracking-wide text-[#98a2b3]">{title}</h3>{items.length ? badges ? <div className="mt-2 flex flex-wrap gap-2">{items.map((item) => <Badge key={item} tone="purple">{item}</Badge>)}</div> : <ul className="mt-2 space-y-1 text-sm text-[#475467]">{items.map((item) => <li key={item}>• {item}</li>)}</ul> : <p className="mt-2 text-sm text-[#98a2b3]">Not specified</p>}</div>;
}

function ScoreCircle({ score, label }: { score: number; label: string }) {
  return <div className="flex items-center gap-3"><span className="flex size-20 shrink-0 items-center justify-center rounded-full border-[7px] border-[#ffd2e8] text-xl font-bold text-primary">{score}%</span><span className="text-xs font-medium text-[#667085]">{label}</span></div>;
}

function Metric({ label, score }: { label: string; score: number }) {
  return <div><div className="mb-2 flex justify-between text-xs"><span>{label}</span><strong>{score}%</strong></div><Progress value={score} /></div>;
}

function EvidenceList({ title, items, tone }: { title: string; items: string[]; tone: "green" | "amber" }) {
  return <div className={`rounded-xl border p-4 ${tone === "green" ? "border-green-200 bg-green-50" : "border-amber-200 bg-amber-50"}`}><h3 className="font-semibold">{title}</h3>{items.length ? <ul className="mt-2 space-y-2 text-sm">{items.map((item) => <li key={item}>• {item}</li>)}</ul> : <p className="mt-2 text-sm text-[#667085]">None identified.</p>}</div>;
}

function StatusBadge({ status }: { status: string }) {
  const tone = status === "Accepted" || status === "Advanced" ? "green" : status === "Rejected" ? "red" : status.includes("Progress") ? "purple" : "amber";
  return <Badge tone={tone}>{status}</Badge>;
}

function decisionLabel(decision: Decision) {
  if (decision === "accepted" || decision === "advanced") return "Accepted";
  if (decision === "needs_review") return "Needs Review";
  return "Rejected";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function ReviewSkeleton() {
  return <div className="mx-auto max-w-7xl space-y-5 p-8"><Skeleton className="h-28 rounded-xl" /><div className="grid gap-5 lg:grid-cols-[1fr_340px]"><div className="space-y-5"><Skeleton className="h-72 rounded-xl" /><Skeleton className="h-96 rounded-xl" /></div><Skeleton className="h-72 rounded-xl" /></div></div>;
}
