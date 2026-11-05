// Page decisions with no DOM access, so they can be tested under node --test.

export const RELEASE_BASE = "https://github.com/fungusta/cat-type/releases/latest/download/";

export const DEFAULT_CHOICE = Object.freeze({
  cat: "gray",
  outfit: Object.freeze({ hat: "beanie", neck: "bow-tie" }),
});

const STORAGE_KEY = "cat-type-choice";

const DOWNLOADS = {
  windows: {
    label: "Download for Windows",
    href: `${RELEASE_BASE}Cat-Type-Windows-x64.exe`,
    icon: "windows",
    note: null,
    secondary: null,
  },
  mac: {
    label: "Download for Mac",
    href: `${RELEASE_BASE}Cat-Type-macOS-arm64.dmg`,
    icon: "apple",
    note: "On first launch, choose Enable Input Monitoring so your cat can hear you type.",
    secondary: { label: "Intel Mac?", href: `${RELEASE_BASE}Cat-Type-macOS-x64.dmg` },
  },
  other: {
    label: "Get it for Windows or Mac",
    href: "#download",
    icon: null,
    note: null,
    secondary: null,
  },
};

const DOWNLOAD_SLUGS = {
  "Cat-Type-Windows-x64.exe": "windows",
  "Cat-Type-macOS-arm64.dmg": "mac-arm64",
  "Cat-Type-macOS-x64.dmg": "mac-intel",
};

// GoatCounter click-event name for a download link, e.g. "download-hero-windows".
// The hero button on other devices only scrolls to the platform list.
export function downloadEvent(placement, href) {
  if (!href.startsWith(RELEASE_BASE)) return `${placement}-see-platforms`;
  const slug = DOWNLOAD_SLUGS[href.slice(RELEASE_BASE.length)];
  return slug ? `download-${placement}-${slug}` : null;
}

// Only Windows and non-touch Macs get a direct download. iPadOS sends a
// desktop "Macintosh" agent, so a touch screen rules a Mac out.
export function platformFor({ userAgent = "", maxTouchPoints = 0 } = {}) {
  if (/Windows/.test(userAgent)) return "windows";
  if (/Macintosh/.test(userAgent) && maxTouchPoints <= 1) return "mac";
  return "other";
}

export function downloadFor(platform) {
  const download = DOWNLOADS[platform] ?? DOWNLOADS.other;
  return { ...download, secondary: download.secondary && { ...download.secondary } };
}

function sameOutfit(a = {}, b = {}) {
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every((slot) => a[slot] === b[slot]);
}

// Every outfit of two or three starter items with at most one per slot,
// in a stable order so a repeat can step to its neighbour.
function allOutfits(starters) {
  const bySlot = new Map();
  for (const { id, slot } of starters) {
    if (!bySlot.has(slot)) bySlot.set(slot, []);
    bySlot.get(slot).push(id);
  }
  const outfits = [];
  const extend = (slots, outfit) => {
    const size = Object.keys(outfit).length;
    if (size >= 2) outfits.push(outfit);
    if (size === 3 || slots.length === 0) return;
    slots.forEach((slot, index) => {
      for (const id of bySlot.get(slot)) extend(slots.slice(index + 1), { ...outfit, [slot]: id });
    });
  };
  extend([...bySlot.keys()], {});
  return outfits;
}

export function nextOutfit(starters, previous, random = Math.random) {
  const outfits = allOutfits(starters);
  let index = Math.min(outfits.length - 1, Math.floor(random() * outfits.length));
  if (sameOutfit(outfits[index], previous)) index = (index + 1) % outfits.length;
  return { ...outfits[index] };
}

function copyOfDefault() {
  return { cat: DEFAULT_CHOICE.cat, outfit: { ...DEFAULT_CHOICE.outfit } };
}

// Touching window.localStorage itself throws when site data is blocked, so
// resolve it once here; readChoice and writeChoice treat null as "no storage".
export function storageFrom(getStorage) {
  try {
    return getStorage() ?? null;
  } catch {
    return null;
  }
}

// Renders can finish out of order; only the most recent one may be shown.
export function createRenderTickets() {
  let latest = 0;
  return {
    next: () => ++latest,
    isCurrent: (ticket) => ticket === latest,
  };
}

export function readChoice(storage, catalog) {
  try {
    const saved = JSON.parse(storage.getItem(STORAGE_KEY));
    const slotOf = new Map(catalog.starters.map(({ id, slot }) => [id, slot]));
    const outfit = saved?.outfit;
    const valid = catalog.cats.includes(saved?.cat)
      && outfit && typeof outfit === "object" && !Array.isArray(outfit)
      && Object.entries(outfit).every(([slot, id]) => slotOf.get(id) === slot);
    return valid ? { cat: saved.cat, outfit: { ...outfit } } : copyOfDefault();
  } catch {
    return copyOfDefault();
  }
}

export function writeChoice(storage, choice) {
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(choice));
  } catch {
    // Storage can be blocked; the choice simply won't survive a reload.
  }
}
