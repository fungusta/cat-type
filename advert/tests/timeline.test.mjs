import test from "node:test";
import assert from "node:assert/strict";
import { ARRIVE_POP, CARDS, DURATION, END_BEATS, LOOKS, LOOK_CHANGES, SCENES, STATS, TYPED_TEXT, UNLOCKS, frameState, pawFor, presses, soundCues } from "../src/timeline.mjs";

const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} vs ${b}`);

test("pawFor follows the app's keyboard split", () => {
  assert.equal(pawFor("B"), "left");
  assert.equal(pawFor("u"), "right");
  assert.equal(pawFor(","), "right");
  assert.equal(pawFor(" "), "both");
  assert.equal(pawFor("é"), "alternate");
});

test("the typed sentence gets one press per character, speeding up", () => {
  const typed = presses().filter((p) => p.scene === "type");
  assert.equal(typed.length, 40);
  assert.equal(typed.map((p) => p.char).join(""), TYPED_TEXT);
  near(typed[0].t, 2.3);
  near(typed[39].t, 6.4);
  const gaps = typed.slice(1).map((p, i) => p.t - typed[i].t);
  assert.ok(gaps.every((gap, i) => i === 0 || gap < gaps[i - 1]));
  assert.ok(gaps.at(-1) > 0.05);
});

test("a paw goes down on its key and comes back up within 0.16 s", () => {
  assert.equal(frameState(2.3).pawLeft, 1);
  assert.equal(frameState(2.3).pawRight, 0);
  near(frameState(2.3 + 0.12).pawLeft, 0.5);
  assert.equal(frameState(2.29).pawLeft, 0);
});

test("space taps both paws and excites the cat", () => {
  const space = presses().find((p) => p.paw === "both");
  const state = frameState(space.t);
  assert.deepEqual([state.pawLeft, state.pawRight, state.excited], [1, 1, true]);
});

test("slow typing is calm and fast typing is excited", () => {
  assert.equal(frameState(2.35).excited, false);
  assert.equal(frameState(6.38).excited, true);
  assert.equal(frameState(16.01).excited, true);
  assert.equal(frameState(1).excited, false);
});

test("the sentence fills in and stays", () => {
  assert.equal(frameState(2.29).typedChars, 0);
  assert.equal(frameState(2.3).typedChars, 1);
  assert.equal(frameState(6.9).typedChars, 40);
});

test("looks change on schedule", () => {
  const looks = [0, 8.59, 8.6, 12.5, 13.5, 15.0, 17.5, 24].map((t) => frameState(t).look);
  assert.deepEqual(looks, ["plain", "plain", "ginger", "crownCape", "plain", "party", "crownWings", "brand"]);
  for (const { look } of LOOK_CHANGES) assert.ok(LOOKS[look], look);
});

test("the counter reaches each target as its outfit unlocks", () => {
  assert.equal(frameState(14).counter, 0);
  assert.equal(frameState(15.0).counter, 50000);
  assert.equal(frameState(16.2).counter, 100000);
  assert.equal(frameState(26).counter, 500000);
  assert.deepEqual(frameState(14.99).unlocked, []);
  assert.deepEqual(frameState(17.4).unlocked, ["party-hat", "crown", "dragon-wings"]);
});

test("stats count up and bars grow one after another", () => {
  assert.deepEqual(frameState(19.4).stats, { today: 0, last7: 0, allTime: 0 });
  assert.deepEqual(frameState(22).stats, { today: 1440, last7: 10500, allTime: 510500 });
  assert.deepEqual(frameState(19.5).bars, [0, 0, 0, 0, 0, 0, 0]);
  near(frameState(22).bars[5], 1);
  near(frameState(22).bars[0], 1180 / 2060);
  assert.ok(frameState(19.8).bars[0] > 0 && frameState(19.8).bars[1] === 0);
});

test("frameState is a pure function of time", () => {
  const first = frameState(3.21);
  frameState(20);
  assert.deepEqual(frameState(3.21), first);
});

test("every press has a sound cue at the same time", () => {
  const cues = soundCues();
  for (const press of presses()) {
    assert.ok(cues.some((cue) => cue.t === press.t && /^(key-[1-6]|space)$/.test(cue.sound)), `press at ${press.t}`);
  }
});

test("scene sounds sit on their beats and inside the video", () => {
  const at = (sound) => soundCues().filter((cue) => cue.sound === sound).map((cue) => cue.t);
  const [customiseFrom, customiseTo] = SCENES.customise;
  assert.deepEqual(at("whoosh"), CARDS.map((card) => card.start));
  assert.deepEqual(at("swap"), LOOK_CHANGES.filter((change) => change.t > customiseFrom && change.t < customiseTo).map((change) => change.t));
  assert.deepEqual(at("chime"), UNLOCKS.map((unlock) => unlock.t));
  assert.deepEqual(at("pop"), [ARRIVE_POP, END_BEATS.cat]);
  assert.equal(at("tick").length, 7);
  assert.ok(soundCues().every((cue) => cue.t >= 0 && cue.t <= DURATION - 0.7 && cue.gain > 0 && cue.gain <= 1));
});

test("the counter shows each unlock's target at its moment", () => {
  for (const unlock of UNLOCKS) assert.equal(frameState(unlock.t).counter, unlock.target, unlock.id);
});

test("today and last 7 days follow from the bars", () => {
  assert.equal(STATS.today, STATS.week.at(-1));
  assert.equal(STATS.last7, STATS.week.reduce((sum, value) => sum + value, 0));
});
