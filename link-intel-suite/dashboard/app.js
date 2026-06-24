// app.js — Link Intel Suite multi-page dashboard

const $ = id => document.getElementById(id);
const slug = url => (url || "").replace(/https?:\/\/[^/]+/, "") || "/";
const trunc = (s, n) => s && s.length > n ? s.slice(0, n) + "…" : (s || "");
const CIRC = 2 * Math.PI * 50; // gauge r=50

// ─── Chart registry (prevent duplicate instances) ─────────────────────────────
const charts = {};
function mkChart(id, config) {
  const el = $(id); if (!el) return null;
  if (charts[id]) { charts[id].destroy(); }
  charts[id] = new Chart(el, config);
  return charts[id];
}

// ─── SPA Navigation ───────────────────────────────────────────────────────────
function nav(page) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  const pg = $("page-" + page); if (pg) pg.classList.add("active");
  const ni = document.querySelector(`[data-page="${page}"]`); if (ni) ni.classList.add("active");
  window.location.hash = page;
  // lazy-render charts when page becomes visible
  if (page === "graph") { renderDepthChart(RUN.depth_distribution); renderLinkDistChart(RUN.graph_stats); }
  if (page === "anchors") { renderAnchorChart(RUN.anchor_breakdown); renderAnchorKwChart(RUN.digital_marketing?.anchor_keyword_map); }
  if (page === "clusters") { renderClusterChart(RUN.clusters); renderAuthorityChart(RUN.clusters); }
  if (page === "cannibal") { renderCannibalChart(RUN.digital_marketing?.cannibalization); }
  if (page === "opportunities") { renderOppsChart(RUN.digital_marketing?.seo_opportunities); }
  if (page === "pagerank") { renderPRCharts(RUN.digital_marketing?.pagerank_top, RUN.digital_marketing?.pagerank_bottom); }
}
// restore hash on load
window.addEventListener("hashchange", () => nav(location.hash.slice(1) || "overview"));

