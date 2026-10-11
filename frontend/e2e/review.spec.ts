import { test, expect as baseExpect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const expect = baseExpect.configure({ timeout: 15000 });
test.setTimeout(90000);

test.beforeEach(async ({ page }) => {
  if (process.env.LAB_PASSWORD) {
    await page.goto("/");
    await page
      .getByLabel("Username", { exact: true })
      .fill(process.env.LAB_USERNAME || "operator");
    await page
      .getByLabel("Password", { exact: true })
      .fill(process.env.LAB_PASSWORD);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByLabel("Recipe name", { exact: true })).toBeVisible();
  }
});

test("saved versions remain immutable and Start records the selected revision", async ({
  page,
}) => {
  const device = await (await page.request.get("/api/device")).json();
  test.skip(
    !device.connected,
    "This acquisition check requires the real simulator",
  );
  await page.goto("/#configure");
  const name = "Recipe version study " + Date.now();
  await page.getByLabel("Recipe name", { exact: true }).fill(name);
  for (let index = 1; index <= 3; index++)
    await page.getByLabel(`Step ${index} duration`, { exact: true }).fill("1");
  await page.getByRole("button", { name: "Save recipe", exact: true }).click();
  await expect(
    page.getByText("Version 1 · saved", { exact: true }),
  ).toBeVisible();
  const firstId = await page.getByLabel("Load a saved recipe").inputValue();
  await page.getByLabel("Step 1 setpoint", { exact: true }).fill("0.45");
  await expect(
    page.getByRole("button", { name: /Start experiment/ }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Save new version", exact: true })
    .click();
  await expect(
    page.getByText("Version 2 · saved", { exact: true }),
  ).toBeVisible();
  const secondId = await page.getByLabel("Load a saved recipe").inputValue();
  const first = await (
    await page.request.get("/api/recipes/" + firstId)
  ).json();
  expect(first.recipe.steps[0].setpoint).toBe(0.25);
  expect(firstId).not.toBe(secondId);
  await page.getByRole("button", { name: /Start experiment/ }).click();
  await expect(page).toHaveURL(/#monitor\//);
  const runId = page.url().split("/").pop()!;
  await expect
    .poll(
      async () =>
        (await (await page.request.get("/api/runs/" + runId)).json()).recording,
    )
    .toBe("complete");
  const run = await (await page.request.get("/api/runs/" + runId)).json();
  expect(run.recipe_id).toBe(secondId);
  expect(run.snapshot.recipe_version.revision).toBe(2);
  await page.goto("/#review/" + runId);
  await page.getByLabel("Find a run").fill(name);
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect(
    page
      .getByRole("region", { name: "Run history" })
      .getByRole("button", { name: new RegExp(name) }),
  ).toHaveCount(1);
  await page
    .getByLabel("Find a run")
    .fill("no-such-synthetic-run-" + Date.now());
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect(page.getByText("No runs match these filters.")).toBeVisible();
  await page.getByRole("button", { name: "Clear", exact: true }).click();
  await page.getByRole("button", { name: "Configure", exact: true }).click();
  await page.goBack();
  await expect(page).toHaveURL(new RegExp("#review/" + runId));
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
});

test("saved review exports full data and replays without control traffic", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const device = await (await page.request.get("/api/device")).json();
  if (process.env.LAB_EXPECT_OFFLINE === "1")
    expect(device.connected).toBe(false);
  const runs = await (
    await page.request.get("/api/runs?recording=complete")
  ).json();
  const saved = runs.find(
    (run: { persisted_seq: number }) => run.persisted_seq >= 5,
  );
  expect(saved).toBeTruthy();
  const prefix = "/api/runs/" + saved.id;
  const samples = await (await page.request.get(prefix + "/samples")).json();
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/"))
      requests.push(request.method() + " " + new URL(request.url()).pathname);
  });
  await page.goto("/#review/" + saved.id);
  await expect(
    page.getByText(`${samples.length} saved samples`, { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Chart window").selectOption("5");
  await expect(
    page.getByText(`${samples.length} saved samples`, { exact: true }),
  ).toBeVisible();
  const csvEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV", exact: true }).click();
  const csv = await csvEvent;
  const csvText = await readFile((await csv.path())!, "utf8");
  const csvRows = csvText.trim().split(/\r?\n/);
  expect(csvRows).toHaveLength(samples.length + 1);
  expect(csvRows[0]).toContain("response_raw_au");
  expect(csvRows[1]).toContain(String(samples[0].response));
  const metadataEvent = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download metadata", exact: true })
    .click();
  const metadata = JSON.parse(
    await readFile((await (await metadataEvent).path())!, "utf8"),
  );
  expect(metadata.summary.sample_count).toBe(samples.length);
  expect(metadata.run.id).toBe(saved.id);
  await page.getByLabel("Chart window").selectOption("all");
  await expect(
    page.getByText("Loading recorded evidence…", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Export CSV", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("img", {
      name: "Raw response, filtered response and reference over logical time",
      exact: true,
    }),
  ).toBeVisible();
  if (process.env.UPDATE_PHASE3_SCREENSHOTS === "1") {
    for (const [name, width, height] of [
      ["desktop", 1440, 1050],
      ["mobile", 390, 844],
      ["user-1270", 1270, 900],
    ] as const) {
      await page.setViewportSize({ width, height });
      await expect
        .poll(() =>
          page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
          ),
        )
        .toBe(true);
      await page.screenshot({
        path: fileURLToPath(
          new URL(`../../.impeccable/review/${name}.png`, import.meta.url),
        ),
        fullPage: true,
        animations: "disabled",
      });
    }
    await page.setViewportSize({ width: 1440, height: 1050 });
  }
  await page
    .getByRole("button", { name: "Replay saved run", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Replay · saved observations" }),
  ).toBeVisible();
  await page.getByLabel("Playback speed").selectOption("4");
  await page.getByRole("button", { name: "Play replay", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Pause replay", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Pause replay", exact: true }).click();
  await page.getByLabel("Seek replay", { exact: true }).focus();
  await page.keyboard.press("End");
  await expect(
    page.getByText(
      `${samples.length} / ${samples.length} recorded samples shown`,
      { exact: true },
    ),
  ).toBeVisible();
  if (process.env.UPDATE_PHASE3_SCREENSHOTS === "1")
    await page.screenshot({
      path: fileURLToPath(
        new URL("../../.impeccable/review/replay.png", import.meta.url),
      ),
      fullPage: true,
      animations: "disabled",
    });
  await page
    .getByRole("button", { name: "Restart replay", exact: true })
    .click();
  await expect(
    page.getByText(`0 / ${samples.length} recorded samples shown`, {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Exit replay", exact: true }).click();
  await page.reload();
  await expect(
    page.getByText(`${samples.length} saved samples`, { exact: true }),
  ).toBeVisible();
  expect(requests.every((request) => request.startsWith("GET "))).toBe(true);
  expect(requests.some((request) => request.includes("/api/device"))).toBe(
    false,
  );
  expect(errors).toEqual([]);
  if (process.env.UPDATE_PHASE3_SCREENSHOTS === "1") {
    await page.goto("/#configure");
    await expect(
      page.getByRole("option", { name: "Current draft", exact: true }),
    ).toBeAttached();
    for (const [name, width, height] of [
      ["configure-desktop", 1440, 1050],
      ["configure-mobile", 390, 844],
    ] as const) {
      await page.setViewportSize({ width, height });
      await expect
        .poll(() =>
          page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
          ),
        )
        .toBe(true);
      await page.screenshot({
        path: fileURLToPath(
          new URL(`../../.impeccable/review/${name}.png`, import.meta.url),
        ),
        fullPage: true,
        animations: "disabled",
      });
    }
  }
});
