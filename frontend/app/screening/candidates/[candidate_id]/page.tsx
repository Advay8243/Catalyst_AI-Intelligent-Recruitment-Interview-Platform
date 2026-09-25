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
  Trash2,
  UserRound,
  XCircle,
} from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { EmailComposer } from "@/components/email-composer";
import { EmptyState } from "@/components/empty-state";
import { Badge, Button, Dialog, DialogContent, Progress, Skeleton } from "@/components/ui";
import {
  correctResumeParse,
  getCandidateReview,
  recordDecision,
  removeCandidateApplication,
  resumeDownloadUrl,
} from "@/lib/api";
import type { Candidate, CandidateReview, Decision, EmailHistoryItem, EmailType } from "@/lib/types";
import {
  formatAiRecommendation,
  friendlyErrorMessage,
  initials,
  scoreTextClass,
  scoreTone,
} from "@/lib/utils";

type DetailTab = "overview" | "match" | "screening" | "decision" | "history";

export default function CandidateReviewPage() {
  const { candidate_id: candidateId } = useParams<{ candidate_id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const jobId = searchParams.get("job_id") ?? undefined;
  const screeningHref = jobId
    ? `/screening?job_id=${encodeURIComponent(jobId)}`
    : "/screening";
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
  const [editingParse, setEditingParse] = useState(false);
  const [savingParse, setSavingParse] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [tab, setTab] = useState<DetailTab>("overview");
  const [parseForm, setParseForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    skills: "",
    years_experience: "",
    education: "",
    certifications: "",
    projects: "",
    employment_history: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setReview(await getCandidateReview(candidateId, jobId));
    } catch (caught) {
      setError(friendlyErrorMessage(caught, "Unable to load candidate review."));
    } finally {
      setLoading(false);
    }
  }, [candidateId, jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!review) return;
    const parsed = review.resume.parsed_data;
    setParseForm({
      full_name: review.candidate.name,
      email: review.candidate.email,
      phone: review.candidate.phone ?? "",
      skills: (parsed.skills ?? []).join(", "),
      years_experience: String(parsed.years_experience ?? ""),
      education: (parsed.education ?? []).join(", "),
      certifications: (parsed.certifications ?? []).join(", "),
      projects: (parsed.projects ?? []).join("\n"),
      employment_history: (parsed.employment_history ?? []).join("\n"),
    });
  }, [review]);

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

  async function saveParseCorrections() {
    if (!review) return;
    setSavingParse(true);
    setError("");
    try {
      const split = (value: string) =>
        value
          .split(/[,\n]/)
          .map((item) => item.trim())
          .filter(Boolean);
      await correctResumeParse(review.candidate.id, review.job.id, {
        full_name: parseForm.full_name.trim() || undefined,
        email: parseForm.email.trim() || undefined,
        phone: parseForm.phone.trim() || undefined,
        skills: split(parseForm.skills),
        years_experience: Number(parseForm.years_experience) || 0,
        education: split(parseForm.education),
        certifications: split(parseForm.certifications),
        projects: split(parseForm.projects),
        employment_history: split(parseForm.employment_history),
      });
      setEditingParse(false);
      setNotice("Parsed resume corrected. Matching scores were refreshed.");
      await load();
    } catch (caught) {
      setError(friendlyErrorMessage(caught, "Unable to save parse corrections."));
    } finally {
      setSavingParse(false);
    }
  }

  async function removeResume() {
    if (!review) return;
    if (!confirm("Remove this resume application so it can be re-uploaded? Screening, decisions, and emails for this job will also be cleared.")) {
      return;
    }
    setRemoving(true);
    setError("");
    try {
      await removeCandidateApplication(review.job.id, review.candidate.id);
      setNotice("Resume removed. You can re-upload from Candidate Screening.");
      router.push(screeningHref);
    } catch (caught) {
      setError(friendlyErrorMessage(caught, "Unable to remove resume."));
    } finally {
      setRemoving(false);
    }
  }

  if (loading) return <ReviewSkeleton />;
  if (!review) {
    return (
      <main className="mx-auto max-w-3xl p-8">
        <div className="rounded-xl border bg-white p-10 text-center shadow-panel">
          <h1 className="font-semibold">Unable to load candidate</h1>
          <p className="mt-2 text-sm text-[#667085]">{error}</p>
          <Button className="mt-5" onClick={() => router.push(screeningHref)}>
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
          <button onClick={() => router.push(screeningHref)} className="mb-3 flex items-center gap-2 text-sm font-semibold text-[#667085] hover:text-primary">
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
              <Button variant="danger" disabled={removing} onClick={() => void removeResume()}>
                <Trash2 className="size-4" />{removing ? "Removing…" : "Remove resume"}
              </Button>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {([
              ["overview", "Overview"],
              ["match", "Resume Match"],
              ["screening", "HR Screening"],
              ["decision", "Decision & Email"],
              ["history", "History"],
            ] as const).map(([id, label]) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`rounded-full px-3 py-1.5 text-sm font-semibold ${tab === id ? "bg-[#fff0f7] text-primary" : "text-[#667085] hover:bg-muted"}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-5 p-5 sm:p-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          {(tab === "overview" || tab === "match") && (
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
          )}

          {tab === "overview" && (
          <Card title="JD Summary" icon={<BriefcaseBusiness />}>
            <ul className="space-y-2 text-sm text-[#475467]">
              {(review.job.summary_bullets?.length
                ? review.job.summary_bullets
                : review.job.responsibilities.slice(0, 8)
              ).map((bullet) => (
                <li key={bullet} className="flex gap-2"><span className="text-primary">•</span><span>{bullet}</span></li>
              ))}
            </ul>
            <div className="mt-5 grid gap-5 md:grid-cols-2">
              <RequirementList title="Required skills" items={review.job.required_skills} badges />
              <RequirementList title="Preferred skills" items={review.job.preferred_skills} badges />
            </div>
            <p className="mt-5 text-sm"><strong>Experience requirement:</strong> {review.job.experience_requirements}</p>
          </Card>
          )}

          {(tab === "overview" || tab === "match") && (
          <Card title="Resume analysis" icon={<FileText />}>
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <Badge tone="purple">AI-generated analysis</Badge>
              {review.resume.parse_corrected_by && (
                <Badge tone="amber">Corrected by {review.resume.parse_corrected_by}</Badge>
              )}
              <Button variant="secondary" size="sm" className="ml-auto" onClick={() => setEditingParse((value) => !value)}>
                {editingParse ? "Cancel edit" : "Correct parsed data"}
              </Button>
            </div>
            {editingParse ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {([
                  ["full_name", "Name"],
                  ["email", "Email"],
                  ["phone", "Phone"],
                  ["years_experience", "Years experience"],
                  ["skills", "Skills"],
                  ["education", "Education"],
                  ["certifications", "Certifications"],
                  ["projects", "Projects"],
                  ["employment_history", "Employment history"],
                ] as const).map(([key, label]) => (
                  <label key={key} className={`block text-sm ${key === "projects" || key === "employment_history" || key === "skills" ? "sm:col-span-2" : ""}`}>
                    <span className="mb-1 block font-medium">{label}</span>
                    {key === "projects" || key === "employment_history" || key === "skills" || key === "education" || key === "certifications" ? (
                      <textarea rows={3} value={parseForm[key]} onChange={(event) => setParseForm((current) => ({ ...current, [key]: event.target.value }))} className="w-full rounded-lg border p-3 text-sm" />
                    ) : (
                      <input value={parseForm[key]} onChange={(event) => setParseForm((current) => ({ ...current, [key]: event.target.value }))} className="h-10 w-full rounded-lg border px-3 text-sm" />
                    )}
                  </label>
                ))}
                <div className="sm:col-span-2">
                  <Button disabled={savingParse} onClick={() => void saveParseCorrections()}>{savingParse ? "Saving…" : "Save corrections & re-match"}</Button>
                </div>
              </div>
            ) : (
              <div className="grid gap-5 md:grid-cols-[180px_1fr]">
                <ScoreCircle score={review.resume_analysis.overall_score} label="AI Calculated" />
                <div>
                  <RequirementList title="Extracted skills" items={review.resume.parsed_data.skills ?? []} badges />
                  <p className="mt-4 text-sm text-[#475467]"><strong>Experience:</strong> {review.resume.parsed_data.years_experience ?? "Not extracted"} years</p>
                  <RequirementList title="Education" items={review.resume.parsed_data.education ?? []} />
                  <RequirementList title="Certifications" items={review.resume.parsed_data.certifications ?? []} />
                  <RequirementList title="Projects" items={review.resume.parsed_data.projects ?? []} />
                  <RequirementList title="Employment history" items={review.resume.parsed_data.employment_history ?? []} />
                  <RequirementList title="Relevant highlights" items={review.resume.parsed_data.highlights ?? []} />
                </div>
              </div>
            )}
            {!editingParse && (
              <>
                <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <Metric label="Required skills" score={Number((review.resume_analysis.scoring?.match_details as { required_skill_score?: number } | undefined)?.required_skill_score ?? (review.resume_analysis.scoring?.skills as { score?: number } | undefined)?.score ?? 0)} />
                  <Metric label="Preferred skills" score={Number((review.resume_analysis.scoring?.match_details as { preferred_skill_score?: number } | undefined)?.preferred_skill_score ?? 0)} />
                  <Metric label="Experience" score={Number((review.resume_analysis.scoring?.experience as { score?: number } | undefined)?.score ?? 0)} />
                  <Metric label="Responsibilities" score={Number((review.resume_analysis.scoring?.match_details as { responsibilities_score?: number } | undefined)?.responsibilities_score ?? 0)} />
                  <Metric label="Education / certs" score={Number((review.resume_analysis.scoring?.match_details as { education_certification_score?: number } | undefined)?.education_certification_score ?? (review.resume_analysis.scoring?.education as { score?: number } | undefined)?.score ?? 0)} />
                </div>
                <div className="mt-5 grid gap-4 md:grid-cols-2">
                  <EvidenceList title="Matched skills" items={(review.resume_analysis.evidence?.matched_skills as string[] | undefined) ?? []} tone="green" />
                  <EvidenceList title="Missing skills" items={(review.resume_analysis.evidence?.missing_skills as string[] | undefined) ?? []} tone="amber" />
                </div>
                <div className="mt-5 rounded-xl bg-[#f8f9fb] p-4 text-sm text-[#475467]">
                  <p className="mb-3 font-semibold text-[#101828]">AI Suggestion — Why Fits / Not Fits</p>
                  {(review.resume_analysis.fit_points?.length || review.resume_analysis.gap_points?.length) ? (
                    <div className="space-y-3">
                      {!!review.resume_analysis.fit_points?.length && (
                        <div>
                          <p className="mb-1 font-semibold text-green-800">Fits</p>
                          <ul className="list-disc space-y-1 pl-5">
                            {review.resume_analysis.fit_points.map((point) => <li key={point}>{point}</li>)}
                          </ul>
                        </div>
                      )}
                      {!!review.resume_analysis.gap_points?.length && (
                        <div>
                          <p className="mb-1 font-semibold text-amber-800">Does Not Fit / Gaps</p>
                          <ul className="list-disc space-y-1 pl-5">
                            {review.resume_analysis.gap_points.map((point) => <li key={point}>{point}</li>)}
                          </ul>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="leading-6">{review.resume_analysis.explanation}</p>
                  )}
                </div>
              </>
            )}
          </Card>
          )}

          {(tab === "overview" || tab === "screening") && (
          <Card title="HR screening review" icon={<Sparkles />}>
            {!screening ? (
              <EmptyState
                icon={<Phone className="size-6" />}
                title="No HR calls yet"
                description="Complete the recruiter screening call to populate transcript analysis and HR scores."
                action={
                  <Button onClick={() => router.push(`/screening/call/${encodeURIComponent(review.candidate.id)}?job_id=${encodeURIComponent(review.job.id)}`)}>
                    Start HR call
                  </Button>
                }
              />
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
                {review.call_session?.transcript?.length ? (
                  <div className="mt-6">
                    <h3 className="mb-3 font-semibold">Call transcript</h3>
                    <div className="max-h-72 space-y-3 overflow-y-auto rounded-xl border p-4">
                      {review.call_session.transcript.map((entry) => (
                        <div key={entry.id} className="text-sm">
                          <p className="text-xs font-bold uppercase tracking-wide text-[#98a2b3]">{entry.speaker}</p>
                          <p className="mt-1 text-[#475467]">{entry.text}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  <EvidenceList title="Strengths" items={screening.strengths} tone="green" />
                  <EvidenceList title="Concerns" items={screening.concerns} tone="amber" />
                </div>
              </>
            )}
          </Card>
          )}

          {(tab === "overview" || tab === "history") && (
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
            ) : (
              <EmptyState icon={<History className="size-6" />} title="No audit history" description="Timeline events appear as resumes are uploaded, scored, screened, and decided." />
            )}
          </Card>
          )}

          {(tab === "overview" || tab === "decision" || tab === "history") && (
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
            ) : (
              <EmptyState icon={<CheckCircle2 className="size-6" />} title="No decisions yet" description="Record an Accept, Reject, or Further Review decision after HR screening." />
            )}
          </Card>
          )}

          {(tab === "overview" || tab === "decision" || tab === "history") && (
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
            ) : (
              <EmptyState icon={<Mail className="size-6" />} title="No emails yet" description="Acceptance, rejection, and interviewer notifications appear here after sending." />
            )}
          </Card>
          )}
        </div>

        <aside className="space-y-5">
          <Card title="Review status" icon={<Sparkles />}>
            <Badge tone="green" className="mb-4">Human decision</Badge>
            <dl className="space-y-4">
              <CompactInfo label="Resume" value={review.application.resume_status} />
              <CompactInfo label="HR screening" value={review.application.screening_status} />
              <CompactInfo label="AI recommendation" value={formatAiRecommendation(screening?.recommendation)} />
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
  const tone = scoreTone(score);
  const ring =
    tone === "emerald" || tone === "green"
      ? "border-green-300"
      : tone === "red"
        ? "border-red-300"
        : tone === "orange"
          ? "border-orange-300"
          : "border-amber-300";
  return (
    <div className="flex items-center gap-3">
      <span className={`flex size-20 shrink-0 items-center justify-center rounded-full border-[7px] text-xl font-bold ${ring} ${scoreTextClass(score)}`}>
        {score}%
      </span>
      <span className="text-xs font-medium text-[#667085]">{label}</span>
    </div>
  );
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
