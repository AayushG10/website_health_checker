"""
notion_sync.py - push Link Intel analysis to Notion via REST API.
Standard library only (urllib). No external dependencies.

Usage:
  from linkintel.notion_sync import export_report, verify_token
  url = export_report(token, parent_page_id, RUN)
"""
from __future__ import annotations
import json
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError

API      = "https://api.notion.com/v1"
VERSION  = "2022-06-28"


# ─────────────────────────────────────────── HTTP helper ──────
def _req(method: str, path: str, token: str, data: dict | None = None) -> dict:
    body = json.dumps(data).encode() if data else None
    req  = Request(API + path, data=body, method=method)
    req.add_header("Authorization",   f"Bearer {token}")
    req.add_header("Notion-Version",  VERSION)
    req.add_header("Content-Type",    "application/json")
    try:
        with urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except HTTPError as e:
        msg = ""
        try: msg = json.loads(e.read()).get("message", "")
        except Exception: pass
        raise RuntimeError(msg or f"Notion API error {e.code}")


# ─────────────────────────────────────────── block builders ───
def _h2(text: str) -> dict:
    return {"type": "heading_2",
            "heading_2": {"rich_text": [{"type":"text","text":{"content": text}}]}}

def _h3(text: str) -> dict:
    return {"type": "heading_3",
            "heading_3": {"rich_text": [{"type":"text","text":{"content": text}}]}}

def _divider() -> dict:
    return {"type": "divider", "divider": {}}

def _paragraph(text: str, color: str = "default") -> dict:
    return {"type": "paragraph",
            "paragraph": {"rich_text": [{"type":"text","text":{"content": text},
                                         "annotations":{"color": color}}]}}

def _bullet(parts: list[dict]) -> dict:
    return {"type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": parts}}

def _todo(text: str, checked: bool = False) -> dict:
    return {"type": "to_do",
            "to_do": {"rich_text": [{"type":"text","text":{"content": text}}],
                      "checked": checked}}

def _callout(text: str, emoji: str, color: str = "gray_background") -> dict:
    return {"type": "callout",
            "callout": {
                "rich_text": [{"type":"text","text":{"content": text}}],
                "icon": {"type":"emoji","emoji": emoji},
                "color": color,
            }}

def _rich(text: str, bold=False, italic=False, color="default") -> dict:
    return {"type": "text", "text": {"content": text},
            "annotations": {"bold": bold, "italic": italic, "color": color}}

def _code(text: str) -> dict:
    return {"type": "code",
            "code": {"rich_text": [{"type":"text","text":{"content": text}}],
                     "language": "plain text"}}


# ─────────────────────────────────────────── main export ──────
def verify_token(token: str) -> dict:
    """Return the integration bot info or raise on bad token."""
    return _req("GET", "/users/me", token)


