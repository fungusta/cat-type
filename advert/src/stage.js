// The advert's stage: dresses the cats, then builds one paused GSAP timeline that the
// renderer seeks frame by frame. Bundled as an IIFE; GSAP is the global from js/gsap.min.js.
//
// Two layers set what is on screen:
// - applyFrame(t) sets everything that frameState(t) and the current scene decide (look, paws,
//   face, typed text, where the cat stands, what part of the stage shows, counter, tiles,
//   stats and bars).
//   A frame driver tween re-runs it on every seek, so frames can be asked for in any order.
// - Scene functions add their own tweens (camera, pops, caret, squashes, hop, heart) to the timeline at
//   fixed times. GSAP only tweens elements and properties that applyFrame never sets.
// To add a scene, write a function that takes the timeline and add it to SCENES below.
//
// HyperFrames shows and hides the clips (#scene-stage and the .card sections) by their data-start.

import { renderCat } from "../../site/js/cat.js";
import { ARRIVE_POP, CARDS, DURATION, END, END_BEATS, LOOKS, LOOK_CHANGES, SCENES as TIMES, STATS, TYPED_TEXT, UNLOCKS, WIDTH, frameState, presses } from "./timeline.mjs";

// Camera scale for the wide opening shot; 1 is the close shot the CSS lays out.
const CAMERA_WIDE = 0.6;
const CAMERA_CLOSE = 1;
// When the camera starts pushing in (s); no sound marks it.
const CAMERA_PUSH = 1.4;

const CARET_BLINK = 0.5;
const TYPE_START = presses().find((press) => press.scene === "type").t;

// Where #cat-spot puts the cat in each scene, as a move (px) and a scale about the cat's centre.
const HOME = { x: 0, y: 0, scale: 1 };
const CAT_SPOTS = {
  customise: { x: 0, y: 73, scale: 1.35 },
  unlock: { x: -440, y: 73, scale: 1 },
  track: { x: 780, y: 380, scale: 0.4 },
  end: { x: 0, y: -97, scale: 0.6 },
};
const TYPED_LINE_SCENES = new Set(["arrive", "type"]);

// The website's padlock and a matching tick, for the tile badges.
const PADLOCK = '<svg class="badge-lock" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M5 7V5a3 3 0 0 1 6 0v2h.5A1.5 1.5 0 0 1 13 8.5v5a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 3 13.5v-5A1.5 1.5 0 0 1 4.5 7H5Zm1.5 0h3V5a1.5 1.5 0 0 0-3 0v2Z"/></svg>';
const TICK = '<svg class="badge-tick" viewBox="0 0 16 16" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" d="M3.5 8.5l3 3 6-7"/></svg>';
const TILE_ART_PAD = 6;
// Clear space each word card keeps on either side of the frame.
const CARD_MARGIN = 120;

let looks = [];
let typed = null;
let stage = {};

/** The SCENES key whose [start, end) holds t; the last scene from its end on. */
export function sceneAt(t) {
  const names = Object.keys(TIMES);
  return names.find((name) => t >= TIMES[name][0] && t < TIMES[name][1]) ?? names.at(-1);
}

/** Sets every frameState- and scene-driven property for time t. Reads no previous DOM state. */
export function applyFrame(t) {
  const state = frameState(t);
  const scene = sceneAt(t);
  applyCat(state, scene);
  applyTypedLine(state, scene);
  applyUnlockUi(state, scene);
  applyTrackUi(state, scene);
  stage.endCard.style.visibility = scene === "end" ? "visible" : "hidden";
}

function applyCat(state, scene) {
  const pressed = state.pawLeft > 0 || state.pawRight > 0;
  for (const look of looks) {
    look.element.style.visibility = look.key === state.look ? "visible" : "hidden";
    look.pawLeft.style.transform = `scaleY(${1 - 0.34 * state.pawLeft})`;
    look.pawRight.style.transform = `scaleY(${1 - 0.34 * state.pawRight})`;
    for (const pads of look.pads) pads.style.display = pressed ? "none" : "";
    look.svg.classList.toggle("is-excited", state.excited);
  }
  const spot = CAT_SPOTS[scene] ?? HOME;
  stage.catSpot.style.transform = `translate(${spot.x}px, ${spot.y}px) scale(${spot.scale})`;
}

function applyTypedLine(state, scene) {
  stage.typedLine.style.visibility = TYPED_LINE_SCENES.has(scene) ? "visible" : "hidden";
  typed.textContent = TYPED_TEXT.slice(0, state.typedChars);
}