// ─── Animated counter ─────────────────────────────────────────────────────────
function animCount(el, target, dur = 700) {
  if (!el || el.dataset.target == target) return;
  el.dataset.target = target;
  const start = parseInt(el.textContent) || 0;
  const t0 = performance.now();
  const tick = now => {
    const p = Math.min((now - t0) / dur, 1);
    el.textContent = Math.round(start + (target - start) * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// ─── Grade colors ──────────────────────────────────────────────────────────────
const GC = { A: "#10B981", B: "#818CF8", C: "#F59E0B", D: "#F59E0B", F: "#EF4444" };

// ─── Health gauge ──────────────────────────────────────────────────────────────
function paintGauge(score, grade) {
  const fill = $("gauge-fill"), sc = $("gauge-score"), gr = $("gauge-grade"), bar = $("score-bar");
  const col = GC[grade] || "#818CF8";
  if (fill) { fill.style.stroke = col; fill.style.strokeDashoffset = CIRC * (1 - score / 100); }
  if (sc) { sc.style.color = col; animCount(sc, score); }
  if (gr) { gr.textContent = grade; gr.style.color = col; }
  if (bar) { bar.style.width = score + "%"; bar.style.background = col; }
  const lbl = $("health-label");
  if (lbl) lbl.textContent = "Site Link Health: " + score + "/100";
  const desc = $("health-desc");
  const msgs = { A: "Excellent — this site links like a pro", B: "Good — a few tweaks and you're there",
                 C: "Fair — several issues need attention", D: "Poor — significant problems present",
                 F: "Critical — major linking failures detected" };
  if (desc) desc.textContent = msgs[grade] || "Link health score";
  const pills = $("health-pills");
  if (pills && RUN.summary) {
    const s = RUN.summary;
    pills.innerHTML = [
      s.broken_internal_links > 0 ? `<span class="health-pill" style="border-color:var(--red);color:var(--red);background:#3a081244">${s.broken_internal_links} broken links</span>` : "",
      s.orphan_pages > 0 ? `<span class="health-pill" style="border-color:var(--amber);color:var(--amber);background:#2a1a0044">${s.orphan_pages} orphans</span>` : "",
      s.generic_anchors > 0 ? `<span class="health-pill" style="border-color:var(--amber);color:var(--amber);background:#2a1a0044">${s.generic_anchors} generic anchors</span>` : "",
      `<span class="health-pill" style="border-color:var(--indigo2);color:var(--indigo2);background:#0a142844">${s.topical_clusters} clusters</span>`,
    ].join("");
  }
  const sub = $("ov-sub");
  if (sub && RUN.site) sub.textContent = RUN.site + " · " + (RUN.summary?.pages_crawled || "?") + " pages · " + (RUN.summary?.internal_links || "?") + " links";
}

// ─── KPI cards ────────────────────────────────────────────────────────────────
function paintKPIs(RUN) {
  const g = RUN.graph_stats, a = RUN.anchors, s = RUN.summary, dm = RUN.digital_marketing;
  if (g) {
    animCount($("k-links"), g.internal_links); animCount($("k-broken"), g.broken_internal_links);
    animCount($("k-orphans"), g.orphan_pages); animCount($("k-redirects"), g.redirect_internal_links);
    // graph page
    animCount($("g-links"), g.internal_links); animCount($("g-pages"), g.pages_total);
    animCount($("g-broken"), g.broken_internal_links); animCount($("g-redirects"), g.redirect_internal_links);
    animCount($("g-nofollow"), g.nofollow_internal_links); animCount($("g-orphans"), g.orphan_pages);
    animCount($("g-depth"), g.max_crawl_depth); animCount($("g-avg"), g.avg_inlinks);
    $("broken-cnt") && ($("broken-cnt").textContent = g.broken_internal_links + " found");
  }
  if (a) {
    animCount($("k-generic"), a.generic); animCount($("a-total"), a.total);
    animCount($("a-generic"), a.generic); animCount($("a-empty"), a.empty_or_image_only);
    animCount($("a-over"), a.over_optimized);
    const good = (a.total || 0) - (a.generic || 0) - (a.empty_or_image_only || 0) - (a.over_optimized || 0);
    animCount($("a-good"), Math.max(good, 0));
  }
  if (RUN.clusters) {
    animCount($("k-clusters"), RUN.clusters.length);
    animCount($("cl-total"), RUN.clusters.length);
    const hubs = RUN.clusters.filter(c => c.authority === "hub").length;
    const scat = RUN.clusters.length - hubs;
    animCount($("cl-hub"), hubs); animCount($("cl-scattered"), scat);
    animCount($("scattered-count"), scat);
    const total = RUN.clusters.reduce((n, c) => n + c.size, 0);
    animCount($("cl-pages"), total);
  }
  if (s) { animCount($("k-recs"), s.link_recommendations); }
  else if (RUN.recommendations != null) animCount($("k-recs"), RUN.recommendations);
  if (dm) {
    const thin = dm.thin_content?.length || 0;
    animCount($("k-thin"), thin); animCount($("thin-count"), thin);
    animCount($("gap-count"), dm.content_gaps?.length || 0);
    if (dm.money_pages) {
      animCount($("mp-critical"), dm.money_pages.filter(p => p.risk === "critical").length);
      animCount($("mp-high"), dm.money_pages.filter(p => p.risk === "high").length);
      animCount($("mp-medium"), dm.money_pages.filter(p => p.risk === "medium").length);
      animCount($("mp-low"), dm.money_pages.filter(p => p.risk === "low").length);
    }
    // nav badges
    const nb = $("nb-money"); if (nb) { nb.textContent = dm.money_pages?.filter(p => p.risk === "critical" || p.risk === "high").length || 0; }
    const nc = $("nb-cannibal"); if (nc) { nc.textContent = dm.cannibalization?.length || 0; }
    const nt = $("nb-thin"); if (nt) { nt.textContent = thin; }
  }
  // nav badges
  if (g) { const b = $("nb-broken"); if (b) { b.textContent = g.broken_internal_links || 0; b.className = "nav-badge " + (g.broken_internal_links > 0 ? "red" : ""); } }
  if (a) { const b = $("nb-generic"); if (b) { b.textContent = a.generic || 0; } }
  if (RUN.clusters) { const b = $("nb-clusters"); if (b) b.textContent = RUN.clusters.length; }
  if (s) { const b = $("nb-recs"); if (b) { b.textContent = s.link_recommendations || 0; } }
  if (RUN.health_score != null) { const b = $("nb-score"); if (b) { b.textContent = (RUN.health_grade || "") + " " + RUN.health_score; } }
}

// ─── Charts ───────────────────────────────────────────────────────────────────
const darkGrid = { color: "#1f1f2e" }, muteTick = { color: "#7a7a90", font: { size: 10 } };

function renderDepthChart(dist) {
  if (!dist) return;
  const labels = Object.keys(dist).sort((a,b) => +a - +b).map(l => "Depth " + l);
  const vals = Object.keys(dist).sort((a,b) => +a - +b).map(k => dist[k]);
  mkChart("chart-depth", { type: "bar", data: { labels, datasets: [{ label:"Pages", data: vals, backgroundColor:"#818CF8", borderRadius:6, borderWidth:0 }] },
    options: { responsive:true, maintainAspectRatio:false, plugins:{ legend:{ display:false } },
      scales:{ x:{ ticks:muteTick, grid:{ color:"#1f1f2e" } }, y:{ ticks:muteTick, grid:{ color:"#1f1f2e" } } } } });
}

function renderLinkDistChart(g) {
  if (!g) return;
  mkChart("chart-link-dist", { type:"doughnut",
    data:{ labels:["Good links","Broken","Redirects","Nofollow"],
      datasets:[{ data:[g.internal_links - g.broken_internal_links - g.redirect_internal_links - g.nofollow_internal_links, g.broken_internal_links, g.redirect_internal_links, g.nofollow_internal_links],
        backgroundColor:["#10B981","#EF4444","#F59E0B","#6366F1"], borderWidth:0 }] },
    options:{ responsive:true, maintainAspectRatio:false, cutout:"62%",
      plugins:{ legend:{ position:"bottom", labels:{ color:"#7a7a90", font:{ size:10 }, boxWidth:10, padding:8 } } } } });
}

function renderAnchorChart(bd) {
  if (!bd) return;
  const good = Math.max((bd.good || 0), 0);
  mkChart("chart-anchors", { type:"doughnut",
    data:{ labels:["Descriptive","Generic","Empty/Image","Over-optimized"],
      datasets:[{ data:[good, bd.generic||0, bd.empty||0, bd.over_optimized||0],
        backgroundColor:["#10B981","#F59E0B","#7a7a90","#EF4444"], borderWidth:0 }] },
    options:{ responsive:true, maintainAspectRatio:false, cutout:"62%",
      plugins:{ legend:{ position:"bottom", labels:{ color:"#7a7a90", font:{ size:10 }, boxWidth:10, padding:8 } } } } });
}

function renderAnchorKwChart(kws) {
  if (!kws || !kws.length) return;
  const top = kws.slice(0, 12);
  mkChart("chart-anchor-kw", { type:"bar",
    data:{ labels: top.map(k => k.keyword),
      datasets:[{ label:"Uses", data: top.map(k => k.count), backgroundColor:"#6366F1", borderRadius:5, borderWidth:0 }] },
    options:{ indexAxis:"y", responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ display:false } },
      scales:{ x:{ ticks:muteTick, grid:darkGrid }, y:{ ticks:{ ...muteTick, color:"#c8c5be" }, grid:{ display:false } } } } });
}

function renderClusterChart(clusters) {
  if (!clusters || !clusters.length) return;
  const top = clusters.slice(0, 10);
  mkChart("chart-clusters", { type:"bar",
    data:{ labels: top.map(c => trunc(c.name || c.key, 16)),
      datasets:[{ label:"Pages", data: top.map(c => c.size),
        backgroundColor: top.map(c => c.authority === "hub" ? "#10B981" : "#6366F1"), borderRadius:5, borderWidth:0 }] },
    options:{ indexAxis:"y", responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ display:false } },
      scales:{ x:{ ticks:muteTick, grid:darkGrid }, y:{ ticks:{ ...muteTick, color:"#c8c5be" }, grid:{ display:false } } } } });
}

