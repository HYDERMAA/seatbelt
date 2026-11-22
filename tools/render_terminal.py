#!/usr/bin/env python3
"""Turn real Seatbelt output into a terminal-style PNG for the README (maintainers only).

    python3 tools/render_terminal.py output.txt assets/scan.png --command "python3 check_secrets.py ." [--max-lines 40]

Needs Google Chrome or Chromium for the screenshot. The text is the tool's real output; only
long runs are trimmed, and a visible line says how many lines were left out.
"""
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile

COLOURS = [
    (r"^== MUST FIX", "#ff6b6b"), (r"^== FIX BEFORE", "#ffa94d"), (r"^== WORTH", "#ffd43b"),
    (r"^== TIP", "#74c0fc"), (r"^== PAID", "#63e6be"), (r"^== DATABASE", "#b197fc"), (r"^== NOTES", "#adb5bd"),
    (r"^NOT READY", "#ff6b6b"), (r"^No serious|^PASSED", "#69db7c"), (r"risk: HIGH", "#ff6b6b"),
    (r"^- \[STOP AND CHECK\]", "#ff8787"), (r"^- \[CHECK\]", "#ffd43b"), (r"^Suggested save point", "#69db7c"),
    (r"OPEN,", "#ff8787"), (r"refused \(good\)", "#69db7c"), (r"^Seatbelt|^What changed", "#ffffff"),
    (r"^\s+What:", "#e9ecef"), (r"^\s+Fix:", "#8ce99a"), (r"^\s+Why it matters:", "#adb5bd"),
]


def colour(line):
    for rx, c in COLOURS:
        if re.search(rx, line):
            return c
    return "#ced4da"


def main(argv):
    src, out = argv[0], argv[1]
    command = argv[argv.index("--command") + 1] if "--command" in argv else ""
    max_lines = int(argv[argv.index("--max-lines") + 1]) if "--max-lines" in argv else 999
    width = int(argv[argv.index("--width") + 1]) if "--width" in argv else 920
    with open(src, encoding="utf-8") as fh:
        lines = fh.read().rstrip("\n").splitlines()
    if len(lines) > max_lines:
        cut = len(lines) - max_lines
        keep_tail = int(argv[argv.index("--tail") + 1]) if "--tail" in argv else 6
        lines = lines[:max_lines - keep_tail] + [f"   ... {cut} more lines (trimmed for this picture) ..."] + lines[-keep_tail:]
    body = []
    if command:
        body.append(f'<div><span style="color:#69db7c">you@laptop</span> <span style="color:#74c0fc">my-app</span> $ '
                    f'<span style="color:#fff">{html.escape(command)}</span></div>')
    for line in lines:
        style = "color:#868e96;font-style:italic" if "trimmed for this picture" in line else f"color:{colour(line)}"
        weight = ";font-weight:700" if line.startswith(("==", "NOT READY", "Seatbelt", "What changed")) else ""
        body.append(f'<div style="{style}{weight}">{html.escape(line) or "&nbsp;"}</div>')
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:transparent}}
.win{{width:{width}px;margin:24px;border-radius:12px;overflow:hidden;background:#11131a;
border:1px solid #2b2f3a}}
.bar{{height:36px;background:#1c1f29;display:flex;align-items:center;padding:0 14px;gap:8px}}
.dot{{width:12px;height:12px;border-radius:50%}}
.title{{color:#8b92a5;font:13px -apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin-left:12px}}
.term{{padding:16px 20px 20px;font:13px/1.55 'DejaVu Sans Mono',Menlo,Consolas,monospace;white-space:pre-wrap;word-break:break-word}}
</style></head><body><div class="win" id="win"><div class="bar"><span class="dot" style="background:#ff5f57"></span>
<span class="dot" style="background:#febc2e"></span><span class="dot" style="background:#28c840"></span>
<span class="title">Terminal</span></div><div class="term">{''.join(body)}</div></div></body></html>"""
    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    if not chrome:
        sys.exit("Chrome or Chromium is needed for the screenshot.")
    with tempfile.TemporaryDirectory() as tmp:
        page_path = os.path.join(tmp, "t.html")
        with open(page_path, "w", encoding="utf-8") as fh:
            fh.write(page)
        # first pass: tall screenshot, then crop to the window
        raw = os.path.join(tmp, "raw.png")
        height = 120 + 21 * (len(body) + 2) + 400
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        "--default-background-color=00000000", "--force-device-scale-factor=2",
                        f"--window-size={width + 48},{height}", f"--screenshot={raw}", "file://" + page_path],
                       check=True, capture_output=True, timeout=120)
        from PIL import Image
        im = Image.open(raw)
        bbox = im.getchannel("A").getbbox()
        if bbox:
            pad = 2
            im = im.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(im.width, bbox[2] + pad), min(im.height, bbox[3] + pad)))
        w, h = im.size
        im = im.resize((int(w * 0.75), int(h * 0.75)), Image.LANCZOS)
        im.quantize(colors=256, method=Image.Quantize.FASTOCTREE).save(out, optimize=True)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main(sys.argv[1:])
