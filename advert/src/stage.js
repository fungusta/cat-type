// The advert's stage: dresses the cats, then builds one paused GSAP timeline that the
// renderer seeks frame by frame. Bundled as an IIFE; GSAP is the global from js/gsap.min.js.
//
// Two layers set what is on screen:
// - applyFrame(t) sets everything that frameState(t) decides (look, paws, face, typed text).
//   A frame driver tween re-runs it on every seek, so frames can be asked for in any order.
// - Scene functions add their own tweens (camera, pops, caret) to the timeline at fixed times.
// To add a scene, write a function that takes the timeline and add it to SCENES below.

import { renderCat } from "../../site/js/cat.js";
import { DURATION, LOOKS, SCENES as TIMES, TYPED_TEXT, frameState } from "./timeline.mjs";

// Camera scale for the wide opening shot; 1 is the close shot the CSS lays out.
export const CAMERA_WIDE = 0.6;
export const CAMERA_CLOSE = 1;

const CARET_BLINK = 0.5;
const TYPE_START = 2.3;

let looks = [];
let typed = null;

/** Sets every frameState-driven property for time t. Reads no previous DOM state. */
export function applyFrame(t) {
  const state = frameState(t);
  const pressed = state.pawLeft > 0 || state.pawRight > 0;
  for (const look of looks) {
    look.element.style.visibility = look.key === state.look ? "visible" : "hidden";
    look.pawLeft.style.transform = `scaleY(${1 - 0.34 * state.pawLeft})`;
    look.pawRight.style.transform = `scaleY(${1 - 0.34 * state.pawRight})`;
    for (const pads of look.pads) pads.style.display = pressed ? "none" : "";
    look.svg.classList.toggle("is-excited", state.excited);
  }
  typed.textContent = TYPED_TEXT.slice(0, state.typedChars);
}

/** Renders one .look per LOOKS key into #cat-rig and waits for the fonts. */
async function setup() {
  const rig = document.getElementById("cat-rig");
  typed = document.getElementById("typed");
  document.getElementById("typed-ghost").textContent = TYPED_TEXT;

  const pending = Object.entries(LOOKS).map(([key, look]) => {
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
  });
  looks = await Promise.all(pending);
  await Promise.all([document.fonts.load('800 160px "Nunito"'), document.fonts.load('700 160px "Nunito"')]);
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

/** Scene 1 (0-2 s): a blinking caret, the cat pops up, the camera pushes in. */
function arriveScene(tl) {
  const [start] = TIMES.arrive;
  for (let t = start, on = true; t < TYPE_START; t += CARET_BLINK, on = !on) {
    tl.set("#caret", { opacity: on ? 1 : 0 }, t);
  }
  tl.fromTo("#cat-rig", { scale: 0 }, { scale: 1, duration: 0.35, ease: "back.out(2.2)" }, 0.9);
  tl.fromTo("#camera", { scale: CAMERA_WIDE }, { scale: CAMERA_CLOSE, duration: 0.8, ease: "power2.inOut" }, 1.4);
}

/** Scene 2 (2-7 s): the sentence types itself (applyFrame); the caret stops blinking and follows it. */
function typeScene(tl) {
  tl.set("#caret", { opacity: 1 }, TYPE_START);
}

const SCENES = [arriveScene, typeScene];

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
});
