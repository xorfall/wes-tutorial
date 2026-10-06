import { compareNumeric, drawingNumber, nanos, numericText, type NumericValue } from "@wes/view-sdk";
import type { Input } from "./contract";

type Sample = NonNullable<Input["sample"]>;

export class ResourcesInputError extends Error {}

function check(condition: unknown, message: string): asserts condition {
  if (!condition) throw new ResourcesInputError(message);
}

/** A display reading. `exact` is the source lexeme; `approximate` is true only when `shown` differs in value. */
export interface Shown { readonly shown: string; readonly exact: string; readonly approximate: boolean }

/**
 * Rounds an exact decimal lexeme half up to `places` decimals on its digits as text, so no value
 * passes through a lossy JS number. Trailing zeros are dropped. Exponent forms are returned unchanged.
 */
export function decimalShown(text: string, places: number): Shown {
  const parts = /^(-?)(\d+)(?:\.(\d+))?$/.exec(text);
  if (!parts || text.length > 4096) return { shown: text, exact: text, approximate: false };
  const sign = parts[1]!, whole = parts[2]!.replace(/^0+(?=\d)/, ""), fraction = parts[3] ?? "";
  if (fraction.length <= places) {
    const decimals = fraction.replace(/0+$/, "");
    return { shown: `${sign}${whole}${decimals ? `.${decimals}` : ""}`, exact: text, approximate: false };
  }
  const kept = (whole + fraction.slice(0, places)).split("").map(Number);
  if (Number(fraction[places]) >= 5) {
    let at = kept.length - 1;
    while (at >= 0 && kept[at] === 9) { kept[at] = 0; at--; }
    if (at >= 0) kept[at]! += 1; else kept.unshift(1);
  }
  const integerLength = kept.length - places;
  const integer = kept.slice(0, integerLength).join("") || "0";
  const decimals = kept.slice(integerLength).join("").replace(/0+$/, "");
  return { shown: `${sign}${integer}${decimals ? `.${decimals}` : ""}`, exact: text, approximate: /[1-9]/.test(fraction.slice(places)) };
}

/** Percentages keep two decimals below 100 and one from 100; the exact lexeme stays available. */
export function percentShown(value: NumericValue): Shown {
  const text = numericText(value);
  return decimalShown(text, compareNumeric(value, "100") < 0 ? 2 : 1);
}

const BYTE_UNITS = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB"] as const;

export interface Bytes {
  readonly number: string;
  readonly unit: string;
  readonly exact: string;
  readonly approximate: boolean;
  /** Absent when the exact count cannot be converted to a JS number without loss. */
  readonly drawing: number | undefined;
}

/** IEC units for display; the exact byte count is kept for titles and accessible text. */
export function bytesShown(value: NumericValue): Bytes {
  const exact = numericText(value), n = drawingNumber(value);
  if (n === undefined || !Number.isSafeInteger(n)) return { number: exact, unit: "B", exact, approximate: false, drawing: undefined };
  let unit = 0;
  while (unit < BYTE_UNITS.length - 1 && n >= 1024 ** (unit + 1)) unit++;
  if (unit === 0) return { number: String(n), unit: "B", exact, approximate: false, drawing: n };
  const scaled = n / 1024 ** unit, rounded = Math.round(scaled * 100) / 100;
  const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(rounded);
  return { number, unit: BYTE_UNITS[unit]!, exact, approximate: rounded * 1024 ** unit !== n, drawing: n };
}

/** `14:05:09Z`, or `14:05:09.123Z`; digits beyond milliseconds become `…`. Callers keep the full Instant in a title. */
export function clockLabel(at: string): string {
  const match = /T(\d{2}:\d{2}:\d{2})(?:\.(\d+))?Z$/.exec(at);
  if (!match) return at;
  const fraction = match[2] === undefined ? "" : `.${match[2].slice(0, 3)}${match[2].length > 3 ? "…" : ""}`;
  return `${match[1]}${fraction}Z`;
}

export type Cores =
  /** `maximum` is count × 100 %, checked to be an exact JS integer before it is drawn or compared. */
  | { readonly kind: "known"; readonly count: number; readonly text: string; readonly maximum: number }
  | { readonly kind: "unknown"; readonly reason: string };

export type Cpu =
  | { readonly kind: "unknown"; readonly reason: string }
  | {
    readonly kind: "value";
    readonly reading: Shown;
    /** Share of the drawn scale (online CPUs × 100 %), for geometry only; never shown as a number. */
    readonly fraction: number | undefined;
    /** The exact value exceeds online CPUs × 100 %; the dial is full and says so. */
    readonly aboveScale: boolean;
    /** The exact value exceeds one core (100 %), which is valid for a multi-threaded process. */
    readonly aboveOneCore: boolean;
  };

export type MemoryShare =
  | { readonly kind: "unknown"; readonly reason: string }
  /** `fraction` is undefined whenever the memory has no basis, so a delivered share is never placed against an unknown limit. */
  | { readonly kind: "value"; readonly reading: Shown; readonly fraction: number | undefined; readonly aboveLimit: boolean };

