# -*- coding: utf-8 -*-
"""HTML-страницы энциклопедии."""

from __future__ import annotations

import html
import re
from collections import defaultdict
from typing import Any, Iterable

from . import config
from .model import Site
from .render import (
    esc,
    render_bib_entry_text,
    render_categories as render_article_categories,
    render_infobox,
    render_key_terms,
    render_list,
    render_prev_next,
    render_section_body,
    render_see_also,
    render_sources,
    render_tabs,
    render_table,
)
from .texparse import Section, Term, html_to_text


# ---------------------------------------------------------------------------
# Общий каркас
# ---------------------------------------------------------------------------

def page_shell(
    site: Site,
    *,
    title: str,
    content: str,
    root: str = "",
    active: str = "",
    description: str = "",
    body_class: str = "",
    sidebar_extra: str = "",
    extra_head: str = "",
    extra_scripts: str = "",
    page_kind: str = "",
) -> str:
    full_title = title if title == config.SITE_TITLE else f"{title} — {config.SITE_TITLE}"
    desc = description or config.SITE_DESCRIPTION
    katex_head = ""
    katex_scripts = ""
    if page_kind in ("article", "term", "theorems"):
        katex_head = f'<link rel="stylesheet" href="{root}assets/katex/katex.min.css">'
        katex_scripts = (
            f'<script defer src="{root}assets/katex/katex.min.js"></script>'
            f'<script defer src="{root}assets/katex/contrib/auto-render.min.js"></script>'
        )
    return f"""<!doctype html>
<html lang="ru" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}assets/style.css">
{katex_head}
{extra_head}
<script>window.SITE_ROOT={root!r};</script>
</head>
<body class="{esc(body_class)}">
<a class="skip-link" href="#main">Перейти к содержимому</a>
<header class="site-header">
  <div class="header-inner">
    <button class="icon-button menu-toggle" id="menu-toggle" type="button"
            aria-controls="sidebar" aria-expanded="false" aria-label="Открыть меню">
      <svg class="icon-burger" viewBox="0 0 20 20" width="19" height="19" aria-hidden="true" focusable="false">
        <path d="M3 5.5h14M3 10h14M3 14.5h14" fill="none" stroke="currentColor"
              stroke-width="1.6" stroke-linecap="round"/>
      </svg>
      <svg class="icon-close" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" focusable="false">
        <path d="M4 4l12 12M16 4L4 16" fill="none" stroke="currentColor"
              stroke-width="1.7" stroke-linecap="round"/>
      </svg>
    </button>
    <a class="site-logo" href="{root}index.html" aria-label="На главную">
      <span class="logo-mark" aria-hidden="true">П</span>
      <span class="logo-text">{esc(config.SITE_TITLE)}</span>
    </a>
    <form class="search-form header-search" action="{root}search.html" method="get" role="search">
      <label class="visually-hidden" for="search-input">Поиск по энциклопедии</label>
      <input id="search-input" name="q" type="search" placeholder="Искать в энциклопедии"
             autocomplete="off" spellcheck="false" aria-autocomplete="list"
             aria-controls="search-suggest">
      <button type="submit" class="search-submit" aria-label="Найти">Найти</button>
      <div class="search-suggest" id="search-suggest" role="listbox" aria-label="Подсказки"></div>
    </form>
    <nav class="header-nav" aria-label="Быстрые ссылки">
      <a href="{root}contents.html">Содержание</a>
      <a href="{root}glossary.html">Словарь</a>
      <a href="{root}bibliography.html">Литература</a>
      <a href="{root}about.html">О книге</a>
    </nav>
    <button class="icon-button theme-toggle" id="theme-toggle" type="button"
            aria-label="Переключить тему" title="Светлая или тёмная тема">
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" focusable="false">
        <circle cx="10" cy="10" r="7.25" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <path d="M10 2.75a7.25 7.25 0 0 1 0 14.5z" fill="currentColor"/>
      </svg>
    </button>
  </div>
</header>
<div class="page-layout">
  <aside class="sidebar" id="sidebar" aria-label="Навигация">
    <div class="mobile-menu-head">
      <span class="mobile-menu-title">Меню</span>
      <button class="icon-button mobile-menu-close" type="button"
              data-menu-close aria-label="Закрыть меню">
        <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" focusable="false">
          <path d="M4 4l12 12M16 4L4 16" fill="none" stroke="currentColor"
                stroke-width="1.7" stroke-linecap="round"/>
        </svg>
      </button>
    </div>
    {sidebar_nav(root, active)}
    {sidebar_extra}
  </aside>
  <main class="content" id="main">
    {content}
  </main>
</div>
<footer class="site-footer">
  <div class="footer-inner">
    <div class="footer-cite">
      <span class="footer-cite-label">Цитировать</span>
      Викулов, И. С. (2026). <em>{esc(config.CITATION_TITLE)}</em>. Zenodo.
      <a href="{config.DOI_URL}">{config.DOI_URL}</a>
    </div>
    <div class="footer-links">
      <a href="{root}about.html">О книге</a>
      <a href="{root}{config.PDF_NAME}" download="{config.PDF_NAME}">Скачать PDF</a>
      <a href="{config.LICENSE_URL}" rel="license">Лицензия {esc(config.LICENSE)}</a>
    </div>
  </div>
</footer>
<script defer src="{root}assets/titles.js"></script>
{katex_scripts}
<script defer src="{root}assets/app.js"></script>
{extra_scripts}
</body>
</html>"""


