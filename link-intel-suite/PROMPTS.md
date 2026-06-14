# PROMPTS.md - my key prompts log

Keep the handful of prompts that actually moved the build. Not every message - the ones that
mattered: the system/sub-agent prompts, the ones you iterated on, the "this finally worked"
moment. Paste them here MANUALLY as you go.

Why manual? Some free Ollama cloud models do not save a local session log, so an auto audit
log may be empty. That is fine and expected (see the brief's Model Fairness section). What
guarantees your process is judged fairly is: the working plugin + reproducible report.json,
incremental git commits, this PROMPTS.md, and a short DECISIONS.md. Keep these up to date.

Format per entry:
- **Prompt** (paste it)
- **For:** what you were trying to do
- **Revised?** did you have to change it, and why

---

## Example (replace with your own)

- **Prompt:** "Extend linkintel/analyzer.py over_optimized_anchors: flag a destination where
  one non-generic anchor is >= 60% of all internal anchors pointing at it AND count >= 10.
  Run python linkintel/analyzer.py and show the counts."
- **For:** completing the over-optimized exact-match anchor rule
- **Revised?** Yes - first version flagged tiny destinations; added the count >= 10 floor.

---

## My prompts

1. **Prompt:** "Fix the over_linked_page detection in graph_stats(). Rulebook: page in top 5%
   by Unique Inlinks. Replace the current logic with: sort values ascending, threshold =
   vals[int(len(vals)*0.95)], over_linked = all pages where Unique Inlinks >= threshold,
   skip if threshold == 0. Run analyzer and show count + first 3 URLs."
   - **For:** fixing a dead-code bug (`[:0]` made first branch always empty)
   - **Revised?** No — one shot. Result: 23 pages, first 3 are homepage / /blog / /about-us.

2. **Prompt:** "Extend GENERIC_ANCHORS. Rulebook core set + these additional terms: 'read
   more...', 'learn more...', 'click', 'go', 'view', 'see more', 'see details', 'more details',
   'more info', 'info', 'this page', 'this post', 'this article', 'visit', 'visit page',
   'visit here', 'check it out', 'check this out', 'find out', 'get started', 'start here',
   'see here', 'view details', 'read this', 'read here', 'follow this link', 'follow link',
   'open', 'open here', 'show more', 'show details', 'expand', 'see all', 'view all',
   'get more', 'get info', 'know more...'. Run analyzer, show new vs old count."
   - **For:** extending the rulebook anchor set with common real-world non-descriptive phrases
   - **Revised?** No — 21 → 50 terms; generic_anchors count: 157 → 158 on sample export.

3. **Prompt:** "Harden _norm(). Add: lowercase full URL, strip whitespace from both ends, drop
   #fragment (already done), remove exactly ONE trailing slash (not recursive — '/path//' →
   '/path/' not '/path'). Keep query strings. After fixing, confirm orphan count and total
   pages stay the same."
   - **For:** making URL matching case-insensitive and bulletproof per rulebook
   - **Revised?** No — all 5 edge-case tests passed first try; page counts unchanged.

4. **Prompt:** "Replace URL path-segment clustering with greedy keyword-similarity clustering.
   Seed = most-inlinked page. Each page joins the cluster whose seed it has highest Jaccard
   overlap with (>0); if all overlaps are 0, start a new cluster. cluster['name'] = None
   (topic-agent fills it). cluster['key'] = top keyword slug. Show cluster count, top 3
   clusters, confirm 201/201 pages covered with no duplicates."
   - **For:** replacing the crude path-segment grouping with topical grouping
   - **Revised?** Yes — plain TF produced 4 clusters (site-wide terms dominated). Switched to
     TF-IDF via `compute_tfidf()` (prompt #5). With TF-IDF: 24 clusters, largest = 50 pages.

5. **Prompt:** "Add compute_tfidf(pages, page_text, top=12). Step 1: raw token counts with
   H1 weighted ×3. Step 2: document frequency. Step 3: TF-IDF = (cnt/total) * (log(N/(df+1))+1).
   In cluster_pages(), replace page_keywords() call with compute_tfidf(idx200, page_text).
   In analyze(), pass clusters['page_keywords'] directly to relatedness() — no separate
   build_tfidf_keywords() call. Run analyzer; expect 8-15+ clusters, confirm 201/201 coverage."
   - **For:** fixing the 4-cluster collapse caused by plain TF generic terms dominating Jaccard
   - **Revised?** No — 24 clusters on first try, largest 50 pages, all 201 covered.

7. **Prompt:** "qwen3:8b returns empty content on all streaming chunks — content is '' and
   thinking is non-empty. Test think=False API param vs /no_think in system/user message vs
   increasing num_predict. Report which works with num_predict=20."
   - **For:** debugging why _chat() returned empty string for every call through the module
   - **Revised?** Yes — `/no_think` in system/user message still triggers thinking. `think: False`
     in the top-level JSON payload (not in `options`) disables thinking entirely. With that fix
     `num_predict=50` is sufficient. Root cause: thinking tokens count against `num_predict`,
     so a budget of 20 is entirely consumed by `<think>` with no room for the answer.

6. **Prompt:** "Create linkintel/model_steps.py with three Ollama API functions:
   name_clusters(clusters) — one batched call for all clusters, returns {key: name};
   extract_entities(url, body, title, h1) — one call per page, returns list of 5-10 entities;
   write_anchors(source_url, source_title, candidates, pages_by_url) — one call per source
   page, returns candidates with suggested_anchor filled. Degrade gracefully if Ollama
   unreachable. Wire into run.py after deterministic steps with --no-model flag for headless
   testing. Add page_text to analyze() return dict."
   - **For:** wiring model-driven cluster naming and anchor writing into the headless pipeline
   - **Revised?** Minor — added is_available() check + --no-model CLI flag so run.py works
     without Ollama for grader testing. Schema still passes with null anchors.
