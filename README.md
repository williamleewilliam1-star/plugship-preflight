# PlugShip Preflight

[![CI](https://github.com/williamleewilliam1-star/plugship-preflight/actions/workflows/ci.yml/badge.svg)](https://github.com/williamleewilliam1-star/plugship-preflight/actions/workflows/ci.yml)

Website: https://williamleewilliam1-star.github.io/plugship-preflight/

PlugShip Preflight checks a Claude plugin folder before submission to the Claude Plugin Directory. It combines a deterministic local scanner with an Agent Skill that explains findings and prepares safe fixes.

The scanner runs locally, uses only the Python standard library, and makes no network requests. It reads the target plugin tree and reports likely blocking findings, reviewer holds, warnings, and notes. It does not upload, publish, modify, or transmit the target plugin unless the user explicitly asks an agent to edit files.

## What it checks

- plugin manifest presence, JSON syntax, name shape, and core metadata
- README word count and license presence
- operating-system junk files, invalid cross-platform names, symlinks, file counts, and file sizes
- `.gitattributes` patterns that can rewrite plugin contents
- `.mcp.json` syntax and remote URL schemes
- skill, command, and agent frontmatter basics
- package-launcher version pinning
- likely accidentally committed credential strings

## Install as a Claude plugin

Add the PlugShip marketplace from GitHub, then install the plugin:

```bash
claude plugin marketplace add williamleewilliam1-star/plugship-preflight
claude plugin install plugship-preflight@plugship-tools
```

For a one-session test without installing, use the packaged release directly:

```bash
claude --plugin-url https://github.com/williamleewilliam1-star/plugship-preflight/releases/download/v1.2.0/plugship-preflight-v1.2.0.zip
```

## Use

Run the deterministic scanner directly:

```bash
python3 scripts/preflight.py /path/to/your/plugin
```

Write machine-readable and Markdown reports:

```bash
python3 scripts/preflight.py /path/to/your/plugin --report-dir ./plugship-report
```

If Claude Code is installed, add `--claude-validate` to run Anthropic's local schema validator after PlugShip's checks.

## Cloud Beta

Try the browser-based scanner at https://williamleewilliam1-star.github.io/plugship-preflight/cloud/ . It scans selected metadata/configuration files from a public GitHub repository directly in the browser, supports single-repository and batch modes, stores recent history in browser localStorage, and exports Markdown/JSON reports. The launch beta is open for testing; deeper source checks and official local Claude validation remain in the free local plugin.

The bundled skill is for guided remediation. Ask Claude to use PlugShip Preflight on a plugin repository, review the generated findings, make only evidence-backed edits, rerun the scanner, and leave portal-only checks for the official developer portal.

## Scope and limitations

This project is a preflight aid, not Anthropic's validator and not a guarantee of directory approval. Anthropic can change its rules, portal validation can perform checks that a local tool cannot reproduce, and the post-submission scan may produce additional findings. Always run the official portal Validate step before submission.

## Data handling

The local PlugShip scanner reads local files and does not send repository contents or scan results to BABYDOV. The optional Claude Code validation subprocess is local. The Cloud Beta is separate: the user's browser requests selected files directly from public GitHub repositories, keeps recent scan summaries in browser localStorage, and does not proxy repository contents through a PlugShip application server. See [PRIVACY.md](./PRIVACY.md) for details.

## License

MIT.

## Claude → OpenAI portability

PlugShip 1.1 adds an OpenAI port analyzer for Claude plugins. It checks whether a plugin can be moved as a skills-only package, identifies commands/agents/hooks and local MCP servers that need migration, flags Claude `userConfig` references, reviews Claude-specific skill wording, and scans for likely committed credentials.

For a compatible skills-only plugin, build a portable Agent Plugins package and ZIP:

```bash
python3 scripts/openai_port.py /path/to/claude-plugin --zip --report ./openai-port-report.md
```

The generated package uses the portable Agent Plugins `plugin.json` format. Complex plugins are not silently rewritten: commands, agents, hooks, userConfig, and local MCP dependencies are reported as migration work instead of being guessed.

## Suggested commercial use

The scanner is suitable as the deterministic first stage of a paid plugin-portability audit: scan the customer's repository, return the report, repair supported issues, build the portable package, then complete portal-only checks in the publisher's own verified account.

## Privacy

PlugShip is local-first: the scanner does not make network requests or retain repository contents. See [PRIVACY.md](./PRIVACY.md) for the complete data-handling policy.

## Plans

The core PlugShip local plugin remains free and open source.

- **Free — €0:** local scanner, Claude validation, OpenAI portability report, public marketplace install.
- **Pro — €4.90/month (Early Access):** Free plus priority rule updates, subscriber release notes, priority support, and early access to hosted/batch features as they ship. Subscribe: https://buy.stripe.com/9B6dR2bbA8Q0fJJbn2aZi02
- **Studio — €9.90/month (Early Access):** Pro plus higher-priority support, priority feedback on complex reports, and early access to private-repo/team/bulk workflow features as they ship. Subscribe: https://buy.stripe.com/5kQdR27Zod6g2WX2QwaZi03

Manage or cancel a subscription: https://billing.stripe.com/p/login/28E8wI2F44zK699gHmaZi00

## Premium human service

Want a reviewed submission package instead of a self-serve scan? See [SERVICES.md](./SERVICES.md) for the separate €39 Quick Audit and €89 Audit + Fix Pack.
