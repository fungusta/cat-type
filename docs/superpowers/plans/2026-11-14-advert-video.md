# Cat Type Advert Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render a 27-second, 1920 × 1080, 60 fps MP4 advert in which the real Cat Type cat pops up, types to audible key clicks, changes outfits, and shows three selling points as on-screen words.

**Architecture:** One pure module (`timeline.mjs`) answers "what is on screen and what sounds at time t". A browser script maps that state onto the DOM every frame, driven by a paused GSAP timeline that HyperFrames seeks. A build script assembles a self-contained HyperFrames project (bundled script, copied artwork, one pre-mixed soundtrack WAV) in `advert/build/`, and HyperFrames renders it to MP4.

**Tech Stack:** Node 26 (`node --test`), HyperFrames CLI 0.9.45, GSAP 3, esbuild, `@fontsource/nunito`, FFmpeg (Homebrew).

**Spec:** `docs/superpowers/specs/2026-11-14-advert-video-design.md`

## Global Constraints

- Output: 1920 × 1080, 60 fps, 27 seconds, MP4 with sound, at `advert/out/cat-type-advert.mp4`.
- Colours: background `#fff9f3`, ink `#302a33`, butter `#f2d66b`. Font: Nunito 800 for words, 700 for small labels, loaded from local files.
- On-screen words, exactly: `Customise it.` / `Unlock new outfits.` / `Track your productivity.` / `Cat Type` / `Get it for Windows or Mac` / `fungusta.github.io/cat-type`. Typed sentence: `Brighten up your day, one key at a time.`
- Only real artwork from `assets/vector-cats` and `assets/accessories`, dressed by `site/js/cat.js` `renderCat`. No accessory marked `hidden=True` in `cat_accessories.py` may appear.
- Nothing in the frame may depend on the wall clock, `Math.random()`, `requestAnimationFrame`, `setTimeout`, CSS transitions, or CSS keyframe animations. Every visible property is set from the frame time.
- No changes to the app, to `site/`, or to CI. Everything new lives in `advert/` plus the two docs.
- `advert/build/`, `advert/out/`, `advert/node_modules/` are not committed.
- Work on a new branch `advert-video`. Stage files by path; never `git add -A` (the untracked `assets/shirt-cats/` is not part of this work).
- Two things need Peter's go-ahead before they happen: `brew install ffmpeg`, and downloading the key-click sound pack.
- All commands below run from `advert/` unless they start with `git`.

## Review Focus

1. **Frames requested out of order.** The renderer may ask for frame 1200 and then frame 180. Frame 180 must look the same as if asked first. Pinned by `frameState is a pure function of time` (Task 2) and by `applyFrame` setting every property unconditionally (Task 5 snapshot check).
2. **A sound that lands off its paw tap.** Pinned by `every press has a sound cue at the same time` (Task 2) and `places a sound at round(t * sampleRate)` (Task 3).
3. **Many clicks overlapping and distorting.** Pinned by `keeps the peak at or under 0.89` (Task 3).
4. **A wrong or secret accessory id.** A typo must stop the build with the id in the message, not render a bare cat. Pinned by the three `assertPublishable` tests (Task 4).
5. **A sound file in the wrong format** (stereo, 44.1 kHz). Pinned by `rejects a file that is not 48000 Hz mono` (Task 3).
6. **Nunito not loaded, so words render in a fallback font.** No unit test can see this; Task 5 Step 6 checks it in a snapshot.

---

### Task 1: Scaffold and prove the tool

Proves three things the rest of the plan relies on, with a throwaway composition: HyperFrames re-applies script-driven state when it seeks, it waits for asynchronous setup, and it mixes an `<audio>` clip into the MP4.

**Files:**
- Create: `advert/package.json`, `advert/.gitignore`, `advert/README.md`
- Create and delete within this task (never committed): `advert/spike/index.html`, `advert/spike/gsap.min.js`, `advert/spike/beep.wav`

**Interfaces:**
- Produces npm scripts: `test` → `node --test tests/`; `build` → `node scripts/build.mjs`; `snap` → `hyperframes snapshot build --at` (used as `npm run snap -- 0.5,1.5`); `render` → `hyperframes render build -o out/cat-type-advert.mp4 --fps 60 --quality high`. Dev dependencies pinned: `hyperframes@0.9.45`, `gsap@^3`, `esbuild`, `@fontsource/nunito`.
- Produces: the frame-driver pattern recorded in `advert/README.md` (setter or `onUpdate`), which Task 5 uses.

