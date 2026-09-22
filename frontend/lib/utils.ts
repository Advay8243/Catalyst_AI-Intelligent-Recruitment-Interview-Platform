import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

export type ScoreTone = "emerald" | "green" | "amber" | "orange" | "red";

/** Visualization bands only — does not change scoring logic. */
export function scoreTone(score: number): ScoreTone {
  if (score >= 90) return "emerald";
  if (score >= 80) return "green";
  if (score >= 70) return "amber";
  if (score >= 60) return "orange";
  return "red";
}

export function scoreBandLabel(score: number) {
  if (score >= 90) return "90–100";
  if (score >= 80) return "80–89";
  if (score >= 70) return "70–79";
  if (score >= 60) return "60–69";
  return "Below 60";
}

export function scoreTextClass(score: number) {
  const tone = scoreTone(score);
  return {
    emerald: "text-[#027a48]",
    green: "text-[#039855]",
    amber: "text-[#b54708]",
    orange: "text-[#c4320a]",
    red: "text-[#b42318]",
  }[tone];
}

export function formatAiRecommendation(recommendation?: string | null) {
  if (!recommendation) return "Not available";
  const labels: Record<string, string> = {
    advance: "ADVANCE_TO_HUMAN_REVIEW",
    review: "NEEDS_FURTHER_REVIEW",
    do_not_advance: "DOES_NOT_MEET_CONFIGURED_CRITERIA",
  };
  return labels[recommendation] ?? recommendation.replaceAll("_", " ").toUpperCase();
}

export function formatEmailStatus(status?: string | null) {
  const value = status?.trim() || "Not Sent";
  return `✉ ${value}`;
}

export function friendlyErrorMessage(error: unknown, fallback: string) {
  const message = error instanceof Error ? error.message : String(error ?? "");
  const lower = message.toLowerCase();
  if (!message || lower.includes("failed to fetch") || lower.includes("network")) {
    return "Backend unavailable. Check that the API server is running and try again.";
  }
  if (lower.includes("corrupt") || lower.includes("unable to read")) {
    return "This file could not be read. It may be corrupted — try re-exporting as PDF or DOCX.";
  }
  if (lower.includes("parse") || lower.includes("extract")) {
    return "Parsing failed. Please verify the document and try again.";
  }
  if (lower.includes("matching failed") || lower.includes("ai ")) {
    return "AI analysis failed for this item. You can retry or continue with other candidates.";
  }
  if (lower.includes("email") && lower.includes("fail")) {
    return "Email delivery failed. Review the draft and try sending again.";
  }
  if (lower.includes("call") && lower.includes("fail")) {
    return "The screening call could not be completed. Start a new call session to retry.";
  }
  return message || fallback;
}