def export_report(token: str, parent_page_id: str, run: dict) -> str:
    """
    Create a Notion report page under parent_page_id.
    Returns the URL of the created page.
    """
    site    = run.get("site") or "Unknown"
    score   = run.get("health_score", 0)
    grade   = run.get("health_grade", "?")
    summary = run.get("summary") or {}
    fixes   = (run.get("priority_fixes") or [])[:15]
    recs    = (run.get("link_recs") or [])[:20]
    dm      = run.get("digital_marketing") or {}
    cannibal = (dm.get("cannibalization") or [])[:10]
    money   = (dm.get("money_pages") or [])[:8]
    opps    = (dm.get("seo_opportunities") or [])[:8]
    clusters= (run.get("clusters") or [])[:10]

    date_str = datetime.now().strftime("%B %d, %Y")

    grade_color = {"A":"green_background","B":"blue_background",
                   "C":"yellow_background","D":"orange_background","F":"red_background"}.get(grade,"gray_background")

    # ── title page ────────────────────────────────────────────
    page_title = f"Link Intel — {site} — {date_str}"

    # ── health score callout ───────────────────────────────────
    grade_emoji = {"A":"🟢","B":"🔵","C":"🟡","D":"🟠","F":"🔴"}.get(grade,"⚪")
    blocks: list[dict] = [
        _callout(
            f"Health Score  {score}/100  ·  Grade {grade}  ·  {summary.get('pages_crawled',0)} pages  ·  "
            f"{summary.get('internal_links',0)} links  ·  Generated {date_str}",
            grade_emoji, grade_color
        ),
        _divider(),
    ]

    # ── key stats ──────────────────────────────────────────────
    blocks.append(_h2("📊 Key Metrics"))
    stat_rows = [
        ("Pages crawled",         summary.get("pages_crawled", 0)),
        ("Internal links",        summary.get("internal_links", 0)),
        ("Broken internal links", summary.get("broken_internal_links", 0)),
        ("Orphan pages",          summary.get("orphan_pages", 0)),
        ("Generic anchors",       summary.get("generic_anchors", 0)),
        ("Over-optimised anchors",summary.get("over_optimized_anchors", 0)),
        ("Topical clusters",      summary.get("topical_clusters", 0)),
        ("Link recommendations",  summary.get("link_recommendations", 0)),
    ]
    for label, val in stat_rows:
        blocks.append(_bullet([_rich(label + ": ", bold=True), _rich(str(val))]))

    blocks.append(_divider())

    # ── priority fix queue ─────────────────────────────────────
    if fixes:
        blocks.append(_h2("🔧 Priority Fix Queue"))
        blocks.append(_paragraph("Check off each fix as your team completes it.", "gray"))
        for fix in fixes:
            impact  = (fix.get("impact") or "").upper()
            action  = fix.get("action") or ""
            detail  = fix.get("detail") or ""
            label   = f"[{impact}]  {action}" + (f"  ({detail})" if detail else "")
            blocks.append(_todo(label, checked=False))
        blocks.append(_divider())

    # ── link recommendations ───────────────────────────────────
    if recs:
        blocks.append(_h2("🔗 Link Recommendations"))
        blocks.append(_paragraph(f"Top {len(recs)} contextual link opportunities identified by the pipeline.","gray"))
        for rec in recs:
            src    = (rec.get("source") or "").replace("https://","").replace("http://","")
            tgt    = (rec.get("target") or "").replace("https://","").replace("http://","")
            anchor = rec.get("suggested_anchor") or rec.get("reason") or ""
            score_r= rec.get("relatedness") or ""
            parts  = [
                _rich(src, bold=True),
                _rich(" → "),
                _rich(tgt, bold=True),
            ]
            if anchor:
                parts += [_rich("  ·  anchor: ", color="gray"), _rich(f'"{anchor}"', italic=True, color="gray")]
            if score_r:
                parts += [_rich(f"  ·  rel: {round(float(score_r),2)}", color="gray")]
            blocks.append(_bullet(parts))
        blocks.append(_divider())

    # ── topical clusters ───────────────────────────────────────
    if clusters:
        blocks.append(_h2("🗂 Topical Clusters"))
        for cl in clusters:
            name     = cl.get("name") or cl.get("key") or "Unnamed"
            size     = cl.get("size", 0)
            authority= cl.get("authority", "")
            kw       = ", ".join((cl.get("keywords") or [])[:5])
            auth_emoji = "🟢" if authority == "hub" else "🟡" if authority == "moderate" else "🔴"
            blocks.append(_bullet([
                _rich(f"{auth_emoji} {name}", bold=True),
                _rich(f"  ·  {size} pages  ·  {authority}  ·  {kw}", color="gray"),
            ]))
        blocks.append(_divider())

    # ── keyword cannibalization ────────────────────────────────
    if cannibal:
        blocks.append(_h2("⚠️ Keyword Cannibalization"))
        blocks.append(_paragraph("Pages competing for the same keywords — consider consolidating or differentiating.","gray"))
        for pair in cannibal:
            overlap = int((pair.get("overlap") or 0) * 100)
            pa = (pair.get("page_a") or "").replace("https://","").replace("http://","")
            pb = (pair.get("page_b") or "").replace("https://","").replace("http://","")
            severity = "🔴 High" if overlap >= 65 else "🟡 Medium" if overlap >= 50 else "🟢 Low"
            kw = ", ".join((pair.get("shared_keywords") or [])[:4])
            blocks.append(_bullet([
                _rich(f"{severity}  {overlap}% overlap  ", bold=True),
                _rich(f"{pa}  ↔  {pb}", color="gray"),
                _rich(f"  ·  keywords: {kw}" if kw else "", color="gray", italic=True),
            ]))
        blocks.append(_divider())

    # ── money pages ───────────────────────────────────────────
    if money:
        blocks.append(_h2("💰 Money Page Protection"))
        for mp in money:
            url_  = (mp.get("url") or "").replace("https://","").replace("http://","")
            score_= mp.get("protection_score") or mp.get("score") or 0
            inl   = mp.get("inlinks") or 0
            risk  = "🔴" if float(score_) < 40 else "🟡" if float(score_) < 70 else "🟢"
            blocks.append(_bullet([
                _rich(f"{risk} {url_}", bold=True),
                _rich(f"  ·  score: {score_}  ·  {inl} inlinks", color="gray"),
            ]))
        blocks.append(_divider())

    # ── SEO opportunities ─────────────────────────────────────
    if opps:
        blocks.append(_h2("🚀 SEO Opportunities"))
        blocks.append(_paragraph("Pages with high content value but poor internal link support.","gray"))
        for opp in opps:
            url_  = (opp.get("url") or "").replace("https://","").replace("http://","")
            score_= opp.get("opportunity_score") or opp.get("score") or ""
            inl   = opp.get("inlinks") or 0
            depth = opp.get("crawl_depth") or 0
            blocks.append(_bullet([
                _rich(url_, bold=True),
                _rich(f"  ·  opp score: {score_}  ·  {inl} inlinks  ·  depth {depth}", color="gray"),
            ]))

    # ── create the page (Notion blocks limit = 100 per request) ─
    chunks     = [blocks[i:i+100] for i in range(0, len(blocks), 100)]
    first_page = _req("POST", "/pages", token, {
        "parent":     {"type": "page_id", "page_id": parent_page_id.replace("-","")},
        "icon":       {"type": "emoji", "emoji": "⚡"},
        "properties": {
            "title": {"title": [{"type":"text","text":{"content": page_title}}]}
        },
        "children": chunks[0] if chunks else [],
    })

    page_id  = first_page["id"]
    page_url = first_page.get("url","")

    # append remaining block chunks (if report was large)
    for chunk in chunks[1:]:
        _req("PATCH", f"/blocks/{page_id}/children", token, {"children": chunk})

    return page_url
