# Cat Type landing page v2 design

Supersedes `2026-09-11-cat-type-landing-page-design.md`. The earlier page lives
unmerged on `codex/cat-type-landing`; this design starts fresh from `main` and
does not build on that branch. Terms in **bold** are defined in `CONTEXT.md`.

## Intent

A minimal, cute page that sells Cat Type as a typing companion that brightens
your day. Its one job is the **primary download**: a visitor arrives, is
charmed, and leaves with the installer for their computer.

The three supporting promises are: customize the cat, unlock new clothing and
accessories, and track your typing.

## Goals, non-goals, anti-goals

Goals
- A first-time visitor understands what Cat Type is within the hero and can
  download it in one click.
- Each supporting promise is visible in its own **feature band**, carried by
  one picture and one sentence.
- What the page shows matches the app a visitor will actually install.

Non-goals
- A typing box or any keyboard demo. The hero cat performs on its own.
- A speech bubble or any words spoken by the cat.
- An accessory picker, a full wardrobe, or a full reward album.
- Dark mode. The app is light-only, so the page is too.
- A custom domain, analytics, or a newsletter.

Anti-goals (the page fails even if it works)
- It promises something the app does not do. In particular, it must not call
  typing activity a productivity score, and it must not imply focus, task, or
  goal tracking. (The Track subline may say it shows your most productive
  times, by the owner's choice.)
- It reveals or hints at secret rewards. No secret accessory, and no mystery
  tile or copy saying secrets exist.
- It looks like a generic SaaS template, or uses art that is not real Cat Type
  artwork.
- A visitor gives up at an operating-system hurdle nobody warned them about:
  Input Monitoring on Mac. (Windows SmartScreen goes unmentioned, by the
  owner's choice; the real fix is code signing.)

## Page structure

A short scroll, roughly three screens tall on desktop.

1. **Header.** Wordmark and a GitHub link.
2. **Hero.**
   - Headline: "Brighten up your day, one key at a time."
   - Subline: "A cute cat that sits by your cursor and taps along while you
     type. Dress it up, unlock new outfits, and see your typing week at a
     glance." Its three clauses introduce the three feature bands in order.
   - The **primary download** button, plus the Windows note when relevant (see
     Downloads).
   - The animated hero cat (see Hero cat).
3. **Customise band.** Six cat style chips and a **Mix it up** button acting on
   one cat. One sentence of copy.
4. **Unlock band** (the **unlock showcase**). Locker-style tiles: one earned
   reward and three locked ones with progress meters. Headline in the spirit of
   "Type more, unlock more." It must not mention secrets.
5. **Track band.** A miniature of the app's Metrics card: Today, Last 7 days and
   All time stat tiles, and a 7-day column chart with today's column in Butter
   Sun. Headline: "See your typing week at a glance." Subline: "Keystrokes by
   hour and day, so you know your most productive times." (The owner chose
   this wording, overriding the earlier "typing, not productivity" rule.)
6. **Footer.** Links to the three offered release files (Windows, Mac Apple
   Silicon, Mac Intel) with plain labels, a link to the GitHub repo, and a line
   saying typed text is never recorded.

## Hero cat

The cat SVG is inlined so CSS can animate its named parts (`paw-left`,
`paw-right`, `pads-*`, `eyes`, `mouth-idle`, `mouth-excited`; see
`assets/SPRITES.md`). No new artwork is drawn and no pre-rendered pose frames
are used.

It plays a gentle loop:
1. On load it **waves** hello: `paw-right` lifts and swings from its base.
2. It sits and blinks for a few seconds.
3. A short typing burst (paws dropping one after the other, as the app's tap
   poses do), then the excited mouth.
4. It waves again, leaning toward the download button.

Interactions: hovering over the cat makes it wave. Clicking it gives a happy
bounce with a small heart. Hovering or focusing the download button gives the
excited mouth.

With reduced motion requested, the cat sits still and blinks only. The page
reads fully without any animation.

The hero cat wears whatever cat style and outfit the visitor last made in the
Customise band. Before any choice, it is the gray cat with a starter outfit
(builder's pick).

## Customise band

- Six style chips: gray, ginger, charcoal, brown-tabby, white, black-and-white.
- **Mix it up** dresses the cat in a random outfit drawn only from **starter
  items**: up to one per slot, typically two or three items, never the same
  outfit twice in a row.
- With the current catalog the starter items are: ribbon clip, daisy clip,
  round glasses, sunglasses, bell collar, bow tie, beanie. There are no
  back-slot starter items.
- The visitor's choice carries to the hero cat and persists across reloads in
  `localStorage`. If storage is unavailable, the page still works with the
  default.
- Accessories layer as the app layers them (`cat_artwork._add_accessory`):
  back items behind the body, neckwear behind the paws, items marked
  `data-clip-to-body` clipped to the cat outline, and `data-render-layer="front"`
  groups in front. Starter items do not include back items today, but the
  layering must be correct for any slot.

## Unlock band

- Locker tiles styled like the app's **accessory locker**, with the app's
  meanings: Butter fill and a check mark mean *equipped*; locked tiles are faded
  grey with a padlock and a small progress meter.
- The beanie is shown equipped (the pretend user is wearing it), not merely
  earned, so the page never invents a tile state the app does not have. Settled
  by the designer.
- Content: beanie (equipped), party hat (50,000), crown (100,000) and dragon wings
  (500,000), each with its line from `ACCESSORY_BLURBS`.
- Every progress figure on the page comes from **one pretend first-week user**
  with about 10,500 keystrokes over 7 days. Unlock progress and Track figures
  must agree with each other and with the real unlock thresholds.
- No hover try-on, and no mystery tile.

## Track band

- Uses the same pretend user. The 7-day column total equals Last 7 days, and
  All time equals the ~10,500 keystrokes used in the Unlock band.
- Bars and the three tiles only: no tooltips and no per-point labels, matching
  the limits in the app's metrics design.

## Downloads

Every link uses `https://github.com/fungusta/cat-type/releases/latest/download/<file>`
so the page never needs editing per release. Offered files:
`Cat-Type-Windows-x64.exe`, `Cat-Type-macOS-arm64.dmg`, `Cat-Type-macOS-x64.dmg`.

**Linux is not offered on the landing page yet** (the owner's decision). The
releases still publish Linux archives, but the page does not link to them,
mention Linux, or promise it is "coming soon". The `<title>`, meta description
and copy name only Windows and Mac where platforms are named.

| Detected | Primary button | Secondary |
|---|---|---|
| Windows | "Download for Windows" → Windows x64 exe | none |
| macOS | "Download for Mac" → arm64 dmg | Input Monitoring note, and an "Intel Mac?" link → x64 dmg |
| Linux, phone or unknown | "Get it for Windows or Mac" → scrolls to footer | none |

Detection only changes the label, link and note. The footer always lists the
three offered files. Before scripts run, or without JavaScript, the page shows
the "Get it for Windows or Mac" behavior.

Windows visitors get no note. The owner removed the SmartScreen note; the
lasting fix is signing the Windows build so SmartScreen recognises it.
macOS builds are notarized, so Gatekeeper needs no note. But on first launch the
user must open Settings and choose **Enable Input Monitoring**, or the cat never
reacts to typing (README, "Install on macOS"). So Mac visitors get one calm line
under the button, along the lines of: "On first launch, choose Enable Input
Monitoring so your cat can hear you type." Each note shows only to its own
platform.

The page shows no version number, because it would go stale.

## Visual direction

The **website visual direction** is the app's toybox language:
- Neutral warm surfaces and dark ink.
- Rounded shelves with hairline borders and soft shadows.
- Pill buttons with small lift on hover.
- Butter Sun reserved for the primary download, selected chips, and earned or
  "today" elements.

Typography: a rounded humanist web font, or a system UI fallback. The page does
not depend on Segoe UI Variable or Avenir Next being installed.

Light only. Set `color-scheme: light` and an explicit body background so forced
dark modes do not invert the art. The white cat must stay readable against its
shelf.

Copy follows the **copy voice**: calm product language with occasional dry cat
asides.

## Single source of truth

The page must not drift from the app.
- Cat and accessory SVGs come from `assets/vector-cats/` and
  `assets/accessories/`.
- Accessory names, slots, thresholds and blurbs come from
  `cat_accessories.py`.
- Starter items are selected by rule, not by a hand-kept list:
  - visible (not `hidden`);
  - and either `metric == "keystrokes" and target <= 10_000`, or
    `metric == "days" and target <= 7`.
- A secret accessory must never reach the published site, in its data or its
  files.

How the site gets these (a build step run by the deploy workflow, committed
generated files guarded by a test, or another approach) is left to the builder.
Local preview must work without manual copying.

## Hosting

- GitHub Pages at `https://fungusta.github.io/cat-type/`.
- A `pages.yml` workflow deploys on pushes to `main` that touch the site or its
  sources, using `actions/upload-pages-artifact` and `actions/deploy-pages`.
- Only the site output is published; nothing else from the repo is.
- All asset paths are relative, because the site is served from `/cat-type/`.
- The repository owner enables Pages once (Settings → Pages → Source: GitHub
  Actions). Setting the repo homepage URL is optional and also the owner's step.

## Responsive and accessibility

- Works from 360px wide upward with no horizontal scroll. The hero stacks on
  narrow screens.
- Semantic buttons and links, visible focus in the app's Butter and ink ring
  style, and labels on the style chips.
- The cat is decorative (`aria-hidden`). Animations respect
  `prefers-reduced-motion`.

## Validation

- Check the page at desktop and phone widths.
- Check download labels, links and notes for Windows, Mac, Linux and phone
  (user agent overrides are fine).
- Confirm no Linux file or Linux mention appears on the page.
- Confirm Mix it up only ever uses starter items.
- Confirm no secret accessory appears in the published files.
- Confirm the pretend-user numbers agree across the bands.
- Check reduced motion, and check that the Pages artifact contains only the site.

## Left to the builder

- Exact spacing and type scale.
- The web font choice.
- Animation timings.
- Exact band copy beyond what is quoted here.
- The default starter outfit.
- The pretend user's daily distribution.
- The mechanism for pulling assets and catalog data into the site.
