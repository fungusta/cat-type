// Stub stage: registers an empty, paused timeline as long as the advert. Task 5 fills it.
// Bundled as an IIFE; GSAP is the global loaded from js/gsap.min.js.

import { DURATION } from "./timeline.mjs";

const tl = gsap.timeline({ paused: true });
tl.to({}, { duration: DURATION }, 0);

window.__timelines = window.__timelines || {};
window.__timelines.advert = tl;
