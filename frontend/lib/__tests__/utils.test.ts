import { describe, expect, it } from "vitest";
import {
  formatAiRecommendation,
  formatEmailStatus,
  formatShortDate,
  scoreBandLabel,
  scoreTone,
} from "@/lib/utils";

describe("scoreTone", () => {
  it("maps visualization bands without changing scoring logic", () => {
    expect(scoreTone(95)).toBe("emerald");
    expect(scoreTone(85)).toBe("green");
    expect(scoreTone(75)).toBe("amber");
    expect(scoreTone(65)).toBe("orange");
    expect(scoreTone(40)).toBe("red");
  });

  it("labels score bands for recruiters", () => {
    expect(scoreBandLabel(92)).toBe("90–100");
    expect(scoreBandLabel(80)).toBe("80–89");
    expect(scoreBandLabel(70)).toBe("70–79");
    expect(scoreBandLabel(60)).toBe("60–69");
    expect(scoreBandLabel(59)).toBe("Below 60");
  });
});

describe("formatAiRecommendation", () => {
  it("maps AI decision-support labels without implying a final hire decision", () => {
    expect(formatAiRecommendation("advance")).toBe("ADVANCE_TO_HUMAN_REVIEW");
    expect(formatAiRecommendation("review")).toBe("NEEDS_FURTHER_REVIEW");
    expect(formatAiRecommendation("do_not_advance")).toBe(
      "DOES_NOT_MEET_CONFIGURED_CRITERIA",
    );
  });
});

describe("formatEmailStatus", () => {
  it("prefixes email lifecycle statuses for the candidate table", () => {
    expect(formatEmailStatus(undefined)).toBe("✉ Not Sent");
    expect(formatEmailStatus("Draft")).toBe("✉ Draft");
    expect(formatEmailStatus("Sent")).toBe("✉ Sent");
    expect(formatEmailStatus("Failed")).toBe("✉ Failed");
  });
});

describe("formatShortDate", () => {
  it("formats persisted timestamps without exposing raw database values", () => {
    expect(formatShortDate("2026-09-24T13:57:23.293Z")).toBe("24 Sep 2026");
    expect(formatShortDate(undefined)).toBe("");
  });
});
