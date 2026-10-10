# Authenticated cloud deployment

The hosted image serves the same React app and runs the same Python API and C++
simulator as local Compose. Python and C++ remain separate processes using actual
control and telemetry TCP connections. Hosted C++ listeners bind to 127.0.0.1;
only the HTTP service is reachable through the platform's HTTPS edge. PostgreSQL
runs separately on Neon so container sleep, replacement and restarts preserve
completed run history. Local Compose remains the default development path.

## Live instance

Open [Remote Experiment Control Lab](https://remote-experiment-control-lab.onrender.com).
Sign in as **operator**. Retrieve the current **LAB_PASSWORD** from the
[Render service](https://dashboard.render.com/web/srv-db4jf9mi0phs73ctof0g)'s
Environment page and keep it in a password manager. Never send it in chat or
include it in a URL. The instance uses Render Free and Neon Free in Singapore.

Verified on 2026-10-10 (Pacific/Auckland) against deployed application commit
`201f5d0b49f4f73b8babe34ab0b9bbf543c6d83d`: authenticated access, real API/C++
acquisition, 100 ordered durable samples, confirmed Stop, live browser refresh,
saved Review, and desktop/mobile layouts. Four synthetic runs start the cloud
history. A real redeploy preserved their 462 samples and recording statuses.
Automatic deployment is off. See PROGRESS.md for the latest Phase 2 release evidence.

## Free hosting choice

Use one **Render Free web service** and a **Neon Free PostgreSQL project**, both in
Singapore when available. Vercel's request-scoped functions are not a suitable
home for this continuously running instrument/controller pair. No custom domain,
paid worker, object storage or additional identity service is required.

Verified provider documentation on 2026-10-10:

- [Render Free](https://render.com/docs/free): 750 instance hours per workspace
  per month; sleeps after 15 minutes without inbound traffic and takes roughly a
  minute to wake. Local container files are ephemeral. Free Render PostgreSQL
  expires after 30 days, so this configuration uses Neon instead.
- [Neon Free](https://neon.com/blog/neon-free-plan-1-gb-per-project): 1 GB per project
  and 100 CU-hours per month. An internal database heartbeat keeps the ownership
  session and compute active while the Render container is awake. This is a small
  personal demo, not an unlimited always-on service. Watch the provider dashboards
  for actual usage.

Use free plans without adding a payment method or enabling paid upgrades. Render
can suspend services for exhausted free quotas or excessive external traffic.
An unexpected platform restart can interrupt a run. Same-boot recovery can drain
retained telemetry; a changed engine boot preserves the committed prefix and marks
unrecoverable evidence partial. Closing the browser normally leaves a short backend-owned run to
finish (runs are capped at 60 seconds, below Render's idle timeout).

## Provision and configure

1. Create a dedicated Neon Free project in `aws-ap-southeast-1`, PostgreSQL 17.
   Do not reuse a database containing unrelated data.
2. Obtain its **direct, unpooled** PostgreSQL connection string. Session advisory
   locks enforce one orchestrator, so transaction pooling is incompatible. Use
   `sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt` for the
   remote database. Store it only in Render's `DATABASE_URL` environment setting.
3. Deploy the repository's `main` branch using the root `render.yaml` Blueprint:
   [Open deployment configuration](https://dashboard.render.com/blueprint/new?repo=https://github.com/ammaar134/Remote-Expriment-Control-Lab).
   Confirm the web service plan says **Free**. The Blueprint builds
   `backend/Dockerfile`; its final `hosted` stage includes the C++ executable.
4. Render generates `LAB_PASSWORD` and a separate `LAB_SESSION_SECRET` as random
   secrets. `LAB_USERNAME` is `operator`. Use the password on the app's sign-in
   screen. A manually selected password must contain at least 12 characters;
   prefer a unique password from a password manager. Keep both values out of
   URLs, repositories, frontend bundles and screenshots. Changing either secret
   and redeploying invalidates existing sessions. When upgrading an existing
   service, add the random signing secret before deploying the session-based app.
5. Render supplies `RENDER_EXTERNAL_HOSTNAME`; the app constructs its HTTPS origin
   from this value. For another trusted proxy host, set `LAB_PUBLIC_ORIGIN` to the
   exact HTTPS origin without a path, trailing slash or port. Set `LAB_MODE=hosted`
   and `WEB_CONCURRENCY=1`. The image obeys the platform's `PORT` setting.
6. Verify the live URL, signed-out denial, sign-in, complete run, confirmed Stop,
   and saved Review. A successful build alone does not verify a live deployment.

The deployment container refuses to start without hosted mode, a valid HTTPS
origin, a password of at least 12 characters and a separate random signing secret
of at least 32 characters. The sign-in shell and static assets are public; API
data, instrument controls and OpenAPI docs require an authenticated session.
State-changing requests require the exact allowed Origin; cross-site browser
API requests are refused. Opening the public sign-in page from an external
link is allowed. There are no hosted fault-injection endpoints. GET
`/healthz` returns only `ok` or `starting` for platform startup probes.
Authenticated `/api/health` reports database readiness and device connectivity.

## Sign-in and sessions

Sign-in protects the shared instrument controls and saved history on the public
URL. It is one operator account, not a multi-user permission system. Local
loopback-only Compose does not require a login.

The app loads a stable form and checks `/auth/session` once. No instrument or
history polling starts until authentication succeeds. `/auth/login` accepts JSON
credentials over HTTPS and issues a signed, HttpOnly, Secure, SameSite=Strict,
host-only cookie for 12 hours. Passwords are not kept in browser storage.
Incorrect credentials stay inline without clearing inputs or refreshing the
page. A 401 from the API returns the console to the form and stops polling;
responses never issue a native browser Basic-auth challenge.

Five failed attempts from one source within a minute trigger a temporary limit.
The limiter is bounded and in memory on the single instance; it resets on a
process restart. Sessions survive normal refreshes and container replacements
while credentials/signing keys remain unchanged. Sign out clears the browser's
cookie; a copied cookie remains valid until its expiry or credential rotation.
Signing out does not stop a running experiment. Use Stop first when intended.

The launcher trusts forwarded HTTPS headers because Render's edge is the only
public entry point. Do not publish its raw HTTP port directly to the internet or
place it behind a proxy that passes untrusted forwarding headers unchanged.

## Restart and deployment behavior

Automatic deploys are disabled. Deploy manually while no experiment is active;
changing code should not unexpectedly interrupt an operator's run.

Render starts a replacement before stopping the previous container. The new
Python process first checks database access, then waits for the existing
PostgreSQL session advisory lock. During this brief handoff, `/healthz` can pass
so Render can switch traffic and retire the old owner, but every API route
returns 503 with a retry hint until the new process owns the lock and migrations
are complete. UI files can load during the transition. Startup gives up after
180 seconds and fails the platform probe. No two controllers acquire ownership.
This deliberately accepts a short control outage during deployment.

The launcher forwards shutdown to both child processes and waits up to ten
seconds. Unexpected exit of either child terminates the container; the provider
owns restart. A new C++ boot does not restart an old experiment. Completed saved
runs survive. Interrupted runs are reconciled against boot identity and retained
telemetry; missing evidence after a changed boot remains partial/unknown.
Cloud history begins empty; no local database upload is part of deployment.

The hosted API checks its existing database ownership connection every 20
seconds, including before any experiment has started. This prevents Neon's idle
suspension from closing the session while the app is awake. It sends no HTTP
keepalive traffic to Render. If the connection fails or its check exceeds ten
seconds, the API closes instrument control and exits through the supervisor.
The next container boot must acquire ownership again; a closed connection cannot
leave a permanently unusable signed-in UI. Existing saved history is preserved.

## Reproducible checks

```sh
docker build --target hosted -f backend/Dockerfile -t experiment-lab-hosted .
python3 tests/hosted_smoke.py
```

The test creates its own disposable PostgreSQL and two app containers, verifies
cookie authentication and private C++ ports, completes and stops real experiments,
checks exclusive ownership while containers overlap, verifies saved history
after replacement, survives a real 45-second PostgreSQL idle-session timeout,
and checks whole-container shutdown on database-session or child failure. The
same sign-in cookie remains valid across replacement and restart. The test
removes only those test resources. Local Compose history is untouched.

`tests/api_smoke.py` can also test a live deployment using process environment
variables `LAB_URL`, `LAB_USERNAME`, `LAB_PASSWORD` and `LAB_PUBLIC_ORIGIN`.
Inject secrets through the supported credential tooling, never command arguments
or shell history. The test creates two synthetic saved runs.
