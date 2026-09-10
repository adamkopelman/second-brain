"use strict";
const { Plugin, Notice, setIcon } = require("obsidian");
const { spawn } = require("child_process");
const path = require("path");
const { timestampSlug, buildWavBuffer, meetingNoteContent } = require("./lib.js");

const SAMPLE_RATE = 16000;
const RECORDINGS_DIR = "Meetings/recordings";
const PYTHON_CANDIDATES = ["python", "python3", "py"];

module.exports = class RecordMeetingPlugin extends Plugin {
  async onload() {
    this.recording = null; // { stream, audioCtx, source, processor, chunks, startedAt }

    this.ribbonEl = this.addRibbonIcon("mic", "Start/stop meeting recording", () => {
      this.toggleRecording();
    });

    this.addCommand({
      id: "toggle-recording",
      name: "Toggle meeting recording",
      callback: () => this.toggleRecording(),
    });

    this.addRibbonIcon("captions", "Transcribe pending meeting recordings", () => {
      this.transcribePending();
    });

    this.addCommand({
      id: "transcribe-pending",
      name: "Transcribe pending meeting recordings",
      callback: () => this.transcribePending(),
    });
  }

  onunload() {
    if (this.recording) this.stopRecording().catch(() => {});
  }

  async toggleRecording() {
    if (this.recording) await this.stopRecording();
    else await this.startRecording();
  }

  async startRecording() {
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: SAMPLE_RATE, echoCancellation: true, noiseSuppression: true },
      });
    } catch (e) {
      new Notice(`Could not access microphone: ${e.message || e}`);
      return;
    }

    const audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
    const source = audioCtx.createMediaStreamSource(stream);
    const processor = audioCtx.createScriptProcessor(4096, 1, 1);
    const chunks = [];

    processor.onaudioprocess = (event) => {
      chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };

    source.connect(processor);
    processor.connect(audioCtx.destination);

    this.recording = { stream, audioCtx, source, processor, chunks, startedAt: new Date() };
    setIcon(this.ribbonEl, "circle-stop");
    new Notice("Recording meeting…");
  }

  async stopRecording() {
    const rec = this.recording;
    this.recording = null;
    if (!rec) return;

    rec.processor.disconnect();
    rec.source.disconnect();
    rec.stream.getTracks().forEach((t) => t.stop());
    await rec.audioCtx.close();
    setIcon(this.ribbonEl, "mic");

    if (rec.chunks.length === 0) {
      new Notice("No audio captured; discarding.");
      return;
    }

    const wavBuffer = buildWavBuffer(rec.chunks, SAMPLE_RATE);
    const slug = timestampSlug(rec.startedAt);
    const recordingRelPath = `${RECORDINGS_DIR}/${slug}.wav`;

    await this.ensureFolder(RECORDINGS_DIR);
    await this.app.vault.adapter.writeBinary(recordingRelPath, wavBuffer);

    const dateStr = `${rec.startedAt.getFullYear()}-${String(rec.startedAt.getMonth() + 1).padStart(2, "0")}-${String(rec.startedAt.getDate()).padStart(2, "0")}`;
    const noteContent = meetingNoteContent({ dateStr, recordingRelPath });
    const notePath = `Meetings/${slug} Meeting.md`;
    const noteFile = await this.app.vault.create(notePath, noteContent);

    new Notice(`Saved recording + meeting note: ${notePath}`);
    await this.app.workspace.getLeaf(true).openFile(noteFile);
  }

  async ensureFolder(folderPath) {
    if (!(await this.app.vault.adapter.exists(folderPath))) {
      await this.app.vault.createFolder(folderPath);
    }
  }

  async transcribePending() {
    const basePath = this.getBasePath();
    if (!basePath) {
      new Notice("Transcription requires the desktop app.");
      return;
    }
    const scriptPath = path.join(basePath, "scripts", "transcribe_meetings.py");

    new Notice("Transcribing pending meeting recordings…");
    try {
      const output = await this.runPython(scriptPath, [basePath]);
      const lastLine = output.trim().split("\n").filter(Boolean).pop();
      new Notice(lastLine || "No pending meeting recordings.");
      console.log("[record-meeting] transcribe output:\n" + output);
    } catch (e) {
      new Notice(`Transcription failed: ${e.message || e}`);
      console.error("[record-meeting] transcribe error", e);
    }
  }

  getBasePath() {
    const adapter = this.app.vault.adapter;
    return typeof adapter.getBasePath === "function" ? adapter.getBasePath() : null;
  }

  runPython(scriptPath, args) {
    return new Promise((resolve, reject) => {
      const tryNext = (i) => {
        if (i >= PYTHON_CANDIDATES.length) {
          reject(new Error("No Python interpreter found (tried python, python3, py)"));
          return;
        }
        const bin = PYTHON_CANDIDATES[i];
        const child = spawn(bin, [scriptPath, ...args], { windowsHide: true });
        let stdout = "";
        let stderr = "";
        child.stdout.on("data", (d) => (stdout += d.toString()));
        child.stderr.on("data", (d) => (stderr += d.toString()));
        child.on("error", () => tryNext(i + 1));
        child.on("close", (code) => {
          if (code === 0) resolve(stdout);
          else reject(new Error(stderr.trim() || `exit code ${code}`));
        });
      };
      tryNext(0);
    });
  }
};
