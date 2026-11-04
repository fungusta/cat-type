# Cat Type Landing Page v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a short, cute, static landing page in `site/` that converts visitors into Windows or Mac downloads and is deployed to GitHub Pages.

**Architecture:**
- A Python build script, `scripts/build_site.py`, assembles `build/site/` from three sources: hand-written page files in `site/`, cat and accessory SVGs in `assets/`, and a generated `catalog.json` derived from `cat_accessories.py`.
  - This keeps the app as the single source of truth.
  - Secret accessories can never be published.
- In the browser, ES modules inline the cat SVGs. Accessories are layered the way `cat_artwork._add_accessory` does it, and named parts are animated with CSS.
- Pure decision logic lives in one module with no DOM access, so `node --test` can test it.

**Tech Stack:**
- Python 3.12 with `unittest`: the build script and its tests.
- Plain HTML, CSS, and JavaScript ES modules: no framework and no bundler.
- `node:test` on Node 22, with no dependencies.
- GitHub Actions Pages deploy.

**Spec:** `docs/superpowers/specs/2026-11-05-cat-type-landing-page-v2-design.md` (read it before starting any task)

## Global Constraints

- Work on branch `landing-page-v2`, never directly on `main`.
- Download URLs are exactly `https://github.com/fungusta/cat-type/releases/latest/download/<file>`.
- Offered files are exactly `Cat-Type-Windows-x64.exe`, `Cat-Type-macOS-arm64.dmg`, and `Cat-Type-macOS-x64.dmg`.
- Linux restrictions:
  - No Linux file, link, or the word "Linux" may appear anywhere in `build/site/`.
  - Do not say "coming soon".
- Starter item rule:
  - The item is not `hidden`.
  - And either `metric == "keystrokes" and target <= 10_000`, or `metric == "days" and target <= 7`.
- No `hidden` accessory may appear in `build/site/`, whether in data or as a file.
- Never use "productivity" in page copy. Never use "open source"; say "The source is public on GitHub."
- Never show or hint at secret rewards. No mystery tile.
- Copy is fixed by the spec and must be used verbatim:
  - Headline: `Brighten up your day, one keystroke at a time.`
  - Subline: `A cute cat that sits by your cursor and taps along while you type. Dress it up, unlock new outfits, and see your typing week at a glance.`
  - Track band: `See your typing week at a glance.` / `Keystrokes by hour and day. Only the counts, never what you type.`
  - Windows note: `Windows might say it doesn't recognise Cat Type yet. Choose More info, then Run anyway. The source is public on GitHub.`
  - Mac note: `On first launch, choose Enable Input Monitoring so your cat can hear you type.`
  - Fallback button: `Get it for Windows or Mac`
- Pretend first-week user: daily keystrokes `(1180, 1620, 940, 1850, 1410, 2060, 1440)`, oldest first with today last. That makes Today 1,440, Last 7 days 10,500, and All time 10,500.
- Light only:
  - Set `color-scheme: light` and give `body` an explicit background.
  - Butter Sun appears only on the primary download, selected chips, the equipped tile, and today's bar.
- All asset paths are relative. No leading `/`, because the site is served from `/cat-type/`.
- Do not show a version number on the page.

## Review Focus

1. **iPad visitors.** iPadOS Safari sends a desktop `Macintosh` user agent. A touch-screen "Mac" must get the fallback button, not a `.dmg`. Covered by `test_ipad_is_not_a_mac` in Task 2.
2. **Stale or hostile `localStorage`.** A saved choice may hold an unknown cat, a no-longer-starter item, a hidden accessory id, or bad JSON, or storage may throw on access. In every case the page must fall back to the default cat without errors. Covered by the `readChoice` tests in Task 2.
3. **Two inline cats on one page.** The hero and the Customise band both inline a cat. Duplicate SVG ids such as `body-clip` would make one cat's clip paths use the other's shapes. Covered by the duplicate-id check in Task 3.
4. **JavaScript off, or `catalog.json` failing to load.** The page must still read top to bottom: the fallback button, footer links that work, and both notes hidden. Covered by Task 5, Step 4.
5. **Mix it up repeating.** A random pick could repeat the current outfit, and the click would look broken. Covered by `test_next_outfit_never_repeats` in Task 2.

