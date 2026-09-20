"use client";

import { CheckCircle2, Eye, Mail, Send } from "lucide-react";
import { useEffect, useState } from "react";
import type { Candidate, Decision, EmailDraft, EmailHistoryItem, EmailType } from "@/lib/types";
import { Button, Dialog, DialogContent, Input } from "@/components/ui";
import { generateEmailDraft, sendMockEmail } from "@/lib/api";

export function EmailComposer({
  candidate,
  open,
  onOpenChange,
  onNotice,
  decision,
  emailType,
  jobId,
  onSent,
}: {
  candidate: Candidate | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onNotice: (message: string) => void;
  decision?: Decision;
  emailType?: EmailType;
  jobId?: string;
  onSent?: (email: EmailHistoryItem) => void;
}) {
  const [interviewer, setInterviewer] = useState("");
  const [recipient, setRecipient] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [draft, setDraft] = useState<EmailDraft | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!candidate) return;
    setRecipient(candidate.email);
    setSubject(`Next steps for ${candidate.jobTitle ?? "your application"} at Catalyst AI`);
    setMessage(`Hi ${candidate.name.split(" ")[0]},\n\nThank you for your interest in ${candidate.jobTitle ?? "the role"}. We would like to invite you to the next stage of our process.\n\nPlease reply with your availability, and our recruiting team will coordinate the details.\n\nBest,\nCatalyst AI Recruiting`);
    setInterviewer("");
    setPreviewing(false);
    setError("");
    setDraft(null);
    const selectedEmailType = emailType ?? decision;
    if (selectedEmailType && selectedEmailType !== "needs_review" && jobId) {
      generateEmailDraft(candidate.id, jobId, selectedEmailType)
        .then((draft) => {
          setDraft(draft);
          setRecipient(draft.recipient);
          setSubject(draft.subject);
          setMessage(draft.body);
        })
        .catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to generate email draft."));
    }
  }, [candidate, decision, emailType, jobId]);

  if (!candidate) return null;
  const recipientValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(recipient);
  const canPreview = Boolean(recipientValid && subject.trim() && message.trim());

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={previewing ? "Email preview" : emailType === "internal" ? "Email interviewer / HR" : "Email candidate"} description={emailType === "internal" ? `Share next steps for ${candidate.name}` : `Compose a message for ${candidate.name}`} className="max-w-2xl">
        {previewing ? (
          <div className="mt-6 overflow-hidden rounded-xl border">
            <div className="space-y-2 border-b bg-[#f8f9fb] p-4 text-sm">
              <p><span className="inline-block w-16 text-[#98a2b3]">To</span>{recipient}</p>
              <p><span className="inline-block w-16 text-[#98a2b3]">From</span>{interviewer || "Recruiting team (not assigned)"}</p>
              <p><span className="inline-block w-16 text-[#98a2b3]">Subject</span><strong>{subject}</strong></p>
            </div>
            <div className="whitespace-pre-wrap p-5 text-sm leading-6 text-[#344054]">{message}</div>
          </div>
        ) : (
          <div className="mt-6 space-y-4">
            <label className="block"><span className="mb-1.5 block text-sm font-medium">Recipient</span><Input type="email" value={recipient} onChange={(event) => setRecipient(event.target.value)} aria-label="Recipient" aria-invalid={!recipientValid} /></label>
            <label className="block"><span className="mb-1.5 block text-sm font-medium">Interviewer</span><Input value={interviewer} onChange={(event) => setInterviewer(event.target.value)} placeholder="Assign an interviewer (optional)" aria-label="Interviewer" /></label>
            <label className="block"><span className="mb-1.5 block text-sm font-medium">Subject</span><Input value={subject} onChange={(event) => setSubject(event.target.value)} aria-label="Subject" /></label>
            <label className="block"><span className="mb-1.5 block text-sm font-medium">Message</span><textarea value={message} onChange={(event) => setMessage(event.target.value)} aria-label="Message" rows={9} className="w-full resize-none rounded-lg border bg-white p-3 text-sm leading-6 shadow-sm focus:border-primary" /></label>
          </div>
        )}
        <div className="mt-6 flex flex-col-reverse justify-end gap-2 sm:flex-row">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>
          {previewing && <Button variant="secondary" onClick={() => setPreviewing(false)}>Edit</Button>}
          {!previewing && <Button variant="secondary" disabled={!canPreview} onClick={() => setPreviewing(true)}><Eye className="size-4" />Preview</Button>}
          {previewing && <Button
            disabled={!canPreview || sending}
            onClick={async () => {
              if (!(emailType ?? decision) || (emailType ?? decision) === "needs_review" || !jobId || !draft) {
                onNotice("Record an HR decision before sending a candidate email.");
                return;
              }
              setSending(true);
              setError("");
              try {
                const sent = await sendMockEmail(candidate.id, jobId, {
                  ...draft,
                  recipient,
                  subject,
                  body: message,
                });
                onSent?.(sent);
                onNotice("Email mock-sent and added to candidate history.");
                onOpenChange(false);
              } catch (caught) {
                setError(caught instanceof Error ? caught.message : "Unable to send email.");
              } finally {
                setSending(false);
              }
            }}
          >
            <Send className="size-4" />{sending ? "Sending…" : "Send Email"}
          </Button>}
        </div>
        {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
        <div className="mt-4 flex gap-2 rounded-lg bg-[#f8f9fb] px-3 py-2 text-xs text-[#667085]">
          <CheckCircle2 className="size-4 shrink-0 text-[#98a2b3]" />
          Email delivery uses the local mock provider and is recorded in PostgreSQL; no external email is sent.
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function EmailButton({ onClick }: { onClick: () => void }) {
  return <Button variant="ghost" size="icon" onClick={onClick} aria-label="Email candidate"><Mail className="size-[18px]" /></Button>;
}
