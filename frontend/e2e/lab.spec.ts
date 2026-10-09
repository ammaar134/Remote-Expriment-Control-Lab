import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
const screenshot = (name: string) =>
  fileURLToPath(new URL("../../docs/screenshots/" + name, import.meta.url));

test("configure -> real live samples -> refresh -> completion -> saved review, then confirmed stop", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByText("Instrument connected", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Recipe name", { exact: true })
    .fill("Seeded response study");
  for (let i = 1; i <= 3; i++)
    await page.getByLabel("Step " + i + " duration", { exact: true }).fill("2");
  if (process.env.UPDATE_SCREENSHOTS === "1")
    await page.screenshot({
      path: screenshot("configure.png"),
      fullPage: true,
    });
  await page.getByRole("button", { name: /Start experiment/ }).click();
  await expect(page).toHaveURL(/#monitor\//);
  const runId = page.url().split("/").pop()!;
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/runs/" + runId)).json()).persisted_seq,
    )
    .toBeGreaterThan(5);
  await page.reload();
  await expect(page.getByRole("img", { name: /Raw response/ })).toBeVisible();
  if (process.env.UPDATE_SCREENSHOTS === "1")
    await page.screenshot({ path: screenshot("monitor.png"), fullPage: true });
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/runs/" + runId)).json()).recording,
      { timeout: 12000 },
    )
    .toBe("complete");
  await page.goto("/#review/" + runId);
  await expect(
    page.getByText("300 saved samples", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Seeded response study" }),
  ).toBeVisible();
  if (process.env.UPDATE_SCREENSHOTS === "1")
    await page.screenshot({ path: screenshot("review.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  if (process.env.UPDATE_SCREENSHOTS === "1")
    await page.screenshot({
      path: screenshot("review-mobile.png"),
      fullPage: true,
    });
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page.goto("/#configure");
  await page.getByRole("button", { name: /Start experiment/ }).click();
  await expect(page).toHaveURL(/#monitor\//);
  await expect(
    page.getByRole("button", { name: /Stop experiment/ }),
  ).toBeEnabled();
  await page.getByRole("button", { name: /Stop experiment/ }).click();
  await expect(
    page.getByText("stopped", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Data: complete", { exact: true }).first(),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
