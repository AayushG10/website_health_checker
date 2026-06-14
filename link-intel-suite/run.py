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
import argparse, json as _json, os, re as _re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "mcp"))
sys.path.insert(0, HERE)
import server  # the MCP server module exposes every tool as a function
from linkintel import analyzer as _ana
from linkintel import model_steps as _ms


def _run_model_steps():
    """Three model steps: name clusters, extract entities, write anchor text."""
    pages_by_url = {_ana._norm(p["Address"]): p for p in server._A["pages"]}
    page_text    = server._A.get("page_text", {})
    clusters     = server._A["clusters"]["clusters"]
    tfidf_kw     = server._A["clusters"]["page_keywords"]   # TF-IDF fallback
    model_calls  = 0

    # ── Step 1: Name every cluster (one call per cluster) ────────────────────
    total = len(clusters)
    for i, cluster in enumerate(clusters, 1):
        kw_str = ", ".join((cluster.get("keywords") or [])[:5])
        titles = [
            (pages_by_url.get(u, {}).get("Title 1") or "").strip()
            for u in cluster.get("pages", [])[:3]
        ]
        titles_str = "; ".join(t for t in titles if t) or "(no titles)"
        prompt = (
            f"Given these keywords: {kw_str} and these page titles: {titles_str}, "
            f"give a 2-4 word plain English name for this topic cluster. "
            f"Reply with only the cluster name, nothing else."
        )
        try:
            name = _ms._chat(prompt, max_tokens=20).strip().strip("\"'")
            cluster["name"] = name
            model_calls += 1
            print(f"[li] Naming cluster {i}/{total}: {name}", flush=True)
        except Exception as e:
            print(f"[li] cluster {i} naming failed: {e}", flush=True)

    # push names to the server RUN state
    server.li_topics({c["key"]: c.get("name") for c in clusters if c.get("name")})

    # ── Step 2: Entity extraction — top 30 pages by Unique Inlinks ───────────
    inl = {
        _ana._norm(p["Address"]): _ana._int(p.get("Unique Inlinks"))
        for p in server._A["pages"]
        if _ana.is_html(p) and _ana.is_200(p) and _ana.indexable(p)
    }
    important = sorted(inl, key=lambda u: -inl[u])[:30]

    entities: dict = {}
    for url in important:
        p       = pages_by_url.get(url, {})
        title   = (p.get("Title 1") or "").strip()
        h1      = (p.get("H1-1")    or "").strip()
        content = " ".join((page_text.get(url, "") or "").split()[:600])
        prompt  = (
            "Extract 5-8 key entities from this webpage. Entities are: product names, service "
            "names, technologies, methodologies, or named concepts specific to this page. "
            "Do NOT include generic words like 'development', 'services', 'company', 'solutions'.\n\n"
            f"Page title: {title}\nH1: {h1}\nContent: {content}\n\n"
            'Reply with a JSON array of strings only. Example: ["React Native", "iOS", "Flutter"]'
        )
        try:
            raw  = _ms._chat(prompt, max_tokens=150)
            m    = _re.search(r"\[.*?\]", raw, _re.DOTALL)
            ents = _json.loads(m.group()) if m else []
            entities[url] = [str(e).strip() for e in ents if e][:8] or tfidf_kw.get(url, [])
            model_calls += 1
        except Exception:
            entities[url] = tfidf_kw.get(url, [])
        print(f"[li] Entities for {url}: {entities[url]}", flush=True)

    # merge real entities with TF-IDF fallback for pages not in the entity dict,
    # so relatedness() has full page coverage and link_candidates stays non-empty
    merged = dict(tfidf_kw)
    merged.update(entities)
    server.li_entities(merged)   # rebuilds relatedness + link_candidates on full set

    # ── Step 3: Anchor text — one call per candidate ──────────────────────────
    recs = []
    for item in server._A.get("link_candidates", []):
        source    = item["source"]
        src_p     = pages_by_url.get(source, {})
        src_title = (src_p.get("Title 1") or "").strip() \
                    or source.rstrip("/").split("/")[-1].replace("-", " ")

        for c in item["candidates"]:
            target    = c["target"]
            tgt_p     = pages_by_url.get(target, {})
            tgt_title = (tgt_p.get("Title 1") or "").strip() \
                        or target.rstrip("/").split("/")[-1].replace("-", " ")
            tgt_h1    = (tgt_p.get("H1-1") or "").strip()
            tgt_ents  = entities.get(target, tfidf_kw.get(target, []))[:3]

            prompt = (
                "Write a 3-6 word internal link anchor text for a link pointing to this page.\n\n"
                f"Target page title: {tgt_title}\n"
                f"Target page H1: {tgt_h1}\n"
                f"Target page topics: {', '.join(tgt_ents)}\n"
                f"Source page context: {src_title}\n\n"
                "Rules:\n"
                "- Describe the TARGET page specifically\n"
                "- Do NOT use: click here, read more, learn more, here, this, view more\n"
                "- Do NOT repeat the exact page title word-for-word\n"
                "- Write naturally as if it appears mid-sentence in body copy\n"
                "- Reply with only the anchor text, nothing else"
            )
            try:
                anchor = _ms._chat(prompt, max_tokens=30).strip().strip("\"'")
                c["suggested_anchor"] = anchor
                model_calls += 1
            except Exception:
                pass   # stays None; schema allows null

            recs.append({
                "source":           source,
                "target":           target,
                "suggested_anchor": c.get("suggested_anchor"),
                "relatedness":      c["relatedness"],
                "reason":           "shares topics: " + ", ".join((c.get("shared_topics") or [])[:3]),
            })

    if recs:
        server.li_set_recommendations(recs)
        print(f"[li] wrote {len(recs)} recommendations", flush=True)

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

    if not args.no_dashboard:
        print(f"\n[li] Dashboard live at http://localhost:{server.PORT}  (Ctrl+C to quit)", flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
