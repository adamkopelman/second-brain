// Pure helpers for the queue page. No DOM, no fetch — so `node --test` can cover them.
"use strict";

const STATUS_LABELS = { queued: "Queued", running: "Transcribing", done: "Done", failed: "Failed" };
const STATUS_ORDER = { running: 0, queued: 1, failed: 2, done: 3 };

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return "—";
  const total = Math.max(0, Math.round(Number(seconds)));
  if (total < 60) return `${total}s`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes}m ${total % 60}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

function formatBytes(bytes) {
  if (bytes === null || bytes === undefined || Number.isNaN(Number(bytes))) return "—";
  const n = Number(bytes);
  if (n < 1024) return `${Math.round(n)} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = n / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(1)} ${units[unit]}`;
}

function percentText(progress) {
  const value = Number(progress);
  if (!Number.isFinite(value) || value <= 0) return "0%";
  return `${Math.round(Math.min(value, 1) * 100)}%`;
}

function statusLabel(job) {
  return STATUS_LABELS[job && job.status] || "Unknown";
}

function ordinal(n) {
  const suffixes = { 1: "st", 2: "nd", 3: "rd" };
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  return `${n}${suffixes[n % 10] || "th"}`;
}

function metaText(job) {
  if (!job) return "";
  if (job.status === "queued") {
    const position = job.queue_position === 1 ? "Next up" : `${ordinal(job.queue_position)} in queue`;
    return `${position} · ${formatBytes(job.bytes)}`;
  }
  if (job.status === "running") {
    const eta = job.eta_seconds ? `~${formatDuration(job.eta_seconds)} left` : "estimating…";
    return `${percentText(job.progress)} · ${formatDuration(job.elapsed_seconds)} elapsed · ${eta}`;
  }
  if (job.status === "done") {
    const parts = [`Took ${formatDuration(job.elapsed_seconds)} for ${formatDuration(job.duration_seconds)} of audio`];
    if (job.detected_language) parts.push(job.detected_language);
    return parts.join(" · ");
  }
  return job.error || "Failed";
}

function sortJobs(jobs) {
  return (jobs || []).slice().sort((a, b) => {
    const rank = (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9);
    if (rank !== 0) return rank;
    if (a.status === "queued" && b.status === "queued") {
      return (a.queue_position || 0) - (b.queue_position || 0);
    }
    return String(b.created_at || "").localeCompare(String(a.created_at || ""));
  });
}

function summaryText(stats, modelReady) {
  const s = stats || {};
  if (!modelReady) return "Loading the model — jobs will start once it is ready";
  return [
    `${s.running || 0} transcribing`,
    `${s.queued || 0} queued`,
    `${s.done || 0} done`,
    `${s.failed || 0} failed`,
  ].join(" · ");
}

function isActive(job) {
  return !!job && (job.status === "queued" || job.status === "running");
}

const API = {
  formatDuration, formatBytes, percentText, statusLabel, metaText, sortJobs, summaryText, isActive,
};

if (typeof module !== "undefined" && module.exports) module.exports = API;
if (typeof window !== "undefined") window.WhisperLogic = API;
