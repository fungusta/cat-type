import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_CHOICE,
  RELEASE_BASE,
  downloadFor,
  nextOutfit,
  platformFor,
  readChoice,
  writeChoice,
} from "../js/logic.js";

const WINDOWS_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36";
const MAC_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15";
const X11_UA = "Mozilla/5.0 (X11; Ubuntu; x86_64; rv:131.0) Gecko/20100101 Firefox/131.0";
const ANDROID_UA = "Mozilla/5.0 (Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36";
const IPHONE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";

const STARTERS = [
  { id: "ribbon-clip", slot: "ears" },
  { id: "round-glasses", slot: "glasses" },
  { id: "bell-collar", slot: "neck" },
  { id: "bow-tie", slot: "neck" },
  { id: "beanie", slot: "hat" },
  { id: "daisy-clip", slot: "ears" },
  { id: "sunglasses", slot: "glasses" },
];
const CATALOG = {
  cats: ["gray", "ginger", "charcoal", "brown-tabby", "white", "black-white"],
  starters: STARTERS,
};
const STARTER_SLOT = Object.fromEntries(STARTERS.map(({ id, slot }) => [id, slot]));

function memoryStorage(initial = {}) {
  const data = { ...initial };
  return {
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => { data[key] = String(value); },
  };
}

const throwingStorage = {
  getItem() { throw new Error("blocked"); },
  setItem() { throw new Error("blocked"); },
};

test("test_windows_detection", () => {
  assert.equal(platformFor({ userAgent: WINDOWS_UA, maxTouchPoints: 0 }), "windows");
});

test("test_mac_detection", () => {
  assert.equal(platformFor({ userAgent: MAC_UA, maxTouchPoints: 0 }), "mac");
});

test("test_ipad_is_not_a_mac", () => {
  assert.equal(platformFor({ userAgent: MAC_UA, maxTouchPoints: 5 }), "other");
});

test("test_linux_and_phones_are_other", () => {
  for (const userAgent of [X11_UA, ANDROID_UA, IPHONE_UA]) {
    assert.equal(platformFor({ userAgent, maxTouchPoints: 0 }), "other", userAgent);
  }
});

test("test_download_targets", () => {
  const windows = downloadFor("windows");
  assert.equal(windows.label, "Download for Windows");
  assert.equal(windows.href, `${RELEASE_BASE}Cat-Type-Windows-x64.exe`);
  assert.equal(windows.note, "Windows might say it doesn't recognise Cat Type yet. Choose More info, then Run anyway. The source is public on GitHub.");
  assert.equal(windows.secondary, null);

  const mac = downloadFor("mac");
  assert.equal(mac.label, "Download for Mac");
  assert.equal(mac.href, `${RELEASE_BASE}Cat-Type-macOS-arm64.dmg`);
  assert.equal(mac.note, "On first launch, choose Enable Input Monitoring so your cat can hear you type.");
  assert.deepEqual(mac.secondary, { label: "Intel Mac?", href: `${RELEASE_BASE}Cat-Type-macOS-x64.dmg` });

  const other = downloadFor("other");
  assert.equal(other.label, "Get it for Windows or Mac");
  assert.equal(other.href, "#download");
  assert.equal(other.note, null);
  assert.equal(other.secondary, null);

  assert.equal(RELEASE_BASE, "https://github.com/fungusta/cat-type/releases/latest/download/");
});

test("test_next_outfit_never_repeats", () => {
  let previous = DEFAULT_CHOICE.outfit;
  for (let round = 0; round < 20; round += 1) {
    const outfit = nextOutfit(STARTERS, previous, () => 0);
    assert.notDeepEqual(outfit, previous, `round ${round}`);
    const entries = Object.entries(outfit);
    assert.ok(entries.length >= 2 && entries.length <= 3, `round ${round}: ${entries.length} items`);
    for (const [slot, id] of entries) assert.equal(STARTER_SLOT[id], slot, id);
    previous = outfit;
  }
});

test("test_read_choice_rejects_bad_saved_state", () => {
  const saved = (value) => memoryStorage({ "cat-type-choice": value });
  const cases = {
    "malformed JSON": saved("{bad"),
    "unknown cat": saved(JSON.stringify({ cat: "tiger", outfit: {} })),
    "locked item": saved(JSON.stringify({ cat: "gray", outfit: { hat: "crown" } })),
    "hidden item": saved(JSON.stringify({ cat: "gray", outfit: { neck: "moon-pendant" } })),
    "wrong slot": saved(JSON.stringify({ cat: "gray", outfit: { hat: "bow-tie" } })),
    "throwing storage": throwingStorage,
  };
  for (const [name, storage] of Object.entries(cases)) {
    assert.deepEqual(readChoice(storage, CATALOG), DEFAULT_CHOICE, name);
  }
});

test("test_read_choice_round_trips_valid_state", () => {
  const storage = memoryStorage();
  const choice = { cat: "white", outfit: { ears: "daisy-clip", glasses: "sunglasses" } };
  writeChoice(storage, choice);
  assert.deepEqual(readChoice(storage, CATALOG), choice);
  assert.doesNotThrow(() => writeChoice(throwingStorage, choice));
});
