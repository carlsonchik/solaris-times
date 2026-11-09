#!/usr/bin/env python3
"""Solaris Times static builder.
Source of truth: content/YYYY-MM-DD.json (one per issue).
Builds: issues/<date>/index.html, index.html (latest published), archive/index.html, issues.json.
Issues whose publish_at (ISO, with offset) is in the future are NOT built (embargo)."""
import json, glob, os, re, sys, html, struct, itertools, datetime as dt
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

# A photo this wide (4:3) or wider spans the full measure in the weekly PDF.
# Narrower photos stay one column wide so the story can run beside them.
WIDE_FIGURE = 4 / 3
_PRINT_BLOCK = re.compile(
    r'<(article|section)\b[^>]*\bclass="(?:lead|feature|rubric)"[^>]*>.*?</\1>', re.S)

def _image_aspect(src):
    """Width/height of a raster in assets/img, or None if it cannot be read."""
    name = os.path.basename(src.split("?", 1)[0])
    path = os.path.join(ROOT, "assets", "img", name)
    try:
        data = open(path, "rb").read()
    except OSError:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        w, h = struct.unpack(">II", data[16:24])
        return (w / h) if h else None
    if data[:2] != b"\xff\xd8":
        return None
    i, n = 2, len(data)
    while i + 8 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            break
        marker = data[i]
        i += 1
        if marker in (0xD8, 0xD9) or marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if i + 2 > n:
            break
        seglen = struct.unpack(">H", data[i:i + 2])[0]
        if marker in (0xC0, 0xC1, 0xC2) and i + 7 <= n:
            h, w = struct.unpack(">HH", data[i + 3:i + 7])
            return (w / h) if h else None
        if seglen < 2:
            break
        i += seglen
    return None

def _add_class(fig, cls):
    if re.match(r'<figure\b[^>]*\bclass="', fig):
        return re.sub(r'\bclass="', f'class="{cls} ', fig, count=1)
    return re.sub(r'<figure\b', f'<figure class="{cls}"', fig, count=1)

def _place_in_block(block):
    """Close the blank column beside an opening figure.

    A heading with column-span:all ends the column band above it. A figure
    that is the only box in that band sits in column one and leaves column
    two empty. A wide photo spans the band instead. Any other photo moves
    to just after the heading, into the same band as the body, which is how
    the feature stories already set type beside a picture.
    """
    fm = re.search(r'<figure\b[^>]*>.*?</figure>', block, re.S)
    if not fm:
        return block
    fig = fm.group(0)
    srcm = re.search(r'\bsrc="([^"]+)"', fig)
    aspect = _image_aspect(srcm.group(1)) if srcm else None
    if aspect is not None and aspect >= WIDE_FIGURE:
        return block[:fm.start()] + _add_class(fig, "wide") + block[fm.end():]
    hm = re.search(r'<h[23]\b[^>]*>.*?</h[23]>', block, re.S)
    if not hm or fm.start() > hm.start():
        return block
    original = block
    end = fm.end() + (1 if fm.end() < len(block) and block[fm.end()] == "\n" else 0)
    block = block[:fm.start()] + block[end:]
    hm = re.search(r'<h[23]\b[^>]*>.*?</h[23]>', block, re.S)
    if not hm:
        return original
    return block[:hm.end()] + "\n" + fig + block[hm.end():]

def place_print_figures(body):
    return _PRINT_BLOCK.sub(lambda m: _place_in_block(m.group(0)), body)

_KEEP_BLOCK = re.compile(
    r'<(article|section)\b[^>]*\bclass="(?:lead|feature|rubric)"[^>]*>.*?</\1>', re.S)
_KEEP_HEAD = re.compile(r'<p class="(?:kicker|part-title)">.*?</p>|<h[23]\b[^>]*>.*?</h[23]>', re.S)
_KEEP_FIG = re.compile(r'<figure\b[^>]*>.*?</figure>', re.S)
_KEEP_PARA = re.compile(
    r'<p\b(?![^>]*\bclass="(?:kicker|op|src|part-title)")[^>]*>.*?</p>|<ul\b[^>]*>.*?</ul>|<ol\b[^>]*>.*?</ol>',
    re.S)

