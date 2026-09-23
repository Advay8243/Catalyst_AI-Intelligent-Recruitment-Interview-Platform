import type {
  BatchResumeResult,
  CallSession,
  Candidate,
  CandidateComparison,
  CandidateQuery,
  CandidateReview,
  DashboardActivity,
  DashboardStats,
  Decision,
  EmailDraft,
  EmailHistoryItem,
  EmailType,
  GenerateScoresResult,
  Job,
  JobParsePreview,
  JobRequirements,
  JobSearchHit,
  JobStatus,
  PaginatedCandidates,
  ScoringCriteria,
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
    fitPoints: Array.isArray(raw.fitPoints)
      ? raw.fitPoints.map(String)
      : Array.isArray(raw.fit_points)
        ? raw.fit_points.map(String)
        : [],
    gapPoints: Array.isArray(raw.gapPoints)
      ? raw.gapPoints.map(String)
      : Array.isArray(raw.gap_points)
        ? raw.gap_points.map(String)
        : [],
    status: raw.status ? String(raw.status) : raw.application_status ? String(raw.application_status) : undefined,
    callStatus: raw.callStatus ? String(raw.callStatus) : raw.call_status ? String(raw.call_status) : undefined,
    jobId: raw.jobId ? String(raw.jobId) : raw.job_id ? String(raw.job_id) : undefined,
    jobTitle: raw.jobTitle ? String(raw.jobTitle) : raw.job_title ? String(raw.job_title) : undefined,
    resumeUrl: raw.resumeUrl ? String(raw.resumeUrl) : raw.resume_url ? String(raw.resume_url) : undefined,
    skills: Array.isArray(raw.skills) ? raw.skills.map(String) : [],
    scoreBreakdown: (() => {
      const rawBreakdown = (raw.scoreBreakdown ?? raw.score_breakdown) as Record<string, unknown> | undefined;
      if (!rawBreakdown || typeof rawBreakdown !== "object") return undefined;
      return {
        skills: rawBreakdown.skills != null ? Number(rawBreakdown.skills) : undefined,
        experience: rawBreakdown.experience != null ? Number(rawBreakdown.experience) : undefined,
        education: rawBreakdown.education != null ? Number(rawBreakdown.education) : undefined,
        relevance: rawBreakdown.relevance != null ? Number(rawBreakdown.relevance) : undefined,
        required_skills: rawBreakdown.required_skills != null ? Number(rawBreakdown.required_skills) : undefined,
        preferred_skills: rawBreakdown.preferred_skills != null ? Number(rawBreakdown.preferred_skills) : undefined,
        responsibilities: rawBreakdown.responsibilities != null ? Number(rawBreakdown.responsibilities) : undefined,
        education_certification: rawBreakdown.education_certification != null ? Number(rawBreakdown.education_certification) : undefined,
        matched_skills: Array.isArray(rawBreakdown.matched_skills) ? rawBreakdown.matched_skills.map(String) : [],
        missing_skills: Array.isArray(rawBreakdown.missing_skills) ? rawBreakdown.missing_skills.map(String) : [],
        summary: rawBreakdown.summary ? String(rawBreakdown.summary) : undefined,
      };
    })(),
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
  const params = new URLSearchParams();
  params.set("page", String(query.page));
  params.set("page_size", String(query.pageSize));
  if (query.jobId) params.set("job_id", query.jobId);
  if (query.search) params.set("search", query.search);
  if (query.status) params.set("status", query.status);
  if (query.decisionStatus) params.set("decision_status", query.decisionStatus);
  if (query.screeningStatus) params.set("screening_status", query.screeningStatus);
  if (query.emailStatus) params.set("email_status", query.emailStatus);
  if (query.minScore) params.set("min_score", query.minScore);
  if (query.maxScore) params.set("max_score", query.maxScore);
  if (query.minHrScore) params.set("min_hr_score", query.minHrScore);
  if (query.maxHrScore) params.set("max_hr_score", query.maxHrScore);
  if (query.uploadedFrom) params.set("uploaded_from", query.uploadedFrom);
  if (query.uploadedTo) params.set("uploaded_to", query.uploadedTo);
  const sortMap: Record<string, string> = {
    jdScore: "score",
    hrScore: "hr_score",
    createdAt: "created_at",
    name: "name",
    decision: "decision",
    decisionStatus: "decision",
  };
  params.set("sort", sortMap[query.sortBy ?? "jdScore"] ?? "score");
  params.set("order", query.sortOrder ?? "desc");
  const raw = await request<Record<string, unknown>>(`/candidates?${params}`);
  const list = (raw.items ?? raw.results ?? raw.candidates ?? []) as Record<string, unknown>[];
  return {
    items: list.map(normalizeCandidate),
    total: Number(raw.total ?? raw.count ?? list.length),
    page: Number(raw.page ?? query.page),
    pageSize: Number(raw.pageSize ?? raw.page_size ?? query.pageSize),
    totalUploaded: raw.totalUploaded != null
      ? Number(raw.totalUploaded)
      : raw.total_uploaded != null
        ? Number(raw.total_uploaded)
        : undefined,
    shortlistedThreshold: raw.shortlistedThreshold != null
      ? Number(raw.shortlistedThreshold)
      : raw.shortlisted_threshold != null
        ? Number(raw.shortlisted_threshold)
        : 60,
  };
}

