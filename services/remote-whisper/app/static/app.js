// Queue page: polls the API, updates rows in place, uploads dropped files, shows transcripts.
"use strict";
(function () {
  const L = window.WhisperLogic;
  const POLL_ACTIVE_MS = 2000;
  const POLL_IDLE_MS = 10000;
  const POLL_HIDDEN_MS = 30000;

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
  const rows = new Map(); // job id -> row parts, so a tick updates instead of rebuilding
  const latest = new Map(); // job id -> last seen job json
  let timer = null;
  let timerMs = null;
  let inFlight = false;

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

  function buildRow(job) {
    const li = node("li", `job job-${job.status}`);
    const head = node("div", "job-head");
    const name = node("span", "job-name");
    const pill = node("span", "pill");
    head.appendChild(name);
    head.appendChild(pill);
    const bar = node("div", "bar");
    const fill = node("div", "bar-fill");
    bar.appendChild(fill);
    const meta = node("div", "job-meta");
    const toggle = node("button", "toggle");
    toggle.type = "button";
    toggle.hidden = true;
    const detail = node("div", "job-detail");
    detail.hidden = true;
    li.appendChild(head);
    li.appendChild(bar);
    li.appendChild(meta);
    li.appendChild(toggle);
    li.appendChild(detail);

    const row = { li, name, pill, fill, meta, toggle, detail, detailKey: null };
    toggle.addEventListener("click", () => {
      if (expanded.has(job.id)) {
        expanded.delete(job.id);
      } else {
        expanded.add(job.id);
        const current = latest.get(job.id);
        if (current && current.status === "done" && !transcripts.has(job.id)) {
          loadTranscript(job.id);
        }
      }
      updateRow(row, latest.get(job.id));
    });
    return row;
  }

  function buildDetail(job) {
    if (job.status === "failed") {
      return node("pre", "transcript-body", job.error || "No error message was recorded.");
    }
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

  // Updates an existing row's text and widths. Rebuilding the row (or its detail panel) on every
  // tick is what resets scroll position inside an open transcript and drops keyboard focus, so the
  // detail panel is only rebuilt when something it actually displays has changed.
  function updateRow(row, job) {
    if (!job) return;
    row.li.className = `job job-${job.status}`;
    row.name.textContent = job.name || job.filename;
    row.pill.className = `pill pill-${job.status}`;
    row.pill.textContent = L.statusLabel(job);
    row.fill.style.width = job.status === "done" ? "100%" : L.percentText(job.progress);
    row.meta.textContent = L.metaText(job);

    const finished = job.status === "done" || job.status === "failed";
    row.toggle.hidden = !finished;
    if (finished) {
      const open = expanded.has(job.id);
      const noun = job.status === "failed" ? "error" : "transcript";
      row.toggle.textContent = `${open ? "Hide" : "Show"} ${noun}`;
      const key = `${job.status}:${open}:${transcripts.has(job.id) ? transcripts.get(job.id).length : -1}`;
      if (key !== row.detailKey) {
        row.detailKey = key;
        row.detail.replaceChildren(...(open ? [buildDetail(job)] : []));
      }
      row.detail.hidden = !open;
    } else {
      row.detail.hidden = true;
    }
  }

  async function loadTranscript(jobId) {
    try {
      const response = await fetch(`api/jobs/${jobId}`, { cache: "no-store" });
      const job = await response.json();
      transcripts.set(jobId, job.transcript || "(empty transcript)");
    } catch (err) {
      transcripts.set(jobId, `Could not load transcript: ${err.message || err}`);
    }
    const row = rows.get(jobId);
    if (row) updateRow(row, latest.get(jobId));
  }

  function render(payload) {
    els.summary.textContent = L.summaryText(payload.stats, payload.model_ready);
    const jobs = L.sortJobs(payload.jobs);
    const seen = new Set();

    jobs.forEach((job) => {
      seen.add(job.id);
      latest.set(job.id, job);
      let row = rows.get(job.id);
      if (!row) {
        row = buildRow(job);
        rows.set(job.id, row);
        els.jobs.appendChild(row.li);
      }
      updateRow(row, job);
    });

    rows.forEach((row, id) => {
      if (!seen.has(id)) {
        row.li.remove();
        rows.delete(id);
        latest.delete(id);
        expanded.delete(id);
        transcripts.delete(id);
      }
    });

    // Re-append only when the order actually changed: moving a node re-inserts it, which would
    // undo the in-place updates above for scroll and focus.
    const wanted = jobs.map((job) => job.id).join(",");
    const actual = Array.from(els.jobs.children)
      .map((li) => {
        let found = "";
        rows.forEach((row, id) => {
          if (row.li === li) found = id;
        });
        return found;
      })
      .join(",");
    if (wanted !== actual) {
      jobs.forEach((job) => els.jobs.appendChild(rows.get(job.id).li));
    }

    els.empty.hidden = jobs.length > 0;
    schedule(jobs.some(L.isActive) ? POLL_ACTIVE_MS : POLL_IDLE_MS);
  }

  async function tick() {
    if (inFlight) return; // a slow response must not be clobbered by a later one
    inFlight = true;
    try {
      const response = await fetch("api/jobs", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json());
      showBanner("");
    } catch (err) {
      showBanner(`Cannot reach the service: ${err.message || err}`);
    } finally {
      inFlight = false;
    }
  }

  function schedule(ms) {
    const wanted = document.hidden ? POLL_HIDDEN_MS : ms;
    if (timer && timerMs === wanted) return;
    if (timer) clearInterval(timer);
    timerMs = wanted;
    timer = setInterval(tick, wanted);
  }

  function upload(file) {
    const row = node("div", "upload", `Uploading ${file.name}… 0%`);
    els.uploads.appendChild(row);
    const label = file.name.replace(/\.[^.]+$/, "");
    const query = `?filename=${encodeURIComponent(file.name)}&name=${encodeURIComponent(label)}`;
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

  function uploadAll(files) {
    Array.from(files || []).forEach(upload);
  }

  function wireUploads() {
    els.pick.addEventListener("click", () => els.file.click());
    els.file.addEventListener("change", () => {
      uploadAll(els.file.files);
      els.file.value = "";
    });
    // The drop zone is a tab stop, so it has to answer the keyboard too.
    els.dropzone.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        els.file.click();
      }
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
    els.dropzone.addEventListener("drop", (event) => uploadAll(event.dataTransfer.files));
  }

  document.addEventListener("visibilitychange", () => schedule(timerMs || POLL_ACTIVE_MS));
  wireUploads();
  tick();
  schedule(POLL_ACTIVE_MS);
})();
