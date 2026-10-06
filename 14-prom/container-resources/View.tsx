import { defineView } from "@wes/view-sdk";
import { useMemo } from "react";
import { definition } from "./contract";
import { clockLabel, coreTicks, prepareResources, ResourcesInputError, type Bytes, type Cores, type Cpu, type Memory, type ResourcesModel, type SampleModel, type Shown } from "./model";
import "./view.css";

/** Dial geometry in its own viewBox; the dial is decoration only and every value it shows is also text. */
const CX = 100, CY = 100, R = 84, TRACK = 12, OVERFLOW_START = 0.94;
const MEMORY_TICKS = [0, 0.25, 0.5, 0.75, 1] as const;

const point = (fraction: number, radius = R) => {
  const angle = Math.PI * (1 - fraction);
  return [CX + radius * Math.cos(angle), CY - radius * Math.sin(angle)] as const;
};
const arc = (from: number, to: number) => {
  const [x0, y0] = point(from), [x1, y1] = point(to);
  return `M${x0.toFixed(2)},${y0.toFixed(2)} A${R},${R} 0 0 1 ${x1.toFixed(2)},${y1.toFixed(2)}`;
};
const approx = (reading: Shown) => `${reading.approximate ? "≈" : ""}${reading.shown}`;
const bytesText = (bytes: Bytes) => `${bytes.approximate ? "≈" : ""}${bytes.number} ${bytes.unit}`;
const exactBytes = (bytes: Bytes) => `${bytes.exact} bytes`;

/**
 * A half dial. A known value fills from zero to its share of the scale and gets a marker, so a small
 * value stays locatable without being enlarged. A value above the scale fills the dial and adds a
 * dashed overflow cap; the text beside it states the exact value. Unknown leaves the track empty.
 */
function Dial({ fraction, ticks, emphasis, over }: { fraction: number | undefined; ticks: readonly number[]; emphasis?: number; over: boolean }) {
  const shown = fraction === undefined ? undefined : Math.max(0, Math.min(1, fraction));
  const [mx0, my0] = shown === undefined ? [0, 0] : point(shown, R + TRACK / 2 + 3);
  const [mx1, my1] = shown === undefined ? [0, 0] : point(shown, R - TRACK / 2 - 3);
  return <svg className="container-resources-dial" viewBox="0 0 200 106" aria-hidden="true" focusable="false">
    <path d={arc(0, 1)} className="container-resources-track" />
    {ticks.map(tick => {
      const inner = R - TRACK / 2 - (tick === emphasis ? 11 : 6), [x0, y0] = point(tick, R - TRACK / 2 - 1), [x1, y1] = point(tick, inner);
      return <line key={tick} x1={x0} y1={y0} x2={x1} y2={y1} className={tick === emphasis ? "container-resources-tick emphasis" : "container-resources-tick"} />;
    })}
    {shown !== undefined && shown > 0 && <path d={arc(0, shown)} className="container-resources-fill" />}
    {over && <path d={arc(OVERFLOW_START, 1)} className="container-resources-over" />}
    {shown !== undefined && <line x1={mx0} y1={my0} x2={mx1} y2={my1} className="container-resources-marker" />}
  </svg>;
}

function Reading({ value, unit, label, unknown }: { value: string; unit: string; label: string; unknown?: boolean }) {
  return <p className="container-resources-reading">
    <strong className={`table-value${unknown ? " container-resources-unknown" : ""}`} tabIndex={0} aria-label={label} title={label}>{value}</strong>
    {unit && <span className="table-value container-resources-unit" aria-hidden="true">{unit}</span>}
  </p>;
}

/**
 * A qualifier line: `text` is short enough for two lines in a medium-tier column, `full` is the complete
 * wording kept in the title and the reading's accessible label. Delivered reasons are never shortened.
 */
interface Qualifier { readonly text: string; readonly full: string }
const same = (text: string): Qualifier => ({ text, full: text });

