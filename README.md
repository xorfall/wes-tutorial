# wes tutorial

The tutorial teaches the wes language and the WesDesk client step by step. Each
chapter builds on the previous ones, uses examples from backend and operations
work, and runs against synthetic local data only.

Each available chapter contains its text, runnable programs and a `check.py`
that checks the examples and expected failures in temporary data homes.

## Set up

The tutorial is separate from the wes source. Clone both next to each other:

```text
projects/
  wes/            https://github.com/xorfall/wes
  wes-tutorial/   this repository
```

The repositories are [Wes](https://github.com/xorfall/wes) and
[wes-tutorial](https://github.com/xorfall/wes-tutorial). They have independent
Git histories; no submodule setup is needed.

Install the Rust toolchain specified by the Wes checkout, Node.js 22 or newer
with npm, Go 1.26 or newer, and Python 3.11 or newer. The commands below use a
POSIX shell and start from this tutorial repository's root.

Build the CLI, native View validator, client and OpenAPI helper in the Wes
checkout, then return to the tutorial:

```sh
cd ../wes
npm ci
cargo build -p wes -p wes-views --bin wes --bin wes-view-build --locked
npm run build
(cd tools/describe && go build -o wes-extract ./cmd/extract)
cd ../wes-tutorial
```

Set these variables in the shell that runs the tutorial:

```sh
export WES="$PWD/../wes/target/debug/wes"
export WES_SITE="$PWD/../wes/gui/dist"
export WES_VIEW_CONTRACT_TOOL="$PWD/../wes/target/debug/wes-view-build"
```

The chapters write commands as `$WES …`, and start the client with
`$WES --home /tmp/wes-tutorial --serve 8099 --site "$WES_SITE"`. Run every
command from the root of this repository: the programs refer to their files
as `01-first-calculations/main.wes`, `12-api-contracts/orders.json` and so on.

Chapters 9 and 14 also need Docker with Compose and a running local daemon;
chapter 9 needs an OpenSSH client. Their labs use synthetic services. Chapter 14
requires a local Unix Docker socket. Follow each chapter's lab setup before
running its interactive examples.

## Check the chapters

The tutorial targets Wes 0.1.0. The checks have been run on macOS; the tutorial's
scripts and labs have not been verified on Windows or Linux. Run the checks
against the Wes build selected above.

By default, calculations over existing data can update when their inputs
change. Chapter 6 selects `manual` so each refresh can be examined before
dependent calculations run again.

Each `check.py` accepts `--binary` or finds wes through `WES`, then a sibling
checkout (`../wes/target/debug/wes`), then `PATH`. `WES_CHECKOUT` selects another
Wes checkout for the checks and View build tools.

`check_all.py` runs the numbered chapters listed below. It does not run the
separate Custom Views series. Chapters 9 and 14 report `SKIP` when Docker is
unavailable; chapter 14 also skips without a local Unix socket. A skipped lab
has not passed. If the socket differs from `/var/run/docker.sock`, set
`WES_DOCKER_SOCKET` to its absolute path before running the checks:

```sh
python3 check_all.py
```

| Chapter | Topic |
| --- | --- |
| [1. First calculations](01-first-calculations/README.md) | Calculations, names, references, types and failures |
| [2. Values and operators](02-values-and-operators/README.md) | Numbers, text, booleans, records, lists, optional values and JSON |
| [3. Control flow and functions](03-control-flow-and-functions/README.md) | Variables, loops, functions, list operations, sorting, failure outputs and limits |
| [4. Iterators and text](04-iterators-and-text/README.md) | Lines, words, regular expressions and captures, JSON Lines, lazy iteration and typed iterators |
| [5. Time values](05-time-values/README.md) | Instants, durations, intervals, epoch conversions and timelines |
| [6. Nodes and dependencies](06-nodes-and-dependencies/README.md) | Refresh, change, policies, timeouts and removal of results |
| [7. Saving, loading and keeping results](07-saving-and-keeping/README.md) | Workspaces, snapshots, kept results and deletion plans |
| [8. Sandbox](08-sandbox/README.md) | Trying programs in an isolated, memory-only sandbox |
| [9. Environments and targets](09-environments-and-targets/README.md) | Local, Docker and SSH targets in a Docker lab; plans, selection and target failures |
| [12. API contracts](12-api-contracts/README.md) | OpenAPI documents, drafts, imported providers, calls and the API library |
| [13. Credentials and authentication](13-credentials/README.md) | Authentication methods, secret references, supplying values and granting access |
| [14. A Prometheus dashboard](14-prom/README.md) | Typed HTTP results, coordinated timelines, Current/Pin, live container resources and logs |

Chapters 10 (*Shell commands*) and 11 (*HTTP requests*) are planned.

[Custom Views with an agent](custom-views/README.md) is a separate series:
an agent connected to Wes writes React View packages for a synthetic service
monitor, and the reader reviews, installs and displays them.

Run its reference-package checks separately, after the setup above:

```sh
python3 custom-views/01-first-view/check.py
python3 custom-views/02-revise-view/check.py
```

These checks do not call a model or require an AI account. To follow the agent
workflow interactively, use an installed, configured client as described in
[Local tools](custom-views/reference/local-tools.md).

## License

This tutorial is licensed under [MIT](LICENSE).
