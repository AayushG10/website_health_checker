"""
server.py - local MCP server + live dashboard host (one process, two faces).

  1. MCP tools over stdio  -> Claude Code calls: li_load, li_graph, li_anchors,
     li_topics, li_entities, li_recommend, li_report, li_export
  2. HTTP + SSE on localhost:7700 -> the live cockpit that fills as the analysis runs.

STARTER: works end to end out of the box. The deterministic analysis (graph, orphans,
anchor classes) is complete; the model-driven parts (cluster names, entity extraction,
contextual link anchors) are wired as setter tools the agents call.

Needs the MCP SDK to expose tools to Claude (`pip install mcp`); without it the dashboard
still runs so you can use run.py. Standard library otherwise.
"""
from __future__ import annotations
import json, os, queue, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DASH_DIR = os.path.join(ROOT, "dashboard")
OUT_DIR = os.path.join(ROOT, "outputs")
PORT = int(os.environ.get("LI_PORT", os.environ.get("SEO_PORT", "7700")))
MODEL = os.environ.get("RADAR_MODEL", os.environ.get("LI_MODEL", "gpt-oss:20b-cloud"))

import sys
sys.path.insert(0, ROOT)
from linkintel import analyzer  # noqa: E402

RUN = {"site": None, "urls": 0, "status": "idle",
       "graph_stats": None, "anchors": None, "clusters": None,
       "entities": None, "relatedness": None, "recommendations": None,
       "summary": None}
_A = {}            # full analysis blob (kept out of RUN so /state stays light)
_subs: list[queue.Queue] = []
_lock = threading.Lock()


def _emit(event, data):
    payload = json.dumps({"event": event, "data": data})
    with _lock:
        for q in list(_subs):
            try: q.put_nowait(payload)
            except Exception: pass


def _site(pages):
    if not pages: return "unknown"
    try: return urlparse(pages[0].get("Address", "")).netloc or "unknown"
    except Exception: return "unknown"


# ---------- pipeline tools (importable by run.py without MCP) ----------
def li_load(export_dir: str) -> dict:
    res = analyzer.analyze(export_dir)
    _A.clear(); _A.update(res)
    RUN.update({"urls": res["graph_stats"]["pages_total"],
                "site": _site(res["pages"]), "status": "running",
                "page_text_count": res["page_text_count"]})
    _emit("loaded", {"site": RUN["site"], "urls": RUN["urls"],
                     "page_text": res["page_text_count"]})
    return {"urls": RUN["urls"], "site": RUN["site"], "page_text": res["page_text_count"]}


def li_graph() -> dict:
    g = _A["graph_stats"]
    RUN["graph_stats"] = {
        "pages_total": g["pages_total"], "pages_indexable": g["pages_indexable"],
        "internal_links": g["internal_links"], "max_crawl_depth": g["max_crawl_depth"],
        "avg_inlinks": g["avg_inlinks"],
        "orphan_pages": len(g["orphan_pages"]), "deepest_pages": len(g["deepest_pages"]),
        "under_linked_pages": len(g["under_linked_pages"]),
        "over_linked_pages": len(g["over_linked_pages"]),
        "broken_internal_links": len(g["broken_internal_links"]),
        "redirect_internal_links": len(g["redirect_internal_links"]),
        "nofollow_internal_links": len(g["nofollow_internal_links"]),
    }
    _emit("graph", RUN["graph_stats"])
    return RUN["graph_stats"]


def li_anchors() -> dict:
    a = _A["anchors"]
    RUN["anchors"] = {"generic": len(a["generic_anchors"]),
                      "empty_or_image_only": len(a["empty_or_image_only"]),
                      "over_optimized": len(a["over_optimized_anchors"]),
                      "total": a["total_internal_anchors"]}
    _emit("anchors", RUN["anchors"])
    return RUN["anchors"]


def li_topics(names: dict = None) -> dict:
    """Compute clusters; `names` (optional) is {cluster_key: model_chosen_name}."""
    cl = _A["clusters"]["clusters"]
    if names:
        for c in cl:
            if c["key"] in names:
                c["name"] = names[c["key"]]
    RUN["clusters"] = [{"key": c["key"], "name": c["name"], "size": c["size"],
                        "hub_page": c["hub_page"], "authority": c["authority"],
                        "keywords": c["keywords"]} for c in cl]
    _emit("topics", {"clusters": RUN["clusters"]})
    return {"clusters": len(cl)}


