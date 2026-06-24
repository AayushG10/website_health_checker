"""
crawler.py - built-in web crawler that generates Screaming-Frog-compatible
CSV exports from a live URL, so users don't need Screaming Frog at all.

Generates:
  internal_html.csv  — page inventory
  all_inlinks.csv    — full internal link graph
  all_anchor_text.csv — anchor text (same format)

Usage:
  from linkintel.crawler import crawl
  stats = crawl("https://example.com", "/tmp/upload", max_pages=200,
                on_progress=lambda msg, pct: None)
"""
from __future__ import annotations
import csv, os, ssl, re
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.robotparser import RobotFileParser
from html.parser import HTMLParser

UA      = "Mozilla/5.0 (compatible; LinkIntelBot/1.0; +https://github.com/link-intel)"
TIMEOUT = 12
MAX_BYTES = 600_000  # 600 KB per page

HTML_COLS = [
    "Address","Content Type","Status Code","Status",
    "Indexability","Indexability Status",
    "Title 1","Title 1 Length","Meta Description 1","Meta Description 1 Length",
    "H1-1","H1-1 Length","H2-1",
    "Word Count","Crawl Depth",
    "Inlinks","Unique Inlinks","Outlinks","Unique Outlinks",
    "External Outlinks","Unique External Outlinks",
    "Redirect URL","Redirect Type",
]

LINK_COLS = [
    "Type","Source","Destination","Size (Bytes)","Alt Text",
    "Anchor","Status Code","Status","Follow","Target","Rel",
    "Path Type","Link Path","Link Position","Link Origin",
]


# ─────────────────────────────────────────────── HTML PARSER ──
class _Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""; self.h1 = ""; self.h2 = ""; self.meta_desc = ""
        self.links: list[tuple] = []
        self.noindex = False
        self._in = {}           # tag -> bool
        self._skip = 0          # depth inside script/style/noscript
        self._skip_tags = {"script","style","noscript"}
        self._body = False
        self._words: list[str] = []
        self._cur_href = None; self._cur_follow = True
        self._cur_alt = ""; self._cur_anchor: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self._skip_tags: self._skip += 1; return
        if tag == "body": self._body = True
        if tag == "title": self._in["title"] = True
        if tag == "h1":   self._in["h1"] = True
        if tag == "h2":   self._in["h2"] = True
        if tag == "meta":
            n = a.get("name","").lower()
            if n == "description": self.meta_desc = a.get("content","")
            if n == "robots":
                c = a.get("content","").lower()
                if "noindex" in c: self.noindex = True
        if tag == "a":
            rel = a.get("rel","").lower()
            self._cur_href = a.get("href","")
            self._cur_follow = "nofollow" not in rel
            self._cur_alt = ""; self._cur_anchor = []
        if tag == "img" and self._cur_href is not None:
            self._cur_alt = a.get("alt","")
            if self._cur_alt: self._cur_anchor.append(self._cur_alt)

    def handle_endtag(self, tag):
        if tag in self._skip_tags: self._skip = max(0, self._skip-1); return
        if tag == "title": self._in.pop("title", None)
        if tag == "h1":   self._in.pop("h1", None)
        if tag == "h2":   self._in.pop("h2", None)
        if tag == "a" and self._cur_href is not None:
            anchor = " ".join(self._cur_anchor).strip()
            self.links.append((self._cur_href, anchor, self._cur_follow, self._cur_alt))
            self._cur_href = None; self._cur_anchor = []

    def handle_data(self, data):
        if self._skip > 0: return
        t = data.strip()
        if not t: return
        if self._in.get("title") and not self.title: self.title = t
        if self._in.get("h1")    and not self.h1:   self.h1 = t
        if self._in.get("h2")    and not self.h2:   self.h2 = t
        if self._cur_href is not None: self._cur_anchor.append(data)
        if self._body: self._words.extend(t.split())

    @property
    def word_count(self): return len(self._words)


# ─────────────────────────────────────────────── HELPERS ──────
def _norm(url: str) -> str:
    p = urlparse(url)
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", p.query, ""))

def _same_domain(url: str, root: str) -> bool:
    n = urlparse(url).netloc.lower()
    return n == root or n.endswith("." + root)

def _charset(ct: str) -> str:
    m = re.search(r"charset=([^\s;]+)", ct, re.I)
    return m.group(1) if m else "utf-8"