def sidebar_nav(root: str, active: str) -> str:
    groups = [
        ("", [
            ("index", "Главная", "index.html"),
            ("contents", "Содержание", "contents.html"),
            ("search", "Поиск", "search.html"),
        ]),
        ("Указатели", [
            ("az", "Указатель А–Я", "index-a-z.html"),
            ("glossary", "Словарь терминов", "glossary.html"),
            ("bibliography", "Литература", "bibliography.html"),
            ("quotes", "Аяты и хадисы", "quotes.html"),
            ("objections", "Возражения и ответы", "objections.html"),
            ("systems", "Мировоззренческие системы", "systems.html"),
            ("theorems", "Теоремы и формулировки", "theorems.html"),
            ("categories", "Категории", "categories.html"),
        ]),
        ("", [
            ("about", "О книге и проекте", "about.html"),
        ]),
    ]
    parts: list[str] = []
    for heading, links in groups:
        if heading:
            parts.append(f'<div class="nav-heading">{esc(heading)}</div>')
        parts.append('<ul class="nav-list">')
        for key, label, url in links:
            cls = ' class="active" aria-current="page"' if key == active else ""
            parts.append(f'<li><a{cls} href="{root}{url}">{esc(label)}</a></li>')
        parts.append("</ul>")
    parts.append(
        f'<div class="nav-random"><a href="#" data-random-article>Случайная статья</a></div>'
    )
    return "".join(parts)


def crumbs(root: str, items: list[tuple[str | None, str]]) -> str:
    parts = ['<nav class="breadcrumb" aria-label="Хлебные крошки">']
    for i, (url, label) in enumerate(items):
        if i:
            parts.append('<span class="sep">›</span>')
        if url:
            parts.append(f'<a href="{root}{url}">{esc(label)}</a>')
        else:
            parts.append(f"<span>{esc(label)}</span>")
    parts.append("</nav>")
    return "".join(parts)


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(int(n))
    if 11 <= n % 100 <= 19:
        return many
    if n % 10 == 1:
        return one
    if 2 <= n % 10 <= 4:
        return few
    return many


def group_by_letter(items: Iterable[Any], key) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = defaultdict(list)
    for item in items:
        text = key(item)
        letter = ""
        for ch in text:
            if ch.isalpha():
                letter = ch.upper().replace("Ё", "Е")
                break
        out[letter or "—"].append(item)
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def letter_nav(letters: list[str], prefix: str) -> str:
    parts = ['<nav class="letter-nav" aria-label="Алфавитный указатель">']
    for letter in letters:
        parts.append(f'<a href="#{prefix}{esc(letter)}">{esc(letter)}</a>')
    parts.append("</nav>")
    return "".join(parts)


def render_paragraphs(paragraphs: list[str], site: Site, root: str, section: Section | None = None) -> str:
    return "".join(
        f'<p class="prose">{site.renderer.render_inline(p, section, root, allow_xrefs=False, allow_terms=False)}</p>'
        for p in paragraphs
    )


# ---------------------------------------------------------------------------
# Главная и содержание
# ---------------------------------------------------------------------------

