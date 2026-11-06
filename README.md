# ns-temp-target

[![build](https://github.com/OpossumGit/NS-Temp-Target/actions/workflows/build.yml/badge.svg)](https://github.com/OpossumGit/NS-Temp-Target/actions/workflows/build.yml)

A small Flask web app for setting (and cancelling) a **Temporary Target** in [Nightscout](https://nightscout.github.io/) from a phone-friendly page.

1. Enter a 4-digit PIN (auto-submits on the fourth digit).
2. Pick a target (4.0–8.0 mmol/L) and a duration (10–120 min).
3. Press **Submit TT** to create the target, or **Cancel Target** to end any active one.

## How it talks to Nightscout

For each action the app:

1. `GET {NIGHTSCOUT_URL}/api/v2/authorization/request/{NIGHTSCOUT_TOKEN}` to exchange the access token for a JWT.
2. `POST {NIGHTSCOUT_URL}/api/v3/treatments` with `Authorization: Bearer <jwt>`.

The target is sent as integer **mg/dL** (`units: "mg/dl"`) for compatibility with clients such as Nightguard; Nightscout converts it for display. Cancelling sends a Temporary Target with `duration: 0`.

## Project layout

```
app.py                    entry point (python app.py, or gunicorn app:app)
requirements.txt          Python dependencies
Dockerfile, docker-compose.yml, .env.example   container setup
ns_temp_target/
  __init__.py             create_app() factory
  models.py               model: config, input validation, Nightscout client, login lockout
  api.py                  controller: /login, /submit, /cancel JSON endpoints
  web.py                  controller: page, icons, web app manifest
  icons.py                view assets: favicon SVG and generated PNG icons
  templates/index.html    view: the page
  static/                 view: app.js and style.css
```

The app follows a simple MVC split: views (templates, static files, icons) hold no logic, controllers (`api.py`, `web.py`) only handle requests and sessions, and `models.py` contains the business logic and has no Flask dependency.

## Configuration

All configuration is through environment variables.

| Variable | Required | Default | Description |
|---|---|---|---|
| `NIGHTSCOUT_URL` | yes | – | Base URL, e.g. `https://my.nightscout.example.com` |
| `NIGHTSCOUT_TOKEN` | yes | – | Nightscout access token (subject), e.g. `name-abc123` |
| `APP_PIN` | no | `0000` | 4-digit PIN. **Always set this**; the default is public. |
| `SECRET_KEY` | no | random per start | Signs the session cookie. Set a fixed value so logins survive restarts. |
| `PORT` | no | `8080` | Port to listen on |

Generate a secret key with:

```
python -c "import secrets; print(secrets.token_hex(32))"
```

## Run locally

```powershell
pip install -r requirements.txt
$env:NIGHTSCOUT_URL = "https://your-nightscout.example.com"
$env:NIGHTSCOUT_TOKEN = "yourname-abc123"
$env:APP_PIN = "1234"
python app.py
```

Open http://localhost:8080.

## Run with a container

The image is built by GitHub Actions and published to GHCR on pushes to `main` and on `v*` tags:

```
docker run -d -p 8080:8080 \
  -e NIGHTSCOUT_URL=https://your-nightscout.example.com \
  -e NIGHTSCOUT_TOKEN=yourname-abc123 \
  -e APP_PIN=1234 \
  -e SECRET_KEY=some-long-random-string \
  ghcr.io/<owner>/<repo>:main
```

`podman` works the same way. To build it yourself:

```
docker build -t ns-temp-target .
```

With Podman, add `--format docker` if you want the image health check kept.

## Security notes

- The PIN is a light barrier, not strong authentication. Serve the app over **HTTPS**, since a PIN sent over plain HTTP can be sniffed.
- After 5 wrong PINs from one IP, that IP is locked out for 5 minutes. The counter is kept in memory, so it resets on restart, and the container runs a single gunicorn worker on purpose so the count is not split across processes.
- The lockout uses the client IP. Behind a reverse proxy every request may appear to come from the proxy, so the lockout would affect everyone. Proxy-aware IP handling (e.g. Werkzeug `ProxyFix`) is not yet configured.
- No secrets are stored in the code or image; they are supplied at runtime. Never commit a `.env` file.
