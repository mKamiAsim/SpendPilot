import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const outDir = process.env.PHASE2_OUT ?? "/cursor/stores/bc-0ab49cf1-1382-4750-afb7-4a738ee5f16a/media/phase-2";
const sizes = [
  { name: "1440", width: 1440, height: 900 },
  { name: "1024", width: 1024, height: 768 },
  { name: "390", width: 390, height: 844 },
];

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage();
const stamp = Date.now().toString(36);
const username = `vis${stamp}`.slice(0, 32);

await page.setViewportSize({ width: 1440, height: 900 });
await page.goto(baseURL);
await page.evaluate(() => window.localStorage.setItem("spendpilot-theme", "light"));
await page.goto(`${baseURL}/register`);
await page.getByLabel("Username").fill(username);
await page.getByLabel("Email").fill(`${username}@example.com`);
await page.getByLabel("Password").fill("correct-horse-battery");
await page.getByRole("button", { name: "Create account" }).click();
await page.waitForURL(/\/overview$/);

async function shot(name) {
  const file = `${outDir}/${name}.png`;
  await page.screenshot({ path: file, fullPage: true });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  console.log(`${overflow ? "OVERFLOW" : "ok"} ${file}`);
}

for (const theme of ["light", "dark"]) {
  await page.evaluate((value) => window.localStorage.setItem("spendpilot-theme", value), theme);
  for (const size of sizes) {
    await page.setViewportSize(size);
    await page.goto(`${baseURL}/overview`);
    if (theme === "dark") await page.locator("html.dark").waitFor();
    await page.getByTestId("dev-fixture-banner").waitFor();
    if (size.name === "1440" && theme === "light") {
      const text = await page.locator("main").innerText();
      for (const expected of ["4,770.55", "500.00", "3,240.15", "Development-only fixture", "لولو"]) {
        if (!text.includes(expected)) throw new Error(`Overview missing ${expected}`);
      }
    }
    await shot(`overview-${size.name}-${theme}`);

    await page.goto(`${baseURL}/money/transactions`);
    await page.getByTestId("dev-fixture-banner").waitFor();
    if (size.width < 768) await shot(`transactions-list-${size.name}-${theme}`);
    if (size.width < 768) await page.getByRole("button", { name: /Noon/ }).first().click();
    else await page.locator("tbody tr").nth(4).click();
    await page.getByTestId("evidence-drawer").waitFor();
    await shot(`transactions-${size.name}-${theme}`);
    await page.keyboard.press("Escape");

    await page.goto(`${baseURL}/intelligence/advisor`);
    await page.getByRole("heading", { name: "Advisor" }).waitFor();
    await shot(`advisor-${size.name}-${theme}`);
    if (size.width < 1280) {
      await page.getByRole("button", { name: "Evidence", exact: true }).click();
      await page.getByTestId("advisor-evidence-sheet").waitFor();
      await shot(`advisor-evidence-${size.name}-${theme}`);
      await page.getByRole("button", { name: "Close", exact: true }).click();
    }
  }
}

await page.setViewportSize({ width: 1440, height: 900 });
await page.evaluate(() => window.localStorage.setItem("spendpilot-theme", "light"));
await page.goto(`${baseURL}/dev/components`);
await page.getByRole("heading", { name: "Component preview" }).waitFor();
await shot("components-1440-light");
await page.evaluate(() => window.localStorage.setItem("spendpilot-theme", "dark"));
await page.reload();
await page.getByRole("heading", { name: "Component preview" }).waitFor();
await shot("components-1440-dark");

await browser.close();
