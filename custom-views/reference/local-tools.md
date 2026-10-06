# Local tools

The agent reads Wes guidance through MCP. Its ordinary local tools create files
and run the independent compiler. Setup is required once before chapter 1.

## Repository setup

Use Node.js 20 or newer, Python 3.11 or newer and the Rust/platform prerequisites
from the testing guide of the wes repository (`docs/testing.md`). Build in the
wes checkout next to this repository, then export the tools from the root of
this repository:

```sh
(cd ../wes && npm ci &&
  cargo build -p wes -p wes-views --bin wes --bin wes-view-build --locked &&
  npm run build)
export WES_CHECKOUT="$PWD/../wes"
export PATH="$WES_CHECKOUT/node_modules/.bin:$PATH"
export WES_VIEW_CONTRACT_TOOL="$WES_CHECKOUT/target/debug/wes-view-build"
```

The exports make the workspace compiler and native validator available in this
Shell. Repeat them in another Shell, or install both executables on that
Shell's PATH.
The compiler uses the public `@wes/view-sdk` supplied by the npm workspace of the
wes checkout.

For a dedicated tutorial workspace, start Wes from the root of this repository:

```sh
mkdir -p view-work
"$WES_CHECKOUT/target/debug/wes" --home view-work/home --serve 8123 \
  --site "$WES_CHECKOUT/gui/dist"
```

Open `http://127.0.0.1:8123`. This data home is separate from a normal desktop
workspace. Ctrl+C stops the server; its files remain in `view-work/`.

## Connect an installed agent

Open a local Wes Shell with `/rsplitx xterm`. Launch an installed agent with its
plain command name: `claude`, `opencode` or `codex`. Wes supplies the
`wes_workspace` MCP attachment. A separately launched external terminal does
not acquire that attachment automatically.

The chosen client must already be installed and configured. The tutorial checks
use reference files and synthetic agent fixtures, not a model account.

Before the agent compiles, ensure the validator is available in its Shell:

```sh
export WES_VIEW_CONTRACT_TOOL="$WES_CHECKOUT/target/debug/wes-view-build"
export PATH="$WES_CHECKOUT/node_modules/.bin:$PATH"
```

`WES_CHECKOUT` is the absolute path of the wes checkout, as exported above.
Node packages and executables are local prerequisites; reading the MCP
guidance does not install them.

## Build the reference source manually

Copy the first chapter's source without overwriting an existing source folder:

```sh
mkdir -p view-work
test ! -e view-work/service-board &&
  cp -R custom-views/01-first-view/service-board \
    view-work/service-board
```

The copy stops if `view-work/service-board` already exists; choose a new
destination in that case. Build and check the copy from the repository root:

```sh
npx --no-install wes-view-package build \
  view-work/service-board \
  view-work/service-board.wes-view.json
npx --no-install wes-view-package check \
  view-work/service-board.wes-view.json
```

Both compiler commands return JSON. A successful response has `ok: true`.
A failed build has `ok: false` and structured diagnostics with a code, message
and source location when available. A failure retains the previous artifact.

For chapter 2, copy `02-revise-view/service-board-priority` instead and build
`view-work/service-board-priority.wes-view.json` with the same commands.
The compiler generates `contract.ts`; do not maintain it by hand.

Shell paths are resolved by that Shell. `:package load` paths are resolved by
Wes's working directory. Use an absolute artifact path if those differ.
