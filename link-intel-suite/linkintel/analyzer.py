"""
analyzer.py - deterministic internal-linking + topical-authority analysis from a
Screaming Frog export (internal_html.csv + all_inlinks.csv + all_outlinks.csv +
all_anchor_text.csv + a page text/ folder).

STARTER IMPLEMENTATION. It already builds the internal link graph, detects orphan
pages, deepest pages, broken/redirect/nofollow internal links and basic anchor-text
problems so the pipeline runs end to end. Your job in the build is to COMPLETE the
analysis (see rulebook.md): finish the anchor classes, build the topical clusters,
the entity graph, and feed the linker. The grader uses these same definitions.

Standard library only (csv). The heavy lifting (graph, orphans, anchor classes) is
deterministic Python on purpose - the model is for entity extraction, cluster naming
and writing the contextual link suggestions, NOT for counting rows.
"""
from __future__ import annotations
import csv, os, re, math
from collections import defaultdict, Counter, deque
from urllib.parse import urlparse

csv.field_size_limit(10_000_000)

# --------------------------------------------------------------------------- #
# generic / non-descriptive anchors (lowercased, stripped). Extend per rulebook.
# --------------------------------------------------------------------------- #
GENERIC_ANCHORS = {
    # rulebook core set
    "click here", "read more", "learn more", "more", "here", "this", "link",
    "view more", "details", "know more", "discover more", "find out more",
    "continue reading",
    # common variants and extensions
    "read more...", "learn more...", "know more...",
    "click", "go", "view", "see more", "see details", "more details", "more info",
    "info", "this page", "this post", "this article",
    "visit", "visit page", "visit here",
    "check it out", "check this out",
    "find out", "get started", "start here", "see here",
    "view details", "read this", "read here",
    "follow this link", "follow link",
    "open", "open here",
    "show more", "show details",
    "expand", "see all", "view all",
    "get more", "get info",
}

STOPWORDS = set("""a an the and or but if then else for to of in on at by with from as is are was were be been being this that these those it its we you they he she them our your their i me my mine our ours us not no yes do does did doing have has had having will would can could should may might must shall about into over under again further once here there all any both each few more most other some such only own same so than too very s t can just don now get got also into out up down off above below""".split())

# Blog / boilerplate terms that appear on many pages and pollute TF-IDF keyword vectors
BOILERPLATE_WORDS = {
    "minutes", "reading", "estimated", "min", "read", "time",
    "author", "published", "updated", "posted", "date", "category", "tags", "tag",
    "views", "comments", "comment", "share", "shares", "like", "likes",
    "january", "february", "march", "april", "june", "july", "august",
    "september", "october", "november", "december",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    "home", "page", "click", "contact", "email", "phone", "address",
    "copyright", "rights", "reserved", "privacy", "terms", "policy",
    "subscribe", "newsletter", "follow", "social", "twitter", "linkedin",
    "facebook", "instagram", "youtube",
    "inc", "ltd", "llc", "pvt", "corp",
    "loading", "please", "wait", "error", "sorry",
    "table", "contents",
}


# --------------------------------------------------------------------------- #
# parsing helpers
# --------------------------------------------------------------------------- #
def _int(v, d=0):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return d


def _norm(u: str) -> str:
    """Normalise a URL for matching.

    Rules (per rulebook):
      - Strip leading/trailing whitespace
      - Lowercase (URLs are case-insensitive)
      - Drop the # fragment
      - Drop exactly ONE trailing slash (// -> /, not recursively)
      - Keep query strings as-is (different query = different page)
    """
    if not u:
        return ""
    u = u.strip().lower()
    u = u.split("#")[0]          # drop fragment
    if len(u) > 1 and u.endswith("/"):
        u = u[:-1]               # drop exactly one trailing slash
    return u


def is_html(r):  return "text/html" in (r.get("Content Type", "") or "").lower()
def is_200(r):   return _int(r.get("Status Code")) == 200
def indexable(r): return (r.get("Indexability", "") or "").strip().lower() == "indexable"


def load_pages(export_dir: str) -> list[dict]:
    """Load internal_html.csv (falls back to internal_all.csv)."""
    for name in ("internal_html.csv", "internal_all.csv"):
        p = os.path.join(export_dir, name)
        if os.path.exists(p):
            with open(p, encoding="utf-8-sig", newline="") as f:
                return list(csv.DictReader(f))
    raise FileNotFoundError("internal_html.csv / internal_all.csv not found in export dir")