def _plain_len(html_chunk):
    text = re.sub(r"<[^>]+>", " ", html_chunk)
    return len(re.sub(r"\s+", " ", text).strip())

def _wrap_block(block):
    """Keep a title with the first lines of the piece under it.

    Chromium will leave a part title and kicker at the bottom of a column
    when the headline no longer fits. break-inside:avoid on the whole
    opener is what this PDF engine honors.
    """
    m = re.match(r'(<(?:article|section)\b[^>]*>)(.*)</(article|section)>\s*$', block, re.S)
    if not m:
        return block
    open_tag, inner, close = m.group(1), m.group(2), m.group(3)
    # The cover column under the contents is short. A lead photo locked
    # to the headline is taller than that column, so the opener would
    # skip the cover. The photo stays in the flow; the title does not.
    skip_figures = "lead" in open_tag
    out, pos = [], 0
    while True:
        found = _KEEP_HEAD.search(inner, pos)
        if not found:
            out.append(inner[pos:])
            break
        out.append(inner[pos:found.start()])
        end = found.end()
        while True:
            ws = re.match(r"\s*", inner[end:])
            nxt = end + ws.end()
            nxt_head = _KEEP_HEAD.match(inner, nxt)
            if nxt_head and nxt_head.start() == nxt:
                end = nxt_head.end()
                continue
            nxt_fig = _KEEP_FIG.match(inner, nxt)
            if nxt_fig and nxt_fig.start() == nxt and not skip_figures:
                end = nxt_fig.end()
                continue
            break
        ws = re.match(r"\s*", inner[end:])
        nxt = end + ws.end()
        div = re.match(r'<div class="(?:cols|text)">\s*', inner[nxt:])
        para_at = nxt + div.end() if div else nxt
        para = _KEEP_PARA.match(inner, para_at)
        if not para or para.start() != para_at:
            out.append("<div class=\"keep\">" + inner[found.start():end] + "</div>")
            pos = end
            continue
        end2 = para.end()
        if _plain_len(para.group(0)) < 180 and para.group(0).startswith("<p"):
            ws2 = re.match(r"\s*", inner[end2:])
            nxt2 = end2 + ws2.end()
            para2 = re.match(r"<p\b[^>]*>.*?</p>", inner[nxt2:], re.S)
            if para2 and para2.start() == 0 and "kicker" not in para2.group(0)[:80]:
                end2 = nxt2 + para2.end()
        heads = inner[found.start():nxt]
        paras = inner[para_at:end2]
        out.append("<div class=\"keep\">" + heads + paras + "</div>")
        if div:
            out.append(div.group(0))
        pos = end2
    return open_tag + "".join(out) + f"</{close}>"

def keep_print_openings(body):
    """Weekly print: a heading group moves with its opening paragraph."""
    def part_title(m):
        name = m.group(1)
        return f'<section class="part" data-part="{name}">\n<p class="part-title">{name}</p>\n'
    body = re.sub(r'<section class="part" data-part="([^"]+)">', part_title, body)
    body = _KEEP_BLOCK.sub(lambda m: _wrap_block(m.group(0)), body)
    return re.sub(
        r'<p class="part-title">(.*?)</p>\s*(<article class="feature">\s*<div class="keep">)',
        r'\2<p class="part-title">\1</p>',
        body, flags=re.S)

def load_fillers(date):
    """Optional print-only pool: issues/<date>/fillers.json. Absent → no досыпки."""
    path = os.path.join(ROOT, "issues", date, "fillers.json")
    if not os.path.isfile(path):
        return []
    return json.load(open(path, encoding="utf-8"))

