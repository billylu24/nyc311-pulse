import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("filters, shares, opens evidence, and exports aggregates", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Find the signal/i })).toBeVisible();
  await expect(page.locator("main")).toHaveAttribute("data-app-ready", "true");
  await page.getByLabel("Borough").selectOption("Bronx");
  await expect(page).toHaveURL(/borough=Bronx/);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: /CSV/i }).click();
  expect((await download).suggestedFilename()).toBe("nyc311-pulse-signals.csv");
  await page.getByRole("link", { name: /Inspect evidence/i }).first().click();
  await expect(page.getByRole("heading", { name: /volume moved above/i })).toBeVisible();
  await expect(page.getByText(/not population need or agency quality/i).first()).toBeVisible();
});

test("home has no serious or critical axe violations", async ({ page }) => {
  await page.goto("/");
  const results = await new AxeBuilder({ page }).analyze();
  const severe = results.violations.filter(item => item.impact === "critical" || item.impact === "serious");
  expect(severe).toEqual([]);
});

test("evaluation lab exposes locked metrics and the pending human gate", async ({ page }) => {
  await page.goto("/evaluation");
  await expect(page.getByRole("heading", { name: /A signal earns release/i })).toBeVisible();
  await expect(page.getByText(/locked synthetic test/i).first()).toBeVisible();
  await expect(page.getByText("Real-history review", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /download packet/i })).toBeVisible();
});

test("district selection changes the explore trend title", async ({ page }) => {
  await page.goto("/explore");
  await expect(page.locator("main")).toHaveAttribute("data-app-ready", "true");
  await page.getByLabel("Selected district").selectOption("Queens 01");
  await expect(page.getByRole("region", { name: "Queens 01 evaluated category volume" })).toBeVisible();
});

test("cached snapshot remains usable when the API check fails", async ({ page }) => {
  await page.route("**/data/snapshot.json", route => route.abort());
  await page.goto("/");
  await expect(page.getByText(/verified cached snapshot/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: /What needs investigation/i })).toBeVisible();
});
