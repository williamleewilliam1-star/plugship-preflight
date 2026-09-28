---
name: directory-preflight
description: Preflight plugin repositories for public AI plugin directories and prepare portable skills-only packages. Use when the user asks to validate, package, repair, or migrate a plugin before Claude or OpenAI directory submission.
---

# PlugShip directory preflight

Use the bundled deterministic tools first. Do not rely on memory for directory rules when the local reports can establish the mechanical facts.

## Choose the target

First determine whether the user is preparing for the Claude Plugin Directory, an OpenAI skills-only plugin submission, or both.

For Claude, the source plugin normally contains `.claude-plugin/plugin.json`. For OpenAI portability, the same Claude source can be analyzed and packaged into the portable Agent Plugins layout.

## Claude workflow

1. Identify the plugin folder containing `.claude-plugin/plugin.json`.
2. Set `PLUGIN_HOME="${PLUGIN_ROOT:-$CLAUDE_PLUGIN_ROOT}"`.
3. Run `python3 "$PLUGIN_HOME/scripts/preflight.py" <plugin-folder> --report-dir <plugin-folder>/.plugship-report --claude-validate`.
4. Read `.plugship-report/report.md` and `report.json`.
5. Resolve every local BLOCK finding before submission. Treat HOLD and WARN as review items, not guaranteed rejection.

## OpenAI portability workflow

1. Start from the Claude plugin folder containing `.claude-plugin/plugin.json`.
2. Set `PLUGIN_HOME="${PLUGIN_ROOT:-$CLAUDE_PLUGIN_ROOT}"`.
3. Run `python3 "$PLUGIN_HOME/scripts/openai_port.py" <plugin-folder> --zip --report <plugin-folder>/.plugship-openai-report.md`.
4. Read the report and separate BLOCK, MIGRATE, REVIEW, and NOTE findings.
5. Do not silently convert commands, agents, hooks, local MCP servers, credentials, or authentication flows when intent is ambiguous.
6. Rerun the analyzer after fixes until no BLOCK or unresolved MIGRATE findings remain.
7. Use the generated ZIP only as a submission candidate; portal validation, identity verification, policy attestations, and final publication remain separate gates.

## Safe remediation rules

- Preserve the plugin's intended behavior and public API.
- Never invent credentials, endpoints, licenses, ownership claims, organization names, privacy statements, or legal attestations.
- Do not place authentication values directly in manifests, examples, connector headers, or skill text.
- Do not weaken permission or security settings merely to satisfy a validator.
- Do not rename a released plugin without warning that its identity may be permanent.
- Do not claim that local validation guarantees directory acceptance.
- Do not submit, publish, accept legal terms, or complete identity verification unless the user explicitly performs or authorizes that specific action.

## Required final report

Return:

- source plugin path and detected name/version
- selected target: Claude, OpenAI, or both
- blocker and warning counts for each tool that ran
- every edited file and the reason for the edit
- result of Claude local validation, when run
- generated OpenAI package/ZIP path, when built
- remaining portal-only work such as security scan, identity verification, policy attestations, review, or publish decision
