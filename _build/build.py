# -*- coding: utf-8 -*-
"""Сборка статической энциклопедии «Пределы обоснования»."""

from __future__ import annotations

import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import config, pages, render, terms as terms_mod, texparse
from .model import Site
from .texparse import Quote


OUT = Path(__file__).resolve().parent.parent
BUILD = Path(__file__).resolve().parent
VENDOR = BUILD / "vendor"


# ---------------------------------------------------------------------------
# Служебные проверки
# ---------------------------------------------------------------------------

def tex_plain(raw: str) -> str:
    """Текст без формул, цитат и команд — для сверки с HTML."""
    out: list[str] = []
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == "$":
            end = raw.find("$", i + 1)
            i = end + 1 if end >= 0 else i + 1
            continue
        if raw.startswith("\\cite", i):
            m = re.match(r"\\cite\s*\{", raw[i:])
            if m:
                _, j = texparse.read_group(raw, i + m.end() - 1)
                i = j
                continue
        if ch == "\\":
            m = re.match(r"\\([A-Za-z@]+)\*?", raw[i:])
            if not m:
                i += 1
                continue
            cmd = m.group(1)
            j = i + m.end()
            if cmd in ("textbf", "emph", "textit", "Amiri"):
                while j < n and raw[j].isspace():
                    j += 1
                if j < n and raw[j] == "{":
                    group, j = texparse.read_group(raw, j)
                    out.append(tex_plain(group))
                    i = j
                    continue
            if cmd in ("ldots", "dots", "cdots"):
                out.append("…")
                i = j
                continue
            if cmd in ("&", "%", "$", "#", "_", "{", "}"):
                out.append(cmd)
                i = j
                continue
            if cmd == "hspace":
                while j < n and raw[j].isspace():
                    j += 1
                if j < n and raw[j] == "{":
                    _, j = texparse.read_group(raw, j)
                i = j
                continue
            if cmd in ("relax", "ignorespaces", "par", "noindent", "hfill", "vfill"):
                i = j
                continue
            # Неизвестную команду пропускаем.
            i = j
            continue
        if ch == "{":
            group, j = texparse.read_group(raw, i)
            out.append(tex_plain(group))
            i = j
            continue
        if ch == "}":
            i += 1
            continue
        if ch == "~":
            out.append(" ")
            i += 1
            continue
        out.append(ch)
        i += 1
    return texparse.normalize_ws("".join(out))


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", text)


def source_tokens(sec: texparse.Section) -> list[str]:
    parts: list[str] = []
    for block in sec.blocks:
        if block.kind in ("para", "quote"):
            parts.append(tex_plain(block.raw))
        elif block.kind == "list":
            parts.extend(tex_plain(item["raw"]) for item in block.items)
        elif block.kind == "table":
            for row in block.rows:
                parts.extend(row)
        # Формулы намеренно пропускаются: в HTML они заменяются KaTeX.
    return tokens(" ".join(parts))


def html_tokens(body_html: str) -> list[str]:
    markup = re.sub(r'<span class="tex[^"]*"[^>]*>.*?</span>', " ", body_html, flags=re.S)
    markup = re.sub(r'<span class="eqno">.*?</span>', " ", markup, flags=re.S)
    markup = markup.replace("¶", " ")
    markup = re.sub(r"<[^>]+>", " ", markup)
    text = html.unescape(markup)
    text = re.sub(r"\[\d+(?:\s*,\s*\d+)*\]", " ", text)
    text = re.sub(r"\[\?[^\]]+\]", " ", text)
    return tokens(text)


def fidelity_row(sec: texparse.Section, site: Site) -> dict:
    body = getattr(sec, "body_html", "")
    src = source_tokens(sec)
    got = html_tokens(body)
    if src == got:
        status = "совпадает"
        detail = ""
    else:
        status = "расхождение"
        first = 0
        for i in range(min(len(src), len(got))):
            if src[i] != got[i]:
                first = i
                break
        detail = (
            f"первые токены: источник={src[max(0, first - 2):first + 8]}, "
            f"HTML={got[max(0, first - 2):first + 8]}"
        )
    return {
        "label": f"{sec.label}. {sec.title}",
        "blocks": len(sec.blocks),
        "theses": sec.thesis_count,
        "status": status,
        "detail": detail,
        "src_len": len(src),
        "got_len": len(got),
    }


