#!/usr/bin/env python3
"""Draw a run's timeline, or export a project's timeline and spend by day into its archive folder.

Usage:
    python3 timeline.py [--run DIR] --out FILE [--skills REPO]   one run's timeline page
    python3 timeline.py [--run DIR] --export [--skills REPO]     the project's timeline.html and spend-by-day.md,
                                                                 written into the run's archive folder

A project is every registered run whose orchestrator.json names the same archive folder
(`state.py init --archive FOLDER`). The page is self-contained: one row per item, one bar per round
coloured and patterned by kind, a diamond at each merge, a strip of workers running at once, and the
machine's sleep. Times are in this machine's local zone. It takes its theme from a host page by a
`message` event whose data carries `theme` ('light' or 'dark') and optional `tokens`, whatever its
`type`; otherwise it follows `prefers-color-scheme`.

Sources (all read-only):
  mine.py --json     rounds and days per run; spend is taken from it, never recomputed
  orchestrator.json  title, repo and archive of each run; the registry (OW_REGISTRY) lists the runs
  git log --merges --first-parent   of each repo the runs name; an item is merged as mine.py counts it
  <run>/<name>.jsonl a round ends at its last event timestamp; with none, start + wall_min
  pmset -g log       machine asleep, macOS only; elsewhere or on failure the page says it is unknown
  --skills REPO      optional: merges to that repository's HEAD, drawn as their own row

Environment: OW_RUN_DIR (default run folder) and OW_REGISTRY (run registry), as state.py reads them.
--export rewrites only those two files. Exit 2 when the run names no archive folder; 1 on any other failure.
"""
import argparse, collections, datetime, html, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mine, state  # noqa: E402

MINE = os.path.join(HERE, 'mine.py')
MIN_SLEEP_MIN = 5
TIMELINE, SPEND = 'timeline.html', 'spend-by-day.md'


class Refused(Exception):
    pass


class NoArchive(Exception):
    pass


def parse_time(text):
    try:
        t = datetime.datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return None
    return t if t.tzinfo else t.astimezone()


def last_event_time(path):
    try:
        f = open(path, 'rb')
    except FileNotFoundError:
        return None
    with f:
        f.seek(0, 2)
        pos, tail = f.tell(), b''
        while pos > 0:
            step = min(1 << 16, pos)
            pos -= step
            f.seek(pos)
            tail = f.read(step) + tail
            lines = tail.split(b'\n')
            tail = lines[0] if pos > 0 else b''
            for raw in reversed(lines[1:] if pos > 0 else lines):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(obj, dict) and obj.get('timestamp'):
                    t = parse_time(obj['timestamp'])
                    if t:
                        return t
    return None


def sleep_gaps(lo, hi):
    if sys.platform != 'darwin':
        return None
    try:
        out = subprocess.run(['pmset', '-g', 'log'], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    line = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4}) (Sleep|Wake)\s{2,}')
    gaps, asleep = [], None
    for ln in out.splitlines():
        m = line.match(ln)
        if not m:
            continue
        t = datetime.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S %z')
        if m.group(2) == 'Sleep':
            asleep = asleep or t
        elif asleep:
            if (t - asleep).total_seconds() >= MIN_SLEEP_MIN * 60 and t > lo and asleep < hi:
                gaps.append((max(asleep, lo), min(t, hi)))
            asleep = None
    return gaps


def orchestrator(run):
    try:
        _, doc = state.load(run)
    except state.Refused as e:
        raise Refused(str(e))
    o = (doc or {}).get('orchestrator')
    return o if isinstance(o, dict) else {}


def project_runs(run, archive):
    real, runs = os.path.realpath(archive), [os.path.realpath(run)]
    try:
        with open(state.registry_path(), encoding='utf-8') as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []
    for raw in lines:
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        d = e.get('dir') if isinstance(e, dict) else None
        if not isinstance(d, str) or not os.path.isdir(d) or os.path.realpath(d) in runs:
            continue
        try:
            o = orchestrator(d)
        except Refused:
            continue
        if isinstance(o.get('archive'), str) and os.path.realpath(o['archive']) == real:
            runs.append(os.path.realpath(d))
    return runs


def mined(run):
    p = subprocess.run([sys.executable, MINE, run, '--json'], capture_output=True, text=True)
    if p.returncode != 0:
        raise Refused(f"mine.py failed for {run}: {' '.join(p.stderr.split())}")
    return json.loads(p.stdout)


def midnight(day):
    return datetime.datetime.combine(day, datetime.time()).astimezone()


