#!/usr/bin/env python3
"""
run.py - headless runner for the Link Intel Suite (also the grader's entry point).

Runs the full internal-linking analysis on a Screaming Frog export:
  load -> graph -> anchors -> topics -> entities -> recommend -> report

Model-driven steps (cluster naming, entity extraction, anchor writing) call Ollama
when available; fall back to TF-IDF placeholders so the contract always holds.

Usage:
  python run.py sample-export/
  python run.py sample-export/ --no-dashboard
  python run.py sample-export/ --no-model      # skip Ollama even if running
"""
from __future__ import annotations
import argparse, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "mcp"))
sys.path.insert(0, HERE)
import server  # the MCP server module exposes every tool as a function
from linkintel import analyzer as _ana
from linkintel import model_steps as _ms


def _run_model_steps():
    """Name clusters, extract entities, write anchors via Ollama."""
    model_calls = 0

    # 1. name clusters (one batched call)
    clusters = server._A["clusters"]["clusters"]
    names = _ms.name_clusters(clusters)
    if names:
        server.li_topics(names)
        model_calls += 1
        print(f"[li] named {len(names)} clusters", flush=True)

    # 2. entity extraction for important pages (top 25 by inlinks)
    pages_by_url = {_ana._norm(p["Address"]): p for p in server._A["pages"]}
    page_text = server._A.get("page_text", {})
    inl = {_ana._norm(p["Address"]): _ana._int(p.get("Unique Inlinks"))
           for p in server._A["pages"]
           if _ana.is_html(p) and _ana.is_200(p) and _ana.indexable(p)}
    important_urls = sorted(inl, key=lambda u: -inl[u])[:25]

    entities: dict = {}
    for u in important_urls:
        p = pages_by_url.get(u, {})
        body = page_text.get(u, "")
        ents = _ms.extract_entities(u, body, p.get("Title 1", ""), p.get("H1-1", ""))
        if ents:
            entities[u] = ents
            model_calls += 1

    if entities:
        server.li_entities(entities)
        print(f"[li] entities extracted for {len(entities)} pages", flush=True)

    # 3. write anchors (one call per source page)
    recs = []
    for blk in server._A.get("link_candidates", []):
        source = blk["source"]
        source_title = (pages_by_url.get(source, {}).get("Title 1") or "").strip() \
                       or source.rstrip("/").split("/")[-1].replace("-", " ")
        updated = _ms.write_anchors(source, source_title, blk["candidates"], pages_by_url)
        model_calls += 1
        for c in updated:
            recs.append({
                "source": source,
                "target": c["target"],
                "suggested_anchor": c.get("suggested_anchor"),
                "relatedness": c["relatedness"],
                "reason": "shared topics: " + ", ".join(c.get("shared_topics") or []),
            })

    if recs:
        server.li_set_recommendations(recs)
        print(f"[li] wrote {len(recs)} link recommendations with anchors", flush=True)

    return model_calls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export_dir")
    ap.add_argument("--no-dashboard", action="store_true")
    ap.add_argument("--no-model", action="store_true",
                    help="Skip model calls (use TF-IDF placeholders)")
    args = ap.parse_args()

    if not args.no_dashboard:
        server.start_dashboard()
        print(f"[li] dashboard: http://localhost:{server.PORT}", flush=True)
        time.sleep(1)

    t0 = time.time()

    # deterministic steps
    server.li_load(args.export_dir)
    server.li_graph()
    server.li_anchors()
    server.li_topics()    # initial clusters with TF-IDF keyword names
    server.li_entities()  # TF-IDF relatedness proxy (rebuilt if model adds entities)

    # model steps (Ollama)
    model_calls = 0
    if not args.no_model:
        if _ms.is_available():
            print(f"[li] Ollama available — running model steps (model={_ms.MODEL})", flush=True)
            try:
                model_calls = _run_model_steps()
            except Exception as e:
                print(f"[li] model steps error: {e}", flush=True)
        else:
            print("[li] Ollama not running — using TF-IDF placeholders", flush=True)

    server.RUN["model_calls"] = model_calls
    server.RUN["duration_sec"] = round(time.time() - t0, 1)
    server.li_report()
    server.li_export()

    s = server.RUN["summary"]
    print("\n=== INTERNAL LINKING INTELLIGENCE ===")
    print(f"Site            : {server.RUN['site']}  ({s['pages_crawled']} pages)")
    print(f"Internal links  : {s['internal_links']}")
    print(f"Orphan pages    : {s['orphan_pages']}")
    print(f"Broken internal : {s['broken_internal_links']}")
    print(f"Generic anchors : {s['generic_anchors']}")
    print(f"Topical clusters: {s['topical_clusters']}")
    print(f"Link suggestions: {s['link_recommendations']}")
    print(f"Model calls     : {model_calls}")
    print("Wrote outputs/report.json and outputs/report.html")


if __name__ == "__main__":
    main()