export async function compareCandidates(
  jobId: string,
  candidateIds: string[],
): Promise<CandidateComparison> {
  const params = new URLSearchParams();
  for (const id of candidateIds) params.append("ids", id);
  const raw = await request<Record<string, unknown>>(
    `/jobs/${encodeURIComponent(jobId)}/candidates/compare?${params}`,
  );
  const items = (raw.items ?? []) as Record<string, unknown>[];
  return {
    jobId: String(raw.jobId ?? raw.job_id ?? jobId),
    jobTitle: String(raw.jobTitle ?? raw.job_title ?? ""),
    items: items.map((item) => ({
      candidateId: String(item.candidateId ?? item.candidate_id ?? ""),
      fullName: String(item.fullName ?? item.full_name ?? ""),
      email: String(item.email ?? ""),
      jobId: String(item.jobId ?? item.job_id ?? jobId),
      jobTitle: String(item.jobTitle ?? item.job_title ?? ""),
      jdScore: item.jdScore != null ? Number(item.jdScore) : item.jd_score != null ? Number(item.jd_score) : null,
      hrScore: item.hrScore != null ? Number(item.hrScore) : item.hr_score != null ? Number(item.hr_score) : null,
      requiredSkillsScore:
        item.requiredSkillsScore != null
          ? Number(item.requiredSkillsScore)
          : item.required_skills_score != null
            ? Number(item.required_skills_score)
            : null,
      preferredSkillsScore:
        item.preferredSkillsScore != null
          ? Number(item.preferredSkillsScore)
          : item.preferred_skills_score != null
            ? Number(item.preferred_skills_score)
            : null,
      experienceScore:
        item.experienceScore != null
          ? Number(item.experienceScore)
          : item.experience_score != null
            ? Number(item.experience_score)
            : null,
      responsibilitiesScore:
        item.responsibilitiesScore != null
          ? Number(item.responsibilitiesScore)
          : item.responsibilities_score != null
            ? Number(item.responsibilities_score)
            : null,
      educationScore:
        item.educationScore != null
          ? Number(item.educationScore)
          : item.education_score != null
            ? Number(item.education_score)
            : null,
      matchedRequiredSkills: Array.isArray(item.matchedRequiredSkills)
        ? item.matchedRequiredSkills.map(String)
        : Array.isArray(item.matched_required_skills)
          ? item.matched_required_skills.map(String)
          : [],
      matchedPreferredSkills: Array.isArray(item.matchedPreferredSkills)
        ? item.matchedPreferredSkills.map(String)
        : Array.isArray(item.matched_preferred_skills)
          ? item.matched_preferred_skills.map(String)
          : [],
      missingRequiredSkills: Array.isArray(item.missingRequiredSkills)
        ? item.missingRequiredSkills.map(String)
        : Array.isArray(item.missing_required_skills)
          ? item.missing_required_skills.map(String)
          : [],
      experienceYears:
        item.experienceYears != null
          ? Number(item.experienceYears)
          : item.experience_years != null
            ? Number(item.experience_years)
            : null,
      education: Array.isArray(item.education) ? item.education.map(String) : [],
      strengths: Array.isArray(item.strengths) ? item.strengths.map(String) : [],
      missingInformation: Array.isArray(item.missingInformation)
        ? item.missingInformation.map(String)
        : Array.isArray(item.missing_information)
          ? item.missing_information.map(String)
          : [],
      aiRecommendation:
        item.aiRecommendation != null
          ? String(item.aiRecommendation)
          : item.ai_recommendation != null
            ? String(item.ai_recommendation)
            : null,
      humanDecision: String(item.humanDecision ?? item.human_decision ?? "pending"),
      fitReason: item.fitReason != null ? String(item.fitReason) : item.fit_reason != null ? String(item.fit_reason) : null,
    })),
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

export async function getJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${encodeURIComponent(jobId)}`);
}

export async function searchJobs(query: string, limit = 20): Promise<JobSearchHit[]> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  const raw = await request<{ items?: Array<{ job: Job; similarity: number }> }>(
    `/jobs/search?${params}`,
  );
  return (raw.items ?? []).map((item) => ({
    job: item.job,
    similarity: Number(item.similarity ?? 0),
  }));
}

export async function getScoringCriteria(): Promise<ScoringCriteria> {
  return request<ScoringCriteria>("/scoring-criteria");
}

export async function generateJobScores(jobId: string): Promise<GenerateScoresResult> {
  return request<GenerateScoresResult>(
    `/jobs/${encodeURIComponent(jobId)}/generate-scores`,
    { method: "POST" },
  );
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

export async function parseJobDescription(input: {
  description?: string;
  title?: string;
  file?: File;
}): Promise<JobParsePreview> {
  if (input.file) {
    const form = new FormData();
    form.append("file", input.file);
    if (input.title) form.append("title", input.title);
    return uploadFiles("/jobs/parse", form, () => undefined) as Promise<JobParsePreview>;
  }
  return request<JobParsePreview>("/jobs/parse", {
    method: "POST",
    body: JSON.stringify({
      description: input.description,
      title: input.title,
    }),
  });
}

export async function createJob(payload: {
  description: string;
  title?: string;
  company?: string;
  department?: string;
  location?: string;
  employment_type?: string;
  experience_required?: string;
  required_skills?: string[];
  preferred_skills?: string[];
  responsibilities?: string[];
  education?: string[];
  certifications?: string[];
  status?: JobStatus;
}): Promise<Job> {
  return request<Job>("/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateJob(
  jobId: string,
  payload: Partial<{
    title: string;
    company: string;
    department: string;
    location: string;
    employment_type: string;
    experience_required: string;
    description: string;
    required_skills: string[];
    preferred_skills: string[];
    responsibilities: string[];
    education: string[];
    certifications: string[];
    status: JobStatus;
  }>,
): Promise<Job> {
  return request<Job>(`/jobs/${encodeURIComponent(jobId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function publishJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${encodeURIComponent(jobId)}/publish`, { method: "POST" });
}

export async function archiveJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${encodeURIComponent(jobId)}/archive`, { method: "POST" });
}

export async function deleteJob(jobId: string): Promise<void> {
  const response = await fetch(`${API_URL}/jobs/${encodeURIComponent(jobId)}`, {
    method: "DELETE",
  });
  if (!response.ok && response.status !== 204) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail ?? `Delete failed (${response.status})`);
  }
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

export async function uploadResumesBatch(
  jobId: string,
  files: File[],
  onProgress: (percent: number) => void,
): Promise<BatchResumeResult> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  return uploadFiles(
    `/jobs/${encodeURIComponent(jobId)}/resumes/batch`,
    form,
    onProgress,
  ) as Promise<BatchResumeResult>;
}