- [ ] **Step 1:** `git switch -c advert-video`.
- [ ] **Step 2:** With Peter's go-ahead, `brew install ffmpeg`. Verify: `ffmpeg -version` and `ffprobe -version` print versions.
- [ ] **Step 3:** Create `advert/package.json` (`"type": "module"`, `"private": true`, the scripts and dev dependencies above) and `advert/.gitignore` containing `node_modules/`, `build/`, `out/`, `renders/`. Run `npm install`. Run `npx hyperframes doctor`; expected: no failing checks.
- [ ] **Step 4:** Write `advert/spike/index.html`: root `data-composition-id="spike"`, `data-width="1920"`, `data-height="1080"`, `data-duration="2"`; a `#readout` clip; an `<audio src="beep.wav" data-start="0.5" data-duration="0.2">`; GSAP loaded from `gsap.min.js`, copied there from `node_modules/gsap/dist/`. The script first `await`s `fetch("beep.wav")`, then builds a paused timeline with one tween `tl.to(clock, { t: 2, duration: 2, ease: "none" }, 0)` where `clock` has an accessor property `t` whose setter writes `value.toFixed(2)` into `#readout`, then registers `window.__timelines.spike`. Generate `beep.wav` with `ffmpeg -f lavfi -i "sine=frequency=880:duration=0.2" -ar 48000 -ac 1 spike/beep.wav`.
- [ ] **Step 5:** Run `npx hyperframes lint spike` (expected: no errors) and `npx hyperframes snapshot spike --at 0.5,1.5` (check `npx hyperframes snapshot --help` for the output-path flag). Open both PNGs. Expected: they read `0.50` and `1.50`.
  - If they do not, replace the setter with `onUpdate` on the same tween and repeat. If neither follows the seek time, **stop and report to Peter**: the fallback is Remotion, which changes Tasks 4, 5 and 8.
- [ ] **Step 6:** Run `npx hyperframes render spike -o out/spike.mp4 --fps 60`. Verify with `ffprobe -v error -show_entries stream=codec_type,width,height,r_frame_rate -of csv=p=0 out/spike.mp4`. Expected: a `video,1920,1080,60/1` line and an `audio` line.
- [ ] **Step 7:** Write `advert/README.md`: what the folder is, the four npm commands, which driver pattern worked, the snapshot output flag. Delete `advert/spike/`.
- [ ] **Step 8:** Commit `advert/package.json advert/package-lock.json advert/.gitignore advert/README.md` with message `chore: scaffold the advert video project and prove the render tool`.

---

### Task 2: The timeline

**Files:**
- Create: `advert/src/timeline.mjs`
- Test: `advert/tests/timeline.test.mjs`

**Interfaces:**
- Produces, all exported from `timeline.mjs`:
  - `FPS = 60`, `WIDTH = 1920`, `HEIGHT = 1080`, `DURATION = 27`, `SAMPLE_RATE = 48000`
  - `SCENES = { arrive: [0, 2], type: [2, 7], cardCustomise: [7, 8], customise: [8, 13], cardUnlock: [13, 14], unlock: [14, 18], cardTrack: [18, 19], track: [19, 23], end: [23, 27] }`
  - `CARDS = [{ id: "card-customise", text: "Customise it.", start: 7, duration: 1 }, { id: "card-unlock", text: "Unlock new outfits.", start: 13, duration: 1 }, { id: "card-track", text: "Track your productivity.", start: 18, duration: 1 }]`
  - `TYPED_TEXT = "Brighten up your day, one key at a time."`
  - `LOOKS`: `plain {gray, {}}`, `ginger {ginger, {}}`, `blackWhite {black-white, {}}`, `wizard {gray, {hat: wizard-hat}}`, `shades {gray, {glasses: sunglasses, neck: red-bandana}}`, `crownCape {gray, {hat: crown, back: royal-cape}}`, `party {gray, {hat: party-hat}}`, `crown {gray, {hat: crown}}`, `crownWings {gray, {hat: crown, back: dragon-wings}}`, `brand {gray, {hat: beanie, neck: bow-tie}}`. Each value is `{ cat: string, outfit: Record<slot, id> }`.
  - `LOOK_CHANGES = [{t: 0, look: "plain"}, {t: 8.6, look: "ginger"}, {t: 9.5, look: "blackWhite"}, {t: 10.4, look: "wizard"}, {t: 11.2, look: "shades"}, {t: 11.9, look: "crownCape"}, {t: 13, look: "plain"}, {t: 15.0, look: "party"}, {t: 16.2, look: "crown"}, {t: 17.4, look: "crownWings"}, {t: 23, look: "brand"}]`
  - `UNLOCKS = [{t: 15.0, id: "party-hat", name: "Party hat", target: 50000}, {t: 16.2, id: "crown", name: "Crown", target: 100000}, {t: 17.4, id: "dragon-wings", name: "Dragon wings", target: 500000}]`
  - `STATS = { week: [1180, 1620, 940, 1850, 1410, 2060, 1440], labels: ["M", "T", "W", "T", "F", "S", "Today"], today: 1440, last7: 10500, allTime: 510500 }`
  - `END = { title: "Cat Type", line: "Get it for Windows or Mac", url: "fungusta.github.io/cat-type" }`
  - `pawFor(char: string): "left" | "right" | "both" | "alternate"`
  - `presses(): Array<{ t: number, paw: "left" | "right" | "both", scene: "type" | "unlock" | "track", char?: string }>` sorted by `t`
  - `frameState(t: number): { look: string, pawLeft: number, pawRight: number, excited: boolean, typedChars: number, counter: number, unlocked: string[], stats: { today: number, last7: number, allTime: number }, bars: number[] }`
  - `soundCues(): Array<{ t: number, sound: string, gain: number }>` sorted by `t`

