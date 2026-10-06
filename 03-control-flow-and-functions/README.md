# 3. Control flow and functions

This chapter covers the statements inside a calculation body: variables,
conditions, loops and functions, and the list operations `map`, `filter` and
`reduce`. It also covers failure outputs, which pass an error to another
calculation, and the limits that stop a runaway calculation.

The examples analyse a batch of request samples from an `orders-api` service:
slow requests, retry delays, status classes, latency statistics and a
per-route summary.

## Prerequisites

- [Chapter 1](../01-first-calculations/README.md) and
  [chapter 2](../02-values-and-operators/README.md).
- Running the programs requires a local build of wes; see
  [Run the programs](#run-the-programs).

## The request samples

Every step uses the same eight request samples. Each has a route, an HTTP
status and a duration in milliseconds:

```text
:calc {
  return [
    { route: "/orders",      status: 200, durationMs: 120  },
    { route: "/orders",      status: 201, durationMs: 95   },
    { route: "/orders/{id}", status: 404, durationMs: 40   },
    { route: "/checkout",    status: 503, durationMs: 1250 },
    { route: "/checkout",    status: 200, durationMs: 310  },
    { route: "/orders/{id}", status: 200, durationMs: 88   },
    { route: "/checkout",    status: 500, durationMs: 990  },
    { route: "/orders",      status: 200, durationMs: 105  },
  ];
} > samples
```

## Part 1: Variables, loops and functions

The first animation shows steps 1–3: counting slow requests, computing a retry
schedule and classifying statuses.

![WesDesk entering the request samples, then calculations that count 3 slow
requests, compute 5 retry attempts totalling 3100 ms, and classify each status
as 2xx, 4xx or 5xx](03a-loops-and-functions.gif)

### Step 1: Variables and `for...of`

Count the requests that took longer than 300 ms:

```text
:calc {
  const thresholdMs = 300;
  let slow = 0;
  for (const sample of $samples) {
    if (sample.durationMs > thresholdMs) {
      slow = slow + 1;
    }
  }
  return slow;
} > slowCount
```

```text
✓ $slowCount   Int
3
```

- `const` declares a variable that cannot change. `let` declares one that can
  be assigned again with `=`. Both need a value when they are declared.
- Variables exist only inside the braces where they are declared, and only
  while the calculation runs. The calculation's result is its `return` value.
- `for (const sample of $samples) { ... }` runs the block once for each item of
  the list, in order. Write `let` instead of `const` to reassign the loop
  variable inside the block.
- `if (condition) { ... }` runs the block only when the condition is `true`.
  The condition must be a `Bool`: `if (1)` fails with
  `CAL004: condition requires Bool; received Int`.

### Step 2: `while`

A client retries a failed request with exponential backoff: 100 ms, then twice
as long each time, and gives up when the total waiting time would exceed
5 seconds. Compute how many retries fit:

```text
:calc {
  let delayMs = 100;
  let totalMs = 0;
  let attempts = 0;
  while (totalMs + delayMs <= 5000) {
    totalMs = totalMs + delayMs;
    attempts = attempts + 1;
    delayMs = delayMs * 2;
  }
  return { attempts: attempts, totalMs: totalMs };
} > backoff
```

```text
✓ $backoff   { attempts: Int, totalMs: Int }   2 fields
attempts  5
totalMs   3100
```

`while (condition) { ... }` repeats the block as long as the condition is
`true`. The delays are 100, 200, 400, 800 and 1600 ms; the next delay, 3200 ms,
would bring the total to 6300 ms.

A loop whose condition never becomes `false` is stopped by the calculation's
work limit; see [step 11](#step-11-limits).

### Step 3: Functions and `else if`

Define a function that turns a status code into its class, and apply it to
every sample:

```text
:calc {
  function statusClass(status) {
    if (status >= 500) {
      return "5xx";
    } else if (status >= 400) {
      return "4xx";
    } else if (status >= 300) {
      return "3xx";
    } else {
      return "2xx";
    }
  }
  return $samples.map(sample => statusClass(sample.status));
} > classes
```

```text
✓ $classes   List<Text>   8 items
2xx · 2xx · 4xx · 5xx · 2xx · 2xx · 5xx · 2xx
```

- `function name(parameters) { ... }` declares a function. `return` ends the
  function and gives its result.
- `else if` tests another condition when the previous one was `false`; `else`
  runs when no condition matched.
- A function must be declared before the line that calls it. Calling it
  earlier fails before running with
  `CAL013: local 'double' is used before initialization; keep declarations
  before their use`.
- Calling a function with the wrong number of arguments fails before running:
  `CAL012: function 'add' expects 2 argument(s); received 1`.
- wes has no conditional expression (`a ? b : c`). Writing one fails with
  `CAL001: the ?: operator is not supported; use if/else and return the
  selected value`.

The second animation shows steps 4–6: finding the first failure, summarising
latency and sorting.

![WesDesk entering the request samples, then calculations that find /checkout as
the first failing route, summarise 2 failures with a mean of 374.8 ms and a
maximum of 1250 ms, compute a p95 of 1250 ms, and list the three slowest
requests as a table](03b-lists-and-sorting.gif)

### Step 4: `break` and `continue`

Find the route of the first request that failed with a server error:

```text
:calc {
  let firstFailure = none;
  for (const sample of $samples) {
    if (sample.status < 500) {
      continue;
    }
    firstFailure = some(sample.route);
    break;
  }
  return firstFailure;
} > firstFailure
```

```text
✓ $firstFailure   Option<Text>
/checkout
```

- `continue` skips the rest of the block and moves to the next item.
- `break` leaves the loop immediately.
- The result is an optional value (chapter 2): `none` when no request failed.
  A `return` inside the loop would also work, and would end the whole
  calculation at once.

### Step 5: `map`, `filter` and `reduce`

These three operations replace most loops:

| Operation | Result |
| --- | --- |
| `list.map(f)` | a new list with `f(item)` for each item |
| `list.filter(f)` | a new list with the items for which `f(item)` is `true` |
| `list.reduce(f, start)` | one value: `f` combines a running value with each item, beginning with `start` |

Summarise the latency of the samples:

```text
:calc {
  const larger = (a, b) => {
    if (a > b) {
      return a;
    }
    return b;
  };
  const durations = $samples.map(sample => sample.durationMs);
  const totalMs = durations.reduce((sum, d) => sum + d, 0);
  return {
    failures: length($samples.filter(sample => sample.status >= 500)),
    meanMs:   roundDiv(totalMs, length(durations), 1),
    maxMs:    durations.reduce(larger, 0),
  };
} > latency
```

```text
✓ $latency   { failures, meanMs, maxMs }   3 fields
failures  2
meanMs    374.8
maxMs     1250
```

- `sample => sample.durationMs` is an **arrow function**: a short function
  written inline. With several parameters, use parentheses: `(sum, d) => sum + d`.
  With several statements, use a block and `return`, as in `larger`.
- A function can be stored in a variable (`larger`) and passed to `reduce`,
  `map` or `filter` by name.
- The function given to `filter` must return a `Bool`. Returning another type
  fails at run time with `CAL004: expected Bool; received Int`.
- `map`, `filter` and `reduce` can also be written as functions:
  `filter($samples, sample => sample.status >= 500)`.
- An arrow function that returns a record needs parentheses around the record:
  `status => ({ status: status })`. Without them, the braces are read as a
  block, and the calculation fails before running with `CAL001: expected a
  statement, not a record field; braces after => start a block. Return a record
  with => ({field: value}) or { return {field: value}; }`.

### Step 6: Sorting

`list.sortBy(f)` returns a new list sorted by the key `f(item)`, in ascending
order. Compute the 95th percentile (p95) latency, the duration that 95% of
requests do not exceed, and list the three slowest requests:

```text
:calc {
  const durations = $samples
    .map(sample => sample.durationMs)
    .sortBy(d => d);
  const rank = div(95 * length(durations) + 99, 100);
  return durations[rank - 1];
} > p95Ms
:calc {
  return $samples
    .sortBy(sample => 0 - sample.durationMs)
    .slice(0, 3);
} > slowest
```

```text
✓ $p95Ms   Int
1250
✓ $slowest   List<{ route, status, durationMs }>   3 rows

  route       status  durationMs
  /checkout      503        1250
  /checkout      500         990
  /checkout      200         310
```

- The p95 uses the nearest-rank method: the value at position
  ⌈0.95 × n⌉ in the sorted list. `div(95 * n + 99, 100)` rounds that position
  up with integer arithmetic. With only 8 samples, p95 is the maximum.
- Negate a numeric key to sort in descending order: `0 - sample.durationMs`.
- The sort is stable: items with equal keys keep their original order.
- Keys must be `Int`, `Decimal`, `Text`, `Instant` or `Duration`, and all keys
  must have the same type. A list or record key fails with
  `CAL004: sortBy keys requires matching Int, Decimal, Text, Instant or
  Duration`.
- The key function must be pure: it may only compute a key from its item. A
  key function that assigns a variable fails before running with
  `CAL009: sortBy selector must be pure and cannot capture mutable outer
  bindings`.
- `sortBy` accepts lists only. Collect an iterator first (chapter 4).

## Part 2: Closures, recursion, failure outputs and limits

The third animation shows steps 7–11: a per-route summary table, a generated
list of thresholds, a recursive delay calculation, a failure that is passed to
another calculation, and a loop stopped by the work limit.

![WesDesk entering the request samples, then a per-route table with requests
and failures, escalation thresholds of 250, 500 and 750 ms, a sixth retry delay
of 3200 ms, a failed JSON health check whose error is turned into the alert
text "health check failed: CAL004 …", and an endless loop stopped with
"calculation work limit reached"](03c-closures-and-failures.gif)

### Step 7: Closures

A function defined inside another function can use the variables around it.
Such a function is called a **closure**. Summarise requests and failures per
route:

```text
:calc {
  const routes = ["/orders", "/orders/{id}", "/checkout"];
  return routes.map(route => {
    const hits = $samples.filter(sample => sample.route == route);
    return {
      route:    route,
      requests: length(hits),
      failures: length(hits.filter(sample => sample.status >= 500)),
    };
  });
} > byRoute
```

```text
✓ $byRoute   List<{ route, requests, failures }>   3 rows

  route          requests   failures
  /orders               3          0
  /orders/{id}          2          0
  /checkout             3          2
```

The inner function `sample => sample.route == route` uses `route`, the
parameter of the outer function. Each call of the outer function has its own
`route`.

### Step 8: `range`

`range` produces a list of whole numbers:

| Call | Result |
| --- | --- |
| `range(4)` | `[0, 1, 2, 3]` |
| `range(1, 4)` | `[1, 2, 3]` (the end is excluded) |
| `range(0, 10, 3)` | `[0, 3, 6, 9]` (step 3) |
| `range(5, 0, -1)` | `[5, 4, 3, 2, 1]` |

Generate three escalation thresholds:

```text
:calc { return range(1, 4).map(level => level * 250); } > escalationMs
```

The result is `[250, 500, 750]`. A range whose end is not reachable, such as
`range(3, 1)`, is empty. A step of `0` fails with
`CAL005: range step must be nonzero`.

### Step 9: Recursion

A function can call itself. Compute the delay before the sixth attempt of the
backoff in step 2:

```text
:calc {
  function delayFor(attempt) {
    if (attempt == 0) {
      return 100;
    }
    return 2 * delayFor(attempt - 1);
  }
  return delayFor(5);
} > sixthDelay
```

The result is `3200`. Each call waits for the call inside it, so recursion
depth is limited; see [step 11](#step-11-limits).

### Step 10: Failure outputs

`*> name` after a command names its **failure output**. When the calculation
fails, its error becomes a value under that name, and other calculations can
use it. Turn a failed health check into an alert message:

```text
:calc {
  return parseJson('{"status": "ok", ');
} > health *> healthError
:calc {
  return "health check failed: " + $healthError.code
    + " " + $healthError.message;
} > healthAlert
```

```text
❯ :calc { … } > health *> healthError
failed · CAL016 · error → $healthError · not kept
JSON input: invalid JSON: EOF while parsing an object at line 1 column 17
this cell · line 2, column 10

❯ :calc { … } > healthAlert
ok · kept
✓ $healthAlert   Text
health check failed: CAL016 JSON input: invalid JSON: EOF while parsing an object at line 1 column 17
```

- `> health` names the result when the calculation succeeds; `*> healthError`
  names the error when it fails. A command can have both, or only one.
- The error is a record with the fields `code`, `message`, `id`, `issues`,
  `locations` and `causeId`.
- The run line shows `error → $healthError`: the error was passed on under
  that name. A failed calculation has no result of its own, so the cell shows
  the run line and the error only.
- The failed calculation is still marked as failed, and the command line exits
  with a non-zero status. The failure output does not hide the failure; it
  makes the error available to other calculations.
- When the calculation succeeds, `$healthError` has no value, and a calculation
  that reads it does not run. The command line reports this on standard error,
  for example `error output was not produced by $health in this run`.
  `failure-output-success.wes` shows this case.

### Step 11: Limits

Every calculation runs within fixed limits. A calculation that exceeds one
fails with `CAL006`, and nothing else in the workspace is affected:

```text
:calc {
  let n = 0;
  while (true) {
    n = n + 1;
  }
  return n;
} > forever
```

```text
failed · CAL006 · not kept
calculation work limit reached (1000000 work units). Reduce the input or split
the calculation; work units count evaluated operations, not loop iterations.
this cell · line 3, column 16
called from line 1, column 8
```

| Limit | Value | Example that fits | Example that fails |
| --- | --- | --- | --- |
| Work | 1,000,000 work units | a simple loop of 50,000 turns | the same loop with 70,000 turns |
| Memory | 64 MiB retained | `length(range(600000))` | `length(range(700000))` |
| Call depth | 128 frames | recursion 126 levels deep | recursion 127 levels deep |
| Provider calls | 1,000 calls | — | — (calls are introduced in a later chapter) |

A work unit is an internal measure of evaluation steps, not a number of loop
turns. The examples show the order of magnitude. `limits.wes` and the programs
in `failures/` verify the examples.

The values above are the defaults. The WesDesk application can change them in
`/settings` → `limits`, under *Calculation*; a change applies the next time the
application starts. The command line and `wes --serve` always use the defaults,
so a program that passes there passes for every reader.

## Watch out

### Values cannot be modified

Lists and records never change after they are created. `delays[0] = 50` and
`record.field = 1` fail before running with `CAL001: only local let bindings may
be assigned; record fields and list items are immutable values. Build a new
record with withFields or a new list with slice/concat, then rebind the local
let variable`.
wes has no spread syntax (`[...list]`). Two operations build modified copies:

- `record.withFields(patch)` returns a new record with the fields of `patch`
  replaced or added. `withFields({ a: 1, b: 2 }, { b: 3, c: 4 })` is
  `{ a: 1, b: 3, c: 4 }`.
- `concat(left, right)` returns a new list with the items of both lists, in
  order. The item types must be compatible:
  `concat([120, 95], ["slow"])` fails before running with
  `CAL004: concat requires compatible element types`.

Reassign a `let` variable to the new value in a loop:

```text
:calc {
  let counts = { ok: 0, failed: 0 };
  for (const sample of $samples) {
    if (sample.status >= 500) {
      counts = counts.withFields({ failed: counts.failed + 1 });
    } else {
      counts = counts.withFields({ ok: counts.ok + 1 });
    }
  }
  return counts;
} > counts
:calc {
  let schedule = [];
  let delayMs = 100;
  while (delayMs <= 1600) {
    schedule = concat(schedule, [delayMs]);
    delayMs = delayMs * 2;
  }
  return schedule;
} > schedule
```

The results are `{ ok: 6, failed: 2 }` and `[100, 200, 400, 800, 1600]`. No
record or list is modified; each turn creates a new one. Prefer `map`, `filter`
and `reduce` when they express the calculation directly.

### Missing `return`

A calculation or function must reach a `return`. When wes can see that it
never does, the calculation fails before running with
`CAL013: calculation/function reaches its end without returning a value; add
return`. When it depends on the values, for example an `if` without `else`
whose condition turns out `false`, the calculation fails while running with
`CAL013: calculation or anonymous function completed without return`:

```text
:calc { return 0; } > errors
:calc {
  if ($errors > 0) {
    return "page";
  }
} > action
```

Inside a named function, the message names it: `CAL013: function 'decide'
completed without return; return a value on every executed path`. Add an
`else` branch or a final `return` to cover every case.

### Callbacks run in order and can update variables

The functions given to `map`, `filter` and `reduce` run once per item, in list
order. They can assign `let` variables of the surrounding calculation. Prefer
`reduce` for accumulating a value; it states the intent and keeps each
function independent.

### Functions stay inside the calculation

A function cannot be the result of a calculation:
`:calc { return status => status >= 500; }` fails with
`CAL004: functions cannot cross a value boundary`.
[Chapter 14](../14-prom/README.md#2-define-one-reusable-adapter-and-load-a-view)
uses templates to define reusable, named operations for the whole workspace.

### Loops accept lists only

`for...of` accepts a list. Looping over a record fails with
`CAL004: for-of requires List or Iter; received Record`; loop over
`keys(record)` instead:

```text
:calc {
  const response = { status: 503, retryAfter: 30 };
  let fields = [];
  for (const key of keys(response)) {
    fields = concat(fields, [key]);
  }
  return fields.join(", ");
} > fieldNames
```

The result is `"status, retryAfter"`. Chapter 4 covers iterating over text.

### Local names hide built-in operations

A variable, parameter or function may have the name of a built-in operation,
such as `count`, `length`, `range` or `text`. Inside its scope, the name then
refers to the local value, and the operation is not available under that name:

```text
:calc {
  const length = 5;
  return length([200, 503]);
} > requests
```

fails before running with `CAL004: This value is not callable; expected
Function.` Use
the method form, `[200, 503].length()`, or a more specific name, such as
`requestCount`.

The words of the language itself cannot be names. Keywords and literals such as
`return`, `if`, `true` and `none` fail with `CAL001: expected a local name`, and
`iter`, the namespace of chapter 4, fails with `CAL010: local name 'iter'
conflicts with the language vocabulary; choose another name`.

### Failures in this chapter

| Error | Cause | Found |
| --- | --- | --- |
| `CAL001` binding declarations require an initial value | `let` or `const` without a value | before running |
| `CAL001` only local let bindings may be assigned | assigning to a list item or field | before running |
| `CAL001` the ?: operator is not supported | `a ? b : c` | before running |
| `CAL001` expected a statement, not a record field | arrow function returning a record without parentheses | before running |
| `CAL004` condition requires Bool | non-`Bool` condition in `if` or `while` | before running |
| `CAL004` This value is not callable | calling a local value that hides an operation | before running |
| `CAL004` concat requires compatible element types | `concat` of different item types | before running |
| `CAL009` sortBy selector must be pure | a sort key function that assigns a variable | before running |
| `CAL001` expected a local name | a variable named like a keyword or literal | before running |
| `CAL010` local name conflicts with the language vocabulary | a variable named `iter` | before running |
| `CAL011` cannot assign a const binding; use let … | assigning to a `const` | before running |
| `CAL012` function expects N argument(s) | wrong number of arguments | before running |
| `CAL013` used before initialization | calling a function above its declaration | before running |
| `CAL013` reaches its end without returning | a body that can never return | before running |
| `CAL013` completed without return | no `return` reached with the actual values | while running |
| `CAL004` expected Bool | `filter` function returning a non-`Bool` | while running |
| `CAL004` sortBy keys requires matching … | sort keys that are lists, records or mixed types | while running |
| `CAL004` functions cannot cross a value boundary | returning a function | while running |
| `CAL005` range step must be nonzero | `range(a, b, 0)` | while running |
| `CAL006` work, allocation or call-frame limit | see step 11 | while running |

## Run the programs

From the repository root, after building wes as described in
[chapter 1](../01-first-calculations/README.md#run-the-programs):

```sh
$WES --home /tmp/wes-tutorial-03 --file 03-control-flow-and-functions/main.wes
python3 03-control-flow-and-functions/check.py
```

- `main.wes` contains the samples and steps 1–9.
- `failure-output.wes` and `failure-output-success.wes` contain step 10.
- `limits.wes` contains the examples that fit within the limits of step 11.
- `watch-out.wes` contains the examples of the "Watch out" section.
- `failures/` contains one program per documented failure.
- `check.py` runs all of them and verifies every value and error in this
  chapter.

## Summary

| Concept | Syntax |
| --- | --- |
| Constant, variable | `const name = value;`, `let name = value;`, `name = value;` |
| Condition | `if (c) { ... } else if (c) { ... } else { ... }` |
| Loops | `for (const item of list) { ... }`, `while (c) { ... }` |
| Leave or skip | `break;`, `continue;` |
| Function | `function name(a, b) { return ...; }` |
| Arrow function | `x => expression`, `(a, b) => { ...; return ...; }` |
| List operations | `list.map(f)`, `list.filter(f)`, `list.reduce(f, start)` |
| Sort | `list.sortBy(item => key)` |
| Modified copies | `record.withFields(patch)`, `concat(left, right)` |
| Number sequence | `range(end)`, `range(start, end)`, `range(start, end, step)` |
| Failure output | `:calc { ... } > result *> error` |

## Exercises

Start from `$samples`.

1. Count the successful requests (status class 2) with `filter`.
2. Write a function `isSlow(sample)` that is `true` above 300 ms, and list the
   routes of the slow requests.
3. Compute the percentage of failed requests (status 500 or higher) on
   `/checkout`, rounded to one decimal place.
4. Starting at 100 ms, how many times must a delay double before it exceeds
   one minute (60000 ms)? Use `while`.

<details>
<summary>Answers</summary>

```text
:calc {
  return length($samples.filter(sample => div(sample.status, 100) == 2));
} > successCount
:calc {
  function isSlow(sample) {
    return sample.durationMs > 300;
  }
  return $samples.filter(isSlow).map(sample => sample.route);
} > slowRoutes
:calc {
  const hits = $samples.filter(sample => sample.route == "/checkout");
  const failures = hits.filter(sample => sample.status >= 500);
  return roundDiv(length(failures) * 100, length(hits), 1);
} > checkoutErrors
:calc {
  let delayMs = 100;
  let doublings = 0;
  while (delayMs <= 60000) {
    delayMs = delayMs * 2;
    doublings = doublings + 1;
  }
  return doublings;
} > doublings
```

The results are `5`, `["/checkout", "/checkout", "/checkout"]`, `66.7` and
`10`. `exercises.wes` contains these answers.

</details>

## Next

[Chapter 4, *Iterators and text*](../04-iterators-and-text/README.md), covers reading text line by line, splitting
and matching it, and processing large inputs lazily.
