# Catalyst AI

Catalyst AI is a recruitment operations application. This first module covers job-description ingestion, PDF/DOCX resume ingestion, transparent JD-to-resume matching, unified candidate screening, HR-call navigation, and an email-composer shell. Online assessments, real calling/email delivery, and technical interviews are intentionally out of scope.

The application runs without external AI credentials by using a deterministic `MockAIProvider`. Set `AI_PROVIDER=groq` with a backend `GROQ_API_KEY` to use Groq for parsing, fit explanations, interview questions, and transcript analysis. Resume scores stay on the weighted formula. Groq does not provide embeddings, so semantic search uses local hash vectors.

The HR screening module provides a full mock-provider workflow at
`/screening/call/{candidate_id}`: call lifecycle, live transcript capture,
structured question/answer analysis, an HR screening score, and return of that
score to the unified Candidate Screening table. Mock mode never places an
external telephone call.

## Architecture

```text
Next.js UI (frontend/)
        |
        v
FastAPI routes (backend/api/)
        |
        v
Application services (backend/services/)
        |
        +--> AIProvider / document parsers
        +--> FileStorageProvider
        +--> CallProvider and EmailProvider interfaces
        |
        v
Repositories -> SQLAlchemy ORM -> PostgreSQL
```

Original documents and structured AI output are stored separately. Uploaded binaries are written to `storage/uploads`; PostgreSQL stores metadata and paths. Matching details and evidence use PostgreSQL JSONB.

## Prerequisites

- Python 3.10+
- Node.js 20+
- npm 10+
- PostgreSQL 14+ or Docker with Docker Compose

## Environment

Copy the example configuration:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

The main variables are:

- `DATABASE_URL`: SQLAlchemy PostgreSQL URL. Never commit credentials.
- `AI_PROVIDER`: `mock`, `groq`, `gemini`, or `openai`. `mock` makes no external AI calls.
- `GROQ_API_KEY` and `GROQ_MODEL`: backend-only Groq settings. Leave the key empty in mock mode.
- `GEMINI_API_KEY`: backend-only Gemini key. Leave empty in mock mode. Never put this in frontend env vars or source code.
- `GEMINI_MODEL`: text model, default `gemini-2.5-flash`. Use a model enabled on your account.
- `GEMINI_EMBEDDING_MODEL`: embedding model, default `gemini-embedding-001`.
- `AI_API_KEY`: used only when `AI_PROVIDER=openai`.
- `AI_TIMEOUT_SECONDS` and `AI_MAX_RETRIES`: Gemini and OpenAI request limits.
- `CORS_ORIGINS`: comma-separated allowed frontend origins.
- `MAX_UPLOAD_SIZE_MB`: upload limit.
- `UPLOAD_DIR`: local file-storage directory.
- `NEXT_PUBLIC_API_URL`: browser-visible FastAPI base URL.
- `BACKEND_API_URL`: FastAPI URL used by the Next.js server-side HR proxy.
- `HR_API_TOKEN`: securely managed shared token used only between Next.js and
  FastAPI for HR mutation endpoints. Set the same value in backend and frontend
  server environments; never prefix it with `NEXT_PUBLIC_`.
- `HR_USER_NAME`: audit attribution used until user authentication is added.

## PostgreSQL with Docker

```bash
docker compose up -d postgres
```

The development Compose service creates database `catalyst_ai` and waits for PostgreSQL health. Its credentials are local development defaults only; use environment-managed credentials outside local development.

## PostgreSQL without Docker

Install and start PostgreSQL using your platform package manager, then create a local role and database:

```bash
createuser --login --pwprompt catalyst_user
createdb --owner=catalyst_user catalyst_ai
```

Set `DATABASE_URL` in `.env` to match the credentials entered above. Do not put a real password in source control.

## Backend setup

From the repository root:

```bash
python3.10 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -r requirements.txt
alembic upgrade head
python -m backend.seed
uvicorn backend.main:app --reload
```

FastAPI runs at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`.

Alembic is the only supported schema-initialization path. A fresh database is initialized with `alembic upgrade head`; application startup does not create tables implicitly.

Migration `0002_hr_screening_calls` adds call sessions, ordered transcript
entries, and structured HR screening analysis.

Migration `0003_candidate_decisions_email_history` adds HR decision metadata to
applications and a PostgreSQL-backed history of mock-sent candidate emails.

Migration `0004_audit_timeline_email_lifecycle` adds immutable decision history,
candidate audit events, and Draft/Sent/Failed email lifecycle support.

## Frontend setup

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000/screening`.

## Demo data

After migrations:

```bash
python -m backend.seed
```

The idempotent seed creates three fictional jobs and eight fictional candidates with varied scores, evidence, and explanations.

## Tests and static checks

Backend:

```bash
pytest backend/tests
```

Frontend:

```bash
cd frontend
npm test
npm run lint
npm run typecheck
```

## Using the screening workflow

