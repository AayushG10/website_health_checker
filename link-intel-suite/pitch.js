const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "Link Intel Suite — Pitch Deck";

// ── Palette ──────────────────────────────────────────────────────────────────
const C = {
  dark:    "060A14",
  navy:    "0C1120",
  navy2:   "111827",
  indigo:  "6366F1",
  indigo2: "818CF8",
  indigo3: "3730A3",
  green:   "10B981",
  amber:   "F59E0B",
  red:     "EF4444",
  white:   "F1F5F9",
  mute:    "94A3B8",
  line:    "1E2A3A",
};

// ── Helpers ───────────────────────────────────────────────────────────────────
const makeShadow = () => ({ type: "outer", blur: 14, offset: 4, angle: 135, color: "000000", opacity: 0.3 });

function card(slide, x, y, w, h) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: C.navy },
    line: { color: C.line, pt: 1 },
    shadow: makeShadow(),
  });
}

function accentLine(slide, x, y, h) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 0.07, h,
    fill: { color: C.indigo },
    line: { color: C.indigo, pt: 0 },
  });
}

function pill(slide, label, x, y, w, color) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h: 0.3,
    fill: { color: color || C.indigo, transparency: 80 },
    line: { color: color || C.indigo, pt: 1 },
    rectRadius: 0.04,
  });
  slide.addText(label, {
    x, y, w, h: 0.3,
    fontSize: 9, color: color || C.indigo2, bold: true, align: "center", valign: "middle", margin: 0,
  });
}

function statBox(slide, num, label, x, y, color) {
  card(slide, x, y, 2.1, 1.1);
  slide.addText(num, {
    x, y: y + 0.08, w: 2.1, h: 0.6,
    fontSize: 34, fontFace: "Arial Black", color: color || C.indigo2,
    bold: true, align: "center", margin: 0,
  });
  slide.addText(label, {
    x, y: y + 0.68, w: 2.1, h: 0.32,
    fontSize: 10, color: C.mute, align: "center", margin: 0,
  });
}

