# -*- coding: utf-8 -*-
"""Словарь терминов: извлечение определений и построение словарных статей."""

from __future__ import annotations

import re
from typing import Any

from . import config, texparse

MARKERS = [
    " называется ",
    " называются ",
    " означают ",
    " означает ",
    " образуют ",
    " составляют ",
    " мы понимаем ",
    " требует ",
    " имеет ",
    " есть ",
]

# Соответствие извлечённого заголовка канонической словарной форме.
# Ключ — нормализованный заголовок до маркера.
CANONICAL = {
    "формальной системой": "Формальная система",
    "синтаксисом": "Синтаксис",
    "семантикой": "Семантика",
    "достаточно сложной": "Достаточная сложность",
    "достаточной сложностью": "Достаточная сложность",
    "имманентным": "Имманентное и трансцендентное",
    "трансцендентным": "Имманентное и трансцендентное",
    "знамением": "Знамение",
    "верой": "Вера",
    "фитрой": "Фитра",
    "аклем": "Акль",
    "аманатом": "Аманат",
    "под интенсиональной сложностью": "Сложность",
    "интенсиональной сложностью": "Сложность",
    "сложностью": "Сложность",
    "сложность (интенсиональная и экстенсиональная)": "Сложность",
    "кат'и": "Кат'и и занни",
    "кат’и": "Кат'и и занни",
    "суббрендом": "Суббренд",
    "источником": "Источник",
    "асимметрией проверяемости": "Асимметрия проверяемости",
    "барзахом": "Барзах",
    "би-ля кайфа": "Би-ля кайфа",
    "вычислимостью": "Вычислимость",
    "иджазом": "Иджаз",
    "имманентное": "Имманентное и трансцендентное",
    "иснад": "Иснад и матн",
    "касбом": "Касб",
    "мерой": "Мера",
    "мисаком": "Мисак",
    "настройкой": "Настройка",
    "первичным основанием": "Первичное основание",
    "слабый принцип достаточного основания": "Слабый принцип достаточного основания",
    "профиль источника": "Профиль Источника",
    "регистрами установления": "Регистры установления",
    "рух, нафс, акль и кальб": "Рух, нафс, акль и кальб",
    "сакиной": "Сакина",
    "скрытостью": "Скрытость",
    "стрелой времени": "Стрела времени",
    "таватуром": "Таватур",
    "таухид": "Таухид и ширк",
    "тахрифом": "Тахриф",
    "триангуляцией": "Триангуляция",
    "элиминационным анализом": "Элиминационный анализ",
    "эпистемологией материализма": "Эпистемология материализма",
    "ядро религии": "Ядро религии",
}

# Алиасы для поиска термина в тексте. Это регулярные выражения, а не
# переписанный текст. Порядок в Renderer задаётся длиной шаблона.
ALIASES = {
    "Формальная система": [r"формальн\w*\s+систем\w*"],
    "Синтаксис": [r"синтаксис\w*"],
    "Семантика": [r"семантик\w*"],
    "Достаточная сложность": [r"достаточн\w*\s+сложност\w*"],
    "Имманентное и трансцендентное": [r"имманентн\w*", r"трансцендентн\w*"],
    "Знамение": [r"знамени\w*"],
    "Вера": [r"вер(?:а|ы|е|у|ой|ою|ам|ами|ах)?\b"],
    "Фитра": [r"фитр\w*"],
    "Акль": [r"акл(?:ь|я|ю|ем|е)?\b"],
    "Аманат": [r"аманат\w*"],
    "Сложность": [
        r"интенсиональн\w*\s+сложност\w*",
        r"экстенсиональн\w*\s+сложност\w*",
        r"сложност\w*",
    ],
    "Кат'и и занни": [r"кат['’]?и\b", r"занни\b"],
    "Суббренд": [r"суббренд\w*"],
    "Источник": [r"Источник(?:а|у|ом|е)?"],
    "Асимметрия проверяемости": [r"асимметри\w*\s+проверяемости"],
    "Барзах": [r"барзах\w*"],
    "Би-ля кайфа": [r"би-ля\s+кайфа"],
    "Вычислимость": [r"вычислимост\w*"],
    "Иджаз": [r"иджаз\w*"],
    "Иснад и матн": [r"иснад\w*", r"матн\w*", r"иснад-кум-матн"],
    "Касб": [r"касб\w*"],
    "Мера": [r"мер(?:а|ы|е|у|ой|ою|ам|ами|ах)?\b"],
    "Мисак": [r"мисак\w*"],
    "Настройка": [r"настройк\w*"],
    "Первичное основание": [r"первичн\w*\s+основани\w*"],
    "Слабый принцип достаточного основания": [
        r"слаб\w*\s+принцип\w*\s+достаточного\s+основания"
    ],
    "Профиль Источника": [r"профил\w*\s+Источник\w*"],
    "Регистры установления": [r"регистр\w*\s+установления"],
    "Рух, нафс, акль и кальб": [
        r"рух(?:а|у|ом|е)?\b",
        r"нафс\w*",
        r"кальб\w*",
        r"фуад\w*",
    ],
    "Сакина": [r"сакин\w*"],
    "Скрытость": [r"скрытост\w*"],
    "Стрела времени": [r"стрел\w*\s+времени"],
    "Таватур": [r"таватур\w*"],
    "Таухид и ширк": [r"таухид\w*", r"ширк\w*"],
    "Тахриф": [r"тахриф\w*"],
    "Триангуляция": [r"триангуляци\w*"],
    "Элиминационный анализ": [r"элиминационн\w*\s+анализ\w*"],
    "Эпистемология материализма": [r"эпистемологи\w*\s+материализма"],
    "Ядро религии": [r"ядр\w*\s+религии"],
}