function renderAuthorityChart(clusters) {
  if (!clusters) return;
  const hub = clusters.filter(c => c.authority === "hub").length;
  const scat = clusters.length - hub;
  mkChart("chart-authority", { type:"doughnut",
    data:{ labels:["Hub (clear authority)","Scattered (no clear hub)"],
      datasets:[{ data:[hub, scat], backgroundColor:["#10B981","#EF4444"], borderWidth:0 }] },
    options:{ responsive:true, maintainAspectRatio:false, cutout:"60%",
      plugins:{ legend:{ position:"bottom", labels:{ color:"#7a7a90", font:{ size:11 }, boxWidth:12, padding:10 } } } } });
}

function renderCannibalChart(pairs) {
  if (!pairs || !pairs.length) return;
  const buckets = { "45–55%":0, "55–70%":0, ">70%":0 };
  pairs.forEach(p => { const pct = p.overlap_score * 100; if (pct >= 70) buckets[">70%"]++; else if (pct >= 55) buckets["55–70%"]++; else buckets["45–55%"]++; });
  mkChart("chart-cannibal", { type:"bar",
    data:{ labels: Object.keys(buckets), datasets:[{ label:"Page pairs", data: Object.values(buckets),
        backgroundColor:["#818CF8","#F59E0B","#EF4444"], borderRadius:8, borderWidth:0 }] },
    options:{ responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ display:false } },
      scales:{ x:{ ticks:muteTick, grid:darkGrid }, y:{ ticks:muteTick, grid:darkGrid } } } });
}

function renderOppsChart(opps) {
  if (!opps || !opps.length) return;
  const labels = opps.slice(0, 12).map((o, i) => "P" + (i + 1));
  const vals = opps.slice(0, 12).map(o => o.opportunity_score);
  mkChart("chart-opps", { type:"bar",
    data:{ labels, datasets:[{ label:"Opportunity Score", data: vals,
        backgroundColor: vals.map((v, i) => i < 3 ? "#EF4444" : i < 7 ? "#F59E0B" : "#818CF8"), borderRadius:6, borderWidth:0 }] },
    options:{ responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ display:false }, tooltip:{ callbacks:{ label: c => " Score: " + c.parsed.y } } },
      scales:{ x:{ ticks:muteTick, grid:darkGrid }, y:{ ticks:muteTick, grid:darkGrid } } } });
}

function renderPRCharts(top, bottom) {
  if (!top || !top.length) return;
  const topLabels = top.slice(0, 10).map(p => slug(p.url).replace(/\/$/, "").split("/").pop() || "/");
  const topVals = top.slice(0, 10).map(p => p.score);
  mkChart("chart-pr-top", { type:"bar",
    data:{ labels:topLabels, datasets:[{ label:"PR Score", data:topVals, backgroundColor:"#10B981", borderRadius:5, borderWidth:0 }] },
    options:{ indexAxis:"y", responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ display:false } },
      scales:{ x:{ ticks:muteTick, grid:darkGrid }, y:{ ticks:{ ...muteTick, color:"#c8c5be" }, grid:{ display:false } } } } });
  if (!bottom || !bottom.length) return;
  const botLabels = bottom.slice(0, 10).map(p => slug(p.url).replace(/\/$/, "").split("/").pop() || "/");
  const botVals = bottom.slice(0, 10).map(p => p.score);
  mkChart("chart-pr-bottom", { type:"bar",
    data:{ labels:botLabels, datasets:[{ label:"PR Score", data:botVals, backgroundColor:"#EF4444", borderRadius:5, borderWidth:0 }] },
    options:{ indexAxis:"y", responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ display:false } },
      scales:{ x:{ ticks:muteTick, grid:darkGrid }, y:{ ticks:{ ...muteTick, color:"#c8c5be" }, grid:{ display:false } } } } });
}

// ─── Table renderers ──────────────────────────────────────────────────────────
function paintFixList(fixes) {
  const el = $("fix-list"); if (!el) return;
  if (!fixes || !fixes.length) { el.innerHTML = '<div class="empty-state"><span class="icon">✅</span>No critical fixes found</div>'; return; }
  el.innerHTML = fixes.map((f, i) => `
    <div class="fix-item">
      <div class="fix-num ${f.impact}">#${i+1}</div>
      <div class="fix-body">
        <div class="fix-action">${f.action}</div>
        <div class="fix-detail">${f.detail || f.source || ""}</div>
      </div>
      <span class="badge ${f.impact}">${f.impact}</span>
    </div>`).join("");
}

function paintBroken(links) {
  const tbody = $("broken-tbody"); if (!tbody) return;
  if (!links || !links.length) { tbody.innerHTML = '<tr><td colspan="4" class="empty-state" style="color:var(--green)">✅ No broken internal links</td></tr>'; return; }
  tbody.innerHTML = links.slice(0, 40).map(l => `<tr>
    <td class="mono">${trunc(slug(l.source), 40)}</td>
    <td class="mono">${trunc(slug(l.destination), 40)}</td>
    <td><span class="badge ${l.status >= 500 ? "critical" : "high"}">${l.status}</span></td>
    <td style="color:var(--mute)">${trunc(l.anchor || "", 40)}</td>
  </tr>`).join("");
}