function applyUnlockUi(state, scene) {
  stage.unlockUi.style.visibility = scene === "unlock" ? "visible" : "hidden";
  stage.counter.textContent = state.counter.toLocaleString("en");
  for (const tile of stage.tiles) tile.classList.toggle("is-unlocked", state.unlocked.includes(tile.dataset.id));
}

function applyTrackUi(state, scene) {
  stage.trackUi.style.visibility = scene === "track" ? "visible" : "hidden";
  for (const stat of stage.stats) stat.textContent = state.stats[stat.dataset.stat].toLocaleString("en");
  stage.barFills.forEach((fill, i) => { fill.style.transform = `scaleY(${state.bars[i]})`; });
}

/** Renders the cats, fills the cards and tiles, and waits for the fonts. */
async function setup() {
  typed = document.getElementById("typed");
  stage = {
    catSpot: document.getElementById("cat-spot"),
    typedLine: document.getElementById("typed-line"),
    unlockUi: document.getElementById("unlock-ui"),
    counter: document.getElementById("counter"),
    tiles: [],
    trackUi: document.getElementById("track-ui"),
    stats: [...document.querySelectorAll("#stats dd[data-stat]")],
    barFills: renderBars(),
    endCard: document.getElementById("end-card"),
  };
  document.getElementById("typed-ghost").textContent = TYPED_TEXT;
  assertDurations();
  fillCards();
  document.getElementById("end-title").textContent = END.title;
  document.getElementById("end-line").textContent = END.line;
  document.getElementById("end-url").textContent = END.url;
  const [rendered, tiles] = await Promise.all([renderLooks(), renderTiles()]);
  looks = rendered;
  stage.tiles = tiles;
  await Promise.all([document.fonts.load('800 160px "Nunito"'), document.fonts.load('700 160px "Nunito"')]);
  if (!document.fonts.check('800 72px "Nunito"') || !document.fonts.check('700 24px "Nunito"')) {
    throw new Error("Nunito did not load");
  }
  assertCardsFit();
  assertStatsFit();
}

/** Throws, naming it, unless the root, #scene-stage and #soundtrack each last DURATION seconds. */
function assertDurations() {
  for (const id of ["root", "scene-stage", "soundtrack"]) {
    const element = document.getElementById(id);
    if (!element || Number(element.dataset.duration) !== DURATION) {
      throw new Error(`#${id} must have data-duration="${DURATION}" (DURATION in timeline.mjs)`);
    }
  }
}

/** Puts each card's words into its section, checking the section's clip timing matches CARDS. */
function fillCards() {
  for (const card of CARDS) {
    const section = document.getElementById(card.id);
    if (!section || Number(section.dataset.start) !== card.start || Number(section.dataset.duration) !== card.duration) {
      throw new Error(`#${card.id} must be a .card clip with data-start="${card.start}" data-duration="${card.duration}"`);
    }
    section.querySelector(".card-text").textContent = card.text;
  }
}

/** The advance width of text in element's computed font, plus its side padding when asked. */
function textWidth(element, text = element.textContent, withPadding = false) {
  const style = getComputedStyle(element);
  const context = document.createElement("canvas").getContext("2d");
  context.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
  const padding = withPadding ? parseFloat(style.paddingLeft) + parseFloat(style.paddingRight) + parseFloat(style.borderLeftWidth) * 2 : 0;
  return context.measureText(text).width + padding;
}

/** Throws, naming it, if a card's words or an end-card line are wider than the frame less CARD_MARGIN a side. */
function assertCardsFit() {
  const limit = WIDTH - 2 * CARD_MARGIN;
  const lines = [
    ...CARDS.map((card) => [card.id, document.querySelector(`#${card.id} .card-text`)]),
    ...["end-title", "end-line", "end-url"].map((id) => [id, document.getElementById(id)]),
  ];
  for (const [id, element] of lines) {
    const width = textWidth(element, element.textContent, true);
    if (width > limit) throw new Error(`#${id} "${element.textContent}" is ${Math.ceil(width)} px wide; cards must fit in ${limit} px`);
  }
}

/** Throws if a stat's final number would be wider than its block. */
function assertStatsFit() {
  for (const stat of stage.stats) {
    const text = STATS[stat.dataset.stat].toLocaleString("en");
    const width = textWidth(stat, text);
    if (width > stat.clientWidth) throw new Error(`stat "${text}" is ${Math.ceil(width)} px wide; its block holds ${stat.clientWidth} px`);
  }
}