def li_entities(entities: dict = None) -> dict:
    """Attach model-extracted entities per page: {url: [entity, ...]}.

    If provided, the relatedness graph is rebuilt on the richer entities.
    """
    if entities:
        _A["entities"] = entities
        _A["relatedness"] = analyzer.relatedness(entities)
        # refresh candidates against the new relatedness
        _A["link_candidates"] = analyzer.link_candidates(
            _A["graph"], _A["relatedness"], _A["pages"])
    RUN["entities"] = {"pages_with_entities": len(_A.get("entities") or {})}
    _emit("entities", RUN["entities"])
    return RUN["entities"]


def li_set_recommendations(recommendations: list) -> dict:
    """Attach the final contextual link recommendations written by the linker-agent.

    Each item: {source, target, suggested_anchor, relatedness, reason}.
    """
    _A["final_recs"] = recommendations or []
    RUN["recommendations"] = len(_A["final_recs"])
    RUN["link_recs"] = _A["final_recs"][:20]  # top 20 in state for dashboard
    _emit("recommendations", {"count": RUN["recommendations"]})
    return {"count": RUN["recommendations"]}


def _report_obj() -> dict:
    g = _A["graph_stats"]; a = _A["anchors"]; cl = _A["clusters"]["clusters"]
    recs = _A.get("final_recs")
    if recs is None:
        # starter fallback: surface raw candidates (no anchors) so the contract holds
        recs = []
        for blk in _A.get("link_candidates", []):
            for c in blk["candidates"]:
                recs.append({"source": blk["source"], "target": c["target"],
                             "suggested_anchor": c.get("suggested_anchor"),
                             "relatedness": c["relatedness"],
                             "reason": "shared topics: " + ", ".join(c["shared_topics"])})
    summary = {
        "pages_crawled": g["pages_total"],
        "indexable_pages": g["pages_indexable"],
        "internal_links": g["internal_links"],
        "orphan_pages": len(g["orphan_pages"]),
        "broken_internal_links": len(g["broken_internal_links"]),
        "generic_anchors": len(a["generic_anchors"]),
        "topical_clusters": len(cl),
        "link_recommendations": len(recs),
    }
    RUN["summary"] = summary
    return {
        "site": RUN["site"],
        "pages_crawled": g["pages_total"],
        "summary": summary,
        "link_graph": {
            "internal_links": g["internal_links"],
            "max_crawl_depth": g["max_crawl_depth"],
            "avg_inlinks": g["avg_inlinks"],
            "orphan_pages": g["orphan_pages"],
            "deepest_pages": g["deepest_pages"],
            "under_linked_pages": g["under_linked_pages"],
            "over_linked_pages": g["over_linked_pages"],
            "broken_internal_links": g["broken_internal_links"],
            "redirect_internal_links": g["redirect_internal_links"],
            "nofollow_internal_links": g["nofollow_internal_links"],
        },
        "anchor_text": {
            "total_internal_anchors": a["total_internal_anchors"],
            "generic_anchors": a["generic_anchors"],
            "empty_or_image_only": a["empty_or_image_only"],
            "over_optimized_anchors": a["over_optimized_anchors"],
        },
        "topical_clusters": [
            {"key": c["key"], "name": c["name"], "size": c["size"], "pages": c["pages"],
             "hub_page": c["hub_page"], "hub_inlinks": c["hub_inlinks"],
             "authority": c["authority"], "keywords": c["keywords"]} for c in cl
        ],
        "entity_graph": _A.get("relatedness", {}),
        "link_recommendations": recs,
        "run_meta": {"model": MODEL, "model_calls": RUN.get("model_calls", 0),
                     "duration_sec": RUN.get("duration_sec", 0)},
    }


def li_report() -> dict:
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "report.json")
    json.dump(_report_obj(), open(p, "w", encoding="utf-8"), indent=2)
    RUN["status"] = "done"; _emit("saved", {"path": p}); return {"path": p}


