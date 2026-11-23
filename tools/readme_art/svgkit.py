"""Tiny SVG kit for the README art: text is shaped with HarfBuzz and turned
into paths, so every graphic looks identical on every computer and needs no
web fonts. Fonts: Inter and Geist Mono (both SIL Open Font Licence).

Needs: pip install uharfbuzz fonttools
Font paths can be overridden with SEATBELT_INTER and SEATBELT_MONO.
"""
import os
import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen

INTER = os.environ.get("SEATBELT_INTER", "/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf")
MONO = os.environ.get("SEATBELT_MONO", "/usr/share/fonts/truetype/sand-box/google/Geist Mono/GeistMono-VariableFont_wght.ttf")

_faces = {}


def _face(path):
    if path not in _faces:
        _faces[path] = hb.Face(hb.Blob.from_file_path(path))
    return _faces[path]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class Doc:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.defs = []
        self.body = []
        self.glyphs = {}
        self.n = 0

    def uid(self, p="i"):
        self.n += 1
        return f"{p}{self.n}"

    def add(self, s):
        self.body.append(s)

    def adddef(self, s):
        self.defs.append(s)

    # ---- text -------------------------------------------------------
    def _font(self, mono, wght, size):
        path = MONO if mono else INTER
        face = _face(path)
        font = hb.Font(face)
        var = {"wght": wght}
        if not mono:
            var["opsz"] = 14 if size < 18 else (22 if size < 30 else 32)
        font.set_variations(var)
        key = ("m" if mono else "s") + str(wght) + ("" if mono else "o%d" % var["opsz"])
        return font, face.upem, key

    def measure(self, text, size, wght=400, mono=False, track=0):
        font, upem, _ = self._font(mono, wght, size)
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf, {"kern": True, "liga": True, "calt": True})
        adv = sum(p.x_advance for p in buf.glyph_positions)
        return adv * size / upem + track * size * max(0, len(text) - 1)

    def text(self, x, y, text, size, fill, wght=400, mono=False, anchor="start", track=0, opacity=None):
        """track: letter spacing as a fraction of size (e.g. -0.02)."""
        font, upem, key = self._font(mono, wght, size)
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        feats = {"kern": True, "liga": True, "calt": True}
        if not mono:
            feats.update({"cv11": True, "ss03": False})
        hb.shape(font, buf, feats)
        s = size / upem
        tr_units = track * size / s
        width = sum(p.x_advance for p in buf.glyph_positions) * s + track * size * max(0, len(text) - 1)
        if anchor == "middle":
            x -= width / 2
        elif anchor == "end":
            x -= width
        uses = []
        pen_x = 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            gid = info.codepoint
            gk = f"{key}g{gid}"
            if gk not in self.glyphs:
                pen = SVGPathPen(None, ntos=lambda v: "%d" % round(v))
                font.draw_glyph_with_pen(gid, pen)
                d = pen.getCommands()
                self.glyphs[gk] = (f"g{len(self.glyphs)}", d)
            gidname, d = self.glyphs[gk]
            if d:
                gx = pen_x + pos.x_offset
                uses.append(f'<use href="#{gidname}" x="{gx:.0f}" y="{pos.y_offset:.0f}"/>')
            pen_x += pos.x_advance + tr_units
        op = f' opacity="{opacity}"' if opacity is not None else ""
        self.add(f'<g fill="{fill}"{op} transform="translate({x:.2f} {y:.2f}) scale({s:.5f} {-s:.5f})">{"".join(uses)}</g>')
        return width

    def wrap(self, text, size, maxw, wght=400, mono=False):
        words, lines, cur = text.split(" "), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if cur and self.measure(t, size, wght, mono) > maxw:
                lines.append(cur)
                cur = w
            else:
                cur = t
        if cur:
            lines.append(cur)
        return lines

    def para(self, x, y, text, size, fill, maxw, lh=1.4, wght=400, anchor="start"):
        lines = self.wrap(text, size, maxw, wght)
        for i, ln in enumerate(lines):
            self.text(x, y + i * size * lh, ln, size, fill, wght, anchor=anchor)
        return len(lines)

    def render(self):
        g = "".join(f'<path id="{n}" d="{d}"/>' for n, d in self.glyphs.values())
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" role="img">'
                f'<title>{esc(self.title)}</title><defs>{g}{"".join(self.defs)}</defs>{"".join(self.body)}</svg>\n')


