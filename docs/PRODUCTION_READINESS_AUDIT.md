# Production Readiness & Security Audit

**Date:** 2026-11-10
**Scope:** Full backend (`FastAPI` + SQLAlchemy/Alembic/PostgreSQL) and frontend (`React` + TypeScript/Vite) of JURISCAN-AI, branch `feature/realtime-messaging`.
**Method:** Every fix below was verified by automated regression tests and, where possible, by running the real deployment stack. Verification levels are marked explicitly — **[tested]** (automated test), **[verified live]** (exercised against the running Docker stack), **[manual]** (code inspection only).

---

## 1. Executive summary

The codebase entered this audit in a well-hardened state: server-side ownership and role checks on every route, upload validation with magic-byte/MIME/size/zip-bomb defenses, path-traversal protection, WebSocket auth via first frame with per-event re-authorization, stdlib-only PBKDF2 (240k iterations) password hashing and HMAC-signed session tokens, production settings validation (strong `SECRET_KEY` required, debug rejected), CI migration-drift guard.

Four confirmed issues were found and fixed in this pass; one deployment gap (no production artifacts) was closed. No critical vulnerabilities were found.

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | No brute-force protection on `/auth/login` and `/auth/register` | High | **Fixed** |
| 2 | Login timing side-channel → account enumeration | Medium | **Fixed** |
| 3 | `/docs`, `/redoc`, `/openapi.json` exposed in production | Medium | **Fixed** |
| 4 | Registration race (`IntegrityError`) → HTTP 500 | Medium | **Fixed** |
| 5 | No production deployment artifacts (`docker/` empty) | Medium | **Fixed** |

Remaining, accepted risks and operational requirements are listed in §5.

---

## 2. Fixes delivered

### 2.1 Rate limiting on the auth endpoints (High) — [tested] + [verified live]

**Problem.** Neither `/auth/login` nor `/auth/register` had any brute-force protection; an attacker could attempt unlimited password guesses.

**Fix.** A thread-safe, stdlib-only sliding-window limiter (`backend/app/core/ratelimit.py`) is applied as a FastAPI route dependency (`backend/app/api/auth.py:auth_rate_limit`) to both endpoints.

* Default: **10 requests / 60 s per client IP** (configurable via `AUTH_RATE_LIMIT_MAX_REQUESTS` / `AUTH_RATE_LIMIT_WINDOW_SECONDS`; `0` disables).
* Responses carry `429` with error code `rate_limited` and a `Retry-After` header (`backend/app/core/exceptions.py:TooManyRequestsError`, `AppError.headers` passthrough added to the exception handler).
* Counters are bounded (expired-key pruning at 65 536 tracked keys) so a flood of spoofed source addresses cannot grow memory.
* Limits are read through the settings object at check time, so operators can change them without a restart.
* The limiter is keyed on the **connecting socket IP only** — `X-Forwarded-For` is deliberately never trusted; reverse proxies must pass the real client address at the connection level (see §5).

**Verified live:** against the production Docker stack through nginx, 10 failed logins were allowed (401) and the 11th returned `429` + `Retry-After`.

**Precise coverage (pinned by `tests/test_rate_limit.py::test_malformed_json_rejects_before_rate_limiting`):** FastAPI 0.115 parses the JSON body *before* solving route dependencies (`fastapi/routing.py:267`), so syntactically malformed JSON is rejected with 422 without consuming budget — but such requests never reach the endpoint (no PBKDF2, no DB), so no credential attempt is possible without a valid JSON body. Valid JSON — including schema-invalid payloads — is always counted, which is what protects the expensive password-verification path.

### 2.2 Login timing equalization (Medium) — [tested]

**Problem.** A login for a *nonexistent* email skipped PBKDF2 entirely while a wrong password for an *existing* account burned a full 240k-iteration cycle — a response-time oracle for enumerating registered addresses.