def li_export() -> dict:
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "report.html")
    open(p, "w", encoding="utf-8").write(_render_html(_report_obj()))
    _emit("exported", {"path": p}); return {"path": p}


def _render_html(o) -> str:
    s  = o["summary"]
    g  = o["link_graph"]
    at = o["anchor_text"]

    # ── health score (simple weighted formula) ───────────────────────────────
    score = 100
    score -= min(len(g["orphan_pages"]) * 3, 15)
    score -= min(len(g["broken_internal_links"]) * 5, 15)
    score -= min(len(g.get("redirect_internal_links", [])) * 1, 5)
    score -= min(len(at["generic_anchors"]) * 0.5, 10)
    score -= min(len(at["over_optimized_anchors"]) * 5, 5)
    scattered = sum(1 for c in o["topical_clusters"] if c.get("authority") == "scattered")
    score -= min(scattered * 5, 20)
    under = len(g.get("under_linked_pages", []))
    score -= min(under * 0.5, 5)
    maxd = g.get("max_crawl_depth", 0)
    score -= (10 if maxd > 6 else 5 if maxd > 4 else 0)
    score = max(0, round(score))
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 45 else "F"
    grade_color = {"A":"#22c55e","B":"#6ea8fe","C":"#e2b53e","D":"#f97316","F":"#FF0000"}.get(grade,"#c8c5be")

    # ── helpers ──────────────────────────────────────────────────────────────
    def slug(url): return (url or "").replace("https://","").replace("http://","")
    def tag(label, color, bg):
        return f'<span style="font-size:11px;font-weight:700;padding:2px 9px;border-radius:999px;background:{bg};color:{color}">{label}</span>'
    def badge_auth(a):
        return tag("hub","#04210f","#22c55e") if a=="hub" else tag("scattered","#c8c5be","#3a3a42")

    # ── section: clusters ─────────────────────────────────────────────────────
    cl_rows = "".join(
        f'<tr><td><strong>{c.get("name") or c["key"]}</strong></td>'
        f'<td>{c["size"]}</td>'
        f'<td>{badge_auth(c.get("authority","scattered"))}</td>'
        f'<td class="mono" style="font-size:11px;color:#c8c5be">{slug(c.get("hub_page") or "")}</td></tr>'
        for c in o["topical_clusters"])

    # ── section: recommendations ──────────────────────────────────────────────
    rec_rows = "".join(
        f'<tr>'
        f'<td class="mono" style="font-size:11px;color:#c8c5be">{slug(r["source"])}</td>'
        f'<td class="mono" style="font-size:11px">{slug(r["target"])}</td>'
        f'<td><strong style="color:#6ea8fe">{r.get("suggested_anchor") or "(pending)"}</strong></td>'
        f'<td style="color:#c8c5be">{r.get("reason","")[:60]}</td>'
        f'</tr>'
        for r in o["link_recommendations"][:50])

    # ── section: broken links ─────────────────────────────────────────────────
    broken_rows = "".join(
        f'<tr>'
        f'<td class="mono" style="font-size:11px;color:#c8c5be">{slug(b["source"])}</td>'
        f'<td class="mono" style="font-size:11px">{slug(b["destination"])}</td>'
        f'<td>{tag(str(b["status"]),"#fff","#FF0000")}</td>'
        f'<td style="color:#c8c5be">{(b.get("anchor") or "")[:40]}</td>'
        f'</tr>'
        for b in g["broken_internal_links"][:30])

    # ── section: generic anchors ──────────────────────────────────────────────
    generic_rows = "".join(
        f'<tr>'
        f'<td class="mono" style="font-size:11px;color:#c8c5be">{slug(a["source"])}</td>'
        f'<td class="mono" style="font-size:11px">{slug(a["destination"])}</td>'
        f'<td style="color:#e2b53e">{a.get("anchor","")}</td>'
        f'</tr>'
        for a in at["generic_anchors"][:30])

    # ── section: orphan pages ─────────────────────────────────────────────────
    orphan_items = "".join(
        f'<div style="padding:5px 0;border-bottom:1px solid #3a3a42;font-family:monospace;font-size:12px;color:#c8c5be">{slug(u)}</div>'
        for u in g["orphan_pages"][:20]) or '<div style="color:#c8c5be;font-size:13px">No orphan pages found.</div>'

    # ── section: over-optimised anchors ──────────────────────────────────────
    over_rows = "".join(
        f'<tr>'
        f'<td class="mono" style="font-size:11px;color:#c8c5be">{slug(a["destination"])}</td>'
        f'<td><strong style="color:#f97316">{a["anchor"]}</strong></td>'
        f'<td>{a["count"]}</td>'
        f'<td>{int(a.get("share",0)*100)}%</td>'
        f'</tr>'
        for a in at["over_optimized_anchors"][:20])

    # ── section: editorially invisible ───────────────────────────────────────
    invisible = g.get("editorially_invisible_pages", [])
    invisible_items = "".join(
        f'<div style="padding:5px 0;border-bottom:1px solid #3a3a42;font-family:monospace;font-size:12px;color:#c8c5be">{slug(u)}</div>'
        for u in invisible[:20]) or '<div style="color:#22c55e;font-size:13px">All pages have editorial links.</div>'

    model = o.get("run_meta", {}).get("model", "")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Internal Linking Report — {o['site']}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Inter,system-ui,sans-serif;background:#0f0f13;color:#f8f7f4;line-height:1.6;padding:40px 20px}}
