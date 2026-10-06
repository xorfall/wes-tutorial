# 8. Sandbox

This chapter covers sandboxes: named programs that run in their own
memory-only workspace, separate from the current one. A sandbox is a place to
try a calculation, change it and read its results without adding cells or
changing the results of the workspace.

The example tries capacity plans for a service: "what if the service ran six
replicas that each handle 300 requests per second?", while the workspace keeps
its measured capacity.

## Prerequisites

- Chapters [1](../01-first-calculations/README.md) to
  [7](../07-saving-and-keeping/README.md), in particular `:read`, `:inspect`,
  `:cancel` and `:refresh` from chapter 6.
- The sandbox is used from the client. Running the check requires a local build
  of wes; see [Run the programs](#run-the-programs).

## What a sandbox is

| | Workspace | Sandbox |
| --- | --- | --- |
| Holds | cells, nodes, names | one named program with its members |
| Results | kept according to size (chapter 7) | memory only, never kept |
| Stored in the data home | commands and kept results | the program text only |
| Visible in the session | one cell per command | a preview panel, opened with `:read` |
| Listed by | `:list names` | `:list sandboxes` |
| References | any workspace result | only members of the same sandbox |

The results of a sandbox are called its **members**: the names bound inside its
program.

## Part 1: Define and read

The first animation shows steps 1–3.

![WesDesk defining the workspace capacity of 750, defining a sandbox named
whatIf, and opening its preview panel, which lists four members with their
types, states and values: 6 replicas, 300 per replica, a capacity of 1800 and a
headroom of 900; then reading only the headroom, and inspecting the members
without values](08a-define-and-read.gif)

### Step 1: The workspace result

The workspace holds the measured capacity:

```text
:calc { return 750; } > capacityRps
```

### Step 2: Define a sandbox

`:sandbox { ... } > name` defines a sandbox and starts it. The braces contain
an ordinary program, one command per line:

```text
:sandbox {
  :calc { return 6; } > replicas
  :calc { return 300; } > perReplicaRps
  :calc { return $replicas * $perReplicaRps; } > capacityRps
  :calc { return $capacityRps - 900; } > headroomRps
} > whatIf
```

The command adds no cell to the session. Open the sandbox with `:read`:

```text
:read $whatIf
```

A panel opens above the session:

```text
whatIf   Sandbox · current values · results in memory                 close

4 members
Member           Type   State   Value
$replicas        Int    ready   6
$perReplicaRps   Int    ready   300
$capacityRps     Int    ready   1800
$headroomRps     Int    ready   900

Providers use their real configured targets. Isolation applies to results, not
machine or service effects.

Closing this view leaves the sandbox active. Use :cancel $whatIf to stop it.
```

- The sandbox has its own `$capacityRps` (1800). The workspace `$capacityRps`
  (750) is a different result and does not change.
- `results in memory` means that the data home stores the program text, never
  the values. The command line shows the same as `"persistence": "definition
  only"`.
- The last line of the panel follows the state of the sandbox as a whole:
  active, stopped or not run.
- The panel updates every second while it is open. <kbd>Esc</kbd> or `close`
  closes it; the sandbox stays active.
- A sandbox must have a name (`> whatIf`) and a program:
  `:sandbox { }` fails with `SBX001: sandbox requires a program`.

### Step 3: Read one member

Add the member name after the sandbox name to read one value:

```text
:read $whatIf.headroomRps
```

The panel shows `900`. `:inspect $whatIf` shows the members with their types
and states but without values: `Sandbox · inspect · results in memory`.

## Part 2: Change, isolation and lifetime

The second animation shows steps 4–7.

![WesDesk redefining whatIf with four replicas and reading a capacity of 1200
and a headroom of 300, a sandbox that refers to the workspace capacity failing
before it runs, a workspace calculation that cannot read the sandbox, a sandbox
with one failed member and one ready member, and stopping and restarting
whatIf](08b-isolation-and-lifecycle.gif)

### Step 4: Change the program

Defining a sandbox again with the same name replaces its program and runs it
again. Try four replicas:

```text
:sandbox {
  :calc { return 4; } > replicas
  :calc { return 300; } > perReplicaRps
  :calc { return $replicas * $perReplicaRps; } > capacityRps
  :calc { return $capacityRps - 900; } > headroomRps
} > whatIf
:read $whatIf
```

The members are now `4`, `300`, `1200` and `300`. Repeat until the plan fits;
the workspace is not touched.

### Step 5: Isolation

A sandbox and the workspace cannot read each other's results.

A sandbox cannot use a workspace result. This definition is refused before it
runs:

```text
:sandbox {
  :calc { return $capacityRps * 2; } > doubled
} > fromWorkspace
```

The cell shows that the definition was refused, with the reason:

```text
refused · CAL010: Calculation analysis failed at this span. Check referenced
names, fields, types and supported operations. Reference $capacityRps. Sandbox
calculations can only reference their own declared members; parent workspace
results are not visible. · nothing ran
```

The client shows the reason on one line; when it is longer than the cell,
`▸ show full message` displays it completely. Inside a sandbox, `$capacityRps`
would have to be one of its own members.

The workspace cannot use a sandbox member:

```text
:calc { return $whatIf.capacityRps; } > copied
```

```text
not run · CAL010: unknown workspace output '$whatIf' · nothing ran
```

To move a result from a sandbox into the workspace, enter its calculation in
the workspace.

### Step 6: Failures inside a sandbox

A failing member does not stop the others:

```text
:sandbox {
  :calc { return 900 / 0; } > perReplica
  :calc { return 4 * 300; } > capacityRps
} > faulty
:read $faulty
```

`perReplica` is `failed` with error code `CAL005` (division by zero), and
`capacityRps` is `ready` with `1200`. The error details are part of the member
in the panel; their locations name the source `sandbox $faulty`, with the line
and column inside the sandbox program.

### Step 7: Stop and restart

A sandbox runs until it is stopped. Stop it, and start it again:

```text
:cancel $whatIf
:read $whatIf
:refresh $whatIf
:read $whatIf
```

After `:cancel`, the sandbox and every member are `stopped`, the members have no
value, and the panel ends with `Sandbox stopped. Use :refresh $whatIf to run it
again.` `:refresh` runs the program again, and the members are `ready` with
their values.

When wes starts again, the sandbox program is still defined, but nothing runs:
`:read $whatIf` shows the sandbox and every member as `not run`, and the panel
ends with `Only the definition was restored. Use :refresh $whatIf to run it.`

## Part 3: List and remove

The third animation shows step 8.

![WesDesk defining the sandboxes whatIf and faulty, listing both, removing faulty
with scope:downstream, and listing only whatIf](08c-list-and-remove.gif)

### Step 8: List and remove sandboxes

The definitions of a workspace are listed by name, and removed like nodes:

```text
:list sandboxes
:remove $faulty scope:downstream
:list sandboxes
```

The first list is `["faulty", "whatIf"]`: `fromWorkspace` was refused in step 5,
so it was never defined. `:remove` stops the sandbox, waits until it has
stopped, and deletes its definition; the second list is `["whatIf"]`.

- Listing runs nothing; it reads the stored definitions.
- `scope:downstream` is required, as for nodes (chapter 6). Without it, the
  command fails with `CMD001: Removal requires scope:downstream to approve
  stopping affected work and removing its definitions or names. Nothing was
  removed.`
- Removing a sandbox removes its program and its results. It does not undo
  effects of providers that the program called.
- If wes cannot tell whether a call made from this workspace had an external
  effect, removal is refused and the definition stays; the message refers to
  the log.

## Watch out

### A sandbox isolates results, not effects

A sandbox program may call providers, such as `sh run`. The call is real:
the command runs on the machine, and an HTTP request reaches its service.
Only its result stays in the sandbox. Do not use a
sandbox to try commands whose effects must not happen.

### No cell in the session

Sandbox commands add no cells to the session; the preview panel is the view of
a sandbox in the client. On the command line, `:sandbox`, `:read`, `:inspect`,
`:cancel` and `:refresh` print the observation as indented JSON. After a restart:

```sh
$WES --home /tmp/wes-tutorial-08 --sequential \
  --command ':refresh $whatIf
:read $whatIf.capacityRps'
```

```text
whatIf: {
  "kind": "Sandbox",
  "persistence": "definition only",
  "state": "active",
  "members": [
    …
  ]
}
whatIf: 1200
```

A member marked private is withheld from the command line with a notice on
standard error, as for workspace results.

### Definitions stay until removed

A sandbox definition is stored in the data home until it is replaced or
removed with `:remove`. Deleting the workspace (chapter 7) deletes its
sandbox definitions too.

### Failures in this chapter

| Message | Cause |
| --- | --- |
| `SBX001` sandbox requires a program | empty braces |
| `CMD001` Name the sandbox with > name. | a sandbox without `> name` |
| `refused · CAL010` Calculation analysis failed … Reference $capacityRps … | a sandbox that refers to a workspace result |
| `CAL010` unknown workspace output '$whatIf' | a workspace calculation that refers to a sandbox |
| `CMD001` Removal requires scope:downstream … | `:remove` of a sandbox without the scope |
| member `failed` with its own error | a failing calculation inside the sandbox |

## Run the programs

`session.wes` contains the commands of this chapter, separated by `// ---`;
enter them in the client in order.

`check.py` starts its own `wes --serve` on a free loopback port with a
temporary data home, sends each command the way the client does, and reads the
sandbox observations. It restarts the server to verify the `not run` state,
lists and removes a sandbox, and uses the command line to verify the list, the
exercise, that the workspace kept `750` and that it cannot read the sandbox:

```sh
python3 08-sandbox/check.py
```

## Summary

| Command | Effect |
| --- | --- |
| `:sandbox { ... } > name` | define or replace a sandbox and run it |
| `:read $name` | open the preview panel with all members |
| `:read $name.member` | read one member |
| `:inspect $name` | members with types and states, without values |
| `:cancel $name` | stop the sandbox |
| `:refresh $name` | run the sandbox again |
| `:list sandboxes` | list the sandbox definitions of the workspace |
| `:remove $name scope:downstream` | stop the sandbox and delete its definition |

## Exercises

1. Change `whatIf` so that it computes how many replicas of 300 requests per
   second are needed for a load of 900. Which member gives the answer?
2. After defining the sandbox of exercise 1, what does `$capacityRps` in the
   workspace contain, and why?
3. wes was restarted. Which two commands show the current values of `whatIf`?
4. Which command deletes the sandbox of exercise 1, and what does it not undo?

<details>
<summary>Answers</summary>

1. For example:

   ```text
   :sandbox {
     :calc { return 900; } > loadRps
     :calc { return 300; } > perReplicaRps
     :calc { return div($loadRps + $perReplicaRps - 1, $perReplicaRps); } > replicas
   } > whatIf
   ```

   `:read $whatIf.replicas` gives `3`. `div(a + b - 1, b)` divides and rounds up
   (chapter 2).
2. Still `750`. The sandbox and the workspace do not share results.
3. `:refresh $whatIf`, then `:read $whatIf`.
4. `:remove $whatIf scope:downstream`. It does not undo effects of providers the
   program called; this program calls none.

`exercises.wes` contains the sandbox of exercise 1; `check.py` verifies it.

</details>

## Next

The next chapters connect the workspace to local lab systems.
[Chapter 9, *Environments and targets*](../09-environments-and-targets/README.md),
covers where commands run and which services they may reach.
