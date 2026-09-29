import { expect, test } from "@playwright/test";
import fs from "node:fs";

const shots = process.env.PHASE7_SCREENSHOT_DIR ?? "/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-7";

const pages = [
  ["/overview", "overview"],
  ["/money/cards", "cards"],
  ["/money/transactions", "transactions"],
  ["/money/statements", "statements"],
  ["/money/analytics", "analytics"],
  ["/money/obligations", "obligations"],
  ["/intelligence/advisor", "advisor"],
  ["/intelligence/scenarios", "scenarios"],
  ["/settings", "settings"],
];

test("keyboard pass and 200% zoom on the main screens", async ({ page }) => {
  test.setTimeout(120_000);
  fs.mkdirSync(shots, { recursive: true });
  const stamp = Date.now().toString(36);
  const username = `qa${stamp}`.slice(0, 32);
  await page.addInitScript(() => {
    window.localStorage.setItem("spendpilot-theme", "light");
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/register");
  await page.getByLabel("Username").focus();
  await page.keyboard.type(username);
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Email")).toBeFocused();
  await page.keyboard.type(`${username}@example.com`);
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password")).toBeFocused();
  await page.keyboard.type("correct-horse-battery");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Create account" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/overview$/);

  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog", { name: "Search navigation" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Search navigation" })).toBeHidden();

  for (let step = 0; step < 20; step += 1) {
    const current = await page.evaluate(() => document.activeElement?.getAttribute("data-testid"));
    if (current === "theme-toggle") break;
    await page.keyboard.press("Tab");
  }
  await expect(page.getByTestId("theme-toggle")).toBeFocused();
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineStyle);
  expect(outline).not.toBe("none");
  await page.screenshot({ path: `${shots}/overview-keyboard-focus-1440-light.png` });
  await page.keyboard.press("Enter");
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.keyboard.press("Enter");
  await expect(page.locator("html")).not.toHaveClass(/dark/);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByTestId("open-menu").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#mobile-navigation").getByRole("link", { name: "Overview" })).toBeVisible();
  await page.screenshot({ path: `${shots}/overview-keyboard-menu-390-light.png` });
  await page.keyboard.press("Escape");
  await expect(page.locator("#mobile-navigation")).toBeHidden();

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/overview");
  await settle(page);
  await page.screenshot({ path: `${shots}/overview-1440-light.png` });

  await page.getByRole("link", { name: "Obligations" }).click();
  await page.getByLabel("Description").fill("Laptop");
  await page.getByLabel("Principal AED").fill("6000.00");
  await page.getByLabel("Parts").fill("12");
  await page.getByLabel("Posted on").fill("2026-09-01");
  await page.getByRole("button", { name: "Save purchase" }).click();
  await expect(page.getByText("Monthly commitment 500.00 AED")).toBeVisible();

  await shoot(page, 720, 450, "zoom200");
  await page.goto("/overview");
  await settle(page);
  await page.getByTestId("theme-toggle").click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await assertNoOverflow(page);
  await page.screenshot({ path: `${shots}/overview-720-zoom200-dark.png` });
  await page.getByTestId("theme-toggle").click();

  await page.setViewportSize({ width: 512, height: 384 });
  await page.goto("/overview");
  await settle(page);
  await page.screenshot({ path: `${shots}/overview-512-zoom200-light.png`, fullPage: true });

  await page.setViewportSize({ width: 195, height: 422 });
  await page.goto("/overview");
  await settle(page);
  await page.screenshot({ path: `${shots}/overview-195-zoom200-light.png`, fullPage: true });
  await page.goto("/money/obligations");
  await expect(page.getByText("Monthly commitment 500.00 AED")).toBeVisible();
  await settle(page);
  await page.screenshot({ path: `${shots}/obligations-195-zoom200-light.png`, fullPage: true });
});

async function settle(page: import("@playwright/test").Page) {
  await expect(page.getByTestId("shell")).toBeVisible();
  await expect(page.getByRole("heading").first()).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await assertNoOverflow(page);
}

async function shoot(page: import("@playwright/test").Page, width: number, height: number, label: string) {
  await page.setViewportSize({ width, height });
  for (const [path, name] of pages) {
    await page.goto(path);
    await settle(page);
    await page.screenshot({ path: `${shots}/${name}-${width}-${label}-light.png`, fullPage: true });
  }
}

async function assertNoOverflow(page: import("@playwright/test").Page) {
  const fits = await page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
  );
  expect(fits).toBe(true);
}