def render_home(site: Site) -> str:
    total_theses = sum(s.thesis_count for s in site.sections)
    stats = [
        (len(site.numbered_sections), plural(len(site.numbered_sections), "раздел", "раздела", "разделов")),
        (len(site.appendices), plural(len(site.appendices), "приложение", "приложения", "приложений")),
        (len(site.bib), plural(len(site.bib), "источник", "источника", "источников")),
        (len(site.quotes), plural(len(site.quotes), "цитата", "цитаты", "цитат")),
        (total_theses, plural(total_theses, "тезис", "тезиса", "тезисов")),
    ]
    stat_html = "".join(
        f'<div class="stat"><span class="stat-num">{n}</span><span class="stat-label">{label}</span></div>'
        for n, label in stats
    )
    description = site.front.get("cover_description") or (
        "Теоремы Гёделя о неполноте, онтологическое доказательство и Коран как внешнее откровение."
    )
    contents_parts: list[str] = []
    for gid, gtitle, nums in config.GROUPS:
        sections = [site.section(str(n)) for n in nums]
        sections = [s for s in sections if s]
        if not sections:
            continue
        items = []
        for sec in sections:
            if sec.starred:
                url = site.appendix_url(sec.num)
                label = f"{sec.label}. {sec.title.split('. ', 1)[-1]}"
            else:
                url = sec.url
                label = sec.title
            items.append(
                f'<li><span class="home-num">{esc(sec.num)}</span> '
                f'<a href="{url}">{esc(label)}</a></li>'
            )
        contents_parts.append(
            f'<section class="home-group"><h3>{esc(gtitle)}</h3>'
            f'<ul class="home-toc">{"".join(items)}</ul></section>'
        )
    sidebar_extra = ""
    n_obj = sum(len(b.items) for b in site.section("A").blocks if b.kind == "list") if site.section("A") else 0
    n_sys = sum(len(b.items) for b in site.section("C").blocks if b.kind == "list") if site.section("C") else 0
    key_specs = [
        ("1", "Метод и термины"),
        ("7", "Первая теорема о неполноте"),
        ("8", "Вторая теорема о неполноте"),
        ("35", "Эпистемология материализма"),
        ("61", "Элиминационный анализ"),
        ("65", "Первичное основание"),
        ("76", "Итоговое положение"),
    ]
    key_links = []
    for num, label in key_specs:
        sec = site.section(num)
        if sec:
            key_links.append(f'<li><a href="{sec.url}">{esc(label)}</a></li>')
    key_links_html = "".join(key_links)
    content = f"""
<div class="home-head">
  <div class="home-kicker">Энциклопедия</div>
  <h1>{esc(config.SITE_TITLE)}</h1>
  <p class="home-subtitle">{esc(config.SITE_SUBTITLE)}</p>
  <p class="home-biblio">{esc(config.AUTHOR)}. {esc(config.BOOK_TITLE)}.
  {esc(config.EDITION)}. {esc(config.BOOK_DATE)}</p>
  <p class="home-description">{esc(description)}</p>
  <form class="search-form home-search" action="search.html" method="get" role="search">
    <label class="visually-hidden" for="home-search-input">Поиск по энциклопедии</label>
    <input id="home-search-input" name="q" type="search" placeholder="Найти тезис, термин, источник или цитату"
           autocomplete="off" spellcheck="false">
    <button type="submit" class="search-submit">Искать</button>
  </form>
  <p class="home-hint">Поиск идёт по отдельным предложениям, а также по словарю,
  литературе, цитатам и приложениям.</p>
  <div class="stats">{stat_html}</div>
</div>
<div class="home-columns">
  <section class="home-main" aria-labelledby="home-contents-title">
    <div class="section-heading">
      <h2 id="home-contents-title">Содержание</h2>
      <a class="section-link" href="contents.html">Полное содержание</a>
    </div>
    <p class="section-note">Разделы идут в книжном порядке. Тематические группы — только навигация.</p>
    {''.join(contents_parts)}
    <p class="home-more"><a href="contents.html">Все разделы и приложения →</a></p>
  </section>
  <aside class="home-side">
    <section class="home-box">
      <h2>Указатели</h2>
      <ul class="link-list">
        <li><a href="index-a-z.html">Указатель А–Я</a></li>
        <li><a href="glossary.html">Словарь терминов</a></li>
        <li><a href="bibliography.html">Литература</a> <span class="muted">{len(site.bib)}</span></li>
        <li><a href="quotes.html">Аяты и хадисы</a> <span class="muted">{len(site.quotes)}</span></li>
        <li><a href="objections.html">Возражения и ответы</a> <span class="muted">{n_obj}</span></li>
        <li><a href="systems.html">Мировоззренческие системы</a> <span class="muted">{n_sys}</span></li>
        <li><a href="theorems.html">Теоремы и формулировки</a></li>
        <li><a href="categories.html">Категории</a></li>
      </ul>
    </section>
    <section class="home-box">
      <h2>Ключевые статьи</h2>
      <ul class="link-list">
        {key_links_html}
      </ul>
    </section>
    <section class="home-box">
      <h2>О книге</h2>
      <p>Книга исследует пределы имманентного обоснования: от теорем Гёделя
      и философии математики до космологии, сознания, богословских аргументов
      и текстологии Корана.</p>
      <p><a href="about.html">Подробнее о книге →</a></p>
    </section>
  </aside>
</div>
"""
    return page_shell(
        site,
        title=config.SITE_TITLE,
        content=content,
        root="",
        active="index",
        body_class="home-page",
    )


def render_contents(site: Site) -> str:
    parts = [
        '<header class="page-header"><h1>Содержание</h1>',
        '<p class="page-subtitle">Полное содержание книги в порядке разделов. '
        'Тематические группы служат только для навигации.</p></header>',
    ]
    for gid, gtitle, nums in config.GROUPS:
        sections = [site.section(str(n)) for n in nums]
        sections = [s for s in sections if s]
        if not sections:
            continue
        parts.append(f'<section class="contents-group"><h2>{esc(gtitle)}</h2><ol class="contents-list">')
        for sec in sections:
            if sec.starred:
                url = site.appendix_url(sec.num)
                title = sec.title.split(". ", 1)[-1]
            else:
                url = sec.url
                title = sec.title
            cats = " · ".join(site.category_name(c) for c in sec.categories)
            words = f"{sec.words:,}".replace(",", " ")
            parts.append(
                f'<li><span class="contents-num">{esc(sec.num)}</span>'
                f'<div class="contents-body"><a href="{url}">{esc(title)}</a>'
                f'<div class="contents-meta">{esc(cats)} · {words} слов · {sec.thesis_count} '
                f'{plural(sec.thesis_count, "тезис", "тезиса", "тезисов")}</div></div></li>'
            )
        parts.append("</ol></section>")
    parts.append(
        '<section class="contents-group"><h2>Литература</h2>'
        '<p><a href="bibliography.html">Список литературы</a> — 425 источников, '
        'на которые ссылается текст.</p></section>'
    )
    content = "".join(parts)
    return page_shell(
        site,
        title="Содержание",
        content=content,
        root="",
        active="contents",
        description="Полное содержание книги «Пределы обоснования».",
    )


# ---------------------------------------------------------------------------
# Статья
# ---------------------------------------------------------------------------

def render_article(site: Site, section: Section) -> str:
    body = render_section_body(section, site, "../")
    sources = render_sources(section, site, "../")
    see_also = render_see_also(section, site, "../")
    key_terms = render_key_terms(section, site, "../")
    categories = render_article_categories(section, site, "../")
    infobox = render_infobox(section, site, "../")
    tabs = render_tabs(section)
    prev_next = render_prev_next(section, site, "../")
    subtitle = (
        f'<div class="article-subtitle">{esc(section.label)} · '
        f'материал из энциклопедии «{esc(config.SITE_TITLE)}»</div>'
    )
    breadcrumb = crumbs("../", [
        ("index.html", "Главная"),
        ("contents.html", "Содержание"),
        (None, section.title),
    ])
    content = f"""
{breadcrumb}
<article class="article">
  <header class="article-header">
    <h1>{esc(section.title)}</h1>
    {subtitle}
    {tabs}
  </header>
  {infobox}
  {body}
  {sources}
  {see_also}
  {key_terms}
  {categories}
  {prev_next}
</article>
"""
    return page_shell(
        site,
        title=section.title,
        content=content,
        root="../",
        active="",
        description=f"{section.label}. {section.title}. {section.lead[:160]}",
        body_class="article-page",
        page_kind="article",
    )


