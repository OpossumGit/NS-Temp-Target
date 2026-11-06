"""Nightscout temporary target web app.

Layout:
  models.py     business logic: config, validation, Nightscout client, login lockout
  icons.py      view asset generation (favicon, PNG icons)
  web.py        controller (blueprint): HTML page, icons, manifest
  api.py        controller (blueprint): login / submit / cancel JSON endpoints
  templates/    HTML views
  static/       CSS and JS
"""
import os
import secrets

from flask import Flask


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict")

    from . import api, web
    app.register_blueprint(web.bp)
    app.register_blueprint(api.bp)
    return app