def load_links(export_dir: str, fname="all_inlinks.csv") -> list[dict]:
    p = os.path.join(export_dir, fname)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_page_text(export_dir: str) -> dict:
    """Map normalised URL -> body text from the page text/ folder.

    Filenames are URL-encoded, e.g.
      original_https_nmgtechnologies.com_advanced-seo-case-studies.txt
    We reconstruct the URL by stripping the prefix and decoding.
    """
    out = {}
    folder = None
    for cand in ("page text", "page_text", "pagetext"):
        d = os.path.join(export_dir, cand)
        if os.path.isdir(d):
            folder = d
            break
    if not folder:
        return out
    from urllib.parse import unquote
    for fn in os.listdir(folder):
        if not fn.endswith(".txt"):
            continue
        stem = fn[:-4]
        stem = re.sub(r"^original_", "", stem)
        # original_https_host_path -> https://host/path
        stem = stem.replace("https_", "https://", 1).replace("http_", "http://", 1)
        # remaining underscores in the path segment were '/'
        if "://" in stem:
            scheme, rest = stem.split("://", 1)
            rest = rest.replace("_", "/")
            url = f"{scheme}://{rest}"
        else:
            url = stem.replace("_", "/")
        url = unquote(url)
        try:
            with open(os.path.join(folder, fn), encoding="utf-8", errors="ignore") as f:
                out[_norm(url)] = f.read()
        except Exception:
            pass
    return out


# --------------------------------------------------------------------------- #
# 1. INTERNAL LINK GRAPH  (deterministic - DONE in starter)
# --------------------------------------------------------------------------- #
def build_graph(pages, inlinks):
    """Return graph structures from the crawl.

    Uses only internal Hyperlink rows whose Source AND Destination are crawled
    pages. Returns adjacency (out), reverse adjacency (in), and per-page degree.
    """
    page_set = {_norm(p["Address"]) for p in pages}
    out_adj = defaultdict(set)
    in_adj = defaultdict(set)
    follow_in = defaultdict(int)
    for r in inlinks:
        if r.get("Type") != "Hyperlink":
            continue
        s = _norm(r.get("Source", ""))
        d = _norm(r.get("Destination", ""))
        if not s or not d or s == d:
            continue
        if d not in page_set:
            continue  # only count links pointing at crawled internal pages
        out_adj[s].add(d)
        in_adj[d].add(s)
        if (r.get("Follow", "true") or "true").strip().lower() == "true":
            follow_in[d] += 1
    return {"page_set": page_set, "out": out_adj, "in": in_adj, "follow_in": follow_in}


def graph_stats(pages, inlinks, graph) -> dict:
    """Internal-link graph statistics + structural issues.

    Definitions (match the rulebook):
      orphan_page          : indexable 200 html page with Unique Inlinks == 0
      deepest_pages        : indexable pages at the maximum Crawl Depth (>=3 listed)
      under_linked         : indexable 200 page with Unique Inlinks <= UNDER (default 1)
      over_linked          : page in the top 5% by Unique Inlinks (sitewide nav noise)
      broken_internal_link : all_inlinks rows with Status Code 400-599
      redirect_internal    : all_inlinks rows with Status Code 300-399 (3xx)
      nofollow_internal    : all_inlinks Hyperlink rows with Follow == false
    """
    idx200 = [p for p in pages if is_html(p) and is_200(p) and indexable(p)]
    by_url = {_norm(p["Address"]): p for p in pages}

    # orphans (use SF's own Unique Inlinks column - authoritative)
    orphans = sorted(_norm(p["Address"]) for p in idx200 if _int(p.get("Unique Inlinks")) == 0)

    # deepest
    depth = {_norm(p["Address"]): _int(p.get("Crawl Depth")) for p in idx200}
    maxd = max(depth.values()) if depth else 0
    deepest = sorted([u for u, d in depth.items() if d == maxd])

    # under/over linked by Unique Inlinks
    inl = {_norm(p["Address"]): _int(p.get("Unique Inlinks")) for p in idx200}
    UNDER = 1
    under_linked = sorted([u for u, n in inl.items() if n <= UNDER])
    vals = sorted(inl.values())
    if vals:
        over_thresh = vals[int(len(vals) * 0.95)]
        over_linked = sorted([u for u, n in inl.items() if n >= over_thresh]) if over_thresh > 0 else []
    else:
        over_linked = []

    # broken / redirect / nofollow internal links (from all_inlinks)
    # editorial inlinks: Link Position == "Content" only (not Header/Nav/Footer)
    broken, redir, nofollow = [], [], []
    editorial_inlinks = defaultdict(int)   # destination -> count of Content-position links
    nav_inlinks       = defaultdict(int)   # destination -> count of Header/Nav/Footer links
    for r in inlinks:
        sc  = _int(r.get("Status Code"))
        typ = r.get("Type", "")
        dst = _norm(r.get("Destination", ""))
        src = _norm(r.get("Source", ""))
        pos = (r.get("Link Position", "") or "").strip().lower()
        if typ == "Hyperlink" and 400 <= sc <= 599:
            broken.append({"source": src, "destination": dst, "status": sc,
                           "anchor": (r.get("Anchor", "") or "").strip()})
        if typ == "Hyperlink" and 300 <= sc <= 399:
            redir.append({"source": src, "destination": dst, "status": sc,
                          "anchor": (r.get("Anchor", "") or "").strip()})
        if typ == "Hyperlink" and (r.get("Follow", "true") or "").strip().lower() == "false":
            nofollow.append({"source": src, "destination": dst,
                             "anchor": (r.get("Anchor", "") or "").strip()})
        if typ == "Hyperlink" and dst in {_norm(p["Address"]) for p in idx200}:
            if pos == "content":
                editorial_inlinks[dst] += 1
            elif pos in ("header", "nav", "footer"):
                nav_inlinks[dst] += 1

    # editorially invisible: indexable 200 pages with total inlinks > 0 but 0 Content links
    editorially_invisible = sorted([
        u for u in inl
        if inl[u] > 0 and editorial_inlinks.get(u, 0) == 0
    ])

    return {
        "pages_total": len(pages),
        "pages_indexable": len(idx200),
        "internal_links": sum(len(v) for v in graph["out"].values()),
        "max_crawl_depth": maxd,
        "orphan_pages": orphans,
        "deepest_pages": deepest,
        "under_linked_pages": under_linked,
        "over_linked_pages": over_linked,
        "broken_internal_links": broken,
        "redirect_internal_links": redir,
        "nofollow_internal_links": nofollow,
        "avg_inlinks": round(sum(inl.values()) / len(inl), 1) if inl else 0,
        "editorial_inlinks": dict(editorial_inlinks),
        "nav_inlinks": dict(nav_inlinks),
        "editorially_invisible_pages": editorially_invisible,
    }