# ---- icons: hand drawn on a 24 x 24 grid, stroke style ------------------
ICONS = {
    "chat": '<path d="M4 5.5h16a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5H10l-4.5 3.5V17.5H4A1.5 1.5 0 0 1 2.5 16V7A1.5 1.5 0 0 1 4 5.5z"/><path d="M7 10h10M7 13.5h6"/>',
    "save": '<path d="M3.5 12a8.5 8.5 0 1 0 2.5-6"/><path d="M3 3.5V8h4.5"/><path d="M12 7.5V12l3 2"/>',
    "key": '<circle cx="8" cy="15" r="4.5"/><path d="M11.2 11.8 20 3M16.5 6.5l2.5 2.5M14 9l2 2"/>',
    "shield": '<path d="M12 2.5 20 5.5v6c0 5-3.4 8.6-8 10-4.6-1.4-8-5-8-10v-6z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    "globe": '<circle cx="12" cy="12" r="9.5"/><path d="M2.5 12h19M12 2.5c2.6 2.8 3.9 6 3.9 9.5s-1.3 6.7-3.9 9.5c-2.6-2.8-3.9-6-3.9-9.5S9.4 5.3 12 2.5z"/>',
    "diff": '<path d="M14 2.5H6.5A1.5 1.5 0 0 0 5 4v16a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 20V7.5z"/><path d="M14 2.5v5h5M12 10v5M9.5 12.5h5M9.5 18h5"/>',
    "gauge": '<path d="M3.5 17a8.5 8.5 0 1 1 17 0"/><path d="m12 17 4-5.5"/><circle cx="12" cy="17" r="1.2"/><path d="M6.5 12.5l1 .8M12 8.5v1.2M17.5 12.5l-1 .8"/>',
    "stop": '<path d="M8.2 2.5h7.6l5.7 5.7v7.6l-5.7 5.7H8.2l-5.7-5.7V8.2z"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "lock": '<rect x="4" y="10.5" width="16" height="11" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>',
    "card": '<rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="M2.5 9.5h19M6 15h4"/>',
    "coins": '<ellipse cx="9" cy="7" rx="6" ry="3"/><path d="M3 7v4c0 1.7 2.7 3 6 3s6-1.3 6-3V7"/><path d="M9 14v4c0 1.7 2.7 3 6 3s6-1.3 6-3v-4c0-1.6-2.4-2.9-5.5-3"/>',
    "branch": '<circle cx="6" cy="5" r="2.5"/><circle cx="6" cy="19" r="2.5"/><circle cx="18" cy="8" r="2.5"/><path d="M6 7.5v9M18 10.5c0 4-6 3-11 6.5"/>',
    "pin": '<path d="M12 21.5s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "rocket": '<path d="M12 15.5 8.5 12c1.5-5 5-8.5 11-9-.5 6-4 9.5-7.5 12.5z"/><path d="M8.5 12H5l2.5-3.5h4M12 15.5V19l3.5-2.5v-4"/><path d="M6.5 16c-1.5.5-2.5 2-2.5 4 2 0 3.5-1 4-2.5"/>',
    "term": '<rect x="2.5" y="4" width="19" height="16" rx="2.5"/><path d="m7 10 3 2.5L7 15M12.5 15.5h4.5"/>',
    "box": '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M3 9h18M9 21V9"/>',
    "file": '<path d="M14 2.5H6.5A1.5 1.5 0 0 0 5 4v16a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 20V7.5z"/><path d="M14 2.5v5h5M8.5 13h7M8.5 17h5"/>',
    "pkg": '<path d="M12 2.5 20.5 7v10L12 21.5 3.5 17V7z"/><path d="M3.5 7 12 11.5 20.5 7M12 11.5v10"/>',
}


def icon(doc, name, x, y, size, color, sw=1.8):
    s = size / 24
    doc.add(f'<g transform="translate({x:.1f} {y:.1f}) scale({s:.4f})" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</g>')