function CpuMeter({ cpu, cores }: { cpu: Cpu; cores: Cores }) {
  const count = cores.kind === "known" ? cores.count : undefined;
  const maximum = cores.kind === "known" ? `${cores.maximum} %` : undefined;
  const scale: Qualifier = cores.kind === "known"
    ? {
      text: `0–${maximum}, not a quota · ${cores.text} online ${cores.count === 1 ? "CPU" : "CPUs"} (Docker)`,
      full: `0–${maximum} · ${cores.text} online ${cores.count === 1 ? "CPU" : "CPUs"} reported by Docker, not a quota`,
    }
    : same(`No scale: ${cores.reason}`);
  let note = same("");
  if (cpu.kind === "unknown") note = same(cpu.reason);
  else if (cpu.aboveScale) note = { text: `Above the ${maximum} scale; dial full, exact value shown.`, full: `Above the ${maximum} scale; the dial is full and the exact value is shown.` };
  else if (cpu.fraction === undefined && count !== undefined) note = { text: "Too precise to place on the dial.", full: "The exact value is too precise to place on the dial." };
  else if (cpu.aboveOneCore) note = { text: "Over one core; valid when multi-threaded.", full: "More than one core in use; valid for a multi-threaded process." };
  const label = cpu.kind === "value"
    ? [`CPU ${cpu.reading.exact} % of one core`, scale.full, note.full].filter(Boolean).join(" · ")
    : `CPU unknown: ${cpu.reason}`;
  return <figure className="container-resources-meter">
    <figcaption className="screen-label container-resources-caption">CPU · 100 % = one core</figcaption>
    <div className="container-resources-face">
      <Dial fraction={cpu.kind === "value" ? cpu.fraction : undefined} over={cpu.kind === "value" && cpu.aboveScale}
        ticks={count === undefined ? [] : coreTicks(count)} emphasis={count !== undefined && count > 1 ? 1 / count : undefined} />
      <span className="table-time container-resources-end start" aria-hidden="true">0</span>
      <span className="table-time container-resources-end" aria-hidden="true" title={maximum}>{maximum ?? "no scale"}</span>
      {cpu.kind === "value"
        ? <Reading value={approx(cpu.reading)} unit="%" label={label} />
        : <Reading value="Unknown" unit="" label={label} unknown />}
    </div>
    <p className="screen-label container-resources-line" title={scale.full}>{scale.text}</p>
    <p className={`container-resources-line${note.text && cpu.kind === "unknown" ? " status-warn" : " screen-label"}`} title={note.full || undefined}>{note.text}</p>
  </figure>;
}

function MemoryMeter({ memory }: { memory: Memory }) {
  const { workingSet, limit, noBasis, share } = memory;
  const scale: Qualifier = limit && noBasis === undefined
    ? { text: `0–100 % of ${bytesText(limit)} limit (Docker)`, full: `0–100 % of ${bytesText(limit)}, the limit Docker reports` }
    : same(`No scale: ${noBasis}`);
  let note: Qualifier = { text: "No limit set: Docker reports the memory available.", full: "With no limit set, Docker reports the memory available to it." };
  if (share.kind === "unknown") note = same(share.reason);
  else if (noBasis !== undefined) note = { text: "No known limit: share as delivered, not on a dial.", full: "Share shown as delivered; with no known limit it is not placed on a dial." };
  else if (share.aboveLimit) note = { text: "Above the reported limit; dial full, exact value shown.", full: "Above the reported limit; the dial is full and the exact value is shown." };
  else if (share.fraction === undefined) note = { text: "Too precise to place on the dial.", full: "The exact share is too precise to place on the dial." };
  const title = [workingSet && `Working set ${exactBytes(workingSet)}`, limit && `Limit ${exactBytes(limit)}`, memory.cacheSource && `Working set = usage minus ${memory.cacheSource}`].filter(Boolean).join(" · ");
  const label = share.kind === "unknown" ? `Memory unknown: ${share.reason}`
    : [noBasis === undefined ? `Memory working set ${share.reading.exact} % of the reported limit` : `Memory working set ${share.reading.exact} % as delivered; no known limit`,
      scale.full, limit && `Limit ${exactBytes(limit)}`, note.full].filter(Boolean).join(" · ");
  const caption = `Memory working set${workingSet ? ` · ${bytesText(workingSet)}` : ""}`;
  return <figure className="container-resources-meter">
    <figcaption className="screen-label container-resources-caption" title={title || undefined}>{caption}</figcaption>
    <div className="container-resources-face">
      <Dial fraction={share.kind === "value" ? share.fraction : undefined} over={share.kind === "value" && share.aboveLimit} ticks={noBasis === undefined ? MEMORY_TICKS : []} />
      <span className="table-time container-resources-end start" aria-hidden="true">0</span>
      <span className="table-time container-resources-end" aria-hidden="true" title={limit ? exactBytes(limit) : undefined}>{limit && noBasis === undefined ? bytesText(limit) : "no limit"}</span>
      {share.kind === "value"
        ? <Reading value={approx(share.reading)} unit="%" label={label} />
        : <Reading value="Unknown" unit="" label={label} unknown />}
    </div>
    <p className="screen-label container-resources-line" title={scale.full}>{scale.text}</p>
    <p className={`container-resources-line${share.kind === "unknown" ? " status-warn" : " screen-label"}`} title={note.full}>{note.text}</p>
  </figure>;
}

