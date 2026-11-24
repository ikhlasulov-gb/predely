# -*- coding: utf-8 -*-
"""Разбор book.tex и рендеринг фрагментов в HTML.

Принцип: текст не переписывается. Меняется только разметка: команды LaTeX
превращаются в HTML, цитаты — в ссылки на литературу, теоремы и цитаты
получают оформление, а предложения — постоянные адреса.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable

from . import config


# ---------------------------------------------------------------------------
# Модель данных
# ---------------------------------------------------------------------------

@dataclass
class Sentence:
    raw: str
    anchor: str
    number: int
    para_anchor: str
    para_number: int
    plain: str = ""
    html: str = ""

    @property
    def text(self) -> str:
        return self.plain


@dataclass
class Block:
    kind: str
    raw: str = ""
    line: int = 0
    anchor: str = ""
    number: int = 0
    items: list[dict[str, Any]] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    sentences: list[Sentence] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    html: str = ""


@dataclass
class Section:
    num: str
    title: str
    starred: bool
    slug: str
    line: int
    blocks: list[Block] = field(default_factory=list)
    words: int = 0
    thesis_count: int = 0
    quote_count: int = 0
    source_keys: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    group: str = ""
    lead: str = ""
    theorem_groups: dict[str, str] = field(default_factory=dict)
    xref_targets: set[str] = field(default_factory=set)
    xref_sources: set[str] = field(default_factory=set)
    term_ids: set[str] = field(default_factory=set)

    @property
    def url(self) -> str:
        return f"articles/{self.slug}.html"

    @property
    def label(self) -> str:
        if self.starred:
            return f"Приложение {self.num}"
        return f"Раздел {self.num}"

    @property
    def sort_key(self) -> tuple[int, str]:
        if self.starred:
            return (10_000 + {"A": 1, "B": 2, "C": 3}.get(self.num, 9), "")
        return (int(self.num), "")


@dataclass
class BibEntry:
    key: str
    text: str
    number: int
    letter: str = ""
    html: str = ""
    cited_in: list[str] = field(default_factory=list)


@dataclass
class Term:
    id: str
    headword: str
    slug: str
    definitions: list[dict[str, Any]] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    patterns: list[re.Pattern[str]] = field(default_factory=list)
    occurrences: list[dict[str, Any]] = field(default_factory=list)
    related: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"terms/{self.slug}.html"

    @property
    def first_definition(self) -> str:
        return self.definitions[0]["text"] if self.definitions else ""


@dataclass
class Quote:
    text: str
    article: Section
    anchor: str
    number: int
    kind: str = "Цитата"
    source: str = ""
    html: str = ""


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(text: str, max_len: int = 72) -> str:
    text = text.lower().replace("ё", "е")
    out: list[str] = []
    for ch in text:
        if ch in TRANSLIT:
            out.append(TRANSLIT[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch in "–—−":
            out.append("-")
        elif ch.isspace() or ch in "-_/.,:;!?()[]{}«»„“”\"'’":
            out.append("-")
        else:
            decomposed = unicodedata.normalize("NFKD", ch)
            out.append(decomposed.encode("ascii", "ignore").decode("ascii"))
    slug = re.sub(r"-+", "-", "".join(out)).strip("-")
    return (slug[:max_len].rstrip("-") or "article")


def norm_key(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = text.replace("'", "").replace("’", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def count_words(text: str) -> int:
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"[${}]", " ", text)
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:-[A-Za-zА-Яа-яЁё0-9]+)*", text))


def read_group(text: str, index: int) -> tuple[str, int]:
    """Читает {...}, начиная с позиции index (там должна быть '{')."""
    if index >= len(text) or text[index] != "{":
        return "", index
    depth = 0
    i = index
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[index + 1:i], i + 1
        i += 1
    return text[index + 1:], len(text)


def strip_commands(text: str) -> str:
    """Грубая очистка TeX до текста — для отчётов и служебных проверок."""
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = text.replace("{", " ").replace("}", " ")
    text = text.replace("$", " ")
    return normalize_ws(text)


def html_to_text(markup: str) -> str:
    text = re.sub(r"<[^>]+>", "", markup)
    text = html.unescape(text)
    return normalize_ws(text)


def math_to_text(tex: str) -> str:
    s = tex
    s = re.sub(r"\\operatorname\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\text\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\mathbb\{([^{}]*)\}", lambda m: {
        "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "R": "ℝ", "C": "ℂ",
    }.get(m.group(1), m.group(1)), s)
    replacements = {
        r"\ulcorner": "⌜", r"\urcorner": "⌝",
        r"\vdash": "⊢", r"\nvdash": "⊬", r"\neg": "¬",
        r"\leftrightarrow": "↔", r"\to": "→", r"\rightarrow": "→",
        r"\exists": "∃", r"\forall": "∀", r"\wedge": "∧",
        r"\le": "≤", r"\leq": "≤", r"\ge": "≥", r"\geq": "≥",
        r"\approx": "≈", r"\cdot": "·", r"\cdots": "⋯", r"\ldots": "…",
        r"\dots": "…", r"\times": "×", r"\ln": "ln",
        r"\varphi": "φ", r"\psi": "ψ", r"\theta": "θ", r"\delta": "δ",
        r"\rho": "ρ", r"\omega": "ω", r"\Sigma": "Σ", r"\Omega": "Ω",
        r"\varepsilon": "ε", r"\Diamond": "◇",
        r"\bigl": "", r"\bigr": "", r"\left": "", r"\right": "",
        r"\,": " ", r"\;": " ", r"\!": "", r"\ ": " ",
    }
    for a, b in replacements.items():
        s = s.replace(a, b)
    s = re.sub(r"\\bar\s+([A-Za-zА-Яа-я])", r"\1", s)
    s = re.sub(r"\\([A-Za-z]+)", r"\1", s)
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ---------------------------------------------------------------------------
# Разбор книги
# ---------------------------------------------------------------------------

def extract_command_arg(source: str, command: str) -> str:
    m = re.search(r"\\" + re.escape(command) + r"\s*\{", source)
    if not m:
        return ""
    start = m.end() - 1
    value, _ = read_group(source, start)
    return value


def parse_front_matter(source: str) -> dict[str, Any]:
    title = extract_command_arg(source, "title")
    short_title = ""
    # \title[short]{long}
    m = re.search(r"\\title(?:\[([^\]]*)\])?\s*\{", source)
    if m:
        short_title = normalize_ws(m.group(1) or "")
        title, _ = read_group(source, m.end() - 1)
    author = extract_command_arg(source, "author")
    date_raw = extract_command_arg(source, "date")
    date = re.sub(r"\{\\footnotesize\s*([^{}]*)\}", r"\1", date_raw)
    date = normalize_ws(date.replace("~", " "))
    keywords = extract_command_arg(source, "keywords")
    subjclass = ""
    m = re.search(r"\\subjclass(?:\[[^\]]*\])?\s*\{", source)
    if m:
        subjclass, _ = read_group(source, m.end() - 1)
    abstract_m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", source, re.S)
    abstract_raw = abstract_m.group(1).strip() if abstract_m else ""
    abstract_paras = [
        normalize_ws(p) for p in re.split(r"\n\s*\n", abstract_raw) if normalize_ws(p)
    ]
    imprint = ""
    m = re.search(r"\\newcommand\s*\\imprinthere\s*\{", source)
    if m:
        body, _ = read_group(source, m.end() - 1)
        fm = re.search(r"\\@footnotetext\s*\{", body)
        if fm:
            imprint, _ = read_group(body, fm.end() - 1)
            imprint = normalize_ws(imprint.replace("\\par", " "))
    return {
        "title": normalize_ws(title),
        "short_title": short_title,
        "author": normalize_ws(author),
        "date": date,
        "keywords": normalize_ws(keywords),
        "subjclass": normalize_ws(subjclass),
        "abstract_paras": abstract_paras,
        "imprint": imprint,
    }


def parse_blocks(content: str, section_num: str) -> list[Block]:
    """Разбирает содержимое раздела на блоки, сохраняя порядок."""
    content = content.replace("\r\n", "\n")
    # Служебные команды, не создающие блоков.
    for cmd in ["\\clearpage", "\\begingroup", "\\endgroup", "\\noindent"]:
        content = content.replace(cmd, "")
    content = re.sub(r"\\emergencystretch\s*=\s*[0-9.]+\s*em", "", content)
    content = re.sub(r"\\renewcommand\{[^{}]*\}\{[^{}]*\}", "", content)

    block_re = re.compile(r"\\begin\{(quote|equation|itemize|center)\}")
    blocks: list[Block] = []
    pos = 0

    def add_paragraphs(segment: str) -> None:
        segment = segment.strip()
        if not segment:
            return
        for para in re.split(r"\n\s*\n", segment):
            raw = normalize_ws(para)
            if not raw:
                continue
            # Иногда в тексте остаются только служебные команды.
            if re.fullmatch(r"(?:\\(?:clearpage|begingroup|endgroup|par|noindent)\s*)+", raw):
                continue
            blocks.append(Block(kind="para", raw=raw))

    while True:
        m = block_re.search(content, pos)
        if not m:
            add_paragraphs(content[pos:])
            break
        add_paragraphs(content[pos:m.start()])
        env = m.group(1)
        end_marker = f"\\end{{{env}}}"
        end = content.find(end_marker, m.end())
        if end < 0:
            add_paragraphs(content[m.start():])
            break
        inner = content[m.end():end]
        if env == "quote":
            blocks.append(Block(kind="quote", raw=normalize_ws(inner)))
        elif env == "equation":
            blocks.append(Block(kind="equation", raw=inner.strip()))
        elif env == "itemize":
            items = parse_itemize(inner)
            if items:
                blocks.append(Block(kind="list", items=items))
        elif env == "center":
            rows = parse_table(inner)
            if rows:
                blocks.append(Block(kind="table", rows=rows))
            else:
                raw = normalize_ws(inner)
                if raw:
                    blocks.append(Block(kind="para", raw=raw))
        pos = end + len(end_marker)
    return blocks


def parse_itemize(inner: str) -> list[dict[str, Any]]:
    parts = re.split(r"\\item\b", inner)
    items: list[dict[str, Any]] = []
    for part in parts[1:]:
        raw = normalize_ws(part)
        if raw:
            items.append({"raw": raw})
    return items


def parse_table(inner: str) -> list[list[str]]:
    m = re.search(r"\\begin\{tabular\}\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}(.*?)\\end\{tabular\}", inner, re.S)
    if not m:
        return []
    body = m.group(1)
    body = body.replace("\\hline", "\n")
    rows: list[list[str]] = []
    for raw_row in re.split(r"\\\\", body):
        raw_row = normalize_ws(raw_row)
        if not raw_row:
            continue
        cells = [cell.strip() for cell in raw_row.split("&")]
        if cells:
            rows.append(cells)
    # Убираем случайные пустые строки, оставшиеся от \hline.
    return [row for row in rows if any(cell for cell in row)]


def parse_sections(source: str) -> tuple[list[Section], dict[str, Any]]:
    first = re.search(r"\\section\*?\{", source)
    body_end = source.find("\\begin{thebibliography}")
    if body_end < 0:
        body_end = len(source)
    body_start = first.start() if first else 0
    body = source[body_start:body_end]

    matches = list(re.finditer(r"\\section(\*?)\{([^{}]*)\}", body))
    sections: list[Section] = []
    numbered = 0
    appendix_letters = {"А": "A", "Б": "B", "В": "C"}
    for i, m in enumerate(matches):
        starred = bool(m.group(1))
        title = normalize_ws(m.group(2))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = body[start:end]
        line = source[:body_start + m.start()].count("\n") + 1
        if starred:
            num = "A"
            for letter, latin in appendix_letters.items():
                if title.startswith(f"Приложение {letter}"):
                    num = latin
                    break
        else:
            numbered += 1
            num = str(numbered)
        slug = f"{int(num):02d}-{slugify(title)}" if not starred else f"appendix-{num.lower()}-{slugify(title, 40)}"
        sec = Section(
            num=num,
            title=title,
            starred=starred,
            slug=slug,
            line=line,
            blocks=parse_blocks(content, num),
        )
        sections.append(sec)
    return sections, {"body_start": body_start, "body_end": body_end}


def parse_bibliography(source: str) -> list[BibEntry]:
    m = re.search(r"\\begin\{thebibliography\}\{999\}(.*?)\\end\{thebibliography\}", source, re.S)
    if not m:
        return []
    body = m.group(1)
    items = list(re.finditer(r"\\bibitem\{([^}]*)\}\s*(.*?)(?=\n\\bibitem|\Z)", body, re.S))
    entries: list[BibEntry] = []
    for i, item in enumerate(items, 1):
        key = item.group(1).strip()
        text = normalize_ws(item.group(2).strip())
        if not text:
            continue
        letter = ""
        for ch in text:
            if ch.isalpha():
                letter = ch.upper().replace("Ё", "Е")
                break
        entries.append(BibEntry(key=key, text=text, number=i, letter=letter))
    return entries


# ---------------------------------------------------------------------------
# Деление на предложения
# ---------------------------------------------------------------------------

def split_sentences(text: str) -> list[str]:
    """Делит абзац на предложения, не трогая формулы и сокращения."""
    if not text:
        return []

    protected: list[str] = []

    def protect_math(m: re.Match[str]) -> str:
        protected.append(m.group(0))
        return f"\uE100{len(protected) - 1}\uE101"

    work = re.sub(r"\$[^$]*\$", protect_math, text)

    # Сокращения: заменяем точки служебным символом, чтобы не делить фразу.
    for abbr in sorted(config.ABBREVIATIONS, key=len, reverse=True):
        if not abbr:
            continue
        pattern = re.escape(abbr)
        work = re.sub(pattern, lambda m: m.group(0).replace(".", "\u0001"), work, flags=re.I)
    # Десятичные числа.
    work = re.sub(r"(\d)\.(\d)", lambda m: m.group(1) + "\u0001" + m.group(2), work)
    # Многоточие из трёх точек.
    work = work.replace("...", "…")

    boundaries: list[int] = []
    i = 0
    n = len(work)
    closers = "»\"”’)]}"
    while i < n:
        ch = work[i]
        if ch in ".!?…" and ch != "\u0001":
            j = i + 1
            while j < n and work[j] in closers:
                j += 1
            k = j
            while k < n and work[k].isspace():
                k += 1
            if k < n:
                nxt = work[k]
                if nxt.isupper() or nxt.isdigit() or nxt in "«„\"(“—–":
                    boundaries.append(j)
            i = max(j, i + 1)
            continue
        i += 1

    sentences: list[str] = []
    start = 0
    for b in boundaries:
        chunk = work[start:b].strip()
        if chunk:
            sentences.append(chunk)
        start = b
        while start < n and work[start].isspace():
            start += 1
    tail = work[start:].strip()
    if tail:
        sentences.append(tail)

    def restore(chunk: str) -> str:
        chunk = chunk.replace("\u0001", ".")
        def unmath(m: re.Match[str]) -> str:
            return protected[int(m.group(1))]
        return re.sub(r"\uE100(\d+)\uE101", unmath, chunk).strip()

    return [restore(s) for s in sentences if restore(s)]


# ---------------------------------------------------------------------------
# Рендерер
# ---------------------------------------------------------------------------

class Renderer:
    def __init__(self, sections_by_num: dict[str, Section], bib_entries: list[BibEntry]):
        self.sections_by_num = sections_by_num
        self.bib_entries = bib_entries
        self.bib_by_key = {e.key: e for e in bib_entries}
        self.terms: list[Term] = []
        self.term_patterns: list[tuple[Term, re.Pattern[str]]] = []
        self.warnings: list[str] = []
        self.alias_regex, self.alias_map = self._build_alias_regex()

    # -- цели ссылок -----------------------------------------------------
    def target_url(self, target: str, root: str) -> str:
        if target == "A":
            return f"{root}objections.html"
        if target == "B":
            return f"{root}glossary.html"
        if target == "C":
            return f"{root}systems.html"
        sec = self.sections_by_num.get(str(target))
        return f"{root}{sec.url}" if sec else f"{root}contents.html"

    def target_title(self, target: str) -> str:
        if target == "A":
            return "Приложение А. Карта сильнейших возражений и ответов"
        if target == "B":
            return "Приложение Б. Словарь терминов"
        if target == "C":
            return "Приложение В. Сравнительная матрица мировоззренческих систем"
        sec = self.sections_by_num.get(str(target))
        return sec.title if sec else "Раздел"

    # -- ссылки «раздел о …» --------------------------------------------
    def _build_alias_regex(self) -> tuple[re.Pattern[str], dict[str, str]]:
        entries: list[tuple[str, str]] = []
        for target, aliases in config.SECTION_ALIASES.items():
            for alias in aliases:
                entries.append((alias, str(target)))
        entries.sort(key=lambda x: len(x[0]), reverse=True)
        alias_map: dict[str, str] = {}
        for alias, target in entries:
            alias_map.setdefault(norm_key(alias), target)
        alternatives = "|".join(re.escape(alias) for alias, _ in entries)
        prefix = r"(?:раздел(?:ы|ов|ам|ами|ах|а|у|ом|е)?|приложени(?:е|я|ю|ем|и))"
        pattern = re.compile(
            rf"(?<!\w)(?P<prefix>{prefix})\s+(?:о|об|про)\s+(?P<alias>{alternatives})(?![\w-])",
            re.IGNORECASE,
        )
        return pattern, alias_map

    def find_xrefs(self, text: str) -> list[tuple[int, int, str, str]]:
        found: list[tuple[int, int, str, str]] = []
        for m in self.alias_regex.finditer(text):
            target = self.alias_map.get(norm_key(m.group("alias")))
            if target:
                found.append((m.start(), m.end(), target, m.group(0)))
        return found

    def protect_xrefs(self, text: str, section: Section | None, root: str) -> tuple[str, dict[str, str]]:
        replacements: dict[str, str] = {}
        counter = 0

        def add(start: int, end: int, target: str, original: str) -> None:
            nonlocal counter, text
            if section is not None:
                section.xref_targets.add(target)
            key = f"\uE200{counter}\uE201"
            counter += 1
            title = html.escape(f"{self.target_title(target)}")
            replacements[key] = (
                f'<a class="xref" href="{html.escape(self.target_url(target, root))}" '
                f'title="{title}">{html.escape(original)}</a>'
            )

        # Специальная ссылка «(словарь)».
        m = re.search(r"\(словарь\)", text, re.IGNORECASE)
        if m:
            original = m.group(0)
            if section is not None:
                section.xref_targets.add("B")
            key = f"\uE200{counter}\uE201"
            counter += 1
            replacements[key] = (
                f'<a class="xref" href="{html.escape(self.target_url("B", root))}" '
                f'title="Приложение Б. Словарь терминов">(словарь)</a>'
            )
            text = text[:m.start()] + key + text[m.end():]

        # Основные ссылки. Идём с конца, чтобы не сбить смещения.
        refs = self.find_xrefs(text)
        for start, end, target, original in reversed(refs):
            # Ссылка на тот же раздел не нужна: она ведёт в начало той же статьи.
            if section is not None and target == section.num:
                continue
            # Пропускаем уже вставленные служебные маркеры.
            if "\uE200" in text[start:end]:
                continue
            key = f"\uE200{counter}\uE201"
            counter += 1
            if section is not None:
                section.xref_targets.add(target)
            replacement = (
                f'<a class="xref" href="{html.escape(self.target_url(target, root))}" '
                f'title="{html.escape(self.target_title(target))}">{html.escape(original)}</a>'
            )
            replacements[key] = replacement
            # Заменяем только этот диапазон. Так как идём с конца, смещения целы.
            text = text[:start] + key + text[end:]
        return text, replacements

    # -- термины --------------------------------------------------------
    def set_terms(self, terms: list[Term]) -> None:
        self.terms = terms
        patterns: list[tuple[Term, re.Pattern[str]]] = []
        for term in terms:
            if not term.patterns:
                continue
            combined = "|".join(f"(?:{p})" for p in [x.pattern for x in term.patterns])
            flags = re.IGNORECASE
            if term.patterns and all(not (p.flags & re.IGNORECASE) for p in term.patterns):
                flags = 0
            try:
                compiled = re.compile(combined, flags)
            except re.error:
                compiled = term.patterns[0]
            patterns.append((term, compiled))
        patterns.sort(key=lambda x: max((len(p.pattern) for p in x[0].patterns), default=0), reverse=True)
        self.term_patterns = patterns

    def protect_terms(
        self,
        text: str,
        section: Section | None,
        used: set[str] | None,
        root: str,
        exclude_term: str | None = None,
    ) -> tuple[str, dict[str, str]]:
        if not self.term_patterns:
            return text, {}
        replacements: dict[str, str] = {}
        counter = 0
        for term, pattern in self.term_patterns:
            if term.id == exclude_term:
                continue
            if used is not None and term.id in used:
                continue
            m = pattern.search(text)
            if not m:
                continue
            matched = m.group(0)
            key = f"\uE300{counter}\uE301"
            counter += 1
            replacements[key] = (
                f'<a class="term-link" href="{html.escape(root + term.url)}" '
                f'title="Термин: {html.escape(term.headword)}">{html.escape(matched)}</a>'
            )
            text = text[:m.start()] + key + text[m.end():]
            if used is not None:
                used.add(term.id)
            if section is not None:
                section.term_ids.add(term.id)
        return text, replacements

    # -- инлайн-рендер ---------------------------------------------------
    def render_inline(
        self,
        text: str,
        section: Section | None,
        root: str,
        *,
        allow_xrefs: bool = True,
        allow_terms: bool = True,
        used_terms: set[str] | None = None,
        exclude_term: str | None = None,
    ) -> str:
        xrefs: dict[str, str] = {}
        terms: dict[str, str] = {}
        if allow_xrefs and section is not None:
            text, xrefs = self.protect_xrefs(text, section, root)
        if allow_terms and section is not None:
            text, terms = self.protect_terms(text, section, used_terms, root, exclude_term)
        out = self._scan_inline(text, section, root)
        # Сначала термины, затем ссылки: термины не могут попасть внутрь ссылок,
        # потому что ссылки были защищены раньше.
        for key, value in terms.items():
            out = out.replace(key, value)
        for key, value in xrefs.items():
            out = out.replace(key, value)
        return out

    def render_plain(self, text: str, section: Section | None = None) -> str:
        markup = self.render_inline(
            text, section, "", allow_xrefs=False, allow_terms=False
        )
        return html_to_text(markup)

    def _scan_inline(self, text: str, section: Section | None, root: str) -> str:
        out: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "$":
                end = text.find("$", i + 1)
                if end < 0:
                    out.append(html.escape(ch))
                    i += 1
                    continue
                tex = text[i + 1:end]
                fallback = html.escape(math_to_text(tex))
                out.append(
                    f'<span class="tex" data-tex="{html.escape(tex, quote=True)}">{fallback}</span>'
                )
                i = end + 1
                continue
            if ch == "\\":
                if i + 1 < n and text[i + 1] == " ":
                    out.append("\u00a0")
                    i += 2
                    continue
                if i + 1 < n and text[i + 1] in "&%$#_{}":
                    out.append(html.escape(text[i + 1]))
                    i += 2
                    continue
                m = re.match(r"\\([A-Za-z@]+)\*?", text[i:])
                if not m:
                    out.append(html.escape(ch))
                    i += 1
                    continue
                cmd = m.group(1)
                j = i + m.end()
                if cmd in ("textbf", "emph", "textit"):
                    while j < n and text[j].isspace():
                        j += 1
                    if j < n and text[j] == "{":
                        group, j = read_group(text, j)
                        inner = self._scan_inline(group, section, root)
                        tag = {"textbf": "strong", "emph": "em", "textit": "i"}[cmd]
                        out.append(f"<{tag}>{inner}</{tag}>")
                        i = j
                        continue
                if cmd == "cite":
                    while j < n and text[j].isspace():
                        j += 1
                    if j < n and text[j] == "{":
                        group, j = read_group(text, j)
                        out.append(self._render_citations(group, root))
                        i = j
                        continue
                if cmd == "hspace":
                    while j < n and text[j].isspace():
                        j += 1
                    if j < n and text[j] == "{":
                        _, j = read_group(text, j)
                    i = j
                    continue
                if cmd == "Amiri":
                    while j < n and text[j].isspace():
                        j += 1
                    if j < n and text[j] == "{":
                        group, j = read_group(text, j)
                    else:
                        k = j
                        while k < n and not text[k].isspace() and text[k] not in "{}":
                            k += 1
                        group, j = text[j:k], k
                    out.append(f'<span class="arabic" lang="ar" dir="rtl">{html.escape(group)}</span>')
                    i = j
                    continue
                if cmd in ("ldots", "dots", "cdots"):
                    out.append("…")
                    i = j
                    continue
                if cmd == "textbullet":
                    out.append("•")
                    i = j
                    continue
                if cmd in ("relax", "ignorespaces", "par", "noindent", "hfill", "vfill"):
                    i = j
                    continue
                if cmd in ("Diamond",):
                    out.append("◇")
                    i = j
                    continue
                # Неизвестная команда: сохраняем имя, чтобы не потерять текст.
                self.warnings.append(f"Неизвестная команда \\{cmd}")
                out.append(html.escape(cmd))
                i = j
                continue
            if ch == "{":
                group, j = read_group(text, i)
                if group.lstrip().startswith("\\Amiri"):
                    rest = group.lstrip()[len("\\Amiri"):].lstrip()
                    inner = self._scan_inline(rest, section, root)
                    out.append(f'<span class="arabic" lang="ar" dir="rtl">{inner}</span>')
                else:
                    out.append(self._scan_inline(group, section, root))
                i = j
                continue
            if ch == "}":
                i += 1
                continue
            if ch == "~":
                out.append("\u00a0")
                i += 1
                continue
            if text.startswith("---", i):
                out.append("—")
                i += 3
                continue
            if text.startswith("--", i):
                out.append("–")
                i += 2
                continue
            if ch in "&<>":
                out.append(html.escape(ch))
                i += 1
                continue
            out.append(ch)
            i += 1
        return "".join(out)

    def _render_citations(self, group: str, root: str) -> str:
        keys = [k.strip() for k in group.split(",") if k.strip()]
        parts: list[str] = []
        for key in keys:
            entry = self.bib_by_key.get(key)
            if not entry:
                self.warnings.append(f"Не найден источник: {key}")
                parts.append(f'<span class="citation-missing">[?{html.escape(key)}]</span>')
                continue
            title = html.escape(self.render_plain(entry.text))
            parts.append(
                f'<a class="citation" href="{html.escape(root)}bibliography.html#b-{entry.number}" '
                f'title="{title}">[{entry.number}]</a>'
            )
        return '<span class="citation-group">' + ", ".join(parts) + "</span>"


# ---------------------------------------------------------------------------
# Подготовка секций
# ---------------------------------------------------------------------------

def assign_sections_meta(sections: list[Section], renderer: Renderer) -> None:
    """Заполняет категории, группы, счётчики и якоря блоков."""
    group_of: dict[str, str] = {}
    for gid, _, nums in config.GROUPS:
        for num in nums:
            group_of[str(num)] = gid

    eqno = 0
    for sec in sections:
        sec.group = group_of.get(str(sec.num), "")
        cat_key = int(sec.num) if sec.num.isdigit() else sec.num
        sec.categories = list(config.SECTION_CATEGORIES.get(cat_key, []))
        all_raw_parts: list[str] = []
        for b in sec.blocks:
            if b.kind == "list":
                all_raw_parts.extend(item.get("raw", "") for item in b.items)
            elif b.kind == "table":
                all_raw_parts.extend(" ".join(row) for row in b.rows)
            else:
                all_raw_parts.append(b.raw)
        all_raw = " ".join(all_raw_parts)
        cite_groups = re.findall(r"\\cite\{([^}]*)\}", all_raw)
        keys: list[str] = []
        for group in cite_groups:
            keys.extend(k.strip() for k in group.split(",") if k.strip())
        sec.source_keys = sorted(set(keys))
        sec.words = count_words(all_raw)

        pnum = 0
        qnum = 0
        lnum = 0
        tnum = 0
        thesis_count = 0
        quote_count = 0
        for block in sec.blocks:
            if block.kind == "para":
                pnum += 1
                block.anchor = f"p{pnum}"
                block.number = pnum
                block.meta["para_number"] = pnum
                sentences = split_sentences(block.raw)
                block.sentences = []
                for si, raw in enumerate(sentences, 1):
                    block.sentences.append(Sentence(
                        raw=raw,
                        anchor=f"p{pnum}-s{si}",
                        number=si,
                        para_anchor=f"p{pnum}",
                        para_number=pnum,
                    ))
                thesis_count += len(block.sentences)
                raw = block.raw.strip()
                if raw.startswith("\\textbf{Теорема 1}"):
                    block.meta["theorem"] = "1"
                elif raw.startswith("\\textbf{Теорема 2}"):
                    block.meta["theorem"] = "2"
                elif raw.startswith("\\emph{Доказательство.}") or raw.startswith("\\emph{Доказательство}."):
                    block.meta["proof"] = "1" if sec.num == "7" else ("2" if sec.num == "8" else "")
                elif raw.startswith("Доказательство леммы."):
                    block.meta["proof_lemma"] = True
            elif block.kind == "quote":
                qnum += 1
                quote_count += 1
                block.anchor = f"q{qnum}"
                block.number = qnum
                block.sentences = []
                for si, raw in enumerate(split_sentences(block.raw), 1):
                    block.sentences.append(Sentence(
                        raw=raw,
                        anchor=f"q{qnum}-s{si}",
                        number=si,
                        para_anchor=f"q{qnum}",
                        para_number=qnum,
                    ))
            elif block.kind == "list":
                lnum += 1
                block.anchor = f"list{lnum}"
                block.number = lnum
                block.meta["list_type"] = {
                    "1": "terms",
                    "8": "conditions",
                    "A": "objections",
                    "B": "glossary",
                    "C": "systems",
                }.get(sec.num, "list")
                for ii, item in enumerate(block.items, 1):
                    item["anchor"] = f"list{lnum}-{ii}"
                    item["number"] = ii
                    raw_sentences = split_sentences(item["raw"])
                    item["sentences"] = []
                    for si, raw in enumerate(raw_sentences, 1):
                        item["sentences"].append(Sentence(
                            raw=raw,
                            anchor=f"list{lnum}-{ii}-s{si}",
                            number=si,
                            para_anchor=f"list{lnum}-{ii}",
                            para_number=ii,
                        ))
                    thesis_count += len(raw_sentences)
            elif block.kind == "equation":
                eqno += 1
                block.number = eqno
                block.anchor = f"eq-{eqno}"
            elif block.kind == "table":
                tnum += 1
                block.anchor = f"table{tnum}"
                block.number = tnum
        sec.thesis_count = thesis_count
        sec.quote_count = quote_count

    # Собираем ссылки «раздел о …» до построения обратного графа.
    for sec in sections:
        texts: list[str] = []
        for block in sec.blocks:
            if block.kind in ("para", "quote"):
                texts.append(block.raw)
            elif block.kind == "list":
                texts.extend(item["raw"] for item in block.items)
        for text in texts:
            for _, _, target, _ in renderer.find_xrefs(text):
                sec.xref_targets.add(target)

    # Входящие ссылки и первые абзацы.
    for sec in sections:
        for target in sec.xref_targets:
            target_sec = renderer.sections_by_num.get(target)
            if target_sec:
                target_sec.xref_sources.add(sec.num)
        first_para = next((b for b in sec.blocks if b.kind == "para"), None)
        if first_para:
            plain = renderer.render_plain(first_para.raw, sec)
            sec.lead = plain


def section_paragraph_map(sec: Section, renderer: Renderer) -> list[tuple[str, int, str]]:
    items: list[tuple[str, int, str]] = []
    for block in sec.blocks:
        if block.kind == "para":
            plain = renderer.render_plain(block.raw, sec)
            label = plain[:78].rstrip()
            if len(plain) > 78:
                label += "…"
            items.append((block.anchor, block.number, label))
    return items