function paintOrphans(orphanUrls, underUrls) {
  const tbody = $("orphan-tbody"); if (!tbody) return;
  const orphans = (orphanUrls || []).map(u => ({url:u, inlinks:0}));
  const orphanSet = new Set(orphanUrls || []);
  const under = (underUrls || []).filter(u => !orphanSet.has(u)).map(u => ({url:u, inlinks:1}));
  const pages = [...orphans, ...under];
  if (!pages.length) { tbody.innerHTML = '<tr><td colspan="3" class="empty-state" style="color:var(--green)">✅ No orphan pages</td></tr>'; return; }
  tbody.innerHTML = pages.slice(0, 25).map(p => `<tr>
    <td class="mono">${trunc(slug(p.url), 45)}</td>
    <td><span class="badge ${p.inlinks === 0 ? "critical" : "high"}">${p.inlinks}</span></td>
    <td style="color:var(--mute)">${p.inlinks === 0 ? "Orphan" : "Under-linked"}</td>
  </tr>`).join("");
}

function paintGenericAnchors(anchors) {
  const tbody = $("generic-tbody"); if (!tbody) return;
  if (!anchors || !anchors.length) { tbody.innerHTML = '<tr><td colspan="3" class="empty-state" style="color:var(--green)">✅ No generic anchors found</td></tr>'; return; }
  tbody.innerHTML = anchors.slice(0, 30).map(a => `<tr>
    <td class="mono">${trunc(slug(a.source), 38)}</td>
    <td class="mono">${trunc(slug(a.destination), 38)}</td>
    <td><span style="color:var(--amber);font-weight:600">${a.anchor}</span></td>
  </tr>`).join("");
}

function paintOverAnchors(overs) {
  const tbody = $("over-tbody"); if (!tbody) return;
  if (!overs || !overs.length) { tbody.innerHTML = '<tr><td colspan="4" class="empty-state" style="color:var(--green)">✅ No over-optimized anchors</td></tr>'; return; }
  tbody.innerHTML = overs.slice(0, 20).map(o => `<tr>
    <td class="mono">${trunc(slug(o.destination), 38)}</td>
    <td><span style="color:var(--red);font-weight:600">${o.anchor}</span></td>
    <td>${o.count}</td>
    <td><span style="color:${o.share >= 0.8 ? "var(--red)" : "var(--amber)"}">${Math.round(o.share*100)}%</span></td>
  </tr>`).join("");
}

function paintKeywordCloud(kws) {
  const el = $("kw-cloud"); if (!el || !kws || !kws.length) return;
  const max = kws[0]?.count || 1;
  el.innerHTML = kws.map(k => {
    const sz = Math.round(11 + (k.count / max) * 14);
    const op = (0.4 + (k.count / max) * 0.6).toFixed(2);
    return `<span title="${k.count} uses" style="font-size:${sz}px;font-weight:${sz>18?700:500};color:var(--indigo2);opacity:${op};padding:5px 12px;background:var(--card2);border:1px solid var(--line);border-radius:9px;cursor:default;transition:opacity .15s">${k.keyword}</span>`;
  }).join("");
}

