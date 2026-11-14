import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { readCatalog, assertPublishable, build } from "../scripts/build.mjs";
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

test("a secret accessory stops the build", () => {
  assert.throws(() => assertPublishable({ x: { cat: "gray", outfit: { neck: "moon-pendant" } } }, [], catalog), /moon-pendant/);
});

test("an unknown accessory stops the build", () => {
  assert.throws(() => assertPublishable({}, ["nope"], catalog), /nope/);
});

test("an accessory in the wrong slot stops the build", () => {
  assert.throws(() => assertPublishable({ x: { cat: "gray", outfit: { hat: "sunglasses" } } }, [], catalog), /sunglasses/);
});

test("build writes a complete project", async () => {
  const outDir = await mkdtemp(join(tmpdir(), "advert-"));
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

test("build refuses to empty a folder outside advert/ and the temp directory", async () => {
  await assert.rejects(build({ outDir: repoRoot }), /refus/i);
  await assert.rejects(build({ outDir: fileURLToPath(new URL("../", import.meta.url)) }), /refus/i);
  await assert.rejects(build({ outDir: join(repoRoot, "assets") }), /refus/i);
});