def find_unresolved_xrefs(sections: list[texparse.Section], renderer: texparse.Renderer) -> list[str]:
    pattern = re.compile(
        r"(?:раздел(?:ы|ов|ам|ами|ах|а|у|ом|е)?|приложени(?:е|я|ю|ем|и))"
        r"\s+(?:о|об|про)\s+[^.;:()]+",
        re.IGNORECASE,
    )
    unresolved: list[str] = []
    for sec in sections:
        texts: list[str] = []
        for block in sec.blocks:
            if block.kind in ("para", "quote"):
                texts.append(block.raw)
            elif block.kind == "list":
                texts.extend(item["raw"] for item in block.items)
        for text in texts:
            for m in pattern.finditer(text):
                phrase = m.group(0).strip()
                refs = renderer.find_xrefs(text)
                if not any(a < m.end() and b > m.start() for a, b, _, _ in refs):
                    snippet = phrase[:150] + ("…" if len(phrase) > 150 else "")
                    unresolved.append(f"{sec.label}: {snippet}")
    # Убираем дубли, сохраняя порядок.
    seen = set()
    result = []
    for item in unresolved:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def check_links(out: Path) -> dict:
    html_files = [p for p in out.rglob("*.html") if "_build" not in p.parts]
    id_cache: dict[Path, set[str]] = {}

    def ids_for(path: Path) -> set[str]:
        if path not in id_cache:
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                text = ""
            id_cache[path] = set(re.findall(r'\bid="([^"]+)"', text))
        return id_cache[path]

    total = 0
    anchors = 0
    broken: list[str] = []
    for file in html_files:
        try:
            markup = file.read_text(encoding="utf-8")
        except Exception:
            continue
        for attr, value in re.findall(r'\b(href|src)="([^"]*)"', markup):
            value = html.unescape(value)
            if not value or value == "#":
                continue
            if re.match(r"^(?:https?:|mailto:|tel:|data:|javascript:)", value, re.I):
                continue
            parts = urlsplit(value)
            if parts.scheme or parts.netloc:
                continue
            total += 1
            path = unquote(parts.path)
            if path:
                if path.startswith("/"):
                    target = (out / path.lstrip("/")).resolve()
                else:
                    target = (file.parent / path).resolve()
                if target.is_dir() or path.endswith("/"):
                    target = target / "index.html"
            else:
                target = file
            if not target.exists():
                broken.append(f"{file.relative_to(out)} → {value} (нет файла)")
                continue
            if parts.fragment and target.suffix.lower() == ".html":
                anchors += 1
                frag = unquote(parts.fragment)
                if frag not in ids_for(target):
                    broken.append(
                        f"{file.relative_to(out)} → {value} (нет якоря #{frag})"
                    )
    return {
        "total": total,
        "anchors": anchors,
        "broken": len(broken),
        "examples": broken[:20],
    }


# ---------------------------------------------------------------------------
# Поисковый индекс
# ---------------------------------------------------------------------------

