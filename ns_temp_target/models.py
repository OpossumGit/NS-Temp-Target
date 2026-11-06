"""Model layer: configuration, login lockout, and Nightscout treatments."""
import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

PIN = os.environ.get("APP_PIN", "0000")
NS_URL = os.environ.get("NIGHTSCOUT_URL", "").rstrip("/")
NS_TOKEN = os.environ.get("NIGHTSCOUT_TOKEN", "")

MGDL_PER_MMOL = 18.0182
TARGET_RANGE = (4.0, 8.0)       # mmol/L
DURATION_RANGE = (10, 120)      # minutes


class NightscoutError(Exception):
    """Raised when talking to Nightscout fails."""


class InvalidInput(ValueError):
    """Raised when user-supplied target/duration are malformed or out of range."""


class LoginGuard:
    """Simple in-memory brute-force protection, per client IP."""

    def __init__(self, max_fails=5, lock_seconds=300):
        self.max_fails, self.lock_seconds = max_fails, lock_seconds
        self._fails = {}

    def is_locked(self, ip):
        n, until = self._fails.get(ip, (0, 0))
        return n >= self.max_fails and time.time() < until

    def record_failure(self, ip):
        n, _ = self._fails.get(ip, (0, 0))
        self._fails[ip] = (n + 1, time.time() + self.lock_seconds)

    def reset(self, ip):
        self._fails.pop(ip, None)


def parse_target_input(data):
    """Validate request data and return (target_mmol, duration_min)."""
    try:
        target = round(float(data["target"]), 1)
        duration = int(data["duration"])
    except (KeyError, TypeError, ValueError):
        raise InvalidInput("Invalid input")
    if not (TARGET_RANGE[0] <= target <= TARGET_RANGE[1]
            and DURATION_RANGE[0] <= duration <= DURATION_RANGE[1]):
        raise InvalidInput("Values out of range")
    return target, duration


def temp_target_treatment(target_mmol, duration):
    target_mgdl = int(round(target_mmol * MGDL_PER_MMOL))
    return {
        "eventType": "Temporary Target",
        # One of AAPS's known reasons (Custom, Hypo, Activity, Eating Soon).
        "reason": "Custom",
        # Sent in mg/dL (integer) for compatibility with clients such as
        # Nightguard that expect mg/dL; Nightscout converts for display.
        "targetTop": target_mgdl,
        "targetBottom": target_mgdl,
        "units": "mg/dl",
        "duration": duration,
    }


def cancel_treatment():
    # A Temporary Target with duration 0 ends any currently active target.
    return {
        "eventType": "Temporary Target",
        "reason": "Canceled",
        "duration": 0,
    }


def server_now(response):
    """Current UTC time according to the Nightscout server.

    Taken from the HTTP Date header, so a wrong clock on this host cannot push
    events into the future (AAPS ignores targets stamped ahead of its own clock).
    The header has 1-second resolution, so the result is at most about a second
    behind the true time, which is the safe direction. Falls back to the local
    clock if the header is missing or unparseable.
    """
    try:
        return parsedate_to_datetime(response.headers["Date"]).astimezone(timezone.utc)
    except (KeyError, TypeError, ValueError):
        return datetime.now(timezone.utc)


def send_treatment(treatment):
    """Post a treatment to Nightscout. Raises NightscoutError on failure."""
    try:
        # 1. Exchange access token for a JWT.
        r = requests.get(f"{NS_URL}/api/v2/authorization/request/{NS_TOKEN}", timeout=15)
        r.raise_for_status()
        jwt = r.json()["token"]

        # Stamp the event with the server's clock, not this host's.
        now = server_now(r)
        millis = int(now.timestamp() * 1000)
        treatment["created_at"] = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        # Epoch milliseconds; API v3 requires `date`, and AAPS uses it as the event timestamp.
        treatment["date"] = millis
        treatment["mills"] = millis
        # Local UTC offset in minutes; 0 because the timestamps above are UTC.
        treatment["utcOffset"] = 0
        # API v3 requires `app`.
        treatment["app"] = "ns-temp-target"
        treatment["enteredBy"] = "ns-temp-target"

        # 2. Create the treatment.
        r = requests.post(
            f"{NS_URL}/api/v3/treatments",
            json=treatment,
            headers={"Authorization": f"Bearer {jwt}"},
            timeout=15,
        )
        r.raise_for_status()
    except (requests.RequestException, KeyError, ValueError) as e:
        raise NightscoutError(str(e)) from e
