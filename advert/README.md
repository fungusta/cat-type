# Cat Type advert

This folder renders the 27-second Cat Type advert video (1920x1080, 60 fps MP4 with sound) using the [HyperFrames](https://hyperframes.heygen.com) CLI: an HTML page with a GSAP timeline is seeked frame by frame in headless Chrome and encoded with FFmpeg. It is separate from the desktop app and from `site/`.

Run every command from this folder. You need Node and FFmpeg (`brew install ffmpeg`); HyperFrames uses the installed Google Chrome.

## Commands

| Command | What it does |
| --- | --- |
| `npm test` | Runs the unit tests in `tests/` (`node --test tests/`). |
| `npm run build` | Builds the composition into `build/` (`node scripts/build.mjs`). |
| `npm run snap -- 0.5,1.5` | Captures still PNGs of `build/` at the given seconds. |
| `npm run render` | Renders `build/` to `out/cat-type-advert.mp4` at 60 fps, high quality. |

`build/`, `out/`, `renders/` and `node_modules/` are generated and never committed.

## Changing the advert

Almost everything you might want to change is a constant near the top of `src/timeline.mjs`. Times are in seconds from the start of the video (0 to 27). After any change, rebuild and look at stills before re-rendering (see "Rebuild, preview and re-render" below).

| To change | Edit | Notes |
| --- | --- | --- |
| The words on the three butter-yellow cards | `CARDS` (`text`) | Each card has a `start` and `duration`. If you move a card, also change the matching `<section class="clip card">` `data-start` / `data-duration` in `src/index.html`; the page stops with an error naming the card if they disagree. |
| The sentence the cat types (2.3–6.4 s) | `TYPED_TEXT` | It is always typed over the same 4.1 s, so a longer sentence types faster. It is one line at 72 px with no width check, so take stills at 6.5 s to see it fits. Spaces make both paws tap. |
| The end card | `END` (`title`, `line`, `url`) | |
| The outfits | `LOOKS` | Each look is a cat colour (`gray`, `ginger`, `black-white`, `brown-tabby`, `charcoal` or `white`: files in `assets/vector-cats/`) and an outfit of `hat`, `glasses`, `neck`, `back` or `ears` slots. Accessory ids are the first column of `cat_accessories.py` (files in `assets/accessories/`). The build stops if an id is unknown, is a secret (`hidden=True`) one, or is worn in the wrong slot. |
| Which outfit is worn when, and in what order | `LOOK_CHANGES` | A list of `{ t, look }`: from time `t` the cat wears that look until the next entry. Keep it in time order. Each change strictly inside the customise scene (8–13 s) gets a squash and a swap sound automatically. |
| The three unlocks (14–18 s) | `UNLOCKS` | `t`, accessory `id`, the name shown, and the keystroke `target`. The keystroke counter climbs from 0 at the start of the unlock scene through each `target` at its `t` (`COUNTER_POINTS` follows automatically), and each unlock gets a chime. |
| The stats (19–23 s) | `STATS` | The seven daily bars (`week`, `labels`) and the all-time total; `today` (the last bar) and `last7` (the sum of the bars) follow from `week` automatically. The page stops with an error if a total is too wide for its box. |
| Scene timing | `SCENES` | Start and end of each scene. Typing, bar and beat timings sit below it (`TYPE_START`, `TYPE_SPAN`, `UNLOCK_KEYS`, `TRACK_KEYS`, `STATS_FROM`, `STATS_TO`, `BAR_START`, `BAR_STAGGER`, `BAR_GROW`, `ARRIVE_POP`, `END_BEATS`). Changing the total length (`DURATION`, 27) also needs the three `data-duration="27"` values in `src/index.html`; the page stops with an error naming the element if one disagrees. |

### Word card text size

The three word cards share one text size (150 px, `.card-text` in `src/advert.css`), so they look alike. When the page loads, it measures each card line and each end-card line; if one is wider than the frame less 120 px a side, the snapshot or render stops with an error such as `#card-track "..." is <width> px wide; cards must fit in 1680 px` (a render exits with code 1 and writes no video). Shorten the words (or lower the shared size for all cards) rather than squeezing one card.

### Sounds

The soundtrack is mixed by `npm run build` into `build/sfx/soundtrack.wav` from the cue lists in `src/timeline.mjs`. Every sound is placed from the same constant the picture uses, so moving a beat moves its sound too.

| Sound | File | Where its timing and volume live |
| --- | --- | --- |
| Key clicks (one per paw tap) | `sfx/key-1.wav` … `sfx/key-6.wav`, taken in turn | Follows the paw taps automatically. Volume per scene: `KEY_GAIN` (`type`, `unlock`, `track`). |
| Space bar (both paws) | `sfx/space.wav` | Every space in `TYPED_TEXT`; volume `KEY_GAIN.type`. |
| Pop (cat arrives, end card) | made in `src/sfx-synth.mjs` (`pop`) | Follows `ARRIVE_POP` and `END_BEATS.cat` automatically (the same constants the cat's pop-in tweens use). |
| Whoosh (each word card) | `src/sfx-synth.mjs` (`whoosh`) | Follows each card's `CARDS` `start` automatically. |
| Swap (outfit changes) | `src/sfx-synth.mjs` (`swap`) | Follows the `LOOK_CHANGES` inside the customise scene automatically. |
| Chime (each unlock) | `src/sfx-synth.mjs` (`chime`) | Follows `UNLOCKS` automatically. |
| Tick (each stats bar) | `src/sfx-synth.mjs` (`tick`) | Follows `BAR_START` and `BAR_STAGGER` automatically. |

When a scene moves, these still have to move by hand: `SCENES`, `CARDS` plus the matching clip attributes in `src/index.html`, `LOOK_CHANGES`, `UNLOCKS`, the key schedules (`TYPE_START`, `UNLOCK_KEYS`, `TRACK_KEYS`), `END_BEATS`, and `CAT_SPOTS` in `src/stage.js` if a layout changes; then check stills.

Each `SCENE_CUES` row has a `gain` (1 is the sound's own level). To swap a key click, replace the file with a 48000 Hz mono 16-bit WAV (the build refuses anything else) and note its source in `SOUNDS.md`. If the mix gets too loud it is scaled down as a whole, so nothing clips.

### Rebuild, preview and re-render

1. `npm test` — the timeline checks.
2. `npm run build` — rebuilds `build/` (page, artwork, soundtrack). Stops with a message if an outfit uses an unknown or secret accessory.
3. `npm run snap -- 6.5,7.5,13.5 -o renders/check` — stills at the seconds you name, plus `contact-sheet.jpg`, in `renders/check/`. Open them to check the change before a full render.
4. `npm run render` — writes `out/cat-type-advert.mp4` (about 1.5 minutes on an 8 GB Mac; see the low-memory note below).
5. Optional sound check: `ffmpeg -y -i out/cat-type-advert.mp4 -ar 48000 -ac 1 -c:a pcm_s16le out/audio.wav && node scripts/check-sync.mjs out/audio.wav 1.5` prints when the first key click is heard after 1.5 s; it should be about `2.300`, when the first paw goes down. `node scripts/check-sync.mjs out/audio.wav 23.0` should print about `23.100` (the end-card pop).

### Not done yet

- An upright, phone-shaped (9:16) version. The advert is 1920x1080 only.
- Music. The soundtrack is sound effects only.

## Snapshots

`hyperframes snapshot` writes to `<project>/.hyperframes/artifacts/snapshots/<unique dir>/` by default, so `npm run snap` puts stills under `build/.hyperframes/artifacts/snapshots/`. Choose the folder with `-o <dir>` (also `--output=<dir>`), e.g. `npm run snap -- 0.5,1.5 -o renders/snaps`. Stills are named `frame-NN-at-<seconds>s.png`, plus a `contact-sheet.jpg`. On its own, `hyperframes snapshot` also adds an end-of-timeline frame; `npm run snap` passes `--no-end`, so it captures only the `--at` times.

## Rendering on a machine with little free memory

`npm run render` uses several Chrome workers. If the render fails or the machine runs out of memory, render with one worker: `npm run render -- --workers 1`.

## Driving the frame from the timeline

The **setter** pattern works: the renderer seeks the paused timeline to each frame, and a tween on an object with an accessor property re-runs the setter with the value for that time.

```js
const clock = {
  get t() { return current; },
  set t(value) { current = value; draw(value); },
};
tl.to(clock, { t: duration, duration, ease: "none" }, 0);
```

HyperFrames also waits for asynchronous setup: the script may `await` loads before it builds the timeline and sets `window.__timelines["<composition id>"]`. An `<audio data-start data-duration>` clip is mixed into the MP4 at its start time.

## Telemetry

HyperFrames telemetry must stay off. On a fresh clone, before the first HyperFrames command, run `npx hyperframes telemetry disable` (it writes `"telemetryEnabled": false` to `~/.hyperframes/config.json`); check with `npx hyperframes telemetry status`. The npm scripts also set `DO_NOT_TRACK=1`, and any HyperFrames command run by hand should too (`HYPERFRAMES_NO_TELEMETRY=1` also works). Do not run `hyperframes publish`, `auth`, `cloud`, `lambda` or `feedback`.
