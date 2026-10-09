// ExpiryBox — front-end behaviour. Every page still works without JavaScript.
(function () {
  "use strict";
  var root = document.documentElement;
  var body = document.body;
  var $ = function (s, el) { return (el || document).querySelector(s); };
  var $$ = function (s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); };
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };

  /* ---------------------------------------------------------- light / dark */
  $$("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      store.set("sl-theme", next);
    });
  });

  /* ---------------------------------------------------------- mobile sidebar */
  var openNav = $("[data-nav-open]");
  if (openNav) openNav.addEventListener("click", function () { body.classList.add("nav-open"); });
  $$("[data-nav-close]").forEach(function (el) {
    el.addEventListener("click", function () { body.classList.remove("nav-open"); });
  });

  /* ---------------------------------------------------------- fluid sidebar */
  // Navigation is never delayed: Chrome/Edge prerender the page while you hover a
  // link, so it opens instantly. The motion happens on the page you land on:
  // the highlight slides over from the item you came from and the sidebar does
  // one springy stretch on the GPU.
  var sidebar = $("#sidebar");
  var calm = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var isDrawer = function () { return window.matchMedia && matchMedia("(max-width: 860px)").matches; };
  if (sidebar) {
    var nav = $(".side-nav", sidebar);
    var pill = $(".side-nav__pill", sidebar);
    var placePill = function (link, animate) {
      if (!pill || !link) { if (pill) pill.classList.remove("is-ready"); return; }
      pill.classList.toggle("is-sliding", !!animate);
      pill.style.setProperty("--pill-y", link.offsetTop + "px");
      pill.style.setProperty("--pill-h", link.offsetHeight + "px");
      pill.classList.add("is-ready");
    };
    var arrive = function () {
      var current = $(".side-nav a.is-active", sidebar);
      var from = null;
      try {
        from = JSON.parse(sessionStorage.getItem("sl-nav-from") || "null");
        sessionStorage.removeItem("sl-nav-from");
      } catch (e) {}
      var fresh = from && Date.now() - from.t < 8000;
      if (fresh && current && !calm && !isDrawer()) {
        // Start where the old highlight was, then slide to the new item.
        pill.style.setProperty("--pill-y", from.y + "px");
        pill.style.setProperty("--pill-h", from.h + "px");
        pill.classList.add("is-ready");
        void pill.offsetWidth;
        requestAnimationFrame(function () { placePill(current, true); });
      } else {
        placePill(current, false);
      }
      // Continue the squish exactly where the previous page left it, so the
      // stretch and the spring back read as one movement across the page change.
      var t0 = 0;
      try { t0 = +sessionStorage.getItem("sl-squish") || 0; sessionStorage.removeItem("sl-squish"); } catch (e) {}
      var elapsed = Date.now() - t0;
      if (t0 && elapsed < SQUISH_MS && !calm && !isDrawer()) squish(elapsed);
    };
    var SQUISH_MS = 600;
    var squish = function (offset) {
      sidebar.classList.remove("is-squish");
      sidebar.style.animationDelay = offset ? (-offset) + "ms" : "";
      void sidebar.offsetWidth;
      sidebar.classList.add("is-squish");
    };
    sidebar.addEventListener("animationend", function (e) {
      if (e.target === sidebar) { sidebar.classList.remove("is-squish"); sidebar.style.animationDelay = ""; }
    });
    $$(".side-nav a", sidebar).forEach(function (link) {
      link.addEventListener("click", function (e) {
        if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        if (calm || link.classList.contains("is-active")) return;
        // Play the whole stretch and the highlight slide here, then open the page.
        // The next page simply shows the highlight in place, so nothing jumps.
        e.preventDefault();
        // Start loading the next page right away, while the menu animates.
        try {
          var sr = document.createElement("script");
          sr.type = "speculationrules";
          sr.textContent = JSON.stringify({ prerender: [{ source: "list", urls: [link.href], eagerness: "immediate" }] });
          document.head.appendChild(sr);
        } catch (err) {}
        var pf = document.createElement("link");
        pf.rel = "prefetch"; pf.href = link.href;
        document.head.appendChild(pf);
        squish(0);
        squish(0);
        $$(".side-nav a.is-active", sidebar).forEach(function (a) { a.classList.remove("is-active"); });
        link.classList.add("is-active");
        placePill(link, true);
        var href = link.href;
        var done = false;
        var go = function () { if (!done) { done = true; window.location.href = href; } };
        sidebar.addEventListener("animationend", function (ev) { if (ev.target === sidebar) go(); });
        setTimeout(go, SQUISH_MS + 300);   // safety net if the animation is skipped
      });
    });
    // When the page actually unloads, remember where the highlight is on screen
    // right now, so the next page continues the slide from exactly there.
    window.addEventListener("pagehide", function () {
      var raw;
      try { raw = sessionStorage.getItem("sl-nav-from"); } catch (e) { return; }
      if (!raw || !pill) return;
      var from = JSON.parse(raw);
      var m = getComputedStyle(pill).transform.match(/matrix\(([^)]+)\)/);
      if (m) from.y = parseFloat(m[1].split(",")[5]) || from.y;
      from.h = pill.offsetHeight || from.h;
      try { sessionStorage.setItem("sl-nav-from", JSON.stringify(from)); } catch (e) {}
    });
    // A prerendered page must wait until it's actually shown before animating.
    if (document.prerendering) {
      document.addEventListener("prerenderingchange", arrive, { once: true });
    } else {
      arrive();
    }
    window.addEventListener("pageshow", function (e) { if (e.persisted) placePill($(".side-nav a.is-active", sidebar), false); });
    window.addEventListener("resize", function () { placePill($(".side-nav a.is-active", sidebar), false); });
  }

  /* ---------------------------------------------------------- success tick */
  var celebrate = $("[data-celebrate]");
  if (celebrate) {
    var closeCelebrate = function () {
      if (!celebrate.isConnected || celebrate.classList.contains("is-leaving")) return;
      celebrate.classList.add("is-leaving");
      setTimeout(function () { celebrate.remove(); }, 350);
    };
    var startCelebrate = function () {
      celebrate.addEventListener("click", closeCelebrate);
      document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeCelebrate(); }, { once: true });
      setTimeout(closeCelebrate, calm ? 1200 : 2000);
    };
    if (document.prerendering) document.addEventListener("prerenderingchange", startCelebrate, { once: true });
    else startCelebrate();
  }

  /* ---------------------------------------------------------- notification popover */
  var popover = $("#note-popover");
  var bell = $("[data-popover-toggle]");
  function setPopover(open) {
    if (!popover) return;
    popover.hidden = !open;
    bell.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) body.classList.remove("nav-open");
  }
  if (bell && popover) {
    bell.addEventListener("click", function (e) { e.stopPropagation(); setPopover(popover.hidden); });
    popover.addEventListener("click", function (e) { e.stopPropagation(); });
  }
  document.addEventListener("click", function (e) {
    setPopover(false);
    $$("details.menu[open]").forEach(function (d) { if (!d.contains(e.target)) d.removeAttribute("open"); });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { setPopover(false); body.classList.remove("nav-open"); }
  });

  /* ---------------------------------------------------------- toasts */
  var toastBox = $("[data-toasts]");
  function dismiss(t) {
    if (!t || t.classList.contains("is-leaving")) return;
    t.classList.add("is-leaving");
    setTimeout(function () { t.remove(); }, 300);
  }
  function arm(t, ms) {
    var close = $(".toast__close", t);
    if (close) close.addEventListener("click", function () { dismiss(t); });
    if (ms) {
      var bar = document.createElement("span");
      bar.className = "toast__timer";
      bar.style.animationDuration = ms + "ms";
      t.appendChild(bar);
      var timer = setTimeout(function () { dismiss(t); }, ms);
      t.addEventListener("mouseenter", function () { clearTimeout(timer); bar.style.animationPlayState = "paused"; });
      t.addEventListener("mouseleave", function () { bar.style.animationPlayState = "running"; timer = setTimeout(function () { dismiss(t); }, 2500); });
    }
  }
  $$(".toast", toastBox).forEach(function (t, i) {
    arm(t, t.classList.contains("toast--error") ? 0 : 4500 + i * 500);
  });

  var ICONS = {
    EXPIRY: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    EXPIRED: '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/>',
    PAYMENT: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18"/>',
    REVIEW: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.2l1-6.2L3 9.6l6.2-.9z"/>',
    ORDER: '<path d="M5 8h14l-1 13H6z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    SYSTEM: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>'
  };
  function svg(path) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + path + "</svg>";
  }
  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }
  function popNotification(n) {
    var t = document.createElement("div");
    t.className = "toast toast--note";
    t.innerHTML =
      '<span class="note-icon" data-type="' + esc(n.type) + '">' + svg(ICONS[n.type] || ICONS.SYSTEM) + "</span>" +
      '<div class="toast__body">' +
        '<div class="toast__title">' + esc(n.title) + "<span>" + esc(n.time) + "</span></div>" +
        '<p class="toast__msg">' + esc(n.message) + "</p>" +
        '<a class="toast__action" href="' + esc(n.url) + '">View</a>' +
      "</div>" +
      '<button type="button" class="toast__close" aria-label="Dismiss">' + svg('<path d="M6 6l12 12M18 6 6 18"/>') + "</button>";
    toastBox.appendChild(t);
    arm(t, 9000);
    // Also show a system notification when the tab is in the background and the user allowed it.
    if (document.hidden && "Notification" in window && Notification.permission === "granted") {
      try {
        var sys = new Notification(n.title, { body: n.message, tag: "shelflife-" + n.id });
        sys.onclick = function () { window.focus(); location.href = n.url; };
      } catch (e) {}
    }
  }

  /* ---------------------------------------------------------- live notifications */
  var feedUrl = body.getAttribute("data-feed-url");
  if (feedUrl && toastBox) {
    var key = "sl-last-popped-" + body.getAttribute("data-user");
    var lastId = parseInt(store.get(key) || "0", 10);
    var firstRun = !store.get(key);
    var bellBadge = $("[data-unread]");
    var unreadPill = $("[data-unread-pill]");

    var poll = function () {
      fetch(feedUrl + "?after=" + lastId, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (!data) return;
          if (bellBadge) {
            bellBadge.textContent = data.unread;
            bellBadge.hidden = !data.unread;
          }
          if (unreadPill) unreadPill.textContent = data.unread + " new";
          var items = data.items || [];
          // On the very first visit only show the latest three, not a backlog.
          if (firstRun) items = items.slice(-3);
          items.forEach(function (n, i) {
            setTimeout(function () { popNotification(n); }, 350 * i);
            if (n.id > lastId) lastId = n.id;
          });
          if (items.length && bell) {
            bell.classList.remove("is-ringing");
            void bell.offsetWidth;
            bell.classList.add("is-ringing");
          }
          firstRun = false;
          store.set(key, String(lastId));
        })
        .catch(function () {});
    };
    setTimeout(poll, 900);
    setInterval(function () { if (!document.hidden || "Notification" in window) poll(); }, 15000);
  }

  // "Turn on desktop alerts" button on the notifications page.
  var alertBtn = $("[data-desktop-alerts]");
  if (alertBtn) {
    if (!("Notification" in window)) alertBtn.hidden = true;
    else if (Notification.permission === "granted") { alertBtn.disabled = true; alertBtn.lastChild.textContent = "Desktop alerts on"; }
    alertBtn.addEventListener("click", function () {
      Notification.requestPermission().then(function (p) {
        if (p === "granted") { alertBtn.disabled = true; alertBtn.lastChild.textContent = "Desktop alerts on"; }
      });
    });
  }

  /* ---------------------------------------------------------- share shop link */
  $$("[data-share]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var url = btn.getAttribute("data-share");
      var done = function () {
        var t = document.createElement("div");
        t.className = "toast toast--success";
        t.innerHTML = '<span class="toast__icon">' + svg('<path d="m5 12.5 4.5 4.5L19 7"/>') + '</span><div class="toast__body"><p>Shop link copied. Paste it anywhere to share.</p></div>';
        toastBox.appendChild(t);
        arm(t, 3500);
      };
      if (navigator.share && /Mobi/.test(navigator.userAgent)) {
        navigator.share({ title: "My ExpiryBox shop", url: url }).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(done, function () { prompt("Copy your shop link:", url); });
      } else {
        prompt("Copy your shop link:", url);
      }
    });
  });

  /* ---------------------------------------------------------- live search suggestions */
  var searchForm = $("[data-suggest-url]");
  if (searchForm) {
    var sInput = $("input[name=q]", searchForm);
    var panel = $("#search-suggest");
    var sUrl = searchForm.getAttribute("data-suggest-url");
    var timer = null, ctrl = null, activeIdx = -1, lastQuery = null;

    var options = function () { return $$(".suggest__item, .suggest__all", panel); };
    var openPanel = function (open) {
      panel.hidden = !open;
      sInput.setAttribute("aria-expanded", open ? "true" : "false");
      if (!open) { activeIdx = -1; sInput.removeAttribute("aria-activedescendant"); }
    };
    var setActive = function (i) {
      var opts = options();
      if (!opts.length) return;
      activeIdx = (i + opts.length) % opts.length;
      opts.forEach(function (o, n) { o.classList.toggle("is-active", n === activeIdx); o.setAttribute("aria-selected", n === activeIdx ? "true" : "false"); });
      var cur = opts[activeIdx];
      sInput.setAttribute("aria-activedescendant", cur.id);
      cur.scrollIntoView({ block: "nearest" });
    };
    // Wrap the matching part of a name in <mark>, escaping everything else.
    var highlight = function (text, q) {
      var i = text.toLowerCase().indexOf(q.toLowerCase());
      if (i < 0 || !q) return esc(text);
      return esc(text.slice(0, i)) + "<mark>" + esc(text.slice(i, i + q.length)) + "</mark>" + esc(text.slice(i + q.length));
    };
    var render = function (data) {
      var q = data.query;
      var allUrl = searchForm.action + "?q=" + encodeURIComponent(q);
      var html = "";
      if (data.results.length) {
        html += '<div class="suggest__label">Your items</div>';
        data.results.forEach(function (r, n) {
          var pic = r.image
            ? '<img src="' + esc(r.image) + '" alt="" loading="lazy">'
            : esc(r.initial);
          var sub = [];
          if (r.category) sub.push(esc(r.category));
          sub.push(esc(r.when));
          if (r.status) sub.push(esc(r.status));
          html +=
            '<a class="suggest__item" role="option" id="sg-' + n + '" href="' + esc(r.url) + '">' +
              '<span class="suggest__pic" data-tone="' + esc(r.tone) + '">' + pic + "</span>" +
              '<span class="suggest__main">' +
                '<span class="suggest__name">' + highlight(r.name, q) + "</span>" +
                '<span class="suggest__sub"><span class="suggest__dot" data-tone="' + esc(r.tone) + '"></span>' + sub.join(" · ") + "</span>" +
              "</span>" +
              (r.price ? '<span class="suggest__price">' + esc(r.price) + "</span>" : "") +
            "</a>";
        });
        html += '<a class="suggest__all" role="option" id="sg-all" href="' + esc(allUrl) + '"><span>' +
          (data.total > data.results.length ? "See all " + data.total + " results" : "Show these in My items") +
          '</span>' + svg('<path d="m9 6 6 6-6 6"/>') + "</a>";
      } else {
        html = '<div class="suggest__empty">No items match “' + esc(q) + '”. <a href="/items/new/">Add it as a new item</a></div>';
      }
      panel.innerHTML = html;
      activeIdx = -1;
      openPanel(true);
    };
    var fetchSuggestions = function () {
      var q = sInput.value.trim();
      if (!q) { openPanel(false); lastQuery = null; return; }
      if (q === lastQuery && panel.innerHTML) { openPanel(true); return; }
      lastQuery = q;
      if (ctrl) ctrl.abort();
      ctrl = "AbortController" in window ? new AbortController() : null;
      fetch(sUrl + "?q=" + encodeURIComponent(q), { credentials: "same-origin", signal: ctrl ? ctrl.signal : undefined })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) { if (data && data.query === sInput.value.trim()) render(data); })
        .catch(function () {});
    };

    sInput.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(fetchSuggestions, 140);
    });
    sInput.addEventListener("focus", function () { if (sInput.value.trim()) fetchSuggestions(); });
    sInput.addEventListener("keydown", function (e) {
      if (panel.hidden) {
        if (e.key === "ArrowDown" && sInput.value.trim()) { fetchSuggestions(); e.preventDefault(); }
        return;
      }
      if (e.key === "ArrowDown") { e.preventDefault(); setActive(activeIdx + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setActive(activeIdx - 1); }
      else if (e.key === "Enter" && activeIdx >= 0) { e.preventDefault(); location.href = options()[activeIdx].href; }
      else if (e.key === "Escape") { e.stopPropagation(); openPanel(false); }
    });
    panel.addEventListener("mousedown", function (e) { e.preventDefault(); }); // keep focus while clicking
    document.addEventListener("click", function (e) { if (!searchForm.contains(e.target)) openPanel(false); });
    // Press "/" anywhere to jump to the search bar.
    document.addEventListener("keydown", function (e) {
      var tag = (e.target.tagName || "").toLowerCase();
      if (e.key === "/" && tag !== "input" && tag !== "textarea" && tag !== "select" && !e.target.isContentEditable) {
        e.preventDefault();
        sInput.focus();
        sInput.select();
      }
    });
  }

  /* ---------------------------------------------------------- photo upload preview */
  $$("input[data-upload]").forEach(function (input) {
    input.addEventListener("change", function () {
      var box = input.closest(".upload");
      var file = input.files && input.files[0];
      if (!box || !file) return;
      var img = $("[data-upload-preview]", box);
      img.src = URL.createObjectURL(file);
      img.hidden = false;
      var icon = $("[data-upload-icon]", box);
      if (icon) icon.hidden = true;
      $("[data-upload-name]", box).textContent = file.name;
      var remove = box.parentNode.querySelector(".check input");
      if (remove) remove.checked = false;
    });
  });

  /* ---------------------------------------------------------- small touches */
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("is-drawn"); io.unobserve(e.target); }
      });
    }, { threshold: .3 });
    $$(".ring").forEach(function (r) { io.observe(r); });
  }

  document.addEventListener("submit", function (e) {
    var msg = e.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  var qty = $("[data-unit-price] input[name=quantity]");
  if (qty) {
    var wrap = qty.closest("[data-unit-price]");
    var unit = parseFloat(wrap.getAttribute("data-unit-price"));
    var out = $("[data-total]");
    var sym = wrap.getAttribute("data-currency");
    var update = function () {
      var q = Math.max(1, parseInt(qty.value || "1", 10));
      var n = unit * q;
      out.textContent = sym + n.toLocaleString(undefined, { minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2 });
    };
    qty.addEventListener("input", update);
    update();
  }
})();