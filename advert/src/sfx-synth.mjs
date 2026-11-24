// The advert's five UI sounds, made from sines and seeded noise so every render is identical.

const SAMPLE_RATE = 48000;

/** A small seeded noise generator (mulberry32) giving values in -1..1. */
function noise(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return (((t ^ (t >>> 14)) >>> 0) / 4294967296) * 2 - 1;
  };
}

/** Fills `seconds` of samples from `sampleAt(time, index)` and scales the result to `peak`. */
function render(seconds, peak, sampleAt) {
  const samples = new Float32Array(Math.floor(seconds * SAMPLE_RATE));
  for (let i = 0; i < samples.length; i++) samples[i] = sampleAt(i / SAMPLE_RATE, i);
  const loudest = samples.reduce((max, value) => Math.max(max, Math.abs(value)), 0);
  for (let i = 0; i < samples.length; i++) samples[i] *= peak / loudest;
  return samples;
}

/** Attack-then-exponential-decay envelope. */
const envelope = (time, attack, decay) => Math.min(1, time / attack) * Math.exp(-Math.max(0, time - attack) / decay);

/** A sine whose pitch glides exponentially from `from` to `to` Hz over `seconds`; returns phase at each time. */
function glide(from, to, seconds) {
  const ratio = Math.log(to / from) / seconds;
  return (time) => (2 * Math.PI * from * (Math.exp(ratio * time) - 1)) / ratio;
}

function pop() {
  const SECONDS = 0.12, FROM_HZ = 900, TO_HZ = 320, ATTACK = 0.003, DECAY = 0.03, PEAK = 0.7;
  const phase = glide(FROM_HZ, TO_HZ, SECONDS);
  return render(SECONDS, PEAK, (time) => Math.sin(phase(time)) * envelope(time, ATTACK, DECAY));
}

function swap() {
  const SECONDS = 0.08, FROM_HZ = 1500, TO_HZ = 750, ATTACK = 0.002, DECAY = 0.018, PEAK = 0.6;
  const phase = glide(FROM_HZ, TO_HZ, SECONDS);
  return render(SECONDS, PEAK, (time) => Math.sin(phase(time)) * envelope(time, ATTACK, DECAY));
}

function whoosh() {
  // Noise through a one-pole low-pass whose cutoff rises and falls with a swelling half-sine envelope.
  const SECONDS = 0.32, LOW_HZ = 300, HIGH_HZ = 2400, SEED = 7, PEAK = 0.45;
  const next = noise(SEED);
  let filtered = 0;
  return render(SECONDS, PEAK, (time) => {
    const swell = Math.sin((Math.PI * time) / SECONDS) ** 2;
    const cutoff = LOW_HZ + (HIGH_HZ - LOW_HZ) * swell;
    filtered += (1 - Math.exp((-2 * Math.PI * cutoff) / SAMPLE_RATE)) * (next() - filtered);
    return filtered * swell;
  });
}

function chime() {
  // Two soft sine partials, a fifth apart; the upper one fades faster.
  const SECONDS = 0.55, LOW_HZ = 1046.5, HIGH_HZ = 1568, ATTACK = 0.006, LOW_DECAY = 0.16, HIGH_DECAY = 0.09, PEAK = 0.5;
  return render(SECONDS, PEAK, (time) =>
    Math.sin(2 * Math.PI * LOW_HZ * time) * envelope(time, ATTACK, LOW_DECAY) +
    0.6 * Math.sin(2 * Math.PI * HIGH_HZ * time) * envelope(time, ATTACK, HIGH_DECAY));
}

function tick() {
  // A tiny burst of seeded noise plus a high sine, gone in a few milliseconds.
  const SECONDS = 0.03, TONE_HZ = 3200, DECAY = 0.003, SEED = 11, PEAK = 0.5;
  const next = noise(SEED);
  return render(SECONDS, PEAK, (time) => (0.6 * next() + 0.4 * Math.sin(2 * Math.PI * TONE_HZ * time)) * Math.exp(-time / DECAY));
}

export const SYNTHS = { pop, whoosh, swap, chime, tick };
