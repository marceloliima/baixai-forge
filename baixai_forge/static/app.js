"use strict";

const VIDEO_QUALITIES = [
  ["best", "Máxima / original"], ["2160", "2160p (4K)"], ["1440", "1440p"],
  ["1080", "1080p"], ["720", "720p"], ["480", "480p"], ["360", "360p"]
];
const AUDIO_QUALITIES = [["320","320 kbps"],["256","256 kbps"],["192","192 kbps"],["128","128 kbps"],["96","96 kbps"]];
const ACTIVE = new Set(["queued","downloading","processing","retrying","cancelling"]);
const STATUS_LABEL = {
  queued:"Na fila", downloading:"Baixando", processing:"Processando", retrying:"Tentando novamente",
  cancelling:"Cancelando", done:"Concluído", error:"Erro", cancelled:"Cancelado", interrupted:"Interrompido"
};

const $ = (selector) => document.querySelector(selector);
const form = $("#download-form");
const urlInput = $("#url");
const mediaType = $("#media-type");
const quality = $("#quality");
const jobsRoot = $("#jobs");
const emptyState = $("#empty-state");
let toastTimer = null;
let pollTimer = null;

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 3500);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {"Content-Type":"application/json", ...(options.headers || {})}
  });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) throw new Error(body?.detail || `Erro HTTP ${response.status}`);
  return body;
}

function updateQualities() {
  const options = mediaType.value === "mp3" ? AUDIO_QUALITIES : VIDEO_QUALITIES;
  const preferred = mediaType.value === "mp3" ? "192" : "1080";
  quality.replaceChildren();
  for (const [value, label] of options) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (value === preferred) option.selected = true;
    quality.append(option);
  }
}

function platformFromUrl(value) {
  try {
    const withScheme = value.includes("://") ? value : `https://${value}`;
    const host = new URL(withScheme).hostname.toLowerCase();
    if (host === "youtu.be" || host.endsWith(".youtube.com") || host === "youtube.com") return "YouTube";
    if (host === "instagram.com" || host.endsWith(".instagram.com")) return "Instagram";
    if (host === "tiktok.com" || host.endsWith(".tiktok.com")) return "TikTok";
    if (["facebook.com","fb.watch"].some(d => host === d || host.endsWith(`.${d}`))) return "Facebook";
    if (host.includes("shopee") || host === "shp.ee") return "Shopee";
  } catch (_) {}
  return "Plataforma automática";
}

function formatBytes(value) {
  if (value == null) return "—";
  const units = ["B","KB","MB","GB","TB"];
  let size = Number(value), index = 0;
  while (size >= 1024 && index < units.length - 1) { size /= 1024; index++; }
  return `${size.toFixed(index ? 1 : 0)} ${units[index]}`;
}

function formatSpeed(value) { return value ? `${formatBytes(value)}/s` : "—"; }
function formatEta(value) {
  if (value == null) return "—";
  const s = Math.max(0, Number(value));
  if (s < 60) return `${Math.round(s)}s`;
  return `${Math.floor(s/60)}m ${Math.round(s%60)}s`;
}

function button(label, className, action) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = className;
  btn.textContent = label;
  btn.addEventListener("click", action);
  return btn;
}

