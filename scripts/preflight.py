#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
RESERVED_EXACT = {"claude", "anthropic", "official", "plugin", "mcp", "test"}
SYSTEM_JUNK = {".DS_Store", "Thumbs.db", "desktop.ini", "__MACOSX"}
WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
ALLOWED_BINARY = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ttf", ".otf", ".woff", ".woff2"}
LAUNCHER_PATTERNS = [
    re.compile(r"\bnpx\s+([^\s]+)"),
    re.compile(r"\bbunx\s+([^\s]+)"),
    re.compile(r"\buvx\s+([^\s]+)"),
    re.compile(r"\bpnpm\s+dlx\s+([^\s]+)"),
    re.compile(r"\byarn\s+dlx\s+([^\s]+)"),
]
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".zsh", ".css", ".html", ".xml", ".csv", ".svg"}


def add(findings, level, code, message, path=None):
    findings.append({"level": level, "code": code, "message": message, "path": str(path) if path else None})


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    except OSError:
        return None

def word_count_without_fences(text):
    kept = []
    inside = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            inside = not inside
            continue
        if not inside:
            kept.append(line)
    return len(re.findall(r"\b[\w'-]+\b", "\n".join(kept)))


def is_probably_binary(path):
    if path.suffix.lower() in ALLOWED_BINARY:
        return True
    if path.suffix.lower() in TEXT_EXTENSIONS or path.name in {"LICENSE", "Dockerfile", "Makefile"}:
        return False
    try:
        data = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"\x00" in data


def valid_frontmatter(path, findings):
    text = read_text(path)
    if text is None:
        add(findings, "BLOCK", "frontmatter-unreadable", "Component file is not readable as UTF-8 text.", path)
        return
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        add(findings, "WARN", "frontmatter-missing", "Component has no YAML frontmatter.", path)
        return
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        add(findings, "BLOCK", "frontmatter-unclosed", "YAML frontmatter is not closed with ---.", path)
        return
    meta = lines[1:end]
    desc = [line for line in meta if re.match(r"^description\s*:", line)]
    if not desc:
        add(findings, "WARN", "description-missing", "Component frontmatter has no description field.", path)
    elif re.match(r"^description\s*:\s*\[", desc[0]):
        add(findings, "BLOCK", "description-not-scalar", "Description must be one text value, not a list.", path)

def check_manifest(root, findings):
    manifest_path = root / ".claude-plugin" / "plugin.json"
    if not manifest_path.exists():
        add(findings, "BLOCK", "manifest-missing", "Missing .claude-plugin/plugin.json.", manifest_path)
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        add(findings, "BLOCK", "manifest-json", f"plugin.json is not valid JSON: {exc}", manifest_path)
        return {}
    name = manifest.get("name")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        add(findings, "BLOCK", "name-shape", "Plugin name should use lowercase letters, digits, and hyphens, up to 64 characters.", manifest_path)
    elif name in RESERVED_EXACT:
        add(findings, "BLOCK", "reserved-name", f"Plugin name '{name}' is reserved as a standalone name.", manifest_path)
    for key in ("description", "author", "version"):
        if key not in manifest:
            add(findings, "WARN", f"manifest-{key}-missing", f"Manifest is missing recommended field: {key}.", manifest_path)
    author = manifest.get("author")
    if author is not None and not isinstance(author, (str, dict)):
        add(findings, "BLOCK", "author-shape", "Manifest author must be a string or object.", manifest_path)
    display = manifest.get("displayName")
    for label, value in (("displayName", display), ("author.name", author.get("name") if isinstance(author, dict) else author)):
        if isinstance(value, str) and re.search(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f]", value):
            add(findings, "BLOCK", "invisible-characters", f"{label} contains invisible or directional characters.", manifest_path)
    return manifest

def check_docs(root, manifest, findings):
    readme = next((p for p in (root / "README.md", root / "README") if p.exists()), None)
    if readme is None:
        add(findings, "BLOCK", "readme-missing", "A README is required for directory submission.", root)
    else:
        text = read_text(readme) or ""
        count = word_count_without_fences(text)
        if count < 40:
            add(findings, "BLOCK", "readme-short", f"README has about {count} non-code words; directory guidance requires at least 40.", readme)
    has_license_file = any((root / name).exists() for name in ("LICENSE", "LICENSE.md", "LICENSE.txt"))
    if not has_license_file and not manifest.get("license"):
        add(findings, "BLOCK", "license-missing", "Add a LICENSE file or a license field in plugin.json.", root)


