import { defineView, nanos, ratio, type TimeRange } from "@wes/view-sdk";
import { useMemo } from "react";
import { definition } from "./contract";
import { compactNumber, PanelInputError, preparePanel, timeLabel, type PanelModel, type PanelSeries } from "./model";
import "./view.css";

/** A compact reading; `≈` marks it only when it differs from the exact value. */
const short = (text: string) => { const c = compactNumber(text); return c.approximate ? `≈${c.shown}` : c.shown; };

/** Plot coordinates; strokes stay one pixel wide because they do not scale with the box. */
const WIDTH = 1000, HEIGHT = 100, PAD = 6;

/**
 * One series' trend on its own vertical scale. Series never share an axis: units may differ,
 * and one scale would make a smaller series unreadable. The vertical scale spans the true lowest
 * and highest plotted values; it is not zero-based, so a zero line is drawn only when zero lies
 * inside that span.
 */
function Trend({ series, range, coverage, height, withDate }: {
  series: PanelSeries; range: TimeRange; coverage: TimeRange; height: string; withDate: boolean;
}) {
  const low = series.lowest, high = series.highest;
  const flat = low !== undefined && high !== undefined && low.y === high.y;
  const x = (t: bigint) => ratio(t, range) * WIDTH;
  const y = (value: number) => low === undefined || high === undefined || flat ? HEIGHT / 2
    : HEIGHT - PAD - ((value - low.y!) / (high.y! - low.y!)) * (HEIGHT - 2 * PAD);
  const zero = low !== undefined && high !== undefined && !flat && low.y! < 0 && high.y! > 0 ? y(0) : undefined;
  const covered = [x(nanos(coverage.start)!), x(nanos(coverage.end)!)];
  const drawn = series.runs.reduce((n, run) => n + run.length, 0);
  const unit = series.unit ? ` ${series.unit}` : "";
  const description = drawn === 0
    ? `${series.label || series.id}: no plottable samples in this range.`
    : `${series.label || series.id}: ${drawn} plotted samples from ${range.start} until ${range.end}; `
      + (flat ? `every plotted value is ${low!.text}${unit}.` : `lowest ${low!.text}${unit} at ${low!.at}, highest ${high!.text}${unit} at ${high!.at}.`);
  const latest = series.latest.kind === "value" && series.latest.sample.y !== undefined ? series.latest.sample : undefined;
  return <figure className="prometheus-panel-trend">
    <div className="prometheus-panel-plot">
      <div className="prometheus-panel-scale" aria-hidden="true">
        {high && <span className="table-value" title={`Highest plotted ${high.text}${unit} at ${high.at}`}>{short(high.text)}</span>}
        {low && !flat && <span className="table-value" title={`Lowest plotted ${low.text}${unit} at ${low.at}`}>{short(low.text)}</span>}
      </div>
      <div className="prometheus-panel-canvas">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none" role="img" aria-label={description} style={{ height }}>
          {covered[0]! > 0 && <rect className="prometheus-panel-uncovered" x={0} y={0} width={covered[0]} height={HEIGHT} />}
          {covered[1]! < WIDTH && <rect className="prometheus-panel-uncovered" x={covered[1]} y={0} width={WIDTH - covered[1]!} height={HEIGHT} />}
          {zero !== undefined && <line className="prometheus-panel-zero" x1={0} x2={WIDTH} y1={zero} y2={zero} />}
          {series.runs.filter(run => run.length > 1).map((run, at) =>
            <polyline key={at} className="prometheus-panel-line" points={run.map(sample => `${x(sample.t)},${y(sample.y!)}`).join(" ")} />)}
        </svg>
        {/* Markers are positioned in the box, not in the stretched SVG, so they stay round at any width. */}
        {series.runs.filter(run => run.length === 1).map((run, at) =>
          <span key={at} className="prometheus-panel-marker prometheus-panel-point" aria-hidden="true"
            style={{ left: `${x(run[0]!.t) / WIDTH * 100}%`, top: `${y(run[0]!.y!) / HEIGHT * 100}%` }} />)}
        {latest && <span className="prometheus-panel-marker prometheus-panel-latest" aria-hidden="true"
          style={{ left: `${x(latest.t) / WIDTH * 100}%`, top: `${y(latest.y!) / HEIGHT * 100}%` }} />}
      </div>
    </div>
    <figcaption className="prometheus-panel-axis">
      <span className="table-time" title={range.start}>{timeLabel(range.start, withDate)}</span>
      <span className="table-time" title={`${range.end} (the range end is exclusive)`}>until {timeLabel(range.end, withDate)}</span>
    </figcaption>
  </figure>;
}

