# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Small Flask app that sets/cancels a Nightscout Temporary Target from a phone-friendly, PIN-protected page. See `README.md` for the user-facing description, env var table and security notes.

## Commands

```powershell
pip install -r requirements.txt
$env:NIGHTSCOUT_URL = "https://your-nightscout.example.com"
$env:NIGHTSCOUT_TOKEN = "yourname-abc123"
$env:APP_PIN = "1234"
python app.py                      # dev server on http://localhost:8080 (PORT to override)
docker build -t ns-temp-target .   # container build (production runs gunicorn app:app)
```

There is no test suite or linter configured. CI (`.github/workflows/build.yml`) only builds and pushes the image to GHCR on pushes to `main` and `v*` tags, passing the tag/branch as `APP_VERSION` (shown in the page footer; `web.py` prefixes `v` to numeric versions).

## Architecture

Strict MVC split inside the `ns_temp_target/` package (`create_app()` factory in `__init__.py`, entry point `app.py`):

- `models.py` — all business logic, no Flask dependency: env config (`NS_URL`, `PIN`, ...), input validation (`parse_target_input`), Nightscout client (`send_treatment`, `temp_target_treatment`, `cancel_treatment`), and the in-memory `LoginGuard` lockout.
- `api.py` — blueprint with `/login`, `/submit`, `/cancel` JSON endpoints; only handles requests/session and maps model exceptions (`InvalidInput` → 400, `NightscoutError` → 502).
- `web.py` — blueprint for the HTML page, icons and web app manifest.
- `icons.py`, `templates/`, `static/` — view assets; keep logic out of them.

Keep new logic in `models.py` and keep controllers thin.

Nightscout flow: GET `/api/v2/authorization/request/{token}` for a JWT, then POST `/api/v3/treatments` as Bearer. Targets are sent as integer **mg/dL** (for Nightguard compatibility); cancel is a Temporary Target with `duration: 0`.

## Constraints to preserve

- Gunicorn runs with a **single worker** (threads for concurrency) because the login lockout counter lives in process memory; don't add workers without moving that state out of process.
- Lockout is keyed on `request.remote_addr`; no `ProxyFix` is configured, so behind a reverse proxy all clients share one IP.
- `SECRET_KEY` is random per start if unset, so sessions don't survive restarts.
