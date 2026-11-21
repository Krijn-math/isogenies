/* The Isogeny Forest: renders data/graph.json as a supervision tree that fills the
   window. Nodes are people, edges go from supervisor up to student: the present is at
   the top and the roots (the first person) at the bottom. The forest grows from the
   centre: the first person sits in the middle and later branches appear alternately to
   the right and the left. Scrolling travels back in time and the view zooms in as the
   forest thins out; the year bar on the left jumps to a year; dragging or
   shift-scrolling looks sideways, pinching or ctrl-scrolling zooms. */
(function () {
  "use strict";

  const CONFIG = Object.assign({ email: "", data: "data/graph.json", papers: "data/papers.json" }, window.FOREST_CONFIG || {});
  const COL = 50;          // horizontal unit of the tidy-tree layout
  const K_START = 1.0;     // zoom at the first year ...
  const K_END = 0.6;       // ... and once everyone has appeared; in between it follows how many have
  const GROW = 0.7;        // names and dots grow by (K_START / zoom)^GROW, so they stay readable when zoomed out
  const YEAR_BASE = 30;    // height of a year: YEAR_BASE + YEAR_PER per person in it (outside supervisors count half),
  const YEAR_PER = 16;     // but at least enough for its rows of names
  const ROW_H = 30;        // height of each further row of names within a year
  const GAP_H = 8;         // per empty year between two years (at most two count)
  const LABEL_Y = 18;      // baseline of a name, below its dot
  const LABEL_GAP = 12;    // minimum space between two names in the same row
  const SHIFTS = [0, 14, -14, 28, -28, 42, -42, 56, -56, 70, -70];   // sideways nudges tried before a new row
  const R = 5;             // dot radius of a doctor
  const RX = 4;            // dot radius of a supervisor whose thesis is outside the field
  const FONT = "13px Inter, system-ui, sans-serif";   // must match .node text in forest.css
  const ZOOM_CAP = 1.25;    // zooming in to fill the width goes at most this far beyond the planned zoom
  const ZOOM_RATE = 0.45;   // the zoom changes by at most this factor (e^0.45 ≈ 1.6) per 1000 px of scrolling
  const MARGIN_L = 64;     // screen pixels kept free on the left (for the year bar) ...
  const MARGIN_R = 20;     // ... and on the right
  const FLAG_DIR = "assets/vendor/flags/";
  const COUNTRY_CODES = "ad ae af ag ai al am ao aq ar as at au aw ax az ba bb bd be bf bg bh bi bj bl bm bn bo bq br bs bt bv bw by bz ca cc cd cf cg ch ci ck cl cm cn co cr cu cv cw cx cy cz de dj dk dm do dz ec ee eg eh er es et fi fj fk fm fo fr ga gb gd ge gf gg gh gi gl gm gn gp gq gr gs gt gu gw gy hk hm hn hr ht hu id ie il im in io iq ir is it je jm jo jp ke kg kh ki km kn kp kr kw ky kz la lb lc li lk lr ls lt lu lv ly ma mc md me mf mg mh mk ml mm mn mo mp mq mr ms mt mu mv mw mx my mz na nc ne nf ng ni nl no np nr nu nz om pa pe pf pg ph pk pl pm pn pr ps pt pw py qa re ro rs ru rw sa sb sc sd se sg sh si sj sk sl sm sn so sr ss st sv sx sy sz tc td tf tg th tj tk tl tm tn to tr tt tv tw tz ua ug um us uy uz va vc ve vg vi vn vu wf ws xk ye yt za zm zw".split(" ");

  const $ = (id) => document.getElementById(id);
  const regionNames = (() => { try { return new Intl.DisplayNames(["en"], { type: "region" }); } catch (e) { return null; } })();
  const countryName = (cc) => { if (!cc) return ""; try { return (regionNames && regionNames.of(cc.toUpperCase())) || cc.toUpperCase(); } catch (e) { return cc.toUpperCase(); } };
  const flagUrl = (cc) => (cc && /^[a-z]{2}$/.test(cc) ? FLAG_DIR + cc + ".svg" : null);
  const fold = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);
  const label = (n) => n.label || "Dr. " + n.name;
  const pageBase = () => location.href.replace(/[#?].*$/, "").replace(/[^/]*$/, "");

  /* ---------- Short links: first name, plus 2, 3, … for later namesakes ---------- */
  const RESERVED = new Set(["assets", "data", "tools", "index", "index.html", "404", "thesis_data", "eprint", "graph", "src"]);
  function baseSlug(name) {
    const first = fold(String(name).trim().split(/\s+/)[0]).replace(/[^a-z0-9]/g, "");
    return first || "doctor";
  }
  function assignSlugs(nodes) {
    const taken = new Set(RESERVED);
    nodes.forEach((n) => { if (n.slug) taken.add(n.slug); });
    const eligible = nodes.filter((n) => !n.slug && !n.external)
      .sort((a, b) => (a.year || 9999) - (b.year || 9999) || a.name.localeCompare(b.name));
    for (const n of eligible) {
      const b = baseSlug(n.name);
      let s = b, k = 2;
      while (taken.has(s)) s = b + k++;
      n.slug = s; taken.add(s);
    }
    return taken;
  }

  /* ---------- Data ---------- */
  function normalise(raw) {
    const nodes = (raw.nodes || []).map((n) => Object.assign({}, n, { country: n.country ? String(n.country).toLowerCase() : "" }));
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const edges = [];
    for (const e of raw.edges || []) {
      const s = byId.get(e.from != null ? e.from : e.source), t = byId.get(e.to != null ? e.to : e.target);
      if (!s || !t) { console.warn("Isogeny Forest: edge with unknown person", e); continue; }
      edges.push({ source: s, target: t, role: e.role || "" });
    }
    nodes.forEach((n) => { n.sup = []; n.stu = []; });
    edges.forEach((e) => { e.target.sup.push(e.source); e.source.stu.push(e.target); });
    const taken = assignSlugs(nodes);
    return { meta: raw.meta || {}, nodes, edges, byId, taken };
  }

  /* ---------- Layout ---------- */
  // The name on a node: the full name without initials or "Jr.", unless "short" is set in graph.json.
  const shortName = (n) => n.short || String(n.name).replace(/,?\s+Jr\.?$/, "").split(/\s+/).filter((p) => !/^\p{Lu}\.$/u.test(p)).join(" ");
  const rad = (n) => (n.external ? RX : R);
  const measure = (() => {
    const c = document.createElement("canvas").getContext("2d");
    return (n) => { c.font = FONT; return c.measureText(shortName(n)).width; };
  })();
  // Earliest in the middle, then alternately right and left: [c4, c2, c0, c1, c3].
  const centreOut = (list) => { const out = []; list.forEach((c, i) => (i % 2 ? out.push(c) : out.unshift(c))); return out; };

  // W, H: the window size. Every year has to fit the width at the zoom the camera has there.
  function layout(G, W, H) {
    const { nodes, edges } = G;
    const years = nodes.filter((n) => n.year).map((n) => +n.year);
    const minYear = years.length ? Math.min(...years) : 2000;

    // Year for people without one (supervisors outside the field): two years above their first student.
    const effYear = (n, seen = new Set()) => {
      if (n.year) return +n.year;
      if (n._y != null) return n._y;
      if (seen.has(n)) return minYear;
      seen.add(n);
      const ys = n.stu.map((s) => effYear(s, seen));
      n._y = ys.length ? Math.min(...ys) - 2 : minYear - 2;
      return n._y;
    };
    nodes.forEach((n) => { n.ey = effYear(n); });

    // Planned zoom per year, from K_START to K_END as the share of people who have appeared grows.
    // Narrow windows keep the same zoom, so their names stay readable and stack into more rows.
    const fw = 1;
    const weight = (n) => (n.external ? 0.5 : 1);
    const byYear = d3.group(nodes, (n) => n.ey);
    const yearList = [...byYear.keys()].sort((a, b) => a - b);
    const total = d3.sum(nodes, weight);
    const kOfYear = new Map();
    let cum = 0;
    for (const yr of yearList) {
      const w = d3.sum(byYear.get(yr), weight);
      kOfYear.set(yr, fw * K_START * Math.pow(K_END / K_START, (cum + w / 2) / total));
      cum += w;
    }
    const scOf = (yr) => Math.pow(fw * K_START / kOfYear.get(yr), GROW);
    // Half the width a year may use, in layout units: the window minus margins, at that year's zoom.
    const room = (yr) => ((W - MARGIN_L - MARGIN_R) / 2) / kOfYear.get(yr);
    nodes.forEach((n) => {
      n.sc = scOf(n.ey);
      n.w = Math.max(measure(n), 2 * R) * n.sc;
    });

    // Tidy tree: each person under their first supervisor in the field (or their first supervisor),
    // with a virtual root on top, growing outwards from the centre.
    nodes.forEach((n) => {
      n.primary = n.sup.find((s) => s.year) || n.sup[0] || null;
      if (n.primary === n) n.primary = null;
    });
    nodes.forEach((n) => {   // guard against cycles in that chain
      let p = n.primary, hops = 0;
      while (p && p !== n && hops < nodes.length) { p = p.primary; hops++; }
      if (p === n) n.primary = null;
    });
    const ROOT = { id: "__root__" };
    const kids = new Map();
    nodes.forEach((n) => { const p = n.primary || ROOT; if (!kids.has(p)) kids.set(p, []); kids.get(p).push(n); });
    const order = (a, b) => a.ey - b.ey || a.name.localeCompare(b.name);
    const h = d3.hierarchy(ROOT, (d) => centreOut((kids.get(d) || []).slice().sort(order)));
    d3.tree().nodeSize([1, 1]).separation((a, b) => (a.parent === b.parent ? 1 : 1.3))(h);
    h.descendants().forEach((d) => { if (d.data !== ROOT) d.data.x = d.x * COL; });
    // People without a supervisor in the tree sit above the middle of their students.
    nodes.forEach((n) => { if (!n.primary && n.stu.length) n.x = d3.mean(n.stu, (s) => s.x); });
    const first = nodes.slice().sort(order)[0];
    const x0 = first ? first.x : 0;
    nodes.forEach((n) => { n.x -= x0; });   // the first person sits at x = 0, the centre of the view

    // Squeeze each year towards the centre until it fits its room; the squeeze never relaxes later on,
    // so branches drift smoothly instead of jumping.
    let squeeze = 1;
    for (const yr of yearList) {
      const list = byYear.get(yr), A = room(yr);
      const need = d3.max(list, (n) => Math.abs(n.x) + n.w / 2);
      squeeze = Math.min(squeeze, need > A ? (A * 0.92) / need : 1);
      list.forEach((n) => { n.x *= squeeze; });
    }

    // Within a year, nudge a name sideways (within the room) or give it a new row until it overlaps
    // nothing; doctors first, those nearest the centre first.
    const bands = [];
    for (const yr of yearList) {
      const A = room(yr);
      const list = byYear.get(yr).sort((a, b) => (!!a.external - !!b.external) || Math.abs(a.x) - Math.abs(b.x));
      const rows = [];
      for (const n of list) {
        const half = n.w / 2, gap = LABEL_GAP * n.sc, lim = Math.max(0, A - half);
        placing: for (let k = 0; ; k++) {
          if (k === rows.length) rows.push([]);
          for (const s of SHIFTS) {
            const x = Math.max(-lim, Math.min(lim, n.x + s * n.sc * (n.x < 0 ? -1 : 1)));   // prefer outwards
            if (rows[k].every(([c, d]) => x + half + gap <= c || d + gap <= x - half)) {
              rows[k].push([x - half, x + half]); n.x = x; n.row = k;
              break placing;
            }
          }
          if (k > 40) { n.row = k; break; }   // safety net for absurdly narrow windows
        }
      }
      bands.push({ year: yr, list, rows: rows.length, sc: scOf(yr), k: kOfYear.get(yr), labelled: list.some((n) => n.year) });
    }
    // Stack the years from the newest (top) to the oldest (bottom).
    let y = 0, prev = null;
    bands.reverse();
    for (const b of bands) {
      if (prev != null) y += Math.min(prev - b.year - 1, 2) * GAP_H;
      b.y = y;
      b.yc = y + (b.rows - 1) * ROW_H * b.sc / 2;   // the middle of its rows, where the camera aims for it
      b.list.forEach((n) => { n.y = y + n.row * ROW_H * b.sc; });
      y += Math.max(YEAR_BASE + YEAR_PER * d3.sum(b.list, weight), (b.rows * ROW_H + 18) * b.sc);
      prev = b.year;
      delete b.list;
    }
    // Final view per year: centred on, and zoomed to fill the width with, everything in the window
    // around that year, but never more than ZOOM_CAP times the planned zoom. Both the centre and the
    // zoom change gradually: the centre is a smoothed average, and the zoom is the largest that fits
    // everywhere while changing by at most ZOOM_RATE (in log terms) per 1000 px of scrolling.
    const span = new Map(bands.map((b) => {
      const list = nodes.filter((n) => n.ey === b.year);
      return [b, [d3.min(list, (n) => n.x - n.w / 2), d3.max(list, (n) => n.x + n.w / 2)]];
    }));
    const planned = new Map(bands.map((b) => [b, b.k]));
    const halfW = (W - MARGIN_L - MARGIN_R) / 2;
    for (let pass = 0; pass < 4; pass++) {
      const win = new Map(bands.map((b) => {
        const half = (H / 2) / b.k;   // half the window height, in layout units, at the current guess
        const near = bands.filter((c) => Math.abs(c.y - b.y) <= half);
        return [b, [d3.min(near, (c) => span.get(c)[0]), d3.max(near, (c) => span.get(c)[1])]];
      }));
      // centre: a gaussian average over a window height of neighbours
      for (const b of bands) {
        const sigma = (H / 2) / b.k;
        let sw = 0, sx = 0;
        for (const c of bands) {
          const w = Math.exp(-0.5 * Math.pow((c.y - b.y) / sigma, 2));
          sw += w; sx += w * (win.get(c)[0] + win.get(c)[1]) / 2;
        }
        b.cx = sx / sw;
      }
      // zoom: what fits around that centre, then the largest curve below it that changes gradually
      const fit = bands.map((b) => {
        const [lo, hi] = win.get(b);
        return Math.min(planned.get(b) * ZOOM_CAP, halfW / Math.max(b.cx - lo, hi - b.cx, 1));
      });
      bands.forEach((b, i) => {
        b.k = d3.min(bands, (c, j) => fit[j] * Math.exp(ZOOM_RATE * Math.abs(c.y - b.y) * fit[j] / 1000));
      });
    }
    for (let i = bands.length - 2; i >= 0; i--) bands[i].k = Math.min(bands[i].k, bands[i + 1].k);
    // Edge end points: from just above the supervisor's dot up to just below the student's name.
    edges.forEach((e) => {
      e.y1 = e.source.y - (rad(e.source) + 3) * e.source.sc;
      e.y2 = e.target.y + (LABEL_Y + 7) * e.target.sc;
    });
    return {
      minYear, bands,
      x0: d3.min(nodes, (n) => n.x - n.w / 2), x1: d3.max(nodes, (n) => n.x + n.w / 2),
      y0: -R, y1: d3.max(nodes, (n) => n.y + (LABEL_Y + 6) * n.sc)
    };
  }

  // Long branches fade out in the middle, so they lead the eye without crossing everything.
  function fadeStops(len) {
    if (len < 130) return [[0, 0.7], [1, 0.7]];
    const f = Math.min(0.3, 40 / len), mid = Math.max(0.035, 0.22 * 130 / len);
    return [[0, 0.75], [f, 0.3], [0.5, mid], [1 - f, 0.3], [1, 0.75]];
  }

  /* ---------- Rendering ---------- */
  let current = null;          // the selected person, kept across re-renders
  function render(G, opts = {}) {
    const host = $("forest");
    const W = () => host.clientWidth, H = () => host.clientHeight;
    const box = layout(G, W(), H());
    host.innerHTML = "";
    const svg = d3.select(host).append("svg");
    const defs = svg.append("defs");
    const world = svg.append("g").attr("class", "world");

    G.edges.forEach((e, i) => { e.i = i; });
    defs.selectAll("linearGradient").data(G.edges).join("linearGradient")
      .attr("id", (e) => "eg" + e.i).attr("gradientUnits", "userSpaceOnUse")
      .attr("x1", (e) => e.source.x).attr("y1", (e) => e.y1).attr("x2", (e) => e.target.x).attr("y2", (e) => e.y2)
      .selectAll("stop").data((e) => fadeStops(Math.abs(e.y2 - e.y1) * K_END)).join("stop")
      .attr("class", "fade-stop").attr("offset", (d) => d[0]).attr("stop-opacity", (d) => d[1]);

    // Branches from supervisors outside the field are dashed, branches between doctors in the forest solid.
    const edgeSel = world.append("g").attr("class", "edges").selectAll("path").data(G.edges).join("path")
      .attr("class", (e) => "edge" + (e.source.external ? " outside" : ""))
      .attr("stroke", (e) => `url(#eg${e.i})`)
      .attr("d", (e) => {
        const s = e.source, t = e.target, m = (e.y1 + e.y2) / 2;
        return `M${s.x},${e.y1}C${s.x},${m} ${t.x},${m} ${t.x},${e.y2}`;
      });

    const nodeSel = world.append("g").attr("class", "nodes").selectAll("g").data(G.nodes, (n) => n.id).join("g")
      .attr("class", (n) => "node" + (n.external ? " external" : ""))
      .attr("transform", (n) => `translate(${n.x},${n.y}) scale(${n.sc})`)
      .attr("tabindex", 0).attr("role", "button")
      .attr("aria-label", (n) => label(n) + (n.year ? ", " + n.year : ""));
    nodeSel.append("rect").attr("class", "hit")
      .attr("x", (n) => -n.w / n.sc / 2 - 4).attr("y", -R - 4).attr("width", (n) => n.w / n.sc + 8).attr("height", LABEL_Y + R + 10);
    nodeSel.append("circle").attr("r", rad);
    nodeSel.append("text").attr("y", LABEL_Y).text(shortName);

    // Lineage highlighting, plus a softer one for academic siblings.
    function lineage(n) {
      const up = new Set([n]), down = new Set([n]);
      const walk = (m, key, acc) => m[key].forEach((p) => { if (!acc.has(p)) { acc.add(p); walk(p, key, acc); } });
      walk(n, "sup", up); walk(n, "stu", down);
      return { up, down };
    }
    function light(n) {
      if (!n) {
        host.classList.remove("focus");
        nodeSel.classed("lit", false).classed("sib", false);
        edgeSel.classed("lit", false).classed("sib", false);
        return;
      }
      const { up, down } = lineage(n);
      // academic siblings: the other students of the same supervisors
      const sibs = new Set(n.sup.flatMap((s) => s.stu).filter((m) => !up.has(m) && !down.has(m)));
      const isLit = (e) => (up.has(e.source) && up.has(e.target)) || (down.has(e.source) && down.has(e.target));
      host.classList.add("focus");
      nodeSel.classed("lit", (m) => up.has(m) || down.has(m)).classed("sib", (m) => sibs.has(m));
      edgeSel.classed("lit", isLit).classed("sib", (e) => !isLit(e) && sibs.has(e.target) && n.sup.includes(e.source));
    }

    // ---- Camera: the world point (x, y) sits at the centre of the window; the zoom follows y, times m.
    const ANCHOR = 0.5;                       // where on screen the camera's y sits
    const headerH = () => $("top").getBoundingClientRect().height;
    const kAt = d3.scaleLinear().domain(box.bands.map((b) => b.y)).range(box.bands.map((b) => b.k)).clamp(true);
    // the middle of what is in view at a given height; the camera's x is an offset from it
    const cAt = d3.scaleLinear().domain(box.bands.map((b) => b.y)).range(box.bands.map((b) => b.cx)).clamp(true);
    const cam = { x: 0, y: 0, m: 1 };
    const kOf = (c) => kAt(c.y) * c.m;
    const midX = () => (MARGIN_L + W() - MARGIN_R) / 2;   // screen x the camera aims at
    const transformOf = (c) => { const k = kOf(c); return d3.zoomIdentity.translate(midX() - k * (cAt(c.y) + c.x), H() * ANCHOR - k * c.y).scale(k); };
    function startCam() {
      // The newest year just below the header.
      const c = { x: 0, y: 0, m: 1 };
      for (let i = 0; i < 3; i++) c.y = box.y0 - (headerH() + 50 - H() * ANCHOR) / kOf(c);
      return c;
    }
    function clamp(c) {
      c.m = Math.max(0.35, Math.min(3, c.m));
      const k = kOf(c);
      c.y = Math.max(startCam().y - 40 / k, Math.min(box.y1 - H() * 0.15 / k, c.y));
      // sideways only as far as there is something to see (nothing, when everything fits)
      const half = (W() - MARGIN_L - MARGIN_R) / 2 / k, mid = cAt(c.y);
      const lo = Math.min(0, box.x0 - mid + half), hi = Math.max(0, box.x1 - mid - half);
      c.x = Math.max(lo, Math.min(hi, c.x));
      return c;
    }
    // ---- Year bar: every year with a defence, evenly spaced, newest at the top. Its marker follows
    // the camera; clicking a year flies there, dragging along the bar scrubs through time.
    const years = box.bands.filter((b) => b.labelled);
    const bar = $("years");
    bar.innerHTML = '<div class="years-line"></div><div class="years-mark"></div>' + years.map((b, i) =>
      `<button type="button" data-i="${i}" class="${b.year % 10 === 0 ? "decade" : ""}" style="top:${(100 * i / Math.max(1, years.length - 1)).toFixed(3)}%">${b.year}</button>`).join("");
    const mark = bar.querySelector(".years-mark");
    const yOfU = d3.scaleLinear().domain(years.map((b, i) => i / Math.max(1, years.length - 1))).range(years.map((b) => b.yc)).clamp(true);
    const uOfY = d3.scaleLinear().domain(years.map((b) => b.yc)).range(years.map((b, i) => i / Math.max(1, years.length - 1))).clamp(true);
    const nearest = (y) => years.reduce((a, b) => (Math.abs(b.yc - y) < Math.abs(a.yc - y) ? b : a), years[0]);
    let barHeld = false;
    bar.onclick = (ev) => {
      const b = ev.target.closest("button");
      if (b && !barHeld) flyTo({ x: 0, y: years[+b.dataset.i].yc, m: cam.m }, 800);
    };
    bar.onpointerdown = (ev) => {
      if (ev.button > 0) return;
      const r = bar.getBoundingClientRect(), y0 = ev.clientY;
      barHeld = false;
      const scrub = (e) => {
        if (!barHeld && Math.abs(e.clientY - y0) < 4) return;
        if (!barHeld) { barHeld = true; bar.setPointerCapture(e.pointerId); bar.classList.add("scrubbing"); }
        svg.interrupt("cam");
        cam.y = yOfU((e.clientY - r.top) / r.height); clamp(cam); apply();
      };
      const end = () => { bar.removeEventListener("pointermove", scrub); bar.classList.remove("scrubbing"); setTimeout(() => { barHeld = false; }, 0); };
      bar.addEventListener("pointermove", scrub);
      bar.addEventListener("pointerup", end, { once: true });
      bar.addEventListener("pointercancel", end, { once: true });
    };

    let travelled = false;
    function apply() {
      const t = transformOf(cam);
      world.attr("transform", t);
      host.classList.toggle("far", t.k < 0.45);
      const here = nearest(cam.y);
      $("year-now").textContent = here ? here.year : "";
      mark.style.top = (100 * uOfY(cam.y)).toFixed(3) + "%";
      bar.querySelectorAll("button").forEach((b) => b.classList.toggle("here", years[+b.dataset.i] === here));
      const s = startCam(), away = Math.abs(cam.y - s.y) * kOf(cam) > 60 || Math.abs(cam.x - s.x) * kOf(cam) > 60;
      document.body.classList.toggle("travelling", away);
      if (away && !travelled) { travelled = true; document.body.classList.add("moved"); }
    }
    function moveBy(dxScreen, dyScreen) {
      svg.interrupt("cam");
      const k = kOf(cam);
      cam.x += dxScreen / k; cam.y += dyScreen / k;
      clamp(cam); apply();
    }
    function zoomBy(f, px, py) {
      // keep the world point under (px, py) in place
      svg.interrupt("cam");
      const t0 = transformOf(cam), wx = t0.invertX(px), wy = t0.invertY(py);
      cam.m *= f; clamp(cam);
      const t1 = transformOf(cam);
      cam.x += wx - t1.invertX(px); cam.y += wy - t1.invertY(py);
      clamp(cam); apply();
    }
    function flyTo(target, ms = 750) {
      clamp(target);
      svg.interrupt("cam").transition("cam").duration(ms).ease(d3.easeCubicInOut)
        .tween("cam", () => { const i = d3.interpolateObject(Object.assign({}, cam), target); return (t) => { Object.assign(cam, i(t)); apply(); }; });
    }

    // Scrolling travels through time; shift or a sideways swipe moves sideways; ctrl/pinch zooms.
    function onWheel(ev) {
      if (ev.target.closest && ev.target.closest(".panel, dialog, #search-results")) return;
      ev.preventDefault();
      const unit = ev.deltaMode === 1 ? 16 : ev.deltaMode === 2 ? H() : 1;
      let dx = ev.deltaX * unit, dy = ev.deltaY * unit;
      if (ev.ctrlKey || ev.metaKey) { zoomBy(Math.pow(2, -dy * 0.01), ev.clientX, ev.clientY); return; }
      if (ev.shiftKey && !dx) { dx = dy; dy = 0; }
      host.classList.add("scrolling");
      clearTimeout(scrollTimer);
      scrollTimer = setTimeout(() => host.classList.remove("scrolling"), 200);
      moveBy(dx, dy);
    }
    let scrollTimer;
    function onKey(ev) {
      if (ev.target.closest && ev.target.closest("input, textarea, dialog")) return;
      const k = kOf(cam), page = H() * 0.8 / k;
      const moves = { ArrowDown: [0, 90 / k], ArrowUp: [0, -90 / k], ArrowLeft: [-90 / k, 0], ArrowRight: [90 / k, 0],
                      PageDown: [0, page], PageUp: [0, -page], " ": [0, page] };
      if (moves[ev.key] && !(ev.key === " " && ev.target.closest && ev.target.closest(".node"))) {
        ev.preventDefault();
        flyTo({ x: cam.x + moves[ev.key][0], y: cam.y + moves[ev.key][1], m: cam.m }, 220);
      }
      else if (ev.key === "+" || ev.key === "=") zoomBy(1.25, W() / 2, H() * ANCHOR);
      else if (ev.key === "-") zoomBy(0.8, W() / 2, H() * ANCHOR);
      else if (ev.key === "Home") { ev.preventDefault(); flyTo(startCam(), 900); }
      else if (ev.key === "End") { ev.preventDefault(); flyTo({ x: cam.x, y: box.y1, m: cam.m }, 900); }
    }

    // Dragging (mouse or one finger) moves; two fingers pinch. The pointer is only captured once it has
    // really moved, so a plain click still reaches the name under it.
    const pts = new Map();
    let down = null, dragged = false, pinch = null;
    svg.on("pointerdown", (ev) => {
      if (ev.button > 0) return;
      pts.set(ev.pointerId, [ev.clientX, ev.clientY]);
      if (pts.size === 1) { down = [ev.clientX, ev.clientY]; dragged = false; }
      if (pts.size === 2) { const [a, b] = [...pts.values()]; pinch = Math.hypot(a[0] - b[0], a[1] - b[1]); }
    });
    svg.on("pointermove", (ev) => {
      const p = pts.get(ev.pointerId);
      if (!p) return;
      if (pts.size === 1 && !dragged) {
        if (Math.hypot(ev.clientX - down[0], ev.clientY - down[1]) < 5) return;
        dragged = true;
        svg.node().setPointerCapture(ev.pointerId);
        host.classList.add("grabbing");
      }
      const dx = ev.clientX - p[0], dy = ev.clientY - p[1];
      pts.set(ev.pointerId, [ev.clientX, ev.clientY]);
      if (pts.size === 2) {
        const [a, b] = [...pts.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        if (pinch) zoomBy(d / pinch, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
        pinch = d; dragged = true;
        return;
      }
      moveBy(-dx, -dy);
    });
    const release = (ev) => { pts.delete(ev.pointerId); if (pts.size < 2) pinch = null; if (!pts.size) host.classList.remove("grabbing"); };
    svg.on("pointerup", release).on("pointercancel", release).on("lostpointercapture", release);
    // the click that ends a drag is not a selection
    svg.node().addEventListener("click", (ev) => { if (dragged) { ev.stopPropagation(); dragged = false; } }, true);

    nodeSel
      .on("click",(ev, n) => { ev.stopPropagation(); select(n); })
      .on("keydown", (ev, n) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(n, { pan: true }); } });
    svg.on("click", () => select(null));

    function panTo(n) {
      const c = { x: n.x - cAt(n.y), y: n.y, m: cam.m };
      const k = kOf(c);
      if (W() > 640 && !$("panel").hidden) c.x += Math.min(210, W() * 0.18) / k;   // leave room for the card
      if (W() <= 640) c.y += H() * 0.22 / k;                                       // and for the sheet below
      flyTo(c);
    }

    function select(n, o = {}) {
      current = n;
      nodeSel.classed("selected", (m) => m === n);
      light(n);
      showPanel(G, n && !n.external ? n : null);   // supervisors from outside the field light up but get no card
      const want = n ? "#" + (n.slug || n.id) : " ";
      if (location.hash !== want) history.replaceState(null, "", n ? want : location.pathname + location.search);
      if (n && o.pan) panTo(n);
    }

    // the year at the centre of the view, so a re-render (after a resize) can come back to it
    const yearAt = () => (nearest(cam.y) || {}).year;

    Object.assign(cam, startCam());
    const back = opts.year != null && years.find((b) => b.year === opts.year);
    if (back && back !== years[0]) cam.y = back.yc;
    clamp(cam);
    apply();
    if (current) { nodeSel.classed("selected", (m) => m === current); light(current); }
    return { select, onWheel, onKey, yearAt, width: W(), height: H() };
  }

  /* ---------- Detail panel ---------- */
  function personLinks(list) {
    if (!list.length) return '<span class="none">—</span>';
    return list.map((p) => `<a data-id="${esc(p.id)}" tabindex="0">${esc(label(p))}</a>`).join(", ");
  }
  let API = null;
  /* Recent ePrint papers, from data/papers.json (built by tools/fetch_papers.py). */
  let PAPERS = null, papersOpen = false;
  function papersHtml(n) {
    const list = PAPERS && PAPERS.papers && PAPERS.papers[n.id];
    if (!list || !list.length) return "";
    const total = (PAPERS.counts && PAPERS.counts[n.id]) || list.length;
    const items = list.map((p) => `<li><a href="https://eprint.iacr.org/${esc(p.id)}" target="_blank" rel="noopener">${esc(p.title)}</a><small>${esc(p.id)}${p.with && p.with.length ? " · with " + esc(p.with.join(", ")) : ""}</small></li>`).join("");
    return `<details class="papers"${papersOpen ? " open" : ""}><summary>Recent papers on ePrint <span>${list.length}${total > list.length ? " of " + total : ""}</span></summary><ol>${items}</ol></details>`;
  }
  function showPanel(G, n) {
    const panel = $("panel"), body = $("panel-body");
    if (!n) { panel.hidden = true; return; }
    const flag = flagUrl(n.country);
    const pdf = safeUrl(n.pdf), home = safeUrl(n.homepage);
    const short = n.slug ? pageBase() + n.slug : null;
    const rows = [];
    if (n.university) rows.push(["University", esc(n.university)]);
    if (n.country) rows.push(["Country", (flag ? `<img class="flag-img" src="${flag}" alt="" width="18" height="13.5">` : "") + esc(countryName(n.country))]);
    if (n.year) rows.push(["Year", esc(n.year)]);
    if (!n.external || n.sup.length) rows.push([n.sup.length === 1 ? "Supervisor" : "Supervisors", `<span class="people">${personLinks(n.sup)}</span>`]);
    if (n.stu.length) rows.push([n.stu.length === 1 ? "Student" : "Students", `<span class="people">${personLinks(n.stu.slice().sort((a, b) => a.ey - b.ey))}</span>`]);
    body.innerHTML = `
      <h3>${esc(label(n))}</h3>
      ${n.title ? `<p class="thesis-title">${esc(n.title)}</p>` : n.external ? `<p class="thesis-title">Supervisor in the forest; their own thesis is outside it.</p>` : `<p class="thesis-title none">Thesis title not yet recorded.</p>`}
      <dl>${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>
      <div class="actions">
        ${pdf ? `<a class="solid" href="${esc(pdf)}" target="_blank" rel="noopener">Thesis</a>` : ""}
        ${home ? `<a class="ghost" href="${esc(home)}" target="_blank" rel="noopener">Homepage</a>` : ""}
      </div>
      ${papersHtml(n)}
      ${short && pdf ? `<p class="short">Short link: <a href="${esc(short)}">${esc(short.replace(/^https?:\/\//, ""))}</a></p>` : ""}`;
    body.querySelectorAll("[data-id]").forEach((a) => {
      const go = () => API.select(G.byId.get(a.dataset.id), { pan: true });
      a.addEventListener("click", go);
      a.addEventListener("keydown", (ev) => { if (ev.key === "Enter") go(); });
    });
    const det = body.querySelector("details.papers");
    if (det) det.addEventListener("toggle", () => { papersOpen = det.open; });
    panel.hidden = false;
  }

  /* ---------- Search ---------- */
  function setupSearch(G) {
    const input = $("search"), list = $("search-results");
    let hits = [], cur = 0;
    const show = () => {
      list.innerHTML = hits.map((n, i) => `<li role="option" data-i="${i}" aria-selected="${i === cur}">${esc(label(n))}<small>${esc(n.year || (n.external ? "supervisor" : ""))}</small></li>`).join("");
      list.hidden = !hits.length;
    };
    const pick = (n) => { if (!n) return; API.select(n, { pan: true }); input.value = ""; hits = []; show(); input.blur(); };
    input.addEventListener("input", () => {
      const q = fold(input.value.trim());
      hits = q ? G.nodes.filter((n) => (fold(n.name).includes(q) || fold(n.university).includes(q))).slice(0, 8) : [];
      cur = 0; show();
    });
    input.addEventListener("keydown", (ev) => {
      if (ev.key === "ArrowDown") { cur = Math.min(cur + 1, hits.length - 1); show(); ev.preventDefault(); }
      else if (ev.key === "ArrowUp") { cur = Math.max(cur - 1, 0); show(); ev.preventDefault(); }
      else if (ev.key === "Enter") { pick(hits[cur]); ev.preventDefault(); }
      else if (ev.key === "Escape") { hits = []; show(); }
    });
    list.addEventListener("mousedown", (ev) => { const li = ev.target.closest("li"); if (li) { ev.preventDefault(); pick(hits[+li.dataset.i]); } });
    input.addEventListener("blur", () => setTimeout(() => { list.hidden = true; }, 100));
  }

  /* ---------- Add-a-doctor form ---------- */
  function setupForm(G) {
    const form = $("add-form"), msg = $("form-msg");
    const people = [...new Set(G.nodes.map((n) => n.name))].sort();
    const unis = [...new Set(G.nodes.map((n) => n.university).filter(Boolean))].sort();
    $("people").innerHTML = people.map((p) => `<option value="${esc(p)}">`).join("");
    $("universities").innerHTML = unis.map((u) => `<option value="${esc(u)}">`).join("");
    const countries = COUNTRY_CODES.map((c) => [c, countryName(c)]).filter(([c, n]) => n && n.toLowerCase() !== c).sort((a, b) => a[1].localeCompare(b[1]));
    $("countries").innerHTML = countries.map(([, n]) => `<option value="${esc(n)}">`).join("");
    const codeOf = (name) => { const f = fold(name.trim()); const hit = countries.find(([c, n]) => fold(n) === f || c === f); return hit ? hit[0] : ""; };
    $("notes-open").onclick = () => {
      $("notes-field").hidden = false;
      $("notes-open").parentNode.hidden = true;
      form.elements.notes.focus();
    };
    const newId = (name) => { const b = baseSlug(name); let s = b, k = 2; while (G.taken.has(s)) s = b + k++; return s; };

    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const f = form.elements;
      const val = (k) => (f[k] ? f[k].value.trim() : "");
      const bad = [];
      ["name", "year", "title", "university", "supervisors", "country"].forEach((k) => { if (!val(k)) bad.push(k); });
      if (val("year") && !/^(19|20)\d\d$/.test(val("year"))) bad.push("year");
      if (val("pdf") && !safeUrl(val("pdf"))) bad.push("pdf");
      [...form.querySelectorAll("input")].forEach((i) => i.classList.toggle("invalid", bad.includes(i.name)));
      if (bad.length) { msg.textContent = "Please check the highlighted fields."; msg.className = "form-msg error"; return; }

      const sups = val("supervisors").split(/\s*[,;]\s*|\s+and\s+/).filter(Boolean);
      const known = sups.map((s) => G.nodes.find((n) => fold(n.name) === fold(s)));
      const entry = {
        id: newId(val("name")),
        name: val("name"), year: +val("year"), university: val("university"),
        country: codeOf(val("country")) || val("country"),
        title: val("title"), pdf: val("pdf") || undefined
      };
      const edgesOut = sups.map((s, i) => ({ from: known[i] ? known[i].id : "NEW: " + s, to: entry.id }));
      const lines = [
        "Please add this doctor to The Isogeny Forest.", "",
        "Name: " + entry.name,
        "Thesis: " + entry.title,
        "University: " + entry.university + " (" + val("country") + ")",
        "Year: " + entry.year,
        "Supervisors: " + sups.map((s, i) => s + (known[i] ? "" : " (not yet in the forest)")).join(", "),
        "PDF: " + (entry.pdf || "—"),
        val("notes") ? "\nComment:\n" + val("notes") : "",
        val("sender") ? "\nSubmitted by: " + val("sender") : "",
        "", "--- for graph.json ---",
        JSON.stringify(entry),
        ...edgesOut.map((e) => JSON.stringify(e))
      ].filter((l) => l !== "");
      const subject = "Isogeny Forest: add " + entry.name;
      const body = lines.join("\n");
      const href = "mailto:" + CONFIG.email + "?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(body);
      $("fallback-text").value = "Subject: " + subject + "\n\n" + body;
      $("fallback-mail").textContent = CONFIG.email;
      $("fallback-mail").href = "mailto:" + CONFIG.email;
      $("fallback").hidden = false;
      msg.textContent = "Your mail app should open with the email ready to send.";
      msg.className = "form-msg";
      window.location.href = href;
    });
    $("copy").addEventListener("click", async () => {
      const ta = $("fallback-text");
      try { await navigator.clipboard.writeText(ta.value); $("copy").textContent = "Copied"; }
      catch (e) { ta.select(); document.execCommand && document.execCommand("copy"); $("copy").textContent = "Copied"; }
      setTimeout(() => { $("copy").textContent = "Copy text"; }, 1800);
    });
  }

  /* ---------- Boot ---------- */
  function stats(G) {
    const docs = G.nodes.filter((n) => !n.external);
    const unis = new Set(docs.map((n) => n.university).filter(Boolean));
    const cs = new Set(docs.map((n) => n.country).filter(Boolean));
    $("stats").textContent = `${docs.length} doctors · ${unis.size} universities · ${cs.size} countries`;
    if (G.meta.updated) $("updated").textContent = "updated " + G.meta.updated;
    $("sample-note").hidden = !G.meta.sample;
  }

  function fromHash(G) {
    const h = decodeURIComponent(location.hash.slice(1));
    if (!h) return null;
    return G.nodes.find((n) => n.slug === h || n.id === h) || null;
  }

  function setupDialogs() {
    for (const name of ["add", "fix"]) {
      const dlg = $(name + "-dialog");
      $(name + "-open").onclick = () => {
        // a correction is most likely about whoever is selected
        if (name === "fix" && current && !dlg.open) $("fix-form").elements.who.value = current.name;
        dlg.showModal();
      };
      $(name + "-close").onclick = () => dlg.close();
      dlg.addEventListener("click", (ev) => { if (ev.target === dlg) dlg.close(); });
    }
  }

  /* ---------- Fix-a-mistake form ---------- */
  function setupFix(G) {
    const form = $("fix-form"), msg = $("fix-msg");
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const who = form.elements.who.value.trim(), what = form.elements.what.value.trim(), sender = form.elements.sender.value.trim();
      form.elements.what.classList.toggle("invalid", !what);
      if (!what) { msg.textContent = "Please say what is wrong."; msg.className = "form-msg error"; return; }
      const person = who && G.nodes.find((n) => fold(n.name) === fold(who));
      const subject = "Isogeny Forest: a mistake" + (who ? " about " + who : "");
      const body = [
        "There is a mistake in The Isogeny Forest.", "",
        "About: " + (who || "—") + (person ? " (" + pageBase() + "#" + (person.slug || person.id) + ")" : ""), "",
        "What is wrong:", what,
        sender ? "\nSubmitted by: " + sender : ""
      ].filter((l, i, a) => !(l === "" && i === a.length - 1)).join("\n");
      $("fix-fallback-text").value = "Subject: " + subject + "\n\n" + body;
      $("fix-fallback-mail").textContent = CONFIG.email;
      $("fix-fallback-mail").href = "mailto:" + CONFIG.email;
      $("fix-fallback").hidden = false;
      msg.textContent = "Your mail app should open with the email ready to send.";
      msg.className = "form-msg";
      window.location.href = "mailto:" + CONFIG.email + "?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(body);
    });
    $("fix-copy").addEventListener("click", async () => {
      const ta = $("fix-fallback-text");
      try { await navigator.clipboard.writeText(ta.value); } catch (e) { ta.select(); document.execCommand && document.execCommand("copy"); }
      $("fix-copy").textContent = "Copied";
      setTimeout(() => { $("fix-copy").textContent = "Copy text"; }, 1800);
    });
  }

  async function boot() {
    let raw;
    try {
      const res = await fetch(CONFIG.data, { cache: "no-cache" });
      raw = await res.json();
    } catch (e) {
      $("forest").innerHTML = '<p class="load-error">Could not load the forest data.</p>';
      console.error(e);
      return;
    }
    const G = normalise(raw);
    const papersP = fetch(CONFIG.papers, { cache: "no-cache" }).then((r) => (r.ok ? r.json() : null)).then((d) => { PAPERS = d; }).catch(() => {});
    if (document.fonts && document.fonts.ready) { try { await document.fonts.ready; } catch (e) {} }
    stats(G);
    API = render(G);
    // registered once; they act on whatever the current render is
    document.addEventListener("wheel", (ev) => API.onWheel(ev), { passive: false });
    document.addEventListener("keydown", (ev) => API.onKey(ev));
    // the layout depends on the window size: redo it when that changes, staying at the same year
    let rt;
    window.addEventListener("resize", () => {
      clearTimeout(rt);
      rt = setTimeout(() => { if ($("forest").clientWidth !== API.width || $("forest").clientHeight !== API.height) { API = render(G, { year: API.yearAt() }); window.IsogenyForest.api = API; } }, 150);
    });
    setupSearch(G);
    setupForm(G);
    setupFix(G);
    setupDialogs();
    $("panel-close").onclick = () => API.select(null);
    document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !$("panel").hidden) API.select(null); });
    const n0 = fromHash(G);
    if (n0) { await papersP; API.select(n0, { pan: true }); }
    window.addEventListener("hashchange", () => { const n = fromHash(G); if (n) API.select(n, { pan: true }); });
    window.IsogenyForest = { graph: G, api: API };
  }
  boot();
})();
