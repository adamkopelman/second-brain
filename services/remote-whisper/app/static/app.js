// Queue page: polls the API, renders rows, uploads dropped files, expands finished transcripts.
"use strict";
(function () {
  const L = window.WhisperLogic;
  const POLL_VISIBLE_MS = 2000;
  const POLL_HIDDEN_MS = 5000;

  const els = {
    summary: document.getElementById("summary"),
    banner: document.getElementById("banner"),
    jobs: document.getElementById("jobs"),
    empty: document.getElementById("empty"),
    dropzone: document.getElementById("dropzone"),
    file: document.getElementById("file"),
    pick: document.getElementById("pick"),
    uploads: document.getElementById("uploads"),
  };

  const expanded = new Set();
  const transcripts = new Map();
  let timer = null;

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function showBanner(message) {
    els.banner.textContent = message || "";
    els.banner.hidden = !message;
  }

  function renderTranscript(job) {
    const wrap = node("div", "transcript");
    const text = transcripts.has(job.id) ? transcripts.get(job.id) : "Loading transcript…";
    wrap.appendChild(node("pre", "transcript-body", text));
    const actions = node("div", "transcript-actions");
    const copy = node("button", "", "Copy");
    copy.type = "button";
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(transcripts.get(job.id) || "");
        copy.textContent = "Copied";
        setTimeout(() => (copy.textContent = "Copy"), 1500);
      } catch (err) {
        showBanner(`Could not copy: ${err.message || err}`);
      }
    });
    const download = node("a", "button-link", "Download .txt");
    download.href = `api/jobs/${job.id}/transcript`;
    actions.appendChild(copy);
    actions.appendChild(download);
    wrap.appendChild(actions);
    return wrap;
  }

  function renderJob(job) {
    const item = node("li", `job job-${job.status}`);
    const head = node("div", "job-head");
    head.appendChild(node("span", "job-name", job.name || job.filename));
    head.appendChild(node("span", `pill pill-${job.status}`, L.statusLabel(job)));
    item.appendChild(head);

    const bar = node("div", "bar");
    const fill = node("div", "bar-fill");
    fill.style.width = job.status === "done" ? "100%" : L.percentText(job.progress);
    bar.appendChild(fill);
    item.appendChild(bar);
    item.appendChild(node("div", "job-meta", L.metaText(job)));

    if (job.status === "done" || job.status === "failed") {
      const toggle = node("button", "toggle", expanded.has(job.id) ? "Hide transcript" : "Show transcript");
      toggle.type = "button";
      if (job.status === "failed") toggle.textContent = expanded.has(job.id) ? "Hide error" : "Show error";
      toggle.addEventListener("click", () => {
        if (expanded.has(job.id)) expanded.delete(job.id);
        else {
          expanded.add(job.id);
          if (job.status === "done" && !transcripts.has(job.id)) loadTranscript(job.id);
        }
        tick();
      });
      item.appendChild(toggle);
      if (expanded.has(job.id)) {
        item.appendChild(job.status === "done" ? renderTranscript(job) : node("pre", "transcript-body", job.error || ""));
      }
    }
    return item;
  }

  async function loadTranscript(jobId) {
    try {
      const response = await fetch(`api/jobs/${jobId}`, { cache: "no-store" });
      const job = await response.json();
      transcripts.set(jobId, job.transcript || "(empty transcript)");
    } catch (err) {
      transcripts.set(jobId, `Could not load transcript: ${err.message || err}`);
    }
    tick();
  }

  function render(payload) {
    els.summary.textContent = L.summaryText(payload.stats, payload.model_ready);
    const jobs = L.sortJobs(payload.jobs);
    els.jobs.replaceChildren(...jobs.map(renderJob));
    els.empty.hidden = jobs.length > 0;
  }

  async function tick() {
    try {
      const response = await fetch("api/jobs", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json());
      showBanner("");
    } catch (err) {
      showBanner(`Cannot reach the service: ${err.message || err}`);
    }
  }

  function schedule() {
    if (timer) clearInterval(timer);
    timer = setInterval(tick, document.hidden ? POLL_HIDDEN_MS : POLL_VISIBLE_MS);
  }

  function upload(file) {
    const row = node("div", "upload", `Uploading ${file.name}… 0%`);
    els.uploads.appendChild(row);
    const query = `?filename=${encodeURIComponent(file.name)}&name=${encodeURIComponent(file.name.replace(/\.[^.]+$/, ""))}`;
    const request = new XMLHttpRequest();
    request.open("POST", `api/jobs${query}`);
    request.setRequestHeader("Content-Type", "application/octet-stream");
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        row.textContent = `Uploading ${file.name}… ${Math.round((event.loaded / event.total) * 100)}%`;
      }
    });
    request.addEventListener("load", () => {
      if (request.status === 201) {
        row.remove();
        tick();
      } else {
        let message = `HTTP ${request.status}`;
        try {
          message = JSON.parse(request.responseText).error || message;
        } catch (err) {
          /* keep the status line */
        }
        row.className = "upload upload-failed";
        row.textContent = `${file.name}: ${message}`;
      }
    });
    request.addEventListener("error", () => {
      row.className = "upload upload-failed";
      row.textContent = `${file.name}: upload failed`;
    });
    request.send(file);
  }

  function wireUploads() {
    els.pick.addEventListener("click", () => els.file.click());
    els.file.addEventListener("change", () => {
      Array.from(els.file.files || []).forEach(upload);
      els.file.value = "";
    });
    ["dragenter", "dragover"].forEach((type) =>
      els.dropzone.addEventListener(type, (event) => {
        event.preventDefault();
        els.dropzone.classList.add("dragging");
      })
    );
    ["dragleave", "drop"].forEach((type) =>
      els.dropzone.addEventListener(type, (event) => {
        event.preventDefault();
        els.dropzone.classList.remove("dragging");
      })
    );
    els.dropzone.addEventListener("drop", (event) => {
      Array.from(event.dataTransfer.files || []).forEach(upload);
    });
  }

  document.addEventListener("visibilitychange", schedule);
  wireUploads();
  tick();
  schedule();
})();
