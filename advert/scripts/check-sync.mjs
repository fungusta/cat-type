// Prints the first time after <after-seconds> at which a 48000 Hz mono PCM16 WAV
// gets louder than 0.05, so a rendered soundtrack can be checked against the paws.
// Usage: node scripts/check-sync.mjs <wav> <after-seconds>

import { readFileSync } from "node:fs";
import { parseWav } from "../src/mix.mjs";

const SAMPLE_RATE = 48000;
const THRESHOLD = 0.05;

const [wavPath, afterArg] = process.argv.slice(2);
const after = Number(afterArg);
if (!wavPath || afterArg === undefined || !Number.isFinite(after) || after < 0) {
  console.error("usage: node scripts/check-sync.mjs <wav> <after-seconds>");
  process.exit(2);
}

let samples;
try {
  samples = parseWav(readFileSync(wavPath), wavPath);
} catch (error) {
  console.error(error.message);
  process.exit(1);
}

const first = Math.floor(after * SAMPLE_RATE) + 1;
for (let i = first; i < samples.length; i++) {
  if (Math.abs(samples[i]) > THRESHOLD) {
    console.log((i / SAMPLE_RATE).toFixed(3));
    process.exit(0);
  }
}
console.error(`${wavPath}: no sample louder than ${THRESHOLD} after ${after} s`);
process.exit(1);
