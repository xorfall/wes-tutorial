import { drawingNumber, nanos, numericText, range, type NumericValue, type TimeRange } from "@wes/view-sdk";
import type { Input } from "./contract";

/** Bounds shared with the builtin Timeline so one input is valid for both views. */
export const PANEL_LIMITS = { series: 8, records: 20_000 } as const;

export interface PanelSample {
  readonly at: string;
  readonly t: bigint;
  /** The exact source lexeme; never a rounded drawing number. */
  readonly text: string;
  /** Drawing position only; absent when the value cannot be plotted without loss. */
  readonly y: number | undefined;
}

/** The last valid sample and what, if anything, came after it. */
export type Latest =
  | { readonly kind: "value"; readonly sample: PanelSample; readonly trailingGaps: number; readonly lastAt: string }
  | { readonly kind: "gaps-only"; readonly gaps: number }
  | { readonly kind: "empty" };

export interface PanelSeries {
  readonly id: string;
  readonly label: string;
  readonly unit: string;
  /**
   * Runs of consecutive drawable samples. Only what the input states ends a run: a sample marked
   * as a gap, or a value that cannot be drawn exactly. The cadence of a generic Timeline is not
   * declared, so a longer interval between two samples is drawn as given, not called missing data.
   */
  readonly runs: readonly (readonly PanelSample[])[];
  readonly latest: Latest;
  readonly lowest: PanelSample | undefined;
  readonly highest: PanelSample | undefined;
  /** Valid samples whose exact value cannot be drawn as a safe number. */
  readonly undrawable: number;
  readonly gaps: number;
}

export interface PanelModel {
  readonly title: string;
  readonly range: TimeRange;
  readonly coverage: TimeRange;
  readonly partialCoverage: boolean;
  readonly omitted: string;
  readonly sourceError: string;
  readonly series: readonly PanelSeries[];
  readonly events: number;
}

export class PanelInputError extends Error {}

function check(condition: unknown, message: string): asserts condition {
  if (!condition) throw new PanelInputError(message);
}

function prepareSeries(series: Input["series"][number], start: bigint, end: bigint): PanelSeries {
  const samples = series.samples.map(sample => {
    const t = nanos(sample.at);
    check(t !== undefined, "A sample has an invalid Instant.");
    check(t >= start && t < end, "A sample lies outside the Timeline range.");
    const value = sample.value as NumericValue;
    return { at: sample.at, t, gap: sample.gap, text: numericText(value), y: drawingNumber(value) };
  });
  for (let i = 1; i < samples.length; i++) check(samples[i - 1]!.t <= samples[i]!.t, "Samples must be sorted by Instant.");
  const runs: PanelSample[][] = [];
  let run: PanelSample[] = [];
  let lowest: PanelSample | undefined, highest: PanelSample | undefined;
  let gaps = 0, undrawable = 0;
  const close = () => { if (run.length) runs.push(run); run = []; };
  for (const sample of samples) {
    if (sample.gap) { gaps++; close(); continue; }
    const kept: PanelSample = { at: sample.at, t: sample.t, text: sample.text, y: sample.y };
    if (kept.y === undefined) { undrawable++; close(); continue; }
    run.push(kept);
    if (lowest === undefined || kept.y < lowest.y!) lowest = kept;
    if (highest === undefined || kept.y > highest.y!) highest = kept;
  }
  close();
  let latest: Latest = samples.length === 0 ? { kind: "empty" } : { kind: "gaps-only", gaps: samples.length };
  for (let i = samples.length - 1; i >= 0; i--) {
    const sample = samples[i]!;
    if (!sample.gap) {
      latest = { kind: "value", sample: { at: sample.at, t: sample.t, text: sample.text, y: sample.y },
        trailingGaps: samples.length - 1 - i, lastAt: samples[samples.length - 1]!.at };
      break;
    }
  }
  return { id: series.id, label: series.label, unit: series.unit, runs, latest, lowest, highest, undrawable, gaps };
}

export function preparePanel(input: Input): PanelModel {
  const extent = range(input.range), coverage = range(input.coverage);
  check(extent && coverage, "The Timeline range and coverage must be Intervals.");
  const start = nanos(extent.start)!, end = nanos(extent.end)!;
  check(nanos(coverage.start)! >= start && nanos(coverage.end)! <= end, "Coverage must lie inside the Timeline range.");
  check(input.series.length <= PANEL_LIMITS.series, `At most ${PANEL_LIMITS.series} series can be shown.`);
  check(input.series.reduce((n, s) => n + s.samples.length, 0) + input.events.length <= PANEL_LIMITS.records, `At most ${PANEL_LIMITS.records} records can be shown.`);
  check(new Set(input.series.map(s => s.id)).size === input.series.length, "Series IDs must be unique.");
  return {
    title: input.title,
    range: extent,
    coverage,
    partialCoverage: coverage.start !== extent.start || coverage.end !== extent.end,
    omitted: numericText(input.omitted as NumericValue),
    sourceError: input.sourceError,
    series: input.series.map(series => prepareSeries(series, start, end)),
    events: input.events.length,
  };
}

/**
 * A compact clock reading of an Instant: `14:05:09Z`, or `14:05:09.25Z` when the Instant has a
 * fraction. Digits beyond milliseconds are shortened to `…`; callers put the full Instant in a
 * tooltip. The date is included when the range crosses midnight.
 */
export function timeLabel(at: string, withDate: boolean): string {
  const match = /^(.*)T(\d{2}:\d{2}:\d{2})(?:\.(\d+))?Z$/.exec(at);
  if (!match) return at;
  const fraction = match[3] === undefined ? "" : `.${match[3].slice(0, 3)}${match[3].length > 3 ? "…" : ""}`;
  return `${withDate ? `${match[1]} ` : ""}${match[2]}${fraction}Z`;
}

/**
 * A short reading of an exact decimal lexeme, rounded half up on its digits as text, so no value
 * passes through a lossy JS number. It keeps every integer digit and at least `significant`
 * significant digits. `approximate` is true only when the shown value differs from the exact one;
 * exponent forms and other lexemes are returned unchanged.
 */
export function compactNumber(text: string, significant = 4): { readonly shown: string; readonly approximate: boolean } {
  const parts = /^(-?)(\d+)(?:\.(\d+))?$/.exec(text);
  if (!parts || text.length > 4096) return { shown: text, approximate: false };
  const sign = parts[1]!, whole = parts[2]!.replace(/^0+(?=\d)/, ""), fraction = parts[3] ?? "";
  const digits = whole + fraction;
  const first = digits.search(/[1-9]/);
  if (first < 0) return { shown: text, approximate: false };
  const keep = Math.max(whole.length, first + significant);
  if (keep >= digits.length) return { shown: text, approximate: false };
  const kept = digits.slice(0, keep).split("").map(Number);
  if (Number(digits[keep]) >= 5) {
    let at = kept.length - 1;
    while (at >= 0 && kept[at] === 9) { kept[at] = 0; at--; }
    if (at >= 0) kept[at]! += 1; else kept.unshift(1);
  }
  const grew = kept.length - keep;
  const integer = kept.slice(0, whole.length + grew).join("") || "0";
  const decimals = kept.slice(whole.length + grew).join("").replace(/0+$/, "");
  // Dropped zeros (`1.20000`) change the text but not the value, so they are not marked approximate.
  return { shown: `${sign}${integer}${decimals ? `.${decimals}` : ""}`, approximate: /[1-9]/.test(digits.slice(keep)) };
}
