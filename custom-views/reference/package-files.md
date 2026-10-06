# Package files

The main chapters describe the request and verify the visible result. These
files explain the checked reference implementation without adding rules to the
agent's initial request.

| File | Responsibility |
| --- | --- |
| `view.json` | Definition identity, renderer entry, input type and outputs |
| `types.yaml` | Input fields and their validation rules |
| `View.tsx` | React component using the public Wes SDK |
| `view.css` | Package-local layout styles imported by the renderer |
| `contract.ts` | Generated definition and TypeScript types |
| `*.wes-view.json` | Checked artifact containing the compiled renderer and contracts |

Read the original [manifest](../01-first-view/service-board/view.json),
[contracts](../01-first-view/service-board/types.yaml),
[renderer](../01-first-view/service-board/View.tsx) and
[styles](../01-first-view/service-board/view.css).
The revision has its own [manifest](../02-revise-view/service-board-priority/view.json)
and [renderer](../02-revise-view/service-board-priority/View.tsx).

## Input rules

Both packages use the same `ServiceBoardInput` contract. It requires a title and
a list of service records. Each service requires `name`, `status`, `rps` and
`p95Ms`. The title has 1–128 Unicode code points, names have 1–64, and the list
permits 0–16 services. Status is exactly `ok`, `degraded` or `down`. Both numeric
fields are nonnegative `Int`.

Extra record fields are allowed by these contracts and ignored by the renderer.
Length rules do not trim whitespace or normalize names. Name comparisons are
exact and case-sensitive. The component separately checks uniqueness across rows;
the field contracts alone cannot make names unique.

## Rendering rules

`defineView` binds the generated definition to the React component. The packages
declare no output ports or interaction. `numericText` preserves exact numeric
text, including integers beyond JavaScript's safe integer range. React renders
titles and names as text rather than interpreting them as HTML.

The original preserves row order. The revision sorts derived row references by
status, then by original index. Neither renderer mutates the input. Empty input
has an explicit message. Duplicate names display an alert and suppress the table.

The components select Wes role classes by meaning: `screen-title`, `screen-label`,
`table-key`, `table-value`, `status-ok`, `status-warn` and `status-bad`.
Package CSS uses layout variables and imports through `View.tsx`.
Theme values come from Wes; neither package contains fixed font names or colors.

## MCP discovery

The agent starts with `workspace_context`, reads `serviceData` through
`value_read` with `typed: true`, then reads `view_authoring` topics `overview`,
`sdk`, `theme` and `examples`. These are agent tool calls, not Wes prompt text.
The example topic supplies a starter; the agent still chooses domain-specific
input and behavior for ServiceBoard.

Compilation does not evaluate the renderer source. Installation validates and
registers the artifact. The component renders when a client displays its instance.

## Host sizing

`view.json` may include a `layout` object for the three data tiers: `preview`,
`expanded` and `window` (the inspector). Every tier supplies `min`, `preferred`
and `max`, in integer monospace `columns` and text `rows`. For example:

```json
{
  "preview": {"min":{"columns":24,"rows":4},"preferred":{"columns":80,"rows":6},"max":{"columns":160,"rows":8}},
  "expanded": {"min":{"columns":32,"rows":6},"preferred":{"columns":80,"rows":14},"max":{"columns":160,"rows":40}},
  "window": {"min":{"columns":32,"rows":6},"preferred":{"columns":100,"rows":24},"max":{"columns":320,"rows":80}}
}
```

Each axis must satisfy 1 ≤ min ≤ preferred ≤ max, with limits of 512 columns
and 200 rows. Invalid dimensions fail compilation. The host uses a bounded
viewport, supplies the minimum canvas when space is tight, and contains scroll
inside the view. Preview has a height budget and no resize grip; expanded can
be resized. Composed members use natural height inside the root viewport.
Packages without a layout receive safe defaults; the scaffold declares sizes.
The host does not promise that arbitrary data fits at the minimum size.
Without a layout, preview uses 24×4 / 80×6 / 320×8 columns×rows for
minimum / preferred / maximum. Expanded uses 32×6 / 80×14 / 320×40;
window uses 32×6 / 80×24 / 320×80.