# ---------------------------------------------------------------------------
# Словарь и термины
# ---------------------------------------------------------------------------

def term_definitions_html(term: Term, site: Site, root: str, *, compact: bool = False) -> str:
    parts: list[str] = []
    for d in term.definitions:
        sec = site.section(d["source_num"])
        text = site.renderer.render_inline(
            d["text"], sec, root, allow_xrefs=True, allow_terms=False, exclude_term=term.id
        )
        parts.append(
            f'<div class="definition"><p>{text}</p>'
            f'<div class="definition-source">Источник: '
            f'<a href="{root}{esc(d["source_url"])}">{esc(d["source_label"])}</a></div></div>'
        )
    return "".join(parts)


def render_glossary(site: Site) -> str:
    glossary_sec = site.section("B")
    intro = []
    if glossary_sec:
        # Нужен для сверки текста Приложения Б и для единого рендера.
        render_section_body(glossary_sec, site, "")
        pnum = 0
        for block in glossary_sec.blocks:
            if block.kind == "para":
                pnum += 1
                intro.append(
                    f'<p class="prose" id="p{pnum}">'
                    + site.renderer.render_inline(
                        block.raw, glossary_sec, "", allow_xrefs=False, allow_terms=False
                    )
                    + "</p>"
                )
    terms_by_letter = group_by_letter(site.terms, key=lambda t: t.headword)
    letters = list(terms_by_letter.keys())
    parts = [
        '<header class="page-header"><h1>Словарь терминов</h1>',
        '<p class="page-subtitle">Приложение Б и определения из раздела «Метод и термины». '
        'Определения приведены полностью, с указанием источника.</p></header>',
        "".join(intro),
        letter_nav(letters, "letter-"),
        '<div class="filter-row"><label for="glossary-filter">Фильтр по терминам</label>'
        '<input id="glossary-filter" type="search" placeholder="Например: фитра" '
        'data-filter-target=".glossary-entry" data-filter-text="data-term-text"></div>',
    ]
    for letter, terms in terms_by_letter.items():
        parts.append(f'<h2 class="letter-heading" id="letter-{esc(letter)}">{esc(letter)}</h2>')
        for term in sorted(terms, key=lambda t: t.headword.lower()):
            count = sum(o["count"] for o in term.occurrences)
            parts.append(
                f'<article class="glossary-entry" id="g-{esc(term.slug)}" '
                f'data-term-text="{esc(term.headword + " " + term.first_definition)}">'
                f'<h3><a href="terms/{esc(term.slug)}.html">{esc(term.headword)}</a></h3>'
                + term_definitions_html(term, site, "", compact=True)
                + f'<p class="occurrence-note"><a href="terms/{esc(term.slug)}.html">'
                f'Все употребления: {count}</a></p></article>'
            )
    content = "".join(parts)
    return page_shell(
        site,
        title="Словарь терминов",
        content=content,
        root="",
        active="glossary",
        description="Словарь терминов книги «Пределы обоснования».",
    )


def render_term(site: Site, term: Term) -> str:
    definitions = term_definitions_html(term, site, "../")
    occ_parts = []
    for occ in term.occurrences:
        occ_parts.append(
            f'<li><a href="../{esc(occ["article_url"])}#{esc(occ["anchor"])}">'
            f'{esc(occ["article_title"])}</a> '
            f'<span class="muted">— {occ["count"]} '
            f'{plural(occ["count"], "упоминание", "упоминания", "упоминаний")}</span>'
            f'<div class="occurrence-excerpt">«{esc(occ["text"])}»</div></li>'
        )
    occurrences = (
        '<section class="article-section" id="occurrences"><h2>Упоминания в тексте</h2>'
        '<p class="section-note">По одному первому примеру на раздел; полный поиск — '
        '<a href="../search.html">в разделе «Поиск»</a>.</p>'
        f'<ul class="occurrence-list">{"".join(occ_parts)}</ul></section>'
        if occ_parts else
        '<section class="article-section" id="occurrences"><h2>Упоминания в тексте</h2>'
        '<p>Термин встречается в определениях и в указанных источниках.</p></section>'
    )
    related = getattr(term, "related", []) or []
    related_html = ""
    if related:
        links = "".join(
            f'<li><a href="../terms/{esc(t.slug)}.html">{esc(t.headword)}</a></li>'
            for t in related
        )
        related_html = (
            '<section class="article-section" id="related"><h2>Связанные термины</h2>'
            f'<ul class="term-list">{links}</ul></section>'
        )
    content = f"""
{crumbs("../", [("index.html", "Главная"), ("glossary.html", "Словарь"), (None, term.headword)])}
<article class="term-page">
  <header class="article-header">
    <h1>{esc(term.headword)}</h1>
    <div class="article-subtitle">Термин исследования · словарная статья</div>
  </header>
  <section class="article-section" id="definitions">
    <h2>Значение</h2>
    {definitions}
  </section>
  {occurrences}
  {related_html}
</article>
"""
    return page_shell(
        site,
        title=term.headword,
        content=content,
        root="../",
        active="glossary",
        description=f"{term.headword}: {term.first_definition[:180]}",
        body_class="term-page",
        page_kind="term",
    )


