#!/usr/bin/env python3
"""Terminal-style GitHub profile card -> assets/terminal-dark.svg + assets/terminal-light.svg

    omar@github ~ $ ./contributions.sh    contribution heatmap
    omar@github ~ $ whoami                 rotating tech logos + activity stats

Data:  GraphQL API when GH_TOKEN is set (the Actions GITHUB_TOKEN is enough),
       otherwise your public contributions page.
Logos: official icons from Devicon (https://devicon.dev), downloaded at build time.
       A file at assets/logos/<name>.svg is used instead, for anything Devicon lacks.

Local run (standard library only):
    GH_USER=omarhatem44 python scripts/generate_terminal.py
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import json
import os
import re
import urllib.request

# ── edit me ─────────────────────────────────────────────────────────────────
USER = os.getenv("GH_USER", "omarhatem44")
TOKEN = os.getenv("GH_TOKEN", "")
PROMPT = "omar@github"                      # shown as:  omar@github ~ $
LOGOS = [                                   # (Devicon name, label, variant, variant on dark)
    ("python", "Python", "original", None),
    ("amazonwebservices", "AWS", "original-wordmark", "plain-wordmark"),
    ("docker", "Docker", "original", None),
    ("pytorch", "PyTorch", "original", None),
    ("kubernetes", "Kubernetes", "original", None),
    ("tensorflow", "TensorFlow", "original", None),
    ("fastapi", "FastAPI", "original", None),
    ("apacheairflow", "Airflow", "original", None),
]
LOGO_SECONDS = 1                          # how long each logo stays on screen
OUT_DIR = "assets"
# ────────────────────────────────────────────────────────────────────────────

THEMES = {
    "dark": {
        "bg": "#0d1117", "bar": "#151b23", "line": "#3d444d", "text": "#f0f6fc",
        "muted": "#9198a1", "faint": "#656c76", "green": "#3fb950", "blue": "#4493f8",
        "heat": ["#151b23", "#033a16", "#196c2e", "#2ea043", "#56d364"],
    },
    "light": {
        "bg": "#ffffff", "bar": "#f6f8fa", "line": "#d1d9e0", "text": "#1f2328",
        "muted": "#59636e", "faint": "#818b98", "green": "#1a7f37", "blue": "#0969da",
        "heat": ["#eff2f5", "#aceebb", "#4ac26b", "#2da44e", "#116329"],
    },
}

W, H, PAD = 880, 670, 15
MONO = ('ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,'
        '"Liberation Mono","DejaVu Sans Mono",monospace')
EM = 0.6                                    # monospace advance / font size
CELL, GAP = 12, 3                           # heatmap squares
PANEL_Y, PANEL_H, PANEL_W = 278, 370, 408
LOGO_SIZE = 176                             # logo box (px)
DEVICON = "https://raw.githubusercontent.com/devicons/devicon/v2.17.0/icons"
TYPE_S = 0.045                              # seconds per typed character
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
LEVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
         "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


# ── data ────────────────────────────────────────────────────────────────────
def get(url, data=None, headers=None):
    req = urllib.request.Request(
        url, data=data, headers={"User-Agent": "profile-terminal", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}"""


def from_graphql():
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    res = json.loads(get("https://api.github.com/graphql", body, {
        "Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"}))
    user = (res.get("data") or {}).get("user")
    if res.get("errors") or not user:
        raise RuntimeError(res.get("errors") or f"user {USER} not found")
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [(d["date"], d["contributionCount"], LEVEL[d["contributionLevel"]])
            for w in cal["weeks"] for d in w["contributionDays"]]
    return days, cal["totalContributions"]


