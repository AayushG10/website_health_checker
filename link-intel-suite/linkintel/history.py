"""
history.py - persist health score history across runs.
Appends each completed analysis to outputs/history.json.
"""
from __future__ import annotations
import json, os
from datetime import datetime

def record(run: dict, out_dir: str) -> None:
    path = os.path.join(out_dir, "history.json")
    try:
        with open(path) as f: data = json.load(f)
    except Exception: data = {"runs": []}

    data["runs"].append({
        "date":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        "site":    run.get("site", ""),
        "score":   run.get("health_score", 0),
        "grade":   run.get("health_grade", "?"),
        "pages":   (run.get("summary") or {}).get("pages_crawled", 0),
        "links":   (run.get("summary") or {}).get("internal_links", 0),
        "broken":  (run.get("summary") or {}).get("broken_internal_links", 0),
        "orphans": (run.get("summary") or {}).get("orphan_pages", 0),
        "clusters":(run.get("summary") or {}).get("topical_clusters", 0),
        "recs":    (run.get("summary") or {}).get("link_recommendations", 0),
    })
    data["runs"] = data["runs"][-50:]  # keep last 50 runs

    with open(path, "w") as f: json.dump(data, f, indent=2)

def load(out_dir: str) -> dict:
    path = os.path.join(out_dir, "history.json")
    try:
        with open(path) as f: return json.load(f)
    except Exception: return {"runs": []}
