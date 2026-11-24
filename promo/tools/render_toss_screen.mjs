// Capture the Toss Front 2 screen animation (promo/parts/toss_front_screen/index.html) frame by frame and encode it.
//   node promo/tools/render_toss_screen.mjs                  -> promo/parts/toss_front_screen/toss_front_screen.mp4
//   node promo/tools/render_toss_screen.mjs --stills 0,4,7.5 -> PNG stills at those seconds (into --out dir)
// Needs playwright-core (PLAYWRIGHT_CORE or the copy under ~/.hermes) and a Chromium headless shell; ffmpeg for the mp4.
import { createRequire } from "module";
import { execFileSync } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";
import { fileURLToPath, pathToFileURL } from "url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DIR = path.resolve(HERE, "../parts/toss_front_screen");
const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(k) ? args[args.indexOf(k) + 1] : d);

const require = createRequire(import.meta.url);
const pwPath = process.env.PLAYWRIGHT_CORE || path.join(os.homedir(), ".hermes/hermes-agent/node_modules/playwright-core");
const { chromium } = require(pwPath);
const shellRoot = path.join(os.homedir(), "Library/Caches/ms-playwright");
const shellDir = fs.readdirSync(shellRoot).filter(d => d.startsWith("chromium_headless_shell")).sort().pop();
const exe = process.env.CHROME_PATH || path.join(shellRoot, shellDir, "chrome-headless-shell-mac-arm64/chrome-headless-shell");

const browser = await chromium.launch({ executablePath: exe });
const page = await browser.newPage({ viewport: { width: 800, height: 1280 }, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(path.join(DIR, "index.html")).href + "?capture");
await page.evaluate(() => document.fonts.ready);
await page.waitForFunction(() => [...document.images].every(i => i.complete));
const { duration, fps } = await page.evaluate(() => window.TIMELINE);

const grab = async (t, file) => {
  await page.evaluate(tt => window.seek(tt), t);
  await page.screenshot({ path: file });
};

if (args.includes("--stills")) {
  const out = opt("--out", DIR);
  fs.mkdirSync(out, { recursive: true });
  for (const s of opt("--stills").split(",")) await grab(parseFloat(s), path.join(out, `still_${s}.png`));
} else {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "tossfront-"));
  const n = Math.round(duration * fps);
  for (let i = 0; i < n; i++) await grab(i / fps, path.join(tmp, `f${String(i).padStart(4, "0")}.png`));
  const mp4 = opt("--out", path.join(DIR, "toss_front_screen.mp4"));
  execFileSync(process.env.FFMPEG || "ffmpeg", ["-y", "-loglevel", "error", "-framerate", String(fps), "-i", path.join(tmp, "f%04d.png"),
    "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4]);
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`wrote ${mp4} (${n} frames @ ${fps} fps)`);
}
await browser.close();