def check_paths_and_sizes(root, findings):
    files = []
    total = 0
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        parts = rel.parts
        if any(part in {".git", ".plugship-report", "__pycache__", "dist"} for part in parts):
            continue
        if any(part in SYSTEM_JUNK for part in parts):
            add(findings, "BLOCK", "system-file", "Remove operating-system metadata before submission.", p)
        for part in parts:
            stem = Path(part).stem.lower()
            if ":" in part or part.endswith(" ") or part.endswith(".") or stem in WINDOWS_RESERVED:
                add(findings, "BLOCK", "cross-platform-name", "Path name may be invalid on Windows or macOS.", p)
        if p.is_symlink():
            add(findings, "BLOCK", "symlink", "Directory submission expects regular files and folders, not symbolic links.", p)
            continue
        if not p.is_file():
            continue
        files.append(p)
        try:
            size = p.stat().st_size
        except OSError:
            continue
        total += size
        if size > 5 * 1024 * 1024:
            add(findings, "BLOCK", "file-over-5mb", "A plugin file exceeds 5 MiB.", p)
        if size > 256 * 1024 and p.suffix.lower() not in ALLOWED_BINARY:
            add(findings, "HOLD", "large-nonmedia-file", "Non-image/font file exceeds 256 KiB and may require reviewer inspection.", p)
    if len(files) > 512:
        add(findings, "HOLD", "file-count", f"Plugin contains {len(files)} files; more than 512 may be held for review.", root)
    if total > 256 * 1024 * 1024:
        add(findings, "BLOCK", "unpacked-size", "Plugin folder exceeds 256 MiB unpacked.", root)
    return files

def check_gitattributes(root, findings):
    for p in [root / ".gitattributes", *root.parents]:
        if p.is_dir():
            p = p / ".gitattributes"
        if not p.exists() or not p.is_file():
            continue
        text = read_text(p) or ""
        lowered = text.lower()
        if "export-ignore" in lowered or "export-subst" in lowered:
            add(findings, "BLOCK", "gitattributes-export", "Remove export-ignore/export-subst from relevant .gitattributes files.", p)
        if re.search(r"\bfilter\s*=|\bfilter\b", lowered):
            add(findings, "WARN", "gitattributes-filter", "A Git filter may rewrite files during archive validation; review this file.", p)


def check_mcp(root, findings):
    path = root / ".mcp.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        add(findings, "BLOCK", "mcp-json", f".mcp.json is not valid JSON: {exc}", path)
        return
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        add(findings, "BLOCK", "mcp-servers-shape", ".mcp.json needs a top-level mcpServers object.", path)
        return
    for key, server in servers.items():
        if not isinstance(server, dict):
            add(findings, "BLOCK", "mcp-entry-shape", f"MCP server '{key}' must be an object.", path)
            continue
        url = server.get("url")
        if url is not None:
            typ = server.get("type")
            if typ not in {"http", "sse", "ws"}:
                add(findings, "BLOCK", "mcp-type", f"Remote MCP server '{key}' should use type http, sse, or ws.", path)
            if isinstance(url, str) and url and not (url.startswith("https://") or url.startswith("wss://") or url.startswith("${user_config.")):
                add(findings, "BLOCK", "mcp-url", f"Remote MCP server '{key}' should use an absolute https:// or wss:// URL.", path)
        elif "command" not in server:
            add(findings, "BLOCK", "mcp-endpoint", f"MCP server '{key}' needs either url or command.", path)

def launcher_is_pinned(token):
    if token.startswith("@"):
        match = re.match(r"^(@[^/]+/[^@]+)@(.+)$", token)
        return bool(match and re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", match.group(2)))
    if "@" in token:
        version = token.rsplit("@", 1)[1]
        return bool(re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version))
    if "==" in token:
        version = token.rsplit("==", 1)[1]
        return bool(re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version))
    return False


def check_launchers(files, findings):
    for p in files:
        if p.suffix.lower() not in TEXT_EXTENSIONS and p.name not in {"SKILL.md", "hooks.json"}:
            continue
        text = read_text(p)
        if text is None:
            continue
        for pattern in LAUNCHER_PATTERNS:
            for match in pattern.finditer(text):
                token = match.group(1).strip("'\";,)")
                if not launcher_is_pinned(token):
                    add(findings, "BLOCK", "unpinned-launcher", f"Package launcher target '{token}' is not pinned to an exact version.", p)


def check_sensitive_literals(files, findings):
    labels = re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password)\b\s*[:=]\s*['\"]?([^\s'\"}]{12,})")
    for p in files:
        if p.suffix.lower() not in TEXT_EXTENSIONS and p.name not in {"LICENSE", "Makefile", "Dockerfile"}:
            continue
        text = read_text(p)
        if text is None:
            continue
        for m in labels.finditer(text):
            value = m.group(2)
            if value.startswith("${user_config.") or value.lower() in {"your_token_here", "your_api_key_here"}:
                continue
            add(findings, "BLOCK", "sensitive-literal", f"Possible committed sensitive value next to '{m.group(1)}'; replace it with a user configuration reference or documented placeholder.", p)
            break

