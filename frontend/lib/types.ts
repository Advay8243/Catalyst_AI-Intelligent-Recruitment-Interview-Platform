export type ScoreBreakdown = {
  skills?: number;
  experience?: number;
  education?: number;
  relevance?: number;
  required_skills?: number;
  preferred_skills?: number;
  responsibilities?: number;
  education_certification?: number;
  matched_skills?: string[];
  missing_skills?: string[];
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
  fitPoints?: string[];
  gapPoints?: string[];
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

export type JobStatus = "draft" | "published" | "archived";

export type JobRequirements = {
  title?: string;
  department?: string;
  location?: string;
  employment_type?: string;
  experience_required?: string;
  required_skills?: string[];
  preferred_skills?: string[];
  responsibilities?: string[];
  education?: string[];
  certifications?: string[];
  minimum_years_experience?: number;
  summary_bullets?: string[];
};

export type Job = {
  id: string;
  title: string;
  company?: string;
  department?: string;
  location?: string;
  employment_type?: string;
  description?: string;
  status?: JobStatus | string;
  created_at?: string;
  updated_at?: string;
  application_count?: number;
  requirements?: {
    id?: string;
    structured_data?: JobRequirements;
  };
};

export type JobParsePreview = {
  description: string;
  extracted: JobRequirements;
  editable: JobRequirements;
};

export type BatchResumeResult = {
  job_id: string;
  results: Array<{
    filename: string;
    status: "success" | "failed" | "duplicate";
    message?: string;
  }>;
  success_count: number;
  failure_count: number;
  duplicate_count: number;
};


export type CandidateQuery = {
  page: number;
  pageSize: number;
  search?: string;
  jobId?: string;
  status?: string;
  decisionStatus?: string;
  screeningStatus?: string;
  emailStatus?: string;
  minScore?: string;
  maxScore?: string;
  minHrScore?: string;
  maxHrScore?: string;
  uploadedFrom?: string;
  uploadedTo?: string;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
};

export type CandidateComparisonItem = {
  candidateId: string;
  fullName: string;
  email: string;
  jobId: string;
  jobTitle: string;
  jdScore: number | null;
  hrScore: number | null;
  requiredSkillsScore: number | null;
  preferredSkillsScore: number | null;
  experienceScore: number | null;
  responsibilitiesScore: number | null;
  educationScore: number | null;
  matchedRequiredSkills: string[];
  matchedPreferredSkills: string[];
  missingRequiredSkills: string[];
  experienceYears: number | null;
  education: string[];
  strengths: string[];
  missingInformation: string[];
  aiRecommendation: string | null;
  humanDecision: string;
  scoreBreakdown?: ScoreBreakdown;
  fitReason?: string | null;
};

export type CandidateComparison = {
  jobId: string;
  jobTitle: string;
  items: CandidateComparisonItem[];
};

export type PaginatedCandidates = {
  items: Candidate[];
  total: number;
  page: number;
  pageSize: number;
  totalUploaded?: number;
  shortlistedThreshold?: number;
};

export type ScreeningQuestion = {
  id: string;
  text: string;
  category: "experience" | "skills" | "motivation" | "communication" | "availability";
  reason?: string | null;
  focus_skills?: string[];
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
  transcript_source?: "none" | "realtime" | "pasted" | string;
  realtime_transcription_available?: boolean;
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
    relevance?: string | null;
    completeness?: string | null;
    technical_evidence?: string[];
    missing_information?: string[];
    suggested_follow_up?: string | null;
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
    summary_bullets?: string[];
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
      full_name?: string;
      email?: string;
      phone?: string;
      skills?: string[];
      years_experience?: number;
      education?: string[];
      certifications?: string[];
      highlights?: string[];
      projects?: string[];
      employment_history?: string[];
    };
    uploaded_at: string;
    parse_corrected_at?: string;
    parse_corrected_by?: string;
  };
  resume_analysis: {
    overall_score: number;
    scoring: Record<
      string,
      | { score?: number; explanation?: string; evidence?: string[] }
      | {
          matched_skills?: string[];
          missing_skills?: string[];
          required_skill_score?: number;
          preferred_skill_score?: number;
          responsibilities_score?: number;
          education_certification_score?: number;
        }
    >;
    evidence: Record<string, string[]>;
    explanation: string;
    fit_points?: string[];
    gap_points?: string[];
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

export type DashboardStats = {
  total_candidates: number;
  pending_hr_screening: number;
  hr_screened: number;
  needs_review: number;
  accepted: number;
  rejected: number;
  emails_sent: number;
  active_job_descriptions: number;
  average_jd_resume_score: number | null;
  average_hr_screening_score: number | null;
  candidates_per_job: Array<{
    job_id: string;
    title: string;
    status: string;
    candidate_count: number;
  }>;
  job_id?: string | null;
};

export type DashboardActivity = {
  items: Array<{
    id: string;
    event_type: string;
    title: string;
    description: string;
    timestamp: string;
    actor?: string | null;
    candidate_id?: string | null;
    candidate_name?: string | null;
    job_id?: string | null;
    job_title?: string | null;
  }>;
  job_id?: string | null;
};

export type ScoringCriterion = {
  key: string;
  label: string;
  weight_percent: number;
  description: string;
};

export type ScoringCriteria = {
  criteria: ScoringCriterion[];
  signals: string[];
  note: string;
};

export type JobSearchHit = {
  job: Job;
  similarity: number;
};

export type GenerateScoresResult = {
  job_id: string;
  analyzed_count: number;
  shortlisted_count: number;
  skipped_below_threshold: number;
};

export type TopCandidatePreview = {
  candidate_id: string;
  full_name: string;
  email: string;
  experience_years?: number | null;
  preview_score?: number | null;
};