let allClusters = [];
function paintClustersTable(clusters) {
  if (clusters) allClusters = clusters;
  filterClusters();
}
function filterClusters() {
  const tbody = $("cluster-tbody"); if (!tbody) return;
  const q = ($("cluster-search")?.value || "").toLowerCase();
  const data = q ? allClusters.filter(c => (c.name||c.key).toLowerCase().includes(q) || (c.keywords||[]).some(k=>k.includes(q))) : allClusters;
  if (!data.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No clusters found</td></tr>'; return; }
  tbody.innerHTML = data.map(c => `<tr>
    <td><strong>${c.name || c.key}</strong></td>
    <td>${c.size}</td>
    <td><span class="badge ${c.authority}">${c.authority}</span></td>
    <td class="mono">${trunc(slug(c.hub_page||""), 38)}</td>
    <td><div style="display:flex;flex-wrap:wrap;gap:3px">${(c.keywords||[]).slice(0,4).map(k=>`<span style="font-size:10px;padding:1px 6px;border-radius:4px;background:var(--card2);color:var(--mute)">${k}</span>`).join("")}</div></td>
  </tr>`).join("");
}
$("cluster-search")?.addEventListener("input", filterClusters);

function paintContentGaps(gaps) {
  const tbody = $("gaps-tbody") || $("content-gaps-tbody");
  const tbody2 = $("content-gaps-tbody");
  const render = (el, gaps) => {
    if (!el || !gaps) return;
    if (!gaps.length) { el.innerHTML = '<tr><td colspan="5" class="empty-state" style="color:var(--green)">No major content gaps detected</td></tr>'; return; }
    el.innerHTML = gaps.slice(0, 12).map(g => `<tr>
      <td><strong>${g.cluster}</strong></td>
      <td>${g.size}</td>
      <td><span class="badge ${g.authority}">${g.authority}</span></td>
      <td><span style="font-weight:700;color:${g.gap_score>60?"var(--red)":g.gap_score>40?"var(--amber)":"var(--mute)"}">${g.gap_score}</span></td>
      <td><div style="display:flex;flex-wrap:wrap;gap:3px">${(g.keywords||[]).slice(0,3).map(k=>`<span style="font-size:10px;padding:1px 6px;border-radius:4px;background:var(--card2);color:var(--mute)">${k}</span>`).join("")}</div></td>
    </tr>`).join("");
  };
  render(tbody, gaps); render(tbody2, gaps);
}

let allRecs = [];
function paintRecs(recs) { if (recs) allRecs = recs; filterRecs(); }
function filterRecs() {
  const tbody = $("rec-tbody"); if (!tbody) return;
  const q = ($("rec-search")?.value || "").toLowerCase();
  const data = q ? allRecs.filter(r => slug(r.source).includes(q) || slug(r.target).includes(q) || (r.suggested_anchor||"").toLowerCase().includes(q)) : allRecs;
  const lbl = $("rec-count-label"); if (lbl) lbl.textContent = `${data.length} Link Suggestions`;
  const more = $("rec-more");
  if (!data.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No recommendations yet</td></tr>'; return; }
  tbody.innerHTML = data.slice(0, 60).map(r => {
    const anchor = r.suggested_anchor || "(pending)";
    const score = typeof r.relatedness === "number" ? r.relatedness.toFixed(2) : r.relatedness;
    const pct = Math.round((r.relatedness || 0) * 100);
    return `<tr>
      <td class="mono">${trunc(slug(r.source), 38)}</td>
      <td class="mono">${trunc(slug(r.target), 38)}</td>
      <td><span style="color:var(--indigo2);font-weight:600">${anchor}</span></td>
      <td><div style="display:flex;align-items:center;gap:6px"><div style="background:var(--line);border-radius:3px;height:4px;width:60px;overflow:hidden"><div style="height:4px;width:${Math.max(pct,3)}%;background:var(--indigo2);border-radius:3px"></div></div><span class="mono">${score}</span></div></td>
      <td><button class="copy-btn" onclick="copyText(this,'${anchor.replace(/'/g,"\\'").replace(/"/g,'\\"')}')">Copy</button></td>
    </tr>`;
  }).join("");
  if (more) more.textContent = data.length > 60 ? `Showing 60 of ${data.length} — download CSV for all` : "";
}
$("rec-search")?.addEventListener("input", filterRecs);

function paintMoneyPages(pages) {
  const tbody = $("money-tbody"); if (!tbody) return;
  if (!pages || !pages.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No money pages detected</td></tr>'; return; }
  const rc = { critical:"var(--red)", high:"var(--amber)", medium:"var(--indigo2)", low:"var(--green)" };
  tbody.innerHTML = pages.map(p => {
    const col = p.protection_score < 30 ? "var(--red)" : p.protection_score < 60 ? "var(--amber)" : "var(--green)";
    return `<tr>
      <td><div style="font-weight:600">${trunc(p.title||slug(p.url), 40)}</div><div class="mono">${trunc(slug(p.url),42)}</div></td>
      <td><span style="font-weight:700;color:${p.inlinks<5?"var(--red)":"var(--green)"}">${p.inlinks}</span></td>
      <td>${p.anchor_diversity} unique</td>
      <td><div style="display:flex;align-items:center;gap:8px"><div style="background:var(--line);border-radius:4px;height:6px;width:90px;overflow:hidden"><div style="height:6px;width:${p.protection_score}%;background:${col};border-radius:4px"></div></div><span class="mono" style="font-size:11px;color:var(--mute)">${p.protection_score}/100</span></div></td>
      <td><span class="badge ${p.risk}">${p.risk}</span></td>
    </tr>`;
  }).join("");
}

let allPairs = [];
function paintCannibalization(pairs) { if (pairs) allPairs = pairs; filterPairs(); }
function filterPairs() {
  const tbody = $("cannibal-tbody"); if (!tbody) return;
  const q = ($("cannibal-search")?.value || "").toLowerCase();
  const data = q ? allPairs.filter(p => slug(p.page_a).includes(q) || slug(p.page_b).includes(q)) : allPairs;
  if (!data.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty-state" style="color:var(--green)">✅ No cannibalization detected</td></tr>'; return; }
  tbody.innerHTML = data.slice(0, 20).map(p => {
    const pct = Math.round(p.overlap_score*100);
    const col = pct>=70?"var(--red)":pct>=55?"var(--amber)":"var(--indigo2)";
    const severity = pct>=70?"critical":pct>=55?"high":"medium";
    return `<tr>
      <td class="mono">${trunc(slug(p.page_a),36)}</td>
      <td class="mono">${trunc(slug(p.page_b),36)}</td>
      <td><span style="font-weight:700;font-size:14px;color:${col}">${pct}%</span></td>
      <td><div style="display:flex;flex-wrap:wrap;gap:3px">${p.shared_keywords.slice(0,5).map(k=>`<span style="font-size:10px;padding:1px 6px;border-radius:4px;background:var(--card2);color:var(--mute)">${k}</span>`).join("")}</div></td>
      <td><span class="badge ${severity}">Consolidate</span></td>
    </tr>`;
  }).join("");
}
$("cannibal-search")?.addEventListener("input", filterPairs);

function paintOpportunities(opps) {
  const tbody = $("opps-tbody"); if (!tbody) return;
  if (!opps || !opps.length) { tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Loading…</td></tr>'; return; }
  tbody.innerHTML = opps.slice(0, 15).map((o, i) => {
    const col = i<3?"var(--red)":i<7?"var(--amber)":"var(--mute)";
    return `<tr>
      <td><div style="font-size:12px;font-weight:500">${trunc(o.title||slug(o.url),42)}</div><div class="mono" style="margin-top:2px">${trunc(slug(o.url),42)}</div></td>
      <td><span style="font-size:18px;font-weight:800;color:${col}">${o.opportunity_score}</span></td>
      <td>${o.crawl_depth}</td><td>${o.inlinks}</td><td>${o.word_count}</td>
      <td><div style="display:flex;flex-wrap:wrap;gap:3px">${(o.top_keywords||[]).slice(0,3).map(k=>`<span style="font-size:10px;padding:1px 5px;border-radius:4px;background:var(--card2);color:var(--mute)">${k}</span>`).join("")}</div></td>
    </tr>`;
  }).join("");
}

function paintThinContent(pages) {
  const tbody = $("thin-tbody"); if (!tbody) return;
  if (!pages || !pages.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty-state" style="color:var(--green)">✅ No thin content detected</td></tr>'; return; }
  tbody.innerHTML = pages.slice(0, 15).map(p => {
    const act = p.word_count < 100 ? "Expand or noindex" : "Expand content";
    return `<tr>
      <td><div style="font-size:12px;font-weight:500">${trunc(p.title||slug(p.url),40)}</div><div class="mono" style="margin-top:2px">${trunc(slug(p.url),40)}</div></td>
      <td><span style="font-weight:700;color:${p.word_count<100?"var(--red)":"var(--amber)"}">${p.word_count}</span></td>
      <td>${p.inlinks}</td><td>${p.crawl_depth}</td>
      <td><span class="badge ${p.word_count<100?"critical":"high"}">${act}</span></td>
    </tr>`;
  }).join("");
}

function paintPRTable(top, bottom) {
  const paintRows = (tbodyId, pages, color) => {
    const tbody = $(tbodyId); if (!tbody) return;
    if (!pages || !pages.length) { tbody.innerHTML = '<tr><td colspan="3" class="empty-state">Loading…</td></tr>'; return; }
    const max = pages[0]?.score || 100;
    tbody.innerHTML = pages.slice(0, 12).map((p, i) => {
      const pct = Math.round((p.score / max) * 100);
      const col = i<3 ? color : "var(--mute)";
      return `<tr>
        <td class="mono">${trunc(slug(p.url),40)}</td>
        <td style="font-weight:700;color:${col}">${p.score}</td>
        <td><div style="background:var(--line);border-radius:3px;height:5px;width:100px;overflow:hidden"><div style="height:5px;width:${pct}%;background:${col};border-radius:3px;transition:width 1s"></div></div></td>
      </tr>`;
    }).join("");
  };
  paintRows("pr-top-tbody", top, "var(--green)");
  paintRows("pr-bottom-tbody", bottom, "var(--red)");
}

function paintRunSummary(RUN) {
  const el = $("run-summary"); if (!el || !RUN.site) return;
  const s = RUN.summary || {};
  el.innerHTML = `
    <div class="stat-row"><span>Site</span><span class="v">${RUN.site}</span></div>
    <div class="stat-row"><span>Pages crawled</span><span class="v">${s.pages_crawled||"—"}</span></div>
    <div class="stat-row"><span>Indexable pages</span><span class="v">${s.indexable_pages||"—"}</span></div>
    <div class="stat-row"><span>Internal links</span><span class="v">${s.internal_links||"—"}</span></div>
    <div class="stat-row"><span>Link health score</span><span class="v" style="color:${GC[RUN.health_grade]||"var(--indigo2)"}">${RUN.health_score||"—"}/100 (${RUN.health_grade||"—"})</span></div>
    <div class="stat-row"><span>Topical clusters</span><span class="v">${s.topical_clusters||"—"}</span></div>
    <div class="stat-row"><span>Link recommendations</span><span class="v">${s.link_recommendations||"—"}</span></div>
    <div class="stat-row"><span>Model</span><span class="v">${RUN.model||"TF-IDF (no model)"}</span></div>
    <div class="stat-row"><span>Model calls</span><span class="v">${RUN.model_calls||0}</span></div>
    <div class="stat-row"><span>Analysis duration</span><span class="v">${RUN.duration_sec||"—"}s</span></div>
  `;
}

// ─── Sidebar status ────────────────────────────────────────────────────────────
function paintSidebar(RUN) {
  const dot = $("sb-dot"), st = $("sb-status"), si = $("sb-site"), ms = $("mobile-status");
  const status = RUN.status || "idle";
  if (dot) dot.className = "dot " + status;
  if (st) st.textContent = status;
  if (si && RUN.site) si.textContent = RUN.site;
  if (ms) { ms.textContent = status; ms.style.background = status === "done" ? "#0a1f10" : status === "running" ? "#0a2010" : "var(--card2)"; }
}

// ─── Master paint ──────────────────────────────────────────────────────────────
function paint(RUN) {
  if (!RUN) return;
  paintSidebar(RUN);
  paintKPIs(RUN);
  if (RUN.health_score != null) paintGauge(RUN.health_score, RUN.health_grade || "B");
  if (RUN.priority_fixes) paintFixList(RUN.priority_fixes);
  if (RUN.graph_stats) {
    paintBroken(RUN.broken_links_detail || []);
    paintOrphans(RUN.orphan_urls, RUN.under_linked_urls);
  }
  if (RUN.anchors) {
    if (RUN.anchor_breakdown) renderAnchorChart(RUN.anchor_breakdown);
    paintGenericAnchors(RUN.generic_anchors_list);
    paintOverAnchors(RUN.over_anchors_list);
  }
  if (RUN.clusters) {
    paintClustersTable(RUN.clusters);
    renderClusterChart(RUN.clusters);
    renderAuthorityChart(RUN.clusters);
    const scat = RUN.clusters.filter(c=>c.authority==="scattered").length;
    animCount($("scattered-count"), scat);
  }
  if (RUN.link_recs) paintRecs(RUN.link_recs);
  const dm = RUN.digital_marketing;
  if (dm) {
    paintMoneyPages(dm.money_pages);
    paintCannibalization(dm.cannibalization);
    paintOpportunities(dm.seo_opportunities);
    paintThinContent(dm.thin_content);
    paintContentGaps(dm.content_gaps);
    paintPRTable(dm.pagerank_top, dm.pagerank_bottom);
    paintKeywordCloud(dm.anchor_keyword_map);
    renderCannibalChart(dm.cannibalization);
    renderOppsChart(dm.seo_opportunities);
    renderPRCharts(dm.pagerank_top, dm.pagerank_bottom);
    renderAnchorKwChart(dm.anchor_keyword_map);
  }
  paintRunSummary(RUN);
}

// ─── Utilities ────────────────────────────────────────────────────────────────
function copyText(btn, text) {
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = "✓ Copied"; btn.classList.add("copied");
    setTimeout(() => { btn.textContent = "Copy"; btn.classList.remove("copied"); }, 1500);
  }).catch(() => { btn.textContent = "—"; });
}

function downloadJson(e) {
  e.preventDefault();
  fetch("/state").then(r=>r.json()).then(d => {
    const blob = new Blob([JSON.stringify(d, null, 2)], { type:"application/json" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = "link-intel-report.json"; a.click();
  });
}

// ─── Live event feed ───────────────────────────────────────────────────────────
function feed(msg, type) {
  const f = $("feed"); if (!f) return;
  f.querySelector(".empty-state")?.remove();
  const item = document.createElement("div");
  item.className = "feed-item";
  const colors = { ok:"var(--green)", warn:"var(--amber)", err:"var(--red)", info:"var(--indigo2)" };
  item.innerHTML = `<span class="feed-time">${new Date().toLocaleTimeString()}</span><span style="color:${colors[type]||"var(--mute)"}">${msg}</span>`;
  f.prepend(item);
  while (f.children.length > 100) f.removeChild(f.lastChild);
}

// ─── SSE / polling ────────────────────────────────────────────────────────────
let RUN = {};

function _refreshState(cb) {
  fetch("/state").then(r=>r.json()).then(s=>{ Object.assign(RUN, s); paint(RUN); if(cb) cb(); }).catch(()=>{});
}

function onEvent({ event, data }) {
  const msg = data?.message || "";
  switch(event) {

    case "snapshot":
      RUN = data || {};
      paint(RUN);
      if (RUN.site) feed("snapshot loaded · " + (RUN.site || ""), "ok");
      else feed("connected — waiting for analysis", "info");
      break;

    case "crawl_progress":
      feed(msg || "crawling…", "info");
      const bar = $("prog-bar");
      if (bar && data?.pct != null) bar.style.width = data.pct + "%";
      break;

    case "loaded":
      // data may be full object (run.py path) or just {message} (crawl/upload path)
      if (data?.site) Object.assign(RUN, { site: data.site, urls: data.urls });
      feed(msg || `loaded ${data?.urls || "?"} pages`, "ok");
      _refreshState();
      break;

    case "graph":
      feed(msg || (data?.orphan_pages != null
        ? `graph: ${data.orphan_pages} orphans · ${data.broken_internal_links} broken`
        : "graph built"), "warn");
      _refreshState();
      break;

    case "anchors":
      feed(msg || (data?.generic != null
        ? `anchors: ${data.generic} generic · ${data.empty_or_image_only} empty`
        : "anchors analysed"), "warn");
      _refreshState();
      break;

    case "topics":
      feed(msg || (data?.clusters?.length != null
        ? `topics: ${data.clusters.length} clusters`
        : "clusters built"), "ok");
      _refreshState();
      break;

    case "entities":
      feed(msg || `entities: ${data?.pages_with_entities ?? "?"} pages`, "info");
      break;

    // server emits "recs" from crawl/upload path
    case "recs":
    case "recommendations":
      feed(msg || `${data?.count ?? "?"} link suggestions`, "ok");
      _refreshState(() => { paintRecs(RUN.link_recs); });
      break;

    // server emits "report" from crawl/upload, "report_ready" from run.py path
    case "report":
    case "report_ready":
      feed(msg || (data?.score != null
        ? `report ready · score ${data.score}/100 (${data.grade})`
        : "report written"), "ok");
      _refreshState();
      break;

    // server emits "done" from crawl/upload, "saved" from run.py path
    case "done":
    case "saved":
      feed(msg || "✅ analysis complete", "ok");
      _refreshState();
      break;

    case "exported": feed("✅ report.html exported", "ok"); break;

    case "error":
      feed("❌ " + (msg || "unknown error"), "err");
      break;
  }
  paintKPIs(RUN);
}

function connect() {
  try {
    const es = new EventSource("/events");
    es.onmessage = m => { try{ onEvent(JSON.parse(m.data)); } catch(e){} };
    es.onerror = () => { es.close(); setTimeout(poll, 2000); };
  } catch(e) { poll(); }
}
function poll() {
  fetch("/state").then(r=>r.json()).then(d=>{ RUN=d; paint(RUN); }).catch(()=>{});
  setTimeout(poll, 5000);
}

// ─── Notion Integration ───────────────────────────────────────────────────────
let _notionCfg = { token: "", page_id: "" };

function notionTokenChanged() {
  const t = ($("notion-token") || {}).value || "";
  $("notion-status").textContent = t ? "" : "";
}

function notionSetConnected(name) {
  $("notion-connected").style.display = "block";
  $("notion-setup").style.display = "none";
  $("notion-workspace").textContent = "Integration: " + name;
  notionShowExportRow();
}

function notionShowExportRow() {
  const row = $("notion-export-row");
  if (!row) return;
  row.style.display = (_notionCfg.token && _notionCfg.page_id && RUN.site) ? "flex" : "none";
}

async function notionVerify() {
  const token   = ($("notion-token")   || {}).value?.trim() || "";
  const page_id = ($("notion-page-id") || {}).value?.trim().replace(/-/g,"") || "";
  if (!token || !page_id) {
    $("notion-status").textContent = "⚠️ Enter both token and page ID";
    $("notion-status").style.color = "var(--amber)";
    return;
  }
  $("notion-status").textContent = "Verifying…";
  $("notion-status").style.color = "var(--mute)";
  try {
    const r = await fetch("/notion/verify", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ token })
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error);
    _notionCfg = { token, page_id };
    await fetch("/notion/save-config", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ token, page_id })
    });
    notionSetConnected(j.name || "Notion workspace");
    $("notion-status").textContent = "";
  } catch(e) {
    $("notion-status").textContent = "❌ " + (e.message || "Connection failed");
    $("notion-status").style.color = "var(--red)";
  }
}

function notionDisconnect() {
  _notionCfg = { token:"", page_id:"" };
  fetch("/notion/save-config", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ token:"", page_id:"" })
  });
  $("notion-connected").style.display = "none";
  $("notion-setup").style.display = "block";
  $("notion-token").value = "";
  $("notion-page-id").value = "";
  $("notion-export-row").style.display = "none";
}