Rules the tests pin (the implementer writes the bodies):

- `pawFor` copies the app (`cat_type.py:128-131`): space → `both`; lower-cased char in `` `~12345!@#$%qwertasdfgzxcvb `` → `left`; in ``67890-=_+^&*()yuiop[]{}\|hjkl:;'"nm,./<>?`` → `right`; anything else → `alternate`. `presses()` turns `alternate` into the opposite of the previous press's paw (first one `left`).
- Type scene: one press per character of `TYPED_TEXT` (40), press `i` at `2.3 + 4.1 * (0.6u + 0.4 * (1 - (1 - u)²))` with `u = i / 39`.
- Unlock scene: press `k` at `14.2 + 0.08k` for every `k` whose time is ≤ 17.6, alternating paws starting `left`. Track scene: press `k` at `19.3 + 0.14k` while ≤ 22.6, alternating.
- Paw depth, as in the app's 0.16 s tap frame (`cat_type.py:897-906`): for the latest press on that side at age `a = t - press.t`: 1 while `a < 0.08`, falling linearly to 0 at `a = 0.16`, 0 after. A `both` press counts for both sides.
- `excited`: true while a `both` press is younger than 0.16 s, or while the latest press is younger than 0.16 s and it is at least the fifth of a run in which the fifth-most-recent press is less than 0.34 s older.
- `typedChars`: number of type-scene presses with `press.t <= t`.
- `counter`: straight lines through `(14, 0)`, `(15.0, 50000)`, `(16.2, 100000)`, `(17.4, 500000)`, rounded down; 0 before, 500000 after. `unlocked`: ids of `UNLOCKS` with `t >= unlock.t`.
- `stats`: each value rises in a straight line from 0 at 19.4 to its `STATS` value at 21.8, rounded. `bars[i]`: 0 before `19.6 + 0.3i`, rising in a straight line over 0.35 s to `week[i] / max(week)`.
- `look`: the last `LOOK_CHANGES` entry with `entry.t <= t`.
- `soundCues`: for each press a cue at the same `t` — type scene: `space` for `both`, else `key-1` … `key-6` rotating by press index, gain 0.8; unlock scene keys gain 0.5; track scene keys gain 0.3. Plus `pop` at 0.9 and 23.1 (gain 0.9); `whoosh` at 7, 13, 18 (0.7); `swap` at 8.6, 9.5, 10.4, 11.2, 11.9 (0.8); `chime` at each `UNLOCKS` time (0.8); `tick` at `19.6 + 0.3i` for `i` 0–6 (0.5).

- [ ] **Step 1: Write the failing tests** in `advert/tests/timeline.test.mjs` using `node:test` and `node:assert/strict`:

```js
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} vs ${b}`);

test("pawFor follows the app's keyboard split", () => {
  assert.equal(pawFor("B"), "left");
  assert.equal(pawFor("u"), "right");
  assert.equal(pawFor(","), "right");
  assert.equal(pawFor(" "), "both");
  assert.equal(pawFor("é"), "alternate");
});

test("the typed sentence gets one press per character, speeding up", () => {
  const typed = presses().filter((p) => p.scene === "type");
  assert.equal(typed.length, 40);
  assert.equal(typed.map((p) => p.char).join(""), TYPED_TEXT);
  near(typed[0].t, 2.3);
  near(typed[39].t, 6.4);
  const gaps = typed.slice(1).map((p, i) => p.t - typed[i].t);
  assert.ok(gaps.every((gap, i) => i === 0 || gap < gaps[i - 1]));
  assert.ok(gaps.at(-1) > 0.05);
});

test("a paw goes down on its key and comes back up within 0.16 s", () => {
  assert.equal(frameState(2.3).pawLeft, 1);
  assert.equal(frameState(2.3).pawRight, 0);
  near(frameState(2.3 + 0.12).pawLeft, 0.5);
  assert.equal(frameState(2.29).pawLeft, 0);
});

test("space taps both paws and excites the cat", () => {
  const space = presses().find((p) => p.paw === "both");
  const state = frameState(space.t);
  assert.deepEqual([state.pawLeft, state.pawRight, state.excited], [1, 1, true]);
});

test("slow typing is calm and fast typing is excited", () => {
  assert.equal(frameState(2.35).excited, false);
  assert.equal(frameState(6.38).excited, true);
  assert.equal(frameState(16.01).excited, true);
  assert.equal(frameState(1).excited, false);
});

test("the sentence fills in and stays", () => {
  assert.equal(frameState(2.29).typedChars, 0);
  assert.equal(frameState(2.3).typedChars, 1);
  assert.equal(frameState(6.9).typedChars, 40);
});

test("looks change on schedule", () => {
  const looks = [0, 8.59, 8.6, 12.5, 13.5, 15.0, 17.5, 24].map((t) => frameState(t).look);
  assert.deepEqual(looks, ["plain", "plain", "ginger", "crownCape", "plain", "party", "crownWings", "brand"]);
  for (const { look } of LOOK_CHANGES) assert.ok(LOOKS[look], look);
});

test("the counter reaches each target as its outfit unlocks", () => {
  assert.equal(frameState(14).counter, 0);
  assert.equal(frameState(15.0).counter, 50000);
  assert.equal(frameState(16.2).counter, 100000);
  assert.equal(frameState(26).counter, 500000);
  assert.deepEqual(frameState(14.99).unlocked, []);
  assert.deepEqual(frameState(17.4).unlocked, ["party-hat", "crown", "dragon-wings"]);
});

test("stats count up and bars grow one after another", () => {
  assert.deepEqual(frameState(19.4).stats, { today: 0, last7: 0, allTime: 0 });
  assert.deepEqual(frameState(22).stats, { today: 1440, last7: 10500, allTime: 510500 });
  assert.deepEqual(frameState(19.5).bars, [0, 0, 0, 0, 0, 0, 0]);
  near(frameState(22).bars[5], 1);
  near(frameState(22).bars[0], 1180 / 2060);
  assert.ok(frameState(19.8).bars[0] > 0 && frameState(19.8).bars[1] === 0);
});

test("frameState is a pure function of time", () => {
  const first = frameState(3.21);
  frameState(20);
  assert.deepEqual(frameState(3.21), first);
});

test("every press has a sound cue at the same time", () => {
  const cues = soundCues();
  for (const press of presses()) {
    assert.ok(cues.some((cue) => cue.t === press.t && /^(key-[1-6]|space)$/.test(cue.sound)), `press at ${press.t}`);
  }
});

test("scene sounds sit on their beats and inside the video", () => {
  const at = (sound) => soundCues().filter((cue) => cue.sound === sound).map((cue) => cue.t);
  assert.deepEqual(at("whoosh"), [7, 13, 18]);
  assert.deepEqual(at("pop"), [0.9, 23.1]);
  assert.deepEqual(at("swap"), [8.6, 9.5, 10.4, 11.2, 11.9]);
  assert.deepEqual(at("chime"), [15.0, 16.2, 17.4]);
  assert.equal(at("tick").length, 7);
  assert.ok(soundCues().every((cue) => cue.t >= 0 && cue.t <= DURATION - 0.7 && cue.gain > 0 && cue.gain <= 1));
});
```

