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
