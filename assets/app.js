/* Общий интерфейс энциклопедии: тема, меню, подсказки, режим тезисов,
   подсветка найденного фрагмента, фильтры и формулы. */
(function () {
  "use strict";

  var ROOT = window.SITE_ROOT || "";
  var html = document.documentElement;

  function norm(text) {
    return (text || "")
      .toLowerCase()
      .replace(/ё/g, "е")
      .replace(/['’]/g, "")
      .replace(/[^a-zа-я0-9]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* ------------------------------------------------------------------ */
  /* Тема                                                               */
  /* ------------------------------------------------------------------ */

  var themeButton = document.getElementById("theme-toggle");
  var systemDark = window.matchMedia
    ? window.matchMedia("(prefers-color-scheme: dark)")
    : null;

  function effectiveTheme(theme) {
    if (theme === "light" || theme === "dark") return theme;
    return systemDark && systemDark.matches ? "dark" : "light";
  }

  function applyTheme(theme) {
    html.dataset.theme = theme;
    var effective = effectiveTheme(theme);
    var nextLabel = effective === "dark"
      ? "Включить светлую тему"
      : "Включить тёмную тему";
    if (themeButton) {
      themeButton.title = nextLabel;
      themeButton.setAttribute("aria-label", nextLabel);
    }
  }

  var storedTheme = "auto";
  try {
    storedTheme = localStorage.getItem("site-theme") || "auto";
  } catch (e) { /* localStorage может быть недоступен */ }
  if (storedTheme !== "light" && storedTheme !== "dark" && storedTheme !== "auto") {
    storedTheme = "auto";
  }
  applyTheme(storedTheme);

  if (themeButton) {
    themeButton.addEventListener("click", function () {
      var next = effectiveTheme(html.dataset.theme || "auto") === "dark"
        ? "light"
        : "dark";
      try { localStorage.setItem("site-theme", next); } catch (e) {}
      applyTheme(next);
    });
  }

  if (systemDark) {
    var onSchemeChange = function () {
      if ((html.dataset.theme || "auto") === "auto") applyTheme("auto");
    };
    if (systemDark.addEventListener) systemDark.addEventListener("change", onSchemeChange);
    else if (systemDark.addListener) systemDark.addListener(onSchemeChange);
  }

  /* ------------------------------------------------------------------ */
  /* Мобильное меню                                                     */
  /* ------------------------------------------------------------------ */

  var menuButton = document.getElementById("menu-toggle");
  var sidebar = document.getElementById("sidebar");

  function closeMenu() {
    if (!sidebar) return;
    sidebar.classList.remove("open");
    document.body.classList.remove("menu-open");
    if (menuButton) {
      menuButton.setAttribute("aria-expanded", "false");
      menuButton.setAttribute("aria-label", "Открыть меню");
    }
  }

  if (menuButton && sidebar) {
    menuButton.addEventListener("click", function (event) {
      event.stopPropagation();
      var open = sidebar.classList.toggle("open");
      document.body.classList.toggle("menu-open", open);
      menuButton.setAttribute("aria-expanded", open ? "true" : "false");
      menuButton.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
      if (open) {
        var closeButton = sidebar.querySelector("[data-menu-close]");
        if (closeButton) closeButton.focus();
      }
    });
    document.addEventListener("click", function (event) {
      if (!sidebar.classList.contains("open")) return;
      if (sidebar.contains(event.target) || menuButton.contains(event.target)) return;
      closeMenu();
    });
    sidebar.addEventListener("click", function (event) {
      if (event.target.closest("a")) closeMenu();
    });
    document.querySelectorAll("[data-menu-close]").forEach(function (button) {
      button.addEventListener("click", closeMenu);
    });
  }

  /* ------------------------------------------------------------------ */
  /* Режим тезисов                                                      */
  /* ------------------------------------------------------------------ */

  var viewButtons = document.querySelectorAll(".page-tabs [data-view]");

  function setArticleView(view, updateUrl) {
    if (view !== "theses" && view !== "sources") view = "text";
    if (view === "sources" && !document.getElementById("sources")) view = "text";
    document.body.classList.toggle("theses-mode", view === "theses");
    document.body.classList.toggle("sources-mode", view === "sources");
    viewButtons.forEach(function (button) {
      var active = button.getAttribute("data-view") === view;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    if (updateUrl) {
      var url = new URL(window.location.href);
      if (view === "text") url.searchParams.delete("view");
      else url.searchParams.set("view", view);
      history.replaceState(null, "", url.toString());
    }
  }

  if (viewButtons.length) {
    var startView = new URLSearchParams(window.location.search).get("view") || "text";
    setArticleView(startView, false);
    viewButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        setArticleView(button.getAttribute("data-view"), true);
      });
    });
  }

  /* ------------------------------------------------------------------ */
  /* Подсветка найденного фрагмента                                     */
  /* ------------------------------------------------------------------ */

  function scrollToHash() {
    if (!window.location.hash || window.location.hash.length < 2) return;
    var id;
    try {
      id = decodeURIComponent(window.location.hash.slice(1));
    } catch (e) {
      id = window.location.hash.slice(1);
    }
    var el = document.getElementById(id);
    if (!el) return;
    try {
      el.scrollIntoView({ behavior: "instant", block: "start" });
    } catch (e) {
      el.scrollIntoView();
    }
  }

  function highlightHash() {
    if (!window.location.hash || window.location.hash.length < 2) return;
    var id;
    try {
      id = decodeURIComponent(window.location.hash.slice(1));
    } catch (e) {
      id = window.location.hash.slice(1);
    }
    var target = document.getElementById(id);
    if (!target) return;
    var highlight = target;
    if (!target.classList.contains("thesis")) {
      highlight = target.querySelector(".thesis") || target;
    }
    highlight.classList.add("is-target");
    window.setTimeout(function () {
      highlight.classList.remove("is-target");
    }, 6500);
    window.setTimeout(scrollToHash, 30);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", highlightHash);
  } else {
    highlightHash();
  }
  window.addEventListener("hashchange", highlightHash);

  /* ------------------------------------------------------------------ */
  /* Случайная статья                                                   */
  /* ------------------------------------------------------------------ */

  document.querySelectorAll("[data-random-article]").forEach(function (link) {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      var articles = (window.SITE_INDEX && window.SITE_INDEX.articles) || [];
      if (!articles.length) {
        window.location.href = ROOT + "contents.html";
        return;
      }
      var item = articles[Math.floor(Math.random() * articles.length)];
      window.location.href = ROOT + item.url;
    });
  });

  /* ------------------------------------------------------------------ */
  /* Подсказки в шапке                                                  */
  /* ------------------------------------------------------------------ */

  var searchInput = document.getElementById("search-input");
  var suggestBox = document.getElementById("search-suggest");
  var suggestItems = [];
  var suggestIndex = -1;

  function allSuggestions() {
    var index = window.SITE_INDEX || {};
    var out = [];
    (index.articles || []).forEach(function (item) {
      out.push({ title: item.title, url: item.url, type: item.label || "Статья" });
    });
    (index.terms || []).forEach(function (item) {
      out.push({ title: item.title, url: item.url, type: "Термин" });
    });
    (index.pages || []).forEach(function (item) {
      out.push({ title: item.title, url: item.url, type: "Страница" });
    });
    return out;
  }

  function renderSuggestions() {
    if (!suggestBox || !searchInput) return;
    var query = norm(searchInput.value);
    if (!query) {
      suggestBox.classList.remove("open");
      suggestBox.innerHTML = "";
      suggestItems = [];
      suggestIndex = -1;
      return;
    }
    var all = allSuggestions();
    var scored = [];
    all.forEach(function (item) {
      var title = norm(item.title);
      if (!title) return;
      var score = -1;
      if (title === query) score = 100;
      else if (title.indexOf(query) === 0) score = 70;
      else if (title.indexOf(query) > 0) score = 40;
      else if (query.split(" ").every(function (part) { return title.indexOf(part) >= 0; })) score = 20;
      if (score >= 0) scored.push({ item: item, score: score });
    });
    scored.sort(function (a, b) {
      return b.score - a.score || a.item.title.localeCompare(b.item.title, "ru");
    });
    suggestItems = scored.slice(0, 9).map(function (x) { return x.item; });
    suggestIndex = -1;
    if (!suggestItems.length) {
      suggestBox.innerHTML = '<div class="suggest-empty">Ничего не найдено. Нажмите «Найти» для полного поиска.</div>';
      suggestBox.classList.add("open");
      return;
    }
    suggestBox.innerHTML = suggestItems.map(function (item, i) {
      return '<a class="suggest-item" role="option" data-index="' + i + '" href="' +
        escapeHtml(ROOT + item.url) + '">' + escapeHtml(item.title) + ' ' +
        '<span class="suggest-type">' + escapeHtml(item.type) + "</span></a>";
    }).join("");
    suggestBox.classList.add("open");
    suggestBox.querySelectorAll(".suggest-item").forEach(function (link) {
      link.addEventListener("click", function () {
        suggestBox.classList.remove("open");
      });
    });
  }

  function moveSuggestion(delta) {
    if (!suggestItems.length) return;
    suggestIndex = (suggestIndex + delta + suggestItems.length) % suggestItems.length;
    suggestBox.querySelectorAll(".suggest-item").forEach(function (el, i) {
      el.classList.toggle("active", i === suggestIndex);
    });
    var active = suggestBox.querySelector(".suggest-item.active");
    if (active) active.scrollIntoView({ block: "nearest" });
  }

  if (searchInput && suggestBox) {
    var timer = null;
    searchInput.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(renderSuggestions, 120);
    });
    searchInput.addEventListener("focus", function () {
      if (searchInput.value.trim()) renderSuggestions();
    });
    searchInput.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        moveSuggestion(1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        moveSuggestion(-1);
      } else if (event.key === "Escape") {
        suggestBox.classList.remove("open");
      } else if (event.key === "Enter" && suggestIndex >= 0 && suggestItems[suggestIndex]) {
        event.preventDefault();
        window.location.href = ROOT + suggestItems[suggestIndex].url;
      }
    });
    document.addEventListener("click", function (event) {
      if (!suggestBox.contains(event.target) && event.target !== searchInput) {
        suggestBox.classList.remove("open");
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Фильтры списков                                                    */
  /* ------------------------------------------------------------------ */

  function elementText(el, attr) {
    if (attr && el.hasAttribute(attr)) return el.getAttribute(attr) || "";
    return el.textContent || "";
  }

  function applySimpleFilter(input) {
    var selector = input.getAttribute("data-filter-target");
    if (!selector) return;
    var attr = input.getAttribute("data-filter-text");
    var query = norm(input.value);
    document.querySelectorAll(selector).forEach(function (el) {
      var text = norm(elementText(el, attr));
      el.hidden = !!query && text.indexOf(query) < 0;
    });
  }

  document.querySelectorAll("[data-filter-target]").forEach(function (input) {
    if (input.closest(".quote-filters")) return;
    input.addEventListener("input", function () { applySimpleFilter(input); });
  });

  /* Фильтр цитат: текст + тип. */
  var quoteInput = document.getElementById("quote-filter");
  var quoteButtons = document.querySelectorAll("[data-quote-filter]");
  var quoteKind = "all";

  function applyQuoteFilter() {
    var query = norm(quoteInput ? quoteInput.value : "");
    document.querySelectorAll(".quote-entry").forEach(function (el) {
      var text = norm(el.getAttribute("data-quote-text") || el.textContent);
      var kind = el.getAttribute("data-quote-kind") || "other";
      var okText = !query || text.indexOf(query) >= 0;
      var okKind = quoteKind === "all" || kind === quoteKind;
      el.hidden = !(okText && okKind);
    });
  }

  if (quoteInput) quoteInput.addEventListener("input", applyQuoteFilter);
  quoteButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      quoteButtons.forEach(function (b) { b.classList.remove("active"); });
      button.classList.add("active");
      quoteKind = button.getAttribute("data-quote-filter") || "all";
      applyQuoteFilter();
    });
  });

  /* ------------------------------------------------------------------ */
  /* Формулы KaTeX                                                      */
  /* ------------------------------------------------------------------ */

  function renderMath() {
    if (!window.katex) return;
    document.querySelectorAll(".tex").forEach(function (el) {
      if (el.dataset.rendered === "1") return;
      var tex = el.getAttribute("data-tex");
      if (!tex) return;
      try {
        window.katex.render(tex, el, {
          displayMode: el.classList.contains("tex-display"),
          throwOnError: false,
          strict: false,
          trust: false
        });
        el.dataset.rendered = "1";
      } catch (e) {
        /* оставляем исходный текст */
      }
    });
    // После формул страница меняет высоту — возвращаемся к якорю.
    window.setTimeout(scrollToHash, 50);
    window.setTimeout(scrollToHash, 250);
  }

  window.addEventListener("load", function () {
    window.setTimeout(scrollToHash, 0);
  });
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () {
      window.setTimeout(scrollToHash, 0);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderMath);
  } else {
    renderMath();
  }

  /* ------------------------------------------------------------------ */
  /* Клавиатура                                                         */
  /* ------------------------------------------------------------------ */

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeMenu();
    if (event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey) {
      var tag = (document.activeElement && document.activeElement.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (searchInput) {
        event.preventDefault();
        searchInput.focus();
      }
    }
  });
})();