- [ ] **Step 2:** Run `npm test`. Expected: FAIL, cannot find `../src/timeline.mjs`.
- [ ] **Step 3:** Implement `advert/src/timeline.mjs` with the exports and rules above. No imports, no DOM.
- [ ] **Step 4:** Run `npm test`. Expected: all 12 pass.
- [ ] **Step 5:** Commit `advert/src/timeline.mjs advert/tests/timeline.test.mjs`, message `feat: add the advert's timeline of poses, looks and sounds`.

---

### Task 3: Sounds and the mixer

**Files:**
- Create: `advert/src/mix.mjs`, `advert/src/sfx-synth.mjs`
- Create: `advert/sfx/key-1.wav` … `key-6.wav`, `advert/sfx/space.wav`, `advert/SOUNDS.md`
- Test: `advert/tests/mix.test.mjs`, `advert/tests/sfx.test.mjs`

**Interfaces:**
- Produces from `mix.mjs`:
  - `parseWav(buffer: Buffer, name: string): Float32Array` — PCM16 only; walks the chunk list to find `fmt ` and `data` (FFmpeg adds a `LIST` chunk); throws `Error` whose message contains `name` and `expected 48000 Hz mono` for any other rate or channel count.
  - `mixCues(cues: Array<{t, sound, gain}>, sounds: Record<string, Float32Array>, options: { sampleRate: number, duration: number }): Float32Array` — length `duration * sampleRate`; each sound added at index `Math.round(t * sampleRate)` times `gain`; throws naming an unknown sound; if the peak exceeds 0.89 the whole mix is scaled so the peak is 0.89.
  - `encodeWav(samples: Float32Array, sampleRate: number): Buffer` — PCM16 mono with the plain 44-byte header (`data` chunk at byte 36).
