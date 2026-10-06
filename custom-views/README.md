# Custom Views with an agent

This series covers building custom Views for Wes with an agent. A **View**
draws a workspace value in its own way, for example a service table with
status colors. The agent writes the React source, builds and checks a package,
and returns it; the reader reviews the package, installs it and displays
results with it.

The agent connects to Wes through MCP (Model Context Protocol) and reads the
current SDK, build and theme guidance from there. Each chapter adds one
capability to the same example: a monitor for the synthetic services
`orders-api`, `billing-worker` and `gateway`.

| Chapter | Topics | Status |
| --- | --- | --- |
| [1. A first View](01-first-view/README.md) | Request, review, install and display ServiceBoard; input rules and failures | Available |
| [2. Revise a View](02-revise-view/README.md) | A second identity, two instances on one input, identity collisions | Available |
| 3. The Wes theme | Palette, density and font changes | Planned |
| 4. Input rules | Missing, invalid and boundary values | Planned |
| 5. Selection and outputs | A typed service selection | Planned |
| 6. A Dashboard | Connected list and detail instances | Planned |
| 7. Live data | Starting, updating and stopping a synthetic service query | Planned |
| 8. Save, reopen and diagnose | Reusing a workspace and investigating failures | Planned |

## Chapter structure

Each chapter contains:

- `README.md`, with the request to the agent, the steps and their results;
- `assistant-task.txt`, the request exactly as the chapter quotes it;
- a checked reference source and its programs (`.wes` files);
- `check.py`, which builds the reference package and verifies every documented
  result offline, and `check.py --preview`, which starts Wes with the package
  ready for the programs;
- an animation of the steps in the Wes client, recorded with the reference
  package.

The checks use temporary data homes. They call no model and no live service,
and need no account. The animations show the reference implementation; they do
not show or simulate an agent's response.

## Reference

- [Local tools](reference/local-tools.md): the wes checkout, the View build
  tools and starting an agent inside a Wes Shell.
- [Package files](reference/package-files.md): the files of a View package and
  the input rules of the reference.
