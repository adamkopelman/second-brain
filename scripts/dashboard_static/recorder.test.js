// scripts/dashboard_static/recorder.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const R = require("./recorder.js");

test("toPcm16 joins chunks and scales/clips floats to 16-bit integers", () => {
  const out = R.toPcm16([new Float32Array([0, 1, -1]), new Float32Array([0.5, 2, -2])]);
  assert.ok(out instanceof Int16Array);
  assert.deepEqual(Array.from(out), [0, 32767, -32768, 16383, 32767, -32768]);
});
