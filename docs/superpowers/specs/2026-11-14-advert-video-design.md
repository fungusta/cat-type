# Cat Type advert video — design

Status: awaiting approval. Date: 2026-11-14.

## Intent

A short advert that shows what Cat Type is by letting the cat do it: it pops
up, taps along to typing you can hear, changes outfits, and the video names
each selling point in a few words between the actions. It should feel quick
and punchy, like a product reveal, but cute and in Cat Type's own look.

## Goals

- Someone who has never heard of Cat Type understands it in the first 5
  seconds: a cat that types along with you.
- Three selling points land as words on screen, each followed by the cat
  showing it: customise, unlock outfits, track typing.
- Every frame uses the real cat and accessory artwork from `assets/`.
- Each key sound lands on the frame its paw lands.
- Timing, wording, and outfits are easy to change and re-render.

## Non-goals

- No voiceover.
- No recording of the real app or a real desktop.
- No changes to the app or the website.
- No upright (phone-shaped) version in the first pass. The layout is built so
  one can be added later.

## Anti-goals

- A generic dark "tech startup" look. It uses the site's cream, butter-yellow,
  rounded look.
- Showing anything the app does not do.
- Borrowing another product's art, sounds, or music.

## Approaches considered

1. **Record the real app and polish it.** Rejected: the cat is small on
   screen, close-ups go soft, and outfit changes would be done by hand during
   recording.
2. **Animate by hand in a motion design tool.** Rejected: paw taps and all
   outfits would be rebuilt by hand, and changes mean re-doing timeline work.
3. **Build the video in code and render it to a file.** Chosen by Peter. The
   cat and accessories are already SVG, and `site/js/cat.js` already dresses
   the cat the way the app does.

## Format (Claude's calls)

- 1920 × 1080, widescreen, 60 frames per second, about 27 seconds.
- Output: one MP4 with sound.
- Look: the website's — background `#fff9f3`, ink `#302a33`, butter `#f2d66b`,
  Nunito extra-bold for the words.

## Storyboard

Words on screen are Peter's phrases. Times are a starting point.

| # | Time | What you see | What you hear |
|---|------|--------------|---------------|
| 1 | 0–2s | Cream screen, one blinking text cursor. The cat pops up beside it with a small bounce. | Soft pop. |
| 2 | 2–7s | Close on the cat. A sentence types itself out: "Brighten up your day, one key at a time." Left-hand keys move the left paw, right-hand keys the right, space taps both. Typing speeds up and the cat switches to its excited face. | One key click per letter, a deeper one for space. |
| 3 | 7–8s | Words fill the screen: **Customise it.** | Whoosh in. |
| 4 | 8–13s | The cat stays centred and changes on each beat: coat colours first (gray → ginger → black & white), then outfits (wizard hat → sunglasses + red bandana → crown + royal cape). Swaps get faster. | A click-pop per swap. |
| 5 | 13–14s | **Unlock new outfits.** | Whoosh in. |
| 6 | 14–18s | The cat types. A keystroke counter races upward beside it. Three reward tiles unlock one after another (party hat, crown, dragon wings) and the cat ends up wearing them. | Fast key clicks, a chime per unlock. |
| 7 | 18–19s | **Track your productivity.** | Whoosh in. |
| 8 | 19–23s | The stats card from the site: Today / Last 7 days / All time count up, and the weekly bar chart grows bar by bar. The cat taps in the corner. | Soft tick per bar. |
| 9 | 23–27s | End card: the cat, "Cat Type", "Get it for Windows or Mac", and `fungusta.github.io/cat-type`. The cat does its happy lean with a heart. | Final pop, then silence. |

## Sound (Claude's calls)

- Sound effects only in the first version; the typing is the rhythm. A music
  bed can be added after Peter has seen it.
- Key clicks: several different single-key recordings, rotated so it does not
  sound like one sample on repeat.
- Sources must be free for commercial use. Prefer CC0. Each file's source and
  licence is recorded in `advert/SOUNDS.md`.

## How it is built (Claude's calls)

- Tool: HyperFrames (`hyperframes` on npm, Apache-2.0), which renders a web
  page timeline to MP4. Fallback if it gives trouble: Remotion.
- Location: a new `advert/` folder at the repo root with its own
  `package.json`. Nothing in it ships with the app or the site.
- The cat is drawn by reusing `site/js/cat.js` and the SVGs in
  `assets/vector-cats` and `assets/accessories`. A build step copies the ones
  the advert uses into a throwaway `advert/build/` folder, because the render
  tool only serves files inside its own project folder. No copies are
  committed.
- Paw poses are driven by the video's clock, not by the site's CSS timers, so
  every render comes out identical.
- One timeline file lists scenes, words, outfits, and key presses with their
  times. Sounds are placed from the same list and mixed into a single
  soundtrack file at build time, which is what keeps picture and sound in
  step.
- Accessories marked secret in the app (`hidden=True`) never appear, matching
  the rule the website build already enforces.
- Result is written to `advert/out/`, which is not committed.

## Left to the builder

- Exact easing, bounce, and camera moves.
- Which CC0 sound files.
- How the typed sentence maps to left and right paws (use the app's own
  keyboard split if it is easy to read from the code).

## Known needs

- `ffmpeg` is not installed on this Mac. If the render tool does not bring
  its own, it needs installing (Homebrew), with Peter's go-ahead.
