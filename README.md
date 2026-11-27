<p align="center">
  <img src="assets/favicon.svg" alt="Пределы обоснования" width="120"/>
</p>

<h1 align="center">Пределы обоснования</h1>

<p align="center">
  Статическая энциклопедия по книге Викулова И. С.<br>
  «О неполноте достаточно сложных формальных систем и пределах имманентного обоснования».
</p>

<p align="center">
  <a href="https://creativecommons.org/licenses/by-nc-nd/4.0/"><img src="https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey.svg" alt="License: CC BY-NC-ND 4.0"/></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3-3776AB?logo=python&amp;logoColor=white" alt="Python 3"/></a>
  <a href="https://pages.github.com/"><img src="https://img.shields.io/badge/GitHub%20Pages-live-222222?logo=githubpages&amp;logoColor=white" alt="GitHub Pages"/></a>
  <a href="https://doi.org/10.5281/zenodo.24498693"><img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.24498693-blue" alt="DOI"/></a>
</p>

<p align="center"><strong>Сайт:</strong> <a href="https://ikhlasulov.github.io/predely/">ikhlasulov.github.io/predely</a></p>

<p align="center">
  <img src="assets/img/cover.webp" alt="Обложка книги «Пределы обоснования»" width="260"/>
</p>

## Что в репозитории

- `index.html`, `contents.html`, `search.html` — главная, содержание и поиск;
- `articles/` — 76 статей по разделам книги;
- `terms/` — словарные статьи;
- `assets/` — CSS, JavaScript, KaTeX, шрифты, поисковый индекс;
- `predely-obosnovaniya.pdf` — готовая книга в PDF;
- `_build/` — генератор сайта на Python.

## Сборка

Генератор читает `book.tex` из пути, заданного переменной окружения
`PREDELY_SOURCE_FILE` (по умолчанию — `source/book.tex`), и пересобирает
статьи, словарь, поисковый индекс и основные страницы:

```bash
PREDELY_SOURCE_FILE=/path/to/book.tex python3 -m _build.build
```

Также можно задать `PREDELY_COVER_FILE`, `PREDELY_COVER_JSON` и
`PREDELY_PDF_FILE`.

Локальный просмотр:

```bash
python3 -m http.server 8000
```

и открыть <http://localhost:8000/>.

## Цитирование

Викулов, И. С. (2026). *О неполноте достаточно сложных формальных систем и пределах имманентного обоснования*. Zenodo. https://doi.org/10.5281/zenodo.24498693

## Лицензия

Текст книги распространяется на условиях
[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/).
