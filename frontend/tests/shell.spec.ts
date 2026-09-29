import { expect, test } from "@playwright/test";

test("shell works at desktop and phone width in light and dark", async ({ page }) => {
  const stamp = Date.now().toString(36);
  const username = `shell${stamp}`.slice(0, 32);
  await page.addInitScript(() => {
    window.localStorage.setItem("spendpilot-theme", "light");
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/register");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Email").fill(`${username}@example.com`);
  await page.getByLabel("Password").fill("correct-horse-battery");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByTestId("sidebar")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByText("There is no statement data here")).toBeVisible();

  const desktopOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
  );
  expect(desktopOverflow).toBe(true);

  await page.getByTestId("theme-toggle").click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect
    .poll(async () => page.evaluate(() => getComputedStyle(document.body).backgroundColor))
    .toBe("rgb(16, 21, 29)");

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByTestId("sidebar")).toBeHidden();
  await page.getByTestId("open-menu").click();
  await expect(page.locator("#mobile-navigation").getByRole("link", { name: "Overview" })).toBeVisible();
  const phoneOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
  );
  expect(phoneOverflow).toBe(true);
});
