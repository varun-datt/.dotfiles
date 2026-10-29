"""Draw cloud diagrams as inline SVG inside one self-contained HTML page.

Import it from a small build script written for the diagram at hand:

    import sys; sys.path.insert(0, "<skill>/scripts")
    from diagram_kit import Kit, page
    kit = Kit("icons/", {"s3": "Res_Amazon-Simple-Storage-Service_Bucket_48.svg"})
    svg = kit.svg(1240, 300, "What it shows", [kit.img(80, 120, "s3"), kit.txt(80, 164, "orders bucket")])
    Path("out.html").write_text(page("Title", f"<h1>Title</h1><section>{svg}</section>"))
"""
import base64
import html
from pathlib import Path

INK = "oklch(0.400 0.110 250.0)"

CSS = """
  :root { --paper:#fbfaf7; --card:#ffffff; --text:#1c1f24; --muted:#535a66; --line:#d6d9e0; --code:#f3f4f7;
    --ink:oklch(0.400 0.110 250.0); --gold:oklch(0.650 0.146 60.0); --gold-tint:oklch(0.955 0.045 80);
    --today:oklch(0.945 0.030 250); }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--paper); color:var(--text);
    font:15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  main { width:1280px; margin:0 auto; padding:28px 0 36px; }
  h1 { font-size:24px; margin:0 0 4px; color:var(--ink); }
  h2 { font-size:17px; margin:0 0 10px; color:var(--ink); }
  .key { color:var(--muted); font-size:13px; margin-bottom:20px; }
  section { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:18px 20px; margin-bottom:18px; }
  code { font:12.5px ui-monospace, SFMono-Regular, Menlo, monospace; }
  svg text { font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; fill:var(--text); }
  svg .t { font-size:13px; font-weight:600; }
  svg .s { font-size:11.5px; fill:var(--muted); }
  svg .m { font:11px ui-monospace, SFMono-Regular, Menlo, monospace; fill:var(--muted); }
  svg .h { font-size:12.5px; font-weight:700; fill:var(--ink); }
  svg .arr { stroke:var(--ink); stroke-width:1.6; fill:none; }
  svg .dash { stroke-dasharray:5 4; }
  svg .dot { stroke:var(--muted); stroke-width:1.2; stroke-dasharray:2 3; fill:none; }
  svg .acct { fill:none; stroke:var(--line); stroke-width:1.5; }
  svg .grid { stroke:var(--line); stroke-width:1; }
  svg .pill { fill:var(--code); stroke:var(--line); }
  svg .gold { fill:var(--gold-tint); stroke:var(--gold); }
  svg .band { fill:var(--gold-tint); }
  svg .chip { fill:var(--card); stroke:var(--line); }
  svg .chipdev { fill:var(--gold-tint); stroke:var(--gold); }
  svg .chiptrial { fill:var(--card); stroke:var(--ink); stroke-dasharray:4 3; }
  svg .num circle { fill:var(--ink); }
  svg .num text { fill:#fff; font-size:12px; font-weight:700; }
  ol.steps { margin:10px 0 0; padding-left:22px; font-size:14px; }
  ol.steps li { margin-bottom:4px; }
  .legend { display:flex; flex-wrap:wrap; gap:16px; font-size:13px; color:var(--muted); margin-top:10px; align-items:center; }
  .legend img { width:22px; height:22px; vertical-align:middle; margin-right:5px; }
  .sw { display:inline-block; width:22px; height:14px; vertical-align:middle; margin-right:5px; border-radius:3px; }
  .sw.dev { background:var(--gold-tint); border:1.5px solid var(--gold); }
  .sw.trial { border:1.5px dashed var(--ink); }
  .sw.today { background:var(--today); border:1px solid var(--line); }
  .facts { font-size:13.5px; margin:0; padding-left:18px; }
  .legend + .facts { margin-top:12px; }
  .facts li { margin-bottom:4px; }
  .gloss { display:grid; grid-template-columns:repeat(3, 1fr); gap:10px 22px; font-size:13px; margin-top:12px; }
  .gloss div { display:flex; gap:9px; align-items:flex-start; }
  .gloss img { width:28px; height:28px; flex:none; }
  .gloss b { color:var(--ink); }
  table.m { border-collapse:collapse; width:100%; font-size:14px; table-layout:fixed; }
  table.m th { text-align:left; font-size:13px; color:var(--muted); padding:7px 8px; border-bottom:2px solid var(--line); }
  table.m td { padding:8px; border-top:1px solid var(--line); vertical-align:top; }
  table.m td:first-child, table.m th:first-child { width:250px; font-weight:600; }
  table.m td img { width:22px; height:22px; vertical-align:middle; margin-right:6px; }
  td.none { color:var(--muted); }
  td.today { background:var(--today); }
  .bd { display:inline-block; font-size:11px; font-weight:700; border-radius:9px; padding:0 7px; margin-right:6px; vertical-align:1px; }
  .bd.today { color:var(--ink); background:var(--card); border:1px solid var(--line); }
  .bd.new { color:var(--ink); border:1.5px solid var(--ink); }
  .src { font-size:12.5px; color:var(--muted); margin-top:10px; }
"""

