"use client";

import { BriefcaseBusiness, Download, ExternalLink, Mail, MapPin, Phone, UserRound } from "lucide-react";
import type { Candidate } from "@/lib/types";
import { Badge, Button, Dialog, DialogContent, Progress } from "@/components/ui";
import { initials, scoreBandLabel, scoreTextClass, scoreTone } from "@/lib/utils";

export function ScorePill({ score }: { score: number | null }) {
  if (score == null) return <span className="text-sm text-[#98a2b3]">Pending</span>;
  return (
    <span className="inline-flex flex-col items-center gap-0.5">
      <Badge tone={scoreTone(score)} className="min-w-12 justify-center py-1">{Math.round(score)}%</Badge>
      <span className="text-[10px] font-medium text-[#98a2b3]">{scoreBandLabel(score)}</span>
    </span>
  );
}

function Drawer({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={title} description={description} className="left-auto right-0 top-0 h-screen max-h-none w-full max-w-md translate-x-0 translate-y-0 rounded-none border-y-0 p-0 [&>button]:right-6 [&>button]:top-6">
        {children}
      </DialogContent>
    </Dialog>
  );
}

export function CandidateDrawer({ candidate, open, onOpenChange }: { candidate: Candidate | null; open: boolean; onOpenChange: (open: boolean) => void }) {
  if (!candidate) return null;
  return (
    <Drawer open={open} onOpenChange={onOpenChange} title={candidate.name} description={candidate.currentTitle ?? "Candidate profile"}>
      <div className="mt-6 border-y bg-[#fafbfc] p-6">
        <div className="flex items-center gap-4">
          <span className="flex size-14 items-center justify-center rounded-full bg-[#ffe0ef] text-lg font-bold text-[#b00665]">{initials(candidate.name)}</span>
          <div>
            <p className="font-semibold text-[#101828]">{candidate.name}</p>
            <p className="text-sm text-[#667085]">{candidate.email}</p>
          </div>
        </div>
      </div>
      <div className="space-y-6 p-6">
        <section>
          <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-[#98a2b3]">Contact & experience</h3>
          <div className="space-y-3 text-sm text-[#475467]">
            <p className="flex items-center gap-3"><Mail className="size-4 text-[#98a2b3]" />{candidate.email || "Not provided"}</p>
            <p className="flex items-center gap-3"><Phone className="size-4 text-[#98a2b3]" />{candidate.phone || "Not provided"}</p>
            <p className="flex items-center gap-3"><MapPin className="size-4 text-[#98a2b3]" />{candidate.location || "Not provided"}</p>
            <p className="flex items-center gap-3"><BriefcaseBusiness className="size-4 text-[#98a2b3]" />{candidate.experienceYears ? `${candidate.experienceYears} years experience` : "Experience not provided"}</p>
          </div>
        </section>
        <section>
          <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-[#98a2b3]">Matched role</h3>
          <div className="rounded-xl border p-4">
            <p className="font-semibold">{candidate.jobTitle ?? "Selected job"}</p>
            <div className="mt-3 flex items-center justify-between"><span className="text-sm text-[#667085]">JD match</span><ScorePill score={candidate.jdScore} /></div>
          </div>
        </section>
        <section>
          <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-[#98a2b3]">Skills</h3>
          <div className="flex flex-wrap gap-2">{candidate.skills?.length ? candidate.skills.map((skill) => <Badge key={skill} tone="purple">{skill}</Badge>) : <span className="text-sm text-[#98a2b3]">Skills analysis pending</span>}</div>
        </section>
        {candidate.resumeUrl ? <a href={candidate.resumeUrl} target="_blank" rel="noreferrer"><Button variant="secondary" className="w-full"><Download className="size-4" />View resume<ExternalLink className="size-3" /></Button></a> : <Button variant="secondary" className="w-full" disabled><Download className="size-4" />Resume unavailable</Button>}
      </div>
    </Drawer>
  );
}

export function ScoreDrawer({
  candidate,
  type,
  open,
  onOpenChange,
}: {
  candidate: Candidate | null;
  type: "jd" | "hr";
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!candidate) return null;
  const score = type === "jd" ? candidate.jdScore : candidate.hrScore;
  const scoreColor = score == null ? "text-[#101828]" : scoreTextClass(score);
  const breakdown = candidate.scoreBreakdown;
  const metrics = [
    ["Required skills", breakdown?.required_skills ?? breakdown?.skills],
    ["Preferred skills", breakdown?.preferred_skills],
    ["Experience fit", breakdown?.experience],
    ["Responsibilities", breakdown?.responsibilities],
    ["Education / certifications", breakdown?.education_certification ?? breakdown?.education],
    ["Role relevance", breakdown?.relevance],
  ] as const;
  return (
    <Drawer open={open} onOpenChange={onOpenChange} title={type === "jd" ? "JD → Resume Score" : "HR Screening Analysis"} description={`${candidate.name} · ${candidate.jobTitle ?? "Selected job"}`}>
      <div className="mt-6 border-y bg-[#fafbfc] p-6">
        <p className="text-sm text-[#667085]">Overall score</p>
        <div className="mt-2 flex items-end gap-2">
          <span className={`text-4xl font-bold ${scoreColor}`}>
            {score == null ? "—" : Math.round(score)}
          </span>
          {score != null && <span className="mb-1 text-lg text-[#98a2b3]">/ 100</span>}
        </div>
        {score != null && <p className="mt-1 text-xs font-medium text-[#667085]">Band {scoreBandLabel(score)}</p>}
      </div>
      <div className="space-y-6 p-6">
        {type === "hr" ? (
          candidate.hrAnalysis ? <div className="rounded-xl border bg-white p-4 text-sm leading-6 text-[#475467]">{candidate.hrAnalysis}</div> : <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">HR screening analysis is not available yet. It will appear after the recruiter screening call is reviewed.</div>
        ) : (
          <>
            <section className="space-y-5">
              {metrics.map(([label, value]) => (
                <div key={label}>
                  <div className="mb-2 flex justify-between text-sm"><span className="text-[#475467]">{label}</span><span className="font-semibold">{value == null ? "Pending" : `${Math.round(value)}%`}</span></div>
                  <Progress value={value ?? 0} />
                </div>
              ))}
            </section>
            {(breakdown?.matched_skills?.length || breakdown?.missing_skills?.length) ? (
              <section className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-green-200 bg-green-50 p-4">
                  <h3 className="text-sm font-semibold text-green-900">Matched skills</h3>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {(breakdown?.matched_skills ?? []).length
                      ? breakdown?.matched_skills?.map((skill) => <Badge key={skill} tone="green">{skill}</Badge>)
                      : <span className="text-sm text-[#667085]">None</span>}
                  </div>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <h3 className="text-sm font-semibold text-amber-900">Missing skills</h3>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {(breakdown?.missing_skills ?? []).length
                      ? breakdown?.missing_skills?.map((skill) => <Badge key={skill} tone="amber">{skill}</Badge>)
                      : <span className="text-sm text-[#667085]">None</span>}
                  </div>
                </div>
              </section>
            ) : null}
            <section className="rounded-xl bg-[#f8f9fb] p-4">
              <h3 className="mb-2 text-sm font-semibold">Why Candidate Fits</h3>
              <p className="text-sm leading-6 text-[#667085]">{breakdown?.summary ?? candidate.fitReason}</p>
            </section>
          </>
        )}
        <div className="flex items-start gap-3 rounded-xl bg-[#fff0f7] p-4 text-sm text-[#a1085d]"><UserRound className="mt-0.5 size-4 shrink-0" /><p>AI scores support recruiter decisions and should be reviewed alongside the full candidate profile.</p></div>
      </div>
    </Drawer>
  );
}
