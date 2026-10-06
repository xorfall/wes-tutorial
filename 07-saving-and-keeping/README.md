# 7. Saving, loading and keeping results

This chapter covers what survives when a workspace is closed and opened again:
named workspaces, snapshots taken with `:workspace save`, results that are
kept or not kept, and the review step that protects workspace deletion.

The example keeps a snapshot of a capacity calculation before a scaling change,
opens it again later, and deletes it when it is no longer needed.

## Prerequisites

- Chapters [1](../01-first-calculations/README.md) to
  [6](../06-nodes-and-dependencies/README.md), in particular stale results and
  `:refresh` from chapter 6.
- Running the programs requires a local build of wes; see
  [Run the programs](#run-the-programs).

## Data homes and workspaces

A **data home** is a folder that holds all wes data: workspaces, kept results,
the API library and settings. `--home DIR` selects it when wes starts; the
default is `~/.wes`. Tutorials use a separate folder, such as
`/tmp/wes-tutorial`, so that experiments never touch other data.

A data home contains any number of **workspaces**. Each has a name, its own
commands and results, and its own execution policy. The workspace named
`default` is opened when no other is selected; `--workspace NAME` opens another
one at startup. The client shows the current workspace in its header:
`wes / default`.

The current workspace is stored as it changes. Nothing needs to be saved to
continue later.

## Part 1: Save, load and keep

The first animation shows steps 1–4. The server was started with
`--keep-under 200`, so that one result is too large to be kept (step 4).

![WesDesk listing the default workspace, defining a capacity of 750 that is
kept and a list of 100 request identifiers that is not kept, saving the
workspace as capacity-0930, listing both workspaces, adding a result after the
save, loading capacity-0930 so that the header changes and the request list is
stale because it was not kept, and refreshing it](07a-save-load-and-keep.gif)

### Step 1: Workspaces

```text
:list workspaces
```

The result is `["default"]`: a new data home contains only the default
workspace. `:list workspaces` lists the workspaces of the current data home.

Define a capacity and a list of request identifiers for the investigation:

```text
:calc { return 750; } > capacityRps
:calc {
  return range(100).map(i => "request-" + text(i));
} > requestIds
```

The run line of `$capacityRps` shows `kept`; the run line of `$requestIds`
shows `not kept`. Step 4 explains the difference.

### Step 2: Save a snapshot

Before the service is scaled, save the state of the investigation under a new
name:

```text
:workspace save "capacity-0930"
:list workspaces
```

`:workspace save` answers `saved workspace 'capacity-0930'`, and
`:list workspaces` returns `["capacity-0930", "default"]`.

`:workspace save` copies the current workspace to a new saved workspace. The
current workspace does not change: it is still `default`, and work continues in
it. Add a result after the save:

```text
:calc { return 1250; } > afterScaleOut
```

`default` now has three names; `capacity-0930` still has two. The two
workspaces are independent from this point on.

- Saving under a name that already exists replaces that saved workspace without
  asking; the answer is then `replaced saved workspace 'capacity-0930'`. Choose
  a new name, such as one with a date, for each snapshot.
- Save and load are entered one at a time, like the control commands of
  chapter 6. On the command line, `--sequential` runs a file of such commands in
  order (step 5).

### Step 3: Load a saved workspace

```text
:workspace load "capacity-0930"
```

The header changes to `wes / capacity-0930`, and the session shows the commands
and results of the snapshot. `$afterScaleOut` is not there: it was added to
`default` after the save.

**Loading runs nothing.** Every result that was kept appears with its value.
Every result that was not kept is stale:

```text
❯ :calc { return 750; } > capacityRps
ok · kept
✓ $capacityRps   Int
750

❯ :calc { … } > requestIds
stale · No retained result was available when the workspace reopened. The command was not rerun. · 1 stale
~ $requestIds
stale · the value was not re-run
```

The cell of `:list workspaces` is stale for the same reason: its result was too
large to keep with `--keep-under 200`.

`:read $requestIds` fails with `RUN001: Result $requestIds is stale: No retained
result was available when the workspace reopened. The command was not rerun.
Use :refresh $requestIds to recompute the selected work; …`. The stale result
keeps its type, `List<Text>`, so calculations that use it are still checked
before running. Run it again when its value is needed:

```text
:refresh $requestIds
```

This rule protects external systems. A workspace can contain commands that
call APIs, run programs or change containers; opening it must never repeat
them.

On the command line, `--workspace capacity-0930` opens the saved workspace at
startup. `:workspace load` changes the current workspace of the running session
only; the next command-line invocation opens `default` again unless
`--workspace` is given.

### Step 4: Kept and not kept results

A result is **kept** when its value is stored in the data home, so that it is
available after the workspace is opened again. wes keeps each finite result
automatically when its size is under a limit:

| Startup option | Effect |
| --- | --- |
| (none) | keep results of at most 10 MiB (10485760 bytes) |
| `--keep-under BYTES` | keep results of at most `BYTES` |
| `--no-auto-keep` | keep no results automatically |

- The size is the number of bytes wes stores for a result: the encoded value
  with its type and origin. It is larger than the JSON text of the value: with
  `--keep-under 200`, the list of 100 identifiers is not kept, and even the
  result of `:list workspaces` is not kept. The details of a result show its
  stored size and the current limit.
- Results that are not finite values are not kept: iterators (chapter 4) are
  recipes, and failed runs have no value.
- The limit applies when a result is produced. Starting wes later with a larger
  limit does not keep results that were produced earlier and not kept.
- A cell that holds several results counts them: `1 of 2 kept` when only one of
  two results was kept. Failed results have no value and are not counted.

## Part 2: Deletion plans

The second animation shows step 5.

![WesDesk saving capacity-0930, planning its deletion and showing the plan with
its expiry of 120 seconds, deleting it, listing the remaining default
workspace, planning the deletion of the current workspace, adding a result, and
a refused deletion because the workspace changed after the plan was
made](07b-deletion-plans.gif)

### Step 5: Delete a workspace

Deleting a workspace removes its commands and the results that only it uses.
It takes two steps. First, create a **deletion plan**, which describes what
would be deleted:

```text
:workspace plan delete workspace:"capacity-0930" > plan
```

```text
ok · not kept
✓ $plan   WorkspaceDeletePlan
expiresInSeconds  120
workspace         "capacity-0930"
identity          "…"
cells             1
show 13 more · 13 not shown
```

The plan has seventeen fields; `show 13 more` lists the others, among them
`nodes`, `exclusivePayloads`, `protectedPayloads`, `lifetime` (`session only;
applying revalidates the captured workspace`), `running` and `streams`. A plan
is not kept: it is valid only in the session that made it.

| Field | Meaning |
| --- | --- |
| `workspace`, `identity` | the workspace the plan applies to |
| `cells`, `nodes` | how many commands and nodes it contains |
| `running`, `streams`, `terminals` | work that is still active |
| `exclusivePayloads` | kept results that only this workspace uses and that would be removed |
| `protectedPayloads` | kept results that need explicit approval to remove |
| `sharedWorkspaces` | other workspaces that share results with this one; they keep them |
| `blockers` | reasons the deletion cannot happen |
| `preserved` | what deletion never touches: other workspaces, the API library, saved credentials, source files, and effects outside wes |

Then apply the plan:

```text
:workspace delete $plan
:list workspaces
```

`capacity-0930` is deleted, and `:list workspaces` returns `["default"]`.

- A plan expires after 120 seconds, and it belongs to the session that created
  it. It cannot be applied from another session or after the workspace was
  opened again.
- On the command line, one `--sequential` invocation is one session, so a plan
  and its application can be sent together; see
  [Deletion on the command line](#deletion-on-the-command-line).
- A plan describes the workspace at the moment it was made. If anything that
  affects the deletion changes before the plan is applied, the deletion is
  refused and nothing is deleted:

  ```text
  :workspace plan delete > current
  :calc { return 1; } > late
  :workspace delete $current
  ```

  ```text
  not run · STO003: The deletion preview expired or its workspace, work,
  retention or saved references changed. Request a new preview; nothing was
  deleted by this request.
  ```

  Reading or inspecting the plan does not invalidate it.
- Without `workspace:`, the plan applies to the current workspace.
- `:workspace delete $plan stop:true` also approves stopping work that is still
  running, and `protected:true` approves removing protected results. Blockers
  and runs with an unknown outcome refuse the deletion even with these
  options.
- Stopping a command is not a rollback: effects it already had outside wes
  remain.

## Watch out

### Deletion on the command line

On the command line, each invocation is a new session. A plan created in one
invocation is no longer valid in the next: `:workspace delete $plan` answers
`Expected a live WorkspaceDeletePlan; use a plan node reference and replan if
its authority has expired or was restored.`

`--sequential` runs the statements of one `--command` or `--file` one after
another in a single session, so the plan and the deletion belong together.
`delete.wes`:

```text
:workspace save "capacity-0930"
:workspace plan delete workspace:"capacity-0930" > plan
:workspace delete $plan
:list workspaces
```

```sh
$WES --home /tmp/wes-tutorial-07 --sequential --file 07-saving-and-keeping/delete.wes
```

The deletion answers `Workspace deletion completed.`, and the last line is
`["default"]`. The command line prints the plan as indented JSON.

- The whole file is checked for syntax errors before the first statement runs;
  an error runs nothing.
- The first statement that is refused or fails stops the run, and wes exits
  with a non-zero status. `refused.wes` changes the workspace between the plan
  and the deletion; the deletion is refused with `STO003` and the run stops.
- Without `--sequential`, a file that mixes save, load or delete with other
  commands fails with `ENG005`, as in chapter 6; on the command line its hint
  reads `For an ordered CLI workflow, use --sequential.`

### Saving is copying

`:workspace save` never renames the current workspace and never switches to the
saved one. To continue in the saved workspace, load it.

### Failures in this chapter

| Message | Cause |
| --- | --- |
| `MET011` there is no saved workspace with this name | `:workspace load` of an unknown name |
| `STO003` The deletion preview expired or … changed | applying an expired or outdated plan |
| `Expected a live WorkspaceDeletePlan` | applying a plan from another session or invocation |
| `ENG005` submit … separately | save, load or delete sent together with other commands |

## Run the programs

`session.wes` contains the commands of steps 1–3 and 5, separated by `// ---`.
Lines such as `// workspace: capacity-0930` mark commands that run in the
saved workspace; on the command line, send them with
`--workspace capacity-0930`:

```sh
$WES --home /tmp/wes-tutorial-07 --keep-under 200 --workspace capacity-0930 --command ':list names'
```

`delete.wes` and `refused.wes` run with `--sequential`. `check.py` sends every
part of `session.wes` in order with `--keep-under 200`, then runs the two
sequential files, and verifies the results, the stale state and type of the
result that was not kept, the deletion plan, the refusal to apply a plan from
another invocation, the deletion and the `STO003` refusal:

```sh
python3 07-saving-and-keeping/check.py
```

## Summary

| Command or option | Effect |
| --- | --- |
| `--home DIR` | select the data home |
| `--workspace NAME` | open a workspace at startup |
| `:list workspaces` | list the workspaces of the data home |
| `:workspace save "name"` | copy the current workspace to a saved workspace |
| `:workspace load "name"` | switch to a saved workspace; runs nothing |
| `--keep-under BYTES`, `--no-auto-keep` | change automatic keeping |
| `--sequential` | run the statements of a command or file in order, in one session |
| `:workspace plan delete [workspace:"name"] > plan` | describe a deletion |
| `:workspace delete $plan [stop:true] [protected:true]` | apply a deletion plan |

## Exercises

1. After step 3, which command makes `$requestIds` available again, and why is
   it not available right after loading?
2. `default` is the current workspace. Which commands show whether a saved
   workspace named `capacity-0930` still contains `$afterScaleOut`, without
   leaving `default` on the command line?
3. A deletion plan was created two minutes ago. What happens when it is
   applied now, and what should be done instead?

<details>
<summary>Answers</summary>

1. `:refresh $requestIds`. The list was larger than the keep limit, so its value
   was not stored, and loading never runs commands again.
2. `$WES --home … --workspace capacity-0930 --command ':list names'`; the list
   contains `$capacityRps` and `$requestIds` only.
3. The plan has expired, so the deletion is refused with `STO003` and nothing is
   deleted. Create a new plan and apply it within 120 seconds.

</details>

## Next

[Chapter 8, *Sandbox*](../08-sandbox/README.md), covers running commands in an
isolated, memory-only workspace to try them without changing the current
workspace.