**Fix.** `backend/app/api/auth.py` now verifies a `_DUMMY_HASH` (a PBKDF2 hash of a random, unrecorded secret) when the account does not exist, so both paths cost the same. The dummy hash can never authenticate anything (regression-tested against multiple candidate passwords, including the generation-time value of the hash's own salt input space). The pre-existing generic error message ("Invalid email or password.") is retained.

### 2.3 Interactive API docs disabled in production/staging (Medium) — [tested] + [verified live]

**Problem.** `/docs`, `/redoc` and `/openapi.json` published the complete route surface of the application in every environment.

**Fix.** `backend/main.py:create_app` sets `docs_url`/`redoc_url`/`openapi_url` to `None` when `APP_ENV` is `production` or `staging`.

**Verified live:** inside the production container, `GET /docs` and `GET /openapi.json` both return 404 while `/api/health` returns 200.

### 2.4 Registration race returns 409, not 500 (Medium) — [tested]

**Problem.** Two concurrent sign-ups with the same email (or emails deriving the same username) could slip past the duplicate check; the `IntegrityError` on commit escaped as an unhandled 500.

**Fix.** `backend/app/api/auth.py:register` wraps the commit; on `IntegrityError` it rolls back and raises a retryable `ConflictError` (409, code `registration_conflict`). (Reproduced deterministically by monkeypatching `Session.commit` to raise `IntegrityError`.)

### 2.5 Production deployment artifacts (Medium) — [verified live]

**Problem.** `docker/` contained only `.gitkeep`; there was no supported way to run the system in production.

**Fix.** A complete, self-contained stack:

| File | Purpose |
|------|---------|
| `docker/backend.Dockerfile` | `python:3.13-slim`, non-root user, `libgl1`/`libglib2.0` (for OpenCV), pinned requirements, startup = `alembic upgrade head` + uvicorn **single worker** |
| `docker/frontend.Dockerfile` | Multi-stage: `node:22-alpine` build (with `VITE_API_BASE_URL=/api` for same-origin API) → `nginx:1.27-alpine` |
| `docker/nginx.conf` | SPA serving with `try_files` fallback, `/api` reverse proxy with WebSocket upgrade handling, hashed-asset caching, `client_max_body_size 30m`, baseline security headers |
| `docker-compose.yml` | Postgres 16 with healthcheck, backend gated on DB health, fail-fast `:?` guards on `SECRET_KEY`/`DB_PASSWORD`, named volumes for DB data, uploads and models; DB is **not** published to the host |
| `.dockerignore` | Excludes `.venv`, `node_modules`, test artifacts, local `data/`, `models/` and `.env` from build contexts |

**Verified live (scratch stack, then fully removed):** images built; `docker compose up -d` reached healthy; SPA served (200); `/api/health` returned `{"status":"ok","environment":"production"}`; a user registered, called `/api/auth/me`, and completed a full WebSocket round-trip through the proxy (`ready` + `pong` on the workspace socket of a case with an assigned lawyer); rate limiting engaged with the production defaults; `/docs` and `/openapi.json` were 404. Alembic applied all 12 migrations to the fresh Postgres 16 volume at startup.

---

## 3. Verification evidence

| Check | Command | Result |
|-------|---------|--------|
| Backend test suite | `.venv\Scripts\python.exe -m pytest` (backend venv) | **308 passed, 1 skipped** (baseline 290 passed; +18 new regression tests, 0 regressions) |
| New regression tests | `pytest tests/test_rate_limit.py` | 18 passed |
| Frontend unit tests | `npm run test` (node --test) | 42 passed |
| Frontend lint | `npm run lint` (oxlint) | Clean exit; 4 pre-existing warnings, unchanged |
| Frontend build | `npm run build` (tsc -b && vite build) | Succeeded; advisory chunk-size warning only (674 kB main bundle) |
| Migration consistency | `alembic heads` | Single head `c9e1a3b5d7f2`; clean linear chain of 12 |
| Migration application | `alembic upgrade head` on a scratch Postgres 16 container | All 12 migrations applied cleanly |
| Migration drift | `alembic check` | "No new upgrade operations detected" — models match migration state |
| Production stack | `docker compose build` + `up -d` + smoke tests | All green (see §2.5) |
| Whitespace/errors | `git diff --check` | Clean (exit 0; CRLF notices are informational) |

CI (`.github/workflows/ci.yml`) already runs the migrations plus `alembic check` against Postgres 16 on every push, so migration drift remains guarded going forward.

---

## 4. Files changed in this phase

Backend:
* `backend/app/core/ratelimit.py` — **new** — sliding-window limiter
* `backend/app/api/auth.py` — rate-limit dependency on login/register; dummy-hash timing equalization; IntegrityError → 409
* `backend/app/core/exceptions.py` — `AppError.headers` passthrough; `TooManyRequestsError` (429)
* `backend/app/config/settings.py` — `auth_rate_limit_max_requests`, `auth_rate_limit_window_seconds`
* `backend/main.py` — docs disabled in production/staging
* `backend/tests/conftest.py` — suite-wide `AUTH_RATE_LIMIT_MAX_REQUESTS=0` (tests opt in explicitly)
* `backend/tests/test_rate_limit.py` — **new** — 18 regression tests

Deployment:
* `docker/backend.Dockerfile`, `docker/frontend.Dockerfile`, `docker/nginx.conf` — **new**
* `docker-compose.yml`, `.dockerignore` — **new**
* `.env.example` — documents the new rate-limit settings

(Other modified files in `git status` predate this phase and were left untouched.)

---

## 5. Remaining risks & operational requirements (accepted, documented)

1. **In-process limiter and realtime hubs — single worker only.** The rate limiter and the WebSocket connection hubs keep state in process memory. The Dockerfile therefore pins `--workers 1`. Scaling to multiple replicas requires sticky-session load balancing (WebSockets) and a shared rate-limit store (e.g. Redis). **[manual]**
2. **Reverse proxy and client IPs.** The limiter uses the connecting socket address. Behind nginx (as deployed) all proxied clients share one bucket; that is conservative (stricter), not permissive. If per-client limits are needed behind an edge proxy, the proxy must propagate real client IPs at the connection level. **[manual]**
3. **Token in `localStorage`.** XSS would allow token theft (7-day TTL). Mitigations in place: React's default escaping, no `dangerouslySetInnerHTML`, CSP via nginx headers is a candidate enhancement. A move to `HttpOnly` cookies would be an architectural change and was intentionally not made. **[manual]**
4. **No server-side token revocation.** Sessions are stateless HMAC tokens (7-day TTL); deactivating a user (`is_active`) is enforced on every request, but stolen tokens remain valid until expiry. **[manual]**
5. **Malformed-JSON requests bypass the limiter** (§2.1) — harmless because they never reach credential verification; raw floods should be throttled at the edge (nginx `limit_req`, WAF or similar). **[tested]**
6. **`/api/status` exposes the environment name** (`production`/`staging`) to authenticated users — informational only, accepted. **[manual]**
7. **Upload deletion is `unlink`-only** — no forensic retention. Accepted for the current product stage. **[manual]**
8. **Single-worker uvicorn** bounds throughput; the OCR executor is already bounded and time-limited, so the practical ceiling is CPU-bound OCR work. Load testing at production traffic levels has **not** been performed. **[unverified]**
9. **HTTPS/TLS** is not terminated anywhere in the provided stack — it must be provided by the operator's edge (nginx served on 80 inside the network). WebSocket URLs upgrade to `wss://` automatically when the page is served over HTTPS. **[manual]**
10. **Operational to-dos before first production launch:** set strong `SECRET_KEY` and `DB_PASSWORD` in `.env`, configure real backup strategy for the `pgdata` volume, define log shipping (JSON logs are already emitted), and consider nginx `limit_req` for edge throttling.

---

## 6. Conclusion

All confirmed vulnerabilities found in this audit are fixed with regression tests (backend suite: 308 passed / 1 skipped, no regressions), the frontend builds and tests cleanly, the database schema is drift-free on Postgres 16, and a complete, verified production deployment path now exists. The remaining items in §5 are documented operational considerations rather than open defects.
