// Reads, mixes and writes the advert's sounds as 16-bit PCM mono WAV.

const SAMPLE_RATE = 48000;
const PEAK_LIMIT = 0.89;
const PCM_FORMAT = 1;

/** Reads a PCM16 48000 Hz mono WAV into samples in -1..1, walking the chunk list for `fmt ` and `data`. */
export function parseWav(buffer, name) {
  if (buffer.length < 12 || buffer.toString("latin1", 0, 4) !== "RIFF" || buffer.toString("latin1", 8, 12) !== "WAVE") {
    throw new Error(`${name}: not a RIFF WAVE file`);
  }
  let format = null;
  let data = null;
  for (let offset = 12; offset + 8 <= buffer.length; ) {
    const id = buffer.toString("latin1", offset, offset + 4);
    const size = buffer.readUInt32LE(offset + 4);
    const body = offset + 8;
    if (id === "fmt ") {
      format = {
        audioFormat: buffer.readUInt16LE(body),
        channels: buffer.readUInt16LE(body + 2),
        sampleRate: buffer.readUInt32LE(body + 4),
        bitsPerSample: buffer.readUInt16LE(body + 14),
      };
    } else if (id === "data") {
      data = buffer.subarray(body, Math.min(body + size, buffer.length));
    }
    offset = body + size + (size % 2);
  }
  if (!format || !data) throw new Error(`${name}: missing fmt or data chunk`);
  if (format.audioFormat !== PCM_FORMAT || format.bitsPerSample !== 16) {
    throw new Error(`${name}: expected 16-bit PCM, got format ${format.audioFormat} at ${format.bitsPerSample} bits`);
  }
  if (format.sampleRate !== SAMPLE_RATE || format.channels !== 1) {
    throw new Error(`${name}: ${format.sampleRate} Hz ${format.channels} channels, expected 48000 Hz mono`);
  }
  const samples = new Float32Array(Math.floor(data.length / 2));
  for (let i = 0; i < samples.length; i++) samples[i] = data.readInt16LE(i * 2) / 32768;
  return samples;
}

/** Adds each cue's sound at round(t * sampleRate) times its gain, then scales the mix down if its peak passes 0.89. */
export function mixCues(cues, sounds, { sampleRate, duration }) {
  const out = new Float32Array(Math.round(duration * sampleRate));
  for (const { t, sound, gain } of cues) {
    const samples = sounds[sound];
    if (!samples) throw new Error(`unknown sound "${sound}"`);
    const start = Math.round(t * sampleRate);
    const end = Math.min(out.length, start + samples.length);
    for (let i = Math.max(0, start); i < end; i++) out[i] += samples[i - start] * gain;
  }
  const peak = out.reduce((max, value) => Math.max(max, Math.abs(value)), 0);
  if (peak > PEAK_LIMIT) {
    const scale = PEAK_LIMIT / peak;
    for (let i = 0; i < out.length; i++) out[i] *= scale;
  }
  return out;
}

/** Writes samples in -1..1 as a PCM16 mono WAV with the plain 44-byte header. */
export function encodeWav(samples, sampleRate) {
  const dataSize = samples.length * 2;
  const buffer = Buffer.alloc(44 + dataSize);
  buffer.write("RIFF", 0, "latin1");
  buffer.writeUInt32LE(36 + dataSize, 4);
  buffer.write("WAVE", 8, "latin1");
  buffer.write("fmt ", 12, "latin1");
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(PCM_FORMAT, 20);
  buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate * 2, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write("data", 36, "latin1");
  buffer.writeUInt32LE(dataSize, 40);
  samples.forEach((value, i) => {
    const clamped = Math.max(-1, Math.min(1, value));
    buffer.writeInt16LE(Math.round(clamped * 32767), 44 + i * 2);
  });
  return buffer;
}
