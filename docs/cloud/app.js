import { scanRepository, reportMarkdown, reportFilename } from "./scanner.mjs";

const $ = selector => document.querySelector(selector);
const singleForm = $("#single-form");
const repoInput = $("#repo");
const resultEl = $("#result");
const batchForm = $("#batch-form");
const batchInput = $("#batch");
const batchResults = $("#batch-results");
const historyEl = $("#history");
const singleButton = $("#single-button");
const batchButton = $("#batch-button");

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  })[char]);
}

function stateLabel(state) {
  if (state === "ready") return "Ready";
  if (state === "review") return "Review";
  return "Needs fixes";
}

function saveHistory(report) {
  const key = "plugship-cloud-history-v1";
  let items = [];
  try { items = JSON.parse(localStorage.getItem(key) || "[]"); } catch {}
  items = items.filter(item => item.repository !== report.repository);
  items.unshift({
    repository: report.repository,
    state: report.state,
    summary: report.summary,
    scannedAt: report.scannedAt
  });
  localStorage.setItem(key, JSON.stringify(items.slice(0, 12)));
  renderHistory();
}

function renderHistory() {
  const key = "plugship-cloud-history-v1";
  let items = [];
  try { items = JSON.parse(localStorage.getItem(key) || "[]"); } catch {}
  if (!items.length) {
    historyEl.innerHTML = '<p class="muted">No browser-local scan history yet.</p>';
    return;
  }
  historyEl.innerHTML = items.map(item => {
    const s = item.summary;
    return `<button class="history-item" data-repo="${esc(item.repository)}">
      <span><strong>${esc(item.repository)}</strong><small>${new Date(item.scannedAt).toLocaleString()}</small></span>
      <span class="history-counts">B ${s.BLOCK} · H ${s.HOLD} · W ${s.WARN}</span>
    </button>`;
  }).join("");
  historyEl.querySelectorAll("[data-repo]").forEach(button => {
    button.addEventListener("click", () => {
      repoInput.value = button.dataset.repo;
      repoInput.focus();
    });
  });
}

function download(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function findingRows(report) {
  if (!report.findings.length) return '<div class="clean">No hosted preflight findings.</div>';
  return report.findings.map(item => `<div class="finding">
    <span class="level level-${item.level.toLowerCase()}">${item.level}</span>
    <div><strong>${esc(item.code)}</strong><p>${esc(item.message)}</p>${item.path ? `<code>${esc(item.path)}</code>` : ""}</div>
  </div>`).join("");
}

function reportCard(report, compact = false) {
  const s = report.summary;
  const pluginName = report.manifest?.displayName || report.manifest?.name || report.repository;
  const scope = report.meta ? `${report.meta.fileCount} files · ${report.meta.scannedTextFiles} config/docs read` : "";
  return `<article class="report ${compact ? "compact" : ""}">
    <div class="report-head">
      <div>
        <span class="state state-${report.state}">${stateLabel(report.state)}</span>
        <h2>${esc(pluginName)}</h2>
        <p><a href="${esc(report.meta?.htmlUrl || "#")}" target="_blank" rel="noopener">${esc(report.repository)}</a> · ${esc(report.branch)} ${scope ? "· " + esc(scope) : ""}</p>
      </div>
      <div class="score-grid">
        <span><strong>${s.BLOCK}</strong>BLOCK</span>
        <span><strong>${s.HOLD}</strong>HOLD</span>
        <span><strong>${s.WARN}</strong>WARN</span>
      </div>
    </div>
    ${compact ? "" : `<div class="report-actions">
      <button class="secondary export-md">Download Markdown</button>
      <button class="secondary export-json">Download JSON</button>
    </div>`}
    <div class="findings">${findingRows(report)}</div>
    <p class="scope-note">Hosted scan is intentionally privacy-light. Run the local plugin for deeper source checks and official local Claude validation.</p>
  </article>`;
}

function wireExports(container, report) {
  container.querySelector(".export-md")?.addEventListener("click", () => {
    download(reportMarkdown(report), reportFilename(report, "md"), "text/markdown;charset=utf-8");
  });
  container.querySelector(".export-json")?.addEventListener("click", () => {
    download(JSON.stringify(report, null, 2) + "\n", reportFilename(report, "json"), "application/json;charset=utf-8");
  });
}

singleForm.addEventListener("submit", async event => {
  event.preventDefault();
  const value = repoInput.value.trim();
  if (!value) return;
  singleButton.disabled = true;
  singleButton.textContent = "Scanning…";
  resultEl.innerHTML = '<div class="loading">Fetching public repository metadata from GitHub…</div>';
  try {
    const report = await scanRepository(value);
    resultEl.innerHTML = reportCard(report);
    wireExports(resultEl, report);
    saveHistory(report);
  } catch (error) {
    resultEl.innerHTML = `<div class="error"><strong>Scan failed</strong><p>${esc(error.message)}</p></div>`;
  } finally {
    singleButton.disabled = false;
    singleButton.textContent = "Run cloud scan";
  }
});

batchForm.addEventListener("submit", async event => {
  event.preventDefault();
  const repos = batchInput.value.split(/\r?\n|,/).map(x => x.trim()).filter(Boolean);
  const unique = [...new Set(repos)].slice(0, 10);
  if (!unique.length) return;
  batchButton.disabled = true;
  batchButton.textContent = "Scanning batch…";
  batchResults.innerHTML = "";
  for (let i = 0; i < unique.length; i++) {
    const slot = document.createElement("div");
    slot.className = "batch-slot";
    slot.innerHTML = `<div class="loading">[${i + 1}/${unique.length}] ${esc(unique[i])}</div>`;
    batchResults.appendChild(slot);
    try {
      const report = await scanRepository(unique[i]);
      slot.innerHTML = reportCard(report, true);
      saveHistory(report);
    } catch (error) {
      slot.innerHTML = `<div class="error"><strong>${esc(unique[i])}</strong><p>${esc(error.message)}</p></div>`;
    }
  }
  batchButton.disabled = false;
  batchButton.textContent = "Run batch scan";
});

renderHistory();
