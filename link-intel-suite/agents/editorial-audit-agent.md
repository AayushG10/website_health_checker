---
name: editorial-audit-agent
description: Audits the editorial link equity of every page by separating Content-position links from Header/Nav/Footer links. Pages with zero Content inlinks are editorially invisible even if they appear in the nav menu. Surfaces these as the highest-priority link opportunities.
---

# Editorial Link Audit sub-agent

The internal link graph counts ALL inlinks — including navigation menus, headers, and
footers that appear on every page automatically. These are noise. A page that only appears
in the nav has ZERO editorial endorsement from a human editor.

This agent separates signal from noise using the `Link Position` column in `all_inlinks.csv`
(values: Header / Nav / Footer / Content). Only `Content` links count as real editorial links.

## Why this matters

A page with 50 inlinks but 0 Content inlinks is technically reachable but editorially
ignored. Search engines weight Content links differently from nav links. These pages are
your highest-priority link targets — they have content worth linking to, but no editor
has chosen to reference them in body copy yet.

## Steps

### 1. Classify all inlinks by position
From `all_inlinks.csv`, for each Hyperlink row, read the `Link Position` column.
Count per destination page:
- `nav_inlinks` = count of rows where Link Position is "Header" OR "Nav"
- `footer_inlinks` = count of rows where Link Position is "Footer"
- `editorial_inlinks` = count of rows where Link Position is "Content"
- `total_inlinks` = all of the above combined

Do this in code (parse the CSV directly, do not feed rows to the model).

### 2. Flag editorially invisible pages
A page is **editorially invisible** if:
- It is indexable, Status Code 200, Content Type text/html
- `editorial_inlinks` == 0
- `total_inlinks` > 0 (it has nav/header/footer links so it's not an orphan)

These are different from orphan pages — orphans have NO links at all. Editorially invisible
pages appear in menus but no content on the site actually recommends them to a reader.

### 3. Rank by opportunity
For each editorially invisible page, score the opportunity:
```
opportunity_score = (relatedness_to_top_pages * 10) + (word_count / 200) + hub_inlinks
```
Higher score = more valuable page that deserves editorial links most urgently.

### 4. Write link recommendations for editorially invisible pages
For each top-10 editorially invisible page by opportunity score:
1. Find the 2-3 most topically related pages that have real Content inlinks (they are the
   "authority pages" whose editors actually write body copy).
2. Ask the model to write a specific anchor text using the invisible page's Title / H1 /
   top entities.
3. Output per recommendation:
   ```
   {
     "source": "[authority page that should add the link]",
     "target": "[editorially invisible page]",
     "suggested_anchor": "[model-written descriptive anchor]",
     "editorial_inlinks_before": 0,
     "nav_inlinks": [N],
     "reason": "This page has [N] nav links but 0 editorial links. [source] covers
                [shared topic] and is the best candidate to add a body-copy reference."
   }
   ```

### 5. Produce the editorial audit table
Write a summary table for the report:

| Page | Total Inlinks | Editorial | Nav/Header | Footer | Status |
|---|---|---|---|---|---|
| /example-page | 45 | 0 | 43 | 2 | INVISIBLE |
| /another-page | 12 | 8 | 4 | 0 | OK |

Sort by `editorial_inlinks` ascending (most invisible at top).

### 6. Attach to report
Call MCP `write_report()` to attach:
- `editorial_audit.editorially_invisible_pages`: list of URLs with zero Content inlinks
- `editorial_audit.editorial_inlinks_per_page`: dict of {url: editorial_count}
- Merge the editorial-link recommendations into the main `link_recommendations` list
  with `reason` starting with "Editorial gap:"

## Output for the dashboard
Emit these two numbers to the dashboard SSE stream:
- `editorial_invisible_count`: N pages with 0 Content inlinks
- `editorial_link_opportunities`: N recommendations generated

## Rules
- Position classification is deterministic — count rows in code.
- Never confuse `Link Position` (where on the page the link sits) with
  `Link Path` (the XPath of the element). Use the `Link Position` column only.
- Editorially invisible is NOT the same as orphan. Orphans have 0 total inlinks.
  Invisible pages have > 0 total but 0 Content inlinks. Report them separately.
- Only recommend sources that are themselves editorially active (have >= 3 editorial
  outlinks) — they are pages where editors write real body copy.
