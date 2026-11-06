"""Entry point. See ns_temp_target/ for the application code.

Environment variables:
  APP_PIN             4-digit PIN (default "0000")
  NIGHTSCOUT_URL      Base URL of Nightscout, e.g. https://my.ns.example.com
  NIGHTSCOUT_TOKEN    Nightscout access token (subject), used for the login GET
  SECRET_KEY          Optional Flask session secret (random per start if unset)
  PORT                Optional port (default 8080)
"""
import os

from ns_temp_target import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
