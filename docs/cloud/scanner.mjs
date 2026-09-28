const NAME_RE = /^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/;
const RESERVED = new Set(["claude", "anthropic", "official", "plugin", "mcp", "test"]);
const SYSTEM_JUNK = new Set([".DS_Store", "Thumbs.db", "desktop.ini", "__MACOSX"]);
const WINDOWS_RESERVED = new Set(["con","prn","aux","nul",..."123456789".split("").map(n=>"com"+n),..."123456789".split("").map(n=>"lpt"+n)]);
const MEDIA = new Set([".png",".jpg",".jpeg",".gif",".webp",".ttf",".otf",".woff",".woff2"]);
const TEXT_EXT = new Set([".md",".txt",".json",".yaml",".yml",".toml",".py",".js",".mjs",".cjs",".ts",".tsx",".jsx",".sh",".bash",".zsh",".css",".html",".xml",".csv",".svg"]);

function ext(path) {
  const file = path.split("/").pop() || "";
  const i = file.lastIndexOf(".");
  return i >= 0 ? file.slice(i).toLowerCase() : "";
}

function add(findings, level, code, message, path = null) {
  findings.push({ level, code, message, path });
}

export function parseRepo(input) {
  let value = String(input || "").trim().replace(/\.git$/, "");
  if (!value) throw new Error("Enter a GitHub repository URL or owner/repo.");
  if (/^[\w.-]+\/[\w.-]+$/.test(value)) {
    const [owner, repo] = value.split("/");
    return { owner, repo };
  }
  const url = new URL(value);
  if (url.hostname !== "github.com" && url.hostname !== "www.github.com") throw new Error("Only github.com repositories are supported.");
  const parts = url.pathname.split("/").filter(Boolean);
  if (parts.length < 2) throw new Error("GitHub URL must contain owner/repository.");
  return { owner: parts[0], repo: parts[1] };
}

async function ghJson(url) {
  const res = await fetch(url, { headers: { Accept: "application/vnd.github+json" } });
  if (res.status === 403) throw new Error("GitHub API rate limit reached. Try again later or run PlugShip locally.");
  if (res.status === 404) throw new Error("Repository not found or it is private.");
  if (!res.ok) throw new Error(`GitHub API error ${res.status}.`);
  return res.json();
}

async function fetchText(owner, repo, ref, path) {
  const encoded = path.split("/").map(encodeURIComponent).join("/");
  const url = `https://raw.githubusercontent.com/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${encodeURIComponent(ref)}/${encoded}`;
  const res = await fetch(url);
  if (!res.ok) return null;
  return res.text();
}