- Produces from `sfx-synth.mjs`: `SYNTHS: Record<"pop" | "whoosh" | "swap" | "chime" | "tick", () => Float32Array>` at 48000 Hz. Maximum lengths in seconds: pop 0.15, whoosh 0.35, swap 0.10, chime 0.60, tick 0.04. Any noise comes from a seeded generator. Character is the implementer's call: pop a short falling sine blip, whoosh a swelling filtered-noise breath, swap a higher shorter pop, chime two soft sine partials, tick a tiny click.

- [ ] **Step 1: Write the failing tests.**

`tests/mix.test.mjs`:
```js
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
```

`tests/sfx.test.mjs`:
```js
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
```

- [ ] **Step 2:** Run `npm test`. Expected: FAIL, modules not found.
- [ ] **Step 3:** Implement `src/mix.mjs` and `src/sfx-synth.mjs`. Run `npm test`. Expected: everything passes except `the recorded key clicks…`.
- [ ] **Step 4:** Get the key clicks. Open `https://opengameart.org/content/keyboard-soundpack-1-typing-and-single-keystrokes` and confirm the page states CC0. Tell Peter the file name, source and size and wait for his go-ahead, then download into a new empty folder in the scratchpad. Pick six distinct single-keystroke recordings and one deeper one for space. Convert each: `ffmpeg -i <in> -ar 48000 -ac 1 -c:a pcm_s16le -t 0.25 -af "afade=t=out:st=0.2:d=0.05" sfx/<name>.wav`.
  - If the page does not say CC0, or Peter declines: add `key` and `space` to `SYNTHS` (seeded noise burst through a short resonant thock, ≤ 0.12 s), write the seven files from them with a one-off script, and say so in `SOUNDS.md`.
- [ ] **Step 5:** Write `advert/SOUNDS.md`: one row per file in `sfx/` with source URL, original file name, licence; a line saying the other five sounds are generated by `src/sfx-synth.mjs`.
- [ ] **Step 6:** Run `npm test`. Expected: all pass.
- [ ] **Step 7:** Commit `advert/src/mix.mjs advert/src/sfx-synth.mjs advert/sfx advert/SOUNDS.md advert/tests/mix.test.mjs advert/tests/sfx.test.mjs`, message `feat: add the advert's sounds and soundtrack mixer`.

---

### Task 4: The build

**Files:**
- Create: `advert/scripts/build.mjs`, `advert/src/index.html`, `advert/src/advert.css`, `advert/src/stage.js` (a stub that registers an empty 27 s timeline; Task 5 fills it)
- Test: `advert/tests/build.test.mjs`

**Interfaces:**
- Consumes: `LOOKS`, `UNLOCKS`, `soundCues`, `DURATION`, `SAMPLE_RATE` (Task 2); `parseWav`, `mixCues`, `encodeWav`, `SYNTHS` (Task 3).
- Produces from `build.mjs`:
  - `readCatalog(repoRoot: string): Map<string, { slot: string, hidden: boolean }>` — parsed from `cat_accessories.py` lines of the form `Accessory("id", "Name", "slot", …)`, `hidden` true when the line contains `hidden=True`.
  - `assertPublishable(looks: Record<string, { cat, outfit }>, extraIds: string[], catalog): void` — throws an `Error` containing the id when an id is not in the catalog, is hidden, or sits under a slot key different from its catalog slot.
  - `build(options?: { outDir?: string }): Promise<string>` — default `advert/build`. Empties `outDir`, then writes: `index.html`, `advert.css` (copied from `src/`); `js/advert.js` (esbuild bundle of `src/stage.js`, `format: "iife"`); `js/gsap.min.js`; `fonts/nunito-latin-700-normal.woff2` and `fonts/nunito-latin-800-normal.woff2`; `assets/cats/<cat>.svg` for every cat in `LOOKS`; `assets/accessories/<id>.svg` for every outfit id in `LOOKS` and every `UNLOCKS` id; `sfx/soundtrack.wav` (mix of `soundCues()` over `DURATION`). Running the file directly calls `build()` and prints the path.
- Produces in `src/index.html`: root `<div id="root" data-composition-id="advert" data-start="0" data-duration="27" data-width="1920" data-height="1080">`; `<audio id="soundtrack" src="sfx/soundtrack.wav" data-start="0" data-duration="27" data-track-index="9" data-volume="1">`; classic `<script src="js/gsap.min.js">` then `<script src="js/advert.js">`; `<link rel="stylesheet" href="advert.css">`. `advert.css` declares the two `@font-face` rules and `html, body { margin: 0; background: #fff9f3; }`.