async function notionExport() {
  if (!_notionCfg.token || !_notionCfg.page_id) return;
  const btn = $("btn-notion-export");
  const status = $("notion-export-status");
  btn.disabled = true; btn.textContent = "Exporting…";
  status.textContent = ""; status.style.color = "var(--mute)";
  try {
    const r = await fetch("/notion/export", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ token: _notionCfg.token, page_id: _notionCfg.page_id })
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error);
    status.innerHTML = `✅ Report created — <a href="${j.url}" target="_blank" style="color:var(--indigo)">Open in Notion ↗</a>`;
    status.style.color = "var(--green)";
  } catch(e) {
    status.textContent = "❌ " + (e.message || "Export failed");
    status.style.color = "var(--red)";
  } finally {
    btn.disabled = false; btn.textContent = "⚡ Export to Notion";
  }
}

// load saved config on page load
fetch("/notion/config").then(r=>r.json()).then(cfg => {
  if (cfg.token && cfg.page_id) {
    _notionCfg = cfg;
    if ($("notion-token"))   $("notion-token").value   = cfg.token;
    if ($("notion-page-id")) $("notion-page-id").value = cfg.page_id;
    fetch("/notion/verify", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ token: cfg.token })
    }).then(r=>r.json()).then(j => {
      if (j.ok) notionSetConnected(j.name || "Notion workspace");
    }).catch(()=>{});
  }
}).catch(()=>{});

