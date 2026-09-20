import type {
  CallSession,
  Candidate,
  CandidateQuery,
  CandidateReview,
  Decision,
  EmailDraft,
  EmailHistoryItem,
  EmailType,
  Job,
  PaginatedCandidates,
  ScreeningAnalysis,
  TranscriptEntry,
} from "@/lib/types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export function resumeDownloadUrl(resumeId: string) {
  return `${API_URL}/resumes/${encodeURIComponent(resumeId)}/download`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.message ?? data?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

async function hrRequest<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`/api/hr${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail ?? `HR action failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

function normalizeCandidate(raw: Record<string, unknown>): Candidate {
  return {
    id: String(raw.id ?? raw.candidate_id ?? ""),
    name: String(raw.name ?? raw.full_name ?? "Unknown candidate"),
    email: String(raw.email ?? ""),
    phone: raw.phone ? String(raw.phone) : undefined,
    location: raw.location ? String(raw.location) : undefined,
    currentTitle: raw.currentTitle ? String(raw.currentTitle) : raw.current_title ? String(raw.current_title) : undefined,
    experienceYears: Number(raw.experienceYears ?? raw.experience_years) || undefined,
    jdScore: raw.jdScore != null ? Number(raw.jdScore) : raw.jd_score != null ? Number(raw.jd_score) : null,
    hrScore: raw.hrScore != null ? Number(raw.hrScore) : raw.hr_score != null ? Number(raw.hr_score) : null,
    fitReason: String(raw.fitReason ?? raw.fit_reason ?? raw.why_candidate_fits ?? "Analysis pending"),
    status: raw.status ? String(raw.status) : raw.application_status ? String(raw.application_status) : undefined,
    callStatus: raw.callStatus ? String(raw.callStatus) : raw.call_status ? String(raw.call_status) : undefined,
    jobId: raw.jobId ? String(raw.jobId) : raw.job_id ? String(raw.job_id) : undefined,
    jobTitle: raw.jobTitle ? String(raw.jobTitle) : raw.job_title ? String(raw.job_title) : undefined,
    resumeUrl: raw.resumeUrl ? String(raw.resumeUrl) : raw.resume_url ? String(raw.resume_url) : undefined,
    skills: Array.isArray(raw.skills) ? raw.skills.map(String) : [],
    scoreBreakdown: (raw.scoreBreakdown ?? raw.score_breakdown) as Candidate["scoreBreakdown"],
    hrAnalysis: raw.hrAnalysis ? String(raw.hrAnalysis) : raw.hr_analysis ? String(raw.hr_analysis) : undefined,
    resumeStatus: raw.resumeStatus ? String(raw.resumeStatus) : raw.resume_status ? String(raw.resume_status) : undefined,
    screeningStatus: raw.screeningStatus ? String(raw.screeningStatus) : raw.screening_status ? String(raw.screening_status) : undefined,
    screeningRecommendation: raw.screeningRecommendation ? String(raw.screeningRecommendation) : raw.screening_recommendation ? String(raw.screening_recommendation) : undefined,
    appliedAt: raw.appliedAt ? String(raw.appliedAt) : raw.applied_at ? String(raw.applied_at) : undefined,
    screenedAt: raw.screenedAt ? String(raw.screenedAt) : raw.screened_at ? String(raw.screened_at) : undefined,
    decisionAt: raw.decisionAt ? String(raw.decisionAt) : raw.decision_at ? String(raw.decision_at) : undefined,
    decisionStatus: (raw.decisionStatus ?? raw.decision_status ?? "pending") as Candidate["decisionStatus"],
    emailStatus: raw.emailStatus ? String(raw.emailStatus) : raw.email_status ? String(raw.email_status) : "Not Sent",
    currentStage: raw.currentStage ? String(raw.currentStage) : raw.current_stage ? String(raw.current_stage) : undefined,
  };
}

export async function getCandidates(query: CandidateQuery): Promise<PaginatedCandidates> {
  if (!query.jobId) {
    return { items: [], total: 0, page: query.page, pageSize: query.pageSize };
  }
  const params = new URLSearchParams();
  params.set("page", String(query.page));
  params.set("page_size", String(query.pageSize));
  if (query.search) params.set("search", query.search);
  if (query.status) params.set("status", query.status);
  if (query.minScore) params.set("min_score", query.minScore);
  const sortMap: Record<string, string> = {
    jdScore: "score",
    hrScore: "hr_score",
    createdAt: "created_at",
    name: "name",
  };
  params.set("sort", sortMap[query.sortBy ?? "jdScore"] ?? "score");
  params.set("order", query.sortOrder ?? "desc");
  const raw = await request<Record<string, unknown>>(
    `/jobs/${encodeURIComponent(query.jobId)}/candidates?${params}`,
  );
  const list = (raw.items ?? raw.results ?? raw.candidates ?? []) as Record<string, unknown>[];
  return {
    items: list.map(normalizeCandidate),
    total: Number(raw.total ?? raw.count ?? list.length),
    page: Number(raw.page ?? query.page),
    pageSize: Number(raw.pageSize ?? raw.page_size ?? query.pageSize),
  };
}

