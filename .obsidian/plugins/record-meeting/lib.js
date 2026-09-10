// lib.js — pure helpers for the record-meeting plugin.
// Deliberately zero Obsidian/Electron dependencies so this can be tested with plain `node`.
"use strict";

function pad(n) {
  return String(n).padStart(2, "0");
}

function timestampSlug(date) {
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}_` +
    `${pad(date.getHours())}-${pad(date.getMinutes())}-${pad(date.getSeconds())}`
  );
}

// Encode mono Float32 PCM chunks (as produced by Web Audio) into a 16-bit PCM WAV ArrayBuffer.
// whisper.cpp decodes wav/mp3/flac/ogg natively, so no external encoder is needed.
function buildWavBuffer(float32Chunks, sampleRate) {
  let total = 0;
  for (const c of float32Chunks) total += c.length;

  const buffer = new ArrayBuffer(44 + total * 2);
  const view = new DataView(buffer);

  const writeString = (offset, str) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + total * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true); // PCM fmt chunk size
  view.setUint16(20, 1, true); // audio format = PCM
  view.setUint16(22, 1, true); // channels = mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate (mono, 16-bit)
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeString(36, "data");
  view.setUint32(40, total * 2, true);

  let offset = 44;
  for (const chunk of float32Chunks) {
    for (let i = 0; i < chunk.length; i++) {
      const s = Math.max(-1, Math.min(1, chunk[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      offset += 2;
    }
  }
  return buffer;
}

function meetingNoteContent({ dateStr, recordingRelPath }) {
  return (
    "---\n" +
    "type: meeting\n" +
    `date: ${dateStr}\n` +
    "attendees: \n" +
    `recording: "[[${recordingRelPath}]]"\n` +
    "transcription_status: pending\n" +
    "---\n\n" +
    `# Meeting ${dateStr}\n\n` +
    `**Date:** ${dateStr}\n` +
    "**Attendees:** \n\n" +
    "## Notes\n\n" +
    "## Decisions\n\n" +
    "## Transcript\n\n" +
    "## Action items\n- [ ]  #next\n"
  );
}

module.exports = { timestampSlug, buildWavBuffer, meetingNoteContent };
