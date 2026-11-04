"""Nightscout temporary target web app.

Environment variables:
  APP_PIN             4-digit PIN (default "0000")
  NIGHTSCOUT_URL      Base URL of Nightscout, e.g. https://my.ns.example.com
  NIGHTSCOUT_TOKEN    Nightscout access token (subject), used for the login GET
  SECRET_KEY          Optional Flask session secret (random per start if unset)
  PORT                Optional port (default 8080)
"""
import hmac
import os
import secrets
import time
from datetime import datetime, timezone

import requests
from flask import Flask, Response, jsonify, render_template_string, request, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict")

PIN = os.environ.get("APP_PIN", "0000")
NS_URL = os.environ.get("NIGHTSCOUT_URL", "").rstrip("/")
NS_TOKEN = os.environ.get("NIGHTSCOUT_TOKEN", "")

# Simple brute-force protection (per client IP, in memory).
MAX_FAILS, LOCK_SECONDS = 5, 300
_fails = {}


def _locked(ip):
    n, until = _fails.get(ip, (0, 0))
    return n >= MAX_FAILS and time.time() < until


PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Temp Target</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>
 body{font-family:system-ui,sans-serif;max-width:420px;margin:2rem auto;padding:0 1rem}
 h1{font-size:1.3rem;text-align:center} label{display:block;margin-top:1.5rem}
 output{font-weight:bold} input[type=range]{width:100%}
 #pinbox{text-align:center}
 input[type=password]{font-size:1.5rem;letter-spacing:.5rem;width:6rem;text-align:center;padding:.4rem .2rem .4rem .7rem;
  margin-top:.5rem;border:2px solid #9ca3af;border-radius:12px}
 button{display:flex;align-items:center;justify-content:center;gap:.5rem;width:100%;max-width:280px;
  margin:1rem auto 0;padding:.8rem 1.5rem;font-size:1rem;font-weight:600;color:#fff;background:#2563eb;
  border:0;border-radius:12px;cursor:pointer;box-shadow:0 2px 6px rgba(0,0,0,.2);transition:filter .15s,transform .05s}
 button:hover{filter:brightness(1.1)} button:active{transform:scale(.98)}
 button:disabled{opacity:.5;cursor:not-allowed}
 button svg{width:1.2em;height:1.2em;flex:none}
 #cancel{background:#dc2626}
 #msg{text-align:center}
 #msg{margin-top:1rem;font-weight:bold}.ok{color:#080}.err{color:#b00}
 .hidden{display:none}
</style></head><body>
<h1>Nightscout Temporary Target</h1>

<div id="pinbox" class="{{ 'hidden' if unlocked else '' }}">
  <label>Enter PIN<br>
  <input id="pin" type="password" inputmode="numeric" pattern="\\d{4}" maxlength="4" autofocus></label>
</div>

<div id="main" class="{{ '' if unlocked else 'hidden' }}">
  <label>Target: <output id="tv">6.0</output> mmol/L
    <input id="target" type="range" min="4.0" max="8.0" step="0.1" value="6.0"></label>
  <label>Duration: <output id="dv">60</output> min
    <input id="dur" type="range" min="10" max="120" step="5" value="60"></label>
  <button id="submit"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4"/></svg>Submit TT</button>
  <button id="cancel"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M15 9l-6 6M9 9l6 6"/></svg>Cancel Target</button>
</div>
<div id="msg"></div>

<script>
const $ = id => document.getElementById(id), msg = $("msg");
function say(t, ok){ msg.textContent = t; msg.className = ok ? "ok" : "err"; }
async function post(url, body){
  const r = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
  return [r.ok, await r.json().catch(() => ({}))];
}
$("target").oninput = e => $("tv").textContent = Number(e.target.value).toFixed(1);
$("dur").oninput = e => $("dv").textContent = e.target.value;
async function unlock(){
  $("pin").disabled = true;
  const [ok, d] = await post("/login", {pin: $("pin").value});
  $("pin").disabled = false;
  if (ok){ $("pinbox").classList.add("hidden"); $("main").classList.remove("hidden"); say("", true); }
  else say(d.error || "Login failed", false);
  $("pin").value = "";
  if (!ok) $("pin").focus();
}
window.addEventListener("load", () => { if (!$("pinbox").classList.contains("hidden")) $("pin").focus(); });
$("pin").oninput = e => {
  e.target.value = e.target.value.replace(/\\D/g, "");
  if (e.target.value.length === 4) unlock();
};
async function send(url, body, okText){
  $("submit").disabled = $("cancel").disabled = true; say("Sending...", true);
  const [ok, d] = await post(url, body);
  $("submit").disabled = $("cancel").disabled = false;
  if (ok) say(okText, true);
  else { say(d.error || "Failed", false); if (d.relogin){ $("main").classList.add("hidden"); $("pinbox").classList.remove("hidden"); } }
}
$("submit").onclick = () => send("/submit", {target: parseFloat($("target").value), duration: parseInt($("dur").value)}, "Temporary target set.");
$("cancel").onclick = () => send("/cancel", {}, "Temporary target cancelled.");
</script></body></html>"""


FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<circle cx="32" cy="32" r="30" fill="#dc2626"/>
<circle cx="32" cy="32" r="21" fill="#fff"/>
<circle cx="32" cy="32" r="13" fill="#dc2626"/>
<circle cx="32" cy="32" r="5" fill="#fff"/>
</svg>"""


@app.get("/favicon.svg")
@app.get("/favicon.ico")
def favicon():
    return Response(FAVICON, mimetype="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/")
def index():
    return render_template_string(PAGE, unlocked=bool(session.get("auth")))


@app.post("/login")
def login():
    ip = request.remote_addr or "?"
    if _locked(ip):
        return jsonify(error="Too many attempts. Try again later."), 429
    pin = str((request.get_json(silent=True) or {}).get("pin", ""))
    if hmac.compare_digest(pin.encode(), PIN.encode()):
        _fails.pop(ip, None)
        session["auth"] = True
        return jsonify(ok=True)
    n, _ = _fails.get(ip, (0, 0))
    _fails[ip] = (n + 1, time.time() + LOCK_SECONDS)
    return jsonify(error="Wrong PIN"), 401


@app.post("/submit")
def submit():
    if not session.get("auth"):
        return jsonify(error="Not authenticated", relogin=True), 401
    if not NS_URL:
        return jsonify(error="NIGHTSCOUT_URL is not configured"), 500

    data = request.get_json(silent=True) or {}
    try:
        target = round(float(data["target"]), 1)
        duration = int(data["duration"])
    except (KeyError, TypeError, ValueError):
        return jsonify(error="Invalid input"), 400
    if not (4.0 <= target <= 8.0 and 10 <= duration <= 120):
        return jsonify(error="Values out of range"), 400
    target_mgdl = int(round(target * 18.0182))

    return send_treatment({
        "eventType": "Temporary Target",
        "reason": "Manual",
        # Sent in mg/dL (integer) for compatibility with clients such as
        # Nightguard that expect mg/dL; Nightscout converts for display.
        "targetTop": target_mgdl,
        "targetBottom": target_mgdl,
        "units": "mg/dl",
        "duration": duration,
    })


@app.post("/cancel")
def cancel():
    if not session.get("auth"):
        return jsonify(error="Not authenticated", relogin=True), 401
    if not NS_URL:
        return jsonify(error="NIGHTSCOUT_URL is not configured"), 500
    # A Temporary Target with duration 0 ends any currently active target.
    return send_treatment({
        "eventType": "Temporary Target",
        "reason": "Cancel",
        "duration": 0,
        "units": "mg/dl",
    })


def send_treatment(treatment):
    treatment["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    treatment["enteredBy"] = "ns-temp-target"
    try:
        # 1. Exchange access token for a JWT.
        r = requests.get(f"{NS_URL}/api/v2/authorization/request/{NS_TOKEN}", timeout=15)
        r.raise_for_status()
        jwt = r.json()["token"]

        # 2. Create the treatment.
        r = requests.post(
            f"{NS_URL}/api/v1/treatments",
            json=treatment,
            headers={"Authorization": f"Bearer {jwt}"},
            timeout=15,
        )
        r.raise_for_status()
    except (requests.RequestException, KeyError, ValueError) as e:
        app.logger.error("Nightscout error: %s", e)
        return jsonify(error="Nightscout request failed"), 502
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