# --------------------------------------------------------------------------- #
# 2. ANCHOR TEXT ANALYSIS  (starter: generic + empty done; TODO: exact-match)
# --------------------------------------------------------------------------- #
def anchor_analysis(inlinks) -> dict:
    """Classify internal Hyperlink anchors.

    generic_anchors      : anchor (lowercased) in GENERIC_ANCHORS
    empty_or_image_only  : Hyperlink row with empty Anchor (image link / bare link)
    over_optimized       : TODO - the SAME exact-match keyword anchor used to point at
                           one destination from many sources (keyword stuffing signal)
    """
    hyper = [r for r in inlinks if r.get("Type") == "Hyperlink"]
    generic, empty = [], []
    dest_anchor = defaultdict(Counter)  # destination -> Counter(anchor)
    for r in hyper:
        a = (r.get("Anchor", "") or "").strip()
        al = a.lower()
        src = _norm(r.get("Source", ""))
        dst = _norm(r.get("Destination", ""))
        if not a:
            empty.append({"source": src, "destination": dst})
            continue
        if al in GENERIC_ANCHORS:
            generic.append({"source": src, "destination": dst, "anchor": a})
        dest_anchor[dst][al] += 1

    # TODO (build): over-optimized exact-match. Starter flags destinations where a
    # single non-generic anchor accounts for a large share AND a high count.
    over = []
    for dst, ctr in dest_anchor.items():
        total = sum(ctr.values())
        if total < 10:
            continue
        anchor, cnt = ctr.most_common(1)[0]
        if anchor and anchor not in GENERIC_ANCHORS and cnt / total >= 0.6 and cnt >= 10:
            over.append({"destination": dst, "anchor": anchor, "count": cnt, "share": round(cnt / total, 2)})

    return {
        "generic_anchors": generic,
        "empty_or_image_only": empty,
        "over_optimized_anchors": sorted(over, key=lambda x: -x["count"]),
        "total_internal_anchors": len(hyper),
    }


# --------------------------------------------------------------------------- #
# 3. TOPICAL CLUSTERS  (starter: path-prefix + keyword TF; TODO: refine + name)
# --------------------------------------------------------------------------- #
def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9\-]{2,}", (text or "").lower())
            if w not in STOPWORDS and w not in BOILERPLATE_WORDS]


