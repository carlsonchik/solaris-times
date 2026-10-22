#!/usr/bin/env python3
"""Solaris Times static builder.
Source of truth: content/YYYY-MM-DD.json (one per issue).
Builds: issues/<date>/index.html, index.html (latest published), archive/index.html, issues.json.
Issues whose publish_at (ISO, with offset) is in the future are NOT built (embargo)."""
import json, glob, os, sys, html, datetime as dt
ROOT = os.path.dirname(os.path.abspath(__file__))
MONTHS = "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split()
WD = "понедельник вторник среда четверг пятница суббота воскресенье".split()

def ru_date(d):
    x = dt.date.fromisoformat(d)
    return f"{WD[x.weekday()]}, {x.day} {MONTHS[x.month-1]} {x.year}"

def load(now):
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "content", "*.json"))):
        it = json.load(open(f, encoding="utf-8"))
        if dt.datetime.fromisoformat(it["publish_at"]) <= now:
            out.append(it)
    out.sort(key=lambda i: i["date"])
    return out

def page(title, body, depth, desc=""):
    p = "../" * depth
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,800;1,600&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=Inter:wght@400;600&display=swap&subset=cyrillic" rel="stylesheet">
<link rel="stylesheet" href="{p}assets/style.css"></head><body>
<header class="mast"><a class="brand" href="{p}">Solaris Times</a>
<nav class="top"><a href="{p}">Свежий номер</a><a href="{p}archive/">Архив</a></nav></header>
{body}
<footer class="foot"><p>Solaris Times — личная утренняя газета. Факты со ссылками на первоисточники; редакционные выводы помечены «Мнение редакции».</p>
<p><a href="{p}archive/">Архив</a></p></footer></body></html>"""

def issue_html(it, prev, nxt, depth):
    p = "../" * depth
    pdf = f'<a href="{p}issues/{it["date"]}/solaris-times-{it["date"]}.pdf">печатная версия</a>' 
    nav = '<nav class="pager">' + (f'<a href="{p}issues/{prev["date"]}/">← № {prev["number"]} · {prev["date"]}</a>' if prev else '<span></span>') \
        + f'<span><a href="{p}archive/">все выпуски</a> · {pdf}</span>' + (f'<a href="{p}issues/{nxt["date"]}/">№ {nxt["number"]} · {nxt["date"]} →</a>' if nxt else '<span></span>') + '</nav>'
    head = f'''<div class="dateline"><span>№ {it["number"]}</span><span>{ru_date(it["date"])}</span><span>{it["read_time"]}</span></div>
<p class="lede">{it["lede"]}</p>'''
    body = it["body"].replace("{{ROOT}}", p)
    return page(f'Solaris Times № {it["number"]} — {it["date"]}', f'<main class="issue">{head}{nav}{body}{nav}</main>', depth, it["lede"])

import re
def print_html(it):
    notes = []
    def fn(m):
        href, text = m.group(1), m.group(2)
        notes.append(href); return f'{text}<sup>{len(notes)}</sup>'
    body = it["body"].replace("{{ROOT}}", "../../")
    body = re.sub(r'<a href="([^"]+)">(.*?)</a>', fn, body, flags=re.S)
    short = lambda u: re.sub(r'^https?://(www\d*\.)?', '', u)
    fns = "".join(f'<li>{html.escape(short(u))}</li>' for u in notes)
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Solaris Times № {it["number"]} — печать</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap&subset=cyrillic" rel="stylesheet">
<link rel="stylesheet" href="../../assets/print.css"></head><body>
<header class="pm"><div class="orbit">✦ ежедневная газета для одного читателя ✦</div><h1>Solaris Times</h1>
<div class="pd"><span>№ {it["number"]}</span><span>{ru_date(it["date"])}</span><span>{it["read_time"]}</span></div></header>
<p class="lede">{it["lede"]}</p><div class="paper">{body}</div>
<section class="fns"><h4>Источники</h4><ol>{fns}</ol></section></body></html>"""

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
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(issue_html(it, prev, nxt, 2))
        open(os.path.join(d, "print.html"), "w", encoding="utf-8").write(print_html(it))
        if "--no-pdf" not in sys.argv: make_pdf(d, it["date"])
    if issues:
        latest = issues[-1]
        open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(
            issue_html(latest, issues[-2] if len(issues) > 1 else None, None, 0))
    rows = "".join(f'<li><a href="../issues/{it["date"]}/"><span class="n">№ {it["number"]}</span><span class="d">{ru_date(it["date"])}</span><span class="t">{html.escape(it["headline"])}</span></a></li>' for it in reversed(issues))
    os.makedirs(os.path.join(ROOT, "archive"), exist_ok=True)
    open(os.path.join(ROOT, "archive", "index.html"), "w", encoding="utf-8").write(
        page("Архив — Solaris Times", f'<main class="archive"><h1>Архив выпусков</h1><ul>{rows}</ul></main>', 1))
    manifest = [{k: it[k] for k in ("date", "number", "headline", "publish_at", "items")} | {"url": f"issues/{it['date']}/"} for it in issues]
    json.dump(manifest, open(os.path.join(ROOT, "issues.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"built {len(issues)} issue(s); latest: {issues[-1]['date'] if issues else None}")

if __name__ == "__main__":
    main()
