"""Controller: page and static-asset routes."""
from flask import Blueprint, Response, jsonify, render_template, session

from . import icons

bp = Blueprint("web", __name__)

_ICON_CACHE = {"Cache-Control": "public, max-age=86400"}


@bp.get("/")
def index():
    return render_template("index.html", unlocked=bool(session.get("auth")))


@bp.get("/favicon.svg")
@bp.get("/favicon.ico")
def favicon():
    return Response(icons.FAVICON_SVG, mimetype="image/svg+xml", headers=_ICON_CACHE)


def _png_response(size):
    return Response(icons.target_png(size), mimetype="image/png", headers=_ICON_CACHE)


@bp.get("/apple-touch-icon.png")
@bp.get("/apple-touch-icon-precomposed.png")
def apple_touch_icon():
    return _png_response(180)


@bp.get("/icon-192.png")
def icon_192():
    return _png_response(192)


@bp.get("/icon-512.png")
def icon_512():
    return _png_response(512)


@bp.get("/manifest.webmanifest")
def manifest():
    return jsonify(
        name="Nightscout Temp Target",
        short_name="Temp Target",
        start_url="/",
        scope="/",
        display="standalone",
        background_color="#f8f7f4",
        theme_color="#f8f7f4",
        icons=[
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    ), 200, {"Content-Type": "application/manifest+json"}
