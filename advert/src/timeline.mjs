// The advert's timeline: what is on screen and what sounds at time t.
// Pure data and pure functions only: no imports, no DOM, no Node APIs, no state.
// Edit the constants below to change words, outfits and timings.

export const FPS = 60;
export const WIDTH = 1920;
export const HEIGHT = 1080;
export const DURATION = 27;
export const SAMPLE_RATE = 48000;

export const SCENES = {
  arrive: [0, 2],
  type: [2, 7],
  cardCustomise: [7, 8],
  customise: [8, 13],
  cardUnlock: [13, 14],
  unlock: [14, 18],
  cardTrack: [18, 19],
  track: [19, 23],
  end: [23, 27],
};

export const CARDS = [
  { id: "card-customise", text: "Customise it.", start: 7, duration: 1 },
  { id: "card-unlock", text: "Unlock new outfits.", start: 13, duration: 1 },
  { id: "card-track", text: "Track your productivity.", start: 18, duration: 1 },
];

export const TYPED_TEXT = "Brighten up your day, one key at a time.";

export const LOOKS = {
  plain: { cat: "gray", outfit: {} },
  ginger: { cat: "ginger", outfit: {} },
  blackWhite: { cat: "black-white", outfit: {} },
  wizard: { cat: "gray", outfit: { hat: "wizard-hat" } },
  shades: { cat: "gray", outfit: { glasses: "sunglasses", neck: "red-bandana" } },
  crownCape: { cat: "gray", outfit: { hat: "crown", back: "royal-cape" } },
  party: { cat: "gray", outfit: { hat: "party-hat" } },
  crown: { cat: "gray", outfit: { hat: "crown" } },
  crownWings: { cat: "gray", outfit: { hat: "crown", back: "dragon-wings" } },
  brand: { cat: "gray", outfit: { hat: "beanie", neck: "bow-tie" } },
};

export const LOOK_CHANGES = [
  { t: 0, look: "plain" },
  { t: 8.6, look: "ginger" },
  { t: 9.5, look: "blackWhite" },
  { t: 10.4, look: "wizard" },
  { t: 11.2, look: "shades" },
  { t: 11.9, look: "crownCape" },
  { t: 13, look: "plain" },
  { t: 15.0, look: "party" },
  { t: 16.2, look: "crown" },
  { t: 17.4, look: "crownWings" },
  { t: 23, look: "brand" },
];

export const UNLOCKS = [
  { t: 15.0, id: "party-hat", name: "Party hat", target: 50000 },
  { t: 16.2, id: "crown", name: "Crown", target: 100000 },
  { t: 17.4, id: "dragon-wings", name: "Dragon wings", target: 500000 },
];

const WEEK = [1180, 1620, 940, 1850, 1410, 2060, 1440];
// today and last7 follow from the bars, so they cannot disagree with them.
export const STATS = {
  week: WEEK,
  labels: ["M", "T", "W", "T", "F", "S", "Today"],
  today: WEEK.at(-1),
  last7: WEEK.reduce((sum, value) => sum + value, 0),
  allTime: 510500,
};

export const END = { title: "Cat Type", line: "Get it for Windows or Mac", url: "fungusta.github.io/cat-type" };

// Picture beats that also carry a sound (s). stage.js tweens on them and SCENE_CUES places the sound on them.
// The cat pops up in the opening shot.
export const ARRIVE_POP = 0.9;
// The end scene: the cat pops in, the words follow, the cat hops with a heart.
export const END_BEATS = { cat: 23.1, title: 23.4, line: 23.9, url: 24.3, hop: 25.0 };

// Keyboard halves, copied from cat_type.py (LEFT_/RIGHT_PORTABLE_CHARACTERS).
const LEFT_CHARACTERS = new Set("`~12345!@#$%qwertasdfgzxcvb");
const RIGHT_CHARACTERS = new Set("67890-=_+^&*()yuiop[]{}\\|hjkl:;'\"nm,./<>?");

// Paw tap shape, as in the app's 0.16 s tap frame.
const PAW_HOLD = 0.08;
const PAW_RELEASE = 0.16;

// Excitement: a space tap, or the fifth of five presses inside this window.
const EXCITED_FOR = 0.16;
const RUN_LENGTH = 5;
const RUN_WINDOW = 0.34;

// Typing schedules.
const TYPE_START = 2.3;
const TYPE_SPAN = 4.1;
const UNLOCK_KEYS = { start: 14.2, step: 0.08, last: 17.6 };
const TRACK_KEYS = { start: 19.3, step: 0.14, last: 22.6 };

// Counter: straight lines from 0 at the start of the unlock scene through each unlock's target.
const COUNTER_POINTS = [[SCENES.unlock[0], 0], ...UNLOCKS.map((unlock) => [unlock.t, unlock.target])];

// Stats and bars.
const STATS_FROM = 19.4;
const STATS_TO = 21.8;
const BAR_START = 19.6;
const BAR_STAGGER = 0.3;
const BAR_GROW = 0.35;

