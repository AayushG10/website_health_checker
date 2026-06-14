"""
model_steps.py - model-driven steps for the Link Intel Suite.

Calls the Ollama API (local or free cloud) for:
  1. Cluster naming    - one batched call for all clusters
  2. Entity extraction - one call per important page
  3. Anchor writing    - one call per source page (3-5 anchors per call)

All functions degrade gracefully: if Ollama is unavailable, they return empty
results and run.py falls back to TF-IDF keyword names / no anchors.

Set RADAR_MODEL or LI_MODEL to pick the model (default: gpt-oss:20b-cloud).
Set OLLAMA_URL to override the endpoint (default: http://localhost:11434).
"""
from __future__ import annotations
import json, os, re, urllib.request, urllib.error

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("RADAR_MODEL", os.environ.get("LI_MODEL", "qwen3:8b"))


# --------------------------------------------------------------------------- #
# low-level chat call
# --------------------------------------------------------------------------- #
def _chat(prompt: str, max_tokens: int = 512) -> str:
    """Call Ollama chat API with streaming.

    Uses think=False to disable qwen3/deepseek-r1 thinking chains — otherwise
    qwen3 spends its entire num_predict budget on <think> tokens and returns
    empty content.  stream=True so we can join incremental content tokens.
    """
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "think": False,
        "options": {"num_predict": max_tokens, "temperature": 0.15},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()

    lines = [json.loads(l) for l in raw.strip().split(b"\n") if l.strip()]
    # collect content tokens (not thinking tokens — those are in message.thinking)
    content = "".join(d.get("message", {}).get("content", "") for d in lines).strip()
    # also strip any inline <think>…</think> blocks (non-streaming reasoning models)
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    return content


def _extract_json(text: str, kind: str = "object"):
    """Pull the first JSON object or array out of a model response."""
    pat = r"\{.*\}" if kind == "object" else r"\[.*?\]"
    m = re.search(pat, text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except Exception:
        return None


def is_available() -> bool:
    """Return True if the Ollama server is reachable."""
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=4)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# 1. cluster naming  (one call for all clusters)
# --------------------------------------------------------------------------- #
def name_clusters(clusters: list) -> dict:
    """Return {cluster_key: "Plain English Name"} for every cluster.

    Sends all clusters in one prompt to stay within quota.
    """
    lines = []
    for c in clusters:
        kw = ", ".join((c.get("keywords") or [])[:5])
        hub = (c.get("hub_page") or "").rstrip("/").split("/")[-1].replace("-", " ")
        lines.append(f'key="{c["key"]}"  keywords=[{kw}]  hub="{hub}"')

    prompt = (
        "You are naming topical clusters for an internal-linking SEO report.\n"
        "Each cluster is described by its URL path key, top TF-IDF keywords, and hub page slug.\n"
        "For EVERY cluster, assign a short (2–5 word) plain-English topic name.\n"
        "Rules:\n"
        "- No jargon; a client must understand it\n"
        "- Do NOT just echo the key back\n"
        "- Output ONLY valid JSON: {\"key\": \"Name\", ...}  — no markdown, no comments\n\n"
        + "\n".join(lines)
    )
    try:
        raw = _chat(prompt, max_tokens=600)
        result = _extract_json(raw, "object")
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


# --------------------------------------------------------------------------- #
# 2. entity extraction  (one call per page)
# --------------------------------------------------------------------------- #
def extract_entities(url: str, body: str, title: str = "", h1: str = "") -> list[str]:
    """Extract 5–10 key entities from a single page. Returns list of strings."""
    snippet = (body or "")[:1500]
    prompt = (
        "Extract 5–10 key entities (products, services, technologies, named concepts) "
        "from this webpage. Focus on specific, named things — not generic words.\n"
        "Output ONLY a JSON array of strings, e.g. [\"React\", \"CI/CD pipeline\"].\n\n"
        f"Title: {title}\nH1: {h1}\n\nBody excerpt:\n{snippet}"
    )
    try:
        raw = _chat(prompt, max_tokens=200)
        result = _extract_json(raw, "array")
        if isinstance(result, list):
            return [str(e).strip() for e in result if e][:10]
    except Exception:
        pass
    return []


# --------------------------------------------------------------------------- #
# 3. anchor writing  (one call per source page, 3–5 anchors per call)
# --------------------------------------------------------------------------- #
def write_anchors(
    source_url: str,
    source_title: str,
    candidates: list,
    pages_by_url: dict,
) -> list:
    """Return candidates with suggested_anchor filled in.

    `candidates` is a list of dicts from link_candidates() output.
    `pages_by_url` maps normalised URL → page row dict.
    """
    targets_text = []
    for c in candidates[:5]:
        t = c["target"]
        info = pages_by_url.get(t, {})
        title = (info.get("Title 1") or "").strip() or t.rstrip("/").split("/")[-1].replace("-", " ")
        h1    = (info.get("H1-1") or "").strip()
        shared = ", ".join((c.get("shared_topics") or [])[:4])
        targets_text.append(
            f'- url: {t}\n  title: "{title}"\n  h1: "{h1}"\n  shared_topics: {shared}'
        )

    prompt = (
        "You are writing internal link anchor text for an SEO report.\n"
        f'Source page: "{source_title}" ({source_url})\n\n'
        "For each target below, write a SPECIFIC, descriptive 3–7 word anchor text that:\n"
        "- describes what the TARGET page is about (use its title / H1)\n"
        "- reads naturally as body copy link text on the source page\n"
        "- is NOT generic ('click here', 'read more', 'learn more', 'here', 'this')\n"
        "- is NOT keyword-stuffed (no exact-match repetition)\n\n"
        "Targets (in order):\n"
        + "\n".join(targets_text)
        + "\n\nOutput ONLY a JSON array of strings matching the order above, "
        'e.g. ["Custom Android app development", "Mobile UX design services"]'
    )
    try:
        raw = _chat(prompt, max_tokens=300)
        anchors = _extract_json(raw, "array")
        if not isinstance(anchors, list):
            anchors = []
    except Exception:
        anchors = []

    result = []
    for i, c in enumerate(candidates[:5]):
        c = dict(c)
        if i < len(anchors) and anchors[i] and str(anchors[i]).strip():
            c["suggested_anchor"] = str(anchors[i]).strip()
        result.append(c)
    return result