# ---------------------------------------------------------------------------
# Литература
# ---------------------------------------------------------------------------

def render_bibliography(site: Site) -> str:
    by_letter = group_by_letter(site.bib, key=lambda e: e.text)
    letters = list(by_letter.keys())
    parts = [
        '<header class="page-header"><h1>Литература</h1>',
        f'<p class="page-subtitle">{len(site.bib)} источников. Номера соответствуют '
        'ссылкам в тексте; у каждой записи есть обратные ссылки на разделы. '
        'Порядок записей соответствует книге, поэтому латинские имена открывают список.</p></header>',
        letter_nav(letters, "letter-"),
        '<div class="filter-row"><label for="bib-filter">Фильтр по автору или названию</label>'
        '<input id="bib-filter" type="search" placeholder="Например: Гёдель" '
        'data-filter-target=".bib-entry" data-filter-text="data-bib-text"></div>',
    ]
    for letter, entries in by_letter.items():
        parts.append(f'<h2 class="letter-heading" id="letter-{esc(letter)}">{esc(letter)}</h2>')
        parts.append('<ol class="bibliography-list">')
        for entry in sorted(entries, key=lambda e: e.number):
            backlinks = ""
            if entry.cited_in:
                links = []
                for num in entry.cited_in:
                    sec = site.section(num)
                    if sec:
                        links.append(
                            f'<a href="articles/{esc(sec.slug)}.html#src-{entry.number}">'
                            f'{esc(sec.label)}</a>'
                        )
                if links:
                    backlinks = '<div class="bib-backlinks">Цитируется: ' + ", ".join(links) + "</div>"
            parts.append(
                f'<li class="bib-entry" id="b-{entry.number}" '
                f'data-bib-text="{esc(entry.text)}">'
                f'<span class="bib-number">[{entry.number}]</span> '
                f'<span class="bib-text">{render_bib_entry_text(entry, site, "")}</span>'
                f'{backlinks}</li>'
            )
        parts.append("</ol>")
    content = "".join(parts)
    return page_shell(
        site,
        title="Литература",
        content=content,
        root="",
        active="bibliography",
        description="Полный список литературы книги «Пределы обоснования».",
    )


# ---------------------------------------------------------------------------
# Цитаты
# ---------------------------------------------------------------------------

def render_quotes(site: Site) -> str:
    parts = [
        '<header class="page-header"><h1>Аяты и хадисы</h1>',
        '<p class="page-subtitle">Все цитаты Писания, приведённые в книге, '
        'в порядке появления. Полный текст сохранён; указан раздел.</p></header>',
        '<div class="filter-row quote-filters">'
        '<label for="quote-filter">Фильтр по тексту</label>'
        '<input id="quote-filter" type="search" placeholder="Например: милость" '
        'data-filter-target=".quote-entry" data-filter-text="data-quote-text">'
        '<div class="segmented" role="group" aria-label="Тип цитаты">'
        '<button type="button" class="active" data-quote-filter="all">Все</button>'
        '<button type="button" data-quote-filter="quran">Коран</button>'
        '<button type="button" data-quote-filter="hadith">Хадисы</button>'
        '<button type="button" data-quote-filter="other">Прочее</button>'
        '</div></div>',
    ]
    for q in site.quotes:
        kind = q.kind.lower()
        cls = "quran" if kind == "коран" else ("hadith" if kind == "хадис" else "other")
        badge = q.kind
        parts.append(
            f'<article class="quote-entry" id="quote-{q.number}" data-quote-kind="{cls}" '
            f'data-quote-text="{esc(q.text)}">'
            f'<div class="quote-entry-head"><span class="badge badge-{cls}">{esc(badge)}</span>'
            f'<span class="muted">{esc(q.article.label)} · {esc(q.article.title)}</span></div>'
            f'<blockquote>{q.html}</blockquote>'
            f'<div class="quote-entry-foot"><a href="articles/{esc(q.article.slug)}.html#{esc(q.anchor)}">'
            f'Открыть в тексте</a></div></article>'
        )
    content = "".join(parts)
    return page_shell(
        site,
        title="Аяты и хадисы",
        content=content,
        root="",
        active="quotes",
        description="Указатель цитат Корана и хадисов в книге «Пределы обоснования».",
    )


# ---------------------------------------------------------------------------
# Приложения
# ---------------------------------------------------------------------------

def render_objections(site: Site) -> str:
    sec = site.section("A")
    assert sec is not None
    n_obj = len([i for b in sec.blocks if b.kind == "list" for i in b.items])
    body = render_section_body(sec, site, "")
    content = f"""
{crumbs("", [("index.html", "Главная"), ("contents.html", "Содержание"), (None, "Приложение А")])}
<header class="page-header">
  <h1>Карта сильнейших возражений и ответов</h1>
  <p class="page-subtitle">Приложение А · {n_obj} {plural(n_obj, "пункт", "пункта", "пунктов")}</p>
</header>
<div class="filter-row"><label for="objections-filter">Фильтр по возражению</label>
<input id="objections-filter" type="search" placeholder="Например: Гёдель"
       data-filter-target=".list-objections > li" data-filter-text="data-filter-text"></div>
{body}
"""
    return page_shell(
        site,
        title="Карта сильнейших возражений и ответов",
        content=content,
        root="",
        active="objections",
        description="Приложение А книги «Пределы обоснования»: возражения и ответы.",
        body_class="appendix-page",
    )


