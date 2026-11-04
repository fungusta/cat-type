// Inline the app's cat SVGs, dress them exactly as cat_artwork._add_accessory
// does, and expose small gestures the page can play.

const SVG_NS = "http://www.w3.org/2000/svg";
const PART_CLASSES = {
  "paw-left": "cat-paw-left",
  "paw-right": "cat-paw-right",
  "pads-left": "cat-pads",
  "pads-right": "cat-pads",
  eyes: "cat-eyes",
  "mouth-idle": "cat-mouth-idle",
  "mouth-excited": "cat-mouth-excited",
};
// Layer order matches the app: back, neck, glasses, hat, ears.
const SLOT_ORDER = ["back", "neck", "glasses", "hat", "ears"];

const sources = new Map();

function fetchSvg(url) {
  if (!sources.has(url)) {
    sources.set(url, fetch(url).then((response) => {
      if (!response.ok) throw new Error(`Could not load ${url}`);
      return response.text();
    }));
  }
  return sources.get(url).then((text) => new DOMParser().parseFromString(text, "image/svg+xml").documentElement);
}

function insertBeforePawLeft(root, layer) {
  const paw = root.querySelector("#paw-left");
  if (!paw) throw new Error("Cat artwork has no paw layer");
  paw.parentNode.insertBefore(layer, paw);
}

function addAccessory(root, accessory, slot) {
  const layer = document.createElementNS(SVG_NS, "g");
  layer.id = `accessory-${slot}`;
  for (const child of [...accessory.children]) {
    if (!["title", "desc"].includes(child.localName)) layer.append(document.importNode(child, true));
  }
  const fitted = [...layer.querySelectorAll('[data-clip-to-body="true"]')];
  const front = [...layer.querySelectorAll('[data-render-layer="front"]')];
  let frontLayer = null;
  if (front.length) {
    frontLayer = document.createElementNS(SVG_NS, "g");
    frontLayer.id = `accessory-${slot}-front`;
    for (const group of front) frontLayer.append(group);
  }
  if (fitted.length) {
    // Clip only the marked band so pendants can still hang below the body.
    const outline = root.querySelector("#outline");
    const clipId = `accessory-${slot}-body-clip`;
    const defs = layer.appendChild(document.createElementNS(SVG_NS, "defs"));
    const clip = defs.appendChild(document.createElementNS(SVG_NS, "clipPath"));
    clip.id = clipId;
    clip.setAttribute("clipPathUnits", "userSpaceOnUse");
    const path = clip.appendChild(document.createElementNS(SVG_NS, "path"));
    path.setAttribute("d", outline.getAttribute("d"));
    path.setAttribute("fill", "black");
    path.setAttribute("stroke", "none");
    for (const part of fitted) part.setAttribute("clip-path", `url(#${clipId})`);
  }
  if (slot === "back") {
    root.insertBefore(layer, root.firstElementChild);
  } else if (slot === "neck") {
    // Neckwear sits behind the animated paws, as in the app.
    insertBeforePawLeft(root, layer);
    return;
  } else {
    root.append(layer);
  }
  if (frontLayer) insertBeforePawLeft(root, frontLayer);
}

// Two cats share a page, so every id and reference gets a per-cat prefix.
function prefixIds(root, prefix) {
  const renamed = new Map();
  for (const element of root.querySelectorAll("[id]")) {
    renamed.set(element.id, `${prefix}-${element.id}`);
    element.id = `${prefix}-${element.id}`;
  }
  const rename = (id) => renamed.get(id) ?? id;
  for (const element of [root, ...root.querySelectorAll("*")]) {
    for (const attribute of [...element.attributes]) {
      if (attribute.name === "id") continue;
      if ((attribute.name === "href" || attribute.name === "xlink:href") && attribute.value.startsWith("#")) {
        element.setAttribute(attribute.name, `#${rename(attribute.value.slice(1))}`);
      } else if (attribute.value.includes("url(#")) {
        element.setAttribute(attribute.name, attribute.value.replace(/url\(#([^)]+)\)/g, (_, id) => `url(#${rename(id)})`));
      }
    }
  }
}

export async function renderCat(container, { cat, outfit = {} }, idPrefix, assetBase = "assets/") {
  const slots = SLOT_ORDER.filter((slot) => outfit[slot]);
  const [base, ...accessories] = await Promise.all([
    fetchSvg(`${assetBase}cats/${cat}.svg`),
    ...slots.map((slot) => fetchSvg(`${assetBase}accessories/${outfit[slot]}.svg`)),
  ]);
  const root = document.importNode(base, true);
  root.querySelectorAll(":scope > title, :scope > desc").forEach((node) => node.remove());
  slots.forEach((slot, index) => addAccessory(root, accessories[index], slot));
  for (const [id, className] of Object.entries(PART_CLASSES)) root.querySelector(`#${id}`)?.classList.add(className);
  prefixIds(root, idPrefix);
  root.removeAttribute("width");
  root.removeAttribute("height");
  root.setAttribute("aria-hidden", "true");
  root.setAttribute("focusable", "false");
  root.classList.add("cat");
  container.replaceChildren(root);
  return root;
}

function play(svg, className, duration) {
  svg.classList.remove(className);
  // Restart the animation even if the gesture is already playing.
  void svg.getBoundingClientRect();
  svg.classList.add(className);
  clearTimeout(svg[`${className}Timer`]);
  svg[`${className}Timer`] = setTimeout(() => svg.classList.remove(className), duration);
}

export const wave = (svg) => play(svg, "is-waving", 1600);
export const burst = (svg) => play(svg, "is-typing", 1300);
export const blink = (svg) => play(svg, "is-blinking", 160);

export function happy(svg) {
  play(svg, "is-happy", 900);
  const heart = document.createElement("span");
  heart.className = "cat-heart";
  heart.setAttribute("aria-hidden", "true");
  heart.textContent = "♥";
  svg.parentElement?.append(heart);
  setTimeout(() => heart.remove(), 1000);
}

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// The hero's gentle routine: hello wave, blinks, a typing burst with the
// excited face, then a wave that leans toward the download button.
export function startHeroLoop(getSvg) {
  const current = typeof getSvg === "function" ? getSvg : () => getSvg;
  const timers = [];
  const at = (delay, action) => timers.push(setTimeout(() => current() && action(current()), delay));
  const blinker = setInterval(() => current() && blink(current()), 3400);
  const cycle = () => {
    if (reducedMotion()) return;
    at(0, wave);
    at(4200, burst);
    at(4200, (svg) => play(svg, "is-excited", 1500));
    at(7600, (svg) => { play(svg, "is-leaning", 1700); wave(svg); });
  };
  cycle();
  const loop = setInterval(cycle, 11000);
  return () => {
    timers.forEach(clearTimeout);
    clearInterval(blinker);
    clearInterval(loop);
  };
}