export async function correctResumeParse(
  candidateId: string,
  jobId: string,
  corrections: {
    full_name?: string;
    email?: string;
    phone?: string;
    skills?: string[];
    years_experience?: number;
    education?: string[];
    certifications?: string[];
    projects?: string[];
    employment_history?: string[];
    highlights?: string[];
  },
) {
  return hrRequest<{
    candidate: Record<string, unknown>;
    analysis: Record<string, unknown>;
    corrected_by: string;
  }>(`/candidates/${encodeURIComponent(candidateId)}/resume-parse-correction`, {
    method: "POST",
    body: JSON.stringify({ job_id: jobId, ...corrections }),
  });
}

export async function getDashboardStats(jobId?: string): Promise<DashboardStats> {
  const params = jobId ? `?job_id=${encodeURIComponent(jobId)}` : "";
  return request<DashboardStats>(`/dashboard/stats${params}`);
}

export async function getDashboardActivity(
  jobId?: string,
  limit = 20,
): Promise<DashboardActivity> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (jobId) params.set("job_id", jobId);
  return request<DashboardActivity>(`/dashboard/activity?${params}`);
}

export async function removeCandidateApplication(jobId: string, candidateId: string) {
  const response = await fetch(
    `${API_URL}/jobs/${encodeURIComponent(jobId)}/candidates/${encodeURIComponent(candidateId)}/application`,
    { method: "DELETE" },
  );
  if (!response.ok && response.status !== 204) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail ?? `Remove failed (${response.status})`);
  }
}

export type { JobRequirements };

export async function createCallSession(candidateId: string, jobId?: string): Promise<CallSession> {
  return request<CallSession>(`/candidates/${encodeURIComponent(candidateId)}/call-sessions`, {
    method: "POST",
    body: JSON.stringify({ job_id: jobId || null }),
  });
}

export async function getCallSession(sessionId: string): Promise<CallSession> {
  return request<CallSession>(`/call-sessions/${encodeURIComponent(sessionId)}`);
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

export async function pasteTranscript(
  sessionId: string,
  transcriptText: string,
): Promise<{ session: CallSession; entries: TranscriptEntry[] }> {
  return request<{ session: CallSession; entries: TranscriptEntry[] }>(
    `/call-sessions/${encodeURIComponent(sessionId)}/paste-transcript`,
    {
      method: "POST",
      body: JSON.stringify({ transcript_text: transcriptText }),
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