/** One .bar per STATS.labels entry in #chart (the last is today's, in butter); returns the fills. */
function renderBars() {
  const chart = document.getElementById("chart");
  return STATS.labels.map((label, i) => {
    const bar = document.createElement("div");
    bar.className = i === STATS.labels.length - 1 ? "bar bar-today" : "bar";
    bar.innerHTML = '<div class="bar-fill"></div><p class="bar-label"></p>';
    bar.querySelector(".bar-label").textContent = label;
    chart.append(bar);
    return bar.querySelector(".bar-fill");
  });
}

/** One .look per LOOKS key in #cat-rig, each dressed by renderCat. */
function renderLooks() {
  const rig = document.getElementById("cat-rig");
  return Promise.all(Object.entries(LOOKS).map(([key, look]) => {
    const element = document.createElement("div");
    element.className = "look";
    element.dataset.look = key;
    rig.append(element);
    return renderCat(element, look, `look-${key}`, "assets/").then((svg) => ({
      key,
      element,
      svg,
      pawLeft: svg.querySelector(".cat-paw-left"),
      pawRight: svg.querySelector(".cat-paw-right"),
      pads: [...svg.querySelectorAll(".cat-pads")],
    }));
  }));
}

/** One .tile[data-id] per UNLOCKS entry: the accessory's own art, its name and a badge. */
function renderTiles() {
  const list = document.getElementById("tiles");
  return Promise.all(UNLOCKS.map(async (unlock) => {
    const tile = document.createElement("li");
    tile.className = "tile";
    tile.dataset.id = unlock.id;
    tile.innerHTML = `<div class="tile-art"></div><p class="tile-name"></p><span class="tile-badge">${PADLOCK}${TICK}</span>`;
    tile.querySelector(".tile-name").textContent = unlock.name;
    list.append(tile);
    await inlineAccessory(tile.querySelector(".tile-art"), unlock.id);
    return tile;
  }));
}

/** Inlines assets/accessories/<id>.svg without ids (so none clash with the cats') and crops it to its art. */
async function inlineAccessory(holder, id) {
  const url = `assets/accessories/${id}.svg`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not load ${url}`);
  const svg = new DOMParser().parseFromString(await response.text(), "image/svg+xml").documentElement;
  svg.querySelectorAll("[id]").forEach((element) => element.removeAttribute("id"));
  svg.querySelectorAll("title, desc").forEach((element) => element.remove());
  svg.setAttribute("aria-hidden", "true");
  const inline = document.importNode(svg, true);
  holder.append(inline);
  const box = inline.getBBox();
  if (!box.width || !box.height) throw new Error(`Could not measure ${url}`);
  const pad = TILE_ART_PAD;
  inline.setAttribute("viewBox", `${box.x - pad} ${box.y - pad} ${box.width + pad * 2} ${box.height + pad * 2}`);
  inline.removeAttribute("width");
  inline.removeAttribute("height");
}

/** One tween over the whole advert whose setter calls applyFrame on every seek. */
function frameDriver(tl) {
  let current = 0;
  const clock = {
    get t() { return current; },
    set t(value) { current = value; applyFrame(value); },
  };
  tl.fromTo(clock, { t: 0 }, { t: DURATION, duration: DURATION, ease: "none" }, 0);
}

/**
 * A quick squeeze and settle that starts and ends at rest, so seeking either way leaves no residue.
 * immediateRender is off so building the timeline does not leave the target squeezed before `at`.
 */
function pop(tl, target, at, squeezed, settle) {
  const quiet = { immediateRender: false };
  tl.fromTo(target, { scaleX: 1, scaleY: 1 }, { ...squeezed, ...quiet, duration: 0.07, ease: "power2.out" }, at);
  tl.fromTo(target, squeezed, { scaleX: 1, scaleY: 1, ...quiet, duration: settle, ease: "back.out(3)" }, at + 0.07);
}

/** Each card's words rise about 40 px and fade in as its clip starts. */
function cardWords(tl) {
  for (const card of CARDS) {
    tl.fromTo(`#${card.id} .card-text`, { y: 40, opacity: 0 }, { y: 0, opacity: 1, duration: 0.25, ease: "power2.out" }, card.start);
  }
}

/** Scene 1 (0-2 s): a blinking caret, the cat pops up, the camera pushes in. */
function arriveScene(tl) {
  const [start] = TIMES.arrive;
  for (let t = start, on = true; t < TYPE_START; t += CARET_BLINK, on = !on) {
    tl.set("#caret", { opacity: on ? 1 : 0 }, t);
  }
  tl.fromTo("#cat-rig", { scale: 0 }, { scale: 1, duration: 0.35, ease: "back.out(2.2)" }, ARRIVE_POP);
  tl.fromTo("#camera", { scale: CAMERA_WIDE }, { scale: CAMERA_CLOSE, duration: 0.8, ease: "power2.inOut" }, CAMERA_PUSH);
}

