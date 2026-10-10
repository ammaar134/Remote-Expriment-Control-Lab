import { useEffect, useState, type FormEvent } from "react";
import { App } from "./App";
import { resetApiSession } from "./api";

type Session = { authenticated: boolean; mode: "local" | "hosted" };

async function auth(path: string, payload?: unknown, signal?: AbortSignal) {
  const response = await fetch("/auth/" + path, {
    method: payload === undefined ? "GET" : "POST",
    credentials: "same-origin",
    signal,
    ...(payload === undefined
      ? {}
      : {
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.detail || "Sign-in could not be completed");
  return data as Session;
}

export function AuthGate() {
  const [session, setSession] = useState<Session | null>(null);
  const [username, setUsername] = useState("operator");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    const timeout = setTimeout(() => controller.abort(), 30000);
    setError("");
    auth("session", undefined, controller.signal)
      .then((value) => {
        if (!cancelled) setSession(value);
      })
      .catch(() => {
        if (!cancelled)
          setError(
            "The lab could not be reached. It may still be waking up. Try again in a moment.",
          );
      })
      .finally(() => clearTimeout(timeout));
    return () => {
      cancelled = true;
      controller.abort();
      clearTimeout(timeout);
    };
  }, [retry]);

  useEffect(() => {
    const expired = () => {
      if (!session?.authenticated) return;
      resetApiSession();
      setSession({ authenticated: false, mode: "hosted" });
      setPassword("");
      setError("Your session has ended. Sign in to reconnect to the lab.");
    };
    window.addEventListener("lab:sign-in-required", expired);
    return () => window.removeEventListener("lab:sign-in-required", expired);
  }, [session?.authenticated]);

  async function signIn(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await auth("login", { username, password }, AbortSignal.timeout(30000));
      const confirmed = await auth(
        "session",
        undefined,
        AbortSignal.timeout(30000),
      );
      if (!confirmed.authenticated) {
        throw new Error(
          "Allow cookies for this site, then try signing in again.",
        );
      }
      resetApiSession();
      setSession(confirmed);
      setPassword("");
    } catch (failure) {
      setError(
        failure instanceof Error && failure.name === "Error"
          ? failure.message
          : "Connection interrupted. Your details are still here; try signing in again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    if (busy) return;
    setBusy(true);
    try {
      const signedOut = await auth("logout", {}, AbortSignal.timeout(30000));
      resetApiSession();
      setSession(signedOut);
      setPassword("");
      setError("");
    } catch {
      setError(
        "Sign-out could not be confirmed. Check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (session?.authenticated) {
    return (
      <>
        {error && (
          <div className="session-error" role="alert">
            {error}
          </div>
        )}
        <App
          onSignOut={session.mode === "hosted" ? signOut : undefined}
          signingOut={busy}
        />
      </>
    );
  }

  return (
    <main className="sign-in-page">
      <div className="sign-in-brand">
        <span aria-hidden="true">∿</span> REMOTE EXPERIMENT CONTROL LAB
      </div>
      <section className="sign-in-panel" aria-labelledby="sign-in-title">
        <p className="sign-in-eyebrow">OPERATOR ACCESS</p>
        <h1 id="sign-in-title">
          Your lab, ready
          <br />
          when you are.
        </h1>
        <p className="sign-in-description">
          Sign in to control the instrument and open your saved experiments.
        </p>
        {!session ? (
          <>
            {error ? (
              <>
                <p role="alert" className="sign-in-error">
                  {error}
                </p>
                <button className="primary" onClick={() => setRetry(retry + 1)}>
                  Try connection again
                </button>
              </>
            ) : (
              <p role="status">Connecting to the lab…</p>
            )}
          </>
        ) : (
          <form onSubmit={signIn}>
            <label htmlFor="username">Username</label>
            <input
              id="username"
              name="username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              maxLength={128}
            />
            <label htmlFor="password">Password</label>
            <div className="password-entry">
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                maxLength={1024}
                aria-describedby={error ? "sign-in-error" : undefined}
              />
              <button
                type="button"
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
            {error && (
              <p id="sign-in-error" role="alert" className="sign-in-error">
                {error}
              </p>
            )}
            <button className="primary" type="submit" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
              <span aria-hidden="true">↗</span>
            </button>
            <p className="sign-in-note">
              Stay signed in for 12 hours on this browser.
              <br />
              Your experiment keeps running if you sign out.
            </p>
          </form>
        )}
      </section>
      <p className="sign-in-footer">A quiet space for precise experiments.</p>
    </main>
  );
}