def calendar_from_html(page):
    """Parse github.com/users/<user>/contributions -> (days, total)."""
    tips = dict(re.findall(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', page))
    days = []
    for td in re.findall(r"<td[^>]*\bdata-date=[^>]*>", page):
        attr = dict(re.findall(r'([\w-]+)="([^"]*)"', td))
        n = re.match(r"\s*([\d,]+)", tips.get(attr.get("id", ""), ""))
        days.append((attr["data-date"], int(n[1].replace(",", "")) if n else 0,
                     int(attr.get("data-level", 0))))
    days.sort()
    m = re.search(r"([\d,]+)\s+contributions?\s+in the last year", page)
    return days, int(m[1].replace(",", "")) if m else sum(d[1] for d in days)


def from_public():
    return calendar_from_html(get(f"https://github.com/users/{USER}/contributions").decode())


# ── stats ───────────────────────────────────────────────────────────────────
def day(s, year=False):
    d = dt.date.fromisoformat(s)
    return f"{MONTHS[d.month - 1]} {d.day}" + (f", {d.year}" if year else "")


def span(a, b):
    if a == b:
        return day(a)
    if a[:7] == b[:7]:
        return f"{day(a)} – {int(b[8:])}"
    return f"{day(a)} – {day(b)}"


def stats(days, total):
    best, best_span, start = 0, None, None
    for i, (d, n, _) in enumerate(days):
        if not n:
            start = None
            continue
        start = i if start is None else start
        if i - start + 1 > best:
            best, best_span = i - start + 1, (days[start][0], d)
    end = len(days) - 1
    if end >= 0 and days[end][1] == 0:       # today isn't over yet
        end -= 1
    first = end
    while first >= 0 and days[first][1]:
        first -= 1
    current = end - first
    active = sum(1 for _, n, _ in days if n)
    top = max(days, key=lambda d: d[1], default=("", 0, 0))
    months = {}
    for d, n, _ in days:
        months[d[:7]] = months.get(d[:7], 0) + n
    unit = lambda n: "day" if n == 1 else "days"
    return {
        "items": [
            ("current streak", str(current), unit(current),
             span(days[first + 1][0], days[end][0]) if current else "no active streak"),
            ("longest streak", str(best), unit(best), span(*best_span) if best else "none yet"),
            ("total", f"{total:,}", "", "contributions"),
            ("active days", str(active), f"/ {len(days)}",
             f"{round(100 * active / max(len(days), 1))}% of days"),
            ("best day", str(top[1]), "", day(top[0], year=True) if top[1] else "none yet"),
            ("per active day", f"{total / max(active, 1):.1f}", "", "average"),
        ],
        "months": list(months.items())[-12:],
        "range": f"{day(days[0][0], True)} – {day(days[-1][0], True)}" if days else "",
    }


# ── logos ───────────────────────────────────────────────────────────────────
def logo_source(name, variant):
    local = os.path.join(OUT_DIR, "logos", f"{name}.svg")
    if os.path.exists(local):
        with open(local, encoding="utf-8") as f:
            return f.read()
    return get(f"{DEVICON}/{name}/{name}-{variant}.svg").decode("utf-8")


KEEP = {"fill", "fill-rule", "clip-rule", "stroke", "stroke-width", "stroke-linecap",
        "stroke-linejoin", "stroke-miterlimit", "style", "preserveAspectRatio"}


def embed(svg, x, y, size, uid):
    """Place an icon SVG in a size x size box, keeping its ids unique."""
    svg = re.sub(r"<\?xml.*?\?>|<!DOCTYPE[^>]*>|<!--.*?-->", "", svg, flags=re.S)
    root = re.search(r"<svg\b[^>]*>", svg)
    if root is None or "<style" in svg:          # isolate anything with its own CSS
        data = base64.b64encode(svg.encode()).decode()
        return (f'<image x="{x:g}" y="{y:g}" width="{size}" height="{size}" '
                f'href="data:image/svg+xml;base64,{data}"/>')
    attrs = dict(re.findall(r'([\w:-]+)="([^"]*)"', root.group(0)))
    view = attrs.get("viewBox") or f'0 0 {attrs.get("width", "128").rstrip("px")} ' \
                                   f'{attrs.get("height", "128").rstrip("px")}'
    keep = "".join(f' {k}="{v}"' for k, v in attrs.items() if k in KEEP)
    inner = svg[root.end():svg.rfind("</svg>")]
    for i in set(re.findall(r'\bid="([^"]+)"', inner)):
        inner = re.sub(r'(\bid="|url\(#|href="#)' + re.escape(i) + r'(?=["\)])',
                       lambda m, i=i: f"{m.group(1)}{uid}-{i}", inner)
    return (f'<svg x="{x:g}" y="{y:g}" width="{size}" height="{size}" viewBox="{view}"'
            f'{keep}>{inner}</svg>')


def carousel(logos, cx, cy, t0):
    """One logo at a time, forever: rise in, hold, rise out; dots track the position."""
    n, T, fade, size = len(logos), LOGO_SECONDS, 0.45, LOGO_SIZE
    cycle = n * T
    a, b, c = (100 * v / cycle for v in (fade, T - fade, T))
    keyframes = "" if n < 2 else (
        f"@keyframes cyc{{0%{{opacity:0;transform:translateY(12px)}}"
        f"{a:.2f}%,{b:.2f}%{{opacity:1;transform:none}}"
        f"{c:.2f}%,100%{{opacity:0;transform:translateY(-12px)}}}}"
        f"@keyframes cyd{{0%{{opacity:0}}{a:.2f}%,{b:.2f}%{{opacity:1}}{c:.2f}%,100%{{opacity:0}}}}"
        f".lg{{animation:cyc {cycle:.2f}s ease-in-out infinite both}}"
        f".dn{{animation:cyd {cycle:.2f}s ease-in-out infinite both}}")
    out = []
    for i, (label, svg) in enumerate(logos):
        first = " lg0" if i == 0 else ""
        out.append(f'<g class="lg{first}" style="animation-delay:{t0 + i * T:.2f}s">'
                   f'{embed(svg, cx - size / 2, cy - size / 2, size, f"l{i}")}'
                   f'{txt(cx, cy + size / 2 + 38, label, "lgl", anchor="middle")}</g>')
    if n > 1:
        gap, dy = 14, cy + size / 2 + 64
        for i in range(n):
            x = cx - (n - 1) * gap / 2 + i * gap
            first = " dn0" if i == 0 else ""
            out.append(f'<circle cx="{x:g}" cy="{dy:g}" r="3" class="dt"/>'
                       f'<circle cx="{x:g}" cy="{dy:g}" r="3" class="dn{first}" '
                       f'style="animation-delay:{t0 + i * T:.2f}s"/>')
    return "".join(out), keyframes


# ── svg ─────────────────────────────────────────────────────────────────────
def esc(s):
    return html.escape(str(s), quote=False)


def txt(x, y, s, cls, delay=None, anchor=None):
    extra = f' style="animation-delay:{delay:.2f}s"' if delay is not None else ""
    extra += f' text-anchor="{anchor}"' if anchor else ""
    return f'<text x="{x:g}" y="{y:g}" class="{cls}"{extra}>{esc(s)}</text>'


def prompt(y, cmd, name, t_type, t_show=None):
    """Centered `omar@github ~ $ cmd`; a cover slides off the command to type it."""
    cw = 14 * EM
    x = (W - (len(PROMPT) + 5 + len(cmd)) * cw) / 2
    x_cmd, w, dur = x + (len(PROMPT) + 5) * cw, len(cmd) * cw, len(cmd) * TYPE_S
    out = [txt(x, y, PROMPT, "pu"), txt(x + (len(PROMPT) + 1) * cw, y, "~", "pp"),
           txt(x + (len(PROMPT) + 3) * cw, y, "$", "pd"), txt(x_cmd, y, cmd, "pc"),
           f'<g style="animation:{name} {dur:.2f}s steps({len(cmd)}) {t_type:.2f}s both">'
           f'<rect x="{x_cmd + w:.1f}" y="{y - 14}" width="{w + 16:.1f}" height="19" class="bgf"/>'
           f'<rect x="{x_cmd + w:.1f}" y="{y - 12}" width="{cw:.1f}" height="16" class="cur" '
           f'style="animation-delay:{t_type + dur + 0.25:.2f}s"/></g>']
    show = f' class="o" style="animation-delay:{t_show:.2f}s"' if t_show else ""
    keyframes = f"@keyframes {name}{{from{{transform:translateX(-{w:.1f}px)}}to{{transform:none}}}}"
    return f'<g{show}>{"".join(out)}</g>', keyframes


def heatmap(days, total, top, t0):
    p, gx = CELL + GAP, PAD + 30
    off = (dt.date.fromisoformat(days[0][0]).weekday() + 1) % 7      # Sunday-first rows
    weeks = {}
    for i, (d, _, lv) in enumerate(days):
        wk, row = divmod(i + off, 7)
        weeks.setdefault(wk, []).append((row, d, lv))
    out, last_month, last_label = [], None, -9
    for wk, col in sorted(weeks.items()):
        x, month = gx + wk * p, int(col[0][1][5:7])
        if month != last_month:
            if wk - last_label >= 3:
                out.append(txt(x, top - 8, MONTHS[month - 1], "lbl o", t0))
                last_label = wk
            last_month = month
        rects = "".join(f'<rect x="{x}" y="{top + row * p}" width="{CELL}" height="{CELL}" '
                        f'rx="2" class="h{lv}"/>' for row, _, lv in col)
        out.append(f'<g class="o" style="animation-delay:{t0 + wk * 0.012:.3f}s">{rects}</g>')
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(txt(PAD, top + row * p + 10, name, "lbl o", t0))
    end, fy = gx + (max(weeks) + 1) * p - GAP, top + 7 * p - GAP + 24
    t1 = t0 + max(weeks) * 0.012 + 0.1
    legend_x = end - len("More") * 11 * EM - 6 - (5 * 13 - 3)
    out += [txt(PAD, fy, f"{total:,} contributions in the last year", "sm o", t1),
            txt(end, fy, "More", "lbl o", t1, "end"),
            txt(legend_x - 6, fy, "Less", "lbl o", t1, "end"),
            f'<g class="o" style="animation-delay:{t1:.2f}s">' + "".join(
                f'<rect x="{legend_x + i * 13:g}" y="{fy - 9}" width="10" height="10" rx="2" '
                f'class="h{i}"/>' for i in range(5)) + "</g>"]
    return "".join(out)


def whoami(st, logos, t0):
    lx, rx = PAD, W - PAD - PANEL_W
    keyframes = ""
    if logos:
        reel, keyframes = carousel(logos, lx + PANEL_W / 2, PANEL_Y + 168, t0 + 0.1)
        out = [f'<g class="o" style="animation-delay:{t0:.2f}s">{reel}</g>']
    else:
        out = [txt(lx + PANEL_W / 2, PANEL_Y + 200, "logos unavailable", "ph", anchor="middle")]
    col_w, y0 = (PANEL_W - 28) / 2, PANEL_Y + 48
    for i, (label, value, unit, sub) in enumerate(st["items"]):
        x, y = rx + 18 + (i % 2) * col_w, y0 + (i // 2) * 66
        unit_span = f'<tspan class="unit" dx="6">{esc(unit)}</tspan>' if unit else ""
        out.append(
            f'<g class="o" style="animation-delay:{t0 + 0.15 + i * 0.05:.2f}s">'
            f'{txt(x, y, label, "sl")}<text x="{x}" y="{y + 26}"><tspan class="'
            f'{"num acc" if i == 0 else "num"}">{esc(value)}</tspan>{unit_span}</text>'
            f'{txt(x, y + 42, sub, "ss")}</g>')
    months = st["months"]
    vmax = max([v for _, v in months] + [1])
    cx, base, slot, bw, maxh = rx + 18, PANEL_Y + 340, (PANEL_W - 36) / 12, 18, 52
    bars = [txt(cx, PANEL_Y + 262, "contributions / month", "sl")]
    for i, (ym, v) in enumerate(months):
        bx = cx + i * slot + (slot - bw) / 2
        h = max(2.0, v / vmax * maxh) if v else 2.0
        lv = 0 if not v else 4 if v == vmax else 3
        bars.append(f'<rect x="{bx:.1f}" y="{base - h:.1f}" width="{bw}" height="{h:.1f}" '
                    f'rx="2" class="h{lv}"/>')
        if v == vmax and v:
            bars.append(txt(bx + bw / 2, base - h - 5, f"{v:,}", "pk", anchor="middle"))
        bars.append(txt(bx + bw / 2, base + 15, MONTHS[int(ym[5:]) - 1], "ml", anchor="middle"))
    out.append(f'<g class="o" style="animation-delay:{t0 + 0.5:.2f}s">{"".join(bars)}</g>')
    return "".join(out), keyframes


def style(T, keyframes):
    h = T["heat"]
    return "\n".join([
        f"text{{font-family:{MONO};font-size:14px;fill:{T['text']}}}",
        f".win{{fill:{T['bg']};stroke:{T['line']}}}", f".bar{{fill:{T['bar']}}}",
        f".sep{{stroke:{T['line']}}}",
        f".ttl{{font-size:12px;fill:{T['muted']}}}",
        f".pu{{fill:{T['green']};font-weight:700}}", f".pp{{fill:{T['blue']};font-weight:700}}",
        f".pd{{fill:{T['muted']}}}", ".pc{font-weight:600}", f".bgf{{fill:{T['bg']}}}",
        f".cur{{fill:{T['muted']};opacity:0;animation:hide 1ms linear both}}",
        f".lbl{{font-size:11px;fill:{T['muted']}}}", f".sm{{font-size:12px;fill:{T['muted']}}}",
        *(f".h{i}{{fill:{c}}}" for i, c in enumerate(h)),
        f".ph{{font-size:11px;fill:{T['faint']}}}", f".sl{{font-size:11px;fill:{T['muted']}}}",
        ".num{font-size:22px;font-weight:700}", f".acc{{fill:{T['green']}}}",
        f".unit{{font-size:12px;fill:{T['muted']}}}", f".ss{{font-size:10.5px;fill:{T['faint']}}}",
        f".pk{{font-size:10px;fill:{T['text']}}}", f".ml{{font-size:9.5px;fill:{T['faint']}}}",
        ".lg,.dn{opacity:0}", ".lg0,.dn0{opacity:1}",          # still frame: first logo
        f".lgl{{font-size:15px;font-weight:600;fill:{T['text']}}}",
        f".dt{{fill:{T['line']}}}", f".dn{{fill:{T['green']}}}",
        ".o{animation:fade .35s ease-out both}",
        "@keyframes fade{from{opacity:0}to{opacity:1}}",
        "@keyframes hide{from{opacity:1}to{opacity:0}}",
        "@media (prefers-reduced-motion:reduce){*{animation:none!important}}",
        keyframes,
    ])


def render(days, total, st, logos, theme):
    T = THEMES[theme]
    p1, k1 = prompt(70, "./contributions.sh", "type1", 0.35)
    heat = heatmap(days, total, 106, 1.3) if days else ""
    p2, k2 = prompt(280, "whoami", "type2", 2.35, 2.15)
    me, k3 = whoami(st, logos, 2.75)
    desc = (f"{PROMPT}: {total:,} contributions ({st['range']}). "
            + ", ".join(f"{label} {value} {unit}".strip() for label, value, unit, _ in st["items"][:2])
            + ". Stack: " + ", ".join(label for label, _ in logos) + ".")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-labelledby="t d">\n<title id="t">{esc(PROMPT)} ~ $ whoami</title>'
        f'<desc id="d">{esc(desc)}</desc>\n<style>\n{style(T, k1 + k2 + k3)}\n</style>\n'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" class="win"/>'
        f'<path d="M.5 36.5V10.5A10 10 0 0 1 10.5 .5H{W - 10.5}A10 10 0 0 1 {W - .5} 10.5V36.5Z" '
        f'class="bar"/><line x1=".5" y1="36.5" x2="{W - .5}" y2="36.5" class="sep"/>'
        f'<circle cx="22" cy="18.5" r="6" fill="#ff5f57"/><circle cx="42" cy="18.5" r="6" '
        f'fill="#febc2e"/><circle cx="62" cy="18.5" r="6" fill="#28c840"/>'
        f'{txt(W / 2, 23, f"{PROMPT}: ~", "ttl", anchor="middle")}\n'
        f"{p1}\n{heat}\n{p2}\n{me}\n</svg>\n")


def load_logos(theme, cache):
    out = []
    for name, label, variant, dark_variant in LOGOS:
        key = (name, dark_variant if theme == "dark" and dark_variant else variant)
        if key not in cache:
            try:
                cache[key] = logo_source(*key)
            except Exception as e:                       # noqa: BLE001
                print(f"logo {key[0]}-{key[1]} skipped ({e})")
                cache[key] = None
        if cache[key]:
            out.append((label, cache[key]))
    return out


def main():
    data = None
    if TOKEN:
        try:
            data = from_graphql()
        except Exception as e:                           # noqa: BLE001
            print(f"GraphQL failed ({e}); using the public contributions page")
    days, total = data or from_public()
    st = stats(days, total)
    cache = {}
    os.makedirs(OUT_DIR, exist_ok=True)
    for theme in THEMES:
        logos = load_logos(theme, cache)
        with open(os.path.join(OUT_DIR, f"terminal-{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(render(days, total, st, logos, theme))
    print(f"ok: {total} contributions, {len(days)} days, {len(logos)} logos, "
          f"current streak {st['items'][0][1]}, longest {st['items'][1][1]}")


if __name__ == "__main__":
    main()