def page_keywords(page, body: str, top=12) -> list[str]:
    """Cheap TF keywords from Title + H1 + H2 + body (deterministic).
    Title and H1 are repeated 3x to give them higher weight in TF counts."""
    title = page.get("Title 1", "") or ""
    h1    = page.get("H1-1", "") or ""
    h2_1  = page.get("H2-1", "") or ""
    h2_2  = page.get("H2-2", "") or ""
    blob = " ".join([title]*3 + [h1]*3 + [h2_1]*2 + [h2_2]*2 + [(body or "")[:4000]])
    c = Counter(_tokens(blob))
    return [w for w, _ in c.most_common(top)]


def compute_tfidf(pages: list, page_text: dict, top=12) -> dict[str, list[str]]:
    """TF-IDF keywords per indexable page. IDF penalises terms common across all pages
    so site-wide terms like 'development' or 'nmg' don't dominate every page's vector."""
    idx200 = [p for p in pages if is_html(p) and is_200(p) and indexable(p)]
    N = len(idx200)
    if N == 0:
        return {}

    # Step 1: raw token counts per page (title once, H1 ×3, H2, body)
    raw: dict[str, Counter] = {}
    for p in idx200:
        u = _norm(p["Address"])
        blob = " ".join([
            p.get("Title 1", "") or "",
            ((p.get("H1-1", "") or "") + " ") * 3,
            p.get("H2-1", "") or "",
            p.get("H2-2", "") or "",
            (page_text.get(u, "") or "")[:4000],
        ])
        raw[u] = Counter(_tokens(blob))

    # Step 2: document frequency — how many pages contain each term
    df: Counter = Counter()
    for counts in raw.values():
        df.update(counts.keys())

    # Step 3: TF-IDF score; top terms returned as ordered list
    tfidf: dict[str, list[str]] = {}
    for u, counts in raw.items():
        total = sum(counts.values()) or 1
        scores: dict[str, float] = {}
        for term, cnt in counts.items():
            tf = cnt / total
            idf = math.log(N / (df[term] + 1)) + 1
            scores[term] = tf * idf
        tfidf[u] = [t for t, _ in sorted(scores.items(), key=lambda x: -x[1])[:top]]
    return tfidf


def build_tfidf_keywords(pages: list, page_text: dict, top=12) -> dict[str, list[str]]:
    """Compute TF-IDF keywords per page. Downweights terms common across all pages
    (e.g. 'development', 'software' on a tech site), surfacing page-specific terms."""
    idx200 = [p for p in pages if is_html(p) and is_200(p) and indexable(p)]
    N = len(idx200)
    if N == 0:
        return {}

    def _raw_tf(page, body):
        title = page.get("Title 1", "") or ""
        h1    = page.get("H1-1", "") or ""
        h2_1  = page.get("H2-1", "") or ""
        h2_2  = page.get("H2-2", "") or ""
        blob  = " ".join([title]*3 + [h1]*3 + [h2_1]*2 + [h2_2]*2 + [(body or "")[:4000]])
        return Counter(_tokens(blob))

    url_tf: dict[str, Counter] = {}
    for p in idx200:
        u = _norm(p["Address"])
        url_tf[u] = _raw_tf(p, page_text.get(u, ""))

    # document frequency: how many pages contain each term
    df: Counter = Counter()
    for tf in url_tf.values():
        df.update(tf.keys())

    kw_out: dict[str, list[str]] = {}
    for u, tf in url_tf.items():
        total = sum(tf.values()) or 1
        scored = []
        for w, cnt in tf.items():
            idf = math.log((N + 1) / (df[w] + 1))
            scored.append((w, (cnt / total) * idf))
        scored.sort(key=lambda x: -x[1])
        kw_out[u] = [w for w, _ in scored[:top]]
    return kw_out


def _path_segment(url: str) -> str:
    """Return the primary path segment of a URL (e.g. 'blog', 'services', or '')."""
    try:
        from urllib.parse import urlparse
        parts = [x for x in urlparse(url).path.strip("/").split("/") if x]
        return parts[0] if parts else ""
    except Exception:
        return ""


