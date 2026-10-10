import { afterEach, expect, it, vi } from "vitest";
import { api, resetApiSession } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("ignores a delayed unauthorized response from an earlier sign-in session", async () => {
  let finish!: (response: Response) => void;
  vi.stubGlobal(
    "fetch",
    () =>
      new Promise<Response>((resolve) => {
        finish = resolve;
      }),
  );
  const expired = vi.fn();
  window.addEventListener("lab:sign-in-required", expired);
  try {
    const oldRequest = api("/device").catch((error: Error) => error.message);
    resetApiSession();
    finish(
      new Response(JSON.stringify({ detail: "Sign in" }), { status: 401 }),
    );
    expect(await oldRequest).toBe("Sign in");
    expect(expired).not.toHaveBeenCalled();
    const currentRequest = api("/device").catch(() => null);
    finish(
      new Response(JSON.stringify({ detail: "Sign in" }), { status: 401 }),
    );
    await currentRequest;
    expect(expired).toHaveBeenCalledOnce();
  } finally {
    window.removeEventListener("lab:sign-in-required", expired);
  }
});
