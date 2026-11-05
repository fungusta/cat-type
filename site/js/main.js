import {
  DEFAULT_CHOICE,
  createRenderTickets,
  downloadFor,
  nextOutfit,
  platformFor,
  readChoice,
  storageFrom,
  writeChoice,
} from "./logic.js";
import { happy, renderCat, startHeroLoop } from "./cat.js";

document.documentElement.classList.add("js");

const $ = (selector) => document.querySelector(selector);
const PADLOCK = '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path fill="currentColor" d="M5 7V5a3 3 0 0 1 6 0v2h.5A1.5 1.5 0 0 1 13 8.5v5a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 3 13.5v-5A1.5 1.5 0 0 1 4.5 7H5Zm1.5 0h3V5a1.5 1.5 0 0 0-3 0v2Z"/></svg>';

// The platform logos are <symbol>s in index.html, shared with the footer.
function platformIcon(name) {
  const SVG = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("width", "20");
  svg.setAttribute("height", "20");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.classList.add("pill-icon");
  svg.appendChild(document.createElementNS(SVG, "use")).setAttribute("href", `#icon-${name}`);
  return svg;
}

export function renderDownload(nav = navigator) {
  const download = downloadFor(platformFor(nav));
  const button = $("#primary-download");
  const label = document.createTextNode(download.label);
  button.replaceChildren(...(download.icon ? [platformIcon(download.icon), label] : [label]));
  button.href = download.href;
  const note = $("#download-note");
  note.textContent = download.note ?? "";
  note.hidden = !download.note;
  const secondary = $("#download-secondary");
  secondary.textContent = download.secondary?.label ?? "";
  secondary.href = download.secondary?.href ?? "#download";
  secondary.hidden = !download.secondary;
}

// Accessory art shares the cats' 120×120 canvas, so crop each tile's art to
// its own bounds once it is in the document and measurable.
async function fitAccessory(img) {
  const text = await fetch(img.getAttribute("src")).then((response) => response.text());
  const svg = new DOMParser().parseFromString(text, "image/svg+xml").documentElement;
  svg.querySelectorAll("[id]").forEach((element) => element.removeAttribute("id"));
  svg.querySelectorAll("title, desc").forEach((element) => element.remove());
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", img.className);
  const inline = document.importNode(svg, true);
  img.replaceWith(inline);
  const box = inline.getBBox();
  const pad = 6;
  inline.setAttribute("viewBox", `${box.x - pad} ${box.y - pad} ${box.width + pad * 2} ${box.height + pad * 2}`);
  inline.setAttribute("width", "64");
  inline.setAttribute("height", "64");
}

function renderTiles(showcase) {
  const list = $("#unlock-tiles");
  list.replaceChildren(...showcase.map((item) => {
    const tile = document.createElement("li");
    tile.className = `tile ${item.equipped ? "tile-equipped" : "tile-locked"}`;
    tile.innerHTML = `
      <img class="tile-art" src="assets/accessories/${item.id}.svg" alt="" width="64" height="64">
      <div>
        <p class="tile-name"></p>
        <p class="tile-blurb"></p>
      </div>
      <span class="tile-badge">${item.equipped ? "✓" : PADLOCK}</span>`;
    tile.querySelector(".tile-name").textContent = item.name;
    tile.querySelector(".tile-blurb").textContent = item.blurb;
    tile.setAttribute("aria-label", item.equipped
      ? `${item.name}, unlocked and worn`
      : `${item.name}, locked, ${item.progress}% of the way`);
    if (!item.equipped) {
      const meter = document.createElement("div");
      meter.className = "meter";
      meter.innerHTML = `<span style="width:${item.progress}%"></span>`;
      const target = document.createElement("p");
      target.className = "tile-target";
      target.textContent = `${item.target.toLocaleString("en")} keystrokes`;
      tile.querySelector("div").append(meter, target);
    }
    return tile;
  }));
  list.querySelectorAll("img").forEach((img) => fitAccessory(img).catch(() => {}));
}

function renderTrack({ week, today, last7, allTime }) {
  const values = $("#track-stats").querySelectorAll("dd");
  [today, last7, allTime].forEach((value, index) => { values[index].textContent = value.toLocaleString("en"); });
  const max = Math.max(...week);
  const now = new Date();
  $("#track-chart").replaceChildren(...week.map((count, index) => {
    const daysAgo = week.length - 1 - index;
    const day = new Date(now.getFullYear(), now.getMonth(), now.getDate() - daysAgo);
    const bar = document.createElement("div");
    bar.className = daysAgo === 0 ? "bar bar-today" : "bar";
    bar.innerHTML = `<span class="bar-fill" style="height:${Math.round((count / max) * 100)}%"></span><span class="bar-label"></span>`;
    bar.querySelector(".bar-label").textContent = daysAgo === 0 ? "Today" : day.toLocaleDateString("en", { weekday: "narrow" });
    return bar;
  }));
}

async function start() {
  renderDownload();
  let catalog;
  try {
    // Revalidate so a fresh deploy's catalog is used straight away.
    const response = await fetch("catalog.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`catalog.json ${response.status}`);
    catalog = await response.json();
  } catch {
    // The static page still reads and downloads without the catalog.
    document.documentElement.classList.remove("js");
    return;
  }

  const storage = storageFrom(() => window.localStorage);
  let choice = readChoice(storage, catalog);
  let heroSvg = null;
  let customSvg = null;
  const chips = [...document.querySelectorAll("#style-chips [data-cat]")];
  const renders = createRenderTickets();

  // Cats render off-page first, so a slow earlier render can never land on
  // top of a newer choice.
  const show = async () => {
    const ticket = renders.next();
    chips.forEach((chip) => chip.setAttribute("aria-pressed", String(chip.dataset.cat === choice.cat)));
    const [hero, custom] = await Promise.all([
      renderCat(document.createElement("div"), choice, "hero"),
      renderCat(document.createElement("div"), choice, "custom"),
    ]);
    if (!renders.isCurrent(ticket)) return;
    $("#hero-cat").replaceChildren(hero);
    $("#customise-cat").replaceChildren(custom);
    [heroSvg, customSvg] = [hero, custom];
  };

  const choose = async (next) => {
    choice = next;
    writeChoice(storage, choice);
    await show();
  };

  try {
    await show();
  } catch {
    choice = { cat: DEFAULT_CHOICE.cat, outfit: { ...DEFAULT_CHOICE.outfit } };
    await show().catch(() => {});
  }
  startHeroLoop(() => heroSvg);
  renderTiles(catalog.showcase);
  renderTrack(catalog);

  const heroCat = $("#hero-cat");
  heroCat.addEventListener("click", () => heroSvg && happy(heroSvg));
  const button = $("#primary-download");
  const perk = (on) => heroSvg?.classList.toggle("is-perky", on);
  button.addEventListener("mouseenter", () => perk(true));
  button.addEventListener("mouseleave", () => perk(false));
  button.addEventListener("focus", () => perk(true));
  button.addEventListener("blur", () => perk(false));

  for (const chip of chips) {
    chip.addEventListener("click", () => choose({ cat: chip.dataset.cat, outfit: choice.outfit }));
  }
  $("#mix-it-up").addEventListener("click", async () => {
    await choose({ cat: choice.cat, outfit: nextOutfit(catalog.starters, choice.outfit) });
    if (customSvg) happy(customSvg);
  });
}

start();