def filler_box(item):
    title = f'<h4>{html.escape(item["title"])}</h4>' if item.get("title") else ""
    ident = html.escape(item["id"])
    # A/Z marks bracket the box so a split across columns is visible. Stripped before the final PDF.
    return (f'<aside class="filler" data-id="{ident}" '
            f'data-kicker="{html.escape(item["kicker"])}">'
            f'<span class="fill-mark">FID:{ident}:A</span>'
            f'<p class="kicker">{html.escape(item["kicker"])}</p>{title}{item["html"]}'
            f'<span class="fill-mark">FID:{ident}:Z</span></aside>')

_SLOT_RE = re.compile(r'<section class="part"|<article class="feature"|<section class="rubric"')

def insert_fill_slots(body):
    """Markers before each part, later feature, and rubric — the spots a page break leaves empty."""
    parts, pos, n, after_part = [], 0, 0, False
    for m in _SLOT_RE.finditer(body):
        kind = m.group(0)
        slot = ""
        if kind.startswith("<section class=\"part"):
            slot = f'<span class="fill-mark" data-slot="{n}">FS{n:02d}</span>'
            n += 1
            after_part = True
        elif kind.startswith("<article class=\"feature"):
            if after_part:
                after_part = False  # shares the part's page break
            else:
                slot = f'<span class="fill-mark" data-slot="{n}">FS{n:02d}</span>'
                n += 1
        else:
            after_part = False
            slot = f'<span class="fill-mark" data-slot="{n}">FS{n:02d}</span>'
            n += 1
        parts.append(body[pos:m.start()] + slot)
        pos = m.start()
    parts.append(body[pos:])
    parts.append(f'<span class="fill-mark" data-slot="{n}">FS{n:02d}</span>')
    return "".join(parts), n + 1

def apply_slot_fillers(body, slot_items):
    """slot_items: {slot index: [filler dict, ...]}."""
    def repl(m):
        idx = int(m.group(1))
        boxes = "".join(filler_box(it) for it in slot_items.get(idx, []))
        return boxes + m.group(0)
    return re.sub(r'<span class="fill-mark" data-slot="(\d+)">FS\d+</span>', repl, body)

def print_html(it, slot_items=None, with_slots=False, strip_marks=False):
    body = it["body"].replace("{{ROOT}}", "../../")
    body = re.sub(r'<a [^>]*>(.*?)</a>', r'\1', body, flags=re.S)  # print: links -> plain text, no sources
    weekly = is_weekly(it)
    if weekly:
        body = place_print_figures(body)
        body = keep_print_openings(body)
        if with_slots or slot_items is not None:
            body, _ = insert_fill_slots(body)
            if slot_items:
                body = apply_slot_fillers(body, slot_items)
            if strip_marks:
                body = re.sub(r'<span class="fill-mark"[^>]*>.*?</span>', '', body)
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

