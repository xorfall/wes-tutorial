# 4. Iterators and text

This chapter covers **iterators**: values that produce items one at a time from
a text, a list or a record. Iterators split text into lines, words and fields,
find patterns with regular expressions, and read JSON Lines logs.

The examples parse an HTTP access log and a structured application log, the
two most common text inputs in operations work.

## Prerequisites

- Chapters [1](../01-first-calculations/README.md) to
  [3](../03-control-flow-and-functions/README.md), in particular `map`,
  `filter`, `reduce` and `for...of`.
- Running the programs requires a local build of wes; see
  [Run the programs](#run-the-programs).

## The access log

Steps 1–4 use a short access log. Each line records one request: client
address, method, path, status and duration in milliseconds. The first line is a
header. `\n` inside quotes is a line break:

```text
:calc {
  return "# client method path status durationMs\n"
    + "10.0.0.5 GET /orders 200 120\n"
    + "10.0.0.7 POST /checkout 503 1250\n"
    + "10.0.0.5 GET /orders/17 404 40\n"
    + "10.0.0.9 POST /checkout 200 310\n"
    + "10.0.0.7 GET /orders 200 105\n"
    + "10.0.0.9 POST /checkout 500 990\n";
} > accessLog
```

## How iterators work

An iterator does not hold its items. It holds a source (here, the log text)
and a description of how to produce items from it. Items are produced only
when a **consumer** asks for them:

| Consumer | Result |
| --- | --- |
| `.collect()` | a list of all items |
| `.count()` | the number of items |
| `.reduce(f, start)` | one combined value |
| `for (const item of iterator) { ... }` | runs a block per item |

Between the source and the consumer, **stages** transform the items without
producing them yet: `.map(f)`, `.filter(f)`, `.take(n)`, `.skip(n)` and
`.field(name)`. This is called lazy evaluation. A consumer that needs only the
first items, such as `.take(2).collect()`, stops reading the source early.
For example, `iter.jsonLines('{"level": "info"}\nnot json').take(1).collect()`
succeeds: the invalid second line is never read.

| Source | Items |
| --- | --- |
| `iter.lines(text)` | lines, without the line break |
| `iter.words(text)` | words separated by whitespace |
| `iter.split(text, delimiter)` | parts between occurrences of a fixed delimiter |
| `iter.matches(text, regex)` | every match of a regular expression |
| `iter.captures(text, regex)` | every match, with the text of its groups |
| `iter.regexSplit(text, regex)` | parts between matches of a regular expression |
| `iter.chars(text)` | single characters |
| `iter.jsonLines(text)` | one parsed JSON value per line |
| `iter.items(list)` | the items of a list |
| `iter.keys(record)`, `iter.values(record)`, `iter.entries(record)` | field names, field values, or `{ key, value }` records |

## Part 1: Lines, words and patterns

The first animation shows steps 1–3 on the access log.

![WesDesk entering the access log, counting 7 lines, collecting the first 2,
storing an iterator that skips the header as a recipe that has not run yet,
counting 6 requests from it, and parsing the lines into a table of
requests](04a-lines-and-words.gif)

### Step 1: Lines

```text
:calc { return iter.lines($accessLog).count(); } > lineCount
:calc { return iter.lines($accessLog).take(2).collect(); } > firstLines
```

```text
✓ $lineCount   Int
7
✓ $firstLines   List<Text>   2 items
# client method path status durationMs · 10.0.0.5 GET /orders 200 120
```

- The final line break does not produce an empty line: the log has 7 lines.
- Empty lines in the middle of the text are kept as `""`.
- Windows line endings (`\r\n`) are handled: the `\r` is removed.

### Step 2: An iterator as a result

A calculation can return an iterator. Skip the header line and keep the
iterator for later calculations:

```text
:calc { return iter.lines($accessLog).skip(1); } > requestLines
:calc { return $requestLines.count(); } > requestCount
```

```text
◇ $requestLines   Iter<Text>
◇ recipe · nothing run yet — collect it explicitly to run it
✓ $requestCount   Int
6
```

- The result `$requestLines` is a **recipe**: the source and the stages,
  but no items. Its type is `Iter<Text>`, an iterator of `Text` items.
- The recipe is marked `not kept`: the workspace stores the results of
  consumers, such as `$requestCount`, rather than the iterator itself.
- Each consumer starts from the beginning. Counting the same iterator twice
  returns the same number both times.
- An iterator is not a list. `$requestLines[0]` and `length($requestLines)`
  fail before running, and the message names the alternative:
  `CAL004: Iter does not support indexing; use .take(1).collect() for a bounded
  list, then index that list` and `CAL004: length does not accept Iter; use
  .count() to traverse and count it, or .take(n).collect() for a bounded list`.

### Step 3: Words

Turn each line into a record. `iter.words` splits a line at spaces and tabs,
and ignores repeated or leading whitespace:

```text
:calc {
  return $requestLines.map(line => {
    const fields = iter.words(line).collect();
    return {
      client:     fields[0],
      method:     fields[1],
      path:       fields[2],
      status:     int(fields[3]),
      durationMs: int(fields[4]),
    };
  }).collect();
} > requests
```

```text
✓ $requests   List<{ client, method, path, +2 }>   6 rows

  client     method  path        status  durationMs
  10.0.0.5   GET     /orders        200         120
  10.0.0.7   POST    /checkout      503        1250
  10.0.0.5   GET     /orders/17     404          40
  10.0.0.9   POST    /checkout      200         310
  10.0.0.7   GET     /orders        200         105
  10.0.0.9   POST    /checkout      500         990
```

Text fields stay `Text` until converted: `int(fields[3])` turns `"200"` into
the `Int` `200` (chapter 2).

The second animation shows step 4.

![WesDesk counting 2 server errors with a regular expression, extracting the
path /orders/17, and capturing the status and duration of the two server errors
into a table](04b-patterns.gif)

### Step 4: Regular expressions

A **regular expression** (regex) describes a text pattern. Count the lines
with a 5xx status, find the paths of single orders, and extract the status and
duration of each server error:

```text
:calc {
  return $requestLines
    .filter(line => iter.matches(line, " 5[0-9][0-9] ").count() > 0)
    .count();
} > serverErrors
:calc {
  return iter.matches($accessLog, "/orders/[0-9]+").collect();
} > orderPaths
:calc {
  return iter.captures($accessLog, " (5[0-9][0-9]) ([0-9]+)")
    .map(found => {
      return {
        status:     unwrapOr(found.groups[0], ""),
        durationMs: unwrapOr(found.groups[1], ""),
      };
    })
    .collect();
} > serverErrorsAt
```

`$serverErrors` is `2` and `$orderPaths` is `["/orders/17"]`.

```text
✓ $serverErrorsAt   List<{ status: Text, durationMs: Text }>   2 rows

  status  durationMs
  503     1250
  500     990
```

| Pattern | Matches |
| --- | --- |
| `[0-9]` | one digit |
| `[0-9]+` | one or more digits |
| `[0-9]{4}` | exactly four digits |
| `.` | any character except a line break |
| `^`, `$` | start, end of the text |
| `(?i)` at the start | ignore case: `(?i)error` matches `ERROR` and `error` |
| `\\.` | a literal dot; the backslash is doubled inside quotes, so `"[0-9]+\\.[0-9]+"` finds `10.0` and `0.5` in `10.0.0.5` |

- Parentheses mark a **group**. `iter.matches` ignores groups and returns the
  whole match: `iter.matches("status=503", "status=([0-9]+)")` returns
  `["status=503"]`.
- `iter.captures` returns one record per match: `match` is the whole match, and
  `groups` is a list with one optional value (chapter 2) per group, in order.
  A group that did not take part in the match is `none`; a group that matched
  empty text is `some("")`. Hence `unwrapOr(found.groups[0], "")`.
- The syntax is that of the Rust `regex` library. Look-ahead (`(?=...)`) and
  back-references (`\1`) are not supported.
- An invalid or unsupported pattern fails when the calculation runs, and the
  message gives the reason: `CAL016: invalid Iter regex: error: unclosed group`,
  or `… look-around, including look-ahead and look-behind, is not supported`.

## Part 2: Fields, characters and JSON Lines

The third animation shows steps 5–9, followed by a lazy stage that wes
rejects.

![WesDesk parsing a settings string into key and value records, shortening a
message to "payment provider timed..." and counting its digits, selecting the
x- tracing headers of a
record, parsing a JSON Lines log, listing its error message "payment timeout",
counting 2 problems in a loop, and failing a lazy map stage that changes a
variable](04c-fields-and-json-lines.gif)

### Step 5: Split

`iter.split(text, delimiter)` cuts text at every occurrence of a fixed
delimiter. Parse a settings string of `key=value` pairs:

```text
:calc {
  return iter.split("timeout=30;retries=3;region=eu-west-1", ";")
    .map(pair => {
      const parts = iter.split(pair, "=").collect();
      return { key: parts[0], value: parts[1] };
    })
    .collect();
} > settings
```

```text
✓ $settings   List<{ key: Text, value: Text }>   3 rows

  key      value
  timeout  30
  retries  3
  region   eu-west-1
```

- Two delimiters in a row produce an empty part: splitting `"a,b,,c"` at `","`
  gives `["a", "b", "", "c"]`.
- The delimiter must not be empty: `iter.split(text, "")` fails with
  `CAL005: iter.split delimiter must not be empty; use iter.chars for
  individual characters`.
- To split at a pattern rather than fixed text, use
  `iter.regexSplit(text, regex)`: `iter.regexSplit("a1b22c", "[0-9]+")` gives
  `["a", "b", "c"]`.

### Step 6: Characters and slices

`iter.chars` produces one character at a time; `slice` (chapter 2) takes a
part of a text directly. Shorten a message for a notification, and count its
digits:

```text
:calc {
  const message = "payment provider timed out after 30 seconds";
  return {
    preview: slice(message, 0, 22) + "...",
    digits:  iter.chars(message)
      .filter(c => iter.matches(c, "[0-9]").count() > 0)
      .count(),
  };
} > messageFacts
```

The result is `{ preview: "payment provider timed...", digits: 2 }`. A
character is a Unicode character, not a byte: `iter.chars("café").count()` is
`4`. To join a list of text, use `join` (chapter 2):
`["orders-api", "billing-worker"].join(", ")`.

### Step 7: Record fields

`iter.entries(record)` produces one `{ key, value }` record per field. Select
the tracing headers of a request, which start with `x-`:

```text
:calc {
  const headers = {
    "content-type": "application/json",
    "x-request-id": "req-7f3a",
    "x-trace-id":   "trace-91c2",
  };
  return iter.entries(headers)
    .filter(entry => iter.matches(entry.key, "^x-").count() > 0)
    .map(entry => entry.key + "=" + entry.value)
    .collect();
} > tracingHeaders
```

The result is `["x-request-id=req-7f3a", "x-trace-id=trace-91c2"]`.
`iter.keys` and `iter.values` produce only the names or only the values, in the
order the fields were written.

### Step 8: JSON Lines

JSON Lines is a log format with one JSON object per line. Single quotes keep
the JSON readable:

```text
:calc {
  return '{"level": "info", "ms": 12, "msg": "order created"}\n'
    + '{"level": "error", "ms": 340, "msg": "payment timeout"}\n'
    + '{"level": "warn", "ms": 95, "msg": "retrying payment"}\n';
} > appLog
:calc {
  return iter.jsonLines($appLog)
    .filter(event => event.level == "error")
    .map(event => event.msg)
    .collect();
} > errorMessages
```

The result is `["payment timeout"]`.

- Each line is parsed like `parseJson` (chapter 2): objects become records,
  `null` becomes `none`.
- An invalid line fails the calculation, and the message gives the item number
  (counting from 0), the byte position and the JSON error.
- An empty line is not valid JSON, so it fails too, and the message shows how
  to skip such lines explicitly:

  ```text
  CAL016: JSONL line 2 is blank; every line must contain JSON. To skip blank
  lines explicitly, use iter.lines(source).filter(line => iter.words(line).count()
  > 0).map(line => parseJson(line)).collect()
  ```

  The filter keeps lines that contain at least one word, so lines of only
  spaces are skipped too. A final line break is allowed.

### Step 9: Loops with effects

The functions given to iterator stages are **pure**: they may only compute a
value from their input. A stage that assigns a variable of the calculation
fails before running:

```text
:calc {
  let seen = 0;
  return iter.lines("GET /orders 200\nGET /checkout 503")
    .map(line => {
      seen = seen + 1;
      return line;
    })
    .count();
} > counted
```

```text
✗ :calc { ... } > counted
  failed · CAL009: lazy Iter callbacks must be pure and cannot capture mutable outer bindings; use for-of for effects · nothing ran
```

A stage may run at a different time than the line it is written on, or not at
all when a consumer stops early, so changing a variable inside it would be
unpredictable. Use `for...of` when each item must change a variable. Count the
log events that are not informational:

```text
:calc {
  let problems = 0;
  for (const event of iter.jsonLines($appLog)) {
    if (event.level != "info") {
      problems = problems + 1;
    }
  }
  return problems;
} > problems
```

The result is `2`. The list operations of chapter 3 (`list.map`) run
immediately, once per item, and are not subject to this rule.

## Part 3: Typed iterators

The fourth animation shows step 10: loading a package that declares an
iterator, using it on the access log, and a check that rejects the header line.

![WesDesk loading a package with one type and one iterator recipe, storing the
requestEntries iterator for the access log, counting 6 entries, and failing a
checked iterator at item 0 because the header line does not match the
RequestLine type](04d-typed-iterators.gif)

### Step 10: Declare an iterator in a package

An iterator used in many calculations can be declared once, with a name and a
type for its items, in a **package**: a YAML file that declares types and
iterators for the workspace. `request-lines.types.yaml` declares a text type
for access log entries and an iterator that produces only such lines:

```yaml
types:
  RequestLine:
    base: Text
    pattern: '^[0-9.]+ [A-Z]+ /'
iterators:
  requestEntries:
    input: Text
    output: 'Iter<RequestLine>'
    mode: matches
    pattern: '(?m)^[0-9.]+ [A-Z]+ /.*$'
```

- `RequestLine` is a `Text` whose value must match the regular expression in
  `pattern`: an address, a method and a path.
- `requestEntries` takes a `Text` (`input`) and produces `RequestLine` items
  (`output`, always written `Iter<...>`).
- `mode` is one of the sources of this chapter: `lines`, `words`, `split`,
  `matches`, `regexSplit`, `chars`, `jsonLines`, `items`, `keys`, `values` or
  `entries`. `split` takes a `delimiter`; `matches` and `regexSplit` take a
  `pattern`. Here, `(?m)` makes `^` and `$` match at the start and end of every
  line, so the iterator produces each request line and skips the header.

Load the package, then use the iterator by name with `iter.use`:

```text
:package load path:"request-lines.types.yaml"
:calc { return iter.use("requestEntries", $accessLog); } > entries
:calc { return $entries.count(); } > entryCount
```

```text
❯ :package load path:"04-iterators-and-text/request-lines.types.yaml"
ok
ⓘ loaded 1 type definitions and 1 iterator recipes

❯ :calc { return iter.use("requestEntries", $accessLog); } > entries
ok · not kept
◇ $entries   Iter<RequestLine>
◇ recipe · nothing run yet — collect it explicitly to run it

❯ :calc { return $entries.count(); } > entryCount
ok · kept
✓ $entryCount   Int
6
```

- A relative `path` is resolved from the directory of the `.wes` file when a
  program runs with `--file`, and from the directory where wes was started when
  the command is entered in the client or with `--command`. The animation
  starts the server in the repository root and loads
  `04-iterators-and-text/request-lines.types.yaml`.
- The header shows the declared item type, `Iter<RequestLine>`. Every item is
  checked against it when it is produced. Stages and consumers work as in the
  previous steps.
- `iter.checked(iterator, "Type")` applies the same check to any iterator.
  Checking all lines of the log fails at the header, item 0:

  ```text
  :calc {
    return iter.checked(iter.lines($accessLog), "RequestLine").count();
  } > checkedLines
  ```

  ```text
  CAL017: Iter item 0, byte 0: item contract validation failed
    : TYP005: text does not match ^[0-9.]+ [A-Z]+ /
  ```

  `CAL017` marks a value that does not satisfy a declared type; the indented
  line below it gives the reason for each violated rule (`TYP005`).

## Watch out

### Limits

| Limit | Value | Failure |
| --- | --- | --- |
| Delimiter or pattern length | 16 KiB | `CAL006: Iter pattern exceeds its 16384-byte limit` |
| Compiled regular expression | 1 MiB | `CAL006: Iter regex exceeds its compiled size limit (1048576 bytes); simplify the pattern` |
| Stages in one iterator | 64 | `CAL006: Iter pipeline exceeds 64 stages` |
| Work, memory and depth | as in chapter 3 | `CAL006` |

Iterators help stay within the memory limit: `.count()` and `.reduce` never
build a list of all items. `.collect()` does.

### Sources must match their operation

Text sources (`iter.lines`, `iter.words`, `iter.split`, `iter.matches`,
`iter.captures`, `iter.regexSplit`, `iter.chars`, `iter.jsonLines`) require
`Text`. `iter.items` requires a list; `iter.keys`, `iter.values` and
`iter.entries` require a record. When the input type is known, a mismatch fails
before running, for example `CAL004: iter.words expects Text; received Int`.

### Process output is Bytes

Shell commands return their output as `Bytes`, not `Text`.
Text sources do not accept `Bytes`; convert explicitly with `text(bytes)`.

### Counts must not be negative

`.take(-1)` fails with `CAL015: take count must be nonnegative; received -1`, and
`.skip(-1)` with the same message for `skip`.
`.take(0)` produces no items.

### Failures in this chapter

| Error | Cause | Found |
| --- | --- | --- |
| `CAL004` Iter does not support indexing | `iterator[0]` | before running |
| `CAL004` length does not accept Iter | `length(iterator)` | before running |
| `CAL004` iter.words expects Text | wrong source type | before running |
| `CAL009` lazy Iter callbacks must be pure | a stage assigns a variable | before running |
| `CAL005` iter.split delimiter must not be empty | empty delimiter | while running |
| `CAL016` invalid Iter regex: … | invalid or unsupported regex | while running |
| `CAL016` Iter item N, byte B: JSON input: invalid JSON | an invalid JSON Lines line | while running |
| `CAL016` JSONL line N is blank | an empty JSON Lines line | while running |
| `CAL017` Iter item N, byte B: item contract validation failed | an item that does not match the item type | while running |
| `CAL015` take/skip count must be nonnegative | negative `take` or `skip` | while running |
| `CAL006` Iter pipeline exceeds 64 stages, pattern or regex size limit | a limit of this chapter | while running |

## Run the programs

From the repository root, after building wes as described in
[chapter 1](../01-first-calculations/README.md#run-the-programs):

```sh
$WES --home /tmp/wes-tutorial-04 --file 04-iterators-and-text/main.wes
python3 04-iterators-and-text/check.py
```

- `main.wes` contains the logs and steps 1–10, and loads
  `request-lines.types.yaml`.
- `edge-cases.wes` contains the smaller examples of this chapter: line
  endings, empty fields, ignored groups, case-insensitive matching, fresh
  consumers, joining text, early stopping, literal dots, optional groups and
  JSON with empty lines.
- `failures/` contains one program per documented failure.
- `check.py` runs all of them and verifies every value and error in this
  chapter.

## Summary

| Concept | Syntax |
| --- | --- |
| Text sources | `iter.lines(t)`, `iter.words(t)`, `iter.split(t, d)`, `iter.chars(t)` |
| Pattern sources | `iter.matches(t, re)`, `iter.captures(t, re)`, `iter.regexSplit(t, re)` |
| Other sources | `iter.jsonLines(t)`, `iter.items(list)`, `iter.entries(record)` |
| Stages | `.map(f)`, `.filter(f)`, `.take(n)`, `.skip(n)`, `.field(name)` |
| Consumers | `.collect()`, `.count()`, `.reduce(f, start)`, `for...of` |
| Declared iterators | `:package load path:"file.yaml"`, `iter.use("name", source)` |
| Item checks | `iter.checked(iterator, "Type")` |

## Exercises

Start from `$accessLog` and `$appLog`.

1. Count the requests from client `10.0.0.9`.
2. Count the lines with a 4xx status.
3. Add up the durations of all `POST` requests without building the list of
   requests first.
4. Find the message of the slowest event in `$appLog`.

<details>
<summary>Answers</summary>

```text
:calc {
  return iter.lines($accessLog)
    .skip(1)
    .filter(line => iter.words(line).collect()[0] == "10.0.0.9")
    .count();
} > fromClient9
:calc {
  return iter.lines($accessLog)
    .filter(line => iter.matches(line, " 4[0-9][0-9] ").count() > 0)
    .count();
} > clientErrors
:calc {
  return iter.lines($accessLog)
    .skip(1)
    .map(line => iter.words(line).collect())
    .filter(fields => fields[1] == "POST")
    .reduce((sum, fields) => sum + int(fields[4]), 0);
} > postDurationMs
:calc {
  return iter.jsonLines($appLog)
    .reduce((slowest, event) => {
      if (event.ms > slowest.ms) {
        return event;
      }
      return slowest;
    }, { level: "none", ms: 0, msg: "none" })
    .msg;
} > slowestMessage
```

The results are `2`, `1`, `2550` and `"payment timeout"`. `exercises.wes`
contains these answers.

</details>

## Next

[Chapter 5, *Time values*](../05-time-values/README.md), covers instants, durations and intervals: parsing
timestamps from logs, converting epoch values, measuring time between events
and sorting events in time.
