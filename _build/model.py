# -*- coding: utf-8 -*-
"""Общая модель собранного сайта."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import config
from .texparse import BibEntry, Quote, Renderer, Section, Term


@dataclass
class Site:
    front: dict[str, Any]
    sections: list[Section]
    bib: list[BibEntry]
    terms: list[Term]
    quotes: list[Quote]
    renderer: Renderer
    objections: list[dict[str, Any]] = field(default_factory=list)
    systems: list[dict[str, Any]] = field(default_factory=list)
    tables: dict[str, str] = field(default_factory=dict)
    theorem_groups: dict[str, str] = field(default_factory=dict)
    build_date: str = ""
    report: dict[str, Any] = field(default_factory=dict)

    @property
    def sections_by_num(self) -> dict[str, Section]:
        return {s.num: s for s in self.sections}

    @property
    def numbered_sections(self) -> list[Section]:
        return [s for s in self.sections if not s.starred]

    @property
    def appendices(self) -> list[Section]:
        return [s for s in self.sections if s.starred]

    @property
    def bib_by_key(self) -> dict[str, BibEntry]:
        return {e.key: e for e in self.bib}

    @property
    def terms_by_id(self) -> dict[str, Term]:
        return {t.id: t for t in self.terms}

    def section(self, num: str) -> Section | None:
        return self.sections_by_num.get(str(num))

    def group_title(self, gid: str) -> str:
        for key, title, _ in config.GROUPS:
            if key == gid:
                return title
        return ""

    def category_name(self, cid: str) -> str:
        return config.CATEGORIES.get(cid, cid)

    def article_url(self, num: str) -> str:
        sec = self.section(num)
        return sec.url if sec else "contents.html"

    def appendix_url(self, num: str) -> str:
        return {"A": "objections.html", "B": "glossary.html", "C": "systems.html"}.get(num, "contents.html")

    def prev_next(self, sec: Section) -> tuple[Section | None, Section | None]:
        for i, s in enumerate(self.sections):
            if s.num == sec.num:
                prev = self.sections[i - 1] if i > 0 else None
                nxt = self.sections[i + 1] if i + 1 < len(self.sections) else None
                return prev, nxt
        return None, None