def render_systems(site: Site) -> str:
    sec = site.section("C")
    assert sec is not None
    body = render_section_body(sec, site, "")
    # Сравнительная таблица из раздела 46.
    table_html = ""
    sec46 = site.section("46")
    if sec46:
        for block in sec46.blocks:
            if block.kind == "table":
                table_html = render_table(block, sec46, site, "")
                break
    content = f"""
{crumbs("", [("index.html", "Главная"), ("contents.html", "Содержание"), (None, "Приложение В")])}
<header class="page-header">
  <h1>Сравнительная матрица мировоззренческих систем</h1>
  <p class="page-subtitle">Приложение В · системы, их притязания и итог испытания</p>
</header>
{f'<section class="article-section" id="comparative-table"><h2>Сравнительная таблица</h2><p class="section-note">Фрагмент раздела 46 «Конкуренты в профиле».</p>{table_html}</section>' if table_html else ''}
<div class="filter-row"><label for="systems-filter">Фильтр по системе</label>
<input id="systems-filter" type="search" placeholder="Например: буддизм"
       data-filter-target=".list-systems > li" data-filter-text="data-filter-text"></div>
{body}
"""
    return page_shell(
        site,
        title="Сравнительная матрица мировоззренческих систем",
        content=content,
        root="",
        active="systems",
        description="Приложение В книги «Пределы обоснования»: сравнительная матрица систем.",
        body_class="appendix-page",
    )


# ---------------------------------------------------------------------------
# Теоремы
# ---------------------------------------------------------------------------

def render_theorems(site: Site) -> str:
    sec7 = site.section("7")
    sec8 = site.section("8")
    assert sec7 and sec8
    render_section_body(sec7, site, "")
    render_section_body(sec8, site, "")
    th1 = sec7.theorem_groups.get("1", "")
    th2 = sec8.theorem_groups.get("2", "")
    lemma_html = ""
    for block in sec7.blocks:
        if block.kind == "para" and block.raw.startswith("Доказательство опирается на лемму о диагонализации"):
            lemma_html = (
                f'<p class="prose" id="lemma-statement">'
                f'{site.renderer.render_inline(block.raw, sec7, "")}</p>'
            )
            break
    # Условия D1–D3 из раздела 8.
    conditions = ""
    used: set[str] = set()
    for block in sec8.blocks:
        if block.kind == "list" and block.meta.get("list_type") == "conditions":
            conditions = render_list(block, sec8, site, "", used)
            break
    content = f"""
{crumbs("", [("index.html", "Главная"), ("contents.html", "Содержание"), (None, "Теоремы")])}
<header class="page-header">
  <h1>Теоремы и ключевые формулировки</h1>
  <p class="page-subtitle">Точные формулировки из книги. Полные доказательства —
  в разделах 7 и 8.</p>
</header>
<article class="article theorem-page">
  <section class="article-section" id="first-theorem">
    <h2>Первая теорема о неполноте</h2>
    {th1}
    <p class="section-note"><a href="articles/07-pervaya-teorema-o-nepolnote.html#proof-1">Полное доказательство →</a></p>
  </section>
  <section class="article-section" id="lemma">
    <h2>Лемма о диагонализации</h2>
    {lemma_html}
    <p class="section-note">Формулировка из раздела 7 «Первая теорема о неполноте».</p>
  </section>
  <section class="article-section" id="second-theorem">
    <h2>Вторая теорема о неполноте</h2>
    {th2}
    <p class="section-note"><a href="articles/08-vtoraya-teorema-o-nepolnote.html#proof-2">Полное доказательство →</a></p>
  </section>
  <section class="article-section" id="conditions">
    <h2>Условия выводимости (D1)–(D3)</h2>
    {conditions}
    <p class="section-note">Формулировка из раздела 8 «Вторая теорема о неполноте».</p>
  </section>
  <section class="article-section" id="definitions">
    <h2>Связанные определения</h2>
    <ul class="term-list">
      <li><a href="terms/dostatochnaya-slozhnost.html">Достаточная сложность</a></li>
      <li><a href="terms/formalnaya-sistema.html">Формальная система</a></li>
      <li><a href="terms/vychislimost.html">Вычислимость</a></li>
      <li><a href="terms/sintaksis.html">Синтаксис</a></li>
      <li><a href="terms/semantika.html">Семантика</a></li>
    </ul>
  </section>
</article>
"""
    return page_shell(
        site,
        title="Теоремы и ключевые формулировки",
        content=content,
        root="",
        active="theorems",
        description="Точные формулировки теорем Гёделя о неполноте из книги «Пределы обоснования».",
        page_kind="theorems",
    )


# ---------------------------------------------------------------------------
# Указатели
# ---------------------------------------------------------------------------

