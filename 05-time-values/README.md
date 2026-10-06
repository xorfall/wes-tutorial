# 5. Time values

This chapter covers the three time types of wes: `Instant` (a moment),
`Duration` (a length of time) and `Interval` (a span between two moments). It
covers creating and converting them, calculating with them, and showing a
series of measurements on a timeline.

The example investigates a deployment of orders-api: how soon after
the deployment the first error occurred, which requests fall into the
observation window, and how latency changed around the deployment.

## Prerequisites

- Chapters [1](../01-first-calculations/README.md) to
  [4](../04-iterators-and-text/README.md), in particular records, `sortBy`,
  `filter` and `iter.captures`.
- Running the programs requires a local build of wes; see
  [Run the programs](#run-the-programs).

## The three time types

| Type | Written as | Example |
| --- | --- | --- |
| `Instant` | `instant("ISO 8601 timestamp")` | `instant("2026-09-28T14:30:00Z")` |
| `Duration` | `duration("ISO 8601 duration")` | `duration("PT10M")` |
| `Interval` | `interval(start, end)` or `around(center, radius)` | `interval($a, $b)` |

All three are exact: an `Instant` has nanosecond precision, and no calculation
rounds. wes never reads the current time: every instant in a calculation comes
from its input, so repeating a calculation gives the same result.

## Part 1: Instants, durations and intervals

The first animation shows steps 1–3, followed by a duration that wes rejects.

![WesDesk creating the deployment instant 2026-09-28T14:30:00Z from a
timestamp with a +03:00 offset, a ten-minute duration, the end of the
observation window, the time to the first error (PT1M5S), a comparison, a
quarter of the window (PT2M30S), and a failed duration written as
"5m"](05a-instants-and-durations.gif)

### Step 1: Instants

The deployment started at 17:30 local time in a UTC+3 time zone:

```text
:calc { return instant("2026-09-28T17:30:00+03:00"); } > deployedAt
```

```text
✓ $deployedAt   Instant
2026-09-28T14:30:00Z
```

- The text must be a complete ISO 8601 timestamp: date, `T`, time, and a time
  zone, either `Z` (UTC) or an offset such as `+03:00`. Fractions of a second
  are allowed up to nanoseconds: `2026-09-28T14:30:00.123456789Z`.
- An `Instant` is a moment, not a local time. wes stores and shows it in UTC:
  `17:30:00+03:00` and `14:30:00Z` are the same instant, and `==` between them
  is `true`.
- A timestamp without a time zone or with a space instead of `T` fails when the
  calculation runs, and the message states the expected form:
  `CAL016: invalid timestamp or duration: expected ISO date and time with T and
  an explicit Z or UTC offset, for example 2026-01-02T03:04:05Z; at most 9
  fractional digits`.
- A timestamp in the right form with an impossible value, such as
  `2026-02-30T00:00:00Z`, fails with a different reason: `invalid calendar date,
  time, UTC offset or supported year range; check month/day (including leap
  years), time and offset`.

### Step 2: Durations

Watch the service for ten minutes after the deployment:

```text
:calc { return duration("PT10M"); } > watchFor
```

```text
✓ $watchFor   Duration
PT10M
```

A duration is written in ISO 8601 format: `P` starts it, `T` separates days
from time, and each number has a unit letter.

| Text | Length |
| --- | --- |
| `PT30S` | 30 seconds |
| `PT1.5S` | 1.5 seconds |
| `PT5M` | 5 minutes |
| `PT1H30M` | 1 hour 30 minutes |
| `P1D` | 1 day, shown as `PT24H` |
| `-PT5M` | minus 5 minutes |

- Months and years are not durations, because their length varies.
  Shorthands such as `"5m"` or `"300s"` are not accepted either; there are no
  implicit units. Both fail with `CAL016: invalid timestamp or duration:
  expected ISO duration such as PT5M or -PT1.5S (days/hours/minutes/seconds, at
  most 9 fractional digits); calendar months, years and shorthand such as 5m are
  unsupported`.

### Step 3: Arithmetic and comparison

| Operation | Result |
| --- | --- |
| `Instant + Duration`, `Instant - Duration` | `Instant` |
| `Instant - Instant` | `Duration` |
| `Duration + Duration`, `Duration - Duration` | `Duration` |
| `Duration * number`, `Duration / number` | `Duration` |
| `Duration / Duration` | `Decimal` |
| `<`, `<=`, `>`, `>=`, `==` on two instants or two durations | `Bool` |

Compute the end of the observation window, the time between the deployment and
the first error, whether the error came within five minutes, and a check
interval of a quarter of the window:

```text
:calc { return $deployedAt + $watchFor; } > watchEnd
:calc {
  return instant("2026-09-28T14:31:05Z") - $deployedAt;
} > firstErrorIn
:calc { return $firstErrorIn < duration("PT5M"); } > fastFailure
:calc { return $watchFor / 4; } > checkEvery
```

The results are `2026-09-28T14:40:00Z`, `PT1M5S`, `true` and `PT2M30S`.

- Subtracting a later instant from an earlier one gives a negative duration:
  `$deployedAt - instant("2026-09-28T14:31:05Z")` is `-PT1M5S`.
- A number is an `Int` or a `Decimal`: `duration("PT10M") * 1.5` is `PT15M`.
- Scaling is exact and never rounds. A duration has nanosecond precision, so a
  result that is not a whole number of nanoseconds fails:
  `duration("PT10S") / 3` fails with `CAL005: duration division requires exact
  nanoseconds; for explicit rounding use durationNanos(roundDiv(toNanos(total),
  count, 0))`. See [Dividing durations unevenly](#dividing-durations-unevenly).
- `duration("PT10M") / duration("PT2M30S")` is the `Decimal` `4`: how many times
  one duration fits into the other. It follows the division rules of chapter 2:
  `duration("PT1M5S") / duration("PT10M")` has no finite decimal result and
  fails with `CAL005: division is nonterminating; use roundDiv(toNanos(a),
  toNanos(b), scale) for an explicitly rounded Duration ratio`.
- A number is not a duration: `$deployedAt + 60` fails before running with
  `CAL004: invalid temporal operation: Instant add Int`. Step 5 shows how to
  turn a number into a duration.

### Step 4: Intervals

The second animation shows steps 4 and 5, after defining the instants of steps
1–3 again.

![WesDesk defining the deployment, the window and the first error, then two
intervals, their length of PT10M, and a record of epoch seconds, seconds to the
first error (65) and the UTC hour (14)](05b-intervals-and-numbers.gif)


An `Interval` is the span from a start instant up to, but not including, an end
instant. Create the observation window, and a window of five minutes on each
side of the deployment:

```text
:calc { return interval($deployedAt, $watchEnd); } > watchWindow
:calc { return around($deployedAt, duration("PT5M")); } > deployWindow
:calc { return $watchWindow.end - $watchWindow.start; } > watchLength
```

```text
✓ $watchWindow   Interval
2026-09-28T14:30:00Z/2026-09-28T14:40:00Z
✓ $deployWindow   Interval
2026-09-28T14:25:00Z/2026-09-28T14:35:00Z
✓ $watchLength   Duration
PT10M
```

- An interval is shown as `start/end`. `.start` and `.end` read its instants;
  their difference is its length.
- The start belongs to the interval and the end does not. A moment `t` is
  inside when `t >= window.start && t < window.end`. Two adjacent intervals,
  such as 14:30–14:40 and 14:40–14:50, therefore never share a moment.
- `interval(at, at)` is an empty interval.
- The start must not be later than the end:
  `CAL005: invalid timestamp or duration: interval start must not exceed end`.
- The radius of `around` must be positive:
  `CAL005: invalid timestamp or duration: interval radius must be positive`.

### Step 5: Numbers and calendar fields

Other systems describe time with numbers: seconds since 1970-01-01T00:00:00Z
(the Unix epoch), a timeout in seconds, or the hour of the day. Convert the
deployment and the time to the first error:

```text
:calc {
  return {
    seconds:     int(toEpochSeconds($deployedAt)),
    fromMillis:  fromEpochMillis(1790605865000),
    errorAfterS: int(toSeconds($firstErrorIn)),
    deployHour:  utcParts($deployedAt).hour,
  };
} > timeNumbers
```

```text
✓ $timeNumbers   { seconds, fromMillis, errorAfterS, +1 }   4 fields
seconds      1790605800
fromMillis   2026-09-28T14:31:05Z
errorAfterS  65
deployHour   14
```

| Conversion | Operations | Result |
| --- | --- | --- |
| number → `Instant` | `fromEpochSeconds`, `fromEpochMillis`, `fromEpochNanos` | `Instant` |
| `Instant` → number | `toEpochSeconds`, `toEpochMillis`, `toEpochNanos` | `Decimal` |
| number → `Duration` | `durationSeconds`, `durationMillis`, `durationNanos` | `Duration` |
| `Duration` → number | `toSeconds`, `toMillis`, `toNanos` | `Decimal` |
| `Instant` → calendar fields | `utcParts` | record of `Int` |

- The operations that take a number accept an `Int` or a `Decimal`:
  `fromEpochSeconds(1790000000.5)` keeps the half second, and
  `durationSeconds(1.5)` is `PT1.5S`. A value with more precision than a
  nanosecond fails instead of being rounded.
- The operations that return a number return an exact `Decimal`:
  `toEpochSeconds($deployedAt)` is `1790605800.000000000` and
  `toSeconds(duration("PT1M30S"))` is `90.000000000`, with nine decimal places.
  The client and the command line show them without the trailing zeros, as
  `1790605800` and `90`; `--json` and `text(…)` keep them (chapter 2).
  Convert with `int` when a whole number is needed; `int` fails if the value
  has a fraction (chapter 2).
- `utcParts(t)` returns `year`, `month`, `day`, `hour`, `minute`, `second`,
  `nanosecond` and `weekday` (1 for Monday to 7 for Sunday). The fields are
  always in UTC: the deployment at 17:30+03:00 has `hour` 14.
- An `Instant` has no fields of its own: `$deployedAt.hour` fails before running
  with `CAL004: field 'hour' is absent on Instant; use utcParts(instant) for UTC
  calendar fields`. A field of a `Duration`, such as `.seconds`, points to the
  unit conversions instead: `use toSeconds/toMillis/toNanos(duration) for
  explicit units`.

## Part 2: Timestamps from logs and the timeline

The third animation shows steps 6 and 7: parsing request timestamps from a
log, selecting the errors inside the observation window, and a timeline of
latency with the deployment marked.

![WesDesk parsing seven checkout requests from a log into a table sorted by
time, listing the errors in the observation window as PT1M5S and PT3M40S after
the deployment, and drawing a latency timeline from 14:25 to 14:45 in which
latency rises from about 200 ms to 1250 ms after the deployment marker at
14:30](05c-logs-and-timeline.gif)

### Step 6: Timestamps from logs

A log of checkout requests has one line per request: timestamp, method, path,
status and duration in milliseconds. One line arrived out of order:

```text
:calc {
  return "2026-09-28T14:26:10Z GET /checkout 200 180\n"
    + "2026-09-28T14:28:45Z GET /checkout 200 210\n"
    + "2026-09-28T14:31:05Z POST /checkout 503 1250\n"
    + "2026-09-28T14:29:30Z GET /checkout 200 190\n"
    + "2026-09-28T14:33:40Z POST /checkout 500 990\n"
    + "2026-09-28T14:36:15Z GET /checkout 200 240\n"
    + "2026-09-28T14:41:50Z GET /checkout 200 205\n";
} > checkoutLog
```

Parse the lines into records with `iter.captures` (chapter 4), turn the
timestamp text into an `Instant`, and sort by time:

```text
:calc {
  return iter.captures(
      $checkoutLog,
      "(?m)^(\\S+) \\S+ \\S+ ([0-9]{3}) ([0-9]+)$"
    )
    .map(found => {
      const groups = found.groups.map(group => unwrapOr(group, ""));
      return {
        at:         instant(groups[0]),
        status:     int(groups[1]),
        durationMs: int(groups[2]),
      };
    })
    .collect()
    .sortBy(request => request.at);
} > requests
```

```text
✓ $requests   List<{ at, status, durationMs }>   7 rows

  at                     status  durationMs
  2026-09-28T14:26:10Z      200         180
  2026-09-28T14:28:45Z      200         210
  2026-09-28T14:29:30Z      200         190
  2026-09-28T14:31:05Z      503        1250
  2026-09-28T14:33:40Z      500         990
  2026-09-28T14:36:15Z      200         240
  2026-09-28T14:41:50Z      200         205
```

`\\S+` matches a run of characters other than whitespace. Instants are valid
`sortBy` keys, so the out-of-order line moves into place.

List how long after the deployment each server error inside the observation
window occurred:

```text
:calc {
  return $requests
    .filter(request => request.at >= $watchWindow.start
      && request.at < $watchWindow.end
      && request.status >= 500)
    .map(request => request.at - $deployedAt);
} > errorsAfter
```

The result is `["PT1M5S", "PT3M40S"]`, a `List<Duration>`.

### Step 7: The timeline

A record with `view: "timeline"` is shown as a timeline chart in the client.
Draw the latency of each request, and mark the deployment:

```text
:calc {
  const span = interval(
    instant("2026-09-28T14:25:00Z"),
    instant("2026-09-28T14:45:00Z")
  );
  return {
    view:        "timeline",
    id:          "checkout",
    title:       "Checkout latency",
    range:       span,
    coverage:    span,
    omitted:     0,
    sourceError: "",
    series: [{
      id:      "latency",
      label:   "latency",
      unit:    "ms",
      samples: $requests.map(request => ({
        id:    text(request.at),
        at:    request.at,
        value: decimal(request.durationMs),
        gap:   false,
      })),
    }],
    events: [{
      id:     "deploy",
      at:     $deployedAt,
      label:  "deploy v2.4.1",
      detail: "orders-api rollout",
    }],
  };
} > timeline
```

The client draws the latency line from 14:25 to 14:45 and marks the deployment
at 14:30. Pointing at the marker, or moving the keyboard focus to it, shows its
label `deploy v2.4.1`; labels are not drawn permanently, so that dense events do
not cover the line. The buttons above the chart, `Fit`, `-`, `+`, `←`, `→` and
`Zoom to selection`, zoom and move it; the `w timeline` key opens the timeline
in a wide view.

| Field | Meaning |
| --- | --- |
| `range` | the span the chart shows |
| `coverage` | the span the data describes; the same as `range` here |
| `omitted` | the number of samples left out by the data source, `0` here |
| `sourceError` | a message from the data source, empty here |
| `series` | lines to draw: each has an `id`, a `label`, a `unit` and `samples` |
| `samples` | points: a unique `id`, the instant `at`, a `Decimal` `value`, and `gap: true` to break the line before the point |
| `events` | markers: a unique `id`, the instant `at`, a `label` and a `detail` |

- Samples and events must be sorted by `at`, and their `id` values must be
  unique. `$requests` is already sorted.
- The timeline always shows UTC.
- A timeline can hold at most 8 series. Up to 8 timelines can be combined into
  one record with `view: "timeline-group"` to share zoom and selection; all
  members together hold at most 20,000 samples and events and 4 MiB of data.
- The value must be a `Decimal`: `decimal(request.durationMs)` converts the
  `Int` duration.
- The calculation calls its interval `span` rather than `range`, so that the
  operation `range` stays available in it (chapter 3).

## Watch out

### Dividing durations unevenly

A mean latency divides a total duration by a number of requests, and the result
is rarely a whole number of nanoseconds. `roundDiv` (chapter 2) works on
numbers, not durations, so convert to nanoseconds, round, and convert back, as
the message of step 3 suggests:

```text
:calc {
  const total = duration("PT10S");
  return durationNanos(roundDiv(toNanos(total), 3, 0));
} > meanLatency
```

The result is `PT3.333333333S`: rounded to whole nanoseconds. Another unit
states another precision: `durationMillis(roundDiv(toMillis(total), 3, 0))` is
`PT3.333S`. The same pattern gives a ratio that does not terminate:
`roundDiv(toNanos(duration("PT1M5S")), toNanos(duration("PT10M")), 3)` is
`0.108`.

### Calendar arithmetic

wes has no time zones other than UTC and no month arithmetic: there is no
"add one month" and no local hour. `utcParts` reads UTC fields; group by hour
with `utcParts(t).hour` together with the date fields.

### Endpoints from other systems

Many APIs treat the end of a requested time range as included. wes intervals
never include their end. When data comes from such an API, filter the returned
records with `t >= window.start && t < window.end` before combining them with
other intervals, so that a record exactly at the end is not counted twice.

### Failures in this chapter

| Error | Cause | Found |
| --- | --- | --- |
| `CAL004` invalid temporal operation: Instant add Int | a number added to an instant | before running |
| `CAL004` field … is absent on Instant | a calendar field such as `.hour` | before running |
| `CAL016` invalid timestamp or duration: expected ISO … | a malformed timestamp or duration, a month or year duration, a unit shorthand | while running |
| `CAL016` invalid calendar date, time, UTC offset … | an impossible date or time | while running |
| `CAL005` duration division requires exact nanoseconds | a duration divided into parts that are not whole nanoseconds | while running |
| `CAL005` division is nonterminating | a ratio of two durations without a finite decimal result | while running |
| `CAL005` interval start must not exceed end | `interval` with the end before the start | while running |
| `CAL005` interval radius must be positive | `around` with a zero or negative radius | while running |

## Run the programs

From the repository root, after building wes as described in
[chapter 1](../01-first-calculations/README.md#run-the-programs):

```sh
$WES --home /tmp/wes-tutorial-05 --file 05-time-values/main.wes
python3 05-time-values/check.py
```

- `main.wes` contains the log and steps 1–7. The command line prints the
  timeline record as JSON; the chart appears in the client.
- `edge-cases.wes` contains the smaller examples: end-of-day notation,
  nanoseconds, offsets, normalised durations, an empty interval, epoch
  decimals, duration conversions, a duration ratio, the rounded mean latency, a
  negative duration and hour grouping.
- `failures/` contains one program per documented failure.
- `check.py` runs all of them and verifies every value and error in this
  chapter.

## Summary

| Concept | Syntax |
| --- | --- |
| Instant | `instant("2026-09-28T14:30:00Z")` |
| Duration | `duration("PT10M")` |
| Interval | `interval(start, end)`, `around(center, radius)`, `.start`, `.end` |
| Arithmetic | `instant ± duration`, `instant - instant`, `duration ± duration`, `duration * n`, `duration / n`, `duration / duration` |
| Epoch in | `fromEpochSeconds(n)`, `fromEpochMillis(n)`, `fromEpochNanos(n)` |
| Epoch out | `toEpochSeconds(t)`, `toEpochMillis(t)`, `toEpochNanos(t)` |
| Duration in | `durationSeconds(n)`, `durationMillis(n)`, `durationNanos(n)` |
| Duration out | `toSeconds(d)`, `toMillis(d)`, `toNanos(d)` |
| Calendar fields | `utcParts(t)`: UTC `year` … `nanosecond`, `weekday` |
| Timeline | a record with `view: "timeline"`, `range`, `series` and `events` |

## Exercises

Start from `$requests` and `$deployedAt`.

1. How much time passes between the first and the last request in the log?
2. How many requests fall inside the five minutes before and after the
   deployment?
3. What is the epoch time, in milliseconds, of the first server error?
4. What is the longest gap between two consecutive requests?

<details>
<summary>Answers</summary>

```text
:calc {
  return $requests[length($requests) - 1].at - $requests[0].at;
} > logSpan
:calc {
  const window = around($deployedAt, duration("PT5M"));
  return length($requests.filter(request => request.at >= window.start
    && request.at < window.end));
} > nearDeploy
:calc {
  const firstError = $requests.filter(request => request.status >= 500)[0];
  return int(toEpochMillis(firstError.at));
} > firstErrorMs
:calc {
  let longest = duration("PT0S");
  for (const i of range(1, length($requests))) {
    const gap = $requests[i].at - $requests[i - 1].at;
    if (gap > longest) {
      longest = gap;
    }
  }
  return longest;
} > longestGap
```

The results are `PT15M40S`, `5`, `1790605865000` and `PT5M35S`. `exercises.wes`
contains these answers.

</details>

## Next

[Chapter 6, *Nodes and dependencies*](../06-nodes-and-dependencies/README.md),
covers the workspace itself: how results depend on each other, how to refresh,
change and remove them, and how execution policies decide when dependent
results run again.