function renderJob(job) {
  const root = document.createElement("article");
  root.className = "job";

  const head = document.createElement("div"); head.className = "job-head";
  const titleWrap = document.createElement("div"); titleWrap.className = "job-title";
  const title = document.createElement("strong"); title.textContent = job.title || job.filename || job.url;
  const meta = document.createElement("div"); meta.className = "job-meta";
  meta.textContent = `${job.platform_name} • ${job.media_type === "mp3" ? "MP3" : "Vídeo"} • ${job.quality === "best" ? "máxima" : job.quality + (job.media_type === "mp3" ? " kbps" : "p")}`;
  titleWrap.append(title, meta);
  const status = document.createElement("span"); status.className = `status ${job.status}`; status.textContent = STATUS_LABEL[job.status] || job.status;
  head.append(titleWrap, status);

  const progressShell = document.createElement("div"); progressShell.className = "progress-shell";
  const progressBar = document.createElement("div"); progressBar.className = "progress-bar"; progressBar.style.width = `${job.progress || 0}%`;
  progressShell.append(progressBar);

  const line = document.createElement("div"); line.className = "job-line";
  const message = document.createElement("span"); message.textContent = job.message || "";
  const numbers = document.createElement("span");
  numbers.textContent = ACTIVE.has(job.status)
    ? `${Math.round(job.progress || 0)}% • ${formatSpeed(job.speed)} • ETA ${formatEta(job.eta)}`
    : (job.filesize ? formatBytes(job.filesize) : "");
  line.append(message, numbers);
  root.append(head, progressShell, line);

  if (job.error) {
    const error = document.createElement("div"); error.className = "error-line"; error.textContent = job.error;
    root.append(error);
  }

  const actions = document.createElement("div"); actions.className = "job-actions";
  if (ACTIVE.has(job.status)) {
    actions.append(button("Cancelar", "ghost small danger", async () => {
      try { await api(`/api/jobs/${job.id}/cancel`, {method:"POST", body:"{}"}); await loadJobs(); }
      catch (err) { toast(err.message); }
    }));
  }
  if (job.download_url) {
    const link = document.createElement("a"); link.className = "primary small"; link.href = job.download_url; link.textContent = "Salvar arquivo";
    actions.append(link);
  }
  if (["error","cancelled","interrupted"].includes(job.status)) {
    actions.append(button("Tentar novamente", "ghost small", async () => {
      try { await api(`/api/jobs/${job.id}/retry`, {method:"POST", body:"{}"}); await loadJobs(); }
      catch (err) { toast(err.message); }
    }));
  }
  if (!ACTIVE.has(job.status)) {
    actions.append(button("Remover", "ghost small", async () => {
      try { await api(`/api/jobs/${job.id}`, {method:"DELETE"}); await loadJobs(); }
      catch (err) { toast(err.message); }
    }));
  }
  root.append(actions);
  return root;
}

async function loadJobs() {
  try {
    const data = await api("/api/jobs?limit=50");
    jobsRoot.replaceChildren();
    emptyState.classList.toggle("hidden", data.jobs.length > 0);
    let hasActive = false;
    for (const job of data.jobs) {
      jobsRoot.append(renderJob(job));
      if (ACTIVE.has(job.status)) hasActive = true;
    }
    clearTimeout(pollTimer);
    pollTimer = setTimeout(loadJobs, hasActive ? 900 : 3500);
  } catch (err) {
    toast(err.message);
    clearTimeout(pollTimer);
    pollTimer = setTimeout(loadJobs, 5000);
  }
}

async function loadHealth() {
  try {
    const health = await api("/api/health");
    const pill = $("#health-pill");
    pill.textContent = health.ok ? (health.warnings.length ? "Sistema com alertas" : "Sistema pronto") : "Configuração incompleta";
    pill.className = `health-pill ${health.ok ? (health.warnings.length ? "warn" : "good") : "bad"}`;

    const cards = [
      ["yt-dlp", health.yt_dlp || "Não instalado"],
      ["FFmpeg", health.ffmpeg ? "Disponível" : "Não encontrado"],
      ["JS runtime", health.javascript_runtime || "Não detectado"],
      ["Disco livre", formatBytes(health.free_disk_bytes)]
    ];
    const grid = $("#health-grid"); grid.replaceChildren();
    for (const [label, value] of cards) {
      const card = document.createElement("div"); card.className = "health-card";
      const span = document.createElement("span"); span.textContent = label;
      const strong = document.createElement("strong"); strong.textContent = value;
      card.append(span, strong); grid.append(card);
    }
    const warnings = $("#health-warnings");
    warnings.classList.toggle("hidden", health.warnings.length === 0);
    warnings.textContent = health.warnings.join(" ");
  } catch (err) { toast(err.message); }
}

mediaType.addEventListener("change", updateQualities);
urlInput.addEventListener("input", () => { $("#platform-hint").textContent = platformFromUrl(urlInput.value); });
$("#refresh-jobs").addEventListener("click", loadJobs);
$("#refresh-health").addEventListener("click", loadHealth);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = $("#submit-button"); submit.disabled = true; submit.textContent = "Adicionando…";
  try {
    await api("/api/jobs", {
      method:"POST",
      body: JSON.stringify({url:urlInput.value, media_type:mediaType.value, quality:quality.value})
    });
    urlInput.value = "";
    $("#platform-hint").textContent = "Plataforma automática";
    toast("Download adicionado à fila.");
    await loadJobs();
  } catch (err) { toast(err.message); }
  finally { submit.disabled = false; submit.textContent = "Adicionar à fila"; }
});

updateQualities();
loadHealth();
loadJobs();