def _pdf_html(html_path, pdf_path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        pg.goto("file://" + html_path, wait_until="networkidle")
        pg.pdf(path=pdf_path, format="A4", print_background=True, margin={"top":"14mm","bottom":"16mm","left":"13mm","right":"13mm"},
               display_header_footer=True, header_template="<span></span>",
               footer_template='<div style="font:8px serif;width:100%;text-align:center;color:#555">Solaris Times · <span class="pageNumber"></span>/<span class="totalPages"></span></div>')
        b.close()

def make_pdf(d, date):
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("WARN: playwright not installed, PDF skipped for", date); return
    _pdf_html(os.path.join(d, "print.html"), os.path.join(d, f"solaris-times-{date}.pdf"))

_MM = 72 / 25.4
# A column tail deeper than this is worth a досыпка. Below it, the remainder is noise.
_GAP_MIN = 20.0

def _flat(s):
    return re.sub(r"[\s\u00ad]+", "", s or "")

def _editorial_titles(it):
    titles = []
    for m in re.finditer(r"<h[23][^>]*>(.*?)</h[23]>", it["body"], re.S):
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
        if len(t) >= 18:
            titles.append(t)
    return titles

def _analyze_pdf(pdf_path):
    """Column tails (mm) and where each FS marker sits, with the room below it."""
    import fitz
    doc = fitz.open(pdf_path)
    top, bot = 14 * _MM, 16 * _MM
    gaps, marks, texts, content, floors, ids = [], {}, [], [], [], {}
    try:
        for i, page in enumerate(doc):
            r = page.rect
            floor = r.height - bot
            floors.append(floor)
            mid = r.width / 2
            cols = {"L": [], "R": []}
            texts.append(page.get_text())
            for b in page.get_text("dict")["blocks"]:
                x0, y0, x1, y1 = b["bbox"]
                if y0 > r.height - 28:
                    continue
                text = ""
                if b.get("type") == 0:
                    for ln in b.get("lines", []):
                        text += "".join(s["text"] for s in ln["spans"])
                    if "Solaris Times" in text:
                        continue
                compact = re.sub(r"\s+", "", text)
                side = "L" if (x0 + x1) / 2 < mid else "R"
                if b.get("type") == 0:
                    # A box-end mark and the following slot mark often share one PDF block.
                    for mid_id in re.finditer(r"FID:([^:]+):([AZ])", compact):
                        ids[mid_id.group(2) + mid_id.group(1)] = {
                            "page": i + 1, "side": side, "y0": y0, "y1": y1}
                    for m in re.finditer(r"FS(\d+)", compact):
                        marks[int(m.group(1))] = {"page": i + 1, "side": side, "y0": y0, "y1": y1}
                    leftover = re.sub(r"FID:[^:]+:[AZ]|FS\d+", "", compact)
                    if leftover == "":
                        continue
                cols[side].append((y0, y1))
            content.append(cols)
            def gap(side):
                if not cols[side]:
                    return (floor - top) / _MM
                return (floor - max(y1 for _, y1 in cols[side])) / _MM
            gaps.append({"page": i + 1, "left": gap("L"), "right": gap("R")})
        for slot, mk in marks.items():
            spans = content[mk["page"] - 1][mk["side"]]
            floor = floors[mk["page"] - 1]
            below = [y0 for y0, _y1 in spans if y0 > mk["y1"] - 0.6]
            if below:
                room = (min(below) - mk["y0"]) / _MM
            else:
                above = [y1 for y0, y1 in spans if y1 <= mk["y0"] + 1.0]
                end = max(above) if above else mk["y0"]
                room = (floor - end) / _MM
            mk["room"] = room
        return {"pages": doc.page_count, "gaps": gaps, "marks": marks, "texts": texts, "ids": ids}
    finally:
        doc.close()

def _anchor_pages(texts, titles):
    flats = [_flat(t) for t in texts]
    found = {}
    for title in titles:
        key = _flat(title)[:36]
        if len(key) < 12:
            continue
        for i, ft in enumerate(flats):
            if key in ft:
                found[title] = i + 1
                break
    return found

def _measure_filler_heights(fillers):
    """Height of each досыпка in one print column, in millimetres, margins included."""
    from playwright.sync_api import sync_playwright
    boxes = "".join(f'<div class="probe">{filler_box(it)}</div>' for it in fillers)
    page = f'''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap&subset=cyrillic" rel="stylesheet">
<link rel="stylesheet" href="file://{ROOT}/assets/print.css">
<style>.probe{{width:89.5mm;margin:0 0 4mm;padding:0;border:0}}</style></head>
<body class="weekly"><div>{boxes}</div></body></html>'''
    path = os.path.join(ROOT, "issues", "_filler_probe.html")
    open(path, "w", encoding="utf-8").write(page)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page()
            pg.emulate_media(media="print")
            pg.goto("file://" + path, wait_until="networkidle")
            pg.evaluate("() => document.fonts.ready")
            raw = pg.evaluate("""() => [...document.querySelectorAll('.filler')].map(el => {
              const cs = getComputedStyle(el);
              const h = el.getBoundingClientRect().height
                + parseFloat(cs.marginTop) + parseFloat(cs.marginBottom);
              return {id: el.dataset.id, h};})""")
            b.close()
    finally:
        os.remove(path)
    return {row["id"]: row["h"] / (96 / 25.4) for row in raw}

def _filler_norm(item):
    text = re.sub(r"<[^>]+>", " ", item.get("html") or "")
    return re.sub(r"[\s\u00ad«»\"'.,—–\-]+", "", text).lower()

def _shares_fact(a, b, n=28):
    """True when two fillers tell the same dated fact (a long shared phrase)."""
    if len(a) < n or len(b) < n:
        return False
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return any(short[i:i + n] in long for i in range(len(short) - n + 1))

def _fact_already_told(it, fillers, used, norms):
    """Skip a shorter box when a longer one still carries the same fact."""
    mine = norms[it["id"]]
    for other in fillers:
        if other["id"] == it["id"]:
            continue
        theirs = norms[other["id"]]
        if not _shares_fact(mine, theirs):
            continue
        if other["id"] in used or len(theirs) > len(mine):
            return True
    return False

def _pack_fillers(holes, fillers, heights, norms):
    """Fill every measured tail at once, so a large hole does not steal the items a small one needs.

    holes: reading order of {slot, page, side, room}. A dated fact that already lives in a
    longer filler is left unused. Returns the best {slot: [item, ...]} or {}.
    """
    pool = [it for it in fillers
            if heights.get(it["id"]) and not _fact_already_told(it, fillers, set(), norms)]
    if not holes or not pool:
        return {}
    names = [h["slot"] for h in holes]
    room = {h["slot"]: h["room"] for h in holes}
    page = {h["slot"]: h["page"] for h in holes}
    by = {it["id"]: it for it in pool}

    def perms(group):
        if not group:
            return [[]]
        out = []
        for perm in itertools.permutations(group):
            ks = [by[i]["kicker"] for i in perm]
            if any(ks[i] == ks[i + 1] for i in range(len(ks) - 1)):
                continue
            out.append(list(perm))
        return out

    def layout(assign):
        pages = {}
        for slot, ids in assign.items():
            seen = []
            for i in ids:
                k = by[i]["kicker"]
                if k in seen:
                    return None
                seen.append(k)
            bag = pages.setdefault(page[slot], [])
            for k in seen:
                if k in bag:
                    return None
                bag.append(k)
        opts = [perms(assign[s]) for s in names]
        if any(not o for o in opts):
            return None
        seq = [None] * len(names)

        def walk(i, prev):
            if i == len(names):
                return True
            for perm in opts[i]:
                if perm and prev and by[perm[0]]["kicker"] == prev:
                    continue
                seq[i] = perm
                nxt = by[perm[-1]]["kicker"] if perm else prev
                if walk(i + 1, nxt):
                    return True
            return False

        if not walk(0, None):
            return None
        return {names[i]: [by[n] for n in seq[i]] for i in range(len(names)) if seq[i]}

    best = None
    assign = {s: [] for s in names}

    def score():
        rems = [room[s] - sum(heights[i] for i in assign[s]) for s in names]
        over = sum(max(0.0, r - 25) for r in rems)
        return (max(rems), over, round(sum(rems), 1))

    def dfs(i):
        nonlocal best
        if i == len(pool):
            laid = layout(assign)
            if not laid:
                return
            sc = score()
            if best is None or sc < best[0]:
                best = (sc, laid)
            return
        it = pool[i]
        h = heights[it["id"]]
        k = it["kicker"]
        for slot in names:
            used = sum(heights[n] for n in assign[slot])
            if used + h > room[slot] - 1.5:
                continue
            if any(by[n]["kicker"] == k for n in assign[slot]):
                continue
            pg = page[slot]
            if any(by[n]["kicker"] == k for s in names if page[s] == pg for n in assign[s]):
                continue
            assign[slot].append(it["id"])
            dfs(i + 1)
            assign[slot].pop()

    dfs(0)
    if not best:
        return {}
    print(f"packed tails, largest remainder {best[0][0]:.0f}mm")
    return best[1]

def compose_fillers(it, d):
    """Place досыпки into spare column tails. Never grows the page count."""
    fillers = load_fillers(it["date"])
    if not fillers or not is_weekly(it):
        return None
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("WARN: playwright not installed, fillers skipped", it["date"]); return None
    heights = _measure_filler_heights(fillers)
    norms = {it["id"]: _filler_norm(it) for it in fillers}
    print("filler heights mm:", {k: round(v, 1) for k, v in heights.items()})
    pdf = os.path.join(d, f"solaris-times-{it['date']}.pdf")
    html_path = os.path.join(d, "print.html")
    titles = _editorial_titles(it)
    open(html_path, "w", encoding="utf-8").write(print_html(it, with_slots=True))
    _pdf_html(html_path, pdf)
    base = _analyze_pdf(pdf)
    baseline = base["pages"]
    base_anchors = _anchor_pages(base["texts"], titles)
    print(f"baseline {baseline} pages, anchors {len(base_anchors)}/{len(titles)}")
    for g in base["gaps"]:
        print(f"  p{g['page']} L {g['left']:.0f} R {g['right']:.0f}")
    holes = [{"slot": s, "page": mk["page"], "side": mk["side"], "room": mk["room"], "y0": mk["y0"]}
             for s, mk in base["marks"].items() if mk["room"] >= _GAP_MIN]
    holes.sort(key=lambda h: (h["page"], h["side"] == "R", h["y0"]))
    print("holes:", [(h["slot"], h["page"], h["side"], round(h["room"])) for h in holes])
    assignment = _pack_fillers(holes, fillers, heights, norms)
    # Confirm the whole set still fits the tails it was measured for.
    open(html_path, "w", encoding="utf-8").write(print_html(it, assignment, with_slots=True))
    _pdf_html(html_path, pdf)
    check = _analyze_pdf(pdf)
    anchors = _anchor_pages(check["texts"], titles)
    moved = [t for t, pg in base_anchors.items() if anchors.get(t, 99) > pg]
    missed = []
    hole_at = {h["slot"]: h for h in holes}
    for slot, items in assignment.items():
        for item in items:
            a = check["ids"].get("A" + item["id"])
            z = check["ids"].get("Z" + item["id"])
            want = hole_at[slot]
            if (not a or not z or a["page"] != want["page"] or a["side"] != want["side"]
                    or z["page"] != a["page"] or z["side"] != a["side"] or z["y0"] + 1 < a["y0"]):
                missed.append(item["id"])
    if check["pages"] > baseline or moved or missed:
        print("pack missed the tails", missed, "moved", len(moved), "pages", check["pages"])
        assignment = {}
    placed_at = []
    for slot, items in assignment.items():
        h = hole_at[slot]
        for item in items:
            placed_at.append({
                "id": item["id"], "kicker": item["kicker"], "title": item.get("title") or "",
                "topic": item.get("topic") or "", "page": h["page"], "side": h["side"],
            })
            print(f"  put {item['id']} slot {slot} → p{h['page']}{h['side']}")
    # Drop the measurement marks. Sources stay in the JSON and are not rendered.
    open(html_path, "w", encoding="utf-8").write(print_html(it, assignment, with_slots=True, strip_marks=True))
    _pdf_html(html_path, pdf)
    final = _analyze_pdf(pdf)
    print(f"filled PDF: {final['pages']} pages (baseline {baseline})")
    for g in final["gaps"]:
        print(f"  p{g['page']} L {g['left']:.0f}mm  R {g['right']:.0f}mm")
    used = {item["id"] for items in assignment.values() for item in items}
    unused = [it["id"] for it in fillers if it["id"] not in used]
    print("unused:", unused)
    return assignment, final["gaps"], final["pages"], placed_at

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
        if "--no-pdf" not in sys.argv:
            if is_weekly(it) and load_fillers(it["date"]):
                compose_fillers(it, d)
            else:
                make_pdf(d, it["date"])
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
