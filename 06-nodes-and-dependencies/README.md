# 6. Nodes and dependencies

This chapter covers the workspace as a graph of results. It shows how results
depend on each other, how to run a result again, change its command, limit its
run time and remove it, and how an execution policy decides whether dependent
results run again automatically.

The example computes the request capacity of a service from its number of
replicas and compares it with the current load. The replica count comes from a
command, so it can change.

## Prerequisites

- Chapters [1](../01-first-calculations/README.md) to
  [5](../05-time-values/README.md).
- Running the programs requires a local build of wes; see
  [Run the programs](#run-the-programs).

## Nodes, runs and names

Every command entered in the workspace creates a **node**: its definition, such
as a calculation or a provider call. Each time a node executes, it produces a
**run** with a result. A **name** such as `$capacityRps` points to a node, and
references between nodes form a graph:

```text
replicas ──┐
           ├──> capacityRps ──> headroomRps ──> healthy
perReplicaRps ┘
```

A node that reads another node **depends** on it. The node it reads is
**upstream**; the nodes that read it are **downstream**.

Commands that control nodes, such as `:refresh` and `:change`, are entered one
at a time: each must be sent on its own, not together with other commands. Each
answers with a **receipt**: one line that names the command, its target and
what it did, for example `change $replicas · definition updated · 4 marked stale`.

## Part 1: Dependencies and refresh

The first animation shows steps 1–4. After each refresh, the view returns to
the top, where the results change state.

![WesDesk defining replicas, perReplicaRps, capacityRps and headroomRps in one
command, inspecting headroomRps, listing names, refreshing replicas so that the
two downstream results turn stale, failing to read a stale result, a new
calculation waiting for its stale input, and a downstream refresh that makes
every result current again](06a-dependencies-and-refresh.gif)

### Step 1: Dependencies

Select the manual policy first, as a separate submission. The refresh examples
in steps 1–5 deliberately leave dependents stale so their dependencies can be
examined. New workspaces use `automatic`; step 6 explains the policies.

```text
:workspace policy mode:manual
```

Define the replica count, the capacity of one replica, the total capacity and
the headroom above a current load of 600 requests per second. The replica count
comes from a shell command.
`printf 3` prints the text `3`:

```text
sh run cmd:"printf 3" > replicas
:calc { return 250; } > perReplicaRps
:calc {
  return int(text($replicas.stdout)) * $perReplicaRps;
} > capacityRps
:calc { return $capacityRps - 600; } > headroomRps
```

```text
ok · 4 results · kept · local
✓ $replicas        ProcessOutput   exit 0
exit 0 · stdout 1 B · 1 line · stderr empty
✓ $perReplicaRps   Int
250
✓ $capacityRps     Int
750
✓ $headroomRps     Int
150
```

Several commands entered together form one cell with one result per command;
each result has its own header. `local` on the run line is the target that ran
the shell command (chapter 9). The `‹ $headroomRps ›` control in the action
keys selects which result of the cell the data keys act on.

`:inspect` describes a node: its state, its task, the nodes it depends on and
whether it is pure:

```text
:inspect $headroomRps
```

```text
id           id1003
state        READY
task         :calc
purity       pure
names        headroomRps
dependsOn    id1002
type         Int
```

`dependsOn` lists node identifiers; `id1002` is `$capacityRps`.

### Step 2: Listing results

`:list names` returns a table of all names with their node, type, state and
output:

```text
:list names
```

```text
Snapshot · 2026-09-30T08:12:43Z · Refresh

  name            node    type           state  output
  $replicas       id1000  ProcessOutput  READY  data
  $perReplicaRps  id1001  Int            READY  data
  $capacityRps    id1002  Int            READY  data
  $headroomRps    id1003  Int            READY  data
```

The table is a **snapshot**: it records the states at the moment it was
created and does not update itself. The `Refresh` button creates a new
snapshot. `:list nodes` lists all nodes with the same fields as `:inspect`, and
`:list runs` lists the latest run of every node.

### Step 3: Refresh one result

`:refresh` runs a node again with the same definition. Run the replica count
again:

```text
:refresh $replicas
```

```text
refresh $replicas · default / sh · target local · rev 1cdd6a70 · 1 execution requested · 1 started · 2 marked stale
```

`$replicas` runs again. `$capacityRps` and `$headroomRps` are not recalculated.
They become **stale**: their header starts with `~`, the value is shown below
`Stale · previous result`, and the footer counts `~ 2 results stale`. The
receipt reports what the command did when it was entered: one execution
requested and started, two results marked stale. For a provider call, it also
names the connection the result was made with: the environment and provider
(`default / sh`), the target, and the first eight characters of the
environment revision (`rev 1cdd6a70`). `:inspect` shows the full revision.
Chapter 12 shows what happens when that connection has changed.

A stale result is not used as a current value:

- `:read $headroomRps` fails, and the message names the result, the reason and
  the command that recalculates it:

  ```text
  RUN001: Result $headroomRps is stale: An upstream result was requested again;
  this result is no longer current. Use :refresh $capacityRps scope:downstream
  to recompute the selected work; if an earlier upstream is also stale, refresh
  that root with scope:downstream. This read did not rerun anything.
  ```

  A read never runs anything. The suggested command refreshes the nearest stale
  input; here, `$replicas` is already current.
- A new calculation that uses a stale result does not run. It waits:

  ```text
  :calc { return $headroomRps > 0; } > healthy
  ```

  ```text
  waiting · not kept
  · $healthy
  Waiting for data output from $headroomRps
  ```

  The cell offers `x cancel` while it waits.

wes never combines a new upstream value with an old downstream value without
saying so.

### Step 4: Refresh downstream

`scope:downstream` runs a node and every node that depends on it, directly or
indirectly:

```text
:refresh $replicas scope:downstream
```

`$replicas`, `$capacityRps` and `$headroomRps` run in order, and the waiting
`$healthy` runs too: the results are `750`, `150` and `true`. `$perReplicaRps`
does not depend on `$replicas` and does not run.

## Part 2: Changes, policies, timeouts and removal

The second animation shows steps 5 and 6.

![WesDesk defining the capacity results, changing the replica command so that
all dependent results turn stale, refreshing downstream to a capacity of 1250
and headroom of 650, switching to the reactive policy and refreshing, with a
receipt on each control command](06b-change-and-policy.gif)

### Step 5: Change a command

The service scales out to five replicas. `:change` replaces the arguments of a
provider call such as `sh run`:

```text
:change $replicas cmd:"printf 5"
```

```text
change $replicas · definition updated · 4 marked stale
```

`:change` does not run anything. `$replicas` and every result that depends on
it, including `$healthy`, become stale, with the messages `The definition
changed; the previous result is no longer current.` and `An upstream definition
changed; this result needs to be recalculated`. The cell keeps the command as
it was entered and adds the note `Submitted source is superseded for $replicas.
Current definition: sh run cmd:"printf 5"`. Run them explicitly:

```text
:refresh $replicas scope:downstream
:read $headroomRps
```

The capacity is now `1250` and the headroom `650`.

- `:change` applies to provider calls only. `:change` on a calculation fails
  with `MET004: the target is not a provider call`; define a new calculation
  instead.
- A change never runs by itself, in any policy. A provider call can have
  effects outside the workspace, so wes runs a changed definition only when
  asked.

### Step 6: Execution policy

The **execution policy** decides what happens to dependent results when a node
runs again:

| Policy | After `:refresh $node` |
| --- | --- |
| `automatic` (default) | calculations over existing data can run again |
| `manual` | dependents become stale |
| `reactive` | also allows provider operations to run again |

With `automatic`, a new input can update calculations that use existing data,
without making another service call. `reactive` can also repeat an operation
when its provider says it can be repeated and the workspace allows it to run.
If Wes cannot tell whether an operation ran, it does not automatically retry it.

Set the policy for the whole workspace:

```text
:workspace policy mode:reactive
:refresh $replicas
```

`$capacityRps`, `$headroomRps` and `$healthy` now run after `$replicas` without
`scope:downstream`.

`:policy $node mode:reactive` sets the policy of one node, overriding the
workspace policy. With `:policy $capacityRps mode:reactive` in a manual
workspace, a refresh of `$replicas` recalculates `$capacityRps`, while other
dependents become stale. The policy is stored with the workspace and still
applies after the workspace is opened again.

### Step 7: Timeouts

The third animation shows steps 7 and 8.

![WesDesk setting a two-second timeout, changing the command to one that sleeps
five seconds, a cancelled run with skipped dependents, unbinding a name,
removing the nodes and listing the remaining name](06c-timeouts-and-removal.gif)


`:timeout` limits how long a node may run. A replica check that hangs should
not block the workspace:

```text
:timeout $replicas after:PT2S
:change $replicas cmd:"sleep 5; printf 9"
:refresh $replicas
```

```text
failed · 4 results · 1 ok · 1 cancelled · 2 skipped · kept · local
ⓘ Submitted source is superseded for $replicas. Current definition: sh run cmd:"sleep 5; printf 9"
✗ $replicas
cancelled · The local operation was cancelled because its timeout expired.
✓ $perReplicaRps   Int
250
○ $capacityRps
skipped · an earlier stage failed
○ $headroomRps
skipped · an earlier stage failed
```

The note at the top says that the cell still shows the command as it was
entered, while `$replicas` now runs the changed definition.

- `after:` takes a duration (chapter 5): `PT2S` is two seconds.
- The run is cancelled with `RUN002: The local operation was cancelled because
  its timeout expired.`. Dependent results are skipped, not calculated from old
  values.
- Without `:timeout`, a finite node may run for 900 seconds; the `--node-timeout`
  startup option changes this default. Open streams are not limited by the
  default.
- `:cancel $node` stops a running node immediately. Streams, which run until
  stopped, use it most; [chapter 14](../14-prom/README.md#8-monitor-actual-logs-and-container-resources)
  shows live logs and cancellation.

### Step 8: Unbind and remove

`:name unbind` removes a name but keeps the node; `:remove` deletes a node and
all nodes that depend on it:

```text
:name unbind "healthy"
:remove $replicas scope:downstream
:list names
```

`:remove` deletes `$replicas`, `$capacityRps`, `$headroomRps` and the unnamed
node that was `$healthy`. `:list names` shows only `$perReplicaRps`.

- `scope:downstream` is required: `:remove` always removes dependents too, and
  the scope states that explicitly. Without it, `:remove $replicas` fails with
  `CMD001: Removal requires scope:downstream to approve stopping affected work
  and removing its definitions or names. Nothing was removed.`
  `:help remove` describes the command.
- The receipt counts what was removed:
  `remove downstream $replicas · 4 removed · 3 names unbound`.
- An unbound node keeps its result, which can still be read by its
  identifier. `unbind.wes` defines `$healthy` as node `id1004`, unbinds it, and
  reads `true` with `:read $id1004`.

## Watch out

### Stale means "not current", not "wrong"

A stale result keeps its previous value for display, marked
`Stale · previous result`. It is not used as an input and cannot be read with
`:read`. Refresh it, or refresh its upstream node with `scope:downstream`.

### Reopening a workspace runs nothing

When a workspace is opened again, changed or stale nodes stay as they were; wes
does not run them to catch up. On the command line, each invocation reopens the
workspace; a stale result then explains itself when it is read:
`RUN001: Result $capacityRps is stale: A definition or dependency changed; the
previous result is no longer current. Reopening preserved this stale state and
did not rerun the command. Use :refresh $replicas scope:downstream …`. Chapter
7 covers saving and loading.

### Identifiers in messages

Messages about results use their names, such as `$headroomRps`. The
descriptions of nodes use identifiers: `dependsOn: id1002` in `:inspect`, and
the `node` column of `:list names` and `:list runs`. `:list names` maps
identifiers to names.

### A receipt is not a result

A receipt reports what the command requested, started and marked stale when it
was entered, not how the runs ended. After `:refresh $replicas
scope:downstream`, the receipt reads `… · 4 executions requested · 1 started · 3
marked stale`: the three dependent results wait for `$replicas` and then run.
The cells show the outcome.

### Failures in this chapter

| Error | Cause |
| --- | --- |
| `RUN001` Result … is stale | `:read` of a stale result |
| `RUN001` Missing available output | `:read` of a failed result or one without output |
| `RUN002` cancelled because its timeout expired | a run longer than its `:timeout` |
| `MET004` the target is not a provider call | `:change` on a calculation |
| `CMD001` Removal requires scope:downstream … | `:remove` without the scope |
| `ENG005` submit … separately | a control command sent together with other commands |

## Run the programs

`session.wes` contains every command of this chapter. The line `// ---`
separates commands that must be sent one at a time. In the client, enter them
in order. On the command line, send each part with `--command` to the same
data folder and workspace, so that each invocation continues the previous one.
The command line prints `ProcessOutput` as JSON, with `stdout` and `stderr` in
base64 (`"Mw=="` is `3`), and says so in a line starting with `[value]`:

```sh
$WES --home /tmp/wes-tutorial-06 --workspace capacity --command ':list names'
```

`unbind.wes` and `exercises.wes` are built the same way. `check.py` sends
every part of the three files in order and verifies each result and message:

```sh
python3 06-nodes-and-dependencies/check.py
```

## Summary

| Command | Effect |
| --- | --- |
| `:inspect $r` | describe a node: state, task, dependencies, purity |
| `:list names`, `:list nodes`, `:list runs` | snapshots of names, nodes and runs |
| `:read $r` | read the current value of a result |
| `:refresh $r` | run a node again; dependents follow the policy |
| `:refresh $r scope:downstream` | run a node and all its dependents |
| `:change $r arg:value` | change a provider call; runs nothing |
| `:workspace policy mode:automatic\|manual\|reactive` | set the default policy |
| `:policy $r mode:automatic\|manual\|reactive` | set the policy of one node |
| `:timeout $r after:PT2S` | limit the run time of a node |
| `:cancel $r` | stop a running node |
| `:name unbind "r"` | remove a name, keep the node |
| `:remove $r scope:downstream` | delete a node and its dependents |

## Exercises

Start from a new workspace with the four definitions of step 1.

1. The load rises to 900 requests per second. Define the new headroom as a new
   result, and explain why `:change` cannot update `$headroomRps`.
2. Make `$capacityRps` reactive while the workspace stays manual. Which results
   are stale after `:refresh $replicas`?
3. After `:refresh $replicas` in a manual workspace, which command makes every
   result current with one command?

<details>
<summary>Answers</summary>

1. `:calc { return $capacityRps - 900; } > headroomAt900` gives `-150`.
   `$headroomRps` is a calculation, and `:change` applies only to provider
   calls (`MET004`).
2. `:policy $capacityRps mode:reactive`, then `:refresh $replicas`:
   `$capacityRps` runs again; `$headroomRps` and `$headroomAt900`, which depend
   on it and use the manual workspace policy, become stale. `:list runs` shows
   the states.
3. `:refresh $replicas scope:downstream`.

`exercises.wes` contains these commands; `check.py` verifies them.

</details>

## Next

[Chapter 7, *Saving, loading and keeping results*](../07-saving-and-keeping/README.md),
covers named workspaces, what
is kept when a workspace is saved, and why opening a workspace never repeats
external work.
