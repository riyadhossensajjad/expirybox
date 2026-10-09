// ExpiryBox — fill the "Add item" form by scanning a QR code.
//
// Uses the browser's built-in BarcodeDetector when it has one (Chrome on Android,
// macOS, ChromeOS) and falls back to the bundled jsQR decoder everywhere else
// (Windows, Firefox, Safari). People without a camera can upload a photo of the code.
//
// Understands:
//   • ExpiryBox labels and any JSON:   {"name": "...", "expiry": "2026-10-12", "price": 120, ...}
//   • GS1 codes on medicine/food:      (01)GTIN (17)YYMMDD expiry (10)batch, raw or in a GS1 Digital Link URL
//   • "Key: value" text, one per line: Name: Milk / Expiry: 12/10/2026 / Price: 95
//   • URLs with query parameters:      ...?name=Milk&exp=2026-10-12&price=95
//   • Anything else becomes the item name (or a link in the description).
(function () {
  "use strict";
  var root = document.querySelector("[data-qr]");
  if (!root) return;

  var $ = function (s, el) { return (el || document).querySelector(s); };
  var form = root.closest("form") || document.querySelector("form.form");
  var modal = $("#qr-modal");
  var video = $("video", modal);
  var statusEl = $("[data-qr-status]", modal);
  var fileInput = $("[data-qr-file]", modal);
  var resultBox = $("[data-qr-result]");
  var jsqrSrc = root.getAttribute("data-jsqr-src");
  var canvas = document.createElement("canvas");
  var ctx = canvas.getContext("2d", { willReadFrequently: true });
  var stream = null, rafId = null, detector = null, lastTick = 0, busy = false;
  var HINT_AFTER = 2000, searchingSince = 0;

  /* ------------------------------------------------------------------ decoding */
  var loadJsQR = function () {
    if (window.jsQR) return Promise.resolve(window.jsQR);
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = jsqrSrc;
      s.onload = function () { resolve(window.jsQR); };
      s.onerror = reject;
      document.head.appendChild(s);
    });
  };
  var getDetector = function () {
    if (detector !== null) return Promise.resolve(detector);
    if (!("BarcodeDetector" in window)) { detector = false; return Promise.resolve(false); }
    return window.BarcodeDetector.getSupportedFormats().then(function (formats) {
      var wanted = ["qr_code", "data_matrix"].filter(function (f) { return formats.indexOf(f) >= 0; });
      detector = wanted.length ? new window.BarcodeDetector({ formats: wanted }) : false;
      return detector;
    }).catch(function () { detector = false; return false; });
  };
  // Decode a video frame or image. Resolves with the text or null.
  var decode = function (source, w, h) {
    return getDetector().then(function (det) {
      if (det) {
        return det.detect(source).then(function (codes) {
          return codes.length ? codes[0].rawValue : null;
        }).catch(function () { return null; });
      }
      return loadJsQR().then(function (jsQR) {
        var scale = Math.min(1, 900 / Math.max(w, h));
        canvas.width = Math.round(w * scale);
        canvas.height = Math.round(h * scale);
        ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
        var img = ctx.getImageData(0, 0, canvas.width, canvas.height);
        var code = jsQR(img.data, img.width, img.height, { inversionAttempts: "attemptBoth" });
        return code ? code.data : null;
      });
    });
  };

  /* ------------------------------------------------------------------ parsing */
  var pad = function (n) { return (n < 10 ? "0" : "") + n; };
  var iso = function (y, m, d) {
    if (!y || !m || m < 1 || m > 12) return "";
    if (y < 100) y += 2000;
    var last = new Date(y, m, 0).getDate();
    if (!d || d > last) d = last; // "00" day or month-only dates mean end of month
    return y + "-" + pad(m) + "-" + pad(d);
  };
  var MONTHS = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, sept: 9, oct: 10, nov: 11, dec: 12 };
  var parseDate = function (raw) {
    if (!raw) return "";
    var v = String(raw).trim(), m;
    if ((m = v.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/))) return iso(+m[1], +m[2], +m[3]);
    if ((m = v.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})$/))) return iso(+m[3], +m[2], +m[1]); // day first (BD style)
    if ((m = v.match(/^(\d{2})(\d{2})(\d{2})$/))) return iso(+m[1], +m[2], +m[3]);                // GS1 YYMMDD
    if ((m = v.match(/^(\d{1,2})[-/.](\d{4})$/))) return iso(+m[2], +m[1], 0);                    // MM/YYYY
    if ((m = v.match(/^(\d{1,2})?\s*([a-z]{3,9})\.?,?\s*(\d{2,4})$/i))) {
      var mo = MONTHS[m[2].slice(0, 3).toLowerCase()];
      if (mo) return iso(+m[3], mo, m[1] ? +m[1] : 0);
    }
    if ((m = v.match(/^([a-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})$/i)) && MONTHS[m[1].slice(0, 3).toLowerCase()]) {
      return iso(+m[3], MONTHS[m[1].slice(0, 3).toLowerCase()], +m[2]);
    }
    return "";
  };
  var parsePrice = function (raw) {
    if (raw === undefined || raw === null || raw === "") return "";
    var n = parseFloat(String(raw).replace(/,/g, "").replace(/[^\d.]/g, ""));
    return isFinite(n) && n >= 0 ? String(Math.round(n * 100) / 100) : "";
  };

  var KEYS = {
    name: ["name", "item", "item_name", "itemname", "product", "product_name", "title"],
    expiry: ["expiry", "expiry_date", "expiration", "expiration_date", "exp", "expires", "exp_date", "best_before", "bestbefore", "bb", "use_by", "useby"],
    price: ["price", "value", "mrp", "cost", "amount"],
    category: ["category", "type"],
    provider: ["provider", "brand", "shop", "store", "seller", "manufacturer", "maker", "from"],
    batch: ["batch", "lot", "batch_no", "lot_no", "batch_number", "reference", "reference_number", "ref", "receipt"],
    purchase: ["purchase", "purchase_date", "purchased", "bought", "bought_on"],
    description: ["description", "desc", "notes", "note", "details"]
  };
  var normKey = function (k) { return String(k).toLowerCase().trim().replace(/[\s.-]+/g, "_"); };
  var fromPairs = function (pairs) {
    var out = {}, extra = [];
    Object.keys(pairs).forEach(function (rawKey) {
      var k = normKey(rawKey), val = pairs[rawKey], hit = false;
      if (val === null || val === undefined || typeof val === "object") return;
      Object.keys(KEYS).forEach(function (field) {
        if (!hit && KEYS[field].indexOf(k) >= 0) { out[field] = String(val).trim(); hit = true; }
      });
      if (!hit && /^(gtin|ean|upc|barcode|mfg|mfd|manufactured|production)/.test(k)) extra.push(rawKey + ": " + val);
    });
    if (extra.length) out.description = [out.description, extra.join("\n")].filter(Boolean).join("\n");
    return out;
  };

  // GS1 Application Identifiers we care about; fixed lengths where defined.
  var GS1_FIXED = { "00": 18, "01": 14, "02": 14, "11": 6, "12": 6, "13": 6, "15": 6, "16": 6, "17": 6 };
  var parseGS1 = function (text) {
    var t = text.replace(/^\][A-Za-z]\d/, ""); // symbology prefix like ]Q3 or ]d2
    var ai = {};
    if (/^\(\d{2,4}\)/.test(t)) {
      var re = /\((\d{2,4})\)([^(]*)/g, m;
      while ((m = re.exec(t))) ai[m[1]] = m[2].trim();
    } else if (/^(01|02)\d{14}/.test(t) || t.indexOf("\x1d") >= 0) {
      var i = 0, guard = 0;
      while (i < t.length && guard++ < 20) {
        if (t[i] === "\x1d") { i++; continue; }
        var code = t.substr(i, 2);
        if (GS1_FIXED[code]) { ai[code] = t.substr(i + 2, GS1_FIXED[code]); i += 2 + GS1_FIXED[code]; }
        else {
          var end = t.indexOf("\x1d", i + 2);
          if (end < 0) end = t.length;
          ai[code] = t.slice(i + 2, end);
          i = end;
        }
      }
    }
    if (!Object.keys(ai).length) return null;
    var out = {};
    var exp = ai["17"] || ai["15"] || ai["16"] || ai["12"];
    if (exp) out.expiry = exp;
    if (ai["10"]) out.batch = ai["10"];
    var notes = [];
    if (ai["01"]) notes.push("GTIN: " + ai["01"]);
    if (ai["21"]) notes.push("Serial: " + ai["21"]);
    if (ai["11"]) notes.push("Produced: " + (parseDate(ai["11"]) || ai["11"]));
    if (notes.length) out.description = notes.join("\n");
    return out.expiry || out.batch || notes.length ? out : null;
  };

  var parseUrl = function (text) {
    var u;
    try { u = new URL(text); } catch (e) { return null; }
    if (!/^https?:$/.test(u.protocol)) return null;
    // GS1 Digital Link: /01/<gtin>/10/<batch>?17=YYMMDD
    var segs = u.pathname.split("/").filter(Boolean), ai = [], params = {};
    for (var i = 0; i + 1 < segs.length; i++) {
      if (/^\d{2,4}$/.test(segs[i])) { ai.push("(" + segs[i] + ")" + decodeURIComponent(segs[i + 1])); i++; }
    }
    u.searchParams.forEach(function (v, k) {
      if (/^\d{2,4}$/.test(k)) ai.push("(" + k + ")" + v); else params[k] = v;
    });
    var out = ai.length ? (parseGS1(ai.join("")) || {}) : {};
    var named = fromPairs(params);
    Object.keys(named).forEach(function (k) { if (!out[k]) out[k] = named[k]; });
    if (!out.name && !out.expiry && !out.price) {
      return { description: "Scanned link: " + text, onlyLink: true };
    }
    return out;
  };

  var parseKeyValues = function (text) {
    var pairs = {}, count = 0;
    text.split(/\r?\n|;|\|/).forEach(function (line) {
      var m = line.match(/^\s*([A-Za-z][A-Za-z _.-]{0,30})\s*[:=]\s*(.+?)\s*$/);
      if (m) { pairs[m[1]] = m[2]; count++; }
    });
    return count ? fromPairs(pairs) : null;
  };

  var parseQR = function (text) {
    var t = String(text || "").trim();
    if (!t) return {};
    if (t[0] === "{") {
      try { var obj = JSON.parse(t); if (obj && typeof obj === "object") return fromPairs(obj); } catch (e) {}
    }
    return parseUrl(t) || parseGS1(t) || parseKeyValues(t) || { name: t.split(/\r?\n/)[0].slice(0, 150) };
  };

  /* ------------------------------------------------------------------ filling the form */
  var field = function (name) { return form.querySelector("[name=" + name + "]"); };
  var setValue = function (name, value, filled) {
    var el = field(name);
    if (!el || value === "" || value === undefined) return;
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    var box = el.closest(".field") || el;
    box.classList.remove("is-filled");
    void box.offsetWidth;
    box.classList.add("is-filled");
    var label = el.closest(".field") && el.closest(".field").querySelector(".field__label");
    filled.push((label ? label.firstChild.textContent : name).trim().replace(/\.+$/, "").toLowerCase());
  };
  var pickCategory = function (name) {
    var sel = field("category");
    if (!sel || !name) return "";
    var want = name.toLowerCase();
    for (var i = 0; i < sel.options.length; i++) {
      var opt = sel.options[i].text.toLowerCase();
      if (sel.options[i].value && (opt === want || opt.indexOf(want) >= 0 || want.indexOf(opt.split(" ")[0]) >= 0)) return sel.options[i].value;
    }
    return "";
  };
  var apply = function (text) {
    var data = parseQR(text), filled = [];
    setValue("item_name", data.name ? data.name.slice(0, 150) : "", filled);
    setValue("expiry_date", parseDate(data.expiry), filled);
    setValue("price", parsePrice(data.price), filled);
    setValue("category", pickCategory(data.category), filled);
    setValue("purchase_date", parseDate(data.purchase), filled);
    setValue("provider", data.provider ? data.provider.slice(0, 120) : "", filled);
    setValue("reference_number", data.batch ? data.batch.slice(0, 80) : "", filled);
    if (data.description) {
      var desc = field("description");
      if (desc) setValue("description", desc.value ? desc.value + "\n" + data.description : data.description, filled);
    }
    var missing = [];
    if (!field("item_name").value) missing.push("name");
    if (!field("expiry_date").value) missing.push("expiry date");
    if (!field("price").value) missing.push("price");

    var msg;
    if (!filled.length) msg = "The code was read, but it didn't contain item details.";
    else if (data.onlyLink) msg = "This QR code only holds a link, so we saved it in Description.";
    else msg = "Filled " + filled.length + " field" + (filled.length === 1 ? "" : "s") + " from the QR code: " + filled.join(", ") + ".";
    if (missing.length) msg += " Add the " + missing.join(" and ") + " before saving.";
    else msg += " Check them, then press Add item.";
    resultBox.querySelector("p").textContent = msg;
    resultBox.classList.toggle("callout--ok", !missing.length);
    resultBox.hidden = false;
    var target = missing.length ? field(missing[0] === "name" ? "item_name" : missing[0] === "price" ? "price" : "expiry_date") : null;
    if (target) setTimeout(function () { target.focus(); }, 150);
  };

  /* ------------------------------------------------------------------ camera modal */
  var setStatus = function (text, tone) {
    statusEl.textContent = text;
    statusEl.setAttribute("data-tone", tone || "");
  };
  var stopCamera = function () {
    modal.classList.remove("is-searching");
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    stream = null;
    video.srcObject = null;
  };
  var close = function () {
    stopCamera();
    modal.classList.remove("is-open");
    setTimeout(function () { modal.hidden = true; }, 200);
    document.removeEventListener("keydown", onKey);
  };
  var onKey = function (e) { if (e.key === "Escape") close(); };
  var found = function (text) {
    modal.classList.add("is-found");
    setStatus("Code found", "ok");
    if (navigator.vibrate) navigator.vibrate(40);
    // Let the gradient tick draw and glow before the form fills in.
    setTimeout(function () {
      close();
      setTimeout(function () { modal.classList.remove("is-found"); }, 250);
      apply(text);
    }, 1150);
  };
  var loop = function (now) {
    rafId = requestAnimationFrame(loop);
    if (busy || now - lastTick < 120 || video.readyState < 2) return;
    lastTick = now;
    busy = true;
    decode(video, video.videoWidth, video.videoHeight).then(function (text) {
      busy = false;
      if (text && stream) { stopCamera(); found(text); return; }
      if (!searchingSince) searchingSince = now;
      if (stream) modal.classList.toggle("is-searching", now - searchingSince > HINT_AFTER);
    }, function () { busy = false; });
  };
  var open = function () {
    modal.hidden = false;
    requestAnimationFrame(function () { modal.classList.add("is-open"); });
    document.addEventListener("keydown", onKey);
    modal.classList.remove("is-found", "no-camera");
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      modal.classList.add("no-camera");
      setStatus(window.isSecureContext ? "This browser can't use the camera. Upload a photo of the code instead."
        : "The camera only works on https:// or localhost. Upload a photo of the code instead.", "warn");
      return;
    }
    setStatus("Starting camera…");
    navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } }, audio: false })
      .then(function (s) {
        stream = s;
        video.srcObject = s;
        return video.play();
      })
      .then(function () {
        setStatus("Point the camera at the QR code");
        loadJsQR().catch(function () {}); // warm up the fallback decoder
        searchingSince = 0;
        rafId = requestAnimationFrame(loop);
      })
      .catch(function (err) {
        modal.classList.add("no-camera");
        setStatus(err && err.name === "NotAllowedError"
          ? "Camera access was blocked. Allow it in the address bar, or upload a photo of the code."
          : "No camera found. Upload a photo of the code instead.", "warn");
      });
  };

  fileInput.addEventListener("change", function () {
    var file = fileInput.files && fileInput.files[0];
    if (!file) return;
    setStatus("Reading the photo…");
    var img = new Image();
    img.onload = function () {
      decode(img, img.naturalWidth, img.naturalHeight).then(function (text) {
        URL.revokeObjectURL(img.src);
        if (text) { stopCamera(); found(text); }
        else setStatus("No QR code found in that photo. Try a sharper, closer picture.", "warn");
      });
    };
    img.onerror = function () { setStatus("That file isn't an image we can read.", "warn"); };
    img.src = URL.createObjectURL(file);
    fileInput.value = "";
  });
  root.addEventListener("click", open);
  modal.addEventListener("click", function (e) { if (e.target === modal || e.target.closest("[data-qr-close]")) close(); });
  if (resultBox) resultBox.querySelector("button").addEventListener("click", function () { resultBox.hidden = true; });

  // Exposed for the test page / console: ExpiryBoxQR.parse("...")
  window.ExpiryBoxQR = { parse: parseQR, parseDate: parseDate, apply: apply };
})();