function wordCountWithoutFences(text) {
  let inside = false;
  const kept = [];
  for (const line of String(text || "").split(/\r?\n/)) {
    if (line.trim().startsWith("```")) { inside = !inside; continue; }
    if (!inside) kept.push(line);
  }
  return (kept.join("\n").match(/[A-Za-z0-9_'-]+/g) || []).length;
}

function frontmatterCheck(path, text, findings) {
  const lines = String(text || "").split(/\r?\n/);
  if (lines[0]?.trim() !== "---") {
    add(findings, "WARN", "frontmatter-missing", "Component has no YAML frontmatter.", path);
    return;
  }
  const end = lines.slice(1).findIndex(x => x.trim() === "---");
  if (end < 0) {
    add(findings, "BLOCK", "frontmatter-unclosed", "YAML frontmatter is not closed with ---.", path);
    return;
  }
  const meta = lines.slice(1, end + 1);
  const desc = meta.find(x => /^description\s*:/.test(x));
  if (!desc) add(findings, "WARN", "description-missing", "Component frontmatter has no description.", path);
  if (desc && /^description\s*:\s*\[/.test(desc)) add(findings, "BLOCK", "description-not-scalar", "Description must be a single text value.", path);
}

function checkPaths(files, findings) {
  let total = 0;
  for (const file of files) {
    const parts = file.path.split("/");
    if (parts.some(x => SYSTEM_JUNK.has(x))) add(findings, "BLOCK", "system-file", "Remove operating-system metadata before submission.", file.path);
    for (const part of parts) {
      const stem = part.split(".")[0].toLowerCase();
      if (part.includes(":") || part.endsWith(" ") || part.endsWith(".") || WINDOWS_RESERVED.has(stem)) {
        add(findings, "BLOCK", "cross-platform-name", "Path may be invalid on Windows or macOS.", file.path);
        break;
      }
    }
    if (file.mode === "120000") add(findings, "BLOCK", "symlink", "Symbolic links are not suitable for directory submission.", file.path);
    if (file.type !== "blob") continue;
    total += file.size || 0;
    if ((file.size || 0) > 5 * 1024 * 1024) add(findings, "BLOCK", "file-over-5mb", "A file exceeds 5 MiB.", file.path);
    if ((file.size || 0) > 256 * 1024 && !MEDIA.has(ext(file.path))) add(findings, "HOLD", "large-nonmedia-file", "Non-media file exceeds 256 KiB and may need reviewer inspection.", file.path);
  }
  if (files.filter(x => x.type === "blob").length > 512) add(findings, "HOLD", "file-count", "Repository contains more than 512 files.", null);
  if (total > 256 * 1024 * 1024) add(findings, "BLOCK", "unpacked-size", "Repository exceeds 256 MiB.", null);
}

function checkManifest(text, findings) {
  if (text == null) {
    add(findings, "BLOCK", "manifest-missing", "Missing .claude-plugin/plugin.json.", ".claude-plugin/plugin.json");
    return {};
  }
  let manifest;
  try { manifest = JSON.parse(text); }
  catch (e) {
    add(findings, "BLOCK", "manifest-json", `plugin.json is invalid JSON: ${e.message}`, ".claude-plugin/plugin.json");
    return {};
  }
  const name = manifest.name;
  if (typeof name !== "string" || !NAME_RE.test(name)) add(findings, "BLOCK", "name-shape", "Plugin name should use lowercase letters, digits, and hyphens, up to 64 characters.", ".claude-plugin/plugin.json");
  else if (RESERVED.has(name)) add(findings, "BLOCK", "reserved-name", `Plugin name "${name}" is reserved as a standalone name.`, ".claude-plugin/plugin.json");
  for (const key of ["description","author","version"]) if (!(key in manifest)) add(findings, "WARN", `manifest-${key}-missing`, `Manifest is missing recommended field: ${key}.`, ".claude-plugin/plugin.json");
  return manifest;
}

function checkMcp(text, findings) {
  if (text == null) return;
  let data;
  try { data = JSON.parse(text); }
  catch (e) { add(findings, "BLOCK", "mcp-json", `.mcp.json is invalid JSON: ${e.message}`, ".mcp.json"); return; }
  if (!data.mcpServers || typeof data.mcpServers !== "object" || Array.isArray(data.mcpServers)) {
    add(findings, "BLOCK", "mcp-servers-shape", ".mcp.json needs a top-level mcpServers object.", ".mcp.json");
    return;
  }
  for (const [name, server] of Object.entries(data.mcpServers)) {
    if (!server || typeof server !== "object" || Array.isArray(server)) { add(findings, "BLOCK", "mcp-entry-shape", `MCP server "${name}" must be an object.`, ".mcp.json"); continue; }
    if ("url" in server) {
      if (!["http","sse","ws"].includes(server.type)) add(findings, "BLOCK", "mcp-type", `Remote MCP server "${name}" should use type http, sse, or ws.`, ".mcp.json");
      if (typeof server.url === "string" && server.url && !server.url.startsWith("https://") && !server.url.startsWith("wss://") && !server.url.startsWith("${user_config.")) {
        add(findings, "BLOCK", "mcp-url", `Remote MCP server "${name}" should use https:// or wss://.`, ".mcp.json");
      }
    } else if (!("command" in server)) add(findings, "BLOCK", "mcp-endpoint", `MCP server "${name}" needs url or command.`, ".mcp.json");
  }
}

function exactPinned(token) {
  if (token.startsWith("@")) {
    const m = token.match(/^(@[^/]+\/[^@]+)@(.+)$/);
    return !!(m && /^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/.test(m[2]));
  }
  if (token.includes("@")) return /^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/.test(token.split("@").pop());
  if (token.includes("==")) return /^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/.test(token.split("==").pop());
  return false;
}

function checkLaunchers(path, text, findings) {
  const patterns = [
    /\bnpx\s+([^\s]+)/g,
    /\bbunx\s+([^\s]+)/g,
    /\buvx\s+([^\s]+)/g,
    /\bpnpm\s+dlx\s+([^\s]+)/g,
    /\byarn\s+dlx\s+([^\s]+)/g
  ];
  for (const re of patterns) {
    for (const m of text.matchAll(re)) {
      const token = m[1].replace(/['";,)]+$/g, "");
      if (!exactPinned(token)) add(findings, "BLOCK", "unpinned-launcher", `Package launcher target "${token}" is not pinned to an exact version.`, path);
    }
  }
}

export function scanSnapshot(snapshot) {
  const findings = [];
  checkPaths(snapshot.files || [], findings);
  const texts = snapshot.texts || {};
  const manifest = checkManifest(texts[".claude-plugin/plugin.json"] ?? null, findings);

  const readmePath = Object.keys(texts).find(path => /^readme(?:\.md)?$/i.test(path));
  if (!readmePath) {
    add(findings, "BLOCK", "readme-missing", "A README is required for directory submission.", null);
  } else {
    const count = wordCountWithoutFences(texts[readmePath]);
    if (count < 40) add(findings, "BLOCK", "readme-short", `README has about ${count} non-code words; at least 40 are recommended.`, readmePath);
  }

  const licenseFile = (snapshot.files || []).some(file => /(^|\/)license(?:\.md|\.txt)?$/i.test(file.path));
  if (!licenseFile && !manifest.license) add(findings, "BLOCK", "license-missing", "Add a LICENSE file or a license field in plugin.json.", null);

  checkMcp(texts[".mcp.json"] ?? null, findings);
  for (const [path, text] of Object.entries(texts)) {
    if (/^skills\/[^/]+\/SKILL\.md$/.test(path) || /^commands\/[^/]+\.md$/.test(path) || /^agents\/[^/]+\.md$/.test(path)) {
      frontmatterCheck(path, text, findings);
    }
    checkLaunchers(path, text, findings);
  }

  const summary = { BLOCK: 0, HOLD: 0, WARN: 0, NOTE: 0 };
  for (const finding of findings) summary[finding.level] = (summary[finding.level] || 0) + 1;
  const state = summary.BLOCK ? "needs-fixes" : (summary.HOLD || summary.WARN) ? "review" : "ready";
  return { repository: snapshot.repository, branch: snapshot.branch, manifest, summary, state, findings, scannedAt: new Date().toISOString() };
}

function wantedTextFiles(files) {
  const core = new Set([
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".mcp.json",
    ".gitattributes",
    "plugin.json",
    "README.md",
    "README",
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt"
  ]);
  const component = /^(skills\/[^/]+\/SKILL\.md|commands\/[^/]+\.md|agents\/[^/]+\.md|hooks\/hooks\.json)$/;
  return files
    .filter(file => file.type === "blob" && (file.size || 0) <= 256 * 1024)
    .map(file => file.path)
    .filter(path => core.has(path) || component.test(path))
    .slice(0, 48);
}

export async function scanRepository(input) {
  const { owner, repo } = parseRepo(input);
  const meta = await ghJson(`https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`);
  const branch = meta.default_branch || "main";
  const tree = await ghJson(`https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/git/trees/${encodeURIComponent(branch)}?recursive=1`);
  if (tree.truncated) throw new Error("GitHub returned a truncated repository tree. Run the local scanner for this large repository.");

  const files = (tree.tree || []).map(item => ({
    path: item.path,
    size: item.size || 0,
    type: item.type,
    mode: item.mode
  }));
  const targets = wantedTextFiles(files);
  const texts = {};
  await Promise.all(targets.map(async path => {
    const text = await fetchText(owner, repo, branch, path);
    if (text != null) texts[path] = text;
  }));

  const report = scanSnapshot({
    repository: `${owner}/${repo}`,
    branch,
    files,
    texts
  });
  report.meta = {
    htmlUrl: meta.html_url,
    description: meta.description || "",
    stars: meta.stargazers_count || 0,
    private: !!meta.private,
    fileCount: files.filter(x => x.type === "blob").length,
    scannedTextFiles: Object.keys(texts).length
  };
  return report;
}

export function reportMarkdown(report) {
  const s = report.summary;
  const name = report.manifest?.displayName || report.manifest?.name || report.repository;
  const lines = [
    "# PlugShip Cloud Report",
    "",
    `Repository: \`${report.repository}\``,
    `Branch: \`${report.branch}\``,
    `Plugin: \`${name}\``,
    "",
    `BLOCK: **${s.BLOCK}** · HOLD: **${s.HOLD}** · WARN: **${s.WARN}** · NOTE: **${s.NOTE}**`,
    ""
  ];
  if (!report.findings.length) lines.push("- No hosted preflight findings.");
  for (const item of report.findings) {
    const suffix = item.path ? ` — \`${item.path}\`` : "";
    lines.push(`- **${item.level} / ${item.code}**: ${item.message}${suffix}`);
  }
  lines.push(
    "",
    "## Scope",
    "",
    "This hosted scan reads only selected public repository metadata and configuration/documentation files directly from GitHub in your browser.",
    "For deeper source scanning and official local Claude validation, run the PlugShip local plugin.",
    "",
    `Scanned at: ${report.scannedAt}`
  );
  return lines.join("\n") + "\n";
}

export function reportFilename(report, extension) {
  return `plugship-${report.repository.replace(/[^A-Za-z0-9._-]+/g, "-")}-report.${extension}`;
}
