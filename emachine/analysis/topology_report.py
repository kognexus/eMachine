"""
Report of the multi-topology study (T64): charts of every verified pick, the interactive Pareto page and
the comparison report against the ILM-E85x23.

    python -m emachine.analysis.topology_report --config <study folder>/study.json

Writes into <study>/report/: report.md, report.html, pareto.html (self-contained, works offline) and
figures/<topology>_<pick>_*.svg; ParaView pictures are referenced from <study>/paraview/.
"""

import argparse
import html
import json
import math
import os

import numpy as np

from emachine.io.svg import Chart, save
from emachine.machines.catalogue import TOPOLOGIES

from .topology_study import load_config, picks, read_designs

#: categorical slots 1-3 of the reference palette (dataviz skill), light mode
PHASE_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a"]
MUTED = "#8a8985"


# ----------------------------------------------------------------------------- figures of one design

def _range(values, pad=0.08):
    v = np.asarray([x for x in np.ravel(values) if np.isfinite(x)])
    if v.size == 0:
        return -1.0, 1.0
    lo, hi = float(v.min()), float(v.max())
    span = hi - lo or abs(hi) or 1.0
    return lo - pad * span, hi + pad * span


def phase_figure(record, path, drive):
    """Motor-CAD style: phase voltages, phase flux linkages and the line voltage against the DC link, over one
    electrical period at the rated point (sinusoidal current, current angle of the most torque)."""
    w = record["waveforms"]
    t = np.asarray(w["time_s"]) * 1000.0
    v = np.asarray(w["voltage_V"])
    psi = np.asarray(w["flux_Wb"])
    charts = []
    title = f"{record['machine']}: rated point, {drive['rated_current_A']} A, {drive['speed_rpm']:.0f} rpm"
    c = Chart((t[0], t[-1]), _range(v), "Time (ms)", "Voltage (V)", "Phase voltages  " + title, width=880, height=300)
    for k in range(v.shape[1]):
        c.line(t, v[:, k], PHASE_COLOURS[k], label="v" + "ABC"[k])
    charts.append(c)
    c = Chart((t[0], t[-1]), _range(psi), "Time (ms)", "Flux linkage (Wb-turns)", "Phase flux linkages", width=880, height=300)
    for k in range(psi.shape[1]):
        c.line(t, psi[:, k], PHASE_COLOURS[k], label="psi" + "ABC"[k])
    charts.append(c)
    if "line_voltage_V" in w:
        line = np.asarray(w["line_voltage_V"])
        limit = drive["modulation"] * drive["bus_voltage_V"]
        c = Chart((t[0], t[-1]), _range(np.concatenate([line[:, 0], [limit, -limit]])), "Time (ms)", "Voltage (V)",
                  "Line voltage A-B against the DC-link limit", width=880, height=260)
        c.line(t, line[:, 0], PHASE_COLOURS[0], label="vAB")
        c.line([t[0], t[-1]], [limit, limit], MUTED, label=f"+-{limit:.1f} V", dash="5,4", width=1.2)
        c.line([t[0], t[-1]], [-limit, -limit], MUTED, dash="5,4", width=1.2)
        charts.append(c)
    if "current_A" in w:
        cur = np.asarray(w["current_A"])
        c = Chart((t[0], t[-1]), _range(cur), "Time (ms)", "Current (A)", "Phase currents", width=880, height=240)
        for k in range(cur.shape[1]):
            c.line(t, cur[:, k], PHASE_COLOURS[k], label="i" + "ABC"[k])
        charts.append(c)
    save(path, charts)


def emf_figure(record, path):
    nl = record.get("no_load")
    if not nl:
        return False
    e = np.asarray(nl["emf_V"])
    n = e.shape[0]
    period_ms = 1000.0 / record["electrical_Hz"]
    t = np.arange(n) * period_ms / n
    c = Chart((t[0], t[-1]), _range(e), "Time (ms)", "Voltage (V)",
              f"{record['machine']}: back-EMF at no load, {record['electrical_Hz'] * 60 / record['design']['pe']:.0f} rpm",
              width=880, height=280)
    for k in range(e.shape[1]):
        c.line(t, e[:, k], PHASE_COLOURS[k], label="e" + "ABC"[k])
    save(path, [c])
    return True


def torque_figure(record, path):
    t = np.asarray(record.get("torque_waveform_Nm") or [])
    if t.size == 0:
        return False
    charts = []
    if record["principle"] == "srm":
        x = np.linspace(0, 360, len(t), endpoint=False)
        label = "Rotor position (el. deg, one rotor pole pitch)"
    else:
        x = np.linspace(0, 180, len(t), endpoint=False)
        label = "Rotor position (el. deg)"
    lo, hi = _range(np.concatenate([t, [0.0]]))
    c = Chart((x[0], x[-1] if x[-1] > x[0] else 1.0), (lo, hi), label, "Torque (Nm)",
              f"{record['machine']}: torque at the rated point (mean {np.mean(t):.2f} Nm, ripple {100 * record['ripple']:.1f} %)",
              width=880, height=280)
    c.line(x, t, PHASE_COLOURS[0], label="torque")
    charts.append(c)
    nl = record.get("no_load")
    if nl and nl.get("cogging_Nm"):
        cg = np.asarray(nl["cogging_Nm"])
        xc = np.linspace(0, 180, len(cg), endpoint=False)
        c = Chart((xc[0], xc[-1]), _range(cg), label, "Torque (Nm)",
                  f"Cogging torque (peak to peak {1000 * nl['cogging_pp_Nm']:.0f} mNm)", width=880, height=240)
        c.line(xc, cg, PHASE_COLOURS[1], label="cogging")
        charts.append(c)
    save(path, charts)
    return True