def collect(runs):
    rounds, days, repos = [], {}, []
    for run in runs:
        o = orchestrator(run)
        title = o.get('title') or os.path.basename(run)
        if isinstance(o.get('repo'), str) and o['repo']:
            repo = os.path.abspath(os.path.expanduser(o['repo']))
            if repo not in repos:
                repos.append(repo)
        m = mined(run)
        for d in m['days']:
            day = days.setdefault(d['day'], {'day': d['day'], 'rounds': 0, 'credits': 0.0, 'capped': 0, 'unknown': 0, 'kinds': {}})
            day['rounds'] += d['rounds']
            day['credits'] += d['credits']
            day['capped'] += d['capped']
        for r in m['rounds']:
            r['run'], r['dir'] = title, run
            r['startT'] = parse_time(r['start'])
            day = days[r['startT'].astimezone().date().isoformat()]
            k = day['kinds'].setdefault(r['kind'], [0.0, 0, 0])
            k[2] += 1
            if r['credits'] is None:
                day['unknown'] += 1
                k[1] += 1
            else:
                k[0] += r['credits']
            rounds.append(r)
    rows = []
    for repo in repos:
        try:
            rows.append(mine.merges(repo))
        except (OSError, RuntimeError) as e:
            print(f'timeline.py: merges from {repo} unknown: {e}', file=sys.stderr)
    return rounds, [days[k] for k in sorted(days)], rows


def page(runs, title, skills_repo=None):
    rounds_in, days, merge_rows = collect(runs)
    if days:
        first, last = datetime.date.fromisoformat(days[0]['day']), datetime.date.fromisoformat(days[-1]['day'])
    else:
        first = last = datetime.date.today()
    t0, t1 = midnight(first), midnight(last + datetime.timedelta(days=1))

    def mins(t):
        return round((t - t0).total_seconds() / 60, 2)

    def local(t):
        return t.astimezone().strftime('%Y-%m-%d %H:%M')

    mid, zones, d = [], [], first
    while d <= last:
        md = midnight(d)
        mid.append([mins(md), d.isoformat()])
        z = md.strftime('%Z') or md.strftime('UTC%z')
        if z not in zones:
            zones.append(z)
        d += datetime.timedelta(days=1)
    tz = '/'.join(zones)
    off = t0.strftime('%z')
    zone = f'{tz} (UTC{off[:3]}:{off[3:]} at the start)'
    for day in days:
        dd = datetime.date.fromisoformat(day['day'])
        day['lo'], day['hi'] = mins(midnight(dd)), mins(midnight(dd + datetime.timedelta(days=1)))

    rounds = []
    for r in rounds_in:
        start = r['startT']
        end, end_from = last_event_time(os.path.join(r['dir'], r['name'] + '.jsonl')), 'last event'
        if end is None and r.get('wall_min') is not None:
            end, end_from = start + datetime.timedelta(minutes=r['wall_min']), 'start + wall time'
        elif end is None:
            end, end_from = start, 'unknown'
        outcome = ('capped' if r.get('capped') else 'errored' if r.get('error')
                   else 'died' if not r.get('ended') else 'done')
        kind = {'catchup': 'merge'}.get(r['kind'], r['kind'])
        rounds.append(dict(name=r['name'], item=r['item'], run=r['run'], kind=kind, rawkind=r['kind'],
                           model=r.get('model'), effort=r.get('effort'), credits=r.get('credits'),
                           wall=r.get('wall_min'), s=mins(start), e=mins(max(end, start)),
                           sl=local(start), el=local(end), endFrom=end_from, outcome=outcome))

    first_seen = {}
    for r in sorted(rounds, key=lambda r: r['s']):
        first_seen.setdefault(r['item'], r['s'])
    items = sorted(first_seen, key=first_seen.get)
    merges = []
    for it in items:
        ts = sorted(t for t in (parse_time(w) for w in (mine.merged_at(it, rows) for rows in merge_rows) if w) if t)
        if ts:
            merges.append(dict(item=it, t=mins(ts[0]), tl=local(ts[0])))

    skills = []
    if skills_repo:
        out = subprocess.run(['git', '-C', skills_repo, 'log', '--merges', '--first-parent', '--format=%H %cI %s', 'HEAD'],
                             capture_output=True, text=True)
        if out.returncode != 0:
            raise Refused(f"--skills: {' '.join(out.stderr.split()) or 'git log failed'}")
        for ln in out.stdout.splitlines():
            sha, when, subject = (ln.split(' ', 2) + ['', ''])[:3]
            t = parse_time(when)
            if t and t0 <= t < t1:
                skills.append(dict(sha=sha[:9], subject=subject, t=mins(t), tl=local(t)))
        skills.sort(key=lambda m: m['t'])

    gaps = sleep_gaps(t0, t1)
    if gaps is not None:
        gaps = [dict(s=mins(s), e=mins(e), sl=local(s), el=local(e)) for s, e in gaps]

    total = int(mins(t1))
    conc = [0] * total
    for r in rounds:
        for m in range(max(0, int(r['s'])), min(total, int(r['e']) + (r['e'] > int(r['e'])))):
            conc[m] += 1

    shown = [{k: v for k, v in d.items() if k != 'kinds'} for d in days]
    full = f'{title}: workers over time, {first} to {last}' if days else f'{title}: no rounds yet'
    data = dict(title=full, zone=zone, tz=tz, whole='Whole project' if len(runs) > 1 else 'Whole run', runs=len(runs),
                days=shown, mid=mid, defaultDay=days[-1]['day'] if days else None, total=total, rounds=rounds,
                items=items, merges=merges, skillsFrom=bool(skills_repo), skills=skills, gaps=gaps, conc=conc,
                creditTotal=round(sum(d['credits'] for d in days), 2),
                unknownTotal=sum(r['credits'] is None for r in rounds))
    payload = json.dumps(data, separators=(',', ':')).replace('</', '<\\/')
    text = (PAGE.replace('__TITLE__', html.escape(full)).replace('__ZONE__', html.escape(zone))
            .replace('__DATA__', payload))
    return text, data, days


