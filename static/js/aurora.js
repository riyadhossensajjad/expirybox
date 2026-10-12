// ExpiryBox — flowing gradient ribbon behind the landing, log-in and sign-up pages.
//
// A band of ~70 fine lines follows one wavy path across the screen. Each line is
// offset a little and drifts on its own phase, so together they read as a soft
// ribbon of light. A blurred copy underneath gives it the glow. On first load the
// ribbon sweeps in from the left; after that it keeps flowing slowly.
// Colours come from the site's gradient (the + button: pink → purple), plus a blue
// highlight.
//
// Performance notes (the picture is unchanged by any of these):
//  * The ribbon is drawn in a background thread (Web Worker + OffscreenCanvas)
//    where the browser supports it, so the page stays responsive to clicks,
//    typing and scrolling while it animates. Otherwise it is drawn on the page.
//  * The glow used to be blurred by a 64px CSS filter, which makes the browser
//    re-blur a full-screen layer every frame. Now the bands are drawn on a hidden
//    quarter-size canvas and blurred while being copied onto the visible one
//    (64px on screen = 16px at quarter size): same look, 1/16 of the pixels.
//  * Everything in the line formula that does not depend on the individual line
//    is computed once per frame, so the inner loop has no trigonometry.
//  * The dot grid is drawn once; each frame only the circle under the pointer is redrawn.