1. Select an existing job or create one by pasting/uploading a JD.
2. Upload one or more PDF or DOCX resumes.
3. Follow the processing status while text is extracted, parsed, and matched.
4. Review candidates in the unified table.
5. Open a score for its component breakdown and evidence.
6. Use the phone icon to navigate to the dedicated HR Calling Screen.
7. Use the email icon to open the composer.

The local call workflow uses `MockCallProvider`; it simulates connection and
completion while persisting the same application state a future telephony
provider will use. Email delivery remains pending and no external message is
sent.

## HR screening call workflow

1. Select the phone icon in the unified candidate table.
2. Start the mock call and confirm the status changes to Connected.
3. Use the consistent suggested questions.
4. Capture HR and candidate transcript entries.
5. Select **End & Analyze** after at least one candidate response.
6. Review the evidence-based score and component scores.
7. Return to Candidate Screening; the HR Screening Score and analysis are now
   available in the existing table.

After screening, open the candidate detail page to review the JD, resume
evidence, transcript, per-answer analysis, strengths, and concerns. HR must
explicitly confirm **Advance Candidate** or **Reject Candidate**. The resulting
email is editable and requires a second explicit send action. Mock sends are
stored in email history; no external delivery occurs.

The profile timeline combines persisted audit events with existing entity
timestamps, preserving visibility for records created before audit logging was
introduced.

Transcript analysis excludes protected characteristics and scores only captured,
job-relevant evidence. A real provider can replace `MockCallProvider` through
FastAPI dependency injection.

## AI providers

Restart the backend after changing `.env`. `GET /ai/status` reports the active provider and does not return credentials.

`AI_PROVIDER=mock` uses local rules for parsing, question wording, transcript scoring, and hash-based vectors. The Candidate Screening page labels this mode as rule-based. Mock output is not labeled as Gemini output.

`AI_PROVIDER=groq` calls the Groq API for resume and job extraction, fit and gap explanations, screening questions, and transcript analysis. The resume number still comes from the weighted formula. Groq has no embedding API, so search uses local 256-dimension hash vectors and reports retrieval as `local-hash`. Invalid keys, unavailable models, rate limits, and malformed responses are returned as errors and are not replaced with mock text. The default model is `openai/gpt-oss-120b`.

`AI_PROVIDER=gemini` calls the Gemini API for:

- Resume and job-description extraction, including skills outside the old fixed list
- The numerical resume score, category scores, and fit or gap explanations
- Screening questions, including why the question matters and what a good answer should show
- Semantic transcript analysis
- Job and resume embeddings for search

In Gemini mode, the resume score and its category breakdown are model-generated and saved in the existing score fields. Mock mode still calculates that score with the weighted formula. Email and phone values are taken from the document with deterministic checks. A transcript without enough candidate evidence returns an insufficient-evidence result instead of an invented score.

Gemini failures, including an invalid key, quota exhaustion, an unavailable model, or a malformed response, are returned as errors. They are not replaced with mock text. Old 256-dimension hash vectors are not compared with Gemini embeddings; the next search rebuilds a job vector in the active embedding space.

Gemini availability and quota depend on the Google account and model. The default models are `gemini-2.5-flash` and `gemini-embedding-001`. If a model is not enabled for the key, set `GEMINI_MODEL` or `GEMINI_EMBEDDING_MODEL` to one that is.

Calling and email delivery are still local mocks. Gemini does not place phone calls, transcribe live audio, or send email.

`MockAIProvider` and the Gemini path share the same score weights: skills 40, experience 20, education 20, industry 15, and other responsibilities 5. Weights must total 100. Scoring excludes protected characteristics, including age, gender, race, religion, disability, photographs, and marital status.

## API

- `POST /jobs`
- `GET /ai/status`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/resume`
- `GET /jobs/{job_id}/candidates`
- `GET /candidates/{candidate_id}`
- `GET /candidates/{candidate_id}/resume-analysis`
- `POST /candidates/{candidate_id}/call-sessions`
- `GET /call-sessions/{call_session_id}`
- `POST /call-sessions/{call_session_id}/start`
- `POST /call-sessions/{call_session_id}/transcript`
- `POST /call-sessions/{call_session_id}/complete`
- `GET /candidates/{candidate_id}/review`
- `POST /candidates/{candidate_id}/decision`
- `POST /candidates/{candidate_id}/email-draft`
- `POST /candidates/{candidate_id}/emails`
- `GET /candidates/{candidate_id}/emails`
- `GET /resumes/{resume_id}/download`

Candidate listing supports `page`, `page_size`, `search`, score/status filters, and sorting.

## Future integrations

The provider interfaces are intended for:

- Additional model providers behind `AIProvider`
- S3-compatible storage behind `FileStorageProvider`
- Telephony behind `CallProvider`
- Transactional email behind `EmailProvider`
- Online assessments and technical interviews in later modules

None of these external integrations are enabled in this phase.
