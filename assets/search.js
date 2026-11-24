/* Полнотекстовый поиск по данным, собранным при сборке сайта. */
(function () {
  "use strict";

  var ROOT = window.SITE_ROOT || "";
  var DATA = window.SEARCH_DATA || { records: [] };
  var records = (DATA.records || []).slice();
  var state = {
    query: "",
    type: "all",
    sort: "relevance",
    limit: 40,
    tokens: [],
    stems: [],
    phrase: ""
  };
  var input = document.getElementById("page-search-input");
  var form = document.getElementById("page-search-form");
  var resultsBox = document.getElementById("search-results");
  var statusBox = document.getElementById("search-status");
  var moreButton = document.getElementById("search-more");
  var sortSelect = document.getElementById("search-sort");
  var typeButtons = Array.prototype.slice.call(document.querySelectorAll("[data-search-type]"));
  var typeLabels = {
    thesis: "Тезис",
    article: "Статья",
    glossary: "Словарь",
    bibliography: "Литература",
    quote: "Цитата",
    objection: "Возражение",
    system: "Система"
  };
  var typeTitles = {
    thesis: "Тезисы",
    article: "Статьи",
    glossary: "Словарь",
    bibliography: "Литература",
    quote: "Цитаты",
    objection: "Возражения",
    system: "Системы"
  };
  var stopWords = {
    "в": 1, "во": 1, "на": 1, "и": 1, "с": 1, "со": 1, "о": 1, "об": 1,
    "по": 1, "к": 1, "из": 1, "от": 1, "до": 1, "не": 1, "что": 1, "как": 1,
    "это": 1, "для": 1, "при": 1, "а": 1, "но": 1, "или": 1, "ли": 1,
    "же": 1, "бы": 1, "то": 1, "у": 1, "за": 1, "над": 1, "под": 1,
    "про": 1, "без": 1, "через": 1, "между": 1
  };

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

  function stem(word) {
    if (!word || word.length < 4) return word;
    var endings = [
      "иями", "ями", "ами", "ого", "его", "ому", "ему", "ыми", "ими",
      "ая", "яя", "ое", "ее", "ые", "ие", "ой", "ей", "ий", "ый",
      "ов", "ев", "ам", "ям", "ах", "ях", "ом", "ем", "а", "я",
      "о", "е", "ы", "и", "у", "ю", "ь"
    ];
    for (var i = 0; i < endings.length; i++) {
      var e = endings[i];
      if (word.length - e.length >= 3 && word.slice(-e.length) === e) {
        return word.slice(0, -e.length);
      }
    }
    return word;
  }

  function parseQuery(raw) {
    raw = (raw || "").trim();
    state.query = raw;
    state.tokens = [];
    state.stems = [];
    state.phrase = "";
    if (!raw) return;
    if (raw.length >= 2 && raw.charAt(0) === '"' && raw.charAt(raw.length - 1) === '"') {
      state.phrase = norm(raw.slice(1, -1));
      state.tokens = state.phrase.split(" ").filter(Boolean);
    } else {
      state.tokens = norm(raw).split(" ").filter(function (token) {
        return token && !stopWords[token];
      });
    }
    state.stems = state.tokens.map(stem);
  }

  function wordMatches(word, token, stemmed) {
    return word === token || word.indexOf(token) === 0 ||
      (stemmed && stemmed.length >= 3 && word.indexOf(stemmed) === 0);
  }

  function tokenMatches(text, token, stemmed) {
    if (!token) return true;
    var words = text.split(" ");
    for (var i = 0; i < words.length; i++) {
      if (wordMatches(words[i], token, stemmed)) return true;
    }
    return false;
  }

  // Предварительная нормализация записей.
  records.forEach(function (rec, index) {
    rec._index = index;
    rec._text = norm(rec.text || "");
    rec._title = norm(rec.title || rec.articleTitle || "");
    rec._all = norm((rec.text || "") + " " + (rec.title || "") + " " + (rec.articleTitle || ""));
  });

  function matches(rec) {
    if (!state.query) return false;
    if (state.phrase) {
      if (rec._all.indexOf(state.phrase) < 0) return false;
    } else {
      if (!state.tokens.length) return false;
      for (var i = 0; i < state.tokens.length; i++) {
        if (!tokenMatches(rec._all, state.tokens[i], state.stems[i])) return false;
      }
    }
    return true;
  }

  function score(rec) {
    var s = 0;
    var weights = {
      glossary: 14, article: 12, thesis: 9, quote: 8,
      objection: 7, system: 7, bibliography: 4
    };
    s += weights[rec.type] || 1;
    if (state.phrase) {
      if (rec._all.indexOf(state.phrase) >= 0) s += 30;
    } else {
      state.tokens.forEach(function (token, i) {
        if (rec._title === token) s += 40;
        else if (rec._title.indexOf(token) === 0) s += 22;
        else if (rec._title.indexOf(token) > 0) s += 10;
        var stemmed = state.stems[i];
        if (stemmed && rec._title.indexOf(stemmed) === 0) s += 8;
        var hits = 0;
        var words = rec._all.split(" ");
        for (var j = 0; j < words.length; j++) {
          if (wordMatches(words[j], token, stemmed)) hits++;
        }
        s += Math.min(hits, 6) * 2;
      });
    }
    if (state.query && rec.num && String(rec.num) === state.query.trim()) s += 20;
    return s;
  }

  function highlight(text, limit) {
    var escaped = escapeHtml(text);
    var terms = state.phrase ? [state.phrase] : state.tokens.concat(state.stems);
    terms = terms.filter(function (t) { return t && t.length >= 2; });
    terms = terms.filter(function (t, i) { return terms.indexOf(t) === i; });
    terms.sort(function (a, b) { return b.length - a.length; });
    if (!terms.length) return escaped;
    var pattern = new RegExp("(" + terms.map(function (t) {
      return t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }).join("|") + ")", "gi");
    escaped = escaped.replace(pattern, "<mark>$1</mark>");
    if (limit && escaped.length > limit && !state.phrase) {
      var idx = escaped.indexOf("<mark>");
      if (idx > limit) {
        escaped = "…" + escaped.slice(idx - 120);
      }
    }
    return escaped;
  }

  function shorten(text, limit) {
    if (!text) return "";
    if (text.length <= limit) return text;
    return text.slice(0, limit).replace(/\s+\S*$/, "") + "…";
  }

  function snippetAround(text, limit) {
    if (!text) return "";
    if (text.length <= limit) return text;
    var lower = text.toLowerCase();
    var terms = state.phrase ? [state.phrase] : state.tokens.concat(state.stems);
    var pos = -1;
    terms.forEach(function (term) {
      if (!term) return;
      var p = lower.indexOf(term);
      if (p >= 0 && (pos < 0 || p < pos)) pos = p;
    });
    if (pos < 0) return shorten(text, limit);
    var start = Math.max(0, pos - Math.floor(limit / 3));
    var end = Math.min(text.length, start + limit);
    return (start > 0 ? "…" : "") + text.slice(start, end) + (end < text.length ? "…" : "");
  }

  function resultMeta(rec) {
    var parts = [typeLabels[rec.type] || "Запись"];
    if (rec.type === "thesis") {
      parts.push(rec.articleTitle || "");
      if (rec.para) parts.push(rec.para);
    } else if (rec.type === "article") {
      parts.push(rec.label || "");
    } else if (rec.type === "glossary") {
      parts.push("термин");
    } else if (rec.type === "bibliography") {
      parts.push("[" + (rec.number || "") + "]");
    } else if (rec.type === "quote") {
      parts.push(rec.articleTitle || "");
    } else if (rec.type === "objection") {
      parts.push("Приложение А");
      if (rec.number) parts.push("№ " + rec.number);
    } else if (rec.type === "system") {
      parts.push("Приложение В");
      if (rec.number) parts.push("№ " + rec.number);
    }
    return parts.filter(Boolean).join(" · ");
  }

  function renderResult(rec) {
    var url = ROOT + (rec.url || "");
    var titleHtml = "";
    if (rec.type === "article" || rec.type === "glossary") {
      titleHtml = '<h2 class="result-title"><a href="' + escapeHtml(url) + '">' +
        highlight(rec.title || rec.articleTitle || "", 0) + "</a></h2>";
    }
    var snippetText = rec.text || "";
    if (rec.type === "article") snippetText = snippetAround(snippetText, 600);
    else if (rec.type === "glossary") snippetText = snippetAround(snippetText, 800);
    var snippet = highlight(snippetText, 0);
    var snippetHtml;
    if (rec.type === "article" || rec.type === "glossary") {
      snippetHtml = '<p class="result-snippet">' + snippet + "</p>";
    } else {
      snippetHtml = '<p class="result-snippet"><a href="' + escapeHtml(url) + '">' + snippet + "</a></p>";
    }
    return '<article class="search-result">' +
      '<div class="result-meta">' + escapeHtml(resultMeta(rec)) + "</div>" +
      titleHtml + snippetHtml + "</article>";
  }

  function matchedRecords() {
    var out = records.filter(matches);
    if (state.type !== "all") {
      out = out.filter(function (rec) { return rec.type === state.type; });
    }
    if (state.sort === "book") {
      out.sort(function (a, b) { return (a.order || 0) - (b.order || 0); });
    } else {
      out.sort(function (a, b) {
        return score(b) - score(a) || (a.order || 0) - (b.order || 0);
      });
    }
    return out;
  }

  function updateTypeCounts(allMatched) {
    var counts = { all: allMatched.length };
    allMatched.forEach(function (rec) {
      counts[rec.type] = (counts[rec.type] || 0) + 1;
    });
    typeButtons.forEach(function (button) {
      var type = button.getAttribute("data-search-type");
      var label = type === "all" ? "Всё" : (typeTitles[type] || typeLabels[type] || type);
      var n = counts[type] || 0;
      button.textContent = label + " (" + n + ")";
      button.classList.toggle("active", state.type === type);
      button.setAttribute("aria-selected", state.type === type ? "true" : "false");
    });
  }

  function setStatus(text) {
    if (statusBox) statusBox.textContent = text;
  }

  function render(updateUrl) {
    if (!resultsBox) return;
    var rawQuery = input ? input.value : "";
    parseQuery(rawQuery);
    state.limit = 40;
    if (updateUrl) {
      var url = new URL(window.location.href);
      if (rawQuery.trim()) url.searchParams.set("q", rawQuery.trim());
      else url.searchParams.delete("q");
      if (state.type !== "all") url.searchParams.set("type", state.type);
      else url.searchParams.delete("type");
      if (state.sort !== "relevance") url.searchParams.set("sort", state.sort);
      else url.searchParams.delete("sort");
      history.replaceState(null, "", url.toString());
    }
    resultsBox.innerHTML = "";
    if (!state.query) {
      setStatus("Введите запрос. Можно искать слово, основу слова или точную фразу в кавычках.");
      updateTypeCounts([]);
      if (moreButton) moreButton.hidden = true;
      resultsBox.innerHTML =
        '<p class="search-empty">Например: <a href="?q=неполнота">неполнота</a>, ' +
        '<a href="?q=тонкая настройка">тонкая настройка</a>, ' +
        '<a href="?q=фитра">фитра</a>, <a href="?q=онтологическое доказательство">онтологическое доказательство</a>.</p>';
      return;
    }
    if (state.query.length < 2) {
      setStatus("Введите хотя бы два символа.");
      updateTypeCounts([]);
      if (moreButton) moreButton.hidden = true;
      return;
    }
    var allMatched = records.filter(matches);
    updateTypeCounts(allMatched);
    var found = matchedRecords();
    var shown = found.slice(0, state.limit);
    if (!found.length) {
      setStatus("Ничего не найдено. Попробуйте другую форму слова или откройте содержание.");
      if (moreButton) moreButton.hidden = true;
      return;
    }
    setStatus("Найдено: " + found.length + (state.type === "all" ? "" : " в выбранном разделе") + ".");
    resultsBox.innerHTML = shown.map(renderResult).join("");
    if (moreButton) {
      moreButton.hidden = found.length <= state.limit;
      moreButton.textContent = "Показать ещё (" + Math.min(40, found.length - state.limit) + ")";
    }
  }

  function loadMore() {
    state.limit += 40;
    var found = matchedRecords();
    var shown = found.slice(0, state.limit);
    resultsBox.innerHTML = shown.map(renderResult).join("");
    if (moreButton) {
      moreButton.hidden = found.length <= state.limit;
      moreButton.textContent = "Показать ещё (" + Math.min(40, found.length - state.limit) + ")";
    }
  }

  // Начальное состояние из URL.
  var params = new URLSearchParams(window.location.search);
  if (input) input.value = params.get("q") || "";
  if (params.get("type")) state.type = params.get("type");
  if (params.get("sort")) state.sort = params.get("sort");
  if (sortSelect) sortSelect.value = state.sort;

  typeButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      state.type = button.getAttribute("data-search-type") || "all";
      render(true);
    });
  });
  if (sortSelect) {
    sortSelect.addEventListener("change", function () {
      state.sort = sortSelect.value;
      render(true);
    });
  }
  if (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      render(true);
    });
  }
  if (input) {
    var timer = null;
    input.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () { render(true); }, 180);
    });
  }
  if (moreButton) moreButton.addEventListener("click", loadMore);

  render(false);
})();