function Reading({ series, withDate, named }: { series: PanelSeries; withDate: boolean; named: boolean }) {
  const latest = series.latest;
  const name = named ? <span className="screen-label prometheus-panel-series" title={series.label || series.id}>{series.label || series.id}</span> : null;
  if (latest.kind === "empty") {
    return <div className="prometheus-panel-reading">{name}<p className="status-warn" role="status">No samples in this range.</p></div>;
  }
  if (latest.kind === "gaps-only") {
    return <div className="prometheus-panel-reading">{name}<p className="status-warn" role="status">
      No valid sample: all {latest.gaps} samples are gaps (NaN).</p></div>;
  }
  const full = `${latest.sample.text}${series.unit ? ` ${series.unit}` : ""} at ${latest.sample.at}`;
  return <div className="prometheus-panel-reading">
    {name}
    <p className="prometheus-panel-value">
      {/* A compact reading, marked ≈ when rounded; the exact value stays in the tooltip and label. */}
      <strong className="table-value" tabIndex={0} title={full} aria-label={`Latest valid sample ${full}`}>{short(latest.sample.text)}</strong>
      {series.unit && <span className="table-value prometheus-panel-unit" title={series.unit}>{series.unit}</span>}
    </p>
    <p className="table-time" title={latest.sample.at}>latest valid · {timeLabel(latest.sample.at, withDate)}</p>
    {latest.trailingGaps > 0 && <p className="status-warn" title={`Last sample at ${latest.lastAt}`}>
      {latest.trailingGaps === 1 ? "The newest sample is a gap" : `The newest ${latest.trailingGaps} samples are gaps`} (NaN); this value precedes {latest.trailingGaps === 1 ? "it" : "them"}.</p>}
  </div>;
}

function Notes({ model }: { model: PanelModel }) {
  const notes: string[] = [];
  if (model.partialCoverage) notes.push(`Data covers ${model.coverage.start} to ${model.coverage.end}; the shaded part of the range has no data.`);
  if (model.omitted !== "0") notes.push(`${model.omitted} samples were omitted by the source.`);
  const gaps = model.series.reduce((n, s) => n + s.gaps, 0);
  if (gaps > 0) notes.push(`${gaps} gap${gaps === 1 ? "" : "s"} (NaN) break the line; a gap is never drawn as zero.`);
  const undrawable = model.series.reduce((n, s) => n + s.undrawable, 0);
  if (undrawable > 0) notes.push(`${undrawable} exact value${undrawable === 1 ? " is" : "s are"} too precise to plot and break the line.`);
  if (model.events > 0) notes.push(`${model.events} event${model.events === 1 ? " is" : "s are"} not shown here; open the data with Timeline to see them.`);
  return notes.length === 0 ? null
    : <ul className="prometheus-panel-notes" tabIndex={0} aria-label="Notes about this data">{notes.map(note => <li key={note} className="screen-label">{note}</li>)}</ul>;
}

export default defineView(definition, {
  Component: ({ input, context }) => {
    const prepared = useMemo(() => {
      try { return { model: preparePanel(input) }; }
      catch (error) { return { problem: error instanceof PanelInputError ? error.message : "This Timeline value cannot be shown." }; }
    }, [input]);
    const title = input.title || "Timeline";
    const heading = <h2 className="screen-title prometheus-panel-title" tabIndex={0} title={title}>{title}</h2>;
    if (!prepared.model) {
      return <section className="prometheus-panel" aria-label={title}>{heading}<p className="status-bad" role="alert">{prepared.problem}</p></section>;
    }
    const model = prepared.model;
    const withDate = model.range.start.slice(0, 10) !== model.range.end.slice(0, 10);
    const height = context.mode === "window" ? "11rem" : context.mode === "expanded" ? "6rem" : "4rem";
    const named = model.series.length > 1;
    return <section className="prometheus-panel" aria-label={title} data-mode={context.mode}>
      {heading}
      {model.sourceError && <p className="status-bad" role="alert" title={model.sourceError}>Source problem: {model.sourceError}</p>}
      {model.series.length === 0
        ? <p className="status-warn" role="status">No series in this Timeline.</p>
        : <div className={`prometheus-panel-series-list${named ? " prometheus-panel-several" : ""}`} tabIndex={named ? 0 : undefined}
            aria-label={named ? `${model.series.length} series, each on its own scale` : undefined}>
            {model.series.map(series => <div className="prometheus-panel-body" key={series.id}>
              <Reading series={series} withDate={withDate} named={named} />
              <Trend series={series} range={model.range} coverage={model.coverage} height={height} withDate={withDate} />
            </div>)}
          </div>}
      <Notes model={model} />
    </section>;
  },
});