def cluster_pages(pages, page_text, n_keywords=12) -> dict:
    """Group indexable pages into topical clusters.

    Improved algorithm:
      1. Compute TF-IDF vectors with extended boilerplate stopwords.
      2. Pre-seed one cluster per distinct URL path segment (blog, services, etc.).
      3. Assign each page (sorted most-inlinked-first) to the best matching cluster:
         path-segment match gives a 0.06 Jaccard bonus; minimum threshold of 0.08 to join.
      4. Post-process: merge singleton clusters into their nearest neighbour.
      5. Hub = member with most Unique Inlinks. Authority = hub if hub_inlinks >= 2x second.

    cluster["name"] is left None — the topic-agent fills it in.
    """
    idx200 = [p for p in pages if is_html(p) and is_200(p) and indexable(p)]
    inl = {_norm(p["Address"]): _int(p.get("Unique Inlinks")) for p in idx200}

    # TF-IDF keywords per page
    kw: dict[str, list[str]] = compute_tfidf(idx200, page_text, n_keywords)

    # Primary path segment for each URL
    seg: dict[str, str] = {_norm(p["Address"]): _path_segment(_norm(p["Address"])) for p in idx200}

    # Process pages most-inlinked first so authoritative pages seed good clusters
    sorted_urls = sorted([_norm(p["Address"]) for p in idx200], key=lambda u: -inl.get(u, 0))

    MIN_JAC = 0.08     # minimum score to join an existing cluster
    SEG_BONUS = 0.06   # bonus for sharing the same URL path segment

    seeds: list[str] = []
    seed_kw: list[set] = []
    seed_seg: list[str] = []
    assignments: dict[str, str] = {}

    for u in sorted_urls:
        kw_u = set(kw.get(u, []))
        u_seg = seg.get(u, "")
        best_seed, best_score = None, -1.0
        for i, s in enumerate(seeds):
            kw_s = seed_kw[i]
            if not kw_u or not kw_s:
                continue
            union = len(kw_u | kw_s)
            jac = len(kw_u & kw_s) / union if union else 0.0
            bonus = SEG_BONUS if (u_seg and u_seg == seed_seg[i]) else 0.0
            score = jac + bonus
            if score > best_score:
                best_score = score
                best_seed = s
        if best_seed is None or best_score < MIN_JAC:
            seeds.append(u)
            seed_kw.append(kw_u)
            seed_seg.append(u_seg)
            assignments[u] = u
        else:
            assignments[u] = best_seed

    # post-process: merge singletons into their nearest non-singleton neighbour
    seed_members_raw: dict[str, list] = defaultdict(list)
    for u, s in assignments.items():
        seed_members_raw[s].append(u)

    singletons = [s for s, m in seed_members_raw.items() if len(m) == 1]
    non_single = [s for s in seeds if len(seed_members_raw.get(s, [])) > 1]
    for s in singletons:
        kw_s = set(kw.get(s, []))
        best_target, best_jac = None, -1.0
        for t in non_single:
            kw_t = set(kw.get(t, []))
            union = len(kw_s | kw_t)
            jac = len(kw_s & kw_t) / union if union else 0.0
            seg_bonus = SEG_BONUS if (seg.get(s) and seg.get(s) == seg.get(t)) else 0.0
            score = jac + seg_bonus
            if score > best_jac:
                best_jac = score
                best_target = t
        if best_target and best_jac > 0.0:
            assignments[s] = best_target

    # group members by seed
    seed_members: dict[str, list] = defaultdict(list)
    for u, s in assignments.items():
        seed_members[s].append(u)

    # build output clusters
    used_keys: Counter = Counter()
    out: list[dict] = []
    for s, members in seed_members.items():
        if not members:
            continue
        members = sorted(members)
        hub = max(members, key=lambda u: inl.get(u, 0))
        hub_inlinks = inl.get(hub, 0)
        member_inl = sorted((inl.get(m, 0) for m in members), reverse=True)
        clear_hub = bool(len(member_inl) >= 2 and hub_inlinks >= 2 * (member_inl[1] or 1))
        ck: Counter = Counter()
        for m in members:
            ck.update(kw.get(m, []))
        top_kw = [w for w, _ in ck.most_common(8)]
        # key: prefer URL path segment of the seed, else top keyword
        primary_seg = seg.get(s, "")
        base_key = primary_seg if primary_seg else (top_kw[0] if top_kw else s.rstrip("/").split("/")[-1])
        used_keys[base_key] += 1
        key = base_key if used_keys[base_key] == 1 else f"{base_key}_{used_keys[base_key]}"
        out.append({
            "key": key,
            "name": None,   # topic-agent names this cluster
            "size": len(members),
            "pages": members,
            "hub_page": hub,
            "hub_inlinks": hub_inlinks,
            "authority": "hub" if clear_hub else "scattered",
            "keywords": top_kw,
        })

    out.sort(key=lambda c: -c["size"])
    return {"clusters": out, "page_keywords": kw}


