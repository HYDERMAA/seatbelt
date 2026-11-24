"""Blueprint-style engineering drawings of how Seatbelt works, for the README.

    python3 tools/readme_art/blueprints.py

Writes assets/readme/bp-*.svg. One version each: the blueprint sheet has its own background,
so it reads the same on GitHub's light and dark themes. Text is turned into paths (svgkit).
Every box is taken from SKILL.md and the three scripts, so update this file when they change.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from svgkit import Doc  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "readme")
VERSION = "3.1.0"
TOTAL = 5

BG, BG2 = "#0e3a7a", "#0a2c5f"
INK = "#eef5ff"      # main line work and titles
CY = "#7fe0ff"       # flow lines, numbers
DIM = "#d2e3f8"      # body text
FAINT = "#9fbde8"    # small print
G, A, R = "#7ef0a8", "#ffd27a", "#ff8f9a"
W = 1100
M = 30               # inner frame inset

S_HEAD, S_TITLE, S_BODY, S_SMALL = 25, 16.5, 14.5, 12.5


class Sheet:
    def __init__(self, h, no, title, subtitle, alt):
        self.h = h
        self.d = Doc(W, h, alt)
        self.no, self.title = no, title
        d = self.d
        d.adddef(f'<linearGradient id="bpbg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG}"/><stop offset="1" stop-color="{BG2}"/></linearGradient>')
        d.adddef('<pattern id="minor" width="12" height="12" patternUnits="userSpaceOnUse"><path d="M12 0H0V12" fill="none" stroke="#ffffff" stroke-opacity="0.055" stroke-width="1"/></pattern>')
        d.adddef('<pattern id="major" width="60" height="60" patternUnits="userSpaceOnUse"><path d="M60 0H0V60" fill="none" stroke="#ffffff" stroke-opacity="0.11" stroke-width="1"/></pattern>')
        for name, col in (("c", CY), ("i", INK), ("g", G), ("a", A), ("r", R), ("f", FAINT)):
            d.adddef(f'<marker id="ah{name}" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="11" markerHeight="11" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0 1.5 L12 6 L0 10.5 L3 6 z" fill="{col}"/></marker>')
            d.adddef(f'<marker id="tk{name}" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="12" markerHeight="12" markerUnits="userSpaceOnUse" orient="auto"><path d="M2 9 L8 1" stroke="{col}" stroke-width="1.4"/></marker>')
        d.add(f'<rect width="{W}" height="{h}" rx="16" fill="url(#bpbg)"/>')
        d.add(f'<rect x="{M}" y="{M}" width="{W-2*M}" height="{h-2*M}" fill="url(#minor)"/>')
        d.add(f'<rect x="{M}" y="{M}" width="{W-2*M}" height="{h-2*M}" fill="url(#major)"/>')
        # drawing frame with zone markers, like a real sheet
        d.add(f'<rect x="10" y="10" width="{W-20}" height="{h-20}" rx="8" fill="none" stroke="{INK}" stroke-opacity="0.35" stroke-width="1"/>')
        d.add(f'<rect x="{M}" y="{M}" width="{W-2*M}" height="{h-2*M}" fill="none" stroke="{INK}" stroke-opacity="0.85" stroke-width="1.4"/>')
        cols = 8
        for i in range(cols):
            x0 = M + i * (W - 2 * M) / cols
            xm = x0 + (W - 2 * M) / cols / 2
            if i:
                d.add(f'<path d="M{x0:.1f} 10V{M}M{x0:.1f} {h-M}V{h-10}" stroke="{INK}" stroke-opacity="0.35"/>')
            d.text(xm, 25, str(i + 1), 10.5, FAINT, 500, mono=True, anchor="middle")
            d.text(xm, h - 15.5, str(i + 1), 10.5, FAINT, 500, mono=True, anchor="middle")
        rows = max(3, round((h - 2 * M) / 220))
        for j in range(rows):
            y0 = M + j * (h - 2 * M) / rows
            ym = y0 + (h - 2 * M) / rows / 2
            if j:
                d.add(f'<path d="M10 {y0:.1f}H{M}M{W-M} {y0:.1f}H{W-10}" stroke="{INK}" stroke-opacity="0.35"/>')
            d.text(20, ym + 4, "ABCDEFGH"[j], 10.5, FAINT, 500, mono=True, anchor="middle")
            d.text(W - 20, ym + 4, "ABCDEFGH"[j], 10.5, FAINT, 500, mono=True, anchor="middle")
        # centring marks
        for x, y, dx, dy in ((W / 2, M, 0, 10), (W / 2, h - M, 0, -10), (M, h / 2, 10, 0), (W - M, h / 2, -10, 0)):
            d.add(f'<path d="M{x} {y}l{dx} {dy}" stroke="{INK}" stroke-width="1.4"/>')
        # heading
        d.text(M + 26, M + 46, f"{no}", S_HEAD, CY, 700, mono=True)
        x = M + 26 + d.measure(no, S_HEAD, 700, True) + 18
        d.text(x, M + 46, title.upper(), S_HEAD, INK, 650, mono=True, track=0.02)
        d.text(M + 26, M + 72, subtitle, S_BODY, DIM, 400, mono=True)
        d.add(f'<path d="M{M+26} {M+86}H{W-M-26}" stroke="{INK}" stroke-opacity="0.4" stroke-dasharray="2 4"/>')

    # ---- primitives ------------------------------------------------
    def t(self, x, y, s, size=S_BODY, fill=DIM, wght=400, anchor="start", track=0):
        if not s:
            return 0
        return self.d.text(x, y, s, size, fill, wght, mono=True, anchor=anchor, track=track)

    def wrap(self, s, size, maxw):
        return self.d.wrap(s, size, maxw, mono=True)

    def balloon(self, cx, cy, n, col=CY, r=14):
        self.d.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{BG2}" stroke="{col}" stroke-width="1.6"/>')
        self.t(cx, cy + 5, str(n), 14, col, 700, anchor="middle")

    def box(self, x, y, w, h, title, lines=(), n=None, col=INK, dashed=False, fill=0.05, tag=None, size=S_BODY):
        da = ' stroke-dasharray="6 5"' if dashed else ""
        self.d.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffffff" fill-opacity="{fill}" stroke="{col}" stroke-width="1.4"{da}/>')
        # crop marks just outside each corner
        k = 7
        for cx, cy, sx, sy in ((x, y, -1, -1), (x + w, y, 1, -1), (x, y + h, -1, 1), (x + w, y + h, 1, 1)):
            self.d.add(f'<path d="M{cx+sx*3} {cy}h{sx*k}M{cx} {cy+sy*3}v{sy*k}" stroke="{col}" stroke-opacity="0.7"/>')
        tx = x + 16 + (22 if n is not None else 0)
        if n is not None:
            self.balloon(x + 2, y + 2, n, CY if col == INK else col)
        yy = y + 27
        if title:
            self.t(tx - (22 if n is not None else 0) + (10 if n is not None else 0), yy, title, S_TITLE, col if col != INK else INK, 700, track=0.02)
            yy += 8
        if tag:
            self.t(x + w - 12, y + 25, tag, S_SMALL, FAINT, 500, anchor="end")
        out = []
        cw = self.d.measure("0", size, 400, True)
        for ln in lines:
            bullet = ln.startswith("- ")
            body = ln[2:] if bullet else ln
            lead = len(body) - len(body.lstrip(" "))
            body = body.strip()
            indent = (16 if bullet else 0) + lead * cw
            for i, part in enumerate(self.wrap(body, size, w - 32 - indent) or [""]):
                yy += size * 1.45
                if bullet and i == 0:
                    self.d.add(f'<rect x="{x+18}" y="{yy-size*0.42:.1f}" width="5" height="5" fill="{CY}"/>')
                self.t(x + 16 + indent + (16 if bullet and i else 0) * 0, yy, part, size, DIM)
                out.append(yy)
        return yy

    def line(self, pts, col=CY, arrow=True, dashed=False, start=False, sw=1.5):
        key = {CY: "c", INK: "i", G: "g", A: "a", R: "r", FAINT: "f"}[col]
        p = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        da = ' stroke-dasharray="7 5"' if dashed else ""
        me = f' marker-end="url(#ah{key})"' if arrow else ""
        ms = f' marker-start="url(#ah{key})"' if start else ""
        self.d.add(f'<path d="{p}" fill="none" stroke="{col}" stroke-width="{sw}"{da}{me}{ms}/>')

    def label(self, x, y, s, col=FAINT, anchor="middle", size=S_SMALL, bg=True, wght=500):
        w = self.d.measure(s, size, wght, True)
        lx = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
        if bg:
            self.d.add(f'<rect x="{lx-5:.1f}" y="{y-size:.1f}" width="{w+10:.1f}" height="{size+7:.1f}" fill="{BG}"/>')
        self.t(x, y, s, size, col, wght, anchor=anchor)

    def dim(self, x1, x2, y, s, col=FAINT, ext=14, lx=None):
        """Dimension line: extension lines, arrows both ends, label in the middle."""
        self.d.add(f'<path d="M{x1} {y-ext}V{y+6}M{x2} {y-ext}V{y+6}" stroke="{col}" stroke-width="1"/>')
        key = {CY: "c", FAINT: "f", A: "a", G: "g", INK: "i"}[col]
        self.d.add(f'<path d="M{x1+1} {y}H{x2-1}" stroke="{col}" stroke-width="1" marker-end="url(#ah{key})" marker-start="url(#ah{key})"/>')
        self.label(lx if lx is not None else (x1 + x2) / 2, y + 4.5, s, col)

    def vdim(self, x, y1, y2, s, col=FAINT, ext=14):
        self.d.add(f'<path d="M{x-6} {y1}H{x+ext}M{x-6} {y2}H{x+ext}" stroke="{col}" stroke-width="1"/>')
        key = {CY: "c", FAINT: "f", A: "a", G: "g", INK: "i"}[col]
        self.d.add(f'<path d="M{x} {y1+1}V{y2-1}" stroke="{col}" stroke-width="1" marker-end="url(#ah{key})" marker-start="url(#ah{key})"/>')
        ym = (y1 + y2) / 2
        w = self.d.measure(s, S_SMALL, 500, True)
        self.d.add(f'<rect x="{x-8}" y="{ym-w/2-5:.1f}" width="16" height="{w+10:.1f}" fill="{BG}"/>')
        self.d.add(f'<g transform="rotate(-90 {x} {ym})">')
        self.t(x, ym + 4.5, s, S_SMALL, col, 500, anchor="middle")
        self.d.add('</g>')

    def callout(self, x, y, tx, ty, lines, col=CY, anchor="start"):
        """Leader line from a dot on the part to a note, with a shoulder."""
        sh = 16 if anchor == "start" else -16
        self.d.add(f'<circle cx="{x}" cy="{y}" r="3" fill="{col}"/>')
        self.d.add(f'<path d="M{x} {y}L{tx} {ty}h{sh}" fill="none" stroke="{col}" stroke-width="1"/>')
        for i, s in enumerate(lines):
            self.t(tx + sh + (6 if anchor == "start" else -6), ty + 4.5 + i * 18, s, S_SMALL, col if i == 0 else DIM, 600 if i == 0 else 400, anchor=anchor)

    def diamond(self, cx, cy, w, h, lines, col=INK):
        self.d.add(f'<path d="M{cx} {cy-h/2}L{cx+w/2} {cy}L{cx} {cy+h/2}L{cx-w/2} {cy}z" fill="#ffffff" fill-opacity="0.05" stroke="{col}" stroke-width="1.4"/>')
        n = len(lines)
        for i, s in enumerate(lines):
            self.t(cx, cy + 5 + (i - (n - 1) / 2) * 19, s, S_BODY if i == 0 else S_SMALL, INK if i == 0 else DIM, 700 if i == 0 else 400, anchor="middle")

    def chip(self, x, y, s, col=CY, size=S_SMALL):
        w = self.d.measure(s, size, 600, True) + 18
        self.d.add(f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{size+11}" rx="2" fill="{col}" fill-opacity="0.12" stroke="{col}" stroke-opacity="0.8"/>')
        self.t(x + 9, y + size + 3.5, s, size, col, 600)
        return w

    def notes(self, x, y, w, items, head="NOTES"):
        self.t(x, y, head, S_SMALL, INK, 700, track=0.12)
        self.d.add(f'<path d="M{x} {y+7}H{x+w}" stroke="{INK}" stroke-opacity="0.4"/>')
        yy = y + 8
        for i, s in enumerate(items, 1):
            for j, part in enumerate(self.wrap(s, S_SMALL, w - 30)):
                yy += S_SMALL * 1.5
                if j == 0:
                    self.t(x, yy, f"{i}.", S_SMALL, CY, 700)
                self.t(x + 26, yy, part, S_SMALL, DIM)
        return yy

    def title_block(self, sheet, scale="NTS"):
        d, h = self.d, self.h
        bw, bh = 410, 96
        x, y = W - M - bw, h - M - bh
        d.add(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" fill="{BG2}" stroke="{INK}" stroke-width="1.4"/>')
        d.add(f'<path d="M{x} {y+40}H{x+bw}M{x} {y+68}H{x+bw}M{x+250} {y}V{y+40}M{x+102} {y+68}V{y+bh}M{x+204} {y+68}V{y+bh}M{x+306} {y+68}V{y+bh}" stroke="{INK}" stroke-opacity="0.7"/>')
        self.t(x + 12, y + 27, "SEATBELT", 19, INK, 750, track=0.08)
        self.t(x + 262, y + 15, "DWG NO.", 9.5, FAINT, 500, track=0.1)
        self.t(x + 262, y + 33, self.no, 15, CY, 700)
        self.t(x + 12, y + 59, "TITLE  " + self.title.upper(), 12.5, DIM, 600)
        for i, (k, v) in enumerate((("SCALE", scale), ("SHEET", f"{sheet} OF {TOTAL}"), ("REV", VERSION), ("DRAWN", "M. HYDER"))):
            self.t(x + 10 + i * 102, y + 79, k, 9, FAINT, 500, track=0.1)
            self.t(x + 10 + i * 102, y + 92, v, 11.5, INK, 600)
        return x, y


# =====================================================================
def bp_system():
    H = 1290
    s = Sheet(H, "BP-01", "System flow", "From your message to an honest report. Source: SKILL.md.",
              "Blueprint BP-01, system flow. 1 Request. Decide first: broken goes to rescue mode, a question or fix gets a direct answer in steps, a feature gets its safety parts named, a new app goes to risk triage. 2 Risk triage: Green, Amber or Red, more risk means more care. 3 One-screen plan you approve. 4 Build loop: save point, explain_changes.py, one change, proof, update PROJECT.md. 5 Ship check with check_secrets.py, check_live.py and the builder's own scans. If a fix breaks twice, roll back to the last save point. 6 Honest report: passed, problems worst first, left for later.")
    s.box(60, 190, 250, 150, "REQUEST", ['"make me an app"', '"my app broke"', "a question", "a new feature"], n=1)
    s.diamond(470, 265, 230, 150, ["DECIDE", "first: what", "kind of ask?"])
    s.line([(310, 265), (353, 265)])
    s.label(332, 252, "chat", size=11.5, bg=False)
    rx, rw, trunk = 680, 360, 630
    routes = [
        (148, 112, "RESCUE MODE", "IF BROKEN", ["back to the last save point, get the real error, one fix", "two strikes: stop, change approach"], A),
        (282, 74, "ANSWER IN STEPS", "IF QUESTION/FIX", ["no starter questions, no risk level"], INK),
        (378, 92, "FEATURE SAFETY PARTS", "IF FEATURE", ["named in the first reply, then build"], INK),
    ]
    for y, hh, title, tag, lines, col in routes:
        s.box(rx, y, rw, hh, title, lines, col=col, size=13.5, tag=tag)
        s.line([(trunk, y + 22), (rx - 2, y + 22)], col=CY)
    s.d.add(f'<path d="M585 265H{trunk}M{trunk} {148+22}V{378+22}" fill="none" stroke="{CY}" stroke-width="1.5"/>')
    s.d.add(f'<circle cx="{trunk}" cy="265" r="3.5" fill="{CY}"/>')
    # new app goes down to triage
    s.line([(470, 340), (470, 543)])
    s.label(470, 420, "NEW APP", CY, wght=700)
    s.balloon(60, 490, 2)
    s.t(84, 495, "RISK TRIAGE", S_TITLE, INK, 700, track=0.02)
    s.t(1040, 495, "from what the app does, told to you in one line", S_SMALL, FAINT, anchor="end")
    s.dim(60, 1040, 522, "MORE RISK = MORE CARE", lx=790, ext=10)
    tw = (980 - 40) / 3
    tri = [
        ("GREEN", G, ["no logins, personal data or money", "e.g. menu, portfolio, event page", "- at most 2 questions, then build", "- simple websites stay Green"]),
        ("AMBER", A, ["logins, personal data or a paid AI", "e.g. booking form, AI chat app", "- 6 starter questions + plan", "- database rules, spending caps"]),
        ("RED", R, ["money, health, children or many users", "e.g. shop, health or finance app", "- everything in Amber", "- verified webhooks, developer review"]),
    ]
    for i, (name, col, lines) in enumerate(tri):
        s.box(60 + i * (tw + 20), 545, tw, 185, name, lines, col=col, size=13.5)
    s.t(1040, 750, "the level can go up mid-project", S_SMALL, FAINT, anchor="end")
    # collector into plan
    y3 = 790
    xs = [185, 550, 877]
    s.d.add(f'<path d="M185 730V766M550 730V766M877 730V766M185 766H877" fill="none" stroke="{CY}" stroke-width="1.5"/>')
    for x in xs[1:]:
        s.d.add(f'<circle cx="{x}" cy="766" r="3" fill="{CY}"/>')
    s.line([(185, 766), (185, y3 - 2)])
    s.box(60, y3, 250, 200, "ONE-SCREEN PLAN", ["what, who, risk level", "features, data, money", "steps small enough to check", "you reply yes"], n=3)
    s.line([(310, y3 + 70), (348, y3 + 70)])
    s.box(350, y3, 340, 230, "BUILD LOOP", [], n=4)
    s.t(676, y3 + 25, "one change per step", S_SMALL, FAINT, anchor="end")
    steps = ["save point", "explain_changes.py", "one change", "proof it works", "update PROJECT.md"]
    cx0, cy0 = 520, y3 + 132
    pts = [(cx0, cy0 - 70), (cx0 + 112, cy0 - 22), (cx0 + 78, cy0 + 60), (cx0 - 78, cy0 + 60), (cx0 - 112, cy0 - 22)]
    s.d.add(f'<ellipse cx="{cx0}" cy="{cy0-4}" rx="118" ry="68" fill="none" stroke="{CY}" stroke-opacity="0.6" stroke-dasharray="3 5"/>')
    for i, ((px, py), st) in enumerate(zip(pts, steps)):
        w = s.d.measure(st, 12.5, 600, True) + 16
        s.d.add(f'<rect x="{px-w/2:.1f}" y="{py-12}" width="{w:.1f}" height="23" fill="{BG}" stroke="{CY}"/>')
        s.t(px, py + 4.5, st, 12.5, INK if i != 1 else CY, 600, anchor="middle")
    s.t(cx0, cy0 + 1, "repeat", 11.5, FAINT, 500, anchor="middle")
    s.line([(690, y3 + 70), (718, y3 + 70)])
    s.box(720, y3, 320, 230, "SHIP CHECK", ["- check_secrets.py", "  > ship-report.md", "- check_live.py --mine", "  [--two-users]", "  > live-report.md", "- the builder's own scans"], n=5)
    # rescue return path, with a line hop where it crosses the report line
    yr = 1040
    s.d.add(f'<path d="M1040 170H1056V{yr}H888A8 8 0 0 0 872 {yr}H520V{y3+234}" fill="none" stroke="{A}" stroke-width="1.5" stroke-dasharray="7 5" marker-end="url(#aha)"/>')
    s.label(700, yr + 4.5, "BROKE TWICE: back to the last save point", A, wght=600)
    s.line([(880, y3 + 230), (880, 1110), (612, 1110)])
    s.box(60, 1070, 550, 80, "HONEST REPORT", ['passed, problems worst first, left for later. Never says "secure".'], n=6, size=13.5)
    s.notes(60, 1186, 560, ["Fixes and features use the same habits: save point first, keys secret, two strikes.", "PROJECT.md carries progress between chats."])
    s.title_block(1)
    return s.d


def bp_scanner():
    H = 1090
    s = Sheet(H, "BP-02", "Ship check scanner",
              "check_secrets.py: reads files only, needs only Python 3, uploads nothing.",
              "Blueprint BP-02, the ship check scanner. 1 Project folder. 2 Walk the files, skipping .git, node_modules, images, lock files and files over 2 MB. 3 Scan each file: secret keys, public prefixes, the Supabase service role in browser code, code risks such as prices set in the browser and unverified webhooks, the runaway-cost guard, and collecting SQL and Firebase rules. 4 Project checks: database rules, .env in git history, frequent cron jobs, .gitignore. 5 Optional npm audit. 6 Sort worst first and fold repeats. 7 Output to the terminal, JSON or a Markdown or HTML report, with exit codes.")
    s.box(60, 150, 260, 120, "PROJECT FOLDER", ["check_secrets.py .", "  [--report r.md|.html]", "  [--audit] [--json]"], n=1, size=13)
    s.box(60, 330, 260, 230, "WALK", ["- skips .git, node_modules, build caches", "- skips images, fonts, zips, lock files, files over 2 MB", "- notes source maps in public build folders"], n=2, size=13)
    s.line([(190, 270), (190, 328)])
    bx, bw = 380, 380
    s.box(bx, 150, bw, 660, "PER-FILE SCAN", [], n=3)
    s.t(bx + bw - 12, 175, "every text file", S_SMALL, FAINT, 500, anchor="end")
    subs = [
        ("3a", "SECRET KEYS", "26 key patterns; placeholders ignored; .env vs browser code", INK),
        ("3b", "PUBLIC PREFIXES", "NEXT_PUBLIC_, VITE_ ... holding a secret-looking name", INK),
        ("3c", "SERVICE ROLE IN BROWSER", "Supabase master key in code visitors download", INK),
        ("3d", "CODE RISKS", "price set in the browser, success-page grant, unverified webhook, CORS *", INK),
        ("3e", "RUNAWAY-COST GUARD", "paid services, AI calls with no per-person limit, AI in loops, timers", A),
        ("3f", "COLLECT FOR LATER", ".sql files and Firebase .rules", INK),
    ]
    yy = 198
    bus = bx + 26
    tops = []
    for code, title, text, col in subs:
        hh = 44 + 18.2 * len(s.wrap(text, 12.5, bw - 70 - 32))
        tops.append(yy)
        s.line([(bus, yy + 22), (bx + 48, yy + 22)])
        s.d.add(f'<circle cx="{bus}" cy="{yy+22}" r="3" fill="{CY}"/>')
        s.box(bx + 50, yy, bw - 70, hh, f"{code} {title}", [text], col=col, size=12.5, fill=0.04)
        yy += hh + 11
    s.d.add(f'<path d="M{bus} 190V{tops[-1]+22}" stroke="{CY}" stroke-width="1.5"/>')
    s.d.add(f'<path d="M320 445H350V190H{bus}" fill="none" stroke="{CY}" stroke-width="1.5"/>')
    s.label(350, 320, "each file", CY, size=11.5)
    cx, cw = 810, 230
    s.box(cx, 150, cw, 250, "PROJECT CHECKS", ["- SQL: RLS off, a policy that lets everyone in, public buckets", "- .env in git history", "- frequent cron jobs", "- .gitignore covers .env"], n=4, size=12.5)
    s.line([(bx + bw, 470), (785, 470), (785, 275), (cx - 2, 275)])
    s.box(cx, 440, cw, 80, "--audit", ["npm audit (optional, needs internet)"], n=5, dashed=True, size=12.5)
    s.line([(cx + cw / 2, 400), (cx + cw / 2, 438)], dashed=True)
    s.box(cx, 555, cw, 100, "SORT AND FOLD", ["critical > high > medium > low; repeats folded"], n=6, size=12.5)
    s.line([(cx + cw / 2, 520), (cx + cw / 2, 553)])
    s.callout(bx + bw - 24, tops[4] + 60, 790, 720, ["v3 COST GUARD", "lists every paid service,", "so you cap each one"], col=A)
    s.box(60, 860, 720, 100, "OUTPUT", ["terminal  |  --json  |  --report ship-report.md or .html", "exit 0 ready  |  1 fix something first  |  2 usage error"], n=7, size=13.5)
    s.line([(1020, 655), (1020, 910), (782, 910)])
    s.dim(380, 760, 836, "ONE PASS, NO NETWORK (except --audit)")
    s.t(60, 610, '"seatbelt-ignore" on a line', S_SMALL, CY, 600)
    s.t(60, 628, "silences a finding you", S_SMALL, DIM)
    s.t(60, 646, "checked by hand", S_SMALL, DIM)
    s.d.add(f'<path d="M60 662H320" stroke="{CY}" stroke-opacity="0.5" stroke-dasharray="2 4"/>')
    s.t(60, 686, "Placeholders such as", S_SMALL, DIM)
    s.t(60, 704, "your-key-here are ignored", S_SMALL, DIM)
    s.title_block(2)
    return s.d


def bp_live():
    H = 1400
    s = Sheet(H, "BP-03", "Live check",
              "check_live.py: reads your live site like a stranger. Changes nothing. Your own site only.",
              "Blueprint BP-03, the live check. 1 Your site address. 2 Gather the home page and up to 40 same-site JavaScript files. 3 Stranger checks: keys in served code, downloadable .env and .git files, HTTPS and headers, source maps. With --mine: 4 find the Supabase or Firebase address and public key in your own pages, never a secret key. 5 Ask each table for one row as a stranger: open, refused or empty. With --two-users: 6 log in as test accounts A and B, find B's rows, ask for them as A, then the other way round, and list each other's storage folders. Reads only, writes are not tested. 7 Report with database, between customers and notes sections, counts and column names only.")
    s.box(60, 150, 220, 110, "SITE ADDRESS", ["https://your-site", "--mine --two-users", "--report live.md"], n=1, size=13)
    s.line([(280, 205), (318, 205)])
    s.box(320, 150, 320, 110, "GATHER", ["home page + same-site JS, imports and chunks (max 40)"], n=2, size=13)
    s.line([(640, 205), (678, 205)])
    s.box(680, 150, 360, 165, "STRANGER CHECKS", ["- keys inside served code", "- /.env, /.git/HEAD downloadable? (vs a random page)", "- HTTPS and security headers", "- public source maps"], n=3, size=13)
    s.diamond(495, 385, 200, 110, ["--mine?", "your own site"])
    s.line([(860, 315), (860, 385), (597, 385)])
    s.d.add(f'<path d="M395 385H45V1280H58" fill="none" stroke="{FAINT}" stroke-width="1.5" stroke-dasharray="7 5" marker-end="url(#ahf)"/>')
    s.label(240, 377, "no: database not tested", FAINT)
    s.line([(495, 440), (495, 478)])
    s.label(518, 465, "yes", CY, anchor="start", bg=False)
    s.box(280, 480, 430, 150, "FIND THE DATABASE", ["Supabase address + PUBLIC key from your own pages; table and bucket names from .from(...); Firebase config too.", "A secret key is never used, even if leaked."], n=4, size=12.5)
    s.line([(710, 555), (738, 555)])
    s.box(740, 480, 300, 150, "STRANGER PROBE", ["each table, public key only:", "?select=*&limit=1"], n=5, size=12.5)
    for i, (lab, col) in enumerate((("OPEN", R), ("REFUSED", G), ("EMPTY", INK))):
        s.chip(756 + i * 92, 590, lab, col)
    s.diamond(495, 700, 220, 100, ["--two-users?", "logins in your app"])
    s.line([(495, 630), (495, 648)])
    s.d.add(f'<path d="M890 630V700H607" fill="none" stroke="{CY}" stroke-width="1.5"/>')
    sy, sh = 790, 410
    s.box(60, sy, 980, sh, "TWO-ACCOUNT TEST", [], n=6)
    s.t(1026, sy + 26, "can customer A read customer B's data?", S_SMALL, FAINT, 500, anchor="end")
    s.line([(495, 750), (495, sy - 2)])
    s.label(518, 774, "yes", CY, anchor="start", bg=False)
    lanes = [(230, "TEST ACCOUNT A"), (520, "YOUR DATABASE API"), (810, "TEST ACCOUNT B")]
    for x, name in lanes:
        w = s.d.measure(name, 13, 700, True) + 24
        s.d.add(f'<rect x="{x-w/2:.1f}" y="{sy+46}" width="{w:.1f}" height="28" fill="{BG2}" stroke="{INK}"/>')
        s.t(x, sy + 65, name, 13, INK, 700, anchor="middle")
        s.d.add(f'<path d="M{x} {sy+74}V{sy+sh-20}" stroke="{INK}" stroke-opacity="0.55" stroke-dasharray="5 5"/>')
    rows = [
        (230, 520, "log in as A (env vars or prompt)", CY),
        (810, 520, "log in as B (a different user)", CY),
        (810, 520, "read own rows, find B's id columns", CY),
        (230, 520, "ask for rows where <col> = B's id", CY),
        (520, 230, "rows back? LEAK.  none? good", A),
        (230, 520, "swap: B asks for A's rows", CY),
        (230, 520, "list B's folder in each bucket", CY),
    ]
    yy = sy + 114
    for i, (x1, x2, lab, col) in enumerate(rows, 1):
        s.line([(x1, yy), (x2 + (-6 if x2 > x1 else 6), yy)], col=col)
        s.label((x1 + x2) / 2, yy - 8, lab, DIM if col == CY else A, size=12)
        bxp = min(x1, x2) - 26 if (x1 < x2 or x1 == 520) else max(x1, x2) + 26
        s.balloon(bxp, yy, i, col, r=11)
        yy += 40
    s.t(866, sy + 250, "READS ONLY", S_SMALL, A, 700, track=0.06)
    for i, ln in enumerate(["logging in is the", "only thing it sends", "", "writes (can A edit", "or delete B's rows?)", "are not tested:", "check those by hand"]):
        s.t(866, sy + 272 + i * 18, ln, S_SMALL, DIM)
    s.d.add(f'<path d="M856 {sy+236}V{sy+392}" stroke="{A}" stroke-opacity="0.7"/>')
    s.line([(495, sy + sh), (495, 1218)])
    s.box(60, 1220, 560, 120, "REPORT", ["DATABASE: what a stranger can read", "BETWEEN CUSTOMERS: can one account read another's", "NOTES  |  counts and column names, never the data"], n=7, size=12.5)
    s.title_block(3)
    return s.d


def bp_changes():
    H = 1090
    s = Sheet(H, "BP-04", "Change explainer",
              "explain_changes.py: before each save point, what changed and is it risky. Reads only.",
              "Blueprint BP-04, the change explainer. 1 Project folder. Is it using git? If not, make the first save point. 2 Compare with the last save point, or a branch with --since, including new files not saved yet. 3 Sort changed files into areas such as database, payments, logins, secrets and settings, packages, server code, tests and pages. 4 Risk rules on added lines, removed lines and whole files. 5 New packages, checked against npm and PyPI with --check-packages. 6 Verdict: risk low, medium or high, with a suggested save point name. Exit 1 when high.")
    s.box(60, 150, 250, 100, "PROJECT FOLDER", ["explain_changes.py .", "[--since main]"], n=1, size=13)
    s.line([(310, 200), (378, 200)])
    s.diamond(480, 200, 200, 100, ["git?", "save points on"])
    s.line([(480, 250), (480, 288)], col=FAINT, dashed=True)
    s.box(370, 290, 220, 84, "NOT YET", ["make the first save point, then run again"], col=FAINT, dashed=True, size=12.5)
    s.label(496, 274, "no", FAINT, anchor="start", bg=False)
    s.line([(580, 200), (638, 200)])
    s.label(609, 190, "yes", CY, bg=False)
    s.box(640, 150, 400, 130, "DIFF SINCE LAST SAVE POINT", ["git diff HEAD (or --since): numstat, name-status, -U0 patch", "+ new files not saved yet"], n=2, size=13)
    s.line([(840, 280), (840, 398)])
    s.box(60, 400, 980, 120, "SORT INTO AREAS", [], n=3)
    areas = ["database", "payments", "logins", "secrets and settings", "packages", "server code", "tests", "pages and design", "app code", "documents"]
    x, y = 84, 445
    for a in areas:
        w = s.d.measure(a, 12.5, 600, True) + 18
        if x + w > 1016:
            x, y = 84, y + 34
        s.chip(x, y, a, A if a in ("database", "payments", "logins") else CY)
        x += w + 10
    s.line([(550, 520), (550, 590)])
    s.balloon(60, 572, 4)
    s.t(84, 577, "RISK RULES", S_TITLE, INK, 700, track=0.02)
    cw = (980 - 40) / 3
    rules = [
        ("ADDED LINES", ["- a real key (same patterns as the ship check)", "- RLS turned off, using (true)", "- grant all to anon", "- drop, truncate, delete all", "- AI key allowed in the browser", "- paid API, timers, CORS *"]),
        ("REMOVED LINES", ["- Stripe signature check", "- enable row level security", "- login or ownership checks", "- rate limits"]),
        ("WHOLE FILES", ["- a file deleted", "- 40+ lines removed, few added", "- .env about to be saved", "- database changed: back up the data first", "- big change: split it"]),
    ]
    for i, (t, lines) in enumerate(rules):
        s.box(60 + i * (cw + 20), 600, cw, 215, t, lines, col=INK, size=12.5)
    s.line([(550, 815), (550, 835), (295, 835), (295, 853)])
    s.box(60, 855, 470, 110, "NEW PACKAGES", ["package.json, requirements.txt", "--check-packages: on npm or PyPI? widely downloaded?"], n=5, size=12.5)
    s.line([(530, 910), (568, 910)])
    s.box(570, 855, 470, 110, "VERDICT", ["risk LOW / MEDIUM / HIGH", 'suggested name: "payments changes"', "exit 1 when HIGH"], n=6, size=12.5)
    s.t(60, 1000, "Made-up package names are a known attack: AI tools invent", S_SMALL, A, 500)
    s.t(60, 1018, "them and attackers publish malware under them.", S_SMALL, A, 500)
    s.t(60, 1036, "--check-packages looks each one up.", S_SMALL, A, 500)
    s.title_block(4)
    return s.d


def bp_loop():
    H = 1040
    s = Sheet(H, "BP-05", "Where Seatbelt sits",
              "The vibe-coding loop, with Seatbelt as a skill inside your builder AI.",
              "Blueprint BP-05, where Seatbelt sits in the vibe-coding loop. You describe an idea, the builder AI writes code, a save point is made, the app is deployed, and people use the live app, which feeds back new ideas. Seatbelt is loaded into the builder AI and adds four gates: G1 plan and risk level before building, G2 the change explainer at each save point, G3 the ship check before deploy, G4 the live check after deploy. If a fix breaks twice, it goes back to the last save point.")
    nodes = [
        (70, 170, 220, "YOU", ["an idea, in", "plain English"]),
        (440, 170, 260, "BUILDER AI", ["Claude Code, Cursor, Codex,", "Lovable, Bolt, Replit"]),
        (810, 170, 200, "CODE", ["your project", "files"]),
        (810, 430, 200, "SAVE POINT", ["git commit or", "builder history"]),
        (810, 690, 200, "DEPLOY", ["Vercel, Netlify,", "builder hosting"]),
        (440, 690, 260, "LIVE APP", ["pages + database", "(Supabase, Firebase)"]),
        (70, 690, 220, "PEOPLE", ["your customers", "and visitors"]),
    ]
    for x, y, w, t, lines in nodes:
        s.box(x, y, w, 100, t, lines, size=13)
    s.line([(290, 220), (438, 220)])
    s.label(395, 210, "prompt", FAINT)
    s.line([(700, 220), (808, 220)])
    s.label(754, 210, "writes", FAINT)
    s.line([(910, 270), (910, 428)])
    s.line([(910, 530), (910, 688)])
    s.line([(810, 740), (702, 740)])
    s.line([(440, 740), (292, 740)])
    s.label(366, 730, "use", FAINT)
    s.line([(180, 690), (180, 272)])
    s.label(180, 480, "feedback, new ideas", FAINT)
    sx, sy, sw, sh = 330, 340, 350, 260
    s.d.add(f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="{CY}" fill-opacity="0.07" stroke="{CY}" stroke-width="2"/>')
    s.d.add(f'<rect x="{sx+6}" y="{sy+6}" width="{sw-12}" height="{sh-12}" fill="none" stroke="{CY}" stroke-opacity="0.5"/>')
    s.t(sx + sw / 2, sy + 40, "SEATBELT SKILL", 20, CY, 750, anchor="middle", track=0.08)
    s.t(sx + sw / 2, sy + 62, "loaded into the builder AI", S_SMALL, DIM, 400, anchor="middle")
    inner = [("SKILL.md", "habits + triage"), ("check_secrets.py", "ship check"), ("check_live.py", "live check"), ("explain_changes.py", "changes")]
    for i, (a, b) in enumerate(inner):
        s.t(sx + 28, sy + 104 + i * 26, a, 13, INK, 600)
        s.t(sx + sw - 28, sy + 104 + i * 26, b, 13, DIM, 400, anchor="end")
    s.t(sx + sw / 2, sy + sh - 22, "reads only, uploads nothing", S_SMALL, FAINT, 500, anchor="middle")
    s.line([(505, 270), (505, sy - 2)], col=CY, start=True)
    s.label(505, 312, "loads", CY)
    gates = [((330, 220), "G1", "plan + risk level"), ((910, 350), "G2", "explain_changes.py"),
             ((910, 610), "G3", "check_secrets.py"), ((570, 790), "G4", "check_live.py --mine --two-users")]
    for (gx, gy), g, lab in gates:
        if g == "G1":
            s.d.add(f'<path d="M{gx} {gy}V140" stroke="{A}" stroke-dasharray="3 3"/>')
            s.label(gx, 136, f"{g}  {lab}", A, wght=600)
        elif g == "G4":
            s.d.add(f'<path d="M{gx} {gy}V836" stroke="{A}" stroke-dasharray="3 3"/>')
            s.label(gx, 852, f"{g}  {lab}", A, wght=600)
        else:
            s.d.add(f'<path d="M{gx} {gy}H{gx-40}" stroke="{A}" stroke-dasharray="3 3"/>')
            s.label(gx - 46, gy + 4.5, f"{g}  {lab}", A, anchor="end", wght=600)
        s.d.add(f'<rect x="{gx-15}" y="{gy-11}" width="30" height="22" fill="{BG2}" stroke="{A}" stroke-width="1.5"/>')
        s.t(gx, gy + 5, g, 12.5, A, 700, anchor="middle")
    s.d.add(f'<path d="M1010 740H1036V480H1012" fill="none" stroke="{A}" stroke-width="1.5" stroke-dasharray="7 5" marker-end="url(#aha)"/>')
    s.d.add('<g transform="rotate(-90 1052 610)">')
    s.t(1052, 614, "broke twice: roll back", S_SMALL, A, 600, anchor="middle")
    s.d.add('</g>')
    s.notes(70, 900, 540, ["Gates are habits the AI follows, plus scripts it runs when it can run commands.", "In chat-only tools the AI follows G1 and talks you through the rest."])
    s.title_block(5)
    return s.d


ALL = dict(system=bp_system, scanner=bp_scanner, live=bp_live, changes=bp_changes, loop=bp_loop)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:]
    for name, fn in ALL.items():
        if only and name not in only:
            continue
        svg = fn().render()
        p = os.path.join(OUT, f"bp-{name}.svg")
        with open(p, "w") as fh:
            fh.write(svg)
        print(f"{p}  {len(svg)//1024} KB")