function SampleFacts({ sample }: { sample: SampleModel }) {
  return <div className="container-resources-sample">
    <dl className="container-resources-facts">
      <div><dt className="screen-label">Docker sample time</dt>
        <dd className="table-time" title={sample.sampledAt ?? undefined}>{sample.sampledAt ? clockLabel(sample.sampledAt) : "not supplied by Docker"}</dd></div>
      <div><dt className="screen-label">Received by Wes</dt>
        <dd className="table-time" title={sample.receivedAt}>{clockLabel(sample.receivedAt)}</dd></div>
      <div><dt className="screen-label">Stream sequence</dt>
        <dd className="table-value">{sample.sequence}</dd></div>
    </dl>
    <p className="screen-label container-resources-line">Latest sample delivered to this view. It never polls or refreshes.</p>
  </div>;
}

/** Preview: three bounded lines; values, units and reasons stay text with the exact value in titles. */
function PreviewLines({ sample }: { sample: SampleModel }) {
  const { cpu, cores, memory } = sample;
  const scale = cores.kind === "known" ? `of ${cores.maximum} % · ${cores.text} online ${cores.count === 1 ? "CPU" : "CPUs"} · 100 % = one core` : "100 % = one core · no scale";
  return <div className="container-resources-preview">
    <p><span className="screen-label">CPU</span>
      {cpu.kind === "value"
        ? <><strong className="table-value" title={`${cpu.reading.exact} %`}>{approx(cpu.reading)} %</strong><span className="screen-label" title={scale}>{scale}</span></>
        : <span className="status-warn" title={cpu.reason}>Unknown · {cpu.reason}</span>}</p>
    <p><span className="screen-label">Memory</span>
      {memory.share.kind === "value"
        ? <><strong className="table-value" title={`${memory.share.reading.exact} %`}>{approx(memory.share.reading)} %</strong>
          {memory.limit && memory.noBasis === undefined
            ? <span className="screen-label" title={exactBytes(memory.limit)}>{memory.workingSet ? `${bytesText(memory.workingSet)} of ` : "of "}{bytesText(memory.limit)} reported limit</span>
            : <span className="screen-label" title={memory.noBasis}>{memory.workingSet ? `${bytesText(memory.workingSet)} · ` : ""}as delivered · no known limit</span>}</>
        : <span className="status-warn" title={memory.share.reason}>Unknown · {memory.share.reason}</span>}</p>
    <p className="table-time" title={sample.sampledAt ?? sample.receivedAt}>sample {sample.sampledAt ? clockLabel(sample.sampledAt) : `received ${clockLabel(sample.receivedAt)}`} · #{sample.sequence}</p>
  </div>;
}

function Body({ model, preview }: { model: ResourcesModel; preview: boolean }) {
  const sample = model.sample;
  if (!sample) {
    return <p className="status-warn container-resources-waiting" role="status">
      No stats sample yet. The view shows a reading once the source delivers its first sample; it does not start or poll the source.</p>;
  }
  if (preview) return <PreviewLines sample={sample} />;
  return <div className="container-resources-body">
    <CpuMeter cpu={sample.cpu} cores={sample.cores} />
    <MemoryMeter memory={sample.memory} />
    <SampleFacts sample={sample} />
  </div>;
}

export default defineView(definition, {
  Component: ({ input, context }) => {
    const prepared = useMemo(() => {
      try { return { model: prepareResources(input) }; }
      catch (error) { return { problem: error instanceof ResourcesInputError ? error.message : "This container resource value cannot be shown." }; }
    }, [input]);
    const title = input.label || "Container resources";
    return <section className="container-resources" data-mode={context.mode} aria-label={`Container resources · ${title}`}>
      <header className="container-resources-head">
        <h2 className="screen-title container-resources-title" tabIndex={0} title={title}>{title}</h2>
        <span className="table-key container-resources-id" title={`Container ${input.container}`}>{input.container.slice(0, 12)}</span>
      </header>
      {prepared.model
        ? <Body model={prepared.model} preview={context.mode === "preview"} />
        : <p className="status-bad" role="alert" title={prepared.problem}>{prepared.problem}</p>}
    </section>;
  },
});