# ─────────────────────────────────────────────── MAIN CRAWLER ─
def crawl(start_url: str, output_dir: str,
          max_pages: int = 200,
          on_progress=None) -> dict:
    """
    Crawl start_url (BFS, internal-only) and write 3 CSVs to output_dir.
    on_progress(message, percent_int) is called at each page.
    Returns {"pages": N, "links": N}.
    """
    def prog(msg, pct=None):
        if on_progress: on_progress(msg, pct)

    os.makedirs(output_dir, exist_ok=True)

    parsed = urlparse(start_url)
    root_netloc = parsed.netloc.lower()
    root_scheme = parsed.scheme

    # robots.txt
    rp = RobotFileParser()
    try:
        rp.set_url(f"{root_scheme}://{root_netloc}/robots.txt")
        rp.read()
    except Exception:
        rp = None

    def can_fetch(u):
        if rp is None: return True
        try: return rp.can_fetch(UA, u)
        except: return True

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    visited: dict[str, dict] = {}   # norm_url -> page_dict
    queue: deque[tuple[str, int]] = deque()
    seen: set[str] = set()
    all_links: list[dict] = []

    start_norm = _norm(start_url)
    queue.append((start_norm, 0))
    seen.add(start_norm)

    while queue and len(visited) < max_pages:
        url, depth = queue.popleft()
        if not can_fetch(url): continue

        n_done = len(visited) + 1
        pct = min(90, int(n_done / max_pages * 90))
        prog(f"Crawling page {n_done}: {url.replace(f'{root_scheme}://{root_netloc}','') or '/'}", pct)

        # ── fetch ──────────────────────────────────────────────────
        final_url = url; status = 0; content_type = ""; raw = b""
        try:
            req = Request(url, headers={"User-Agent": UA})
            with urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
                final_url = _norm(resp.geturl())
                status = resp.status
                content_type = resp.headers.get("Content-Type","")
                raw = resp.read(MAX_BYTES)
        except HTTPError as e:
            status = e.code; final_url = url
        except Exception:
            status = 0; final_url = url

        redirect_url  = final_url if final_url != url else ""
        redirect_type = "301" if final_url != url else ""

        is_html_page = "text/html" in content_type.lower() and status == 200

        # ── parse ──────────────────────────────────────────────────
        parser = _Parser()
        if is_html_page and raw:
            try:
                parser.feed(raw.decode(_charset(content_type), errors="ignore"))
            except Exception:
                pass

        indexable = ("Indexable"
                     if is_html_page and not parser.noindex
                     else "Non-Indexable")

        page = {
            "Address":                     final_url,
            "Content Type":                content_type.split(";")[0].strip() or "text/html",
            "Status Code":                 str(status),
            "Status":                      "OK" if status == 200 else str(status),
            "Indexability":                indexable,
            "Indexability Status":         "",
            "Title 1":                     parser.title[:200],
            "Title 1 Length":              str(len(parser.title)),
            "Meta Description 1":          parser.meta_desc[:300],
            "Meta Description 1 Length":   str(len(parser.meta_desc)),
            "H1-1":                        parser.h1[:200],
            "H1-1 Length":                 str(len(parser.h1)),
            "H2-1":                        parser.h2[:200],
            "Word Count":                  str(parser.word_count),
            "Crawl Depth":                 str(depth),
            "Inlinks":                     "0",
            "Unique Inlinks":              "0",
            "Outlinks":                    "0",
            "Unique Outlinks":             "0",
            "External Outlinks":           "0",
            "Unique External Outlinks":    "0",
            "Redirect URL":                redirect_url,
            "Redirect Type":               redirect_type,
        }
        visited[url] = page
        if final_url != url:
            visited[final_url] = page

        # ── extract links ──────────────────────────────────────────
        if is_html_page:
            ext_out = set()
            for href, anchor, follow, alt in parser.links:
                if not href or href.startswith(("javascript:","mailto:","tel:","#")):
                    continue
                abs_url = urljoin(final_url, href)
                abs_norm = _norm(abs_url)
                if not abs_norm.startswith(("http://","https://")): continue

                if _same_domain(abs_norm, root_netloc):
                    all_links.append({
                        "Type":          "Hyperlink",
                        "Source":        final_url,
                        "Destination":   abs_norm,
                        "Size (Bytes)":  "",
                        "Alt Text":      alt,
                        "Anchor":        anchor,
                        "Status Code":   "",
                        "Status":        "",
                        "Follow":        "true" if follow else "false",
                        "Target":        "",
                        "Rel":           "" if follow else "nofollow",
                        "Path Type":     "Absolute",
                        "Link Path":     "",
                        "Link Position": "Content",
                        "Link Origin":   "HTML",
                    })
                    if abs_norm not in seen:
                        seen.add(abs_norm); queue.append((abs_norm, depth+1))
                else:
                    ext_out.add(abs_norm)

            page["External Outlinks"]        = str(len(ext_out))
            page["Unique External Outlinks"]  = str(len(ext_out))

    # ── fill in destination status codes ──────────────────────────
    for lnk in all_links:
        d = lnk["Destination"]
        if d in visited:
            lnk["Status Code"] = visited[d].get("Status Code","")
            lnk["Status"]      = visited[d].get("Status","")

    # ── compute inlink / outlink counts ───────────────────────────
    in_pages:  dict[str, set] = {}
    out_pages: dict[str, set] = {}
    for lnk in all_links:
        s, d = lnk["Source"], lnk["Destination"]
        in_pages.setdefault(d, set()).add(s)
        out_pages.setdefault(s, set()).add(d)

    pages = list({p["Address"]: p for p in visited.values()}.values())
    for p in pages:
        addr = p["Address"]
        p["Unique Inlinks"]  = str(len(in_pages.get(addr, set())))
        p["Unique Outlinks"] = str(len(out_pages.get(addr, set())))
        p["Inlinks"]         = p["Unique Inlinks"]
        p["Outlinks"]        = p["Unique Outlinks"]

    prog("Writing CSV files…", 95)

    # ── write CSVs ────────────────────────────────────────────────
    def write_csv(path, cols, rows):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader(); w.writerows(rows)

    write_csv(os.path.join(output_dir, "internal_html.csv"),     HTML_COLS, pages)
    write_csv(os.path.join(output_dir, "all_inlinks.csv"),       LINK_COLS, all_links)
    write_csv(os.path.join(output_dir, "all_anchor_text.csv"),   LINK_COLS, all_links)

    prog("Crawl complete!", 100)
    return {"pages": len(pages), "links": len(all_links)}
