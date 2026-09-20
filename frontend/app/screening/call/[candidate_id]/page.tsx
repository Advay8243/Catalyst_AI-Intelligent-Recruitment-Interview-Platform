"use client";

import {
  ArrowLeft,
  BriefcaseBusiness,
  CheckCircle2,
  CircleDot,
  Loader2,
  Mail,
  MessageSquareText,
  Mic,
  Phone,
  PhoneOff,
  Sparkles,
} from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Badge, Button, Input, Skeleton } from "@/components/ui";
import {
  addTranscriptEntry,
  completeCall,
  createCallSession,
  startCall,
} from "@/lib/api";
import type {
  CallSession,
  ScreeningAnalysis,
  TranscriptEntry,
} from "@/lib/types";
import { initials } from "@/lib/utils";

const statusLabel: Record<string, string> = {
  not_started: "Not Started",
  connecting: "Connecting",
  connected: "Connected",
  completed: "Completed",
  failed: "Failed",
};

export default function HRScreeningCallPage() {
  const { candidate_id: candidateId } = useParams<{ candidate_id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [session, setSession] = useState<CallSession | null>(null);
  const [analysis, setAnalysis] = useState<ScreeningAnalysis | null>(null);
  const [speaker, setSpeaker] = useState<"hr" | "candidate">("candidate");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    createCallSession(candidateId, searchParams.get("job_id") ?? undefined)
      .then(setSession)
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "Unable to prepare this call."),
      )
      .finally(() => setLoading(false));
  }, [candidateId, searchParams]);

  const currentQuestion = useMemo(() => {
    if (!session) return null;
    const candidateResponses = session.transcript.filter(
      (entry) => entry.speaker === "candidate",
    ).length;
    return session.questions[Math.min(candidateResponses, session.questions.length - 1)];
  }, [session]);

  async function handleStart() {
    if (!session) return;
    setAction("start");
    setError("");
    try {
      setSession({ ...session, status: "connecting" });
      setSession(await startCall(session.id));
    } catch (caught) {
      setSession(session);
      setError(caught instanceof Error ? caught.message : "Unable to start the call.");
    } finally {
      setAction("");
    }
  }

  async function addEntry(entrySpeaker = speaker, entryText = text) {
    if (!session || !entryText.trim()) return;
    setAction("transcript");
    setError("");
    try {
      const entry = await addTranscriptEntry(
        session.id,
        entrySpeaker,
        entryText.trim(),
      );
      setSession({
        ...session,
        transcript: [...session.transcript, entry],
      });
      setText("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save transcript.");
    } finally {
      setAction("");
    }
  }

  async function handleComplete() {
    if (!session) return;
    setAction("complete");
    setError("");
    try {
      const result = await completeCall(session.id);
      setSession(result.session);
      setAnalysis(result.analysis);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to complete analysis.");
    } finally {
      setAction("");
    }
  }

  if (loading) return <CallPageSkeleton />;

  if (error && !session) {
    return (
      <main className="mx-auto max-w-3xl p-8">
        <div className="rounded-xl border bg-white p-10 text-center shadow-panel">
          <h1 className="text-lg font-semibold">Unable to prepare HR screening call</h1>
          <p className="mt-2 text-sm text-[#667085]">{error}</p>
          <Button className="mt-5" onClick={() => router.push("/screening")}>
            <ArrowLeft className="size-4" /> Back to Candidates
          </Button>
        </div>
      </main>
    );
  }

  if (!session) return null;
  const candidate = session.candidate;
  const active = session.status === "connected" || session.status === "connecting";

  return (
    <div className="min-h-screen bg-[#f7f8fa]">
      <header className="border-b bg-white px-5 py-5 sm:px-8">
        <div className="mx-auto max-w-[1440px]">
          <button
            onClick={() => router.push("/screening")}
            className="mb-3 flex items-center gap-2 text-sm font-semibold text-[#667085] hover:text-primary"
          >
            <ArrowLeft className="size-4" /> Back to Candidates
          </button>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="text-2xl font-bold text-[#101828]">HR Screening Call</h1>
              <p className="mt-1 text-sm text-[#667085]">
                {candidate.candidate_name} · {candidate.job_title}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="rounded-lg border px-3 py-2 text-sm">
                <span className="text-[#667085]">JD → Resume Score </span>
                <strong>{candidate.jd_resume_score}%</strong>
              </div>
              <Badge tone={session.status === "completed" ? "green" : active ? "purple" : "amber"}>
                <CircleDot className="mr-1 size-3" />
                {statusLabel[session.status] ?? session.status}
              </Badge>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1440px] gap-5 p-5 sm:p-8 xl:grid-cols-[320px_minmax(0,1fr)_340px]">
        <aside className="space-y-5">
          <section className="rounded-xl border bg-white p-5 shadow-panel">
            <div className="flex items-center gap-3">
              <span className="flex size-11 items-center justify-center rounded-full bg-[#fff0f7] text-sm font-bold text-[#b00665]">
                {initials(candidate.candidate_name)}
              </span>
              <div className="min-w-0">
                <h2 className="truncate font-semibold">{candidate.candidate_name}</h2>
                <p className="truncate text-xs text-[#667085]">{candidate.job_title}</p>
              </div>
            </div>
            <dl className="mt-5 space-y-4">
              <Info icon={<BriefcaseBusiness />} label="Applied Position" value={candidate.job_title} />
              <Info icon={<Mail />} label="Email" value={candidate.email} />
              <Info icon={<Phone />} label="Phone" value={candidate.phone ?? "Not provided"} />
              <Info icon={<Sparkles />} label="JD → Resume Score" value={`${candidate.jd_resume_score}%`} />
            </dl>
            <div className="mt-5 border-t pt-4">
              <p className="text-xs font-bold uppercase tracking-wide text-[#98a2b3]">Key matched skills</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {candidate.key_matched_skills.length ? candidate.key_matched_skills.map((skill) => (
                  <Badge key={skill} tone="purple">{skill}</Badge>
                )) : <span className="text-xs text-[#667085]">No matched skills available.</span>}
              </div>
            </div>
          </section>

          <section className="rounded-xl border bg-white p-5 shadow-panel">
            <h2 className="font-semibold">Call controls</h2>
            <p className="mt-1 text-xs leading-5 text-[#667085]">
              Mock provider mode simulates connectivity; no external call is placed.
            </p>
            {session.status === "not_started" ? (
              <Button className="mt-4 w-full" onClick={handleStart} disabled={!candidate.phone || action === "start"}>
                {action === "start" ? <Loader2 className="size-4 animate-spin" /> : <Phone className="size-4" />}
                Start Call
              </Button>
            ) : active ? (
              <Button className="mt-4 w-full" variant="danger" onClick={handleComplete} disabled={action === "complete"}>
                {action === "complete" ? <Loader2 className="size-4 animate-spin" /> : <PhoneOff className="size-4" />}
                End & Analyze
              </Button>
            ) : (
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-green-50 p-3 text-sm font-medium text-green-800">
                <CheckCircle2 className="size-4" /> Screening completed
              </div>
            )}
          </section>
        </aside>

        <section className="flex min-h-[620px] flex-col overflow-hidden rounded-xl border bg-white shadow-panel">
          <div className="border-b px-5 py-4">
            <h2 className="flex items-center gap-2 font-semibold">
              <MessageSquareText className="size-4 text-primary" /> Live Transcript
            </h2>
            <p className="mt-1 text-xs text-[#667085]">Capture only job-relevant answers. Protected characteristics are not analyzed.</p>
          </div>
          <div aria-live="polite" className="flex-1 space-y-4 overflow-y-auto p-5">
            {!session.transcript.length && (
              <div className="flex h-full min-h-72 flex-col items-center justify-center text-center">
                <Mic className="mb-3 size-8 text-[#98a2b3]" />
                <p className="font-medium">Transcript will appear here</p>
                <p className="mt-1 max-w-sm text-sm text-[#667085]">
                  Start the call, ask a suggested question, and capture the candidate response.
                </p>
              </div>
            )}
            {session.transcript.map((entry) => <TranscriptBubble key={entry.id} entry={entry} />)}
          </div>
          <div className="border-t bg-[#fcfcfd] p-4">
            <div className="mb-3 flex rounded-lg border bg-white p-1">
              {(["candidate", "hr"] as const).map((value) => (
                <button
                  key={value}
                  onClick={() => setSpeaker(value)}
                  className={`flex-1 rounded-md px-3 py-1.5 text-xs font-semibold capitalize ${speaker === value ? "bg-primary text-white" : "text-[#667085]"}`}
                >
                  {value} speaking
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                value={text}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void addEntry();
                }}
                disabled={!active}
                placeholder={active ? "Type the live transcript…" : "Start the call to capture transcript"}
                aria-label="Transcript text"
              />
              <Button onClick={() => void addEntry()} disabled={!active || !text.trim() || action === "transcript"}>
                {action === "transcript" ? <Loader2 className="size-4 animate-spin" /> : "Add"}
              </Button>
            </div>
          </div>
        </section>

        <aside className="space-y-5">
          {!analysis ? (
            <section className="rounded-xl border bg-white p-5 shadow-panel">
              <h2 className="font-semibold">AI-assisted questions</h2>
              <p className="mt-1 text-xs leading-5 text-[#667085]">
                Use these consistent questions to collect scoreable evidence.
              </p>
              <div className="mt-4 space-y-3">
                {session.questions.map((question, index) => (
                  <button
                    key={question.id}
                    disabled={!active}
                    onClick={() => void addEntry("hr", question.text)}
                    className={`w-full rounded-lg border p-3 text-left text-sm transition hover:border-primary ${currentQuestion?.id === question.id ? "border-primary bg-[#fff7fb]" : "bg-white"} disabled:cursor-not-allowed disabled:opacity-60`}
                  >
                    <span className="mb-1 block text-[10px] font-bold uppercase tracking-wide text-[#98a2b3]">
                      Question {index + 1} · {question.category}
                    </span>
                    {question.text}
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <AnalysisPanel analysis={analysis} />
          )}
        </aside>
      </main>

      {error && session && (
        <div role="alert" className="fixed bottom-5 right-5 max-w-md rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 shadow-xl">
          {error}
        </div>
      )}
    </div>
  );
}

function Info({ icon, label, value }: { icon: React.ReactElement; label: string; value: string }) {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 text-[#98a2b3] [&>svg]:size-4">{icon}</span>
      <div className="min-w-0">
        <dt className="text-xs text-[#98a2b3]">{label}</dt>
        <dd className="truncate text-sm font-medium text-[#344054]">{value}</dd>
      </div>
    </div>
  );
}

function TranscriptBubble({ entry }: { entry: TranscriptEntry }) {
  const candidate = entry.speaker === "candidate";
  return (
    <div className={`flex ${candidate ? "justify-start" : "justify-end"}`}>
      <div className={`max-w-[82%] rounded-xl px-4 py-3 ${candidate ? "bg-[#f2f4f7]" : "bg-[#fff0f7]"}`}>
        <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-[#667085]">
          {candidate ? "Candidate" : "HR"}
        </p>
        <p className="text-sm leading-6 text-[#344054]">{entry.text}</p>
      </div>
    </div>
  );
}

function AnalysisPanel({ analysis }: { analysis: ScreeningAnalysis }) {
  return (
    <section className="rounded-xl border bg-white p-5 shadow-panel">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold">HR Screening Score</h2>
          <p className="mt-1 text-xs capitalize text-[#667085]">{analysis.recommendation.replaceAll("_", " ")}</p>
        </div>
        <span className="text-3xl font-bold text-primary">{analysis.overall_score}%</span>
      </div>
      <div className="mt-5 space-y-3">
        {[
          ["Experience", analysis.experience_score],
          ["Skills", analysis.skills_score],
          ["Communication", analysis.communication_score],
          ["Motivation", analysis.motivation_score],
          ["Availability", analysis.availability_score],
        ].map(([label, score]) => (
          <div key={String(label)}>
            <div className="mb-1 flex justify-between text-xs"><span>{label}</span><strong>{score}%</strong></div>
            <div className="h-1.5 rounded-full bg-[#eaecf0]"><div className="h-full rounded-full bg-primary" style={{ width: `${score}%` }} /></div>
          </div>
        ))}
      </div>
      <p className="mt-5 text-sm leading-6 text-[#475467]">{analysis.summary}</p>
      <Button className="mt-5 w-full" onClick={() => window.location.assign("/screening")}>
        <ArrowLeft className="size-4" /> Return to Candidates
      </Button>
    </section>
  );
}

function CallPageSkeleton() {
  return (
    <div className="mx-auto max-w-[1440px] space-y-5 p-8">
      <Skeleton className="h-20 rounded-xl" />
      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)_340px]">
        <Skeleton className="h-[500px] rounded-xl" />
        <Skeleton className="h-[620px] rounded-xl" />
        <Skeleton className="h-[500px] rounded-xl" />
      </div>
    </div>
  );
}