# --------------------------------------------------------------------------- #
# 4. ENTITY GRAPH  (starter: TF-overlap relatedness; TODO: model entities)
# --------------------------------------------------------------------------- #
def relatedness(page_keywords: dict, top_per_page=10) -> dict:
    """Page-to-page topical relatedness via keyword (Jaccard) overlap.

    STARTER: uses the deterministic TF keywords as a proxy for entities. The
    entity-agent should replace `page_keywords` with model-extracted entities for
    a sharper graph, then this same overlap math builds the edges.
    """
    urls = list(page_keywords.keys())
    sets = {u: set(page_keywords[u]) for u in urls}
    edges = {}
    for u in urls:
        scored = []
        su = sets[u]
        if not su:
            edges[u] = []
            continue
        for v in urls:
            if v == u:
                continue
            sv = sets[v]
            if not sv:
                continue
            inter = len(su & sv)
            if inter == 0:
                continue
            jac = inter / len(su | sv)
            scored.append((v, round(jac, 3), sorted(su & sv)[:6]))
        scored.sort(key=lambda x: -x[1])
        edges[u] = [{"to": v, "score": s, "shared": sh} for v, s, sh in scored[:top_per_page]]
    return edges


# --------------------------------------------------------------------------- #
# 5. CONTEXTUAL LINK RECOMMENDATIONS  (starter: candidates; model writes anchors)
# --------------------------------------------------------------------------- #
def _tfidf_anchor(page: dict, kw: list) -> str:
    """Generate a descriptive fallback anchor from title/H1/keywords (no model needed)."""
    title = (page.get("Title 1") or "").strip()
    h1 = (page.get("H1-1") or "").strip()
    # Prefer title words that aren't generic; strip company suffix patterns
    candidate = h1 or title
    # Remove trailing " | Company" style suffixes
    candidate = re.sub(r"\s*[\|\-–]\s*.{1,30}$", "", candidate).strip()
    if len(candidate.split()) <= 7:
        return candidate
    # Fall back to top keywords joined
    return " ".join(kw[:4]).title() if kw else candidate[:50]


def link_candidates(graph, relate: dict, pages, page_keywords: dict = None, max_per_page=5) -> list:
    """For each important page, find topically-related pages it does NOT already
    link to. Returns candidates with a TF-IDF fallback anchor (model overwrites these).
    """
    idx200 = [p for p in pages if is_html(p) and is_200(p) and indexable(p)]
    inl = {_norm(p["Address"]): _int(p.get("Unique Inlinks")) for p in idx200}
    pages_by_url = {_norm(p["Address"]): p for p in pages}
    kw_map = page_keywords or {}
    # "important" = top pages by inlinks (hubs + money pages)
    important = sorted(inl, key=lambda u: -inl[u])[:60]
    out = []
    for u in important:
        already = graph["out"].get(u, set())
        cands = []
        for e in relate.get(u, []):
            v = e["to"]
            if v in already or v == u:
                continue
            tgt_page = pages_by_url.get(v, {})
            tgt_kw = kw_map.get(v, [])
            fallback_anchor = _tfidf_anchor(tgt_page, tgt_kw)
            cands.append({
                "target": v,
                "relatedness": e["score"],
                "shared_topics": e["shared"],
                "suggested_anchor": fallback_anchor or None,
            })
            if len(cands) >= max_per_page:
                break
        if cands:
            out.append({"source": u, "candidates": cands})
    return out


# --------------------------------------------------------------------------- #
# 6. DIGITAL MARKETING INTELLIGENCE
# --------------------------------------------------------------------------- #

# URL path signals that identify conversion / money pages
MONEY_SIGNALS = [
    "contact", "contact-us", "pricing", "price", "prices", "demo", "free-demo",
    "quote", "get-a-quote", "hire", "hire-us", "consultation", "book", "booking",
    "get-started", "free-trial", "trial", "buy", "purchase", "checkout",
    "request", "proposal", "services", "service", "solutions", "solution",
    "work-with-us", "start-project", "estimate",
]


def keyword_cannibalization(page_keywords: dict, threshold: float = 0.45) -> list:
    """Find page pairs with high TF-IDF keyword overlap — cannibalization risk.

    Two indexable pages competing for the same terms split link equity and
    confuse search engines. Returns pairs sorted by overlap score descending.
    """
    urls = list(page_keywords.keys())
    sets = {u: set(page_keywords[u]) for u in urls}
    pairs = []
    for i, u in enumerate(urls):
        su = sets[u]
        if not su:
            continue
        for v in urls[i + 1:]:
            sv = sets[v]
            if not sv:
                continue
            inter = len(su & sv)
            union = len(su | sv)
            jac = inter / union if union else 0.0
            if jac >= threshold:
                pairs.append({
                    "page_a": u,
                    "page_b": v,
                    "overlap_score": round(jac, 3),
                    "shared_keywords": sorted(su & sv)[:8],
                })
    pairs.sort(key=lambda x: -x["overlap_score"])
    return pairs[:30]


