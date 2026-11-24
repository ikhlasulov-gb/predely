# -*- coding: utf-8 -*-
"""Рендеринг блоков статьи, теорем, цитат, списков и таблиц."""

from __future__ import annotations

import html
from typing import Any

from . import config
from .model import Site
from .texparse import (
    Block,
    Section,
    Sentence,
    count_words,
    math_to_text,
    section_paragraph_map,
)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def sentence_html(
    sentence: Sentence,
    section: Section,
    site: Site,
    root: str,
    used_terms: set[str],
    allow_terms: bool = True,
) -> str:
    inner = site.renderer.render_inline(
        sentence.raw,
        section,
        root,
        allow_terms=allow_terms,
        used_terms=used_terms,
    )
    return (
        f'<span class="thesis" id="{sentence.anchor}" '
        f'data-thesis-number="{sentence.number}">{inner}'
        f'<a class="thesis-permalink" href="#{sentence.anchor}" '
        f'aria-label="Постоянная ссылка на тезис" title="Ссылка на тезис">¶</a></span>'
    )


def block_permalink(anchor: str) -> str:
    return (
        f'<a class="block-permalink" href="#{anchor}" '
        f'aria-label="Постоянная ссылка" title="Ссылка на этот фрагмент">¶</a>'
    )


def render_equation(block: Block) -> str:
    fallback = html.escape(math_to_text(block.raw))
    tex = html.escape(block.raw, quote=True)
    return (
        f'<div class="equation" id="{block.anchor}">'
        f'<div class="equation-math"><span class="tex tex-display" data-tex="{tex}">'
        f"{fallback}</span></div>"
        f'<span class="eqno">({block.number})</span></div>'
    )


def render_quote(block: Block, section: Section, site: Site, root: str) -> str:
    inner = site.renderer.render_inline(
        block.raw, section, root, allow_xrefs=False, allow_terms=False
    )
    return (
        f'<figure class="quote-block" id="{block.anchor}">'
        f"<blockquote>{inner}</blockquote></figure>"
    )


def render_list(
    block: Block,
    section: Section,
    site: Site,
    root: str,
    used_terms: set[str],
) -> str:
    list_type = block.meta.get("list_type", "list")
    allow_terms = list_type in ("objections", "systems")
    items_html: list[str] = []
    for item in block.items:
        spans = []
        for sentence in item.get("sentences", []):
            spans.append(sentence_html(
                sentence, section, site, root, used_terms, allow_terms=allow_terms
            ))
        items_html.append(
            f'<li id="{item["anchor"]}" data-item-number="{item["number"]}">'
            + " ".join(spans)
            + block_permalink(item["anchor"])
            + "</li>"
        )
    return (
        f'<ul class="book-list list-{list_type}" id="{block.anchor}">'
        + "".join(items_html)
        + "</ul>"
    )


def render_table(block: Block, section: Section, site: Site, root: str) -> str:
    rows = block.rows
    if not rows:
        return ""
    header = rows[0]
    body = rows[1:]

    def cell(tag: str, text: str, scope: str | None = None) -> str:
        attrs = f' scope="{scope}"' if scope else ""
        inner = site.renderer.render_inline(
            text, section, root, allow_xrefs=False, allow_terms=False
        )
        return f"<{tag}{attrs}>{inner}</{tag}>"

    thead = "<thead><tr>" + "".join(cell("th", c, "col") for c in header) + "</tr></thead>"
    tbody_rows = []
    for row in body:
        tbody_rows.append("<tr>" + "".join(cell("td", c) for c in row) + "</tr>")
    tbody = "<tbody>" + "".join(tbody_rows) + "</tbody>" if tbody_rows else ""
    return (
        f'<div class="table-wrap"><table class="wikitable" id="{block.anchor}">'
        f"{thead}{tbody}</table></div>"
    )


def render_paragraph(
    block: Block,
    section: Section,
    site: Site,
    root: str,
    used_terms: set[str],
    *,
    lead: bool = False,
    continuation: bool = False,
) -> str:
    spans = [
        sentence_html(s, section, site, root, used_terms)
        for s in block.sentences
    ]
    classes = ["prose"]
    if lead:
        classes.append("lead")
    if block.meta.get("theorem"):
        classes.append("theorem-statement")
    if block.meta.get("proof"):
        classes.append("proof-start")
    if continuation:
        classes.append("theorem-continuation")
    return (
        f'<p class="{" ".join(classes)}" id="{block.anchor}" '
        f'data-para-number="{block.number}">'
        + " ".join(spans)
        + block_permalink(block.anchor)
        + "</p>"
    )