def build_search_records(site: Site) -> list[dict]:
    records: list[dict] = []
    section_index = {sec.num: i + 1 for i, sec in enumerate(site.sections)}

    def add(**kwargs):
        records.append(kwargs)

    for sec in site.sections:
        base = section_index.get(sec.num, 99) * 1_000_000
        cats = [site.category_name(c) for c in sec.categories]
        if sec.starred:
            article_url = site.appendix_url(sec.num)
            article_title = sec.title
        else:
            article_url = sec.url
            article_title = sec.title
        add(
            type="article",
            title=article_title,
            text=(sec.title + ". " + (sec.lead or ""))[:1200],
            url=article_url,
            order=base,
            label=sec.label,
            num=sec.num,
            cats=cats,
        )
        block_index = 0
        for block in sec.blocks:
            block_index += 1
            if block.kind == "para":
                for sentence in block.sentences:
                    text = site.renderer.render_plain(sentence.raw, sec)
                    para = f"абз. {block.number}"
                    if len(block.sentences) > 1:
                        para += f", тезис {sentence.number}"
                    anchor = block.anchor if sec.num == "B" else sentence.anchor
                    add(
                        type="thesis",
                        text=text,
                        url=f"{article_url}#{anchor}",
                        order=base + block_index * 1000 + sentence.number,
                        articleTitle=article_title,
                        num=sec.num,
                        para=para,
                        cats=cats,
                    )
            elif block.kind == "list":
                list_type = block.meta.get("list_type", "list")
                if list_type in ("terms", "glossary"):
                    continue
                for item in block.items:
                    item_text = site.renderer.render_plain(item["raw"], sec)
                    if list_type == "objections":
                        add(
                            type="objection",
                            text=item_text,
                            url=f"objections.html#{item['anchor']}",
                            order=base + block_index * 1000 + item["number"],
                            articleTitle="Приложение А. Карта сильнейших возражений и ответов",
                            num=sec.num,
                            para=f"пункт {item['number']}",
                            number=item["number"],
                            cats=cats,
                        )
                        continue
                    if list_type == "systems":
                        add(
                            type="system",
                            text=item_text,
                            url=f"systems.html#{item['anchor']}",
                            order=base + block_index * 1000 + item["number"],
                            articleTitle="Приложение В. Сравнительная матрица мировоззренческих систем",
                            num=sec.num,
                            para=f"пункт {item['number']}",
                            number=item["number"],
                            cats=cats,
                        )
                        continue
                    for sentence in item.get("sentences", []):
                        text = site.renderer.render_plain(sentence.raw, sec)
                        if list_type == "conditions":
                            para = f"условие {item['number']}"
                        else:
                            para = f"пункт {item['number']}"
                        add(
                            type="thesis",
                            text=text,
                            url=f"{article_url}#{sentence.anchor}",
                            order=base + block_index * 1000 + item["number"] * 20 + sentence.number,
                            articleTitle=article_title,
                            num=sec.num,
                            para=para,
                            cats=cats,
                        )
            elif block.kind == "quote":
                text = site.renderer.render_plain(block.raw, sec)
                add(
                    type="quote",
                    text=text,
                    url=f"{article_url}#{block.anchor}",
                    order=base + block_index * 1000,
                    articleTitle=article_title,
                    num=sec.num,
                    para="цитата",
                    cats=cats,
                )
            elif block.kind == "equation":
                add(
                    type="thesis",
                    text=texparse.math_to_text(block.raw),
                    url=f"{article_url}#{block.anchor}",
                    order=base + block_index * 1000,
                    articleTitle=article_title,
                    num=sec.num,
                    para=f"формула ({block.number})",
                    cats=cats,
                )
            elif block.kind == "table":
                text = " ".join(" ".join(row) for row in block.rows)
                add(
                    type="thesis",
                    text=site.renderer.render_plain(text, sec),
                    url=f"{article_url}#{block.anchor}",
                    order=base + block_index * 1000,
                    articleTitle=article_title,
                    num=sec.num,
                    para="таблица",
                    cats=cats,
                )

    # Словарь.
    for i, term in enumerate(site.terms):
        definitions = " ".join(
            site.renderer.render_plain(d["text"], site.section(d["source_num"]))
            for d in term.definitions
        )
        add(
            type="glossary",
            title=term.headword,
            text=(term.headword + ". " + definitions)[:2200],
            url=term.url,
            order=91_000_000 + i,
            para="словарь",
            cats=["Словарь"],
        )

    # О книге: аннотация и выходные данные.
    about_text = " ".join([
        config.AUTHOR,
        config.BOOK_TITLE,
        config.EDITION,
        config.BOOK_DATE,
        config.IMPRINT,
        " ".join(site.front.get("abstract_paras", [])),
        site.front.get("cover_description", ""),
    ])
    add(
        type="article",
        title="О книге и проекте",
        text=about_text,
        url="about.html",
        order=93_000_000,
        label="О книге",
        para="о книге",
        cats=["О книге"],
    )

    # Литература.
    for entry in site.bib:
        add(
            type="bibliography",
            title=f"[{entry.number}]",
            text=site.renderer.render_plain(entry.text),
            url=f"bibliography.html#b-{entry.number}",
            order=92_000_000 + entry.number,
            number=entry.number,
            para="литература",
            cats=["Литература"],
        )
    return records