def sketch_of(rundir, pick, path):
    """Material sketch of the verified pick from its kept mesh (position 0)."""
    from emachine.io.section_svg import read_msh, sketch
    work = os.path.join(rundir, "verify", f"{pick}_work", "pos000")
    if not os.path.isdir(work):
        return False
    parts = []
    for part in sorted(os.listdir(work)):
        msh = os.path.join(work, part, "section.msh")
        meta = os.path.join(work, part, "section.regions.json")
        if os.path.isfile(msh) and os.path.isfile(meta):
            with open(meta) as f:
                m = json.load(f)
            pts, tri, names = read_msh(msh)
            kind = (m.get("geometry") or {}).get("kind") or ("axial" if m.get("part") == "axial" else "radial")
            parts.append((pts, tri, names, m["regions"], kind))
    if not parts:
        return False
    with open(path, "w") as f:
        f.write(sketch(parts, title="", width=480))
    return True


# ----------------------------------------------------------------------------- data

def pareto_front(points):
    """Indices of the non-dominated points; each point: tuple of values to maximise."""
    idx = []
    for i, p in enumerate(points):
        dominated = False
        for j, q in enumerate(points):
            if j != i and all(a >= b for a, b in zip(q, p)) and any(a > b for a, b in zip(q, p)):
                dominated = True
                break
        if not dominated:
            idx.append(i)
    return idx


def design_row(d):
    w = d.get("winding") or {}
    m = d.get("masses") or {}
    row = {"id": d.get("id"), "ok": d.get("violation", 1) == 0 and d.get("analysed", False),
           "analysed": d.get("analysed", False), "reason": d.get("reason")}
    if d.get("analysed"):
        row.update({"T": d["torque_Nm"], "Tpk": d["peak_torque_Nm"], "ripple": 100 * d["ripple"] if math.isfinite(d["ripple"]) else None,
                    "eta": 100 * d["efficiency"], "km": d.get("km_Nm_sqrtW"), "mass": m.get("active_kg"),
                    "magnet": m.get("magnet_kg"), "loss": d["losses_W"]["total"], "kt": d["kt_Nm_A"],
                    "fill": w.get("fill"), "awg": w.get("awg"), "strands": w.get("strands"), "turns": w.get("turns_per_coil"),
                    "paths": w.get("paths"), "jr": w.get("j_rated_rms_A_mm2"),
                    "viol": {k: round(v, 3) for k, v in (d.get("constraints") or {}).items() if v > 0}})
    row["values"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d["values"].items()}
    des = d.get("design") or {}
    if des.get("winding"):
        row["winding"] = f"{des['winding'].get('slots')}/{des['winding'].get('poles')}"
    return row


def collect(cfg, out):
    data = {}
    for key in cfg["topologies"]:
        rundir = os.path.join(out, "runs", key)
        designs = read_designs(rundir)
        if not designs:
            continue
        topo = TOPOLOGIES[key]()
        verified = {}
        for name in ("optimal", "highest_torque", "closest"):
            path = os.path.join(rundir, "verify", f"{name}.json")
            if os.path.isfile(path):
                with open(path) as f:
                    verified[name] = json.load(f)
        chosen = picks(designs, cfg)
        data[key] = {"title": topo.title, "summary": topo.summary, "sources": topo.sources, "flux_path": topo.flux_path,
                     "principle": topo.principle, "designs": designs, "picks": chosen, "verified": verified,
                     "rundir": rundir}
    return data


# ----------------------------------------------------------------------------- pareto page

