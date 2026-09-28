#!/usr/bin/env python3
import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
SENSITIVE_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password)\b\s*[:=]\s*['\"]?([^\s'\"}]{12,})"
)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def add(items, level, code, message, path=None):
    items.append({"level": level, "code": code, "message": message, "path": str(path) if path else None})


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def iter_text_files(root):
    allowed = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".css", ".html", ".xml"}
    for p in root.rglob("*"):
        if p.is_file() and (p.suffix.lower() in allowed or p.name in {"LICENSE", "Makefile", "Dockerfile"}):
            yield p


def scan_source(root):
    findings = []
    manifest_path = root / ".claude-plugin" / "plugin.json"
    if not manifest_path.exists():
        add(findings, "BLOCK", "claude-manifest-missing", "Missing .claude-plugin/plugin.json.", manifest_path)
        return {}, findings
    try:
        manifest = load_json(manifest_path)
    except Exception as exc:
        add(findings, "BLOCK", "claude-manifest-json", f"Claude manifest is invalid JSON: {exc}", manifest_path)
        return {}, findings

    name = manifest.get("name")
    version = manifest.get("version")
    description = manifest.get("description")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        add(findings, "BLOCK", "name", "Plugin name must fit OpenAI's 64-character ASCII plugin-name rule.", manifest_path)
    if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
        add(findings, "BLOCK", "version", "Plugin version must be semantic versioning such as 1.0.0.", manifest_path)
    if not isinstance(description, str) or not description.strip():
        add(findings, "BLOCK", "description", "Plugin description must be non-empty.", manifest_path)
    return manifest, findings


def inspect_components(root, findings):
    skills = sorted(root.glob("skills/*/SKILL.md"))
    if not skills:
        add(findings, "BLOCK", "skills-missing", "OpenAI skills-only submission needs at least one valid skill under skills/<name>/SKILL.md.", root / "skills")

    for dirname, code in (("commands", "commands-present"), ("agents", "agents-present")):
        path = root / dirname
        if path.exists() and any(path.rglob("*.md")):
            add(findings, "MIGRATE", code, f"{dirname}/ must be converted into reusable skills for OpenAI submission.", path)

    hooks = root / "hooks"
    if hooks.exists() and any(hooks.rglob("*")):
        add(findings, "MIGRATE", "hooks-present", "Claude hooks may need adaptation for the Codex hook runtime.", hooks)

    mcp_path = root / ".mcp.json"
    if mcp_path.exists():
        try:
            data = load_json(mcp_path)
        except Exception as exc:
            add(findings, "BLOCK", "mcp-json", f".mcp.json is invalid JSON: {exc}", mcp_path)
            data = {}
        servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
        for server_name, server in servers.items():
            if not isinstance(server, dict):
                add(findings, "BLOCK", "mcp-entry", f"MCP server {server_name!r} is not an object.", mcp_path)
                continue
            if "command" in server:
                add(findings, "MIGRATE", "local-mcp", f"Local MCP server {server_name!r} must be deployed to a stable public HTTPS endpoint for public OpenAI submission.", mcp_path)
            url = server.get("url")
            if isinstance(url, str) and url.startswith("https://"):
                add(findings, "NOTE", "remote-mcp", f"Remote MCP server {server_name!r} can be reused through an OpenAI With MCP submission after auth/domain checks.", mcp_path)

    for p in iter_text_files(root):
        text = read_text(p)
        if text is None:
            continue
        config_or_instruction = (
            p.name in {"plugin.json", ".mcp.json", "hooks.json", "SKILL.md"}
            or "commands" in p.parts
            or "agents" in p.parts
            or "skills" in p.parts
            or "hooks" in p.parts
        )
        if "${user_config." in text and config_or_instruction:
            add(findings, "MIGRATE", "user-config", "Claude userConfig references need an OpenAI replacement: task input, OAuth/hosted storage, or documented local config.", p)
        if p.name == "SKILL.md" and re.search(r"\bClaude\b", text, flags=re.I):
            add(findings, "REVIEW", "claude-wording", "Skill text mentions Claude; review whether the wording should become provider-neutral.", p)

        for match in SENSITIVE_RE.finditer(text):
            value = match.group(2)
            if value.startswith("${user_config.") or value.lower() in {"your_token_here", "your_api_key_here"}:
                continue
            add(findings, "BLOCK", "possible-secret", f"Possible committed credential near {match.group(1)!r}; remove it before packaging.", p)
            break

    return skills


def portable_manifest(source_manifest):
    out = {
        "$schema": SCHEMA,
        "name": source_manifest["name"],
        "version": source_manifest["version"],
        "description": source_manifest["description"].strip(),
    }
    for key in ("author", "homepage", "repository", "license", "keywords"):
        value = source_manifest.get(key)
        if value not in (None, "", [], {}):
            out[key] = value
    return out