def build_titles(site: Site) -> dict:
    articles = []
    for sec in site.sections:
        articles.append({
            "title": sec.title,
            "url": site.appendix_url(sec.num) if sec.starred else sec.url,
            "label": sec.label,
            "num": sec.num,
            "kind": "appendix" if sec.starred else "section",
        })
    terms = [{"title": t.headword, "url": t.url} for t in site.terms]
    pages_list = [
        ("Главная", "index.html"),
        ("Содержание", "contents.html"),
        ("Указатель А–Я", "index-a-z.html"),
        ("Словарь терминов", "glossary.html"),
        ("Литература", "bibliography.html"),
        ("Аяты и хадисы", "quotes.html"),
        ("Возражения и ответы", "objections.html"),
        ("Мировоззренческие системы", "systems.html"),
        ("Теоремы и формулировки", "theorems.html"),
        ("Категории", "categories.html"),
        ("О книге", "about.html"),
        ("Поиск", "search.html"),
    ]
    return {
        "articles": articles,
        "terms": terms,
        "pages": [{"title": title, "url": url} for title, url in pages_list],
    }


# ---------------------------------------------------------------------------
# Сборка
# ---------------------------------------------------------------------------

def write_page(out: Path, rel: str, content: str) -> Path:
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def prepare_quote_kind(text: str) -> str:
    hadith = [
        "аль-Бухари", "Муслим", "Абу Дауд", "ат-Тирмизи", "ан-Насаи",
        "Ибн Маджа", "Ахмад", "Малик", "ад-Дарими",
    ]
    if any(h.lower() in text.lower() for h in hadith):
        return "Хадис"
    return "Коран"


