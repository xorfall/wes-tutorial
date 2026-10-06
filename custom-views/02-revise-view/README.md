# 2. Revise a View

This chapter covers changing a View that is already in use: a second package
with its own identity, installed next to the first one, and a comparison of
both instances on the same input. An installed definition never changes, so a
revision is always a new definition.

The example adds ServiceBoardPriority, which shows unhealthy services first and
the latency before the request rate, while `$board` from chapter 1 keeps its
original order.

## Prerequisites

- [Chapter 1](../01-first-view/README.md), in the same workspace: `$serviceData`,
  the ServiceBoard definition and the `$board` instance.
- An agent with Wes tools for step 1, or the checked reference package; see
  [Run the programs](#run-the-programs).

## Part 1: Request and identity

### Step 1: The revision request

The agent receives the request in [assistant-task.txt](assistant-task.txt):

> Make a second version of ServiceBoard called ServiceBoardPriority.
> Put down services first, degraded services next and healthy services last.
> Keep the original order within each group.
> Move the p95 / ms column before Requests / s. Keep the same input and theme.
> Read the current View authoring guidance through Wes MCP.
> Use a new package name and id; preserve the original source and View.
> Write view-work/service-board-priority, build and check it, and return
> view-work/service-board-priority.wes-view.json with the test results.
> Leave workspace installation to me.

- The request changes the presentation only: no new data, no polling, no
  selection.
- The reference renderer sorts a derived list of rows: by status, and by the
  original position within a status. It never sorts or changes
  `$serviceData.services`.

### Step 2: A distinct identity

| Item | Original | Revision |
| --- | --- | --- |
| definition `name` | `ServiceBoard` | `ServiceBoardPriority` |
| renderer `id` | `service-board` | `service-board-priority` |
| source folder | `view-work/service-board/` | `view-work/service-board-priority/` |
| package file | `service-board.wes-view.json` | `service-board-priority.wes-view.json` |
| input type | `ServiceBoardInput` | `ServiceBoardInput` |

- The `name` and the `id` in `view.json` identify a definition. A new file name
  alone does not: Wes reads the identity from the package.
- The revision keeps [types.yaml](service-board-priority/types.yaml) identical
  to chapter 1, so both definitions accept the same input. It changes
  [View.tsx](service-board-priority/View.tsx) and the identity.

## Part 2: Install and compare

The animation shows steps 3 to 6 with the reference packages.

![WesDesk installing ServiceBoardPriority, creating priorityBoard with gateway,
billing-worker and orders-api in severity order and the p95 column first,
reading both instances, listing the unchanged input order, and refusing a
package that reuses the ServiceBoard identity with VIE004](02-revise-view.gif)

### Step 3: Install the revision

Enter [load.wes](load.wes):

```text
:package load path:"view-work/service-board-priority.wes-view.json"
```

```text
ok
ⓘ installed view ServiceBoardPriority · 0d154dff911900aa…
```

- ServiceBoard stays installed. Both packages declare the same input type;
  importing an identical type again is allowed, a conflicting one is refused.
- Editing source files changes nothing in the workspace. A revision takes
  effect only after it is built, checked and installed.

### Step 4: Compare the instances

Enter [create.wes](create.wes):

```text
:view create ServiceBoardPriority input:$serviceData > priorityBoard
```

```text
ok · kept
✓ $priorityBoard   ViewInstance
Service monitor
Service health by severity
Service          Status     p95 / ms   Requests / s
gateway          down            850              0
billing-worker   degraded        240             40
orders-api       ok               85            120
```

The new name `priorityBoard` keeps `board` bound to the first instance. Both
instances use the same `$serviceData`; only the presentation differs:

| Instance | Row order | Columns |
| --- | --- | --- |
| `$board` | `orders-api`, `billing-worker`, `gateway` (input order) | Requests / s, then p95 / ms |
| `$priorityBoard` | `gateway`, `billing-worker`, `orders-api` (down, degraded, ok) | p95 / ms, then Requests / s |

[read-original.wes](read-original.wes) and [read.wes](read.wes) refer to both
instances:

```text
:read $board
```

```text
:read $priorityBoard
```

Each answers with a link to its instance, such as `→ $priorityBoard ·
ServiceBoardPriority   Go to view` (chapter 1, step 6).

### Step 5: The input is unchanged

Enter [input-order.wes](input-order.wes):

```text
:calc pure {
  return $serviceData.services.map(service => service.name);
} > inputOrder
```

```text
ok · kept
✓ $inputOrder   List<Text>   3 items
orders-api · billing-worker · gateway
```

The services are still in their original order: the revision sorted its own
rows, not the input. The check of this chapter also verifies that rendering
never modifies the input.

### Step 6: An identity collision

A package whose code changed but whose `name` or `id` is already installed is
refused. The preview of this chapter includes such a package,
`collision.wes-view.json`: the revised code with the identity of ServiceBoard.
Enter [collision.wes](collision.wes):

```text
:package load path:"view-work/collision.wes-view.json"
```

```text
not run · VIE004: View name/id is already installed; use a new identity for different code · nothing ran
```

- The original definition and `$board` remain as they were.
- The file is an exercise in refusal, not the revision to install.
- Installing the exact same package again is allowed: the command of step 3
  answers again and replaces no instance.

## Watch out

### An installed definition never changes

Instances keep the package they were created with. Editing `View.tsx`, or
building it again under the same identity, does not change `$board`. To
present the data differently, install a definition with a new `name` and `id`
and create a new instance.

### A failed build can leave an older package

After a failed build, the previous `.wes-view.json` file may still be there.
Its presence does not mean that the revision compiled; read the result of the
latest build before installing.

### Equal statuses keep their order

Within one status, the revision keeps the input order. Two degraded services
stay in the order of `$serviceData`.

### Reusing a result name moves it

`:view create ServiceBoardPriority input:$serviceData > board` would move the
name `board` to the new instance (main tutorial, chapter 1). A new name keeps
both instances available.

### Failures in this chapter

| Message | Cause |
| --- | --- |
| `VIE004` View name/id is already installed; use a new identity for different code | a changed package with an installed `name` or `id` |
| (a type conflict) | a package that declares an installed input type differently |

## Run the programs

`load.wes`, `create.wes`, `read-original.wes`, `read.wes`, `input-order.wes` and
`collision.wes` contain steps 3 to 6. `check.py --preview` builds both packages
and the collision package, prepares chapter 1 in a temporary workspace and
prints its address; enter the programs there. No model is called:

```sh
python3 custom-views/02-revise-view/check.py --preview
```

Without `--preview`, the check builds both packages, verifies the severity
order, stable ties, the unchanged input, the collision and the rendered
components, and makes a TypeScript build fail on purpose to verify that the
older package is kept:

```sh
python3 custom-views/02-revise-view/check.py
```

```text
PASS revision: severity order, stable ties and unchanged input
PASS packages: collision refused; both definitions remain usable
PASS rebuild: identical reload and failed-build artifact retention
```

## Summary

| Concept | Meaning |
| --- | --- |
| `name` and `id` in `view.json` | the identity of a definition |
| a new identity, the same input type | two definitions side by side |
| `> priorityBoard` | a second instance next to `$board` |
| `VIE004` | changed code cannot replace an installed definition |

## Exercises

1. Only the package file is renamed, to `service-board-v2.wes-view.json`. Can it
   replace the installed ServiceBoard?
2. A build failed, but `service-board-priority.wes-view.json` exists. Which
   version does it contain?
3. Which command shows that `$serviceData` kept its order after step 4?

<details>
<summary>Answers</summary>

1. No. Wes reads the `name`, the `id` and the compiled content from the
   package; the file name is only a location. With changed code, loading it
   fails with `VIE004`; with identical code, it is the same package.
2. The last successful build. The failed revision is not in it; read the
   diagnostics of the latest build.
3. `input-order.wes`: `$serviceData.services.map(service => service.name)`
   gives `orders-api`, `billing-worker`, `gateway`.

</details>

## Next

The next chapters of the series cover the Wes theme, input rules, selection
and outputs, a Dashboard, live data, and saving and diagnosing a workspace.
The [series index](../README.md) lists them.
