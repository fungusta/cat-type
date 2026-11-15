import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { readCatalog, parseCatalog, assertPublishable, assertSafeOutDir, build } from "../scripts/build.mjs";
import { LOOKS, UNLOCKS } from "../src/timeline.mjs";
import { parseWav } from "../src/mix.mjs";

const repoRoot = fileURLToPath(new URL("../../", import.meta.url));
const catalog = readCatalog(repoRoot);

test("the catalog knows slots and secrets", () => {
  assert.deepEqual(catalog.get("crown"), { slot: "hat", hidden: false });
  assert.deepEqual(catalog.get("moon-pendant"), { slot: "neck", hidden: true });
  assert.equal(catalog.size, 30);
});

test("the advert's own looks are publishable", () => {
  assertPublishable(LOOKS, UNLOCKS.map((unlock) => unlock.id), catalog);
});

test("the catalog parser reads hidden=True on a continuation line", () => {
  const text = [
    "ACCESSORIES = (",
    '    Accessory("crown", "Crown", "hat", "Keyboard Royalty", "keystrokes", 100_000),',
    '    Accessory("moon-pendant", "Moon pendant", "neck", "Night Owl",',
    '              "night_keystrokes", 1_000,',
    "              hidden=True),",
    '    Accessory("bow-tie", "Bow tie", "neck", "Helping Paw", "keystrokes", 5_000),',
    ")",
  ].join("\n");
  const parsed = parseCatalog(text);
  assert.deepEqual(parsed.get("crown"), { slot: "hat", hidden: false });
  assert.deepEqual(parsed.get("moon-pendant"), { slot: "neck", hidden: true });
  assert.deepEqual(parsed.get("bow-tie"), { slot: "neck", hidden: false });
  assert.equal(parsed.size, 3);
});

test("a catalog with no accessories stops the build", () => {
  assert.throws(() => parseCatalog("ACCESSORIES = ()\n"), /no Accessory/);
});

test("a secret accessory stops the build", () => {
  assert.throws(() => assertPublishable({ x: { cat: "gray", outfit: { neck: "moon-pendant" } } }, [], catalog), /moon-pendant/);
});

test("an unknown accessory stops the build", () => {
  assert.throws(() => assertPublishable({}, ["nope"], catalog), /nope/);
});

test("an accessory in the wrong slot stops the build", () => {
  assert.throws(() => assertPublishable({ x: { cat: "gray", outfit: { hat: "sunglasses" } } }, [], catalog), /sunglasses/);
});

test("build writes a complete project", async (t) => {
  const outDir = await mkdtemp(join(tmpdir(), "advert-"));
  t.after(() => rm(outDir, { recursive: true, force: true }));
  await build({ outDir });
  for (const file of [
    "index.html", "advert.css", "js/advert.js", "js/gsap.min.js",
    "fonts/nunito-latin-700-normal.woff2", "fonts/nunito-latin-800-normal.woff2",
    "assets/cats/gray.svg", "assets/cats/ginger.svg", "assets/cats/black-white.svg",
    ...["wizard-hat", "sunglasses", "red-bandana", "crown", "royal-cape", "party-hat", "dragon-wings", "beanie", "bow-tie"]
      .map((id) => `assets/accessories/${id}.svg`),
  ]) assert.ok(existsSync(join(outDir, file)), file);
  const soundtrack = parseWav(await readFile(join(outDir, "sfx/soundtrack.wav")), "soundtrack");
  assert.equal(soundtrack.length, 27 * 48000);
  assert.ok(soundtrack.some((sample) => Math.abs(sample) > 0.1));
  assert.match(await readFile(join(outDir, "index.html"), "utf8"), /data-composition-id="advert"/);
});

const advertDir = fileURLToPath(new URL("../", import.meta.url));

test("the output-folder guard refuses anything but advert/build or a temp subfolder", () => {
  for (const outDir of [
    repoRoot,
    advertDir,
    join(advertDir, "src"),
    join(advertDir, "sfx"),
    join(advertDir, "scripts"),
    join(advertDir, "tests"),
    join(advertDir, "node_modules"),
    join(advertDir, "out"),
    join(advertDir, "build-evil"),
    join(advertDir, "build/nested"),
    tmpdir(),
    `${join(advertDir, "build")}/../src`,
  ]) assert.throws(() => assertSafeOutDir(outDir), /refusing/, outDir);
});

test("the output-folder guard allows advert/build and a temp subfolder", () => {
  assertSafeOutDir(join(advertDir, "build"));
  assertSafeOutDir(join(tmpdir(), "advert-guard"));
});