.wrap{{max-width:980px;margin:0 auto}}
h1{{font-size:26px;font-weight:700;margin-bottom:4px}}
h2{{font-size:16px;font-weight:600;margin-bottom:14px;color:#f8f7f4}}
.sub{{color:#c8c5be;font-size:14px;margin-bottom:32px}}
.card{{background:#17171c;border:1px solid #2e2e38;border-radius:14px;padding:24px;margin-bottom:20px}}
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px}}
.kpi{{background:#17171c;border:1px solid #2e2e38;border-radius:12px;padding:18px}}
.kpi .val{{font-size:32px;font-weight:700;line-height:1;display:block;margin-bottom:4px}}
.kpi .lbl{{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:#c8c5be}}
.grade-box{{background:#17171c;border:1px solid #2e2e38;border-radius:14px;padding:24px;margin-bottom:20px;display:flex;align-items:center;gap:28px}}
.grade-circle{{width:88px;height:88px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:42px;font-weight:700;flex-shrink:0;border:3px solid {grade_color};color:{grade_color}}}
.grade-detail{{flex:1}}
.grade-detail h2{{font-size:18px;margin-bottom:6px}}
.grade-detail p{{font-size:13px;color:#c8c5be;margin-bottom:10px}}
.score-bar-bg{{background:#2e2e38;border-radius:999px;height:8px;width:100%}}
.score-bar-fill{{background:{grade_color};border-radius:999px;height:8px;width:{score}%}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#c8c5be;padding:8px 10px;border-bottom:1px solid #2e2e38;text-align:left}}
td{{padding:9px 10px;border-bottom:1px solid #2e2e38;vertical-align:top}}
tr:last-child td{{border-bottom:none}}
.mono{{font-family:'JetBrains Mono',monospace}}
.section-label{{font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:#c8c5be;margin-bottom:10px;display:flex;align-items:center;gap:8px}}
.dot-red{{width:8px;height:8px;border-radius:50%;background:#FF0000;display:inline-block}}
.dot-amber{{width:8px;height:8px;border-radius:50%;background:#e2b53e;display:inline-block}}
.dot-green{{width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block}}
.dot-blue{{width:8px;height:8px;border-radius:50%;background:#6ea8fe;display:inline-block}}
.footer{{color:#c8c5be;font-size:12px;margin-top:32px;padding-top:16px;border-top:1px solid #2e2e38}}
</style>
</head>
<body>
<div class="wrap">

<h1>Internal Linking Intelligence</h1>
<div class="sub">{o['site']} &nbsp;·&nbsp; {o['pages_crawled']} pages crawled &nbsp;·&nbsp; model: {model}</div>

<!-- HEALTH SCORE -->
<div class="grade-box">
  <div class="grade-circle">{grade}</div>
  <div class="grade-detail">
    <h2>Site Link Health Score: {score}/100</h2>
    <p>Based on orphan pages, broken links, anchor quality, topical authority, and crawl depth.</p>
    <div class="score-bar-bg"><div class="score-bar-fill"></div></div>
  </div>
</div>

<!-- KPI CARDS -->
<div class="kpi-grid">
  <div class="kpi"><span class="val">{s['internal_links']}</span><span class="lbl">Internal Links</span></div>
  <div class="kpi"><span class="val" style="color:#e2b53e">{s['orphan_pages']}</span><span class="lbl">Orphan Pages</span></div>
  <div class="kpi"><span class="val" style="color:#FF0000">{s['broken_internal_links']}</span><span class="lbl">Broken Links</span></div>
  <div class="kpi"><span class="val" style="color:#e2b53e">{s['generic_anchors']}</span><span class="lbl">Generic Anchors</span></div>
  <div class="kpi"><span class="val">{s['topical_clusters']}</span><span class="lbl">Topic Clusters</span></div>
  <div class="kpi"><span class="val" style="color:#6ea8fe">{s['link_recommendations']}</span><span class="lbl">Link Suggestions</span></div>
  <div class="kpi"><span class="val" style="color:#f97316">{len(invisible)}</span><span class="lbl">Editorially Invisible</span></div>
  <div class="kpi"><span class="val" style="color:#f97316">{scattered}</span><span class="lbl">Scattered Clusters</span></div>
</div>

<!-- BROKEN LINKS -->
<div class="card">
  <div class="section-label"><span class="dot-red"></span>Broken Internal Links ({len(g["broken_internal_links"])} total)</div>
  {"<p style='color:#22c55e;font-size:13px'>No broken internal links found.</p>" if not g["broken_internal_links"] else
  f'<table><thead><tr><th>Source page</th><th>Broken destination</th><th>Status</th><th>Anchor</th></tr></thead><tbody>{broken_rows}</tbody></table>'}
  {"" if len(g["broken_internal_links"]) <= 30 else f'<p style="color:#c8c5be;font-size:12px;margin-top:8px">Showing 30 of {len(g["broken_internal_links"])} broken links.</p>'}
</div>

<!-- ORPHAN PAGES -->
<div class="card">
  <div class="section-label"><span class="dot-amber"></span>Orphan Pages — no inlinks ({len(g["orphan_pages"])} total)</div>
  {orphan_items}
</div>

<!-- EDITORIALLY INVISIBLE -->
<div class="card">
  <div class="section-label"><span class="dot-amber"></span>Editorially Invisible Pages ({len(invisible)} total)</div>
  <p style="font-size:13px;color:#c8c5be;margin-bottom:12px">These pages appear in nav/header/footer but no article body text links to them. Zero editorial endorsement.</p>
  {invisible_items}
</div>

<!-- TOPICAL CLUSTERS -->
<div class="card">
  <div class="section-label"><span class="dot-blue"></span>Topical Clusters &amp; Authority ({len(o["topical_clusters"])} clusters, {scattered} scattered)</div>
  <table><thead><tr><th>Cluster</th><th>Pages</th><th>Authority</th><th>Hub page</th></tr></thead>
  <tbody>{cl_rows or '<tr><td colspan=4 style="color:#c8c5be">No clusters.</td></tr>'}</tbody></table>
</div>

<!-- LINK RECOMMENDATIONS -->
<div class="card">
  <div class="section-label"><span class="dot-green"></span>Contextual Link Recommendations ({len(o["link_recommendations"])} suggestions)</div>
  <table><thead><tr><th>From page</th><th>Should link to</th><th>Suggested anchor</th><th>Reason</th></tr></thead>
  <tbody>{rec_rows or '<tr><td colspan=4 style="color:#c8c5be">No recommendations.</td></tr>'}</tbody></table>
  {"" if len(o["link_recommendations"]) <= 50 else f'<p style="color:#c8c5be;font-size:12px;margin-top:8px">Showing 50 of {len(o["link_recommendations"])} recommendations.</p>'}
</div>

<!-- ANCHOR TEXT -->
<div class="card">
  <div class="section-label"><span class="dot-amber"></span>Generic Anchors ({len(at["generic_anchors"])} found)</div>
  {"<p style='color:#22c55e;font-size:13px'>No generic anchors found.</p>" if not at["generic_anchors"] else
  f'<table><thead><tr><th>Source</th><th>Destination</th><th>Anchor text</th></tr></thead><tbody>{generic_rows}</tbody></table>'}
</div>

{"" if not at["over_optimized_anchors"] else f'''
<div class="card">
  <div class="section-label"><span class="dot-red"></span>Over-Optimised Anchors ({len(at["over_optimized_anchors"])} destinations)</div>
  <p style="font-size:13px;color:#c8c5be;margin-bottom:12px">One non-generic anchor accounts for &ge;60% of all internal links to this page with &ge;10 uses — unnatural pattern.</p>
  <table><thead><tr><th>Destination</th><th>Dominant anchor</th><th>Count</th><th>Share</th></tr></thead>
  <tbody>{over_rows}</tbody></table>
</div>
'''}

<div class="footer">Generated by Link Intel Suite &nbsp;·&nbsp; model: {model} &nbsp;·&nbsp; {o['pages_crawled']} pages &nbsp;·&nbsp; {s['internal_links']} internal links</div>
</div>
</body>
</html>"""


# ---------- dashboard HTTP host ----------
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache"); self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else body)
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            p = os.path.join(DASH_DIR, "index.html")
            self._send(200, open(p, encoding="utf-8").read() if os.path.exists(p) else "no dashboard")
        elif self.path == "/app.js":
            p = os.path.join(DASH_DIR, "app.js")
            self._send(200, open(p, encoding="utf-8").read() if os.path.exists(p) else "", "application/javascript")
        elif self.path == "/state":
            self._send(200, json.dumps(RUN), "application/json")
        elif self.path == "/events":
            self.send_response(200); self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache"); self.end_headers()
            q = queue.Queue()
            with _lock: _subs.append(q)
            try:
                self.wfile.write(f"data: {json.dumps({'event':'snapshot','data':RUN})}\n\n".encode()); self.wfile.flush()
                while True:
                    try: self.wfile.write(f"data: {q.get(timeout=15)}\n\n".encode())
                    except queue.Empty: self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except Exception: pass
            finally:
                with _lock:
                    if q in _subs: _subs.remove(q)
        else: self._send(404, "not found")


def start_dashboard(port=PORT):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _run_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print(f"[li] MCP SDK not found. Dashboard only at http://localhost:{PORT}", flush=True)
        while True: time.sleep(3600)
    mcp = FastMCP("link-intel-suite")

    @mcp.tool()
    def load(export_dir: str) -> dict:
        """Load a Screaming Frog export (internal_html.csv + all_inlinks.csv + page text/)."""
        return li_load(export_dir)

    @mcp.tool()
    def graph_stats() -> dict:
        """Run the deterministic internal-link graph analysis (orphans, depth, broken/redirect/nofollow)."""
        return li_graph()

    @mcp.tool()
    def anchors() -> dict:
        """Run anchor-text analysis (generic, empty/image-only, over-optimized)."""
        return li_anchors()

    @mcp.tool()
    def topics(names: dict = None) -> dict:
        """Compute topical clusters; optionally attach model-chosen cluster names {key:name}."""
        return li_topics(names)

    @mcp.tool()
    def entities(entities: dict = None) -> dict:
        """Attach model-extracted entities per page {url:[entity,...]} and rebuild the entity graph."""
        return li_entities(entities)

    @mcp.tool()
    def recommend(recommendations: list) -> dict:
        """Attach the final contextual link recommendations [{source,target,suggested_anchor,relatedness,reason}]."""
        return li_set_recommendations(recommendations)

    @mcp.tool()
    def write_report() -> dict:
        """Write outputs/report.json (the grader reads this)."""
        return li_report()

    @mcp.tool()
    def export_report() -> dict:
        """Write outputs/report.html (the client deliverable)."""
        return li_export()

    mcp.run()


if __name__ == "__main__":
    start_dashboard()
    print(f"[li] dashboard live at http://localhost:{PORT}", flush=True)
    _run_mcp()