---

### Task 1: Site build script and catalog

**Files:**
- Create: `scripts/build_site.py`
- Create: `site/index.html` (placeholder `<!doctype html><title>Cat Type</title>`; Task 4 replaces it)
- Create: `tests/test_site_build.py`
- Modify: `scripts/run_ci_tests.py` (add `"tests.test_site_build"` to `TEST_MODULES`)

**Interfaces:**
- Produces: `scripts.build_site`, containing:
  - `starter_items() -> tuple[Accessory, ...]`
  - `SHOWCASE_IDS = ("beanie", "party-hat", "crown", "dragon-wings")`
  - `PRETEND_WEEK: tuple[int, ...]`
  - `catalog() -> dict`
  - `build_site(out_dir: Path = PROJECT_ROOT / "build" / "site") -> Path`
  - Run it with `python -m scripts.build_site`.
- Produces: `build/site/catalog.json`, with this shape:
  - `cats`: a list of the six `CAT_VARIANTS` ids.
  - `starters`: a list of `{id, name, slot}`.
  - `showcase`: a list of `{id, name, blurb, target, metric, progress, equipped}`.
    - `progress` is an int percentage from 0 to 100, computed from `sum(PRETEND_WEEK)` for keystrokes items.
    - `equipped` is true only for `beanie`.
  - `week`: `PRETEND_WEEK` as a list.
  - `today`, `last7`, `allTime`: ints.
- Produces these files under `build/site/`:
  - `assets/cats/<variant>.svg`
  - `assets/accessories/<id>.svg`, only for starter and showcase ids.
  - Everything in `site/` except a `site/tests/` folder.

- [ ] **Step 1: Branch**

Run: `git switch -c landing-page-v2`

- [ ] **Step 2: Write the failing tests in `tests/test_site_build.py`**

Write these `unittest` tests:
- `test_starter_items_follow_the_rule`: the starter ids are exactly `{"ribbon-clip", "round-glasses", "bell-collar", "bow-tie", "beanie", "daisy-clip", "sunglasses"}`.
- `test_starter_rule_never_admits_hidden_items`: patch `scripts.build_site.ACCESSORIES` to add a hidden item with `metric="keystrokes", target=10`, and assert it is excluded.
- `test_pretend_week_matches_spec`: `sum(PRETEND_WEEK) == 10_500`, `len(PRETEND_WEEK) == 7`, and in `catalog()`, `today == 1440`, `last7 == allTime == 10_500`.
- `test_showcase_progress_agrees_with_thresholds`: in `catalog()["showcase"]`:
  - `beanie` is `progress == 100, equipped is True`;
  - `party-hat` is 21, `crown` is 10 (floor of 10.5), and `dragon-wings` is 2;
  - each blurb equals `ACCESSORY_BLURBS[id]`.
- `test_build_publishes_no_hidden_or_linux_content`, using a temp out dir with `build_site(tmp)`:
  - no file stem under `assets/accessories` is a hidden id;
  - the text of every `.html`, `.css`, `.js`, `.json` and `.svg` file contains neither `"Linux"` nor any hidden id;
  - `catalog.json` parses.
- `test_build_copies_all_six_cats_and_excludes_site_tests`: six SVGs in `assets/cats`, and no `tests` directory in the output.

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m unittest tests.test_site_build -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.build_site'`

- [ ] **Step 4: Implement `scripts/build_site.py`**

- Import `ACCESSORIES` and `ACCESSORY_BLURBS` from `cat_accessories`, and `CAT_VARIANTS` from `cat_settings`.
- `build_site` deletes and recreates `out_dir`, copies `site/` with `shutil.copytree` while ignoring `tests`, then copies the SVGs and writes `catalog.json` (UTF-8, indent 2).
- Progress is `min(100, total * 100 // target)`.
- Add a `__main__` block that prints the output path.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest tests.test_site_build -v`
Expected: 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/build_site.py scripts/run_ci_tests.py tests/test_site_build.py site/index.html
git commit -m "feat: build landing page catalog from the accessory source"
```

---

### Task 2: Pure page logic

**Files:**
- Create: `site/js/logic.js`
- Create: `site/tests/logic.test.mjs`