// Sounds.
const KEY_SOUNDS = 6;
const KEY_GAIN = { type: 0.8, unlock: 0.5, track: 0.3 };
const [CUSTOMISE_FROM, CUSTOMISE_TO] = SCENES.customise;
const SCENE_CUES = [
  { sound: "pop", gain: 0.9, times: [ARRIVE_POP, END_BEATS.cat] },
  { sound: "whoosh", gain: 0.7, times: CARDS.map((card) => card.start) },
  { sound: "swap", gain: 0.8, times: LOOK_CHANGES.filter((change) => change.t > CUSTOMISE_FROM && change.t < CUSTOMISE_TO).map((change) => change.t) },
  { sound: "chime", gain: 0.8, times: UNLOCKS.map((unlock) => unlock.t) },
  { sound: "tick", gain: 0.5, times: STATS.week.map((_, i) => BAR_START + BAR_STAGGER * i) },
];

const clamp01 = (x) => Math.min(1, Math.max(0, x));
const ramp = (t, from, to) => clamp01((t - from) / (to - from));
const byTime = (a, b) => a.t - b.t;
const opposite = (paw) => (paw === "left" ? "right" : "left");

function pawDepth(press, t) {
  if (!press) return 0;
  const age = t - press.t;
  if (age < PAW_HOLD) return 1;
  if (age < PAW_RELEASE) return (PAW_RELEASE - age) / (PAW_RELEASE - PAW_HOLD);
  return 0;
}

function evenKeys({ start, step, last }, scene) {
  const keys = [];
  for (let k = 0; start + step * k <= last; k++) {
    keys.push({ t: start + step * k, paw: k % 2 === 0 ? "left" : "right", scene });
  }
  return keys;
}

function typedKeys() {
  const last = TYPED_TEXT.length - 1;
  const keys = [];
  let previous = null;
  for (let i = 0; i < TYPED_TEXT.length; i++) {
    const u = i / last;
    const char = TYPED_TEXT[i];
    let paw = pawFor(char);
    // "alternate" flips the previous paw; with no previous one-sided paw it starts left.
    if (paw === "alternate") paw = previous === "left" || previous === "right" ? opposite(previous) : "left";
    keys.push({ t: TYPE_START + TYPE_SPAN * (0.6 * u + 0.4 * (1 - (1 - u) ** 2)), paw, scene: "type", char });
    previous = paw;
  }
  return keys;
}

function counterAt(t) {
  const [first] = COUNTER_POINTS;
  const final = COUNTER_POINTS.at(-1);
  if (t < first[0]) return 0;
  if (t >= final[0]) return final[1];
  for (let i = 0; i < COUNTER_POINTS.length - 1; i++) {
    const [t0, v0] = COUNTER_POINTS[i];
    const [t1, v1] = COUNTER_POINTS[i + 1];
    if (t < t1) return Math.floor(v0 + ((t - t0) / (t1 - t0)) * (v1 - v0));
  }
  return final[1];
}

export function pawFor(char) {
  if (char === " ") return "both";
  const key = char.toLowerCase();
  if (LEFT_CHARACTERS.has(key)) return "left";
  if (RIGHT_CHARACTERS.has(key)) return "right";
  return "alternate";
}

export function presses() {
  return [...typedKeys(), ...evenKeys(UNLOCK_KEYS, "unlock"), ...evenKeys(TRACK_KEYS, "track")].sort(byTime);
}

export function frameState(t) {
  const past = presses().filter((press) => press.t <= t);
  const latest = past.at(-1);
  const latestOn = (side) => past.findLast((press) => press.paw === side || press.paw === "both");

  const fresh = (press) => press !== undefined && t - press.t < EXCITED_FOR;
  const spaceFresh = fresh(past.findLast((press) => press.paw === "both"));
  const runStart = past.at(-RUN_LENGTH);
  const fastRun = fresh(latest) && past.length >= RUN_LENGTH && latest.t - runStart.t < RUN_WINDOW;

  const look = LOOK_CHANGES.findLast((change) => change.t <= t).look;
  const grow = ramp(t, STATS_FROM, STATS_TO);
  const tallest = Math.max(...STATS.week);

  return {
    look,
    pawLeft: pawDepth(latestOn("left"), t),
    pawRight: pawDepth(latestOn("right"), t),
    excited: spaceFresh || fastRun,
    typedChars: past.filter((press) => press.scene === "type").length,
    counter: counterAt(t),
    unlocked: UNLOCKS.filter((unlock) => t >= unlock.t).map((unlock) => unlock.id),
    stats: {
      today: Math.round(STATS.today * grow),
      last7: Math.round(STATS.last7 * grow),
      allTime: Math.round(STATS.allTime * grow),
    },
    bars: STATS.week.map((value, i) => {
      const start = BAR_START + BAR_STAGGER * i;
      return ramp(t, start, start + BAR_GROW) * (value / tallest);
    }),
  };
}

export function soundCues() {
  const sceneIndex = { type: 0, unlock: 0, track: 0 };
  const keyCues = presses().map((press) => {
    const index = sceneIndex[press.scene]++;
    const sound = press.paw === "both" ? "space" : `key-${(index % KEY_SOUNDS) + 1}`;
    return { t: press.t, sound, gain: KEY_GAIN[press.scene] };
  });
  const beatCues = SCENE_CUES.flatMap(({ sound, gain, times }) => times.map((t) => ({ t, sound, gain })));
  return [...keyCues, ...beatCues].sort(byTime);
}