export async function getCandidate(id: string): Promise<Candidate> {
  const raw = await request<Record<string, unknown>>(`/candidates/${encodeURIComponent(id)}`);
  return normalizeCandidate((raw.candidate ?? raw) as Record<string, unknown>);
}

export async function getJobs(): Promise<Job[]> {
  const raw = await request<Job[] | { items?: Job[]; jobs?: Job[] }>("/jobs");
  return Array.isArray(raw) ? raw : raw.items ?? raw.jobs ?? [];
}

function parseErrorDetail(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const detail = (payload as { detail?: unknown; message?: unknown }).detail
    ?? (payload as { message?: unknown }).message;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  return fallback;
}

export function uploadFiles(
  path: string,
  form: FormData,
  onProgress: (percent: number) => void,
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}${path}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onerror = () => reject(new Error("Upload failed. Check your connection and try again."));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText || "{}")); } catch { resolve({}); }
      } else {
        try {
          reject(new Error(parseErrorDetail(JSON.parse(xhr.responseText), `Upload failed (${xhr.status})`)));
        } catch {
          reject(new Error(`Upload failed (${xhr.status})`));
        }
      }
    };
    xhr.send(form);
  });
}

export async function createJobFromDescription(description: string): Promise<Job> {
  return request<Job>("/jobs", {
    method: "POST",
    body: JSON.stringify({ description }),
  });
}

export async function uploadJobDescriptionFile(
  file: File,
  onProgress: (percent: number) => void,
): Promise<Job> {
  const form = new FormData();
  form.append("file", file);
  return uploadFiles("/jobs", form, onProgress) as Promise<Job>;
}

export async function uploadResumeToJob(
  jobId: string,
  file: File,
  onProgress: (percent: number) => void,
): Promise<unknown> {
  const form = new FormData();
  form.append("file", file);
  return uploadFiles(`/jobs/${encodeURIComponent(jobId)}/resume`, form, onProgress);
}

export async function createCallSession(candidateId: string, jobId?: string): Promise<CallSession> {
  return request<CallSession>(`/candidates/${encodeURIComponent(candidateId)}/call-sessions`, {
    method: "POST",
    body: JSON.stringify({ job_id: jobId || null }),
  });
}

export async function startCall(sessionId: string): Promise<CallSession> {
  return request<CallSession>(`/call-sessions/${encodeURIComponent(sessionId)}/start`, {
    method: "POST",
  });
}

export async function addTranscriptEntry(
  sessionId: string,
  speaker: "hr" | "candidate",
  text: string,
): Promise<TranscriptEntry> {
  return request<TranscriptEntry>(
    `/call-sessions/${encodeURIComponent(sessionId)}/transcript`,
    {
      method: "POST",
      body: JSON.stringify({ speaker, text }),
    },
  );
}

export async function completeCall(
  sessionId: string,
): Promise<{ session: CallSession; analysis: ScreeningAnalysis }> {
  return request<{ session: CallSession; analysis: ScreeningAnalysis }>(
    `/call-sessions/${encodeURIComponent(sessionId)}/complete`,
    { method: "POST" },
  );
}

export async function getCandidateReview(
  candidateId: string,
  jobId?: string,
): Promise<CandidateReview> {
  const params = jobId ? `?job_id=${encodeURIComponent(jobId)}` : "";
  return request<CandidateReview>(
    `/candidates/${encodeURIComponent(candidateId)}/review${params}`,
  );
}

export async function recordDecision(
  candidateId: string,
  jobId: string,
  decision: Decision,
  details?: { decisionReason?: string; decisionNotes?: string },
) {
  return hrRequest<{
    application_id: string;
    decision: Decision;
    decision_at: string;
    decision_by?: string;
    status: string;
    previous_status: string;
    new_status: string;
  }>(`/candidates/${encodeURIComponent(candidateId)}/decision`, {
    method: "POST",
    body: JSON.stringify({
      job_id: jobId,
      decision,
      decision_reason: details?.decisionReason || null,
      decision_notes: details?.decisionNotes || null,
    }),
  });
}

export async function generateEmailDraft(
  candidateId: string,
  jobId: string,
  emailType: EmailType,
  recipient?: string,
): Promise<EmailDraft> {
  return hrRequest<EmailDraft>(
    `/candidates/${encodeURIComponent(candidateId)}/email-draft`,
    {
      method: "POST",
      body: JSON.stringify({ job_id: jobId, email_type: emailType, recipient }),
    },
  );
}

export async function sendMockEmail(
  candidateId: string,
  jobId: string,
  draft: EmailDraft,
): Promise<EmailHistoryItem> {
  return hrRequest<EmailHistoryItem>(
    `/candidates/${encodeURIComponent(candidateId)}/emails`,
    {
      method: "POST",
      body: JSON.stringify({
        job_id: jobId,
        draft_id: draft.id,
        recipient: draft.recipient,
        subject: draft.subject,
        body: draft.body,
      }),
    },
  );
}