// The ribbon renderer. Self-contained (no access to the page) so the very same
// code can run on the page or inside a worker.
function shelfRibbon(lineCanvas, glowCanvas, makeCanvas, bake) {
  "use strict";
  var ctx = lineCanvas.getContext("2d");
  var gctx = glowCanvas ? glowCanvas.getContext("2d") : null;
  var GLOW_SCALE = 0.25;
  var GLOW_FILTER = "blur(" + (64 * GLOW_SCALE) + "px) saturate(1.2)";
  var srcGlow = null, sctx = null;
  if (gctx && bake) { srcGlow = makeCanvas(1, 1); sctx = srcGlow.getContext("2d"); }
  var W = 0, H = 0, DPR = 1;
  var colors = { a: "#e23cf7", b: "#8b3dff", c: "#4f7dff", dark: false };

  var resize = function (w, h, dpr) {
    W = w; H = h; DPR = dpr;
    lineCanvas.width = Math.round(W * DPR); lineCanvas.height = Math.round(H * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    if (gctx) {
      glowCanvas.width = Math.max(1, Math.round(W * GLOW_SCALE));
      glowCanvas.height = Math.max(1, Math.round(H * GLOW_SCALE));
      gctx.setTransform(GLOW_SCALE, 0, 0, GLOW_SCALE, 0, 0);
      if (sctx) {
        srcGlow.width = glowCanvas.width; srcGlow.height = glowCanvas.height;
        sctx.setTransform(GLOW_SCALE, 0, 0, GLOW_SCALE, 0, 0);
      }
    }
    tabSteps = -1;
  };

  // The ribbon's centre line: enters low on the left, dips under the middle,
  // and rises out on the right, like a wide swoosh.
  var centreY = function (u, t) {
    var base = 0.62 - 0.28 * Math.sin(Math.PI * (u * 0.95 + 0.08)) + 0.20 * u * u;
    var wave = 0.035 * Math.sin(u * 5.2 + t * 0.55) + 0.02 * Math.sin(u * 9.1 - t * 0.8);
    return (base + wave) * H;
  };
  var ease = function (x) { return 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3); };

  // Per-frame tables shared by every line. The per-line twist sin(A + B) is
  // expanded as sinA·cosB + cosA·sinB, so the inner loop has no trig.
  var tabSteps = -1, tabT = -1, tabReveal = -1;
  var tX = [], tC = [], tW = [], tSA = [], tCA = [];
  var buildTables = function (t, reveal, steps) {
    if (steps === tabSteps && t === tabT && reveal === tabReveal) return;
    tabSteps = steps; tabT = t; tabReveal = reveal;
    var xEnd = W * reveal;
    for (var s = 0; s <= steps; s++) {
      var x = (s / steps) * xEnd, u = x / W, a = u * 3.4 + t * 0.7;
      tX[s] = x;
      tC[s] = centreY(u, t);
      tW[s] = 0.55 + 0.45 * Math.sin(u * 2.2 + t * 0.4);
      tSA[s] = Math.sin(a); tCA[s] = Math.cos(a);
    }
  };

  var drawBand = function (c, t, reveal, lines, lineWidth, alpha, spread) {
    var grad = c.createLinearGradient(0, 0, W, 0);
    grad.addColorStop(0, colors.c);
    grad.addColorStop(0.32, colors.b);
    grad.addColorStop(0.6, colors.a);
    grad.addColorStop(0.82, colors.b);
    grad.addColorStop(1, colors.c);
    c.strokeStyle = grad;
    c.lineWidth = lineWidth;
    c.lineCap = "round";
    // How wide the ribbon is. "spread" widens it: the glow layer is spread much
    // wider than the fine lines so the colour fades out softly instead of looking solid.
    var thick = Math.max(120, H * 0.26) * (spread || 1);
    var steps = Math.max(40, Math.round(W / 14));
    buildTables(t, reveal, steps);
    for (var i = 0; i < lines; i++) {
      var f = lines === 1 ? 0.5 : i / (lines - 1);   // 0 = top edge, 1 = bottom edge
      var offset = (f - 0.5) * thick;
      var bright = Math.pow(Math.sin(Math.PI * f), 1.6);   // brighter in the middle
      if (alpha * bright < 0.002) continue;                // edge lines are invisible anyway
      c.globalAlpha = alpha * bright;
      // Each line twists on its own phase, so the ribbon looks like silk.
      var amp = thick * 0.22 * (0.5 + f) * 0.35, cb = Math.cos(f * 2.6) * amp, sb = Math.sin(f * 2.6) * amp;
      c.beginPath();
      c.moveTo(tX[0], tC[0] + offset * tW[0] + tSA[0] * cb + tCA[0] * sb);
      for (var s = 1; s <= steps; s++) {
        c.lineTo(tX[s], tC[s] + offset * tW[s] + tSA[s] * cb + tCA[s] * sb);
      }
      c.stroke();
    }
    c.globalAlpha = 1;
  };

  // t = seconds since the page opened; calm = reduced motion (no sweep-in).
  var draw = function (t, calm) {
    if (!W || !H) return;
    var reveal = calm ? 1 : ease(t / 1.8);        // sweeps in over 1.8 s on first load
    var thick = Math.max(120, H * 0.26);
    if (gctx) {                                   // wide, soft colour cloud (blurred)
      var g = sctx || gctx;
      g.clearRect(0, 0, W, H);
      g.globalCompositeOperation = colors.dark ? "lighter" : "source-over";
      drawBand(g, t, reveal, 18, thick / 3, colors.dark ? 0.26 : 0.2, 2.4);
      drawBand(g, t, reveal, 10, thick / 4, colors.dark ? 0.3 : 0.2, 1.2);
      g.globalCompositeOperation = "source-over";
      if (sctx) {                                 // copy across with the blur baked in
        gctx.setTransform(1, 0, 0, 1, 0, 0);
        gctx.clearRect(0, 0, glowCanvas.width, glowCanvas.height);
        gctx.filter = GLOW_FILTER;
        gctx.drawImage(srcGlow, 0, 0);
        gctx.filter = "none";
        gctx.setTransform(GLOW_SCALE, 0, 0, GLOW_SCALE, 0, 0);
      }
    }
    ctx.clearRect(0, 0, W, H);                    // fine silky lines, kept faint
    ctx.globalCompositeOperation = colors.dark ? "lighter" : "source-over";
    drawBand(ctx, t, reveal, 60, 1, colors.dark ? 0.16 : 0.1, 1.5);
    ctx.globalCompositeOperation = "source-over";
  };

  return { resize: resize, draw: draw, setColors: function (c) { colors = c; } };
}

