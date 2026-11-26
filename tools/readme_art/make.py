"""Builds every README graphic in assets/readme/, in a light and a dark version.

    python3 tools/readme_art/make.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from svgkit import Doc, icon  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "readme")

THEMES = {
    "light": dict(
        card="#ffffff", card2="#f6f8fa", line="#d8dee4", line2="#eaeef2", ink="#0b1220", ink2="#3d4756", mute="#6b7685",
        brand="#4f46e5", brand2="#7c3aed", brandsoft="#eef0ff", coral="#f43f5e", amberc="#f59e0b",
        green="#15803d", greensoft="#e7f6ec", amber="#b45309", ambersoft="#fdf3e1", red="#c81e3a", redsoft="#fde8ec",
        shadow="#1f2937", shadowop="0.07",
    ),
    "dark": dict(
        card="#111722", card2="#0d121b", line="#273142", line2="#1c2432", ink="#f2f5f9", ink2="#c3ccd8", mute="#8a96a8",
        brand="#8b8cff", brand2="#b388ff", brandsoft="#1d1f45", coral="#ff6b81", amberc="#fbbf24",
        green="#4ade80", greensoft="#0f2a1b", amber="#fbbf24", ambersoft="#2e2410", red="#ff6b81", redsoft="#341620",
        shadow="#000000", shadowop="0.35",
    ),
}


def card(d, t, x, y, w, h, r=20, fill=None, stroke=None, shadow=True):
    if shadow:
        fid = "sh"
        if not any('id="sh"' in s for s in d.defs):
            d.adddef(f'<filter id="sh" x="-10%" y="-10%" width="120%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="{t["shadow"]}" flood-opacity="{t["shadowop"]}"/></filter>')
        d.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill or t["card"]}" stroke="{stroke or t["line"]}" filter="url(#{fid})"/>')
    else:
        d.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill or t["card"]}" stroke="{stroke or t["line"]}"/>')


def grad(d, gid, c1, c2, x2=1, y2=0):
    d.adddef(f'<linearGradient id="{gid}" x1="0" y1="0" x2="{x2}" y2="{y2}"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>')


def eyebrow(d, t, x, y, label, anchor="start"):
    d.text(x, y, label.upper(), 15, t["brand"], 700, anchor=anchor, track=0.12)


# =====================================================================
def hero(mode):
    t = THEMES[mode]
    W, H = 1200, 560
    d = Doc(W, H, "Seatbelt: vibe code like a pro, without being one. A free skill that makes your AI build, fix and launch apps safely, in plain English.")
    dark = mode == "dark"
    if dark:
        grad(d, "bg", "#090d1f", "#14123d", 1, 1)
        bgline = "#ffffff"
    else:
        grad(d, "bg", "#f7f8ff", "#eef1fb", 1, 1)
        bgline = "#4f46e5"
    d.adddef('<clipPath id="clip"><rect width="1200" height="560" rx="28"/></clipPath>')
    d.adddef(f'<radialGradient id="glow1" cx="0.8" cy="0.25" r="0.55"><stop offset="0" stop-color="{"#5b5cf6" if dark else "#a5b4fc"}" stop-opacity="{0.55 if dark else 0.55}"/><stop offset="1" stop-color="#5b5cf6" stop-opacity="0"/></radialGradient>')
    d.adddef(f'<radialGradient id="glow2" cx="0.05" cy="1" r="0.6"><stop offset="0" stop-color="{"#f43f5e" if dark else "#fda4af"}" stop-opacity="{0.28 if dark else 0.35}"/><stop offset="1" stop-color="#f43f5e" stop-opacity="0"/></radialGradient>')
    d.adddef(f'<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="{bgline}" stroke-opacity="{0.05 if dark else 0.06}"/></pattern>')
    grad(d, "strap", "#ffb547", "#ff5f6d", 1, 1)
    grad(d, "word", "#ffffff" if dark else "#0b1220", "#c7cbff" if dark else "#4338ca")
    d.add('<g clip-path="url(#clip)">')
    d.add('<rect width="1200" height="560" fill="url(#bg)"/><rect width="1200" height="560" fill="url(#grid)"/>')
    d.add('<rect width="1200" height="560" fill="url(#glow1)"/><rect width="1200" height="560" fill="url(#glow2)"/>')
    # diagonal seatbelt strap behind the product card
    d.add('<path d="M760 -40 L900 -40 L1260 470 L1260 620 L1180 620 Z" fill="url(#strap)" opacity="0.95"/>')
    d.add('<path d="M782 -40 L1240 610" stroke="#fff" stroke-opacity="0.35" stroke-width="2" stroke-dasharray="9 8"/>')
    d.add('<path d="M880 -40 L1262 500" stroke="#fff" stroke-opacity="0.35" stroke-width="2" stroke-dasharray="9 8"/>')
    d.add('</g>')
    d.add(f'<rect x="0.5" y="0.5" width="1199" height="559" rx="28" fill="none" stroke="{"#ffffff" if dark else "#4f46e5"}" stroke-opacity="{0.08 if dark else 0.12}"/>')

    ink = "#ffffff" if dark else t["ink"]
    ink2 = "#b9c2e0" if dark else t["ink2"]
    # pill
    px, py = 64, 70
    label = "Agent skill  ·  v3.1.0  ·  Free and open source"
    w = d.measure(label, 16, 600) + 42
    d.add(f'<rect x="{px}" y="{py}" width="{w:.0f}" height="34" rx="17" fill="{"#ffffff" if dark else "#4f46e5"}" fill-opacity="{0.08 if dark else 0.08}" stroke="{"#ffffff" if dark else "#4f46e5"}" stroke-opacity="{0.18 if dark else 0.25}"/>')
    d.add(f'<circle cx="{px+20}" cy="{py+17}" r="4" fill="{"#4ade80" if dark else "#16a34a"}"/>')
    d.text(px + 32, py + 23, label, 16, ink2 if dark else t["brand"], 600)
    # wordmark
    d.text(60, 214, "Seatbelt", 112, "url(#word)", 800, track=-0.035)
    d.text(64, 278, "Vibe code like a pro.", 40, ink, 650, track=-0.015)
    d.text(64, 326, "Without being one.", 40, "#ff7a85" if dark else "#e11d48", 650, track=-0.015)
    d.para(64, 376, "A free skill that makes your AI build, fix and launch apps the careful way, and explain it all in plain English.", 21, ink2, 580, 1.5)
    # chips
    cx = 64
    for lab, ic in [("Plain English", "chat"), ("Save points", "save"), ("Keys kept safe", "key"), ("Ship check", "shield")]:
        tw = d.measure(lab, 17, 600)
        cw = tw + 56
        d.add(f'<rect x="{cx}" y="446" width="{cw:.0f}" height="44" rx="22" fill="{"#ffffff" if dark else "#ffffff"}" fill-opacity="{0.07 if dark else 0.9}" stroke="{"#ffffff" if dark else "#c7d2fe"}" stroke-opacity="{0.16 if dark else 1}"/>')
        icon(d, ic, cx + 15, 458, 20, "#a5b4fc" if dark else t["brand"], 2)
        d.text(cx + 42, 474, lab, 17, ink, 600)
        cx += cw + 10

    # product card (illustration of a ship check result)
    X, Y, CW, CH = 708, 78, 432, 362
    d.adddef('<filter id="hs" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="18" stdDeviation="22" flood-color="#0b1026" flood-opacity="0.35"/></filter>')
    cf = "#0f1424" if dark else "#ffffff"
    cl = "#2a3350" if dark else "#e2e6f0"
    d.add(f'<rect x="{X}" y="{Y}" width="{CW}" height="{CH}" rx="20" fill="{cf}" stroke="{cl}" filter="url(#hs)"/>')
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        d.add(f'<circle cx="{X+26+i*18}" cy="{Y+26}" r="5.5" fill="{c}"/>')
    d.text(X + CW - 24, Y + 31, "ship check", 14, t["mute"], 500, mono=True, anchor="end")
    d.add(f'<path d="M{X} {Y+52}H{X+CW}" stroke="{cl}"/>')
    d.text(X + 24, Y + 92, "Ready to launch?", 24, ink if dark else t["ink"], 700, track=-0.01)
    d.text(X + 24, Y + 120, "Fix 1 thing first. Here is how.", 16, t["mute"], 500)
    rows = [
        ("ok", "No secret keys in browser code"),
        ("ok", "Database rules on every table"),
        ("warn", "Payment page unlocks Pro by itself"),
        ("ok", "Spending caps listed for 3 services"),
    ]
    ry = Y + 140
    for kind, txt in rows:
        if kind == "ok":
            col, soft = ("#4ade80", "#12301f") if dark else ("#15803d", "#e7f6ec")
        else:
            col, soft = ("#fbbf24", "#33270c") if dark else ("#b45309", "#fdf0d8")
        d.add(f'<rect x="{X+16}" y="{ry}" width="{CW-32}" height="42" rx="10" fill="{soft if kind=="warn" else ("#151b2e" if dark else "#f6f8fb")}"/>')
        d.add(f'<circle cx="{X+40}" cy="{ry+21}" r="11" fill="{soft}" stroke="{col}" stroke-width="1.5"/>')
        if kind == "ok":
            d.add(f'<path d="M{X+35} {ry+20.5} l3.5 3.5 6.5-7" fill="none" stroke="{col}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>')
        else:
            d.add(f'<path d="M{X+40} {ry+14}v7" stroke="{col}" stroke-width="2.4" stroke-linecap="round"/><circle cx="{X+40}" cy="{ry+25.5}" r="1.5" fill="{col}"/>')
        d.text(X + 62, ry + 26.5, txt, 16.5, ink if dark else t["ink"], 500)
        ry += 50
    d.text(X + CW - 24, Y + CH - 18, "Illustration", 13, t["mute"], 500, anchor="end", opacity=0.8)
    return d


# =====================================================================
SPECS = [
    ("100", "automated tests", "Scripts, database rules, payments and the skill text"),
    ("19/19", "planted problems caught", "Across 4 sample apps built the AI way"),
    ("0", "false alarms", "On the safe twin of every sample app"),
    ("86%", "on fresh test questions", "vs 80% for v3.0, on a small open model"),
    ("8", "places it works", "Claude, Claude Code, Codex, Cursor, Lovable, Bolt, Replit, v0"),
    ("3", "built-in checkers", "Ship check, live check and change explainer"),
    ("0", "installs or sign-ups", "Plain Python 3. Nothing is sent anywhere"),
    ("£0", "free forever", "MIT licence. Use it, share it, change it"),
]


def specs(mode):
    t = THEMES[mode]
    W, H = 1200, 500
    d = Doc(W, H, "Seatbelt at a glance: 100 automated tests; 19 of 19 planted problems caught with 0 false alarms; 86% on fresh test questions vs 80% for v3.0, with a small open model; works in 8 places; 3 built-in checkers; nothing to install; free, MIT licence.")
    card(d, t, 10, 10, W - 20, H - 30, 24)
    eyebrow(d, t, 50, 62, "At a glance")
    d.text(W - 50, 62, "Seatbelt 3.1", 17, t["mute"], 600, anchor="end", track=0.04)
    d.add(f'<path d="M10 86H{W-10}" stroke="{t["line2"]}"/>')
    cols, cw = 4, (W - 20) / 4
    for i, (big, lab, sub) in enumerate(SPECS):
        r, c = divmod(i, cols)
        x0 = 10 + c * cw
        y0 = 86 + r * 192
        if c:
            d.add(f'<path d="M{x0} {y0+28}V{y0+166}" stroke="{t["line2"]}"/>')
        if r and c == 0:
            d.add(f'<path d="M40 {y0}H{W-40}" stroke="{t["line2"]}"/>')
        gid = f"sg{i}"
        grad(d, gid, t["brand"], t["brand2"])
        d.text(x0 + 36, y0 + 82, big, 56, f"url(#{gid})" if i not in (7,) else t["ink"], 750, track=-0.03)
        d.text(x0 + 36, y0 + 116, lab, 20, t["ink"], 650)
        d.para(x0 + 36, y0 + 144, sub, 17, t["mute"], cw - 60, 1.4)
    return d


# =====================================================================
FEATURES = [
    ("chat", "Plain-English plans", "A few easy questions, then a one-screen plan you approve.", "#6366f1"),
    ("save", "Save points", "Saves before every change, so you can always go back.", "#0ea5e9"),
    ("key", "Keys kept safe", "Never in browser code or on GitHub, and spending capped.", "#f59e0b"),
    ("stop", "Fix-loop breaker", "Two failed fixes and it stops, goes back and tries another way.", "#ef4444"),
    ("shield", "Ship check", "Scans your code for leaked keys, open tables and fake payments.", "#22c55e"),
    ("globe", "Live check", "Looks at your live site the way a stranger would. Read-only.", "#14b8a6"),
    ("diff", "Change explainer", "What changed, what is risky, and packages the AI made up.", "#a855f7"),
    ("gauge", "Cost guard", "Finds AI calls with no limits and shows where to cap spending.", "#f43f5e"),
]


def features(mode):
    t = THEMES[mode]
    W, H = 1200, 584
    d = Doc(W, H, "Features: plain-English plans, save points, keys kept safe, fix-loop breaker, ship check, live check, change explainer, cost guard.")
    cols, gap = 4, 20
    cw = (W - 20 - gap * (cols - 1)) / cols
    ch = 262
    for i, (ic, title, desc, col) in enumerate(FEATURES):
        r, c = divmod(i, cols)
        x = 10 + c * (cw + gap)
        y = 10 + r * (ch + gap)
        card(d, t, x, y, cw, ch, 20)
        op = 0.12 if mode == "light" else 0.2
        d.add(f'<rect x="{x+26}" y="{y+28}" width="56" height="56" rx="16" fill="{col}" fill-opacity="{op}"/>')
        icon(d, ic, x + 40, y + 42, 28, col, 2)
        d.text(x + 26, y + 128, title, 24, t["ink"], 700, track=-0.01)
        nl = d.para(x + 26, y + 164, desc, 18.5, t["ink2"], cw - 50, 1.42)
        assert nl <= 3, title
    return d


# =====================================================================
FLOW = [
    ("chat", "Ask", "You say what you want in your own words."),
    ("pin", "Plan", "A few questions, then a plan you approve."),
    ("save", "Build", "One small change, then a save point."),
    ("diff", "Explain", "What changed, in plain English. Risks flagged."),
    ("rocket", "Launch", "Ship check on the code, then a live check."),
]


def flow(mode):
    t = THEMES[mode]
    W, H = 1040, 456
    d = Doc(W, H, "How it works: Ask, Plan, Build with a save point, Explain the changes, then Launch after the ship check and live check. If a fix fails twice, it goes back to the last save point and tries another way.")
    n = len(FLOW)
    gap = 18
    cw = (W - 20 - gap * (n - 1)) / n
    y = 70
    ch = 236
    grad(d, "track", t["brand"], t["coral"])
    # track
    d.add(f'<path d="M{10+cw/2} 40H{W-10-cw/2}" stroke="url(#track)" stroke-width="3" stroke-linecap="round"/>')
    for i, (ic, title, desc) in enumerate(FLOW):
        x = 10 + i * (cw + gap)
        cxm = x + cw / 2
        d.add(f'<circle cx="{cxm}" cy="40" r="17" fill="{t["card"]}" stroke="{t["brand"] if i < 4 else t["coral"]}" stroke-width="3"/>')
        d.text(cxm, 46.5, str(i + 1), 17, t["brand"] if i < 4 else t["coral"], 750, anchor="middle")
        card(d, t, x, y, cw, ch, 20)
        col = t["brand"] if i < 4 else t["coral"]
        d.add(f'<rect x="{x+24}" y="{y+26}" width="52" height="52" rx="15" fill="{col}" fill-opacity="{0.12 if mode=="light" else 0.2}"/>')
        icon(d, ic, x + 37, y + 39, 26, col, 2)
        d.text(x + 24, y + 120, title, 25, t["ink"], 700, track=-0.01)
        nl = d.para(x + 24, y + 154, desc, 18.5, t["ink2"], cw - 42, 1.42)
        assert nl <= 3, title
    # loop back from Explain to Build
    xb = 10 + 2 * (cw + gap) + cw / 2
    xe = 10 + 3 * (cw + gap) + cw / 2
    yb = y + ch
    col = t["amber"]
    d.add(f'<path d="M{xe} {yb+4} V{yb+46} Q{xe} {yb+66} {xe-20} {yb+66} H{xb+20} Q{xb} {yb+66} {xb} {yb+46} V{yb+14}" fill="none" stroke="{col}" stroke-width="2.5" stroke-dasharray="7 6" stroke-linecap="round"/>')
    d.add(f'<path d="M{xb-8} {yb+20} L{xb} {yb+8} L{xb+8} {yb+20}" fill="none" stroke="{col}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>')
    lab = "Broke twice? Back to the last save point, then try another way."
    tw = d.measure(lab, 17, 600)
    bx = (xb + xe) / 2 - (tw + 44) / 2
    d.add(f'<rect x="{bx:.0f}" y="{yb+90}" width="{tw+44:.0f}" height="44" rx="22" fill="{t["ambersoft"]}" stroke="{col}" stroke-opacity="0.5"/>')
    icon(d, "save", bx + 14, yb + 102, 20, col, 2)
    d.text(bx + 40, yb + 118, lab, 17, t["ink"], 600)
    return d


# =====================================================================
RISK = [
    ("Green", "green", "No logins, no personal data, no money", "A menu, portfolio, event page or calculator", ["One or two questions, then build", "Still no secret keys in the page"]),
    ("Amber", "amber", "Logins, personal data, or a paid AI or API", "A habit tracker, a booking form, an AI chat app", ["Questions and a plan you approve", "Database rules and spending caps", "Ship check before launch"]),
    ("Red", "red", "Takes money, sensitive data or many users", "A shop, a health or finance app, a business's customers", ["Everything in Amber", "Only trusts verified payments", "A developer review before launch"]),
]


def risk(mode):
    t = THEMES[mode]
    W, H = 1200, 476
    d = Doc(W, H, "Care matched to risk. Green: no logins, data or money; one or two questions, then build. Amber: logins, personal data or a paid AI; questions, a plan, database rules, spending caps and a ship check. Red: money, sensitive data or many users; everything in Amber plus verified payments and a developer review.")
    gap = 20
    cw = (W - 20 - 2 * gap) / 3
    ch = H - 30
    for i, (name, key, when, eg, does) in enumerate(RISK):
        x = 10 + i * (cw + gap)
        y = 10
        col, soft = t[key], t[key + "soft"]
        card(d, t, x, y, cw, ch, 22)
        d.adddef(f'<clipPath id="rc{i}"><rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="22"/></clipPath>')
        d.add(f'<rect x="{x}" y="{y}" width="{cw}" height="112" fill="{soft}" clip-path="url(#rc{i})"/>')
        d.add(f'<rect x="{x}" y="{y}" width="{cw}" height="6" fill="{col}" clip-path="url(#rc{i})"/>')
        # signal dots
        for j in range(3):
            on = j <= i
            d.add(f'<circle cx="{x+cw-40-(2-j)*22}" cy="{y+50}" r="7" fill="{col if on else "none"}" stroke="{col}" stroke-width="2" opacity="{1 if on else 0.45}"/>')
        d.text(x + 28, y + 60, name, 30, col, 750, track=-0.01)
        d.text(x + 28, y + 92, "WHEN THE APP HAS", 14, t["mute"], 600, track=0.02)
        n = d.para(x + 28, y + 152, when, 21, t["ink"], cw - 56, 1.32, 650)
        yy = y + 152 + n * 21 * 1.32 + 2
        n2 = d.para(x + 28, yy, "For example: " + eg, 17, t["mute"], cw - 56, 1.4)
        yy = y + 152 + 2 * 21 * 1.32 + 2 + 2 * 17 * 1.4 + 22
        d.add(f'<path d="M{x+28} {yy-6}H{x+cw-28}" stroke="{t["line2"]}"/>')
        d.text(x + 28, yy + 20, "SEATBELT DOES", 14, t["mute"], 700, track=0.1)
        yy += 50
        for item in does:
            d.add(f'<circle cx="{x+39}" cy="{yy-5}" r="10" fill="{soft}"/>')
            d.add(f'<path d="M{x+34.5} {yy-5} l3 3 5.5-6" fill="none" stroke="{col}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
            assert d.measure(item, 17.5, 500) < cw - 80, item
            d.text(x + 60, yy, item, 17.5, t["ink2"], 500)
            yy += 36
    return d


# =====================================================================
CATCH = [
    ("key", "Leaked keys", "#f59e0b", ["OpenAI, Gemini, Stripe, AWS keys", "Secrets behind NEXT_PUBLIC_", ".env files that could leak"]),
    ("lock", "Open data", "#6366f1", ["Tables with no Row Level Security", "Rules that let everyone in", "Users who can edit their own plan"]),
    ("card", "Fake payments", "#22c55e", ["Webhooks with no signature check", "Prices taken from the browser", "Thank-you pages that unlock Pro"]),
    ("coins", "Runaway costs", "#f43f5e", ["AI calls with no per-person limit", "AI calls inside loops", "Jobs that run every minute"]),
    ("diff", "Risky changes", "#a855f7", ["Database rules switched off", "Tables dropped or wiped", "Packages the AI made up"]),
    ("globe", "Live site leaks", "#14b8a6", ["Keys in your page's JavaScript", "Exposed .env, .git or source maps", "Tables a stranger can read"]),
]


def catches(mode):
    t = THEMES[mode]
    W, H = 1200, 600
    d = Doc(W, H, "What it catches: leaked keys, open data, fake payments, runaway costs, risky changes and live site leaks.")
    cols, gap = 3, 20
    cw = (W - 20 - gap * 2) / cols
    ch = 270
    for i, (ic, title, col, items) in enumerate(CATCH):
        r, c = divmod(i, cols)
        x = 10 + c * (cw + gap)
        y = 10 + r * (ch + gap)
        card(d, t, x, y, cw, ch, 20)
        d.add(f'<rect x="{x+26}" y="{y+26}" width="48" height="48" rx="14" fill="{col}" fill-opacity="{0.12 if mode=="light" else 0.2}"/>')
        icon(d, ic, x + 38, y + 38, 24, col, 2)
        d.text(x + 90, y + 58, title, 24, t["ink"], 700, track=-0.01)
        yy = y + 118
        for it in items:
            d.add(f'<rect x="{x+22}" y="{yy-26}" width="{cw-44}" height="40" rx="10" fill="{t["card2"]}" stroke="{t["line2"]}"/>')
            d.add(f'<circle cx="{x+40}" cy="{yy-6}" r="4" fill="{col}"/>')
            mono = any(k in it for k in ("NEXT_PUBLIC_", ".env"))
            assert d.measure(it, 17, 500) < cw - 72, (it, d.measure(it, 17, 500), cw - 72)
            d.text(x + 54, yy, it, 17, t["ink2"], 500)
            yy += 48
    return d


# =====================================================================
COMPARE = [
    ("Explains every technical word", "If you ask", "Always"),
    ("Questions and a plan before building", "If you ask", "Matched to risk"),
    ("Save point before each change", "If you ask", "Always"),
    ("Stops after two failed fixes", "If you ask", "Always"),
    ("Scans the code before launch", "Not included", "Built in"),
    ("Checks the live site like a stranger", "Not included", "Built in, read-only"),
    ("Spots packages the AI made up", "Not included", "Built in"),
    ("Says when to get a developer", "If you ask", "For Red apps"),
]


def compare(mode):
    t = THEMES[mode]
    W = 1200
    rh = 60
    top = 112
    H = top + rh * len(COMPARE) + 40
    d = Doc(W, H, "Your AI on its own versus with Seatbelt: plain-English explanations, a plan first, save points, a fix-loop breaker, a code scan, a live check, a made-up package check and honest advice on when to get a developer are built in with Seatbelt; on its own the AI does these only if you ask, or not at all.")
    card(d, t, 10, 10, W - 20, H - 30, 24)
    c1, c2, c3 = 50, 640, 900
    # seatbelt column highlight
    d.add(f'<rect x="{c3-30}" y="26" width="{W-10-16-(c3-30)}" height="{H-62}" rx="16" fill="{t["brandsoft"]}"/>')
    d.text(c1, 74, "WHAT YOU GET", 15, t["mute"], 700, track=0.08)
    d.text(c2, 74, "YOUR AI ON ITS OWN", 15, t["mute"], 700, track=0.08)
    grad(d, "cg", t["brand"], t["brand2"])
    d.text(c3, 74, "WITH SEATBELT", 15, t["brand"], 750, track=0.08)
    d.add(f'<path d="M40 {top-12}H{W-40}" stroke="{t["line"]}"/>')
    for i, (feat, alone, sb) in enumerate(COMPARE):
        y = top + i * rh + 37
        d.text(c1, y, feat, 20, t["ink"], 600)
        # alone
        if alone == "Not included":
            d.add(f'<path d="M{c2} {y-6}h12" stroke="{t["mute"]}" stroke-width="2.2" stroke-linecap="round"/>')
        else:
            d.add(f'<circle cx="{c2+6}" cy="{y-6}" r="6" fill="none" stroke="{t["mute"]}" stroke-width="2"/>')
        d.text(c2 + 24, y, alone, 18.5, t["mute"], 500)
        d.add(f'<circle cx="{c3+10}" cy="{y-6}" r="11" fill="{t["brand"]}"/>')
        d.add(f'<path d="M{c3+5} {y-6} l3.5 3.5 6-6.5" fill="none" stroke="#fff" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/>')
        d.text(c3 + 32, y, sb, 18.5, t["ink"], 650)
        if i < len(COMPARE) - 1:
            d.add(f'<path d="M40 {top+(i+1)*rh}H{c3-40}" stroke="{t["line2"]}"/>')
    return d


# =====================================================================
STATS = [
    ("5,000+", "vibe-coded apps found with virtually no security", "WIRED, May 2026"),
    ("1 in 5", "of about 130,000 sites exposed a secret key", "RedHunt Labs"),
    ("$55,444.78", "cloud bill after one leaked Gemini key (later waived)", "Reddit, r/googlecloud"),
]


def stats(mode):
    t = THEMES[mode]
    W, H = 1200, 270
    d = Doc(W, H, "Why it matters: more than 5,000 vibe-coded apps found with virtually no security (WIRED, May 2026); 1 in 5 of about 130,000 sites exposed a secret key (RedHunt Labs); a $55,444.78 cloud bill after one leaked Gemini key, later waived (Reddit).")
    gap = 20
    cw = (W - 20 - 2 * gap) / 3
    for i, (big, lab, src) in enumerate(STATS):
        x = 10 + i * (cw + gap)
        card(d, t, x, 10, cw, H - 30, 20)
        d.text(x + 30, 92, big, 46, t["coral"] if mode == "light" else t["coral"], 750, track=-0.03)
        d.para(x + 30, 134, lab, 19, t["ink"], cw - 60, 1.4, 600)
        d.text(x + 30, H - 48, src, 16, t["mute"], 500)
    return d


# =====================================================================
def footer(mode):
    t = THEMES[mode]
    W, H = 1200, 220
    d = Doc(W, H, "Seatbelt. Free and open source under the MIT licence. Made by Mohammed Hyder. A safety net, not a full security audit.")
    grad(d, "fb", "#0b1026", "#1a1554", 1, 1)
    grad(d, "strap", "#ffb547", "#ff5f6d", 1, 1)
    d.adddef('<clipPath id="fc"><rect width="1200" height="220" rx="24"/></clipPath>')
    d.add('<g clip-path="url(#fc)"><rect width="1200" height="220" fill="url(#fb)"/>')
    d.add('<path d="M1000 -20 L1090 -20 L1240 240 L1150 240 Z" fill="url(#strap)" opacity="0.95"/></g>')
    d.add('<g transform="translate(60 66)"><path d="M30 0 L60 10.5 L60 34.5 C60 54 46.5 67.5 30 75 C13.5 67.5 0 54 0 34.5 L0 10.5 Z" fill="#fff" fill-opacity="0.08" stroke="#8fb0ff" stroke-width="2.5"/><path d="M17 37.5 L27 47.5 L45 27" fill="none" stroke="#7CFFB2" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></g>')
    d.text(146, 112, "Seatbelt", 44, "#ffffff", 800, track=-0.03)
    d.text(148, 146, "Free and open source. MIT licence. Made by Mohammed Hyder.", 19, "#b9c2e0", 500)
    d.text(148, 176, "A safety net, not a full security audit.", 17, "#8a94b8", 500)
    return d


BADGES = [
    ("claude-code", "CLAUDE CODE", "term", "#d9774b", "#b8532a"),
    ("agents", "CODEX  ·  CURSOR  ·  AGENTS", "term", "#4f46e5", "#7c3aed"),
    ("claude-ai", "CLAUDE.AI", "chat", "#c26a43", "#9a4a28"),
    ("builders", "LOVABLE  ·  BOLT  ·  REPLIT  ·  V0", "box", "#db2777", "#e11d48"),
    ("cursor-rule", "CURSOR RULE", "file", "#64748b", "#334155"),
    ("anything", "ANYTHING ELSE", "file", "#0f766e", "#0e7490"),
]


def badge(slug, label, ic, c1, c2):
    tw = Doc(10, 10, "").measure(label, 14, 700, track=0.08)
    W, H = int(tw + 62), 34
    d = Doc(W, H, label.title())
    grad(d, "bg", c1, c2)
    d.add(f'<rect width="{W}" height="{H}" rx="17" fill="url(#bg)"/>')
    icon(d, ic, 14, 8, 18, "#ffffff", 2)
    d.text(42, 22, label, 14, "#ffffff", 700, track=0.08)
    return d


ALL = dict(hero=hero, specs=specs, features=features, flow=flow, risk=risk, catches=catches, compare=compare, stats=stats, footer=footer)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, fn in ALL.items():
        for mode in ("light", "dark"):
            if name == "footer" and mode == "dark":
                continue
            svg = fn(mode).render()
            p = os.path.join(OUT, f"{name}-{mode}.svg" if name != "footer" else "footer.svg")
            open(p, "w").write(svg)
            print(f"{p}  {len(svg)//1024} KB")
    for b in BADGES:
        open(os.path.join(OUT, f"badge-{b[0]}.svg"), "w").write(badge(*b).render())
