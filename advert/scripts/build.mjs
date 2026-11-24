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
const defaultOutDir = resolve(advertDir, "build");
const modulesDir = join(advertDir, "node_modules");
const RECORDED_SOUNDS = ["key-1", "key-2", "key-3", "key-4", "key-5", "key-6", "space"];
const FONTS = ["nunito-latin-700-normal.woff2", "nunito-latin-800-normal.woff2"];
// One Accessory("id", "name", "slot", ...) call, across lines, up to its closing parenthesis.
const ACCESSORY_CALL = /\bAccessory\(\s*"([^"]+)"\s*,\s*"[^"]*"\s*,\s*"([^"]+)"[^)]*\)/g;

/** Parses cat_accessories.py text into id -> { slot, hidden }; throws if it finds no accessories. */
export function parseCatalog(text) {
  const catalog = new Map();
  for (const match of text.matchAll(ACCESSORY_CALL)) {
    catalog.set(match[1], { slot: match[2], hidden: /\bhidden\s*=\s*True\b/.test(match[0]) });
  }
  if (catalog.size === 0) throw new Error("found no Accessory(...) entries in cat_accessories.py");
  return catalog;
}

/** Reads the accessory catalog from cat_accessories.py: id -> { slot, hidden }. */
export function readCatalog(root) {
  return parseCatalog(readFileSync(join(root, "cat_accessories.py"), "utf8"));
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
export async function build({ outDir = defaultOutDir } = {}) {
  assertSafeOutDir(outDir);
  assertPublishable(LOOKS, UNLOCKS.map((unlock) => unlock.id), readCatalog(repoRoot));
  const out = resolve(outDir);
  const copies = plannedCopies();
  for (const from of [...copies.map(([source]) => source), ...RECORDED_SOUNDS.map(recordedSound)]) {
    if (!existsSync(from)) throw new Error(`missing source file ${from}`);
  }

  await rm(out, { recursive: true, force: true });
  for (const [from, to] of copies) {
    await mkdir(dirname(join(out, to)), { recursive: true });
    await copyFile(from, join(out, to));
  }
  await esbuild.build({ entryPoints: [join(srcDir, "stage.js")], bundle: true, format: "iife", outfile: join(out, "js/advert.js"), supported: { "template-literal": false }, logLevel: "warning" });
  await mkdir(join(out, "sfx"), { recursive: true });
  await writeFile(join(out, "sfx/soundtrack.wav"), await soundtrack());
  return out;
}

/** Throws unless outDir is exactly advert/build or a folder strictly inside the OS temp directory. Touches no files. */
export function assertSafeOutDir(outDir) {
  const out = resolve(outDir);
  const temp = resolve(tmpdir());
  const inTemp = (() => {
    const path = relative(temp, out);
    return path !== "" && !path.startsWith("..") && !isAbsolute(path);
  })();
  if (out !== defaultOutDir && !inTemp) {
    throw new Error(`refusing to empty ${out}: outDir must be ${defaultOutDir} or a folder inside ${temp}`);
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

/** The path of a recorded sound in advert/sfx/. */
function recordedSound(name) {
  return join(advertDir, "sfx", `${name}.wav`);
}

/** Mixes every cue over the advert's duration into one PCM16 mono WAV. */
async function soundtrack() {
  const sounds = Object.fromEntries(Object.entries(SYNTHS).map(([name, synth]) => [name, synth()]));
  for (const name of RECORDED_SOUNDS) {
    const file = recordedSound(name);
    sounds[name] = parseWav(await readFile(file), file);
  }
  return encodeWav(mixCues(soundCues(), sounds, { sampleRate: SAMPLE_RATE, duration: DURATION }), SAMPLE_RATE);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  console.log(await build());
}