PARETO_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Topology Pareto explorer</title>
<style>
:root{--surface:#fcfcfb;--panel:#f4f3f0;--text:#0b0b0b;--text2:#52514e;--muted:#8a8985;--grid:#e6e5e1;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--off:#c9c8c3;color-scheme:light}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){--surface:#1a1a19;--panel:#242422;--text:#f0efec;
--text2:#c3c2b7;--muted:#8f8e88;--grid:#33332f;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--off:#4a4945;color-scheme:dark}}
:root[data-theme="dark"]{--surface:#1a1a19;--panel:#242422;--text:#f0efec;--text2:#c3c2b7;--muted:#8f8e88;--grid:#33332f;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--off:#4a4945;color-scheme:dark}
body{margin:0;background:var(--surface);color:var(--text);font:14px/1.45 -apple-system,Helvetica,Arial,sans-serif}
main{max-width:1180px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:4px 0 2px} p.sub{color:var(--text2);margin:0 0 12px}
.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:8px 0 12px}
label{color:var(--text2);font-size:13px} select{font:inherit;padding:3px 6px;background:var(--panel);color:var(--text);border:1px solid var(--grid);border-radius:6px}
.wrap{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:16px}
@media (max-width:860px){.wrap{grid-template-columns:1fr}}
svg{width:100%;height:auto;display:block;background:var(--surface)}
.card{background:var(--panel);border-radius:10px;padding:12px;overflow-wrap:anywhere}
.card h2{font-size:15px;margin:0 0 6px} .card table{border-collapse:collapse;width:100%;font-size:12.5px}
.card td{padding:2px 4px;border-bottom:1px solid var(--grid)} .card td:first-child{color:var(--text2)}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;color:var(--text2);margin-top:6px}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:-1px}
#tip{position:fixed;pointer-events:none;background:var(--panel);color:var(--text);border:1px solid var(--grid);border-radius:6px;
padding:6px 8px;font-size:12px;display:none;box-shadow:0 2px 8px rgba(0,0,0,.15);max-width:280px}
.summary{color:var(--text2);font-size:13px;margin:4px 0 10px}
table.all{border-collapse:collapse;width:100%;font-size:12.5px;margin-top:18px} table.all th,table.all td{padding:3px 6px;border-bottom:1px solid var(--grid);text-align:right}
table.all th:first-child,table.all td:first-child{text-align:left} table.all th{color:var(--text2);font-weight:600}
</style></head><body><main>
<h1>Topology Pareto explorer</h1>
<p class="sub">__SUBTITLE__</p>
<div class="controls">
<label>Topology <select id="topo"></select></label>
<label>x <select id="xs"></select></label>
<label>y <select id="ys"></select></label>
<label>Show <select id="show"><option value="all">all analysed designs</option><option value="ok">feasible only</option></select></label>
</div>
<div class="summary" id="summary"></div>
<div class="wrap"><div><svg id="plot" viewBox="0 0 760 520" role="img" aria-label="Scatter of the designs of the chosen topology"></svg>
<div class="legend"><span><span class="dot" style="background:var(--s1)"></span>feasible</span>
<span><span class="dot" style="background:var(--off)"></span>violates a limit</span>
<span><span class="dot" style="background:transparent;border:2px solid var(--s2)"></span>Pareto front (rated torque, peak torque, low ripple; feasible)</span>
<span><span class="dot" style="background:var(--s3)"></span>picks (optimal, highest torque)</span></div></div>
<div class="card" id="detail"><h2>Design</h2><p style="color:var(--text2)">Hover over a point for its values, click to keep it here.</p></div></div>
<table class="all" id="picks"></table>
<p class="summary">Picks: values of the verification (finer mesh, 36 rotor positions); * not verified yet (optimization values).</p>
<div id="tip"></div>
<script>
const DATA = __DATA__;
const AXES = {T:"Rated torque (Nm)",Tpk:"Peak torque at 42 A (Nm)",ripple:"Torque ripple (%)",eta:"Efficiency at rated point (%)",
km:"Motor constant (Nm/sqrt W)",mass:"Active mass (kg)",magnet:"Magnet mass (kg)",loss:"Losses at rated point (W)",kt:"Torque constant (Nm/A)",jr:"Rated current density (A/mm2)"};
const topoSel=document.getElementById('topo'),xs=document.getElementById('xs'),ys=document.getElementById('ys'),show=document.getElementById('show');
Object.keys(DATA.topologies).forEach(k=>{const o=document.createElement('option');o.value=k;o.textContent=k+' - '+DATA.topologies[k].title;topoSel.appendChild(o)});
for(const [k,v] of Object.entries(AXES)){for(const s of [xs,ys]){const o=document.createElement('option');o.value=k;o.textContent=v;s.appendChild(o)}}
xs.value='T';ys.value='Tpk';
let pinned=null;
function nice(lo,hi){const span=hi-lo||1,raw=span/6,p=Math.pow(10,Math.floor(Math.log10(raw)));const st=[1,2,2.5,5,10].map(m=>m*p).reduce((a,b)=>Math.abs(b-raw)<Math.abs(a-raw)?b:a);
const out=[];for(let v=Math.ceil(lo/st)*st;v<=hi+1e-9*st;v+=st)out.push(+v.toFixed(10));return out}
function fmt(v){return v==null?'-':(Math.abs(v)>=100?v.toFixed(0):Math.abs(v)>=10?v.toFixed(1):v.toFixed(3))}
function detail(d,t){const rows=[['design',d.id],['slots/poles',d.winding||'-'],['rated torque',fmt(d.T)+' Nm'],['peak torque',fmt(d.Tpk)+' Nm'],
['ripple',fmt(d.ripple)+' %'],['efficiency',fmt(d.eta)+' %'],['motor constant',fmt(d.km)+' Nm/sqrt W'],['losses',fmt(d.loss)+' W'],
['active mass',fmt(d.mass)+' kg'],['winding',d.turns?(d.turns+' turns/coil, '+d.paths+' path(s), '+d.strands+' x AWG '+d.awg+', fill '+fmt(d.fill)):'-'],
['rated J',fmt(d.jr)+' A/mm2']];
if(d.viol&&Object.keys(d.viol).length)rows.push(['violates',Object.entries(d.viol).map(([k,v])=>k+' '+v).join(', ')]);
for(const [k,v] of Object.entries(d.values))rows.push([k,v]);
document.getElementById('detail').innerHTML='<h2>'+(t||'Design')+'</h2><table>'+rows.map(r=>'<tr><td>'+r[0]+'</td><td>'+r[1]+'</td></tr>').join('')+'</table>'}
function draw(){const key=topoSel.value,t=DATA.topologies[key],X=xs.value,Y=ys.value;
document.getElementById('summary').textContent=t.summary+' Designs: '+t.rows.length+', analysed '+t.rows.filter(r=>r.analysed).length+', feasible '+t.rows.filter(r=>r.ok).length+'.';
let pts=t.rows.filter(r=>r.analysed&&r[X]!=null&&r[Y]!=null&&isFinite(r[X])&&isFinite(r[Y]));if(show.value==='ok')pts=pts.filter(r=>r.ok);
const svg=document.getElementById('plot');const W=760,H=520,L=70,R=20,T=20,B=56;
if(!pts.length){svg.innerHTML='<text x="380" y="260" text-anchor="middle" fill="currentColor">no analysed designs</text>';return}
let x0=Math.min(...pts.map(p=>p[X])),x1=Math.max(...pts.map(p=>p[X])),y0=Math.min(...pts.map(p=>p[Y])),y1=Math.max(...pts.map(p=>p[Y]));
const px=(x1-x0)||Math.abs(x1)||1,py=(y1-y0)||Math.abs(y1)||1;x0-=.05*px;x1+=.05*px;y0-=.05*py;y1+=.05*py;
const sx=v=>L+(v-x0)/(x1-x0)*(W-L-R),sy=v=>H-B-(v-y0)/(y1-y0)*(H-T-B);
let s='';for(const v of nice(x0,x1)){s+=`<line x1="${sx(v)}" x2="${sx(v)}" y1="${T}" y2="${H-B}" stroke="var(--grid)"/><text x="${sx(v)}" y="${H-B+16}" font-size="11" text-anchor="middle" fill="var(--text2)">${v}</text>`}
for(const v of nice(y0,y1)){s+=`<line x1="${L}" x2="${W-R}" y1="${sy(v)}" y2="${sy(v)}" stroke="var(--grid)"/><text x="${L-6}" y="${sy(v)+4}" font-size="11" text-anchor="end" fill="var(--text2)">${v}</text>`}
s+=`<text x="${(L+W-R)/2}" y="${H-14}" text-anchor="middle" font-size="12.5" fill="var(--text)">${AXES[X]}</text><text x="16" y="${(T+H-B)/2}" text-anchor="middle" font-size="12.5" fill="var(--text)" transform="rotate(-90 16 ${(T+H-B)/2})">${AXES[Y]}</text>`;
const front=new Set(t.front),pk=t.picks;
const order=[...pts].sort((a,b)=>(a.ok-b.ok));
for(const p of order){const isPick=Object.values(pk).includes(p.id);const fill=isPick?'var(--s3)':(p.ok?'var(--s1)':'var(--off)');
s+=`<circle class="pt" data-id="${p.id}" cx="${sx(p[X])}" cy="${sy(p[Y])}" r="${isPick?7:5}" fill="${fill}" stroke="var(--surface)" stroke-width="2"/>`;
if(front.has(p.id))s+=`<circle cx="${sx(p[X])}" cy="${sy(p[Y])}" r="9" fill="none" stroke="var(--s2)" stroke-width="2" pointer-events="none"/>`;
const names=Object.entries(pk).filter(([n,id])=>id===p.id).map(([n])=>n.replace('_',' '));if(names.length)s+=`<text x="${sx(p[X])+11}" y="${sy(p[Y])-9}" font-size="11.5" fill="var(--text)">${names.join(' = ')}</text>`}
for(const p of pts)s+=`<circle class="hit" data-id="${p.id}" cx="${sx(p[X])}" cy="${sy(p[Y])}" r="11" fill="transparent"/>`;
svg.innerHTML=s;const byId=Object.fromEntries(t.rows.map(r=>[r.id,r]));const tip=document.getElementById('tip');
svg.querySelectorAll('.hit').forEach(c=>{c.addEventListener('mousemove',e=>{const d=byId[c.dataset.id];tip.style.display='block';tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY+10)+'px';
tip.innerHTML='<b>design '+d.id+'</b> ('+(d.winding||'')+')<br>'+AXES[X]+': '+fmt(d[X])+'<br>'+AXES[Y]+': '+fmt(d[Y])+'<br>'+(d.ok?'feasible':'violates a limit');if(!pinned)detail(d)});
c.addEventListener('mouseleave',()=>{tip.style.display='none'});c.addEventListener('click',()=>{pinned=c.dataset.id;detail(byId[c.dataset.id],'Design '+c.dataset.id+' (kept)')})})}
function picksTable(){let h='<tr><th>Topology</th><th>Pick</th><th>Slots/poles</th><th>Rated torque (Nm)</th><th>Peak torque (Nm)</th><th>Ripple (%)</th><th>Efficiency (%)</th><th>Motor constant</th><th>Active mass (kg)</th></tr>';
for(const [k,t] of Object.entries(DATA.topologies)){const byId={};for(const [n,id] of Object.entries(t.picks))(byId[id]=byId[id]||[]).push(n.replace('_',' '));
for(const [id,names] of Object.entries(byId)){const d=(t.verified&&t.verified[id])||t.rows.find(r=>r.id==id);if(!d)continue;
h+=`<tr><td>${k}</td><td>${names.join(' = ')}${t.verified&&t.verified[id]?'':' *'}</td><td>${d.winding||''}</td><td>${fmt(d.T)}</td><td>${fmt(d.Tpk)}</td><td>${fmt(d.ripple)}</td><td>${fmt(d.eta)}</td><td>${fmt(d.km)}</td><td>${fmt(d.mass)}</td></tr>`}}
h+=`<tr><td>ILM-E85x23 (datasheet)</td><td>reference</td><td>-/20</td><td>${DATA.reference.rated_torque_Nm}</td><td>${DATA.reference.peak_torque_Nm}</td><td>-</td><td>${DATA.reference.max_efficiency*100} max</td><td>${DATA.reference.km_Nm_sqrtW}</td><td>${(DATA.reference.mass_g/1000).toFixed(3)}</td></tr>`;
document.getElementById('picks').innerHTML=h}
[topoSel,xs,ys,show].forEach(e=>e.addEventListener('change',()=>{pinned=null;draw()}));draw();picksTable();
</script></main></body></html>
"""


def write_pareto(data, cfg, path):
    payload = {"reference": cfg["reference"], "topologies": {}}
    for key, item in data.items():
        rows = [design_row(d) for d in item["designs"]]
        ok = [r for r in rows if r["ok"] and r.get("ripple") is not None]
        front_idx = pareto_front([(r["T"], r["Tpk"], -r["ripple"]) for r in ok])
        verified = {}
        for v in item.get("verified", {}).values():
            if v.get("analysed") and v.get("id") is not None:
                verified[v["id"]] = design_row(v)
        payload["topologies"][key] = {"title": item["title"], "summary": item["summary"], "rows": rows,
                                      "front": [ok[i]["id"] for i in front_idx], "verified": verified,
                                      "picks": {k: v["id"] for k, v in item["picks"].items()}}
    sub = (f"Every design the optimizer evaluated, per topology, in the ILM-E85x23 envelope (85 mm outer, 52 mm bore, 30 mm active "
           f"length) at {cfg['drive']['bus_voltage_V']:.0f} V, {cfg['drive']['rated_current_A']} A rated, "
           f"{cfg['drive']['peak_current_A']:.0f} A peak, rated point {cfg['drive']['speed_rpm']:.0f} rpm.")
    page = PARETO_HTML.replace("__DATA__", json.dumps(payload, separators=(",", ":"))).replace("__SUBTITLE__", html.escape(sub))
    with open(path, "w") as f:
        f.write(page)


# ----------------------------------------------------------------------------- markdown -> html

def md_to_html(md, title):
    """The subset of Markdown the report uses: headings, paragraphs, lists, tables, images, bold, code, links."""
    import re

    def inline(text):
        text = html.escape(text, quote=False)
        text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2">', text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        return text
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            text = line[level:].strip()
            anchor = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
            out.append(f'<h{level} id="{anchor}">{inline(text)}</h{level}>')
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, body = rows[0], [r for r in rows[2:]]
            out.append('<div class="tw"><table><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table></div>")
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith(("- ", "  ")):
                if lines[i].startswith("- "):
                    items.append(lines[i][2:])
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
        elif not line.strip():
            i += 1
        else:
            para = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "- ")):
                para.append(lines[i])
                i += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
    css = """:root{--surface:#fcfcfb;--panel:#f4f3f0;--text:#0b0b0b;--text2:#52514e;--grid:#e3e2de;--link:#2a78d6;color-scheme:light}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){--surface:#1a1a19;--panel:#242422;--text:#f0efec;--text2:#c3c2b7;--grid:#3a3a36;--link:#6da7ec;color-scheme:dark}}
:root[data-theme="dark"]{--surface:#1a1a19;--panel:#242422;--text:#f0efec;--text2:#c3c2b7;--grid:#3a3a36;--link:#6da7ec;color-scheme:dark}
body{margin:0;background:var(--surface);color:var(--text);font:15px/1.55 -apple-system,Helvetica,Arial,sans-serif}
main{max-width:1060px;margin:0 auto;padding:16px} a{color:var(--link)} h1{font-size:26px} h2{font-size:21px;margin-top:34px;border-bottom:1px solid var(--grid);padding-bottom:4px}
h3{font-size:17px;margin-top:26px} img{max-width:100%;height:auto;background:#fff;border-radius:6px;margin:6px 0}
.tw{overflow-x:auto} table{border-collapse:collapse;font-size:13px;margin:8px 0} th,td{padding:4px 8px;border-bottom:1px solid var(--grid);text-align:left;vertical-align:top}
th{color:var(--text2)} code{background:var(--panel);padding:1px 4px;border-radius:4px;font-size:13px}"""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{html.escape(title)}</title><style>{css}</style></head><body><main>" + "\n".join(out) + "</main></body></html>")


# ----------------------------------------------------------------------------- the report

def fmt(v, digits=2):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "-"
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return str(v)
    return f"{v:.{digits}f}"


def pick_row(key, name, r, cfg):
    w, m, d = r.get("winding") or {}, r.get("masses") or {}, r.get("design") or {}
    los = r.get("losses_W") or {}
    nl = r.get("no_load") or {}
    wind = d.get("winding") or {}
    label = wind.get("label") or ""
    sp = f"{wind.get('slots')}/{wind.get('poles')}" + (f" (rotor {wind['rotor_poles']})" if wind.get("rotor_poles") else "")
    return [key, name.replace("_", " "), sp + (" " + label if label and "SRM" not in label else ""),
            fmt(r["torque_Nm"]), fmt(r["kt_Nm_A"], 3), fmt(r["peak_torque_Nm"]), fmt(100 * r["ripple"], 1),
            fmt(1000 * nl["cogging_pp_Nm"], 0) if nl.get("cogging_pp_Nm") is not None else "-",
            fmt(100 * r["efficiency"], 1), f"{fmt(los.get('copper'), 1)} / {fmt(los.get('stator_iron'), 1)} / {fmt(los.get('rotor'), 1)}",
            fmt(r.get("km_Nm_sqrtW"), 3),
            fmt(r["km_Nm_sqrtW"] * math.sqrt(cfg["reference"]["copper_loss_rated_20C_W"]), 2) if r.get("km_Nm_sqrtW") else "-",
            f"{w.get('turns_per_coil')} x {w.get('coils_per_phase')}/{w.get('paths')}, {w.get('strands')} x AWG {w.get('awg')}, fill {fmt(w.get('fill'))}",
            f"{fmt(w.get('j_rated_rms_A_mm2'), 1)} / {fmt(w.get('j_peak_rms_A_mm2'), 1)}",
            fmt((r.get("voltage") or {}).get("line_peak_V"), 1),
            fmt(m.get("magnet_kg"), 3), fmt(m.get("active_kg"), 3),
            fmt(r["peak_torque_Nm"] / m["active_kg"], 1) if m.get("active_kg") else "-",
            fmt(d.get("axial_length_mm"), 1),
            ", ".join(f"{k} {v:.2f}" for k, v in (r.get("constraints") or {}).items() if v > 0) or "all met"]


HEADER = ["Topology", "Pick", "Slots/poles", "Rated torque (Nm)", "kT (Nm/A)", "Peak torque at 42 A (Nm)", "Ripple (%)",
          "Cogging p-p (mNm)", "Efficiency (%)", "Losses Cu / Fe / rotor (W)", "Motor constant (Nm/sqrt W, 20 C)",
          "Torque at the ILM-E's copper loss, 26.7 W at 20 C (Nm)",
          "Winding: turns x coils/paths, wire, fill", "J rated / peak (A/mm2 rms)", "Line voltage peak (V)", "Magnet (kg)",
          "Active mass (kg)", "Peak torque / active mass (Nm/kg)", "Axial length with end turns (mm)",
          "Limits in the verification (relative violation)"]


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def speed_section(cfg, out, figs):
    """Markdown of the speed sensitivity (the optimal picks wound for other rated speeds), with a chart."""
    path = os.path.join(out, "speed_sensitivity", "results.json")
    if not os.path.isfile(path):
        return ""
    with open(path) as f:
        res = json.load(f)
    rated = os.path.join(out, "runs")
    speeds = sorted({float(s) for r in res.values() for s in r} | {cfg["drive"]["speed_rpm"]})
    rows, series = [], {}
    for key in list(cfg["topologies"]) + ["ilm_e_model"]:
        if key not in res:
            continue
        cells = [key if key != "ilm_e_model" else "ILM-E model"]
        pts = []
        for sp in speeds:
            r = res[key].get(str(int(sp)))
            if r is None and abs(sp - cfg["drive"]["speed_rpm"]) < 1e-6:
                vpath = os.path.join(rated, key, "verify", "optimal.json") if key != "ilm_e_model" else \
                    os.path.join(out, "reference_model", "study_rules.json")
                if os.path.isfile(vpath):
                    with open(vpath) as f:
                        r = json.load(f)
            if r and r.get("analysed"):
                ok = "" if r.get("violation", 1) == 0 else "*"
                cells.append(f"{r['torque_Nm']:.2f} / {100 * r['efficiency']:.0f}{ok}")
                pts.append((sp, r["torque_Nm"]))
            else:
                cells.append("-")
        rows.append(cells)
        series[cells[0]] = pts
    bound = []
    for sp in speeds:
        w = 2 * math.pi * sp / 60
        v = cfg["drive"]["modulation"] * cfg["drive"]["bus_voltage_V"] / math.sqrt(3) * 0.97
        bound.append(1.5 * v * cfg["drive"]["rated_current_A"] * 0.9 / w)
    md = ["## Rated torque against the rated speed", "",
          "The optimal pick of each topology wound again for other rated speeds (the turns follow the voltage at "
          f"{cfg['drive']['rated_current_A']} A, the efficiency limit stays {100 * cfg['limits']['min_efficiency']:.0f} %). Cells: rated torque (Nm) "
          "/ efficiency (%); * a limit is not met (mostly the efficiency at low speed or the current density). Upper bound of any "
          "machine on this drive at power factor 1 and 90 % efficiency: " +
          ", ".join(f"{b:.1f} Nm at {sp:.0f} rpm" for sp, b in zip(speeds, bound)) + ".", "",
          table(["Topology"] + [f"{sp:.0f} rpm" for sp in speeds], rows), ""]
    best = sorted([k for k in series if k != "ILM-E model" and series[k]], key=lambda k: -max(t for _, t in series[k]))[:3]
    show = best + (["ILM-E model"] if "ILM-E model" in series else [])
    if show:
        allt = [t for k in show for _, t in series[k]] + [0.0]
        c = Chart((speeds[0], speeds[-1]), _range(allt), "Rated speed (rpm)", "Rated torque at 10.5 A (Nm)",
                  "Rated torque against the rated speed (leading topologies)", width=880, height=340)
        colours = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
        for k, col in zip(show, colours):
            xs, ys = zip(*series[k])
            c.line(xs, ys, col, label=k)
            for x, y in zip(xs, ys):
                c.marker(x, y, col)
        save(os.path.join(figs, "speed_sensitivity.svg"), [c])
        md += ["![Rated torque against the rated speed](figures/speed_sensitivity.svg)", ""]
    return "\n".join(md)


def build(cfg, out, log=print):
    rep = os.path.join(out, "report")
    figs = os.path.join(rep, "figures")
    os.makedirs(figs, exist_ok=True)
    data = collect(cfg, out)
    write_pareto(data, cfg, os.path.join(rep, "pareto.html"))
    drive, ref = cfg["drive"], cfg["reference"]
    rows, sections = [], []
    for key, item in data.items():
        sec = [f"### {key}: {item['title']}", "", item["summary"], "", f"Variable ranges from: {item['sources']}.", ""]
        designs = item["designs"]
        analysed = [d for d in designs if d.get("analysed")]
        feasible = [d for d in analysed if d.get("violation", 1) == 0]
        sec.append(f"Designs evaluated: {len(designs)}; drawn and solved: {len(analysed)}; within every limit: {len(feasible)}.")
        sec.append("")
        reasons = {}
        for d in analysed:
            for k, v in (d.get("constraints") or {}).items():
                if v > 0:
                    reasons[k] = reasons.get(k, 0) + 1
        if reasons:
            sec.append("Limits that rejected solved designs: " + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items(), key=lambda x: -x[1])) + ".")
            sec.append("")
        shown = set()
        for name in ("optimal", "highest_torque", "closest"):
            r = item["verified"].get(name)
            if not r or not r.get("analysed"):
                continue
            tag = json.dumps(r["values"], sort_keys=True)
            same = tag in shown
            if same:                             # one row for picks that are the same design
                rows[-1][1] = "optimal = highest torque"
            else:
                rows.append(pick_row(key, name, r, cfg))
            shown.add(tag)
            title = name.replace("_", " ")
            if same:
                sec.append(f"The {title} pick is the same design as the optimal pick.")
                sec.append("")
                continue
            sec.append(f"#### Pick: {title} (design {r.get('id')})")
            sec.append("")
            base = f"{key}_{name}"
            if sketch_of(item["rundir"], (r.get("picks") or [name])[0], os.path.join(figs, base + "_sketch.svg")):
                sec.append(f"![{key} {title}: section](figures/{base}_sketch.svg)")
                sec.append("")
            dims = (r.get("design") or {}).get("dims") or {}
            wind = (r.get("design") or {}).get("winding") or {}
            sec.append("Dimensions: " + ", ".join(f"{k.replace('_', ' ')} {fmt(v) if isinstance(v, float) else v}" for k, v in dims.items()) + ".")
            sec.append("")
            if wind.get("label"):
                sec.append(f"Winding: {wind.get('label')}, q = {wind.get('q_text', '-')}, k_w1 = {fmt(wind.get('k_w1'), 3)}"
                           if wind.get("k_w1") else f"Winding: {wind.get('label')}")
                sec.append("")
            w = r["winding"]
            sec.append(f"Result (verified, finer mesh, {len(r.get('torque_waveform_Nm') or [])} rotor positions): rated torque "
                       f"{fmt(r['torque_Nm'])} Nm at {drive['rated_current_A']} A and {drive['speed_rpm']:.0f} rpm, peak torque "
                       f"{fmt(r['peak_torque_Nm'])} Nm at {drive['peak_current_A']:.0f} A, ripple {fmt(100 * r['ripple'], 1)} %, efficiency "
                       f"{fmt(100 * r['efficiency'], 1)} %, {w['turns_per_coil']} turns per coil of {w['strands']} x AWG {w['awg']} "
                       f"({fmt(w['wire_diameter_mm'], 3)} mm), {w['paths']} parallel path(s), fill {fmt(w['fill'])}, phase resistance "
                       f"{fmt(1000 * w['resistance_20C_ohm'], 0)} mOhm at 20 C.")
            if r.get("principle") == "srm":
                s = r["srm"]
                sec.append(f"SRM drive: turn-on {fmt(s['theta_on_deg'], 1)} deg, turn-off {fmt(s['theta_off_deg'], 1)} deg (mechanical, "
                           f"from the aligned position), chopping at {fmt(s['i_ref_A'], 1)} A, phase rms {fmt(s['rms_current_A'], 2)} A.")
            sec.append("")
            if r.get("waveforms") and r.get("principle") != "srm":
                phase_figure(r, os.path.join(figs, base + "_phase_voltage.svg"), drive)
                sec.append(f"![{key} {title}: phase voltages and flux linkages](figures/{base}_phase_voltage.svg)")
                sec.append("")
            elif r.get("waveforms"):
                srm_figure(r, os.path.join(figs, base + "_phase_voltage.svg"), drive)
                sec.append(f"![{key} {title}: SRM phase voltage, current and flux](figures/{base}_phase_voltage.svg)")
                sec.append("")
            if emf_figure(r, os.path.join(figs, base + "_emf.svg")):
                sec.append(f"![{key} {title}: back-EMF](figures/{base}_emf.svg)")
                sec.append("")
            if torque_figure(r, os.path.join(figs, base + "_torque.svg")):
                sec.append(f"![{key} {title}: torque](figures/{base}_torque.svg)")
                sec.append("")
            views = os.path.join(out, "paraview", base, "views")
            if os.path.isdir(views):
                for png in ("rated_discs.png", "materials_discs.png", "rated_field.png", "rated_field_zoom.png", "rated_unrolled.png", "materials_unrolled.png", "peak_field.png", "peak_field_zoom.png", "aligned_peak_field.png", "1_full_motor.png", "6_radial_and_axial_field.png",
                            "no_load_field.png"):
                    if os.path.isfile(os.path.join(views, png)):
                        sec.append(f"![{key} {title}: {png[:-4].replace('_', ' ')}](../paraview/{base}/views/{png})")
                sec.append("")
                sec.append(f"ParaView files: `paraview/{base}/` (open `rated.pvd`, `peak.pvd`; `summary.json` lists them).")
                sec.append("")
        sections.append("\n".join(sec))
    ilm_row = ["ILM-E85x23 (datasheet)", "reference", "?/20 FSCW", fmt(ref["rated_torque_Nm"]), fmt(ref["kt_Nm_A"], 3),
               fmt(ref["peak_torque_Nm"]), "-", "-", f"{ref['max_efficiency'] * 100:.0f} (max)",
               f"{ref['copper_loss_rated_20C_W']} (Cu at 20 C)", fmt(ref["km_Nm_sqrtW"], 3), fmt(ref["rated_torque_Nm"]), "star-serial", "-", "-", "-",
               f"{ref['mass_g'] / 1000:.3f} (kit)", fmt(ref["peak_torque_Nm"] / (ref["mass_g"] / 1000), 1), fmt(ref["stator_length_mm"], 1),
               "datasheet"]
    extra = []
    ref_path = os.path.join(out, "reference_model", "summary.json")
    if os.path.isfile(ref_path):
        with open(ref_path) as f:
            refmodel = json.load(f)
        for name, r in refmodel.get("records", {}).items():
            if r.get("analysed"):
                extra.append(pick_row("ILM-E model", name, r, cfg))
    rows_sorted = sorted(rows, key=lambda r: -float(r[5]) if r[5] != "-" else 0)
    findings = ""
    fpath = os.path.join(rep, "findings.md")
    if os.path.isfile(fpath):
        with open(fpath) as f:
            findings = f.read()
    speed = speed_section(cfg, out, figs)
    md = [f"# {cfg['title']}", "",
          "Written for the tfm-machine project team; produced by `emachine.analysis.topology_report` "
          "(tickets T58 to T66).", "", findings, "",
          "## Interactive Pareto charts", "",
          "[pareto.html](pareto.html): every evaluated design of each topology, any two of rated torque, peak torque, ripple, "
          "efficiency, motor constant, losses and masses as axes; hover for values, click to keep a design. Works offline.", "",
          "## Comparison of the picks with the ILM-E85x23", "",
          "Verified picks (finer mesh, more rotor positions, no-load sweep), sorted by peak torque. Rated point: "
          f"{drive['rated_current_A']} A amplitude at {drive['speed_rpm']:.0f} rpm, the winding chosen for {drive['bus_voltage_V']:.0f} V "
          f"(line voltage at most {drive['modulation'] * drive['bus_voltage_V']:.1f} V); peak: {drive['peak_current_A']:.0f} A at low speed. "
          "Optimal pick: the most rated torque with ripple at most "
          f"{100 * cfg['limits']['pick_max_ripple']:.0f} % and every limit met; highest torque: the most rated torque, any ripple.", "",
          table(HEADER, rows_sorted + extra + [ilm_row]), "", speed, "",
          "## Topologies", "", "\n\n".join(sections), "", METHOD.format(**{**drive, **cfg["limits"],
                                                                            "lo": cfg["limits"]["fill_range"][0], "hi": cfg["limits"]["fill_range"][1]})]
    text = "\n".join(md)
    with open(os.path.join(rep, "report.md"), "w") as f:
        f.write(text)
    with open(os.path.join(rep, "report.html"), "w") as f:
        f.write(md_to_html(text, "Multi-topology study, ILM-E85x23 envelope"))
    log(f"report -> {rep}")
    return rep


def srm_figure(record, path, drive):
    w = record["waveforms"]
    t = np.asarray(w["time_s"]) * 1000.0
    charts = []
    for name, unit, label in (("voltage_V", "Voltage (V)", "Phase voltages (asymmetric half bridge)"),
                              ("current_A", "Current (A)", "Phase currents"), ("flux_Wb", "Flux linkage (Wb-turns)", "Phase flux linkages")):
        v = np.asarray(w[name])
        c = Chart((t[0], t[-1]), _range(v), "Time (ms)", unit, f"{record['machine']}: {label}, rated point", width=880, height=260)
        for k in range(v.shape[1]):
            c.line(t, v[:, k], PHASE_COLOURS[k], label="ABC"[k])
        charts.append(c)
    save(path, charts)


METHOD = """## Method, assumptions and limits of the models

- **Envelope** (the ILM-E85x23 form factor): outer diameter 85 mm, inner diameter of every active part 52 mm (the ILM-E's
  hollow rotor), active length 30 mm. Radial machines: a 30 mm stack, end windings outside it (the table gives the length
  with them; the ILM-E: 35.7 mm stator with end windings over a 25.2 mm rotor). Axial machines: discs, stators and gaps
  within 30 mm, end windings in the radial room.
- **Drive**: {bus_voltage_V:.0f} V DC link, space-vector modulation with a line-voltage limit of {modulation} x 48 V,
  {rated_current_A} A rated and {peak_current_A:.0f} A peak phase current (amplitude), as the ILM-E85x23 (peak current from
  8.31 Nm at 20 % below the linear torque: 8.31 / (0.8 x 0.247)). The SRM uses an asymmetric half bridge on the same bus and the
  same rms phase current (7.42 A) at the rated point.
- **Turns**: the most effective turns (turns per coil over parallel paths) for which the phase voltage at {rated_current_A} A and
  {speed_rpm:.0f} rpm stays 3 % below the limit, fewer if the efficiency there would be below {min_efficiency:.0%}; then the
  winding with the fewest strands of AWG 12 to 32 that fills {lo} to {hi} of the coil side.
- **Field model**: 2D magnetostatics (Gmsh, Elmer MagnetoDynamics2D) with saturating iron (Froehlich curves: laminations mu_r 4000,
  1.75 T; SMC mu_r 600, 1.95 T), whole cross-section, torque by Arkkio's method in every air gap; axial machines as two (in the
  optimization) or three (verification) unrolled slices at the Gauss radii of the active annulus, periodic around. End effects,
  3D leakage and end-winding fields are not modelled (axial machines: the slices neglect the radial flux components).
- **Currents**: sinusoidal; the current angle of the most torque at the rated point (six angles, refined) and again at the peak
  current (MTPA). SRM: one phase solved alone over half a rotor pole pitch at six currents; dynamic model with chopping; firing
  angles optimized; peak torque from ideal flat-top currents at low speed.
- **Ripple**: (highest - lowest) / mean of the torque at the rated point over half an electrical period (12 positions in the
  optimization, 36 in the verification, skew applied to the harmonics); deterministic ripple of this kind can largely be
  cancelled by the drive (harmonic current injection, learned feed-forward), see docs/design_principles.md.
- **Losses**: copper at 100 C, stator core loss per element from the flux density over a period (M270-35A for laminations,
  Somaloy for SMC), eddy-current loss of magnets and rotor iron; no mechanical, PWM or end-winding proximity losses.
- **Not modelled**: thermal limits beyond the current density (the ILM-E's rated point is a continuous thermal rating, ours is a
  copper current density of {max_j_rated_rms_A_mm2} A/mm2 rms), demagnetisation at the peak current, mechanical stress of the
  rotor bridges, manufacturing tolerances.
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    build(cfg, args.out or cfg["_dir"])


if __name__ == "__main__":
    main()