def render_section_body(section: Section, site: Site, root: str) -> str:
    """Возвращает HTML тела статьи и заполняет theorem_groups/term_ids."""
    parts: list[str] = []
    used_terms: set[str] = set()
    lead_added = False
    blocks = section.blocks
    i = 0
    while i < len(blocks):
        block = blocks[i]
        if block.kind == "para" and block.meta.get("theorem"):
            n = block.meta["theorem"]
            group_parts: list[str] = []
            group_parts.append(render_paragraph(
                block, section, site, root, used_terms, lead=not lead_added
            ))
            lead_added = True
            j = i + 1
            if j < len(blocks) and blocks[j].kind == "equation":
                group_parts.append(render_equation(blocks[j]))
                j += 1
                if j < len(blocks) and blocks[j].kind == "para" and re_starts_continuation(blocks[j].raw):
                    group_parts.append(render_paragraph(
                        blocks[j], section, site, root, used_terms, continuation=True
                    ))
                    j += 1
            group_html = (
                f'<div class="theorem-box" id="theorem-{n}">'
                + "".join(group_parts)
                + "</div>"
            )
            section.theorem_groups[n] = group_html
            parts.append(group_html)
            i = j
            continue

        if block.kind == "para" and block.meta.get("proof"):
            n = block.meta.get("proof") or ""
            inner = render_paragraph(
                block, section, site, root, used_terms, lead=not lead_added
            )
            lead_added = True
            if n:
                group_html = f'<div class="proof-start" id="proof-{n}">{inner}</div>'
                section.theorem_groups[f"proof-{n}"] = group_html
                parts.append(group_html)
            else:
                parts.append(inner)
            i += 1
            continue

        if block.kind == "para":
            parts.append(render_paragraph(
                block, section, site, root, used_terms, lead=not lead_added
            ))
            lead_added = True
        elif block.kind == "quote":
            parts.append(render_quote(block, section, site, root))
        elif block.kind == "list":
            parts.append(render_list(block, section, site, root, used_terms))
        elif block.kind == "equation":
            parts.append(render_equation(block))
        elif block.kind == "table":
            parts.append(render_table(block, section, site, root))
        i += 1
    body_html = '<div id="text" class="article-text">' + "".join(parts) + "</div>"
    setattr(section, "body_html", body_html)
    return body_html


def re_starts_continuation(raw: str) -> bool:
    return raw.lstrip().lower().startswith(("и при этом", "где ", "тогда "))


def render_bib_entry_text(entry, site: Site, root: str) -> str:
    return site.renderer.render_inline(
        entry.text, None, root, allow_xrefs=False, allow_terms=False
    )


def render_sources(section: Section, site: Site, root: str) -> str:
    entries = []
    for key in section.source_keys:
        entry = site.bib_by_key.get(key)
        if entry:
            entries.append(entry)
    entries.sort(key=lambda e: e.number)
    if not entries:
        return ""
    items = []
    for entry in entries:
        items.append(
            f'<li id="src-{entry.number}"><span class="bib-number">[{entry.number}]</span> '
            f'{render_bib_entry_text(entry, site, root)} '
            f'<a class="source-link" href="{root}bibliography.html#b-{entry.number}">в литературе</a></li>'
        )
    return (
        '<section class="article-section" id="sources">'
        "<h2>Источники</h2>"
        '<p class="section-note">Номера соответствуют списку литературы. '
        "Полные записи и обратные ссылки — в разделе «Литература».</p>"
        f'<ol class="source-list">{"".join(items)}</ol>'
        "</section>"
    )


def see_also_lists(section: Section, site: Site) -> tuple[list[Section], list[Section]]:
    outgoing: list[Section | None] = []
    incoming: list[Section | None] = []
    for target in section.xref_targets:
        if target == section.num or target in ("A", "B", "C"):
            continue
        outgoing.append(site.section(target))
    for source in section.xref_sources:
        if source == section.num or source in ("A", "B", "C"):
            continue
        incoming.append(site.section(source))
    outgoing = sorted({s.num: s for s in outgoing if s}.values(), key=lambda s: s.sort_key)
    incoming = sorted({s.num: s for s in incoming if s}.values(), key=lambda s: s.sort_key)
    return outgoing, incoming


def render_see_also(section: Section, site: Site, root: str) -> str:
    outgoing, incoming = see_also_lists(section, site)
    if not outgoing and not incoming:
        return ""
    parts = ['<section class="article-section" id="see-also"><h2>См. также</h2>']
    if outgoing:
        parts.append('<h3>В этой статье есть ссылки</h3><ul class="see-list">')
        for s in outgoing:
            parts.append(f'<li><a href="{root}{s.url}">{esc(s.title)}</a> <span class="muted">— {esc(s.label)}</span></li>')
        parts.append("</ul>")
    if incoming:
        parts.append('<h3>На эту статью ссылаются</h3><ul class="see-list">')
        for s in incoming:
            parts.append(f'<li><a href="{root}{s.url}">{esc(s.title)}</a> <span class="muted">— {esc(s.label)}</span></li>')
        parts.append("</ul>")
    parts.append("</section>")
    return "".join(parts)