CASE_SENSITIVE = {"Источник"}


def extract_headword(raw: str) -> str:
    text = raw.strip()
    positions: list[tuple[int, str]] = []
    for marker in MARKERS:
        pos = text.find(marker)
        if pos >= 0:
            positions.append((pos, marker))
    if not positions:
        return text.split(".")[0].strip()
    pos, marker = min(positions)
    head = text[:pos].strip()
    if head.lower().startswith("под "):
        head = head[4:].strip()
    return head


def normalize_headword(head: str) -> str:
    head = head.lower().replace("ё", "е").replace("’", "'")
    head = re.sub(r"\s+", " ", head).strip(" .,:;—-")
    return head


def extract_terms(
    method_sec: texparse.Section,
    glossary_sec: texparse.Section,
) -> list[texparse.Term]:
    terms: dict[str, texparse.Term] = {}

    def add_item(sec: texparse.Section, block: texparse.Block, item: dict[str, Any]) -> None:
        raw = item["raw"].strip()
        head = extract_headword(raw)
        key = normalize_headword(head)
        canonical = CANONICAL.get(key)
        if not canonical:
            # Если правило не сработало, оставляем заголовок как есть.
            canonical = head[:1].upper() + head[1:]
        slug = texparse.slugify(canonical)
        term = terms.get(canonical)
        if term is None:
            term = texparse.Term(id=slug, headword=canonical, slug=slug)
            terms[canonical] = term
        label = sec.title if sec.starred else f"{sec.label}. {sec.title}"
        source_url = f"{sec.url}#{item['anchor']}"
        if sec.num == "B":
            source_url = f"glossary.html#g-{slug}"
        term.definitions.append({
            "text": raw,
            "source_num": sec.num,
            "source_title": sec.title,
            "source_label": label,
            "source_url": source_url,
            "anchor": item["anchor"],
        })

    for sec in (method_sec, glossary_sec):
        for block in sec.blocks:
            if block.kind != "list":
                continue
            for item in block.items:
                add_item(sec, block, item)

    # Паттерны для поиска в тексте.
    for term in terms.values():
        aliases = ALIASES.get(term.headword, [re.escape(term.headword)])
        term.aliases = aliases
        flags = 0 if term.headword in CASE_SENSITIVE else re.IGNORECASE
        term.patterns = []
        for alias in aliases:
            bounded = r"(?<!\w)(?:" + alias + r")(?!\w)"
            try:
                term.patterns.append(re.compile(bounded, flags))
            except re.error:
                term.patterns.append(re.compile(r"(?<!\w)(?:" + re.escape(alias) + r")(?!\w)", flags))

    result = sorted(terms.values(), key=lambda t: t.headword.lower())
    return result


def collect_occurrences(
    terms: list[texparse.Term],
    sections: list[texparse.Section],
    renderer: texparse.Renderer,
) -> None:
    """Заполняет term.occurrences: по одному первому примеру на раздел."""
    for term in terms:
        term.occurrences = []
        for sec in sections:
            if sec.num == "B":
                continue
            first: dict[str, Any] | None = None
            count = 0
            for block in sec.blocks:
                sentences: list[texparse.Sentence] = []
                anchor = ""
                if block.kind == "para":
                    sentences = block.sentences
                    anchor = block.anchor
                elif block.kind == "list":
                    for item in block.items:
                        sentences.extend(item.get("sentences", []))
                        anchor = item.get("anchor", "")
                elif block.kind == "quote":
                    sentences = block.sentences
                    anchor = block.anchor
                for sentence in sentences:
                    hits = 0
                    for pattern in term.patterns:
                        hits += len(pattern.findall(sentence.raw))
                    if hits:
                        count += hits
                        if first is None:
                            if sec.num == "A":
                                article_url = "objections.html"
                            elif sec.num == "C":
                                article_url = "systems.html"
                            else:
                                article_url = sec.url
                            anchor = block.anchor if block.kind == "quote" else sentence.anchor
                            first = {
                                "article_num": sec.num,
                                "article_title": sec.title,
                                "article_url": article_url,
                                "anchor": anchor,
                                "text": renderer.render_plain(sentence.raw, sec),
                            }
            if count:
                term.occurrences.append({
                    "article_num": sec.num,
                    "article_title": sec.title,
                    "article_url": first["article_url"] if first else sec.url,
                    "anchor": first["anchor"] if first else "",
                    "text": first["text"] if first else "",
                    "count": count,
                })
