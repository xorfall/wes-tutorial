# 9. Environments and targets

This chapter covers where commands run. A **target** is a place that runs
commands: the local machine, a container or a host reached over SSH. An
**environment** binds providers to targets, so that the same command can run
in different places under different names.

The example uses a small lab of two containers. One runs an `orders-api`
service and is reached through Docker. The other is an `edge-host` that is
reached over SSH, like a remote server. Commands run in both, and on the local
machine, from one workspace.

## Prerequisites

- Chapters [1](../01-first-calculations/README.md) to
  [8](../08-sandbox/README.md).
- Docker with Compose v2, an OpenSSH client (`ssh`, `ssh-keygen`,
  `ssh-keyscan`), and a local build of wes; see
  [Run the programs](#run-the-programs).

## The lab

The folder `lab/` contains everything the chapter needs:

| File | Purpose |
| --- | --- |
| `compose.yaml` | two containers in the Compose project `wes-tutorial-09` |
| `orders-api/` | files mounted read-only into the `orders-api` container: `VERSION`, `deploy.log` |
| `edge-host/Dockerfile` | an Alpine image with an SSH server and one user, `ops`, that accepts only keys |
| `environments.yaml` | the environment package of this chapter |
| `setup.sh` | creates a key pair in `lab/.state/`, starts the containers and records the host key |
| `teardown.sh` | stops the containers and removes the image and the generated keys |

Start the lab from the repository root:

```sh
sh 09-environments-and-targets/lab/setup.sh
```

- `setup.sh` builds the `edge-host` image on first use, which downloads the
  OpenSSH package for Alpine.
- The SSH server listens only on `127.0.0.1:2222`, and accepts only the key
  generated in `lab/.state/`. Nothing else is published.
- The key and the `known_hosts` file are generated in `lab/.state/`, which is
  not part of the repository. `environments.yaml` refers to them with paths
  relative to itself.

## Part 1: Targets, environments and plans

The first animation shows steps 3–5, after the lab has been started.

![WesDesk planning the lab environment package, applying it, selecting the lab
environment, listing the providers app, edge and local, and running a command
on each target: the local machine, the orders-api container and the edge-host
reached over SSH, each cell labelled with the environment and target
name](09a-plan-apply-and-run.gif)

### Step 1: Targets

The first part of `environments.yaml` declares three targets:

```yaml
targets:
  local:
    kind: local
  orders_api:
    kind: docker
    socket: /var/run/docker.sock
    compose: {project: wes-tutorial-09, service: orders-api}
    inherit: container
    shell: /bin/sh
    cwd: /srv/orders-api
  edge:
    kind: ssh
    client: /usr/bin/ssh
    host: 127.0.0.1
    port: 2222
    user: ops
    identity_file: .state/id_ed25519
    known_hosts: .state/known_hosts
    shell: posix
    inherit: remote
    cwd: /home/ops
```

| Kind | Runs commands | Main fields |
| --- | --- | --- |
| `local` | on the machine that runs wes | `cwd`, `env` |
| `docker` | inside a running container, through the Docker socket | `socket`; `compose` (project, service, optional replica) or `container` (a full container ID); `shell`, `cwd`, `env` |
| `ssh` | on a remote host, through the OpenSSH client | `client`, `host`, `port`, `user`, `identity_file`, `known_hosts`, `shell: posix`, `cwd`, `env` |

- `inherit: container` gives commands the environment variables of the
  container, such as `SERVICE_VERSION`; `inherit: remote` gives them the login
  environment of the SSH user.
- `compose` finds the container by its Compose labels, so the target keeps
  working when the container is recreated with a new ID.
- `known_hosts` is required. wes connects only to a host whose key is listed
  there; `setup.sh` records the key of `edge-host` with `ssh-keyscan`.
- `env` sets extra variables for every command on the target, as a map of
  names to text values.
- `identity_file` and `known_hosts` are absolute or relative to the directory
  of the package file, never to the directory where wes was started. `~` is not
  expanded: `~/.ssh/id_ed25519` fails while planning with `ENV010: SSH paths do
  not expand '~'; use an absolute path or a path relative to the package
  directory`.
- `client` is the OpenSSH program. The `PATH` is not searched: `client: ssh`
  fails with `ENV010: SSH client does not search PATH; use ./ssh or an absolute
  executable path`.
- wes checks that both files exist while planning and again right before each
  SSH command, without reading their contents. A missing file is refused before
  anything runs: `ENV010: SSH identity file was not found` or `ENV010: SSH
  known-hosts file was not found`. The contents do not affect the revision.

### Step 2: Environments

The second part binds providers to the targets:

```yaml
environments:
  lab:
    imports:
      local:
        source: {kind: builtin, name: sh}
        bind: {target: local, timeout_ms: 10000}
      app:
        source: {kind: builtin, name: sh}
        bind: {target: orders_api, timeout_ms: 10000}
      edge:
        source: {kind: builtin, name: sh}
        bind: {target: edge, timeout_ms: 10000}
```

- An environment is a named set of **imports**. Each import has a name, a
  `source` (here the built-in shell provider `sh`) and a `bind` that says which
  target it uses.
- The import name becomes the provider name in commands. The same `sh`
  provider is imported three times, as `local`, `app` and `edge`, so
  `app run` runs in the container and `edge run` runs on the SSH host.
- `timeout_ms` is the default time limit of a command through this import.
- The file is an **environment package**: `version`, a `package` name, the
  targets and the environments.

### Step 3: Plan

Environment packages are applied in two steps. First, wes checks the package and
shows what would change:

```text
:env plan file:"09-environments-and-targets/lab/environments.yaml" > proposed
```

```text
plan 'proposed': 1 environment change; apply uses these captured inputs
lab: new (revision sha256:b5927d…); imports added: app, edge, local
  id=lab abstract=false retired=false protected=false
  app: origin=lab target=orders_api endpoint=descriptor-defined private=false credential-refs={}
  edge: origin=lab target=edge endpoint=descriptor-defined private=false credential-refs={}
  local: origin=lab target=local endpoint=descriptor-defined private=false credential-refs={}
```

The second line summarises the change: `lab` is new, and three imports are
added. A changed package lists imports that are added, removed or rebound. The
indented lines show the planned definition of the environment and of each
import.

- Planning runs nothing and contacts no target.
- `sha256:…` is the **revision** of the environment: a fingerprint of its
  definition. A changed package gives a new revision.
- A relative `file:` path is resolved from the directory where wes was started;
  the animation starts the server in the repository root. Paths inside the
  package are then resolved from the package directory, as in step 1.

### Step 4: Apply and select

```text
:env apply $proposed
:env use "lab"
:list providers
```

- `:env apply` publishes the planned definitions: `published 1 environment
  change`.
- `:env use "lab"` selects the environment for this client. The footer changes
  to `env: lab`. Other clients can use other environments at the same time.
- `:list providers` returns the providers of the selected environment:
  `app`, `edge` and `local`, each with environment `lab`.
- `:list environments` lists all environments of the data home, for example
  `["default", "lab"]`. `:env clear` returns to no selection.

### Step 5: Run on three targets

```text
local run cmd:"echo running on the local machine" > onLocal
app run cmd:"hostname; cat VERSION; echo $SERVICE_VERSION" > onApp
edge run cmd:"hostname; whoami; cat /etc/edge-release" > onEdge
```

```text
ok · kept · lab · local
✓ $onLocal   ProcessOutput   exit 0
exit 0 · stdout 29 B · 1 line · stderr empty
stdout  1  running on the local machine

ok · kept · lab · orders_api
✓ $onApp   ProcessOutput   exit 0
exit 0 · stdout 34 B · 3 lines · stderr empty
stdout  1  orders-api
        2  orders-api 2.4.1
        3  2.4.1

ok · kept · lab · edge
✓ $onEdge   ProcessOutput   exit 0
exit 0 · stdout 41 B · 4 lines · stderr empty
stdout  1  edge-host
        2  ops
        3  edge-host
        4  region=eu-west-1
```

- The run line of each cell shows the environment (`lab`) and the target that
  ran the command.
- In the container, `cat VERSION` reads `/srv/orders-api/VERSION`, because the
  target's working directory is `/srv/orders-api`, and `$SERVICE_VERSION` comes
  from the container.
- On the SSH host, the command runs as the user `ops`.
- The result type `ProcessOutput` has `exitCode`, `stdout` and `stderr`. The
  outputs are `Bytes`; the cell shows their size and their lines, numbered,
  and `text(bytes)` converts them in a calculation (step 6).
- `run` is an **UNSAFE** operation: it can change the target. `:help app run`
  shows `Safety UNSAFE`.

## Part 2: Outputs and failures

The second animation shows steps 6 and 7.

![WesDesk applying and selecting the lab environment, running commands in the
container and over SSH, combining both outputs into one record, a command that
exits with status 1 and a stderr message, and an SSH command stopped by a
one-second timeout](09b-outputs-and-failures.gif)

### Step 6: Outputs are data

Combine the outputs of both targets:

```text
:calc {
  return {
    app:  iter.lines(text($onApp.stdout)).collect(),
    edge: iter.lines(text($onEdge.stdout)).collect(),
  };
} > hosts
```

The result is
`{ app: ["orders-api", "orders-api 2.4.1", "2.4.1"], edge: ["edge-host", "ops", "edge-host", "region=eu-west-1"] }`.

A command that fails on the target is still a result:

```text
app run cmd:"cat missing.txt" > missing
```

```text
ok · kept · lab · orders_api
✓ $missing   ProcessOutput   exit 1
exit 1 · stdout empty · stderr 57 B · 1 line
stderr  1  cat: can't open 'missing.txt': No such file or directory
```

The cell is `ok`: the command ran and reported its exit code. Decide in a
calculation what an exit code means, for example with
`$missing.exitCode == 0`.

### Step 7: When a target fails

When wes cannot run a command or cannot tell how it ended, the result fails:

```text
edge run cmd:"sleep 3; echo late" timeout:PT1S > slow
```

```text
failed · ENV036 · not kept · lab · edge
SSH execution exceeded its time budget; remote work may have run or still be
running. No automatic retry or remote cleanup is claimed.
```

| Situation | Message |
| --- | --- |
| the Compose service has no running container | `ENV038: Compose target wes-tutorial-09/orders-api has no running service container` |
| the command exceeds its time limit on SSH | `ENV036: SSH execution exceeded its time budget; remote work may have run or still be running.` |
| SSH fails, for example because the host key is not in `known_hosts` | `ENV036: SSH client did not report a trustworthy remote exit (status 255 or signal); remote work may have run or still be running.`, followed by the SSH message, such as `Host key verification failed.` |
| the provider is not imported | `RES004: 'db' is neither a meta command nor an imported provider` |

- `timeout:` overrides the `timeout_ms` of the import for one command.
- When the outcome is unknown, wes does not repeat the command. A command that
  may already have changed a remote system must not run twice without a
  decision. Check the target, then use `:refresh` if repeating is safe.
- For an SSH failure, the result keeps the first 4 KiB of the SSH client's
  error output as `/ssh/stderr: SSH_CLIENT_DIAGNOSTIC: …`. It helps to find the
  cause, such as a missing host key, but wes does not conclude from it that the
  command did not run: a remote command can print the same text and exit with
  the same status.
- Stop the `orders-api` container with `docker compose -f
  09-environments-and-targets/lab/compose.yaml stop orders-api`
  to see `ENV038`, and start it again with `start orders-api`.

## Watch out

### Plans belong to the session

A plan can be applied only by the client that created it, in the same session.
On the command line, each invocation is a new session: `:env apply $proposed`
in a later invocation answers `ENV001: No live environment plan with this name
belongs to this client. Plan again after load.` Use `--env-file` instead (see
[Run the programs](#run-the-programs)).

### Reopening closes environment execution

When a data home is opened again, commands through environments do not run
until execution is explicitly reopened; this prevents a workspace from
contacting systems just because it was opened. On the command line, a second
invocation on the same data home answers `ENV020: Environment execution is
closed after reopening; explicitly select it again or use --env NAME
--env-revision REVISION --activate-env.` until `--activate-env` is added.
Other reasons have their own `ENV020` message, for example `Environment is
disabled for this live session; explicitly enable or select it again.` after
`:env disable`.

### Managing environments

| Command | Effect |
| --- | --- |
| `:env disable "lab"` | block new commands through the environment for this live session only; running work is not cancelled, and a new session can use it again |
| `:env enable "lab"` | allow them again |
| `:env retire "lab"` | prevent new selection and imports; existing results can still be refreshed |
| `:env rename "lab" to:"name"` | rename while keeping identity and bindings |
| `:env delete "lab"` | delete a retired environment that nothing references |
| `:env export file:"path"` | write the environment lock (definitions without secret values) to a file |

`rename` and other edits change the environment in the data home, so it no
longer matches the package file. Planning the file again then answers `ENV010:
workspace edits diverged from this package`; plan with `reconcile:file` to
replace the edits with the file explicitly.

`:env export` answers `Exported captured environment lock; no result values,
credential material or grants included. Local paths and target metadata are
included; review them before sharing.` The lock records the resolved absolute
paths, such as the key file path of this checkout, so it describes this machine;
the package file with its relative paths is the portable form.

### Secrets do not belong in the package

The package holds paths and addresses, never passwords or tokens. The SSH key
stays in its file. [Credentials and authentication](../13-credentials/README.md)
covers credential references.

## Run the programs

Start the lab first (see [The lab](#the-lab)). `session.wes` contains the client
commands of steps 3–7, separated by `// ---`; enter them in order.

On the command line, `--env-file` applies the package and `--env` selects the
environment for one invocation:

```sh
$WES --home /tmp/wes-tutorial-09 \
  --env-file 09-environments-and-targets/lab/environments.yaml \
  --env lab --command 'edge run cmd:"hostname"'
```

Add `--activate-env` when the data home has been opened before.

An applied environment can also be selected without the package, by its
revision; `:list environments` and `:inspect env:"lab"` show it:

```sh
$WES --home /tmp/wes-tutorial-09 --env lab \
  --env-revision sha256:b5927d… --activate-env --command 'edge run cmd:"hostname"'
```

`--env-file` always applies the package before the command. To see what a
changed package would do without applying it, use `:env plan file:"…"`.

`check.py` starts the lab if it is not running, verifies every output and
failure of this chapter on the command line (including a stopped container, an
unknown host key, the `ENV020` activation rule and the `ENV001` plan rule), and
stops the lab again if it started it. Without Docker it prints `SKIP`:

```sh
python3 09-environments-and-targets/check.py
```

If Docker uses a different local Unix socket, set `WES_DOCKER_SOCKET` to its
absolute path before running the check. The check copies the lab package into
its temporary home and substitutes this path; the committed lab file is unchanged.

Remove the lab when it is no longer needed:

```sh
sh 09-environments-and-targets/lab/teardown.sh
```

## Summary

| Concept | Syntax |
| --- | --- |
| Target kinds | `kind: local`, `kind: docker`, `kind: ssh` |
| Import | `name: {source: {kind: builtin, name: sh}, bind: {target: t}}` |
| Plan a package | `:env plan file:"environments.yaml" > proposed` |
| Apply, select | `:env apply $proposed`, `:env use "lab"`, `:env clear` |
| List | `:list environments`, `:list providers` |
| Run on a target | `app run cmd:"..."`, `edge run cmd:"..." timeout:PT1S` |
| Command line | `--env-file FILE --env NAME [--activate-env]`, `--env NAME --env-revision REVISION` |

## Exercises

1. Add an import `logs` bound to `orders_api` that could read the deployment
   log, and write the command that prints its last line.
2. Which target runs `edge run cmd:"cat /srv/orders-api/VERSION"`, and what
   happens?
3. A command over SSH failed with `ENV036` after its timeout. Why does wes not
   run it again automatically?

<details>
<summary>Answers</summary>

1. Add to `imports`:

   ```yaml
   logs:
     source: {kind: builtin, name: sh}
     bind: {target: orders_api, timeout_ms: 10000}
   ```

   Then `logs run cmd:"tail -n 1 deploy.log"` prints
   `2026-09-30T10:01:30Z deploy 2.4.1 finished`.
2. The SSH target `edge-host`. The file exists only in the `orders-api`
   container, so the result is `ok` with exit code `1` and a stderr message.
3. The outcome is unknown: the remote command may have run. Repeating it could
   apply an effect twice, so wes leaves the decision to the user.

`exercises.yaml` and `exercises.wes` contain these answers; `check.py` verifies
them.

</details>

## Next

Continue with [Chapter 12, *API contracts*](../12-api-contracts/README.md).
The chapters on shell commands and HTTP requests are planned.