// Worker side: receives the two canvases, then sizes/colours/pause messages,
// and runs its own animation loop off the page's main thread.
function shelfRibbonWorker() {
  var r = null, calm = false, startEpoch = 0, running = false, timer = 0;
  var tick = self.requestAnimationFrame
    ? function (f) { return self.requestAnimationFrame(f); }
    : function (f) { return setTimeout(function () { f(performance.now()); }, 16); };
  var untick = self.cancelAnimationFrame ? function (id) { self.cancelAnimationFrame(id); } : clearTimeout;
  var drawAt = function (now) { r.draw((performance.timeOrigin + now - startEpoch) / 1000, calm); };
  var loop = function (now) { if (!running) return; drawAt(now); timer = tick(loop); };
  self.onmessage = function (e) {
    var m = e.data;
    if (m.type === "init") {
      r = shelfRibbon(m.line, m.glow, function (w, h) { return new OffscreenCanvas(w, h); }, m.bake);
      calm = m.calm; startEpoch = m.startEpoch;
      r.setColors(m.colors); r.resize(m.w, m.h, m.dpr);
    } else if (m.type === "resize") { r.resize(m.w, m.h, m.dpr); }
    else if (m.type === "colors") { r.setColors(m.colors); }
    if (m.type === "run" || (m.type === "init" && m.run)) {
      if (calm) { drawAt(performance.now()); }
      else if (!running) { running = true; timer = tick(loop); }
    } else if (m.type === "pause") { running = false; untick(timer); }
    else if (calm && r) { drawAt(performance.now()); }       // redraw the still picture
  };
}

