import { chromium } from "@playwright/test";
import { mkdir, rm } from "node:fs/promises";
import path from "node:path";

const baseURL = process.env.DEMO_BASE_URL ?? "http://127.0.0.1:3000";
const outputDir = path.resolve(".cache/walkthrough-video");
const outputPath = path.resolve(".cache/nyc311-pulse-walkthrough.webm");

await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1280, height: 720 },
  deviceScaleFactor: 1,
  recordVideo: { dir: outputDir, size: { width: 1280, height: 720 } },
});

await context.addInitScript(() => {
  const installCursor = () => {
    if (document.querySelector("#walkthrough-cursor")) return;
    const style = document.createElement("style");
    style.textContent = `
      #walkthrough-cursor {
        position: fixed; left: 0; top: 0; width: 20px; height: 20px;
        border: 3px solid #fff; border-radius: 50%; background: #f65230;
        box-shadow: 0 2px 9px rgba(0,0,0,.45); pointer-events: none;
        transform: translate(-50%, -50%); z-index: 2147483647;
        transition: width .14s ease, height .14s ease, background .14s ease;
      }
      #walkthrough-cursor.clicking { width: 34px; height: 34px; background: #191917; }
    `;
    const cursor = document.createElement("div");
    cursor.id = "walkthrough-cursor";
    document.head.append(style);
    document.body.append(cursor);
    window.addEventListener("mousemove", event => {
      cursor.style.left = `${event.clientX}px`;
      cursor.style.top = `${event.clientY}px`;
    });
    window.addEventListener("mousedown", () => cursor.classList.add("clicking"));
    window.addEventListener("mouseup", () => cursor.classList.remove("clicking"));
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installCursor, { once: true });
  } else {
    installCursor();
  }
});

const page = await context.newPage();
const pause = milliseconds => page.waitForTimeout(milliseconds);

async function moveTo(locator, steps = 22) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (!box) throw new Error("Cannot move to a hidden walkthrough target");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps });
  await pause(350);
}

async function click(locator) {
  await moveTo(locator);
  await page.mouse.down();
  await pause(140);
  await page.mouse.up();
  await pause(850);
}

async function select(locator, value) {
  await moveTo(locator);
  await page.mouse.down();
  await pause(130);
  await page.mouse.up();
  await pause(350);
  await locator.selectOption(value);
  await pause(1200);
}

async function scroll(deltaY, pauses = 1) {
  await page.mouse.move(1180, 620, { steps: 14 });
  await page.mouse.wheel(0, deltaY);
  await pause(700 * pauses);
}

async function navigate(name, urlPattern) {
  await page.keyboard.press("Home");
  await pause(550);
  await click(page.getByRole("link", { name, exact: true }));
  await page.waitForURL(urlPattern);
  await page.waitForLoadState("networkidle");
  await pause(1000);
}

try {
  await page.goto(baseURL, { waitUntil: "networkidle" });
  await page.locator("main[data-app-ready='true']").waitFor();
  await page.mouse.move(90, 90);
  await pause(1800);

  await scroll(390, 2);
  await select(page.getByLabel("Borough"), "Bronx");
  const evidenceLink = page.getByRole("link", { name: /Inspect evidence/i }).first();
  await click(evidenceLink);
  await page.waitForLoadState("networkidle");
  await pause(1200);
  await scroll(500, 2);
  await scroll(430, 2);

  await navigate("Explore", /\/explore/);
  await scroll(360, 2);
  await select(page.getByLabel("Selected district"), "Queens 01");
  await scroll(550, 2);

  await navigate("Evaluation", /\/evaluation$/);
  await scroll(470, 2);
  await scroll(520, 2);

  await navigate("Methodology", /\/methodology$/);
  await scroll(520, 2);
  await scroll(520, 2);

  await navigate("Research queue", /\/$/);
  await pause(1700);
} finally {
  const video = page.video();
  await page.close();
  if (video) await video.saveAs(outputPath);
  await context.close();
  await browser.close();
}

console.log(`Recorded ${outputPath}`);