def main() -> int:
    source = Path(config.SOURCE_FILE).read_text(encoding="utf-8")
    cover = {}
    try:
        cover = json.loads(Path(config.COVER_JSON).read_text(encoding="utf-8"))
    except Exception:
        pass

    front = texparse.parse_front_matter(source)
    front["cover_description"] = cover.get("description", "").strip()
    front["cover_title"] = cover.get("book_title", config.BOOK_SHORT_TITLE)
    front["cover_mark"] = cover.get("mark_text", "")

    sections, _ = texparse.parse_sections(source)
    bib = texparse.parse_bibliography(source)
    sections_by_num = {s.num: s for s in sections}
    renderer = texparse.Renderer(sections_by_num, bib)
    texparse.assign_sections_meta(sections, renderer)

    method_sec = sections_by_num["1"]
    glossary_sec = sections_by_num["B"]
    term_list = terms_mod.extract_terms(method_sec, glossary_sec)
    renderer.set_terms(term_list)
    terms_mod.collect_occurrences(term_list, sections, renderer)

    # Связанные термины: по общим разделам употребления.
    for term in term_list:
        own = {o["article_num"] for o in term.occurrences}
        scored = []
        for other in term_list:
            if other.id == term.id:
                continue
            shared = own & {o["article_num"] for o in other.occurrences}
            if shared:
                scored.append((len(shared), other))
        scored.sort(key=lambda x: (-x[0], x[1].headword.lower()))
        term.related = [x[1] for x in scored[:6]]

    # Цитаты.
    quotes: list[Quote] = []
    qnum = 0
    for sec in sections:
        for block in sec.blocks:
            if block.kind != "quote":
                continue
            qnum += 1
            kind = prepare_quote_kind(block.raw)
            qhtml = renderer.render_inline(
                block.raw, sec, "", allow_xrefs=False, allow_terms=False
            )
            quotes.append(Quote(
                text=block.raw,
                article=sec,
                anchor=block.anchor,
                number=qnum,
                kind=kind,
                html=qhtml,
            ))

    # Обратные ссылки литературы.
    for sec in sections:
        for key in sec.source_keys:
            entry = renderer.bib_by_key.get(key)
            if entry:
                entry.cited_in.append(sec.num)

    site = Site(
        front=front,
        sections=sections,
        bib=bib,
        terms=term_list,
        quotes=quotes,
        renderer=renderer,
        build_date=date.today().strftime("%d.%m.%Y"),
    )

    # Чистим генерируемые каталоги.
    for sub in ("articles", "terms"):
        path = OUT / sub
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
    for name in [
        "index.html", "search.html", "contents.html", "index-a-z.html",
        "glossary.html", "bibliography.html", "quotes.html", "objections.html",
        "systems.html", "theorems.html", "categories.html", "about.html",
        "build-report.html", "BUILD-REPORT.md", "README.md", "404.html",
    ]:
        p = OUT / name
        if p.exists():
            p.unlink()
    old_source = OUT / "source"
    if old_source.exists():
        shutil.rmtree(old_source)

    # Статьи.
    article_files = 0
    for sec in sections:
        if sec.starred:
            continue
        write_page(OUT, sec.url, pages.render_article(site, sec))
        article_files += 1

    # Термины.
    for term in site.terms:
        write_page(OUT, term.url, pages.render_term(site, term))

    # Основные страницы.
    page_map = {
        "index.html": pages.render_home(site),
        "contents.html": pages.render_contents(site),
        "search.html": pages.render_search_page(site),
        "index-a-z.html": pages.render_index_az(site),
        "glossary.html": pages.render_glossary(site),
        "bibliography.html": pages.render_bibliography(site),
        "quotes.html": pages.render_quotes(site),
        "objections.html": pages.render_objections(site),
        "systems.html": pages.render_systems(site),
        "theorems.html": pages.render_theorems(site),
        "categories.html": pages.render_categories(site),
        "about.html": pages.render_about(site),
        "404.html": pages.render_404(site),
    }
    for rel, content in page_map.items():
        write_page(OUT, rel, content)

    # Данные поиска и подсказок.
    records = build_search_records(site)
    search_data = {
        "generated": site.build_date,
        "records": records,
    }
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / "search-data.js").write_text(
        "window.SEARCH_DATA=" + json.dumps(search_data, ensure_ascii=False, separators=(",", ":")) + ";",
        encoding="utf-8",
    )
    titles = build_titles(site)
    (OUT / "assets" / "titles.js").write_text(
        "window.SITE_INDEX=" + json.dumps(titles, ensure_ascii=False, separators=(",", ":")) + ";",
        encoding="utf-8",
    )

    # Ассеты и шрифты.
    assets_dir = OUT / "assets"
    for name in ("style.css", "app.js", "search.js", "favicon.svg"):
        shutil.copy2(BUILD / "assets" / name, assets_dir / name)
    katex_dst = assets_dir / "katex"
    if katex_dst.exists():
        shutil.rmtree(katex_dst)
    katex_dst.mkdir(parents=True, exist_ok=True)
    for name in ("katex.min.css", "katex.min.js"):
        shutil.copy2(VENDOR / "katex" / name, katex_dst / name)
    (katex_dst / "contrib").mkdir(exist_ok=True)
    shutil.copy2(
        VENDOR / "katex" / "contrib" / "auto-render.min.js",
        katex_dst / "contrib" / "auto-render.min.js",
    )
    if (VENDOR / "katex" / "fonts").exists():
        shutil.copytree(VENDOR / "katex" / "fonts", katex_dst / "fonts", dirs_exist_ok=True)
    fonts_dst = assets_dir / "fonts"
    fonts_dst.mkdir(exist_ok=True)
    shutil.copy2(VENDOR / "fonts" / "Amiri-Regular.woff2", fonts_dst / "Amiri-Regular.woff2")

    # Обложка.
    img_dir = assets_dir / "img"
    img_dir.mkdir(exist_ok=True)
    try:
        from PIL import Image
        im = Image.open(config.COVER_FILE).convert("RGB")
        im.thumbnail((640, 960))
        im.save(img_dir / "cover.webp", "WEBP", quality=88)
    except Exception as exc:
        renderer.warnings.append(f"Не удалось подготовить обложку: {exc}")

    # Готовый PDF для скачивания.
    pdf_src = Path(config.PDF_FILE)
    if pdf_src.exists():
        shutil.copy2(pdf_src, OUT / config.PDF_NAME)
    else:
        renderer.warnings.append(f"Не найден PDF: {pdf_src}")

    # Проверка текста.
    fidelity = [fidelity_row(sec, site) for sec in sections]
    mismatches = [f for f in fidelity if f["status"] != "совпадает"]
    for f in mismatches:
        renderer.warnings.append(f"Сверка текста: {f['label']}: {f['detail']}")

    # Нераспознанные ссылки.
    unresolved = find_unresolved_xrefs(sections, renderer)

    # Проверка ссылок.
    link_report = check_links(OUT)

    site.report = {
        "counts": {
            "Разделов": len(site.numbered_sections),
            "Приложений": len(site.appendices),
            "Библиографических записей": len(site.bib),
            "Терминов": len(site.terms),
            "Цитат": len(site.quotes),
            "Возражений": sum(len(b.items) for b in sections_by_num["A"].blocks if b.kind == "list"),
            "Систем": sum(len(b.items) for b in sections_by_num["C"].blocks if b.kind == "list"),
            "Тезисов": sum(s.thesis_count for s in site.sections),
            "Слов": sum(s.words for s in site.sections),
            "HTML-страниц": len(list(OUT.rglob("*.html"))) - len(list((OUT / "_build").rglob("*.html"))) if (OUT / "_build").exists() else len(list(OUT.rglob("*.html"))),
        },
        "warnings": renderer.warnings,
        "unresolved_xrefs": unresolved,
        "link_check": link_report,
        "fidelity": fidelity,
    }

    # README и markdown-отчёт в служебном каталоге.
    counts = site.report["counts"]
    readme = f"""# {config.SITE_TITLE}

Статическая энциклопедия по книге {config.AUTHOR} «{config.BOOK_TITLE}»
({config.EDITION}, {config.BOOK_DATE}).

## Как открыть

Сайт полностью статический. Его можно открыть напрямую:

    xdg-open index.html

Лучше запустить локальный сервер:

    python3 -m http.server 8000

и открыть <http://localhost:8000/>.

## Как собрать заново

Из каталога сайта:

    python3 -m _build.build

Сборщик читает `book.tex` из исходного каталога книги, указанного в
`_build/config.py`, и перезаписывает `articles/`, `terms/`, `assets/` и
основные страницы.

## Что внутри

- `articles/` — 76 статей книги;
- `terms/` — словарные статьи;
- `assets/` — CSS, JS, KaTeX, шрифты, поисковый индекс;
- `predely-obosnovaniya.pdf` — готовый PDF книги;
- `_build/BUILD-REPORT.md` — отчёт о сборке и сверке.

Текст книги не переписывался. Добавлены только навигация, ссылки, поиск,
словарь, указатели и постоянные ссылки на фрагменты.
"""
    (BUILD / "README.md").write_text(readme, encoding="utf-8")

    report_md = [
        "# Отчёт о сборке",
        "",
        f"Дата сборки: {site.build_date}",
        "",
        "## Числа",
        "",
    ]
    for k, v in counts.items():
        report_md.append(f"- {k}: {v}")
    report_md += [
        "",
        "## Проверка ссылок",
        "",
        f"- Всего ссылок: {link_report['total']}",
        f"- Проверено якорей: {link_report['anchors']}",
        f"- Битых ссылок: {link_report['broken']}",
        "",
    ]
    if link_report["examples"]:
        report_md.append("### Примеры")
        report_md += [f"- {x}" for x in link_report["examples"]]
        report_md.append("")
    report_md += [
        "## Сверка текста",
        "",
        f"- Разделов: {len(fidelity)}",
        f"- Совпадает: {sum(1 for f in fidelity if f['status'] == 'совпадает')}",
        f"- Расхождений: {len(mismatches)}",
        "",
    ]
    if mismatches:
        report_md.append("### Расхождения")
        report_md += [f"- {f['label']}: {f['detail']}" for f in mismatches]
        report_md.append("")
    report_md += [
        "## Предупреждения",
        "",
    ]
    if renderer.warnings:
        report_md += [f"- {w}" for w in renderer.warnings]
    else:
        report_md.append("- нет")
    report_md += [
        "",
        "## Общие ссылки «раздел о …»",
        "",
        "Фразы, относящиеся к нескольким разделам или к теме в целом; оставлены текстом.",
        "",
    ]
    if unresolved:
        report_md += [f"- {w}" for w in unresolved]
    else:
        report_md.append("- все распознаны")
    (BUILD / "BUILD-REPORT.md").write_text("\n".join(report_md) + "\n", encoding="utf-8")

    print(f"Готово: {OUT}")
    print(f"Статей: {article_files}; терминов: {len(site.terms)}; записей поиска: {len(records)}")
    print(f"Битых ссылок: {link_report['broken']}; расхождений текста: {len(mismatches)}")
    if renderer.warnings:
        print(f"Предупреждений: {len(renderer.warnings)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
