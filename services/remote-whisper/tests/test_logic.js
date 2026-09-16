"use strict";
const test = require("node:test");
const assert = require("node:assert");
const L = require("../app/static/logic.js");

test("formatDuration renders human units and handles nulls", () => {
  assert.equal(L.formatDuration(0), "0s");
  assert.equal(L.formatDuration(45), "45s");
  assert.equal(L.formatDuration(95), "1m 35s");
  assert.equal(L.formatDuration(3725), "1h 2m");
  assert.equal(L.formatDuration(null), "—");
  assert.equal(L.formatDuration(undefined), "—");
});

test("formatBytes uses binary units", () => {
  assert.equal(L.formatBytes(0), "0 B");
  assert.equal(L.formatBytes(1023), "1023 B");
  assert.equal(L.formatBytes(1024), "1.0 KB");
  assert.equal(L.formatBytes(5 * 1024 * 1024), "5.0 MB");
  assert.equal(L.formatBytes(null), "—");
});

test("percentText rounds and clamps", () => {
  assert.equal(L.percentText(0), "0%");
  assert.equal(L.percentText(0.4213), "42%");
  assert.equal(L.percentText(1), "100%");
  assert.equal(L.percentText(1.5), "100%");
  assert.equal(L.percentText(null), "0%");
});

test("statusLabel is human and covers every status", () => {
  assert.equal(L.statusLabel({ status: "queued" }), "Queued");
  assert.equal(L.statusLabel({ status: "running" }), "Transcribing");
  assert.equal(L.statusLabel({ status: "done" }), "Done");
  assert.equal(L.statusLabel({ status: "failed" }), "Failed");
});

test("metaText explains what each status is waiting on", () => {
  assert.equal(
    L.metaText({ status: "queued", queue_position: 3, bytes: 2048 }),
    "3rd in queue · 2.0 KB"
  );
  assert.equal(L.metaText({ status: "queued", queue_position: 1, bytes: 1024 }), "Next up · 1.0 KB");
  assert.equal(
    L.metaText({ status: "running", progress: 0.5, elapsed_seconds: 60, eta_seconds: 60 }),
    "50% · 1m 0s elapsed · ~1m 0s left"
  );
  assert.equal(
    L.metaText({ status: "running", progress: 0, elapsed_seconds: 5, eta_seconds: null }),
    "0% · 5s elapsed · estimating…"
  );
  assert.equal(
    L.metaText({ status: "done", elapsed_seconds: 720, duration_seconds: 1800,
                 detected_language: "he" }),
    "Took 12m 0s for 30m 0s of audio · he"
  );
  assert.equal(L.metaText({ status: "failed", error: "boom" }), "boom");
  assert.equal(L.metaText({ status: "failed", error: null }), "Failed");
});

test("sortJobs puts running first, then the queue in order, then finished newest-first", () => {
  const jobs = [
    { id: "d", status: "done", created_at: "2026-09-15T09:00:00+00:00" },
    { id: "q2", status: "queued", queue_position: 2, created_at: "2026-09-15T09:05:00+00:00" },
    { id: "f", status: "failed", created_at: "2026-09-15T09:02:00+00:00" },
    { id: "r", status: "running", created_at: "2026-09-15T09:04:00+00:00" },
    { id: "q1", status: "queued", queue_position: 1, created_at: "2026-09-15T09:03:00+00:00" },
  ];
  assert.deepEqual(L.sortJobs(jobs).map((j) => j.id), ["r", "q1", "q2", "f", "d"]);
});

test("sortJobs does not mutate its input", () => {
  const jobs = [{ id: "a", status: "done", created_at: "x" }, { id: "b", status: "running" }];
  L.sortJobs(jobs);
  assert.deepEqual(jobs.map((j) => j.id), ["a", "b"]);
});

test("summaryText reports the queue and a loading model", () => {
  assert.equal(
    L.summaryText({ queued: 2, running: 1, done: 5, failed: 1 }, true),
    "1 transcribing · 2 queued · 5 done · 1 failed"
  );
  assert.equal(
    L.summaryText({ queued: 0, running: 0, done: 0, failed: 0 }, false),
    "Loading the model — jobs will start once it is ready"
  );
});

test("isActive marks jobs the page should keep polling for", () => {
  assert.equal(L.isActive({ status: "running" }), true);
  assert.equal(L.isActive({ status: "queued" }), true);
  assert.equal(L.isActive({ status: "done" }), false);
});
