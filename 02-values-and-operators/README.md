# 2. Values and operators

This chapter covers the values a calculation works with: whole and decimal
numbers, text, booleans, records, lists and optional values. It also covers
the operators and conversions between them, and how to read JSON text.

The examples compute a monthly error budget for a service, classify HTTP status
codes, build alert messages, and read an HTTP response and a health payload.

## Prerequisites

- [Chapter 1](../01-first-calculations/README.md): `:calc`, names, references,
  records and lists.
- Running the programs requires a local build of wes; see
  [Run the programs](#run-the-programs).

## Types at a glance

| Type | Example | Notes |
| --- | --- | --- |
| `Int` | `1250`, `-5` | Whole number, signed 64-bit. |
| `Decimal` | `99.9`, `2.50` | Exact decimal number. |
| `Text` | `"orders-api"`, `'eu-west-1'` | A sequence of characters. |
| `Bool` | `true`, `false` | |
| Record | `{ status: 503 }` | Named fields. Type written `{ status: Int }`. |
| List | `[120, 95, 310]` | Ordered values. Type written `List<Int>`. |
| Option | `none`, `some(30)` | A value that may be absent. Type written `Option<Int>`. |

## Part 1: Numbers, text and booleans

The first animation shows steps 1–5: arithmetic on `Int` and `Decimal`,
rounding and conversions, followed by a division that wes rejects.

![WesDesk computing a monthly request count of 10800000, an error budget of 0.1
percent, 10800 allowed failures, 3.33 from a rounded division, half-to-even
rounding, a whole failure count and converted values; the last cell fails
because 10 divided by 3 has no exact decimal result](02a-numbers.gif)

### Step 1: Int

`Int` is a whole number. Compute the number of requests `orders-api` receives
in 30 days, at 1250 requests per five-minute window:

```text
:calc { return 1250 * 12 * 24 * 30; } > requests30d
```

```text
✓ $requests30d   Int
10800000
```

`Int` is a signed 64-bit integer: from −9223372036854775808 to
9223372036854775807. A result outside that range fails at run time:

```text
:calc { return 9223372036854775807 + 1; } > tooLarge
```

```text
CAL005: integer arithmetic overflow; result must fit a signed 64-bit Int
```

Write numbers without separators: `1_000` is a syntax error.

### Step 2: Decimal

A number with a decimal point is a `Decimal`. `Decimal` is exact: it stores
the digits as written, without binary rounding.

A service level objective (SLO) of 99.9% availability allows 0.1% of requests
to fail. Compute the budget and the number of failures it allows over 30 days:

```text
:calc { return 100.0 - 99.9; } > budgetPercent
:calc {
  return decimal($requests30d) * $budgetPercent / 100.0;
} > failureBudget
```

```text
✓ $budgetPercent   Decimal
0.1
✓ $failureBudget   Decimal
10800
```

- `$requests30d` is an `Int`. `decimal(...)` converts it to a `Decimal`, because
  wes never mixes `Int` and `Decimal` implicitly (chapter 1).
- A `Decimal` keeps the number of decimal places that come from its inputs, its
  **scale**. Addition and subtraction keep the larger scale (`2.50 + 1.5` is
  `4.00`), multiplication adds them (`2.50 * 2.0` is `5.000`), and division
  returns the shortest exact result (`1080000.0 / 100.0` is `10800`).
- The client and the command line show a `Decimal` without trailing zeros:
  `2.50 + 1.5` is shown as `4`. The scale is still part of the value:
  `text(2.50 + 1.5)` is `"4.00"`, and `--json` prints `4.00`.

### Step 3: Division and rounding

`/` returns the exact result of a division. When the result has no finite
decimal representation, the calculation fails:

```text
:calc { return 10 / 3; } > perInstance
```

```text
CAL005: division is nonterminating; use roundDiv with an explicit scale
```

`roundDiv(a, b, scale)` divides and rounds to `scale` decimal places. Spread 10
requests per second evenly across 3 instances:

```text
:calc { return roundDiv(10, 3, 2); } > perInstance
```

```text
✓ $perInstance   Decimal
3.33
```

`roundDiv` rounds a value that is exactly halfway to the nearest even digit
("half to even", also called banker's rounding). This avoids a systematic
upward bias when many values are rounded:

```text
:calc { return [roundDiv(5, 2, 0), roundDiv(7, 2, 0)]; } > halves
```

```text
✓ $halves   List<Decimal>   2 items
2 · 4
```

`2.5` rounds to `2` and `3.5` rounds to `4`. The results are `Decimal` values,
even with scale `0`; convert them with `int` when an `Int` is needed (step 4).

### Step 4: Conversions

| Function | Converts | Fails when |
| --- | --- | --- |
| `int(x)` | `Decimal` or `Text` to `Int` | the value is not an exact whole number |
| `decimal(x)` | `Int` or `Text` to `Decimal` | the text is not a number |
| `text(x)` | a number or `Bool` to `Text` | — |

`int` never rounds silently. `int(2.9)` fails:

```text
CAL005: int cannot convert Decimal to an exact signed 64-bit integer
```

Round first, then convert:

```text
:calc { return int(roundDiv($failureBudget, 1, 0)); } > failureCount
```

Conversions from text are common when values arrive as strings, for example
from headers or configuration:

```text
:calc {
  return {
    status: int("503"),
    load:   decimal("0.25"),
    rate:   text(2.4),
  };
} > converted
```

```text
✓ $converted   { status, load, rate }   3 fields
status  503
load    0.25
rate    "2.4"
```

- The header shows the field names of a record with more than two fields;
  `:inspect $converted` shows the complete type,
  `{ status: Int, load: Decimal, rate: Text }`.
- Text values in a record are shown in quotes, `"2.4"`, so that they can be
  told apart from numbers.

Text that is not a number fails when the calculation runs: `int("12x")` fails
with `CAL016: int cannot parse Text as an exact signed 64-bit integer; use
integer numeric Text within the Int range`, and `decimal("1.2.3")` with
`CAL016: decimal cannot parse Text as a decimal number; use numeric Text with a
decimal point or exponent`. `CAL016` marks text that cannot be parsed; the
same code is used for JSON, regular expressions and timestamps.

### Step 5: Integer division and remainder

`div(a, b)` divides two `Int` values and drops the remainder; `rem(a, b)`
returns the remainder. The class of an HTTP status code is its first digit:

```text
:calc { return div(503, 100); } > statusClass
:calc { return rem(503, 100); } > statusDetail
```

`$statusClass` is `5` (a server error); `$statusDetail` is `3`.

- `div` and `rem` accept only `Int`. For a `Decimal`, use `roundDiv`.
- Both round toward zero: `div(-7, 2)` is `-3` and `rem(-7, 2)` is `-1`.
- wes has no `%` operator; use `rem`.
- `div(x, 0)` fails with `CAL005: div divisor must not be zero`.

### Step 6: Text

The second animation shows steps 6 and 7: a status class, an alert message,
text operations and a combined condition.

![WesDesk computing status class 5, the text "orders-api: 2.4% errors", a record
built with length, slice and join, and the condition true](02b-text-and-booleans.gif)


Text is written in double or single quotes. Join text with `+`:

```text
:calc {
  return "orders-api: " + text(2.4) + "% errors";
} > alertMessage
```

```text
✓ $alertMessage   Text
orders-api: 2.4% errors
```

- Both sides of `+` must be `Text`. `"latency: " + 42` fails before running
  with `CAL004: mixed operands require explicit conversion; received Text and
  Int`. Use `text(42)`.
- Single quotes are convenient for text that contains double quotes:
  `'single "quoted" text'`. Inside quotes, `\"`, `\'` and `\t` insert a quote
  or a tab.
- A text value cannot span several lines. A line break inside the quotes fails
  with `CAL001: unescaped control character in string`. Join several pieces
  with `+` instead, as in step 11.
- `length(text)` counts characters, `text[0]` returns the first character as
  `Text`, `slice(text, start, end)` returns the characters from position
  `start` up to, but not including, `end`, and `join(list, separator)` joins a
  list of text:

  ```text
  :calc {
    return {
      length: length("orders-api"),
      first:  "orders-api"[0],
      prefix: slice("orders-api", 0, 6),
      joined: join(["orders-api", "billing-worker"], ", "),
    };
  } > textFacts
  ```

  The result is
  `{ length: 10, first: "o", prefix: "orders", joined: "orders-api, billing-worker" }`.
- Positions count characters, not bytes: `slice("café", 3)` is `"é"`. Without
  `end`, `slice` continues to the end of the text. `start` must not be greater
  than `end`, and `end` must not exceed the length:
  `slice("orders-api", 0, 20)` fails with
  `CAL015: slice end 20 exceeds Text character length 10`.
- `join` accepts only a list of `Text`. `join([120, 95], ", ")` fails before
  running with `CAL004: expected Text; received Int`; convert the items with
  `text` first (chapter 3 shows how, with `map`). `list.join(separator)` is the
  same operation.

### Step 7: Bool

`&&` (and), `||` (or) and `!` (not) combine `Bool` values. Page the on-call
engineer when the service returns server errors and the error rate exceeds 2%,
or when the slowest request took longer than 300 ms:

```text
:calc {
  return $statusClass == 5 && 2.4 > 2.0 || 310 > 300;
} > page
```

```text
✓ $page   Bool
true
```

- The operands must be `Bool`. `1 && true` fails with
  `CAL004: expected Bool; received Int`.
- `&&` applies before `||`, so the condition reads as
  `(server errors and rate above 2%) or (slow request)`.
- `&&` and `||` stop as soon as the result is known. In
  `false && div(1, 0) == 0`, the division never runs, and the result is `false`.
- Operators apply in this order, from first to last. Use parentheses to change
  it: `(2 + 3) * 4` is `20`, `2 + 3 * 4` is `14`.

| Precedence | Operators |
| --- | --- |
| 1 (first) | `!`, unary `-` |
| 2 | `*`, `/` |
| 3 | `+`, `-` |
| 4 | `<`, `<=`, `>`, `>=` |
| 5 | `==`, `!=` |
| 6 | `&&` |
| 7 (last) | `\|\|` |

## Part 2: Records, lists, optional values and JSON

The third animation shows steps 8 and 9: an HTTP response record, facts read
from it and from a list of latencies. The last cell fails because the response
has no `retryAfter` field.

![WesDesk building an HTTP response record with content-type, x-request-id and
status fields, reading facts from it and from a list of latencies, and failing
to read a missing field](02c-records-and-lists.gif)

### Step 8: Records

Field names that are not plain names, such as HTTP header names with hyphens,
are written in quotes:

```text
:calc {
  return {
    "content-type": "application/json",
    "x-request-id": "req-7f3a",
    status:         503,
  };
} > response
```

Read such a field with square brackets. `has`, `keys` and `length` describe the
record:

```text
:calc {
  return {
    contentType:   $response["content-type"],
    hasRetryAfter: has($response, "retry-after"),
    fields:        keys($response),
    fieldCount:    length($response),
  };
} > responseFacts
```

```text
✓ $responseFacts   { contentType, hasRetryAfter, +2 }   4 fields
contentType    "application/json"
hasRetryAfter  false
▸ fields       List · 3 items
fieldCount     3
```

- `$response.status` and `$response["status"]` read the same field. The dot
  form works only for plain names.
- `keys` returns the field names in the order they were written.
- Reading a field that does not exist fails. For a record written in the same
  calculation, wes finds the mistake before running:
  `CAL004: record field 'retryAfter' is absent; use keys(record) to inspect
  available fields`. For a record from another result, such as `$response`,
  the field is checked while the calculation runs:
  `CAL004: field or method 'retryAfter' is absent on Record`. Check with `has`
  first when a field may be missing, or use an optional value (step 10).
- A record cannot contain the same field twice: `{ status: 200, status: 503 }`
  fails with `CAL014: duplicate record field`.

### Step 9: Lists

List positions start at `0`:

```text
:calc { return [120, 95, 310, 88]; } > latenciesMs
:calc {
  return {
    first:  $latenciesMs[0],
    last:   $latenciesMs[3],
    count:  length($latenciesMs),
    middle: slice($latenciesMs, 1, 3),
  };
} > latencyFacts
```

The result is `{ first: 120, last: 88, count: 4, middle: [95, 310] }`. `slice`
works on lists with the same rules as on text.

- A position outside the list fails, and the message lists the valid range:
  `CAL015: index 4 is out of range; List length is 4; valid indices are 0..3
  (inclusive)`. Negative positions are not supported.
- A list may hold values of different types, such as `[1, "orders-api", 2.4]`.
  Its type is then `List<Unknown>`, and later calculations cannot rely on the
  type of an item. Prefer a record when the values have different meanings.

### Step 10: Optional values

The fourth animation shows steps 10 and 11: optional values and a parsed health
payload.

![WesDesk showing an absent and a present optional value, facts read from them,
and a JSON health payload whose maintenance field is none](02d-options-and-json.gif)


An optional value is either `none` (absent) or `some(value)` (present). The
`Retry-After` header of an HTTP response, for example, may be missing:

```text
:calc { return none; } > noRetryAfter
:calc { return some(30); } > retryAfter
```

```text
✓ $noRetryAfter   Option<Unknown>
none
✓ $retryAfter   Option<Int>
30
```

The result shows the value inside `some(...)` directly. `none` on its own has no
value type, so its type is `Option<Unknown>`. In a list, wes combines both:
`[none, some(30)]` has the type `List<Option<Int>>`.

`unwrapOr(option, fallback)` returns the value, or the fallback when the
option is `none`. `isSome(option)` tells whether a value is present:

```text
:calc {
  return {
    missing:    unwrapOr($noRetryAfter, 5),
    present:    unwrapOr($retryAfter, 5),
    hasMissing: isSome($noRetryAfter),
  };
} > retryDelays
```

The result is `{ missing: 5, present: 30, hasMissing: false }`.

### Step 11: JSON

`parseJson(text)` reads JSON text into wes values. JSON objects become records,
arrays become lists, and `null` becomes `none`:

```text
:calc {
  return parseJson(
    '{"status": "degraded", "uptimeSeconds": 86400, '
    + '"load": 0.75, "maintenance": null}'
  );
} > health
:calc {
  return {
    status:      $health.status,
    load:        $health.load,
    maintenance: unwrapOr($health.maintenance, "none scheduled"),
  };
} > healthFacts
```

```text
✓ $health   { status, uptimeSeconds, load, +1 }   4 fields
status         "degraded"
uptimeSeconds  86400
load           0.75
maintenance    none
✓ $healthFacts   { status, load, maintenance }   3 fields
status       "degraded"
load         0.75
maintenance  "none scheduled"
```

- The structure of JSON text is only known after it is read. The header of
  `$health` therefore lists the fields of the value that was read,
  `{ status, uptimeSeconds, load, +1 }`, and later calculations are checked
  against them: `$health.load + 1` fails before running with `CAL004: mixed
  operands require explicit conversion; received Decimal and Int`. A field that
  is not there is found when the calculation runs: `$health.uptime` fails with
  `CAL004: field or method 'uptime' is absent on Record`.
  [Chapter 4](../04-iterators-and-text/README.md) shows validation against a
  declared type.
- JSON numbers keep their digits: `"12.50"` becomes the `Decimal` `12.50`.
- Invalid JSON fails, and the message gives the reason and the position in
  the JSON text: `parseJson("{status: ok}")` fails with
  `CAL016: JSON input: invalid JSON: key must be a string at line 1 column 2`.

## Watch out

### Equality across types is false, ordering is an error

`==` and `!=` compare any two values. Values of different types are never
equal: `1 == 1.0` is `false`, without an error. `<`, `<=`, `>` and `>=` require
matching types and fail otherwise (chapter 1). Records and lists are equal when
all their contents are equal: `[120, 95] == [120, 95]` is `true`.

### Text is ordered by character code

`"B" < "a"` is `true`, because uppercase letters come before lowercase letters
in Unicode. Text comparison does not follow the alphabetical order of any
language.

### Missing operators

wes has no `%` operator (use `rem`), no conditional expression `a ? b : c`
(use `if`, chapter 3), and no string templates (join with `+` and `text`).

### Failures by kind

| Error | Cause | Found |
| --- | --- | --- |
| `CAL004` mixed operands | `Int` with `Decimal`, or `Text` with a number | before running |
| `CAL004` expected Bool | `&&`, `\|\|` or `!` on a non-`Bool` | before running |
| `CAL004` expected Text | `join` on a list of non-`Text` values | before running |
| `CAL004` record field is absent | a missing field of a record written in the same calculation | before running |
| `CAL014` duplicate record field | the same field written twice | before running |
| `CAL001` unescaped control character | a line break inside quotes | before running |
| `CAL005` integer overflow | an `Int` result outside 64 bits | while running |
| `CAL005` nonterminating division | `/` without an exact result | while running |
| `CAL005` int cannot convert | `int` of a non-whole value | while running |
| `CAL016` int cannot parse Text | `int` or `decimal` of text that is not a number | while running |
| `CAL004` field absent | a missing field of a record read at run time | while running |
| `CAL015` index out of range | a position outside the list | while running |
| `CAL015` slice end exceeds length | `slice` beyond the end | while running |
| `CAL016` JSON input: invalid JSON | malformed JSON text, with its line and column | while running |

The code names the kind of cause: `CAL004` a type or an operation that does not
apply, `CAL005` a numeric value, `CAL015` a position or count outside its
bounds, `CAL016` text that cannot be parsed. `:help errors` lists every code
with a typical fix.

## Run the programs

From the repository root, after building wes as described in
[chapter 1](../01-first-calculations/README.md#run-the-programs):

```sh
$WES --home /tmp/wes-tutorial-02 --file 02-values-and-operators/main.wes
python3 02-values-and-operators/check.py
```

- `main.wes` contains steps 1–11.
- `edge-cases.wes` contains the examples of the "Watch out" section.
- `failures/` contains one program per documented failure.
- `check.py` runs all of them and verifies every value and error shown in this
  chapter, including the number of decimal places.

## Summary

| Concept | Syntax | Example |
| --- | --- | --- |
| Exact division | `a / b` | `10 / 4` is `2.5` |
| Rounded division | `roundDiv(a, b, scale)` | `roundDiv(10, 3, 2)` is `3.33` |
| Integer division, remainder | `div(a, b)`, `rem(a, b)` | `div(503, 100)` is `5` |
| Conversions | `int(x)`, `decimal(x)`, `text(x)` | `int("503")` |
| Join text | `a + b`, `join(list, sep)` | `"p95: " + text(310)` |
| Part of text or list | `slice(x, start, end)` | `slice("orders-api", 0, 6)` |
| Logic | `&&`, `\|\|`, `!` | `a && !b` |
| Quoted field | `{ "name": v }`, `r["name"]` | `$response["content-type"]` |
| Record facts | `has(r, "f")`, `keys(r)`, `length(r)` | `has($response, "status")` |
| List facts | `l[i]`, `length(l)` | `$latenciesMs[0]` |
| Optional value | `none`, `some(v)` | `some(30)` |
| Optional access | `unwrapOr(o, fallback)`, `isSome(o)` | `unwrapOr($retryAfter, 5)` |
| JSON | `parseJson(text)` | `parseJson('{"a": 1}')` |

## Exercises

1. The SLO of `billing-worker` is 99.95%. Compute the number of failures it
   allows over 30 days at the same traffic (`$requests30d`), as an `Int`.
2. Compute the status class of `404`.
3. Build the text `billing-worker: 503` from the name and the number `503`.
4. Write a condition that is `true` for client errors (status class 4).
5. Read the `region` field from the JSON text
   `{"region": "eu-west-1", "zone": null}`.

<details>
<summary>Answers</summary>

```text
:calc { return 99.95; } > sloTarget
:calc {
  return int(decimal($requests30d) * (100.0 - $sloTarget) / 100.0);
} > failureBudget
:calc { return div(404, 100); } > notFoundClass
:calc { return "billing-worker: " + text(503); } > statusLine
:calc { return div(404, 100) == 4; } > isClientError
:calc {
  return parseJson('{"region": "eu-west-1", "zone": null}').region;
} > region
```

The results are `5400`, `4`, `billing-worker: 503`, `true` and `eu-west-1`.
In exercise 1, `int` succeeds without rounding because the result is a whole
number. `exercises.wes` contains these answers.

</details>

## Next

[Chapter 3, *Control flow and functions*](../03-control-flow-and-functions/README.md),
covers variables, conditions, loops,
functions, list operations such as `map`, `filter` and `reduce`, failure
outputs and the limits of a calculation.