**Interfaces:**
- Produces (all named exports, none of which touch the DOM):
  - `RELEASE_BASE = "https://github.com/fungusta/cat-type/releases/latest/download/"`
  - `platformFor({userAgent: string, maxTouchPoints: number}) -> "windows" | "mac" | "other"`
  - `downloadFor(platform) -> {label: string, href: string, note: string | null, secondary: {label, href} | null}`
    - `windows`: `"Download for Windows"`, the exe, and the Windows note.
    - `mac`: `"Download for Mac"`, the arm64 dmg, the Mac note, and secondary `{label: "Intel Mac?", href: <x64 dmg>}`.
    - `other`: `"Get it for Windows or Mac"`, `"#download"`, no note, and no secondary.
  - `nextOutfit(starters, previous, random = Math.random) -> {ears?, glasses?, neck?, hat?}`
    - Picks at most one item per slot, with 2 or 3 items in total.
    - Never deep-equals `previous`.
    - `random` is injectable.
  - `DEFAULT_CHOICE = {cat: "gray", outfit: {hat: "beanie", neck: "bow-tie"}}`
  - `readChoice(storage, catalog) -> {cat, outfit}`
  - `writeChoice(storage, choice) -> void`
    - The storage key is `"cat-type-choice"`.
    - Both functions catch every storage error.

- [ ] **Step 1: Write the failing tests in `site/tests/logic.test.mjs`**

Use `node:test` and `node:assert/strict`. Write these tests:
- `test_windows_detection`: a Windows 11 Chrome UA gives `"windows"`.
- `test_mac_detection`: the Mac Safari UA `"Macintosh; Intel Mac OS X 10_15_7"` with `maxTouchPoints: 0` gives `"mac"`.
- `test_ipad_is_not_a_mac`: the same UA with `maxTouchPoints: 5` gives `"other"`.
- `test_linux_and_phones_are_other`: an X11 Linux UA, an Android UA, and an iPhone UA all give `"other"`.
- `test_download_targets`:
  - The `href` and `secondary.href` values equal `RELEASE_BASE` plus the exact file names.
  - `note` equals the exact strings in Global Constraints.
  - `downloadFor("other").href === "#download"`.
- `test_next_outfit_never_repeats`: with a `random` stub that always returns 0, call it 20 times in a row, feeding each result back in as `previous`. No two consecutive results are equal, every id is in `starters`, and each result has 2 or 3 items.
- `test_read_choice_rejects_bad_saved_state`. Each of these returns `DEFAULT_CHOICE`:
  - malformed JSON;
  - an unknown `cat`;
  - an outfit containing `"crown"` (not a starter);
  - an outfit containing `"moon-pendant"` (hidden);
  - an item placed in the wrong slot;
  - a storage whose `getItem` throws.