def money_page_analysis(pages: list, inlinks: list) -> list:
    """Score how well internal links protect money / conversion pages.

    Detects pages by URL path signals and measures their Unique Inlinks.
    Low inlinks to a money page = lost conversion traffic.
    """
    idx200 = [p for p in pages if is_html(p) and is_200(p) and indexable(p)]

    # build per-destination anchor diversity from inlinks
    dest_anchors: dict = defaultdict(set)
    for r in inlinks:
        if r.get("Type") == "Hyperlink":
            dst = _norm(r.get("Destination", ""))
            anc = (r.get("Anchor", "") or "").strip().lower()
            if dst and anc:
                dest_anchors[dst].add(anc)

    money = []
    for p in idx200:
        url = _norm(p["Address"])
        path = url.lower()
        matched = [s for s in MONEY_SIGNALS if s in path]
        # also check title for money signals
        title = (p.get("Title 1") or "").lower()
        if not matched:
            matched = [s for s in ["contact", "pricing", "demo", "services", "hire", "quote", "consultation"]
                       if s in title]
        if not matched:
            continue
        inlink_count = _int(p.get("Unique Inlinks", 0))
        anchor_diversity = len(dest_anchors.get(url, set()))
        protection = min(100, inlink_count * 6 + anchor_diversity * 2)
        risk = "critical" if inlink_count < 2 else "high" if inlink_count < 5 else "medium" if inlink_count < 10 else "low"
        money.append({
            "url": url,
            "title": (p.get("Title 1") or "").strip(),
            "inlinks": inlink_count,
            "anchor_diversity": anchor_diversity,
            "protection_score": protection,
            "risk": risk,
            "signals": matched[:3],
        })

    money.sort(key=lambda x: x["inlinks"])
    return money[:25]


def seo_opportunity_scores(pages: list, page_keywords: dict) -> list:
    """Rank pages by SEO link-building opportunity.

    High score = page has good content but poor internal link support.
    Prioritise these pages when adding new internal links.
    """
    idx200 = [p for p in pages if is_html(p) and is_200(p) and indexable(p)]
    scores = []
    for p in idx200:
        url   = _norm(p["Address"])
        depth = _int(p.get("Crawl Depth", 0))
        inl   = _int(p.get("Unique Inlinks", 0))
        wc    = _int(p.get("Word Count", 0))

        # Opportunity = buried (deep) + content-rich + under-linked
        depth_score   = min(depth * 12, 40)
        inlink_score  = max(0, 35 - inl * 3)
        content_score = min(wc / 80, 25)
        opp = round(depth_score + inlink_score + content_score)

        scores.append({
            "url": url,
            "title": (p.get("Title 1") or "").strip(),
            "opportunity_score": opp,
            "crawl_depth": depth,
            "inlinks": inl,
            "word_count": wc,
            "top_keywords": page_keywords.get(url, [])[:4],
        })

    scores.sort(key=lambda x: -x["opportunity_score"])
    return scores[:20]


def thin_content_pages(pages: list, min_words: int = 300) -> list:
    """Find indexable pages with suspiciously low word counts.

    Thin content hurts crawl budget and topical authority. Pages with
    < min_words words and Word Count > 0 are flagged.
    """
    result = []
    for p in pages:
        if not (is_html(p) and is_200(p) and indexable(p)):
            continue
        wc = _int(p.get("Word Count", 0))
        if 0 < wc < min_words:
            result.append({
                "url": _norm(p["Address"]),
                "title": (p.get("Title 1") or "").strip(),
                "word_count": wc,
                "inlinks": _int(p.get("Unique Inlinks", 0)),
                "crawl_depth": _int(p.get("Crawl Depth", 0)),
            })
    result.sort(key=lambda x: x["word_count"])
    return result[:30]


def pagerank_sim(graph: dict, damping: float = 0.85, iterations: int = 30) -> dict:
    """Simulate PageRank over the internal link graph.

    Returns {url: score_0_to_100} — higher = more link equity received.
    Useful for spotting equity sinks (lots of inlinks but few outlinks passing
    equity on) and orphaned link equity.
    """
    page_set = graph["page_set"]
    N = len(page_set)
    if N == 0:
        return {}
    pr = {u: 1.0 / N for u in page_set}
    out_deg = {u: max(len(graph["out"].get(u, set())), 1) for u in page_set}
    for _ in range(iterations):
        new_pr: dict = {}
        for u in page_set:
            incoming = sum(pr.get(v, 0) / out_deg[v] for v in graph["in"].get(u, set()))
            new_pr[u] = (1 - damping) / N + damping * incoming
        pr = new_pr
    max_pr = max(pr.values()) if pr else 1.0
    return {u: round(v / max_pr * 100, 2) for u, v in pr.items()}