def render_index_az(site: Site) -> str:
    terms_by_letter = group_by_letter(site.terms, key=lambda t: t.headword)
    articles_by_letter = group_by_letter(site.numbered_sections, key=lambda s: s.title)
    letters = sorted(set(terms_by_letter) | set(articles_by_letter))
    parts = [
        '<header class="page-header"><h1>Указатель А–Я</h1>',
        '<p class="page-subtitle">Термины и статьи по алфавиту.</p></header>',
        '<h2>Термины</h2>',
        letter_nav(list(terms_by_letter.keys()), "terms-letter-"),
    ]
    for letter, terms in terms_by_letter.items():
        parts.append(f'<h3 class="letter-heading" id="terms-letter-{esc(letter)}">{esc(letter)}</h3><ul class="az-list">')
        for term in sorted(terms, key=lambda t: t.headword.lower()):
            parts.append(f'<li><a href="terms/{esc(term.slug)}.html">{esc(term.headword)}</a></li>')
        parts.append("</ul>")
    parts.append('<h2>Статьи</h2>')
    parts.append(letter_nav(list(articles_by_letter.keys()), "articles-letter-"))
    for letter, sections in articles_by_letter.items():
        parts.append(f'<h3 class="letter-heading" id="articles-letter-{esc(letter)}">{esc(letter)}</h3><ul class="az-list">')
        for sec in sorted(sections, key=lambda s: s.sort_key):
            parts.append(
                f'<li><a href="{esc(sec.url)}">{esc(sec.title)}</a> '
                f'<span class="muted">— {esc(sec.label)}</span></li>'
            )
        parts.append("</ul>")
    content = "".join(parts)
    return page_shell(
        site,
        title="Указатель А–Я",
        content=content,
        root="",
        active="az",
        description="Алфавитный указатель терминов и статей энциклопедии.",
    )


def render_categories(site: Site) -> str:
    by_cat: dict[str, list[Section]] = defaultdict(list)
    for sec in site.sections:
        for cid in sec.categories:
            by_cat[cid].append(sec)
    parts = [
        '<header class="page-header"><h1>Категории</h1>',
        '<p class="page-subtitle">Тематические категории статей.</p></header>',
        '<div class="category-cloud">',
    ]
    for cid in config.CATEGORIES:
        if cid in by_cat:
            parts.append(f'<a href="#cat-{esc(cid)}">{esc(config.CATEGORIES[cid])} <span class="muted">{len(by_cat[cid])}</span></a>')
    parts.append("</div>")
    for cid, title in config.CATEGORIES.items():
        sections = sorted(by_cat.get(cid, []), key=lambda s: s.sort_key)
        if not sections:
            continue
        parts.append(f'<section class="category-section" id="cat-{esc(cid)}"><h2>{esc(title)}</h2><ul class="link-list">')
        for sec in sections:
            url = site.appendix_url(sec.num) if sec.starred else sec.url
            title_text = sec.title.split(". ", 1)[-1] if sec.starred else sec.title
            parts.append(f'<li><a href="{url}">{esc(title_text)}</a> <span class="muted">— {esc(sec.label)}</span></li>')
        parts.append("</ul></section>")
    content = "".join(parts)
    return page_shell(
        site,
        title="Категории",
        content=content,
        root="",
        active="categories",
        description="Тематические категории статей энциклопедии.",
    )


# ---------------------------------------------------------------------------
# О книге, отчёт, поиск
# ---------------------------------------------------------------------------

def render_about(site: Site) -> str:
    front = site.front
    abstract = "".join(
        f'<p class="prose">{site.renderer.render_inline(p, None, "", allow_xrefs=False, allow_terms=False)}</p>'
        for p in front.get("abstract_paras", [])
    )
    cover = (
        f'<figure class="cover-figure">'
        f'<img src="assets/img/cover.webp" alt="Обложка книги «{esc(config.SITE_TITLE)}»" '
        f'width="320" loading="lazy">'
        f'<figcaption>{esc(config.BOOK_SHORT_TITLE)}. {esc(config.EDITION)}</figcaption>'
        f'</figure>'
    )
    content = f"""
<header class="page-header"><h1>О книге и проекте</h1>
<p class="page-subtitle">Библиографические сведения и аннотация.</p></header>
<article class="about-page">
  <div class="about-layout">
    <aside class="about-cover">{cover}</aside>
    <div class="about-body">
      <section class="article-section">
        <h2>Издание</h2>
        <table class="meta-table">
          <tr><th>Автор</th><td>{esc(config.AUTHOR)}</td></tr>
          <tr><th>Название</th><td>{esc(config.BOOK_TITLE)}</td></tr>
          <tr><th>Краткое название</th><td>{esc(front.get("short_title", ""))}</td></tr>
          <tr><th>Издание</th><td>{esc(config.EDITION)}</td></tr>
          <tr><th>Дата</th><td>{esc(config.BOOK_DATE)}</td></tr>
          <tr><th>Издатель</th><td>{esc(config.PUBLISHER)}</td></tr>
          <tr><th>Классификация</th><td>{esc(front.get("subjclass", ""))}</td></tr>
          <tr><th>Лицензия текста</th><td><a href="{config.LICENSE_URL}">{esc(config.LICENSE)}</a></td></tr>
        </table>
      </section>
      <div class="basmala" lang="ar" dir="rtl" aria-label="Басмала">﷽</div>
      <section class="article-section">
        <h2>Аннотация</h2>
        {abstract}
      </section>
      <section class="article-section">
        <h2>Выходные данные</h2>
        <p class="imprint">{esc(config.IMPRINT)}</p>
        <p class="section-note">Ключевые слова: {esc(front.get("keywords", ""))}.</p>
      </section>
      <section class="article-section" id="citation">
        <h2>Цитирование</h2>
        <p class="citation-text">Викулов, И. С. (2026). <em>{esc(config.CITATION_TITLE)}</em>.
        Zenodo. <a href="{config.DOI_URL}">{config.DOI_URL}</a></p>
        <p><a href="{config.PDF_NAME}" download="{config.PDF_NAME}">Скачать PDF книги</a></p>
      </section>
    </div>
  </div>
</article>
"""
    return page_shell(
        site,
        title="О книге и проекте",
        content=content,
        root="",
        active="about",
        description="О книге «Пределы обоснования».",
    )


