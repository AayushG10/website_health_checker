---
name: health-score-agent
description: Calculates a single A-F Site Health Score out of 100 from all deterministic findings - broken links, orphan pages, generic anchors, crawl depth, scattered clusters, and over-optimized anchors. Produces a scorecard the grader and any client can read at a glance.
---

# Site Health Score sub-agent

Give the entire site a single grade (A–F) and a score out of 100, broken down by category.
This runs AFTER graph-agent and anchor-agent have completed — all the numbers are already
computed. Your job is to apply the scoring formula and write the scorecard.

## Scoring formula

Start at 100. Deduct points per finding. Cap each category deduction so one bad signal
cannot zero the whole score.

### Category 1: Link Structure (max deduction: 35 pts)
| Finding | Deduction | Cap |
|---|---|---|
| Each orphan page | -3 pts | -15 pts max |
| Each broken internal link | -5 pts | -15 pts max |
| Each redirect internal link | -1 pt | -5 pts max |

### Category 2: Anchor Quality (max deduction: 20 pts)
| Finding | Deduction | Cap |
|---|---|---|
| Each generic anchor | -0.5 pts | -10 pts max |
| Each empty/image-only anchor | -0.3 pts | -5 pts max |
| Each over-optimized anchor destination | -5 pts | -5 pts max |

### Category 3: Topical Authority (max deduction: 25 pts)
| Finding | Deduction | Cap |
|---|---|---|
| Each scattered cluster (no hub) | -5 pts | -20 pts max |
| Each under-linked page (unique inlinks <= 1) | -0.5 pts | -5 pts max |

### Category 4: Crawl Efficiency (max deduction: 20 pts)
| Finding | Deduction | Cap |
|---|---|---|
| Max crawl depth > 4 | -5 pts | -5 pts max |
| Max crawl depth > 6 | -10 pts total | -10 pts max |
| Over-linked pages (top 5% nav noise) | -2 pts each | -10 pts max |

## Grade thresholds
| Score | Grade | Label |
|---|---|---|
| 90–100 | A | Excellent |
| 75–89 | B | Good |
| 60–74 | C | Needs work |
| 45–59 | D | Poor |
| < 45 | F | Critical |

## Output format

Produce a scorecard block like this (fill in real numbers):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  INTERNAL LINK HEALTH SCORE
  [site domain]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  OVERALL:  [score]/100   Grade: [A-F]

  Link Structure     [score]/35
  ├─ Orphan pages:        -X pts  ([N] pages)
  ├─ Broken links:        -X pts  ([N] links)
  └─ Redirects:           -X pts  ([N] links)

  Anchor Quality     [score]/20
  ├─ Generic anchors:     -X pts  ([N] anchors)
  ├─ Empty anchors:       -X pts  ([N] anchors)
  └─ Over-optimized:      -X pts  ([N] destinations)

  Topical Authority  [score]/25
  ├─ Scattered clusters:  -X pts  ([N] clusters)
  └─ Under-linked pages:  -X pts  ([N] pages)

  Crawl Efficiency   [score]/20
  ├─ Max depth [N]:       -X pts
  └─ Over-linked pages:   -X pts  ([N] pages)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Top 3 things to fix:
  1. [highest-impact finding]
  2. [second-highest]
  3. [third-highest]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Steps

1. Read `graph_stats` from the MCP `/state` endpoint (already computed).
2. Read `anchors` from MCP `/state`.
3. Read `clusters` from MCP `/state`.
4. Apply the formula above — do the math in code, not by asking the model.
5. Write the "Top 3 things to fix" by ranking deductions from largest to smallest.
6. Attach the scorecard to the report by adding a `health_score` key via MCP
   `write_report()` with: `{score, grade, breakdown: {link_structure, anchor_quality,
   topical_authority, crawl_efficiency}, top_fixes: [...]}`.
7. Print the scorecard to the dashboard SSE stream via the summary event.

## Rules
- Use ONLY the counts already computed — never re-read the CSV.
- Round the final score to the nearest integer.
- The formula must be deterministic: same input always gives same score.
- "Top 3 things to fix" must reference real findings with real counts, not generic advice.