THEME_JS = """
<script>
  window.addEventListener('message', (event) => {
    if (event.source !== window.parent) return;
    const m = event.data;
    if (!m || m.type !== '%s' || !m.tokens) return;
    const r = document.documentElement.style;
    if (m.tokens.text) r.setProperty('--text', m.tokens.text);
    if (m.tokens.paper) { r.setProperty('--paper', m.tokens.paper); r.setProperty('--card', m.tokens.paper); }
    if (m.tokens.accent) r.setProperty('--ink', m.tokens.accent);
    if (m.tokens.line) r.setProperty('--line', m.tokens.line);
    const dark = m.theme === 'dark';
    r.setProperty('--muted', dark ? '#a9afba' : '#535a66');
    r.setProperty('--code', dark ? 'rgba(255,255,255,0.06)' : '#f3f4f7');
    r.setProperty('--gold-tint', dark ? 'oklch(0.34 0.06 70)' : 'oklch(0.955 0.045 80)');
    r.setProperty('--today', dark ? 'oklch(0.32 0.04 250)' : 'oklch(0.945 0.030 250)');
  });
</script>
"""

DEFS = (f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker></defs>')


class Kit:
    """SVG primitives that place official icons and short labels by coordinates."""

    def __init__(self, icon_dir, names):
        folder = Path(icon_dir)
        self.uri = {k: "data:image/svg+xml;base64," + base64.b64encode((folder / f).read_bytes()).decode()
                    for k, f in names.items()}

    def img(self, x, y, key, size=44):
        return f'<image href="{self.uri[key]}" x="{x - size / 2}" y="{y - size / 2}" width="{size}" height="{size}"/>'

    @staticmethod
    def txt(x, y, s, cls="t", anchor="middle"):
        return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{html.escape(s)}</text>'

    @staticmethod
    def line(x1, y1, x2, y2, cls="arr", head=True):
        m = ' marker-end="url(#ah)"' if head else ""
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{cls}"{m}/>'

    @staticmethod
    def path(d, cls="arr", head=True):
        m = ' marker-end="url(#ah)"' if head else ""
        return f'<path d="{d}" class="{cls}"{m}/>'

    @staticmethod
    def num(x, y, n):
        return (f'<g class="num"><circle cx="{x}" cy="{y}" r="11"/>'
                f'<text x="{x}" y="{y + 4}" text-anchor="middle">{n}</text></g>')

    @staticmethod
    def box(x, y, w, h, cls="acct", rx=10):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" class="{cls}"/>'

    def chip(self, cx, y, label, kind="chip"):
        w = 16 + 6.4 * len(label)
        return self.box(round(cx - w / 2), y - 12, round(w), 24, kind, 12) + self.txt(cx, y + 4, label, "s")

    def legend_item(self, key, label):
        return f'<span><img src="{self.uri[key]}" alt="">{html.escape(label)}</span>'

    def gloss_item(self, key, name, plain):
        return f'<div><img src="{self.uri[key]}" alt=""><span><b>{html.escape(name)}</b>: {html.escape(plain)}</span></div>'

    @staticmethod
    def svg(width, height, label, parts):
        head = f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{html.escape(label)}">'
        return "\n".join([head, DEFS, *parts, "</svg>"])


def page(title, body, meta=None, theme_message=None):
    """One self-contained page; `meta` becomes <meta name="key"> tags, `theme_message` adds a host theme listener."""
    tags = "".join(f'<meta name="{html.escape(k)}" content="{html.escape(v)}">\n' for k, v in (meta or {}).items())
    theme = THEME_JS % theme_message if theme_message else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
{tags}<style>{CSS}</style>
</head>
<body>
<main>
{body}
</main>
{theme}</body>
</html>
"""
