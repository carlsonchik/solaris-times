#!/usr/bin/env python3
"""Solaris Times static builder.
Source of truth: content/YYYY-MM-DD.json (one per issue).
Builds: issues/<date>/index.html, index.html (latest published), archive/index.html, issues.json.
Issues whose publish_at (ISO, with offset) is in the future are NOT built (embargo)."""
import json, glob, os, re, sys, html, datetime as dt
ROOT = os.path.dirname(os.path.abspath(__file__))
MONTHS = "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split()
WD = "понедельник вторник среда четверг пятница суббота воскресенье".split()

def ru_date(d):
    x = dt.date.fromisoformat(d)
    return f"{WD[x.weekday()]}, {x.day} {MONTHS[x.month-1]} {x.year}"

def week_range(it):
    """'2–8 ноября 2026' / '30 ноября – 6 декабря 2026' / '29 декабря 2026 – 4 января 2027'."""
    a, b = (dt.date.fromisoformat(x) for x in it["week"])
    if a.year != b.year:
        return f"{a.day} {MONTHS[a.month-1]} {a.year} – {b.day} {MONTHS[b.month-1]} {b.year}"
    if a.month != b.month:
        return f"{a.day} {MONTHS[a.month-1]} – {b.day} {MONTHS[b.month-1]} {b.year}"
    return f"{a.day}–{b.day} {MONTHS[b.month-1]} {b.year}"

def is_weekly(it):
    return it.get("kind") == "weekly"

def when(it):
    """Human date part: week range for weekly issues, weekday+date for old dailies."""
    return week_range(it) if is_weekly(it) else ru_date(it["date"])

def label(it):
    return f'№ {it["number"]} · {week_range(it)}' if is_weekly(it) else f'№ {it["number"]} · {it["date"]}'

# Reading-time budget (minutes ≈ words/130). Daily: ≤18 min; weekly: 35–45 min.
LIMITS = {"daily": (0, 2300), "weekly": (4500, 6000)}
def check_length(it):
    words = len(re.sub(r"<[^>]+>", " ", it["body"]).split())
    lo, hi = LIMITS["weekly" if is_weekly(it) else "daily"]
    if words > hi * 1.1 or (lo and words < lo * 0.8):
        print(f"WARN: № {it['number']}: {words} слов (ориентир {lo}–{hi})", file=sys.stderr)

def toc(body):
    """Contents from body: <section class="part" data-part="…"> headings, then h2 titles and rubric kickers inside."""
    out = []
    for m in re.finditer(r'<section class="part" data-part="([^"]+)"|<h2[^>]*>(.*?)</h2>|<section class="rubric">\s*(?:<figure.*?</figure>\s*)?<p class="kicker">(.*?)</p>', body, re.S):
        part, h2, kick = m.groups()
        if part: out.append(f'<li class="tp">{html.escape(part)}</li>')
        elif h2: out.append(f'<li>{re.sub(r"<[^>]+>", "", h2)}</li>')
        elif kick: out.append(f'<li class="tr">{re.sub(r"<[^>]+>", "", kick)}</li>')
    return '<ol class="toc">' + "".join(out) + '</ol>' if out else ""

def load(now):
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "content", "*.json"))):
        it = json.load(open(f, encoding="utf-8"))
        if dt.datetime.fromisoformat(it["publish_at"]) <= now:
            out.append(it)
    out.sort(key=lambda i: i["date"])
    return out