// ─── Slack integration ────────────────────────────────────────────────────────
let _slackCfg = { webhook: "" };

async function slackSave() {
  const webhook = ($("slack-webhook") || {}).value?.trim() || "";
  if (!webhook.startsWith("https://hooks.slack.com/")) {
    $("slack-status").textContent = "⚠️ Must be a hooks.slack.com URL";
    $("slack-status").style.color = "var(--amber)";
    return;
  }
  $("slack-status").textContent = "Connecting…";
  $("slack-status").style.color = "var(--mute)";
  try {
    const r = await fetch("/slack/test", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ webhook })
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || "Test message failed");
    await fetch("/slack/save", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ webhook })
    });
    _slackCfg = { webhook };
    slackSetConnected();
    $("slack-status").textContent = "";
  } catch(e) {
    $("slack-status").textContent = "❌ " + (e.message || "Connection failed");
    $("slack-status").style.color = "var(--red)";
  }
}

function slackSetConnected() {
  $("slack-connected").style.display = "block";
  $("slack-setup").style.display = "none";
  $("slack-test-row").style.display = "flex";
}

async function slackTest() {
  const btn = $("btn-slack-test");
  const status = $("slack-test-status");
  btn.disabled = true; btn.textContent = "Sending…";
  status.textContent = "";
  try {
    const r = await fetch("/slack/test", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ webhook: _slackCfg.webhook })
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || "Failed");
    status.textContent = "✅ Test message sent!";
    status.style.color = "var(--green)";
  } catch(e) {
    status.textContent = "❌ " + (e.message || "Failed");
    status.style.color = "var(--red)";
  } finally {
    btn.disabled = false; btn.textContent = "Send Test Message";
  }
}

