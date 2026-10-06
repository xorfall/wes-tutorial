# 12. API contracts

This chapter covers turning an HTTP API description into a provider: reading an
OpenAPI document into a draft, importing the draft, and calling its operations
from commands and calculations. An imported provider knows the operations, their
arguments and their response types, so wes can check a call before it sends it
and check a response when it arrives.

The example uses `orders-api`, a small synthetic service that runs on the local
machine. Its contract lists four operations: a health check, a list of orders,
one order by identifier, and a list of refunds that requires credentials
(chapter 13).

## Prerequisites

- Chapters [1](../01-first-calculations/README.md) to
  [9](../09-environments-and-targets/README.md), in particular records and lists
  (chapter 2), loops (chapter 3) and environments (chapter 9).
- Python 3 for the synthetic service, and a local build of wes; see
  [Run the programs](#run-the-programs).

## The service

`service/orders_api.py` serves the API on `127.0.0.1:8770`, on the local machine
only. Start it in a separate terminal from the repository root and leave it
running:

```sh
python3 12-api-contracts/service/orders_api.py
```

`orders-api.openapi.yaml` is its contract, in OpenAPI 3.1:

| Operation | Request | Response |
| --- | --- | --- |
| `health` | `GET /health` | `{status, version}` |
| `listOrders` | `GET /orders?limit=…&status=…` | a list of orders; `limit` is required, 1 to 50; `status` is optional: `open`, `shipped` or `failed` |
| `getOrder` | `GET /orders/{id}` | one order, or `404` with `{error}` |
| `listRefunds` | `GET /refunds?limit=…` | a list of refunds; requires a bearer token or a user name and password |

An order is `{id, status, totalCents}`.

## Contract, draft and provider

Three files and objects take part, and each step is explicit:

```text
orders-api.openapi.yaml ──:describe──> orders.json ──:import spec──> provider orders ──> calls
   (OpenAPI document)                  (draft, editable)              (in the workspace)
```

- `:describe` reads the OpenAPI document and writes a **draft**: the operations,
  types and authentication requirements in wes's own format. It never calls the
  API.
- `:import spec` turns a draft into a **provider** with an endpoint. It never
  calls the API either.
- Only a call, such as `orders health`, sends a request.

## Part 1: Describe and import

The first animation shows steps 1 and 2.

![WesDesk describing orders-api.openapi.yaml into a valid draft with four
operations, importing it as the provider orders with a note that listRefunds
needs an authentication choice, and showing the help of orders and of orders
listOrders](12a-describe-and-import.gif)

### Step 1: Describe the contract

```text
:describe file:"12-api-contracts/orders-api.openapi.yaml" provider:orders out:"12-api-contracts/orders.json" > draft
```

```text
✓ $draft   ok · not kept
           status valid   operationCount 4   next Open /spec to review or complete this draft.
           exportedPath …/12-api-contracts/orders.json
```

- `file:` or `url:` names the OpenAPI document, in JSON or YAML, version 3.0 or
  3.1. A relative `file:` is resolved from the directory where wes was started.
- `provider:` is the name of the provider that the draft describes.
- `out:` writes the draft to a file. Without `out:`, the draft is kept only in
  the API library of the data home (part 3).
- The result is private: the command line answers `Private value withheld from
  stdout/export; inspect in the memory-only browser data plane.` The client
  shows it.

The draft is a JSON file. Each operation lists its route, its parameters and
its responses, with types derived from the schemas of the document:

```json
{
  "path": ["listOrders"],
  "method": "GET",
  "route": "/orders",
  "parameters": [
    {"name": "limit", "location": "query", "required": true, "type": "ApiType3"},
    {"name": "status", "location": "query", "required": false, "type": "ApiType4"}
  ],
  "responses": {"200": "List<Api_Order_ff02bd46>"}
}
```

`ApiType3` is `{"base": "Int", "min": 1, "max": 50}`, and `ApiType4` is a `Text`
with the three allowed values. The draft also records where each fact came from
(`provenance`) and a SHA-256 fingerprint of the document (`source.sha256`).

### Step 2: Import the provider

```text
:import spec file:"12-api-contracts/orders.json" endpoint:"http://127.0.0.1:8770" as:orders
```

The import reports one warning:

```text
IMP007: Authentication choice required for listRefunds; select its schemes in environment bind.auth
```

The provider is imported; only `listRefunds` cannot be called yet, because its
contract offers two ways to authenticate. Chapter 13 makes that choice.

- `endpoint:` is the base address of the API. It is required: the `servers` list
  of the document is not used. A missing endpoint is rejected before the
  contract file is read:

  ```text
  IMP001: Required import argument 'endpoint:' is missing. Read this importer's help.
  ```

- `as:` is the provider name in commands.
- The provider belongs to the current environment of the session (chapter 9).

Explore the provider:

```text
:help orders
:help orders listOrders
:info orders > ordersInfo
```

The help of `listOrders`, as the command line prints it; the client shows the
same facts in the result:

```text
:help orders listOrders
List orders, newest first
Usage  orders listOrders
  limit:  Int (required)
    Constraints  number: 1..50 (inclusive)
  status:  Text (optional)
    Constraints  allowed values: "open", "shipped", "failed"
Safety  SAFE
Result  HttpResponse
```

- The summary comes from the `summary` of the operation in the document, and
  the constraints from its schemas.
- `Safety SAFE` marks an operation that only reads: `GET` is safe. Operations
  that change data are `UNSAFE`.
- `:info orders` reports, for each operation, whether it needs credentials and
  which methods it accepts: `health`, `listOrders` and `getOrder` are
  `selected`, with the one option the document declares, no credentials
  (`security: []`); `listRefunds` is `selection-required`, with the options
  `opsToken` (a header) and `opsBasic` (a user name and password).

## Part 2: Calls and responses

The second animation shows steps 3 to 5.

![WesDesk importing the provider, calling orders health, listing three recent
orders as a table, reading the unknown order 99 with status 404, combining the
responses in a calculation, and a calculation that calls the API in a loop and
finds 7500 cents in failed orders, followed by a call with limit 51 that is
refused before it is sent](12b-calls-and-data.gif)

### Step 3: Call operations

An operation is called like any provider command, with named arguments:

```text
orders health > health
orders listOrders limit:3 > recent
orders listOrders limit:10 status:"open" > openOrders
orders getOrder id:3 > failedOrder
orders getOrder id:99 > unknownOrder
```

Each result is an `HttpResponse`:

| Field | Content |
| --- | --- |
| `status` | the HTTP status code, such as `200` or `404` |
| `version` | the HTTP version |
| `headers` | a list of `{name, value}` records |
| `body` | the parsed body: here a record or a list, with the type from the contract |
| `bodyKind` | how the body was read, such as `json` |
| `originalBody` | the body as received, as `Bytes` |
| `validation` | whether the response matched the contract: `{state, issues}` |

- `$recent.body` is a `List` of orders, shown as a table: orders 4, 3 and 2.
- `$unknownOrder` is `ok` with status `404` and the body
  `{error: "unknown order"}`. **A status code is data**, like the exit code of
  a command in chapter 9: the request worked, and the service answered that the
  order does not exist. Only a failure to send the request or to receive an
  answer fails the result.
- `validation.state` is `validated` when the status and the body match the
  contract. A response that does not match is still returned, with
  `mismatch` and a list of `issues`, for example `HTTP_BODY_UNEXPECTED: The
  documented response has no body, but a body was received`.

### Arguments are checked before the request

wes checks the arguments against the contract and sends nothing when they do
not match:

| Call | Message |
| --- | --- |
| `orders listOrders limit:51` | `HTTP001: /arguments/limit: query parameter "limit": number is outside the permitted bounds; number: 1..50 (inclusive)` |
| `orders listOrders limit:5 status:"lost"` | `HTTP001: /arguments/status: query parameter "status": value is not allowed; allowed values: "open", "shipped", "failed"` |
| `orders listOrders` | `CHK002: 'listOrders' needs 'limit:'` |
| `orders deleteOrder id:3` | `RES005: 'orders' offers nothing called 'deleteOrder'` |

The message names the argument and the rule it breaks, never the rejected
value itself.

### Step 4: Responses are data

Fields of a response are read like the fields of any record:

```text
:calc {
  return {
    status:   $health.status,
    healthy:  $health.body.status == "ok",
    version:  $health.body.version,
    found:    $unknownOrder.status != 404,
    problem:  $unknownOrder.body.error,
  };
} > checks
:calc {
  return $openOrders.body.map(order => order.totalCents);
} > openTotals
```

The results are
`{ status: 200, healthy: true, version: "1.4.0", found: false, problem: "unknown order" }`
and `[1250, 4200]`.

### Step 5: Calls inside a calculation

`call(provider, operation, arguments)` calls an operation from inside a
calculation. Find the failed orders among the recent ones, and read each of
them:

```text
:calc {
  const recent = call("orders", ["listOrders"], { limit: 10 });
  let failedCents = 0;
  for (const order of recent.body) {
    if (order.status == "failed") {
      const detail = call("orders", ["getOrder"], { id: order.id });
      failedCents = failedCents + detail.body.totalCents;
    }
  }
  return { orders: length(recent.body), failedCents: failedCents };
} > failedValue
```

The result is `{ orders: 4, failedCents: 7500 }`.

- The operation is a list of names: `["getOrder"]`. The arguments are a record.
- Calls run one after another, in the order the calculation reaches them. A
  calculation may make at most 1,000 calls.
- A calculation that calls a provider is not pure: `:inspect $failedValue`
  shows `purity effectful`. `:calc pure { … }` with a call fails before running
  with `CAL009: pure calculation contains a possible external provider call`.
- The arguments are checked as in step 3. A call that is refused fails the
  calculation with `CAL008`, followed by the reason: `CAL008: calculation
  provider call failed: HTTP001: /arguments/limit: query parameter "limit":
  number is outside the permitted bounds; number: 1..50 (inclusive)`.
- Use a command (step 3) when one call is enough: it has its own cell, its
  own result and its own run. Use `call` when the calls depend on data, as in
  this loop.

## Part 3: The API library and environments

The third animation shows step 6.

![WesDesk opening the /spec screen with the imported orders contract under
Workspace APIs and the orders draft in the Library, opening the draft with four
operations ready to import, and its import dialog with environment, alias and
endpoint](12c-api-library.gif)

### Step 6: The API library

`/spec` opens the API library of the data home:

| Section | Content |
| --- | --- |
| Workspace APIs | the contracts imported into this workspace, per environment; read-only |
| Library | drafts and saved APIs, shared by every workspace of the data home |
| Import OpenAPI | the same as `:describe`, as a form |

`open draft` shows the operations of a draft, its schema, its source and its
problems. Drafts can be edited there; each edit creates a new revision.

- `Ready to import` means that nothing blocks the import. Advisories are notes;
  this draft has one, `Authentication choice required for listRefunds; select
  its schemes in environment bind.auth` (chapter 13).
- `import…` imports the draft into an environment with an alias and an endpoint,
  like `:import spec`.

### Importing through an environment

`:import spec` imports into the running session. An environment package
(chapter 9) can import the same draft, so that the provider and its endpoint
are part of a reviewed definition. `environments.yaml` in this folder:

```yaml
version: 1
package: orders-tutorial
targets:
  local: {kind: local}
environments:
  shop:
    imports:
      orders:
        source: {kind: spec, file: orders.json}
        bind:
          target: local
          endpoint: http://127.0.0.1:8770
```

- `source: {kind: spec, file: orders.json}` names the draft, relative to the
  package file.
- `bind.endpoint` is the base address; another environment, such as a staging
  environment, can bind the same draft to another address.
- Plan, apply and select it as in chapter 9; `orders health` then runs through
  the environment `shop`.

Chapter 13 adds credentials to this package.

## Watch out

### Describing and importing never call the API

`:describe` reads a document, and `:import spec` records a draft and an
endpoint. Neither sends a request. The service does not even need to run until
the first call.

### Only OpenAPI documents

`:describe` reads OpenAPI 3.0 and 3.1 in JSON or YAML. Other text fails, for
example this README: `DSC002: API source contains unsupported or invalid
declarations; inspect import details. Open failure details for the specific
reasons; no spec was saved.` The client lists the reasons under
`Failure details`.

### An existing draft file is never overwritten

`:describe … out:"orders.json"` when `orders.json` exists fails with `DSC006:
Draft saved; export failed because the output already exists. Choose a new
filename; the existing file was not changed.` The draft itself is saved in the
API library (part 3); only the file is not written. Choose a new file name, or
delete the old draft file first.

### A changed document needs a new draft

The draft records the fingerprint of the document it came from. When the OpenAPI
document changes, describe it again into a new draft, and import that draft
with the same alias and `replace:true`:

```text
:import spec file:"12-api-contracts/orders-v2.json" endpoint:"http://127.0.0.1:8770" as:orders replace:true
```

The answer is the warning `IMP006: provider 'orders' was replaced; existing
nodes retain their captured invocation handles`. Without `replace:true`, the
import is refused and the existing provider stays: `IMP004: Provider already
exists; choose another alias or explicitly use replace:true.`

### Results keep the connection they were made with

A result belongs to the provider, endpoint and contract it was made with. After
the provider is replaced, for example with a new endpoint, new commands use the
new connection, and an older result cannot run again. Here the endpoint is
written as `localhost` instead of `127.0.0.1`: the same service, but a
different endpoint:

```text
orders health > before
:import spec file:"12-api-contracts/orders.json" endpoint:"http://localhost:8770" as:orders replace:true
orders health > after
:refresh $before
```

```text
ENV039: Captured binding for provider 'orders' in environment 'default' changed
or was removed (captured destination: http://127.0.0.1:8770 · target local, rev
e429745b). No provider was called. Existing cells keep their original
destination. Submit a new command or use New branch to resolve the current
binding; inspect the original result to review its captured binding.
```

- wes never sends an older result to a new endpoint, and never sends it to the
  old one without saying so: `:refresh`, reactive recalculation and calls
  inside calculations are all refused before anything is sent.
- The message names the destination the result was made with,
  `http://127.0.0.1:8770`. `:inspect $before` lists the same connection under
  `capturedBindings`, with the full revision, ending with `binding changed or
  removed; new command required`.
- Enter the command again to get a result from the new endpoint. The same rule
  applies when an environment revision changes `bind.endpoint` (chapter 9).
- A change that does not concern the provider, such as another import in the
  same environment, does not block it.

### Correcting the safety of an operation

wes classifies an operation by its HTTP method: `GET`, `HEAD` and `OPTIONS` are
`SAFE`, every other method is `UNSAFE`. The reactive policy (chapter 6) repeats
only `SAFE` operations automatically. Some APIs read with `POST`, such as a
search endpoint; others change data with `GET`. When the method does not match
the behaviour, set `safety` on the operation in the draft:

```json
{
  "path": ["searchOrders"],
  "method": "POST",
  "safety": "safe",
  "route": "/orders/search"
}
```

- The value is `"safe"` or `"unsafe"`. `SAFE` means that the operation may be
  repeated automatically, not merely that it is idempotent: a `PUT` or a
  `DELETE` stays `UNSAFE`.
- The HTTP method that is sent does not change.
- `:help` shows the classification, and `:info` shows where it comes from:
  `"basis": "explicit local contract"` for a value in the draft, the method
  otherwise.
- Only the local draft decides. An OpenAPI document cannot mark an operation
  as safe; review the draft before setting it.
- Any other value fails the import with `IMP001: operation safety must be safe
  or unsafe; SAFE permits automatic repetition, not merely idempotent
  requests`, and an unknown field with `IMP001: unknown operation field;
  allowed fields: …`.

### Drafts can be shared

`source.location` in the draft is the file name of the OpenAPI document, such as
`orders-api.openapi.yaml`, together with its fingerprint. The absolute path on
this machine stays in the local API library and is not written into the draft.

### Failures in this chapter

| Message | Cause | Found |
| --- | --- | --- |
| `DSC002` API source contains unsupported or invalid declarations | a document that is not OpenAPI 3.0 or 3.1 | when describing |
| `DSC003` No such file or directory | a missing document | when describing |
| `DSC006` Draft saved; export failed because the output already exists | `out:` names an existing file | when describing |
| `IMP001` Required import argument 'endpoint:' is missing | `:import spec` without `endpoint:` | before reading the contract |
| `IMP007` Authentication choice required for … | an operation with several authentication methods (warning) | when importing |
| `HTTP001` … outside the permitted bounds / value is not allowed | an argument outside the contract | before sending |
| `IMP004` Provider already exists | importing an existing alias without `replace:true` | when importing |
| `IMP006` provider … was replaced | importing with `replace:true` (warning) | when importing |
| `ENV039` Captured binding … changed or was removed | refreshing a result whose provider was replaced or changed | before sending |
| `HTTP001` authentication choice is missing | calling `listRefunds` before choosing a method (chapter 13) | before sending |
| `CHK002` … needs … | a missing required argument | before sending |
| `RES005` … offers nothing called … | an operation that is not in the contract | before sending |
| `CAL008` calculation provider call failed: … | a refused or failed `call` inside a calculation, with its reason | while running |
| `CAL009` pure calculation contains a possible external provider call | `call` inside `:calc pure` | before running |

## Run the programs

Start the service first (see [The service](#the-service)). `session.wes`
contains steps 1–5. Run it from the repository root, in order and in one
session, with `--sequential`:

```sh
$WES --home /tmp/wes-tutorial-12 --sequential \
  --command "$(cat 12-api-contracts/session.wes)"
```

Delete `12-api-contracts/orders.json` before running it again,
because an existing draft file is never overwritten. The command line prints
each response as JSON, with `originalBody` in base64.

`failures/` contains one program per failure; each imports the provider first.
`check.py` starts its own service on a free port, runs the session, the
environment package and every failure in temporary data homes, and verifies the
results and the requests the service received, including that refused calls
sent nothing:

```sh
python3 12-api-contracts/check.py
```

## Summary

| Command | Effect |
| --- | --- |
| `:describe file:"…" provider:name out:"…" > draft` | read an OpenAPI document into a draft; no API call |
| `:import spec file:"draft.json" endpoint:"…" as:name` | make a provider from a draft; no API call |
| `:help name`, `:help name operation` | operations, arguments, safety and result type |
| `:info name` | authentication requirements and evidence |
| `name operation arg:value > result` | call an operation; the result is an `HttpResponse` |
| `call("name", ["operation"], {…})` | call an operation inside a calculation |
| `/spec` | the API library: imported contracts, drafts, OpenAPI import form |
| `source: {kind: spec, file: …}` | import a draft through an environment package |

## Exercises

1. What is the total value, in cents, of the shipped orders among the ten most
   recent ones? Use a command and a calculation.
2. `orders getOrder id:0` — is it sent? Why?
3. A colleague changed the contract and added an operation `cancelOrder`. Which
   steps make it available, and what happens to `$recent`?

<details>
<summary>Answers</summary>

1. ```text
   orders listOrders limit:10 status:"shipped" > shipped
   :calc {
     return $shipped.body.map(order => order.totalCents).reduce((sum, cents) => sum + cents, 0);
   } > shippedCents
   ```

   The result is `1999`.
2. No. The contract declares `id` with `minimum: 1`, so the call fails with
   `HTTP001: /arguments/id: path parameter "id": number is outside the permitted
   bounds; number: at least 1 (inclusive)` before anything is sent.
3. Describe the new document into a new draft file and import it with
   `as:orders replace:true`. New commands can use `cancelOrder`. `$recent` keeps
   its original contract and connection; refreshing it is refused with `ENV039`
   before any request is sent. Submit a new command to use the new provider.

`exercises.wes` contains the answers to 1 and 2; `check.py` verifies them.

</details>

## Next

[Chapter 13, *Credentials and authentication*](../13-credentials/README.md),
calls `listRefunds`: choosing an authentication method, supplying a token
without writing it into a command, and granting access.
