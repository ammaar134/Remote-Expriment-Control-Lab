import { test, expect as baseExpect } from "@playwright/test";
import { fileURLToPath } from "node:url";
const expect = baseExpect.configure({ timeout: 15000 });
test.setTimeout(100000);

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  if (process.env.LAB_PASSWORD) {
    await page.getByLabel("Username", { exact: true }).fill("operator");
    await page
      .getByLabel("Password", { exact: true })
      .fill(process.env.LAB_PASSWORD);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByLabel("Recipe name", { exact: true })).toBeVisible();
  }
});

test("two real clocks, saved evidence, three time bases and responsive comparison", async ({
  page,
}) => {
  const devices = await (await page.request.get("/api/devices")).json();
  for (const d of devices) {
    if (d.observation.state === "FAULTED")
      await page.request.post(`/api/device/reset?device_id=${d.id}`, {
        headers: { Origin: new URL(page.url()).origin },
        data: { command_id: crypto.randomUUID() },
      });
  }
  await page.getByRole("button", { name: "Timing", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Put time in perspective." }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Start comparison" }),
  ).toBeEnabled();
  await page.getByLabel("Observation duration (s)").fill("26");
  await page.getByRole("button", { name: "Start comparison" }).click();
  await expect(page).toHaveURL(/#timing\//);
  const id = page.url().split("/").pop()!;
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`/api/timing/${id}`)).json()).status,
      { timeout: 65000 },
    )
    .toBe("complete");
  await expect(
    page.getByText("Offset and drift estimated.", { exact: true }),
  ).toHaveCount(2);
  await page
    .getByLabel("Time basis", { exact: true })
    .selectOption("received_utc");
  await expect(page.getByRole("img", { name: /receipt time/ })).toBeVisible();
  await page
    .getByLabel("Time basis", { exact: true })
    .selectOption("aligned_utc");
  await expect(
    page.getByRole("img", { name: /estimated aligned time/ }),
  ).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download timing evidence" }).click();
  expect((await downloadPromise).suggestedFilename()).toBe(`timing-${id}.json`);
  for (const width of [1440, 1270, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect(
      page.getByRole("heading", { name: "Clock evidence" }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    if (process.env.UPDATE_PHASE45_SCREENSHOTS)
      await page.screenshot({
        path: fileURLToPath(
          new URL(
            `../../.impeccable/review/phase45-timing-${width}.png`,
            import.meta.url,
          ),
        ),
        fullPage: true,
      });
  }
  await page.reload();
  await expect(
    page.getByText("Offset and drift estimated.", { exact: true }),
  ).toHaveCount(2);
  expect(await page.getByLabel("Saved comparison").inputValue()).toBe(id);
});

test("early Stop records separate device results and insufficient drift evidence", async ({
  page,
}) => {
  await page.goto("/#timing");
  await expect(
    page.getByRole("button", { name: "Start comparison" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Start comparison" }).click();
  await expect(page).toHaveURL(/#timing\//);
  await expect(
    page.getByRole("button", { name: "Stop both devices" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Stop both devices" }).click();
  const id = page.url().split("/").pop()!;
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`/api/timing/${id}`)).json()).status,
    )
    .toBe("partial");
  const result = await (await page.request.get(`/api/timing/${id}`)).json();
  for (const m of result.members) {
    expect(m.start.stop_result.status.state).toBe("STOPPED");
    expect(m.estimate.drift_ppm).toBeNull();
  }
});