def copy_optional_dir(source, target, name):
    src = source / name
    if src.exists() and src.is_dir():
        shutil.copytree(
            src,
            target / name,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )


def package_skills_only(source, manifest, out_dir, findings, force=False):
    blocking = [f for f in findings if f["level"] in {"BLOCK", "MIGRATE"}]
    if blocking and not force:
        return None
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    (out_dir / "plugin.json").write_text(json.dumps(portable_manifest(manifest), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    shutil.copytree(source / "skills", out_dir / "skills")
    for name in ("scripts", "references", "assets"):
        copy_optional_dir(source, out_dir, name)
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "README.md"):
        src = source / name
        if src.exists() and src.is_file():
            shutil.copy2(src, out_dir / name)
    return out_dir


def make_zip(package_dir, zip_path):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        top = package_dir.name
        for p in package_dir.rglob("*"):
            if p.is_file():
                zf.write(p, Path(top) / p.relative_to(package_dir))
    return zip_path


def counts(findings):
    result = {"BLOCK": 0, "MIGRATE": 0, "REVIEW": 0, "NOTE": 0}
    for item in findings:
        result[item["level"]] = result.get(item["level"], 0) + 1
    return result


def render_report(source, manifest, findings, package_path=None, zip_path=None):
    c = counts(findings)
    lines = [
        "# PlugShip OpenAI Port Report",
        "",
        f"Source: `{source}`",
        f"Plugin: `{manifest.get('name', 'unknown')}` v{manifest.get('version', 'unknown')}",
        "",
        f"BLOCK: **{c['BLOCK']}** · MIGRATE: **{c['MIGRATE']}** · REVIEW: **{c['REVIEW']}** · NOTE: **{c['NOTE']}**",
        "",
    ]
    for item in findings:
        suffix = f" — `{item['path']}`" if item.get("path") else ""
        lines.append(f"- **{item['level']} / {item['code']}**: {item['message']}{suffix}")
    if not findings:
        lines.append("- No migration findings.")
    if package_path:
        lines += ["", f"Portable package: `{package_path}`"]
    if zip_path:
        lines += [f"Submission ZIP: `{zip_path}`"]
    lines += [
        "",
        "## Submission path",
        "",
        "- Skills-only: upload the ZIP as a skills-only plugin and review the generated OpenAI manifest/listing.",
        "- Remote MCP: submit the production HTTPS MCP endpoint separately and include migrated skills in the same draft.",
        "- Local MCP: deploy it to public HTTPS before public OpenAI submission.",
        "",
        "This report is a preparation aid, not a guarantee of directory approval.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Analyze a Claude plugin and prepare an OpenAI-compatible skills-only package.")
    parser.add_argument("source", help="Claude plugin folder containing .claude-plugin/plugin.json")
    parser.add_argument("--out", help="Output package directory")
    parser.add_argument("--zip", action="store_true", help="Create a ZIP around the portable package")
    parser.add_argument("--force", action="store_true", help="Package even when MIGRATE findings exist; BLOCK findings still prevent packaging")
    parser.add_argument("--report", help="Write Markdown report to this path")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.exists() or not source.is_dir():
        print(f"Source is not a directory: {source}", file=sys.stderr)
        return 1

    manifest, findings = scan_source(source)
    if manifest:
        inspect_components(source, findings)

    c = counts(findings)
    package_dir = None
    zip_path = None
    has_block = c["BLOCK"] > 0
    has_migrate = c["MIGRATE"] > 0

    if manifest and not has_block and (not has_migrate or args.force):
        default_out = source.parent / f"{manifest['name']}-openai"
        package_dir = package_skills_only(source, manifest, Path(args.out).expanduser().resolve() if args.out else default_out, findings, force=args.force)
        if package_dir and args.zip:
            zip_path = make_zip(package_dir, package_dir.parent / f"{package_dir.name}.zip")

    report_text = render_report(source, manifest, findings, package_dir, zip_path)
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")

    payload = {
        "source": str(source),
        "plugin": {"name": manifest.get("name"), "version": manifest.get("version")} if manifest else {},
        "summary": c,
        "findings": findings,
        "package_dir": str(package_dir) if package_dir else None,
        "zip_path": str(zip_path) if zip_path else None,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"PlugShip OpenAI: BLOCK={c['BLOCK']} MIGRATE={c['MIGRATE']} REVIEW={c['REVIEW']} NOTE={c['NOTE']}")
        for item in findings:
            suffix = f" [{item['path']}]" if item.get("path") else ""
            print(f"{item['level']:7} {item['code']}: {item['message']}{suffix}")
        if package_dir:
            print(f"PACKAGE {package_dir}")
        if zip_path:
            print(f"ZIP {zip_path}")

    return 2 if has_block else (3 if has_migrate and not args.force else 0)


if __name__ == "__main__":
    raise SystemExit(main())