- [ ] **Step 1: Write the failing tests** in `tests/build.test.mjs`:

```js
const repoRoot = fileURLToPath(new URL("../../", import.meta.url));
const catalog = readCatalog(repoRoot);

test("the catalog knows slots and secrets", () => {
  assert.deepEqual(catalog.get("crown"), { slot: "hat", hidden: false });
  assert.deepEqual(catalog.get("moon-pendant"), { slot: "neck", hidden: true });
  assert.equal(catalog.size, 30);
});

test("the advert's own looks are publishable", () => {
  assertPublishable(LOOKS, UNLOCKS.map((unlock) => unlock.id), catalog);
});

test("a secret accessory stops the build", () => {
  assert.throws(() => assertPublishable({ x: { cat: "gray", outfit: { neck: "moon-pendant" } } }, [], catalog), /moon-pendant/);
});

test("an unknown accessory stops the build", () => {
  assert.throws(() => assertPublishable({}, ["nope"], catalog), /nope/);
});

test("an accessory in the wrong slot stops the build", () => {
  assert.throws(() => assertPublishable({ x: { cat: "gray", outfit: { hat: "sunglasses" } } }, [], catalog), /sunglasses/);
});

test("build writes a complete project", async () => {
  const outDir = await mkdtemp(join(tmpdir(), "advert-"));
  await build({ outDir });
  for (const file of [
    "index.html", "advert.css", "js/advert.js", "js/gsap.min.js",
    "fonts/nunito-latin-700-normal.woff2", "fonts/nunito-latin-800-normal.woff2",
    "assets/cats/gray.svg", "assets/cats/ginger.svg", "assets/cats/black-white.svg",
    ...["wizard-hat", "sunglasses", "red-bandana", "crown", "royal-cape", "party-hat", "dragon-wings", "beanie", "bow-tie"]
      .map((id) => `assets/accessories/${id}.svg`),
  ]) assert.ok(existsSync(join(outDir, file)), file);
  const soundtrack = parseWav(await readFile(join(outDir, "sfx/soundtrack.wav")), "soundtrack");
  assert.equal(soundtrack.length, 27 * 48000);
  assert.ok(soundtrack.some((sample) => Math.abs(sample) > 0.1));
  assert.match(await readFile(join(outDir, "index.html"), "utf8"), /data-composition-id="advert"/);
});
```

- [ ] **Step 2:** Run `npm test`. Expected: FAIL, `../scripts/build.mjs` not found.
- [ ] **Step 3:** Implement `scripts/build.mjs`, `src/index.html`, `src/advert.css`, and the stub `src/stage.js`.
- [ ] **Step 4:** Run `npm test`. Expected: all pass. Run `npm run build && npx hyperframes lint build`. Expected: no errors.
- [ ] **Step 5:** Commit `advert/scripts advert/src/index.html advert/src/advert.css advert/src/stage.js advert/tests/build.test.mjs`, message `feat: assemble the advert into a renderable project`.

---

### Task 5: The cat on stage — arriving and typing (scenes 1–2)

**Files:**
- Modify: `advert/src/stage.js`, `advert/src/index.html`, `advert/src/advert.css`

**Interfaces:**
- Consumes: everything from `timeline.mjs`; `renderCat(container, { cat, outfit }, idPrefix, assetBase)` from `../../site/js/cat.js` (it adds classes `cat-paw-left`, `cat-paw-right`, `cat-pads`, `cat-mouth-idle`, `cat-mouth-excited` to the parts); the driver pattern recorded in `advert/README.md`.
- Produces in `stage.js`:
  - `applyFrame(t: number): void`, also exposed as `window.__advert.applyFrame`. Calls `frameState(t)` and sets, every time and without reading previous DOM state: which `.look` is shown (`visibility`), on the shown cat `transform: scaleY(1 - 0.34 * depth)` for each paw, `.cat-pads` hidden while either depth > 0, class `is-excited` when `excited`, and `#typed` text to `TYPED_TEXT.slice(0, typedChars)`.
  - One element per `LOOKS` key: `<div class="look" data-look="<key>">` inside `#cat-rig`, filled by `renderCat(…, "look-<key>", "assets/")`.
  - A paused GSAP timeline registered as `window.__timelines.advert`, registered only after every `renderCat` promise and `document.fonts.load('800 160px "Nunito"')` have resolved. It holds the frame driver over 0–27 s plus the scene tweens.
- Produces in `index.html`: `#scene-stage` clip (`data-start="0" data-duration="27"`, `z-index: 0`) containing `#camera` → `#cat-rig`, `#typed-line` (`#typed` + `#caret`).

