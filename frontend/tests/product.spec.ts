import { expect, test } from "@playwright/test";

test("obligations, analytics, and backup stay usable", async ({ page }) => {
  const stamp = Date.now().toString(36);
  const username = `phase6${stamp}`.slice(0, 32);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/register");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Email").fill(`${username}@example.com`);
  await page.getByLabel("Password").fill("correct-horse-battery");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByRole("heading", { name: "Monthly briefing" })).toBeVisible();

  await page.getByRole("link", { name: "Obligations" }).click();
  await expect(page.getByRole("heading", { name: "Obligations" })).toBeVisible();
  await page.getByLabel("Description").fill("Laptop");
  await page.getByLabel("Principal AED").fill("6000.00");
  await page.getByLabel("Parts").fill("12");
  await page.getByLabel("Posted on").fill("2026-09-01");
  await page.getByRole("button", { name: "Save purchase" }).click();
  await expect(page.getByText("Monthly commitment 500.00 AED")).toBeVisible();
  await expect(page.getByText("Purchase, counted once")).toBeVisible();
  await expect(page.getByText("6000.00 AED").first()).toBeVisible();
  await expect(page.getByText("500.00 AED").first()).toBeVisible();

  await page.getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();
  await expect(page.getByText("This is not complete coverage.")).toBeVisible();
  await expect(page.getByRole("row", { name: "Net spending" })).toContainText("6000.00 AED");
  await expect(page.getByRole("row", { name: "Instalment purchases" })).toContainText("6000.00 AED");
  await expect(page.getByRole("row", { name: "Card payments" })).toContainText("0.00 AED");

  await page.getByRole("link", { name: "Transactions" }).click();
  await expect(page.getByRole("heading", { name: "Manual entry" })).toBeVisible();
  await page.getByLabel("Date").fill("2026-09-12");
  await page.getByLabel("Amount AED").fill("10.00");
  await page.getByLabel("Description").fill("Market");
  await page.getByRole("button", { name: "Save entry" }).click();
  await expect(page.getByText("Cash purchase saved.")).toBeVisible();

  await page.getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByRole("row", { name: "Net spending" })).toContainText("6010.00 AED");

  await page.getByRole("link", { name: "Statements" }).click();
  await expect(page.getByRole("heading", { name: "Statements", exact: true })).toBeVisible();
  await expect(page.getByText("Real files were not used to confirm these layouts.")).toBeVisible();
  await expect(page.getByText("English and Arabic OCR")).toBeVisible();
  await expect(page.getByText("A text PDF is not sent through OCR.")).toBeVisible();

  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Encrypted backup" })).toBeVisible();
  const secrets = page.getByRole("checkbox", { name: "Include provider keys and saved PDF passwords" });
  await expect(secrets).not.toBeChecked();
  await expect(page.getByLabel("Your category")).toBeVisible();
  await page.getByLabel("Your category").fill("School");
  await page.getByRole("button", { name: "Add category" }).click();
  await expect(page.getByText("Category saved.")).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/money/obligations");
  const phoneOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
  );
  expect(phoneOverflow).toBe(true);
  await expect(page.getByText("Monthly commitment 500.00 AED")).toBeVisible();
});