def page(title, body, depth, desc="", extra_nav=""):
    p = "../" * depth
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,800;1,600&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=Inter:wght@400;600&display=swap&subset=cyrillic" rel="stylesheet">
<link rel="stylesheet" href="{p}assets/style.css"></head><body>
<header class="mast"><a class="brand" href="{p}">Solaris Times</a>
<nav class="top"><a href="{p or "./"}">Свежий номер</a><a href="{p}archive/">Архив</a>{extra_nav}</nav></header>
{body}
<footer class="foot"><p>Solaris Times — личная газета Дениса, выходит по воскресеньям в 21:00 МСК. Факты со ссылками на первоисточники; редакционные выводы помечены «Мнение редакции».</p>
<p><a href="{p}archive/">Архив</a></p></footer></body></html>"""

def issue_html(it, prev, nxt, depth):
    p = "../" * depth
    pdf = f'<a href="{p}issues/{it["date"]}/solaris-times-{it["date"]}.pdf">Печатная версия</a>' 
    nav = '<nav class="pager">' + (f'<a href="{p}issues/{prev["date"]}/">← {label(prev)}</a>' if prev else '<span></span>') \
         + (f'<a href="{p}issues/{nxt["date"]}/">{label(nxt)} →</a>' if nxt else '<span></span>') + '</nav>'
    head = f'''<div class="dateline"><span>№ {it["number"]}</span><span>{when(it)}</span><span>{it["read_time"]}</span></div>
<p class="lede">{it["lede"]}</p>'''
    if is_weekly(it):
        head += f'<details class="contents" open><summary>В номере</summary>{toc(it["body"])}</details>'
    body = it["body"].replace("{{ROOT}}", p)
    return page(f'Solaris Times № {it["number"]} — {when(it) if is_weekly(it) else it["date"]}', f'<main class="issue">{head}{nav}{body}{nav}</main>', depth, it["lede"], pdf)

def print_html(it):
    body = it["body"].replace("{{ROOT}}", "../../")
    body = re.sub(r'<a [^>]*>(.*?)</a>', r'\1', body, flags=re.S)  # print: links -> plain text, no sources
    weekly = is_weekly(it)
    orbit = "еженедельная газета для одного читателя" if weekly else "ежедневная газета для одного читателя"
    cover = ""
    if weekly:
        cover = f'<section class="cover-toc"><h4>В номере</h4>{toc(it["body"])}</section>'
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Solaris Times № {it["number"]} — печать</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap&subset=cyrillic" rel="stylesheet">
<link rel="stylesheet" href="../../assets/print.css"></head><body class="{'weekly' if weekly else 'daily'}">
<header class="pm"><div class="orbit">✦ {orbit} ✦</div><h1>Solaris Times</h1>
<div class="pd"><span>№ {it["number"]}</span><span>{when(it)}</span><span>{it["read_time"]}</span></div></header>
<p class="lede">{it["lede"]}</p>{cover}<div class="paper">{body}</div>
</body></html>"""

def make_pdf(d, date):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("WARN: playwright not installed, PDF skipped for", date); return
    out = os.path.join(d, f"solaris-times-{date}.pdf")
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        pg.goto("file://" + os.path.join(d, "print.html"), wait_until="networkidle")
        pg.pdf(path=out, format="A4", print_background=True, margin={"top":"14mm","bottom":"16mm","left":"13mm","right":"13mm"},
               display_header_footer=True, header_template="<span></span>",
               footer_template='<div style="font:8px serif;width:100%;text-align:center;color:#555">Solaris Times · <span class="pageNumber"></span>/<span class="totalPages"></span></div>')
        b.close()

def main():
    now = dt.datetime.now(dt.timezone.utc)
    if len(sys.argv) > 2 and sys.argv[1] == "--now":
        now = dt.datetime.fromisoformat(sys.argv[2])
    issues = load(now)
    for i, it in enumerate(issues):
        prev = issues[i-1] if i else None
        nxt = issues[i+1] if i+1 < len(issues) else None
        d = os.path.join(ROOT, "issues", it["date"]); os.makedirs(d, exist_ok=True)
        check_length(it)
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(issue_html(it, prev, nxt, 2))
        open(os.path.join(d, "print.html"), "w", encoding="utf-8").write(print_html(it))
        if "--no-pdf" not in sys.argv: make_pdf(d, it["date"])
    if issues:
        latest = issues[-1]
        open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(
            issue_html(latest, issues[-2] if len(issues) > 1 else None, None, 0))
    rows = "".join(f'<li><a href="../issues/{it["date"]}/"><span class="n">№ {it["number"]}</span><span class="d">{when(it)}</span><span class="t">{html.escape(it["headline"])}</span></a></li>' for it in reversed(issues))
    os.makedirs(os.path.join(ROOT, "archive"), exist_ok=True)
    open(os.path.join(ROOT, "archive", "index.html"), "w", encoding="utf-8").write(
        page("Архив — Solaris Times", f'<main class="archive"><h1>Архив выпусков</h1><ul>{rows}</ul></main>', 1))
    manifest = [{k: it[k] for k in ("date", "number", "headline", "publish_at", "items")} | {k: it[k] for k in ("kind", "week") if k in it} | {"url": f"issues/{it['date']}/"} for it in issues]
    json.dump(manifest, open(os.path.join(ROOT, "issues.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"built {len(issues)} issue(s); latest: {issues[-1]['date'] if issues else None}")

if __name__ == "__main__":
    main()