def credits(c, unknown, n, dollars=False):
    if n and unknown == n:
        return 'unknown'
    shown = f'${c / 100:,.2f}' if dollars else f'{c:,.1f}'
    return shown + (f' + unknown ({unknown} round{"s" if unknown != 1 else ""})' if unknown else '')


def spend_md(title, days, zone):
    lines = [f'# Spend by day: {title}', '',
             f'Credits from `mine.py --json`; list price at 1 credit = $0.01. Days in the local zone, {zone}. Newest first.', '',
             '| Day | Credits | List price | Rounds | Credits by kind |', '|---|---:|---:|---:|---|']
    for d in sorted(days, key=lambda d: d['day'], reverse=True):
        kinds = '; '.join(f'{k} {credits(*v)}' for k, v in sorted(d['kinds'].items()))
        lines.append(f"| {d['day']} | {credits(d['credits'], d['unknown'], d['rounds'])} | "
                     f"{credits(d['credits'], d['unknown'], d['rounds'], dollars=True)} | {d['rounds']} | {kinds} |")
    return '\n'.join(lines) + '\n'


def write(target, text):
    state.regular_or_absent(target, 'the output')
    state.write_atomic(target, text)
    return len(text.encode('utf-8'))


def project_title(runs):
    titles = []
    for run in runs:
        t = orchestrator(run).get('title') or os.path.basename(run)
        if t not in titles:
            titles.append(t)
    return '; '.join(titles) if len(titles) <= 2 else f'{titles[0]} and {len(titles) - 1} more runs'


def main(argv=None):
    ap = argparse.ArgumentParser(description="Draw a run's timeline, or export its project's timeline and spend by day.")
    ap.add_argument('--run', help='run folder (default: $OW_RUN_DIR)')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--out', help="write this run's timeline page to this file")
    g.add_argument('--export', action='store_true', help="write the project's timeline.html and spend-by-day.md into its archive folder")
    ap.add_argument('--skills', help='a repository whose merges to HEAD are drawn as their own row')
    a = ap.parse_args(argv)
    run = state.run_dir(a.run)
    try:
        if not os.path.isdir(run):
            raise Refused(f'no run folder at {run}')
        if a.export:
            archive = orchestrator(run).get('archive')
            if not isinstance(archive, str) or not os.path.isdir(archive):
                raise NoArchive(f'the run {run} names no existing archive folder; set one with `state.py --run {run} init --archive FOLDER`')
            runs = project_runs(run, archive)
            title = project_title(runs)
            text, data, days = page(runs, title, a.skills)
            target = os.path.join(archive, TIMELINE)
            n = write(target, text)
            print(f"wrote {target}: {n:,} bytes, {len(runs)} run(s), {len(data['items'])} items, "
                  f"{len(data['rounds'])} rounds, {len(data['merges'])} merged")
            target = os.path.join(archive, SPEND)
            n = write(target, spend_md(title, days, data['zone']))
            print(f'wrote {target}: {n:,} bytes, {len(days)} days')
        else:
            out = os.path.abspath(os.path.expanduser(a.out))
            text, data, _ = page([os.path.realpath(run)], project_title([run]), a.skills)
            n = write(out, text)
            print(f"wrote {out}: {n:,} bytes, {len(data['items'])} items, {len(data['rounds'])} rounds, {len(data['merges'])} merged")
    except NoArchive as e:
        print(f'timeline.py: {e}', file=sys.stderr)
        return 2
    except (Refused, state.Refused, OSError, ValueError) as e:
        print(f"timeline.py: {' '.join(str(e).split())}", file=sys.stderr)
        return 1
    return 0


PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  --ink:oklch(0.400 0.110 250.0);--gold:oklch(0.650 0.146 60.0);
  --paper:oklch(0.985 0.004 85);--text:oklch(0.240 0.030 250);--accent:var(--gold);--line:oklch(0.850 0.010 250);
  --muted:color-mix(in oklch,var(--text) 78%,var(--paper));
  --k-build:var(--ink);--k-review:oklch(0.600 0.140 60);--k-rereview:oklch(0.520 0.120 75);
  --k-fix:oklch(0.540 0.150 30);--k-resume:oklch(0.520 0.070 200);--k-merge:oklch(0.520 0.120 150);
  --k-research:oklch(0.480 0.040 90);--k-other:oklch(0.550 0.010 250);
  --sleep:color-mix(in oklch,var(--text) 10%,transparent);
  color-scheme:light;
}
:root[data-theme=dark]{
  --paper:oklch(0.205 0.020 250);--text:oklch(0.930 0.010 85);--accent:oklch(0.760 0.140 65);--line:oklch(0.360 0.020 250);
  --k-build:oklch(0.620 0.120 250);--k-review:oklch(0.720 0.140 65);--k-rereview:oklch(0.640 0.110 80);
  --k-fix:oklch(0.640 0.150 30);--k-resume:oklch(0.640 0.070 200);--k-merge:oklch(0.650 0.120 150);
  --k-research:oklch(0.600 0.040 90);--k-other:oklch(0.620 0.010 250);
  color-scheme:dark;
}
*{box-sizing:border-box}
body{margin:0;padding:12px 14px;background:var(--paper);color:var(--text);
  font:13px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
h1{font-size:16px;margin:0 0 2px}
.sub{color:var(--muted);margin:0 0 8px}
.bar{display:flex;flex-wrap:wrap;gap:4px;align-items:center;margin:6px 0}
button{font:inherit;color:var(--text);background:transparent;border:1px solid var(--line);border-radius:4px;padding:2px 8px;cursor:pointer}
button[aria-pressed=true]{background:var(--ink);border-color:var(--ink);color:oklch(0.985 0.004 85)}
:root[data-theme=dark] button[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:oklch(0.180 0.020 250)}
button:focus-visible,[tabindex]:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
ul.days{list-style:none;margin:4px 0 8px;padding:0;font-variant-numeric:tabular-nums}
ul.days li{padding:1px 0}
ul.days li.on{font-weight:600}
ul.days li.on::before{content:"\25B8 ";color:var(--accent)}
.legend{display:flex;flex-wrap:wrap;gap:4px 12px;margin:4px 0;color:var(--text)}
.legend span{display:inline-flex;align-items:center;gap:4px}
.legend svg{vertical-align:middle}
#chart{width:100%;overflow-x:auto}
#chart svg{display:block;width:100%;min-width:760px;height:auto}
svg text{fill:var(--text);font-size:10.5px}
svg .muted{fill:var(--muted)}
.grid{stroke:var(--line);stroke-width:1}
.rnd{stroke:var(--paper);stroke-width:.5}
.rnd.died,.rnd.errored,.rnd.capped{stroke:var(--text);stroke-width:1.2;stroke-dasharray:3 2}
.rnd:hover,.rnd:focus,.mk:hover,.mk:focus{stroke:var(--accent);stroke-width:2;stroke-dasharray:none;outline:none}
.diamond{fill:var(--accent);stroke:var(--text);stroke-width:1}
.skill{fill:var(--paper);stroke:var(--k-build);stroke-width:2}
.conc{fill:var(--k-build)}
#tip{position:fixed;z-index:5;pointer-events:none;max-width:340px;background:var(--paper);color:var(--text);
  border:1px solid var(--text);border-radius:4px;padding:5px 7px;font-size:12px;display:none;box-shadow:0 2px 6px rgb(0 0 0/.2)}
