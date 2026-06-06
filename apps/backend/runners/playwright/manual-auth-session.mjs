import { chromium } from "playwright";
import readline from "node:readline";

const [, , startUrl, storageStatePath, channel = ""] = process.argv;

if (!startUrl || !storageStatePath) {
  console.error("Usage: node manual-auth-session.mjs <startUrl> <storageStatePath> [channel]");
  process.exit(2);
}

const browser = await chromium.launch({
  channel: channel || undefined,
  headless: false,
});

const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  ignoreHTTPSErrors: true,
});

const page = await context.newPage();
await page.goto(startUrl, { waitUntil: "domcontentloaded" }).catch(() => {});

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false,
});

let completed = false;

for await (const line of rl) {
  const command = line.trim().toLowerCase();
  if (command === "save") {
    await context.storageState({ path: storageStatePath });
    completed = true;
    break;
  }
  if (command === "cancel") {
    completed = true;
    break;
  }
}

await browser.close();
process.exit(completed ? 0 : 1);
