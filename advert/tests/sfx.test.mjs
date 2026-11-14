import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { parseWav } from "../src/mix.mjs";
import { SYNTHS } from "../src/sfx-synth.mjs";

const LIMITS = { pop: 0.15, whoosh: 0.35, swap: 0.10, chime: 0.60, tick: 0.04 };

test("each made sound is short, audible, unclipped and repeatable", () => {
  for (const [name, seconds] of Object.entries(LIMITS)) {
    const samples = SYNTHS[name]();
    const peak = Math.max(...samples.map(Math.abs));
    assert.ok(samples.length > 0 && samples.length <= seconds * 48000, name);
    assert.ok(peak > 0.2 && peak <= 0.9, `${name} peak ${peak}`);
    assert.deepEqual(SYNTHS[name](), samples, name);
  }
});

test("the recorded key clicks are 48000 Hz mono and short", async () => {
  for (const name of ["key-1", "key-2", "key-3", "key-4", "key-5", "key-6", "space"]) {
    const samples = parseWav(await readFile(new URL(`../sfx/${name}.wav`, import.meta.url)), name);
    assert.ok(samples.length > 0 && samples.length <= 0.25 * 48000, name);
  }
});

test("each recorded click starts on its click and is evenly loud", async () => {
  for (const name of ["key-1", "key-2", "key-3", "key-4", "key-5", "key-6", "space"]) {
    const samples = parseWav(await readFile(new URL(`../sfx/${name}.wav`, import.meta.url)), name);
    const peak = samples.reduce((max, value) => Math.max(max, Math.abs(value)), 0);
    const onset = samples.findIndex((value) => Math.abs(value) >= peak * 0.1);
    assert.ok(onset >= 0 && onset <= 144, `${name} starts at sample ${onset}`);
    assert.ok(peak >= 0.6 && peak <= 0.9, `${name} peak ${peak}`);
  }
});
