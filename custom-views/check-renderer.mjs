// Render the actual author component offline; no application internals are used.
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { execFileSync } from "node:child_process";

// The wes checkout provides the View build tools: WES_CHECKOUT, or ../wes next to this repository.
const root = process.env.WES_CHECKOUT ?? fileURLToPath(new URL("../../wes/", import.meta.url));
const require = createRequire(path.join(root, "tools/view-package/package.json"));
const esbuild = require("esbuild");
const [source, casesFile, mode] = process.argv.slice(2);
const entry = path.join(source, "View.tsx");
const output = path.join(path.dirname(source), "renderer-check.cjs");
const sdk = require.resolve("@wes/view-sdk");
const script = String.raw`
  import assert from "node:assert/strict";
  import fs from "node:fs";
  import React from "react";
  import { renderToStaticMarkup } from "react-dom/server";
  import { parseExactJson } from ${JSON.stringify(sdk)};
  import view from ${JSON.stringify(entry)};
  const cases = parseExactJson(fs.readFileSync(process.argv[2], "utf8"));
  const render = input => {
    const before = JSON.stringify(input);
    const markup = renderToStaticMarkup(React.createElement(
      view.Component, {input, state: null, revision: 0, slots: {}}
    ));
    assert.equal(JSON.stringify(input), before, "Rendering mutated input");
    return markup;
  };
  const priority = process.argv[3] === "priority";
  const rowNames = markup => [...markup.matchAll(
    /<th[^>]*scope="row"[^>]*>([^<]+)<\/th>/g
  )].map(match => match[1]);
  const normal = render(cases.normal);
  for (const text of ["Service monitor", "orders-api", "billing-worker",
    "gateway", "degraded", "Requests / s", "p95 / ms", "120", "240"])
    assert.ok(normal.includes(text), text);
  assert.equal((normal.match(/<tr>/g) || []).length, 4);
  assert.deepEqual(rowNames(normal), priority
    ? ["gateway", "billing-worker", "orders-api"]
    : ["orders-api", "billing-worker", "gateway"]);
  assert.equal(normal.indexOf("p95 / ms") < normal.indexOf("Requests / s"),
    priority);
  if (priority) {
    assert.deepEqual(rowNames(render(cases.ties)),
      ["down-a", "down-b", "warn", "ok-a", "ok-b"]);
  }
  assert.ok(!normal.includes("<button"));
  for (const role of ["screen-title", "screen-label", "table-key", "table-value",
    "status-ok", "status-warn"]) assert.ok(normal.includes(role), role);
  assert.ok(!normal.includes('role="alert"'));
  const empty = render(cases.empty);
  assert.ok(empty.includes("No services in this snapshot."));
  assert.ok(!empty.includes("<table"));
  const duplicate = render(cases.duplicate);
  assert.ok(duplicate.includes('role="alert"'));
  assert.ok(duplicate.includes(
    "Service names must be unique. Fix the input snapshot."));
  assert.ok(!duplicate.includes("<table"));
  const exact = render(cases.exact);
  assert.ok(exact.includes(">9007199254740993</td>"));
  assert.ok(!exact.includes("9007199254740992"));
  assert.ok(exact.includes("service-status status-bad"));
  assert.ok(exact.includes(">0</td>"));
  const boundary = render(cases.boundary);
  assert.equal((boundary.match(/<tr>/g) || []).length, 17);
  const escaped = render(cases.escaped);
  assert.ok(escaped.includes("&lt;script&gt;"));
  assert.ok(!escaped.includes("<script>"));
  assert.ok(!escaped.includes("extraFieldMustNotRender"));
  console.log("PASS renderer: rows, empty, duplicates, exact numbers, " +
    "16 rows, escaped text");
`;
await esbuild.build({
  stdin: { contents: script, resolveDir: path.dirname(sdk), loader: "tsx" },
  outfile: output,
  bundle: true,
  platform: "node",
  format: "cjs",
  jsx: "automatic",
  nodePaths: [path.join(root, "tools/view-package/node_modules")],
  alias: {
    "@wes/view-sdk": sdk,
    react: path.dirname(require.resolve("react/package.json")),
    "react-dom": path.dirname(require.resolve("react-dom/package.json")),
  },
  loader: { ".css": "empty" },
  define: { "process.env.NODE_ENV": '"production"' },
  logLevel: "silent",
});
process.stdout.write(execFileSync(process.execPath, [output, casesFile, mode], {
  encoding: "utf8", timeout: 30000,
}));
fs.unlinkSync(output);
