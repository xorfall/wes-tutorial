# 1. First calculations

This chapter introduces the basic unit of work in wes: a command that produces a
result. It covers running calculations, naming results, referring to them from
other calculations, and how wes reports types and failures.

The example follows a common operations task: turning raw request counts of a
service into an error rate and an alert condition.

## Prerequisites

- No previous chapter.
- Reading requires nothing else. Running the programs requires a local build of
  wes; see [Run the programs](#run-the-programs).

## See it first

The animation is recorded in the WesDesk client with the ink theme. It enters
every command of steps 1–8 and shows the cell each one produces.

![WesDesk entering nine calculations for an orders-api service: request and
error counts, an error rate of 2.4, a summary record, a true alert, a table of
three services, and a failed calculation that refers to an unknown
result](01-first-calculations.gif)

## Commands, cells and results

A **workspace** is the place where commands run and results are kept. Each
command entered in the command field produces a **result**. The client shows
each command and its result together as a **cell**:

| Part of a cell | Content |
| --- | --- |
| command | the command as it was entered, after `❯` |
| run line | how the run ended: `ok`, `failed` or `not run`, and whether the value is `kept` |
| result header | `✓` or `✗`, the name of the result and its type |
| value | the value itself: a number, a record, a table |
| action keys | keys for the cell (`r repeat`, `e edit`, …) and for its value (`v json`, …) |

This tutorial writes a cell as text in this order:

```text
❯ :calc { return 1200 + 50; }
ok · kept
✓ id1000   Int
1250
```

Commands that start with `:` belong to the wes language. This chapter uses one
of them, `:calc`, which evaluates a calculation.

## Step 1: Run a calculation

Enter the following command and press <kbd>Enter</kbd>:

```text
:calc { return 1200 + 50; }
```

| Part | Meaning |
| --- | --- |
| `:calc` | Evaluates the calculation that follows. |
| `{ ... }` | The body of the calculation. |
| `return 1200 + 50;` | The value the calculation produces. The syntax follows JavaScript. |

The cell shows:

```text
❯ :calc { return 1200 + 50; }
ok · kept
✓ id1000   Int
1250
```

- `ok` means the calculation completed.
- `kept` means the value is stored in the workspace, not only displayed. A
  later chapter covers storage in detail.
- `id1000` is the identifier wes assigned to this result.
- `Int` is the type of the value: a whole number. wes determines the type from
  the value; no type declaration is needed.
- `1250` is the value.

The run line and the result header also show how long the calculation took,
for example `<1 ms`, and the run line shows the time of the run. Both vary
between runs and are omitted from the examples in this tutorial.

## Step 2: Name a result

Naming a result makes it reusable. Record the request count and the error
count of the `orders-api` service for the last five minutes:

```text
:calc { return 1250; } > requests
:calc { return 30; } > errors
```

`> requests` binds the name `requests` to the result. The result header now
shows `$requests` instead of an identifier.

`>` after the closing brace is not shell redirection. It writes no file; it only
names the result.

## Step 3: Refer to a result

Refer to a named result by writing `$` followed by its name:

```text
:calc { return $requests - $errors; } > succeeded
```

```text
✓ $succeeded   Int
1220
```

wes looks up `$requests` (1250) and `$errors` (30) and subtracts. It also records
that `$succeeded` depends on both. The workspace therefore holds not only values,
but the connections between them. Later chapters use these connections to refresh
dependent results.

Unnamed results can be referred to by identifier, for example `$id1000`.
Identifiers depend on the order of commands, so names are the reliable choice.

## Step 4: Divide

Compute the error rate as a percentage:

```text
:calc { return $errors * 100 / $requests; } > errorRate
```

```text
✓ $errorRate   Decimal
2.4
```

Dividing two `Int` values always produces a `Decimal`, even when the division is
exact. `Decimal` is an exact decimal number: `0.1 + 0.2` is exactly `0.3`, without
the rounding errors of floating-point arithmetic.

## Step 5: Build a record

A **record** groups named fields into one value. Collect the figures of the
service into a summary:

```text
:calc {
  return {
    service:   "orders-api",
    window:    "5m",
    requests:  $requests,
    errors:    $errors,
    errorRate: $errorRate,
  };
} > summary
```

In the client, <kbd>Shift</kbd>+<kbd>Enter</kbd> inserts a new line in the
command field; <kbd>Enter</kbd> runs the command. The trailing comma after the
last field is allowed.

The result header shows the record and the number of fields; the value lists
the fields:

```text
✓ $summary   { service, window, requests, +2 }   5 fields
service    "orders-api"
window     "5m"
requests   1250
errors     30
errorRate  2.4
```

- A record with more than two fields is shown in the header by its first field
  names. The complete type is
  `{ service: Text, window: Text, requests: Int, errors: Int, errorRate: Decimal }`;
  `:inspect $summary` shows it, and chapter 6 covers `:inspect`.
- Text values in a record are shown in quotes, so that `"5m"` is not mistaken
  for a number.

The command band folds a long command to its first and last lines;
`show full command` expands it.

Text values are written in double quotes (`"orders-api"`); their type is `Text`.

## Step 6: Compare values

Read a field with `.` and compare it with a threshold:

```text
:calc { return $summary.errorRate > 2.0; } > alert
```

```text
✓ $alert   Bool
true
```

- `$summary.errorRate` reads the `errorRate` field of the record.
- Inside the braces, `>` is the "greater than" comparison. Outside the braces, at
  the end of the command, `>` names the result. Both appear in this command.
- The result type is `Bool`: `true` or `false`.
- The threshold is written `2.0`, not `2`. `$summary.errorRate` is a `Decimal`,
  and wes does not compare a `Decimal` with an `Int`. `$summary.errorRate > 2`
  is rejected before it runs. See
  [Int and Decimal do not mix](#int-and-decimal-do-not-mix).

## Step 7: Build a list of records

A **list** holds several values in order, written in square brackets. Record the
figures of three services:

```text
:calc {
  return [
    { service: "orders-api",     requests: 1250, errors: 30 },
    { service: "billing-worker", requests: 480,  errors: 2  },
    { service: "auth-gateway",   requests: 3100, errors: 0  },
  ];
} > services
```

```text
✓ $services   List<{ service, requests, errors }>   3 rows

service          requests   errors
orders-api           1250       30
billing-worker        480        2
auth-gateway         3100        0
```

The header reads as "a list of records with the fields `service`, `requests`
and `errors`"; the complete type is
`List<{ service: Text, requests: Int, errors: Int }>`. `3 rows` is the number
of items.
Because every item has the same fields, the client displays the list as a
table.

## Step 8: Refer to a missing result

Enter a calculation that refers to a name that was never defined:

```text
:calc { return $requests + $retries; } > attempts
```

The cell has no result:

```text
❯ :calc { return $requests + $retries; } > attempts
not run · CAL010: unknown workspace output '$retries' · nothing ran
```

- The error code `CAL010` and the message identify the problem: no result is
  named `$retries`.
- `not run` and `nothing ran` mean that wes checked the references before
  evaluating anything. The calculation was not partly evaluated, and no default
  value was substituted.
- The name `attempts` is not bound, and all earlier results remain unchanged.

Define the missing result, then enter the calculation again:

```text
:calc { return 12; } > retries
:calc { return $requests + $retries; } > attempts
```

## Step 9: Declare a calculation pure

`pure` after `:calc` declares that the calculation only computes a value from its
inputs, here `$errors` and `$requests`:

```text
:calc pure { return $errors * 100 / $requests; } > pureRate
```

Later chapters introduce calculations that call external systems, such as HTTP
services. wes rejects a `pure` calculation that could make such a call, before
running it:

```text
CAL009: pure calculation contains a possible external provider call
```

Use `pure` wherever a calculation must never have side effects. The guarantee is
checked by wes, not assumed.

## Watch out

### `>` has two meanings

Inside the braces, `>` compares values. After the closing brace, `>` names the
result. `:calc { return $a > $b; } > isLarger` uses both.

### Reusing a name moves it

Binding a name that is already in use moves the name to the new result. Results
that referred to the old one keep their values:

```text
:calc { return 1250; } > requests
:calc { return $requests * 2; } > projected
:calc { return 1400; } > requests
:calc { return $requests * 2; } > projectedNow
```

`$projected` remains `2500`, computed from the first result. `$projectedNow` is
`2800`. The first result keeps its value and is shown by its identifier.

### Int and Decimal do not mix

wes never converts between `Int` and `Decimal` implicitly, in arithmetic or in
comparisons. This calculation fails before it runs:

```text
:calc { return $errors / $requests * 100; } > errorRate
```

```text
not run · CAL004: mixed operands require explicit conversion; received Decimal and Int · nothing ran
```

`$errors / $requests` is a `Decimal`, and `* 100` multiplies it by an `Int`. Either
reorder the calculation so that the division comes last
(`$errors * 100 / $requests`), or write the constant as a decimal (`100.0`).

Comparisons follow the same rule:

```text
:calc { return $summary.errorRate > 2; } > alert
```

```text
not run · CAL004: comparison requires matching kinds and explicit conversion; received Decimal and Int · nothing ran
```

wes knows the types of earlier results, including record fields, so both
mistakes are reported before anything runs. Chapter 2 covers numeric
conversions.

### Some failures are found before running, others while running

- Found before running, marked `not run · … · nothing ran`: invalid names (`PAR003`),
  unknown references (`CAL010`), mixed numeric types (`CAL004`), external
  calls in `pure` calculations (`CAL009`).
- Found while running, because they depend on the actual values: for example,
  division by zero (`CAL005`):

  ```text
  :calc { return 0; } > requests
  :calc { return 30 * 100 / $requests; } > errorRate
  ```

  ```text
  ❯ :calc { return 30 * 100 / $requests; } > errorRate
  failed · CAL005 · not kept
  division by zero
  this cell · line 1, column 16
  called from line 1, column 8
  ✗ $errorRate   no stored value
  no value · the run failed
  ```

  `line 1, column 16` is the position of the failing expression,
  `30 * 100 / $requests`, inside the command. `called from` is the position of
  the calculation body that evaluated it. On the command line, the same
  failure names the program file and the result:
  `errorRate: CAL005: division by zero`, `at division-by-zero.wes: line 2, column 16`.

A failed result is never kept and never replaces an earlier value.

### Names

- Names contain only letters, digits and `_`, for example `errorRate` or
  `error_rate_5m`. Other characters are rejected before anything runs:

  ```text
  :calc { return 2.4; } > error-rate
  ```

  ```text
  PAR003: Binding names may contain only letters, digits and underscores; use error_rate instead of error-rate.
  ```

  A hyphen would be ambiguous: `$error-rate` reads as `$error` minus `rate`.
- Names are case-sensitive: `$Requests` and `$requests` are different results.

### Comments

`//` starts a comment that runs to the end of the line. Comments are allowed
between commands and inside calculation bodies:

```text
// Correction for step 8: define the missing result first.
:calc {
  // Requests that returned a 5xx status in the last five minutes.
  return 30;
} > errors
```

`//` inside a text value, such as `"http://127.0.0.1"`, is part of the text,
not a comment.

## Run the programs

Every program in this chapter is in this folder. Build wes and set `WES` and
`WES_SITE` as described in [Set up](../README.md#set-up), then run the
commands from the root of the tutorial repository.

Run steps 1–7 from the command line:

```sh
$WES --home /tmp/wes-tutorial --file 01-first-calculations/main.wes
```

Each output line is one result: its identifier, then its value as JSON.

```text
id1000: 1250
id1001: 1250
id1002: 30
id1003: 1220
id1004: 2.4
id1005: {"service":"orders-api","window":"5m","requests":1250,"errors":30,"errorRate":2.4}
id1006: true
id1007: [{"service":"orders-api","requests":1250,"errors":30},{"service":"billing-worker","requests":480,"errors":2},{"service":"auth-gateway","requests":3100,"errors":0}]
```

`--home` selects the data folder. Use a separate folder for tutorials; the
folder must be empty or an existing wes data folder.

To use the client, start the server:

```sh
$WES --home /tmp/wes-tutorial --serve 8099 --site "$WES_SITE"
```

Open the address that the server prints, for example `http://127.0.0.1:8099`.
The server listens only on the local machine; keep it that way, because it can
run commands on this computer. Enter `/theme ink` to match the animation.

`check.py` runs every program of this chapter, including the failures, the
corrections and the exercise answers, in a temporary data folder and verifies each documented value
and error (Python 3.11 or newer):

```sh
python3 01-first-calculations/check.py
```

## Summary

| Concept | Syntax | Example |
| --- | --- | --- |
| Run a calculation | `:calc { return ...; }` | `:calc { return 1200 + 50; }` |
| Name a result | `> name` after the braces | `... > requests` |
| Refer to a result | `$name` | `$requests - $errors` |
| Refer to an unnamed result | `$id…` | `$id1000` |
| Text | `"..."` | `"orders-api"` |
| Record | `{ field: value, ... }` | `{ service: "orders-api" }` |
| Read a field | `.field` | `$summary.errorRate` |
| List | `[value, ...]` | `[1250, 480, 3100]` |
| Compare | `>` `>=` `<` `<=` `==` inside braces | `$errorRate > 2.0` |
| Pure calculation | `:calc pure { ... }` | `:calc pure { return 1; }` |
| Comment | `// ...` to the end of the line | `// 5xx responses` |

Types introduced: `Int`, `Decimal`, `Text`, `Bool`, records and `List<...>`.

## Exercises

Start from the results of steps 2, 3 and 7.

1. Compute the availability of `orders-api` as a percentage: successful requests
   times 100, divided by all requests. Name it `availability`.
2. The service level objective (SLO) requires an availability of at least 99.0%.
   Compute whether `orders-api` meets it. Name the result `withinSlo`.
3. Read the error count of `billing-worker` from `$services`. The first item of
   a list is at position `0`; `$services[0]` is the `orders-api` record.

<details>
<summary>Answers</summary>

```text
:calc { return $succeeded * 100 / $requests; } > availability
:calc { return $availability >= 99.0; } > withinSlo
:calc { return $services[1].errors; } > billingErrors
```

- `$availability` is `97.6` (`Decimal`).
- `$withinSlo` is `false`. The threshold is written `99.0` because
  `$availability` is a `Decimal`.
- `$billingErrors` is `2`.

`exercises.wes` contains these answers.

</details>

## Next

[Chapter 2, *Values and operators*](../02-values-and-operators/README.md),
covers numbers, text, booleans, records, lists, optional values, conversions
and JSON in detail.
