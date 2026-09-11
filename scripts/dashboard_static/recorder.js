// scripts/dashboard_static/recorder.js
// Microphone capture for "Record a meeting": 16 kHz mono via Web Audio — the same approach as the
// record-meeting Obsidian plugin — handed back as 16-bit PCM; the server writes the WAV.
(function (root) {
  var SAMPLE_RATE = 16000;

  // Float32 chunks in [-1, 1] → one Int16Array (little-endian on every platform browsers run on).
  function toPcm16(chunks) {
    var total = 0;
    chunks.forEach(function (c) { total += c.length; });
    var out = new Int16Array(total);
    var o = 0;
    chunks.forEach(function (c) {
      for (var i = 0; i < c.length; i++) {
        var s = Math.max(-1, Math.min(1, c[i]));
        out[o++] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
    });
    return out;
  }

  function start() {
    return navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, sampleRate: SAMPLE_RATE, echoCancellation: true, noiseSuppression: true },
    }).then(function (stream) {
      var ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
      var source = ctx.createMediaStreamSource(stream);
      var processor = ctx.createScriptProcessor(4096, 1, 1);
      var chunks = [];
      processor.onaudioprocess = function (ev) {
        chunks.push(new Float32Array(ev.inputBuffer.getChannelData(0)));
      };
      source.connect(processor);
      processor.connect(ctx.destination);
      return {
        startedAt: new Date(),
        stop: function () {
          processor.disconnect();
          source.disconnect();
          stream.getTracks().forEach(function (t) { t.stop(); });
          return ctx.close().then(function () { return toPcm16(chunks); });
        },
      };
    });
  }

  var api = { SAMPLE_RATE: SAMPLE_RATE, toPcm16: toPcm16, start: start };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.MeetingRecorder = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
