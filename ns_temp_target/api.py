"""Controller: JSON endpoints (login, submit, cancel)."""
import hmac

from flask import Blueprint, current_app, jsonify, request, session

from . import models

bp = Blueprint("api", __name__)

login_guard = models.LoginGuard()


@bp.post("/login")
def login():
    ip = request.remote_addr or "?"
    if login_guard.is_locked(ip):
        return jsonify(error="Too many attempts. Try again later."), 429
    pin = str((request.get_json(silent=True) or {}).get("pin", ""))
    if hmac.compare_digest(pin.encode(), models.PIN.encode()):
        login_guard.reset(ip)
        session["auth"] = True
        return jsonify(ok=True)
    login_guard.record_failure(ip)
    return jsonify(error="Wrong PIN"), 401


def _guard():
    """Return an error response if the request may not proceed, else None."""
    if not session.get("auth"):
        return jsonify(error="Not authenticated", relogin=True), 401
    if not models.NS_URL:
        return jsonify(error="NIGHTSCOUT_URL is not configured"), 500
    return None


def _dispatch(treatment):
    try:
        models.send_treatment(treatment)
    except models.NightscoutError as e:
        current_app.logger.error("Nightscout error: %s", e)
        return jsonify(error="Nightscout request failed"), 502
    return jsonify(ok=True)


@bp.post("/submit")
def submit():
    if (err := _guard()):
        return err
    try:
        target, duration = models.parse_target_input(request.get_json(silent=True) or {})
    except models.InvalidInput as e:
        return jsonify(error=str(e)), 400
    return _dispatch(models.temp_target_treatment(target, duration))


@bp.post("/cancel")
def cancel():
    if (err := _guard()):
        return err
    return _dispatch(models.cancel_treatment())