def render_build_report(site: Site) -> str:
    r = site.report
    counts = r.get("counts", {})
    rows = "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in counts.items())
    warnings = r.get("warnings", [])
    unresolved = r.get("unresolved_xrefs", [])
    links = r.get("link_check", {})
    fidelity = r.get("fidelity", [])
    fid_rows = "".join(
        f"<tr><td>{esc(f['label'])}</td><td>{f['blocks']}</td><td>{f['theses']}</td>"
        f"<td>{esc(f['status'])}</td></tr>"
        for f in fidelity
    )
    content = f"""
<header class="page-header"><h1>Отчёт о сборке</h1>
<p class="page-subtitle">Служебная страница: числа, проверки и предупреждения.</p></header>
<article class="article about-page">
  <section class="article-section"><h2>Общие сведения</h2>
  <table class="meta-table">{rows}</table></section>
  <section class="article-section"><h2>Проверка ссылок</h2>
  <table class="meta-table">
    <tr><th>Внутренних ссылок</th><td>{links.get("total", "—")}</td></tr>
    <tr><th>Битых ссылок</th><td>{links.get("broken", "—")}</td></tr>
    <tr><th>Проверено якорей</th><td>{links.get("anchors", "—")}</td></tr>
  </table>
  {f'<p class="error">{esc(", ".join(links.get("examples", [])))}</p>' if links.get("examples") else '<p>Битых ссылок не найдено.</p>'}
  </section>
  <section class="article-section"><h2>Текст и блоки</h2>
  <table class="wikitable"><thead><tr><th>Раздел</th><th>Блоков</th><th>Тезисов</th><th>Сверка</th></tr></thead>
  <tbody>{fid_rows}</tbody></table></section>
  <section class="article-section"><h2>Предупреждения</h2>
  {f'<ul class="warn-list">{"".join(f"<li>{esc(w)}</li>" for w in warnings)}</ul>' if warnings else '<p>Предупреждений нет.</p>'}
  </section>
  <section class="article-section"><h2>Общие ссылки «раздел о …»</h2>
  <p class="section-note">Эти фразы относятся к нескольким разделам или к теме в целом;
  они оставлены текстом, чтобы не ставить ложную ссылку на одну статью.</p>
  {f'<ul class="warn-list">{"".join(f"<li>{esc(w)}</li>" for w in unresolved)}</ul>' if unresolved else '<p>Все ссылки распознаны.</p>'}
  </section>
</article>
"""
    return page_shell(
        site,
        title="Отчёт о сборке",
        content=content,
        root="",
        active="",
        description="Служебный отчёт о сборке статической энциклопедии.",
    )


def render_search_page(site: Site) -> str:
    content = f"""
<header class="page-header"><h1>Поиск</h1>
<p class="page-subtitle">Поиск по тезисам, статьям, словарю, литературе, цитатам,
возражениям и системам.</p></header>
<form class="search-form page-search" id="page-search-form" action="search.html" method="get" role="search">
  <label class="visually-hidden" for="page-search-input">Поисковый запрос</label>
  <input id="page-search-input" name="q" type="search" placeholder="Введите слово или фразу"
         autocomplete="off" spellcheck="false">
  <button type="submit" class="search-submit">Искать</button>
</form>
<div class="search-toolbar">
  <div class="search-tabs" role="tablist" aria-label="Тип результата">
    <button type="button" class="active" data-search-type="all" role="tab" aria-selected="true">Всё</button>
    <button type="button" data-search-type="thesis" role="tab" aria-selected="false">Тезисы</button>
    <button type="button" data-search-type="article" role="tab" aria-selected="false">Статьи</button>
    <button type="button" data-search-type="glossary" role="tab" aria-selected="false">Словарь</button>
    <button type="button" data-search-type="bibliography" role="tab" aria-selected="false">Литература</button>
    <button type="button" data-search-type="quote" role="tab" aria-selected="false">Цитаты</button>
    <button type="button" data-search-type="objection" role="tab" aria-selected="false">Возражения</button>
    <button type="button" data-search-type="system" role="tab" aria-selected="false">Системы</button>
  </div>
  <label class="sort-label">Сортировка
    <select id="search-sort">
      <option value="relevance">по релевантности</option>
      <option value="book">по порядку книги</option>
    </select>
  </label>
</div>
<div class="search-status" id="search-status" aria-live="polite">Загрузка поиска…</div>
<div class="search-results" id="search-results"></div>
<button class="load-more" id="search-more" type="button" hidden>Показать ещё</button>
<noscript>
  <p>Для поиска нужен JavaScript. Полное содержание доступно
  <a href="contents.html">на странице содержания</a>, а словарь —
  <a href="glossary.html">в словаре терминов</a>.</p>
</noscript>
"""
    return page_shell(
        site,
        title="Поиск",
        content=content,
        root="",
        active="search",
        description="Поиск по энциклопедии «Пределы обоснования».",
        extra_scripts='<script defer src="assets/search-data.js"></script><script defer src="assets/search.js"></script>',
    )


def render_404(site: Site) -> str:
    content = """
<header class="page-header"><h1>Страница не найдена</h1>
<p class="page-subtitle">Такой страницы нет или ссылка устарела.</p></header>
<p><a href="index.html">На главную</a> · <a href="contents.html">Содержание</a> ·
<a href="search.html">Поиск</a></p>
"""
    return page_shell(
        site,
        title="Страница не найдена",
        content=content,
        root="",
        active="",
    )