/** Scene 2 (2-7 s): the sentence types itself (applyFrame); the caret stops blinking and follows it. */
function typeScene(tl) {
  tl.set("#caret", { opacity: 1 }, TYPE_START);
}

/** Scene 4 (8-13 s): the cat, centred and large (applyFrame), squashes as each outfit lands. */
function customiseScene(tl) {
  const [start, end] = TIMES.customise;
  for (const change of LOOK_CHANGES.filter((change) => change.t > start && change.t < end)) {
    pop(tl, "#cat-rig", change.t, { scaleX: 1.12, scaleY: 0.88 }, 0.18);
  }
}

/** Scene 6 (14-18 s): the counter climbs (applyFrame); each tile pops as it unlocks. */
function unlockScene(tl) {
  for (const unlock of UNLOCKS) {
    pop(tl, `.tile[data-id="${unlock.id}"]`, unlock.t, { scaleX: 1.12, scaleY: 1.12 }, 0.25);
  }
}

/** Scene 8 (19-23 s): the card rises in; the numbers count and the bars grow (applyFrame). */
function trackScene(tl) {
  const [start] = TIMES.track;
  tl.fromTo("#track-card", { y: 40, opacity: 0 }, { y: 0, opacity: 1, duration: 0.3, ease: "power2.out" }, start);
}

/**
 * Scene 9 (23-27 s): the brand cat pops in, the words follow, then the cat hops (site cat-hop) and a
 * heart rises and fades (site cat-heart). Every step is a fromTo from the previous step's end, so a
 * seek to any time, either way, shows the right pose. Nothing moves after 26.2 s.
 */
function endScene(tl) {
  const quiet = { immediateRender: false };
  const cat = '.look[data-look="brand"]';
  tl.fromTo(cat, { scale: 0 }, { scale: 1, duration: 0.35, ease: "back.out(2.2)" }, END_BEATS.cat);
  tl.fromTo("#end-title", { y: 40, opacity: 0 }, { y: 0, opacity: 1, duration: 0.3, ease: "power2.out" }, END_BEATS.title);
  tl.fromTo("#end-line", { scale: 0.6, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.35, ease: "back.out(2)" }, END_BEATS.line);
  tl.fromTo("#end-url", { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.3, ease: "power2.out" }, END_BEATS.url);

  // cat-hop: 900 ms, keyframes at 30%, 55%, 75%; heights scaled to the cat's size here.
  const hop = [
    [0.3, { y: -36, scaleX: 1.03, scaleY: 0.98 }, "power2.out"],
    [0.55, { y: 0, scaleX: 1.02, scaleY: 0.97 }, "power2.in"],
    [0.75, { y: -10, scaleX: 1, scaleY: 1 }, "power1.out"],
    [1, { y: 0, scaleX: 1, scaleY: 1 }, "power1.in"],
  ];
  let from = { y: 0, scaleX: 1, scaleY: 1 };
  let at = 0;
  for (const [until, pose, ease] of hop) {
    tl.fromTo(cat, { ...from }, { ...pose, ...quiet, duration: 0.9 * (until - at), ease }, END_BEATS.hop + 0.9 * at);
    [from, at] = [pose, until];
  }

  // cat-heart: over 1 s the heart rises and grows (easing out), fading in for the first quarter and out after.
  const heartMid = { y: -20, scale: 0.82, opacity: 1 };
  tl.fromTo("#heart", { y: 30, scale: 0.6, opacity: 0 }, { ...heartMid, duration: 0.25, ease: "power1.out" }, END_BEATS.hop);
  tl.fromTo("#heart", { ...heartMid }, { y: -50, scale: 1.1, opacity: 0, ...quiet, duration: 0.75, ease: "power2.out" }, END_BEATS.hop + 0.25);
}

const SCENES = [cardWords, arriveScene, typeScene, customiseScene, unlockScene, trackScene, endScene];

async function main() {
  await setup();
  const tl = gsap.timeline({ paused: true });
  frameDriver(tl);
  for (const scene of SCENES) scene(tl);
  applyFrame(0);
  window.__advert = { applyFrame };
  window.__timelines = window.__timelines || {};
  window.__timelines.advert = tl;
}

main().catch((error) => {
  console.error(error);
  throw error;
});