function featureCard(slide, icon, title, desc, x, y, w, h) {
  card(slide, x, y, w, h);
  accentLine(slide, x, y + 0.18, h - 0.36);
  slide.addText(icon, { x: x + 0.18, y: y + 0.17, w: 0.4, h: 0.4, fontSize: 18, margin: 0 });
  slide.addText(title, {
    x: x + 0.62, y: y + 0.17, w: w - 0.72, h: 0.35,
    fontSize: 13, color: C.white, bold: true, margin: 0,
  });
  slide.addText(desc, {
    x: x + 0.18, y: y + 0.58, w: w - 0.28, h: h - 0.7,
    fontSize: 10.5, color: C.mute, margin: 0, paraSpaceAfter: 2,
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// SLIDE 1 — TITLE
// ─────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.dark };

  // Glow blob behind logo area
  s.addShape(pres.shapes.OVAL, {
    x: 3.8, y: 0.5, w: 4.5, h: 4.5,
    fill: { color: C.indigo3, transparency: 82 },
    line: { color: C.indigo3, pt: 0 },
  });

  // Top badge
  pill(s, "🏆  HACKATHON PROJECT", 3.5, 0.4, 3, C.indigo);

  // Main title
  s.addText("Link Intel Suite", {
    x: 1, y: 1.1, w: 8, h: 1.3,
    fontSize: 54, fontFace: "Arial Black", color: C.white,
    bold: true, align: "center", margin: 0,
  });

  // Gradient-look subtitle line (indigo → lighter)
  s.addShape(pres.shapes.RECTANGLE, {
    x: 3.5, y: 2.4, w: 3, h: 0.05,
    fill: { color: C.indigo },
    line: { color: C.indigo, pt: 0 },
  });

  s.addText("Internal Linking Intelligence, Powered by AI Agents", {
    x: 0.8, y: 2.55, w: 8.4, h: 0.55,
    fontSize: 18, color: C.indigo2, align: "center", margin: 0,
  });

  s.addText("Drop in a Screaming Frog export or enter a URL → get a complete health score,\ntopical clusters, orphan pages, PageRank analysis & contextual link recommendations.", {
    x: 1.2, y: 3.2, w: 7.6, h: 0.9,
    fontSize: 13.5, color: C.mute, align: "center", margin: 0, paraSpaceAfter: 4,
  });

  // Bottom stat pills
  const stats = [["5 AI Agents", C.indigo], ["< 60s Analysis", C.green], ["100% Local", C.amber], ["Notion Export", C.indigo2]];
  stats.forEach(([t, c], i) => pill(s, t, 1.2 + i * 1.95, 4.55, 1.7, c));
}

// ─────────────────────────────────────────────────────────────────────────────
// SLIDE 2 — THE PROBLEM
// ─────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.dark };

  pill(s, "THE PROBLEM", 0.5, 0.3, 1.6, C.red);
  s.addText("Internal linking is broken\nfor most websites", {
    x: 0.5, y: 0.65, w: 5, h: 1.3,
    fontSize: 32, fontFace: "Arial Black", color: C.white, bold: true, margin: 0, paraSpaceAfter: 6,
  });
  s.addText("SEO teams waste hours in spreadsheets trying to manually\nanalyse link graphs that should be automated.", {
    x: 0.5, y: 1.98, w: 4.7, h: 0.8,
    fontSize: 13, color: C.mute, margin: 0,
  });

  const problems = [
    ["🔴", "Orphan pages get zero link equity — invisible to Google"],
    ["🟡", "Generic anchors ('click here') dilute topical authority"],
    ["🔴", "Broken internal links silently destroy crawl budget"],
    ["🟡", "Keyword cannibalization tanks rankings without warning"],
    ["🔴", "No visibility into PageRank flow across the site"],
  ];
  problems.forEach(([icon, text], i) => {
    const y = 2.88 + i * 0.5;
    s.addText(icon, { x: 0.5, y, w: 0.35, h: 0.38, fontSize: 14, margin: 0 });
    s.addText(text, { x: 0.92, y, w: 4.3, h: 0.38, fontSize: 12.5, color: C.white, margin: 0 });
  });

  // Right side — big pain stats
  card(s, 5.6, 0.55, 4.0, 4.7);
  s.addText("The real cost", {
    x: 5.8, y: 0.75, w: 3.6, h: 0.4,
    fontSize: 13, color: C.mute, bold: true, charSpacing: 3, margin: 0,
  });

  const painStats = [
    ["68%", "of pages have\nzero internal links", C.red],
    ["3–5h", "wasted per audit\non manual analysis", C.amber],
    ["40%", "SEO impact from\ninternal link structure", C.indigo2],
  ];
  painStats.forEach(([num, label, color], i) => {
    const y = 1.35 + i * 1.4;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 5.75, y, w: 3.7, h: 1.18,
      fill: { color: C.navy2 }, line: { color: C.line, pt: 1 },
    });
    s.addText(num, {
      x: 5.75, y: y + 0.08, w: 3.7, h: 0.58,
      fontSize: 40, fontFace: "Arial Black", color, bold: true, align: "center", margin: 0,
    });
    s.addText(label, {
      x: 5.75, y: y + 0.65, w: 3.7, h: 0.45,
      fontSize: 11, color: C.mute, align: "center", margin: 0,
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// SLIDE 3 — THE SOLUTION
// ─────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.dark };

  pill(s, "THE SOLUTION", 0.5, 0.3, 1.8, C.green);
  s.addText("One tool. Complete\ninternal link intelligence.", {
    x: 0.5, y: 0.65, w: 9, h: 1.2,
    fontSize: 36, fontFace: "Arial Black", color: C.white, bold: true, margin: 0,
  });

  const solutions = [
    ["🕷", "Built-in Crawler", "Just enter a URL. No Screaming Frog needed."],
    ["📊", "Health Score", "0–100 grade with weighted breakdown of every issue."],
    ["🧠", "AI Agents", "5 specialised agents run sequentially in under 60 seconds."],
    ["🔗", "Link Recs", "Contextual suggestions: which page should link to which, and what anchor to use."],
    ["📤", "Notion Export", "Push a fully structured report to your Notion workspace in one click."],
    ["💬", "Slack Alerts", "Get notified after every run with score, grade, and key stats."],
  ];

  solutions.forEach(([icon, title, desc], i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    featureCard(s, icon, title, desc, 0.4 + col * 4.7, 1.95 + row * 1.12, 4.5, 1.0);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// SLIDE 4 — THE 5 AGENTS PIPELINE
// ─────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.dark };

  pill(s, "HOW IT WORKS", 0.5, 0.3, 1.8, C.indigo);
  s.addText("5 AI Agents. One Pipeline.", {
    x: 0.5, y: 0.62, w: 9, h: 0.7,
    fontSize: 34, fontFace: "Arial Black", color: C.white, bold: true, margin: 0,
  });
  s.addText("Each agent is a specialised Python function. They run sequentially, each feeding results to the next.", {
    x: 0.5, y: 1.35, w: 9, h: 0.4,
    fontSize: 12.5, color: C.mute, margin: 0,
  });

  const agents = [
    { num: "01", name: "Graph Agent", icon: "🕸", desc: "Builds the full internal link graph using NetworkX. Detects orphans, calculates PageRank, finds broken links and redirect chains.", color: C.indigo },
    { num: "02", name: "Anchor Agent", icon: "⚓", desc: "Classifies every anchor text as descriptive, generic, empty, or over-optimised. Flags diversity issues per destination page.", color: C.indigo2 },
    { num: "03", name: "Topic Agent", icon: "🗂", desc: "Clusters pages by TF-IDF cosine similarity into topical silos. Labels each cluster and identifies hub vs. scattered pages.", color: C.green },
    { num: "04", name: "Entity Agent", icon: "🔬", desc: "Optionally calls Claude API to extract named entities and compute semantic relatedness between pages — enables smarter link suggestions.", color: C.amber },
    { num: "05", name: "Reporter", icon: "📋", desc: "Computes the 0–100 health score, generates priority fix queue, writes report.json & report.html, pushes to Notion, and notifies Slack.", color: C.indigo },
  ];

  agents.forEach((a, i) => {
    const x = 0.4 + i * 1.87;
    // Card
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.88, w: 1.78, h: 3.35,
      fill: { color: C.navy }, line: { color: C.line, pt: 1 },
      shadow: makeShadow(),
    });
    // Top color bar
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.88, w: 1.78, h: 0.06,
      fill: { color: a.color }, line: { color: a.color, pt: 0 },
    });
    // Number
    s.addText(a.num, {
      x, y: 2.02, w: 1.78, h: 0.32,
      fontSize: 11, color: a.color, bold: true, align: "center", charSpacing: 2, margin: 0,
    });
    // Icon
    s.addText(a.icon, {
      x, y: 2.34, w: 1.78, h: 0.45,
      fontSize: 22, align: "center", margin: 0,
    });
    // Name
    s.addText(a.name, {
      x: x + 0.08, y: 2.82, w: 1.62, h: 0.42,
      fontSize: 11.5, color: C.white, bold: true, align: "center", margin: 0,
    });
    // Description
    s.addText(a.desc, {
      x: x + 0.1, y: 3.28, w: 1.58, h: 1.82,
      fontSize: 9, color: C.mute, align: "left", margin: 0, paraSpaceAfter: 3,
    });

    // Arrow between cards
    if (i < 4) {
      s.addShape(pres.shapes.RECTANGLE, {
        x: x + 1.78, y: 3.48, w: 0.09, h: 0.09,
        fill: { color: C.indigo }, line: { color: C.indigo, pt: 0 },
      });
    }
  });

  // Bottom flow label
  s.addText("Upload CSV  ──────────────────────────────────────────────────────────────────────────────  Notion / Slack / Dashboard", {
    x: 0.4, y: 5.3, w: 9.2, h: 0.22,
    fontSize: 9, color: C.mute, align: "center", margin: 0,
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// SLIDE 5 — ALL FEATURES
// ─────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.dark };

  pill(s, "FEATURES", 0.5, 0.28, 1.3, C.indigo);
  s.addText("Everything in one tool", {
    x: 0.5, y: 0.62, w: 9, h: 0.65,
    fontSize: 34, fontFace: "Arial Black", color: C.white, bold: true, margin: 0,
  });

  // 12 features in a 3×4 grid — fits within slide height
  const features = [
    ["🕷 Built-in Crawler", "Enter any URL — crawls up to 200 pages, robots.txt compliant. No extra tools needed."],
    ["📂 CSV Upload", "Drag & drop Screaming Frog exports for instant analysis on sites of any size."],
    ["📊 Health Score 0–100", "Weighted across 6 dimensions: broken links, orphans, anchors, PageRank, clusters, depth."],
    ["🏷 Orphan Detection", "Finds zero-inlink pages invisible to Google, suggests which pages should link to them."],
    ["⚓ Anchor Analysis", "Classifies every anchor (generic, empty, over-optimised, descriptive) per destination."],
    ["🗂 Topic Clusters", "TF-IDF cosine similarity silos pages. Labels hubs vs. scattered with authority scores."],
    ["📈 PageRank Flow", "Simulates Google's PageRank — shows which pages gain or are starved of link equity."],
    ["🔗 Link Recommendations", "Per-page suggestions with source, target, anchor text, and the reason why."],
    ["⚠ Cannibalization", "Detects pages competing for the same keywords via title/H1 and anchor overlap."],
    ["📤 Notion Export", "One-click: pushes a fully structured report — score, fix checklist, recs, clusters."],
    ["💬 Slack Alerts", "Webhook sends grade, score, and key stats to your channel after every run."],
    ["📉 History & Trends", "Auto-saves 50 runs. Dashboard sparkline shows how your score changes over time."],
  ];

  features.forEach((f, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.4 + col * 3.1;
    const y = 1.35 + row * 1.06;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 2.96, h: 0.98,
      fill: { color: C.navy }, line: { color: C.line, pt: 1 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 0.05, h: 0.98,
      fill: { color: C.indigo }, line: { color: C.indigo, pt: 0 },
    });
    s.addText(f[0], {
      x: x + 0.12, y: y + 0.07, w: 2.8, h: 0.3,
      fontSize: 11, color: C.white, bold: true, margin: 0,
    });
    s.addText(f[1], {
      x: x + 0.12, y: y + 0.38, w: 2.8, h: 0.52,
      fontSize: 9.5, color: C.mute, margin: 0, paraSpaceAfter: 1,
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// SLIDE 6 — DEMO WALKTHROUGH
// ─────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.dark };

  pill(s, "LIVE DEMO", 0.5, 0.22, 1.5, C.green);
  s.addText("Demo walkthrough", {
    x: 0.5, y: 0.58, w: 5.2, h: 0.55,
    fontSize: 30, fontFace: "Arial Black", color: C.white, bold: true, margin: 0,
  });
  s.addText("Follow this order — each step builds on the previous one.", {
    x: 0.5, y: 1.18, w: 5, h: 0.28,
    fontSize: 11.5, color: C.mute, margin: 0,
  });

  const steps = [
    { n: "1", title: "Open the Landing Page", desc: "localhost:7700/landing.html — show agent explainer & Notion section.", time: "30s", color: C.indigo },
    { n: "2", title: "Enter a URL to Crawl", desc: "Crawl tab → enter domain → hit Analyse. Show live SSE feed.", time: "60s", color: C.indigo2 },
    { n: "3", title: "Walk the Dashboard", desc: "Health Score gauge → Graph (orphans/broken) → Anchors → Clusters.", time: "90s", color: C.green },
    { n: "4", title: "Open Recommendations", desc: "Link Recs page — source, target, anchor text, reason per page.", time: "30s", color: C.amber },
    { n: "5", title: "Export to Notion", desc: "Reports → Notion card → Export. Switch tab to show live result.", time: "30s", color: C.indigo },
    { n: "6", title: "Show History Chart", desc: "Overview → History sparkline. Score trend across runs.", time: "20s", color: C.green },
  ];

  steps.forEach((st, i) => {
    const y = 1.55 + i * 0.67;
    s.addShape(pres.shapes.OVAL, {
      x: 0.4, y: y + 0.04, w: 0.38, h: 0.38,
      fill: { color: st.color, transparency: 75 },
      line: { color: st.color, pt: 1 },
    });
    s.addText(st.n, {
      x: 0.4, y: y + 0.04, w: 0.38, h: 0.38,
      fontSize: 11, color: st.color, bold: true, align: "center", valign: "middle", margin: 0,
    });
    s.addText(st.title, {
      x: 0.88, y: y + 0.02, w: 3.4, h: 0.26,
      fontSize: 12, color: C.white, bold: true, margin: 0,
    });
    s.addText(st.desc, {
      x: 0.88, y: y + 0.28, w: 3.4, h: 0.32,
      fontSize: 9.5, color: C.mute, margin: 0,
    });
    pill(s, "⏱ " + st.time, 4.38, y + 0.08, 0.82, st.color);
  });

  // Right side — talking points box
  card(s, 5.5, 0.55, 4.1, 4.85);
  s.addText("KEY TALKING POINTS", {
    x: 5.65, y: 0.72, w: 3.8, h: 0.28,
    fontSize: 10, color: C.mute, bold: true, charSpacing: 2, margin: 0,
  });

  const points = [
    ["🏗", "Built entirely with Python stdlib + Claude API — no paid crawl tools"],
    ["⚡", "Full analysis in under 60 seconds for a 200-page site"],
    ["🔒", "100% local — your data never leaves your machine"],
    ["🤖", "5 agents each do one job well: graph → anchor → topic → entity → report"],
    ["📊", "Health score is objective & reproducible — not a black box"],
    ["🔌", "Plugs directly into existing workflows: Notion + Slack"],
    ["📈", "Trend tracking: watch your score improve as you fix issues"],
    ["🌐", "Works on any site — no Screaming Frog licence required"],
  ];
  points.forEach(([icon, text], i) => {
    const y = 1.1 + i * 0.47;
    s.addText(icon, { x: 5.65, y, w: 0.35, h: 0.38, fontSize: 14, margin: 0 });
    s.addText(text, { x: 6.05, y, w: 3.4, h: 0.38, fontSize: 10.5, color: C.mute, margin: 0 });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// SLIDE 7 — COMPARISON
// ─────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.dark };

  pill(s, "COMPARISON", 0.5, 0.28, 1.6, C.amber);
  s.addText("Why not just use\nexisting tools?", {
    x: 0.5, y: 0.62, w: 9, h: 1.1,
    fontSize: 34, fontFace: "Arial Black", color: C.white, bold: true, margin: 0,
  });

  const headers = ["Feature", "Link Intel Suite", "Screaming Frog", "Ahrefs / Semrush", "Custom Script"];
  const rows = [
    ["Built-in crawler",          "✓ Zero setup",    "✗ Separate app",   "✗",             "✗"],
    ["Topical cluster detection", "✓ AI-powered",    "✗",                "~ Basic",        "✗"],
    ["PageRank simulation",       "✓ Full graph",    "✗",                "✗",              "~ DIY"],
    ["Contextual link recs",      "✓ Per page",      "✗",                "~ Generic",      "✗"],
    ["Notion export",             "✓ One click",     "✗",                "✗",              "✗"],
    ["Health score history",      "✓ Auto-tracked",  "✗",                "~ Paid only",    "✗"],
    ["Runs locally / free",       "✓ Fully local",   "~ £149/yr",        "✗ Subscription", "✓"],
    ["Setup time",                "< 2 minutes",     "30–60 min",        "Hours",          "Days"],
  ];

  // Header row
  const colW = [2.2, 1.8, 1.8, 1.8, 1.8];
  const tableX = 0.5;
  let tableY = 1.85;

  // Draw header
  s.addShape(pres.shapes.RECTANGLE, {
    x: tableX, y: tableY, w: 9.3, h: 0.4,
    fill: { color: C.indigo3 }, line: { color: C.indigo3, pt: 0 },
  });
  let cx = tableX;
  headers.forEach((h, i) => {
    s.addText(h, {
      x: cx + 0.1, y: tableY + 0.02, w: colW[i] - 0.1, h: 0.38,
      fontSize: 10.5, color: C.white, bold: true, valign: "middle", margin: 0,
    });
    cx += colW[i];
  });

  // Draw rows
  rows.forEach((row, ri) => {
    const y = tableY + 0.4 + ri * 0.42;
    s.addShape(pres.shapes.RECTANGLE, {
      x: tableX, y, w: 9.3, h: 0.42,
      fill: { color: ri % 2 === 0 ? C.navy : C.navy2 },
      line: { color: C.line, pt: 0.5 },
    });
    let cx2 = tableX;
    row.forEach((cell, ci) => {
      const isGood = cell.startsWith("✓");
      const isBad  = cell === "✗";
      const color  = ci === 0 ? C.white : isGood ? C.green : isBad ? "334155" : C.amber;
      s.addText(cell, {
        x: cx2 + 0.1, y, w: colW[ci] - 0.1, h: 0.42,
        fontSize: ci === 0 ? 11 : 10, color,
        bold: ci === 0 || isGood, valign: "middle", margin: 0,
      });
      cx2 += colW[ci];
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// SLIDE 8 — TECH STACK
// ─────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.dark };

  pill(s, "TECH STACK", 0.5, 0.28, 1.6, C.indigo);
  s.addText("Built with the\nright tools", {
    x: 0.5, y: 0.62, w: 5, h: 1.1,
    fontSize: 34, fontFace: "Arial Black", color: C.white, bold: true, margin: 0,
  });

  const stack = [
    { cat: "Backend", items: ["Python 3 stdlib only — no frameworks", "ThreadingHTTPServer + SSE for live dashboard", "BFS web crawler (urllib + html.parser)", "NetworkX for link graph & PageRank"] },
    { cat: "AI / Analysis", items: ["Claude API (claude-sonnet-4-6) for entity extraction", "TF-IDF cosine similarity for topical clusters", "Custom health scoring algorithm", "Anchor text classification logic"] },
    { cat: "Frontend", items: ["Vanilla JS SPA with hash routing", "Chart.js for data visualisation", "Server-Sent Events for live progress", "Dark theme with CSS custom properties"] },
    { cat: "Integrations", items: ["Notion REST API v2022-06-28 (urllib)", "Slack Incoming Webhooks", "Screaming Frog CSV import", "JSON-based history persistence"] },
  ];

  stack.forEach((sec, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.4 + col * 4.7;
    const y = 1.82 + row * 1.85;
    card(s, x, y, 4.5, 1.72);
    accentLine(s, x, y + 0.15, 1.42);
    s.addText(sec.cat.toUpperCase(), {
      x: x + 0.2, y: y + 0.12, w: 4.2, h: 0.3,
      fontSize: 11, color: C.indigo2, bold: true, charSpacing: 2, margin: 0,
    });
    sec.items.forEach((item, ii) => {
      s.addText("·  " + item, {
        x: x + 0.2, y: y + 0.48 + ii * 0.29, w: 4.2, h: 0.28,
        fontSize: 10.5, color: C.mute, margin: 0,
      });
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// SLIDE 9 — RESULTS / IMPACT
// ─────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.dark };

  pill(s, "IMPACT", 0.5, 0.28, 1.3, C.green);
  s.addText("What you get\nafter one run", {
    x: 0.5, y: 0.62, w: 9, h: 1.1,
    fontSize: 34, fontFace: "Arial Black", color: C.white, bold: true, margin: 0,
  });

  // Big stats row
  statBox(s, "0–100", "Health Score", 0.4, 1.88, C.indigo2);
  statBox(s, "< 60s", "Full analysis", 2.65, 1.88, C.green);
  statBox(s, "50+", "Run history saved", 4.9, 1.88, C.amber);
  statBox(s, "5", "AI Agents", 7.15, 1.88, C.indigo2);

  // Output checklist
  s.addText("WHAT THE REPORT INCLUDES", {
    x: 0.4, y: 3.2, w: 9, h: 0.3,
    fontSize: 10, color: C.mute, bold: true, charSpacing: 2, margin: 0,
  });

  const outputs = [
    ["✅", "Priority fix queue — ranked by severity with page-level detail"],
    ["✅", "Broken internal links list with source, destination & status"],
    ["✅", "Orphan pages with suggested linking pages"],
    ["✅", "Anchor text breakdown — generic, empty, over-optimised per page"],
    ["✅", "Topical cluster map — hub pages, scattered pages, gaps"],
    ["✅", "PageRank top 10 / bottom 10 with protection scores"],
    ["✅", "Contextual link recommendations with suggested anchors & reasoning"],
    ["✅", "Notion page + Slack notification — ready to share with the team"],
  ];

  outputs.forEach(([icon, text], i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.4 + col * 4.8;
    const y = 3.6 + row * 0.46;
    s.addText(icon, { x, y, w: 0.3, h: 0.38, fontSize: 13, margin: 0 });
    s.addText(text, { x: x + 0.35, y, w: 4.3, h: 0.38, fontSize: 10.5, color: C.mute, margin: 0 });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// SLIDE 10 — CTA / CLOSE
// ─────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.dark };

  // Glow
  s.addShape(pres.shapes.OVAL, {
    x: 2, y: 0.5, w: 6, h: 5,
    fill: { color: C.indigo3, transparency: 85 },
    line: { color: C.indigo3, pt: 0 },
  });

  s.addText("Try it now.", {
    x: 0.5, y: 1.0, w: 9, h: 1.2,
    fontSize: 60, fontFace: "Arial Black", color: C.white, bold: true, align: "center", margin: 0,
  });
  s.addText("localhost:7700", {
    x: 0.5, y: 2.22, w: 9, h: 0.65,
    fontSize: 28, color: C.indigo2, align: "center", margin: 0,
  });
  s.addText("Drop in any URL or Screaming Frog export and run a complete\ninternal link audit in under 60 seconds.", {
    x: 1, y: 3.0, w: 8, h: 0.75,
    fontSize: 14, color: C.mute, align: "center", margin: 0,
  });

  const ctaItems = ["🕷  No Screaming Frog required", "📤  Push to Notion in one click", "💬  Slack alerts out of the box", "📊  Health score + trend tracking"];
  ctaItems.forEach((t, i) => pill(s, t, 0.85 + i * 2.1, 3.9, 2.0, i % 2 === 0 ? C.indigo : C.green));

  s.addText("Built for the Hackathon · Link Intel Suite · github.com/aayush", {
    x: 0.5, y: 5.08, w: 9, h: 0.3,
    fontSize: 10, color: C.mute, align: "center", margin: 0,
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// WRITE
// ─────────────────────────────────────────────────────────────────────────────
const outPath = "/Users/aayush/Desktop/untitled folder/website_health_checker/link-intel-suite/LinkIntelSuite_Pitch.pptx";
pres.writeFile({ fileName: outPath }).then(() => {
  console.log("✅  Deck written to:", outPath);
});