- `test_read_choice_round_trips_valid_state`: `writeChoice`, then `readChoice`, returns the same choice. `writeChoice` on a storage whose `setItem` throws does not throw.

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test site/tests/`
Expected: FAIL with `Cannot find module` for `site/js/logic.js`

- [ ] **Step 3: Implement `site/js/logic.js`**

`platformFor` treats everything that is not Windows or a non-touch Mac as `"other"`. Do not match on the string `Linux`: `logic.js` is published, and Task 1's test forbids that word anywhere in `build/site/`. `nextOutfit` should shuffle with `random`. If the result equals `previous`, rotate deterministically to a different combination rather than looping. `readChoice` validates each saved slot against `catalog.starters`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test site/tests/`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add site/js/logic.js site/tests/logic.test.mjs
git commit -m "feat: add landing page download and outfit logic"
```

---

### Task 3: Cat composition and animation

**Files:**
- Create: `site/js/cat.js`
- Create: `site/cat.css`

**Interfaces:**
- Consumes: `build/site/assets/cats/*.svg` and `build/site/assets/accessories/*.svg` (Task 1).
- Produces:
  - `async renderCat(container: Element, {cat, outfit}, idPrefix: string, assetBase = "assets/") -> SVGSVGElement`. It fetches `${assetBase}cats/<cat>.svg` and `${assetBase}accessories/<id>.svg` (text cached per URL), parses them with `DOMParser`, and replaces `container`'s children.
  - `wave(svg)`, `burst(svg)`, `happy(svg)`. Each adds and then removes a CSS class: `is-waving`, `is-typing`, or `is-happy`.
  - `startHeroLoop(svg) -> () => void`. It returns a stop function.

Layering must port `cat_artwork._add_accessory` exactly:
- `back` is inserted first.
- `neck` goes immediately before `#paw-left`.
- Every other slot is appended.
- Groups with `data-render-layer="front"` move into a sibling inserted before `#paw-left`.
- Elements with `data-clip-to-body="true"` get a `clipPath` built from `#outline`'s `d`.
- `<title>` and `<desc>` are dropped.

After layering, rewrite every `id` to `${idPrefix}-${id}`, and every `url(#x)` and `href="#x"` reference to match.

Add `aria-hidden="true"` to the SVG. Animation CSS targets the prefixed ids through classes that `renderCat` adds to parts:
- `cat-paw-left`
- `cat-paw-right`
- `cat-eyes`
- `cat-mouth-idle`
- `cat-mouth-excited`

Set `transform-box: fill-box` and `transform-origin: 50% 100%` on the paws.

Hero loop, per the spec's Hero cat section:
1. Wave on load.
2. Blink every few seconds.
3. Burst, then show the excited mouth.
4. Wave again, leaning toward the download button.

Under `prefers-reduced-motion: reduce`, only blinking runs.

- [ ] **Step 1: Add a scratch harness**

Create `site/tests/cat-harness.html` (excluded from the build by Task 1). It renders two cats into one page:
- `gray` with `{hat: "beanie", neck: "bow-tie"}`, prefix `a`.
- `white` with `{ears: "daisy-clip", glasses: "sunglasses", neck: "bell-collar"}`, prefix `b`.

- [ ] **Step 2: Serve it and verify it fails before `cat.js` exists**

Run: `python -m scripts.build_site`, then `python -m http.server 8765 -d .` from the repo root, and open `http://localhost:8765/site/tests/cat-harness.html`.
Expected: a console error about `cat.js`.

- [ ] **Step 3: Implement `site/js/cat.js` and `site/cat.css`**

The harness passes `assetBase = "../../build/site/assets/"`.

- [ ] **Step 4: Verify in the browser**

In the page console, check each of these:
- `[...document.querySelectorAll('[id]')].map(e => e.id)` has no duplicates.
- Both cats show their accessories.
- The bow tie and bell collar sit behind the paws: `#a-paw-left` comes after `#a-accessory-neck` in document order.
- The white cat's ear accessories and sunglasses are visible.
- Calling `wave()` on each SVG visibly lifts the right paw from its base, and it does not fly off to the top-left.
- With reduced motion emulated, `startHeroLoop` only blinks.

Take a screenshot of each cat.

- [ ] **Step 5: Commit**

```bash
git add site/js/cat.js site/cat.css site/tests/cat-harness.html
git commit -m "feat: compose and animate inline cats for the landing page"
```

---

### Task 4: Page markup and toybox styles

**Files:**
- Modify: `site/index.html` (replace the placeholder)
- Create: `site/styles.css`
- Copy: `assets/cat-type.png` → `site/favicon.png`

**Interfaces:**
- Produces these DOM hooks for Task 5. The `id`s are exact:
  - `#hero-cat`
  - `#primary-download` (an `<a>`; its default `href="#download"` and text `Get it for Windows or Mac`)
  - `#download-note` (hidden by default)
  - `#download-secondary` (hidden by default)
  - `#style-chips` (six `<button aria-pressed>` with `data-cat` ids)
  - `#mix-it-up`
  - `#customise-cat`
  - `#unlock-tiles`
  - `#track-stats`
  - `#track-chart`
  - `#download` (the footer download list)

Page structure follows the spec's Page structure section:
- Header: wordmark and a link to `https://github.com/fungusta/cat-type`.
- Hero: copy, button, note, and the cat stage.
- Customise, Unlock, and Track bands.
- Footer, which contains:
  - three static `<a>` download links with full URLs (Windows; Mac, Apple Silicon; Mac, Intel);
  - a GitHub repo link;
  - `Cat Type never records what you type.`

Write the Customise and Unlock band copy in the spec's **copy voice**. The Unlock headline should be in the spirit of "Type more, unlock more."

`<head>` contents:
- `<title>Cat Type — Brighten up your day, one keystroke at a time</title>`
- A meta description naming Windows and Mac only.
- `<link rel="icon" href="favicon.png">`
- `<meta name="color-scheme" content="light">`
- One Google Fonts rounded humanist family with a system UI fallback stack. The family is your choice; Nunito is fine.

Styles:
- Define the toybox tokens as CSS custom properties on `:root`: warm neutral surface, ink, hairline, shelf shadow, and Butter Sun accent.
- Shelves have a hairline border and a soft shadow.
- Use pill buttons with about a 120ms hover lift.
- Use the app's Butter and ink focus ring.
- The hero stacks below 760px.
- There must be no horizontal scroll at 360px.
- The white cat's stage must use a shelf surface darker than the page.

- [ ] **Step 1: Write markup and styles**

Write the markup and styles. Use no JavaScript yet; leave the bands' dynamic containers empty, with a sensible static fallback in each. The Track band, for example, shows the three stat tiles with fixed numbers.

- [ ] **Step 2: Build and verify with JavaScript disabled**

Run: `python -m scripts.build_site`, then serve with `python -m http.server 8765 -d build/site`.

With JavaScript disabled in the browser, check each of these:
- The page reads top to bottom.
- The button says `Get it for Windows or Mac` and jumps to `#download`.
- The three footer links point at the exact release URLs.
- No note is visible.
- No horizontal scroll at 360px wide.

Take screenshots at 1280px and 360px.

- [ ] **Step 3: Run the build tests**

Run: `python -m unittest tests.test_site_build -v`
Expected: PASS. This proves no "Linux" text and no hidden ids reached the page.

- [ ] **Step 4: Commit**

```bash
git add site/index.html site/styles.css site/favicon.png
git commit -m "feat: lay out the landing page in the app's toybox style"
```

---

### Task 5: Wire up the page

**Files:**
- Create: `site/js/main.js`, loaded with `<script type="module" src="js/main.js">`
- Modify: `site/index.html` (add the script tag only)

**Interfaces:**
- Consumes: Task 2's `platformFor`, `downloadFor`, `nextOutfit`, `readChoice`, `writeChoice`, and `DEFAULT_CHOICE`; Task 3's `renderCat`, `startHeroLoop`, `wave`, and `happy`; Task 4's DOM hooks; and Task 1's `catalog.json`.

Behavior:
1. Fill the primary download from `downloadFor(platformFor(navigator))`, and reveal the note and secondary link when they are present.
2. Fetch `catalog.json`. If that fails, stop quietly and leave the static page as it is.
3. Render the saved choice (`readChoice(localStorage, catalog)`) into both `#hero-cat` (prefix `hero`) and `#customise-cat` (prefix `custom`), then start the hero loop.
4. Hero interactions:
   - Hovering the hero cat calls `wave`.
   - Clicking it calls `happy`, with a small heart.
   - Hovering or focusing `#primary-download` shows the excited mouth.
5. Style chips: set `aria-pressed`, re-render both cats, and `writeChoice`.
6. `#mix-it-up`: `nextOutfit(catalog.starters, current.outfit)`, then re-render both cats, `writeChoice`, and `happy` on the Customise cat.
7. Unlock tiles: render them from `catalog.showcase`.
   - Equipped tiles get the Butter fill and a check mark.
   - Locked tiles are faded grey, with a padlock, a meter set to `progress`, and the line `<target> keystrokes`.
   - Each tile shows its accessory image (`assets/accessories/<id>.svg`) and its blurb.
8. Track band:
   - Stats are `today`, `last7`, and `allTime`, formatted with `toLocaleString("en")`.
   - The chart has seven columns from `week`, scaled to the maximum, with only the last column in Butter.
   - It has no tooltips and no per-bar labels.
   - Weekday initials sit under the bars, with today's bar labelled `Today`.

- [ ] **Step 1: Implement `site/js/main.js`**

- [ ] **Step 2: Build, serve, and verify each platform in the browser**

Override the user agent per check, using the browser tooling's emulation or a `?ua=` debug hook that you delete before committing.

| User agent | Label | `href` ends | Note | Secondary |
|---|---|---|---|---|
| Windows | `Download for Windows` | `Cat-Type-Windows-x64.exe` | Windows note | none |
| Mac | `Download for Mac` | `Cat-Type-macOS-arm64.dmg` | Mac note | `Intel Mac?` → `Cat-Type-macOS-x64.dmg` |
| iPad (Mac UA + touch) | `Get it for Windows or Mac` | `#download` | none | none |
| Linux | `Get it for Windows or Mac` | `#download` | none | none |
| Android | `Get it for Windows or Mac` | `#download` | none | none |

- [ ] **Step 3: Verify the bands**

- Click each style chip. Both cats change, and exactly one chip has `aria-pressed="true"`.
- Click Mix it up 15 times. The outfit changes every time, and every equipped accessory id is one of the 7 starter ids.
- Reload. The choice persists.
- Unlock shows the beanie equipped and the party hat (21%), crown (10%), and dragon wings (2%) locked.
- Track shows 1,440, 10,500, and 10,500, with seven bars and only the last in Butter.

- [ ] **Step 4: Verify the failure paths**

- Rename `build/site/catalog.json` and reload. There are no uncaught errors, and the static page and download button still work.
- In the console, run `localStorage.setItem("cat-type-choice", "{bad")` and reload. The default gray cat appears.
- With reduced motion emulated, the hero only blinks.

- [ ] **Step 5: Run all page and build tests**

Run: `node --test site/tests/` and `python -m unittest tests.test_site_build -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add site/js/main.js site/index.html
git commit -m "feat: bring the landing page cat, downloads, and bands to life"
```

---

### Task 6: GitHub Pages deploy and glossary check

**Files:**
- Create: `.github/workflows/pages.yml`
- Modify: `README.md` (add one line near the top linking `https://fungusta.github.io/cat-type/`)

**Interfaces:**
- Consumes: `python -m scripts.build_site` (Task 1) and `node --test site/tests/` (Task 2).

`pages.yml` requirements:
- Triggers:
  - `push` to `main` with `paths`: `site/**`, `assets/vector-cats/**`, `assets/accessories/**`, `cat_accessories.py`, `cat_settings.py`, `scripts/build_site.py`, and `.github/workflows/pages.yml`;
  - plus `workflow_dispatch`.
- `permissions`: `contents: read`, `pages: write`, `id-token: write`.
- `concurrency: {group: pages, cancel-in-progress: true}`.
- Build job:
  1. checkout;
  2. `actions/setup-python` 3.12;
  3. `pip install -r requirements.txt`;
  4. `node --test site/tests/`;
  5. `python -m unittest tests.test_site_build`;
  6. `python -m scripts.build_site`;
  7. `actions/upload-pages-artifact` with `path: build/site`.
- Deploy job: `actions/deploy-pages`, with environment `github-pages`.
- Pin each action to its current major version, in the same style as `build.yml`.

- [ ] **Step 1: Write `pages.yml` and the README line**

- [ ] **Step 2: Validate the workflow locally**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/pages.yml'))"`, or use `actionlint` if it is installed.
Expected: no error.

- [ ] **Step 3: Check the artifact contents**

Run: `python -m scripts.build_site` and list `build/site`.
Expected: only `index.html`, `styles.css`, `cat.css`, `favicon.png`, `catalog.json`, `js/`, and `assets/`. No `tests/` folder.

- [ ] **Step 4: Run the full CI suite**

Run: `python scripts/run_ci_tests.py`
Expected: PASS, including `tests.test_site_build`.

- [ ] **Step 5: Check the glossary**

Re-read `CONTEXT.md` under "Website intent". Every term the page uses (primary download, feature band, starter item, unlock showcase, typing activity, wave) must match what was built. Fix any drift in `CONTEXT.md` only. Do not add implementation detail.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/pages.yml README.md CONTEXT.md
git commit -m "ci: deploy the landing page to GitHub Pages"
```

After the merge, the repository owner must set **Settings → Pages → Source: GitHub Actions** before the first deploy can succeed. Report this to them; do not change the setting yourself.