function slackDisconnect() {
  _slackCfg = { webhook: "" };
  fetch("/slack/save", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ webhook: "" })
  });
  $("slack-connected").style.display = "none";
  $("slack-setup").style.display = "block";
  $("slack-test-row").style.display = "none";
  if ($("slack-webhook")) $("slack-webhook").value = "";
}

// load saved slack config on page load
fetch("/slack/config").then(r=>r.json()).then(cfg => {
  if (cfg.webhook) {
    _slackCfg = cfg;
    if ($("slack-webhook")) $("slack-webhook").value = cfg.webhook;
    slackSetConnected();
  }
}).catch(()=>{});

// ─── Health Score History ──────────────────────────────────────────────────────
function renderHistoryChart(runs) {
  const el = $("history-chart");
  if (!el || !runs || runs.length < 2) return;
  const labels = runs.map(r => r.date.slice(5, 16));
  const scores = runs.map(r => r.score);
  mkChart("history-chart", {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Health Score",
        data: scores,
        borderColor: "#6366F1",
        backgroundColor: "rgba(99,102,241,0.12)",
        borderWidth: 2.5,
        pointRadius: 4,
        pointBackgroundColor: "#6366F1",
        tension: 0.35,
        fill: true
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: {
        callbacks: { label: ctx => ` Score: ${ctx.parsed.y}` }
      }},
      scales: {
        x: { ticks: { color: "#94A3B8", font: { size: 11 }, maxRotation: 45 }, grid: { color: "rgba(255,255,255,.05)" }},
        y: { min: 0, max: 100, ticks: { color: "#94A3B8", font: { size: 11 } }, grid: { color: "rgba(255,255,255,.05)" }}
      }
    }
  });
}

fetch("/history").then(r=>r.json()).then(data => {
  const runs = (data.runs || []).slice(-20);
  if (!runs.length) return;
  // inject history card into overview page if not already present
  const overview = $("page-overview");
  if (!overview || $("history-card")) return;
  const card = document.createElement("div");
  card.id = "history-card";
  card.innerHTML = `
    <div class="section-title" style="margin-top:28px">Health Score History</div>
    <div class="card" style="padding:20px 24px">
      <div style="height:200px;position:relative"><canvas id="history-chart"></canvas></div>
      <div id="history-runs" style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap"></div>
    </div>`;
  overview.appendChild(card);
  setTimeout(() => {
    renderHistoryChart(runs);
    const runsEl = $("history-runs");
    if (runsEl) runs.slice(-5).reverse().forEach(r => {
      const chip = document.createElement("div");
      chip.style.cssText = "font-size:11px;padding:4px 10px;border-radius:20px;background:var(--card2);color:var(--text2);display:flex;gap:6px;align-items:center";
      const grade = GC[r.grade] || "var(--indigo2)";
      chip.innerHTML = `<span style="font-weight:700;color:${grade}">${r.grade}</span><span>${r.score}</span><span style="color:var(--mute)">${r.date.slice(0,10)}</span>`;
      runsEl.appendChild(chip);
    });
  }, 50);
}).catch(()=>{});

// ─── Bootstrap ────────────────────────────────────────────────────────────────
const startPage = location.hash.slice(1) || "overview";
if (startPage !== "overview") nav(startPage);
connect();
