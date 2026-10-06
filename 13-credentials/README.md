# 13. Credentials and authentication

This chapter covers calling an API operation that requires credentials: how a
contract declares authentication, how an environment chooses a method and names
the credentials it needs, and how the values are supplied and authorized at run
time without ever being written into a command, a file or the workspace.

The example calls `listRefunds` of the `orders-api` service from chapter 12. It
accepts either a bearer token or a user name and password.

## Prerequisites

- Chapters [9](../09-environments-and-targets/README.md) (environments) and
  [12](../12-api-contracts/README.md) (API contracts). The draft
  `12-api-contracts/orders.json` from step 1 of chapter 12 must
  exist, and the service of chapter 12 must be running.
- A local build of wes; see [Run the programs](#run-the-programs).

## Four separate things

| Part | Where it lives | Example |
| --- | --- | --- |
| **Requirement**: which methods an operation accepts | the contract (draft) | `listRefunds`: a bearer token `opsToken`, or a user name and password `opsBasic` |
| **Choice and binding**: which method this environment uses, and which named slot fills it | the environment package | `auth: {listRefunds: [opsToken]}`, `opsToken: {secret: token}` |
| **Value**: the token itself | supplied at run time, kept in memory | `tutorial-ops-token` |
| **Access**: permission for a provider to use the values now | granted at run time, for 5 minutes | `orders` may use them until 14:05 |

None of them implies the next one. A contract that requires a token does not
provide one; a supplied token is not used until access is granted; and access
ends after five minutes or when the session ends.

The synthetic service accepts the public tutorial token `tutorial-ops-token`, or
the user `ops` with the password `tutorial-pass`. They are not secrets; never
use a real credential with the tutorial service.

## Part 1: Contract and environment

### Step 1: The requirement in the contract

The OpenAPI document of chapter 12 declares two security schemes and lists both
for `listRefunds`:

```yaml
paths:
  /refunds:
    get:
      operationId: listRefunds
      security:
        - opsToken: []
        - opsBasic: []
components:
  securitySchemes:
    opsToken: {type: http, scheme: bearer}
    opsBasic: {type: http, scheme: basic}
```

`:describe` turned this into two options in the draft:

```json
"authOptions": [
  {"schemes": ["opsToken"], "auth": [{"header": "Authorization", "scheme": "Bearer", "secret": "opsToken"}]},
  {"schemes": ["opsBasic"], "auth": [{"userSecret": "opsBasic.username", "secret": "opsBasic.password"}]}
]
```

Each option names the **credential slots** it needs: `opsToken`, or
`opsBasic.username` and `opsBasic.password`. `:info orders` lists the options
and reports `selection-required` until an environment chooses one.

### Step 2: The environment

`environments.yaml` imports the draft of chapter 12 twice, once for each method:

```yaml
environments:
  ops:
    secretSlots:
      token: {required: true}
    secretRefs:
      token: tutorial/orders/ops-token
    imports:
      orders:
        source: {kind: spec, file: ../12-api-contracts/orders.json}
        bind:
          target: local
          endpoint: http://127.0.0.1:8770
          auth: {listRefunds: [opsToken]}
          credentials:
            opsToken: {secret: token}
  ops-basic:
    secretSlots:
      user: {required: true}
      password: {required: true}
    secretRefs:
      user: tutorial/orders/ops-user
      password: tutorial/orders/ops-password
    imports:
      orders:
        source: {kind: spec, file: ../12-api-contracts/orders.json}
        bind:
          target: local
          endpoint: http://127.0.0.1:8770
          auth: {listRefunds: [opsBasic]}
          credentials:
            opsBasic.username: {secret: user}
            opsBasic.password: {secret: password}
```

| Field | Meaning |
| --- | --- |
| `secretSlots` | the secrets this environment needs, by local name |
| `secretRefs` | the reference under which each secret is supplied, such as `tutorial/orders/ops-token` |
| `bind.auth` | the chosen method for each operation that offers several |
| `bind.credentials` | which secret fills each credential slot of the contract |

The package contains names only. Plan, apply and select it:

```text
:env plan file:"13-credentials/environments.yaml" > proposed
:env apply $proposed
:env use "ops"
```

The plan shows the references, never values:
`orders: origin=ops target=local endpoint=http://127.0.0.1:8770 private=false credential-refs={"opsToken": "tutorial/orders/ops-token"}`.

## Part 2: Supply and grant in the client

The animation shows steps 3 and 4.

![WesDesk calling orders listRefunds without credentials and failing with
HTTP002, opening /env where the ops environment reports 0/1 credentials
missing, opening the orders provider with its three steps Method, Credentials
and Access, typing the token into a masked field, supplying it for this session,
allowing access for 5 minutes, and calling listRefunds again with status 200
and a refund of 7500 cents](13a-supply-and-grant.gif)

### Step 3: A call without credentials

```text
orders listRefunds limit:5 > refunds
```

```text
✗ $refunds   failed · HTTP002
             credential access has not been granted for provider 'orders'; grant
             provider access in /env or use --grant-provider orders in the CLI
             (supply credential values separately)
```

Nothing is sent to the service. When access was granted but a value is
missing, the message names the slot instead: `HTTP002: HTTP requires the
missing credential 'opsToken'`.

### Step 4: Supply the token and grant access

`/env` lists the environments. The card of `ops` reports `credentials 0/1`, and
its providers table shows `orders · ● 0/1 missing · opsToken · not granted`.
Open the `orders` row; its setup has three steps:

| Step | Content |
| --- | --- |
| 1 Method | the method of each operation: `listRefunds` offers `opsToken` (header) and `opsBasic` (basic); `opsToken` is selected, as `bind.auth` chose |
| 2 Credentials | one masked field per slot: paste the value, then `supply` |
| 3 Access | `allow for 5 minutes` lets `orders` use the values; `revoke access` ends it |

Choosing another method and `save authentication` changes the environment in the
data home, like `rename` in chapter 9; results that already exist keep the
environment they were made with.

After `supply`, the slot shows `session only`; after `allow for 5 minutes`,
the access column counts down: `granted · 298s remaining`. Press
<kbd>Esc</kbd> to return to the session and call again:

```text
orders listRefunds limit:5 > refunds
:calc {
  return $refunds.body.map(refund => refund.amountCents).reduce((sum, cents) => sum + cents, 0);
} > refundedCents
```

The response has status `200` and one refund of `7500` cents; `$refundedCents`
is `7500`.

- A supplied value stays in the memory of the running wes for the session. It
  is not written to the data home, and it is gone when wes stops.
- `Remember on this device` stores the value so that it survives a restart:
  on macOS in the Keychain; on other platforms in an encrypted vault in the
  data home, protected by a vault password that wes asks for and never stores,
  so the vault is locked after every start. Access is never restored: after a
  restart, allow access again.
- `forget` removes the value from the session and from the device. The binding
  in the environment stays.
- The form never calls the API. The setup only changes what the next call may
  use.

## Part 3: The command line

### Step 5: Supply credentials on standard input

On the command line, `--credentials-stdin` reads a JSON map from standard input:
each key is a reference from `secretRefs`, each value is the secret.
`--grant-provider` grants access for the invocation. `supply-token.py` asks for
the token without showing it and runs `refunds.wes`:

```sh
python3 13-credentials/supply-token.py --home /tmp/wes-tutorial-13
```

```text
ops token:
id1000: {"status":200, … "body":[{"orderId":3,"amountCents":7500}], …}
id1001: 7500
```

It runs this command, with the token in the JSON map on standard input:

```sh
$WES --home /tmp/wes-tutorial-13 \
  --env-file 13-credentials/environments.yaml --env ops \
  --credentials-stdin --grant-provider orders \
  --file 13-credentials/refunds.wes
```

- Standard input keeps the value out of the command line, the process list and
  the shell history. In a CI job, pipe it from the secret store of the CI
  system.
- The map may contain several references. For `ops-basic`, supply
  `{"tutorial/orders/ops-user": "…", "tutorial/orders/ops-password": "…"}` and
  select `--env ops-basic`.
- Without `--grant-provider`, the call fails with `credential access has not
  been granted for provider 'orders'`, as in step 3. Without the value, it
  fails with `HTTP requires the missing credential 'opsToken'`.

## Part 4: What the service sees, and what wes keeps

### A wrong value is data

With a wrong token, the request is sent and the service refuses it:
`$refunds.status` is `401` and the body is `{error: "missing or invalid
credentials"}`. As in chapter 12, a status code is data; check it in a
calculation, for example `$refunds.status == 200`.

### Traces hide credentials

`@trace(http)` records the request and the response of a call. The credential
header is hidden:

```text
@trace(http) orders listRefunds limit:5 > traced
:read trace:$traced
```

```text
"headers":[{"name":"authorization","value":"[REDACTED]"}]
```

### The token is stored nowhere

After the calls above, the data home contains no copy of the token: not in the
workspace, not in kept results, not in traces. `check.py` searches every file of
its data homes to verify this.

## Watch out

### Never write a credential into a command

A credential written into a command becomes part of the workspace like any
other text:

```text
:calc { return { Authorization: "Bearer tutorial-ops-token" }; } > authHeaders
http request url:"http://127.0.0.1:8770/refunds?limit=5" headers:$authHeaders > leaked
```

wes recognizes the `Authorization` value and warns before the result:

```text
SEC001: Possible credential literal in command source. Commands, including
rejected commands, are saved in workspace history; ordinary results may also be
retained. This warning does not redact or prevent storage.
  Hint: Use /env to supply named credentials, or --credentials-stdin with
  --grant-provider in the CLI. Do not put credential values in commands.
  Detection is limited to recognizable patterns and is not a secret scan.
```

The warning does not stop the command. The request works, and the token is now
stored in the workspace journal, in the kept value of `$authHeaders`, and in
every saved copy of the workspace (chapter 7). It is shown in the cell and can
be read by anyone who can open the data home. Even a command that fails to
parse is recorded with its text, and warned about. A token in another form,
such as a plain text value without `Bearer`, may not be recognized at all.
Remove such a workspace, and replace the credential at its source.

Use the environment instead: the contract or the binding names the header,
and the value is supplied at run time.

### Choosing a method is required

An operation with several methods cannot be called until the environment
chooses one. `failures/no-method.yaml` imports the draft without `bind.auth`;
calling `listRefunds` fails before sending with `HTTP001: authentication choice
is missing; select the endpoint's schemes in environment bind.auth`. Binding
credentials without a choice is refused while planning, and the message names
the operation: `ENV010: Provider 'orders' on target 'local': Authentication
choice is missing for 'listRefunds'; select its schemes in environment
bind.auth before binding credentials. Inspect the API's authentication options;
supplying credentials does not select a method.`

### Access is short and local

Access lasts five minutes and belongs to the running session. A long job that
calls the API for more than five minutes needs access again; a command-line
invocation grants it for its own run only.

### Failures in this chapter

| Message | Cause | Found |
| --- | --- | --- |
| `HTTP002` credential access has not been granted for provider '…' | access not granted, or expired | before sending |
| `HTTP002` HTTP requires the missing credential '…' | access granted, but a slot has no value | before sending |
| `HTTP001` authentication choice is missing | no `bind.auth` for an operation with several methods | before sending |
| `ENV010` Authentication choice is missing for '…' | `bind.credentials` without `bind.auth` for an operation with several methods | when planning |
| `invalid credential JSON map` | standard input that is not a JSON object of text values | at startup |
| `credential value must not be empty; supply a nonempty value or explicitly forget the credential` | an empty value on standard input | at startup |
| `ENV005` Credential grant target is unavailable in the requested environment revision | `--grant-provider` with a provider the environment does not import | at startup |
| `SEC001` Possible credential literal in command source | a recognizable credential written into a command (warning) | when entered |
| status `401` | a wrong value; the request was sent | in the response |

## Run the programs

Start the service of chapter 12, and describe its contract into
`12-api-contracts/orders.json` (chapter 12, step 1).

- `session.wes` contains the client commands of steps 2–4, separated by
  `// ---`; supply the token in `/env` between the two calls.
- `supply-token.py` runs `refunds.wes` with the token from a prompt (step 5).
- `failures/` contains the package without a method choice and the program that
  writes a token into a command.

`check.py` starts its own service on a free port, describes the contract into a
temporary copy, and verifies both methods, every failure, the `401` response,
the trace redaction, and that no data home contains the token afterwards. The
example in [Never write a credential into a command](#never-write-a-credential-into-a-command)
is verified to store the token, in a separate temporary data home:

```sh
python3 13-credentials/check.py
```

## Summary

| Concept | Syntax |
| --- | --- |
| Requirement | `security` and `securitySchemes` in the OpenAPI document; `authOptions` in the draft |
| Method choice | `bind.auth: {operation: [scheme]}` |
| Secrets of an environment | `secretSlots`, `secretRefs` |
| Binding | `bind.credentials: {slot: {secret: name}}` |
| Supply and grant in the client | `/env` → provider → Credentials → `supply`, Access → `allow for 5 minutes` |
| Supply and grant on the command line | `--credentials-stdin` with `{"reference": "value"}`, `--grant-provider name` |
| Hidden in traces | `authorization: [REDACTED]` |

## Exercises

1. Which command-line options call `listRefunds` with the user name and
   password instead of the token?
2. A teammate puts the token in `environments.yaml` as `secretRefs: {token:
   tutorial-ops-token}`. What does that do, and what should it be?
3. `listRefunds` failed with `HTTP002: credential access has not been granted
   for provider 'orders'` in the
   client, although the token was supplied ten minutes ago. Why?

<details>
<summary>Answers</summary>

1. `--env ops-basic --credentials-stdin --grant-provider orders`, with
   `{"tutorial/orders/ops-user": "ops", "tutorial/orders/ops-password":
   "tutorial-pass"}` on standard input. `check.py` runs exactly this.
2. A reference is a name, not a value: wes then expects a secret supplied under
   the reference `tutorial-ops-token`, and the token string is now written in a
   file that is shared and reviewed. Keep `token: tutorial/orders/ops-token`,
   and supply the value at run time.
3. Access lasts five minutes. The value is still supplied, but access expired;
   allow access again in `/env`.

</details>

## Next

Continue with [Chapter 14, *A Prometheus dashboard*](../14-prom/README.md) to query
metrics and follow live container resources and logs.