def render_key_terms(section: Section, site: Site, root: str) -> str:
    terms = [site.terms_by_id[tid] for tid in section.term_ids if tid in site.terms_by_id]
    terms.sort(key=lambda t: t.headword.lower())
    if not terms:
        return ""
    def short_def(t):
        plain = site.renderer.render_plain(t.first_definition, None)
        return plain[:110] + ("…" if len(plain) > 110 else "")
    links = "".join(
        f'<li><a href="{root}{t.url}">{esc(t.headword)}</a> '
        f'<span class="muted">— {esc(short_def(t))}</span></li>'
        for t in terms
    )
    return (
        '<section class="article-section" id="key-terms"><h2>Ключевые понятия</h2>'
        f'<ul class="term-list">{links}</ul></section>'
    )


def render_categories(section: Section, site: Site, root: str) -> str:
    if not section.categories:
        return ""
    links = " · ".join(
        f'<a href="{root}categories.html#cat-{esc(cid)}">{esc(site.category_name(cid))}</a>'
        for cid in section.categories
    )
    return (
        '<section class="article-section" id="categories"><h2>Категории</h2>'
        f'<p class="category-links">{links}</p></section>'
    )


def render_prev_next(section: Section, site: Site, root: str) -> str:
    prev, nxt = site.prev_next(section)
    parts = ['<nav class="prev-next" aria-label="Навигация по книге">']
    def nav_url(s):
        return site.appendix_url(s.num) if s.starred else s.url

    def nav_label(s):
        if s.starred:
            return s.title
        return f"{s.label}. {s.title}"

    if prev:
        parts.append(
            f'<a class="prev" href="{root}{nav_url(prev)}"><span class="dir">←</span> '
            f'<span class="small">Предыдущий</span><br>{esc(nav_label(prev))}</a>'
        )
    else:
        parts.append("<span></span>")
    if nxt:
        parts.append(
            f'<a class="next" href="{root}{nav_url(nxt)}"><span class="dir">→</span> '
            f'<span class="small">Следующий</span><br>{esc(nav_label(nxt))}</a>'
        )
    parts.append("</nav>")
    return "".join(parts)


def render_infobox(section: Section, site: Site, root: str) -> str:
    cats = " · ".join(
        f'<a href="{root}categories.html#cat-{esc(cid)}">{esc(site.category_name(cid))}</a>'
        for cid in section.categories
    ) or "—"
    group = site.group_title(section.group) or "—"
    rows = [
        ("Раздел", f"{esc(section.label)} из {len(site.numbered_sections)}" if not section.starred else esc(section.label)),
        ("Часть", esc(group)),
        ("Объём", f"{section.words:,} слов".replace(",", " ")),
        ("Тезисов", str(section.thesis_count)),
        ("Цитат", str(section.quote_count)),
        ("Источников", str(len(section.source_keys))),
        ("Категории", cats),
    ]
    body = "".join(f"<tr><th>{esc(k)}</th><td>{v}</td></tr>" for k, v in rows)
    return (
        f'<aside class="infobox" aria-label="Сведения о статье">'
        f'<div class="infobox-title">Сведения</div>'
        f'<table class="infobox-table"><tbody>{body}</tbody></table>'
        f'<div class="infobox-source"><a href="{root}{config.PDF_NAME}" download="{config.PDF_NAME}">Скачать PDF</a></div>'
        f"</aside>"
    )


def render_article_toc(section: Section, site: Site) -> str:
    paras = section_paragraph_map(section, site.renderer)
    items = ['<li><a href="#text">Текст статьи</a></li>']
    if paras:
        items.append('<li class="toc-subhead">Абзацы</li>')
        for anchor, number, label in paras:
            items.append(
                f'<li class="toc-para"><a href="#{anchor}"><span class="toc-num">¶ {number}</span> '
                f'{esc(label)}</a></li>'
            )
    if section.source_keys:
        items.append('<li><a href="#sources">Источники</a></li>')
    outgoing, incoming = see_also_lists(section, site)
    if outgoing or incoming:
        items.append('<li><a href="#see-also">См. также</a></li>')
    if section.term_ids:
        items.append('<li><a href="#key-terms">Ключевые понятия</a></li>')
    if section.categories:
        items.append('<li><a href="#categories">Категории</a></li>')
    return (
        '<div class="toc-box"><div class="toc-heading">Содержание</div>'
        f'<ul class="toc-list">{"".join(items)}</ul></div>'
    )


def render_tabs(section: Section) -> str:
    sources = (
        '<button class="tab" type="button" data-view="sources" role="tab" '
        'aria-selected="false">Источники</button>'
        if section.source_keys else ""
    )
    return (
        '<div class="page-tabs" role="tablist" aria-label="Режим чтения">'
        '<button class="tab active" type="button" data-view="text" role="tab" '
        'aria-selected="true">Статья</button>'
        '<button class="tab" type="button" data-view="theses" role="tab" '
        'aria-selected="false">Тезисы</button>'
        f'{sources}'
        "</div>"
    )
