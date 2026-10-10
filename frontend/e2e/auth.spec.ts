import { test, expect } from "@playwright/test";

test("sign-in keeps slow typing and errors stable, then stops polling on expiry", async ({
  page,
}) => {
  let authenticated = false;
  let apiCalls = 0;
  let loginCalls = 0;
  let navigations = 0;
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame()) navigations++;
  });
  await page.route("**/auth/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/auth/login") {
      loginCalls++;
      if (route.request().postDataJSON().password !== "test-browser-password") {
        await route.fulfill({
          status: 401,
          json: { detail: "Username or password is incorrect" },
        });
        return;
      }
      authenticated = true;
    }
    if (path === "/auth/logout") authenticated = false;
    await route.fulfill({ json: { authenticated, mode: "hosted" } });
  });
  await page.route("**/api/**", async (route) => {
    apiCalls++;
    await route.fulfill({
      status: 401,
      json: { detail: "Operator sign-in required" },
    });
  });
  await page.goto("/");
  const password = page.getByLabel("Password", { exact: true });
  await expect(password).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath("sign-in.png"),
    fullPage: true,
  });
  await password.fill("partially typed");
  // Reproduce three of the reported five-second intervals without wall-clock waits.
  await page.clock.install();
  await page.clock.runFor(16000);
  await expect(password).toHaveValue("partially typed");
  expect(navigations).toBe(1);
  expect(apiCalls).toBe(0);
  expect(loginCalls).toBe(0);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "Username or password is incorrect",
  );
  await expect(password).toHaveValue("partially typed");
  await page.clock.runFor(16000);
  expect(loginCalls).toBe(1);
  expect(apiCalls).toBe(0);
  await password.fill("test-browser-password");
  await page.getByRole("button", { name: "Show password" }).click();
  await expect(password).toHaveAttribute("type", "text");
  await page.getByRole("button", { name: "Hide password" }).click();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "Your session has ended. Sign in to reconnect to the lab.",
  );
  const callsAfterExpiry = apiCalls;
  await password.fill("still typing");
  await page.clock.runFor(16000);
  await expect(password).toHaveValue("still typing");
  expect(apiCalls).toBe(callsAfterExpiry);
  expect(navigations).toBe(1);
  await page.setViewportSize({ width: 390, height: 844 });
  await password.fill("");
  await page.screenshot({
    path: test.info().outputPath("sign-in-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("session check failure offers a manual retry without reloading", async ({
  page,
}) => {
  let checks = 0;
  await page.route("**/auth/session", async (route) => {
    checks++;
    await route.fulfill({ status: 503, json: { detail: "Waking up" } });
  });
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("could not be reached");
  const initial = checks;
  await page.clock.install();
  await page.clock.runFor(16000);
  expect(checks).toBe(initial);
  await page.getByRole("button", { name: "Try connection again" }).click();
  await expect.poll(() => checks).toBe(initial + 1);
});