export interface Memory {
  readonly workingSet: Bytes | undefined;
  readonly limit: Bytes | undefined;
  /** Why there is no positive byte limit to draw a share against; undefined when the limit is known and positive. */
  readonly noBasis: string | undefined;
  readonly share: MemoryShare;
  readonly cacheSource: string | null;
}

export interface SampleModel {
  readonly sequence: string;
  readonly sampledAt: string | null;
  readonly receivedAt: string;
  readonly cores: Cores;
  readonly cpu: Cpu;
  readonly memory: Memory;
}

export interface ResourcesModel {
  readonly label: string;
  readonly container: string;
  readonly sample: SampleModel | undefined;
}

function cores(sample: Sample): Cores {
  if (sample.onlineCpus === null) return { kind: "unknown", reason: "The input has no online CPU count." };
  const text = numericText(sample.onlineCpus), count = drawingNumber(sample.onlineCpus);
  if (count === undefined || !Number.isSafeInteger(count)) return { kind: "unknown", reason: `Online CPU count ${text} is too large to draw a scale.` };
  if (count < 1) return { kind: "unknown", reason: `Docker reported ${text} online CPUs; no scale can be drawn.` };
  const maximum = count * 100;
  if (!Number.isSafeInteger(maximum)) return { kind: "unknown", reason: `Online CPU count ${text} is too large to state its ${text} × 100 % scale exactly.` };
  return { kind: "known", count, text, maximum };
}

function cpu(sample: Sample, scale: Cores): Cpu {
  check(sample.cpuPercent === null || sample.cpuUnavailable === null, "The CPU reading has both a value and an unavailability reason.");
  if (sample.cpuPercent === null) {
    return { kind: "unknown", reason: sample.cpuUnavailable ?? "The input supplies neither a CPU value nor a reason." };
  }
  const value = sample.cpuPercent;
  check(compareNumeric(value, "0") >= 0, "The CPU percentage is negative.");
  const drawing = drawingNumber(value);
  const maximum = scale.kind === "known" ? scale.maximum : undefined;
  return {
    kind: "value",
    reading: percentShown(value),
    fraction: drawing === undefined || maximum === undefined ? undefined : drawing / maximum,
    aboveScale: maximum !== undefined && compareNumeric(value, String(maximum)) > 0,
    aboveOneCore: compareNumeric(value, "100") > 0,
  };
}

function memory(sample: Sample): Memory {
  check(sample.memoryPercent === null || sample.memoryUnavailable === null, "The memory reading has both a value and an unavailability reason.");
  const workingSet = sample.memoryWorkingSetBytes === null ? undefined : bytesShown(sample.memoryWorkingSetBytes);
  const limit = sample.memoryLimitBytes === null ? undefined : bytesShown(sample.memoryLimitBytes);
  // An unsafe but positive limit (cgroup v1 "unlimited") is still an exact basis; only a missing or zero limit is not.
  const noBasis = sample.memoryLimitBytes === null ? "The input has no memory limit."
    : compareNumeric(sample.memoryLimitBytes, "0") > 0 ? undefined
    : `Docker reported a ${numericText(sample.memoryLimitBytes)}-byte memory limit.`;
  let share: MemoryShare;
  if (sample.memoryPercent === null) {
    share = { kind: "unknown", reason: sample.memoryUnavailable ?? "The input supplies neither a memory share nor a reason." };
  } else {
    const value = sample.memoryPercent;
    check(compareNumeric(value, "0") >= 0, "The memory percentage is negative.");
    const drawing = noBasis === undefined ? drawingNumber(value) : undefined;
    share = { kind: "value", reading: percentShown(value), fraction: drawing === undefined ? undefined : drawing / 100, aboveLimit: noBasis === undefined && compareNumeric(value, "100") > 0 };
  }
  return { workingSet, limit, noBasis, share, cacheSource: sample.memoryCacheSource };
}

export function prepareResources(input: Input): ResourcesModel {
  // The contract fixes only the length; the full lowercase hex identity is checked here.
  check(/^[0-9a-f]{64}$/.test(input.container), "The container identity must be a full 64-character Docker ID.");
  const sample = input.sample;
  if (sample === null) return { label: input.label, container: input.container, sample: undefined };
  check(nanos(sample.receivedAt) !== undefined, "The receive time is not a valid Instant.");
  check(sample.sampledAt === null || nanos(sample.sampledAt) !== undefined, "The Docker sample time is not a valid Instant.");
  check(compareNumeric(sample.sequence, "0") >= 0, "The sample sequence is negative.");
  const scale = cores(sample);
  return {
    label: input.label,
    container: input.container,
    sample: {
      sequence: numericText(sample.sequence),
      sampledAt: sample.sampledAt,
      receivedAt: sample.receivedAt,
      cores: scale,
      cpu: cpu(sample, scale),
      memory: memory(sample),
    },
  };
}

/** Core ticks: every core up to 16, otherwise a whole-core step that keeps at most 16 ticks. */
export function coreTicks(count: number): readonly number[] {
  const step = count <= 16 ? 1 : Math.ceil(count / 16);
  const ticks: number[] = [];
  for (let core = 0; core <= count; core += step) ticks.push(core / count);
  if (ticks[ticks.length - 1] !== 1) ticks.push(1);
  return ticks;
}