(function () {
  "use strict";
  var canvas = document.getElementById("aurora");
  if (!canvas || !canvas.getContext) return;
  var root = document.documentElement;
  var calm = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var start = performance.now(), raf = 0;

  var css = function (name, fallback) {
    var v = getComputedStyle(root).getPropertyValue(name).trim();
    return v || fallback;
  };
  var palette = function () {
    return {
      a: css("--fab-a", "#e23cf7"),
      b: css("--fab-b", "#8b3dff"),
      c: "#4f7dff",
      dark: root.getAttribute("data-theme") === "dark"
    };
  };
  var colors = palette();
  var glowCanvas = document.getElementById("aurora-glow");
  var size = function () {
    return { w: canvas.clientWidth, h: canvas.clientHeight, dpr: Math.min(window.devicePixelRatio || 1, 1.5) };
  };
  var filterWorks = function (c) {
    try { var x = c.getContext("2d"), f = "blur(16px) saturate(1.2)"; x.filter = f; return x.filter === f; }
    catch (e) { return false; }
  };

  var worker = null;
  if (canvas.transferControlToOffscreen && window.Worker && window.OffscreenCanvas && window.Blob && window.URL) {
    try {
      var bakeW = !!glowCanvas && filterWorks(new OffscreenCanvas(1, 1));
      var src = shelfRibbon.toString() + "\n(" + shelfRibbonWorker.toString() + ")();";
      var url = URL.createObjectURL(new Blob([src], { type: "text/javascript" }));
      worker = new Worker(url);
      URL.revokeObjectURL(url);
      var line = canvas.transferControlToOffscreen();
      var glow = glowCanvas ? glowCanvas.transferControlToOffscreen() : null;
      var sz = size();
      worker.postMessage({
        type: "init", line: line, glow: glow, bake: bakeW, calm: calm, run: !document.hidden,
        startEpoch: performance.timeOrigin + start, colors: colors, w: sz.w, h: sz.h, dpr: sz.dpr
      }, glow ? [line, glow] : [line]);
      if (bakeW) glowCanvas.classList.add("is-baked");
    } catch (e) { worker = null; }
  }

  var ribbon = null, frame = null;
  if (!worker) {                                  // fallback: draw on the page
    var bake = !!glowCanvas && filterWorks(document.createElement("canvas"));
    if (bake) glowCanvas.classList.add("is-baked");
    ribbon = shelfRibbon(canvas, glowCanvas, function (w, h) {
      var c = document.createElement("canvas"); c.width = w; c.height = h; return c;
    }, bake);
    ribbon.setColors(colors);
    var sz0 = size(); ribbon.resize(sz0.w, sz0.h, sz0.dpr);
    frame = function (now) {
      ribbon.draw((now - start) / 1000, calm);
      if (!calm) raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
  }

  canvas.classList.add("is-on");
  if (glowCanvas) glowCanvas.classList.add("is-on");

  // Re-read colours when the light/dark switch is used.
  new MutationObserver(function () {
    colors = palette();
    if (worker) worker.postMessage({ type: "colors", colors: colors });
    else { ribbon.setColors(colors); if (calm) requestAnimationFrame(frame); }
  }).observe(root, { attributes: true, attributeFilter: ["data-theme"] });

  window.addEventListener("resize", function () {
    var s = size();
    if (worker) worker.postMessage({ type: "resize", w: s.w, h: s.h, dpr: s.dpr });
    else { ribbon.resize(s.w, s.h, s.dpr); if (calm) requestAnimationFrame(frame); }
  });
  // Don't burn battery in a background tab.
  document.addEventListener("visibilitychange", function () {
    if (worker) { worker.postMessage({ type: document.hidden ? "pause" : "run" }); return; }
    if (document.hidden) { cancelAnimationFrame(raf); raf = 0; }
    else if (!raf && !calm) { raf = requestAnimationFrame(frame); }
  });

  /* ------------------------------------------------------------------ dots, halo and icons
     The dot grid is drawn on its own canvas so the dots can move. Under the
     mouse they slide outward and fade, opening a clear halo; while the mouse
     moves, product icons (one or more per category) pop up at random spots
     inside that halo, float a little and fade away. */
  var dotCanvas = document.getElementById("aurora-dots");
  var layer = document.querySelector(".aurora__icons");
  if (dotCanvas && dotCanvas.getContext) {
    var dctx = dotCanvas.getContext("2d");
    var canHover = window.matchMedia && matchMedia("(hover: hover) and (pointer: fine)").matches;
    var GRID = 22;
    var HALO = 110;                         // halo radius at full size (px)
    var dW = 0, dH = 0, dDPR = 1;
    var mx = -1e4, my = -1e4;              // smoothed pointer
    var tx = -1e4, ty = -1e4;              // real pointer
    var halo = 0, haloV = 0, haloTarget = 0, lastMove = 0;
    var dotRaf = 0, dotLast = 0;
    var liveIcons = [], updateIcons = null;     // icons currently on screen (filled in below)

    // Performance: the resting grid (a few thousand dots) is drawn once into a
    // hidden canvas. Each frame only the circle around the pointer, where dots
    // actually move, is redrawn; the rest is copied back from that snapshot.
    // Dots are pushed at most to 1.6 × the halo radius, so nothing outside that
    // circle ever changes.
    var baseDots = document.createElement("canvas"), bctx = baseDots.getContext("2d");
    var prevR = 0, prevX = 0, prevY = 0;            // circle that was redrawn last frame

    var sizeDots = function () {
      dDPR = Math.min(window.devicePixelRatio || 1, 2);
      dW = dotCanvas.clientWidth; dH = dotCanvas.clientHeight;
      dotCanvas.width = Math.round(dW * dDPR); dotCanvas.height = Math.round(dH * dDPR);
      dctx.setTransform(dDPR, 0, 0, dDPR, 0, 0);
      baseDots.width = dotCanvas.width; baseDots.height = dotCanvas.height;
      bctx.setTransform(dDPR, 0, 0, dDPR, 0, 0);
    };
    // Spotlight fade: the grid fades out towards the bottom and sides.
    var spot = function (gx, gy) {
      var ex = (gx - dW / 2) / (dW * 0.6), ey = (gy - dH * 0.2) / (dH * 0.9);
      var e = Math.sqrt(ex * ex + ey * ey);
      return e < 0.33 ? 1 : Math.max(0, 1 - (e - 0.33) / 0.6);
    };
    var dotStyle = function () {
      var dark = colors.dark;
      return { base: dark ? "255,255,255" : "30,35,48", a: dark ? 0.15 : 0.17 };
    };
    // Draw the dots whose grid position lies inside [x0,x1] × [y0,y1].
    var paintDots = function (c, x0, y0, x1, y1, withHalo) {
      var st = dotStyle(), r = Math.max(0.001, halo);
      var gx0 = GRID / 2 + Math.max(0, Math.ceil((x0 - GRID / 2) / GRID)) * GRID;
      var gy0 = GRID / 2 + Math.max(0, Math.ceil((y0 - GRID / 2) / GRID)) * GRID;
      var gxEnd = Math.min(dW + GRID, x1), gyEnd = Math.min(dH + GRID, y1);
      for (var gx = gx0; gx < dW + GRID && gx <= gxEnd; gx += GRID) {
        for (var gy = gy0; gy < dH + GRID && gy <= gyEnd; gy += GRID) {
          var a = spot(gx, gy);
          if (a <= 0.01) continue;
          var x = gx, y = gy, size = 1.1;
          if (withHalo) {
            var dx = gx - mx, dy = gy - my, d = Math.sqrt(dx * dx + dy * dy);
            if (d < r * 1.6) {
              // Push the dot outward; dots that end up inside the halo fade away,
              // and the ones on its rim glow a little brighter.
              var k = Math.max(0, 1 - d / (r * 1.6));
              var push = r * 0.7 * k * k;
              if (d > 0.01) { x += (dx / d) * push; y += (dy / d) * push; }
              var nd = d + push;
              if (nd < r) { a *= Math.max(0, (nd / r) - 0.55) / 0.45; }
              else if (nd < r * 1.3) { a = Math.min(1, a * 2.6); size = 1.7; }
            }
          }
          if (a <= 0.01) continue;
          c.fillStyle = "rgba(" + st.base + "," + (st.a * a).toFixed(3) + ")";
          c.beginPath();
          c.arc(x, y, size, 0, 6.2832);
          c.fill();
        }
      }
    };
    // Copy the resting grid back inside a circle (or everywhere when r is 0).
    var restore = function (cx, cy, r) {
      dctx.save();
      if (r) { dctx.beginPath(); dctx.arc(cx, cy, r, 0, 6.2832); dctx.clip(); }
      dctx.setTransform(1, 0, 0, 1, 0, 0);
      dctx.clearRect(0, 0, dotCanvas.width, dotCanvas.height);
      dctx.drawImage(baseDots, 0, 0);
      dctx.restore();
    };
    var renderBase = function () {
      bctx.clearRect(0, 0, dW, dH);
      paintDots(bctx, -GRID, -GRID, dW + GRID, dH + GRID, false);
      restore(0, 0, 0); prevR = 0;
    };
    var drawDots = function () {
      if (prevR) { restore(prevX, prevY, prevR); prevR = 0; }
      if (halo > 1) {
        var R = halo * 1.6 + 3;                       // everything that can move lies inside
        dctx.save();
        dctx.beginPath(); dctx.arc(mx, my, R, 0, 6.2832); dctx.clip();
        dctx.clearRect(mx - R - 1, my - R - 1, 2 * R + 2, 2 * R + 2);
        paintDots(dctx, mx - R - 2, my - R - 2, mx + R + 2, my + R + 2, true);
        dctx.restore();
        prevR = R + 1; prevX = mx; prevY = my;
      }
    };
    var dotLoop = function (now) {
      var dt = Math.min(0.033, (now - dotLast) / 1000 || 0.016);
      dotLast = now;
      // Halo opens while the mouse moves and closes shortly after it stops.
      haloTarget = (now - lastMove < 450) ? HALO : 0;
      haloV += (-160 * (halo - haloTarget) - 18 * haloV) * dt;   // springy open/close
      halo = Math.max(0, halo + haloV * dt);
      mx += (tx - mx) * Math.min(1, dt * 14);
      my += (ty - my) * Math.min(1, dt * 14);
      drawDots();
      if (updateIcons) updateIcons(now);
      if (halo > 0.5 || Math.abs(haloV) > 0.5 || haloTarget > 0 || liveIcons.length) { dotRaf = requestAnimationFrame(dotLoop); }
      else { dotRaf = 0; halo = 0; drawDots(); }
    };
    var wakeDots = function () {
      if (!dotRaf) { dotLast = performance.now(); dotRaf = requestAnimationFrame(dotLoop); }
    };

    sizeDots(); renderBase();
    dotCanvas.classList.add("is-on");
    window.addEventListener("resize", function () { sizeDots(); renderBase(); drawDots(); });
    // colors is refreshed by the observer above (registered first), then the grid is repainted.
    new MutationObserver(function () { renderBase(); drawDots(); }).observe(root, { attributes: true, attributeFilter: ["data-theme"] });

    if (layer && canHover && !calm) {
      var ICONS = [
        // Baby care: feeding bottle
        '<path d="M9 3h6M10 3v3l-2 3v11a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V9l-2-3V3"/><path d="M8 13h8M8 17h8"/>',
        // Bakery: loaf
        '<path d="M5 11a4 4 0 0 1 2-7.5c2 0 3 1 5 1s3-1 5-1A4 4 0 0 1 19 11v8a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1z"/><path d="M9 9v2M12 8v2M15 9v2"/>',
        // Beverages: cup with straw
        '<path d="M6 8h12l-1.5 12a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1z"/><path d="M12 8l2-5h3M6.5 12h11"/>',
        // Dairy & eggs: egg, milk carton
        '<path d="M12 3c3.5 0 6 5.5 6 10a6 6 0 0 1-12 0c0-4.5 2.5-10 6-10z"/>',
        '<path d="M8 3h8v3l2 3v12H6V9l2-3z"/><path d="M6 9h12M10 13h4"/>',
        // Frozen: snowflake
        '<path d="M12 2v20M4.5 6.5l15 11M19.5 6.5l-15 11"/><path d="m9 4 3 2 3-2M9 20l3-2 3 2"/>',
        // Fruit & vegetables: apple, carrot
        '<path d="M12 7c-2-2-7-1.5-7 4 0 4 3 9 5 9 1 0 1.3-.5 2-.5s1 .5 2 .5c2 0 5-5 5-9 0-5.5-5-6-7-4z"/><path d="M12 7c0-2 1-4 3-4"/>',
        '<path d="M15 9 4 20l1.5-6.5L12 7z"/><path d="M15 9c1-2 3-3 5-3M15 9c2-1 3-3 3-5M8 15l1.5 1.5M10 12l1.5 1.5"/>',
        // Groceries: basket
        '<path d="M3 9h18l-2 10a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1z"/><path d="M8 9l3-5M16 9l-3-5M9 13v4M15 13v4M12 13v4"/>',
        // Household: spray bottle
        '<path d="M8 10h7v10a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1z"/><path d="M9 10V7h5v3M14 7h3l2-2M18 9h2M18 11.5l1.5 1"/>',
        // Medicine: capsule
        '<rect x="3" y="9" width="18" height="7" rx="3.5" transform="rotate(-35 12 12.5)"/><path d="m9.4 8.6 5 6"/>',
        // Personal care: pump bottle
        '<path d="M8 10h8v10a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1z"/><path d="M10 10V7h4v3M12 7V4h4M10.5 15h3"/>'
      ].map(function (body) {
        return 'url("data:image/svg+xml,' + encodeURIComponent(
          '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" ' +
          'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + body + "</svg>") + '")';
      });
      // Each icon pops OUT of the halo's centre to a random spot, hovers for a
      // moment, then is pulled BACK into the halo (wherever it is by then) and
      // disappears into it.
      var MAX = 14, lastSpawn = 0, lastIcon = -1;
      var OUT = 380, HOLD = 420, BACK = 520;            // ms for each phase
      var LIFE = OUT + HOLD + BACK;
      var backOut = function (p) { var c = 1.9; p -= 1; return 1 + (c + 1) * p * p * p + c * p * p; };
      var easeIn = function (p) { return p * p * p; };

      var spawnIcon = function () {
        var now = performance.now();
        if (liveIcons.length >= MAX || now - lastSpawn < 110 || halo < HALO * 0.45) return;
        lastSpawn = now;
        var ang = Math.random() * Math.PI * 2;
        var dist = (0.35 + Math.random() * 0.4) * halo;     // somewhere inside the halo
        var pick;
        do { pick = Math.floor(Math.random() * ICONS.length); } while (pick === lastIcon && ICONS.length > 1);
        lastIcon = pick;
        var el = document.createElement("span");
        el.className = "aurora__icon";
        el.style.cssText = "-webkit-mask-image:" + ICONS[pick] + ";mask-image:" + ICONS[pick] + ";" +
          "--g:" + Math.round(100 + Math.random() * 120) + "deg";
        layer.appendChild(el);
        liveIcons.push({
          el: el, born: now,
          cx: mx, cy: my,                                   // where it came out of
          ox: Math.cos(ang) * dist, oy: Math.sin(ang) * dist,
          rot: (Math.random() - 0.5) * 70,
          size: 0.9 + Math.random() * 0.45,
          bob: Math.random() * 6.28
        });
        wakeDots();
      };

      updateIcons = function (now) {
        for (var i = liveIcons.length - 1; i >= 0; i--) {
          var ic = liveIcons[i], t = Math.max(0, now - ic.born), x, y, sc, rot, op;
          var outX = ic.cx + ic.ox, outY = ic.cy + ic.oy;
          if (t < OUT) {                       // 1. pop out of the halo centre
            var p = backOut(t / OUT);
            x = ic.cx + ic.ox * p; y = ic.cy + ic.oy * p;
            sc = ic.size * Math.max(0, p); rot = ic.rot * (1 - p);
            op = Math.min(1, t / (OUT * 0.35));
          } else if (t < OUT + HOLD) {         // 2. hover gently
            var h = (t - OUT) / HOLD;
            x = outX; y = outY + Math.sin(ic.bob + h * 3.2) * 2.5;
            sc = ic.size; rot = 0; op = 1;
          } else if (t < LIFE) {               // 3. get pulled back into the halo
            var b = easeIn((t - OUT - HOLD) / BACK);
            x = outX + (mx - outX) * b; y = outY + (my - outY) * b;
            sc = ic.size * (1 - b); rot = -ic.rot * 0.6 * b;
            op = b > 0.8 ? (1 - b) / 0.2 : 1;
          } else {
            ic.el.remove(); liveIcons.splice(i, 1); continue;
          }
          ic.el.style.opacity = op.toFixed(3);
          ic.el.style.transform = "translate3d(" + x.toFixed(1) + "px," + y.toFixed(1) + "px,0) " +
            "scale(" + Math.max(0, sc).toFixed(3) + ") rotate(" + rot.toFixed(1) + "deg)";
        }
      };
      window.addEventListener("pointermove", function (e) {
        tx = e.clientX; ty = e.clientY;
        if (mx < -1000) { mx = tx; my = ty; }      // first move: start the halo under the pointer
        lastMove = performance.now();
        wakeDots();
        spawnIcon();
      }, { passive: true });
      document.addEventListener("pointerleave", function () { lastMove = 0; });
    }
  }
})();
