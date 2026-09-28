---
name: directory-preflight
description: Prepare or review a Claude plugin repository for directory submission. Use when the user asks to validate, publish, package, repair, or preflight a Claude plugin, skill bundle, or MCP-backed plugin before submission.
---

# PlugShip directory preflight

Use the bundled deterministic scanner first. Do not rely on memory for directory rules when the local report can establish the mechanical facts.

## Workflow

1. Identify the plugin folder: it is the folder containing `.claude-plugin/plugin.json`, or a skills-only folder the user explicitly wants to submit.
2. Set `PLUGIN_HOME="${PLUGIN_ROOT:-$CLAUDE_PLUGIN_ROOT}"` and run `python3 "$PLUGIN_HOME/scripts/preflight.py" <plugin-folder> --report-dir <plugin-folder>/.plugship-report --claude-validate` when Claude Code is available.
3. Read `.plugship-report/report.md` and `report.json`.
4. Separate findings into BLOCK, HOLD, WARN, and NOTE. Never describe a HOLD as guaranteed rejection.
5. Fix only mechanical issues that are supported by the report and by the user's request.
6. Rerun the scanner after edits until no local BLOCK findings remain.

## Safe remediation rules

- Preserve the plugin's intended behavior and public API.
- Never invent credentials, endpoints, licenses, ownership claims, or organization names.
- Do not place authentication values directly in manifests, examples, or connector headers.
- Do not weaken permission or security settings merely to satisfy a scan.
- Do not rename a released plugin without warning that its identity may be permanent.
- Do not claim that local validation guarantees directory acceptance.
- Do not submit or publish unless the user explicitly asks for that action.

## Required final report

Return:

- plugin path and detected plugin name/version
- local blocker count, reviewer-hold count, warning count
- every edited file and the reason for the edit
- result of `claude plugin validate`, if run
- remaining portal-only work: repository validation, official security scan, review, and publish decision
