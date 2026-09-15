# Remote Whisper Service (CPU-only, air-gapped) — Design

**Status:** Approved by user (via Q&A this session), ready for implementation plan.
**Date:** 2026-09-15

## Problem

Transcription in this vault currently runs on the user's own machine: `scripts/transcribe_meetings.py`
shells out to the vendored `vendor/whisper-cpp/whisper-cli.exe` against `ggml-tiny.bin` (~74MB). That
keeps a fresh clone self-contained, but `tiny` is the smallest, least accurate model there is, and
transcribing a long meeting pins the laptop's CPU for the duration with no visibility into progress —
the Obsidian captions button just sits there until it finishes or fails.

The user has a Kubernetes cluster in an air-gapped environment with a Harbor registry, and wants
transcription to move there, using **whisper-large-v3** for real accuracy (including Hebrew, which is
the vault's common meeting language). Because that cluster has **no GPUs**, a large-v3 transcription
takes tens of minutes, which makes queue and progress visibility a requirement rather than a nicety:
the user needs a web page showing what is queued and how far along it is, and the Obsidian plugin
needs to report the same progress instead of blocking silently.

## Goals

1. A container image running whisper-large-v3 transcription on **CPU only**, with the model baked in
   so the air-gapped cluster never has to fetch weights at runtime.
2. A Helm chart that deploys it against Harbor-hosted images, reachable from the user's workstation.
3. A web UI on the service showing the live queue: queued/running/done/failed jobs, per-job progress
   percentage, elapsed and estimated remaining time — auto-refreshing, no reload.
4. Browser upload: drag a `.wav`/`.mp3` onto the page to transcribe it, and read/copy/download the
   resulting transcript from the page.
5. The Obsidian `record-meeting` plugin transcribes via the cluster when configured, showing live
   progress, and writes the transcript into the meeting note exactly as it does today.
6. Backwards compatibility: with no service URL configured, everything behaves exactly as it does
   now (vendored whisper.cpp, local, offline).
7. All new work delivered as a **zip** that can be carried into the air-gapped environment, with
   scripts to build the image outside and push image + chart to Harbor inside.
8. The repo's existing rule holds: the vault's own Python and JS stay **stdlib-only** and the test
   suite runs on a fresh air-gapped clone with no `pip install` / `npm install`.

## Non-goals

- **No authentication.** The user explicitly chose an unauthenticated service reached over the
  air-gapped network via Ingress or NodePort. Anyone who can reach the host can submit jobs and read
  transcripts. This is a deliberate, documented decision, not an oversight — the values file and the
  docs both say so out loud.
- **No horizontal scaling.** `replicas: 1`, `strategy: Recreate`. A single CPU transcription
  saturates every core it is given, so a second concurrent job makes both slower; a shared queue
  backend (Redis/Postgres) would add images to Harbor and failure modes for throughput the user
  cannot use. Out of scope, stated as a limit.
- **No GPU support.** No CUDA base image, no device plugins, no `nvidia.com/gpu` resources.
- **No job cancel or retry** (user declined). A stuck job is dealt with by deleting the pod; a failed
  job is re-submitted by re-uploading.
- **No speaker diarization, no summarization.** Summarization stays where it is: the
  `gtd-summarize-meetings` skill in Claude Code. This service's job stops at a transcript.
- **No changes to the local dashboard** (`scripts/dashboard_server.py`). Its "transcribe pending"
  action keeps calling the same script, which means it inherits remote mode for free once the service
  URL is configured, but no queue/progress UI is added to it. Possible follow-up, not this spec.
- **The built image tar is not committed.** It is ~4GB and needs both Docker and internet to produce.
  The zip carries the scripts that build it; the user runs them.

## Design

### Architecture

One pod, one process, one worker:

```
  Obsidian plugin ─┐
                   ├─> scripts/transcribe_meetings.py --service-url ──┐
  local dashboard ─┘                                                  │
                                                                      ▼
  browser ───────────────────────────────> [ Ingress/NodePort ] ─> remote-whisper pod
                                                                   ├── ThreadingHTTPServer (stdlib)
                                                                   ├── worker thread  ─> faster-whisper
                                                                   │                     (large-v3 int8)
                                                                   └── /data PVC: audio/ + whisper.db
```

The HTTP server, the job store and the worker all live in one process. The model is loaded **once**
at startup and stays resident (loading CTranslate2 large-v3 costs ~10–30s, which is why per-job pods
were rejected). `/readyz` stays false until the model is loaded, so the startup probe holds traffic
off until it is genuinely ready.

**Engine choice:** faster-whisper (CTranslate2) with `int8` quantization. Typically 3–5× faster than
reference PyTorch Whisper on CPU, ~1.5GB of weights at int8, and — critically — its `transcribe()`
returns a generator of segments each carrying an `end` timestamp, which is what makes honest progress
reporting possible without patching the model.

**Dependency containment:** the app's own code is stdlib-only. faster-whisper is reached through a
narrow interface (see *Engine interface* below) that the test suite substitutes with a fake. So the
heavy dependency exists only inside the image, and every test in this repo still runs on a bare
air-gapped clone.

### Layout

```
services/remote-whisper/
  app/
    __init__.py
    jobstore.py     # SQLite-backed job state machine
    engine.py       # faster-whisper adapter + FakeEngine used by tests
    worker.py       # queue loop: claim -> transcribe -> record
    server.py       # ThreadingHTTPServer: API + static files
    __main__.py     # arg parsing / wiring / startup
    static/
      index.html
      app.js        # rendering + polling (vanilla, no build step)
      logic.js      # pure helpers (formatting, ETA, sorting) — node:test testable
      style.css
  tests/
    test_jobstore.py
    test_server.py
    test_worker.py
    test_logic.mjs
  Dockerfile
  requirements.txt  # faster-whisper pin — image only, never installed into the vault
deploy/helm/remote-whisper/
  Chart.yaml values.yaml .helmignore
  templates/{deployment,service,ingress,pvc,configmap,_helpers,NOTES.txt}.yaml
  templates/tests/  (helm test hook: curl /healthz)
scripts/
  package_remote_whisper.py   # builds the air-gap zip (stdlib zipfile)
  remote_whisper/
    build-image.sh            # connected machine: docker build + docker save
    push-to-harbor.sh         # air gap: docker load + tag + push + helm push (OCI)
    lint-chart.sh             # helm lint/template checks; skips cleanly when helm is absent
docs/gtd/remote-whisper.md
```

### Job model and state machine

A job is a row in SQLite (`/data/whisper.db`, WAL mode). States:

```
queued ──claim──> running ──success──> done
                     └─────failure──> failed
```

Columns: `id` (uuid4 hex), `name`, `filename`, `audio_path`, `bytes`, `duration_seconds`,
`language` (requested; null = auto), `detected_language`, `status`, `progress` (0.0–1.0),
`transcript`, `error`, `created_at`, `started_at`, `finished_at`. Timestamps are UTC ISO-8601.

Rules:
- Claiming is a single `UPDATE ... WHERE status='queued'` ordered by `created_at`, so FIFO is
  enforced by the database rather than by worker bookkeeping.
- **Crash recovery:** on startup, any row left in `running` is moved back to `queued` (progress reset
  to 0). A `Recreate` rollout therefore resumes work instead of losing it — the audio is on the PVC.
- **Retention:** a sweep on startup and hourly deletes jobs finished more than
  `retentionDays` ago (default 14) and unlinks their audio. `retentionDays: 0` disables.
- Progress writes are throttled to at most one per second per job, so a 40-minute transcription does
  not generate thousands of writes.

### Engine interface

```python
class Engine(Protocol):
    def load(self) -> None: ...                       # called once at startup
    def duration(self, path: Path) -> float | None: ...
    def transcribe(self, path: Path, language: str | None,
                   on_progress: Callable[[float], None]) -> Result: ...
    # Result: text, detected_language, duration
```

`FasterWhisperEngine` wraps `WhisperModel(model_path, device="cpu", compute_type=<configurable>)` and
calls `on_progress(min(segment.end / duration, 1.0))` as it consumes the segment generator.
`FakeEngine` (in the same module, used by tests and by `--fake-engine` for local UI work) emits
scripted progress and a canned transcript, with no dependency on faster-whisper at all. Decoding
defaults: `beam_size=1`, `vad_filter=True`, `condition_on_previous_text=False` — all overridable by
env, all chosen because they cut CPU time without materially hurting accuracy on meeting audio.

### HTTP API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/jobs` | Upload audio, enqueue. `multipart/form-data` (`file`, optional `name`, `language`) or raw body with `?filename=&name=&language=`. → `201 {job}` |
| `GET` | `/api/jobs` | Queue list, newest first, `?status=&limit=`. → `{jobs: [...], stats: {...}}` (transcripts omitted) |
| `GET` | `/api/jobs/{id}` | Full job incl. transcript. → `200 {job}` / `404` |
| `GET` | `/api/jobs/{id}/transcript` | `text/plain; charset=utf-8`, `Content-Disposition: attachment` |
| `POST` | `/v1/audio/transcriptions` | OpenAI-compatible **synchronous** shim: enqueue, wait, return `{"text": ...}`. Keeps today's `--remote-url` flag working unchanged |
| `GET` | `/healthz` | Process alive (liveness) |
| `GET` | `/readyz` | `200` only once the model is loaded (readiness + startup) |
| `GET` | `/` `/app.js` `/logic.js` `/style.css` | The UI |

Every job JSON carries derived fields the clients would otherwise each have to compute:
`elapsed_seconds`, `eta_seconds` (null unless running with progress > 0), `queue_position` (null
unless queued).

Uploads stream to `/data/audio/<job-id><ext>` in chunks — a 3-hour WAV is ~350MB and must never be
buffered whole in memory. `maxUploadBytes` (default 1GB, mirroring the local dashboard's existing
limit) is enforced from `Content-Length` and again while streaming. Rejected uploads clean up their
partial file.

### Web UI

One page, polling `GET /api/jobs` every 2s (5s when the tab is hidden):

- **Header stats:** queued / running / done / failed counts, and whether the model is loaded.
- **Drop zone:** drag-and-drop or file picker, with an optional name field; uploads via `fetch` with
  an `XMLHttpRequest`-style progress bar for the upload itself, distinct from the transcription bar.
- **Job list:** one row per job — name, status pill, duration, a progress bar with percentage, and
  elapsed/ETA. Running jobs first, then queued (with position), then finished.
- **Finished jobs expand** to show the transcript with its detected language, plus **Copy** and
  **Download .txt** buttons. Failed jobs expand to show the error.

Pure formatting/sorting/ETA logic lives in `logic.js` with no DOM access, tested with Node's built-in
`node:test` — the same split the local dashboard already uses. Styling is hand-written CSS with a
dark/light `prefers-color-scheme`; no framework, no build step, nothing to `npm install`.

### Image

Multi-stage `Dockerfile`:

1. **Stage 1 (`model`)** — installs `huggingface_hub` and downloads the CTranslate2 conversion of
   large-v3 (`Systran/faster-whisper-large-v3`) to `/models/faster-whisper-large-v3`, pinned by
   revision. This is the only stage that needs internet, and it runs on the connected build machine.
2. **Stage 2 (`runtime`)** — `python:3.12-slim`, `pip install -r requirements.txt`
   (`faster-whisper` pinned), app source copied in, model copied from stage 1, non-root `whisper`
   user (uid 10001), `EXPOSE 8080`, healthcheck on `/healthz`.

Configuration is env-only, so the chart can set all of it:
`WHISPER_MODEL_PATH`, `WHISPER_COMPUTE_TYPE` (default `int8`), `WHISPER_DATA_DIR`,
`WHISPER_PORT`, `WHISPER_THREADS` (also exported as `OMP_NUM_THREADS`), `WHISPER_BEAM_SIZE`,
`WHISPER_VAD`, `WHISPER_LANGUAGE`, `WHISPER_RETENTION_DAYS`, `WHISPER_MAX_UPLOAD_BYTES`.

`WHISPER_THREADS` defaults to the pod's CPU limit rather than the node's core count — otherwise
CTranslate2 spawns a thread per host core and thrashes against the cgroup quota. The chart computes
it from `resources.limits.cpu`.

### Helm chart

`deploy/helm/remote-whisper` — Deployment (replicas pinned to 1, `Recreate`), Service, optional
Ingress, optional NodePort, data PVC, optional model PVC override, ConfigMap for env.

Values that matter:

```yaml
image:
  repository: harbor.example.local/second-brain/remote-whisper   # placeholder, documented
  tag: ""            # defaults to .Chart.AppVersion
  pullPolicy: IfNotPresent
imagePullSecrets: []                # Harbor robot-account secret goes here
persistence:
  enabled: true
  size: 20Gi
  storageClass: ""
  accessMode: ReadWriteOnce
model:
  source: image                     # image | pvc
  pvc: { claimName: "", subPath: "", path: /models/faster-whisper-large-v3 }
whisper:
  computeType: int8
  threads: ""                       # "" = derive from resources.limits.cpu
  beamSize: 1
  vad: true
  language: ""                      # "" = auto-detect per recording
  retentionDays: 14
  maxUploadBytes: 1073741824
resources:
  requests: { cpu: "2", memory: 3Gi }
  limits:   { cpu: "4", memory: 6Gi }
service: { type: ClusterIP, port: 80, nodePort: null }
ingress: { enabled: false, className: "", host: whisper.example.local, tls: [], annotations: {} }
probes: { startup: { failureThreshold: 60, periodSeconds: 10 } }   # ~10 min for model load
podSecurityContext / securityContext / nodeSelector / tolerations / affinity / extraEnv / podAnnotations
```

Chart specifics worth stating because they are easy to get wrong:
- The **startup probe** is what tolerates the slow model load (default budget ~10 minutes); liveness
  and readiness use short periods and only take effect after it passes. Without this the pod
  CrashLoopBackOffs on a slow node.
- Ingress needs `nginx.ingress.kubernetes.io/proxy-body-size` (and read/send timeouts) for large
  uploads and the synchronous `/v1` shim; the chart sets sane defaults in `ingress.annotations`
  that the user can override or drop for a non-nginx controller.
- `NOTES.txt` prints the exact URL to open, derived from whichever access mode is enabled.
- A `helm test` hook pod curls `/healthz`.

### Client integration

**The plugin does not learn to write notes.** All note mutation stays in
`scripts/transcribe_meetings.py`, which is already tested; the plugin keeps shelling out to it. New
in the script:

- `--service-url URL` — job-API mode: `POST /api/jobs`, then poll `GET /api/jobs/{id}` every 2s,
  printing `PROGRESS <pct> <note-name>` lines to stdout as progress advances, then write the
  transcript into the note with the existing `apply_transcript()`. On failure, the existing
  `mark_failed()` records the reason in the note, as today.
- `--service-timeout SECONDS` (default 7200) — a CPU large-v3 run on a long meeting can legitimately
  take over an hour, so the existing 120s remote timeout is not reusable.
- Precedence: `--service-url` > `--remote-url` > local vendored whisper.cpp. Nothing about the local
  path changes; existing tests must keep passing untouched.

`.obsidian/plugins/record-meeting/`:
- A settings tab (`serviceUrl`, persisted via `loadData`/`saveData`) with an inline "Test connection"
  button that hits `/healthz`.
- `transcribePending()` passes `--service-url` when the setting is non-empty, and parses `PROGRESS`
  lines from the child process's stdout to update a single live `Notice` ("Transcribing… 42%").
- Empty setting → identical behaviour to today.
- A "Open transcription queue" command/ribbon action that opens the service URL in the browser.

### Air-gap bundle

`python scripts/package_remote_whisper.py [--out dist/]` produces
`dist/remote-whisper-bundle-<version>.zip` using stdlib `zipfile`, with deterministic ordering and
fixed timestamps so rebuilding an unchanged tree yields an identical zip. Contents:

```
remote-whisper-bundle-<version>/
  INSTALL.md              # step-by-step: build outside -> transfer -> load/push -> helm install
  MANIFEST.txt            # every file with its sha256
  service/                # services/remote-whisper/ (source, Dockerfile, requirements, tests)
  chart/                  # deploy/helm/remote-whisper/
  scripts/build-image.sh  # connected machine: docker build + docker save | gzip
  scripts/push-to-harbor.sh
  vault-changes/          # modified vault files at vault-relative paths:
    scripts/transcribe_meetings.py
    .obsidian/plugins/record-meeting/{main.js,lib.js,manifest.json}
    docs/gtd/{remote-whisper.md,meeting-recording.md}
    .claude/skills/gtd-transcribe-meeting/SKILL.md
```

`build-image.sh` (run where there is internet + Docker): `docker build` → `docker save` → gzip to
`remote-whisper-<version>-image.tar.gz`, then `helm package chart/`. Prints the sha256 of both.

`push-to-harbor.sh` (run inside the air gap, with `HARBOR=harbor.internal/project`):
`docker load` → `docker tag` → `docker push`, then `helm push remote-whisper-<v>.tgz oci://$HARBOR`,
then prints the `helm install` command with the right `--set image.repository=...`. Both scripts are
`set -euo pipefail`, take overrides via env vars, and check for their prerequisites up front with
clear errors.

The zip is small (source only, tens of KB) and **is** committed, so the user can pull it straight
from the repo. The image tar and packaged chart are build outputs; `dist/` is gitignored apart from
the bundle zip itself.

### Testing approach

Everything runs with no network and nothing installed beyond Python 3 and Node.

| Unit | How |
|---|---|
| `jobstore.py` | `unittest` against a temp-dir SQLite: FIFO claim order, state transitions, progress throttling, `running`→`queued` crash recovery, retention sweep (including `retentionDays: 0`), queue-position maths |
| `server.py` | Real `ThreadingHTTPServer` on port 0 + `urllib`: upload (multipart and raw), oversize rejection + partial-file cleanup, list/detail/404, transcript content-type and disposition, `/v1` shim end-to-end against `FakeEngine`, `/readyz` false before load |
| `worker.py` | `FakeEngine` with scripted progress: claim → progress writes → `done`; raising engine → `failed` with the message recorded; empty queue idles without spinning |
| `logic.js` | `node:test`: duration/percent formatting, ETA maths (including progress 0 → null), job sort order, byte formatting |
| `transcribe_meetings.py` | Extends the existing test file: `--service-url` happy path and failure path against a stub HTTP server, `PROGRESS` line emission, flag precedence, and the untouched local path still passing |
| `lib.js` (plugin) | Existing `node:test` style: the pure `PROGRESS`-line parser used by the Notice updater |
| Chart | `scripts/remote_whisper/lint-chart.sh`: `helm lint` + `helm template` across value permutations (ingress on/off, NodePort, model from PVC), grepping the rendered YAML for the things that matter (replicas 1, threads derived, probes present). **Skips with a clear message if `helm` is not installed**, so it never fails a machine without Helm |
| Bundle | `unittest` on `package_remote_whisper.py`: expected entries present, manifest hashes match, byte-identical rebuild |

## Open risks

1. **Throughput is the whole risk.** large-v3 int8 on 4 CPU cores is roughly 0.5–1.5× realtime, so a
   90-minute meeting can take over two hours and the queue is strictly serial. If that turns out too
   slow in practice, the mitigations in descending order of value are: raise `resources.limits.cpu`
   (the chart derives thread count from it, so this scales cleanly), or switch the model to
   `distil-large-v3` / `medium` via the model PVC override with no image rebuild. Both are documented
   in `docs/gtd/remote-whisper.md`; neither requires a code change.
2. **No auth on an unauthenticated network path.** Chosen deliberately. Meeting audio and transcripts
   are readable by anyone who can reach the Service/Ingress. Written plainly in the values file and
   the docs so the decision stays visible; adding a shared bearer token later is a contained change
   (one middleware check plus a plugin setting).
3. **`ReadWriteOnce` + `Recreate`** means a rollout has a gap where the old pod must fully terminate
   before the new one can attach the PVC. Acceptable for a single-user service; it is the reason
   `Recreate` is set rather than `RollingUpdate`, which would deadlock on the volume.
4. **Uploads over Ingress** are the most likely first-run failure (413 / timeout from controller
   defaults). The chart ships nginx annotations for it and `NOTES.txt` plus the troubleshooting
   section call it out for other controllers.
5. **Model provenance.** The image pulls `Systran/faster-whisper-large-v3` from Hugging Face at build
   time, pinned by revision, and `build-image.sh` prints digests. If the user's build machine cannot
   reach Hugging Face either, the documented fallback is to download the model directory manually and
   pass `--build-arg MODEL_DIR=...` to use a local copy.
6. **Whisper hallucination on silence** is a known large-v3 behaviour; `vad_filter=True` is on by
   default specifically to reduce it, which is why the default is `true` rather than `false`.
