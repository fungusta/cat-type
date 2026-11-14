import test from "node:test";
import assert from "node:assert/strict";
import { mixCues, parseWav, encodeWav } from "../src/mix.mjs";

const sound = Float32Array.from([0.5, 0.25, 0.125]);

test("places a sound at round(t * sampleRate)", () => {
  const out = mixCues([{ t: 10 / 48000, sound: "a", gain: 1 }], { a: sound }, { sampleRate: 48000, duration: 1 });
  assert.equal(out.length, 48000);
  assert.deepEqual([...out.slice(9, 14)], [0, 0.5, 0.25, 0.125, 0]);
});

test("applies gain and sums overlaps", () => {
  const out = mixCues([{ t: 0, sound: "a", gain: 0.5 }, { t: 1 / 48000, sound: "a", gain: 0.5 }], { a: sound }, { sampleRate: 48000, duration: 1 });
  assert.deepEqual([...out.slice(0, 3)], [0.25, 0.375, 0.1875]);
});

test("keeps the peak at or under 0.89", () => {
  const loud = Float32Array.from([1]);
  const out = mixCues([{ t: 0, sound: "a", gain: 1 }, { t: 0, sound: "a", gain: 1 }], { a: loud }, { sampleRate: 48000, duration: 1 });
  assert.ok(Math.abs(out[0] - 0.89) < 1e-6);
});

test("drops samples that would run past the end", () => {
  const out = mixCues([{ t: 1 - 1 / 48000, sound: "a", gain: 1 }], { a: sound }, { sampleRate: 48000, duration: 1 });
  assert.equal(out.length, 48000);
  assert.equal(out[47999], 0.5);
});

test("names an unknown sound", () => {
  assert.throws(() => mixCues([{ t: 0, sound: "nope", gain: 1 }], {}, { sampleRate: 48000, duration: 1 }), /nope/);
});

test("a WAV survives encode then parse", () => {
  const back = parseWav(encodeWav(sound, 48000), "round-trip");
  assert.ok([...back].every((value, i) => Math.abs(value - sound[i]) < 1 / 32000));
});

test("rejects a file that is not 48000 Hz mono", () => {
  assert.throws(() => parseWav(encodeWav(sound, 44100), "old.wav"), /old\.wav.*expected 48000 Hz mono/);
});

test("skips chunks it does not need", () => {
  const plain = encodeWav(sound, 48000);
  const junk = Buffer.from("LIST\x04\x00\x00\x00abcd", "latin1");
  const withJunk = Buffer.concat([plain.subarray(0, 36), junk, plain.subarray(36)]);
  withJunk.writeUInt32LE(withJunk.length - 8, 4);
  assert.equal(parseWav(withJunk, "junk").length, 3);
});