def content_gap_finder(clusters: list, page_keywords: dict) -> list:
    """Identify topic clusters with thin coverage — content gap opportunities.

    A gap cluster has few pages and/or no clear hub — these are topics where
    a competitor with deeper content can outrank you.
    """
    gaps = []
    for c in clusters:
        size = c["size"]
        authority = c.get("authority", "scattered")
        avg_inl = c.get("hub_inlinks", 0) / max(size, 1)
        if size <= 3 or authority == "scattered":
            gaps.append({
                "cluster": c.get("name") or c["key"],
                "key": c["key"],
                "size": size,
                "authority": authority,
                "hub_page": c.get("hub_page"),
                "keywords": (c.get("keywords") or [])[:5],
                "gap_score": round((1 / max(size, 1)) * 50 + (30 if authority == "scattered" else 0) + max(0, 10 - avg_inl)),
            })
    gaps.sort(key=lambda x: -x["gap_score"])
    return gaps[:15]


def anchor_text_keyword_map(inlinks: list) -> list:
    """Build a ranked map of anchor text keywords used sitewide.

    Shows which keywords are being over- or under-used as anchor text —
    useful for aligning PPC/SEO keyword strategy with internal linking.
    """
    kw_counter: Counter = Counter()
    for r in inlinks:
        if r.get("Type") != "Hyperlink":
            continue
        anchor = (r.get("Anchor", "") or "").strip().lower()
        if not anchor or anchor in GENERIC_ANCHORS:
            continue
        for tok in _tokens(anchor):
            if len(tok) >= 4:
                kw_counter[tok] += 1
    return [{"keyword": kw, "count": cnt} for kw, cnt in kw_counter.most_common(40)]


# --------------------------------------------------------------------------- #
# orchestration entry used by server.py / run.py
# --------------------------------------------------------------------------- #
def analyze(export_dir: str) -> dict:
    pages   = load_pages(export_dir)
    inlinks = load_links(export_dir, "all_inlinks.csv")
    text    = load_page_text(export_dir)
    graph   = build_graph(pages, inlinks)
    gstats  = graph_stats(pages, inlinks, graph)
    anchors = anchor_analysis(inlinks)
    clusters = cluster_pages(pages, text)
    relate   = relatedness(clusters["page_keywords"])
    cands    = link_candidates(graph, relate, pages, clusters["page_keywords"])

    # digital marketing intelligence
    kw       = clusters["page_keywords"]
    dm = {
        "cannibalization":   keyword_cannibalization(kw),
        "money_pages":       money_page_analysis(pages, inlinks),
        "seo_opportunities": seo_opportunity_scores(pages, kw),
        "thin_content":      thin_content_pages(pages),
        "pagerank":          pagerank_sim(graph),
        "content_gaps":      content_gap_finder(clusters["clusters"], kw),
        "anchor_keyword_map": anchor_text_keyword_map(inlinks),
    }

    return {
        "pages": pages, "graph": graph, "graph_stats": gstats,
        "anchors": anchors, "clusters": clusters, "relatedness": relate,
        "link_candidates": cands, "page_text": text, "page_text_count": len(text),
        "digital_marketing": dm,
    }


if __name__ == "__main__":
    import sys, json
    d = sys.argv[1] if len(sys.argv) > 1 else "../sample-export"
    res = analyze(d)
    g = res["graph_stats"]
    print(f"pages={g['pages_total']} indexable={g['pages_indexable']} "
          f"links={g['internal_links']} maxdepth={g['max_crawl_depth']}")
    print(f"orphans={len(g['orphan_pages'])} under_linked={len(g['under_linked_pages'])} "
          f"over_linked={len(g['over_linked_pages'])}")
    print(f"broken_internal={len(g['broken_internal_links'])} "
          f"redirect_internal={len(g['redirect_internal_links'])} "
          f"nofollow_internal={len(g['nofollow_internal_links'])}")
    a = res["anchors"]
    print(f"generic_anchors={len(a['generic_anchors'])} empty={len(a['empty_or_image_only'])} "
          f"over_optimized={len(a['over_optimized_anchors'])}")
    print(f"clusters={len(res['clusters']['clusters'])} "
          f"link_candidate_pages={len(res['link_candidates'])} "
          f"page_text={res['page_text_count']}")