#tip b{display:block}
details{margin-top:10px}
summary{cursor:pointer;font-weight:600}
table{border-collapse:collapse;font-size:12px;margin:6px 0 12px;font-variant-numeric:tabular-nums}
th,td{border-bottom:1px solid var(--line);padding:2px 6px;text-align:left;vertical-align:top}
td.n{text-align:right}
caption{text-align:left;font-weight:600;padding:4px 0}
.note{color:var(--muted);font-size:12px}
</style>
</head>
<body>
<h1 id="title">__TITLE__</h1>
<p class="sub">All times are this machine's local zone, __ZONE__. Each bar is one worker round; each row one item. Credits shown with dollars at list price, 1 credit = $0.01.</p>
<div class="bar" id="view" role="group" aria-label="Choose a day or the whole run"></div>
<ul class="days" id="days" aria-label="Per-day summary"></ul>
<div class="legend" id="legend" aria-label="Legend"></div>
<div id="chart"></div>
<div id="tip" role="tooltip"></div>
<p class="note">Bars run from a round's start to its last logged event. Dashed outline: the round died (no exit recorded), errored or hit its credit cap. <span id="sleepnote">Shaded bands: the machine was asleep.</span> Top strip: workers running at once, per minute.</p>
<details id="data">
<summary>Show data</summary>
<div id="tables"></div>
</details>
<script>
(function(){
"use strict";
var D=__DATA__;
var KINDS=[["build","build","solid"],["review","review","diagonal stripes"],["rereview","re-review","cross-hatch"],
  ["fix","fix","horizontal stripes"],["resume","resume","dots"],["merge","catch-up or merge","vertical stripes"],
  ["research","research","wide diagonal"],["other","other (continues a session)","checks"]];
var KLAB={};KINDS.forEach(function(k){KLAB[k[0]]=k[1];});
var view=D.defaultDay||"all";
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
function num(x,d){return x==null?"unknown":x.toLocaleString("en-US",{minimumFractionDigits:d,maximumFractionDigits:d});}
function money(c){return c==null?"unknown":"$"+num(c/100,2);}
function spend(c,u,n,dg){if(n&&u===n)return "unknown credits (list price unknown)";return num(c,dg)+" credits"+(u?" + "+u+" round"+(u===1?"":"s")+" unknown":"")+" ("+money(c)+" list price"+(u?" + unknown":"")+")";}
function hm(t){return t.slice(11);}
function outcomeText(o){return {done:"done",errored:"errored",died:"died (no exit recorded)",capped:"capped (hit its credit cap)"}[o];}
function dayIndex(d){for(var i=0;i<D.days.length;i++)if(D.days[i].day===d)return i;return -1;}
function range(){if(view==="all")return[0,D.total];var d=D.days[dayIndex(view)];return[d.lo,d.hi];}

/* patterns: kind never relies on colour alone */
function patterns(){
  var p={solid:"",
    "diagonal stripes":'<path d="M-1,1 l2,-2 M0,6 l6,-6 M5,7 l2,-2" stroke="var(--paper)" stroke-width="1.3" stroke-opacity=".7"/>',
    "cross-hatch":'<path d="M0,6 l6,-6 M0,0 l6,6" stroke="var(--paper)" stroke-width="1" stroke-opacity=".7"/>',
    "horizontal stripes":'<path d="M0,1.5 h6 M0,4.5 h6" stroke="var(--paper)" stroke-width="1" stroke-opacity=".7"/>',
    dots:'<circle cx="1.5" cy="1.5" r="1" fill="var(--paper)" fill-opacity=".8"/><circle cx="4.5" cy="4.5" r="1" fill="var(--paper)" fill-opacity=".8"/>',
    "vertical stripes":'<path d="M1.5,0 v6 M4.5,0 v6" stroke="var(--paper)" stroke-width="1.2" stroke-opacity=".7"/>',
    "wide diagonal":'<path d="M0,6 l6,-6" stroke="var(--paper)" stroke-width="2.2" stroke-opacity=".7"/>',
    checks:'<rect width="3" height="3" fill="var(--paper)" fill-opacity=".6"/><rect x="3" y="3" width="3" height="3" fill="var(--paper)" fill-opacity=".6"/>'};
  return KINDS.map(function(k){return '<pattern id="p-'+k[0]+'" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="var(--k-'+k[0]+')"/>'+p[k[2]]+'</pattern>';}).join("")+
    '<pattern id="p-sleep" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="var(--sleep)"/><path d="M0,8 l8,-8" stroke="var(--muted)" stroke-width=".6" stroke-opacity=".5"/></pattern>';
}

function legend(){
  var h=KINDS.map(function(k){return '<span><svg width="22" height="12" aria-hidden="true"><defs>'+patterns()+'</defs><rect width="22" height="12" fill="url(#p-'+k[0]+')"/></svg>'+esc(k[1])+' <span class="note">('+k[2]+')</span></span>';}).join("");
  h+='<span><svg width="12" height="12" aria-hidden="true"><path class="diamond" d="M6,1 L11,6 L6,11 L1,6Z"/></svg>merge to main</span>';
  if(D.skillsFrom)h+='<span><svg width="12" height="12" aria-hidden="true"><path class="skill" d="M6,1.5 L11,10.5 L1,10.5Z"/></svg>skill merge</span>';
  h+='<span><svg width="22" height="12" aria-hidden="true"><defs>'+patterns()+'</defs><rect width="22" height="12" fill="url(#p-sleep)"/></svg>machine asleep</span>';
  document.getElementById("legend").innerHTML=h;
}

function controls(){
  var b=D.days.map(function(d){return '<button type="button" data-v="'+d.day+'">'+d.day+'</button>';}).join("")+'<button type="button" data-v="all">'+esc(D.whole)+'</button>';
  var el=document.getElementById("view");el.innerHTML=b;
  el.addEventListener("click",function(e){var t=e.target.closest("button");if(t){view=t.getAttribute("data-v");render();}});
}

function merges(lo,hi,day){return D.merges.filter(function(m){return m.t>=lo&&m.t<hi;}).length;}
function skillsIn(lo,hi){return D.skills.filter(function(m){return m.t>=lo&&m.t<hi;}).length;}
function daysList(){
  var h=D.days.map(function(d){var lo=d.lo,hi=d.hi;var m=merges(lo,hi),s=skillsIn(lo,hi);
    return '<li class="'+(view===d.day?"on":"")+'">'+d.day+': '+d.rounds+' rounds, '+spend(d.credits,d.unknown,d.rounds,0)+', '+m+' merge'+(m===1?"":"s")+' to main'+(s?', '+s+' skill merge'+(s===1?"":"s"):"")+(d.capped?', '+d.capped+' capped':"")+'</li>';}).join("");
  var R=D.rounds.length;
  h+='<li class="'+(view==="all"?"on":"")+'">'+esc(D.whole)+': '+R+' rounds, '+spend(D.creditTotal,D.unknownTotal,R,1)+', '+D.merges.length+' merges to main, '+D.skills.length+' skill merges</li>';
  document.getElementById("days").innerHTML=h;
}

/* lanes inside an item so overlapping rounds stay visible */
var LANES={};
(function(){var by={};D.rounds.forEach(function(r,i){r.i=i;(by[r.item]=by[r.item]||[]).push(r);});
  Object.keys(by).forEach(function(it){var ends=[];by[it].sort(function(a,b){return a.s-b.s;}).forEach(function(r){
    var l=0;while(l<ends.length&&ends[l]>r.s)l++;ends[l]=Math.max(r.e,r.s+1);r.lane=l;});LANES[it]=Math.max(1,ends.length);});})();

function tipFor(r){
  return '<b>'+esc(r.name)+'</b>'+esc(KLAB[r.kind])+(r.rawkind==="catchup"?" (catch-up)":r.rawkind==="merge"?" (merge)":"")+' &middot; item '+esc(r.item)+(D.runs>1?' &middot; run '+esc(r.run):"")+
    '<br>model '+esc(r.model||"unknown")+' &middot; reasoning effort '+esc(r.effort||"unknown")+
    '<br>'+num(r.credits,1)+' credits = '+money(r.credits)+' (list price, 1 credit = $0.01)'+
    '<br>wall time '+(r.wall==null?"unknown":num(r.wall,1)+' min')+' &middot; '+esc(r.sl)+' to '+esc(hm(r.el))+' '+esc(D.tz)+''+(r.endFrom!=="last event"?' (end from '+esc(r.endFrom)+')':"")+
    '<br>outcome: '+outcomeText(r.outcome);
}
function labelFor(r){return r.name+", "+KLAB[r.kind]+", model "+(r.model||"unknown")+", reasoning effort "+(r.effort||"unknown")+", "+num(r.credits,1)+" credits, "+money(r.credits)+" list price at 1 credit = $0.01, wall time "+(r.wall==null?"unknown":num(r.wall,1)+" minutes")+", "+r.sl+" to "+hm(r.el)+" "+D.tz+", outcome "+outcomeText(r.outcome);}

var TIPS=[];
function render(){
  document.querySelectorAll("#view button").forEach(function(b){b.setAttribute("aria-pressed",String(b.getAttribute("data-v")===view));});
  daysList();
  var rg=range(),lo=rg[0],hi=rg[1],W=1100,L=118,R=10,PW=W-L-R,sx=PW/(hi-lo);
  function X(t){return L+(Math.min(Math.max(t,lo),hi)-lo)*sx;}
  var rs=D.rounds.filter(function(r){return r.e>=lo&&r.s<hi;});
  var its=D.items.filter(function(it){return rs.some(function(r){return r.item===it;})||D.merges.some(function(m){return m.item===it&&m.t>=lo&&m.t<hi;});});
  var LH=11,top=18,CH=38,y=top+CH+8,rows=[],h=[];TIPS=[];
  /* concurrency strip */
  var maxc=1;for(var m=lo;m<hi;m++)maxc=Math.max(maxc,D.conc[m]||0);
  var step=Math.max(1,Math.floor((hi-lo)/PW)),cp="M"+L+","+(top+CH);
  for(m=lo;m<hi;m+=step){var c=0;for(var k=m;k<Math.min(m+step,hi);k++)c=Math.max(c,D.conc[k]||0);var yy=top+CH-c/maxc*CH;cp+=" L"+X(m)+","+yy+" L"+X(m+step)+","+yy;}
  cp+=" L"+X(hi)+","+(top+CH)+"Z";
  var rowsTop=y;
  var skillY=y;if(D.skillsFrom)y+=16;
  its.forEach(function(it){rows.push([it,y]);y+=LANES[it]*LH+5;});
  var H=y+22;
  h.push('<svg viewBox="0 0 '+W+' '+H+'" role="group" aria-label="Rounds by item over time, '+esc(D.zone)+'"><defs>'+patterns()+'</defs>');
  /* sleep */
  (D.gaps||[]).forEach(function(g){if(g.e<lo||g.s>hi)return;var x1=X(g.s),x2=X(g.e);
    h.push('<g><title>Machine asleep '+esc(g.sl)+' to '+esc(hm(g.el))+' '+esc(D.tz)+'</title><rect x="'+x1+'" y="'+top+'" width="'+Math.max(1,x2-x1)+'" height="'+(H-top-20)+'" fill="url(#p-sleep)"/>'+
      (x2-x1>34?'<text x="'+(x1+3)+'" y="'+(top+10)+'" class="muted">asleep</text>':"")+'</g>');});
  /* axis */
  var span=hi-lo,tick=span<=1440?120:span<=2880?360:span<=10080?720:1440*Math.ceil(span/10080);
  D.mid.forEach(function(md,j){if(tick>1440&&j%(tick/1440))return;var nx=j+1<D.mid.length?D.mid[j+1][0]:D.total;
    for(var t=md[0];t<nx&&t<hi;t+=tick){if(t<lo)continue;var x=X(t),lab=t===md[0]&&span>1440?md[1].slice(5):String(Math.floor((t-md[0])/60)).padStart(2,"0")+":00";
    h.push('<line class="grid" x1="'+x+'" x2="'+x+'" y1="'+top+'" y2="'+(H-18)+'"/><text x="'+x+'" y="'+(H-6)+'" text-anchor="middle" class="muted">'+esc(lab)+'</text>');}});
  h.push('<text x="'+L+'" y="11">Workers running at once, per minute (peak '+maxc+' in view)</text>');
  h.push('<path class="conc" d="'+cp+'"><title>Workers running at once, peak '+maxc+'</title></path>');
  h.push('<text x="'+(L-6)+'" y="'+(top+8)+'" text-anchor="end" class="muted">'+maxc+'</text><text x="'+(L-6)+'" y="'+(top+CH)+'" text-anchor="end" class="muted">0</text>');
  h.push('<text x="'+(W-R)+'" y="11" text-anchor="end" class="muted">Axis: local time, '+esc(D.zone)+'</text>');
  /* skills row */
  if(D.skillsFrom)h.push('<text x="'+(L-6)+'" y="'+(skillY+9)+'" text-anchor="end">skill merges</text><line class="grid" x1="'+L+'" x2="'+(W-R)+'" y1="'+(skillY+14)+'" y2="'+(skillY+14)+'"/>');
  D.skills.forEach(function(s){if(s.t<lo||s.t>=hi)return;var x=X(s.t);TIPS.push('<b>Skill merge '+esc(s.sha)+'</b>'+esc(s.subject)+'<br>'+esc(s.tl)+' '+esc(D.tz)+'');
    h.push('<path class="skill mk" tabindex="0" role="img" data-tip="'+(TIPS.length-1)+'" aria-label="Skill merge '+esc(s.sha)+' at '+esc(s.tl)+' '+esc(D.tz)+': '+esc(s.subject)+'" d="M'+x+','+(skillY+1)+' l5,10 h-10Z"/>');});
  /* rows */
  rows.forEach(function(row){var it=row[0],ry=row[1];
    h.push('<text x="'+(L-6)+'" y="'+(ry+9)+'" text-anchor="end">'+esc(it.length>18?it.slice(0,17)+"\u2026":it)+'<title>'+esc(it)+'</title></text>');
    rs.filter(function(r){return r.item===it;}).forEach(function(r){var x1=X(r.s),x2=X(r.e);TIPS.push(tipFor(r));
      h.push('<rect class="rnd '+r.outcome+'" tabindex="0" role="img" data-tip="'+(TIPS.length-1)+'" aria-label="'+esc(labelFor(r))+'" x="'+x1+'" y="'+(ry+r.lane*LH)+'" width="'+Math.max(2,x2-x1)+'" height="'+(LH-2)+'" fill="url(#p-'+r.kind+')"/>');});
    D.merges.forEach(function(m){if(m.item!==it||m.t<lo||m.t>=hi)return;var x=X(m.t),cy=ry+4.5;TIPS.push('<b>Merged to main: '+esc(it)+'</b>'+esc(m.tl)+' '+esc(D.tz)+'');
      h.push('<path class="diamond mk" tabindex="0" role="img" data-tip="'+(TIPS.length-1)+'" aria-label="'+esc(it)+' merged to main at '+esc(m.tl)+' '+esc(D.tz)+'" d="M'+x+','+(cy-6)+' l6,6 l-6,6 l-6,-6Z"/>');});
  });
  if(!rows.length)h.push('<text x="'+(L+8)+'" y="'+(rowsTop+30)+'">No rounds ran in this view.</text>');
  h.push('</svg>');
  document.getElementById("chart").innerHTML=h.join("");
}

var tip=document.getElementById("tip");
function show(el){var i=el.getAttribute("data-tip");if(i==null)return;tip.innerHTML=TIPS[+i];tip.style.display="block";
  var b=el.getBoundingClientRect(),tw=tip.offsetWidth,th=tip.offsetHeight,x=Math.min(Math.max(4,b.left),window.innerWidth-tw-4),y=b.bottom+6;
  if(y+th>window.innerHeight-4)y=Math.max(4,b.top-th-6);tip.style.left=x+"px";tip.style.top=y+"px";}
function hide(){tip.style.display="none";}
var chart=document.getElementById("chart");
chart.addEventListener("mouseover",function(e){if(e.target.hasAttribute&&e.target.hasAttribute("data-tip"))show(e.target);});
chart.addEventListener("mouseout",hide);
chart.addEventListener("focusin",function(e){show(e.target);});
chart.addEventListener("focusout",hide);
document.addEventListener("keydown",function(e){if(e.key==="Escape")hide();});

function tables(){
  var h='<table><caption>Rounds ('+D.rounds.length+'; '+spend(D.creditTotal,D.unknownTotal,D.rounds.length,1)+', 1 credit = $0.01)</caption><thead><tr><th scope="col">Item</th><th scope="col">Round</th><th scope="col">Kind</th><th scope="col">Model</th><th scope="col">Reasoning effort</th><th scope="col">Start ('+esc(D.tz)+')</th><th scope="col">End ('+esc(D.tz)+')</th><th scope="col">Wall min</th><th scope="col">Credits</th><th scope="col">List price</th><th scope="col">Outcome</th></tr></thead><tbody>';
  D.rounds.slice().sort(function(a,b){return a.s-b.s;}).forEach(function(r){
    h+='<tr data-round="'+esc(r.name)+'" data-credits="'+(r.credits==null?"":r.credits)+'"><td>'+esc(r.item)+'</td><th scope="row">'+esc(r.name)+'</th><td>'+esc(KLAB[r.kind])+(r.rawkind==="catchup"?" (catch-up)":"")+'</td><td>'+esc(r.model)+'</td><td>'+esc(r.effort)+'</td><td>'+esc(r.sl)+'</td><td>'+esc(r.el)+(r.endFrom!=="last event"?" *":"")+'</td><td class="n">'+num(r.wall,1)+'</td><td class="n">'+num(r.credits,1)+'</td><td class="n">'+money(r.credits)+'</td><td>'+outcomeText(r.outcome)+'</td></tr>';});
  h+='</tbody></table><p class="note">* end from start + wall time: no usable event log.</p>';
  h+='<table><caption>Merges to main ('+D.merges.length+')</caption><thead><tr><th scope="col">Item</th><th scope="col">Merged ('+esc(D.tz)+')</th></tr></thead><tbody>';
  D.merges.slice().sort(function(a,b){return a.t-b.t;}).forEach(function(m){h+='<tr data-merge="'+esc(m.item)+'"><th scope="row">'+esc(m.item)+'</th><td>'+esc(m.tl)+'</td></tr>';});
  h+='</tbody></table><table><caption>Skill merges ('+D.skills.length+')</caption><thead><tr><th scope="col">Commit</th><th scope="col">Merged ('+esc(D.tz)+')</th><th scope="col">Subject</th></tr></thead><tbody>';
  D.skills.forEach(function(s){h+='<tr data-skill="'+esc(s.sha)+'"><th scope="row">'+esc(s.sha)+'</th><td>'+esc(s.tl)+'</td><td>'+esc(s.subject)+'</td></tr>';});
  h+='</tbody></table><table><caption>Machine asleep ('+(D.gaps?D.gaps.length+' gaps of 5 min or more':'unknown: read from pmset, which is macOS only or failed')+')</caption><thead><tr><th scope="col">From ('+esc(D.tz)+')</th><th scope="col">To ('+esc(D.tz)+')</th></tr></thead><tbody>';
  (D.gaps||[]).forEach(function(g){h+='<tr><td>'+esc(g.sl)+'</td><td>'+esc(g.el)+'</td></tr>';});
  h+='</tbody></table>';
  document.getElementById("tables").innerHTML=h;
}

var hosted=false,root=document.documentElement;
function scheme(dark){root.setAttribute("data-theme",dark?"dark":"light");}
window.addEventListener("message",function(e){
  var d=e.data;
  if(e.source!==window.parent||!d||typeof d!=="object"||(d.theme!=="light"&&d.theme!=="dark"))return;
  hosted=true;scheme(d.theme==="dark");
  var tk=d.tokens&&typeof d.tokens==="object"?d.tokens:{};["text","paper","accent","line"].forEach(function(k){
    if(typeof tk[k]==="string"&&tk[k].length<80&&!/[;{}<>]/.test(tk[k]))root.style.setProperty("--"+k,tk[k]);else root.style.removeProperty("--"+k);});
});
if(window.matchMedia){var mq=window.matchMedia("(prefers-color-scheme: dark)");scheme(mq.matches);
  if(mq.addEventListener)mq.addEventListener("change",function(e){if(!hosted)scheme(e.matches);});}
if(!D.gaps)document.getElementById("sleepnote").textContent="Machine sleep is unknown: it is read from pmset, which is macOS only or failed here.";
legend();controls();tables();render();
})();
</script>
</body>
</html>
'''


if __name__ == '__main__':
    sys.exit(main())