def check_components(root, findings):
    skill_files = list(root.glob("skills/*/SKILL.md"))
    command_files = list((root / "commands").glob("*.md")) if (root / "commands").exists() else []
    agent_files = list((root / "agents").glob("*.md")) if (root / "agents").exists() else []
    for p in skill_files + command_files + agent_files:
        valid_frontmatter(p, findings)
    for expected in ("skills", "commands", "agents", "hooks"):
        for p in root.iterdir():
            if p.is_dir() and p.name.lower() == expected and p.name != expected:
                add(findings, "BLOCK", "component-capitalization", f"Rename component folder '{p.name}' to '{expected}'.", p)


def check_binary_types(files, findings):
    for p in files:
        if not is_probably_binary(p):
            continue
        if p.suffix.lower() not in ALLOWED_BINARY:
            add(findings, "HOLD", "binary-file", "Binary file type may require reviewer inspection; prefer readable source where possible.", p)


def run_claude_validate(root, findings):
    try:
        proc = subprocess.run(["claude", "plugin", "validate", str(root)], text=True, capture_output=True, timeout=90)
    except FileNotFoundError:
        add(findings, "NOTE", "claude-missing", "Claude Code is not installed; skipped official local schema validation.", root)
        return None
    except subprocess.TimeoutExpired:
        add(findings, "WARN", "claude-timeout", "Claude Code validation timed out after 90 seconds.", root)
        return None
    output = (proc.stdout + "\n" + proc.stderr).strip()
    if proc.returncode == 0:
        add(findings, "NOTE", "claude-validation-pass", "Claude Code plugin validation passed.", root)
    else:
        add(findings, "BLOCK", "claude-validation-fail", "Claude Code plugin validation failed: " + output[:1200], root)
    return {"returncode": proc.returncode, "output": output}

def summarize(findings):
    levels = {"BLOCK": 0, "HOLD": 0, "WARN": 0, "NOTE": 0}
    for item in findings:
        levels[item["level"]] = levels.get(item["level"], 0) + 1
    return levels


def render_markdown(root, manifest, findings, claude_result):
    counts = summarize(findings)
    lines = [
        "# PlugShip Preflight Report",
        "",
        f"Target: `{root}`",
        f"Plugin: `{manifest.get('name', 'unknown')}` v{manifest.get('version', 'unknown')}",
        "",
        f"BLOCK: **{counts['BLOCK']}** · HOLD: **{counts['HOLD']}** · WARN: **{counts['WARN']}** · NOTE: **{counts['NOTE']}**",
        "",
    ]
    if not findings:
        lines += ["No local findings.", ""]
    for item in findings:
        path = f" — `{item['path']}`" if item.get("path") else ""
        lines.append(f"- **{item['level']} / {item['code']}**: {item['message']}{path}")
    if claude_result is not None:
        lines += ["", "## Claude Code validator", "", "```text", claude_result["output"][:6000], "```"]
    lines += ["", "## Next gate", "", "Run Validate in the official developer portal. Portal checks and the post-submission scan can find issues that this local tool cannot reproduce.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Preflight a Claude plugin folder before directory submission.")
    parser.add_argument("plugin", help="Path to the plugin folder")
    parser.add_argument("--report-dir", help="Write report.json and report.md to this directory")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of the human-readable summary")
    parser.add_argument("--claude-validate", action="store_true", help="Also run: claude plugin validate <folder>")
    args = parser.parse_args()

    root = Path(args.plugin).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Target is not a directory: {root}", file=sys.stderr)
        return 1

    findings = []
    manifest = check_manifest(root, findings)
    check_docs(root, manifest, findings)
    files = check_paths_and_sizes(root, findings)
    check_gitattributes(root, findings)
    check_mcp(root, findings)
    check_components(root, findings)
    check_binary_types(files, findings)
    check_launchers(files, findings)
    check_sensitive_literals(files, findings)
    claude_result = run_claude_validate(root, findings) if args.claude_validate else None

    payload = {
        "target": str(root),
        "plugin": {"name": manifest.get("name"), "version": manifest.get("version")},
        "summary": summarize(findings),
        "findings": findings,
        "claude_validate": claude_result,
    }

    if args.report_dir:
        report_dir = Path(args.report_dir).expanduser().resolve()
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (report_dir / "report.md").write_text(render_markdown(root, manifest, findings, claude_result), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        counts = payload["summary"]
        print(f"PlugShip: BLOCK={counts['BLOCK']} HOLD={counts['HOLD']} WARN={counts['WARN']} NOTE={counts['NOTE']}")
        for item in findings:
            suffix = f" [{item['path']}]" if item.get("path") else ""
            print(f"{item['level']:5} {item['code']}: {item['message']}{suffix}")

    return 2 if payload["summary"]["BLOCK"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
