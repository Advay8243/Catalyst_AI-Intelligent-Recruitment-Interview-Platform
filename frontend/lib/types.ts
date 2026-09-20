export type ScoreBreakdown = {
  skills?: number;
  experience?: number;
  education?: number;
  relevance?: number;
  summary?: string;
};

export type Candidate = {
  id: string;
  name: string;
  email: string;
  phone?: string;
  location?: string;
  currentTitle?: string;
  experienceYears?: number;
  jdScore: number | null;
  hrScore: number | null;
  fitReason: string;
  status?: string;
  callStatus?: string;
  jobId?: string;
  jobTitle?: string;
  resumeUrl?: string;
  skills?: string[];
  scoreBreakdown?: ScoreBreakdown;
  hrAnalysis?: string;
  resumeStatus?: string;
  screeningStatus?: string;
  screeningRecommendation?: string;
  appliedAt?: string;
  screenedAt?: string;
  decisionAt?: string;
  decisionStatus?: Decision | "pending";
  emailStatus?: string;
  currentStage?: string;
};

export type Job = {
  id: string;
  title: string;
  department?: string;
};

export type CandidateQuery = {
  page: number;
  pageSize: number;
  search?: string;
  jobId?: string;
  status?: string;
  minScore?: string;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
};

export type PaginatedCandidates = {
  items: Candidate[];
  total: number;
  page: number;
  pageSize: number;
};

export type ScreeningQuestion = {
  id: string;
  text: string;
  category: "experience" | "skills" | "motivation" | "communication" | "availability";
};

export type TranscriptEntry = {
  id: string;
  sequence: number;
  speaker: "hr" | "candidate";
  text: string;
  created_at: string;
};

export type CallSession = {
  id: string;
  status: "not_started" | "connecting" | "connected" | "completed" | "failed";
  provider: string;
  provider_call_id?: string;
  candidate: {
    candidate_id: string;
    candidate_name: string;
    email: string;
    phone?: string;
    job_id: string;
    job_title: string;
    jd_resume_score: number;
    key_matched_skills: string[];
  };
  questions: ScreeningQuestion[];
  transcript: TranscriptEntry[];
  started_at?: string;
  ended_at?: string;
  created_at: string;
};

export type ScreeningAnalysis = {
  overall_score: number;
  communication_score: number;
  experience_score: number;
  skills_score: number;
  motivation_score: number;
  availability_score: number;
  question_analysis: Array<{
    question: string;
    answer?: string;
    category: string;
    score: number;
    evidence: string[];
    assessment: string;
  }>;
  strengths: string[];
  concerns: string[];
  recommendation: "advance" | "review" | "do_not_advance";
  summary: string;
};

export type Decision = "accepted" | "rejected" | "needs_review" | "advanced";
export type EmailType = "accepted" | "rejected" | "advanced" | "internal";

export type EmailHistoryItem = {
  id: string;
  candidate_id: string;
  application_id: string;
  recipient: string;
  subject: string;
  body: string;
  email_type: EmailType;
  status: string;
  sent_at?: string;
  created_at: string;
};

export type TimelineEvent = {
  id: string;
  event_type: string;
  timestamp: string;
  title: string;
  description: string;
  actor?: string;
  metadata: Record<string, unknown>;
};

export type CandidateReview = {
  application: {
    id: string;
    status: string;
    resume_status: string;
    screening_status: string;
    current_stage: string;
    applied_at: string;
    screened_at?: string;
    decision?: Decision;
    decision_at?: string;
    decision_by?: string;
    decision_reason?: string;
    decision_notes?: string;
  };
  candidate: {
    id: string;
    name: string;
    email: string;
    phone?: string;
    profile: Record<string, unknown>;
  };
  job: {
    id: string;
    title: string;
    description: string;
    responsibilities: string[];
    required_skills: string[];
    preferred_skills: string[];
    experience_requirements: string;
  };
  resume: {
    id: string;
    filename: string;
    mime_type: string;
    parsed_data: {
      skills?: string[];
      years_experience?: number;
      education?: string[];
      highlights?: string[];
      projects?: string[];
    };
    uploaded_at: string;
  };
  resume_analysis: {
    overall_score: number;
    scoring: Record<string, { score?: number; explanation?: string; evidence?: string[] }>;
    evidence: Record<string, string[]>;
    explanation: string;
  };
  call_session?: {
    id: string;
    status: string;
    started_at?: string;
    ended_at?: string;
    questions: ScreeningQuestion[];
    transcript: TranscriptEntry[];
  };
  screening_analysis?: {
    overall_score: number;
    score_components: Record<string, number>;
    role_relevance: number;
    question_analysis: Array<{
      question: string;
      answer?: string;
      category: string;
      score: number;
      evidence: string[];
      assessment: string;
      follow_up_question?: string;
    }>;
    strengths: string[];
    concerns: string[];
    recommendation: string;
    summary: string;
    label: string;
  };
  email_history: EmailHistoryItem[];
  decision_history: Array<{
    id: string;
    decision: Decision;
    previous_status: string;
    new_status: string;
    decision_maker: string;
    decision_reason?: string;
    decision_notes?: string;
    decision_timestamp: string;
  }>;
  timeline: TimelineEvent[];
  audit_events: TimelineEvent[];
};

export type EmailDraft = {
  id: string;
  recipient: string;
  subject: string;
  body: string;
  email_type: EmailType;
  status: string;
  created_at: string;
};