Scene direction (exact easing and distances are the implementer's call):
- 0–0.9 s: empty cream screen, `#caret` blinking via `tl.set` steps every 0.5 s, sitting where the typed line will start.
- 0.9 s: the cat pops up beside the caret (scale from 0 with a small overshoot, about 0.35 s).
- 1.4–2.2 s: `#camera` pushes in so the cat is about 520 px tall, the typed line below it.
- 2.3–6.4 s: the sentence appears one character per press at 72 px Nunito 800, ink, on one line; the caret follows the text and no longer blinks.
- 6.4–7 s: hold.
- `advert.css` carries only static cat rules (paw `transform-box: fill-box; transform-origin: 50% 100%`, `.cat-mouth-excited` hidden unless `.is-excited`, and the reverse for `.cat-mouth-idle`). No `transition`, no `animation`, no `@keyframes`.

- [ ] **Step 1:** Implement the markup, styles and `stage.js`.
- [ ] **Step 2:** Run `npm test`. Expected: still all pass (the build test bundles the new `stage.js`).
- [ ] **Step 3:** Run `grep -nE "transition|animation|@keyframes|setTimeout|requestAnimationFrame|Math\.random|Date\." src/stage.js src/advert.css`. Expected: no output.
- [ ] **Step 4:** Run `npm run build && npx hyperframes lint build && npx hyperframes check build`. Expected: no errors.
- [ ] **Step 5:** Run `npm run snap -- 0.4,1.2,2.3,2.38,4.5,6.38,6.9` and open each PNG. Expected, in order: caret only; cat present, not yet close; first letter `B`, left paw down; left paw part-way up; about half the sentence, calm mouth; nearly the whole sentence, excited mouth; whole sentence, both paws up, calm mouth.
- [ ] **Step 6:** In the 6.9 s snapshot confirm the sentence is in Nunito (round letterforms, single-storey `a`), on one line, with at least 80 px clear on both sides.
- [ ] **Step 7:** Out-of-order check: run `npm run snap -- 6.38,2.3` and compare the 2.3 s PNG with the one from Step 5 (`cmp` or `shasum`). Expected: identical.
- [ ] **Step 8:** Commit `advert/src`, message `feat: animate the cat arriving and typing`.

---

### Task 6: Word cards, outfit changes and unlocks (scenes 3–6)

**Files:**
- Modify: `advert/src/stage.js`, `advert/src/index.html`, `advert/src/advert.css`

**Interfaces:**
- Consumes: `CARDS`, `LOOK_CHANGES`, `UNLOCKS`, `frameState` (Task 2); `applyFrame`, `#camera`, `#cat-rig` (Task 5).
- Produces: one `<section class="clip card" id="<card.id>" data-start data-duration data-track-index="1">` per `CARDS` entry, `z-index: 2`; `#unlock-ui` containing `#counter` and three `.tile[data-id]`; `applyFrame` extended to set `#counter` to `counter.toLocaleString("en")` and class `is-unlocked` on each tile in `unlocked`.

Scene direction:
- Cards: butter `#f2d66b` full frame, ink text, Nunito 800 at 180 px, centred. Text rises about 40 px and fades in over 0.25 s, holds, and the card is gone when its clip ends.
- 8–13 s, customise: the typed line is hidden, the cat is centred and large. At each customise `LOOK_CHANGES` time the look switches on that exact frame and `#cat-rig` gets a quick squash-and-settle (about 0.25 s).
- 14–18 s, unlock: cat on the left typing. On the right, `#counter` at 120 px Nunito 800 with the small label `keystrokes`, and under it three tiles showing each accessory's own SVG and name. A locked tile is grey and faded with a padlock; at its `UNLOCKS` time it turns butter-soft `#fff1b8` with a quick scale pop, and the cat's look changes on the same frame.
- Accessory tile art is fetched and inlined during setup, before the timeline is registered.

- [ ] **Step 1:** Implement.
- [ ] **Step 2:** Run `npm test`; expected all pass. Repeat the `grep` from Task 5 Step 3; expected no output. Run `npm run build && npx hyperframes lint build && npx hyperframes check build`; expected no errors.
- [ ] **Step 3:** Run `npm run snap -- 7.5,8.3,8.7,9.6,10.5,11.3,12.5,13.5,14.5,15.1,16.3,17.6` and open each. Expected, in order: card `Customise it.`; plain gray cat centred, no typed line; ginger; black and white; gray with wizard hat; gray with sunglasses and red bandana; gray with crown and royal cape; card `Unlock new outfits.`; plain cat typing, counter between 20,000 and 30,000, three locked tiles; party hat on, first tile unlocked, counter just over 50,000; crown on, two tiles unlocked; crown and dragon wings on, three tiles unlocked, counter `500,000`.
- [ ] **Step 4:** Commit `advert/src`, message `feat: add word cards, outfit changes and unlocks to the advert`.

---

### Task 7: Stats and the end card (scenes 7–9)

**Files:**
- Modify: `advert/src/stage.js`, `advert/src/index.html`, `advert/src/advert.css`

**Interfaces:**
- Consumes: `STATS`, `END`, `frameState` (Task 2); `applyFrame` (Tasks 5–6).
- Produces: `#track-ui` with three `.stat` blocks (`Today`, `Last 7 days`, `All time`) and seven `.bar` elements; `#end-card` with `#end-title`, `#end-line`, `#end-url`, `#heart`. `applyFrame` extended to set each stat's text with `toLocaleString("en")` and each bar fill's `transform: scaleY(bars[i])` (origin bottom).

Scene direction:
- 19–23 s, track: a white rounded card (radius 28 px) centred, laid out like the site's Track band (`site/index.html:77-90`, `site/styles.css:293-321`) scaled up for 1080p: three stat blocks on top, a seven-bar chart under them with labels from `STATS.labels`. The last bar is butter, the others `#ece5de`. The cat sits small in the lower right, tapping, wearing crown and dragon wings.
- 23–27 s, end: the cat in the `brand` look pops in at centre-top at 23.1; `Cat Type` (Nunito 800, 160 px) at 23.4; `Get it for Windows or Mac` in a butter pill at 23.9; the URL in ink at 24.3. At 25.0 the cat hops (as `cat-hop` in `site/cat.css:49-54`, rebuilt as GSAP tweens) and a `♥` in `#ef6f95` rises and fades above it. Nothing moves after 26.2.

- [ ] **Step 1:** Implement.
- [ ] **Step 2:** Run `npm test`; the `grep` from Task 5 Step 3; `npm run build && npx hyperframes lint build && npx hyperframes check build`. Expected: all pass, no output, no errors.
- [ ] **Step 3:** Run `npm run snap -- 18.5,19.5,20.3,22.5,23.3,24.5,25.3,26.8` and open each. Expected, in order: card `Track your productivity.`; stats card with zeros and flat bars; some bars grown, numbers part-way; `1,440`, `10,500`, `510,500`, seven bars with the tallest sixth and the last one butter; cat alone; cat, title, pill and URL; cat mid-hop with heart; settled end card with no heart.
- [ ] **Step 4:** Commit `advert/src`, message `feat: add the stats scene and end card to the advert`.

---

### Task 8: Render and hand over

**Files:**
- Modify: `advert/README.md`
- Create: `advert/scripts/check-sync.mjs`

**Interfaces:**
- Consumes: `parseWav` (Task 3).
- Produces: `node scripts/check-sync.mjs <wav> <after-seconds>` prints, in seconds to three decimals, the first time after `<after-seconds>` at which a sample's absolute value exceeds 0.05.

- [ ] **Step 1:** Run `npm test && npm run build && npx hyperframes lint build && npx hyperframes check build`. Expected: all pass, no errors.
- [ ] **Step 2:** Run `npm run render` (`hyperframes render build -o out/cat-type-advert.mp4 --fps 60 --quality high`), in the background if it runs past two minutes.
- [ ] **Step 3:** Run `ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,r_frame_rate -of default=nw=1 out/cat-type-advert.mp4`. Expected: `duration` between 26.9 and 27.1, a video stream `1920`, `1080`, `60/1`, and an audio stream.
- [ ] **Step 4:** Sound-on-paw check. Write `scripts/check-sync.mjs`, then run `ffmpeg -y -i out/cat-type-advert.mp4 -ar 48000 -ac 1 -c:a pcm_s16le out/audio.wav && node scripts/check-sync.mjs out/audio.wav 1.5`. The pop at 0.9 s has died away by 1.5 s, so the next sound is the first key click. Expected: a time between 2.28 and 2.34 (the first paw goes down at 2.30).
- [ ] **Step 5:** Pull frames from the finished file at 1, 4, 7.5, 10.5, 13.5, 16.3, 18.5, 22.5 and 26.5 s with `ffmpeg -ss <t> -i out/cat-type-advert.mp4 -frames:v 1 out/frame-<t>.png` and open each. Expected: they match the snapshots from Tasks 5–7.
- [ ] **Step 6:** Update `advert/README.md`: how to change words, outfits and timing (all in `src/timeline.mjs`), how to re-render, and what is not yet done (upright version, music).
- [ ] **Step 7:** Commit `advert/README.md advert/scripts/check-sync.mjs`, message `docs: explain how to change and re-render the advert`.
- [ ] **Step 8:** Send `out/cat-type-advert.mp4` to Peter and report which checks ran and passed.
