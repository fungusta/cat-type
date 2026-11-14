// Assembles the advert into a self-contained HyperFrames project: page, styles,
// bundled script, GSAP, fonts, the cat artwork the advert uses and one soundtrack WAV.

import { existsSync, readFileSync } from "node:fs";
import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import * as esbuild from "esbuild";
import { DURATION, LOOKS, SAMPLE_RATE, UNLOCKS, soundCues } from "../src/timeline.mjs";
import { encodeWav, mixCues, parseWav } from "../src/mix.mjs";
import { SYNTHS } from "../src/sfx-synth.mjs";

const advertDir = fileURLToPath(new URL("../", import.meta.url));
const repoRoot = fileURLToPath(new URL("../../", import.meta.url));
const srcDir = join(advertDir, "src");
const modulesDir = join(advertDir, "node_modules");
const RECORDED_SOUNDS = ["key-1", "key-2", "key-3", "key-4", "key-5", "key-6", "space"];
const FONTS = ["nunito-latin-700-normal.woff2", "nunito-latin-800-normal.woff2"];
const ACCESSORY_LINE = /Accessory\(\s*"([^"]+)"\s*,\s*"[^"]*"\s*,\s*"([^"]+)"/;

/** Reads the accessory catalog from cat_accessories.py: id -> { slot, hidden }. */
export function readCatalog(root) {
  const catalog = new Map();
  for (const line of readFileSync(join(root, "cat_accessories.py"), "utf8").split("\n")) {
    const match = line.match(ACCESSORY_LINE);
    if (match) catalog.set(match[1], { slot: match[2], hidden: line.includes("hidden=True") });
  }
  return catalog;
}

/** Throws when an accessory is unknown, secret, or worn in a slot other than its own. */
export function assertPublishable(looks, extraIds, catalog) {
  const worn = Object.values(looks).flatMap(({ outfit }) => Object.entries(outfit));
  for (const [slot, id] of [...worn, ...extraIds.map((id) => [null, id])]) {
    const entry = catalog.get(id);
    if (!entry) throw new Error(`accessory "${id}" is not in the catalog`);
    if (entry.hidden) throw new Error(`accessory "${id}" is a secret and must not appear in the advert`);
    if (slot !== null && slot !== entry.slot) throw new Error(`accessory "${id}" is a ${entry.slot} accessory, not ${slot}`);
  }
}

/** Builds the project into outDir (default advert/build) and returns its path. */
export async function build({ outDir = join(advertDir, "build") } = {}) {
  assertPublishable(LOOKS, UNLOCKS.map((unlock) => unlock.id), readCatalog(repoRoot));
  const out = resolve(outDir);
  assertSafeOutDir(out);
  const copies = plannedCopies();
  for (const [from] of copies) if (!existsSync(from)) throw new Error(`missing source file ${from}`);

  await rm(out, { recursive: true, force: true });
  for (const [from, to] of copies) {
    await mkdir(dirname(join(out, to)), { recursive: true });
    await copyFile(from, join(out, to));
  }
  await esbuild.build({ entryPoints: [join(srcDir, "stage.js")], bundle: true, format: "iife", outfile: join(out, "js/advert.js"), logLevel: "silent" });
  await mkdir(join(out, "sfx"), { recursive: true });
  await writeFile(join(out, "sfx/soundtrack.wav"), await soundtrack());
  return out;
}

/** Refuses any outDir that is not strictly inside advert/ or the OS temp directory. */
function assertSafeOutDir(out) {
  const inside = (base) => {
    const path = relative(resolve(base), out);
    return path !== "" && !path.startsWith("..") && !isAbsolute(path);
  };
  if (!inside(advertDir) && !inside(tmpdir())) {
    throw new Error(`refusing to empty ${out}: outDir must be inside ${advertDir} or ${tmpdir()}`);
  }
}

/** [source, path inside the build] pairs for every copied file. */
function plannedCopies() {
  const cats = new Set(Object.values(LOOKS).map((look) => look.cat));
  const accessories = new Set([...Object.values(LOOKS).flatMap((look) => Object.values(look.outfit)), ...UNLOCKS.map((unlock) => unlock.id)]);
  return [
    [join(srcDir, "index.html"), "index.html"],
    [join(srcDir, "advert.css"), "advert.css"],
    [join(modulesDir, "gsap/dist/gsap.min.js"), "js/gsap.min.js"],
    ...FONTS.map((font) => [join(modulesDir, "@fontsource/nunito/files", font), `fonts/${font}`]),
    ...[...cats].map((cat) => [join(repoRoot, "assets/vector-cats", `${cat}.svg`), `assets/cats/${cat}.svg`]),
    ...[...accessories].map((id) => [join(repoRoot, "assets/accessories", `${id}.svg`), `assets/accessories/${id}.svg`]),
  ];
}

/** Mixes every cue over the advert's duration into one PCM16 mono WAV. */
async function soundtrack() {
  const sounds = Object.fromEntries(Object.entries(SYNTHS).map(([name, synth]) => [name, synth()]));
  for (const name of RECORDED_SOUNDS) {
    const file = join(advertDir, "sfx", `${name}.wav`);
    sounds[name] = parseWav(await readFile(file), file);
  }
  return encodeWav(mixCues(soundCues(), sounds, { sampleRate: SAMPLE_RATE, duration: DURATION }), SAMPLE_RATE);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  console.log(await build());
}
