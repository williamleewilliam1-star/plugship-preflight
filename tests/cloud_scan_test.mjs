import assert from "node:assert/strict";
import { parseRepo, scanSnapshot, reportMarkdown } from "../docs/cloud/scanner.mjs";

assert.deepEqual(parseRepo("https://github.com/example/demo"), { owner: "example", repo: "demo" });
assert.deepEqual(parseRepo("example/demo"), { owner: "example", repo: "demo" });

const good = scanSnapshot({
  repository: "example/good",
  branch: "main",
  files: [
    { path: ".claude-plugin/plugin.json", type: "blob", mode: "100644", size: 180 },
    { path: "README.md", type: "blob", mode: "100644", size: 500 },
    { path: "LICENSE", type: "blob", mode: "100644", size: 1000 },
    { path: "skills/check/SKILL.md", type: "blob", mode: "100644", size: 200 }
  ],
  texts: {
    ".claude-plugin/plugin.json": JSON.stringify({ name: "good-plugin", version: "1.0.0", description: "A good fixture.", author: { name: "Fixture" }, license: "MIT" }),
    "README.md": "# Good\n\nThis fixture has enough documentation words to pass the hosted README check. It explains what the plugin does, how a developer can install it, what behavior to expect, how to report problems, and why the repository exists. Nothing in this fixture performs network actions or needs private credentials.",
    "skills/check/SKILL.md": "---\nname: check\ndescription: Run the fixture check.\n---\n\nCheck the fixture."
  }
});
assert.equal(good.summary.BLOCK, 0, JSON.stringify(good, null, 2));

const bad = scanSnapshot({
  repository: "example/bad",
  branch: "main",
  files: [
    { path: ".claude-plugin/plugin.json", type: "blob", mode: "100644", size: 100 },
    { path: "README.md", type: "blob", mode: "100644", size: 20 },
    { path: "skills/bad/SKILL.md", type: "blob", mode: "100644", size: 100 }
  ],
  texts: {
    ".claude-plugin/plugin.json": JSON.stringify({ name: "Bad Name" }),
    "README.md": "# Bad\nToo short.",
    "skills/bad/SKILL.md": "No frontmatter here."
  }
});
assert.ok(bad.summary.BLOCK >= 2, JSON.stringify(bad, null, 2));
assert.ok(bad.findings.some(item => item.code === "name-shape"));
assert.ok(bad.findings.some(item => item.code === "readme-short"));
assert.ok(bad.findings.some(item => item.code === "license-missing"));
assert.ok(bad.findings.some(item => item.code === "frontmatter-missing"));
assert.match(reportMarkdown(bad), /PlugShip Cloud Report/);

console.log("PASS: cloud scanner fixtures and report export");
