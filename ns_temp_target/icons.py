"""View assets: favicon SVG and generated PNG home-screen icons."""
import struct
import zlib
from functools import lru_cache

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<circle cx="32" cy="32" r="30" fill="#dc2626"/>
<circle cx="32" cy="32" r="21" fill="#fff"/>
<circle cx="32" cy="32" r="13" fill="#dc2626"/>
<circle cx="32" cy="32" r="5" fill="#fff"/>
</svg>"""

PNG_SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


@lru_cache(maxsize=None)
def target_png(size):
    """Opaque square PNG of the target icon (pure Python, no image library).

    Full-bleed and opaque on purpose: iOS fills transparent areas with black and
    rounds the corners itself. Artwork stays inside the central 80% so Android
    can also use it as a maskable icon.
    """
    red, white = (220, 38, 38), (255, 255, 255)
    rings = [(0.36, white), (0.25, red), (0.11, white)]  # radius as fraction of size
    ss = 2  # 2x2 supersampling for smooth edges
    c = size / 2.0
    rows = []
    for y in range(size):
        row = bytearray([0])  # PNG filter type 0
        for x in range(size):
            r = g = b = 0
            for sy in range(ss):
                for sx in range(ss):
                    d = (((x + (sx + .5) / ss) - c) ** 2 + ((y + (sy + .5) / ss) - c) ** 2) ** .5 / size
                    col = red
                    for radius, ring_col in rings:
                        if d <= radius:
                            col = ring_col
                    r += col[0]; g += col[1]; b += col[2]
            n = ss * ss
            row += bytes((r // n, g // n, b // n))
        rows.append(bytes(row))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (PNG_SIGNATURE
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
            + chunk(b"IEND", b""))
