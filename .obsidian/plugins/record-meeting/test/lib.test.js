"use strict";
const assert = require("assert");
const { timestampSlug, buildWavBuffer, meetingNoteContent } = require("../lib.js");

function test(name, fn) {
  try {
    fn();
    console.log(`ok - ${name}`);
  } catch (e) {
    console.error(`FAIL - ${name}`);
    console.error(e);
    process.exitCode = 1;
  }
}

test("timestampSlug formats a zero-padded local timestamp", () => {
  const d = new Date(2026, 8, 9, 7, 5, 3); // month is 0-indexed -> September
  assert.strictEqual(timestampSlug(d), "2026-09-09_07-05-03");
});

test("buildWavBuffer writes a valid RIFF/WAVE header", () => {
  const chunk = new Float32Array([0, 0.5, -0.5, 1, -1]);
  const buf = buildWavBuffer([chunk], 16000);
  const view = new DataView(buf);
  const str = (o, n) =>
    Array.from({ length: n }, (_, i) => String.fromCharCode(view.getUint8(o + i))).join("");
  assert.strictEqual(str(0, 4), "RIFF");
  assert.strictEqual(str(8, 4), "WAVE");
  assert.strictEqual(str(12, 4), "fmt ");
  assert.strictEqual(view.getUint16(22, true), 1); // mono
  assert.strictEqual(view.getUint32(24, true), 16000); // sample rate
  assert.strictEqual(view.getUint16(34, true), 16); // bits per sample
  assert.strictEqual(str(36, 4), "data");
  assert.strictEqual(view.getUint32(40, true), chunk.length * 2);
  assert.strictEqual(buf.byteLength, 44 + chunk.length * 2);
});

test("buildWavBuffer clamps out-of-range samples", () => {
  const buf = buildWavBuffer([new Float32Array([2, -2])], 16000);
  const view = new DataView(buf);
  assert.strictEqual(view.getInt16(44, true), 0x7fff);
  assert.strictEqual(view.getInt16(46, true), -0x8000);
});

test("buildWavBuffer concatenates multiple chunks in order", () => {
  const buf = buildWavBuffer([new Float32Array([0.1]), new Float32Array([0.2, 0.3])], 16000);
  assert.strictEqual(buf.byteLength, 44 + 3 * 2);
});

test("meetingNoteContent embeds the recording link, pending status, and both headings", () => {
  const content = meetingNoteContent({
    dateStr: "2026-09-10",
    recordingRelPath: "Meetings/recordings/x.wav",
  });
  assert.ok(content.includes('recording: "[[Meetings/recordings/x.wav]]"'));
  assert.ok(content.includes("transcription_status: pending"));
  assert.ok(content.includes("## Transcript"));
  assert.ok(content.includes("## Action items"));
});

if (process.exitCode) {
  process.exit(process.exitCode);
}
console.log("All lib.js tests passed.");
